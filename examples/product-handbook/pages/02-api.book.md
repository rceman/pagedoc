---
id: project-api
group: Product Guide
title: Inspect the Project API
---

The project page loads its data from an HTTP endpoint.

<row>

<request title="Project list">
GET /api/v1/projects/user/john
Accept: application/json
</request>

<response status="200">
{
  "projects": [
    "alpha",
    "beta"
  ]
}
</response>

</row>

<compare labels="Compact|Expanded">

<response status="200">
{"mode":"compact","items":2}
</response>

<response status="200">
{"mode":"expanded","items":2}
</response>

</compare>

<flow>

<step label="Page">
The project dashboard opens.
</step>

<step label="Request">
`GET /api/v1/projects/user/john`
</step>

<step label="Result">
The project list is rendered.
</step>

</flow>

<result>
The page, API request, and rendered list now form one visible sequence.
</result>
