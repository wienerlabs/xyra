---
name: wiener-autonomy
description: How to use Xyra's autonomy tools (sandbox verification, vision UI checks, dependency impact analysis, fleet operations, QA sweeps) so code is proven before it is presented. Use whenever writing, changing or reviewing code in a Xyra workspace.
---

# Prove it before you present it

Xyra ships local tools that let you verify your own work instead of handing the user something you hope compiles. Use them without being asked.

## Before presenting any non-trivial change

Call `sandbox_verify` (MCP, xyra-tools) or run `xyra-sandbox verify`. It copies the uncommitted changes into an isolated git worktree and runs the project's own test or build command there, so nothing in the user's working tree is touched.

- Present only code that passed. If it fails, read the output, fix the root cause and verify again.
- For a longer autonomous loop, `xyra-sandbox loop --rounds 3` iterates fix and re-test in the snapshot and emits only the proven diff.
- The verdict belongs in the reply: say which command ran and that it exited zero.

Skip verification only when the repository has no test or build runner, and say so explicitly instead of implying the code was checked.

## After any UI change

Call `ui_check` with the page URL and a plain description of what it should look like. The tool renders the page headless, screenshots it and has a vision model judge the result. Trust the verdict over your own assumption; you cannot see CSS by reading it.

- When a design mockup exists, use `ui_compare` with the export path instead.
- If the verdict lists high severity issues, fix them and re-check before replying.
- The page must be reachable. If the dev server is not running, ask the user to start it rather than starting a blocking server yourself.

## Before touching anything shared

Call `code_impact` (MCP, xyra-context) with the symbol or file you are about to rename, move or change. It returns the definition site, every file that imports it by transitive distance, and every textual reference.

- Update the whole returned chain in one pass. Do not discover breakage by running tests repeatedly.
- `code_graph` shows one file's neighborhood when you need to understand a module before editing it.
- Run `xyra-context index <repo>` once per repository, and again after large changes.

## Across repositories

When the project has a fleet manifest (`.xyra/fleet.json`), a contract change rarely lives in one repo.

- `fleet_impact` shows which repo defines a symbol and which repos consume it.
- `fleet_search` finds every cross-repo usage of an endpoint name, type or config key.
- `xyra-fleet refactor "<task>" --symbol X --execute` drives the same change through every affected repository in sequence.
- If there is no manifest yet, tell the user to run `xyra-fleet connect` and pick their repos from GitHub; do not hand-write the manifest.

## After a user-facing feature

Offer a QA sweep: `qa_run` crawls the running app, feeds every input hostile values, clicks aggressively and reports console errors, page errors, HTTP 5xx, failed requests and accessibility problems ranked by severity. Feed the findings back into a fix round rather than reporting them raw.

## Reporting

State the evidence, not the intention. "Tests pass in the sandbox (npm test, exit 0) and the vision check found no high severity issues" is a report. "This should work" is not.
