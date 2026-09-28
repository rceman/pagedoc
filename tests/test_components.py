"""Component parsing happy-path tests."""

import pytest

from conftest import parse_body
from pagedoc.ast import ComponentNode
from pagedoc.errors import PageDocError
from pagedoc.registry import get_registry
from pagedoc.validation import validate_page


def _comp(page, idx=0) -> ComponentNode:
    node = page.children[idx]
    assert isinstance(node, ComponentNode)
    return node


def test_request_raw_body():
    page = parse_body(
        '<request title="Lookup">\nGET /api/items/42\nAccept: application/json\n</request>\n'
    )
    node = _comp(page)
    assert node.name == "request"
    assert node.raw == "GET /api/items/42\nAccept: application/json"
    assert node.attrs == {"title": "Lookup", "lang": "http"}
    assert node.source.start_line == 7
    assert node.source.end_line == 10


def test_response_raw_body():
    page = parse_body('<response status="200">\n{"id":42}\n</response>\n')
    node = _comp(page)
    assert node.name == "response"
    assert node.raw == '{"id":42}'
    assert node.attrs == {"status": "200", "lang": "auto"}


def test_literal_html_inside_raw_request():
    page = parse_body(
        "<request>\nPOST /x HTTP/1.1\nContent-Type: text/html\n\n"
        '<img src="/asset.png">\n<script>example()</script>\n</request>\n'
    )
    node = _comp(page)
    assert node.name == "request"
    assert '<img src="/asset.png">' in node.raw
    assert "<script>example()</script>" in node.raw


def test_raw_body_preserves_inner_blank_lines():
    page = parse_body("<request>\nGET /x\n\nHTTP-body\n</request>\n")
    assert _comp(page).raw == "GET /x\n\nHTTP-body"


def test_note_markdown_body():
    page = parse_body("<note>\nSome *supporting* text.\n</note>\n")
    node = _comp(page)
    assert node.name == "note"
    assert node.attrs["tone"] == "note"
    assert node.body is not None
    assert node.body[0].type == "paragraph"


def test_note_tone_warning():
    page = parse_body('<note tone="warning">\nCareful.\n</note>\n')
    assert _comp(page).attrs["tone"] == "warning"


def test_result_markdown_body():
    page = parse_body('<result title="Outcome">\nIt works.\n</result>\n')
    node = _comp(page)
    assert node.name == "result"
    assert node.attrs["title"] == "Outcome"
    assert node.body[0].type == "paragraph"


def test_row_valid_nesting():
    page = parse_body(
        "<row>\n\n<request>\nGET /x\n</request>\n\n<note>\nWhy.\n</note>\n\n</row>\n"
    )
    node = _comp(page)
    assert node.name == "row"
    assert [c.name for c in node.children] == ["request", "note"]
    assert node.attrs == {"split": "auto", "align": "start"}
    assert validate_page(page, get_registry()) == []


def test_row_split_and_align():
    page = parse_body(
        '<row split="wide-left" align="stretch">\n'
        "<request>\nGET /x\n</request>\n<note>\nN.\n</note>\n</row>\n"
    )
    node = _comp(page)
    assert node.attrs == {"split": "wide-left", "align": "stretch"}


def test_compare():
    page = parse_body(
        '<compare labels="Expected|Actual">\n'
        "<response>\n{}\n</response>\n<response>\n{}\n</response>\n</compare>\n"
    )
    node = _comp(page)
    assert node.name == "compare"
    assert node.attrs["labels"] == "Expected|Actual"
    assert node.attrs["layout"] == "auto"
    assert [c.name for c in node.children] == ["response", "response"]


def test_flow_with_steps():
    page = parse_body(
        "<flow>\n"
        '<step label="Input">\n`a`\n</step>\n'
        '<step label="Out">\ndone\n</step>\n'
        "</flow>\n"
    )
    node = _comp(page)
    assert node.name == "flow"
    assert [c.name for c in node.children] == ["step", "step"]
    assert node.children[0].attrs["label"] == "Input"
    assert node.children[0].body[0].type == "paragraph"
    assert validate_page(page, get_registry()) == []


def test_browser():
    page = parse_body(
        '<browser status="404">\nhttps://app.example.test/projects\n</browser>\n'
    )
    node = _comp(page)
    assert node.name == "browser"
    assert node.raw == "https://app.example.test/projects"
    assert node.attrs["status"] == "404"
    assert validate_page(page, get_registry()) == []


def test_media_local_asset(tmp_path):
    asset = tmp_path / "pic.png"
    asset.write_bytes(b"\x89PNG\r\n\x1a\n")
    from conftest import write_page
    from pagedoc.parser import parse_page_file

    page_path = write_page(
        tmp_path, '<media src="pic.png" alt="Screenshot">\nCaption.\n</media>\n'
    )
    page = parse_page_file(page_path, get_registry())
    assert validate_page(page, get_registry()) == []
    node = _comp(page)
    assert node.attrs["src"] == "pic.png"
    assert node.attrs["fit"] == "contain"


def test_crlf_source_parses():
    from pagedoc.parser import parse_page_text

    text = "---\r\nid: p\ngroup: G\ntitle: T\r\n---\r\n\r\n<request>\r\nGET /x\r\n</request>\r\n"
    page = parse_page_text(text, "p.book.md")
    node = page.children[0]
    assert node.raw == "GET /x"


def test_attribute_quote_escape():
    page = parse_body('<note title="say \\"hi\\"">\nx\n</note>\n')
    assert _comp(page).attrs["title"] == 'say "hi"'
