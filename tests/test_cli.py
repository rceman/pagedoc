"""CLI contract tests: exit codes, diagnostics, render output."""

import json
import os

from conftest import write_page
from pagedoc.cli import main


def _write_document(tmp_path, pages: dict[str, str], extra_manifest: str = "") -> str:
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    for name, fm_body in pages.items():
        write_page(tmp_path, fm_body[1], name=f"pages/{name}", fm=fm_body[0])
    manifest = tmp_path / "document.yaml"
    entries = "\n".join(f"  - pages/{name}" for name in pages)
    manifest.write_text(
        f"id: doc\ntitle: Doc\n{extra_manifest}pages:\n{entries}\n", encoding="utf-8"
    )
    return str(manifest)


_GOOD_PAGE = ("---\nid: p{n}\ngroup: G\ntitle: T{n}\n---\n", "Body text.\n")


def test_lint_ok(tmp_path, capsys):
    manifest = _write_document(
        tmp_path,
        {
            "a.book.md": ("---\nid: a\ngroup: G\ntitle: A\n---\n", "Hello.\n"),
            "b.book.md": ("---\nid: b\ngroup: G\ntitle: B\n---\n", "World.\n"),
        },
    )
    assert main(["lint", manifest]) == 0
    out = capsys.readouterr()
    assert "OK" in out.out


def test_lint_fails_on_bad_page(tmp_path, capsys):
    manifest = _write_document(
        tmp_path,
        {
            "a.book.md": ("---\nid: a\ngroup: G\ntitle: A\n---\n", "<bogus>\nx\n</bogus>\n"),
        },
    )
    assert main(["lint", manifest]) == 1
    err = capsys.readouterr().err
    assert "unknown component 'bogus'" in err
    assert ".book.md:" in err


def test_lint_duplicate_page_ids(tmp_path, capsys):
    manifest = _write_document(
        tmp_path,
        {
            "a.book.md": ("---\nid: dup\ngroup: G\ntitle: A\n---\n", "x\n"),
            "b.book.md": ("---\nid: dup\ngroup: G\ntitle: B\n---\n", "y\n"),
        },
    )
    assert main(["lint", manifest]) == 1
    assert "duplicate page id 'dup'" in capsys.readouterr().err


def test_lint_missing_manifest(tmp_path, capsys):
    assert main(["lint", str(tmp_path / "nope.yaml")]) == 1
    assert "not found" in capsys.readouterr().err


def test_ast_command_outputs_json(tmp_path, capsys):
    page_path = write_page(tmp_path, "<request>\nGET /x\n</request>\n")
    assert main(["ast", page_path]) == 0
    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["schema_version"] == 1
    assert data["children"][0]["type"] == "request"


def test_ast_command_fails_on_invalid(tmp_path, capsys):
    page_path = write_page(tmp_path, "<unknown>\nx\n</unknown>\n")
    assert main(["ast", page_path]) == 1
    assert "unknown component" in capsys.readouterr().err


def test_render_command(tmp_path, capsys):
    manifest = _write_document(
        tmp_path,
        {"a.book.md": ("---\nid: a\ngroup: G\ntitle: A\n---\n", "Hello.\n")},
    )
    out_html = str(tmp_path / "out" / "doc.html")
    assert main(["render", manifest, "--html-out", out_html]) == 0
    with open(out_html, encoding="utf-8") as f:
        html = f.read()
    assert "pd-page" in html and "Hello." in html


def test_render_fails_on_invalid(tmp_path):
    manifest = _write_document(
        tmp_path,
        {"a.book.md": ("---\nid: a\ngroup: G\ntitle: A\n---\n", "<row>\n<request>\nG\n</request>\n</row>\n")},
    )
    out_html = str(tmp_path / "doc.html")
    assert main(["render", manifest, "--html-out", out_html]) == 1
    assert not os.path.exists(out_html)


def test_render_deterministic_bytes(tmp_path):
    manifest = _write_document(
        tmp_path,
        {
            "a.book.md": (
                "---\nid: a\ngroup: G\ntitle: A\n---\n",
                '<request title="R">\nGET /x\n</request>\n',
            ),
            "b.book.md": ("---\nid: b\ngroup: G\ntitle: B\n---\n", "Done.\n"),
        },
    )
    out1 = str(tmp_path / "r1.html")
    out2 = str(tmp_path / "r2.html")
    assert main(["render", manifest, "--html-out", out1]) == 0
    assert main(["render", manifest, "--html-out", out2]) == 0
    with open(out1, "rb") as f:
        b1 = f.read()
    with open(out2, "rb") as f:
        b2 = f.read()
    assert b1 == b2
