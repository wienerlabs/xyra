---
name: wiener-conventions
description: Wiener Labs house conventions for all code, docs, commits and UI copy. Use whenever writing or editing code, documentation, commit messages or user-facing text in any Wiener Labs project.
---

# Wiener Labs conventions

Apply these rules to every edit in this repository. They override generic style defaults.

## Code

1. Never write code comments. No `//`, `#`, `/* */`, docstrings or JSX comments. Code must explain itself through naming and structure. Rationale belongs in the commit message or PR description, not in the source.
2. Never use the em dash character in any output: not in code, strings, docs, commit messages or UI copy. Use a regular hyphen, a comma or restructure the sentence.
3. TypeScript first. Next.js App Router and Tailwind v4 are the house defaults for web work; Solana work uses web3.js and Anchor.

## Next.js specifics

4. Never pass an i18n dictionary object that carries interpolator functions from a Server Component to a Client Component prop. It serializes in dev and crashes with a digest 500 in production. Client components read translations with the `useT()` hook from context instead.

## UI copy

5. No all-caps words in UI. Sentence case only: first letter capitalized, rest lowercase. In Tailwind, do not add the `uppercase` class; remove it when touching existing code.
6. Technical artifacts (READMEs, code identifiers, commit messages) are written in English. Product-facing copy follows the product language, which is Turkish for internal tools.

## Git

7. Commit message format is `<type>: <description>` where type is one of feat, fix, refactor, docs, test, chore, perf, ci. Lowercase description, imperative mood, no trailing period.
8. Never add attribution or co-author lines to commits.
9. In solo projects, push finished work directly to main. Pull request flow is reserved for automated dependency updates and multi-person repositories.

## Working style

10. Before implementing something new, search for an existing implementation to adopt or port: GitHub code search first, then official library docs, then the package registries. Prefer battle-tested libraries over hand-rolled utilities.
11. Keep diffs minimal and scoped. Do not reformat, rename or restructure code that the task does not require touching.
