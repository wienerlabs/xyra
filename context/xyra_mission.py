#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.expanduser("~/.xyra/lib"))

import xyra_bus
import xyra_tools

os.environ.setdefault("XYRA_SESSION", "1")

STATE_NAME = "mission.json"
STOP_NAME = "mission.stop"
LOG_NAME = "mission.log"

VENDOR_ORDER = ["grok", "claude"]
DEFAULT_BUDGET = {
    "max_sessions": 400,
    "max_hours": 12.0,
    "max_attempts_per_ticket": 3,
    "max_consecutive_failures": 5,
    "session_timeout": 3600,
    "max_split_depth": 1,
}


def xyra_dir(root):
    d = os.path.join(os.path.abspath(root), ".xyra")
    os.makedirs(d, exist_ok=True)
    return d


def state_path(root):
    return os.path.join(xyra_dir(root), STATE_NAME)


def stop_path(root):
    return os.path.join(xyra_dir(root), STOP_NAME)


def log_path(root):
    return os.path.join(xyra_dir(root), LOG_NAME)


def load_state(root):
    p = state_path(root)
    if not os.path.exists(p):
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(root, state):
    state["updated_at"] = round(time.time(), 3)
    tmp = state_path(root) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    os.replace(tmp, state_path(root))


def note(root, message):
    line = f"{time.strftime('%H:%M:%S')} {message}"
    print(line, flush=True)
    try:
        with open(log_path(root), "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def git(root, *args, timeout=120):
    return xyra_tools.RUNNER(["git", "-C", root, *args], timeout=timeout)


def head_commit(root):
    code, out = git(root, "rev-parse", "HEAD")
    return out.strip() if code == 0 else None


def working_tree_dirty(root):
    code, out = git(root, "status", "--porcelain")
    if code != 0:
        return False
    lines = [l for l in out.splitlines() if l.strip()]
    return any(".xyra/" not in l for l in lines)


def reset_tree(root):
    git(root, "reset", "--hard")
    git(root, "clean", "-fd", "-e", ".xyra")


def extract_json_array(text):
    block = re.search(r"```json\s*(\[.*?\])\s*```", text, re.DOTALL)
    candidate = block.group(1) if block else None
    if candidate is None:
        arr = re.search(r"\[\s*\{.*\}\s*\]", text, re.DOTALL)
        candidate = arr.group(0) if arr else None
    if candidate is None:
        return []
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def normalize_tickets(raw, prefix="", depth=0):
    tickets = []
    for i, t in enumerate(raw, 1):
        if not isinstance(t, dict):
            continue
        tid = str(t.get("id") or f"{prefix}{i}")
        tickets.append({
            "id": f"{prefix}{tid}" if prefix and not tid.startswith(prefix) else tid,
            "title": str(t.get("title") or "").strip()[:200] or f"ticket {tid}",
            "scope": str(t.get("scope") or "").strip()[:2000],
            "files": [str(f) for f in (t.get("files") or [])][:20],
            "depends_on": [f"{prefix}{d}" if prefix and not str(d).startswith(prefix) else str(d)
                           for d in (t.get("depends_on") or [])],
            "status": "pending",
            "depth": depth,
            "attempts": 0,
            "vendor_index": 0,
            "commit": None,
            "notes": [],
        })
    return tickets


def plan_mission(root, objective, vendor="grok", timeout=1800):
    context = ""
    try:
        import xyra_context
        hits = xyra_context.search(root, objective, k=6)
        context = "\n\n".join(f"{h['path']}:{h['start_line']}\n{h['content'][:800]}" for h in hits)
    except Exception:
        code, out = xyra_tools.RUNNER(["git", "-C", root, "ls-files"], timeout=60)
        context = "\n".join(out.splitlines()[:200]) if code == 0 else ""

    prompt = (
        "You are a staff engineer planning autonomous execution. Break this objective into small, "
        "independently shippable tickets. Each ticket must be completable in one focused session by "
        "an agent that sees only that ticket's brief, and must leave the repository's tests passing.\n\n"
        "Rules: order by dependency, keep each ticket under roughly 400 lines of change, name the real "
        "files it touches, never bundle unrelated work, and include a final ticket that runs the full "
        "test suite and cleans up.\n\n"
        "Respond with exactly one fenced ```json block, no prose. Schema:\n"
        '[{"id": "1", "title": "...", "scope": "what to do, precise enough to act on without asking", '
        '"files": ["path"], "depends_on": []}]\n\n'
        f"Objective: {objective}\n\nRepository context:\n{context[:12000]}"
    )
    code, out = xyra_tools.fixer_run(vendor, prompt, root, timeout=timeout)
    if code != 0:
        raise RuntimeError(f"planner failed: {xyra_tools.tail(out, 8)}")
    tickets = normalize_tickets(extract_json_array(out))
    if not tickets:
        raise RuntimeError("planner returned no tickets")
    return tickets


def split_ticket(root, ticket, failure, vendor="grok", timeout=900):
    prompt = (
        "An autonomous agent failed this ticket repeatedly. Split it into 2 to 4 smaller tickets that "
        "can each succeed on their own, addressing the failure. Respond with exactly one fenced ```json "
        'block: [{"id": "a", "title": "...", "scope": "...", "files": ["..."], "depends_on": []}]\n\n'
        f"Ticket: {ticket['title']}\nScope: {ticket['scope']}\n\nLast failure:\n{failure[:3000]}"
    )
    code, out = xyra_tools.fixer_run(vendor, prompt, root, timeout=timeout)
    if code != 0:
        return []
    return normalize_tickets(extract_json_array(out), prefix=f"{ticket['id']}.",
                             depth=ticket.get("depth", 0) + 1)


def ready_tickets(state):
    done = {t["id"] for t in state["tickets"] if t["status"] == "done"}
    out = []
    for t in state["tickets"]:
        if t["status"] not in ("pending", "retry"):
            continue
        deps = [d for d in t["depends_on"] if d in {x["id"] for x in state["tickets"]}]
        if all(d in done for d in deps):
            out.append(t)
    return out


def ticket_brief(state, ticket):
    done_titles = [f"- {t['id']}: {t['title']}" for t in state["tickets"] if t["status"] == "done"][-8:]
    files = ", ".join(ticket["files"]) if ticket["files"] else "decide from the codebase"
    prior = "\n".join(ticket["notes"][-2:])
    return (
        f"You are executing one ticket of an autonomous mission. Objective of the whole mission: "
        f"{state['objective']}\n\n"
        f"TICKET {ticket['id']}: {ticket['title']}\n"
        f"Scope: {ticket['scope']}\n"
        f"Likely files: {files}\n\n"
        + (f"Already completed:\n" + "\n".join(done_titles) + "\n\n" if done_titles else "")
        + (f"Previous attempt failed with:\n{prior}\n\n" if prior else "")
        + "Rules for this session:\n"
        "- Do the ticket completely, then stop. Do not start other tickets.\n"
        "- Never ask a question; decide and proceed with the most reasonable option.\n"
        "- Never run an interactive command or a server that does not exit.\n"
        "- Leave the repository's tests passing. Do not commit; the supervisor commits.\n"
        "- Follow the wiener-conventions skill: no code comments, no em dashes."
    )


def run_ticket(root, state, ticket, budget, log):
    vendor = VENDOR_ORDER[min(ticket["vendor_index"], len(VENDOR_ORDER) - 1)]
    ticket["status"] = "running"
    ticket["attempts"] += 1
    ticket["started_at"] = round(time.time(), 3)
    save_state(root, state)
    xyra_bus.emit("mission_ticket_start", ticket=ticket["id"], title=ticket["title"],
                  vendor=vendor, attempt=ticket["attempts"])
    log(f"ticket {ticket['id']} [{vendor}] attempt {ticket['attempts']}: {ticket['title']}")

    code, out = xyra_tools.fixer_run(vendor, ticket_brief(state, ticket), root,
                                     timeout=budget["session_timeout"])
    if code != 0:
        return False, f"agent session failed: {xyra_tools.tail(out, 20)}"

    if not working_tree_dirty(root):
        return False, "the session produced no changes"

    log(f"ticket {ticket['id']}: verifying in sandbox")
    xyra_bus.emit("mission_sandbox", ticket=ticket["id"])
    try:
        result = xyra_tools.sandbox_verify(root)
    except RuntimeError as e:
        return False, f"sandbox could not run: {e}"
    if result["ok"] is False:
        step = result["steps"][0]
        return False, f"tests failed ({step['command']}):\n{step['tail']}"
    if result["ok"] is None:
        log(f"ticket {ticket['id']}: no runner detected, accepting on agent completion")
    return True, None


def commit_ticket(root, state, ticket, log):
    git(root, "add", "-A")
    message = (f"feat: {ticket['title']}\n\n{ticket['scope'][:400]}\n\n"
               f"mission {state['id']} ticket {ticket['id']}")
    code, out = git(root, "commit", "-m", message)
    if code != 0 and "nothing to commit" not in out.lower():
        log(f"ticket {ticket['id']}: commit failed: {xyra_tools.tail(out, 5)}")
        return None
    sha = head_commit(root)
    ticket["commit"] = sha
    return sha


def quarantine(root, state, ticket, reason, log):
    ticket["status"] = "quarantined"
    ticket["notes"].append(reason[:1500])
    reset_tree(root)
    log(f"ticket {ticket['id']}: quarantined after {ticket['attempts']} attempts")
    xyra_bus.emit("mission_ticket_quarantined", ticket=ticket["id"], title=ticket["title"])
    save_state(root, state)


def budget_exhausted(state, budget):
    if state["sessions"] >= budget["max_sessions"]:
        return "session budget reached"
    elapsed_h = (time.time() - state["started_at"]) / 3600
    if elapsed_h >= budget["max_hours"]:
        return "time budget reached"
    if state["consecutive_failures"] >= budget["max_consecutive_failures"]:
        return "too many consecutive failures"
    return None


def loop(root, state, log=None):
    log = log or (lambda m: note(root, m))
    budget = state["budget"]
    if os.path.exists(stop_path(root)):
        os.remove(stop_path(root))
    state["status"] = "running"
    save_state(root, state)
    xyra_bus.emit("mission_start", mission=state["id"], objective=state["objective"],
                  tickets=len(state["tickets"]))

    while True:
        if os.path.exists(stop_path(root)):
            state["status"] = "stopped"
            log("stop requested, halting")
            break
        reason = budget_exhausted(state, budget)
        if reason:
            state["status"] = "halted"
            state["halt_reason"] = reason
            log(f"halted: {reason}")
            break

        ready = ready_tickets(state)
        if not ready:
            pending = [t for t in state["tickets"] if t["status"] in ("pending", "retry")]
            if not pending:
                state["status"] = "completed"
                log("all tickets resolved")
                break
            state["status"] = "blocked"
            state["halt_reason"] = "remaining tickets depend on quarantined work"
            log("blocked: remaining tickets depend on quarantined work")
            break

        ticket = ready[0]
        state["current"] = ticket["id"]
        state["sessions"] += 1
        save_state(root, state)

        ok, failure = run_ticket(root, state, ticket, budget, log)
        if ok:
            sha = commit_ticket(root, state, ticket, log)
            ticket["status"] = "done"
            ticket["finished_at"] = round(time.time(), 3)
            state["consecutive_failures"] = 0
            state["done"] = sum(1 for t in state["tickets"] if t["status"] == "done")
            log(f"ticket {ticket['id']}: done" + (f" ({sha[:8]})" if sha else ""))
            xyra_bus.emit("mission_ticket_done", ticket=ticket["id"], title=ticket["title"],
                          commit=(sha or "")[:8])
            xyra_bus.record_decision(root, "mission_ticket", f"{ticket['id']}: {ticket['title']}",
                                     detail={"mission": state["id"]}, commit=sha)
            save_state(root, state)
            continue

        state["consecutive_failures"] += 1
        ticket["notes"].append(failure[:1500])
        log(f"ticket {ticket['id']}: {failure.splitlines()[0][:120] if failure else 'failed'}")
        xyra_bus.emit("mission_ticket_failed", ticket=ticket["id"], attempt=ticket["attempts"])
        reset_tree(root)

        if ticket["attempts"] < budget["max_attempts_per_ticket"]:
            ticket["vendor_index"] += 1
            ticket["status"] = "retry"
            save_state(root, state)
            continue

        if not ticket.get("split_tried") and ticket.get("depth", 0) < budget.get("max_split_depth", 1):
            ticket["split_tried"] = True
            log(f"ticket {ticket['id']}: replanning into smaller tickets")
            xyra_bus.emit("mission_replan", ticket=ticket["id"])
            children = split_ticket(root, ticket, failure or "")
            if children:
                for c in children:
                    c["depends_on"] = list(dict.fromkeys(c["depends_on"] + ticket["depends_on"]))
                idx = state["tickets"].index(ticket)
                state["tickets"][idx + 1:idx + 1] = children
                for t in state["tickets"]:
                    if ticket["id"] in t["depends_on"] and t is not ticket:
                        t["depends_on"] = [d for d in t["depends_on"] if d != ticket["id"]]
                        t["depends_on"] += [c["id"] for c in children]
                ticket["status"] = "split"
                state["consecutive_failures"] = 0
                log(f"ticket {ticket['id']}: split into {len(children)} tickets")
                save_state(root, state)
                continue

        quarantine(root, state, ticket, failure or "unknown failure", log)

    state["current"] = None
    state["finished_at"] = round(time.time(), 3)
    save_state(root, state)
    xyra_bus.emit("mission_end", mission=state["id"], status=state["status"],
                  done=state.get("done", 0), total=len(state["tickets"]))
    return state


def new_state(root, objective, tickets, budget):
    return {
        "id": uuid.uuid4().hex[:8],
        "objective": objective,
        "root": os.path.abspath(root),
        "status": "planned",
        "started_at": round(time.time(), 3),
        "updated_at": round(time.time(), 3),
        "base_commit": head_commit(root),
        "sessions": 0,
        "done": 0,
        "consecutive_failures": 0,
        "current": None,
        "budget": budget,
        "tickets": tickets,
    }


def summarize(state):
    counts = {}
    for t in state["tickets"]:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    total = len([t for t in state["tickets"] if t["status"] != "split"])
    done = counts.get("done", 0)
    return {
        "id": state["id"],
        "status": state["status"],
        "objective": state["objective"],
        "progress": f"{done}/{total}",
        "percent": round(100 * done / total) if total else 0,
        "sessions": state["sessions"],
        "elapsed_min": round((time.time() - state["started_at"]) / 60),
        "counts": counts,
        "current": state.get("current"),
        "halt_reason": state.get("halt_reason"),
    }


def cmd_start(args):
    root = os.path.abspath(args.path)
    objective = " ".join(args.objective).strip()
    if not objective:
        print("usage: xyra-mission start \"<objective>\"", file=sys.stderr)
        return 1
    existing = load_state(root)
    if existing and existing["status"] in ("running",) and not args.force:
        print(f"a mission is already running ({existing['id']}); stop it first", file=sys.stderr)
        return 1
    if working_tree_dirty(root) and not args.force:
        print("working tree is dirty; commit or stash first, or pass --force", file=sys.stderr)
        return 1
    budget = dict(DEFAULT_BUDGET)
    if args.max_hours:
        budget["max_hours"] = args.max_hours
    if args.max_sessions:
        budget["max_sessions"] = args.max_sessions
    note(root, f"planning: {objective}")
    xyra_bus.emit("mission_planning", objective=objective)
    tickets = plan_mission(root, objective, vendor=args.vendor)
    state = new_state(root, objective, tickets, budget)
    save_state(root, state)
    note(root, f"mission {state['id']}: {len(tickets)} tickets planned")
    for t in tickets:
        note(root, f"  {t['id']}. {t['title']}")
    if args.plan_only:
        return 0
    loop(root, state)
    print(json.dumps(summarize(load_state(root)), indent=2, ensure_ascii=False))
    return 0


def cmd_run(args):
    root = os.path.abspath(args.path)
    state = load_state(root)
    if not state:
        print("no mission in this repository; run: xyra-mission start \"<objective>\"", file=sys.stderr)
        return 1
    loop(root, state)
    print(json.dumps(summarize(load_state(root)), indent=2, ensure_ascii=False))
    return 0


def cmd_status(args):
    root = os.path.abspath(args.path)
    state = load_state(root)
    if not state:
        print("no mission in this repository")
        return 1
    if args.json:
        print(json.dumps(summarize(state), indent=2, ensure_ascii=False))
        return 0
    s = summarize(state)
    print(f"mission {s['id']}: {s['status']}  {s['progress']} ({s['percent']}%)")
    print(f"objective: {s['objective']}")
    print(f"sessions: {s['sessions']}, elapsed: {s['elapsed_min']} min")
    if s["halt_reason"]:
        print(f"halted: {s['halt_reason']}")
    print("")
    for t in state["tickets"]:
        mark = {"done": "x", "running": ">", "quarantined": "!", "split": "~"}.get(t["status"], " ")
        print(f"  [{mark}] {t['id']}. {t['title']}"
              + (f"  ({t['status']})" if t["status"] not in ("done", "pending") else ""))
    return 0


def cmd_stop(args):
    root = os.path.abspath(args.path)
    with open(stop_path(root), "w", encoding="utf-8") as f:
        f.write(str(time.time()))
    print("stop requested; the supervisor halts after the current ticket")
    return 0


def cmd_daemon(args):
    root = os.path.abspath(args.path)
    state = load_state(root)
    if not state:
        print("no mission; start one first", file=sys.stderr)
        return 1
    out = open(log_path(root), "a", encoding="utf-8")
    proc = subprocess.Popen([sys.executable, os.path.abspath(__file__), "run", "--path", root],
                            stdout=out, stderr=out, start_new_session=True)
    print(f"supervisor running in the background (pid {proc.pid})")
    print(f"log: {log_path(root)}")
    print("stop with: xyra-mission stop")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="xyra-mission",
                                 description="Autonomous project supervisor: plans, executes, verifies "
                                             "and commits ticket after ticket until the objective is done.")
    ap.add_argument("--path", default=".")
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("start", help="plan and run a mission to completion")
    p.add_argument("objective", nargs="*")
    p.add_argument("--vendor", default="grok")
    p.add_argument("--max-hours", type=float)
    p.add_argument("--max-sessions", type=int)
    p.add_argument("--plan-only", action="store_true")
    p.add_argument("--force", action="store_true")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_start)

    p = sub.add_parser("run", help="resume the mission in this repository")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("status", help="show mission progress")
    p.add_argument("--json", action="store_true")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("stop", help="ask the supervisor to halt")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_stop)

    p = sub.add_parser("daemon", help="run the supervisor in the background")
    p.add_argument("--path", default=".")
    p.set_defaults(func=cmd_daemon)

    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        ap.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
