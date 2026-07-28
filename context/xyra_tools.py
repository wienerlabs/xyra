#!/usr/bin/env python3
import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

OLLAMA_URL = os.environ.get("XYRA_OLLAMA_URL", "http://localhost:11434")
SANDBOX_TIMEOUT = int(os.environ.get("XYRA_SANDBOX_TIMEOUT", "900"))
FIXER_TIMEOUT = int(os.environ.get("XYRA_FIXER_TIMEOUT", "600"))
QA_CACHE = os.path.expanduser("~/.cache/xyra-qa")

IGNORE_DIRS = {
    ".git", "node_modules", ".next", "dist", "build", "target", ".turbo",
    ".venv", "venv", "__pycache__", ".pnpm-store", ".cache", "vendor",
    "coverage", ".idea", ".vscode", "Pods", "DerivedData",
}
SEARCH_EXT = {
    ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".rs", ".go", ".py", ".rb",
    ".java", ".kt", ".swift", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".php",
    ".sol", ".move", ".sql", ".sh", ".toml", ".yaml", ".yml", ".json", ".md",
    ".vue", ".svelte", ".css", ".scss", ".proto", ".graphql", ".prisma",
}

FIXER_VENDORS = {
    "grok": ["grok", "--minimal", "--disable-web-search", "--always-approve", "-p"],
    "claude": ["claude", "-p", "--permission-mode", "acceptEdits"],
}


def run_cmd(argv, cwd=None, timeout=120, env=None, input_text=None):
    try:
        out = subprocess.run(
            argv, cwd=cwd, timeout=timeout, env=env, input=input_text,
            capture_output=True, text=True,
        )
        return out.returncode, (out.stdout or "") + (out.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"timed out after {timeout}s"
    except FileNotFoundError:
        return 127, f"binary not found: {argv[0]}"


RUNNER = run_cmd


def tail(text, lines=60):
    parts = text.strip().splitlines()
    return "\n".join(parts[-lines:])


def detect_commands(root):
    def has(*names):
        return any(os.path.exists(os.path.join(root, n)) for n in names)

    if has("pnpm-lock.yaml"):
        return {"test": "pnpm test", "build": "pnpm build"}
    if has("bun.lock", "bun.lockb"):
        return {"test": "bun test", "build": "bun run build"}
    if has("package-lock.json", "package.json"):
        return {"test": "npm test", "build": "npm run build"}
    if has("Cargo.toml"):
        return {"test": "cargo test", "build": "cargo build"}
    if has("pyproject.toml", "pytest.ini", "setup.py"):
        return {"test": "python3 -m pytest -q", "build": None}
    if has("go.mod"):
        return {"test": "go test ./...", "build": "go build ./..."}
    return {"test": None, "build": None}


def git_root(path):
    code, out = RUNNER(["git", "-C", path, "rev-parse", "--show-toplevel"], timeout=15)
    if code != 0:
        raise RuntimeError(f"not a git repository: {path}")
    return out.strip()


def snapshot_worktree(repo, mode="dirty", patch_text=None):
    repo = git_root(repo)
    tmp = tempfile.mkdtemp(prefix="xyra-sandbox-")
    wt = os.path.join(tmp, "wt")
    code, out = RUNNER(["git", "-C", repo, "worktree", "add", "--detach", wt, "HEAD"], timeout=120)
    if code != 0:
        shutil.rmtree(tmp, ignore_errors=True)
        raise RuntimeError(f"worktree add failed: {tail(out, 10)}")
    if patch_text:
        code, out = RUNNER(["git", "-C", wt, "apply", "--whitespace=nowarn", "-"],
                           timeout=60, input_text=patch_text)
        if code != 0:
            cleanup_worktree(repo, wt)
            raise RuntimeError(f"patch does not apply: {tail(out, 15)}")
    elif mode == "dirty":
        code, diff = RUNNER(["git", "-C", repo, "diff", "HEAD"], timeout=60)
        if code == 0 and diff.strip():
            code, out = RUNNER(["git", "-C", wt, "apply", "--whitespace=nowarn", "-"],
                               timeout=60, input_text=diff)
            if code != 0:
                cleanup_worktree(repo, wt)
                raise RuntimeError(f"dirty diff does not apply: {tail(out, 15)}")
        code, untracked = RUNNER(
            ["git", "-C", repo, "ls-files", "--others", "--exclude-standard"], timeout=60)
        if code == 0:
            for rel in untracked.strip().splitlines():
                src = os.path.join(repo, rel)
                dst = os.path.join(wt, rel)
                if os.path.isfile(src):
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    shutil.copy2(src, dst)
    elif mode == "staged":
        code, diff = RUNNER(["git", "-C", repo, "diff", "--cached"], timeout=60)
        if code == 0 and diff.strip():
            code, out = RUNNER(["git", "-C", wt, "apply", "--whitespace=nowarn", "-"],
                               timeout=60, input_text=diff)
            if code != 0:
                cleanup_worktree(repo, wt)
                raise RuntimeError(f"staged diff does not apply: {tail(out, 15)}")
    return repo, wt


def cleanup_worktree(repo, wt):
    RUNNER(["git", "-C", repo, "worktree", "remove", "--force", wt], timeout=60)
    shutil.rmtree(os.path.dirname(wt), ignore_errors=True)


def sandbox_verify(repo, mode="dirty", patch_text=None, keep=False, timeout=None):
    timeout = timeout or SANDBOX_TIMEOUT
    repo, wt = snapshot_worktree(repo, mode=mode, patch_text=patch_text)
    try:
        cmds = detect_commands(wt)
        cmd = cmds["test"] or cmds["build"]
        if not cmd:
            return {"ok": None, "reason": "no test or build runner detected",
                    "steps": [], "worktree": wt if keep else None}
        code, out = RUNNER(["bash", "-lc", cmd], cwd=wt, timeout=timeout)
        step = {"command": cmd, "exit": code, "tail": tail(out)}
        return {"ok": code == 0, "steps": [step], "worktree": wt if keep else None}
    finally:
        if not keep:
            cleanup_worktree(repo, wt)


def proven_diff(repo, wt):
    code, diff = RUNNER(["git", "-C", wt, "add", "-A"], timeout=60)
    code, diff = RUNNER(["git", "-C", wt, "diff", "--cached", "HEAD"], timeout=60)
    return diff if code == 0 else ""


def fixer_run(vendor, prompt, cwd, timeout=None):
    argv = FIXER_VENDORS.get(vendor)
    if not argv:
        return 127, f"unknown fixer vendor: {vendor}"
    return RUNNER(list(argv) + [prompt], cwd=cwd, timeout=timeout or FIXER_TIMEOUT)


def sandbox_loop(repo, rounds=3, vendor="grok", brief="", out_path=None, log=lambda m: None):
    repo, wt = snapshot_worktree(repo, mode="dirty")
    history = []
    try:
        cmds = detect_commands(wt)
        cmd = cmds["test"] or cmds["build"]
        if not cmd:
            return {"ok": None, "reason": "no test or build runner detected", "rounds": []}
        for r in range(1, rounds + 1):
            log(f"round {r}: {cmd}")
            code, out = RUNNER(["bash", "-lc", cmd], cwd=wt, timeout=SANDBOX_TIMEOUT)
            history.append({"round": r, "command": cmd, "exit": code, "tail": tail(out, 40)})
            if code == 0:
                diff = proven_diff(repo, wt)
                if out_path:
                    with open(out_path, "w", encoding="utf-8") as f:
                        f.write(diff)
                return {"ok": True, "rounds": history, "diff": diff,
                        "proof": f"{cmd} exited 0 in an isolated snapshot"}
            if r == rounds:
                break
            log(f"round {r} failed, invoking {vendor} fixer")
            prompt = (
                "You are working inside an isolated verification snapshot of a repository. "
                f"The command '{cmd}' failed with this output:\n\n{tail(out, 80)}\n\n"
                "Fix the root cause with minimal, scoped changes. Do not refactor unrelated "
                "code, do not add comments, do not create commits. "
                + (f"Task context: {brief}" if brief else "")
            )
            fcode, fout = fixer_run(vendor, prompt, wt)
            history.append({"round": r, "fixer": vendor, "exit": fcode, "tail": tail(fout, 15)})
        return {"ok": False, "rounds": history,
                "reason": f"still failing after {rounds} rounds"}
    finally:
        cleanup_worktree(repo, wt)


def chrome_path():
    envp = os.environ.get("XYRA_CHROME")
    if envp and os.path.exists(envp):
        return envp
    mac_candidates = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    for p in mac_candidates:
        if os.path.exists(p):
            return p
    for name in ("google-chrome", "chromium", "chromium-browser", "msedge"):
        found = shutil.which(name)
        if found:
            return found
    return None


def screenshot(url, out_png, size="1280,900", wait_ms=4000):
    chrome = chrome_path()
    if chrome:
        code, out = RUNNER([
            chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            f"--window-size={size}", f"--virtual-time-budget={wait_ms}",
            f"--screenshot={out_png}", url,
        ], timeout=90)
        if code == 0 and os.path.exists(out_png):
            return {"ok": True, "engine": os.path.basename(chrome)}
        return {"ok": False, "error": tail(out, 8)}
    code, out = RUNNER(["npx", "--yes", "playwright", "screenshot",
                        f"--viewport-size={size}", url, out_png], timeout=300)
    if code == 0 and os.path.exists(out_png):
        return {"ok": True, "engine": "playwright"}
    return {"ok": False, "error": "no Chrome/Chromium found and playwright fallback failed: " + tail(out, 8)}


def ollama_json(url, payload, timeout=300):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


_VISION_MODEL = None


def pick_vision_model():
    global _VISION_MODEL
    if _VISION_MODEL:
        return _VISION_MODEL
    envm = os.environ.get("XYRA_VISION_MODEL")
    if envm:
        _VISION_MODEL = envm
        return envm
    tags = ollama_json(f"{OLLAMA_URL}/api/tags", {}) if False else None
    req = urllib.request.Request(f"{OLLAMA_URL}/api/tags")
    with urllib.request.urlopen(req, timeout=15) as r:
        tags = json.loads(r.read())
    for m in tags.get("models", []):
        name = m.get("name", "")
        try:
            show = ollama_json(f"{OLLAMA_URL}/api/show", {"model": name}, timeout=30)
        except Exception:
            continue
        if "vision" in (show.get("capabilities") or []):
            _VISION_MODEL = name
            return name
    raise RuntimeError(
        "no vision-capable Ollama model found; set XYRA_VISION_MODEL or pull one")


def vlm_verdict(prompt, image_paths, timeout=600):
    model = pick_vision_model()
    images = []
    for p in image_paths:
        with open(p, "rb") as f:
            images.append(base64.b64encode(f.read()).decode())
    resp = ollama_json(f"{OLLAMA_URL}/api/chat", {
        "model": model,
        "stream": False,
        "format": "json",
        "messages": [{"role": "user", "content": prompt, "images": images}],
    }, timeout=timeout)
    content = resp.get("message", {}).get("content", "")
    try:
        return json.loads(content), model
    except json.JSONDecodeError:
        return {"raw": content}, model


def build_check_prompt(expectation):
    return (
        "You are a strict UI reviewer looking at a rendered screenshot of a web page. "
        f"Expectation from the developer: {expectation}\n"
        "Inspect layout, alignment, overflow, contrast, spacing and whether the "
        "expectation is met. Respond with JSON only, using exactly these keys: "
        '{"matches": true|false, "issues": [{"severity": "high|medium|low", '
        '"description": "...", "where": "..."}], "summary": "..."}'
    )


def build_compare_prompt():
    return (
        "You are comparing two images: the FIRST is a live screenshot of the "
        "implemented page, the SECOND is the intended design mockup. List every "
        "visible difference that matters: layout shifts, missing or extra elements, "
        "wrong colors, wrong typography, misalignment, spacing. Respond with JSON "
        'only: {"faithful": true|false, "differences": [{"severity": "high|medium|low", '
        '"description": "...", "where": "..."}], "summary": "..."}'
    )


def ui_check(url, expectation):
    tmp = tempfile.mkdtemp(prefix="xyra-vision-")
    shot = os.path.join(tmp, "shot.png")
    render = screenshot(url, shot)
    if not render.get("ok"):
        return {"ok": False, "error": render.get("error")}
    verdict, model = vlm_verdict(build_check_prompt(expectation), [shot])
    return {"ok": True, "engine": render["engine"], "model": model,
            "screenshot": shot, "verdict": verdict}


def ui_compare(url, design_path):
    if not os.path.exists(design_path):
        return {"ok": False, "error": f"design file not found: {design_path}"}
    tmp = tempfile.mkdtemp(prefix="xyra-vision-")
    shot = os.path.join(tmp, "shot.png")
    render = screenshot(url, shot)
    if not render.get("ok"):
        return {"ok": False, "error": render.get("error")}
    verdict, model = vlm_verdict(build_compare_prompt(), [shot, design_path])
    return {"ok": True, "engine": render["engine"], "model": model,
            "screenshot": shot, "verdict": verdict}


def find_manifest(start=None):
    cur = os.path.abspath(start or os.getcwd())
    while True:
        cand = os.path.join(cur, ".xyra", "fleet.json")
        if os.path.exists(cand):
            return cand
        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent
    home = os.path.expanduser("~/.xyra/fleet.json")
    return home if os.path.exists(home) else None


def load_fleet(manifest=None):
    path = manifest or find_manifest()
    if not path:
        raise RuntimeError(
            "no fleet manifest found; create .xyra/fleet.json with "
            '{"repos": [{"name": "backend", "path": "~/api", "role": "backend"}, ...]}')
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    repos = []
    for r in data.get("repos", []):
        p = os.path.expanduser(r["path"])
        if os.path.isdir(p):
            repos.append({"name": r.get("name", os.path.basename(p)),
                          "path": p, "role": r.get("role", "unknown")})
    return {"manifest": path, "repos": repos}


def iter_search_files(root):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for fn in filenames:
            if os.path.splitext(fn)[1].lower() in SEARCH_EXT:
                yield os.path.join(dirpath, fn)


DEF_PATTERNS = (
    r"\b(?:fn|def|class|interface|type|struct|enum|trait|function|const|let|var|pub fn)\s+{name}\b",
    r"\b{name}\s*[:=]\s*(?:async\s*)?(?:function|\()",
)


def repo_search(root, term, limit=40):
    rg = shutil.which("rg")
    hits = []
    if rg:
        code, out = RUNNER([rg, "-n", "--no-heading", "-S", "-m", str(limit), term, root],
                           timeout=60)
        if code in (0, 1):
            for line in out.splitlines()[:limit]:
                parts = line.split(":", 2)
                if len(parts) == 3:
                    hits.append({"path": os.path.relpath(parts[0], root),
                                 "line": int(parts[1]), "text": parts[2].strip()[:200]})
            return hits
    needle = term.lower()
    for path in iter_search_files(root):
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for i, line in enumerate(f, 1):
                    if needle in line.lower():
                        hits.append({"path": os.path.relpath(path, root),
                                     "line": i, "text": line.strip()[:200]})
                        if len(hits) >= limit:
                            return hits
        except OSError:
            continue
    return hits


def fleet_search(term, manifest=None, limit=40):
    fleet = load_fleet(manifest)
    out = []
    for repo in fleet["repos"]:
        hits = repo_search(repo["path"], term, limit=limit)
        if hits:
            out.append({"repo": repo["name"], "role": repo["role"],
                        "path": repo["path"], "hits": hits})
    return {"manifest": fleet["manifest"], "term": term, "results": out}


def classify_hit(term, text):
    for pat in DEF_PATTERNS:
        if re.search(pat.format(name=re.escape(term)), text):
            return "definition"
    return "reference"


def fleet_impact(term, manifest=None):
    found = fleet_search(term, manifest=manifest, limit=60)
    impact = []
    for block in found["results"]:
        defs, refs = [], []
        for h in block["hits"]:
            (defs if classify_hit(term, h["text"]) == "definition" else refs).append(h)
        impact.append({"repo": block["repo"], "role": block["role"], "path": block["path"],
                       "definitions": defs, "references": refs})
    impact.sort(key=lambda b: (0 if b["definitions"] else 1, b["repo"]))
    return {"term": term, "impact": impact,
            "summary": {b["repo"]: {"definitions": len(b["definitions"]),
                                    "references": len(b["references"])} for b in impact}}


def fleet_refactor(task, term=None, manifest=None, execute=False, vendor="grok",
                   log=lambda m: None):
    fleet = load_fleet(manifest)
    scope = fleet_impact(term, manifest=manifest)["impact"] if term else [
        {"repo": r["name"], "role": r["role"], "path": r["path"],
         "definitions": [], "references": []} for r in fleet["repos"]]
    touched = [b for b in scope if b["definitions"] or b["references"]] or scope
    plan = []
    for block in touched:
        others = [b for b in touched if b is not block]
        context_lines = []
        for o in others:
            for h in (o["definitions"] + o["references"])[:6]:
                context_lines.append(f"{o['repo']} ({o['role']}): {h['path']}:{h['line']}  {h['text']}")
        brief = (
            f"Cross-repo task: {task}\n"
            f"You are editing the '{block['repo']}' repository (role: {block['role']}).\n"
            + (f"The symbol in focus is '{term}'.\n" if term else "")
            + ("Known usages in the other repositories, keep them consistent:\n"
               + "\n".join(context_lines) + "\n" if context_lines else "")
            + "Apply the change here with minimal scoped edits, no comments, "
              "then run the repo's own tests if quick ones exist."
        )
        plan.append({"repo": block["repo"], "path": block["path"], "brief": brief})
    results = []
    if execute:
        for step in plan:
            log(f"executing in {step['repo']}")
            code, out = fixer_run(vendor, step["brief"], step["path"], timeout=1800)
            results.append({"repo": step["repo"], "exit": code, "tail": tail(out, 20)})
    return {"task": task, "plan": plan, "executed": results if execute else None}


QA_SCRIPT = r"""
const fs = require('fs');
const path = require('path');
const puppeteer = require('puppeteer-core');
const url = process.env.QA_URL;
const seconds = parseInt(process.env.QA_SECONDS || '90', 10);
const outDir = process.env.QA_OUT;
const events = [];
function record(type, detail) {
  events.push({ t: Date.now(), type, detail: String(detail).slice(0, 500) });
}
(async () => {
  const browser = await puppeteer.launch({
    executablePath: process.env.QA_CHROME,
    headless: 'new',
    args: ['--no-sandbox', '--window-size=1280,900'],
  });
  const page = await browser.newPage();
  await page.setViewport({ width: 1280, height: 900 });
  page.on('console', m => { if (m.type() === 'error') record('console_error', m.text()); });
  page.on('pageerror', e => record('page_error', e.message));
  page.on('requestfailed', r => record('request_failed', r.url() + ' ' + (r.failure() || {}).errorText));
  page.on('dialog', async d => { record('dialog', d.message()); await d.dismiss().catch(() => {}); });
  const origin = new URL(url).origin;
  await page.goto(url, { waitUntil: 'networkidle2', timeout: 45000 }).catch(e => record('goto_failed', e.message));
  const junk = ["' OR 1=1 --", 'A'.repeat(300), '💥<script>1</script>', '-1e999', '   '];
  const deadline = Date.now() + seconds * 1000;
  let step = 0;
  while (Date.now() < deadline) {
    step += 1;
    try {
      const inputs = await page.$$('input:not([type=hidden]), textarea');
      for (let i = 0; i < inputs.length && i < 6; i++) {
        const v = junk[(step + i) % junk.length];
        await inputs[i].click({ clickCount: 3 }).catch(() => {});
        await inputs[i].type(v, { delay: 5 }).catch(() => {});
      }
      const clickables = await page.$$('button, a[href], [role=button], input[type=submit]');
      if (clickables.length) {
        const el = clickables[step % clickables.length];
        const href = await page.evaluate(e => e.getAttribute && e.getAttribute('href'), el).catch(() => null);
        if (!href || href.startsWith('#') || href.startsWith('/') || href.startsWith(origin)) {
          await el.click({ delay: 10 }).catch(e => record('click_error', e.message));
          if (step % 4 === 0) {
            await el.click().catch(() => {});
            await el.click().catch(() => {});
          }
        }
      }
      if (step % 7 === 0) await page.goBack({ timeout: 8000 }).catch(() => {});
      if (!page.url().startsWith(origin)) {
        await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 20000 }).catch(() => {});
      }
      await new Promise(r => setTimeout(r, 250));
    } catch (e) {
      record('driver_error', e.message);
      const shot = path.join(outDir, 'error-' + step + '.png');
      await page.screenshot({ path: shot }).catch(() => {});
    }
  }
  fs.writeFileSync(path.join(outDir, 'events.json'), JSON.stringify({ steps: step, events }, null, 2));
  await browser.close();
})();
"""


def qa_prepare_runtime():
    os.makedirs(QA_CACHE, exist_ok=True)
    marker = os.path.join(QA_CACHE, "node_modules", "puppeteer-core", "package.json")
    if not os.path.exists(marker):
        if not os.path.exists(os.path.join(QA_CACHE, "package.json")):
            with open(os.path.join(QA_CACHE, "package.json"), "w", encoding="utf-8") as f:
                json.dump({"name": "xyra-qa-runtime", "private": True}, f)
        code, out = RUNNER(["npm", "install", "puppeteer-core@23", "--no-audit",
                            "--no-fund", "--silent"], cwd=QA_CACHE, timeout=600)
        if code != 0:
            raise RuntimeError(f"npm install puppeteer-core failed: {tail(out, 10)}")
    return QA_CACHE


def qa_summarize(report, vendor="grok"):
    prompt = (
        "You are a QA lead. Below is a raw event log from an automated monkey-testing "
        "session against a web app. Produce a concise bug report: group duplicate "
        "events, keep only real defects (console errors, page errors, failed "
        "same-origin requests, dialog storms), and for each give severity, a "
        "hypothesis of the cause and a suggested reproduction. Plain text, no tables.\n\n"
        + json.dumps(report)[:12000]
    )
    code, out = fixer_run(vendor, prompt, os.getcwd(), timeout=300)
    return out.strip() if code == 0 else None


def qa_run(url, seconds=90, out_dir=None, summarize=True, vendor="grok"):
    chrome = chrome_path()
    if not chrome:
        return {"ok": False, "error": "no Chrome/Chromium found; install one or set XYRA_CHROME"}
    if not shutil.which("node") or not shutil.which("npm"):
        return {"ok": False, "error": "node and npm are required for the QA agent"}
    runtime = qa_prepare_runtime()
    out_dir = out_dir or tempfile.mkdtemp(prefix="xyra-qa-")
    os.makedirs(out_dir, exist_ok=True)
    script = os.path.join(runtime, "qa_driver.js")
    with open(script, "w", encoding="utf-8") as f:
        f.write(QA_SCRIPT)
    env = dict(os.environ, QA_URL=url, QA_SECONDS=str(seconds),
               QA_OUT=out_dir, QA_CHROME=chrome)
    code, out = RUNNER(["node", script], cwd=runtime, timeout=seconds + 120, env=env)
    events_path = os.path.join(out_dir, "events.json")
    if not os.path.exists(events_path):
        return {"ok": False, "error": f"qa driver produced no events: {tail(out, 12)}"}
    with open(events_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    defects = [e for e in report["events"]
               if e["type"] in ("console_error", "page_error", "request_failed")]
    result = {"ok": True, "url": url, "steps": report.get("steps"),
              "defect_count": len(defects), "defects": defects[:80],
              "report_dir": out_dir}
    if summarize and defects:
        summary = qa_summarize(result, vendor=vendor)
        if summary:
            result["summary"] = summary
            with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as f:
                f.write(summary + "\n")
    return result


TOOLS = [
    {"name": "sandbox_verify",
     "description": "Run the repository's tests in an isolated git worktree snapshot that includes the current uncommitted changes, without touching the working tree. Call this BEFORE presenting any non-trivial diff to the user, and only present code that passed. mode 'dirty' snapshots staged+unstaged+untracked changes, 'staged' only staged, 'head' verifies HEAD as-is.",
     "inputSchema": {"type": "object", "properties": {
         "path": {"type": "string", "description": "Repository root or any path inside it"},
         "mode": {"type": "string", "enum": ["dirty", "staged", "head"]}},
         "required": ["path"]}},
    {"name": "ui_check",
     "description": "Render a URL headless, screenshot it and have a local vision model judge it against an expectation (layout, alignment, overflow, contrast). Use after any frontend change to SEE the result instead of guessing. Works with http(s) and file:// URLs.",
     "inputSchema": {"type": "object", "properties": {
         "url": {"type": "string"},
         "expectation": {"type": "string", "description": "What the page should look like"}},
         "required": ["url", "expectation"]}},
    {"name": "ui_compare",
     "description": "Render a URL and compare the screenshot against a design mockup image (e.g. a Figma export PNG) with a local vision model. Returns the visible differences ranked by severity.",
     "inputSchema": {"type": "object", "properties": {
         "url": {"type": "string"},
         "design_path": {"type": "string", "description": "Absolute path to the design PNG"}},
         "required": ["url", "design_path"]}},
    {"name": "fleet_repos",
     "description": "List the repositories registered in the fleet manifest (.xyra/fleet.json): the related backend/frontend/infra repos of this project.",
     "inputSchema": {"type": "object", "properties": {}}},
    {"name": "fleet_search",
     "description": "Search a term across every repository in the fleet at once. Use to find all cross-repo usages of an endpoint, type or config key before changing it.",
     "inputSchema": {"type": "object", "properties": {
         "term": {"type": "string"}}, "required": ["term"]}},
    {"name": "fleet_impact",
     "description": "Cross-repo impact analysis for a symbol: which repo defines it and which repos reference it, so a change can be applied consistently everywhere in one pass.",
     "inputSchema": {"type": "object", "properties": {
         "term": {"type": "string"}}, "required": ["term"]}},
    {"name": "qa_run",
     "description": "Drive a running web app like a hostile user for a short budget: fill forms with junk, click rapidly, navigate randomly, and collect console errors, page errors and failed requests into a defect report.",
     "inputSchema": {"type": "object", "properties": {
         "url": {"type": "string"},
         "seconds": {"type": "integer", "description": "Time budget, max 120 for tool calls"}},
         "required": ["url"]}},
]


def rpc_send(obj):
    sys.stdout.write(json.dumps(obj) + "\n")
    sys.stdout.flush()


def tool_call(name, args):
    if name == "sandbox_verify":
        mode = args.get("mode", "dirty")
        res = sandbox_verify(args["path"], mode="dirty" if mode == "head" else mode)
        if res["ok"] is None:
            return f"No runner detected: {res['reason']}"
        status = "PASSED" if res["ok"] else "FAILED"
        step = res["steps"][0]
        return f"Sandbox verification {status}\ncommand: {step['command']} (exit {step['exit']})\n\n{step['tail']}"
    if name == "ui_check":
        res = ui_check(args["url"], args["expectation"])
        if not res.get("ok"):
            return f"error: {res.get('error')}"
        return (f"engine {res['engine']}, model {res['model']}, screenshot {res['screenshot']}\n"
                + json.dumps(res["verdict"], indent=2, ensure_ascii=False))
    if name == "ui_compare":
        res = ui_compare(args["url"], args["design_path"])
        if not res.get("ok"):
            return f"error: {res.get('error')}"
        return (f"engine {res['engine']}, model {res['model']}, screenshot {res['screenshot']}\n"
                + json.dumps(res["verdict"], indent=2, ensure_ascii=False))
    if name == "fleet_repos":
        fleet = load_fleet()
        lines = [f"{r['name']} ({r['role']}): {r['path']}" for r in fleet["repos"]]
        return f"manifest: {fleet['manifest']}\n" + "\n".join(lines)
    if name == "fleet_search":
        res = fleet_search(args["term"])
        if not res["results"]:
            return "no hits in any fleet repository"
        parts = []
        for block in res["results"]:
            hits = "\n".join(f"  {h['path']}:{h['line']}  {h['text']}" for h in block["hits"][:15])
            parts.append(f"{block['repo']} ({block['role']}):\n{hits}")
        return "\n\n".join(parts)
    if name == "fleet_impact":
        res = fleet_impact(args["term"])
        return json.dumps(res["summary"], indent=2) + "\n\n" + json.dumps(res["impact"], indent=2)[:6000]
    if name == "qa_run":
        seconds = min(int(args.get("seconds", 60)), 120)
        res = qa_run(args["url"], seconds=seconds, summarize=False)
        if not res.get("ok"):
            return f"error: {res.get('error')}"
        head = f"steps: {res['steps']}, defects: {res['defect_count']}, report: {res['report_dir']}"
        sample = "\n".join(f"  [{d['type']}] {d['detail']}" for d in res["defects"][:15])
        return head + ("\n" + sample if sample else "\nno defects observed")
    raise ValueError(f"unknown tool: {name}")


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
                "serverInfo": {"name": "xyra-tools", "version": "0.1.0"},
            }})
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            rpc_send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            params = msg.get("params", {})
            try:
                text = tool_call(params.get("name"), params.get("arguments", {}))
                rpc_send({"jsonrpc": "2.0", "id": mid,
                          "result": {"content": [{"type": "text", "text": text}]}})
            except Exception as e:
                rpc_send({"jsonrpc": "2.0", "id": mid,
                          "result": {"content": [{"type": "text", "text": f"error: {e}"}],
                                     "isError": True}})
        elif mid is not None:
            rpc_send({"jsonrpc": "2.0", "id": mid,
                      "error": {"code": -32601, "message": "method not found"}})


def cli_out(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))


def main():
    argv = sys.argv[1:]
    if not argv:
        print("usage: xyra-tools {mcp|sandbox|vision|fleet|qa} ...", file=sys.stderr)
        sys.exit(1)
    cmd, rest = argv[0], argv[1:]
    if cmd == "mcp":
        run_mcp()
    elif cmd == "sandbox":
        sub = rest[0] if rest else "verify"
        repo = next((rest[i + 1] for i, a in enumerate(rest) if a == "--repo"), os.getcwd())
        if sub == "verify":
            mode = "staged" if "--staged" in rest else "dirty"
            res = sandbox_verify(repo, mode=mode, keep="--keep" in rest)
            cli_out(res)
            sys.exit(0 if res["ok"] else 1)
        elif sub == "loop":
            rounds = int(next((rest[i + 1] for i, a in enumerate(rest) if a == "--rounds"), "3"))
            vendor = next((rest[i + 1] for i, a in enumerate(rest) if a == "--vendor"), "grok")
            out_path = next((rest[i + 1] for i, a in enumerate(rest) if a == "--out"), None)
            res = sandbox_loop(repo, rounds=rounds, vendor=vendor, out_path=out_path,
                               log=lambda m: print(f"[sandbox] {m}", file=sys.stderr))
            if res.get("ok") and not out_path:
                print(res["diff"])
                print(f"[sandbox] proven: {res['proof']}", file=sys.stderr)
            else:
                cli_out({k: v for k, v in res.items() if k != "diff"})
            sys.exit(0 if res.get("ok") else 1)
        else:
            print(f"unknown sandbox subcommand: {sub}", file=sys.stderr)
            sys.exit(1)
    elif cmd == "vision":
        sub = rest[0] if rest else ""
        if sub == "check" and len(rest) >= 3:
            cli_out(ui_check(rest[1], " ".join(rest[2:])))
        elif sub == "compare" and len(rest) >= 3:
            cli_out(ui_compare(rest[1], rest[2]))
        else:
            print("usage: xyra-tools vision {check <url> <expectation>|compare <url> <design.png>}",
                  file=sys.stderr)
            sys.exit(1)
    elif cmd == "fleet":
        sub = rest[0] if rest else "list"
        if sub == "list":
            cli_out(load_fleet())
        elif sub == "init":
            os.makedirs(".xyra", exist_ok=True)
            path = os.path.join(".xyra", "fleet.json")
            if not os.path.exists(path):
                with open(path, "w", encoding="utf-8") as f:
                    json.dump({"repos": [{"name": os.path.basename(os.getcwd()),
                                          "path": os.getcwd(), "role": "backend"}]}, f, indent=2)
            print(f"manifest ready: {path}")
        elif sub == "search" and len(rest) >= 2:
            cli_out(fleet_search(" ".join(rest[1:])))
        elif sub == "impact" and len(rest) >= 2:
            cli_out(fleet_impact(rest[1]))
        elif sub == "refactor" and len(rest) >= 2:
            term = next((rest[i + 1] for i, a in enumerate(rest) if a == "--symbol"), None)
            task = " ".join(a for i, a in enumerate(rest[1:], 1)
                            if rest[i - 1] != "--symbol" and a != "--symbol" and a != "--execute")
            res = fleet_refactor(task, term=term, execute="--execute" in rest,
                                 log=lambda m: print(f"[fleet] {m}", file=sys.stderr))
            cli_out(res)
        else:
            print("usage: xyra-tools fleet {list|init|search <term>|impact <symbol>|refactor <task> [--symbol X] [--execute]}",
                  file=sys.stderr)
            sys.exit(1)
    elif cmd == "qa":
        if rest and rest[0] == "run" and len(rest) >= 2:
            seconds = int(next((rest[i + 1] for i, a in enumerate(rest) if a == "--seconds"), "90"))
            res = qa_run(rest[1], seconds=seconds)
            cli_out(res)
            sys.exit(0 if res.get("ok") else 1)
        print("usage: xyra-tools qa run <url> [--seconds N]", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
