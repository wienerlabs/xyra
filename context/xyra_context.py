#!/usr/bin/env python3
import hashlib
import json
import os
import sqlite3
import sys
import urllib.request

import numpy as np

OLLAMA_URL = os.environ.get("XYRA_OLLAMA_URL", "http://localhost:11434")
EMBED_MODEL = os.environ.get("XYRA_EMBED_MODEL", "nomic-embed-text")
CACHE_DIR = os.path.expanduser("~/.cache/xyra-context")

CODE_EXT = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".rs", ".go", ".py", ".rb",
    ".java", ".kt", ".swift", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".php",
    ".sol", ".move", ".sql", ".sh", ".bash", ".zsh", ".toml", ".yaml", ".yml",
    ".json", ".md", ".mdx", ".vue", ".svelte", ".css", ".scss", ".proto",
}
IGNORE_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", "target", ".turbo",
    ".venv", "venv", "__pycache__", ".pnpm-store", ".cache", "vendor",
    "coverage", ".idea", ".vscode", "Pods", "DerivedData",
}
CHUNK_LINES = 60
CHUNK_OVERLAP = 12
MAX_FILE_BYTES = 400_000


def repo_db(root):
    os.makedirs(CACHE_DIR, exist_ok=True)
    key = hashlib.sha256(os.path.abspath(root).encode()).hexdigest()[:16]
    db = sqlite3.connect(os.path.join(CACHE_DIR, f"{key}.db"))
    db.execute(
        "CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, hash TEXT)"
    )
    db.execute(
        "CREATE TABLE IF NOT EXISTS chunks ("
        "path TEXT, start INTEGER, end INTEGER, content TEXT, emb BLOB)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS chunks_path ON chunks(path)")
    return db


def embed(texts):
    out = []
    for t in texts:
        body = json.dumps({"model": EMBED_MODEL, "prompt": t}).encode()
        req = urllib.request.Request(
            f"{OLLAMA_URL}/api/embeddings", data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=120) as r:
            out.append(json.loads(r.read())["embedding"])
    arr = np.array(out, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1
    return arr / norms


def iter_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in CODE_EXT:
                yield os.path.join(dirpath, fn)


def chunk_file(path):
    try:
        if os.path.getsize(path) > MAX_FILE_BYTES:
            return None, []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except OSError:
        return None, []
    h = hashlib.sha256("".join(lines).encode("utf-8", "ignore")).hexdigest()
    chunks = []
    i = 0
    step = CHUNK_LINES - CHUNK_OVERLAP
    while i < len(lines):
        window = lines[i:i + CHUNK_LINES]
        text = "".join(window).strip()
        if text:
            chunks.append((i + 1, min(i + CHUNK_LINES, len(lines)), "".join(window)))
        i += step
    return h, chunks


def index(root, log=lambda m: None):
    root = os.path.abspath(root)
    db = repo_db(root)
    seen = set()
    known = dict(db.execute("SELECT path, hash FROM files").fetchall())
    n_new = n_skip = 0
    for path in iter_files(root):
        rel = os.path.relpath(path, root)
        seen.add(rel)
        h, chunks = chunk_file(path)
        if h is None:
            continue
        if known.get(rel) == h:
            n_skip += 1
            continue
        db.execute("DELETE FROM chunks WHERE path=?", (rel,))
        if chunks:
            embs = embed([c[2] for c in chunks])
            db.executemany(
                "INSERT INTO chunks (path,start,end,content,emb) VALUES (?,?,?,?,?)",
                [(rel, c[0], c[1], c[2], embs[j].tobytes()) for j, c in enumerate(chunks)],
            )
        db.execute("INSERT OR REPLACE INTO files (path,hash) VALUES (?,?)", (rel, h))
        n_new += 1
        log(f"indexed {rel} ({len(chunks)} chunks)")
    for rel in set(known) - seen:
        db.execute("DELETE FROM chunks WHERE path=?", (rel,))
        db.execute("DELETE FROM files WHERE path=?", (rel,))
    db.commit()
    total = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    db.close()
    return {"indexed": n_new, "unchanged": n_skip, "total_chunks": total}


def search(root, query, k=8):
    root = os.path.abspath(root)
    db = repo_db(root)
    rows = db.execute("SELECT path,start,end,content,emb FROM chunks").fetchall()
    db.close()
    if not rows:
        return []
    mat = np.stack([np.frombuffer(r[4], dtype=np.float32) for r in rows])
    q = embed([query])[0]
    scores = mat @ q
    top = np.argsort(-scores)[:k]
    results = []
    for idx in top:
        p, s, e, content, _ = rows[idx]
        results.append({
            "path": p, "start_line": int(s), "end_line": int(e),
            "score": round(float(scores[idx]), 4),
            "content": content if len(content) < 2000 else content[:2000] + "\n...",
        })
    return results


TOOLS = [
    {
        "name": "code_index",
        "description": "Index a repository for semantic code search. Incremental: only re-embeds changed files. Run once per repo, and again after large changes.",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "Absolute path to the repository root"}},
            "required": ["path"],
        },
    },
    {
        "name": "code_search",
        "description": "Semantic search over an indexed repository. Returns the most relevant code chunks with file paths and line ranges, ranked by meaning rather than keywords. Prefer this over grep for finding where a concept, behavior, or feature lives.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the repository root"},
                "query": {"type": "string", "description": "Natural-language description of the code you are looking for"},
                "k": {"type": "integer", "description": "Number of results (default 8)"},
            },
            "required": ["path", "query"],
        },
    },
]


def rpc_send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def run_mcp():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = msg.get("method")
        mid = msg.get("id")
        if method == "initialize":
            rpc_send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "xyra-context", "version": "0.1.0"},
            }})
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            rpc_send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            params = msg.get("params", {})
            name = params.get("name")
            args = params.get("arguments", {})
            try:
                if name == "code_index":
                    res = index(args["path"])
                    text = f"Indexed: {res['indexed']} files, {res['unchanged']} unchanged, {res['total_chunks']} total chunks."
                elif name == "code_search":
                    res = search(args["path"], args["query"], int(args.get("k", 8)))
                    if not res:
                        text = "No results. Run code_index on this repository first."
                    else:
                        parts = []
                        for r in res:
                            parts.append(f"{r['path']}:{r['start_line']}-{r['end_line']} (score {r['score']})\n{r['content']}")
                        text = "\n\n---\n\n".join(parts)
                else:
                    raise ValueError(f"unknown tool: {name}")
                rpc_send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}]}})
            except Exception as e:
                rpc_send({"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": f"error: {e}"}], "isError": True}})
        elif mid is not None:
            rpc_send({"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found"}})


def main():
    if len(sys.argv) < 2:
        print("usage: xyra_context.py {mcp|index <path>|search <path> <query>}", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "mcp":
        run_mcp()
    elif cmd == "index":
        res = index(sys.argv[2], log=lambda m: print(m, file=sys.stderr))
        print(json.dumps(res, indent=2))
    elif cmd == "search":
        for r in search(sys.argv[2], " ".join(sys.argv[3:])):
            print(f"{r['path']}:{r['start_line']}-{r['end_line']} (score {r['score']})")
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
