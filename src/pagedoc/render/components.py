"""Component renderers bound to the registry via ``spec.renderer``.

Each renderer emits deterministic, semantic, fully-escaped HTML using the
stable ``pd-*`` classes from THEME_SPEC.md. Raw bodies are emitted as
escaped text: authored markup can never become executable markup.
"""

from __future__ import annotations

from urllib.parse import SplitResult, urlsplit

from ..ast import ComponentNode
from ..registry import ComponentSpec
from .markdown import _ind, esc, esc_attr, render_blocks


def render_component(
    node: ComponentNode, spec: ComponentSpec, registry: dict[str, ComponentSpec]
) -> str:
    return _RENDERERS[spec.renderer](node, spec, registry)


def _render_children(nodes: list[ComponentNode], registry: dict[str, ComponentSpec]) -> str:
    return "\n".join(render_component(c, registry[c.name], registry) for c in nodes)


def _render_request(node: ComponentNode, spec: ComponentSpec, registry) -> str:
    lines = [f'<figure class="pd-request" data-pd-lang="{esc_attr(node.attrs.get("lang", "http"))}">']
    title = node.attrs.get("title")
    if title:
        lines.append(_ind(f'<figcaption class="pd-request-title">{esc(title)}</figcaption>'))
    body = f'<pre class="pd-request-body"><code>{esc(node.raw or "")}</code></pre>'
    lines.append(_ind(body))
    lines.append("</figure>")
    return "\n".join(lines)


def _render_response(node: ComponentNode, spec: ComponentSpec, registry) -> str:
    lines = [f'<figure class="pd-response" data-pd-lang="{esc_attr(node.attrs.get("lang", "auto"))}">']
    title = node.attrs.get("title")
    status = node.attrs.get("status")
    if title or status:
        cap_parts = [esc(title)] if title else []
        if status:
            cap_parts.append(f'<span class="pd-response-status">{esc(status)}</span>')
        lines.append(_ind(f'<figcaption class="pd-response-title">{" ".join(cap_parts)}</figcaption>'))
    body = f'<pre class="pd-response-body"><code>{esc(node.raw or "")}</code></pre>'
    lines.append(_ind(body))
    lines.append("</figure>")
    return "\n".join(lines)


def _render_browser(node: ComponentNode, spec: ComponentSpec, registry) -> str:
    raw = node.raw or ""
    url = next((ln.strip() for ln in raw.split("\n") if ln.strip()), "")
    lines = ['<div class="pd-browser">']
    title = node.attrs.get("title")
    if title:
        lines.append(_ind(f'<div class="pd-browser-title">{esc(title)}</div>'))
    lines.append(_ind('<div class="pd-browser-bar">'))
    bar = _browser_url_html(url)
    status = node.attrs.get("status")
    if status:
        bar += f'\n<span class="pd-browser-status">{esc(status)}</span>'
    lines.append(_ind(bar, 2))
    lines.append(_ind("</div>"))
    lines.append("</div>")
    return "\n".join(lines)


def _browser_url_html(url: str) -> str:
    """Render one authored URL as structured, escaped segments.

    Malformed or relative URLs degrade to a single escaped text span;
    rendering must not fail after validation succeeded.
    """

    try:
        parts = urlsplit(url)
    except ValueError:
        parts = SplitResult("", "", url, "", "")
    segments: list[str] = []
    if parts.scheme and parts.netloc:
        cls = "pd-browser-secure" if parts.scheme == "https" else "pd-browser-insecure"
        label = "Secure" if parts.scheme == "https" else "Not secure"
        segments.append(
            f'<span class="{cls}" role="img" aria-label="{label} connection">{label}</span>'
        )
    body: list[str] = []
    if parts.scheme:
        body.append(f'<span class="pd-url-scheme">{esc(parts.scheme)}</span>')
    if parts.netloc:
        body.append('<span class="pd-url-delim">://</span>')
        if parts.username:
            userinfo = parts.username + ("@" if parts.username else "")
            if parts.password:
                userinfo = parts.username + ":***@"
            body.append(f'<span class="pd-url-userinfo">{esc(userinfo)}</span>')
        host = parts.hostname or ""
        body.append(f'<span class="pd-url-host">{esc(host)}</span>')
        if parts.port is not None:
            body.append(f'<span class="pd-url-port">:{parts.port}</span>')
    if parts.path:
        body.append(f'<span class="pd-url-path">{esc(parts.path)}</span>')
    if parts.query:
        body.append(f'<span class="pd-url-query">?{esc(parts.query)}</span>')
    if parts.fragment:
        body.append(f'<span class="pd-url-fragment">#{esc(parts.fragment)}</span>')
    if not body:
        body.append(f'<span class="pd-url-raw">{esc(url)}</span>')
    segments.append('<span class="pd-browser-url">' + "".join(body) + "</span>")
    return "\n".join(segments)


def _render_note(node: ComponentNode, spec: ComponentSpec, registry) -> str:
    tone = node.attrs.get("tone", "note")
    lines = [f'<aside class="pd-note pd-note--tone-{esc_attr(tone)}">']
    title = node.attrs.get("title")
    if title:
        lines.append(_ind(f'<p class="pd-note-title">{esc(title)}</p>'))
    if node.body:
        lines.append(_ind(render_blocks(node.body)))
    lines.append("</aside>")
    return "\n".join(lines)


def _render_result(node: ComponentNode, spec: ComponentSpec, registry) -> str:
    lines = ['<div class="pd-result">']
    title = node.attrs.get("title")
    if title:
        lines.append(_ind(f'<p class="pd-result-title">{esc(title)}</p>'))
    if node.body:
        lines.append(_ind(render_blocks(node.body)))
    lines.append("</div>")
    return "\n".join(lines)


def _render_row(node: ComponentNode, spec: ComponentSpec, registry) -> str:
    authored_split = str(node.attrs.get("split", "auto"))
    resolved_split = (
        spec.layout_hints.get("auto_split", "equal") if authored_split == "auto" else authored_split
    )
    align = str(node.attrs.get("align", "start"))
    lines = [
        f'<div class="pd-row pd-row--split-{esc_attr(resolved_split)} pd-row--align-{esc_attr(align)}"'
        f' data-pd-split="{esc_attr(authored_split)}" data-pd-align="{esc_attr(align)}">'
    ]
    for child in node.children or []:
        inner = render_component(child, registry[child.name], registry)
        lines.append(_ind(f'<div class="pd-row-cell">\n{_ind(inner)}\n</div>'))
    lines.append("</div>")
    return "\n".join(lines)


def _render_compare(node: ComponentNode, spec: ComponentSpec, registry) -> str:
    authored_layout = str(node.attrs.get("layout", "auto"))
    resolved = (
        spec.layout_hints.get("auto_layout", "horizontal")
        if authored_layout == "auto"
        else authored_layout
    )
    labels = node.attrs.get("labels")
    label_parts = [p.strip() for p in str(labels).split("|")] if labels else []
    lines = [
        f'<div class="pd-compare pd-compare--layout-{esc_attr(resolved)}"'
        f' data-pd-layout="{esc_attr(authored_layout)}">',
        _ind('<div class="pd-compare-sides">'),
    ]
    for idx, child in enumerate(node.children or []):
        side = ['<div class="pd-compare-side">']
        if idx < len(label_parts):
            side.append(_ind(f'<p class="pd-compare-label">{esc(label_parts[idx])}</p>'))
        inner = render_component(child, registry[child.name], registry)
        side.append(_ind(inner))
        side.append("</div>")
        lines.append(_ind("\n".join(side), 2))
    lines.append(_ind("</div>"))
    lines.append("</div>")
    return "\n".join(lines)


def _render_flow(node: ComponentNode, spec: ComponentSpec, registry) -> str:
    authored_layout = str(node.attrs.get("layout", "auto"))
    resolved = (
        spec.layout_hints.get("auto_layout", "horizontal")
        if authored_layout == "auto"
        else authored_layout
    )
    lines = [
        f'<div class="pd-flow pd-flow--layout-{esc_attr(resolved)}"'
        f' data-pd-layout="{esc_attr(authored_layout)}">'
    ]
    title = node.attrs.get("title")
    if title:
        lines.append(_ind(f'<p class="pd-flow-title">{esc(title)}</p>'))
    lines.append(_ind('<ol class="pd-flow-steps">'))
    for child in node.children or []:
        inner = render_component(child, registry[child.name], registry)
        lines.append(_ind(inner, 2))
    lines.append(_ind("</ol>"))
    lines.append("</div>")
    return "\n".join(lines)


def _render_step(node: ComponentNode, spec: ComponentSpec, registry) -> str:
    lines = ['<li class="pd-step">']
    lines.append(_ind(f'<p class="pd-step-label">{esc(node.attrs.get("label", ""))}</p>'))
    if node.body:
        lines.append(_ind(render_blocks(node.body)))
    lines.append("</li>")
    return "\n".join(lines)


def _render_media(node: ComponentNode, spec: ComponentSpec, registry) -> str:
    fit = str(node.attrs.get("fit", "contain"))
    src = str(node.attrs.get("src", ""))
    alt = str(node.attrs.get("alt", ""))
    lines = [f'<figure class="pd-media pd-media--fit-{esc_attr(fit)}">']
    lines.append(_ind(f'<img class="pd-media-img" src="{esc_attr(src)}" alt="{esc_attr(alt)}">'))
    title = node.attrs.get("title")
    caption = render_blocks(node.body) if node.body else ""
    if title or caption:
        inner = ""
        if title:
            inner += f'<span class="pd-media-title">{esc(title)}</span>'
        if caption:
            inner += ("\n" if inner else "") + caption
        lines.append(_ind(f'<figcaption class="pd-media-caption">\n{_ind(inner)}\n</figcaption>'))
    lines.append("</figure>")
    return "\n".join(lines)


_RENDERERS = {
    "request": _render_request,
    "response": _render_response,
    "browser": _render_browser,
    "note": _render_note,
    "result": _render_result,
    "row": _render_row,
    "compare": _render_compare,
    "flow": _render_flow,
    "step": _render_step,
    "media": _render_media,
}
