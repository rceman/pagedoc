"""WeasyPrint adapter — the sole authoritative fixed-page layout backend.

Public API used:

- ``weasyprint.HTML(string=..., base_url=...).render()`` -> Document
- ``Document.pages`` -> physical page list
- ``Document.write_pdf(...)`` -> PDF bytes

Private API used (isolated here per ARCHITECTURE.md section 12):

- ``Page._page_box``: the rendered box tree root. WeasyPrint exposes no
  public layout-box API; box positions/sizes are required to measure
  content-region usage and attribute overflow to authored nodes. Box
  attributes consumed: ``element.attrib`` (our ``data-pd-*`` markers),
  ``element_tag``, ``position_x``/``position_y``, ``width``, ``height``,
  ``children``. Verified against weasyprint 66.x; the dependency is
  pinned in pyproject.toml.

Determinism: ``SOURCE_DATE_EPOCH`` is set to a fixed value around PDF
generation because fontTools embeds a timestamp in embedded font ``head``
tables otherwise. This makes PDF output byte-identical for identical
inputs.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

from weasyprint import HTML

from .base import DocumentLayout, PageLayout, PlacedBox

# Fixed epoch (2023-11-14) — only used to neutralize embedded timestamps.
_SOURCE_DATE_EPOCH = "1700000000"


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


def render_document_layout(html_text: str, base_url: str):
    """Render HTML with WeasyPrint and return the internal Document.

    Callers outside this module must treat the result opaquely; only the
    helpers below extract layout facts from it.
    """

    return HTML(string=html_text, base_url=base_url).render()


def layout_document(html_text: str, base_url: str) -> DocumentLayout:
    """Render and measure the document.

    Returns a ``DocumentLayout`` describing physical pages, per-page
    content-region usage and overflow.
    """

    doc = render_document_layout(html_text, base_url)
    layout = DocumentLayout(physical_page_count=len(doc.pages))
    for idx, page in enumerate(doc.pages):
        layout.pages.append(_measure_page(page, idx))
    return layout


def write_pdf(html_text: str, base_url: str, out_path: str) -> None:
    """Write a deterministic PDF (byte-stable for identical inputs)."""

    with _fixed_epoch():
        HTML(string=html_text, base_url=base_url).write_pdf(out_path)


def pdf_bytes(html_text: str, base_url: str) -> bytes:
    with _fixed_epoch():
        return HTML(string=html_text, base_url=base_url).write_pdf()


# ---------------------------------------------------------------------
# private box-tree inspection — everything below is the documented,
# isolated use of weasyprint.formatting_structure internals
# ---------------------------------------------------------------------


def _attrib(box) -> dict:
    element = getattr(box, "element", None)
    return getattr(element, "attrib", {}) or {}


def _walk(box) -> Iterator:
    yield box
    for child in getattr(box, "children", None) or ():
        yield from _walk(child)


def _measure_page(page, index: int) -> PageLayout:
    root = page._page_box  # private API: see module docstring
    result = PageLayout(index=index)

    page_box = None
    content_box = None
    for box in _walk(root):
        attrs = _attrib(box)
        if "data-pd-page" in attrs and page_box is None:
            page_box = box
            result.page_id = attrs["data-pd-page"]
            result.page_node_id = attrs.get("data-pd-node")
        if attrs.get("data-pd-region") == "content" and content_box is None:
            content_box = box

    # Direct block children of the content region: the authored top-level
    # blocks of the page.
    blocks: list[PlacedBox] = []
    if content_box is not None:
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
        region_top = content_box.position_y
        region_bottom = region_top + content_box.height
        region_right = content_box.position_x + content_box.width
        result.content_available = content_box.height
        result.blocks = blocks
        result.block_count = len(blocks)

        # Bottom-most point of all rendered descendants vs region bottom.
        max_bottom = region_top
        last_block: PlacedBox | None = None
        for box in _walk(content_box):
            if box is content_box:
                continue
            bottom = box.position_y + box.height
            if bottom > max_bottom:
                max_bottom = bottom
        for blk in blocks:
            if last_block is None or blk.bottom >= last_block.bottom:
                last_block = blk
        result.content_used = max(0.0, max_bottom - region_top)
        result.overflow_px = max(0.0, max_bottom - region_bottom)
        max_right = content_box.position_x
        for box in _walk(content_box):
            right = box.position_x + box.width
            if right > max_right:
                max_right = right
        result.width_overflow_px = max(0.0, max_right - region_right)
        result.last_block_id = last_block.node_id if last_block else None
    return result
