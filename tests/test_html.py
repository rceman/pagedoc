"""HTML rendering structural, escaping and determinism tests."""

import os

import pytest

from conftest import DEFAULT_FM, write_page
from pagedoc.document import load_document
from pagedoc.parser import parse_page_file
from pagedoc.registry import get_registry
from pagedoc.render.components import render_component
from pagedoc.render.html import render_document, render_page
from pagedoc.theme.loader import load_theme


def _render_page_text(body: str) -> str:
    from conftest import parse_body

    page = parse_body(body)
    return render_page(page, get_registry())


def test_stable_component_classes():
    html = _render_page_text(
        '<request title="T">\nGET /x\n</request>\n\n'
        "<response>\n{}\n</response>\n\n"
        "<browser>\nhttps://a.test\n</browser>\n\n"
        "<note>\nn\n</note>\n\n"
        "<result>\nr\n</result>\n"
    )
    for cls in ("pd-request", "pd-response", "pd-browser", "pd-note", "pd-result", "pd-page"):
        assert cls in html


def test_raw_markup_escaped_in_request():
    html = _render_page_text(
        "<request>\n<script>alert(1)</script>\n<img src=\"/a.png\">\n</request>\n"
    )
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "&lt;img" in html


def test_raw_markup_escaped_in_response():
    html = _render_page_text("<response>\n<div onload=\"x()\">y</div>\n</response>\n")
    assert "&lt;div" in html
    assert '<div onload="x()">' not in html


def test_raw_body_text_verbatim_in_pre():
    html = _render_page_text("<request>\nGET /x\nAccept: application/json\n</request>\n")
    assert "GET /x\nAccept: application/json" in html


def test_browser_https_shows_secure_indicator():
    html = _render_page_text("<browser>\nhttps://app.example.test/p?q=1#f\n</browser>\n")
    assert "pd-browser-secure" in html
    assert "Secure" in html
    assert "pd-url-scheme" in html and "pd-url-host" in html
    assert "app.example.test" in html
    assert "pd-url-query" in html and "pd-url-fragment" in html


def test_browser_http_not_secure_textual():
    html = _render_page_text("<browser>\nhttp://a.test/\n</browser>\n")
    assert "pd-browser-insecure" in html
    assert "Not secure" in html


def test_browser_malformed_url_safe():
    html = _render_page_text("<browser>\nnot a url <b>\n</browser>\n")
    assert "pd-browser" in html
    assert "not a url &lt;b&gt;" in html
    assert "<b>" not in html.split("pd-browser-url")[1]


def test_row_split_preset_classes():
    html = _render_page_text(
        '<row split="wide-left">\n<request>\nG\n</request>\n<note>\nn\n</note>\n</row>\n'
    )
    assert "pd-row--split-wide-left" in html
    assert 'data-pd-split="wide-left"' in html


def test_row_auto_resolves_deterministically():
    # M2 auto rules: request+note -> wide-left, request+response -> equal
    html = _render_page_text(
        "<row>\n<request>\nG\n</request>\n<note>\nn\n</note>\n</row>\n"
    )
    assert "pd-row--split-wide-left" in html
    assert 'data-pd-split="auto"' in html
    html = _render_page_text(
        "<row>\n<request>\nG\n</request>\n<response>\n200\n</response>\n</row>\n"
    )
    assert "pd-row--split-equal" in html
    assert 'data-pd-split="auto"' in html


def test_compare_labels_and_layout():
    html = _render_page_text(
        '<compare labels="Before|After" layout="vertical">\n'
        "<response>\n{}\n</response>\n<response>\n{}\n</response>\n</compare>\n"
    )
    assert "pd-compare--layout-vertical" in html
    assert "Before" in html and "After" in html
    assert html.count("pd-compare-side") >= 2


def test_flow_renders_steps_with_labels():
    html = _render_page_text(
        "<flow>\n<step label=\"A\">\nx\n</step>\n<step label=\"B\">\ny\n</step>\n</flow>\n"
    )
    assert "pd-flow" in html and "pd-step" in html
    assert html.count("pd-step-label") == 2
    assert ">A<" in html and ">B<" in html


def test_media_img_and_caption(tmp_path):
    (tmp_path / "a.png").write_bytes(b"x")
    page_path = write_page(
        tmp_path, '<media src="a.png" alt="Pic" title="T">\nCaption text.\n</media>\n'
    )
    page = parse_page_file(page_path, get_registry())
    html = render_page(page, get_registry())
    assert 'class="pd-media' in html
    assert 'src="a.png"' in html and 'alt="Pic"' in html
    assert "Caption text." in html


def test_markdown_table_renders():
    html = _render_page_text("| A | B |\n| --- | --- |\n| 1 | 2 |\n")
    assert "<table>" in html and "<th>A</th>" in html and "<td>2</td>" in html


def test_full_document_html(tmp_path):
    (tmp_path / "pages").mkdir()
    write_page(tmp_path, "Page one body.\n", name="pages/01.book.md",
               fm="---\nid: p1\ngroup: G\ntitle: One\n---\n")
    write_page(tmp_path, "Page two body.\n", name="pages/02.book.md",
               fm="---\nid: p2\ngroup: G\ntitle: Two\n---\n")
    manifest = tmp_path / "document.yaml"
    manifest.write_text(
        "id: d\ntitle: Doc\npages:\n  - pages/01.book.md\n  - pages/02.book.md\n",
        encoding="utf-8",
    )
    doc = load_document(str(manifest), get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    html1 = render_document(doc, theme).html
    html2 = render_document(load_document(str(manifest), get_registry()), theme).html
    assert html1 == html2  # deterministic
    assert html1.index('id="pd-page-p1"') < html1.index('id="pd-page-p2"')  # order
    assert "<title>Doc</title>" in html1
