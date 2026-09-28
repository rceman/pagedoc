"""Backend-neutral layout result types.

A backend renders generated HTML + theme CSS and reports where rendered
boxes landed, so the engine can enforce the fixed-page contract without
reimplementing text measurement in Python.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class PlacedBox:
    """One rendered element carrying a ``data-pd-node`` id."""

    node_id: str
    x: float
    y: float
    width: float
    height: float

    @property
    def bottom(self) -> float:
        return self.y + self.height

    @property
    def right(self) -> float:
        return self.x + self.width


@dataclass
class PageLayout:
    """Layout facts for one physical page of the rendered document."""

    index: int
    page_node_id: str | None = None
    page_id: str = ""
    # Content-region metrics in px (None when the region is missing).
    content_available: float | None = None
    content_used: float | None = None
    overflow_px: float = 0.0
    width_overflow_px: float = 0.0
    # Deepest authored node (by DOM depth) whose rendered bounds cross a
    # region boundary — the most specific actionable offender.
    overflow_node_id: str | None = None
    overflow_axis: str | None = None  # "vertical" | "horizontal"
    last_block_id: str | None = None
    block_count: int = 0
    blocks: list[PlacedBox] = field(default_factory=list)

    @property
    def fits(self) -> bool:
        return self.overflow_px <= 0 and self.width_overflow_px <= 0


@dataclass
class DocumentLayout:
    """Whole-document layout facts."""

    physical_page_count: int
    pages: list[PageLayout] = field(default_factory=list)

    @property
    def all_fit(self) -> bool:
        return all(p.fits for p in self.pages)


class RenderedDocument(Protocol):
    """Backend-neutral contract for a fully-laid-out document.

    The measured document IS the emitted document: diagnostics inspect
    ``layout`` and PDF serialization writes the same rendered document —
    there is never a second layout pass for output.
    """

    @property
    def layout(self) -> DocumentLayout: ...

    def write_pdf(self, out_path: str) -> None: ...

    def pdf_bytes(self) -> bytes: ...
