---
id: gallery-flow
group: Layout Gallery
title: Image Metadata Pipeline
---

<flow layout="horizontal" title="Metadata extraction">

<step label="Read">
Open the source image and read the EXIF and XMP blocks.
</step>

<step label="Normalize">
Map raw fields to the normalized schema; drop unknown keys.
</step>

<step label="Validate">
Check required fields and reject malformed dates.
</step>

<step label="Store">
Write the normalized record to the metadata index.
</step>

</flow>

Each step runs to completion before the next starts; a failed step stops
the pipeline and reports the stage name.
