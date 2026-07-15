from __future__ import annotations

import re

PATTERNS = [
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    r"\bsk-[A-Za-z0-9]{20,}\b",
    r"\bgh[posur]_[A-Za-z0-9]{20,}\b",
    r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bAIza[0-9A-Za-z_-]{30,}\b",
    r"\bxai-[A-Za-z0-9]{20,}\b",
    r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
    r"(?im)^\s*(?:export\s+)?[A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD|PRIVATE_KEY|API_KEY|MNEMONIC|SEED)[A-Z0-9_]*\s*[:=]\s*['\"]?[^\s'\"]{6,}",
    r"\[[0-9]{1,3}(?:\s*,\s*[0-9]{1,3}){31,}\]",
]


def compiled(extra: list[str] | None = None) -> list[re.Pattern]:
    pats = list(PATTERNS) + list(extra or [])
    out = []
    for p in pats:
        try:
            out.append(re.compile(p, re.DOTALL))
        except re.error:
            continue
    return out


def redact(text: str, extra: list[str] | None = None) -> tuple[str, int]:
    count = 0
    for rx in compiled(extra):
        text, n = rx.subn("[REDACTED]", text)
        count += n
    return text, count
