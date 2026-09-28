# PageDoc

PageDoc is a deterministic, Markdown-first authoring and rendering engine for fixed-size technical books, manuals, guides, and visual documentation.

The project is intentionally domain-neutral. It provides a small semantic document language, a reusable component registry, theme-driven styling, deterministic HTML output, and a path to fixed-page PDF rendering.

## Status

Specification-first foundation. The initial implementation should follow the contracts in `docs/`.

## Core idea

Authors should describe **meaning and composition**, not pixel geometry.

```markdown
---
id: project-api
group: Product Guide
title: Inspect a Project API
---

A dashboard loads project data from an HTTP API.

<browser>
https://app.example.test/projects
</browser>

<row>

<request title="Project list">
GET /api/v1/projects/user/john
</request>

<response status="200">
{"projects":["alpha","beta"]}
</response>

</row>

<note>
The request and response are related, so they are presented together.
</note>
```

PageDoc compiles authoring source into a validated semantic AST, then renders that AST through a theme.

```text
.book.md
   |
   v
Parser
   |
   v
Semantic AST / IR
   |
   v
Component registry
   |
   v
HTML + CSS
   |
   v
Optional PDF backend
```

## Principles

- Markdown is the normal authoring surface.
- Custom elements exist only for reusable semantic or layout patterns.
- JSON is suitable for compiled AST/IR, not the primary authoring format.
- Normal page source does not contain pixel heights, widths, gaps, or coordinates.
- Semantic components do not decide where they are placed.
- Layout primitives do not invent content semantics.
- HTML/CSS and the selected rendering backend are the authoritative layout path.
- Diagnostics must retain source locations back to the `.book.md` file.
- Builds are deterministic and offline by default.
- No arbitrary JavaScript or MDX-style code execution is allowed.
- A new component is added only when a recurring pattern cannot be expressed cleanly with Markdown and existing primitives.

## Initial component vocabulary

Semantic components:

- `request`
- `response`
- `browser`
- `note`
- `result`
- `compare`
- `flow`
- `media`

Layout primitive:

- `row`

Markdown already covers headings, prose, lists, tables, emphasis, links, inline code, and fenced code blocks.

## Repository map

- `docs/AUTHORING_SPEC.md` - source language contract
- `docs/COMPONENTS.md` - component semantics and nesting
- `docs/ARCHITECTURE.md` - parser, AST, registry, renderer and backend boundaries
- `docs/THEME_SPEC.md` - theme responsibilities and geometry ownership
- `docs/IMPLEMENTATION_PLAN.md` - staged implementation plan
- `examples/product-handbook/` - neutral example document
- `tests/fixtures/` - contract fixtures for parser and AST behavior
- `AGENTS.md` - implementation constraints for coding agents

## Non-goals for v1

PageDoc v1 is not:

- a WYSIWYG editor;
- a browser engine;
- a general HTML templating framework;
- a CMS;
- a flowing novel/typesetting system;
- an MDX/JS execution environment;
- a domain-specific documentation generator.

One `.book.md` source file represents one logical fixed-size page in v1.

## Development

No GitHub Actions are required for the initial implementation. Validation should be runnable locally and deterministically.

The reference implementation target is Python 3.12+.

See `docs/IMPLEMENTATION_PLAN.md` before writing implementation code.
