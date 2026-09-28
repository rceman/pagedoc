"""Document/page HTML assembly.

Rendering consumes only a validated AST plus a loaded theme. Output is a
single deterministic HTML document: no timestamps, no random IDs, no
network references.
"""

from __future__ import annotations

from ..ast import ComponentNode, PageChild, PageNode
from ..document import Document
from ..registry import ComponentSpec, get_registry
from ..theme.loader import Theme
from .components import render_component
from .markdown import _ind, esc, esc_attr, render_blocks


def _render_child(child: PageChild, registry: dict[str, ComponentSpec]) -> str:
    if isinstance(child, ComponentNode):
        return render_component(child, registry[child.name], registry)
    return render_blocks([child])


def render_page(page: PageNode, registry: dict[str, ComponentSpec]) -> str:
    page_id = page.page_id
    group = str(page.metadata.get("group", ""))
    title = str(page.metadata.get("title", ""))
    lines = [
        f'<section class="pd-page pd-page--kind-{esc_attr(page.kind)}"'
        f' id="pd-page-{esc_attr(page_id)}" data-pd-page-id="{esc_attr(page_id)}">',
        _ind('<header class="pd-page-header">'),
        _ind(f'<p class="pd-page-group">{esc(group)}</p>', 2),
        _ind(f'<h1 class="pd-page-title">{esc(title)}</h1>', 2),
        _ind("</header>"),
        _ind('<div class="pd-page-content">'),
    ]
    for child in page.children:
        lines.append(_ind(_render_child(child, registry), 2))
    lines.append(_ind("</div>"))
    lines.append("</section>")
    return "\n".join(lines)


def render_document(
    document: Document, theme: Theme, registry: dict[str, ComponentSpec] | None = None
) -> str:
    reg = registry if registry is not None else get_registry()
    css = "\n".join(
        ln for ln in (theme.css.strip("\n").split("\n"))
    )
    parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        '<meta name="generator" content="pagedoc">',
        f"<title>{esc(document.title)}</title>",
        "<style>",
        css,
        "</style>",
        "</head>",
        "<body>",
        f'<main class="pd-document" data-pd-document="{esc_attr(document.doc_id)}"'
        f' data-pd-theme="{esc_attr(theme.id)}">',
    ]
    for page in document.pages:
        parts.append(_ind(render_page(page, reg)))
    parts.append("</main>")
    parts.append("</body>")
    parts.append("</html>")
    return "\n".join(parts) + "\n"
