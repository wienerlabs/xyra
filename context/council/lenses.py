from __future__ import annotations

from .models import Config

BUILTIN = {
    "correctness": (
        "Correctness and robustness. Logic errors, wrong edge-case handling, "
        "unhandled rejections and error paths, race conditions, off-by-one, "
        "state that can desync, double-submit on money actions, missing idempotency keys on webhooks."
    ),
    "security": (
        "Security, with emphasis on funds. Money must be integer in the smallest unit "
        "(kurus, lamports, 10^6 USDC); flag any float money math. Solana destination "
        "addresses must come from canonical config, never copied from history (address poisoning). "
        "Flag secrets in client bundles, injection, SSRF, unsafe crypto, anon-client RPCs granted privileged access."
    ),
    "conventions": (
        "House conventions and simplicity. No code comments of any kind. No em dash character anywhere. "
        "No all-caps words in UI, no uppercase Tailwind class. No Server-to-Client prop carrying i18n "
        "interpolator functions (digest 500 in production). Flag scope creep: changes to files the task "
        "did not require. Prefer the restructuring that makes the change smaller and more direct."
    ),
    "performance": (
        "Performance and resource use. N+1 queries, unbounded loops over remote data, missing pagination, "
        "synchronous work on hot paths, needless re-renders, missing indexes, allocations in tight loops."
    ),
    "tests": (
        "Test coverage and verifiability. New behavior without tests, changed behavior with stale tests, "
        "untested error paths, assertions that cannot fail, flaky timing dependencies."
    ),
}


def resolve(config: Config, requested: list[str]) -> dict[str, str]:
    available = dict(BUILTIN)
    available.update(config.custom_lenses)
    out = {}
    for name in requested:
        if name in available:
            out[name] = available[name]
    return out
