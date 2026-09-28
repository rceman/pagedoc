"""Structural error and diagnostic tests."""

import pytest

from conftest import parse_body, write_page
from pagedoc.errors import PageDocError
from pagedoc.parser import parse_page_file, parse_page_text
from pagedoc.registry import get_registry
from pagedoc.validation import validate_page


def _diag_of(body, match):
    with pytest.raises(PageDocError) as exc:
        parse_body(body)
    diag = exc.value.diagnostics[0]
    assert match in diag.message
    return diag


def test_unknown_component():
    diag = _diag_of("<widget>\nstuff\n</widget>\n", "unknown component 'widget'")
    assert diag.line == 7


def test_unknown_component_div():
    _diag_of("<div>\nstuff\n</div>\n", "unknown component 'div'")


def test_unknown_attribute():
    _diag_of('<request foo="bar">\nGET /x\n</request>\n', "unknown attribute 'foo'")


def test_duplicate_attribute():
    _diag_of(
        '<request title="a" title="b">\nGET /x\n</request>\n',
        "duplicate attribute 'title'",
    )


def test_malformed_attribute_unquoted():
    _diag_of("<request title=abc>\nGET /x\n</request>\n", "double-quoted")


def test_malformed_attribute_no_equals():
    _diag_of('<request title>\nGET /x\n</request>\n', "malformed attribute")


def test_malformed_attribute_unterminated():
    _diag_of('<request title="abc>\nGET /x\n</request>\n', "unterminated value")


def test_invalid_enum_value():
    _diag_of(
        '<row split="huge">\n<request>\nG\n</request>\n<note>\nn\n</note>\n</row>\n',
        "must be one of",
    )


def test_mismatched_close_tag():
    diag = _diag_of("<request>\nGET /x\n</response>\n", "mismatched closing tag </response>")
    assert diag.line == 9


def test_missing_close_tag():
    diag = _diag_of("<request>\nGET /x\n", "unclosed component <request>")
    assert diag.line == 7  # points at opening tag


def test_stray_close_tag_at_root():
    _diag_of("Hello\n\n</request>\n", "unexpected closing tag")


def test_row_wrong_child_count():
    page = parse_body(
        "<row>\n\n<request>\nGET /x\n</request>\n\n</row>\n"
    )
    diags = validate_page(page, get_registry())
    assert len(diags) == 1
    assert "row requires exactly 2 children; found 1" in diags[0].message


def test_row_too_many_children():
    page = parse_body(
        "<row>\n<request>\nG\n</request>\n<request>\nG\n</request>\n"
        "<request>\nG\n</request>\n</row>\n"
    )
    diags = validate_page(page, get_registry())
    assert any("exactly 2 children; found 3" in d.message for d in diags)


def test_prose_inside_row_rejected():
    _diag_of(
        "<row>\n\njust some text\n\n<request>\nG\n</request>\n<note>\nn\n</note>\n</row>\n",
        "plain prose is not allowed inside <row>",
    )


def test_step_outside_flow_rejected():
    page = parse_body('<step label="X">\ntext\n</step>\n')
    diags = validate_page(page, get_registry())
    assert any("not allowed inside 'page'" in d.message for d in diags)


def test_step_inside_row_rejected():
    page = parse_body(
        "<row>\n<step label=\"X\">\nt\n</step>\n<note>\nn\n</note>\n</row>\n"
    )
    diags = validate_page(page, get_registry())
    assert any("not allowed inside <row>" in d.message for d in diags)


def test_flow_step_count_bounds():
    page = parse_body(
        "<flow>\n<step label=\"a\">\nx\n</step>\n</flow>\n"
    )
    diags = validate_page(page, get_registry())
    assert any("between 2 and 6" in d.message for d in diags)


def test_flow_rejects_non_step_children():
    page = parse_body(
        "<flow>\n<step label=\"a\">\nx\n</step>\n<step label=\"b\">\ny\n</step>\n"
        "<request>\nG\n</request>\n</flow>\n"
    )
    diags = validate_page(page, get_registry())
    assert any("not allowed inside <flow>" in d.message for d in diags)


def test_component_inside_markdown_body_rejected():
    _diag_of(
        "<note>\n<request>\nGET /x\n</request>\n</note>\n",
        "not allowed inside <note>",
    )


def test_browser_requires_single_url_line():
    page = parse_body("<browser>\n\n</browser>\n")
    diags = validate_page(page, get_registry())
    assert any("exactly one non-empty URL line" in d.message for d in diags)

    page2 = parse_body("<browser>\nhttps://a.test\nhttps://b.test\n</browser>\n")
    diags2 = validate_page(page2, get_registry())
    assert any("exactly one non-empty URL line" in d.message for d in diags2)


def test_missing_media_asset(tmp_path):
    page_path = write_page(
        tmp_path, '<media src="missing.png" alt="Gone">\n</media>\n'
    )
    page = parse_page_file(page_path, get_registry())
    diags = validate_page(page, get_registry())
    assert any("media asset not found" in d.message for d in diags)


def test_remote_media_rejected(tmp_path):
    page_path = write_page(
        tmp_path, '<media src="https://evil.test/x.png" alt="Remote">\n</media>\n'
    )
    page = parse_page_file(page_path, get_registry())
    diags = validate_page(page, get_registry())
    assert any("must be a local path" in d.message for d in diags)


def test_media_missing_required_attrs(tmp_path):
    _diag_of("<media>\ncaption\n</media>\n", "requires attribute 'src'")


def test_compare_labels_format():
    page = parse_body(
        '<compare labels="justone">\n<response>\n{}\n</response>\n<response>\n{}\n</response>\n</compare>\n'
    )
    diags = validate_page(page, get_registry())
    assert any("labels" in d.message and "|" in d.message for d in diags)


def test_opening_tag_with_trailing_content():
    _diag_of(
        "<request> GET /x\n</request>\n",
        "must be the only content on its line",
    )


def test_diagnostics_carry_source_location():
    try:
        parse_body("<request>\nGET /x\n</response>\n")
    except PageDocError as e:
        d = e.diagnostics[0]
        assert d.path == "test.book.md"
        assert d.line == 9
        assert d.col == 1
