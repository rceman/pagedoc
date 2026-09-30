---
id: cmp-flow-recovery
group: Composition
title: Flow Orientation Recovery
---

<flow>
<step label="Discover">
Publish https://inventory.internal.example/api/v2/stock-adjustments/list/0 and verify.
</step>
<step label="Approve">
Publish https://inventory.internal.example/api/v2/stock-adjustments/approve/1 and verify.
</step>
<step label="Apply">
Publish https://inventory.internal.example/api/v2/stock-adjustments/delta/2 and verify.
</step>
<step label="Audit">
Publish https://inventory.internal.example/api/v2/stock-adjustments/audit/3 and verify.
</step>
</flow>
