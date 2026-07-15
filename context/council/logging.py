from __future__ import annotations

import json
import sys
import time


class Logger:
    def __init__(self, run_id: str, structured: bool = False):
        self.run_id = run_id
        self.structured = structured

    def event(self, event: str, **fields) -> None:
        if not self.structured:
            return
        rec = {"ts": round(time.time(), 3), "run": self.run_id, "event": event, **fields}
        sys.stderr.write(json.dumps(rec) + "\n")
        sys.stderr.flush()

    def say(self, text: str) -> None:
        if not self.structured:
            sys.stdout.write(text)
            sys.stdout.flush()
