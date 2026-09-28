"""Front matter contract tests."""

import pytest

from pagedoc.errors import PageDocError
from pagedoc.parser import parse_page_text


def test_valid_front_matter():
    page = parse_page_text(
        "---\nid: p1\ngroup: G\ntitle: T\n---\n\nHello\n", "p.book.md"
    )
    assert page.metadata["id"] == "p1"
    assert page.metadata["group"] == "G"
    assert page.metadata["title"] == "T"
    assert page.kind == "content"


def test_front_matter_optional_keys():
    page = parse_page_text(
        "---\nid: p1\ngroup: G\ntitle: T\nkind: front-matter\ntemplate: cover\n---\n\nHi\n",
        "p.book.md",
    )
    assert page.kind == "front-matter"
    assert page.template == "cover"


def test_unknown_front_matter_keys_preserved():
    page = parse_page_text(
        "---\nid: p1\ngroup: G\ntitle: T\ncustom-key: 42\n---\n\nHi\n", "p.book.md"
    )
    assert page.metadata["custom-key"] == 42
    assert page.to_dict()["metadata"]["custom-key"] == 42


@pytest.mark.parametrize("missing", ["id", "group", "title"])
def test_missing_required_front_matter(missing):
    keys = {"id": "p1", "group": "G", "title": "T"}
    del keys[missing]
    fm = "---\n" + "\n".join(f"{k}: {v}" for k, v in keys.items()) + "\n---\n\nHi\n"
    with pytest.raises(PageDocError) as exc:
        parse_page_text(fm, "p.book.md")
    diag = exc.value.diagnostics[0]
    assert missing in diag.message
    assert diag.path == "p.book.md"


def test_no_front_matter():
    with pytest.raises(PageDocError) as exc:
        parse_page_text("Just markdown\n", "p.book.md")
    assert "front matter" in exc.value.diagnostics[0].message


def test_unclosed_front_matter():
    with pytest.raises(PageDocError) as exc:
        parse_page_text("---\nid: p1\ntitle: T\n", "p.book.md")
    assert "unclosed" in exc.value.diagnostics[0].message


def test_invalid_yaml_front_matter():
    with pytest.raises(PageDocError) as exc:
        parse_page_text("---\nid: [unclosed\n---\n\nHi\n", "p.book.md")
    assert "invalid YAML" in exc.value.diagnostics[0].message
