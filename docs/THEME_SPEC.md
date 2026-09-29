# PageDoc Theme Specification v1

## 1. Goal

A PageDoc theme controls visual presentation without leaking pixel geometry into authored page content.

A theme is selected by the document manifest.

Suggested structure:

```text
themes/dark-technical/
    theme.yaml
    theme.css
    assets/
        fonts/
        icons/
```

## 2. Responsibilities

A theme owns:

- physical page width and height;
- content region;
- optional header/footer/sidebar regions;
- typography roles;
- spacing tokens;
- colors;
- borders and surfaces;
- component appearance;
- named row split presets;
- flow presentation;
- print CSS;
- local theme assets.

A page source owns:

- content;
- semantics;
- component choice;
- named composition intent.

## 3. Theme manifest

A fixed-page theme manifest is a YAML file:

- `page.width` / `page.height` / `page.unit`: physical geometry of one
  logical page. `unit` is `px` in v2. Geometry is required.
- `regions`: named page regions with explicit `x`/`y`/`width`/`height`.
  `content` is required; `header` and `footer` are the other standard
  regions. A theme may leave header/footer visually empty, but region
  geometry is always explicit.
- `splits`: named row split ratios (e.g. `wide-left: [2, 1]`).
- `spacing`: design tokens such as `block`/`internal`.
- `fonts`: named typography roles (`prose`, `mono`, ...) whose `source`,
  when present, is a local file inside the theme directory. Themes never
  reference remote fonts. A role without `source` falls back to system
  font families (`sans-serif`/`monospace` via fontconfig).
- `css`: a local stylesheet inside the theme directory.

Illustrative contract:

```yaml
id: dark-technical
version: 1

page:
  width: 2500
  height: 2500
  unit: px

regions:
  content:
    x: 300
    y: 500
    width: 2150
    height: 1700

spacing:
  block: 15
  internal: 25

splits:
  equal: [1, 1]
  wide-left: [2, 1]
  wide-right: [1, 2]

fonts:
  prose:
    family: Inter
    source: assets/fonts/Inter-Regular.ttf
  mono:
    family: Roboto Mono
    source: assets/fonts/RobotoMono-Regular.ttf

css: theme.css
```

This is an example shape, not permission for page source to reference numeric geometry.

## 4. Geometry ownership

The following belong in the theme or renderer, not `.book.md`:

- page dimensions;
- content box dimensions;
- margins/padding;
- font sizes;
- line heights;
- component min heights;
- row gap;
- borders;
- status colors;
- icon dimensions.

The theme may expose **named presets** to page source.

Example:

```text
<row split="wide-left">
```

The source expresses intent. The theme maps the preset to actual geometry.

## 5. Component CSS contract

Generated HTML should use stable semantic classes, for example:

```text
.pd-request
.pd-response
.pd-browser
.pd-note
.pd-result
.pd-compare
.pd-flow
.pd-media
.pd-row
```

Themes style these classes.

Themes must not depend on source file names or page-specific IDs for normal component styling.

Page-specific CSS is out of scope for v1.

## 6. Typography

Themes define named roles rather than asking authors for font sizes.

Suggested roles:

- page group/header;
- page title;
- body;
- small body;
- mono/code;
- table;
- label;
- footer.

Fonts must be local and loadable without network access.

Fallback behavior must be explicit.

### Typography portability contract

Two tiers:

- **Pinned local fonts** (a font role with `source:` pointing at a
  vendored file): portable deterministic fixed-page typography — the
  same input produces the same wrapping and fit on any host.
- **System-font themes** (roles without `source:`): allowed for custom
  themes but *not* guaranteed cross-host deterministic — glyph metrics
  may differ between operating systems, changing line wrapping and
  overflow results.

`Theme.typography_portable` is true only when every declared role is
backed by a local file; `pagedoc inspect --json` reports it.

The builtin reference theme vendors static instances of **Inter
Regular** (prose) and **Roboto Mono Regular** (mono) under the SIL Open
Font License (`theme/builtin/fonts/`, license texts included,
SHA-256-pinned). The CSS stacks still list system families as fallback.

## 7. Color and accessibility

Themes should:

- preserve strong luminance contrast;
- avoid relying on red/green distinction alone;
- pair status color with text/icon/border cues;
- retain meaning in grayscale where practical.

This is a theme contract, not page-source markup.

## 8. Browser component

The browser/address-bar component may visually distinguish:

- secure scheme indicator;
- scheme;
- host;
- path;
- query;
- fragment.

The URL text remains selectable/inspectable in HTML.

Do not rasterize textual browser bars merely for styling.

## 9. Request/response layout

Themes define visual surfaces for request and response components.

When placed in a `row`, the parent layout controls width distribution.

The components themselves must not know whether they are left, right, full-width, or vertically stacked.

## 10. Automatic layout

For `layout="auto"` or `split="auto"`, the renderer/theme may resolve a deterministic presentation from:

- component type;
- content size information exposed by the authoritative layout path;
- theme presets.

The decision must not depend on randomness, clock time, viewport state, or network resources.

## 11. Overflow

Themes must define a fixed content region for fixed-page output.

Under the M2 fixed-page contract, **one authored `.book.md` page renders
as exactly one physical page**. Rendered content that exceeds the
content region is an authoring error reported with a source location.

The engine should report overflow rather than:

- silently reducing font size;
- clipping without diagnostics;
- changing page geometry;
- inserting arbitrary per-page pixel overrides.

## 12. Theme validation

The theme loader enforces:

- required manifest keys (`id`, `page`, `regions`, `css`);
- `page.width`/`height` > 0 and `unit: px`;
- every region: `x >= 0`, `y >= 0`, `width > 0`, `height > 0`,
  `x + width <= page.width`, `y + height <= page.height` — a region
  extending outside the physical page fails with a theme-path, region
  name, and offending boundary;
- regions may overlap intentionally (decorative overlays);
- spacing values must be non-negative numbers;
- split ratios must be lists of >= 2 positive numbers;
- local CSS exists; font `source` files exist and are local;
- theme CSS must not contain remote resources — `url(http...)`,
  `url(//cdn...)`, and `@import` of remote URLs are rejected at load
  time; local relative `url()`, `data:` URIs, and `#fragment`
  references are allowed. M2 does not rebase `url()` paths inside
  theme CSS: such URLs resolve against the document's base directory,
  so a theme shared across documents should avoid CSS image
  dependencies entirely (the Book v2 reference theme is pure CSS
  geometry + pinned fonts);
- no remote font/import dependency is required;
- deterministic asset resolution.

A theme is selected by the document manifest: `theme: default` uses the
packaged reference theme; any other value is a `theme.yaml` path
resolved relative to the manifest. `examples/themes/book-v2-reference/`
is the standalone square-page reference theme demonstrating this.

## 13. Geometric primitives

Visual primitives whose exact alignment is meaningful (centered dots in
rings, connector endpoints, status markers, checkbox/radio marks) must
be constructed as geometry — inline SVG or CSS boxes sharing explicit
coordinates — not independent font glyphs. The builtin theme's flow
connectors are CSS shaft+arrowhead boxes; marker/check fixtures are
inline SVG. See ARCHITECTURE section 12.

## 14. Flattened PDF tradeoffs

`--flattened-pdf-out` is an experimental output mode producing an
image-only PDF from the validated vector PDF.

| | vector PDF | flattened PDF |
|---|---|---|
| text | searchable/selectable | reduced/absent |
| size | smaller | larger |
| resolution | independent | bounded by raster DPI |
| accessibility | preserved | reduced |
| viewer dependence | renders vectors/fonts | pixel-locked |

Neither is universally superior; M3/publication integration chooses.
Cross-renderer raster validation is part of fixed-page engine
acceptance (tests rasterize the vector PDF with PDFium and MuPDF and
compare marker geometry).
