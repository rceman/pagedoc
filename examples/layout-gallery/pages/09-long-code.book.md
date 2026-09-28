---
id: gallery-long-code
group: Layout Gallery
title: Lockfile Transcript
---

A package manager lockfile records the resolved dependency graph. The
excerpt below shows the entries produced for a minimal install.

<request title="Resolved dependencies">
== lockfile excerpt ==
requests==2.32.3
  # via toolbench
charset-normalizer==3.3.2
  # via requests
idna==3.10
  # via requests
urllib3==2.2.2
  # via requests
certifi==2024.7.4
  # via requests
packaging==24.1
  # via toolbench
typing-extensions==4.12.2
  # via toolbench
</request>

Pins are exact. The comment after each entry names the first package in
the graph that required it.
