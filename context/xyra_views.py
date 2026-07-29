#!/usr/bin/env python3
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.expanduser("~/.xyra/lib"))

import xyra_bus

VIEW_DIR = os.path.expanduser("~/.xyra/views")
GROK_SESSIONS = os.path.expanduser("~/.grok/sessions")

CSS = """
:root { color-scheme: dark; }
body { margin:0; background:#0B0D08; color:#E8F0D8; font:14px/1.5 -apple-system,BlinkMacSystemFont,"SF Pro Text",system-ui,sans-serif; }
header { padding:18px 24px; border-bottom:1px solid #1E2418; display:flex; align-items:baseline; gap:16px; }
h1 { margin:0; font-size:18px; font-weight:600; color:#D9F76F; letter-spacing:.2px; }
.sub { color:#7E8B6A; font-size:12px; }
main { padding:20px 24px; }
.lane { margin-bottom:18px; border:1px solid #1E2418; border-radius:10px; overflow:hidden; }
.lane h2 { margin:0; padding:10px 14px; font-size:13px; font-weight:600; background:#11150D; color:#B7D96A; }
.row { display:flex; gap:12px; padding:8px 14px; border-top:1px solid #151A10; align-items:center; }
.row:hover { background:#0F130B; }
.tag { font-size:11px; padding:2px 8px; border-radius:999px; background:#1B2313; color:#B7D96A; white-space:nowrap; }
.tag.high { background:#3A1414; color:#FF9B9B; }
.tag.medium { background:#3A2E14; color:#F2D06B; }
.tag.low { background:#1B2313; color:#9DB37A; }
.mono { font-family:"SF Mono",Menlo,monospace; font-size:12px; color:#C8D6B0; }
.muted { color:#6F7B5D; }
.bar { height:6px; background:#1A2113; border-radius:3px; overflow:hidden; flex:1; min-width:120px; }
.bar span { display:block; height:100%; background:#D9F76F; }
.grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(260px,1fr)); gap:12px; }
.card { border:1px solid #1E2418; border-radius:10px; padding:14px; background:#0E120A; }
.card h3 { margin:0 0 8px; font-size:14px; color:#D9F76F; }
.k { color:#7E8B6A; font-size:12px; }
.v { font-size:20px; font-weight:600; }
a { color:#B7D96A; }
canvas { display:block; }
.legend { padding:6px 24px 16px; color:#6F7B5D; font-size:12px; }
"""


def shell(argv, cwd=None, timeout=60):
    try:
        out = subprocess.run(argv, cwd=cwd, timeout=timeout, capture_output=True, text=True)
        return out.returncode, (out.stdout or "") + (out.stderr or "")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 1, ""


def page(title, body, extra_head="", refresh=None):
    meta = f'<meta http-equiv="refresh" content="{refresh}">' if refresh else ""
    return (f"<!doctype html><html><head><meta charset='utf-8'>{meta}"
            f"<title>{html.escape(title)}</title><style>{CSS}</style>{extra_head}"
            f"</head><body>{body}</body></html>")


IN_EDITOR = os.environ.get("XYRA_VIEW_TARGET", "editor") != "browser"


def project_view_dir(root=None):
    base = os.path.join(os.path.abspath(root), ".xyra", "views") if root else VIEW_DIR
    os.makedirs(base, exist_ok=True)
    return base


def write_view(name, content, root=None):
    base = project_view_dir(root) if root else VIEW_DIR
    os.makedirs(base, exist_ok=True)
    path = os.path.join(base, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def editor_binary():
    for cand in ("/opt/homebrew/bin/xyra", "/usr/local/bin/xyra",
                 os.path.expanduser("~/.local/bin/xyra")):
        if os.path.exists(cand):
            return cand
    return shutil_which("xyra")


def shutil_which(name):
    import shutil
    return shutil.which(name)


def open_view(path, prefer_editor=None):
    prefer = IN_EDITOR if prefer_editor is None else prefer_editor
    if prefer:
        xyra = editor_binary()
        if xyra:
            subprocess.run([xyra, path], capture_output=True)
            return
    if sys.platform == "darwin":
        subprocess.run(["open", path], capture_output=True)
    elif sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", path], capture_output=True)


def bar(value, peak, width=24):
    if peak <= 0:
        return ""
    filled = max(1, round(width * value / peak)) if value else 0
    return "█" * filled + "░" * (width - filled)


def md_page(title, subtitle, sections):
    out = [f"# {title}", "", f"_{subtitle}_", ""]
    for heading, body in sections:
        if heading:
            out.append(f"## {heading}")
            out.append("")
        out.append(body.rstrip())
        out.append("")
    out.append("---")
    out.append("")
    out.append("Rendered by Xyra. Press cmd-shift-v for the formatted view, "
               "or cmd-k v to open it beside the code.")
    return "\n".join(out) + "\n"


ROLE_OF = {
    "build": "Coder", "builder": "Coder", "review": "Reviewer",
    "lens": "Reviewer", "panel": "Reviewer", "verdict": "Router",
    "run": "Router", "start": "Router", "ticket": "Router",
    "design": "Architect", "challenge": "Architect", "sandbox": "Sandbox",
    "qa": "QA", "vision": "Vision", "decision": "Router", "fleet": "Fleet",
}


def classify(event):
    name = (event.get("event") or "").lower()
    for key, role in ROLE_OF.items():
        if key in name:
            return role
    return "Agent"


def hud_html(events):
    lanes = {}
    for e in events:
        lanes.setdefault(classify(e), []).append(e)
    if not lanes:
        body = ("<header><h1>Agent orchestration</h1><span class='sub'>no activity yet</span></header>"
                "<main><p class='muted'>Run xyra-council, xyra-cosmos or xyra-qa and this view fills up live.</p></main>")
        return page("Xyra agents", body, refresh=3)
    now = time.time()
    parts = ["<header><h1>Agent orchestration</h1>"
             f"<span class='sub'>{len(events)} events, live</span></header><main>"]
    order = ["Router", "Architect", "Coder", "Reviewer", "Sandbox", "QA", "Vision", "Fleet", "Agent"]
    for role in order:
        items = lanes.get(role)
        if not items:
            continue
        parts.append(f"<div class='lane'><h2>{role} <span class='muted'>({len(items)})</span></h2>")
        for e in items[-12:]:
            age = max(0, int(now - e.get("ts", now)))
            fields = {k: v for k, v in e.items() if k not in ("ts", "event", "run")}
            detail = ", ".join(f"{k}={str(v)[:60]}" for k, v in list(fields.items())[:4])
            parts.append(
                f"<div class='row'><span class='tag'>{html.escape(e.get('event',''))}</span>"
                f"<span class='mono'>{html.escape(detail)}</span>"
                f"<span class='muted' style='margin-left:auto'>{age}s ago</span></div>")
        parts.append("</div>")
    parts.append("</main>")
    return page("Xyra agents", "".join(parts), refresh=3)


def hud_md(events):
    if not events:
        return md_page("Agent orchestration", "no activity yet",
                       [("", "Run xyra-council, xyra-cosmos or xyra-qa and this view fills up.")])
    lanes = {}
    for e in events:
        lanes.setdefault(classify(e), []).append(e)
    now = time.time()
    sections = []
    order = ["Router", "Architect", "Coder", "Reviewer", "Sandbox", "QA", "Vision", "Fleet", "Agent"]
    for role in order:
        items = lanes.get(role)
        if not items:
            continue
        rows = ["| event | detail | when |", "|---|---|---|"]
        for e in items[-12:]:
            age = max(0, int(now - e.get("ts", now)))
            fields = {k: v for k, v in e.items() if k not in ("ts", "event", "run")}
            detail = ", ".join(f"{k}={str(v)[:40]}" for k, v in list(fields.items())[:3]) or "-"
            rows.append(f"| `{e.get('event','')}` | {detail} | {age}s ago |")
        sections.append((f"{role} ({len(items)})", "\n".join(rows)))
    return md_page("Agent orchestration", f"{len(events)} events across {len(lanes)} roles", sections)


def cmd_hud(argv):
    root = os.path.abspath(argv[0]) if argv and not argv[0].startswith("-") else os.getcwd()
    events = xyra_bus.read_events(limit=400)
    if IN_EDITOR:
        path = write_view("agents.md", hud_md(events), root)
    else:
        path = write_view("agents.html", hud_html(events))
    open_view(path)
    print(path)


def project_files(root):
    code, out = shell(["git", "-C", root, "ls-files"], timeout=60)
    if code == 0 and out.strip():
        return [l for l in out.splitlines() if l.strip()]
    files = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in
                       ("node_modules", "target", "dist", "build", "__pycache__")]
        for fn in filenames:
            files.append(os.path.relpath(os.path.join(dirpath, fn), root))
        if len(files) > 4000:
            break
    return files


def session_reads(root, limit_files=4000):
    root = os.path.abspath(root)
    counts = {}
    if not os.path.isdir(GROK_SESSIONS):
        return counts, 0
    known = set(project_files(root))
    scanned = 0
    entries = []
    for dirpath, _, filenames in os.walk(GROK_SESSIONS):
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                entries.append((os.path.getmtime(p), p))
            except OSError:
                continue
    entries.sort(reverse=True)
    for _, p in entries[:40]:
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                blob = f.read(4_000_000)
        except OSError:
            continue
        scanned += 1
        for rel in known:
            if len(rel) < 4:
                continue
            n = blob.count(rel)
            if n:
                counts[rel] = counts.get(rel, 0) + n
    return counts, scanned


def xray_html(root, counts, scanned):
    if not counts:
        body = ("<header><h1>Context X-ray</h1><span class='sub'>no agent file access recorded</span></header>"
                f"<main><p class='muted'>Scanned {scanned} Grok sessions and found no references to files in "
                f"{html.escape(root)}. Work with an agent in this project first.</p></main>")
        return page("Xyra context X-ray", body)
    top = sorted(counts.items(), key=lambda kv: -kv[1])
    peak = top[0][1]
    rows = []
    for rel, n in top[:120]:
        pct = int(100 * n / peak)
        heat = f"rgba(217,247,111,{0.15 + 0.85 * n / peak:.2f})"
        rows.append(
            f"<div class='row'><span class='mono' style='flex:1'>{html.escape(rel)}</span>"
            f"<span class='bar'><span style='width:{pct}%;background:{heat}'></span></span>"
            f"<span class='muted' style='width:60px;text-align:right'>{n}</span></div>")
    body = (f"<header><h1>Context X-ray</h1><span class='sub'>{html.escape(root)} · "
            f"{len(counts)} files touched across {scanned} sessions</span></header>"
            f"<main><div class='lane'><h2>Attention heatmap (most read first)</h2>{''.join(rows)}</div>"
            "<p class='muted'>To drop a file from agent attention, add it to file_scan_exclusions in "
            "settings.json or to .gitignore; agents index what the project exposes.</p></main>")
    return page("Xyra context X-ray", body)


def xray_md(root, counts, scanned):
    if not counts:
        return md_page("Context x-ray", f"{root}",
                       [("", f"Scanned {scanned} agent sessions and found no references to files "
                             "in this project. Work with an agent here first.")])
    top = sorted(counts.items(), key=lambda kv: -kv[1])
    peak = top[0][1]
    rows = ["| file | attention | reads |", "|---|---|---|"]
    for rel, n in top[:60]:
        rows.append(f"| `{rel}` | `{bar(n, peak)}` | {n} |")
    note = ("Files at the top dominate the agents' attention. If the wrong file is up there, "
            "add it to `file_scan_exclusions` in settings.json or to .gitignore.")
    return md_page("Context x-ray",
                   f"{root} · {len(counts)} files touched across {scanned} sessions",
                   [("Attention heatmap", "\n".join(rows)), ("", note)])


def cmd_xray(argv):
    root = os.path.abspath(argv[0]) if argv else os.getcwd()
    counts, scanned = session_reads(root)
    if IN_EDITOR:
        path = write_view("xray.md", xray_md(root, counts, scanned), root)
    else:
        path = write_view("xray.html", xray_html(root, counts, scanned))
    open_view(path)
    print(path)


def graph_data(root):
    import xyra_context
    db = xyra_context.repo_db(os.path.abspath(root))
    edges = db.execute("SELECT src,dst FROM edges").fetchall()
    files = [r[0] for r in db.execute("SELECT path FROM files").fetchall()]
    db.close()
    return files, edges


VENDOR_DIR = os.path.expanduser("~/.xyra/lib/vendor")
CYTOSCAPE_URL = "https://unpkg.com/cytoscape@3.30.2/dist/cytoscape.min.js"


def vendor_script(name, url):
    os.makedirs(VENDOR_DIR, exist_ok=True)
    path = os.path.join(VENDOR_DIR, name)
    if os.path.exists(path) and os.path.getsize(path) > 50_000:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    import urllib.request
    with urllib.request.urlopen(url, timeout=90) as r:
        blob = r.read().decode("utf-8")
    with open(path, "w", encoding="utf-8") as f:
        f.write(blob)
    return blob


TOPOLOGY_JS = """
const data = __DATA__;
const deg = {};
data.edges.forEach(([a, b]) => { deg[a] = (deg[a] || 0) + 1; deg[b] = (deg[b] || 0) + 1; });
const dirOf = f => (f.includes('/') ? f.split('/').slice(0, -1).join('/') : '.');
const palette = ['#D9F76F','#8FD4B0','#7FB4E8','#E8A87C','#C89BE8','#E88C9B','#9BE8D8','#E8D48C'];
const dirs = [...new Set(data.files.map(dirOf))].sort();
const colorOf = d => palette[dirs.indexOf(d) % palette.length];
const elements = [];
const connected = data.files.filter(f => deg[f]);
const orphans = data.files.filter(f => !deg[f]);
for (const f of connected) {
  elements.push({ data: { id: f, label: f.split('/').pop(), dir: dirOf(f),
                          deg: deg[f] || 0, color: colorOf(dirOf(f)) } });
}
for (const [a, b] of data.edges) {
  if (deg[a] && deg[b]) {
    elements.push({ data: { id: a + '->' + b, source: a, target: b } });
  }
}
const LAYOUTS = {
  layers: { name: 'breadthfirst', directed: true, spacingFactor: 1.5, padding: 60,
            avoidOverlap: true, animate: false, grid: false },
  organic: { name: 'cose', animate: false, nodeRepulsion: 60000, idealEdgeLength: 180,
             nodeOverlap: 60, gravity: 0.2, numIter: 1500, padding: 60,
             componentSpacing: 260, coolingFactor: 0.95 },
  circle: { name: 'concentric', concentric: n => n.data('deg'), levelWidth: () => 2,
            minNodeSpacing: 40, padding: 60, animate: false },
};
const cy = cytoscape({
  container: document.getElementById('cy'),
  elements,
  wheelSensitivity: 0.25,
  style: [
    { selector: 'node', style: {
        'background-color': 'data(color)',
        'width': 'mapData(deg, 0, 20, 14, 48)',
        'height': 'mapData(deg, 0, 20, 14, 48)',
        'label': '',
        'font-size': 10,
        'font-family': 'ui-monospace, Menlo, monospace',
        'color': '#E8F0D8',
        'text-valign': 'bottom',
        'text-margin-y': 4,
        'text-background-color': '#0B0D08',
        'text-background-opacity': 0.85,
        'text-background-padding': 3,
        'text-background-shape': 'roundrectangle',
        'border-width': 0,
        'z-index': 1,
      } },
    { selector: 'node.labelled', style: { 'label': 'data(label)', 'z-index': 50 } },
    { selector: 'edge', style: {
        'width': 1.6,
        'line-color': 'rgba(183,217,106,0.5)',
        'target-arrow-color': '#B7D96A',
        'target-arrow-shape': 'triangle',
        'arrow-scale': 1.5,
        'curve-style': 'taxi',
        'taxi-direction': 'downward',
        'taxi-turn': '40%',
        'taxi-turn-min-distance': 12,
      } },
    { selector: '.dim', style: { 'opacity': 0.08, 'text-opacity': 0 } },
    { selector: '.hit', style: { 'border-width': 3, 'border-color': '#FFFFFF' } },
    { selector: 'node.focus', style: {
        'border-width': 3, 'border-color': '#D9F76F', 'font-size': 12, 'z-index': 99 } },
    { selector: 'edge.focus', style: {
        'line-color': '#D9F76F', 'target-arrow-color': '#D9F76F', 'width': 2.5, 'z-index': 99 } },
  ],
  layout: LAYOUTS.layers,
});
const info = document.getElementById('info');
function relabel() {
  const zoom = cy.zoom();
  const budget = cy.nodes().length <= 60 ? 999 : (zoom > 1.2 ? 999 : zoom > 0.7 ? 45 : 20);
  const ranked = cy.nodes().sort((a, b) => b.data('deg') - a.data('deg'));
  cy.nodes().removeClass('labelled');
  ranked.slice(0, budget).forEach(n => n.addClass('labelled'));
  cy.nodes('.focus, .hit').addClass('labelled');
}
cy.on('zoom', relabel);
function clearFocus() {
  cy.elements().removeClass('focus').removeClass('dim');
  info.textContent = 'click a file to trace its dependencies';
  relabel();
}
cy.on('tap', 'node', evt => {
  const n = evt.target;
  const out = n.outgoers();
  const inc = n.incomers();
  cy.elements().addClass('dim').removeClass('focus');
  n.removeClass('dim').addClass('focus').addClass('labelled');
  out.union(inc).removeClass('dim').addClass('focus');
  out.union(inc).nodes().addClass('labelled');
  const imports = n.outgoers('node').map(x => x.id());
  const importedBy = n.incomers('node').map(x => x.id());
  info.innerHTML = '<b>' + n.id() + '</b>  imports ' + imports.length +
    ', imported by ' + importedBy.length +
    (imports.length ? '<br><span class="muted">imports: ' + imports.slice(0, 8).join(', ') + '</span>' : '') +
    (importedBy.length ? '<br><span class="muted">imported by: ' + importedBy.slice(0, 8).join(', ') + '</span>' : '');
});
cy.on('tap', evt => { if (evt.target === cy) clearFocus(); });
document.getElementById('q').addEventListener('input', e => {
  const q = e.target.value.trim().toLowerCase();
  cy.nodes().removeClass('hit');
  if (!q) { clearFocus(); return; }
  const hits = cy.nodes().filter(n => n.id().toLowerCase().includes(q));
  cy.elements().addClass('dim');
  cy.nodes().removeClass('labelled');
  hits.removeClass('dim').addClass('hit').addClass('labelled');
  hits.connectedEdges().removeClass('dim');
  hits.neighborhood('node').removeClass('dim');
  info.textContent = hits.length + ' files match "' + q + '"';
  if (hits.length) cy.animate({ fit: { eles: hits, padding: 80 } }, { duration: 300 });
});
document.getElementById('fit').addEventListener('click', () => { clearFocus(); cy.fit(undefined, 40); });
document.getElementById('relayout').addEventListener('change', e => {
  const mode = e.target.value;
  const l = LAYOUTS[mode] || LAYOUTS.layers;
  cy.style().selector('edge').style({
    'curve-style': mode === 'layers' ? 'taxi' : 'bezier',
  }).update();
  cy.layout(Object.assign({}, l, { animate: true })).run();
  setTimeout(() => { cy.fit(undefined, 60); relabel(); }, 400);
});
document.getElementById('count').textContent =
  connected.length + ' connected files, ' + orphans.length + ' with no imports (hidden)';
cy.ready(() => { cy.fit(undefined, 60); relabel(); });
clearFocus();
"""


def layered_positions(files, edges, width=1400, gap_y=120, gap_x=210):
    incoming = {f: 0 for f in files}
    for a, b in edges:
        if b in incoming:
            incoming[b] += 1
    depth = {f: 0 for f in files}
    for _ in range(6):
        changed = False
        for a, b in edges:
            if a in depth and b in depth and depth[b] < depth[a] + 1:
                depth[b] = depth[a] + 1
                changed = True
        if not changed:
            break
    layers = {}
    for f in files:
        layers.setdefault(min(depth[f], 8), []).append(f)
    pos = {}
    for level in sorted(layers):
        row = sorted(layers[level])
        per_row = max(1, min(len(row), int(width / gap_x)))
        for i, f in enumerate(row):
            col = i % per_row
            sub = i // per_row
            x = 90 + col * gap_x + (30 if sub % 2 else 0)
            y = 80 + (level * 2 + sub) * gap_y // 2
            pos[f] = (x, y)
    return pos


def topology_svg(root, files, edges):
    pos = layered_positions(files, edges)
    if not pos:
        return None
    max_x = max(p[0] for p in pos.values()) + 160
    max_y = max(p[1] for p in pos.values()) + 90
    deg = {}
    for a, b in edges:
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
    dirs = sorted({(f.rsplit("/", 1)[0] if "/" in f else ".") for f in files})
    palette = ["#D9F76F", "#8FD4B0", "#7FB4E8", "#E8A87C", "#C89BE8", "#E88C9B", "#9BE8D8"]
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{max_x}" height="{max_y}" '
           f'viewBox="0 0 {max_x} {max_y}">',
           f'<rect width="{max_x}" height="{max_y}" fill="#0B0D08"/>',
           '<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" '
           'markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#B7D96A"/></marker></defs>',
           f'<text x="24" y="34" fill="#D9F76F" font-family="monospace" font-size="16">'
           f'Topology: {html.escape(os.path.basename(root))} · {len(files)} files · {len(edges)} imports</text>']
    for i, (a, b) in enumerate(edges):
        if a not in pos or b not in pos:
            continue
        x1, y1 = pos[a]
        x2, y2 = pos[b]
        mid = (y1 + y2) / 2 + ((i % 7) - 3) * 7
        out.append(f'<path d="M{x1},{y1 + 8} L{x1},{mid:.0f} L{x2},{mid:.0f} L{x2},{y2 - 14}" '
                   f'fill="none" stroke="#B7D96A" stroke-opacity="0.4" stroke-width="1.3" '
                   f'marker-end="url(#a)"/>')
    for f, (x, y) in pos.items():
        d = deg.get(f, 0)
        r = 6 + min(14, d * 1.6)
        color = palette[dirs.index(f.rsplit("/", 1)[0] if "/" in f else ".") % len(palette)]
        label = f.split("/")[-1]
        out.append(f'<circle cx="{x}" cy="{y}" r="{r:.1f}" fill="{color}"/>')
        out.append(f'<text x="{x}" y="{y + r + 13:.0f}" fill="#E8F0D8" font-family="monospace" '
                   f'font-size="10" text-anchor="middle">{html.escape(label)}</text>')
    out.append("</svg>")
    return "\n".join(out)


def topology_md(root, files, edges):
    inbound, outbound = {}, {}
    for a, b in edges:
        outbound.setdefault(a, []).append(b)
        inbound.setdefault(b, []).append(a)
    hubs = sorted(inbound.items(), key=lambda kv: -len(kv[1]))[:15]
    rows = ["| file | imported by | imports |", "|---|---|---|"]
    for f, importers in hubs:
        rows.append(f"| `{f}` | {len(importers)} | {len(outbound.get(f, []))} |")
    orphans = [f for f in files if f not in inbound and f not in outbound]
    sections = [("Most depended on", "\n".join(rows)),
                ("Diagram", "![topology](topology.svg)\n\nOpen `topology.svg` and press cmd-shift-v "
                            "for the full graph.")]
    if orphans:
        sections.append(("Files with no imports",
                         ", ".join(f"`{o}`" for o in orphans[:40])))
    return md_page("Topology", f"{root} · {len(files)} files · {len(edges)} import links", sections)


def cmd_topology(argv):
    root = os.path.abspath(argv[0]) if argv else os.getcwd()
    files, edges = graph_data(root)
    if not files:
        print("no index for this repo; run: xyra-context index <path>", file=sys.stderr)
        return 1
    if IN_EDITOR:
        linked = {f for e in edges for f in e}
        connected = [f for f in files if f in linked][:220]
        cedges = [e for e in edges if e[0] in connected and e[1] in connected]
        svg = topology_svg(root, connected, cedges)
        if svg:
            write_view("topology.svg", svg, root)
        path = write_view("topology.md", topology_md(root, connected or files, cedges), root)
        open_view(path)
        print(path)
        return 0
    linked = {f for e in edges for f in e}
    ranked = sorted(files, key=lambda f: (f not in linked, f))
    keep = set(ranked[:700]) | linked
    files = [f for f in files if f in keep]
    edges = [e for e in edges if e[0] in keep and e[1] in keep]
    try:
        lib = vendor_script("cytoscape.min.js", CYTOSCAPE_URL)
    except Exception as e:
        print(f"could not load the graph library: {e}", file=sys.stderr)
        return 1
    payload = json.dumps({"files": files, "edges": [list(e) for e in edges]})
    ctl = ("background:#11150D;border:1px solid #1E2418;color:#E8F0D8;"
           "padding:6px 10px;border-radius:6px;cursor:pointer")
    controls = (f"<input id='q' placeholder='filter files' style='margin-left:auto;{ctl}'>"
                f"<select id='relayout' style='{ctl}'>"
                "<option value='layers'>Layered</option>"
                "<option value='organic'>Organic</option>"
                "<option value='circle'>Concentric</option></select>"
                f"<button id='fit' style='{ctl}'>Fit</button>")
    body = (f"<header><h1>Topology</h1><span class='sub'>{html.escape(root)} · "
            f"{len(edges)} import links</span>{controls}</header>"
            "<div class='legend'><span id='count'></span> · "
            "<span id='info'>click a file to trace its dependencies</span></div>"
            "<div id='cy' style='width:100vw;height:calc(100vh - 130px)'></div>"
            f"<script>{lib}</script>"
            f"<script>{TOPOLOGY_JS.replace('__DATA__', payload)}</script>")
    path = write_view("topology.html", page("Xyra topology", body))
    open_view(path)
    print(path)
    return 0


def git_log(root, limit=60):
    code, out = shell(["git", "-C", root, "log", f"-{limit}",
                       "--pretty=format:%H\t%h\t%at\t%an\t%s"], timeout=60)
    rows = []
    if code == 0:
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) == 5:
                rows.append({"sha": parts[0], "short": parts[1], "ts": int(parts[2]),
                             "author": parts[3], "subject": parts[4]})
    return rows


def cmd_timeline(argv):
    root = os.path.abspath(argv[0]) if argv else os.getcwd()
    commits = git_log(root)
    journal = xyra_bus.read_journal(root)
    if not commits and not journal:
        print("nothing to show: not a git repo and no decision journal", file=sys.stderr)
        return 1
    marks = []
    for c in commits:
        marks.append({"kind": "commit", "ts": c["ts"], "label": c["subject"],
                      "ref": c["short"], "sha": c["sha"]})
    for d in journal:
        marks.append({"kind": "decision", "ts": int(d.get("ts", 0)),
                      "label": d.get("summary", ""), "ref": d.get("kind", "decision"),
                      "sha": d.get("commit")})
    marks.sort(key=lambda m: -m["ts"])
    rows = []
    for m in marks[:120]:
        when = time.strftime("%d %b %H:%M", time.localtime(m["ts"]))
        tag = "medium" if m["kind"] == "decision" else "low"
        branch = ""
        if m.get("sha"):
            branch = (f"<span class='mono muted'>git switch -c retry-{m['sha'][:7]} {m['sha'][:12]}</span>")
        rows.append(
            f"<div class='row'><span class='tag {tag}'>{html.escape(m['kind'])}</span>"
            f"<span class='mono' style='width:120px'>{html.escape(m['ref'] or '')}</span>"
            f"<span style='flex:1'>{html.escape(m['label'][:110])}</span>"
            f"{branch}<span class='muted' style='margin-left:12px'>{when}</span></div>")
    body = (f"<header><h1>Time travel</h1><span class='sub'>{html.escape(root)} · "
            f"{len(commits)} commits, {len(journal)} recorded decisions</span></header>"
            f"<main><div class='lane'><h2>History and decision points</h2>{''.join(rows)}</div>"
            "<p class='muted'>Copy a branch command to continue from that point with a different "
            "approach; the working tree is never touched by this view.</p></main>")
    if IN_EDITOR:
        rows_md = ["| kind | ref | what | when |", "|---|---|---|---|"]
        for m in marks[:80]:
            when = time.strftime("%d %b %H:%M", time.localtime(m["ts"]))
            rows_md.append(f"| {m['kind']} | `{m.get('ref','')}` | {m['label'][:90]} | {when} |")
        branch = "\n".join(
            f"- `{m['label'][:60]}` -> `git switch -c retry-{m['sha'][:7]} {m['sha'][:12]}`"
            for m in marks[:10] if m.get("sha"))
        sections = [("History and decisions", "\n".join(rows_md))]
        if branch:
            sections.append(("Branch from a decision", branch))
        path = write_view("timeline.md", md_page(
            "Time travel",
            f"{root} · {len(commits)} commits, {len(journal)} recorded decisions", sections), root)
        open_view(path)
        print(path)
        return 0
    path = write_view("timeline.html", page("Xyra time travel", body))
    open_view(path)
    print(path)
    return 0


COST_PATTERNS = [
    (r"await\s+\w+\.(find|query|select|get|fetch)\w*\([^)]*\)\s*;?\s*$", "db call inside a loop", "high"),
    (r"\.map\(\s*async", "async map without concurrency control", "medium"),
    (r"SELECT\s+\*", "select star", "medium"),
    (r"for\s*\(.*\)\s*{[^}]*await ", "await inside a for loop", "high"),
]
SEC_PATTERNS = [
    (r"(?i)(api[_-]?key|secret|password|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}", "hardcoded credential", "high"),
    (r"(?i)eval\s*\(", "eval on dynamic input", "high"),
    (r"dangerouslySetInnerHTML", "raw HTML injection point", "medium"),
    (r"(?i)exec\s*\(\s*[`\"'].*\$\{", "shell command built from interpolation", "high"),
    (r"\.unwrap\(\)", "unchecked unwrap", "low"),
    (r"(?i)invoke_signed|remaining_accounts", "solana privileged instruction, verify signer and owner", "medium"),
]


def scan_paths(root, files):
    findings = []
    for rel in files:
        p = os.path.join(root, rel)
        if not os.path.isfile(p) or os.path.getsize(p) > 400_000:
            continue
        ext = os.path.splitext(rel)[1].lower()
        if ext not in (".ts", ".tsx", ".js", ".jsx", ".py", ".rs", ".go", ".sql", ".sol"):
            continue
        try:
            with open(p, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except OSError:
            continue
        for i, line in enumerate(lines, 1):
            for pat, label, sev in SEC_PATTERNS:
                if re.search(pat, line):
                    findings.append({"kind": "security", "severity": sev, "file": rel,
                                     "line": i, "label": label, "code": line.strip()[:140]})
            for pat, label, sev in COST_PATTERNS:
                if re.search(pat, line):
                    findings.append({"kind": "cost", "severity": sev, "file": rel,
                                     "line": i, "label": label, "code": line.strip()[:140]})
    return findings


def cmd_secops(argv):
    root = os.path.abspath(argv[0]) if argv else os.getcwd()
    code, out = shell(["git", "-C", root, "diff", "--name-only", "HEAD"], timeout=60)
    changed = [l for l in out.splitlines() if l.strip()] if code == 0 else []
    files = changed or project_files(root)[:1200]
    findings = scan_paths(root, files)
    order = {"high": 0, "medium": 1, "low": 2}
    findings.sort(key=lambda f: (order[f["severity"]], f["file"]))
    rows = []
    for f in findings[:150]:
        rows.append(
            f"<div class='row'><span class='tag {f['severity']}'>{f['kind']}</span>"
            f"<span class='mono' style='width:280px'>{html.escape(f['file'])}:{f['line']}</span>"
            f"<span style='flex:1'>{html.escape(f['label'])}</span>"
            f"<span class='mono muted'>{html.escape(f['code'][:60])}</span></div>")
    scope = "changed files" if changed else "whole project"
    body = (f"<header><h1>SecOps and cost</h1><span class='sub'>{html.escape(root)} · "
            f"{scope} · {len(findings)} flags</span></header><main>"
            + (f"<div class='lane'><h2>Flags</h2>{''.join(rows)}</div>" if rows else
               "<p class='muted'>No security or cost patterns matched.</p>")
            + "<p class='muted'>Static heuristics, not a substitute for xyra-council review; "
              "run xyra-council for adversarial analysis of the same diff.</p></main>")
    if IN_EDITOR:
        rows_md = ["| severity | kind | location | issue |", "|---|---|---|---|"]
        for f in findings[:120]:
            rows_md.append(f"| {f['severity']} | {f['kind']} | `{f['file']}:{f['line']}` | {f['label']} |")
        body_md = "\n".join(rows_md) if findings else "No security or cost patterns matched."
        path = write_view("secops.md", md_page(
            "Security and cost", f"{root} · {scope} · {len(findings)} flags",
            [("Flags", body_md),
             ("", "Static heuristics. Run xyra-council for adversarial analysis of the same diff.")]),
            root)
        open_view(path)
        print(json.dumps({"findings": len(findings),
                          "high": sum(1 for f in findings if f["severity"] == "high"),
                          "view": path}, indent=2))
        return 0
    path = write_view("secops.html", page("Xyra secops", body))
    open_view(path)
    print(json.dumps({"findings": len(findings),
                      "high": sum(1 for f in findings if f["severity"] == "high"),
                      "view": path}, indent=2))
    return 0


def cmd_cockpit(argv):
    root = os.path.abspath(argv[0]) if argv else os.getcwd()
    events = xyra_bus.read_events(limit=800)
    journal = xyra_bus.read_journal(root)
    code, out = shell(["git", "-C", root, "diff", "--stat", "HEAD"], timeout=60)
    stat = out.strip().splitlines()[-1] if code == 0 and out.strip() else "no uncommitted changes"
    code, names = shell(["git", "-C", root, "diff", "--name-only", "HEAD"], timeout=60)
    changed = [l for l in names.splitlines() if l.strip()] if code == 0 else []
    verdicts = [e for e in events if "verdict" in (e.get("event") or "")]
    sandbox = [e for e in events if "sandbox" in (e.get("event") or "")]
    cards = [
        ("Files changed", str(len(changed))),
        ("Recorded decisions", str(len(journal))),
        ("Council verdicts", str(len(verdicts))),
        ("Sandbox runs", str(len(sandbox))),
    ]
    card_html = "".join(
        f"<div class='card'><div class='k'>{html.escape(k)}</div><div class='v'>{html.escape(v)}</div></div>"
        for k, v in cards)
    file_rows = "".join(f"<div class='row'><span class='mono'>{html.escape(f)}</span></div>"
                        for f in changed[:60])
    decision_rows = "".join(
        f"<div class='row'><span class='tag'>{html.escape(d.get('kind',''))}</span>"
        f"<span style='flex:1'>{html.escape(str(d.get('summary',''))[:120])}</span></div>"
        for d in journal[-20:])
    body = (f"<header><h1>Decision cockpit</h1><span class='sub'>{html.escape(root)}</span></header>"
            f"<main><div class='grid'>{card_html}</div>"
            f"<div class='lane' style='margin-top:18px'><h2>Diff summary</h2>"
            f"<div class='row'><span class='mono'>{html.escape(stat)}</span></div>{file_rows}</div>"
            + (f"<div class='lane'><h2>Decisions on record</h2>{decision_rows}</div>" if decision_rows else "")
            + "<div class='lane'><h2>Approval</h2><div class='row'>"
              "<span class='mono'>xyra-sandbox verify</span><span class='muted'>prove it first</span></div>"
              "<div class='row'><span class='mono'>git add -A &amp;&amp; git commit</span>"
              "<span class='muted'>then apply, deliberately, in your own terminal</span></div></div>"
              "<p class='muted'>Nothing is applied from this page by design: the cockpit reports, "
              "you execute.</p></main>")
    if IN_EDITOR:
        stats = "\n".join(f"- **{k}**: {v}" for k, v in cards)
        files_md = "\n".join(f"- `{f}`" for f in changed[:60]) or "_no uncommitted changes_"
        dec_md = "\n".join(f"- **{d.get('kind','')}**: {str(d.get('summary',''))[:120]}"
                            for d in journal[-20:]) or "_none recorded_"
        path = write_view("cockpit.md", md_page(
            "Decision cockpit", root,
            [("Summary", stats), ("Diff", f"`{stat}`\n\n{files_md}"),
             ("Decisions on record", dec_md),
             ("Approval", "Nothing is applied from this view by design.\n\n"
                          "1. `xyra-sandbox verify`\n2. `git add -A && git commit`\n"
                          "3. push deliberately, from your own terminal")]), root)
        open_view(path)
        print(path)
        return 0
    path = write_view("cockpit.html", page("Xyra cockpit", body))
    open_view(path)
    print(path)
    return 0


def npm_size(pkg):
    import urllib.request
    try:
        with urllib.request.urlopen(f"https://registry.npmjs.org/{pkg}/latest", timeout=20) as r:
            data = json.loads(r.read())
        size = data.get("dist", {}).get("unpackedSize")
        return {"name": pkg, "version": data.get("version"),
                "unpacked_kb": round(size / 1024) if size else None,
                "deps": len(data.get("dependencies") or {}),
                "description": (data.get("description") or "")[:140]}
    except Exception as e:
        return {"name": pkg, "error": str(e)[:120]}


def cmd_decide(argv):
    if len(argv) < 3:
        print("usage: xyra-views decide <question> <optionA> <optionB> [--npm a-pkg,b-pkg]",
              file=sys.stderr)
        return 1
    question, a, b = argv[0], argv[1], argv[2]
    pkgs = {}
    if "--npm" in argv:
        spec = argv[argv.index("--npm") + 1]
        names = [s.strip() for s in spec.split(",") if s.strip()]
        for n in names:
            pkgs[n] = npm_size(n)
    def card(title, pkg):
        info = pkgs.get(pkg) if pkg else None
        rows = ""
        if info and "error" not in info:
            rows = (f"<div class='k'>package</div><div class='mono'>{html.escape(info['name'])}@{info['version']}</div>"
                    f"<div class='k' style='margin-top:8px'>unpacked size</div>"
                    f"<div class='v'>{info['unpacked_kb']} KB</div>"
                    f"<div class='k' style='margin-top:8px'>direct dependencies</div>"
                    f"<div class='v'>{info['deps']}</div>"
                    f"<p class='muted'>{html.escape(info['description'])}</p>")
        elif info:
            rows = f"<p class='muted'>registry lookup failed: {html.escape(info['error'])}</p>"
        return f"<div class='card'><h3>{html.escape(title)}</h3>{rows}</div>"
    names = list(pkgs.keys())
    body = (f"<header><h1>Decision</h1><span class='sub'>{html.escape(question)}</span></header>"
            f"<main><div class='grid'>{card(a, names[0] if names else None)}"
            f"{card(b, names[1] if len(names) > 1 else None)}</div>"
            "<p class='muted'>Sizes and dependency counts come from the live npm registry. "
            "Tell the agent which option you picked to continue.</p></main>")
    path = write_view("decision.html", page("Xyra decision", body))
    open_view(path)
    print(path)
    return 0


def mission_md(root, state):
    total = len([t for t in state["tickets"] if t["status"] != "split"])
    done = sum(1 for t in state["tickets"] if t["status"] == "done")
    pct = round(100 * done / total) if total else 0
    filled = round(28 * done / total) if total else 0
    progress = "█" * filled + "░" * (28 - filled)
    elapsed = round((time.time() - state["started_at"]) / 60)
    marks = {"done": "done", "running": "running now", "quarantined": "quarantined",
             "retry": "retrying", "split": "split into smaller tickets", "pending": "waiting"}
    rows = ["| # | ticket | status | attempts | commit |", "|---|---|---|---|---|"]
    for t in state["tickets"]:
        commit = (t.get("commit") or "")[:8]
        rows.append(f"| {t['id']} | {t['title']} | {marks.get(t['status'], t['status'])} "
                    f"| {t['attempts']} | `{commit}` |")
    quarantined = [t for t in state["tickets"] if t["status"] == "quarantined"]
    sections = [
        ("Progress", f"`{progress}` **{done}/{total}** ({pct}%)\n\n"
                     f"- status: **{state['status']}**\n"
                     f"- sessions: {state['sessions']}\n"
                     f"- elapsed: {elapsed} min\n"
                     + (f"- current ticket: **{state['current']}**\n" if state.get("current") else "")
                     + (f"- halted: {state['halt_reason']}\n" if state.get("halt_reason") else "")),
        ("Tickets", "\n".join(rows)),
    ]
    if quarantined:
        detail = "\n\n".join(f"**{t['id']}. {t['title']}**\n\n```\n"
                              + (t["notes"][-1][:900] if t["notes"] else "") + "\n```"
                              for t in quarantined)
        sections.append(("Needs a human", detail))
    sections.append(("Controls",
                     "```bash\nxyra-mission status\nxyra-mission daemon   # keep going in the background\n"
                     "xyra-mission stop     # halt after the current ticket\n```"))
    return md_page("Mission control", state["objective"], sections)


def cmd_mission(argv):
    root = os.path.abspath(argv[0]) if argv and not argv[0].startswith("-") else os.getcwd()
    watch = "--watch" in argv
    import xyra_mission
    while True:
        state = xyra_mission.load_state(root)
        if not state:
            path = write_view("mission.md", md_page(
                "Mission control", "no mission in this project",
                [("", "Start one:\n\n```bash\nxyra-mission start \"your objective\"\n```")]), root)
        else:
            path = write_view("mission.md", mission_md(root, state), root)
        if not watch:
            open_view(path)
            print(path)
            return 0
        if state and state["status"] not in ("running", "planned"):
            print(path)
            return 0
        time.sleep(3)


COMMANDS = {
    "mission": cmd_mission,
    "hud": cmd_hud,
    "xray": cmd_xray,
    "topology": cmd_topology,
    "timeline": cmd_timeline,
    "secops": cmd_secops,
    "cockpit": cmd_cockpit,
    "decide": cmd_decide,
}


def main():
    argv = sys.argv[1:]
    if not argv or argv[0] not in COMMANDS:
        print("usage: xyra-views {mission|hud|xray|topology|timeline|secops|cockpit|decide} [path|args]",
              file=sys.stderr)
        return 1
    return COMMANDS[argv[0]](argv[1:]) or 0


if __name__ == "__main__":
    sys.exit(main())
