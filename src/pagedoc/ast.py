"""Typed semantic AST model and deterministic JSON serialization.

Node families (ARCHITECTURE.md section 5):

- ``PageNode``: one logical fixed-size page (one ``*.book.md`` file).
- ``MarkdownNode``: normalized CommonMark + tables subtree.
- ``ComponentNode``: a PageDoc component. Its body is stored in exactly one
  of ``raw`` (raw mode), ``body`` (markdown mode) or ``children``
  (children mode) depending on the registry descriptor.
- ``SourceSpan``: provenance for every node.

JSON serialization emits ``schema_version: 1`` and preserves a ``source``
object on every node, per AUTHORING_SPEC.md section 12.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Union

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SourceSpan:
    """Source provenance of a node inside an authored file."""

    path: str
    start_line: int
    start_col: int
    end_line: int
    end_col: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "start_line": self.start_line,
            "start_col": self.start_col,
            "end_line": self.end_line,
            "end_col": self.end_col,
        }


@dataclass
class MarkdownNode:
    """Normalized Markdown AST node.

    ``type`` is one of: paragraph, heading, block_quote, bullet_list,
    ordered_list, list_item, code_block, table, table_row, table_cell,
    thematic_break, text, emphasis, strong, code_inline, link, image,
    softbreak, hardbreak.
    """

    type: str
    source: SourceSpan
    children: list["MarkdownNode"] = field(default_factory=list)
    attrs: dict[str, Any] = field(default_factory=dict)
    text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.type}
        if self.attrs:
            out["attrs"] = {k: self.attrs[k] for k in sorted(self.attrs)}
        if self.children:
            out["children"] = [c.to_dict() for c in self.children]
        if self.text is not None:
            out["text"] = self.text
        out["source"] = self.source.to_dict()
        return out


@dataclass
class ComponentNode:
    """A PageDoc custom block component.

    Body storage is exclusive by body mode:

    - raw: ``raw`` is a ``str``
    - markdown: ``body`` is a ``list[MarkdownNode]``
    - children: ``children`` is a ``list[ComponentNode]``
    """

    name: str
    source: SourceSpan
    attrs: dict[str, Any] = field(default_factory=dict)
    raw: str | None = None
    body: list[MarkdownNode] | None = None
    children: list["ComponentNode"] | None = None

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"type": self.name}
        out["attrs"] = {k: self.attrs[k] for k in sorted(self.attrs)}
        if self.raw is not None:
            out["raw"] = self.raw
        if self.body is not None:
            out["body"] = [c.to_dict() for c in self.body]
        if self.children is not None:
            out["children"] = [c.to_dict() for c in self.children]
        out["source"] = self.source.to_dict()
        return out


PageChild = Union[MarkdownNode, ComponentNode]


@dataclass
class PageNode:
    """One logical page parsed from a ``*.book.md`` file."""

    metadata: dict[str, Any]
    source: SourceSpan
    children: list[PageChild] = field(default_factory=list)
    kind: str = "content"
    template: str | None = None

    @property
    def page_id(self) -> str:
        return str(self.metadata.get("id", ""))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "type": "page",
            "metadata": {k: self.metadata[k] for k in sorted(self.metadata)},
            "children": [c.to_dict() for c in self.children],
            "source": self.source.to_dict(),
        }


def dumps_page(page: PageNode) -> str:
    """Serialize a page AST to deterministic JSON bytes-compatible text."""

    return json.dumps(page.to_dict(), indent=2, ensure_ascii=False) + "\n"
