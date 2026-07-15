from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys

from . import providers
from .config import load
from .engine import Council
from .logging import Logger


def _root(path: str) -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path,
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return os.path.abspath(path)


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", re.sub(r"\s+", "-", text.lower()))[:48] or "project"


def _context(root: str, objective: str) -> str:
    ctx = os.environ.get("XYRA_CONTEXT_BIN", "xyra-context")
    try:
        subprocess.run([ctx, "index", root], capture_output=True, timeout=180)
        out = subprocess.run([ctx, "search", root, objective], capture_output=True, text=True, timeout=60)
        return out.stdout.strip()[:5000]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return ""


def _extract_array(text: str):
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


def _toposort(tickets):
    by_id = {str(t.get("id")): t for t in tickets if t.get("id") is not None}
    visited, order, temp = set(), [], set()

    def visit(tid):
        if tid in visited or tid not in by_id:
            return
        if tid in temp:
            return
        temp.add(tid)
        for dep in by_id[tid].get("depends_on", []) or []:
            visit(str(dep))
        temp.discard(tid)
        visited.add(tid)
        order.append(by_id[tid])

    for tid in by_id:
        visit(tid)
    remaining = [t for t in tickets if str(t.get("id")) not in {str(x.get("id")) for x in order}]
    return order + remaining


def design(root, config, objective, log):
    builder, panel = config.builder, config.panel()
    ctx = _context(root, objective)
    log.say(f"== {providers.label(builder)} drafts the design ==\n")
    draft, err = providers.run(builder, "read", (
        "You are a staff engineer. Produce a concise design doc for this objective, grounded in the "
        "actual codebase paths below. Do not write code. Sections in order: Goal, Affected components "
        "(real file paths), Approach, Rollout and risks, Testing, Tickets (dependency-ordered).\n\n"
        f"Objective: {objective}\n\nRelevant code context:\n{ctx}"
    ), config.timeout, config.retries)
    if err:
        raise RuntimeError(f"{providers.label(builder)} failed: {err}")

    challenges = []
    for rv in panel:
        log.say(f"== {providers.label(rv)} challenges the design ==\n")
        text, cerr = providers.run(rv, "read", (
            "You are a skeptical principal engineer from a rival vendor. Challenge this design hard: "
            "hidden risks, missing components, a simpler alternative, wrong ticket ordering or "
            "dependencies, scope creep, money and Solana safety (integer units, address poisoning). "
            f"Be specific and terse.\n\nDesign:\n{draft}"
        ), config.timeout, config.retries)
        if not cerr and text:
            challenges.append(f"### {providers.label(rv)}\n{text}")

    log.say(f"== {providers.label(builder)} finalizes ==\n")
    final, ferr = providers.run(builder, "read", (
        "Incorporate the valid challenges into a final design doc, ignore the noise. Keep the section "
        f"structure. Objective: {objective}\n\nDraft:\n{draft}\n\nChallenges:\n"
        + "\n\n".join(challenges)
    ), config.timeout, config.retries)
    if ferr:
        final = draft
    return final, challenges


def tickets_from(config, final, objective):
    text, err = providers.run(config.builder, "read", (
        "Extract the tickets from this design as a JSON array. Respond with exactly one fenced ```json "
        'block. Schema: [{"id": "1", "title": "...", "scope": "...", "files": ["..."], "depends_on": ["id"]}]'
        f"\n\nObjective: {objective}\n\nDesign:\n{final}"
    ), config.timeout, config.retries)
    if err:
        return []
    return _toposort(_extract_array(text))


def write_doc(root, run_id, objective, builder, panel, final, challenges, tickets):
    docdir = os.path.join(root, "docs", "cosmos")
    os.makedirs(docdir, exist_ok=True)
    path = os.path.join(docdir, f"{run_id}-{_slug(objective)}.md")
    parts = [f"# Cosmos design: {objective}", "",
             f"run: `{run_id}`  {builder} wrote, {', '.join(panel)} challenged. Review before executing.", "",
             final, "", "## Tickets (parsed)", ""]
    for t in tickets:
        dep = ", ".join(str(d) for d in t.get("depends_on", []) or []) or "none"
        parts.append(f"- **{t.get('id')}. {t.get('title', '')}** (depends: {dep})  \n  {t.get('scope', '')}")
    parts += ["", "---", "## Rival challenge (for the record)", ""] + challenges
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    return path


def execute(root, config, tickets, force, log):
    council = Council(root, config, log)
    summary = []
    for t in tickets:
        title = f"{t.get('title', '')}: {t.get('scope', '')}".strip(": ")
        log.say(f"\n===== ticket {t.get('id')}: {t.get('title', '')} =====\n")
        try:
            verdict, _ = council.run_task(title)
        except RuntimeError as e:
            log.say(f"ticket {t.get('id')} failed: {e}\n")
            summary.append((t.get("id"), "FAILED"))
            if not force:
                break
            continue
        summary.append((t.get("id"), verdict.label))
        if verdict.label == "BLOCK" and not force:
            log.say(f"\nticket {t.get('id')} blocked by council. Stopping. Use --force to continue.\n")
            break
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="xyra-cosmos", description="Project-scale council: design, challenge, tickets, optional execution.")
    ap.add_argument("objective", nargs="*")
    ap.add_argument("--by", help="designing vendor override")
    ap.add_argument("--review", help="challenging vendor override")
    ap.add_argument("--reviewers")
    ap.add_argument("--execute", action="store_true", help="execute the tickets through the council")
    ap.add_argument("--force", action="store_true", help="keep executing past a blocked ticket")
    ap.add_argument("--path", default=".")
    ap.add_argument("--log-json", action="store_true")
    args = ap.parse_args(argv)

    objective = " ".join(args.objective).strip()
    if not objective:
        sys.stderr.write("xyra-cosmos: provide a project objective\n")
        return 1
    root = _root(args.path)
    overrides = {}
    if args.by:
        overrides["builder"] = args.by
    if args.review:
        overrides["reviewer"] = args.review
    if args.reviewers:
        overrides["reviewers"] = [x.strip() for x in args.reviewers.split(",") if x.strip()]
    try:
        config = load(root, overrides)
    except ValueError as e:
        sys.stderr.write(f"xyra-cosmos: {e}\n")
        return 1

    run_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log = Logger(run_id, structured=args.log_json)
    final, challenges = design(root, config, objective, log)
    tickets = tickets_from(config, final, objective)
    path = write_doc(root, run_id, objective, providers.label(config.builder),
                     [providers.label(p) for p in config.panel()], final, challenges, tickets)
    log.say(f"\ndesign: {os.path.relpath(path, root)}  ({len(tickets)} tickets parsed)\n")

    if args.execute:
        if not tickets:
            log.say("no tickets parsed; review the design and run tickets manually with xyra-council\n")
            return 1
        log.say("\n== executing tickets through the council (mutates the working tree) ==\n")
        summary = execute(root, config, tickets, args.force, log)
        log.say("\n== execution summary ==\n")
        for tid, label in summary:
            log.say(f"  ticket {tid}: {label}\n")
        blocked = any(l in ("BLOCK", "FAILED") for _, l in summary)
        return 2 if blocked else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
