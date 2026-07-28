#!/usr/bin/env python3
import json
import os
import time

BUS_DIR = os.path.expanduser("~/.xyra/bus")
JOURNAL_NAME = "journal.jsonl"


def stream_path(root=None):
    os.makedirs(BUS_DIR, exist_ok=True)
    return os.path.join(BUS_DIR, "events.jsonl")


def journal_path(root):
    d = os.path.join(os.path.abspath(root), ".xyra")
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, JOURNAL_NAME)


def emit(event, **fields):
    rec = {"ts": round(time.time(), 3), "event": event, **fields}
    try:
        with open(stream_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    return rec


def record_decision(root, kind, summary, detail=None, commit=None):
    rec = {"ts": round(time.time(), 3), "kind": kind, "summary": summary,
           "detail": detail or {}, "commit": commit}
    try:
        with open(journal_path(root), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        pass
    emit("decision", kind=kind, summary=summary, root=os.path.abspath(root))
    return rec


def read_events(limit=500, since=None):
    path = stream_path()
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if since and rec.get("ts", 0) <= since:
                continue
            out.append(rec)
    return out[-limit:]


def read_journal(root, limit=200):
    path = os.path.join(os.path.abspath(root), ".xyra", JOURNAL_NAME)
    if not os.path.exists(path):
        return []
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out[-limit:]


def clear():
    path = stream_path()
    if os.path.exists(path):
        os.remove(path)
