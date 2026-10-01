"""Deterministic inspection schema for built documents.

The inspection payload is produced once from the authoritative build
result — the same measured layout that PDF serialization emits. It is
JSON-serializable, timestamp-free, and machine-path-free beyond the
authored manifest/page paths the caller supplied.

Schema version 1.
"""

from __future__ import annotations

import json
from typing import Any

from .document import Document
from .pipeline import BuildResult
from .theme.model import Theme

INSPECTION_SCHEMA_VERSION = 1


def build_inspection(
    document: Document, build: BuildResult, theme: Theme
) -> dict[str, Any]:
    """Construct the deterministic inspection dictionary."""

    expected_blocks = {
        i: len(page.children) for i, page in enumerate(document.pages)
    }
    pages: list[dict[str, Any]] = []
    for pl in build.layout.pages:
        resolved: dict[str, str] = {}
        for key, value in sorted(build.resolved.items()):
            node_id, what = key.rsplit(":", 1)
            ref = build.node_map.get(node_id)
            if ref is not None and ref.page_index == pl.index:
                resolved[node_id] = value
        expected = expected_blocks.get(pl.index, 0)
        missing = max(0, expected - pl.block_count)
        pages.append(
            {
                "index": pl.index,
                "page_id": pl.page_id,
                "fit": bool(pl.fits and missing == 0),
                "blocks": pl.block_count,
                "blocks_rendered": pl.block_count,
                "blocks_expected": expected,
                "blocks_missing": missing,
                "content_used_px": (
                    round(pl.content_used, 1)
                    if pl.content_used is not None
                    else None
                ),
                "content_available_px": (
                    round(pl.content_available, 1)
                    if pl.content_available is not None
                    else None
                ),
                "overflow_px": round(pl.overflow_px, 1),
                "width_overflow_px": round(pl.width_overflow_px, 1),
                "overflow_node": pl.overflow_node_id,
                "overflow_axis": pl.overflow_axis,
                "last_block": pl.last_block_id,
                "resolved": resolved,
            }
        )
    return {
        "schema_version": INSPECTION_SCHEMA_VERSION,
        "document": document.doc_id,
        "manifest": document.manifest_path,
        "theme": theme.id,
        "typography_portable": theme.typography_portable,
        "pages_logical": len(document.pages),
        "pages_physical": build.layout.physical_page_count,
        "all_fit": build.fits,
        "composition": build.composition.to_dict(),
        "diagnostics": [
            {"path": d.path, "line": d.line, "col": d.col, "message": d.message}
            for d in build.diagnostics
        ],
        "pages": pages,
    }


class InspectionReport:
    """Immutable, deterministic inspection of a compiled document."""

    __slots__ = ("_payload",)

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = dict(payload)

    # ---- scalar accessors -------------------------------------------------
    @property
    def schema_version(self) -> int:
        return self._payload["schema_version"]

    @property
    def document_id(self) -> str:
        return self._payload["document"]

    @property
    def manifest_path(self) -> str:
        return self._payload["manifest"]

    @property
    def theme_id(self) -> str:
        return self._payload["theme"]

    @property
    def pages_logical(self) -> int:
        return self._payload["pages_logical"]

    @property
    def pages_physical(self) -> int:
        return self._payload["pages_physical"]

    @property
    def all_fit(self) -> bool:
        return self._payload["all_fit"]

    @property
    def diagnostics(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._payload["diagnostics"])

    # ---- serialization ----------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        """A defensive copy of the deterministic payload."""
        return json.loads(self.to_json())

    def to_json(self) -> str:
        return json.dumps(self._payload, indent=2, sort_keys=True) + "\n"
