import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import xyra_mission
import xyra_tools


def make_repo():
    root = tempfile.mkdtemp(prefix="xyra-mission-test-")
    with open(os.path.join(root, "package.json"), "w") as f:
        json.dump({"name": "demo", "scripts": {"test": "node -e \"process.exit(0)\""}}, f)
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    for argv in (["git", "init", "-q"], ["git", "add", "-A"], ["git", "commit", "-qm", "init"]):
        subprocess.run(argv, cwd=root, env=env, capture_output=True, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, capture_output=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, capture_output=True)
    return root


class Agent:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = []

    def __call__(self, argv, cwd=None, timeout=120, env=None, input_text=None):
        if argv[0] in ("grok", "claude"):
            prompt = argv[-1]
            self.calls.append((argv[0], prompt))
            return self.behaviour(argv[0], prompt, cwd)
        return xyra_tools.run_cmd(argv, cwd=cwd, timeout=timeout, env=env, input_text=input_text)


TICKETS = '''```json
[{"id":"1","title":"add core module","scope":"create src/core.js","files":["src/core.js"],"depends_on":[]},
 {"id":"2","title":"use core in app","scope":"create src/app.js importing core","files":["src/app.js"],"depends_on":["1"]}]
```'''


class MissionTest(unittest.TestCase):
    def setUp(self):
        self.root = make_repo()
        self.addCleanup(shutil.rmtree, self.root, True)
        self.addCleanup(setattr, xyra_tools, "RUNNER", xyra_tools.run_cmd)

    def write(self, rel, text):
        p = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w") as f:
            f.write(text)

    def test_full_mission_runs_to_completion_unattended(self):
        def behaviour(vendor, prompt, cwd):
            if "Respond with exactly one fenced" in prompt and "TICKET" not in prompt:
                return (0, TICKETS)
            if "TICKET 1" in prompt:
                self.write("src/core.js", "module.exports = 1;\n")
                return (0, "done")
            if "TICKET 2" in prompt:
                self.write("src/app.js", "require('./core');\n")
                return (0, "done")
            return (0, "noop")

        agent = Agent(behaviour)
        xyra_tools.RUNNER = agent
        tickets = xyra_mission.plan_mission(self.root, "build a demo")
        state = xyra_mission.new_state(self.root, "build a demo", tickets,
                                       dict(xyra_mission.DEFAULT_BUDGET))
        xyra_mission.save_state(self.root, state)
        final = xyra_mission.loop(self.root, state, log=lambda m: None)

        self.assertEqual(final["status"], "completed")
        self.assertEqual([t["status"] for t in final["tickets"]], ["done", "done"])
        self.assertTrue(all(t["commit"] for t in final["tickets"]))
        code, out = xyra_tools.run_cmd(["git", "-C", self.root, "log", "--oneline"])
        self.assertEqual(len(out.strip().splitlines()), 3)
        self.assertTrue(os.path.exists(os.path.join(self.root, "src", "app.js")))

    def test_failed_tests_trigger_retry_with_other_vendor(self):
        state_box = {"n": 0}

        def behaviour(vendor, prompt, cwd):
            if "TICKET" not in prompt:
                return (0, '```json\n[{"id":"1","title":"x","scope":"y","files":[],"depends_on":[]}]\n```')
            state_box["n"] += 1
            if state_box["n"] == 1:
                self.write("broken.js", "syntax error")
                self.write("package.json", json.dumps(
                    {"name": "demo", "scripts": {"test": "node -e \"process.exit(1)\""}}))
                return (0, "attempted")
            self.write("package.json", json.dumps(
                {"name": "demo", "scripts": {"test": "node -e \"process.exit(0)\""}}))
            self.write("fixed.js", "ok\n")
            return (0, "fixed")

        agent = Agent(behaviour)
        xyra_tools.RUNNER = agent
        tickets = xyra_mission.plan_mission(self.root, "obj")
        state = xyra_mission.new_state(self.root, "obj", tickets, dict(xyra_mission.DEFAULT_BUDGET))
        final = xyra_mission.loop(self.root, state, log=lambda m: None)

        self.assertEqual(final["status"], "completed")
        t = final["tickets"][0]
        self.assertEqual(t["attempts"], 2)
        vendors = [v for v, _ in agent.calls if "TICKET" in _]
        self.assertEqual(vendors[:2], ["grok", "claude"])

    def test_repeated_failure_splits_then_quarantines(self):
        def behaviour(vendor, prompt, cwd):
            if "Split it into" in prompt:
                return (0, '```json\n[{"id":"a","title":"half","scope":"s","files":[],"depends_on":[]}]\n```')
            if "TICKET" not in prompt:
                return (0, '```json\n[{"id":"1","title":"hard","scope":"s","files":[],"depends_on":[]}]\n```')
            self.write("attempt.txt", "x")
            self.write("package.json", json.dumps(
                {"name": "demo", "scripts": {"test": "node -e \"process.exit(1)\""}}))
            return (0, "tried")

        xyra_tools.RUNNER = Agent(behaviour)
        tickets = xyra_mission.plan_mission(self.root, "obj")
        budget = dict(xyra_mission.DEFAULT_BUDGET, max_attempts_per_ticket=2,
                      max_consecutive_failures=99)
        state = xyra_mission.new_state(self.root, "obj", tickets, budget)
        final = xyra_mission.loop(self.root, state, log=lambda m: None)

        statuses = {t["id"]: t["status"] for t in final["tickets"]}
        self.assertEqual(statuses["1"], "split")
        child = [k for k in statuses if k.startswith("1.")]
        self.assertTrue(child, "split should create children")
        self.assertEqual(statuses[child[0]], "quarantined")
        self.assertEqual(len(statuses), 2, "children must not split recursively")
        self.assertIn(final["status"], ("completed", "blocked"))

    def test_dirty_tree_is_reset_between_failures(self):
        def behaviour(vendor, prompt, cwd):
            if "TICKET" not in prompt:
                return (0, '```json\n[{"id":"1","title":"t","scope":"s","files":[],"depends_on":[]}]\n```')
            self.write("junk.txt", "leftover")
            self.write("package.json", json.dumps(
                {"name": "demo", "scripts": {"test": "node -e \"process.exit(1)\""}}))
            return (0, "x")

        xyra_tools.RUNNER = Agent(behaviour)
        tickets = xyra_mission.plan_mission(self.root, "obj")
        budget = dict(xyra_mission.DEFAULT_BUDGET, max_attempts_per_ticket=1,
                      max_consecutive_failures=99)
        state = xyra_mission.new_state(self.root, "obj", tickets, budget)
        xyra_mission.loop(self.root, state, log=lambda m: None)
        self.assertFalse(os.path.exists(os.path.join(self.root, "junk.txt")))
        self.assertFalse(xyra_mission.working_tree_dirty(self.root))

    def test_stop_flag_halts_the_loop(self):
        def behaviour(vendor, prompt, cwd):
            if "TICKET" not in prompt:
                return (0, TICKETS)
            with open(xyra_mission.stop_path(self.root), "w") as f:
                f.write("stop")
            self.write("src/core.js", "x\n")
            return (0, "done")

        xyra_tools.RUNNER = Agent(behaviour)
        tickets = xyra_mission.plan_mission(self.root, "obj")
        state = xyra_mission.new_state(self.root, "obj", tickets, dict(xyra_mission.DEFAULT_BUDGET))
        final = xyra_mission.loop(self.root, state, log=lambda m: None)
        self.assertEqual(final["status"], "stopped")
        self.assertEqual(final["tickets"][0]["status"], "done")

    def test_budget_halts_and_state_survives_reload(self):
        def behaviour(vendor, prompt, cwd):
            if "TICKET" not in prompt:
                return (0, TICKETS)
            self.write("f.txt", "x")
            self.write("package.json", json.dumps(
                {"name": "demo", "scripts": {"test": "node -e \"process.exit(1)\""}}))
            return (0, "x")

        xyra_tools.RUNNER = Agent(behaviour)
        tickets = xyra_mission.plan_mission(self.root, "obj")
        budget = dict(xyra_mission.DEFAULT_BUDGET, max_consecutive_failures=2,
                      max_attempts_per_ticket=9)
        state = xyra_mission.new_state(self.root, "obj", tickets, budget)
        final = xyra_mission.loop(self.root, state, log=lambda m: None)
        self.assertEqual(final["status"], "halted")
        reloaded = xyra_mission.load_state(self.root)
        self.assertEqual(reloaded["status"], "halted")
        self.assertEqual(reloaded["id"], final["id"])

    def test_dependencies_are_respected(self):
        order = []

        def behaviour(vendor, prompt, cwd):
            if "TICKET" not in prompt:
                return (0, TICKETS)
            tid = "1" if "TICKET 1" in prompt else "2"
            order.append(tid)
            self.write(f"src/{tid}.js", "x\n")
            return (0, "done")

        xyra_tools.RUNNER = Agent(behaviour)
        tickets = xyra_mission.plan_mission(self.root, "obj")
        state = xyra_mission.new_state(self.root, "obj", tickets, dict(xyra_mission.DEFAULT_BUDGET))
        xyra_mission.loop(self.root, state, log=lambda m: None)
        self.assertEqual(order, ["1", "2"])

    def test_summary_shape(self):
        tickets = xyra_mission.normalize_tickets(
            [{"id": "1", "title": "a"}, {"id": "2", "title": "b"}])
        state = xyra_mission.new_state(self.root, "obj", tickets, dict(xyra_mission.DEFAULT_BUDGET))
        state["tickets"][0]["status"] = "done"
        state["done"] = 1
        s = xyra_mission.summarize(state)
        self.assertEqual(s["progress"], "1/2")
        self.assertEqual(s["percent"], 50)


if __name__ == "__main__":
    unittest.main()
