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


def test_remote_css_import_rejected(tmp_path):
    css = tmp_path / "theme.css"
    css.write_text('@import url("https://cdn.example.test/x.css");')
    (tmp_path / "theme.yaml").write_text(
        "id: t\npage: {width: 800, height: 600, unit: px}\n"
        "regions:\n  content: {x: 0, y: 0, width: 100, height: 100}\n"
        "css: theme.css\n",
        encoding="utf-8",
    )
    with pytest.raises(PageDocError, match="remote"):
        load_theme("theme.yaml", str(tmp_path))


def test_remote_css_url_rejected(tmp_path):
    css = tmp_path / "theme.css"
    css.write_text('.x { background: url(//cdn.example.test/i.png); }')
    (tmp_path / "theme.yaml").write_text(
        "id: t\npage: {width: 800, height: 600, unit: px}\n"
        "regions:\n  content: {x: 0, y: 0, width: 100, height: 100}\n"
        "css: theme.css\n",
        encoding="utf-8",
    )
    with pytest.raises(PageDocError, match="remote"):
        load_theme("theme.yaml", str(tmp_path))


def test_local_css_url_and_fragment_allowed(tmp_path):
    css = tmp_path / "theme.css"
    css.write_text(
        '.x { background: url(img/local.png); }\n'
        '.y { clip-path: url(#shape); }\n'
        '.z { background: url("data:image/png;base64,iVBOR"); }\n'
    )
    (tmp_path / "theme.yaml").write_text(
        "id: t\npage: {width: 800, height: 600, unit: px}\n"
        "regions:\n  content: {x: 0, y: 0, width: 100, height: 100}\n"
        "css: theme.css\n",
        encoding="utf-8",
    )
    theme = load_theme("theme.yaml", str(tmp_path))
    assert "local.png" in theme.css


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
