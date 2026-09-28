---
id: gallery-media
group: Layout Gallery
title: Component Overview Diagram
---

The diagram shows the four runtime parts of the application: the API
front door, the job queue, the worker pool, and the object store.

<media src="../assets/architecture-overview.png" alt="Diagram of the four application components" title="Runtime layout" fit="contain">

Requests enter through the API front door, jobs are queued, workers
consume the queue, and artifacts land in the object store.

</media>

Keeping the diagram next to its caption makes the page self-contained;
readers do not have to cross-reference an appendix.
