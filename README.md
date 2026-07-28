<p align="center">
  <img src="assets/xyra-icon.png" width="128" alt="Xyra">
</p>

<h1 align="center">Xyra</h1>

<p align="center">The agentic code editor that never shows you code it has not proven. Flat-rate, local-first, and yours.</p>

## Why Xyra is different

Other agentic editors are metered clouds tied to one model vendor, and they hand you code they have never run. Xyra is the opposite, and the difference is architectural, not cosmetic:

- **Nothing reaches you unproven.** Before an agent presents a change, it runs the project's tests against an isolated snapshot of that change. Broken code gets fixed in the snapshot, not in your working tree.
- **A rival reviews every change.** One vendor writes, a rival vendor cross-examines through correctness, security and convention lenses. Metered editors cannot afford two frontier vendors per task. Xyra can, because it runs on flat-rate subscription quota.
- **The agent can see.** After a UI change it renders the page, screenshots it and has a vision model judge the result. It does not guess whether the button moved.
- **It knows, it does not estimate.** Beside semantic search there is a deterministic import graph, so "what breaks if I change this" is answered by traversal, not by embedding similarity.
- **One editor, every model.** Grok Build, Claude Code and local Ollama models live in one panel. Route the best agent per task, run them in parallel, stay vendor-independent.
- **Local-first and yours.** Embeddings, the graph, the QA runs and the visual checks are local. Telemetry is off. The whole setup ships as a repo your team owns.

## The autonomy engine

Five capabilities ship as local tools and are exposed to every panel agent over MCP, so agents reach for them unprompted:

### Invisible sandbox: `xyra-sandbox`

Agents prove code before you see it. `sandbox_verify` copies the uncommitted changes (tracked, staged and untracked) into a throwaway git worktree and runs the project's own test or build command there. Your working tree is never touched.

```bash
xyra-sandbox verify                    # run the project's tests against the current changes, isolated
xyra-sandbox verify --staged           # only what is staged
xyra-sandbox loop --rounds 3           # let a fixer model iterate until green, then print the proven diff
```

`xyra-sandbox loop` is the autonomous mode: on failure it hands the error to a fixer inside the snapshot, retries, and emits only a diff that has passed. The agent instructions make verification mandatory before presenting a non-trivial change.

### Vision: `xyra-vision`

The agent renders the page headless, screenshots it and asks a vision model whether it matches the intent. Grok is the default judge (subscription quota, no API cost) and a local Ollama vision model is the fallback.

```bash
xyra-vision check http://localhost:3000 "the hero button is centered and nothing overflows"
xyra-vision compare http://localhost:3000 ~/Downloads/figma-export.png
XYRA_VISION_PROVIDER=ollama xyra-vision check ...      # force the local model
```

Verdicts are structured JSON with issues ranked by severity, which is what makes them usable inside a fix loop. The topology view in this repository was fixed exactly that way: the vision tool rejected two attempts for label collision and unreadable edge direction before passing the third.

### Fleet: `xyra-fleet`

Modern projects are several repositories. Fleet gives agents one view across all of them, and setup happens from GitHub rather than a hand-written file.

```bash
xyra-fleet connect                     # pick your repos from GitHub, clone the missing ones, write the manifest
xyra-fleet list                        # what is in the fleet
xyra-fleet search getUserProfile       # every usage across every repo
xyra-fleet impact getUserProfile       # which repo defines it, which repos consume it
xyra-fleet refactor "rename the endpoint" --symbol getUserProfile --execute
```

`connect` lists your GitHub repositories through `gh`, clones what is missing and writes `.xyra/fleet.json` with guessed roles. The **Fleet** button in the status bar opens the same flow.

### Dependency graph: `xyra-context`

Beside the vector index there is a deterministic import graph parsed from the source (TypeScript, JavaScript, Python, Rust). It answers impact questions by traversal.

```bash
xyra-context index /path/to/repo
xyra-context search /path/to/repo "where is the auth middleware"
xyra-context impact /path/to/repo fetchUser      # definition, importers by distance, textual references
xyra-context graph /path/to/repo src/api.ts      # one file's neighborhood
```

The graph is built during indexing and works with Ollama off; semantic search simply degrades to symbol lookup in that case.

### QA agent: `xyra-qa`

A hostile user with a time budget. It crawls same-origin pages, optionally logs in, fills every input with type-aware junk (malformed emails, huge strings, injection strings, numeric overflow), clicks aggressively, and collects console errors, uncaught exceptions, HTTP 5xx, failed requests, accessibility problems and load timings.

```bash
xyra-qa run http://localhost:3000 --seconds 120
XYRA_QA_USER=demo@x.io XYRA_QA_PASS=secret xyra-qa run http://localhost:3000
```

Defects are deduplicated and ranked by severity into a markdown report, then summarized into a bug report with reproduction steps.

The agent instructions mandate the flow: verify in the sandbox before presenting, look at the UI after changing it, run impact analysis before touching shared contracts.

## Agent visibility surfaces

Six views render from real local data. Each has a task and a shortcut, and the main ones have a labeled button in the status bar.

| View | What it shows | Shortcut |
|---|---|---|
| **Agents** | Live orchestration: which agent is doing what, grouped into router, architect, coder, reviewer, sandbox, QA and vision lanes, refreshing while work runs | cmd-alt-a |
| **Context x-ray** | Which files the agents actually read, as an attention heatmap built from real session logs, so you can see when focus is on the wrong file | cmd-alt-x |
| **Topology** | The real import graph as a layered dependency diagram with directional connectors, a filter, and per-file dependency tracing on click | cmd-alt-m |
| **Time travel** | Commits and recorded agent decisions on one timeline, each with a ready command to branch from that point and try a different approach | cmd-alt-h |
| **Guard** | Security and cost flags: hardcoded credentials, eval on dynamic input, raw HTML injection, awaits inside loops, select star, unchecked unwraps, Solana privileged instructions | cmd-alt-s |
| **Cockpit** | End-of-mission summary: files changed, decisions on record, council verdicts, sandbox runs, and an approval section that deliberately does not apply anything for you | cmd-alt-k |

```bash
xyra-views hud            # or: xray, topology, timeline, secops, cockpit
xyra-views decide "state management" "Redux" "Context API" --npm @reduxjs/toolkit,react
```

`decide` renders an A/B architecture card with real package sizes and dependency counts pulled from the npm registry, instead of asking the question as terminal text.

## Council: cross-vendor adversarial coding

`xyra-council` is the flagship. One vendor implements a change; a rival vendor cross-examines it through three lenses in parallel, correctness, security and house conventions, and returns a structured verdict. If the verdict blocks, the builder addresses the blocking findings and the rival re-examines, up to a bounded number of rounds. Every run writes an audit trail to `docs/council/`.

```bash
xyra-council "add rate limiting to the API"          # Grok builds, Claude cross-examines, fixes if blocked
xyra-council --review-only                            # rival reviews your own uncommitted diff
xyra-council --review-only --staged                   # review the staged diff before committing
xyra-council --by claude --review grok "..."          # swap roles
xyra-council --lenses security --rounds 3 "..."       # focus one lens, allow more fix rounds
xyra-council --review-only --json                     # machine-readable verdict for scripts and hooks
```

Verdicts: `CLEAN`, `APPROVE WITH NOTES` (only low/medium findings), `BLOCK` (any critical/high), or `INCONCLUSIVE` (a lens failed to return). Exit code is non-zero on `BLOCK`, so it drops straight into a pre-commit or CI gate.

### Enterprise controls

The council is a tested, dependency-light Python package (`context/council/`, installed to `~/.xyra/council`):

- **Secret redaction before review.** Diffs are scrubbed of private keys, tokens, `.env` secrets and Solana keypairs before anything reaches a vendor.
- **Policy as code.** A per-repo `.xyra/council.toml` sets vendors, lenses and gates. Path rules require extra lenses and escalate the blocking severity for sensitive code:

  ```toml
  [[policy.rules]]
  paths = ["**/money*.ts", "programs/**", "**/vault*.rs"]
  require = ["security"]
  block_on = ["critical", "high", "medium"]
  ```

- **Reviewer panel with consensus.** Review with a panel (`--reviewers claude,local`) and require `any` or `majority` to block (`--consensus`).
- **SARIF output** (`--sarif council.sarif`) uploads straight into GitHub Code Scanning.
- **Verdict cache** keyed by content hash, so an unchanged diff is never re-reviewed.
- **Resilient providers** with retry and backoff, per-agent timeouts, and structured JSON logs (`--log-json`).
- **Audit trail** in `docs/council/` as both Markdown and JSON, one file per run.
- **Live events.** Every run publishes to the shared event bus, which is what the Agents view renders.

Drop-in gates ship in `templates/`: a git `pre-commit` hook and a `council.yml` GitHub Actions workflow that reviews the PR diff and uploads SARIF.

## Cosmos: council at project scale

`xyra-cosmos` runs the council at the design level: one vendor writes a design doc grounded in the codebase, a rival challenges it (risks, missing pieces, simpler approach, money and Solana safety), the first finalizes it, and the result lands in `docs/cosmos/` before any code is written.

```bash
xyra-cosmos "migrate the settlement flow to the new vault program"   # design only
xyra-cosmos --reviewers claude,local "..."                            # panel challenge
xyra-cosmos --execute "..."                                           # run every ticket through the council
```

With `--execute`, Cosmos topologically sorts the ticket list and runs each ticket through `xyra-council`, stopping at the first blocked ticket unless you pass `--force`.

## Always-on council

`xyra-watch` turns the council into a heartbeat for a repository. It watches the working tree, and once you stop changing it for a few minutes, a rival vendor reviews the diff in the background and queues the findings.

```bash
xyra-watch ~/cortex                  # foreground: review after 5 idle minutes
xyra-watch ~/cortex --queue          # show what the background council found
xyra-watch ~/cortex --install-agent  # run it under launchd, always on
```

## Skills

Grok sessions load the Wiener skills from `grok/skills/`, installed to `~/.grok/skills/`. Grok also reads Claude skills from `~/.claude/skills` automatically, so both agents share one skill investment.

| Skill | What it enforces |
|---|---|
| **wiener-autonomy** | Prove before you present: sandbox verification before showing a diff, a vision check after any UI change, impact analysis before touching shared contracts, fleet tools for cross-repo work, QA sweeps after a feature. Report evidence, not intentions. |
| **wiener-terminal** | Never hang a thread: no interactive commands (the non-interactive flag per CLI is tabulated), no foreground servers or watchers, no login flows in the panel, kill silent long-running commands instead of waiting. |
| **wiener-conventions** | House rules for code, commits and UI copy, applied whenever code is written. |
| **wiener-review** | Review checklist: integer money math, Supabase RPC grants, the Next.js server-to-client prop boundary, convention violations. |
| **wiener-solana** | Guardrails for anything touching funds: canonical addresses only (address poisoning defense), integer base units, simulation before send, devnet by default. |
| **wiener-ship** | Pre-push checklist: green tests and build, secrets scan, commit format, solo push-to-main flow. |
| **wiener-prompt-optimizer** | Rewrites a vague request into a precise, well-scoped prompt before acting on it. |

## Attribution: Xyra as a contributor

Work done through Xyra can be credited to a Xyra identity on GitHub, the way agent-assisted commits show up elsewhere. GitHub reads the `Co-authored-by` trailer and, when the email belongs to a real GitHub account, lists that account among the repository's contributors.

Setup is one time:

```bash
xyra-attribution setup "xyra" 274924993+xyra-agent@users.noreply.github.com
xyra-attribution status
```

That is the [xyra-agent](https://github.com/xyra-agent) account; point it at your own identity by passing a different name and the noreply address from that account's Settings, Emails page. The account must exist, otherwise the trailer credits nobody.

Every commit made through Xyra carries the trailer: the app tags its own process with `XYRA_SESSION=1`, so agent commits, commits from the integrated terminal and commits from the git panel are all covered. Commits you make in a separate terminal outside the editor stay untouched, and a repository with its own hooks keeps them, because the Xyra hook chains to the repo hook before doing anything. Remove it any time with `xyra-attribution uninstall`.

## What it installs

`install.sh` ships no binaries; everything is installed from official sources, then layered with the Wiener configuration:

- Zed editor (official Homebrew cask), renamed and branded as Xyra
- Xyra theme: lime and near-black palette derived from the logo, dark and light variants, follows the system appearance
- Grok Build CLI (official xAI cask) and Claude Code wired into the agent panel over ACP
- The autonomy tools: `xyra-sandbox`, `xyra-vision`, `xyra-fleet`, `xyra-qa`, and the `xyra-tools` MCP server behind them
- The visibility surfaces: `xyra-views` plus tasks and shortcuts for all six
- `xyra-council`, `xyra-cosmos`, `xyra-watch`: adversarial coding, design orchestration and the always-on reviewer
- `xyra-context`: semantic search plus the deterministic dependency graph, shared by every agent
- `xyra-attribution`: optional Xyra co-author credit on agent commits
- `xyra-grok-keepalive`: keeps the Grok session alive so you sign in once
- All seven Wiener skills, applied in every agent session
- Editor tasks and shortcuts, house-stack snippets (Zod, Next.js, Anchor), a Turkish-speaking agent via AGENTS.md
- JetBrains Mono Nerd Font, Cursor keymap, block cursor, Zeta edit predictions
- The `xyra`, `xyra-fix` and `xyra-doctor` terminal commands

## Downloads

Every release ships packages for all four platforms, built from source by CI:

| Platform | Asset |
|---|---|
| macOS Apple Silicon | `Xyra-<version>-macOS-AppleSilicon.zip` |
| macOS Intel | `Xyra-<version>-macOS-Intel.zip` |
| Linux x64 | `Xyra-<version>-Linux-x64.AppImage` (plus a tar.gz) |
| Windows x64 | `Xyra-<version>-Windows-x64.exe` (Inno Setup installer) |

Turkish builds carry a `-tr` suffix on the same assets. On every platform the agent menu includes Grok Build out of the box, and the welcome page shows a Grok sign-in button (or your signed-in state), so a fresh download is agent-ready in one click. The [Grok CLI](https://x.ai/cli) installs on macOS, Linux and Windows with the one-liners on that page.

## Requirements

- macOS and [Homebrew](https://brew.sh) for the full `install.sh` experience; on Linux and Windows use the packaged builds above
- A personal SuperGrok or X Premium+ subscription for Grok Build
- Chrome or Chromium for the vision and QA agents, Node for the QA agent
- Optional: a Claude Code account, Ollama for local models and offline vision

## Install

```bash
git clone https://github.com/wienerlabs/xyra.git
cd xyra
./install.sh
```

By default this **downloads the pre-built Xyra from the latest GitHub Release** (no compilation) and applies the Wiener configuration. It needs the GitHub CLI signed in (`gh auth login`); the installer installs `gh` if missing. To build from source instead (no Xcode required, ~45-60 minutes), run `./install.sh --source`. If no release exists yet, the installer falls back to a source build automatically.

### Turkish UI (Türkçe arayüz)

```bash
./install.sh --lang tr
```

If a Turkish release is published, the `-tr` package is downloaded; otherwise Xyra is built from source in Turkish (`XYRA_LANG=tr`). The translation layer is a build-time source-string pass that lives entirely under [`translations/`](translations/) and never touches the English build. See [translations/README.md](translations/README.md) for the workflow and how to extend coverage.

**Switching between Turkish and English.** The language is fixed at build time; there is no in-app toggle, because Zed has no runtime localization. Reinstall with the desired flag; each install replaces `/Applications/Xyra.app` in place and leaves your settings, keymaps and extensions alone.

```bash
./install.sh --lang tr   # Turkish
./install.sh             # English (default)
```

## First launch

1. Run `grok login --oauth` in a terminal and sign in with your own X account. Usage draws from your subscription quota, no API key needed.
2. Open Xyra and sign in with GitHub from the top right. This enables Zeta edit predictions.
3. Open the agent panel (cmd+?) and pick Grok Build from the + menu. Claude Code ships in the same menu.

You sign in once. The installer registers a launchd agent (`xyra-grok-keepalive`) that exercises the xAI refresh token every two hours, so the session stays alive instead of dying after long idle gaps. If xAI still revokes the session, the agent reopens the browser flow, which completes on its own while your x.ai web session is alive, and posts a notification either way. Check it with `xyra-grok-keepalive status`.

Track quota from inside Grok Build with the `/usage` command.

## Daily driving

Tasks are available from the task picker (cmd-shift-p, then "task: spawn") and on shortcuts:

| Shortcut | Task |
|---|---|
| cmd-alt-g | Grok: work on this repo (interactive TUI in the terminal pane) |
| cmd-alt-r | Grok: review current file |
| cmd-alt-t | Xyra: test and fix with Grok |
| cmd-alt-c | Claude: continue last session |
| cmd-alt-v | Xyra: verify in sandbox |
| cmd-alt-f | Xyra: connect fleet repos |
| cmd-alt-a | Xyra: agent orchestration HUD |
| cmd-alt-x | Xyra: context x-ray |
| cmd-alt-m | Xyra: topology map |
| cmd-alt-h | Xyra: time travel |
| cmd-alt-s | Xyra: security and cost |
| cmd-alt-k | Xyra: decision cockpit |

The agent panel is docked on the right. Panel toggles in the status bar carry their names (Agent, Terminal, Project, Git) instead of bare icons, and buttons are sized for comfortable clicking. The inline assistant lives on ctrl-enter. Multiple agent threads run side by side. When an agent finishes a task, the panel celebrates with a three second dollar rain, because shipped work should feel like it.

Two commands work in any repository, inside or outside the editor:

- `xyra-fix test` and `xyra-fix build` detect the project's runner (pnpm, bun, npm, cargo, pytest, go), run it, and on failure open Grok with the failure log and a fix mandate. On success they exit quietly.
- `xyra-doctor` verifies the whole setup: app, brew duplicate guard, Grok sign-in and keepalive, autonomy tools, Chrome availability, theme, tasks, snippets, skills, font and optional Ollama.

## Updates

Xyra updates itself in place; it is intentionally detached from Homebrew (the installer removes the brew registration so `brew upgrade` can never create a second Zed.app next to Xyra). For a clean reinstall: `./update.sh`.

## Publishing a release

```bash
./build/build-xyra.sh          # build and verify locally
./build/publish-release.sh v0.5.0
```

`publish-release.sh` refuses to publish an app that does not contain the Xyra brand, zips `Xyra.app`, attaches a SHA-256 and creates the GitHub Release. Pushing a `v*` tag runs the three release workflows instead, producing every platform and both languages.

## Branded build: every pixel Xyra

```bash
./build/build-xyra.sh
```

Requirements: Command Line Tools (`xcode-select --install`), Rust and CMake. No full Xcode needed: the patch enables gpui's `runtime_shaders` feature, which compiles Metal shaders at app startup instead of at build time. The script pins the upstream tag and applies `build/patch-brand.sh`, which layers every Xyra difference onto the GPL source: brand strings and icons, the embedded theme, the agent brand icons, larger buttons, labeled panel toggles, the status bar view buttons, the Grok sign-in on the welcome page, the money rain, the Windows installer identity and, when requested, the Turkish translation pass. Expect 30-60 minutes on first build.

## Optional: local models

If Ollama is present, add this to `~/.config/zed/settings.json`:

```json
{
  "agent": {
    "inline_assistant_model": { "provider": "ollama", "model": "qwen2.5-coder:32b" },
    "commit_message_model": { "provider": "ollama", "model": "qwen2.5-coder:32b" }
  },
  "language_models": {
    "ollama": {
      "api_url": "http://localhost:11434",
      "available_models": [
        {
          "name": "qwen2.5-coder:32b",
          "display_name": "Qwen2.5 Coder 32B (local)",
          "max_tokens": 32768,
          "supports_tools": true
        }
      ]
    }
  }
}
```

A vision-capable local model (any Ollama model reporting the vision capability) is picked up automatically as the offline fallback for `xyra-vision`.

## Troubleshooting

- **An agent command hangs**: it was interactive or a server that never exits. The shipped agent instructions forbid both; if you hit it, kill the command and check that `~/.config/zed/settings.json` still sets `CI=1` for the agent servers.
- **Rename or icon blocked**: grant Terminal the App Management permission under System Settings, Privacy and Security, App Management, then rerun the script.
- **Vision or QA fails**: install Chrome or Chromium, or set `XYRA_CHROME` to a browser binary. The QA agent also needs Node.
- **Topology is empty**: run `xyra-context index <repo>` first; the map renders the indexed graph.
- **Grok models missing**: run `grok models` and confirm your subscription is active.
- **Font not applied**: run `brew install --cask font-jetbrains-mono-nerd-font` and restart Xyra.

## License and distribution note

This repository contains no Zed or Grok Build binaries and distributes none; installation happens from official sources. Zed is an open source project licensed under GPLv3 at [zed-industries/zed](https://github.com/zed-industries/zed); Xyra is a locally rebranded build of it and is not affiliated with Zed Industries. Grok Build is distributed by xAI and subject to xAI's terms. Cytoscape.js, used by the topology view, is MIT licensed. The scripts and configuration files in this repository are MIT licensed.
