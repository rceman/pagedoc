"""Visual-fidelity tests: geometric primitives, cross-renderer raster
checks, and the flattened-PDF prototype.

Rasterizers (PDFium via pypdfium2, MuPDF via PyMuPDF) are validation
tools only — WeasyPrint remains the sole layout engine. Tests skip with
an explicit reason when an optional rasterizer is unavailable; they never
silently pass without performing the comparison.
"""

import hashlib
import os
import re

import pytest

from pagedoc.document import load_document
from pagedoc.flatten import assemble_images_pdf, rasterize_pdf_pages
from pagedoc.pipeline import build_document
from pagedoc.registry import get_registry
from pagedoc.theme.loader import load_theme

import raster
from conftest import REPO_ROOT

VP = os.path.join(REPO_ROOT, "examples", "visual-primitives")
DPI = 288  # high deterministic test scale; 3x CSS pixels
# Center-agreement tolerance in raster px at DPI. Marker rings are ~96-140
# raster px across; 2 px ≈ 0.7 CSS px — far below any visible off-center.
CENTER_TOL_PX = 2.0
CROSS_RENDERER_TOL_PX = 3.0


@pytest.fixture(scope="module")
def vp_build():
    doc = load_document(os.path.join(VP, "document.yaml"), get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    return build_document(doc, theme)


@pytest.fixture(scope="module")
def vp_pdf(tmp_path_factory):
    from pagedoc.document import load_document as ld

    doc = ld(os.path.join(VP, "document.yaml"), get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    out = tmp_path_factory.mktemp("vp") / "vp.pdf"
    build.rendered.write_pdf(str(out))
    return str(out)


def _media_rect(build, page_index, src_suffix):
    for blk in build.layout.pages[page_index].blocks:
        ref = build.node_map.get(blk.node_id)
        node = ref.node if ref else None
        if getattr(node, "name", None) == "media" and node.attrs.get("src", "").endswith(
            src_suffix
        ):
            return blk
    return None


def _marker_pairs(raster_img, build, page_index, src_suffix, expected):
    rect = _media_rect(build, page_index, src_suffix)
    assert rect is not None, f"media {src_suffix} not found"
    crop = raster.crop_region(raster_img, rect, DPI / 96.0)
    pairs = raster.marker_centers(crop, expected)
    assert len(pairs) == expected, f"expected {expected} markers, found {len(pairs)}"
    for p in pairs:
        oc, ic = p["outer_center"], p["inner_center"]
        # inner dot must sit strictly inside the outer ring
        ob = p["outer_bbox"]
        assert ob[0] < ic[0] < ob[2] and ob[1] < ic[1] < ob[3]
        assert abs(oc[0] - ic[0]) <= CENTER_TOL_PX and abs(oc[1] - ic[1]) <= CENTER_TOL_PX, (
            f"off-center marker: ring {oc} dot {ic}"
        )
    return pairs


def test_fixture_markers_are_geometric():
    """Centered primitives must be SVG geometry, not font glyphs."""

    svg = open(os.path.join(VP, "assets", "markers.svg")).read()
    circles = re.findall(
        r'<circle cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"[^>]*?(?:stroke|fill)="([^"]+)"',
        svg,
    )
    assert len(circles) == 6  # 3 rings + 3 dots
    # pair ring/dot by identical cx,cy — exact shared center coordinates
    for i in range(0, 6, 2):
        (rx, ry, _rr, rs), (dx, dy, _rd, df) = circles[i], circles[i + 1]
        assert (rx, ry) == (dx, dy), "ring and dot must share cx,cy"
        assert "#FF6600" in rs or "#009900" in df
    # no text/glyph element draws the markers
    assert "<text" not in svg
    # theme CSS must not rely on glyph arrows for connectors
    css = open(
        os.path.join(
            REPO_ROOT, "src", "pagedoc", "theme", "builtin", "theme.css"
        )
    ).read()
    assert "\\2192" not in css and "content: \"→\"" not in css


def test_visual_primitives_build(vp_build):
    assert vp_build.diagnostics == []
    assert vp_build.layout.physical_page_count == 2


def test_pdfium_raster_geometry(vp_pdf, vp_build):
    if not raster.pdfium_available():
        pytest.skip("pypdfium2 not installed")
    pages = raster.rasterize_pdfium(vp_pdf, DPI)
    assert len(pages) == 2
    _marker_pairs(pages[0], vp_build, 0, "markers.svg", 3)
    _marker_pairs(pages[0], vp_build, 0, "badge.svg", 2)


def test_mupdf_raster_geometry(vp_pdf, vp_build):
    if not raster.mupdf_available():
        pytest.skip("PyMuPDF not installed")
    pages = raster.rasterize_mupdf(vp_pdf, DPI)
    assert len(pages) == 2
    _marker_pairs(pages[0], vp_build, 0, "markers.svg", 3)
    _marker_pairs(pages[0], vp_build, 0, "badge.svg", 2)


def test_cross_renderer_marker_centers(vp_pdf, vp_build):
    if not (raster.pdfium_available() and raster.mupdf_available()):
        pytest.skip("needs both pypdfium2 and PyMuPDF for cross-renderer check")
    a = raster.rasterize_pdfium(vp_pdf, DPI)
    b = raster.rasterize_mupdf(vp_pdf, DPI)
    assert a[0].size == b[0].size, "raster page dimensions must match"
    pa = _marker_pairs(a[0], vp_build, 0, "markers.svg", 3)
    pb = _marker_pairs(b[0], vp_build, 0, "markers.svg", 3)
    for m1, m2 in zip(pa, pb):
        for key in ("outer_center", "inner_center"):
            dx = abs(m1[key][0] - m2[key][0])
            dy = abs(m1[key][1] - m2[key][1])
            assert dx <= CROSS_RENDERER_TOL_PX and dy <= CROSS_RENDERER_TOL_PX, (
                f"cross-renderer center drift {dx:.1f},{dy:.1f}px at {key}"
            )
        # no clipping: ring bbox fully inside the page
        ob = m1["outer_bbox"]
        W, H = a[0].size
        assert ob[0] >= 0 and ob[1] >= 0 and ob[2] <= W and ob[3] <= H


def test_flattened_pdf_round_trip(vp_pdf, tmp_path):
    """Flattened PDF: same page count/dims, markers keep centers."""

    if not raster.pdfium_available():
        pytest.skip("pypdfium2 not installed")
    images, sizes = rasterize_pdf_pages(open(vp_pdf, "rb").read(), 144)
    flat = assemble_images_pdf(images, sizes, 144)
    flat_path = str(tmp_path / "flat.pdf")
    open(flat_path, "wb").write(flat)

    assert raster.pdf_page_count(flat_path) == raster.pdf_page_count(vp_pdf) == 2
    vs = raster.pdf_page_sizes(vp_pdf)
    fs = raster.pdf_page_sizes(flat_path)
    for (vw, vh), (fw, fh) in zip(vs, fs):
        assert abs(vw - fw) <= 0.01 and abs(vh - fh) <= 0.01

    # Round-trip: rasterized flattened PDF keeps marker geometry
    flat_pages = raster.rasterize_pdfium(flat_path, DPI)
    orig_pages = raster.rasterize_pdfium(vp_pdf, DPI)
    # crop to the markers media region computed from the ORIGINAL build
    from pagedoc.document import load_document as ld

    doc = ld(os.path.join(VP, "document.yaml"), get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    rect = _media_rect(build, 0, "markers.svg")
    for orig, flat_page in [(orig_pages[0], flat_pages[0])]:
        po = raster.marker_centers(raster.crop_region(orig, rect, DPI / 96), 3)
        pf = raster.marker_centers(raster.crop_region(flat_page, rect, DPI / 96), 3)
        assert len(po) == len(pf) == 3
        for m1, m2 in zip(po, pf):
            dx = abs(m1["outer_center"][0] - m2["outer_center"][0])
            dy = abs(m1["outer_center"][1] - m2["outer_center"][1])
            assert dx <= 4.0 and dy <= 4.0, "flattened page displaced geometry"


def test_vendored_font_hashes():
    fonts = os.path.join(
        REPO_ROOT, "src", "pagedoc", "theme", "builtin", "fonts"
    )
    expected = {
        "Inter-Regular.ttf": "c0bc3dde07a02d2a93e67a2d91b93d995a8b42deb307421c141678c7306062d2",
        "RobotoMono-Regular.ttf": "4dcd861c90119f9d1e4eb8d4f14b1082b31e6c79fe144e0feba9ddee76a9f7d1",
    }
    for name, sha in expected.items():
        data = open(os.path.join(fonts, name), "rb").read()
        assert hashlib.sha256(data).hexdigest() == sha, name
    assert os.path.exists(os.path.join(fonts, "OFL-inter.txt"))
    assert os.path.exists(os.path.join(fonts, "OFL-robotomono.txt"))


def test_builtin_theme_uses_pinned_local_fonts():
    theme = load_theme("default", ".")
    assert theme.typography_portable
    for role in ("prose", "mono"):
        assert theme.fonts[role].source
        assert not theme.fonts[role].source.startswith("http")


def test_fixture_svgs_contain_no_text_elements():
    """Visual-conformance SVGs must be pure geometry — no font-dependent
    <text> (a generic font-family would pull a host font into the PDF)."""

    assets = os.path.join(VP, "assets")
    total = 0
    for name in sorted(os.listdir(assets)):
        if name.endswith(".svg"):
            total += len(re.findall(r"<text[\\s>]", open(os.path.join(assets, name)).read()))
    assert total == 0, f"expected 0 <text> elements in fixture SVGs, found {total}"


# ---------------- M2-005: Book shell cross-renderer validation ---------------

BOOK_MANIFEST = os.path.join(VP, "..", "layout-gallery", "document-book-v2.yaml")


def _blob_center(img, rgb, box, tol=24):
    """Center (in CSS px) of the color blob inside box (CSS px on the
    2500x2500 page) using a mode-1 mask and bbox center."""
    from PIL import ImageChops

    s = img.size[0] / 2500
    crop = img.crop(tuple(int(v * s) for v in box)).convert("RGB")

    def ch(c, t):
        return c.point(lambda p: 255 if abs(p - t) <= tol else 0).convert("1")

    mask = ImageChops.logical_and(
        ImageChops.logical_and(
            ch(crop.getchannel("R"), rgb[0]), ch(crop.getchannel("G"), rgb[1])
        ),
        ch(crop.getchannel("B"), rgb[2]),
    )
    bb = mask.getbbox()
    if not bb:
        return None
    return (box[0] + (bb[0] + bb[2]) / 2 / s, box[1] + (bb[1] + bb[3]) / 2 / s)


@pytest.mark.skipif(
    not (raster.pdfium_available() and raster.mupdf_available()),
    reason="needs pypdfium2 + pymupdf",
)
def test_book_markers_concentric_both_renderers(tmp_path):
    """Sidebar markers: outer/inner centers must coincide in both
    renderers at 288 DPI (<=1 raster px same-renderer, <=2 cross)."""
    from pagedoc.pipeline import build_document

    doc = load_document(BOOK_MANIFEST, get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    pdf = tmp_path / "book.pdf"
    build.rendered.write_pdf(str(pdf))

    scale = 288 / 72  # 1 css px = 3 raster px at 288dpi
    results = {}
    for name, fn in (("pdfium", raster.rasterize_pdfium),
                     ("mupdf", raster.rasterize_mupdf)):
        img = fn(str(pdf), 288)[0]
        for label, (cx, cy) in (("top", (125, 125)), ("bottom", (125, 2375))):
            box = (cx - 40, cy - 40, cx + 40, cy + 40)
            oc = _blob_center(img, (250, 208, 125), box)
            ic = _blob_center(img, (15, 17, 27), box)
            assert oc and ic, (name, label)
            assert abs(oc[0] - ic[0]) * scale <= 1.0 + 0.5
            assert abs(oc[1] - ic[1]) * scale <= 1.0 + 0.5
            results.setdefault(label, {})[name] = oc
    for label in ("top", "bottom"):
        po = results[label]["pdfium"]
        mo = results[label]["mupdf"]
        assert abs(po[0] - mo[0]) * scale <= 2.0 + 0.5
        assert abs(po[1] - mo[1]) * scale <= 2.0 + 0.5


@pytest.mark.skipif(
    not (raster.pdfium_available() and raster.mupdf_available()),
    reason="needs pypdfium2 + pymupdf",
)
def test_book_footer_logo_renders_both_renderers(tmp_path):
    """Supplied masked-SVG logo must render (not blank/black) in both
    PDFium and MuPDF at the footer logo bounds (page-rel 292..430 x,
    2298..2452 y)."""
    from pagedoc.pipeline import build_document

    doc = load_document(BOOK_MANIFEST, get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    pdf = tmp_path / "book.pdf"
    build.rendered.write_pdf(str(pdf))
    for name, fn in (("pdfium", raster.rasterize_pdfium),
                     ("mupdf", raster.rasterize_mupdf)):
        img = fn(str(pdf), 96)[0].convert("RGB")
        crop = img.crop((292, 2298, 430, 2452))
        colors = crop.getcolors(crop.width * crop.height)
        distinct = len(colors)
        # logo has blue border + white face + dark shield + gray patch
        assert distinct > 20, (name, distinct)
        px = crop.load()
        # blue border around shield top edge
        bluish = [c for c, v in colors if v[2] > 150 and v[0] < 80]
        whitish = [c for c, v in colors if min(v) > 220]
        assert bluish and whitish, (name, "missing logo colors")


# ---------------- M2-006: footer-logo stability ------------------------------

ASSETS = os.path.join(
    REPO_ROOT, "examples", "themes", "book-v2-reference", "assets"
)
LOGO_BOX = (292, 2298, 430, 2452)  # CSS px on the 2500x2500 page


def _logo_crop_hashes(pdf_path, fn=raster.rasterize_pdfium, dpi=96):
    import hashlib

    out = []
    for im in fn(pdf_path, dpi):
        out.append(
            hashlib.sha256(im.crop(LOGO_BOX).convert("RGB").tobytes()).hexdigest()
        )
    return out


def test_active_footer_logo_is_mask_free_svg():
    """The active logo must be mask-free geometry — the masked variant is
    preserved only as provenance (footer-logo-reference.svg)."""
    svg = open(os.path.join(ASSETS, "footer-logo.svg")).read()
    for bad in ("<mask", "<clipPath", "<filter", "<text", "href", "script"):
        assert bad not in svg, bad
    ref = open(os.path.join(ASSETS, "footer-logo-reference.svg")).read()
    assert "<mask" in ref  # provenance file keeps the original artwork


@pytest.mark.skipif(not raster.pdfium_available(), reason="needs pypdfium2")
def test_book_footer_logo_identical_all_ten_pages(tmp_path):
    from pagedoc.pipeline import build_document

    doc = load_document(BOOK_MANIFEST, get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    pdf = tmp_path / "book.pdf"
    build.rendered.write_pdf(str(pdf))
    hashes = _logo_crop_hashes(str(pdf))
    assert len(set(hashes)) == 1, hashes


@pytest.mark.skipif(not raster.pdfium_available(), reason="needs pypdfium2")
def test_rendered_document_serialization_is_stable(tmp_path):
    """Same RenderedDocument serialized repeatedly must be byte-identical
    (the masked-SVG defect mutated state across serializations)."""
    from pagedoc.pipeline import build_document

    doc = load_document(BOOK_MANIFEST, get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    rd = build.rendered
    a = rd.pdf_bytes()
    b = rd.pdf_bytes()
    out = tmp_path / "book.pdf"
    rd.write_pdf(str(out))
    c = out.read_bytes()
    assert a == b == c


@pytest.mark.skipif(not raster.pdfium_available(), reason="needs pypdfium2")
def test_serialization_order_does_not_change_output(tmp_path):
    """pdf_bytes() then write_pdf() and vice versa must rasterize
    identically on every page."""
    from pagedoc.pipeline import build_document
    from PIL import ImageChops

    doc = load_document(BOOK_MANIFEST, get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)

    # order A: bytes then file
    a_bytes = build.rendered.pdf_bytes()
    fa = tmp_path / "a.pdf"
    build.rendered.write_pdf(str(fa))
    # order B: file then bytes
    fb = tmp_path / "b.pdf"
    build.rendered.write_pdf(str(fb))
    b_bytes = build.rendered.pdf_bytes()
    assert a_bytes == b_bytes == fa.read_bytes() == fb.read_bytes()


@pytest.mark.skipif(not raster.pdfium_available(), reason="needs pypdfium2")
def test_vector_vs_flattened_identical_all_ten_pages(tmp_path):
    from pagedoc.flatten import assemble_images_pdf, rasterize_pdf_pages
    from pagedoc.pipeline import build_document
    from PIL import ImageChops

    doc = load_document(BOOK_MANIFEST, get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    vec = tmp_path / "v.pdf"
    build.rendered.write_pdf(str(vec))
    flat = tmp_path / "f.pdf"
    flat.write_bytes(
        assemble_images_pdf(*rasterize_pdf_pages(build.rendered.pdf_bytes(), 96), 96)
    )
    v = raster.rasterize_pdfium(str(vec), 96)
    f = raster.rasterize_pdfium(str(flat), 96)
    assert len(v) == len(f) == 10
    for i in range(10):
        d = ImageChops.difference(v[i], f[i]).convert("L")
        nz = sum(1 for p in d.get_flattened_data() if p)
        assert nz == 0, f"page {i + 1}: {nz} differing px"
