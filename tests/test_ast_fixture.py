"""Golden AST contract fixture + serialization determinism."""

import json
import os

import pytest

from conftest import parse_body
from pagedoc.ast import dumps_page
from pagedoc.parser import parse_page_file, parse_page_text
from pagedoc.registry import get_registry

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")

# The golden fixture records the repo-relative source path so serialized
# output is stable across machines and working directories.
FIXTURE_SRC_PATH = "tests/fixtures/request-response.book.md"


def _parse_fixture():
    with open(os.path.join(FIXTURES, "request-response.book.md"), encoding="utf-8") as f:
        return parse_page_text(f.read(), FIXTURE_SRC_PATH, get_registry())


def test_request_response_fixture_matches_contract():
    page = _parse_fixture()
    actual = dumps_page(page)
    with open(os.path.join(FIXTURES, "request-response.ast.json"), encoding="utf-8") as f:
        expected = f.read()
    assert actual == expected


def test_ast_semantic_content_matches_fixture():
    page = _parse_fixture()
    with open(os.path.join(FIXTURES, "request-response.ast.json"), encoding="utf-8") as f:
        expected = json.load(f)
    assert page.to_dict() == expected


def test_markdown_subtree_fixture_matches_contract():
    src = os.path.join(FIXTURES, "markdown-note.book.md")
    with open(src, encoding="utf-8") as f:
        page = parse_page_text(
            f.read(), "tests/fixtures/markdown-note.book.md", get_registry()
        )
    with open(os.path.join(FIXTURES, "markdown-note.ast.json"), encoding="utf-8") as f:
        expected = f.read()
    assert dumps_page(page) == expected


def test_ast_serialization_is_deterministic():
    body = (
        "Intro paragraph with `code`.\n\n"
        "| A | B |\n| --- | --- |\n| 1 | 2 |\n\n"
        '<row split="wide-left">\n\n<request title="R">\nGET /x\n</request>\n\n'
        "<note>\nNote *text*.\n</note>\n\n</row>\n\n"
        "<flow>\n<step label=\"a\">\nx\n</step>\n<step label=\"b\">\ny\n</step>\n</flow>\n"
    )
    out1 = dumps_page(parse_body(body))
    out2 = dumps_page(parse_body(body))
    assert out1 == out2
    # also: parsing twice yields equal AST dicts
    assert parse_body(body).to_dict() == parse_body(body).to_dict()


def test_ast_schema_version():
    page = parse_body("text\n")
    assert page.to_dict()["schema_version"] == 1
    assert page.to_dict()["type"] == "page"
    assert "source" in page.to_dict()


def test_attribute_order_does_not_affect_ast():
    a = parse_body('<row split="equal" align="stretch">\n<request>\nG\n</request>\n<note>\nn\n</note>\n</row>\n')
    b = parse_body('<row align="stretch" split="equal">\n<request>\nG\n</request>\n<note>\nn\n</note>\n</row>\n')
    assert a.to_dict()["children"][0]["attrs"] == b.to_dict()["children"][0]["attrs"]
