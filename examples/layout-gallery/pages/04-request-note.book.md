---
id: gallery-request-note
group: Layout Gallery
title: Weather API Query
---

A forecast lookup is a plain GET with query parameters.

<row>

<request title="Forecast lookup">
GET /v1/forecast?lat=56.95&lon=24.10&days=3 HTTP/1.1
Host: api.weather.example
</request>

<note tone="warning" title="Rate limit">
The forecast endpoint allows 60 requests per minute per key. Cache
responses for at least 10 minutes; data updates hourly.
</note>

</row>

Coordinates use decimal degrees. The `days` parameter accepts 1-14.
