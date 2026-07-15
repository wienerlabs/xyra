from __future__ import annotations

import hashlib
import json
import os
import time

from . import __version__
from .models import Finding, LensResult

CACHE_DIR = os.path.expanduser("~/.cache/xyra-council")


def key(vendor: str, lens: str, prompt_body: str, diff: str) -> str:
    h = hashlib.sha256()
    h.update(f"{__version__}\0{vendor}\0{lens}\0".encode())
    h.update(prompt_body.encode("utf-8", "ignore"))
    h.update(b"\0")
    h.update(diff.encode("utf-8", "ignore"))
    return h.hexdigest()


def get(k: str) -> LensResult | None:
    path = os.path.join(CACHE_DIR, k + ".json")
    if not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    findings = [Finding(**f) for f in data.get("findings", [])]
    return LensResult(lens=data["lens"], findings=findings, summary=data.get("summary", ""), error=data.get("error", ""))


def put(k: str, result: LensResult) -> None:
    if result.error:
        return
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, k + ".json")
    payload = {
        "lens": result.lens,
        "summary": result.summary,
        "findings": [f.__dict__ for f in result.findings],
        "cached_at": int(time.time()),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    os.replace(tmp, path)
