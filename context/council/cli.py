from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import sys

from . import audit as audit_mod
from . import config as config_mod
from . import sarif as sarif_mod
from .engine import Council
from .logging import Logger
from .models import Verdict
from .providers import VENDORS, label


def _root() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return os.getcwd()


def _render(v: Verdict) -> str:
    if not v.findings:
        return "  no findings\n"
    lines = []
    for f in v.findings:
        loc = f.file + (f":{f.line}" if f.line else "")
        lines.append(f"  [{f.severity}] ({f.lens}) {loc}\n    {f.issue}")
        if f.fix:
            lines.append(f"    fix: {f.fix}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="xyra-council",
        description="Enterprise cross-vendor adversarial coding. One vendor writes, a rival "
                    "cross-examines through parallel lenses under a policy gate, with secret "
                    "redaction, caching, SARIF output and an audit trail.",
    )
    ap.add_argument("task", nargs="*")
    ap.add_argument("--by", choices=VENDORS)
    ap.add_argument("--review", choices=VENDORS)
    ap.add_argument("--reviewers", help="comma-separated reviewer panel, e.g. claude,local")
    ap.add_argument("--consensus", choices=["any", "majority"])
    ap.add_argument("--lenses")
    ap.add_argument("--rounds", type=int)
    ap.add_argument("--timeout", type=int)
    ap.add_argument("--review-only", action="store_true")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--no-redact", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--sarif", metavar="PATH", help="write SARIF report to PATH")
    ap.add_argument("--log-json", action="store_true", help="structured logs to stderr")
    args = ap.parse_args(argv)

    root = _root()
    overrides = {}
    if args.by:
        overrides["builder"] = args.by
    if args.review:
        overrides["reviewer"] = args.review
    if args.reviewers:
        overrides["reviewers"] = [x.strip() for x in args.reviewers.split(",") if x.strip()]
    if args.consensus:
        overrides["consensus"] = args.consensus
    if args.lenses:
        overrides["lenses"] = [x.strip() for x in args.lenses.split(",") if x.strip()]
    if args.rounds is not None:
        overrides["rounds"] = args.rounds
    if args.timeout is not None:
        overrides["timeout"] = args.timeout
    if args.no_cache:
        overrides["cache_enabled"] = False
    if args.no_redact:
        overrides["redact_enabled"] = False

    try:
        config = config_mod.load(root, overrides)
    except ValueError as e:
        sys.stderr.write(f"xyra-council: {e}\n")
        return 1

    task = " ".join(args.task).strip()
    if not args.review_only and not task:
        sys.stderr.write("xyra-council: provide a task, or use --review-only\n")
        return 1

    run_id = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    log = Logger(run_id, structured=args.log_json)
    council = Council(root, config, log)

    try:
        panel_label = "/".join(label(p) for p in config.panel())
        if args.review_only:
            log.say(f"== {panel_label} reviews your changes ({len(config.lenses)} lenses, policy-gated) ==\n")
            final, rounds = council.run_review_only(args.staged)
        else:
            final, rounds = council.run_task(task)
    except RuntimeError as e:
        sys.stderr.write(f"xyra-council: {e}\n")
        return 1

    log.say(f"\nverdict: {final.label}\n{_render(final)}")
    md_path, json_path = audit_mod.write(root, task, label(config.builder), panel_label, run_id, rounds, council.redacted)
    log.say(f"\naudit: {os.path.relpath(md_path, root)}  (json: {os.path.relpath(json_path, root)})\n")
    if council.redacted:
        log.say(f"redacted {council.redacted} secret(s) before review\n")

    if args.sarif:
        with open(args.sarif, "w", encoding="utf-8") as f:
            f.write(sarif_mod.dumps(final.findings))
        log.say(f"sarif: {args.sarif}\n")

    if args.json:
        print(json.dumps({
            "run_id": run_id,
            "verdict": final.label,
            "rounds": len(rounds),
            "redacted_secrets": council.redacted,
            "findings": [f.__dict__ for f in final.findings],
            "audit": {"markdown": md_path, "json": json_path},
        }, indent=2))

    return 0 if final.ok() else 2
