---
name: wiener-terminal
description: Rules for running shell commands from an agent panel so a thread never hangs on an interactive prompt or a process that does not exit. Use whenever running a terminal command, deploying, starting a server or using a cloud CLI.
---

# Terminal discipline

The agent panel waits for a command to exit. A command that asks a question, or one that never returns, freezes the entire thread until it is killed. Every rule here exists to prevent that.

## Never run an interactive command

Pass the non-interactive flag, or do not run the command at all.

| Instead of | Run |
|---|---|
| `vercel` | `vercel --yes` |
| `vercel deploy` | `vercel --yes --prod` on a linked project |
| `vercel link` | `vercel link --yes` |
| `npx <pkg>` | `npx --yes <pkg>` |
| `npm init` | `npm init -y` |
| `gh repo create` | `gh repo create <name> --private --source=. --push` |
| `rm -i`, `git clean -i` | explicit flags, never the interactive form |

If a CLI has no non-interactive mode for what is needed, stop and ask the user to run it in their own terminal. Reporting the exact command for them to paste is a complete answer.

## Never block on a process that does not exit

Development servers, watchers and REPLs never return.

- Do not run `next dev`, `vite`, `vercel dev`, `npm start`, `jest --watch`, `cargo watch`, `tail -f` or a bare `python`/`node` REPL as a blocking command.
- Start a server detached and read its log: `nohup npm run dev > /tmp/dev.log 2>&1 &` then `sleep 3` and `cat /tmp/dev.log`.
- Better still, ask the user whether a server is already running and reuse it.
- Kill what you start when finished, and say so.

## Never start a login flow

`vercel login`, `gh auth login`, `aws configure`, `firebase login`, `npm login` and `heroku login` all open a browser and wait. Ask the user to authenticate once in their own terminal; afterwards use the authenticated CLI non-interactively.

## Long running but finite work

Builds, installs and test suites do exit, so they are allowed, but keep them bounded and visible.

- Prefer the narrowest scope: one test file over the whole suite while iterating.
- If a command has produced no output for a long time, kill it and reconsider rather than waiting silently.
- For repository-wide verification prefer `sandbox_verify`, which runs the suite in an isolated snapshot with its own timeout.

## Deploys

1. Confirm the project is linked (`.vercel/project.json` exists). If not, `vercel link --yes` first.
2. Deploy with `vercel --yes --prod` and report the resulting URL.
3. If any step still demands input, hand it to the user with the exact command; never leave a half-finished deploy waiting on a prompt.
