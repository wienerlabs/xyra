# Xyra agent instructions

## Language
Respond to the user in Turkish. Keep explanations, summaries and conversation in Turkish, with correct Turkish diacritics. Code, code identifiers, commit messages and technical file names stay in English.

## Code conventions
- Never write code comments. No `//`, `#`, `/* */`, docstrings or JSX comments. Rationale belongs in the commit message or PR description, not in the source.
- Never use the em dash character in any output: not in code, strings, docs, commit messages or UI copy. Use a regular hyphen, a comma or restructure the sentence.
- TypeScript first. Next.js App Router and Tailwind v4 are the defaults for web work; Solana work uses web3.js and Anchor.

## UI copy
- No all-caps words in UI. Sentence case only: first letter capitalized, rest lowercase. Do not add the `uppercase` Tailwind class; remove it when touching existing code.

## Next.js
- Never pass an i18n dictionary object that carries interpolator functions from a Server Component to a Client Component prop. It crashes with a digest 500 in production. Client components read translations through the `useT()` hook from context instead.

## Money and Solana
- Money is always an integer in the smallest unit: kurus for TRY, lamports for SOL, 10^6 units for USDC. Float money math is a critical error.
- On Solana, never copy a destination address from transaction history (address poisoning). Addresses come only from a canonical config, an environment variable or a verified constant.

## Working style
- Before writing something new, search for an existing solution to adopt or port. Prefer battle-tested libraries over hand-rolled utilities.
- Keep diffs minimal and scoped. Do not reformat or rename code the task does not require.

## Autonomy tools (prove before you present)
- Before presenting any non-trivial code change, call the `sandbox_verify` tool (xyra-tools MCP). It runs the repository's tests in an isolated snapshot of your uncommitted changes. Only present code that passed; if it fails, fix and verify again first.
- After any frontend or styling change with a reachable page, call `ui_check` with the page URL and what it should look like. Trust the screenshot verdict over your assumption. When a design mockup exists, use `ui_compare` against it.
- Before renaming or changing a shared function, type, endpoint or config key, call `code_impact` (xyra-context MCP) and update every file in the returned chain in the same pass.
- When the project is part of a fleet (.xyra/fleet.json), use `fleet_search` and `fleet_impact` to find cross-repo usages before changing any contract between repositories.
- After completing a user-facing feature on a running web app, offer to run `qa_run` against it to shake out console errors and broken flows.
