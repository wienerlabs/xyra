import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import xyra_context
import xyra_tools


def make_git_repo(files):
    root = tempfile.mkdtemp(prefix="xyra-test-repo-")
    for rel, content in files.items():
        path = os.path.join(root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    for argv in (["git", "init", "-q"], ["git", "add", "-A"],
                 ["git", "commit", "-qm", "init"]):
        subprocess.run(argv, cwd=root, env=env, capture_output=True, check=True)
    return root


class DetectCommandsTest(unittest.TestCase):
    def check(self, files, expected_test):
        root = tempfile.mkdtemp(prefix="xyra-test-")
        for name in files:
            open(os.path.join(root, name), "w").close()
        try:
            self.assertEqual(xyra_tools.detect_commands(root)["test"], expected_test)
        finally:
            shutil.rmtree(root, ignore_errors=True)

    def test_runners(self):
        self.check(["pnpm-lock.yaml"], "pnpm test")
        self.check(["package.json"], "npm test")
        self.check(["Cargo.toml"], "cargo test")
        self.check(["pyproject.toml"], "python3 -m pytest -q")
        self.check(["go.mod"], "go test ./...")
        self.check([], None)


class ScriptedRunner:
    def __init__(self, script):
        self.script = script
        self.calls = []

    def __call__(self, argv, cwd=None, timeout=120, env=None, input_text=None):
        self.calls.append((argv, cwd))
        for matcher, result in self.script:
            if matcher(argv):
                if callable(result):
                    return result(argv, cwd)
                return result
        return xyra_tools.run_cmd(argv, cwd=cwd, timeout=timeout, env=env,
                                  input_text=input_text)


class SandboxTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_git_repo({
            "package.json": json.dumps({"name": "t", "scripts": {"test": "true"}}),
            "src/app.js": "module.exports = 1;\n",
        })
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.addCleanup(setattr, xyra_tools, "RUNNER", xyra_tools.run_cmd)

    def test_verify_pass_and_worktree_isolation(self):
        with open(os.path.join(self.repo, "src", "app.js"), "a") as f:
            f.write("module.exports = 2;\n")
        runner = ScriptedRunner([
            (lambda a: a[0] == "bash", (0, "1 test passed")),
        ])
        xyra_tools.RUNNER = runner
        res = xyra_tools.sandbox_verify(self.repo)
        self.assertTrue(res["ok"])
        self.assertEqual(res["steps"][0]["command"], "npm test")
        bash_calls = [c for c in runner.calls if c[0][0] == "bash"]
        self.assertNotEqual(os.path.realpath(bash_calls[0][1]),
                            os.path.realpath(self.repo))
        code, out = xyra_tools.run_cmd(["git", "-C", self.repo, "worktree", "list"])
        self.assertEqual(len([l for l in out.splitlines() if l.strip()]), 1)

    def test_verify_fail(self):
        xyra_tools.RUNNER = ScriptedRunner([
            (lambda a: a[0] == "bash", (1, "1 test failed: boom")),
        ])
        res = xyra_tools.sandbox_verify(self.repo)
        self.assertFalse(res["ok"])
        self.assertIn("boom", res["steps"][0]["tail"])

    def test_verify_includes_untracked(self):
        with open(os.path.join(self.repo, "src", "new.js"), "w") as f:
            f.write("module.exports = 3;\n")
        seen = {}

        def bash_result(argv, cwd):
            seen["exists"] = os.path.exists(os.path.join(cwd, "src", "new.js"))
            return (0, "ok")

        xyra_tools.RUNNER = ScriptedRunner([(lambda a: a[0] == "bash", bash_result)])
        res = xyra_tools.sandbox_verify(self.repo)
        self.assertTrue(res["ok"])
        self.assertTrue(seen["exists"])

    def test_loop_fix_then_pass(self):
        state = {"round": 0}

        def bash_result(argv, cwd):
            state["round"] += 1
            return (1, "assertion failed") if state["round"] == 1 else (0, "all green")

        runner = ScriptedRunner([
            (lambda a: a[0] == "bash", bash_result),
            (lambda a: a[0] == "grok", (0, "fixed")),
        ])
        xyra_tools.RUNNER = runner
        res = xyra_tools.sandbox_loop(self.repo, rounds=3)
        self.assertTrue(res["ok"])
        self.assertIn("proof", res)
        grok_calls = [c for c in runner.calls if c[0][0] == "grok"]
        self.assertEqual(len(grok_calls), 1)
        self.assertNotEqual(os.path.realpath(grok_calls[0][1]),
                            os.path.realpath(self.repo))

    def test_loop_gives_up(self):
        runner = ScriptedRunner([
            (lambda a: a[0] == "bash", (1, "still broken")),
            (lambda a: a[0] == "grok", (0, "tried")),
        ])
        xyra_tools.RUNNER = runner
        res = xyra_tools.sandbox_loop(self.repo, rounds=2)
        self.assertFalse(res["ok"])


class GraphTest(unittest.TestCase):
    def setUp(self):
        self.repo = make_git_repo({
            "src/api.ts": "export function fetchUser() { return 1; }\n",
            "src/client.ts": "import { fetchUser } from './api';\nexport const c = fetchUser();\n",
            "src/page.tsx": "import { c } from './client';\nexport default function Page() { return c; }\n",
            "lib/util.py": "def helper():\n    return 1\n",
            "lib/main.py": "from lib.util import helper\n",
            "rs/Cargo.toml": "[package]\nname = \"rs\"\n",
            "rs/src/lib.rs": "pub mod engine;\n",
            "rs/src/engine.rs": "pub fn spin() {}\n",
        })
        self.addCleanup(shutil.rmtree, self.repo, True)
        self.addCleanup(shutil.rmtree, xyra_context.CACHE_DIR, True)
        self._old_cache = xyra_context.CACHE_DIR
        xyra_context.CACHE_DIR = tempfile.mkdtemp(prefix="xyra-test-cache-")
        self.addCleanup(setattr, xyra_context, "CACHE_DIR", self._old_cache)
        self._old_embed = xyra_context.embed
        xyra_context.embed = lambda texts: (_ for _ in ()).throw(RuntimeError("no ollama"))
        self.addCleanup(setattr, xyra_context, "embed", self._old_embed)

    def test_index_graph_without_embeddings(self):
        res = xyra_context.index(self.repo)
        self.assertGreaterEqual(res["symbols"], 5)
        self.assertGreaterEqual(res["import_edges"], 3)

    def test_impact_symbol(self):
        xyra_context.index(self.repo)
        res = xyra_context.impact(self.repo, "fetchUser")
        self.assertEqual(res["defined_in"], ["src/api.ts"])
        d1 = res["import_impact"][0]
        self.assertIn("src/client.ts", d1["files"])
        d2 = res["import_impact"][1]
        self.assertIn("src/page.tsx", d2["files"])
        self.assertIn("src/client.ts", res["text_references"])

    def test_impact_python_and_rust(self):
        xyra_context.index(self.repo)
        res = xyra_context.impact(self.repo, "lib/util.py")
        self.assertIn("lib/main.py", res["import_impact"][0]["files"])
        res = xyra_context.graph(self.repo, "rs/src/lib.rs")
        self.assertIn("rs/src/engine.rs", res["imports"])

    def test_symbol_search_without_embeddings(self):
        xyra_context.index(self.repo)
        hits = xyra_context.search(self.repo, "fetchUser")
        self.assertTrue(hits)
        self.assertEqual(hits[0]["path"], "src/api.ts")
        self.assertEqual(hits[0]["score"], 1.0)


class FleetTest(unittest.TestCase):
    def setUp(self):
        self.back = make_git_repo({
            "api/users.ts": "export function getUserProfile() { return db(); }\n",
        })
        self.front = make_git_repo({
            "src/profile.tsx": "const p = api.getUserProfile();\n",
        })
        self.addCleanup(shutil.rmtree, self.back, True)
        self.addCleanup(shutil.rmtree, self.front, True)
        self.manifest = os.path.join(tempfile.mkdtemp(prefix="xyra-test-m-"), "fleet.json")
        with open(self.manifest, "w", encoding="utf-8") as f:
            json.dump({"repos": [
                {"name": "backend", "path": self.back, "role": "backend"},
                {"name": "frontend", "path": self.front, "role": "frontend"},
            ]}, f)

    def test_search_across_repos(self):
        res = xyra_tools.fleet_search("getUserProfile", manifest=self.manifest)
        names = {b["repo"] for b in res["results"]}
        self.assertEqual(names, {"backend", "frontend"})

    def test_impact_orders_definition_first(self):
        res = xyra_tools.fleet_impact("getUserProfile", manifest=self.manifest)
        self.assertEqual(res["impact"][0]["repo"], "backend")
        self.assertTrue(res["impact"][0]["definitions"])
        self.assertTrue(res["impact"][1]["references"])

    def test_refactor_plan_briefs(self):
        res = xyra_tools.fleet_refactor(
            "rename getUserProfile to fetchProfile", term="getUserProfile",
            manifest=self.manifest, execute=False)
        self.assertEqual(len(res["plan"]), 2)
        self.assertIn("frontend", res["plan"][0]["brief"])
        self.assertIsNone(res["executed"])


class VisionQaTest(unittest.TestCase):
    def test_chrome_env_override(self):
        probe = tempfile.NamedTemporaryFile(delete=False)
        self.addCleanup(os.unlink, probe.name)
        os.environ["XYRA_CHROME"] = probe.name
        self.addCleanup(os.environ.pop, "XYRA_CHROME", None)
        self.assertEqual(xyra_tools.chrome_path(), probe.name)

    def test_prompts_demand_json(self):
        self.assertIn('"matches"', xyra_tools.build_check_prompt("centered button"))
        self.assertIn('"faithful"', xyra_tools.build_compare_prompt())

    def test_qa_script_shape(self):
        self.assertIn("puppeteer-core", xyra_tools.QA_SCRIPT)
        self.assertIn("console_error", xyra_tools.QA_SCRIPT)
        self.assertIn("requestfailed", xyra_tools.QA_SCRIPT)

    def test_qa_requires_chrome(self):
        old = xyra_tools.chrome_path
        xyra_tools.chrome_path = lambda: None
        self.addCleanup(setattr, xyra_tools, "chrome_path", old)
        res = xyra_tools.qa_run("http://localhost:1")
        self.assertFalse(res["ok"])
        self.assertIn("Chrome", res["error"])


class McpSurfaceTest(unittest.TestCase):
    def test_tool_names_unique_and_described(self):
        names = [t["name"] for t in xyra_tools.TOOLS]
        self.assertEqual(len(names), len(set(names)))
        for t in xyra_tools.TOOLS:
            self.assertTrue(t["description"])
            self.assertIn("inputSchema", t)
        ctx_names = [t["name"] for t in xyra_context.TOOLS]
        self.assertIn("code_impact", ctx_names)
        self.assertIn("code_graph", ctx_names)


if __name__ == "__main__":
    unittest.main()
