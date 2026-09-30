"""Theme model + loader tests (M2 fixed-page geometry)."""

import os
import sys

import pytest

from pagedoc.errors import PageDocError
sys.path.insert(0, os.path.dirname(__file__))
from conftest import REPO_ROOT
from pagedoc.document import load_document
from pagedoc.pipeline import build_document
from pagedoc.registry import get_registry
from pagedoc.theme.loader import load_theme
from pagedoc.theme.model import Theme


def test_builtin_theme_loads():
    theme = load_theme("default", ".")
    assert theme.id == "default"
    assert theme.page_width > 0 and theme.page_height > 0
    assert "content" in theme.regions
    assert "header" in theme.regions and "footer" in theme.regions
    assert theme.splits["equal"] == (1.0, 1.0)
    assert theme.splits["wide-left"] == (2.0, 1.0)
    assert theme.splits["wide-right"] == (1.0, 2.0)
    assert "prose" in theme.fonts and "mono" in theme.fonts
    assert theme.css.strip() != ""


def test_builtin_theme_alias_and_none():
    assert load_theme(None, ".").id == "default"
    assert load_theme("builtin", ".").id == "default"


def _write_theme(tmp_path, extra="", page="width: 800\n  height: 600\n  unit: px"):
    css = tmp_path / "theme.css"
    css.write_text("body { color: black; }", encoding="utf-8")
    theme = tmp_path / "theme.yaml"
    theme.write_text(
        "id: t\n"
        f"page:\n  {page}\n"
        "regions:\n"
        "  content: {x: 10, y: 10, width: 100, height: 100}\n"
        + extra
        + "\ncss: theme.css\n",
        encoding="utf-8",
    )
    return tmp_path


def test_custom_theme_loads(tmp_path):
    d = _write_theme(tmp_path)
    theme = load_theme("theme.yaml", str(d))
    assert theme.id == "t"
    assert theme.page_width == 800 and theme.page_height == 600
    assert theme.regions["content"].x == 10


def test_theme_missing_content_region_fails(tmp_path):
    css = tmp_path / "theme.css"
    css.write_text("x", encoding="utf-8")
    (tmp_path / "theme.yaml").write_text(
        "id: t\npage: {width: 800, height: 600, unit: px}\n"
        "regions:\n  header: {x: 0, y: 0, width: 10, height: 10}\n",
        encoding="utf-8",
    )
    with pytest.raises(PageDocError, match="'content'"):
        load_theme("theme.yaml", str(tmp_path))


def test_theme_invalid_unit_fails(tmp_path):
    d = _write_theme(tmp_path, page="width: 800\n  height: 600\n  unit: pt")
    with pytest.raises(PageDocError, match="unit"):
        load_theme("theme.yaml", str(d))


def test_theme_invalid_geometry_fails(tmp_path):
    d = _write_theme(tmp_path, page="width: -5\n  height: 600\n  unit: px")
    with pytest.raises(PageDocError, match="page.width"):
        load_theme("theme.yaml", str(d))


def test_theme_invalid_region_fails(tmp_path):
    css = tmp_path / "theme.css"
    css.write_text("x", encoding="utf-8")
    (tmp_path / "theme.yaml").write_text(
        "id: t\npage: {width: 800, height: 600, unit: px}\n"
        "regions:\n  content: {x: 0, y: 0, height: 10}\n",
        encoding="utf-8",
    )
    with pytest.raises(PageDocError, match="regions.content.width"):
        load_theme("theme.yaml", str(tmp_path))


def test_theme_invalid_split_fails(tmp_path):
    d = _write_theme(tmp_path, extra="splits:\n  bad: [0, 1]\n")
    with pytest.raises(PageDocError, match="split"):
        load_theme("theme.yaml", str(d))


def test_theme_remote_font_rejected(tmp_path):
    d = _write_theme(
        tmp_path,
        extra="fonts:\n  prose:\n    family: sans\n    source: https://x.example/f.ttf\n",
    )
    with pytest.raises(PageDocError, match="local"):
        load_theme("theme.yaml", str(d))


def test_theme_missing_font_file_rejected(tmp_path):
    d = _write_theme(
        tmp_path, extra="fonts:\n  prose:\n    family: T\n    source: nope.ttf\n"
    )
    with pytest.raises(PageDocError, match="font file not found"):
        load_theme("theme.yaml", str(d))


def test_theme_local_font_accepted(tmp_path):
    font = tmp_path / "PDTest.ttf"
    font.write_bytes(b"\x00\x01\x00\x00" + b"\x00" * 64)
    d = _write_theme(
        tmp_path,
        extra="fonts:\n  prose:\n    family: 'PDTest'\n    source: PDTest.ttf\n",
    )
    theme = load_theme("theme.yaml", str(d))
    assert theme.fonts["prose"].source == "PDTest.ttf"


def test_theme_remote_css_rejected(tmp_path):
    (tmp_path / "theme.yaml").write_text(
        "id: t\npage: {width: 800, height: 600, unit: px}\n"
        "regions:\n  content: {x: 0, y: 0, width: 10, height: 10}\n"
        "css: https://x.example/t.css\n",
        encoding="utf-8",
    )
    with pytest.raises(PageDocError, match="local"):
        load_theme("theme.yaml", str(tmp_path))


def test_theme_not_found(tmp_path):
    with pytest.raises(PageDocError, match="theme manifest not found"):
        load_theme("nope/theme.yaml", str(tmp_path))


def _write_theme_with_region(tmp_path, region_yaml, extra=""):
    css = tmp_path / "theme.css"
    css.write_text("x", encoding="utf-8")
    (tmp_path / "theme.yaml").write_text(
        "id: t\npage: {width: 800, height: 600, unit: px}\n"
        + region_yaml
        + extra
        + "\ncss: theme.css\n",
        encoding="utf-8",
    )
    return tmp_path


def test_region_past_right_edge_rejected(tmp_path):
    d = _write_theme_with_region(
        tmp_path,
        "regions:\n  content: {x: 700, y: 0, width: 200, height: 100}\n",
    )
    with pytest.raises(PageDocError, match="right page edge"):
        load_theme("theme.yaml", str(d))


def test_region_past_bottom_edge_rejected(tmp_path):
    d = _write_theme_with_region(
        tmp_path,
        "regions:\n  content: {x: 0, y: 550, width: 100, height: 100}\n",
    )
    with pytest.raises(PageDocError, match="bottom page edge"):
        load_theme("theme.yaml", str(d))


def test_region_negative_coordinate_rejected(tmp_path):
    d = _write_theme_with_region(
        tmp_path,
        "regions:\n  content: {x: -5, y: 0, width: 100, height: 100}\n",
    )
    with pytest.raises(PageDocError):
        load_theme("theme.yaml", str(d))


def test_region_exact_page_edge_accepted(tmp_path):
    d = _write_theme_with_region(
        tmp_path,
        "regions:\n  content: {x: 0, y: 0, width: 800, height: 600}\n",
    )
    theme = load_theme("theme.yaml", str(d))
    assert theme.regions["content"].width == 800


def test_overlapping_regions_accepted(tmp_path):
    d = _write_theme_with_region(
        tmp_path,
        "regions:\n"
        "  content: {x: 0, y: 0, width: 800, height: 600}\n"
        "  header: {x: 0, y: 0, width: 800, height: 50}\n",
    )
    theme = load_theme("theme.yaml", str(d))
    assert "header" in theme.regions


def test_negative_spacing_rejected(tmp_path):
    d = _write_theme_with_region(
        tmp_path,
        "regions:\n  content: {x: 0, y: 0, width: 100, height: 100}\n",
        extra="spacing:\n  block: -5\n",
    )
    with pytest.raises(PageDocError, match="non-negative"):
        load_theme("theme.yaml", str(d))


def test_builtin_theme_typography_portable():
    theme = load_theme("default", ".")
    assert theme.typography_portable is True


def test_theme_without_sources_not_portable(tmp_path):
    d = _write_theme_with_region(
        tmp_path,
        "regions:\n  content: {x: 0, y: 0, width: 100, height: 100}\n",
        extra="fonts:\n  prose: {family: 'SystemStack, sans-serif'}\n",
    )
    theme = load_theme("theme.yaml", str(d))
    assert theme.typography_portable is False


# ---------------- M2 final: multi-theme + Book v2 reference ------------------

BOOK_THEME_DIR = os.path.join(REPO_ROOT, "examples", "themes", "book-v2-reference")
BOOK_MANIFEST = os.path.join(
    REPO_ROOT, "examples", "layout-gallery", "document-book-v2.yaml"
)


def test_book_theme_loads_from_relative_manifest_path():
    doc = load_document(BOOK_MANIFEST, get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    assert theme.id == "book-v2-reference"
    assert theme.page_width == 2500 and theme.page_height == 2500


def test_book_theme_exact_geometry():
    theme = load_theme("theme.yaml", BOOK_THEME_DIR)
    c = theme.regions["content"]
    assert (c.x, c.y, c.width, c.height) == (300.0, 513.0, 2150.0, 1687.0)
    s = theme.regions["sidebar"]
    assert (s.x, s.y, s.width, s.height) == (0.0, 0.0, 250.0, 2500.0)
    f = theme.regions["footer"]
    assert (f.x, f.y, f.width, f.height) == (250.0, 2250.0, 2250.0, 250.0)


def test_book_theme_fonts_resolve_and_are_portable():
    theme = load_theme("theme.yaml", BOOK_THEME_DIR)
    assert theme.typography_portable
    for role in ("prose", "mono"):
        src = theme.fonts[role].source
        assert src and not src.startswith(("http", "//"))
        assert os.path.isfile(os.path.join(BOOK_THEME_DIR, src))


def test_book_theme_copied_fonts_match_builtin_hashes():
    import hashlib

    for name in ("Inter-Regular.ttf", "RobotoMono-Regular.ttf"):
        data = open(os.path.join(BOOK_THEME_DIR, "fonts", name), "rb").read()
        expect = {
            "Inter-Regular.ttf":
                "c0bc3dde07a02d2a93e67a2d91b93d995a8b42deb307421c141678c7306062d2",
            "RobotoMono-Regular.ttf":
                "4dcd861c90119f9d1e4eb8d4f14b1082b31e6c79fe144e0feba9ddee76a9f7d1",
        }[name]
        assert hashlib.sha256(data).hexdigest() == expect


def test_same_pages_identical_ast_across_themes():
    default_doc = load_document(
        os.path.join(REPO_ROOT, "examples", "layout-gallery", "document.yaml"),
        get_registry(),
    )
    book_doc = load_document(BOOK_MANIFEST, get_registry())
    assert [p.page_id for p in default_doc.pages] == [
        p.page_id for p in book_doc.pages
    ]
    for a, b in zip(default_doc.pages, book_doc.pages):
        da, db = a.to_dict(), b.to_dict()
        da["source"]["path"] = db["source"]["path"]  # paths may differ by name only
        assert da == db


def test_both_themes_render_same_sources_all_fit():
    for manifest in (
        os.path.join(REPO_ROOT, "examples", "layout-gallery", "document.yaml"),
        BOOK_MANIFEST,
    ):
        doc = load_document(manifest, get_registry())
        theme = load_theme(doc.theme, doc.manifest_dir)
        build = build_document(doc, theme)
        assert build.diagnostics == []
        assert build.layout.physical_page_count == 10
        assert all(p.fits for p in build.layout.pages)


def test_book_theme_no_page_specific_selectors():
    css = open(os.path.join(BOOK_THEME_DIR, "theme.css")).read()
    assert "#pd-page-" not in css
    assert "gallery-" not in css


def _write_min_theme(tmp_path, css_text=None):
    if css_text is not None:
        (tmp_path / "theme.css").write_text(css_text, encoding="utf-8")
    (tmp_path / "theme.yaml").write_text(
        "id: t\npage: {width: 800, height: 600, unit: px}\n"
        "regions:\n  content: {x: 0, y: 0, width: 100, height: 100}\n"
        "css: theme.css\n",
        encoding="utf-8",
    )


def test_remote_css_import_rejected(tmp_path):
    _write_min_theme(tmp_path, '@import url("https://cdn.example.test/x.css");')
    with pytest.raises(PageDocError, match="@import"):
        load_theme("theme.yaml", str(tmp_path))


def test_local_css_import_also_rejected(tmp_path):
    _write_min_theme(tmp_path, '@import "more.css";')
    with pytest.raises(PageDocError, match="@import"):
        load_theme("theme.yaml", str(tmp_path))


def test_remote_css_url_rejected(tmp_path):
    _write_min_theme(tmp_path, '.x { background: url(//cdn.example.test/i.png); }')
    with pytest.raises(PageDocError, match="remote"):
        load_theme("theme.yaml", str(tmp_path))


def test_remote_css_https_url_rejected(tmp_path):
    _write_min_theme(tmp_path, '.x { background: url("https://cdn.example.test/i.png"); }')
    with pytest.raises(PageDocError, match="remote"):
        load_theme("theme.yaml", str(tmp_path))


def test_file_url_css_asset_rejected(tmp_path):
    _write_min_theme(tmp_path, '.x { background: url(file:///etc/passwd.png); }')
    with pytest.raises(PageDocError, match="remote or file"):
        load_theme("theme.yaml", str(tmp_path))


def test_absolute_path_css_asset_rejected(tmp_path):
    _write_min_theme(tmp_path, '.x { background: url("/etc/marker.svg"); }')
    with pytest.raises(PageDocError, match="relative"):
        load_theme("theme.yaml", str(tmp_path))


def test_css_asset_traversal_rejected(tmp_path):
    _write_min_theme(tmp_path, '.x { background: url("../escape.png"); }')
    with pytest.raises(PageDocError, match="escapes"):
        load_theme("theme.yaml", str(tmp_path))


def test_missing_css_asset_rejected(tmp_path):
    _write_min_theme(tmp_path, '.x { background: url("nope.svg"); }')
    with pytest.raises(PageDocError, match="not found"):
        load_theme("theme.yaml", str(tmp_path))


def test_non_image_css_asset_rejected(tmp_path):
    (tmp_path / "x.txt").write_text("nope")
    _write_min_theme(tmp_path, '.x { background: url("x.txt"); }')
    with pytest.raises(PageDocError, match="must be an image"):
        load_theme("theme.yaml", str(tmp_path))


_TINY_SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" width="4" height="4">'
    '<rect width="4" height="4" fill="#00ff00"/></svg>'
)


def test_local_image_asset_inlined_as_data_uri(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "mark.svg").write_text(_TINY_SVG)
    _write_min_theme(tmp_path, '.x { background: url("assets/mark.svg"); }')
    theme = load_theme("theme.yaml", str(tmp_path))
    assert "data:image/svg+xml;base64," in theme.css
    assert "assets/mark.svg" not in theme.css  # fully inlined
    assert str(tmp_path) not in theme.css  # no absolute path leaks


def test_data_uri_and_fragment_urls_allowed(tmp_path):
    _write_min_theme(
        tmp_path,
        '.y { clip-path: url(#shape); }\n'
        '.z { background: url("data:image/png;base64,iVBOR"); }\n',
    )
    theme = load_theme("theme.yaml", str(tmp_path))
    assert "url(#shape)" in theme.css or 'url("#shape")' in theme.css
    assert "data:image/png;base64" in theme.css


def test_theme_asset_renders_into_deterministic_html(tmp_path):
    """A theme in an unrelated directory can own image assets; rendered
    HTML embeds them with no absolute paths and is byte-identical."""
    theme_dir = tmp_path / "mytheme"
    (theme_dir / "assets").mkdir(parents=True)
    (theme_dir / "assets" / "logo.svg").write_text(_TINY_SVG)
    (theme_dir / "theme.css").write_text(
        '.pd-region-header { background: url("assets/logo.svg") no-repeat; }\n',
        encoding="utf-8",
    )
    (theme_dir / "theme.yaml").write_text(
        "id: t\npage: {width: 800, height: 600, unit: px}\n"
        "regions:\n  content: {x: 0, y: 0, width: 100, height: 100}\n"
        "css: theme.css\n",
        encoding="utf-8",
    )
    (tmp_path / "page1.book.md").write_text(
        "---\nid: p1\ntitle: T\ngroup: G\n---\nBody text.\n", encoding="utf-8"
    )
    (tmp_path / "document.yaml").write_text(
        'id: d\ntitle: D\ntheme: mytheme/theme.yaml\npages: [page1.book.md]\n',
        encoding="utf-8",
    )
    doc = load_document(str(tmp_path / "document.yaml"), get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    from pagedoc.render.html import render_document

    html1 = render_document(doc, theme).html
    html2 = render_document(doc, load_theme(doc.theme, doc.manifest_dir)).html
    assert html1 == html2
    assert "data:image/svg+xml;base64," in html1
    assert str(tmp_path) not in html1
    assert "mytheme" not in html1  # no relative machine path leaks


def test_book_theme_pdf_page_size(tmp_path):
    doc = load_document(BOOK_MANIFEST, get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    out = tmp_path / "book.pdf"
    build.rendered.write_pdf(str(out))
    import raster

    if raster.pdfium_available():
        sizes = raster.pdf_page_sizes(str(out))
        assert len(sizes) == 10
        assert abs(sizes[0][0] - 1875.0) < 1 and abs(sizes[0][1] - 1875.0) < 1


def test_book_theme_raster_is_native_2500_square(tmp_path):
    import raster

    if not raster.pdfium_available():
        pytest.skip("pypdfium2 not installed")
    doc = load_document(BOOK_MANIFEST, get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    out = tmp_path / "book.pdf"
    build.rendered.write_pdf(str(out))
    imgs = raster.rasterize_pdfium(str(out), 96)
    assert len(imgs) == 10
    for im in imgs:
        assert im.size == (2500, 2500)


# ---------------- M2-005: Book v2.2.1 shell parity ----------------------------

BOOK_CSS = os.path.join(BOOK_THEME_DIR, "theme.css")


def _book_css():
    return open(BOOK_CSS, encoding="utf-8").read()


def test_book_shell_marker_geometry_constants():
    css = _book_css()
    # top marker: outer bounds x101..149, y101..149 -> center (125,125)
    assert "left: 101px" in css and "top: 101px" in css
    # bottom marker: y2351..2399 -> bottom edge offset 101px
    assert "bottom: 101px" in css
    assert "width: 48px; height: 48px" in css
    assert 'url("assets/sidebar-marker.svg")' in css


def test_book_marker_svg_is_concentric_geometry():
    svg = open(
        os.path.join(BOOK_THEME_DIR, "assets", "sidebar-marker.svg")
    ).read()
    assert 'viewBox="0 0 48 48"' in svg
    assert "<text" not in svg and "font" not in svg
    # both circles share cx=24 cy=24 -> mathematically concentric
    import re
    circles = re.findall(r"<circle[^>]+>", svg)
    assert len(circles) == 2
    for c in circles:
        assert 'cx="24"' in c and 'cy="24"' in c


def test_book_sidebar_label_style():
    css = _book_css()
    label = css.split(".pd-region-sidebar::before")[1].split("}")[0]
    assert '"ETHICAL HACKING"' in label
    assert "left: 48px" in label and "top: 1607px" in label
    assert "rotate(-90deg)" in label
    assert "transform-origin: left top" in label
    assert "font-weight: 400" in label and "font-size: 80px" in label
    assert "var(--pd-gold)" in label
    assert "var(--pd-font-mono" in label
    assert "translate(-50%" not in label


def test_book_header_typography_and_bands():
    css = _book_css()
    group = css.split(".pd-page-group")[1].split("}")[0]
    title = css.split(".pd-page-title")[1].split("}")[0]
    for sel, size in ((group, "150px"), (title, "110px")):
        assert "font-weight: 400" in sel and "font-weight: 700" not in sel
        assert "bold" not in sel
        assert "text-transform" not in sel
    assert f"font-size: 150px" in group
    assert "font-size: 110px" in title
    # title band lower portion of the 513px header
    assert "top: 250px" in title
    # no separator borders on the header region
    hdr = css.split(".pd-region-header")[1] if ".pd-region-header" in css else ""
    assert "border" not in (hdr.split("}")[0] if hdr else "")


def test_book_footer_composition_constants():
    css = _book_css()
    logo = css.split(".pd-page-doc::before")[1].split("}")[0]
    assert "left: 42px" in logo and "top: 48px" in logo
    assert "width: 138px" in logo and "height: 154px" in logo
    assert 'url("assets/footer-logo.svg")' in logo
    sub = css.split(".pd-page-doc::after")[1].split("}")[0]
    assert '"Tips and Tricks Vol.1"' in sub
    assert "left: 822px" in sub and "top: 150px" in sub
    assert "font-size: 48px" in sub
    brand = css.split(".pd-region-footer::before")[1].split("}")[0]
    assert '"#BUGBOUNTY"' in brand
    assert "left: 764px" in brand and "top: 18px" in brand
    assert "font-size: 120px" in brand and "font-weight: 400" in brand
    disc = css.split(".pd-region-footer::after")[1].split("}")[0]
    assert "FOR EDUCATIONAL" in disc and "PURPOSES ONLY" in disc
    assert "left: 1547px" in disc and "top: 52px" in disc
    assert "width: 414px" in disc and "height: 153px" in disc
    assert "6px solid var(--pd-red)" in disc
    assert "font-size: 40px" in disc
    # footer has no decorative top border
    footer = css.split(".pd-region-footer {")[1].split("}")[0]
    assert "border" not in footer


def test_book_single_page_number_counter():
    css = _book_css()
    assert "counter-reset: pd-book-page" in css
    assert "counter-increment: pd-book-page" in css
    assert "counter(pd-book-page)" in css
    num = css.split(".pd-page-number::before")[1].split("}")[0]
    assert "right: 100px" in num and "top: 35px" in num
    assert "font-size: 120px" in num


def test_book_theme_no_system_shell_bold():
    css = _book_css()
    for sel in (".pd-region-sidebar::before", ".pd-page-group",
                ".pd-page-title", ".pd-region-footer::before",
                ".pd-page-doc::after", ".pd-region-footer::after",
                ".pd-page-number::before"):
        block = css.split(sel)[1].split("}")[0]
        assert "font-weight: 700" not in block and "bold" not in block, sel


def test_book_page_uses_single_number_not_range(tmp_path):
    import pymupdf  # noqa: F401 - pymupdf used via raster text below

    import raster
    if not raster.pdfium_available():
        pytest.skip("pypdfium2 not installed")
    import pymupdf as fitz

    doc = load_document(BOOK_MANIFEST, get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    out = tmp_path / "book.pdf"
    build.rendered.write_pdf(str(out))
    d = fitz.open(str(out))
    for i in range(len(d)):
        text = d[i].get_text()
        assert f"{i + 1} / 10" not in text
        # shell strings extract from every page
        for s in ("ETHICAL HACKING", "#BUGBOUNTY", "FOR EDUCATIONAL"):
            assert s in text


def test_book_pdf_embedded_fonts_are_pinned_only(tmp_path):
    import pymupdf as fitz
    import re

    doc = load_document(BOOK_MANIFEST, get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    out = tmp_path / "book.pdf"
    build.rendered.write_pdf(str(out))
    d = fitz.open(str(out))
    fams = set()
    for i in range(len(d)):
        for f in d[i].get_fonts():
            fams.add(re.sub(r"^[A-Z]{6}\+", "", f[3]))
    for bad in ("DejaVu", "Liberation", "Arial", "Courier", "Times"):
        assert not any(bad in f for f in fams), fams
    assert fams <= {"pd-prose", "pd-prose-Bold", "pd-mono", "pd-mono-Bold"}
