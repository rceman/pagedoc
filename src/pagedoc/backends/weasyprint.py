"""WeasyPrint adapter — the sole authoritative fixed-page layout backend.

The central M2 invariant: **what PageDoc measures is exactly what PageDoc
emits.** ``render()`` performs ONE ``HTML.render()`` layout pass and
returns a ``RenderedDocument`` wrapping the resulting WeasyPrint
``Document``. Diagnostics read ``rendered.layout`` (computed from that
same Document's box tree) and ``write_pdf``/``pdf_bytes`` serialize that
same Document — the PDF is never produced by re-laying out the HTML.

Public API used:

- ``weasyprint.HTML(string=..., base_url=...).render()`` -> Document
- ``Document.pages`` -> physical page list
- ``Document.write_pdf(...)`` -> PDF bytes / file

Private API used (isolated here per ARCHITECTURE.md section 12):

- ``Page._page_box``: the rendered box tree root. WeasyPrint exposes no
  public layout-box API; box positions/sizes are required to measure
  content-region usage and attribute overflow to authored nodes. Box
  attributes consumed: ``element.attrib`` (our ``data-pd-*`` markers),
  ``element_tag``, ``position_x``/``position_y``, ``width``, ``height``,
  ``children``. Verified against weasyprint 66.x; the dependency is
  pinned in pyproject.toml.

Determinism: ``SOURCE_DATE_EPOCH`` is set to a fixed value around PDF
serialization because fontTools embeds a timestamp in embedded font
``head`` tables otherwise. This makes PDF output byte-identical for
identical inputs.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from weasyprint import HTML

from .base import DocumentLayout, PageLayout, PlacedBox

# Fixed epoch (2023-11-14) — only used to neutralize embedded timestamps.
_SOURCE_DATE_EPOCH = "1700000000"

# Sub-pixel slack below which a crossing is considered rendering noise,
# not a real overflow.
_EPSILON = 0.1


@contextmanager
def _fixed_epoch() -> Iterator[None]:
    previous = os.environ.get("SOURCE_DATE_EPOCH")
    os.environ["SOURCE_DATE_EPOCH"] = _SOURCE_DATE_EPOCH
    try:
        yield
    finally:
        if previous is None:
            os.environ.pop("SOURCE_DATE_EPOCH", None)
        else:
            os.environ["SOURCE_DATE_EPOCH"] = previous


class RenderedDocument:
    """A measured WeasyPrint Document ready for serialization.

    ``layout`` is computed once at construction from the box tree of
    ``document``; ``write_pdf``/``pdf_bytes`` serialize the same object.
    """

    def __init__(self, document) -> None:
        self._document = document  # weasyprint.document.Document
        self.layout = _measure(document)

    @property
    def physical_page_count(self) -> int:
        return len(self._document.pages)

    def write_pdf(self, out_path: str) -> None:
        with _fixed_epoch():
            self._document.write_pdf(out_path)

    def pdf_bytes(self) -> bytes:
        with _fixed_epoch():
            return self._document.write_pdf()


def render(html_text: str, base_url: str) -> RenderedDocument:
    """Perform the authoritative layout pass and return the measured
    document. Serialization reuses the same Document."""

    return RenderedDocument(HTML(string=html_text, base_url=base_url).render())


def layout_document(html_text: str, base_url: str) -> DocumentLayout:
    """Compatibility helper: render + measure, discarding the document."""

    return render(html_text, base_url).layout


def write_pdf(html_text: str, base_url: str, out_path: str) -> None:
    render(html_text, base_url).write_pdf(out_path)


def pdf_bytes(html_text: str, base_url: str) -> bytes:
    return render(html_text, base_url).pdf_bytes()


# ---------------------------------------------------------------------
# private box-tree inspection — everything below is the documented,
# isolated use of weasyprint.formatting_structure internals
# ---------------------------------------------------------------------


def _attrib(box) -> dict:
    element = getattr(box, "element", None)
    return getattr(element, "attrib", {}) or {}


def _walk(box, depth: int = 0) -> Iterator:
    yield box, depth
    for child in getattr(box, "children", None) or ():
        yield from _walk(child, depth + 1)


def _measure(document) -> DocumentLayout:
    layout = DocumentLayout(physical_page_count=len(document.pages))
    for idx, page in enumerate(document.pages):
        layout.pages.append(_measure_page(page, idx))
    return layout


def _measure_page(page, index: int) -> PageLayout:
    root = page._page_box  # private API: see module docstring
    result = PageLayout(index=index)

    page_box = None
    content_box = None
    for box, _depth in _walk(root):
        attrs = _attrib(box)
        if "data-pd-page" in attrs and page_box is None:
            page_box = box
            result.page_id = attrs["data-pd-page"]
            result.page_node_id = attrs.get("data-pd-node")
        if attrs.get("data-pd-region") == "content" and content_box is None:
            content_box = box
    if content_box is None:
        return result

    region_top = content_box.position_y
    region_bottom = region_top + content_box.height
    region_left = content_box.position_x
    region_right = region_left + content_box.width
    result.content_available = content_box.height

    # Top-level authored blocks = direct children carrying a node id.
    blocks: list[PlacedBox] = []
    for child in getattr(content_box, "children", None) or ():
        nid = _attrib(child).get("data-pd-node")
        if nid:
            blocks.append(
                PlacedBox(
                    node_id=nid,
                    x=child.position_x,
                    y=child.position_y,
                    width=child.width,
                    height=child.height,
                )
            )
    result.blocks = blocks
    result.block_count = len(blocks)

    max_bottom = region_top
    max_right = region_left
    # Deepest authored node whose rendered bounds cross a region boundary.
    # (node_id, depth, vertical overhang, horizontal overhang)
    best: tuple[str, int, float, float] | None = None
    for box, depth in _walk(content_box):
        if box is content_box:
            continue  # region edges themselves are not overflow
        bottom = box.position_y + box.height
        right = box.position_x + box.width
        if bottom > max_bottom:
            max_bottom = bottom
        if right > max_right:
            max_right = right
        nid = _attrib(box).get("data-pd-node")
        if not nid:
            continue
        v_over = bottom - region_bottom
        h_over = right - region_right
        if v_over <= _EPSILON and h_over <= _EPSILON:
            continue
        cand = (nid, depth, max(v_over, 0.0), max(h_over, 0.0))
        if best is None or depth > best[1] or (depth == best[1] and max(v_over, h_over) > max(best[2], best[3])):
            best = cand

    result.content_used = max(0.0, max_bottom - region_top)
    result.overflow_px = max(0.0, max_bottom - region_bottom)
    result.width_overflow_px = max(0.0, max_right - region_right)

    last_block: PlacedBox | None = None
    for blk in blocks:
        if last_block is None or blk.bottom >= last_block.bottom:
            last_block = blk
    result.last_block_id = last_block.node_id if last_block else None

    if best is not None:
        nid, _depth, v_over, h_over = best
        result.overflow_node_id = nid
        result.overflow_axis = "vertical" if v_over >= h_over else "horizontal"
    return result
