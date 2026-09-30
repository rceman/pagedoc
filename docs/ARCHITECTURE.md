# PageDoc Architecture v1

## 1. Pipeline

```text
document.yaml
    |
    +--> ordered *.book.md pages
                |
                v
          Source loader
                |
                v
             Parser
                |
                v
        Semantic AST v1
                |
                v
      Registry validation
                |
                v
          HTML renderer
                |
                v
        Theme HTML + CSS
                |
                +--> deterministic HTML artifact
                |
                +--> WeasyPrint adapter (authoritative fixed-page layout)
                            |
                            v
                  PDF + layout diagnostics
```

> Revision note (M2): the plan originally deferred the PDF backend to a
> later milestone. Real fixed-page fit cannot be validated without the
> actual layout backend, so WeasyPrint moved into M2 as the single
> authoritative layout engine. See `IMPLEMENTATION_PLAN.md`.

## 2. Architectural boundary

PageDoc owns:

- source loading;
- Markdown and PageDoc syntax parsing;
- semantic AST;
- component registry;
- generic validation;
- page composition primitives;
- theme contract;
- deterministic HTML rendering;
- backend interface;
- generic layout/overflow diagnostics.

PageDoc does not own:

- editorial policy;
- domain-specific content rules;
- publication workflow of a consumer project;
- consumer release/version semantics;
- consumer-specific sanitization;
- remote asset acquisition.

## 3. Suggested Python package shape

The exact module names may evolve, but responsibilities should remain separated:

```text
src/pagedoc/
    cli.py
    parser.py
    ast.py
    registry.py
    validation.py
    document.py
    pipeline.py        # render -> backend layout -> diagnostics orchestration
    render/
        html.py
        components.py
        markdown.py
    theme/
        loader.py
        model.py
        builtin/       # reference theme.yaml + theme.css
    backends/
        base.py        # backend-neutral layout result types
        weasyprint.py  # WeasyPrint adapter (see "WeasyPrint adapter" below)
```

Avoid a single renderer file that contains parsing, validation, syntax highlighting, HTML templates, geometry, and PDF orchestration together.

## 4. Parser

The parser converts authored source to a semantic AST.

It must:

- parse YAML front matter;
- parse Markdown;
- recognize registered standalone PageDoc tags;
- respect component body mode;
- preserve source spans;
- produce deterministic nodes;
- report structural errors without renderer involvement.

It must not:

- emit HTML;
- consult CSS;
- fetch assets from the network;
- execute source code.

## 5. AST

The AST is an internal contract and debug surface.

Recommended node families:

- `PageNode`;
- Markdown nodes or a normalized Markdown subtree;
- `ComponentNode`;
- `RawBody`;
- `SourceSpan`.

Every node has a stable `type` and source span.

AST JSON should include `schema_version: 1`.

The internal Python model may use dataclasses or another typed representation. JSON serialization must be deterministic.

## 6. Registry

The registry is the single source of truth for PageDoc components.

It defines:

- body mode;
- attribute schema;
- nesting;
- child count;
- semantic class;
- renderer;
- layout hints.

Parser recognition may consult the set of registered names, but parser behavior must not hardcode per-component presentation logic.

Validation and rendering must consume the same registry descriptors.

## 7. Rendering

HTML rendering consumes only a validated AST plus a loaded theme.

Generated HTML should:

- be semantic and inspectable;
- use stable classes/data attributes;
- avoid inline arbitrary geometry;
- include source/page IDs for diagnostics;
- escape authored text correctly;
- preserve raw technical blocks as text, never executable markup.

Raw request/response bodies containing `<script>` or `<img>` must be rendered escaped.

## 8. Theme

Themes own presentation:

- fixed page size;
- page regions;
- typography;
- spacing;
- colors;
- component appearance;
- split preset geometry;
- syntax-highlight palette;
- print rules.

Document content must not reach into theme CSS.

See `THEME_SPEC.md`.

## 9. One authoritative layout path

A critical design constraint:

**Do not build a second handwritten typography/layout engine that duplicates CSS calculations.**

In particular, do not independently reimplement all of these in Python solely for fit validation:

- line wrapping;
- font metrics;
- paragraph margins;
- table row heights;
- component padding;
- code line heights.

The selected HTML/CSS rendering path is authoritative.

**The authoritative fixed-page layout engine is WeasyPrint.** There is
exactly one layout backend for fixed-page output; do not add Chromium,
Playwright, or screenshot-based alternatives.

Layout diagnostics are derived from the rendered WeasyPrint document:
the adapter walks the rendered box tree, maps boxes back to authored
nodes via `data-pd-node` attributes, and reports overflow against the
theme's explicit content region. One logical `.book.md` page must render
as exactly one physical page; overflow is an authoring error.

**What PageDoc measures is exactly what PageDoc emits.** The adapter
performs `HTML(...).render()` once and returns a `RenderedDocument`
wrapping the resulting WeasyPrint `Document`; diagnostics are computed
from that Document's box tree and `write_pdf`/`pdf_bytes` serialize the
same Document. The PDF is never produced by re-laying out the HTML. A
document whose preferred composition already fits needs exactly one
layout pass; overflow recovery adds bounded candidate passes plus the
final authoritative render (see section 10).

A lightweight preflight may catch obviously invalid structures, but it must not become a divergent duplicate renderer.

## 10. Intrinsic sizing

Normal components are content-sized.

Authors do not specify heights.

Conceptually each rendered block has:

- intrinsic/minimum content size;
- optional growth behavior;
- layout constraints from its parent;
- resolved size from the rendering backend.

`row` resolves a named split preset and aligns children.

`flow layout="auto"` may choose a horizontal or vertical presentation through a deterministic rule.

### Automatic composition (M3.1)

`row split="auto"`, `compare layout="auto"`, and `flow layout="auto"`
resolve by real fit, evaluated exclusively through the authoritative
backend — never by Python-side text measurement:

1. The initial pass renders every `auto` decision at its
   registry-preferred value (child-type rules for rows, `horizontal`
   for compare/flow). Pages that then fit are never recomposed.
2. Each overflowing page enters a **page-local exact search**: the
   Cartesian product of that page's auto-decision candidates, hard
   limit `MAX_COMPOSITION_CANDIDATES_PER_PAGE = 24` complete
   assignments including the preferred one. Larger spaces fail with an
   actionable diagnostic instead of heuristic search.
3. Every candidate assignment is rendered and measured through
   WeasyPrint. Fitting beats non-fitting; among fitting assignments the
   winner minimizes, lexicographically: deviations from the preferred
   composition, real `content_used`, then stable enumeration order.
4. Explicit authored values (`split="equal"`, `layout="vertical"`, ...)
   never participate and are never overridden.
5. Candidates are evaluated with earlier pages' already-selected
   resolutions applied — a block that cannot be placed on its fixed
   page escapes onto the next physical page and would otherwise
   contaminate downstream measurement. A page whose measured block
   count is short of its authored top-level children is never "fit".
6. After all failing pages resolve, one **final full-document render**
   with the combined resolution map is measured and emitted; a page
   whose selected assignment does not reproduce there reports an
   internal composition-stability error.

A structured `CompositionTrace` (JSON-serializable, timestamp-free)
records decisions, candidate space, evaluated measurements, and the
selected resolution per searched page, exposed via `pagedoc inspect`.

Historical note: M2 used a coarse fallback — every still-horizontal
`auto` node on a failing page flipped to vertical in a single extra
pass. M3.1 replaces it with the bounded per-component search above.

Any automatic choice must be reproducible for identical source, theme, engine version, and local assets.

## 11. Overflow diagnostics

For fixed pages, PageDoc detects content outside the page content
region using the rendered box tree.

A diagnostic identifies:

- page ID;
- source file;
- the most specific authored node whose rendered bounds cross a region
  boundary (via `data-pd-node` on the deepest crossing box — e.g. a
  `request` inside a `row`, not the row itself);
- overflow axis (vertical/horizontal) and amount in px;
- suggested structural action, not an automatic content rewrite.

PageDoc must never silently shrink fonts to make content fit.

## 12. Backend interface

HTML generation is mandatory.

The fixed-page backend interface lives behind `pagedoc.backends`.
`backends/base.py` defines backend-neutral layout result types;
`backends/weasyprint.py` is the sole implementation in M2.

A backend interface accepts:

- generated HTML;
- theme assets/base URL;
- deterministic build options.

and returns:

- artifact path/bytes;
- page count;
- backend diagnostics;
- layout metadata (per-node placements, region usage).

### WeasyPrint adapter boundary

WeasyPrint has no public box-tree API. The adapter is allowed to read
the private `Page._page_box` tree (`weasyprint.formatting_structure`)
solely to measure rendered block positions against theme regions. All
private API access is isolated in `backends/weasyprint.py`, documented
there, covered by integration tests, and the WeasyPrint dependency is
pinned accordingly. No other module may import WeasyPrint internals.

PDF byte determinism is achieved by setting `SOURCE_DATE_EPOCH` inside
the adapter around `Document.write_pdf`, which stabilizes embedded font
timestamps. The serialized Document is the same object that diagnostics
measured.

### Visual fidelity contract

Correct geometry in the layout report is not sufficient: small visual
primitives whose alignment is semantically meaningful (centered dots in
rings, connector endpoints, status markers, checkbox/radio marks,
diagram nodes) must be constructed as **geometry** — inline SVG or CSS
boxes/pseudo-elements sharing explicit coordinates — never as
independently positioned font glyphs (e.g. `○` + `•`), which shift under
different font metrics and PDF renderers. Ordinary text stays text.

`examples/visual-primitives/` is the renderer-conformance corpus; its
markers are validated by rasterizing the final PDF with two independent
renderers (PDFium via `pypdfium2`, MuPDF via `PyMuPDF`) and asserting
outer/inner marker centers agree within a small documented tolerance.
These rasterizers are test/inspection tooling only, never layout
engines; they are optional dependencies (`pagedoc[raster]`).

### Flattened PDF (experimental)

`--flattened-pdf-out` writes an image-only PDF derived from the already
validated vector PDF:

    rendered Document -> vector PDF bytes -> PDFium raster at fixed DPI
        -> one PNG per physical page -> img2pdf assembly

The HTML is never re-laid-out; WeasyPrint remains the single layout
truth. Physical page count, order, and exact point size are preserved
(the img2pdf layout function pins each page's pt size from the source
page). `nodate` + the internal writer make flattened output byte
deterministic. Tradeoffs (larger size, no text selection/search, quality
bounded by raster DPI) are documented in THEME_SPEC section 14. Flatten
is opt-in, never the M2 default; M3 decides which artifact a
publication uses.

## 13. Determinism

Given identical:

- sources;
- manifest;
- local assets;
- theme (including pinned font files);
- engine version;
- backend version;

PageDoc should produce byte-stable AST/HTML where practical.

PDF byte identity may depend on backend metadata; if fully byte-stable PDF is not practical, normalized artifact identity and deterministic visible output must still be testable. (Current status: vector PDF and flattened PDF are both byte-identical on repeat.)

Cross-host layout determinism additionally requires pinned local fonts:
the reference theme vendors Inter and Roboto Mono (OFL) so glyph metrics
cannot vary with the host's font stack. Themes that rely on system fonts
are allowed but may produce different wrapping and fit results on
different hosts; `Theme.typography_portable` reports this and
`inspect --json` exposes it.

No build step may depend on current network content.

## 14. Asset handling

All assets are local.

The loader should:

- resolve paths relative to source/manifest/theme;
- reject missing assets;
- never download remote assets implicitly;
- expose resolved assets to the renderer/backend.

Future integrity hashes may be added at the theme/document layer without changing page authoring syntax.

## 15. Syntax highlighting

Syntax highlighting is presentation.

A renderer may tokenize known technical formats for spans, but:

- tokenization must never mutate source text;
- unsupported/invalid input falls back to escaped monospaced text;
- authoring syntax does not require manual highlight spans.

## 16. Testing layers

Required test layers:

1. parser unit tests;
2. registry/validation tests;
3. golden AST fixtures;
4. HTML golden/structural tests;
5. deterministic repeat-run tests;
6. example-document smoke tests;
7. later: layout and backend tests.

Keep tests local; no CI dependency is required.
