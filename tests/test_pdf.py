"""PDF backend tests: artifact creation, physical-page invariant,
byte determinism, and the adapter isolation contract."""

import os

from pagedoc.backends import weasyprint
from pagedoc.backends.base import DocumentLayout
from pagedoc.document import load_document
from pagedoc.pipeline import build_document
from pagedoc.render.html import render_document
from pagedoc.registry import get_registry
from pagedoc.theme.loader import load_theme

from conftest import REPO_ROOT, write_page

GALLERY = os.path.join(REPO_ROOT, "examples", "layout-gallery")


def _doc(tmp_path, body="Hello world.\n"):
    (tmp_path / "pages").mkdir(exist_ok=True)
    write_page(tmp_path, body, name="pages/p.book.md")
    (tmp_path / "document.yaml").write_text(
        "id: d\ntitle: D\npages:\n  - pages/p.book.md\n", encoding="utf-8"
    )
    doc = load_document(str(tmp_path / "document.yaml"), get_registry())
    return doc, load_theme(doc.theme, doc.manifest_dir)


def test_pdf_bytes_created(tmp_path):
    doc, theme = _doc(tmp_path)
    html = render_document(doc, theme).html
    data = weasyprint.pdf_bytes(html, base_url=doc.manifest_dir)
    assert data.startswith(b"%PDF-")
    assert len(data) > 500


def test_pdf_byte_deterministic(tmp_path):
    doc, theme = _doc(tmp_path, "Text <request> filler.\n\n```\ncode\n```\n")
    html = render_document(doc, theme).html
    b1 = weasyprint.pdf_bytes(html, base_url=doc.manifest_dir)
    b2 = weasyprint.pdf_bytes(html, base_url=doc.manifest_dir)
    assert b1 == b2


def test_layout_document_returns_measurements(tmp_path):
    doc, theme = _doc(tmp_path)
    html = render_document(doc, theme).html
    layout = weasyprint.layout_document(html, base_url=doc.manifest_dir)
    assert isinstance(layout, DocumentLayout)
    assert layout.physical_page_count == 1
    page = layout.pages[0]
    assert page.page_id == "test-page"
    assert page.content_available and page.content_available > 0
    assert page.fits


def test_layout_gallery_pdf(tmp_path):
    manifest = os.path.join(GALLERY, "document.yaml")
    doc = load_document(manifest, get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    assert build.diagnostics == []
    assert build.layout.physical_page_count == len(doc.pages) == 10
    data = weasyprint.pdf_bytes(build.html, base_url=doc.manifest_dir)
    assert data.startswith(b"%PDF-")


def test_weasyprint_is_the_only_backend():
    import pagedoc.backends as backends

    modules = sorted(
        f[:-3]
        for f in os.listdir(os.path.dirname(backends.__file__))
        if f.endswith(".py") and f != "__init__.py"
    )
    assert modules == ["base", "weasyprint"]


def test_weasyprint_not_imported_by_parser_or_registry():
    import pagedoc.ast, pagedoc.document, pagedoc.parser, pagedoc.registry
    import pagedoc.render.components, pagedoc.render.html, pagedoc.render.markdown
    import pagedoc.validation

    for mod in (
        pagedoc.ast,
        pagedoc.document,
        pagedoc.parser,
        pagedoc.registry,
        pagedoc.render.components,
        pagedoc.render.html,
        pagedoc.render.markdown,
        pagedoc.validation,
    ):
        src_file = getattr(mod, "__file__", "")
        with open(src_file, encoding="utf-8") as f:
            assert "weasyprint" not in f.read()
