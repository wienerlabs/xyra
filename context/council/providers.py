from __future__ import annotations

import subprocess
import time

VENDORS = {
    "grok": {
        "read": ["grok", "--minimal", "--disable-web-search", "-p"],
        "write": ["grok", "--minimal", "--disable-web-search", "--always-approve", "-p"],
        "label": "Grok",
    },
    "claude": {
        "read": ["claude", "-p"],
        "write": ["claude", "-p", "--permission-mode", "acceptEdits"],
        "label": "Claude",
    },
    "local": {
        "read": ["grok", "--minimal", "--disable-web-search", "-m", "grok-composer-2.5-fast", "-p"],
        "write": ["grok", "--minimal", "--disable-web-search", "--always-approve", "-m", "grok-composer-2.5-fast", "-p"],
        "label": "Local",
    },
}


def label(vendor: str) -> str:
    return VENDORS.get(vendor, {}).get("label", vendor)


def run(vendor: str, mode: str, prompt: str, timeout: int, retries: int = 2) -> tuple[str | None, str | None]:
    if vendor not in VENDORS:
        return None, f"unknown vendor: {vendor}"
    argv = list(VENDORS[vendor][mode]) + [prompt]
    last = "no attempt"
    for attempt in range(retries + 1):
        try:
            out = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            last = f"timeout after {timeout}s"
        except FileNotFoundError:
            return None, f"{vendor} binary not found on PATH"
        else:
            if out.returncode == 0:
                return out.stdout.strip(), None
            last = (out.stderr or out.stdout or "nonzero exit").strip()[:400]
        if attempt < retries:
            time.sleep(min(2 ** attempt, 8))
    return None, last
