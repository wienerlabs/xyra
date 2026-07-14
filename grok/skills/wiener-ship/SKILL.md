---
name: wiener-ship
description: Wiener Labs pre-push and shipping checklist. Use when the user asks to commit, push, ship, release or finish a piece of work in any Wiener Labs project.
---

# Shipping checklist

Complete these steps in order before any push. Report each step's result.

## Verify

1. Run the test suite and the type check. Both must be green. If the project has a lint step, run it.
2. Run the production build when the change touches build-relevant code. A green dev server does not count as a verified build.
3. Scan the diff for secrets: keys, tokens, connection strings, seed phrases. Also scan for accidental debug output.

## Commit

4. Format: type colon description, where type is feat, fix, refactor, docs, test, chore, perf or ci. Lowercase imperative description, no trailing period.
5. No attribution or co-author lines.
6. One logical change per commit. Split unrelated changes.

## Push

7. Solo projects push directly to main. Pull requests are only for automated dependency updates and multi-person repositories.
8. Never force-push a shared branch.
9. If the project deploys automatically on push, state what will go live and double check the money-touching paths in the diff before pushing.

## Release extras

10. When tagging a release: bump the version, update the changelog, verify the artifact builds from a clean checkout.
