<p align="center">
  <img src="assets/xyra-icon.png" width="128" alt="Xyra">
</p>

<h1 align="center">Xyra</h1>

<p align="center">The agentic code editor where every change is cross-examined by a rival AI before you see it. Flat-rate, local-first, and yours.</p>

## Why Xyra is different

Other agentic editors are metered clouds tied to one model vendor. Xyra is the opposite, and the difference is architectural, not cosmetic:

- **A rival reviews every change.** One vendor writes, a rival vendor cross-examines it through correctness, security and convention lenses before it reaches you. Metered editors cannot afford to run two frontier vendors on every task. Xyra can, because it runs on flat-rate subscription quota.
- **Flat-rate, not per-token.** Grok Build runs on your SuperGrok or X Premium quota. No meter, no per-token anxiety, so agents can run wide and often.
- **One editor, every model.** Grok Build, Claude Code and local Ollama models live in one panel. Route the best agent per task, run them in parallel, stay vendor-independent.
- **Local-first and yours.** Semantic code search runs on a local embedding model, local models keep code on the machine, telemetry is off, and the whole setup ships as a repo your team owns. No lock-in, no exfiltration.

The flagship is the council: `xyra-council` and its project-scale sibling `xyra-cosmos`. Both are documented below.

## What it installs

`install.sh` ships no binaries; everything is installed from official sources, then layered with the Wiener configuration:

- Zed editor (official Homebrew cask), renamed and branded as Xyra
- Xyra theme: lime and near-black palette derived from the logo, dark and light variants, follows the system appearance
- Grok Build CLI (official xAI cask) and Claude Code wired into the agent panel over ACP
- `xyra-council`: cross-vendor adversarial coding (the flagship)
- `xyra-cosmos`: project-scale design orchestration with a rival challenge
- `xyra-context`: a local semantic context engine shared by every agent
- The wiener-conventions, wiener-review, wiener-solana, wiener-ship and prompt-optimizer skills applied in every agent session
- Editor tasks and shortcuts, house-stack snippets (Zod, Next.js, Anchor), a Turkish-speaking agent via AGENTS.md
- JetBrains Mono Nerd Font, Cursor keymap, block cursor, Zeta edit predictions
- The `xyra`, `xyra-fix`, `xyra-doctor` terminal commands

After install, one panel gives you three layers: Grok Build (subscription quota, up to 8 parallel agents), Claude Code (built in), and optional local Ollama models, all reviewing each other through the council.

## Requirements

- macOS and [Homebrew](https://brew.sh)
- A personal SuperGrok or X Premium+ subscription for Grok Build
- Optional: a Claude Code account, Ollama

## Install

```bash
git clone https://github.com/wienerlabs/xyra.git
cd xyra
./install.sh
```

By default this **downloads the pre-built Xyra from the latest GitHub Release** (no compilation) and applies the Wiener configuration. It needs the GitHub CLI signed in (`gh auth login`); the installer installs `gh` if missing. To build from source instead (no Xcode required, ~45-60 minutes), run `./install.sh --source`. If no release exists yet, the installer falls back to a source build automatically.

## Publishing a release

Maintainers publish a versioned build to the repo's Releases so employees install without compiling:

```bash
./build/build-xyra.sh          # build and verify locally (or use an existing /Applications/Xyra.app)
./build/publish-release.sh v0.1.0
```

`publish-release.sh` refuses to publish an app that does not contain the Xyra brand, zips `Xyra.app`, attaches a SHA-256, and creates the GitHub Release with source-availability notes. `install.sh` then downloads it.

A `.github/workflows/release.yml` workflow can build and publish automatically on a `v*` tag push, running on a macOS runner. It is optional: macOS Actions minutes are billed at a high multiplier, so if Actions billing is unavailable, use the local `publish-release.sh` path above.

## First launch

1. Run `grok login --oauth` in a terminal and sign in with your own X account. Usage draws from your subscription quota, no API key needed.
2. Open Xyra and sign in with GitHub from the top right. This enables Zeta edit predictions.
3. Open the agent panel (cmd+?) and pick Grok Build from the + menu. Claude Code ships in the same menu.

Track quota from inside Grok Build with the `/usage` command.

## Daily driving

Agent tasks are available from the task picker (cmd-shift-p, then "task: spawn") and on shortcuts:

| Shortcut | Task |
|---|---|
| cmd-alt-g | Grok: work on this repo (interactive TUI in the terminal pane) |
| cmd-alt-r | Grok: review current file |
| cmd-alt-t | Xyra: test and fix with Grok |
| cmd-alt-c | Claude: continue last session |

The agent panel is docked on the right. The inline assistant lives on ctrl-enter and uses the configured model. Multiple agent threads can run side by side; the dashboard task shows parallel Grok agents live.

Two commands work in any repository, inside or outside the editor:

- `xyra-fix test` and `xyra-fix build` detect the project's runner (pnpm, bun, npm, cargo, pytest, go), run it, and on failure open Grok with the failure log and a fix mandate. On success they exit quietly.
- `xyra-doctor` verifies the whole setup: app, brew duplicate guard, Grok sign-in, theme, tasks, snippets, conventions skill, font and optional Ollama. Run it after install or whenever something feels off.

## Updates

Xyra updates itself in place; it is intentionally detached from Homebrew (the installer removes the brew registration so `brew upgrade` can never create a second Zed.app next to Xyra).

For a clean reinstall:

```bash
./update.sh
```

## Council: cross-vendor adversarial coding

`xyra-council` is the flagship. One vendor implements a change; a rival vendor then cross-examines it through three lenses in parallel, correctness, security and house conventions, and returns a structured verdict. If the verdict blocks, the builder addresses the blocking findings and the rival re-examines, up to a bounded number of rounds. Every run writes an audit trail to `docs/council/`.

Because Xyra runs on flat-rate subscription quota (Grok Build) plus local models, running two frontier vendors on every task costs nothing at the margin, which metered cloud editors cannot afford. That is the moat.

```bash
xyra-council "add rate limiting to the API"          # Grok builds, Claude cross-examines, fixes if blocked
xyra-council --review-only                            # rival reviews your own uncommitted diff
xyra-council --review-only --staged                  # review the staged diff before committing
xyra-council --by claude --review grok "..."         # swap roles
xyra-council --lenses security --rounds 3 "..."      # focus one lens, allow more fix rounds
xyra-council --review-only --json                    # machine-readable verdict for scripts and hooks
```

Verdicts: `CLEAN`, `APPROVE WITH NOTES` (only low/medium findings), `BLOCK` (any critical/high), or `INCONCLUSIVE` (a lens failed to return). Exit code is non-zero on `BLOCK`, so it drops straight into a pre-commit or CI gate.

### Enterprise controls

The council is a tested, dependency-light Python package (`context/council/`, installed to `~/.xyra/council`) with the controls a team needs:

- **Secret redaction before review.** Diffs are scrubbed of private keys, tokens, `.env` secrets and Solana keypairs before anything reaches a vendor. Nothing sensitive leaves the machine even when a cloud model reviews.
- **Policy as code.** A per-repo `.xyra/council.toml` sets vendors, lenses, and gates. Path rules require extra lenses and escalate the blocking severity for sensitive code:

  ```toml
  [[policy.rules]]
  paths = ["**/money*.ts", "programs/**", "**/vault*.rs"]
  require = ["security"]
  block_on = ["critical", "high", "medium"]
  ```

- **SARIF output** (`--sarif council.sarif`) uploads straight into GitHub Code Scanning.
- **Verdict cache** keyed by content hash, so an unchanged diff is never re-billed.
- **Resilient providers** with retry and backoff, per-agent timeouts, and structured JSON logs (`--log-json`).
- **Audit trail** in `docs/council/` as both Markdown and JSON, one file per run.

Drop-in gates ship in `templates/`: a git `pre-commit` hook (`xyra-council --review-only --staged`) and a `council.yml` GitHub Actions workflow that reviews the PR diff and uploads SARIF.

In the editor: `cmd-alt-k` runs a rival-vendor review of your current changes. The council grounds the builder with the semantic context engine and sharpens reviews with the wiener-conventions, wiener-review and wiener-solana skills, so money and Solana code get scrutinized on integer units and address-poisoning by default.

## Cosmos: council at project scale

`xyra-cosmos` takes a project objective and runs the council at the design level: one vendor writes a design doc grounded in the codebase, a rival vendor challenges it (risks, missing pieces, simpler approach, money/Solana safety), the first vendor finalizes it, and the result lands in `docs/cosmos/` for you to review before any code is written. The most valuable artifact in a large project is a design vetted from two independent angles.

```bash
xyra-cosmos "migrate the settlement flow to the new vault program"
# -> docs/cosmos/<date>-<slug>.md  (design + rival challenge on the record)
```

Once the design is approved, each ticket runs through `xyra-council` (implement + rival review). Design stays local and in-repo, never in a vendor's cloud.

## Always-on council

`xyra-watch` turns the council into a heartbeat for a repository. It watches your working tree, and once you stop changing it for a few minutes, a rival vendor reviews the diff in the background, queues the findings, and notifies you. Because Xyra is flat-rate and local, this runs continuously at no marginal cost, which a metered cloud editor cannot do.

```bash
xyra-watch ~/cortex                  # foreground: review after 5 idle minutes
xyra-watch ~/cortex --queue          # show what the background council found
xyra-watch ~/cortex --install-agent  # run it under launchd, always on
```

Findings land in a per-repo queue and every run leaves an audit trail. Stop working, and by the time you come back the council has already looked.

## Semantic context engine

`context/xyra_context.py` is a dependency-light MCP server that gives every agent (Grok Build, Claude Code, and the native Xyra agent) semantic search over a codebase, instead of grep. It embeds code chunks with a local Ollama model (`nomic-embed-text`, no API cost, nothing leaves the machine), stores vectors in a per-repo SQLite cache, and re-embeds only changed files (content-hash incremental).

Installed as `xyra-context` and registered with all three agents automatically. Manual use:

```bash
xyra-context index /path/to/repo     # build or refresh the index
xyra-context search /path/to/repo "where is the auth middleware"
```

Agents call the `code_search` and `code_index` tools directly. This is the foundation for smarter, lower-token context assembly.

## Skills

Grok sessions load the Wiener skills from `grok/skills/`, installed to `~/.grok/skills/`:

- **wiener-conventions**: house rules for code, commits and UI copy, applied whenever code is written
- **wiener-review**: review checklist covering integer money math, Supabase RPC grants, the Next.js server-to-client prop boundary and convention violations
- **wiener-solana**: guardrails for anything touching funds: canonical addresses only (address poisoning defense), integer base units, simulation before send, devnet by default
- **wiener-ship**: pre-push checklist: green tests and build, secrets scan, commit format, solo push-to-main flow

Grok also reads Claude skills from `~/.claude/skills` automatically, so both agents share one skill investment.

## Branded build: every pixel Xyra

The stock install renames the app and sets the icon, but compiled strings like the welcome screen still say Zed. For the full rebrand, build Xyra from the GPL source with the Wiener brand patch:

```bash
./build/build-xyra.sh
```

Requirements: Command Line Tools (`xcode-select --install`) and Rust. No full Xcode needed: the patch enables gpui's `runtime_shaders` feature, which compiles Metal shaders at app startup instead of at build time. The script pins the upstream tag, applies `build/patch-brand.sh` (menu bar and About name, welcome screen text and logo, app icon baked into the bundle, Xyra theme embedded as a built-in), builds with the official bundle script and installs to /Applications/Xyra.app. Expect 30-60 minutes on first build. Updates: bump the tag in the script and rerun.

## Optional: local models

If Ollama is present, add this block to `~/.config/zed/settings.json` to use local models for the inline assistant and commit messages:

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

## Troubleshooting

- **Rename or icon blocked**: grant Terminal the App Management permission under System Settings > Privacy & Security > App Management, then rerun the script. Manual icon path: select the app in Finder, press cmd+I, click the small icon in the top left, open `assets/xyra-icon.png` in Preview, copy it with cmd+A cmd+C, then paste with cmd+V into the Get Info window.
- **Menu bar still says "Zed"**: expected. The bundle is left untouched to keep the code signature and self-updater intact; only the name, icon and configuration are changed.
- **Grok models missing**: run `grok models` and confirm your subscription is active.
- **Font not applied**: run `brew install --cask font-jetbrains-mono-nerd-font` and restart Xyra.

## License and distribution note

This repository contains no Zed or Grok Build binaries and distributes none; installation happens from official sources. Zed is an open source project licensed under GPLv3 at [zed-industries/zed](https://github.com/zed-industries/zed); Xyra is a locally rebranded installation of it and is not affiliated with Zed Industries. Grok Build is distributed by xAI and subject to xAI's terms. The scripts and configuration files in this repository are MIT licensed.
