<p align="center">
  <img src="assets/xyra-icon.png" width="128" alt="Xyra">
</p>

<h1 align="center">Xyra</h1>

<p align="center">Wiener Labs' internal code editor. Zed-based, agent-first, with Grok Build and Claude Code built into a single panel.</p>

## What it installs

`install.sh` ships no binaries; everything is installed from official sources, then layered with the Wiener configuration:

- Zed editor (official Homebrew cask), renamed and branded as Xyra
- Xyra theme: lime and near-black palette derived from the logo, dark and light variants, follows the system appearance
- Grok Build CLI (official xAI cask) wired into the agent panel over ACP
- The wiener-conventions skill for Grok: house rules for code, commits and UI copy applied in every agent session
- Editor tasks and keyboard shortcuts for driving agents without leaving the editor
- Snippets for the house stack: Zod, Next.js server actions and route handlers, client components with context i18n, Anchor instructions
- JetBrains Mono Nerd Font (editor, UI and terminal), VSCode keymap, block cursor, Zeta edit predictions
- The `xyra` terminal command

After install, one panel gives you three layers: Grok Build (subscription quota, up to 8 parallel agents), Claude Code (built in), and optional local Ollama models.

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

`xyra-council` is the flagship. One vendor implements a change, a rival vendor reviews it adversarially before you see it. Because Xyra runs on flat-rate subscription quota (Grok Build) plus local models, running two frontier vendors on every task costs nothing at the margin, which metered cloud editors cannot afford. That is the moat.

```bash
xyra-council "add rate limiting to the API"     # Grok implements, Claude reviews
xyra-council --review-only                       # rival vendor reviews your own uncommitted diff
xyra-council --by claude --review grok --fix "..."  # swap roles, auto-apply the review
```

In the editor: `cmd-alt-k` runs a rival-vendor review of your current changes. The council uses the semantic context engine to ground the builder, and the wiener-conventions and wiener-solana skills to keep reviews sharp on money and Solana code. This is also the execution core for project-level orchestration (Cosmos).

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
