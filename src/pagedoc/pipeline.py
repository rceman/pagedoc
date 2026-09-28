"""Build orchestration: validated document -> HTML -> backend layout ->
diagnostics.

The authoritative layout path (ARCHITECTURE.md section 9): generated
HTML/CSS is rendered ONCE by the backend; the returned
``RenderedDocument`` is both what diagnostics measure and what PDF
serialization emits. There is no second layout pass to produce output.

``auto`` orientations for ``compare``/``flow`` resolve by real fit: the
first pass renders them horizontal; if a page then overflows, every still
-horizontal ``auto`` node on an overflowing page flips to vertical and the
document is re-rendered once. A page that still overflows fails. This is
a deliberately bounded, deterministic fallback — per-component candidate
evaluation is M3 scope.
"""

from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass, field

from .backends.base import DocumentLayout, RenderedDocument
from .document import Document
from .errors import Diagnostic
from .registry import ComponentSpec, get_registry
from .render.context import NodeRef, RenderResult
from .render.html import render_document
from .theme.model import Theme


@dataclass
class BuildResult:
    html: str
    node_map: dict[str, NodeRef]
    resolved: dict[str, str]
    layout: DocumentLayout
    # The measured backend document — serialize THIS for PDF output.
    rendered: RenderedDocument | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)

    @property
    def fits(self) -> bool:
        return not self.diagnostics


def _base_url(manifest_dir: str) -> str:
    return pathlib.Path(os.path.abspath(manifest_dir)).as_uri() + "/"


def _auto_flippable(build: RenderResult, layout: DocumentLayout) -> dict[str, str]:
    """auto compare/flow nodes still rendered horizontal on failing pages."""

    failing_indexes = {p.index for p in layout.pages if not p.fits}
    flips: dict[str, str] = {}
    for key, value in build.resolved.items():
        node_id, what = key.rsplit(":", 1)
        if what != "layout" or value != "horizontal":
            continue
        ref = build.node_map.get(node_id)
        if ref is None or ref.page_index not in failing_indexes:
            continue
        node = ref.node
        if getattr(node, "name", None) in ("compare", "flow") and node.attrs.get("layout") == "auto":
            flips[f"{node_id}:layout"] = "vertical"
    return flips


def build_document(
    document: Document,
    theme: Theme,
    registry: dict[str, ComponentSpec] | None = None,
) -> BuildResult:
    """Render HTML, measure with the backend, resolve auto layouts,
    produce diagnostics.

    Exactly one backend layout pass normally; at most two when ``auto``
    compare/flow orientation needs the bounded vertical fallback.
    """

    from .backends import weasyprint  # lazy: keeps lint/ast CLI fast

    reg = registry if registry is not None else get_registry()
    base_url = _base_url(document.manifest_dir)

    render = render_document(document, theme, reg)
    rendered = weasyprint.render(render.html, base_url)

    flips = _auto_flippable(render, rendered.layout)
    if flips:
        render = render_document(document, theme, reg, resolutions=flips)
        rendered = weasyprint.render(render.html, base_url)

    diagnostics = _layout_diagnostics(document, rendered.layout, render.node_map)
    return BuildResult(
        html=render.html,
        node_map=render.node_map,
        resolved=render.resolved,
        layout=rendered.layout,
        rendered=rendered,
        diagnostics=diagnostics,
    )


def _layout_diagnostics(
    document: Document, layout: DocumentLayout, node_map: dict[str, NodeRef]
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    expected = len(document.pages)
    if layout.physical_page_count != expected:
        diagnostics.append(
            Diagnostic(
                document.manifest_path,
                1,
                1,
                f"document produced {layout.physical_page_count} physical pages "
                f"for {expected} authored pages; each .book.md page must fit one physical page",
            )
        )
    for pl in layout.pages:
        page_node = document.pages[pl.index] if pl.index < expected else None
        page_id = pl.page_id or (page_node.page_id if page_node else f"page-{pl.index}")
        src_path = page_node.source.path if page_node else document.manifest_path
        if pl.overflow_px > 0 or pl.width_overflow_px > 0:
            # Attribute to the deepest authored node whose rendered bounds
            # actually cross the region boundary.
            ref = node_map.get(pl.overflow_node_id or pl.last_block_id or "")
            line = ref.node.source.start_line if ref else 1
            col = ref.node.source.start_col if ref else 1
            desc = _block_desc(ref)
            if pl.overflow_axis == "horizontal" or (
                pl.overflow_axis is None and pl.width_overflow_px > 0
            ):
                amount = pl.width_overflow_px
                axis = "content region width"
            else:
                amount = pl.overflow_px
                axis = "content region"
            diagnostics.append(
                Diagnostic(
                    src_path,
                    line,
                    col,
                    f"page '{page_id}' exceeds {axis} by {amount:.0f}px; "
                    f"overflowing block: {desc} starting at line {line}",
                )
            )
    return diagnostics


def _block_desc(ref: NodeRef | None) -> str:
    if ref is None:
        return "unknown block"
    node = ref.node
    name = getattr(node, "name", None) or getattr(node, "type", "block")
    if getattr(node, "name", None):
        return f"<{name}>"
    return f"markdown {name}"
