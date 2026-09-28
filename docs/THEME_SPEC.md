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

Theme linting should eventually verify:

- required manifest keys;
- known split names;
- local CSS exists;
- local font/assets exist;
- page/content region is valid;
- no remote font/import dependency is required;
- deterministic asset resolution.
