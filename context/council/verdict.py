from __future__ import annotations

import json
import re

from .models import Finding, LensResult, Verdict

INSTRUCTION = (
    "Respond with exactly one fenced ```json block and nothing else. Schema:\n"
    '{"findings": [{"severity": "critical|high|medium|low", "file": "path", '
    '"line": 0, "issue": "one sentence", "fix": "concrete remedy"}], '
    '"summary": "one line"}\n'
    "Empty findings array means clean. Be specific and terse. Do not invent issues to look thorough."
)


def parse(text: str, lens: str) -> LensResult:
    if not text:
        return LensResult(lens=lens, error="empty response")
    block = re.search(r"```json\s*(.+?)```", text, re.DOTALL)
    candidate = block.group(1) if block else None
    if candidate is None:
        brace = re.search(r"\{.*\}", text, re.DOTALL)
        candidate = brace.group(0) if brace else None
    if candidate is None:
        return LensResult(lens=lens, error="no json", summary=text[:300])
    try:
        data = json.loads(candidate)
    except json.JSONDecodeError:
        return LensResult(lens=lens, error="invalid json", summary=text[:300])
    findings = []
    for f in data.get("findings") or []:
        findings.append(Finding(
            severity=f.get("severity", "low"),
            issue=f.get("issue", ""),
            file=f.get("file", ""),
            line=f.get("line", 0),
            fix=f.get("fix", ""),
            lens=lens,
        ).normalized())
    return LensResult(lens=lens, findings=findings, summary=str(data.get("summary", "")).strip())


def decide(results: list[LensResult], block_on: list[str]) -> Verdict:
    findings: list[Finding] = []
    for r in results:
        findings.extend(r.findings)
    findings.sort(key=lambda f: -f.rank())
    block_set = {s.lower() for s in block_on}
    blocking = [f for f in findings if f.severity in block_set]
    errored = any(r.error for r in results)
    if blocking:
        label = "BLOCK"
    elif findings:
        label = "APPROVE WITH NOTES"
    elif errored:
        label = "INCONCLUSIVE"
    else:
        label = "CLEAN"
    return Verdict(label=label, findings=findings, results=results, blocking=blocking)
