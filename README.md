# PageDoc

PageDoc is a deterministic, Markdown-first authoring and rendering engine for fixed-size technical books, manuals, guides, and visual documentation.

The project is intentionally domain-neutral. It provides a small semantic document language, a reusable component registry, theme-driven styling, deterministic HTML output, and a path to fixed-page PDF rendering.

## Status

Milestones 1-2 are implemented: the authoring core (parser, semantic
AST, registry, validation, deterministic AST/HTML) and the fixed-page
pipeline (theme regions, WeasyPrint authoritative layout, overflow
diagnostics, deterministic PDF, layout inspection). WeasyPrint is the
single fixed-page layout backend; see `docs/IMPLEMENTATION_PLAN.md` for
the revised milestone boundary.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .[dev]
pagedoc lint examples/product-handbook/document.yaml
pagedoc ast examples/product-handbook/pages/01-overview.book.md
pagedoc render examples/product-handbook/document.yaml --html-out out/book.html --pdf-out out/book.pdf
pagedoc render examples/visual-primitives/document.yaml --pdf-out out/vp.pdf --flattened-pdf-out out/vp.flat.pdf
pagedoc inspect examples/layout-gallery/document.yaml --json
```

Optional extras: `pagedoc[raster]` (pypdfium2 + PyMuPDF + img2pdf +
Pillow) enables the experimental flattened-PDF output and the
cross-renderer raster validation tests.

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
- `docs/AST_FORMAT.md` - serialized AST node shapes (schema_version 1)
- `examples/product-handbook/` - neutral example document
- `examples/layout-gallery/` - 10-page layout acceptance corpus
- `examples/visual-primitives/` - geometric-primitive renderer conformance corpus
- `tests/fixtures/` - contract fixtures for parser and AST behavior
- `tests/fixtures/overflow/` - intentional overflow fixtures
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

## Python API

Consumer projects integrate through the supported public surface — no
CLI subprocess, no internal module imports:

```python
import pagedoc

book = pagedoc.compile_document("document.yaml")

if not book.fits:
    for d in book.diagnostics:
        print(d.format())
    raise SystemExit(1)

artifact = book.write_pdf("dist/book.pdf")
print(artifact.sha256)
```

`pagedoc.lint_document` validates without layout, and
`pagedoc.inspect_document` returns a versioned, deterministic
inspection report. See `docs/PUBLIC_API.md` for the full contract.

## Development

No GitHub Actions are required for the initial implementation. Validation should be runnable locally and deterministically.

The reference implementation target is Python 3.12+.

See `docs/IMPLEMENTATION_PLAN.md` before writing implementation code.
