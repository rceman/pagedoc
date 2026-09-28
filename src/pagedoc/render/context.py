"""Render context shared by page, component and markdown renderers.

Carries the registry/theme, deterministic node-id allocation, the
``data-pd-node`` -> AST mapping used by layout diagnostics, media path
resolution, and any `auto` layout overrides already decided by a prior
backend pass.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Union

from ..ast import ComponentNode, MarkdownNode, PageNode
from ..registry import ComponentSpec, get_registry
from ..theme.model import Theme


@dataclass
class NodeRef:
    """Mapping from a generated ``data-pd-node`` id back to the AST."""

    node_id: str
    page_index: int
    page_id: str
    kind: str  # "page" | "component" | "markdown"
    node: Union[PageNode, ComponentNode, MarkdownNode]
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class RenderResult:
    html: str
    node_map: dict[str, NodeRef]
    resolved: dict[str, str]  # node_id -> resolved presentation value


class RenderCtx:
    def __init__(
        self,
        registry: dict[str, ComponentSpec] | None = None,
        theme: Theme | None = None,
        base_dir: str = ".",
        resolutions: dict[str, str] | None = None,
        annotate: bool = True,
    ) -> None:
        self.registry = registry if registry is not None else get_registry()
        self.theme = theme
        self.base_dir = base_dir
        self.resolutions = resolutions or {}
        self.annotate = annotate
        self.node_map: dict[str, NodeRef] = {}
        self.resolved: dict[str, str] = {}
        self.page_index = 0
        self.page_id = ""
        self.page_source_dir = "."
        self._seq = 0

    def begin_page(self, page: PageNode, index: int) -> str:
        self.page_index = index
        self.page_id = page.page_id
        self.page_source_dir = os.path.dirname(page.source.path) or "."
        self._seq = 0
        node_id = f"p{index}"
        self.node_map[node_id] = NodeRef(node_id, index, page.page_id, "page", page)
        return node_id

    def node_id(self, node: ComponentNode | MarkdownNode, kind: str) -> str:
        if not self.annotate:
            return ""
        self._seq += 1
        nid = f"p{self.page_index}n{self._seq}"
        self.node_map[nid] = NodeRef(nid, self.page_index, self.page_id, kind, node)
        return nid

    def record_resolved(self, node_id: str, key: str, value: str) -> None:
        if not node_id:
            return
        self.resolved[f"{node_id}:{key}"] = value
        ref = self.node_map.get(node_id)
        if ref is not None:
            ref.extra[key] = value

    def override(self, node_id: str, key: str) -> str | None:
        return self.resolutions.get(f"{node_id}:{key}")

    def media_url(self, src: str) -> str:
        """Rewrite a page-relative media path relative to the document
        base dir (which is the WeasyPrint base_url)."""

        resolved = os.path.normpath(os.path.join(self.page_source_dir, src))
        rel = os.path.relpath(resolved, self.base_dir)
        return rel.replace(os.sep, "/")
