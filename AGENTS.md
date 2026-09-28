# AGENTS.md

## Project

PageDoc is a domain-neutral, Markdown-first authoring and fixed-page rendering engine for technical books, manuals, guides, and visual documentation.

Treat this repository as self-contained. Do not infer or depend on an external consumer repository.

## Required reading

Before implementation work, read:

1. `README.md`
2. `docs/AUTHORING_SPEC.md`
3. `docs/COMPONENTS.md`
4. `docs/ARCHITECTURE.md`
5. `docs/THEME_SPEC.md`
6. `docs/IMPLEMENTATION_PLAN.md`

The docs are normative unless a task explicitly changes them.

## Engineering rules

- Target Python 3.12+.
- Keep the implementation deterministic and offline by default.
- Do not add GitHub Actions unless explicitly requested.
- Use TDD for parser, AST, validation, and layout-contract behavior.
- Keep modules small and responsibilities explicit.
- Preserve source locations through parsing and validation.
- Do not execute arbitrary JavaScript, Python, MDX, or embedded code from document sources.
- Do not fetch remote assets during a build.
- Do not place pixel geometry in normal `.book.md` authoring source.
- Do not create domain-specific components.
- Do not add a semantic component merely to simplify one fixture.
- Prefer Markdown primitives when Markdown already expresses the content well.
- Unknown components, attributes, invalid nesting, unresolved local assets, and unsupported layout presets must fail with actionable diagnostics.
- JSON may be emitted as a compiled AST/IR or debug artifact, but it is not the primary authoring language.
- Do not duplicate layout formulas in a second handwritten text-measurement engine. The HTML/CSS + selected backend path is authoritative for layout.

## Component promotion rule

A new top-level semantic component should be introduced only when all are true:

1. the pattern is semantically distinct from existing primitives;
2. Markdown plus existing components cannot express it cleanly;
3. the pattern is expected to recur across multiple independent documents;
4. its validation and rendering contract can be stated generically.

Otherwise keep the content in Markdown, a table, a fenced code block, or an existing layout primitive.

## Initial implementation scope

Unless a task explicitly expands scope, implement Milestone 1 from `docs/IMPLEMENTATION_PLAN.md` only.

Milestone 1 includes:

- YAML front matter parsing;
- Markdown parsing;
- PageDoc custom block parsing;
- source-span aware AST;
- component registry and validation;
- deterministic AST serialization;
- deterministic HTML rendering;
- contract fixtures and tests;
- CLI commands for lint, AST inspection, and HTML rendering.

Milestone 1 does not include PDF generation or consumer migration.

## Development commands

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .[dev]
.venv/bin/python -m pytest tests            # full suite
.venv/bin/pagedoc lint examples/product-handbook/document.yaml
.venv/bin/pagedoc ast tests/fixtures/request-response.book.md
.venv/bin/pagedoc render examples/product-handbook/document.yaml --html-out out.html
```

Package layout: `src/pagedoc/` (`errors`, `ast`, `attributes`, `markdown`,
`parser`, `registry`, `validation`, `document`, `theme/`, `render/`,
`cli`). The serialized AST node vocabulary is documented in
`docs/AST_FORMAT.md`.

## Completion standard

Before reporting completion:

- run the full local test suite;
- run fixture linting;
- render the example document;
- verify deterministic repeated output;
- report exact commands and results;
- report any spec ambiguity instead of silently inventing behavior.
