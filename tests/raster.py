"""Raster inspection helpers for cross-renderer visual validation.

These are TEST/INSPECTION tools — rasterizers are not PageDoc layout
engines. The authoritative layout engine is WeasyPrint.

Marker detection works by color thresholds on the raster PNG: the
visual-primitives fixture draws outer rings in #FF6600 (orange) and inner
dots in #009900 (green), colors absent from the theme palette, so pure
channel masks isolate marker geometry robustly across antialiasing
implementations.
"""

from __future__ import annotations

import os


def _pil():
    from PIL import Image

    return Image


def pdfium_available() -> bool:
    try:
        import pypdfium2  # noqa: F401
        return True
    except ImportError:
        return False


def mupdf_available() -> bool:
    try:
        import pymupdf  # noqa: F401
        return True
    except ImportError:
        return False


def pdfium_version() -> str:
    import pypdfium2 as pdfium

    return pdfium.version.PDFIUM_INFO


def mupdf_version() -> str:
    import pymupdf

    return pymupdf.VersionBind


def rasterize_pdfium(pdf_path: str, dpi: int) -> list:
    """Return a list of PIL Images, one per physical page."""

    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    try:
        images = []
        for page in pdf:
            images.append(page.render(scale=dpi / 72).to_pil().convert("RGB"))
        return images
    finally:
        pdf.close()


def rasterize_mupdf(pdf_path: str, dpi: int) -> list:
    import pymupdf

    doc = pymupdf.open(pdf_path)
    try:
        images = []
        for page in doc:
            pix = page.get_pixmap(dpi=dpi)
            Image = _pil()
            import io

            images.append(Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB"))
        return images
    finally:
        doc.close()


def pdf_page_sizes(pdf_path: str) -> list[tuple[float, float]]:
    """Physical page sizes in points via PDFium."""

    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    try:
        return [tuple(page.get_size()) for page in pdf]
    finally:
        pdf.close()


def pdf_page_count(pdf_path: str) -> int:
    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    try:
        return len(pdf)
    finally:
        pdf.close()


def _color_mask(img, kind: str):
    """Binary mask isolating a fixture color.

    kind="outer": orange ring #FF6600. kind="inner": green dot #009900.
    """

    r, g, b = img.split()
    if kind == "outer":
        mr = r.point(lambda v: 255 if v > 200 else 0, mode="1")
        mg = g.point(lambda v: 255 if 60 < v < 160 else 0, mode="1")
        mb = b.point(lambda v: 255 if v < 90 else 0, mode="1")
    elif kind == "inner":
        mr = r.point(lambda v: 255 if v < 100 else 0, mode="1")
        mg = g.point(lambda v: 255 if v > 130 else 0, mode="1")
        mb = b.point(lambda v: 255 if v < 100 else 0, mode="1")
    else:
        raise ValueError(kind)
    from PIL import ImageChops

    return ImageChops.logical_and(ImageChops.logical_and(mr, mg), mb).convert("L")


def _strip_clusters(mask, n: int):
    """Split a mask's total bbox into n equal vertical strips; return the
    bbox of the colored region in each strip. Callers crop to a known
    media box first, so markers inside are horizontally separated."""

    bbox = mask.getbbox()
    if bbox is None:
        return []
    x0, y0, x1, y1 = bbox
    width = (x1 - x0) / n
    out = []
    for i in range(n):
        lo = int(x0 + i * width)
        hi = int(x0 + (i + 1) * width) if i < n - 1 else x1
        sub = mask.crop((lo, y0, hi, y1)).getbbox()
        if sub is None:
            continue
        out.append((lo + sub[0], y0 + sub[1], lo + sub[2], y0 + sub[3]))
    return out


def _center(bbox):
    x0, y0, x1, y1 = bbox
    return (x0 + x1) / 2.0, (y0 + y1) / 2.0


def marker_centers(img, expected: int = 3):
    """Locate each circle+dot marker pair inside a raster crop.

    ``img`` should be cropped to a media block whose markers are spaced
    horizontally (measured placement comes from the layout inspection).
    Returns list of dicts {outer_bbox, outer_center, inner_bbox,
    inner_center} ordered left to right.
    """

    outers = _strip_clusters(_color_mask(img, "outer"), expected)
    inners = _strip_clusters(_color_mask(img, "inner"), expected)
    pairs = []
    for ob, ib in zip(outers, inners):
        pairs.append(
            {
                "outer_bbox": ob,
                "outer_center": _center(ob),
                "inner_bbox": ib,
                "inner_center": _center(ib),
            }
        )
    return pairs


def crop_region(img, rect, scale: float):
    """Crop raster ``img`` to a CSS-px rect scaled by ``scale`` (dpi/96)."""

    x0 = int(rect.x * scale)
    y0 = int(rect.y * scale)
    x1 = int((rect.x + rect.width) * scale)
    y1 = int((rect.y + rect.height) * scale)
    return img.crop((x0, y0, x1, y1))
