---
id: gallery-tables
group: Layout Gallery
title: Inventory Reference Data
---

The inventory service exposes normalized reference tables. The columns
below use the public field names.

## Order states

| State | Meaning | Terminal |
| ----- | ------- | -------- |
| draft | Created, not yet submitted | no |
| submitted | Awaiting fulfilment | no |
| packed | Ready for shipment | no |
| shipped | Handed to carrier | no |
| delivered | Confirmed delivered | yes |
| cancelled | Cancelled by requester | yes |

## Stock adjustment reasons

| Code | Description | Requires approval |
| ---- | ----------- | ----------------- |
| COUNT | Cycle-count correction | no |
| DAMAGE | Item damaged in warehouse | yes |
| RETURN | Customer return restock | yes |
| WRITE_OFF | Permanent removal | yes |

Tables are the canonical surface for small structured reference data.
