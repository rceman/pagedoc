"""MarkdownNode subtree -> deterministic, escaped HTML.

Every authored text fragment is escaped; links/images get escaped
attributes. Remote markdown images are never embedded (they would fetch
at view time); they render as labelled text instead.
"""

from __future__ import annotations

import html
import re

from ..ast import MarkdownNode

_REMOTE_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def esc(text: object) -> str:
    return html.escape(str(text), quote=False)


def esc_attr(text: object) -> str:
    return html.escape(str(text), quote=True)


def _ind(fragment: str, levels: int = 1) -> str:
    """Indent an HTML fragment without touching ``<pre>`` interiors.

    Whitespace inside ``<pre>`` is rendered literally, so lines between a
    ``<pre`` open and its ``</pre>`` close are emitted verbatim. Authored
    raw/code text must never be re-indented.
    """

    prefix = "  " * levels
    out: list[str] = []
    in_pre = False
    for ln in fragment.split("\n"):
        if in_pre:
            out.append(ln)
        else:
            out.append(prefix + ln if ln else ln)
        if "<pre" in ln and "</pre>" not in ln:
            in_pre = True
        elif "</pre>" in ln:
            in_pre = False
    return "\n".join(out)


def render_inline(nodes: list[MarkdownNode]) -> str:
    return "".join(_inline(n) for n in nodes)


def _inline(node: MarkdownNode) -> str:
    t = node.type
    if t == "text":
        return esc(node.text or "")
    if t == "code_inline":
        return f"<code>{esc(node.text or '')}</code>"
    if t == "emphasis":
        return f"<em>{render_inline(node.children)}</em>"
    if t == "strong":
        return f"<strong>{render_inline(node.children)}</strong>"
    if t == "link":
        attrs = f'href="{esc_attr(node.attrs.get("href", ""))}"'
        if node.attrs.get("title"):
            attrs += f' title="{esc_attr(node.attrs["title"])}"'
        return f"<a {attrs}>{render_inline(node.children)}</a>"
    if t == "image":
        src = str(node.attrs.get("src", ""))
        alt = str(node.attrs.get("alt", ""))
        if _REMOTE_RE.match(src) or src.startswith("//"):
            return f'<span class="pd-md-image-remote">{esc(alt or src)}</span>'
        attrs = f'src="{esc_attr(src)}" alt="{esc_attr(alt)}"'
        if node.attrs.get("title"):
            attrs += f' title="{esc_attr(node.attrs["title"])}"'
        return f"<img {attrs}>"
    if t == "softbreak":
        return "\n"
    if t == "hardbreak":
        return "<br>\n"
    return esc(node.text or "")


def render_blocks(nodes: list[MarkdownNode], ctx=None) -> str:
    return "\n".join(_block(n, ctx) for n in nodes)


def _nid(node: MarkdownNode, ctx) -> str:
    """Emit a ``data-pd-node`` attribute when a render context is live."""

    if ctx is None or not ctx.annotate:
        return ""
    return f' data-pd-node="{ctx.node_id(node, "markdown")}"'


def _block(node: MarkdownNode, ctx=None) -> str:
    t = node.type
    nid = _nid(node, ctx)
    if t == "paragraph":
        return f"<p{nid}>{render_inline(node.children)}</p>"
    if t == "heading":
        level = int(node.attrs.get("level", 1))
        return f"<h{level}{nid}>{render_inline(node.children)}</h{level}>"
    if t == "code_block":
        lang = node.attrs.get("lang")
        attr = f' data-lang="{esc_attr(lang)}"' if lang else ""
        return f'<pre class="pd-code"{attr}{nid}><code>{esc(node.text or "")}</code></pre>'
    if t == "block_quote":
        return f"<blockquote{nid}>\n{_ind(render_blocks(node.children, ctx))}\n</blockquote>"
    if t in ("bullet_list", "ordered_list"):
        tag = "ul" if t == "bullet_list" else "ol"
        items = "\n".join(
            f"<li>\n{_ind(render_blocks(c.children, ctx))}\n</li>" for c in node.children
        )
        start = node.attrs.get("start")
        start_attr = f' start="{int(start)}"' if t == "ordered_list" and isinstance(start, int) and start != 1 else ""
        return f"<{tag}{start_attr}{nid}>\n{items}\n</{tag}>"
    if t == "table":
        return _table(node, ctx)
    if t == "thematic_break":
        return f"<hr{nid}>"
    return f"<p{nid}>{esc(node.text or '')}</p>"


def _table(node: MarkdownNode, ctx=None) -> str:
    head_rows = [r for r in node.children if r.attrs.get("header")]
    body_rows = [r for r in node.children if not r.attrs.get("header")]
    parts: list[str] = [f"<table{_nid(node, ctx)}>"]
    if head_rows:
        parts.append("<thead>")
        parts.extend(_row(r) for r in head_rows)
        parts.append("</thead>")
    if body_rows:
        parts.append("<tbody>")
        parts.extend(_row(r) for r in body_rows)
        parts.append("</tbody>")
    parts.append("</table>")
    return "\n".join(parts)


def _row(row: MarkdownNode) -> str:
    cells = []
    for cell in row.children:
        tag = "th" if cell.attrs.get("header") else "td"
        align = cell.attrs.get("align")
        attr = f' class="pd-ta-{esc_attr(align)}"' if align else ""
        cells.append(f"<{tag}{attr}>{render_inline(cell.children)}</{tag}>")
    return "<tr>" + "".join(cells) + "</tr>"
