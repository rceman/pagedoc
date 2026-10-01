"""EXPERIMENTAL pixel-locked flattened PDF output.

Architecture (one layout truth = WeasyPrint):

    PageDoc source -> HTML/CSS -> WeasyPrint layout -> validated vector
    PDF -> rasterize each physical page (PDFium) -> assemble an
    image-only PDF (img2pdf).

The flattened PDF is derived FROM the already-validated vector PDF — the
HTML is never re-laid-out by a second engine. Python is orchestration;
rasterization and PDF assembly run in native libraries.

Tradeoffs (see THEME_SPEC/ARCHITECTURE docs):
- vector PDF: searchable text, small, resolution-independent, viewer
  renders vectors/fonts.
- flattened PDF: pixel-locked, highly viewer-independent, larger, loses
  text selection/search/accessibility, quality bounded by raster DPI.

Not the default; M3 decides which artifact a publication uses.
"""

from __future__ import annotations

import io
import os

from .backends.base import RenderedDocument
from .errors import Diagnostic, PageDocError

_DEFAULT_DPI = 144


def _missing_dep(name: str, dep: str) -> PageDocError:
    return PageDocError(
        Diagnostic(
            "<flatten>",
            1,
            1,
            f"flattened PDF requires optional dependency '{dep}' "
            f"(pip install 'pagedoc[raster]'); import failed: {name}",
        )
    )


def rasterize_pdf_pages(pdf_bytes: bytes, dpi: int = _DEFAULT_DPI):
    """Rasterize every page of a vector PDF at a deterministic DPI.

    Returns (png_bytes_list, page_sizes_pt). Uses PDFium via pypdfium2.
    """

    try:
        import pypdfium2 as pdfium
    except ImportError as e:  # pragma: no cover - optional dep
        raise _missing_dep(str(e), "pypdfium2") from e

    pdf = pdfium.PdfDocument(pdf_bytes)
    try:
        scale = dpi / 72.0
        images: list[bytes] = []
        sizes: list[tuple[float, float]] = []
        for page in pdf:
            w_pt, h_pt = page.get_size()
            sizes.append((w_pt, h_pt))
            bitmap = page.render(scale=scale)
            pil = bitmap.to_pil().convert("RGB")
            buf = io.BytesIO()
            pil.save(buf, "PNG")
            images.append(buf.getvalue())
        return images, sizes
    finally:
        pdf.close()


def assemble_images_pdf(
    png_pages: list[bytes],
    page_sizes_pt: list[tuple[float, float]],
    dpi: int = _DEFAULT_DPI,
) -> bytes:
    """Assemble raster PNG pages into an image-only PDF.

    Each page's physical size is set to the vector page's exact point
    size (not derived from pixel count), so physical dimensions are
    preserved within exact PDF numeric precision. The raster image fills
    the page exactly — at worst a sub-pixel resample when the pixel grid
    cannot express the point size exactly (e.g. odd pt*dpi/72).
    """

    try:
        import img2pdf
    except ImportError as e:  # pragma: no cover - optional dep
        raise _missing_dep(str(e), "img2pdf") from e

    sizes = iter(page_sizes_pt)

    def layout_fun(_imgwpx: int, _imghpx: int, _ndpi):
        w_pt, h_pt = next(sizes)
        # (page width pt, page height pt, image width pt, image height pt)
        return w_pt, h_pt, w_pt, h_pt

    # engine=internal + nodate: byte-deterministic output (the pikepdf
    # engine mixes a timestamp into the trailer /ID).
    return img2pdf.convert(
        png_pages,
        layout_fun=layout_fun,
        nodate=True,
        engine=img2pdf.Engine.internal,
    )


def _flatten_vector_bytes(vector: bytes, dpi: int) -> bytes:
    if isinstance(dpi, bool) or not isinstance(dpi, int) or dpi <= 0:
        raise PageDocError(
            Diagnostic(
                "<flatten>",
                1,
                1,
                f"flatten dpi must be a positive integer, got {dpi!r}",
            )
        )
    images, sizes = rasterize_pdf_pages(vector, dpi)
    return assemble_images_pdf(images, sizes, dpi)


def flatten_document_pdf_bytes(
    rendered: RenderedDocument, dpi: int = _DEFAULT_DPI
) -> bytes:
    """Flatten the measured/validated rendered document into image-only
    PDF bytes — derived from the canonical vector PDF, never relaid out.

    ``dpi`` must be a positive integer; invalid values fail before any
    raster work.
    """

    return _flatten_vector_bytes(rendered.pdf_bytes(), dpi)


def flatten_document_pdf(
    rendered: RenderedDocument, out_path: str, dpi: int = _DEFAULT_DPI
) -> tuple[int, int]:
    """Flatten the measured/validated rendered document into an
    image-only PDF. Returns (vector_bytes, flattened_bytes)."""

    vector = rendered.pdf_bytes()
    flat = _flatten_vector_bytes(vector, dpi)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(flat)
    return len(vector), len(flat)


def flatten_pdf_file(pdf_path: str, out_path: str, dpi: int = _DEFAULT_DPI) -> int:
    """Flatten an existing vector PDF file. Returns flattened byte size."""

    with open(pdf_path, "rb") as f:
        vector = f.read()
    images, sizes = rasterize_pdf_pages(vector, dpi)
    flat = assemble_images_pdf(images, sizes, dpi)
    out_dir = os.path.dirname(out_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(flat)
    return len(flat)
