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
                +--> optional backend adapter
                            |
                            v
                           PDF
```

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
    source.py
    parser.py
    ast.py
    registry.py
    validation.py
    render/
        html.py
        components.py
    theme/
        loader.py
        model.py
    layout/
        diagnostics.py
    backends/
        base.py
        weasyprint.py
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

Layout diagnostics should be derived from rendered layout/backend information whenever possible.

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

Any automatic choice must be reproducible for identical source, theme, engine version, and local assets.

## 11. Overflow diagnostics

For fixed pages, PageDoc must eventually detect content outside the page content region.

A useful diagnostic should identify:

- page ID;
- source file;
- offending/responsible block where possible;
- content region bounds;
- overflow direction/amount if backend data exposes it;
- suggested structural action, not an automatic content rewrite.

PageDoc must never silently shrink fonts to make content fit.

## 12. Backend interface

HTML generation is mandatory.

PDF is an adapter concern.

A backend interface should accept:

- generated HTML;
- theme assets/base URL;
- deterministic build options.

and return:

- artifact path/bytes;
- page count;
- backend diagnostics;
- optional layout metadata.

Initial PDF target: WeasyPrint, introduced only after the HTML/AST contract is stable.

## 13. Determinism

Given identical:

- sources;
- manifest;
- local assets;
- theme;
- engine version;
- backend version;

PageDoc should produce byte-stable AST/HTML where practical.

PDF byte identity may depend on backend metadata; if fully byte-stable PDF is not practical, normalized artifact identity and deterministic visible output must still be testable.

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
