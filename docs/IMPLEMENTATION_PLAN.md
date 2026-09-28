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

## Milestone 2 - theme and fixed-page layout diagnostics

Start only after M1 contracts are stable.

Implement:

- strict theme manifest model;
- fixed page shell;
- page region rendering;
- row split presets;
- intrinsic component layout;
- deterministic `auto` resolution;
- fixed-page overflow diagnostics;
- layout inspection artifacts.

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

## Milestone 3 - PDF backend

Implement a backend abstraction and an initial WeasyPrint adapter.

Requirements:

- local-only assets;
- exact page size from theme;
- page count reporting;
- deterministic build inputs;
- backend diagnostics;
- HTML remains independently inspectable.

Add PDF only after HTML/layout behavior is stable.

## Milestone 4 - packaging and integration surface

Potential later work:

- public Python package metadata;
- stable CLI;
- versioned AST schema;
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
