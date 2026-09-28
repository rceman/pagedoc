"""Theme model + loader tests (M2 fixed-page geometry)."""

import pytest

from pagedoc.errors import PageDocError
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
