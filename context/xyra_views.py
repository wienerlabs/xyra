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


def write_view(name, content):
    os.makedirs(VIEW_DIR, exist_ok=True)
    path = os.path.join(VIEW_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


def open_view(path):
    if sys.platform == "darwin":
        subprocess.run(["open", path], capture_output=True)
    elif sys.platform.startswith("linux"):
        subprocess.run(["xdg-open", path], capture_output=True)


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


def cmd_hud(argv):
    events = xyra_bus.read_events(limit=400)
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


def cmd_xray(argv):
    root = os.path.abspath(argv[0]) if argv else os.getcwd()
    counts, scanned = session_reads(root)
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


TOPOLOGY_JS = """
const data = __DATA__;
const canvas = document.getElementById('c');
const ctx = canvas.getContext('2d');
function resize(){ canvas.width = innerWidth; canvas.height = innerHeight - 120; }
resize(); addEventListener('resize', () => { resize(); });
const deg = {};
data.edges.forEach(([a,b]) => { deg[a]=(deg[a]||0)+1; deg[b]=(deg[b]||0)+1; });
const nodes = data.files.map((f,i) => ({
  id: f, x: canvas.width/2 + Math.cos(i)*Math.min(canvas.width,canvas.height)/3,
  y: canvas.height/2 + Math.sin(i*1.7)*Math.min(canvas.width,canvas.height)/3,
  vx:0, vy:0, d: deg[f]||0, on:true }));
const index = new Map(nodes.map(n => [n.id, n]));
const links = data.edges.map(([a,b]) => ({s:index.get(a), t:index.get(b)})).filter(l => l.s && l.t);
let hover = null;
function step(){
  for (const n of nodes){ n.vx *= 0.86; n.vy *= 0.86; }
  for (let i=0;i<nodes.length;i++) for (let j=i+1;j<nodes.length;j++){
    const a=nodes[i], b=nodes[j];
    let dx=a.x-b.x, dy=a.y-b.y, d2=dx*dx+dy*dy+0.01;
    if (d2 < 40000){ const f = 240/d2; a.vx+=dx*f; a.vy+=dy*f; b.vx-=dx*f; b.vy-=dy*f; }
  }
  for (const l of links){
    const dx=l.t.x-l.s.x, dy=l.t.y-l.s.y, d=Math.sqrt(dx*dx+dy*dy)||1;
    const f=(d-90)*0.0025; l.s.vx+=dx*f; l.s.vy+=dy*f; l.t.vx-=dx*f; l.t.vy-=dy*f;
  }
  for (const n of nodes){
    n.vx += (canvas.width/2 - n.x)*0.0009; n.vy += (canvas.height/2 - n.y)*0.0009;
    n.x += Math.max(-6, Math.min(6, n.vx)); n.y += Math.max(-6, Math.min(6, n.vy));
  }
  draw();
  requestAnimationFrame(step);
}
function draw(){
  ctx.clearRect(0,0,canvas.width,canvas.height);
  for (const l of links){
    const lit = hover && (l.s === hover || l.t === hover);
    ctx.strokeStyle = lit ? 'rgba(217,247,111,0.85)' : 'rgba(120,140,90,0.18)';
    ctx.lineWidth = lit ? 1.6 : 0.6;
    ctx.beginPath(); ctx.moveTo(l.s.x,l.s.y); ctx.lineTo(l.t.x,l.t.y); ctx.stroke();
  }
  for (const n of nodes){
    const r = 2.5 + Math.min(7, n.d);
    const active = n.on && (!hover || n === hover || links.some(l => (l.s===hover&&l.t===n)||(l.t===hover&&l.s===n)));
    ctx.fillStyle = active ? '#D9F76F' : 'rgba(150,170,120,0.25)';
    ctx.beginPath(); ctx.arc(n.x,n.y,r,0,6.283); ctx.fill();
    if (hover === n || (n.d > 6 && !hover)){
      ctx.fillStyle = '#C8D6B0'; ctx.font = '11px ui-monospace,Menlo,monospace';
      ctx.fillText(n.id.split('/').pop(), n.x + r + 4, n.y + 3);
    }
  }
}
canvas.addEventListener('mousemove', e => {
  const mx=e.clientX, my=e.clientY-120; hover=null; let best=1e9;
  for (const n of nodes){ const d=(n.x-mx)**2+(n.y-my)**2; if (d<400 && d<best){best=d; hover=n;} }
  document.getElementById('info').textContent = hover ? hover.id + '  (' + hover.d + ' links)' : '';
});
document.getElementById('q').addEventListener('input', e => {
  const q = e.target.value.trim().toLowerCase();
  for (const n of nodes) n.on = !q || n.id.toLowerCase().includes(q);
});
step();
"""


def cmd_topology(argv):
    root = os.path.abspath(argv[0]) if argv else os.getcwd()
    files, edges = graph_data(root)
    if not files:
        print("no index for this repo; run: xyra-context index <path>", file=sys.stderr)
        return 1
    payload = json.dumps({"files": files[:900], "edges": [list(e) for e in edges][:3000]})
    body = (f"<header><h1>Topology</h1><span class='sub'>{html.escape(root)} · "
            f"{len(files)} files, {len(edges)} import links</span>"
            "<input id='q' placeholder='filter files' style='margin-left:auto;background:#11150D;"
            "border:1px solid #1E2418;color:#E8F0D8;padding:6px 10px;border-radius:6px'></header>"
            "<div class='legend' id='info'>hover a node to light up what it imports</div>"
            "<canvas id='c'></canvas>"
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


COMMANDS = {
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
        print("usage: xyra-views {hud|xray|topology|timeline|secops|cockpit|decide} [path|args]",
              file=sys.stderr)
        return 1
    return COMMANDS[argv[0]](argv[1:]) or 0


if __name__ == "__main__":
    sys.exit(main())
