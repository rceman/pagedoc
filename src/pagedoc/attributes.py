"""v1 tag and attribute grammar parser.

PageDoc tags are HTML-like but are not XML. An opening tag is recognized
only when it is the sole non-whitespace content of its source line
(AUTHORING_SPEC.md section 4 and the task contract). Attributes use the
``name="value"`` grammar with ``\\"`` and ``\\\\`` escapes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .errors import Diagnostic, PageDocError

_NAME_RE = re.compile(r"[a-z][a-z0-9-]*")
_WS = " \t"


@dataclass(frozen=True)
class OpenTag:
    name: str
    attrs: dict[str, str]
    start_col: int  # 1-based column of '<'
    end_col: int  # 1-based column just past '>'


@dataclass(frozen=True)
class CloseTag:
    name: str
    start_col: int
    end_col: int


def open_tag_candidate(line: str) -> bool:
    """True when the line's first non-whitespace text starts like ``<name``."""

    i = _skip_ws(line, 0)
    return i + 1 < len(line) and line[i] == "<" and line[i + 1].islower()


def close_tag_candidate(line: str) -> bool:
    """True when the line's first non-whitespace text starts like ``</name``."""

    i = _skip_ws(line, 0)
    return (
        i + 2 < len(line)
        and line[i] == "<"
        and line[i + 1] == "/"
        and line[i + 2].islower()
    )


def close_tag_name(line: str) -> str | None:
    """Leniently extract the name from a ``</name``-shaped line.

    Returns the tag name without validating the rest of the line, or
    ``None`` if the line is not closing-tag-shaped.
    """

    i = _skip_ws(line, 0)
    if not (
        i + 2 < len(line) and line[i] == "<" and line[i + 1] == "/" and line[i + 2].islower()
    ):
        return None
    m = _NAME_RE.match(line, i + 2)
    return m.group(0) if m else None


def _skip_ws(line: str, i: int) -> int:
    while i < len(line) and line[i] in _WS:
        i += 1
    return i


def _err(path: str, lineno: int, col: int, message: str) -> PageDocError:
    return PageDocError(Diagnostic(path, lineno, col, message))


def parse_open_tag(line: str, lineno: int, path: str) -> OpenTag:
    """Parse a standalone opening tag line strictly.

    Precondition: ``open_tag_candidate(line)`` is True. Raises
    ``PageDocError`` with a precise column on any malformed input.
    """

    i = _skip_ws(line, 0)
    start_col = i + 1
    i += 1  # consume '<'

    m = _NAME_RE.match(line, i)
    if m is None:
        raise _err(path, lineno, i + 1, "expected component name after '<'")
    name = m.group(0)
    i = m.end()

    attrs: dict[str, str] = {}
    while True:
        j = _skip_ws(line, i)
        if j < len(line) and line[j] == ">":
            rest = line[j + 1 :]
            if rest.strip():
                raise _err(
                    path,
                    lineno,
                    j + 2,
                    f"opening tag <{name}> must be the only content on its line",
                )
            return OpenTag(name=name, attrs=attrs, start_col=start_col, end_col=j + 2)
        if j >= len(line):
            raise _err(path, lineno, len(line) + 1, f"unclosed opening tag <{name}>; expected '>'")
        if j == i:
            raise _err(
                path,
                lineno,
                j + 1,
                f"expected whitespace or '>' after <{name}",
            )
        i = j
        # attribute name
        m = _NAME_RE.match(line, i)
        if m is None or m.group(0) != line[i : m.end()]:
            raise _err(path, lineno, i + 1, f"malformed attribute on <{name}>; expected name=\"value\"")
        attr_name = m.group(0)
        i = m.end()
        if i >= len(line) or line[i] != "=":
            raise _err(
                path,
                lineno,
                i + 1,
                f"malformed attribute '{attr_name}' on <{name}>; expected name=\"value\"",
            )
        i += 1
        if i >= len(line) or line[i] != '"':
            raise _err(
                path,
                lineno,
                i + 1,
                f"attribute '{attr_name}' on <{name}> requires a double-quoted value",
            )
        i += 1
        value_chars: list[str] = []
        while True:
            if i >= len(line):
                raise _err(
                    path,
                    lineno,
                    len(line) + 1,
                    f"unterminated value for attribute '{attr_name}' on <{name}>",
                )
            ch = line[i]
            if ch == '"':
                i += 1
                break
            if ch == "\\":
                if i + 1 >= len(line):
                    raise _err(
                        path,
                        lineno,
                        i + 1,
                        f"unterminated escape in attribute '{attr_name}' on <{name}>",
                    )
                nxt = line[i + 1]
                if nxt not in ('"', "\\"):
                    raise _err(
                        path,
                        lineno,
                        i + 1,
                        f"invalid escape '\\{nxt}' in attribute '{attr_name}' on <{name}>",
                    )
                value_chars.append(nxt)
                i += 2
                continue
            value_chars.append(ch)
            i += 1
        if attr_name in attrs:
            raise _err(
                path,
                lineno,
                i + 1,
                f"duplicate attribute '{attr_name}' on <{name}>",
            )
        attrs[attr_name] = "".join(value_chars)


def parse_close_tag(line: str, lineno: int, path: str) -> CloseTag:
    """Parse a standalone closing tag line strictly.

    Precondition: ``close_tag_candidate(line)`` is True.
    """

    i = _skip_ws(line, 0)
    start_col = i + 1
    i += 2  # consume '</'

    m = _NAME_RE.match(line, i)
    if m is None:
        raise _err(path, lineno, i + 1, "expected component name after '</'")
    name = m.group(0)
    i = m.end()
    i = _skip_ws(line, i)
    if i >= len(line) or line[i] != ">":
        raise _err(path, lineno, i + 1, f"malformed closing tag </{name}>; expected '</{name}>' alone on its line")
    rest = line[i + 1 :]
    if rest.strip():
        raise _err(
            path,
            lineno,
            i + 2,
            f"closing tag </{name}> must be the only content on its line",
        )
    return CloseTag(name=name, start_col=start_col, end_col=i + 2)
