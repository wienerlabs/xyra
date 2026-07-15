import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from council import redact, verdict, policy, sarif
from council.models import Config, Finding, LensResult, PolicyRule


class RedactTest(unittest.TestCase):
    def test_private_key(self):
        t = "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----"
        out, n = redact.redact(t)
        self.assertEqual(n, 1)
        self.assertNotIn("abc", out)

    def test_env_secret(self):
        out, n = redact.redact("export API_KEY=supersecret12345")
        self.assertGreaterEqual(n, 1)
        self.assertNotIn("supersecret12345", out)

    def test_solana_keypair(self):
        arr = "[" + ",".join(["12"] * 40) + "]"
        _, n = redact.redact(arr)
        self.assertEqual(n, 1)

    def test_clean(self):
        out, n = redact.redact("const x = 1")
        self.assertEqual(n, 0)
        self.assertEqual(out, "const x = 1")


class VerdictTest(unittest.TestCase):
    def test_fenced(self):
        r = verdict.parse('```json\n{"findings":[{"severity":"high","issue":"x","file":"a.ts","line":3}],"summary":"s"}\n```', "security")
        self.assertEqual(len(r.findings), 1)
        self.assertEqual(r.findings[0].severity, "high")

    def test_unparseable(self):
        r = verdict.parse("no json here", "correctness")
        self.assertTrue(r.error)

    def test_decide_block(self):
        rs = [LensResult(lens="security", findings=[Finding(severity="critical", issue="x", lens="security")])]
        v = verdict.decide(rs, ["critical", "high"])
        self.assertEqual(v.label, "BLOCK")
        self.assertEqual(len(v.blocking), 1)

    def test_decide_notes(self):
        rs = [LensResult(lens="conventions", findings=[Finding(severity="low", issue="x", lens="conventions")])]
        self.assertEqual(verdict.decide(rs, ["critical", "high"]).label, "APPROVE WITH NOTES")

    def test_decide_clean(self):
        self.assertEqual(verdict.decide([LensResult(lens="tests")], ["critical"]).label, "CLEAN")

    def test_decide_inconclusive(self):
        self.assertEqual(verdict.decide([LensResult(lens="tests", error="boom")], ["critical"]).label, "INCONCLUSIVE")


class PolicyTest(unittest.TestCase):
    def setUp(self):
        self.diff = "diff --git a/programs/vault.rs b/programs/vault.rs\n+++ b/programs/vault.rs\n+let x = 1.0;\n"
        self.cfg = Config(rules=[PolicyRule(paths=["programs/**"], require=["security"], block_on=["medium"])])

    def test_required_lenses_added(self):
        out = policy.required_lenses(self.cfg, self.diff, ["correctness"])
        self.assertIn("security", out)

    def test_block_severities_escalated(self):
        sev = policy.block_severities(self.cfg, self.diff)
        self.assertIn("medium", sev)

    def test_no_match(self):
        d = "+++ b/README.md\n+text\n"
        self.assertNotIn("security", policy.required_lenses(self.cfg, d, ["correctness"]))


class SarifTest(unittest.TestCase):
    def test_shape(self):
        doc = sarif.to_sarif([Finding(severity="high", issue="x", file="a.ts", line=2, lens="security")])
        self.assertEqual(doc["version"], "2.1.0")
        self.assertEqual(doc["runs"][0]["results"][0]["level"], "error")


class WatchTest(unittest.TestCase):
    def setUp(self):
        import tempfile
        from council import watch
        self.watch = watch
        self.tmp = tempfile.mkdtemp()
        watch.QUEUE_DIR = os.path.join(self.tmp, "queue")

    def test_enqueue_and_show(self):
        root = os.path.join(self.tmp, "repo")
        self.watch.enqueue(root, {"ts": "t", "verdict": "BLOCK", "findings": 1, "blocking": 1, "top": []})
        path = self.watch.queue_path(root)
        self.assertTrue(os.path.isfile(path))
        with open(path) as f:
            self.assertIn("BLOCK", f.read())

    def test_queue_path_stable(self):
        r = "/some/repo"
        self.assertEqual(self.watch.queue_path(r), self.watch.queue_path(r))


if __name__ == "__main__":
    unittest.main(verbosity=2)
