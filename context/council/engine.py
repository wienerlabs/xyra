from __future__ import annotations

import concurrent.futures as futures
import json
import os
import subprocess

from . import cache as cache_mod
from . import policy as policy_mod
from . import providers
from . import redact as redact_mod
from . import verdict as verdict_mod
from .lenses import resolve
from .logging import Logger
from .models import Config, LensResult, Verdict


class Council:
    def __init__(self, root: str, config: Config, log: Logger):
        self.root = root
        self.config = config
        self.log = log
        self.redacted = 0

    def _diff(self, staged: bool) -> str:
        args = ["git", "--no-pager", "diff"] + (["--staged"] if staged else [])
        out = subprocess.run(args, cwd=self.root, capture_output=True, text=True)
        return out.stdout

    def _context(self, task: str) -> str:
        if not task:
            return ""
        ctx = os.environ.get("XYRA_CONTEXT_BIN", "xyra-context")
        try:
            subprocess.run([ctx, "index", self.root], capture_output=True, timeout=180)
            out = subprocess.run([ctx, "search", self.root, task], capture_output=True, text=True, timeout=60)
            return out.stdout.strip()[:4000]
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ""

    def _review_one(self, vendor: str, lens: str, prompt_body: str, diff: str) -> LensResult:
        prompt = f"{prompt_body}\n\n{verdict_mod.INSTRUCTION}\n\nDiff:\n{diff}"
        ck = cache_mod.key(vendor, lens, prompt_body, diff)
        if self.config.cache_enabled:
            hit = cache_mod.get(ck)
            if hit is not None:
                self.log.event("cache_hit", lens=lens)
                return hit
        self.log.event("review_start", lens=lens, vendor=vendor)
        text, err = providers.run(vendor, "read", prompt, self.config.timeout, self.config.retries)
        if err:
            self.log.event("review_error", lens=lens, error=err)
            return LensResult(lens=lens, error=err)
        result = verdict_mod.parse(text, lens)
        if self.config.cache_enabled:
            cache_mod.put(ck, result)
        self.log.event("review_done", lens=lens, findings=len(result.findings), error=result.error or None)
        return result

    def review(self, diff: str, task: str, vendor: str, base_lenses: list[str]) -> Verdict:
        if self.config.redact_enabled:
            diff, n = redact_mod.redact(diff, self.config.redact_patterns)
            if n:
                self.redacted += n
                self.log.event("redacted", secrets=n)
        wanted = policy_mod.required_lenses(self.config, diff, base_lenses)
        prompts = resolve(self.config, wanted)
        results: list[LensResult] = []
        with futures.ThreadPoolExecutor(max_workers=max(1, len(prompts))) as pool:
            jobs = {pool.submit(self._review_one, vendor, ln, body, diff): ln for ln, body in prompts.items()}
            for job in futures.as_completed(jobs):
                results.append(job.result())
        results.sort(key=lambda r: r.lens)
        block_on = policy_mod.block_severities(self.config, diff)
        return verdict_mod.decide(results, block_on)

    def review_panel(self, diff: str, task: str, base_lenses: list[str]) -> Verdict:
        panel = self.config.panel()
        if len(panel) == 1:
            return self.review(diff, task, panel[0], base_lenses)
        verdicts = []
        for rv in panel:
            v = self.review(diff, task, rv, base_lenses)
            for f in v.findings:
                f.lens = f"{rv}:{f.lens}"
            verdicts.append((rv, v))
        findings = [f for _, v in verdicts for f in v.findings]
        findings.sort(key=lambda f: -f.rank())
        results = [r for _, v in verdicts for r in v.results]
        block_votes = sum(1 for _, v in verdicts if v.label == "BLOCK")
        if self.config.consensus == "majority":
            blocked = block_votes * 2 > len(verdicts)
        else:
            blocked = block_votes > 0
        blocking = [f for _, v in verdicts for f in v.blocking] if blocked else []
        errored = any(v.label == "INCONCLUSIVE" for _, v in verdicts)
        if blocked:
            label = "BLOCK"
        elif findings:
            label = "APPROVE WITH NOTES"
        elif errored:
            label = "INCONCLUSIVE"
        else:
            label = "CLEAN"
        self.log.event("consensus", panel=panel, mode=self.config.consensus, block_votes=block_votes, label=label)
        return Verdict(label=label, findings=findings, results=results, blocking=blocking)

    def build(self, vendor: str, prompt: str) -> str | None:
        _, err = providers.run(vendor, "write", prompt, self.config.timeout, self.config.retries)
        return err

    def run_review_only(self, staged: bool) -> tuple[Verdict, list[Verdict]]:
        diff = self._diff(staged)
        if not diff.strip():
            raise RuntimeError("no changes to review (git diff is empty)")
        v = self.review_panel(diff, "", self.config.lenses)
        return v, [v]

    def run_task(self, task: str) -> tuple[Verdict, list[Verdict]]:
        ctx = self._context(task)
        build_prompt = (
            f"Task: {task}\n\nFollow the wiener-conventions skill strictly. Make the change "
            f"directly in the working tree, then stop. Relevant code context:\n{ctx}"
        )
        self.log.say(f"== {providers.label(self.config.builder)} implements ==\n")
        err = self.build(self.config.builder, build_prompt)
        if err:
            raise RuntimeError(f"{providers.label(self.config.builder)} failed: {err}")

        rounds: list[Verdict] = []
        for rnd in range(1, self.config.rounds + 1):
            diff = self._diff(False)
            if not diff.strip():
                v = Verdict(label="CLEAN")
                rounds.append(v)
                return v, rounds
            self.log.say(f"\n== round {rnd}: {'/'.join(providers.label(p) for p in self.config.panel())} cross-examines ==\n")
            v = self.review_panel(diff, task, self.config.lenses)
            rounds.append(v)
            if v.label != "BLOCK" or rnd == self.config.rounds:
                return v, rounds
            self.log.say(f"\n== {providers.label(self.config.builder)} addresses {len(v.blocking)} blocking findings ==\n")
            fix_prompt = (
                f"A rival reviewer blocked your change for task '{task}'. Address only the genuine "
                f"blocking findings with minimal edits, ignore false positives. Findings:\n"
                f"{json.dumps([f.__dict__ for f in v.blocking], indent=2)}"
            )
            err = self.build(self.config.builder, fix_prompt)
            if err:
                self.log.say(f"fix round failed: {err}\n")
                return v, rounds
        return rounds[-1], rounds
