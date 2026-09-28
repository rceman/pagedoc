---
id: gallery-mixed
group: Layout Gallery
title: URL Parsing Reference
---

A URL decomposes into scheme, authority, path, query, and fragment.

<browser>
https://user@apps.example.test:8443/projects/12?tab=tasks#list
</browser>

## Parts

| Part | Value |
| ---- | ----- |
| scheme | `https` |
| host | `apps.example.test` |
| port | `8443` |
| path | `/projects/12` |
| query | `tab=tasks` |
| fragment | `list` |

<row>

<result title="Valid">
The URL above parses cleanly; all five parts are present and the port is
inside the valid range.
</result>

<note title="Note">
Userinfo is allowed but discouraged in shared URLs; credentials must
never appear in documentation output.
</note>

</row>
