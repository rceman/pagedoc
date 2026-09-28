---
id: gallery-request-response
group: Layout Gallery
title: Project Tasks API
---

The tasks endpoint returns a task record by id.

<row>

<request title="Fetch task">
GET /v1/tasks/8421 HTTP/1.1
Host: api.projects.example
Accept: application/json
</request>

<response title="Task record" status="200">
HTTP/1.1 200 OK
Content-Type: application/json

{"id": "8421", "title": "Draft handbook",
 "state": "open", "assignee": "team-docs"}
</response>

</row>

<note>
Responses are always JSON; errors use the shared error envelope.
</note>
