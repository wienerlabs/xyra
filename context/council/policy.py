from __future__ import annotations

import fnmatch
import re

from .models import Config


def _changed_paths(diff: str) -> list[str]:
    return re.findall(r"^\+\+\+ b/(.+)$", diff, re.MULTILINE)


def _match(path: str, globs: list[str]) -> bool:
    for g in globs:
        if fnmatch.fnmatch(path, g) or fnmatch.fnmatch(path, "**/" + g):
            return True
    return False


def required_lenses(config: Config, diff: str, base: list[str]) -> list[str]:
    paths = _changed_paths(diff)
    lenses = list(base)
    for rule in config.rules:
        if any(_match(p, rule.paths) for p in paths):
            for lens in rule.require:
                if lens not in lenses:
                    lenses.append(lens)
    return lenses


def block_severities(config: Config, diff: str) -> list[str]:
    paths = _changed_paths(diff)
    sev = set(s.lower() for s in config.block_on)
    for rule in config.rules:
        if rule.block_on and any(_match(p, rule.paths) for p in paths):
            sev |= {s.lower() for s in rule.block_on}
    return sorted(sev, key=lambda s: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(s, 9))
