# PageDoc Authoring Specification v1

## 1. Purpose

PageDoc source is designed for human and agent editing. The source describes document meaning and composition while themes and renderers own presentation geometry.

The primary source format is:

```text
*.book.md
```

One `.book.md` file represents one logical fixed-size page in v1.

A document manifest defines page order and theme selection.

## 2. Page source structure

A page contains:

1. YAML front matter;
2. Markdown content;
3. optional PageDoc custom block elements.

Example:

```markdown
---
id: project-api
group: Product Guide
title: Inspect a Project API
---

The dashboard loads project data from an API.

<row>

<request title="Project list">
GET /api/v1/projects/user/john
</request>

<response status="200">
{"projects":["alpha","beta"]}
</response>

</row>
```

### Required front matter

- `id`: stable page identifier, unique within the document;
- `group`: section or chapter label;
- `title`: page title.

### Optional front matter

- `kind`: defaults to `content`; themes may use values such as `front-matter`;
- `template`: optional theme-defined page template name.

Unknown front-matter keys should be preserved in the AST under metadata but may be rejected by a stricter document profile later. v1 core must not silently discard them.

## 3. Markdown baseline

PageDoc v1 supports a deterministic CommonMark-compatible baseline plus tables.

The authoring surface includes:

- paragraphs;
- headings;
- ordered and unordered lists;
- emphasis and strong emphasis;
- links;
- inline code;
- fenced code blocks;
- tables.

Generic technical content should stay in Markdown whenever a PageDoc component does not add stable semantic meaning.

## 4. Custom block recognition

PageDoc custom elements use HTML-like syntax, but they are not parsed as XML and they are not MDX.

A known PageDoc opening tag is recognized only when:

- it begins at the first non-whitespace character on a line;
- the complete opening tag is on that line;
- the tag name is registered;
- attributes, if present, use the v1 attribute grammar.

A closing tag is recognized only when it is the only non-whitespace content on its line.

Example:

```text
<request title="Project list">
GET /api/projects
</request>
```

This rule deliberately allows raw bodies to contain strings such as:

```html
<img src="/asset.png">
<script>example()</script>
```

without XML escaping.

## 5. Attribute grammar

v1 attributes are:

```text
name="value"
```

Rules:

- attribute names are ASCII lowercase words with optional hyphens;
- values are double-quoted UTF-8 strings;
- `&quot;` is not required for ordinary source authoring; use backslash escaping for a literal quote when needed;
- duplicate attributes are invalid;
- unknown attributes are invalid for registered components;
- source order of attributes does not affect AST equality.

The parser must produce a precise line/column diagnostic for malformed attributes.

## 6. Component body modes

Registered components declare one of these body modes:

### raw

The body is preserved as authored, except that the trailing newline immediately before the matching closing tag is normalized away.

Used by:

- `request`;
- `response`;
- `browser`.

Raw bodies are not recursively parsed as Markdown or PageDoc elements.

### markdown

The body is recursively parsed as Markdown.

Used by:

- `note`;
- `result`;
- `media` caption body;
- `flow/step`.

### children

The body contains registered child PageDoc blocks separated by optional blank lines.

Used by:

- `row`;
- `compare`;
- `flow`.

Plain prose directly inside a `children` body is invalid in v1.

## 7. Nesting

Only nesting explicitly allowed by the component registry is valid.

Examples:

- `row` may contain two renderable child blocks;
- `compare` contains exactly two renderable child blocks;
- `flow` contains `step` children;
- `request` and `response` cannot contain PageDoc children.

Unknown or invalid nesting must fail at lint time.

## 8. Source spans

Every AST node must preserve:

- source path;
- start line;
- start column where practical;
- end line;
- end column where practical.

Diagnostics must point back to authored source, not generated HTML.

## 9. Whitespace

General rules:

- YAML front matter ends at the second `---` delimiter;
- UTF-8 is required;
- LF is canonical in serialized fixtures;
- Markdown whitespace follows the Markdown parser's normal semantics;
- raw component body whitespace is preserved;
- blank lines around custom blocks are allowed and do not create empty nodes;
- generated AST serialization must be deterministic.

## 10. Geometry is not authoring content

Normal `.book.md` sources must not accept presentation geometry such as:

- pixel height;
- pixel width;
- absolute x/y coordinates;
- arbitrary margins;
- arbitrary gaps;
- font sizes;
- CSS snippets.

Examples of forbidden authoring attributes:

```text
height="452"
width="1050"
gap="15"
style="..."
x="300"
```

Composition may use named layout presets such as:

```text
<row split="wide-left">
```

because the name expresses composition intent rather than geometry.

## 11. Document manifest

A document manifest is YAML:

```yaml
id: product-handbook
title: Example Product Handbook
theme: themes/dark-technical/theme.yaml
pages:
  - pages/01-overview.book.md
  - pages/02-api.book.md
```

Required keys:

- `id`;
- `title`;
- `pages`.

Optional:

- `theme`.

Page paths are resolved relative to the manifest.

Duplicate page IDs and duplicate page paths are errors.

## 12. AST serialization

The debug/contract AST is JSON and uses:

```json
{
  "schema_version": 1,
  "type": "page",
  "metadata": {},
  "children": [],
  "source": {}
}
```

Node ordering follows source order.

Object-key ordering in emitted JSON should be deterministic for golden fixtures.

Compiled JSON is an IR/debug artifact, not the authoring format.

## 13. Error behavior

The parser/linter must fail clearly on:

- missing required front matter;
- duplicate page IDs in a document;
- malformed component attributes;
- unknown component names;
- unknown component attributes;
- unclosed components;
- mismatched closing tags;
- invalid nesting;
- wrong child counts;
- invalid enum/preset values;
- unresolved local media assets.

Do not silently recover structural authoring errors.
