"""Document/page HTML assembly for the fixed-page pipeline.

Rendering consumes only a validated AST plus a loaded theme. Output is a
single deterministic HTML document: fixed-size page shells with explicit
named regions, per-node ``data-pd-*`` identifiers for backend
diagnostics, no timestamps, no random IDs, no network references.
"""

from __future__ import annotations

import os

from ..ast import ComponentNode, PageChild, PageNode
from ..document import Document
from ..registry import ComponentSpec, get_registry
from ..theme.loader import load_theme, theme_geometry_css
from ..theme.model import Theme
from .components import render_component
from .context import RenderCtx, RenderResult
from .markdown import _ind, esc, esc_attr, render_blocks


def _render_child(child: PageChild, registry: dict[str, ComponentSpec], ctx) -> str:
    if isinstance(child, ComponentNode):
        return render_component(child, registry[child.name], registry, ctx)
    return render_blocks([child], ctx)


def render_page(
    page: PageNode,
    registry: dict[str, ComponentSpec] | None = None,
    ctx: RenderCtx | None = None,
    page_index: int = 0,
    page_count: int = 1,
) -> str:
    """Render one logical page as a fixed-size shell with named regions.

    Used standalone (defaults) or through ``render_document``.
    """

    if ctx is None:
        theme = load_theme(None, ".")
        ctx = RenderCtx(
            registry=registry,
            theme=theme,
            base_dir=os.path.dirname(page.source.path) or ".",
            annotate=False,
        )
    reg = ctx.registry
    page_id = page.page_id
    group = str(page.metadata.get("group", ""))
    title = str(page.metadata.get("title", ""))
    page_node_id = ctx.begin_page(page, page_index)

    region_names = (
        list(ctx.theme.regions) if ctx.theme is not None else ["header", "content", "footer"]
    )
    lines = [
        f'<section class="pd-page pd-page--kind-{esc_attr(page.kind)}"'
        f' id="pd-page-{esc_attr(page_id)}" data-pd-page="{esc_attr(page_id)}"'
        f' data-pd-node="{page_node_id}">',
    ]
    for name in region_names:
        classes = f"pd-region pd-region-{esc_attr(name)}"
        if name == "header":
            lines.append(_ind(f'<div class="{classes}" data-pd-region="header">'))
            lines.append(_ind(f'<p class="pd-page-group">{esc(group)}</p>', 2))
            lines.append(_ind(f'<h1 class="pd-page-title">{esc(title)}</h1>', 2))
            lines.append(_ind("</div>"))
        elif name == "content":
            lines.append(
                _ind(f'<div class="{classes} pd-page-content" data-pd-region="content">')
            )
            for child in page.children:
                lines.append(_ind(_render_child(child, reg, ctx), 2))
            lines.append(_ind("</div>"))
        elif name == "footer":
            lines.append(_ind(f'<div class="{classes}" data-pd-region="footer">'))
            lines.append(
                _ind(
                    f'<span class="pd-page-doc">{esc(page_id)}</span>'
                    f'<span class="pd-page-number">{page_index + 1} / {page_count}</span>',
                    2,
                )
            )
            lines.append(_ind("</div>"))
        else:
            lines.append(_ind(f'<div class="{classes}" data-pd-region="{esc_attr(name)}">'))
            lines.append(_ind("</div>"))
    lines.append("</section>")
    return "\n".join(lines)


def render_document(
    document: Document,
    theme: Theme,
    registry: dict[str, ComponentSpec] | None = None,
    resolutions: dict[str, str] | None = None,
) -> RenderResult:
    """Render a validated document to deterministic fixed-page HTML."""

    reg = registry if registry is not None else get_registry()
    ctx = RenderCtx(
        registry=reg,
        theme=theme,
        base_dir=document.manifest_dir,
        resolutions=resolutions,
    )
    style_css = "\n".join(
        s for s in (theme_geometry_css(theme, document.manifest_dir), theme.css.strip("\n")) if s
    )
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="generator" content="pagedoc">',
        f"<title>{esc(document.title)}</title>",
        "<style>",
        style_css,
        "</style>",
        "</head>",
        "<body>",
        f'<main class="pd-document" data-pd-document="{esc_attr(document.doc_id)}"'
        f' data-pd-theme="{esc_attr(theme.id)}">',
    ]
    total = len(document.pages)
    for idx, page in enumerate(document.pages):
        parts.append(_ind(render_page(page, reg, ctx, idx, total)))
    parts.append("</main>")
    parts.append("</body>")
    parts.append("</html>")
    html = "\n".join(parts) + "\n"
    return RenderResult(html=html, node_map=ctx.node_map, resolved=ctx.resolved)
