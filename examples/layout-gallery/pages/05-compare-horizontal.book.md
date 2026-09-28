---
id: gallery-compare-horizontal
group: Layout Gallery
title: Encoding Round Trip
---

<compare labels="Input|Output" layout="horizontal">

<request title="Encode">
POST /v1/encode HTTP/1.1
Content-Type: application/json

{"text": "caf\u00e9", "to": "utf-8"}
</request>

<response title="Result" status="200">
HTTP/1.1 200 OK

{"bytes": "636166c3a9", "encoding": "utf-8"}
</response>

</compare>

Both sides of a comparison stay visually linked; labels make the
expected/actual relation explicit rather than relying on position alone.
