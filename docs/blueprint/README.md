# Xyra Blueprint

The product, architecture and delivery specification for Xyra as a standalone IDE built on
permissively licensed foundations.

## Compiling

```bash
tectonic -X compile main.tex
```

Any LaTeX toolchain works. Tectonic is used here because it resolves packages on demand, so
no local TeX installation is required.

## Structure

| File | Chapter |
|---|---|
| `parts/01-thesis.tex` | Product thesis, principles, positioning, surfaces, non goals |
| `parts/02-foundation.tex` | Licensing strategy and the verified open source foundation |
| `parts/03-architecture.tex` | Layers, process model, crates, state ownership, failure containment |
| `parts/04-context.tex` | Compression protocol, tiered escalation, budget solver, accelerators, integrations |
| `parts/05-agents.tex` | Roles, mission supervisor, verification, skills, fleet, tool surface |
| `parts/06-interface.tex` | Every surface, region and control, with wireframes and keymap |
| `parts/07-stories.tex` | Personas and twenty five user stories with acceptance criteria |
| `parts/08-breakdown.tex` | Twelve categories and the register of two hundred and seventeen issues |
| `parts/09-quality.tex` | Testing, performance budgets, security, accessibility, packaging, risk |
| `parts/10-prompts.tex` | Generation prompts that turn this document into code |
| `parts/11-appendix.tex` | Traceability matrix, formats, glossary, maintenance rules |

## Using it to generate code

1. Compile the document, or pass the source files directly to the agent.
2. Prepend the rules of engagement from the prompts chapter to every session.
3. Run the bootstrap prompt once against an empty repository.
4. Execute issues in register order using the issue prompt template, or load the register as
   a mission ticket graph with the self hosting prompt and let the supervisor run it.
5. Review every diff with the review prompt, ideally on a different vendor.
6. When the document is wrong, use the amendment prompt. The document and the code land
   together.

## Maintenance

The document is the source of truth. Code that contradicts it is a defect in one of the two,
resolved before the code lands. New surfaces enter through a user story first.
