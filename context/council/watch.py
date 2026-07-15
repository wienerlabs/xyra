from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import subprocess
import sys
import time

from . import audit as audit_mod
from .config import load
from .engine import Council
from .logging import Logger
from .providers import label

QUEUE_DIR = os.path.expanduser("~/.xyra/queue")


def _root(path: str) -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path,
                             capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return os.path.abspath(path)


def diff_hash(root: str) -> tuple[str, bool]:
    out = subprocess.run(["git", "--no-pager", "diff"], cwd=root, capture_output=True, text=True)
    body = out.stdout
    if not body.strip():
        return "", False
    return hashlib.sha256(body.encode("utf-8", "ignore")).hexdigest(), True


def queue_path(root: str) -> str:
    os.makedirs(QUEUE_DIR, exist_ok=True)
    key = hashlib.sha256(root.encode()).hexdigest()[:16]
    return os.path.join(QUEUE_DIR, f"{key}.jsonl")


def enqueue(root: str, record: dict) -> None:
    with open(queue_path(root), "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


def notify(title: str, text: str) -> None:
    try:
        subprocess.run(["osascript", "-e", f'display notification {json.dumps(text)} with title {json.dumps(title)}'],
                       capture_output=True, timeout=10)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass


def review_once(root: str) -> dict | None:
    config = load(root)
    run_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    council = Council(root, config, Logger(run_id, structured=True))
    try:
        verdict, rounds = council.run_review_only(False)
    except RuntimeError:
        return None
    audit_mod.write(root, "background", label(config.builder), label(config.reviewer), run_id, rounds, council.redacted)
    top = [{"severity": f.severity, "lens": f.lens, "file": f.file, "line": f.line, "issue": f.issue}
           for f in verdict.findings[:5]]
    record = {
        "ts": run_id, "verdict": verdict.label,
        "findings": len(verdict.findings), "blocking": len(verdict.blocking),
        "redacted": council.redacted, "top": top,
    }
    enqueue(root, record)
    if verdict.label == "BLOCK":
        notify("Xyra Council", f"{len(verdict.blocking)} blocking finding(s) in {os.path.basename(root)}")
    elif verdict.label == "APPROVE WITH NOTES":
        notify("Xyra Council", f"{len(verdict.findings)} note(s) in {os.path.basename(root)}")
    return record


def watch(root: str, idle: int, poll: int) -> None:
    reviewed = None
    last_change = time.monotonic()
    last_hash, _ = diff_hash(root)
    sys.stderr.write(json.dumps({"event": "watch_start", "root": root, "idle": idle, "poll": poll}) + "\n")
    sys.stderr.flush()
    while True:
        time.sleep(poll)
        h, has = diff_hash(root)
        if not has:
            reviewed = None
            last_hash = ""
            continue
        if h != last_hash:
            last_hash = h
            last_change = time.monotonic()
            continue
        if h != reviewed and (time.monotonic() - last_change) >= idle:
            sys.stderr.write(json.dumps({"event": "review", "hash": h[:12]}) + "\n")
            sys.stderr.flush()
            review_once(root)
            reviewed = h


def show_queue(root: str, limit: int) -> None:
    path = queue_path(root)
    if not os.path.isfile(path):
        print("queue is empty")
        return
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    for line in lines[-limit:]:
        r = json.loads(line)
        print(f"{r['ts']}  {r['verdict']}  {r['findings']} finding(s), {r['blocking']} blocking")
        for t in r.get("top", []):
            loc = t["file"] + (f":{t['line']}" if t.get("line") else "")
            print(f"    [{t['severity']}] ({t['lens']}) {loc} — {t['issue']}")


def install_agent(root: str) -> None:
    bin_path = os.environ.get("XYRA_WATCH_BIN", "/opt/homebrew/bin/xyra-watch")
    plist_dir = os.path.expanduser("~/Library/LaunchAgents")
    os.makedirs(plist_dir, exist_ok=True)
    key = hashlib.sha256(root.encode()).hexdigest()[:8]
    labelname = f"com.wienerlabs.xyra-council.{key}"
    plist = plist_dir + f"/{labelname}.plist"
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>{labelname}</string>
  <key>ProgramArguments</key>
  <array><string>{bin_path}</string><string>{root}</string></array>
  <key>RunAtLoad</key><true/>
  <key>KeepAlive</key><true/>
  <key>StandardErrorPath</key><string>{os.path.expanduser('~/.xyra')}/watch-{key}.log</string>
</dict>
</plist>
"""
    with open(plist, "w", encoding="utf-8") as f:
        f.write(body)
    subprocess.run(["launchctl", "unload", plist], capture_output=True)
    subprocess.run(["launchctl", "load", plist], capture_output=True)
    print(f"background council installed: {plist}")
    print(f"to remove: launchctl unload {plist} && rm {plist}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="xyra-watch", description="Always-on background council for a repository.")
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--idle", type=int, default=300, help="seconds of no change before a review")
    ap.add_argument("--poll", type=int, default=15, help="poll interval seconds")
    ap.add_argument("--queue", action="store_true", help="show queued findings and exit")
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--install-agent", action="store_true", help="install a launchd agent for this repo")
    args = ap.parse_args(argv)
    root = _root(args.path)
    if args.queue:
        show_queue(root, args.limit)
        return 0
    if args.install_agent:
        install_agent(root)
        return 0
    try:
        watch(root, args.idle, args.poll)
    except KeyboardInterrupt:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
