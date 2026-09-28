"""Component renderers bound to the registry via ``spec.renderer``.

Each renderer emits deterministic, semantic, fully-escaped HTML using the
stable ``pd-*`` classes from THEME_SPEC.md. Raw bodies are emitted as
escaped text: authored markup can never become executable markup.

When a ``RenderCtx`` is supplied, every component element carries a
``data-pd-node`` id so backend layout diagnostics can point back to the
authored source span.
"""

from __future__ import annotations

from urllib.parse import SplitResult, urlsplit

from ..ast import ComponentNode
from ..registry import ComponentSpec
from .context import RenderCtx
from .markdown import _ind, esc, esc_attr, render_blocks


def render_component(
    node: ComponentNode,
    spec: ComponentSpec,
    registry: dict[str, ComponentSpec],
    ctx: RenderCtx | None = None,
) -> str:
    return _RENDERERS[spec.renderer](node, spec, registry, ctx)


def _nid(node: ComponentNode, ctx: RenderCtx | None) -> str:
    if ctx is None or not ctx.annotate:
        return ""
    return f' data-pd-node="{ctx.node_id(node, "component")}"'


def _render_children(
    nodes: list[ComponentNode], registry: dict[str, ComponentSpec], ctx
) -> str:
    return "\n".join(render_component(c, registry[c.name], registry, ctx) for c in nodes)


def _render_request(node, spec, registry, ctx) -> str:
    lines = [
        f'<figure class="pd-request" data-pd-lang="{esc_attr(node.attrs.get("lang", "http"))}"'
        f"{_nid(node, ctx)}>"
    ]
    title = node.attrs.get("title")
    if title:
        lines.append(_ind(f'<figcaption class="pd-request-title">{esc(title)}</figcaption>'))
    body = f'<pre class="pd-request-body"><code>{esc(node.raw or "")}</code></pre>'
    lines.append(_ind(body))
    lines.append("</figure>")
    return "\n".join(lines)


def _render_response(node, spec, registry, ctx) -> str:
    lines = [
        f'<figure class="pd-response" data-pd-lang="{esc_attr(node.attrs.get("lang", "auto"))}"'
        f"{_nid(node, ctx)}>"
    ]
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


def _render_browser(node, spec, registry, ctx) -> str:
    raw = node.raw or ""
    url = next((ln.strip() for ln in raw.split("\n") if ln.strip()), "")
    lines = [f'<div class="pd-browser"{_nid(node, ctx)}>']
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

    Fidelity contract: authored URL text is never silently rewritten —
    userinfo (including passwords) is displayed verbatim (HTML-escaped).
    Malformed input degrades to a single escaped raw span; this function
    must never raise on malformed input.
    """

    try:
        parts = urlsplit(url)
    except ValueError:
        # Malformed authorities (e.g. unclosed IPv6 bracket) — raw fallback.
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
        # Parse the authority ourselves so invalid ports/IPv6 cannot raise
        # (SplitResult.port/.hostname may raise ValueError). Authored
        # text is shown verbatim, escaped.
        netloc = parts.netloc
        userinfo = ""
        hostport = netloc
        if "@" in netloc:
            userinfo, hostport = netloc.rsplit("@", 1)
        if userinfo:
            body.append(f'<span class="pd-url-userinfo">{esc(userinfo)}@</span>')
        if hostport.startswith("[") and "]" in hostport:
            host, _, rest = hostport.partition("]")
            body.append(f'<span class="pd-url-host">{esc(host + "]")}</span>')
            if rest:
                body.append(f'<span class="pd-url-port">{esc(rest)}</span>')
        elif ":" in hostport:
            host, _, port = hostport.rpartition(":")
            body.append(f'<span class="pd-url-host">{esc(host)}</span>')
            body.append(f'<span class="pd-url-port">:{esc(port)}</span>')
        else:
            body.append(f'<span class="pd-url-host">{esc(hostport)}</span>')
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


def _render_note(node, spec, registry, ctx) -> str:
    tone = node.attrs.get("tone", "note")
    lines = [f'<aside class="pd-note pd-note--tone-{esc_attr(tone)}"{_nid(node, ctx)}>']
    if tone == "warning":
        lines.append(
            _ind('<p class="pd-note-cue"><span class="pd-note-cue-dot"></span>Warning</p>')
        )
    title = node.attrs.get("title")
    if title:
        lines.append(_ind(f'<p class="pd-note-title">{esc(title)}</p>'))
    if node.body:
        lines.append(_ind(render_blocks(node.body, ctx)))
    lines.append("</aside>")
    return "\n".join(lines)


def _render_result(node, spec, registry, ctx) -> str:
    lines = [f'<div class="pd-result"{_nid(node, ctx)}>']
    title = node.attrs.get("title")
    if title:
        lines.append(_ind(f'<p class="pd-result-title">{esc(title)}</p>'))
    if node.body:
        lines.append(_ind(render_blocks(node.body, ctx)))
    lines.append("</div>")
    return "\n".join(lines)


def _resolve_row_split(node: ComponentNode, spec: ComponentSpec, ctx) -> tuple[str, str]:
    """Return (authored, resolved) split for a row.

    ``auto`` resolves via registry ``auto_split_rules`` keyed on the
    ordered child component types, falling back to ``auto_split``.
    """

    authored = str(node.attrs.get("split", "auto"))
    if authored != "auto":
        return authored, authored
    rules = spec.layout_hints.get("auto_split_rules", {})
    pair = tuple(c.name for c in (node.children or []))
    resolved = rules.get(pair, spec.layout_hints.get("auto_split", "equal"))
    return authored, resolved


def _render_row(node, spec, registry, ctx) -> str:
    authored_split, resolved_split = _resolve_row_split(node, spec, ctx)
    align = str(node.attrs.get("align", "start"))
    node_id = ""
    if ctx is not None:
        node_id = ctx.node_id(node, "component")
        ctx.record_resolved(node_id, "split", resolved_split)
    lines = [
        f'<div class="pd-row pd-row--split-{esc_attr(resolved_split)} pd-row--align-{esc_attr(align)}"'
        f' data-pd-split="{esc_attr(authored_split)}" data-pd-align="{esc_attr(align)}"'
        + (f' data-pd-node="{node_id}"' if node_id else "")
        + ">"
    ]
    for child in node.children or []:
        inner = render_component(child, registry[child.name], registry, ctx)
        lines.append(_ind(f'<div class="pd-row-cell">\n{_ind(inner)}\n</div>'))
    lines.append("</div>")
    return "\n".join(lines)


def _resolved_layout(node: ComponentNode, spec: ComponentSpec, ctx) -> tuple[str, str]:
    """(authored, resolved) orientation for compare/flow.

    ``auto`` prefers the registry ``auto_layout`` hint (horizontal); a
    prior backend pass may have recorded a vertical override in
    ``ctx.resolutions``.
    """

    authored = str(node.attrs.get("layout", "auto"))
    if authored != "auto":
        return authored, authored
    resolved = spec.layout_hints.get("auto_layout", "horizontal")
    return authored, resolved


def _render_compare(node, spec, registry, ctx) -> str:
    authored_layout, resolved = _resolved_layout(node, spec, ctx)
    node_id = ""
    if ctx is not None:
        node_id = ctx.node_id(node, "component")
        resolved = ctx.override(node_id, "layout") or resolved
        ctx.record_resolved(node_id, "layout", resolved)
    labels = node.attrs.get("labels")
    label_parts = [p.strip() for p in str(labels).split("|")] if labels else []
    lines = [
        f'<div class="pd-compare pd-compare--layout-{esc_attr(resolved)}"'
        f' data-pd-layout="{esc_attr(authored_layout)}"'
        + (f' data-pd-node="{node_id}"' if node_id else "")
        + ">",
        _ind('<div class="pd-compare-sides">'),
    ]
    for idx, child in enumerate(node.children or []):
        side = ['<div class="pd-compare-side">']
        if idx < len(label_parts):
            side.append(_ind(f'<p class="pd-compare-label">{esc(label_parts[idx])}</p>'))
        inner = render_component(child, registry[child.name], registry, ctx)
        side.append(_ind(inner))
        side.append("</div>")
        lines.append(_ind("\n".join(side), 2))
    lines.append(_ind("</div>"))
    lines.append("</div>")
    return "\n".join(lines)


def _render_flow(node, spec, registry, ctx) -> str:
    authored_layout, resolved = _resolved_layout(node, spec, ctx)
    node_id = ""
    if ctx is not None:
        node_id = ctx.node_id(node, "component")
        resolved = ctx.override(node_id, "layout") or resolved
        ctx.record_resolved(node_id, "layout", resolved)
    lines = [
        f'<div class="pd-flow pd-flow--layout-{esc_attr(resolved)}"'
        f' data-pd-layout="{esc_attr(authored_layout)}"'
        + (f' data-pd-node="{node_id}"' if node_id else "")
        + ">"
    ]
    title = node.attrs.get("title")
    if title:
        lines.append(_ind(f'<p class="pd-flow-title">{esc(title)}</p>'))
    lines.append(_ind('<ol class="pd-flow-steps">'))
    for child in node.children or []:
        inner = render_component(child, registry[child.name], registry, ctx)
        lines.append(_ind(inner, 2))
    lines.append(_ind("</ol>"))
    lines.append("</div>")
    return "\n".join(lines)


def _render_step(node, spec, registry, ctx) -> str:
    lines = [f'<li class="pd-step"{_nid(node, ctx)}>']
    lines.append(_ind(f'<p class="pd-step-label">{esc(node.attrs.get("label", ""))}</p>'))
    if node.body:
        lines.append(_ind(render_blocks(node.body, ctx)))
    lines.append("</li>")
    return "\n".join(lines)


def _render_media(node, spec, registry, ctx) -> str:
    fit = str(node.attrs.get("fit", "contain"))
    src = str(node.attrs.get("src", ""))
    alt = str(node.attrs.get("alt", ""))
    if ctx is not None:
        src = ctx.media_url(src)
    lines = [f'<figure class="pd-media pd-media--fit-{esc_attr(fit)}"{_nid(node, ctx)}>']
    lines.append(_ind(f'<img class="pd-media-img" src="{esc_attr(src)}" alt="{esc_attr(alt)}">'))
    title = node.attrs.get("title")
    caption = render_blocks(node.body, ctx) if node.body else ""
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
