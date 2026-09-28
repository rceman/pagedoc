# PageDoc Component Contract v1

## 1. Design rule

The component vocabulary stays intentionally small.

Markdown already owns ordinary prose structures. PageDoc components are reserved for recurring technical semantics or page composition that Markdown cannot express clearly.

Initial top-level semantic components:

- `request`
- `response`
- `browser`
- `note`
- `result`
- `compare`
- `flow`
- `media`

Initial layout primitive:

- `row`

Internal child element:

- `step` inside `flow`

## 2. request

Represents one HTTP-style request or request-like protocol artifact.

Body mode: `raw`.

Allowed attributes:

- `title`: optional display title;
- `lang`: optional syntax hint; default `http`.

Example:

```text
<request title="Project list">
GET /api/v1/projects/user/john
Cookie: session=demo
</request>
```

Renderer responsibilities:

- preserve authored line structure;
- style method, path, headers and body when recognizable;
- degrade safely to monospaced raw text when parsing is incomplete;
- never require the author to wrap the body in a fenced code block.

The renderer must not mutate the request bytes/text represented by the source.

## 3. response

Represents one HTTP-style response or response-like result.

Body mode: `raw`.

Allowed attributes:

- `title`: optional display title;
- `status`: optional short status such as `200`, `404`, or `200 OK`;
- `lang`: optional syntax hint; default `auto`.

Example:

```text
<response status="200">
{"projects":["alpha","beta"]}
</response>
```

A theme may style status classes differently, but status color must never be the sole carrier of meaning.

## 4. browser

Represents a URL as browser navigation/address-bar UI rather than generic code.

Body mode: `raw`.

Allowed attributes:

- `title`: optional title;
- `status`: optional visible navigation/result status.

The body must contain exactly one non-empty URL line in v1.

Example:

```text
<browser status="404">
https://app.example.test/projects
</browser>
```

Renderer behavior:

- parse scheme, userinfo, host, port, path, query and fragment when possible;
- display an HTTPS lock/secure indicator when the scheme is `https`;
- use redundant text/icon cues rather than color alone;
- show malformed/relative URLs safely as text rather than failing rendering after successful validation.

## 5. note

Represents supporting commentary, an observation, caveat, or contextual explanation.

Body mode: `markdown`.

Allowed attributes:

- `tone`: `note` (default) or `warning`;
- `title`: optional.

Example:

```text
<note>
The response format stays the same, but the selected project changes.
</note>
```

Do not create separate `warning`, `tip`, or `aside` components in v1.

## 6. result

Represents the observed conclusion/result of the surrounding example.

Body mode: `markdown`.

Allowed attributes:

- `title`: optional.

Example:

```text
<result>
The second request returns the same data shape with a different project.
</result>
```

A result is semantic, not merely a differently colored note.

## 7. row

Layout primitive for placing related child components on one row.

Body mode: `children`.

v1 child count: exactly 2.

Allowed attributes:

- `split`: `auto` (default), `equal`, `wide-left`, `wide-right`;
- `align`: `start` (default), `stretch`.

Example:

```text
<row>

<request>
GET /api/projects
</request>

<note>
The request is shown beside the explanation.
</note>

</row>
```

Rules:

- `row` has no content semantics;
- children keep their own semantics;
- source does not specify pixel widths;
- themes map split presets to actual geometry;
- `auto` may use registry hints, but the resolved preset must be deterministic.

## 8. compare

Semantic two-way comparison.

Body mode: `children`.

Child count: exactly 2.

Allowed attributes:

- `labels`: two labels separated by `|`, for example `Expected|Actual`;
- `layout`: `auto` (default), `horizontal`, `vertical`.

Example:

```text
<compare labels="Expected|Actual">

<response status="200">
{"mode":"compact"}
</response>

<response status="200">
{"mode":"expanded"}
</response>

</compare>
```

Unlike `row`, `compare` tells the renderer and accessibility layer that the children are alternatives/states being compared.

## 9. flow

Represents a transformation, state progression, or causal sequence.

Body mode: `children`.

Allowed attributes:

- `layout`: `auto` (default), `horizontal`, `vertical`;
- `title`: optional.

Children: 2 to 6 `step` nodes.

Example:

```text
<flow>

<step label="Input">
`q=a+b`
</step>

<step label="Decode">
`q = "a b"`
</step>

<step label="Result">
The decoded value is displayed.
</step>

</flow>
```

`step` is not valid as a top-level page component.

Each step body uses Markdown.

The theme may switch `auto` between horizontal and vertical based on deterministic fit rules.

## 10. media

Represents local visual media with semantic metadata.

Body mode: `markdown` for optional caption.

Allowed attributes:

- `src`: required local path;
- `alt`: required;
- `fit`: `contain` (default) or `cover`;
- `title`: optional.

Example:

```text
<media src="../assets/dashboard.png" alt="Project dashboard" fit="contain">
The dashboard after switching to compact mode.
</media>
```

Rules:

- remote URLs are not fetched;
- missing local assets fail lint;
- alt text is required;
- source files do not specify pixel height.

## 11. Markdown table instead of specialized domain components

Use a normal Markdown table for structured records such as accounts, roles, matrix results, parser outputs, environment comparisons, or metadata.

Example:

```markdown
| Account | Role | Access |
| --- | --- | --- |
| John | Administrator | All projects |
| Bob | Member | One project |
```

Do not create a `roles` component for this.

## 12. Generic fenced code

Use fenced code blocks for code, SQL, shell snippets, HTML, configuration, logs, or terminal output when no stronger semantic PageDoc component is needed.

Example:

````markdown
```sql
SELECT id, name FROM projects;
```
````

## 13. Component registry contract

Each component descriptor should define:

- name;
- body mode;
- allowed attributes;
- required attributes;
- attribute enums/validators;
- allowed parents;
- allowed child types;
- min/max child count;
- semantic CSS class;
- renderer binding;
- deterministic layout hints where applicable.

The registry is the canonical component contract. Parser, validator, renderer, and documentation must not maintain divergent copies of these rules.
