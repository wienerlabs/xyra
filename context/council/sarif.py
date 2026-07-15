from __future__ import annotations

import json

from . import __version__
from .models import Finding

_LEVEL = {"critical": "error", "high": "error", "medium": "warning", "low": "note"}


def to_sarif(findings: list[Finding]) -> dict:
    rules = {}
    results = []
    for f in findings:
        rule_id = f"xyra-council/{f.lens or 'general'}"
        rules.setdefault(rule_id, {
            "id": rule_id,
            "name": f"council-{f.lens or 'general'}",
            "shortDescription": {"text": f"Council {f.lens or 'general'} lens"},
        })
        result = {
            "ruleId": rule_id,
            "level": _LEVEL.get(f.severity, "note"),
            "message": {"text": f.issue + (f"\nFix: {f.fix}" if f.fix else "")},
            "properties": {"severity": f.severity, "lens": f.lens},
        }
        if f.file:
            result["locations"] = [{
                "physicalLocation": {
                    "artifactLocation": {"uri": f.file},
                    "region": {"startLine": max(1, f.line)},
                }
            }]
        results.append(result)
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{
            "tool": {"driver": {
                "name": "xyra-council",
                "version": __version__,
                "informationUri": "https://github.com/wienerlabs/xyra",
                "rules": list(rules.values()),
            }},
            "results": results,
        }],
    }


def dumps(findings: list[Finding]) -> str:
    return json.dumps(to_sarif(findings), indent=2)
