from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

SEVERITIES = ("critical", "high", "medium", "low")
SEVERITY_ORDER = {s: i for i, s in enumerate(reversed(SEVERITIES))}


@dataclass
class Finding:
    severity: str
    issue: str
    file: str = ""
    line: int = 0
    fix: str = ""
    lens: str = ""

    def normalized(self) -> "Finding":
        sev = str(self.severity).lower()
        if sev not in SEVERITY_ORDER:
            sev = "low"
        return Finding(
            severity=sev,
            issue=str(self.issue).strip(),
            file=str(self.file).strip(),
            line=int(self.line) if str(self.line).isdigit() else 0,
            fix=str(self.fix).strip(),
            lens=str(self.lens).strip(),
        )

    def rank(self) -> int:
        return SEVERITY_ORDER.get(self.severity, 0)


@dataclass
class LensResult:
    lens: str
    findings: list[Finding] = field(default_factory=list)
    summary: str = ""
    error: str = ""


@dataclass
class Verdict:
    label: str
    findings: list[Finding] = field(default_factory=list)
    results: list[LensResult] = field(default_factory=list)
    blocking: list[Finding] = field(default_factory=list)

    def ok(self) -> bool:
        return self.label in ("CLEAN", "APPROVE WITH NOTES")

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "findings": [asdict(f) for f in self.findings],
            "blocking": [asdict(f) for f in self.blocking],
            "lens_errors": {r.lens: r.error for r in self.results if r.error},
        }


@dataclass
class PolicyRule:
    paths: list[str]
    require: list[str] = field(default_factory=list)
    block_on: list[str] = field(default_factory=list)


@dataclass
class Config:
    builder: str = "grok"
    reviewer: str = "claude"
    lenses: list[str] = field(default_factory=lambda: ["correctness", "security", "conventions"])
    rounds: int = 2
    timeout: int = 900
    retries: int = 2
    block_on: list[str] = field(default_factory=lambda: ["critical", "high"])
    rules: list[PolicyRule] = field(default_factory=list)
    cache_enabled: bool = True
    redact_enabled: bool = True
    custom_lenses: dict[str, str] = field(default_factory=dict)
    redact_patterns: list[str] = field(default_factory=list)
