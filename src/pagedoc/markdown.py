"""Markdown parsing into a normalized, deterministic MarkdownNode subtree.

Uses markdown-it-py with a CommonMark baseline plus the table extension.
Raw HTML is disabled so authored HTML-like text stays literal text.

The emitted node vocabulary is documented in docs/AST_FORMAT.md.
"""

from __future__ import annotations

from markdown_it import MarkdownIt
from markdown_it.token import Token

from .ast import MarkdownNode, SourceSpan

_md = MarkdownIt("commonmark", {"html": False}).enable("table")


def parse_markdown(text: str, path: str, line_offset: int) -> list[MarkdownNode]:
    """Parse a Markdown region into block nodes.

    ``line_offset`` is the number of source lines preceding ``text`` so
    emitted spans point at real ``*.book.md`` lines (1-based output).
    """

    lines = text.split("\n")
    tokens = _md.parse(text)
    ctx = _Ctx(path=path, line_offset=line_offset, lines=lines)
    nodes, pos = _block_seq(tokens, 0, len(tokens), ctx, None)
    return nodes


class _Ctx:
    def __init__(self, path: str, line_offset: int, lines: list[str]) -> None:
        self.path = path
        self.line_offset = line_offset
        self.lines = lines

    def span(self, token: Token, fallback: SourceSpan | None) -> SourceSpan:
        if token.map:
            start, end = token.map
            start_line = self.line_offset + start + 1
            end_line = self.line_offset + end
            end_col = len(self.lines[end - 1]) + 1 if 0 < end <= len(self.lines) else 1
            return SourceSpan(self.path, start_line, 1, end_line, end_col)
        if fallback is not None:
            return fallback
        return SourceSpan(self.path, self.line_offset + 1, 1, self.line_offset + 1, 1)


def _block_seq(
    tokens: list[Token],
    start: int,
    end: int,
    ctx: _Ctx,
    fallback: SourceSpan | None,
) -> tuple[list[MarkdownNode], int]:
    """Parse a flat token slice into sibling block nodes."""

    nodes: list[MarkdownNode] = []
    i = start
    while i < end:
        tok = tokens[i]
        t = tok.type
        if t in ("paragraph_open", "blockquote_open", "list_item_open"):
            close = {"paragraph_open": "paragraph_close",
                     "blockquote_open": "blockquote_close",
                     "list_item_open": "list_item_close"}[t]
            j = _find_close(tokens, i, end, close)
            inner = tokens[i + 1 : j]
            if t == "paragraph_open":
                children = _inline_children(inner, ctx, ctx.span(tok, fallback))
                nodes.append(MarkdownNode("paragraph", ctx.span(tok, fallback), children=children))
            else:
                children, _ = _block_seq(inner, 0, len(inner), ctx, ctx.span(tok, fallback))
                node_type = "block_quote" if t == "blockquote_open" else "list_item"
                nodes.append(MarkdownNode(node_type, ctx.span(tok, fallback), children=children))
            i = j + 1
        elif t == "heading_open":
            j = _find_close(tokens, i, end, "heading_close")
            span = ctx.span(tok, fallback)
            children = _inline_children(tokens[i + 1 : j], ctx, span)
            level = int(tok.tag[1])
            nodes.append(MarkdownNode("heading", span, children=children, attrs={"level": level}))
            i = j + 1
        elif t in ("bullet_list_open", "ordered_list_open"):
            close = "bullet_list_close" if t == "bullet_list_open" else "ordered_list_close"
            j = _find_close(tokens, i, end, close)
            span = ctx.span(tok, fallback)
            children, _ = _block_seq(tokens[i + 1 : j], 0, j - i - 1, ctx, span)
            node_type = "bullet_list" if t == "bullet_list_open" else "ordered_list"
            attrs = {"ordered": node_type == "ordered_list"}
            if node_type == "ordered_list":
                start_attr = tok.attrGet("start")
                if start_attr is not None:
                    attrs["start"] = int(start_attr)
            nodes.append(MarkdownNode(node_type, span, children=children, attrs=attrs))
            i = j + 1
        elif t in ("fence", "code_block"):
            span = ctx.span(tok, fallback)
            attrs: dict[str, object] = {}
            info = tok.info.strip() if tok.info else ""
            if info:
                attrs["lang"] = info
            text = tok.content[:-1] if tok.content.endswith("\n") else tok.content
            nodes.append(MarkdownNode("code_block", span, attrs=attrs, text=text))
            i += 1
        elif t == "hr":
            nodes.append(MarkdownNode("thematic_break", ctx.span(tok, fallback)))
            i += 1
        elif t == "table_open":
            j = _find_close(tokens, i, end, "table_close")
            span = ctx.span(tok, fallback)
            children = _table_rows(tokens[i + 1 : j], ctx, span)
            nodes.append(MarkdownNode("table", span, children=children))
            i = j + 1
        elif t == "inline":
            children = _inline_children([tok], ctx, ctx.span(tok, fallback))
            nodes.append(MarkdownNode("paragraph", ctx.span(tok, fallback), children=children))
            i += 1
        else:
            i += 1
    return nodes, i


def _find_close(tokens: list[Token], i: int, end: int, close_type: str) -> int:
    depth = 0
    j = i
    while j < end:
        if tokens[j].nesting == 1:
            depth += 1
        elif tokens[j].nesting == -1:
            depth -= 1
            if depth == 0 and tokens[j].type == close_type:
                return j
        j += 1
    raise ValueError(f"unbalanced token stream: no {close_type}")


def _table_rows(tokens: list[Token], ctx: _Ctx, fallback: SourceSpan) -> list[MarkdownNode]:
    """Convert thead/tbody token content into table_row/table_cell nodes."""

    rows: list[MarkdownNode] = []
    in_head = False
    i = 0
    end = len(tokens)
    while i < end:
        tok = tokens[i]
        if tok.type == "thead_open":
            in_head = True
            i += 1
        elif tok.type == "thead_close":
            in_head = False
            i += 1
        elif tok.type == "tr_open":
            j = _find_close(tokens, i, end, "tr_close")
            span = ctx.span(tok, fallback)
            cells: list[MarkdownNode] = []
            k = i + 1
            while k < j:
                ctok = tokens[k]
                if ctok.type in ("th_open", "td_open"):
                    cj = _find_close(tokens, k, end, "th_close" if ctok.type == "th_open" else "td_close")
                    cspan = ctx.span(ctok, span)
                    cell_children = _inline_children(tokens[k + 1 : cj], ctx, cspan)
                    attrs: dict[str, object] = {"header": ctok.type == "th_open"}
                    style = ctok.attrGet("style") or ""
                    if "text-align:" in style:
                        attrs["align"] = style.split("text-align:", 1)[1].strip().rstrip(";")
                    cells.append(MarkdownNode("table_cell", cspan, children=cell_children, attrs=attrs))
                    k = cj + 1
                else:
                    k += 1
            rows.append(MarkdownNode("table_row", span, children=cells, attrs={"header": in_head}))
            i = j + 1
        else:
            i += 1
    return rows


def _inline_children(
    tokens: list[Token], ctx: _Ctx, fallback: SourceSpan
) -> list[MarkdownNode]:
    """Expand inline tokens into inline MarkdownNodes."""

    nodes: list[MarkdownNode] = []
    for tok in tokens:
        if tok.type == "inline" and tok.children:
            nodes.extend(_inline_seq(tok.children, ctx, fallback))
    return nodes


def _inline_seq(tokens: list[Token], ctx: _Ctx, fallback: SourceSpan) -> list[MarkdownNode]:
    nodes: list[MarkdownNode] = []
    i = 0
    end = len(tokens)
    while i < end:
        tok = tokens[i]
        span = ctx.span(tok, fallback)
        t = tok.type
        if t == "text":
            nodes.append(MarkdownNode("text", span, text=tok.content))
        elif t == "code_inline":
            nodes.append(MarkdownNode("code_inline", span, text=tok.content))
        elif t in ("em_open", "strong_open", "link_open"):
            close = {"em_open": "em_close", "strong_open": "strong_close", "link_open": "link_close"}[t]
            j = _find_close(tokens, i, end, close)
            children = _inline_seq(tokens[i + 1 : j], ctx, span)
            if t == "em_open":
                nodes.append(MarkdownNode("emphasis", span, children=children))
            elif t == "strong_open":
                nodes.append(MarkdownNode("strong", span, children=children))
            else:
                attrs = {"href": tok.attrGet("href") or ""}
                title = tok.attrGet("title")
                if title:
                    attrs["title"] = title
                nodes.append(MarkdownNode("link", span, children=children, attrs=attrs))
            i = j
        elif t == "image":
            alt = "".join(c.content for c in (tok.children or []) if c.type == "text")
            attrs = {"src": tok.attrGet("src") or "", "alt": alt}
            title = tok.attrGet("title")
            if title:
                attrs["title"] = title
            nodes.append(MarkdownNode("image", span, attrs=attrs))
        elif t == "softbreak":
            nodes.append(MarkdownNode("softbreak", span))
        elif t == "hardbreak":
            nodes.append(MarkdownNode("hardbreak", span))
        else:
            if tok.content:
                nodes.append(MarkdownNode("text", span, text=tok.content))
        i += 1
    return nodes
