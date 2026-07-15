from __future__ import annotations

import os
import tomllib

from .models import Config, PolicyRule


def _table(data: dict, key: str) -> dict:
    v = data.get(key)
    return v if isinstance(v, dict) else {}


def load(root: str, overrides: dict | None = None) -> Config:
    cfg = Config()
    path = os.path.join(root, ".xyra", "council.toml")
    data: dict = {}
    if os.path.isfile(path):
        with open(path, "rb") as f:
            data = tomllib.load(f)

    council = _table(data, "council")
    cfg.builder = council.get("builder", cfg.builder)
    cfg.reviewer = council.get("reviewer", cfg.reviewer)
    cfg.lenses = list(council.get("lenses", cfg.lenses))
    cfg.rounds = int(council.get("rounds", cfg.rounds))
    cfg.timeout = int(council.get("timeout", cfg.timeout))
    cfg.retries = int(council.get("retries", cfg.retries))

    policy = _table(data, "policy")
    cfg.block_on = list(policy.get("block_on", cfg.block_on))
    for rule in policy.get("rules", []) or []:
        if isinstance(rule, dict) and rule.get("paths"):
            cfg.rules.append(PolicyRule(
                paths=list(rule.get("paths", [])),
                require=list(rule.get("require", [])),
                block_on=list(rule.get("block_on", [])),
            ))

    cache = _table(data, "cache")
    cfg.cache_enabled = bool(cache.get("enabled", cfg.cache_enabled))

    redact = _table(data, "redact")
    cfg.redact_enabled = bool(redact.get("enabled", cfg.redact_enabled))
    cfg.redact_patterns = list(redact.get("extra_patterns", []))

    for lens in _table(data, "lenses").get("custom", []) or []:
        if isinstance(lens, dict) and lens.get("name") and lens.get("prompt"):
            cfg.custom_lenses[str(lens["name"])] = str(lens["prompt"])

    for k, v in (overrides or {}).items():
        if v is not None:
            setattr(cfg, k, v)

    if cfg.builder == cfg.reviewer:
        raise ValueError("builder and reviewer vendor must differ")
    return cfg
