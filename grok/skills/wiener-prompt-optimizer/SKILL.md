---
name: wiener-prompt-optimizer
description: Rewrite a vague or rushed request into a precise, well-scoped prompt before acting on it. Use when the user's instruction is ambiguous, underspecified, or would benefit from clarification, or when the user explicitly asks to optimize or refine a prompt.
---

# Prompt optimizer

When a request is vague, underspecified, or likely to produce the wrong result, first rewrite it into a sharp prompt, then act on the rewritten version.

## When to apply
- The request omits key details (which file, which behavior, what success looks like).
- The request bundles several tasks that should be separated.
- The user says "optimize this prompt", "make this clearer", "reword", or pastes a rough instruction.

## How to rewrite
Produce a refined prompt that makes the following explicit, inferring sensible defaults from the open files and repository when the user did not state them:

1. Goal: the concrete outcome in one sentence.
2. Scope: which files, modules, or surfaces are in and out of scope.
3. Constraints: house conventions (no code comments, no em dash, integer money, sentence-case UI), plus any framework specifics.
4. Acceptance: how to know it worked (tests pass, build green, specific behavior observed).
5. Non-goals: what explicitly should not change.

## Output
- If the original request was clear enough, say so in one line and proceed, do not pad it.
- If it needed refinement, show the rewritten prompt in a short block, then proceed to execute it. Do not stop and wait unless a genuine decision is missing that only the user can make.
- Keep the rewrite shorter than the reasoning that produced it. A good optimized prompt is precise, not longer.
