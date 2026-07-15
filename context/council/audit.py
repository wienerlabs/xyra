from __future__ import annotations

import json
import os
import re

from dataclasses import asdict

from .models import Verdict


def _slug(task: str) -> str:
    return re.sub(r"[^a-z0-9-]", "", re.sub(r"\s+", "-", (task or "review").lower()))[:48] or "review"


def write(root: str, task: str, builder: str, reviewer: str, run_id: str,
          rounds: list[Verdict], redacted: int) -> tuple[str, str]:
    docdir = os.path.join(root, "docs", "council")
    os.makedirs(docdir, exist_ok=True)
    base = os.path.join(docdir, f"{run_id}-{_slug(task)}")

    md = [f"# Council: {task or 'uncommitted review'}", "",
          f"run: `{run_id}`  builder: {builder}  reviewer: {reviewer}  redacted secrets: {redacted}", ""]
    for i, v in enumerate(rounds, 1):
        md.append(f"## Round {i}: {v.label}")
        if not v.findings:
            md.append("  no findings")
        for f in v.findings:
            loc = f.file + (f":{f.line}" if f.line else "")
            md.append(f"- **[{f.severity}]** ({f.lens}) {loc} — {f.issue}" + (f"  \n  fix: {f.fix}" if f.fix else ""))
        md.append("")
    md_path = base + ".md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md))

    json_path = base + ".json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({
            "run_id": run_id, "task": task, "builder": builder, "reviewer": reviewer,
            "redacted_secrets": redacted,
            "rounds": [v.to_dict() for v in rounds],
        }, f, indent=2)
    return md_path, json_path
