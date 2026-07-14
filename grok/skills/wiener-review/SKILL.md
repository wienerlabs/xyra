---
name: wiener-review
description: Wiener Labs review checklist for TypeScript, Next.js, Supabase and Solana code. Use when reviewing code, auditing a diff or checking work before commit in any Wiener Labs project.
---

# Wiener Labs review checklist

Run through every applicable item. Report findings ordered by severity with file and line references.

## Money and numbers

1. Money is always integer in the smallest unit: kurus for TRY, lamports for SOL, 10^6 units for USDC. Any float arithmetic on money is a critical finding.
2. Rounding happens exactly once, at the display boundary, never in storage or transfer math.

## Supabase and API boundaries

3. Check which client executes each RPC. PIN-based staff flows run on the anon client, so any money-touching RPC they call must have an explicit anon grant and a hardening review. Flag RPCs that are granted to anon but look privileged.
4. Server-only secrets must never reach client bundles: no service keys in files imported by client components.

## Next.js

5. No Server to Client prop may carry functions, including i18n dictionary objects with interpolators. Client components read translations through the useT hook from context. This crashes as a digest 500 in production, so treat it as critical.
6. Async server components must not be passed as children into client components that serialize props.

## Conventions

7. No code comments of any kind. If the diff adds comments, list each one.
8. No em dash characters anywhere in the diff.
9. No all-caps words in UI copy and no uppercase Tailwind class.
10. Commit messages follow type colon description format.

## General correctness

11. Error paths: every await can reject, every external call can fail. Flag swallowed errors and empty catch blocks.
12. Concurrency: double-submit protection on money actions, idempotency keys on webhooks.
13. Scope: flag any change that touches files unrelated to the stated task.
