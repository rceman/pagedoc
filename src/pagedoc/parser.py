"""Page parser: YAML front matter + Markdown + PageDoc custom blocks.

Recognition rules (AUTHORING_SPEC.md section 4):

- An opening tag is structural only when it is the sole non-whitespace
  content on its line and its name is registered.
- A closing tag is structural only when it is the sole non-whitespace
  content on its line.
- Tag-shaped lines with unregistered names fail as unknown components.
- Raw bodies never scan for opening tags; only a registered standalone
  closing tag ends (or mismatches) a raw body.
"""

from __future__ import annotations

from typing import Any

import yaml

from .ast import ComponentNode, MarkdownNode, PageChild, PageNode, SourceSpan
from .attributes import (
    close_tag_candidate,
    close_tag_name,
    open_tag_candidate,
    parse_close_tag,
    parse_open_tag,
)
from .errors import Diagnostic, PageDocError
from .markdown import parse_markdown
from .registry import BodyMode, ComponentSpec, get_registry

REQUIRED_FRONT_MATTER = ("id", "group", "title")


def parse_page_file(fs_path: str, registry: dict[str, ComponentSpec] | None = None) -> PageNode:
    """Parse a ``*.book.md`` file. ``fs_path`` is used for reads and spans."""

    with open(fs_path, "r", encoding="utf-8-sig") as f:
        text = f.read()
    return parse_page_text(text, fs_path, registry)


def parse_page_text(
    text: str, path: str, registry: dict[str, ComponentSpec] | None = None
) -> PageNode:
    reg = registry if registry is not None else get_registry()
    text = text.replace("\r\n", "\n").replace("\r", "\n")  # LF is canonical
    lines = text.split("\n")
    metadata, kind, template, body_start = _parse_front_matter(lines, path)
    children, _ = _parse_block_lines(lines, body_start, len(lines), path, reg)
    end_line = max(len(lines), 1)
    source = SourceSpan(path, 1, 1, end_line, len(lines[-1]) + 1 if lines else 1)
    return PageNode(metadata=metadata, source=source, children=children, kind=kind, template=template)


def _parse_front_matter(
    lines: list[str], path: str
) -> tuple[dict[str, Any], str, str | None, int]:
    if not lines or lines[0].strip() != "---":
        raise PageDocError(
            Diagnostic(path, 1, 1, "missing YAML front matter (file must start with '---')")
        )
    end = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end == -1:
        raise PageDocError(
            Diagnostic(path, 1, 1, "unclosed YAML front matter; expected a closing '---' line")
        )
    raw = "\n".join(lines[1:end])
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        line = (mark.line + 2) if mark is not None else 1
        raise PageDocError(Diagnostic(path, line, 1, f"invalid YAML front matter: {e}")) from e
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise PageDocError(Diagnostic(path, 2, 1, "front matter must be a YAML mapping"))
    for key in REQUIRED_FRONT_MATTER:
        if key not in data or data[key] in (None, ""):
            raise PageDocError(
                Diagnostic(path, 1, 1, f"missing required front matter key: '{key}'")
            )
        if not isinstance(data[key], str):
            raise PageDocError(
                Diagnostic(path, 1, 1, f"front matter key '{key}' must be a string")
            )
    kind = data.get("kind", "content")
    if not isinstance(kind, str):
        raise PageDocError(Diagnostic(path, 1, 1, "front matter key 'kind' must be a string"))
    template = data.get("template")
    if template is not None and not isinstance(template, str):
        raise PageDocError(Diagnostic(path, 1, 1, "front matter key 'template' must be a string"))
    metadata = {k: _json_safe(v) for k, v in data.items()}
    return metadata, kind, template, end + 1


def _json_safe(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    return str(value)


class _Parser:
    """Line-oriented scanner state for one page body."""

    def __init__(self, lines: list[str], path: str, registry: dict[str, ComponentSpec]) -> None:
        self.lines = lines
        self.path = path
        self.registry = registry


def _fence_marker(line: str) -> tuple[str, int, bool] | None:
    """Detect a Markdown fence line: (char, count, has_trailing_text)."""

    stripped = line.lstrip(" ")
    if len(line) - len(stripped) > 3:
        return None
    for ch in ("`", "~"):
        if stripped.startswith(ch * 3):
            run = len(stripped) - len(stripped.lstrip(ch))
            rest = stripped[run:]
            if ch == "`" and "`" in rest:
                return None  # info string on backtick fence may not contain `
            return ch, run, bool(rest.strip())
    return None


def _parse_block_lines(
    lines: list[str], start: int, end: int, path: str, registry: dict[str, ComponentSpec]
) -> tuple[list[PageChild], int]:
    """Parse page-level blocks (Markdown regions and components).

    Tag-shaped lines inside Markdown fenced code blocks are literal code
    content, never component boundaries.
    """

    p = _Parser(lines, path, registry)
    nodes: list[PageChild] = []
    i = start
    md_start: int | None = None
    fence: tuple[str, int] | None = None
    while i < end:
        line = lines[i]
        if fence is not None:
            fm = _fence_marker(line)
            if fm and fm[0] == fence[0] and fm[1] >= fence[1] and not fm[2]:
                fence = None
            i += 1
            continue
        if open_tag_candidate(line):
            if md_start is not None:
                nodes.extend(_flush_markdown(p, md_start, i))
                md_start = None
            node, i = _parse_component(p, i)
            nodes.append(node)
            continue
        if close_tag_candidate(line):
            ct = parse_close_tag(line, i + 1, path)
            if ct.name not in p.registry:
                raise PageDocError(
                    Diagnostic(p.path, i + 1, ct.start_col, f"unknown component '{ct.name}'")
                )
            raise PageDocError(
                Diagnostic(
                    p.path,
                    i + 1,
                    ct.start_col,
                    f"unexpected closing tag </{ct.name}> without a matching opening tag",
                )
            )
        fm = _fence_marker(line)
        if fm is not None:
            fence = (fm[0], fm[1])
        if md_start is None and line.strip():
            md_start = i
        i += 1
    if md_start is not None:
        nodes.extend(_flush_markdown(p, md_start, end))
    return nodes, i


def _flush_markdown(p: _Parser, start: int, end: int) -> list[MarkdownNode]:
    text = "\n".join(p.lines[start:end])
    return parse_markdown(text, p.path, start)


def _parse_component(p: _Parser, i: int) -> tuple[ComponentNode, int]:
    """Parse one component block whose opening tag is on line ``i``."""

    line = p.lines[i]
    lineno = i + 1
    tag = parse_open_tag(line, lineno, p.path)
    spec = p.registry.get(tag.name)
    if spec is None:
        raise PageDocError(
            Diagnostic(p.path, lineno, tag.start_col, f"unknown component '{tag.name}'")
        )
    attrs = spec.resolve_attributes(tag.attrs, p.path, lineno, tag.start_col)
    body_start = i + 1

    if spec.body_mode is BodyMode.RAW:
        raw, close_i = _scan_raw_body(p, spec, body_start, lineno, tag.start_col)
        node = ComponentNode(name=spec.name, attrs=attrs, raw=raw,
                             source=_comp_span(p, tag.start_col, lineno, close_i))
        return node, close_i + 1
    if spec.body_mode is BodyMode.MARKDOWN:
        text, close_i = _scan_markdown_body(p, spec, body_start, lineno, tag.start_col)
        body = parse_markdown(text, p.path, body_start)
        node = ComponentNode(name=spec.name, attrs=attrs, body=body,
                             source=_comp_span(p, tag.start_col, lineno, close_i))
        return node, close_i + 1
    children, close_i = _scan_children_body(p, spec, body_start, lineno, tag.start_col)
    node = ComponentNode(name=spec.name, attrs=attrs, children=children,
                         source=_comp_span(p, tag.start_col, lineno, close_i))
    return node, close_i + 1


def _comp_span(p: _Parser, start_col: int, open_lineno: int, close_i: int) -> SourceSpan:
    close_line = p.lines[close_i]
    ct = parse_close_tag(close_line, close_i + 1, p.path)
    return SourceSpan(p.path, open_lineno, start_col, close_i + 1, ct.end_col)


def _scan_raw_body(
    p: _Parser, spec: ComponentSpec, start: int, open_lineno: int, open_col: int
) -> tuple[str, int]:
    """Collect raw text until the matching standalone closing tag.

    Opening-tag-shaped lines are literal content (per spec, raw bodies
    may contain strings like '<img src=\"/a.png\">'). Only a registered
    standalone closing tag is structural.
    """

    end = len(p.lines)
    j = start
    while j < end:
        line = p.lines[j]
        name = close_tag_name(line)
        if name is not None and name in p.registry:
            # A registered standalone closing tag is always structural.
            ct = parse_close_tag(line, j + 1, p.path)
            if ct.name == spec.name:
                return "\n".join(p.lines[start:j]), j
            raise PageDocError(
                Diagnostic(
                    p.path,
                    j + 1,
                    ct.start_col,
                    f"mismatched closing tag </{ct.name}>; expected </{spec.name}>",
                )
            )
        # Unregistered closing-tag-shaped lines stay literal raw content.
        j += 1
    raise PageDocError(
        Diagnostic(p.path, open_lineno, open_col, f"unclosed component <{spec.name}>; expected </{spec.name}>")
    )


def _scan_markdown_body(
    p: _Parser, spec: ComponentSpec, start: int, open_lineno: int, open_col: int
) -> tuple[str, int]:
    """Collect markdown body text until the matching closing tag.

    Registered opening tags are invalid inside a markdown body (the body
    mode declares Markdown, not components), and a registered closing tag
    for another component is a mismatched close.
    """

    end = len(p.lines)
    j = start
    fence: tuple[str, int] | None = None
    while j < end:
        line = p.lines[j]
        if fence is not None:
            fm = _fence_marker(line)
            if fm and fm[0] == fence[0] and fm[1] >= fence[1] and not fm[2]:
                fence = None
            j += 1
            continue
        fm = _fence_marker(line)
        if fm is not None:
            fence = (fm[0], fm[1])
            j += 1
            continue
        name = close_tag_name(line)
        if name is not None and name in p.registry:
            ct = parse_close_tag(line, j + 1, p.path)
            if ct.name == spec.name:
                return "\n".join(p.lines[start:j]), j
            raise PageDocError(
                Diagnostic(
                    p.path,
                    j + 1,
                    ct.start_col,
                    f"mismatched closing tag </{ct.name}>; expected </{spec.name}>",
                )
            )
        elif open_tag_candidate(line):
            tag = parse_open_tag(line, j + 1, p.path)
            if tag.name in p.registry:
                raise PageDocError(
                    Diagnostic(
                        p.path,
                        j + 1,
                        tag.start_col,
                        f"component <{tag.name}> is not allowed inside <{spec.name}> (markdown body)",
                    )
                )
            raise PageDocError(
                Diagnostic(p.path, j + 1, tag.start_col, f"unknown component '{tag.name}'")
            )
        j += 1
    raise PageDocError(
        Diagnostic(p.path, open_lineno, open_col, f"unclosed component <{spec.name}>; expected </{spec.name}>")
    )


def _scan_children_body(
    p: _Parser, spec: ComponentSpec, start: int, open_lineno: int, open_col: int
) -> tuple[list[ComponentNode], int]:
    """Parse nested component children separated by blank lines."""

    children: list[ComponentNode] = []
    end = len(p.lines)
    j = start
    while j < end:
        line = p.lines[j]
        if not line.strip():
            j += 1
            continue
        name = close_tag_name(line)
        if name is not None:
            if name in p.registry:
                ct = parse_close_tag(line, j + 1, p.path)
                if ct.name == spec.name:
                    return children, j
                raise PageDocError(
                    Diagnostic(
                        p.path,
                        j + 1,
                        ct.start_col,
                        f"mismatched closing tag </{ct.name}>; expected </{spec.name}>",
                    )
                )
            raise PageDocError(
                Diagnostic(p.path, j + 1, _first_non_ws_col(line), f"unknown component '{name}'")
            )
        if open_tag_candidate(line):
            node, j = _parse_component(p, j)
            children.append(node)
            continue
        raise PageDocError(
            Diagnostic(
                p.path,
                j + 1,
                _first_non_ws_col(line),
                f"plain prose is not allowed inside <{spec.name}> (children-only body)",
            )
        )
    raise PageDocError(
        Diagnostic(p.path, open_lineno, open_col, f"unclosed component <{spec.name}>; expected </{spec.name}>")
    )


def _first_non_ws_col(line: str) -> int:
    for idx, ch in enumerate(line):
        if ch not in " \t":
            return idx + 1
    return 1
