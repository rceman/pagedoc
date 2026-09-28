# PageDoc Implementation Plan

## Objective

Build PageDoc in small stages so parser/authoring semantics stabilize before fixed-page PDF concerns are introduced.

The first coding-agent task should implement **Milestone 1 only** unless explicitly expanded.

## Milestone 0 - specification foundation

Already provided by the repository:

- project scope;
- authoring contract;
- component contract;
- architecture;
- theme contract;
- neutral examples;
- parser/AST contract fixtures.

No production engine behavior should be inferred from any external repository.

## Milestone 1 - authoring core and deterministic HTML

### Scope

Implement:

1. Python 3.12+ package structure.
2. YAML document manifest loader.
3. YAML page front matter.
4. Markdown parser with table support.
5. standalone PageDoc custom-block scanner/parser.
6. v1 attribute parser.
7. body modes: raw, markdown, children.
8. source spans.
9. typed semantic AST.
10. v1 component registry.
11. registry-driven validation.
12. deterministic JSON AST output.
13. deterministic semantic HTML rendering.
14. minimal built-in reference theme sufficient for examples.
15. CLI:
    - `pagedoc lint <document.yaml>`
    - `pagedoc ast <page.book.md>`
    - `pagedoc render <document.yaml> --html-out <path>`
16. local tests and golden fixtures.

### Explicitly out of scope

- PDF generation;
- WeasyPrint;
- automatic page overflow measurement;
- migration from another format;
- WYSIWYG;
- live preview server;
- remote assets;
- arbitrary plugins loaded from documents;
- JavaScript/MDX execution.

### TDD order

Recommended vertical slices:

1. front matter + plain Markdown AST;
2. raw `request`;
3. raw-body literal HTML safety;
4. `response`;
5. markdown `note`/`result`;
6. child container `row`;
7. `compare`;
8. `flow` + `step`;
9. `browser`;
10. `media` asset validation;
11. full document manifest;
12. HTML rendering;
13. deterministic repeated output.

Write or extend tests before implementation for each slice.

### Acceptance criteria

Milestone 1 is complete when:

- every documented v1 syntax rule has test coverage;
- `tests/fixtures/request-response.book.md` serializes exactly to its expected AST contract, modulo explicitly documented Markdown-subtree representation;
- raw component content containing HTML-like strings is escaped in generated HTML;
- unknown tags/attrs and invalid nesting fail with source locations;
- source files contain no required pixel geometry;
- the example document renders to one deterministic HTML file;
- running render twice produces identical HTML bytes;
- all tests pass locally;
- no GitHub Actions are required.

## Milestone 2 - fixed-page theme, authoritative layout, PDF backend

> Revision note: the original plan separated layout diagnostics (old M2)
> from the PDF backend (old M3). Real fixed-page fit cannot be validated
> correctly without the actual layout backend, so **WeasyPrint moved
> into M2 as the single authoritative layout engine**. Old M3 scope
> (packaging/integration surface, richer automatic composition,
> performance, tooling polish) becomes later work. The M1 language and
> AST contracts remain backward-compatible.

Start only after M1 contracts are stable.

Implement:

- strict theme manifest model with fixed physical page geometry;
- named page regions (at minimum `header`, `content`, `footer`);
- fixed page shell rendering with per-node `data-pd-*` identifiers;
- row split presets (`equal`, `wide-left`, `wide-right`, `auto`);
- intrinsic component layout driven by the real rendered result;
- deterministic `auto` resolution for `row`/`compare`/`flow`, where
  `compare`/`flow` `auto` may re-render with a different orientation when
  the preferred one provably does not fit;
- WeasyPrint backend adapter (`backends/weasyprint.py`) producing PDF
  plus layout diagnostics from the rendered box tree;
- hard invariant: one logical `.book.md` page = one physical PDF page;
  overflow is an authoring error with a source-located diagnostic;
- `pagedoc render --pdf-out` and `pagedoc inspect` (human + `--json`);
- local theme fonts only; no remote assets.

Critical requirement:

Do not build a duplicate handwritten text-fit engine. Derive fit/overflow from the authoritative rendered HTML/CSS/backend path.

Acceptance includes representative fixtures for:

- prose-heavy;
- table-heavy;
- request/response row;
- request/note row;
- horizontal comparison;
- vertical comparison;
- flow;
- media;
- long code;
- intentional overflow.

## Milestone 3 - composition, performance and integration surface

Later work, now that WeasyPrint/PDF lives in M2:

- richer automatic composition and fit heuristics;
- performance work driven by a benchmark suite;
- public Python package metadata polish;
- external theme packages;
- migration/import adapters;
- richer inspection tooling.

These are not part of the first implementation task.

## Performance expectations

M1 operations on a small document should feel immediate.

Do not optimize prematurely, but avoid obvious repeated full-document reparsing inside validation/render loops.

A later benchmark suite should separately measure:

- parse;
- validate;
- render HTML;
- layout;
- PDF backend.

## Code quality

- prefer typed models;
- avoid giant files;
- keep parser, validation, rendering and backend boundaries separate;
- errors are structured, testable values before becoming CLI text;
- no broad exception swallowing;
- no hidden global mutable registry;
- deterministic serialization;
- comments explain non-obvious parser/layout contracts, not restate code.

## Agent handoff result

The implementing agent should finish with:

- commit SHA(s);
- changed-file summary;
- test command and count;
- example render command;
- generated artifact locations;
- spec deviations, if any;
- unresolved questions.

Do not silently modify the normative specification to make implementation easier. Escalate contradictions instead.
