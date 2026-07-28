from __future__ import annotations

import json
import os
import sys
import time

BUS_DIR = os.path.expanduser("~/.xyra/bus")


def publish(rec: dict) -> None:
    try:
        os.makedirs(BUS_DIR, exist_ok=True)
        with open(os.path.join(BUS_DIR, "events.jsonl"), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass


class Logger:
    def __init__(self, run_id: str, structured: bool = False):
        self.run_id = run_id
        self.structured = structured

    def event(self, event: str, **fields) -> None:
        rec = {"ts": round(time.time(), 3), "run": self.run_id, "event": event, **fields}
        publish(rec)
        if not self.structured:
            return
        sys.stderr.write(json.dumps(rec) + "\n")
        sys.stderr.flush()

    def say(self, text: str) -> None:
        if not self.structured:
            sys.stdout.write(text)
            sys.stdout.flush()
