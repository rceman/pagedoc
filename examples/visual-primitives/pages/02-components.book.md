---
id: vp-components
group: Conformance
kind: content
title: Component Primitives
---

Component boundaries, separators, and cues rendered by the fixed-page
theme.

<browser>
https://docs.example.test/guide/getting-started
</browser>

<row split="equal">

<request title="Boundary">
GET /v1/status HTTP/1.1
Host: docs.example.test
</request>

<response title="Boundary">
HTTP/1.1 200 OK
Content-Type: application/json
</response>

</row>

<compare layout="horizontal" labels="Expected|Observed">

<result>
Aligned
</result>

<result>
Aligned
</result>

</compare>

<flow layout="horizontal" title="Connector">

<step label="A">
Parse
</step>

<step label="B">
Render
</step>

<step label="C">
Emit
</step>

</flow>

<row split="wide-left">

<compare layout="vertical" labels="Outer|Inner">

<result>
Alpha
</result>

<result>
Beta
</result>

</compare>

<note>
A compare nested inside a row exercises nested layout primitives.
</note>

</row>

<note tone="warning" title="Limit">
The warning cue pairs a geometric disc with a text label.
</note>

<result>
Done.
</result>
