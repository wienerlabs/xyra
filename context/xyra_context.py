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
    db.execute(
        "CREATE TABLE IF NOT EXISTS symbols (path TEXT, name TEXT, kind TEXT, line INTEGER)"
    )
    db.execute("CREATE INDEX IF NOT EXISTS symbols_name ON symbols(name)")
    db.execute("CREATE TABLE IF NOT EXISTS imports_raw (path TEXT, spec TEXT)")
    db.execute("CREATE TABLE IF NOT EXISTS edges (src TEXT, dst TEXT)")
    db.execute("CREATE INDEX IF NOT EXISTS edges_dst ON edges(dst)")
    return db


def try_embed(texts, warn=[False]):
    try:
        return embed(texts)
    except Exception as e:
        if not warn[0]:
            warn[0] = True
            print(f"embeddings unavailable ({e}); indexing graph only", file=sys.stderr)
        return None


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
    return h, chunks, lines


import re

TS_EXTS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")
TS_IMPORT = re.compile(r"""(?:import|export)\s[^;]*?from\s+['"]([^'"]+)['"]|require\(\s*['"]([^'"]+)['"]\s*\)""")
TS_SYMBOL = re.compile(r"^\s*export\s+(?:default\s+)?(?:async\s+)?(function|class|interface|type|enum|const|let|var)\s+([A-Za-z_$][\w$]*)")
PY_IMPORT = re.compile(r"^\s*(?:from\s+([\w.]+)\s+import|import\s+([\w.]+))")
PY_SYMBOL = re.compile(r"^\s*(?:async\s+)?(def|class)\s+([A-Za-z_]\w*)")
RS_MOD = re.compile(r"^\s*(?:pub\s+)?mod\s+([a-z_][a-z0-9_]*)\s*;")
RS_USE = re.compile(r"^\s*(?:pub\s+)?use\s+([\w:]+)")
RS_SYMBOL = re.compile(r"^\s*pub(?:\([^)]*\))?\s+(?:async\s+)?(fn|struct|enum|trait|type|const)\s+([A-Za-z_]\w*)")


def parse_file(rel, lines):
    ext = os.path.splitext(rel)[1].lower()
    symbols, specs = [], []
    if ext in TS_EXTS:
        for i, line in enumerate(lines, 1):
            m = TS_SYMBOL.match(line)
            if m:
                symbols.append((m.group(2), m.group(1), i))
            for m in TS_IMPORT.finditer(line):
                spec = m.group(1) or m.group(2)
                if spec and spec.startswith("."):
                    specs.append("ts:" + spec)
    elif ext == ".py":
        for i, line in enumerate(lines, 1):
            m = PY_SYMBOL.match(line)
            if m:
                symbols.append((m.group(2), m.group(1), i))
            m = PY_IMPORT.match(line)
            if m:
                specs.append("py:" + (m.group(1) or m.group(2)))
    elif ext == ".rs":
        for i, line in enumerate(lines, 1):
            m = RS_SYMBOL.match(line)
            if m:
                symbols.append((m.group(2), m.group(1), i))
            m = RS_MOD.match(line)
            if m:
                specs.append("rsmod:" + m.group(1))
            m = RS_USE.match(line)
            if m and m.group(1).startswith("crate::"):
                specs.append("rsuse:" + m.group(1))
    return symbols, specs


def resolve_spec(rel, tagged, files):
    kind, spec = tagged.split(":", 1)
    base = os.path.dirname(rel)
    if kind == "ts":
        target = os.path.normpath(os.path.join(base, spec)).replace(os.sep, "/")
        candidates = [target + e for e in TS_EXTS] + [target] + [
            target + "/index" + e for e in TS_EXTS]
        for c in candidates:
            if c in files:
                return c
    elif kind == "py":
        mod = spec.replace(".", "/")
        for prefix in ("", "src/"):
            for c in (f"{prefix}{mod}.py", f"{prefix}{mod}/__init__.py"):
                if c in files:
                    return c
    elif kind == "rsmod":
        for c in (f"{base}/{spec}.rs", f"{base}/{spec}/mod.rs"):
            c = c.lstrip("/")
            if c in files:
                return c
    elif kind == "rsuse":
        parts = spec.split("::")[1:]
        crate_root = base
        while crate_root and f"{crate_root}/Cargo.toml" not in files and "/" in crate_root:
            crate_root = crate_root.rsplit("/", 1)[0]
        if crate_root.endswith("/src"):
            crate_root = crate_root[:-4]
        src = f"{crate_root}/src" if crate_root else "src"
        for depth in range(len(parts), 0, -1):
            c = src + "/" + "/".join(parts[:depth]) + ".rs"
            if c in files:
                return c
            c = src + "/" + "/".join(parts[:depth]) + "/mod.rs"
            if c in files:
                return c
    return None


def rebuild_edges(db, root):
    all_files = {r[0] for r in db.execute("SELECT path FROM files").fetchall()}
    extra = set()
    for rel in list(all_files):
        d = os.path.dirname(rel)
        while d:
            extra.add(d + "/Cargo.toml")
            d = os.path.dirname(d)
    for e in extra:
        if os.path.exists(os.path.join(root, e)):
            all_files.add(e)
    db.execute("DELETE FROM edges")
    rows = db.execute("SELECT path, spec FROM imports_raw").fetchall()
    edges = set()
    for rel, tagged in rows:
        dst = resolve_spec(rel, tagged, all_files)
        if dst and dst != rel:
            edges.add((rel, dst))
    db.executemany("INSERT INTO edges (src, dst) VALUES (?,?)", sorted(edges))
    return len(edges)


def index(root, log=lambda m: None):
    root = os.path.abspath(root)
    db = repo_db(root)
    seen = set()
    known = dict(db.execute("SELECT path, hash FROM files").fetchall())
    n_new = n_skip = 0
    for path in iter_files(root):
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        seen.add(rel)
        h, chunks, lines = chunk_file(path)
        if h is None:
            continue
        if known.get(rel) == h:
            n_skip += 1
            continue
        db.execute("DELETE FROM chunks WHERE path=?", (rel,))
        db.execute("DELETE FROM symbols WHERE path=?", (rel,))
        db.execute("DELETE FROM imports_raw WHERE path=?", (rel,))
        if chunks:
            embs = try_embed([c[2] for c in chunks])
            db.executemany(
                "INSERT INTO chunks (path,start,end,content,emb) VALUES (?,?,?,?,?)",
                [(rel, c[0], c[1], c[2],
                  embs[j].tobytes() if embs is not None else b"")
                 for j, c in enumerate(chunks)],
            )
        symbols, specs = parse_file(rel, lines)
        if symbols:
            db.executemany(
                "INSERT INTO symbols (path,name,kind,line) VALUES (?,?,?,?)",
                [(rel, s[0], s[1], s[2]) for s in symbols],
            )
        if specs:
            db.executemany(
                "INSERT INTO imports_raw (path,spec) VALUES (?,?)",
                [(rel, s) for s in specs],
            )
        db.execute("INSERT OR REPLACE INTO files (path,hash) VALUES (?,?)", (rel, h))
        n_new += 1
        log(f"indexed {rel} ({len(chunks)} chunks, {len(symbols)} symbols)")
    for rel in set(known) - seen:
        db.execute("DELETE FROM chunks WHERE path=?", (rel,))
        db.execute("DELETE FROM symbols WHERE path=?", (rel,))
        db.execute("DELETE FROM imports_raw WHERE path=?", (rel,))
        db.execute("DELETE FROM files WHERE path=?", (rel,))
    n_edges = rebuild_edges(db, root)
    db.commit()
    total = db.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
    n_sym = db.execute("SELECT COUNT(*) FROM symbols").fetchone()[0]
    db.close()
    return {"indexed": n_new, "unchanged": n_skip, "total_chunks": total,
            "symbols": n_sym, "import_edges": n_edges}


def search(root, query, k=8):
    root = os.path.abspath(root)
    db = repo_db(root)
    results = []
    if re.fullmatch(r"[A-Za-z_$][\w$]*", query.strip()):
        for p, name, kind, line in db.execute(
                "SELECT path,name,kind,line FROM symbols WHERE name=? LIMIT 5",
                (query.strip(),)).fetchall():
            results.append({
                "path": p, "start_line": int(line), "end_line": int(line),
                "score": 1.0, "content": f"{kind} {name} is defined here",
            })
    rows = [r for r in db.execute(
        "SELECT path,start,end,content,emb FROM chunks").fetchall() if r[4]]
    db.close()
    if not rows:
        return results
    mat = np.stack([np.frombuffer(r[4], dtype=np.float32) for r in rows])
    q = embed([query])[0]
    scores = mat @ q
    top = np.argsort(-scores)[:k]
    for idx in top:
        p, s, e, content, _ = rows[idx]
        results.append({
            "path": p, "start_line": int(s), "end_line": int(e),
            "score": round(float(scores[idx]), 4),
            "content": content if len(content) < 2000 else content[:2000] + "\n...",
        })
    return results[:k + 5]


def impact(root, target, depth=3):
    root = os.path.abspath(root)
    db = repo_db(root)
    files = {r[0] for r in db.execute("SELECT path FROM files").fetchall()}
    target = target.replace(os.sep, "/")
    if target in files:
        target_paths = [target]
        is_symbol = False
    else:
        target_paths = sorted({r[0] for r in db.execute(
            "SELECT path FROM symbols WHERE name=?", (target,)).fetchall()})
        is_symbol = True
    if not target_paths:
        db.close()
        return {"error": f"'{target}' is neither an indexed file nor a known symbol; run code_index first"}
    rev = {}
    for src, dst in db.execute("SELECT src,dst FROM edges").fetchall():
        rev.setdefault(dst, []).append(src)
    seen_paths = set(target_paths)
    frontier = list(target_paths)
    layers = []
    for dist in range(1, depth + 1):
        nxt = []
        for p in frontier:
            for srcf in rev.get(p, []):
                if srcf not in seen_paths:
                    seen_paths.add(srcf)
                    nxt.append(srcf)
        if not nxt:
            break
        layers.append({"distance": dist, "files": sorted(nxt)})
        frontier = nxt
    refs = []
    if is_symbol:
        pat = re.compile(r"(?<![\w$])" + re.escape(target) + r"(?![\w$])")
        for p, content in db.execute("SELECT path,content FROM chunks").fetchall():
            if p not in target_paths and pat.search(content):
                refs.append(p)
        refs = sorted(set(refs))
    db.close()
    return {"target": target, "defined_in": target_paths,
            "import_impact": layers, "text_references": refs}


def graph(root, target):
    root = os.path.abspath(root)
    db = repo_db(root)
    target = target.replace(os.sep, "/")
    fwd = sorted({d for s, d in db.execute(
        "SELECT src,dst FROM edges WHERE src=?", (target,)).fetchall()})
    back = sorted({s for s, d in db.execute(
        "SELECT src,dst FROM edges WHERE dst=?", (target,)).fetchall()})
    syms = [{"name": n, "kind": k, "line": l} for _, n, k, l in db.execute(
        "SELECT path,name,kind,line FROM symbols WHERE path=? ORDER BY line", (target,)).fetchall()]
    db.close()
    return {"file": target, "imports": fwd, "imported_by": back, "symbols": syms}


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
    {
        "name": "code_impact",
        "description": "Deterministic impact analysis over the repository's import graph: given a file or a symbol name, returns where it is defined, every file that imports it (transitively, by distance) and every file that references the symbol textually. Use BEFORE renaming or changing a shared type, function or endpoint so the whole chain is updated in one pass, not discovered by trial and error.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the repository root"},
                "target": {"type": "string", "description": "Relative file path or a symbol name"},
                "depth": {"type": "integer", "description": "Transitive depth (default 3)"},
            },
            "required": ["path", "target"],
        },
    },
    {
        "name": "code_graph",
        "description": "Dependency neighborhood of one file: what it imports, what imports it, and the symbols it defines. Deterministic, built from parsed import statements rather than embeddings.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Absolute path to the repository root"},
                "target": {"type": "string", "description": "Relative file path inside the repository"},
            },
            "required": ["path", "target"],
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
                    text = (f"Indexed: {res['indexed']} files, {res['unchanged']} unchanged, "
                            f"{res['total_chunks']} chunks, {res['symbols']} symbols, "
                            f"{res['import_edges']} import edges.")
                elif name == "code_impact":
                    res = impact(args["path"], args["target"], int(args.get("depth", 3)))
                    text = json.dumps(res, indent=2)
                elif name == "code_graph":
                    res = graph(args["path"], args["target"])
                    text = json.dumps(res, indent=2)
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
        print("usage: xyra_context.py {mcp|index <path>|search <path> <query>|impact <path> <target>|graph <path> <file>}", file=sys.stderr)
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
    elif cmd == "impact":
        print(json.dumps(impact(sys.argv[2], sys.argv[3]), indent=2))
    elif cmd == "graph":
        print(json.dumps(graph(sys.argv[2], sys.argv[3]), indent=2))
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
