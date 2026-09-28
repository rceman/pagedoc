"""Markdown baseline + table tests."""

from conftest import parse_body

from pagedoc.ast import ComponentNode, MarkdownNode


def _types(nodes):
    return [n.type for n in nodes]


def test_paragraph():
    page = parse_body("Hello world\n")
    assert _types(page.children) == ["paragraph"]
    para = page.children[0]
    assert para.children[0].type == "text"
    assert para.children[0].text == "Hello world"


def test_heading_and_inline():
    page = parse_body("## Title\n\nSome *emphasis* and **strong** and `code`.\n")
    types = _types(page.children)
    assert types == ["heading", "paragraph"]
    assert page.children[0].attrs["level"] == 2
    inline_types = _types(page.children[1].children)
    assert "emphasis" in inline_types and "strong" in inline_types and "code_inline" in inline_types


def test_lists_and_links():
    page = parse_body("- a\n- b\n\n1. x\n2. y\n\n[link](https://example.test)\n")
    types = _types(page.children)
    assert types == ["bullet_list", "ordered_list", "paragraph"]
    assert len(page.children[0].children) == 2
    assert page.children[2].children[0].type == "link"
    assert page.children[2].children[0].attrs["href"] == "https://example.test"


def test_fenced_code_block():
    page = parse_body("```sql\nSELECT 1;\n```\n")
    node = page.children[0]
    assert node.type == "code_block"
    assert node.attrs["lang"] == "sql"
    assert node.text == "SELECT 1;"


def test_markdown_table():
    page = parse_body(
        "| Account | Role |\n| --- | --- |\n| John | Admin |\n| Bob | Member |\n"
    )
    node = page.children[0]
    assert node.type == "table"
    rows = node.children
    assert all(r.type == "table_row" for r in rows)
    assert rows[0].attrs["header"] is True
    assert rows[0].children[0].attrs["header"] is True
    assert rows[0].children[0].children[0].text == "Account"
    assert rows[1].attrs["header"] is False
    assert len(rows) == 3


def test_source_spans_on_markdown_nodes():
    page = parse_body("First\n\nSecond\n")
    para1, para2 = page.children
    assert para1.source.start_line == 7  # after 5 fm lines + blank
    assert para2.source.start_line == 9


def test_html_like_text_in_markdown_stays_text():
    page = parse_body("A literal <img src=\"/x.png\"> inline.\n")
    assert page.children[0].type == "paragraph"
    joined = "".join(c.text or "" for c in page.children[0].children)
    assert "<img" in joined


def test_tag_like_lines_inside_fenced_code_stay_code():
    page = parse_body("```\n<request>\nGET /x\n</request>\n```\n\nAfter.\n")
    assert page.children[0].type == "code_block"
    assert "<request>" in (page.children[0].text or "")
    assert page.children[1].type == "paragraph"


def test_component_close_inside_fenced_markdown_body():
    page = parse_body(
        "<note>\n```\n</note>\n```\n\nAfter fence.\n</note>\n"
    )
    note = page.children[0]
    assert note.name == "note"
    assert note.source.end_line == 13  # closes at the real </note>, not the fenced one
    types = [n.type for n in note.body]
    assert types == ["code_block", "paragraph"]
