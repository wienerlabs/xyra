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

macOS may ask for the "App Management" permission for Terminal on first run; grant it and run the script again.

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

Requirements: Xcode (for the Metal compiler) and Rust. The script pins the upstream tag, applies `build/patch-brand.sh` (menu bar and About name, welcome screen text, app icon baked into the bundle, Xyra theme embedded as a built-in), builds with the official bundle script and installs to /Applications/Xyra.app. Expect 30-60 minutes on first build. Updates: bump the tag in the script and rerun.

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
