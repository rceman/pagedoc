# PageDoc Serialized AST Format v1

This document describes the deterministic JSON serialization emitted by
`pagedoc ast` and consumed by contract fixtures. It implements
AUTHORING_SPEC.md section 12 (`schema_version: 1`) and records the
normalized Markdown subtree representation that section 12 leaves open.

## Top level

```json
{
  "schema_version": 1,
  "type": "page",
  "metadata": { "...": "..." },
  "children": [ "<node>" ],
  "source": { "...": "..." }
}
```

- `metadata` contains the authored front matter keys verbatim (unknown
  keys preserved, `_json_safe` normalized). Keys serialize in sorted
  order.
- `children` follows source order.
- Every node carries `source`:

```json
{
  "path": "tests/fixtures/request-response.book.md",
  "start_line": 9, "start_col": 1,
  "end_line": 12, "end_col": 11
}
```

`path` is the path as addressed by the build (the CLI argument for a
single page, or the manifest-relative page path inside a document). It
is never rewritten to a machine-specific absolute path.

## Component nodes

```json
{
  "type": "<component name>",
  "attrs": { "...": "..." },
  "raw": "...",          // raw body mode: verbatim body text
  "body": [ "<md>" ],    // markdown body mode: list of markdown nodes
  "children": [ "..." ], // children body mode: list of component nodes
  "source": { "...": "..." }
}
```

- Exactly one of `raw` / `body` / `children` is present, matching the
  component's registry body mode. `body`/`children` emit even when empty
  (as `[]`) so the body mode is self-describing; `raw` emits for empty
  raw bodies as `""`.
- `attrs` always contains the resolved attributes: authored values plus
  registry defaults (`row` gains `split: "auto"` and `align: "start"`,
  `request` gains `lang: "http"`, `response` gains `lang: "auto"`, etc.).
  Keys serialize in sorted order, so authored attribute order does not
  affect output.

## Markdown nodes

Markdown blocks appear directly as page children and inside component
`body` arrays. Node shapes:

| type | extra fields | children |
| --- | --- | --- |
| `paragraph` | - | inline nodes |
| `heading` | `attrs.level` (1-6) | inline nodes |
| `block_quote` | - | block nodes |
| `bullet_list` | `attrs.ordered=false` | `list_item` |
| `ordered_list` | `attrs.ordered=true`, `attrs.start` (when != 1) | `list_item` |
| `list_item` | - | block nodes |
| `code_block` | `attrs.lang` (when fenced with info) | `text` payload |
| `table` | - | `table_row` |
| `table_row` | `attrs.header` (bool) | `table_cell` |
| `table_cell` | `attrs.header` (bool), `attrs.align` (when column alignment set) | inline nodes |
| `thematic_break` | - | - |

Inline nodes:

| type | extra fields | children |
| --- | --- | --- |
| `text` | `text` payload | - |
| `code_inline` | `text` payload | - |
| `emphasis` | - | inline nodes |
| `strong` | - | inline nodes |
| `link` | `attrs.href`, `attrs.title` (optional) | inline nodes |
| `image` | `attrs.src`, `attrs.alt`, `attrs.title` (optional) | - |
| `softbreak` | - | - |
| `hardbreak` | - | - |

All `attrs` objects serialize with sorted keys.

## Determinism

- Keys within each object serialize in the fixed field order shown above
  (`type`, `attrs`, `children`/`raw`/`body`, `text`, `source`);
  `metadata`/`attrs` maps sort keys alphabetically.
- Serialization is `json.dumps(..., indent=2, ensure_ascii=False)` plus a
  trailing newline.
- No timestamps, random IDs, or machine-specific absolute paths appear in
  output.

## Contract fixtures

- `tests/fixtures/request-response.book.md` /
  `request-response.ast.json` — component + raw-body contract.
- `tests/fixtures/markdown-note.book.md` / `markdown-note.ast.json` —
  normalized Markdown subtree + `body` field contract.

Fixture sources are regenerated with `pagedoc ast <fixture.book.md>`;
any intentional serialization change must update the fixtures and this
document together.
