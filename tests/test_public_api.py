"""M3.2 public API contract tests.

The CLI and embedded consumers share one supported surface:
``pagedoc.compile_document`` / ``inspect_document`` / ``lint_document``.
"""

import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from conftest import REPO_ROOT, write_page  # noqa: E402

import pagedoc  # noqa: E402
from pagedoc.api import _atomic_write  # noqa: E402
from pagedoc.cli import main as cli_main  # noqa: E402
from pagedoc.errors import PageDocError  # noqa: E402
from pagedoc.inspection import INSPECTION_SCHEMA_VERSION  # noqa: E402

GALLERY = os.path.join(REPO_ROOT, "examples/layout-gallery/document.yaml")
COMPOSITION = os.path.join(
    REPO_ROOT, "examples/composition-gallery/document.yaml"
)
OVERFLOW_PROSE = os.path.join(
    REPO_ROOT, "tests/fixtures/overflow/prose/document.yaml"
)
BUILTIN_THEME = os.path.join(
    REPO_ROOT, "src/pagedoc/theme/builtin"
)


def _doc(tmp_path, body: str = "Body text.\n", extra_manifest: str = "") -> Path:
    (tmp_path / "pages").mkdir(parents=True, exist_ok=True)
    write_page(tmp_path, body, name="pages/p.book.md")
    manifest = tmp_path / "document.yaml"
    manifest.write_text(
        f"id: doc\ntitle: Doc\n{extra_manifest}pages:\n  - pages/p.book.md\n",
        encoding="utf-8",
    )
    return manifest


# ---------------- top-level exports -----------------------------------------


def test_top_level_exports():
    for name in pagedoc.__all__:
        assert hasattr(pagedoc, name), name
    assert pagedoc.compile_document is not None
    assert pagedoc.inspect_document is not None
    assert pagedoc.lint_document is not None
    # internals are not part of the supported top-level surface
    assert "Theme" not in pagedoc.__all__
    assert "BuildResult" not in pagedoc.__all__
    assert "RenderedDocument" not in pagedoc.__all__


def test_version_matches_installed_metadata():
    from importlib import metadata

    assert pagedoc.__version__ == metadata.version("pagedoc") == "0.1.0"


def test_compiled_hides_backend_internals(tmp_path):
    compiled = pagedoc.compile_document(_doc(tmp_path))
    for attr in ("theme", "build", "rendered", "document"):
        assert not hasattr(compiled, attr), attr


# ---------------- compile / lint --------------------------------------------


def test_compile_document_str_and_path(tmp_path):
    manifest = _doc(tmp_path)
    a = pagedoc.compile_document(str(manifest))
    b = pagedoc.compile_document(manifest)  # pathlib.Path
    assert a.fits and b.fits
    assert a.document_id == "doc"
    assert a.theme_id == "default"
    assert a.pages_logical == 1 == a.pages_physical
    assert a.html == b.html


def test_lint_document(tmp_path):
    result = pagedoc.lint_document(_doc(tmp_path))
    assert result.document_id == "doc"
    assert result.title == "Doc"
    assert result.page_count == 1
    assert result.manifest_path.endswith("document.yaml")


def test_lint_document_failure_raises(tmp_path):
    manifest = tmp_path / "document.yaml"
    manifest.write_text("id: d\ntitle: T\npages: [missing.book.md]\n")
    with pytest.raises(PageDocError):
        pagedoc.lint_document(manifest)


def test_compile_document_parse_error_raises(tmp_path):
    with pytest.raises(PageDocError) as e:
        pagedoc.compile_document(tmp_path / "nope.yaml")
    assert e.value.diagnostics


def test_compile_failing_layout_is_inspectable():
    compiled = pagedoc.compile_document(OVERFLOW_PROSE)
    assert compiled.fits is False
    assert compiled.diagnostics
    assert compiled.inspection.all_fit is False
    # HTML remains available for debugging even on a non-fitting build
    assert compiled.html.startswith("<!DOCTYPE")
    for emit in (
        compiled.pdf_bytes,
        compiled.flattened_pdf_bytes,
    ):
        with pytest.raises(PageDocError):
            emit()


def test_nonfitting_write_pdf_refuses(tmp_path):
    compiled = pagedoc.compile_document(OVERFLOW_PROSE)
    out = tmp_path / "bad.pdf"
    with pytest.raises(PageDocError):
        compiled.write_pdf(out)
    assert not out.exists()
    with pytest.raises(PageDocError):
        compiled.write_flattened_pdf(tmp_path / "bad.flat.pdf")
    # diagnostic HTML may still be written
    info = compiled.write_html(tmp_path / "diag.html")
    assert info.kind == "html" and Path(info.path).exists()


# ---------------- silence / cwd / paths -------------------------------------


def test_public_api_is_silent(tmp_path, capsys):
    manifest = _doc(tmp_path)
    pagedoc.lint_document(manifest)
    compiled = pagedoc.compile_document(manifest)
    pagedoc.inspect_document(manifest)
    compiled.pdf_bytes()
    out = capsys.readouterr()
    assert out.out == "" and out.err == ""


def test_unrelated_cwd_and_no_cwd_mutation(tmp_path, monkeypatch):
    manifest = _doc(tmp_path / "docdir")
    other = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)
    before = os.getcwd()
    compiled = pagedoc.compile_document(manifest)
    assert compiled.fits
    assert os.getcwd() == before
    assert pagedoc.lint_document(manifest).page_count == 1


def test_external_local_theme(tmp_path):
    # a consumer-owned theme directory: copied wholesale, referenced
    # relative to the document manifest
    shutil.copytree(BUILTIN_THEME, tmp_path / "mytheme")
    manifest = _doc(tmp_path, extra_manifest="theme: mytheme/theme.yaml\n")
    compiled = pagedoc.compile_document(manifest)
    assert compiled.fits
    assert compiled.theme_id == "default"  # theme.yaml id, not the path
    assert compiled.pdf_bytes().startswith(b"%PDF")


# ---------------- artifacts --------------------------------------------------


@pytest.fixture(scope="module")
def gallery_compiled(tmp_path_factory):
    return pagedoc.compile_document(GALLERY)


def test_artifact_info_metadata(tmp_path, gallery_compiled):
    for write, kind in (
        (gallery_compiled.write_html, "html"),
        (gallery_compiled.write_pdf, "pdf"),
        (gallery_compiled.write_flattened_pdf, "flattened-pdf"),
    ):
        out = tmp_path / "deep" / "nested" / f"doc.{kind}"
        info = write(out)
        data = Path(info.path).read_bytes()
        assert info.kind == kind
        assert info.bytes == len(data)
        assert info.sha256 == hashlib.sha256(data).hexdigest()
        # deterministic: identical rewrite
        assert write(out).sha256 == info.sha256
        # no temp files remain
        leftovers = [
            p for p in out.parent.iterdir() if p.name.startswith(".pagedoc-")
        ]
        assert leftovers == []


def test_atomic_write_failure_exposes_no_partial(tmp_path, monkeypatch):
    out = tmp_path / "final.bin"
    monkeypatch.setattr(
        os, "replace", lambda *_: (_ for _ in ()).throw(OSError("boom"))
    )
    with pytest.raises(OSError):
        _atomic_write(out, b"payload")
    assert not out.exists()
    assert [p.name for p in tmp_path.iterdir()] == []


def test_repeated_pdf_serialization_no_relayout(tmp_path):
    compiled = pagedoc.compile_document(_doc(tmp_path))
    passes_before = compiled._build.composition.layout_passes
    a = compiled.pdf_bytes()
    compiled.write_pdf(tmp_path / "a.pdf")
    b = compiled.pdf_bytes()
    assert a == b
    assert compiled._build.composition.layout_passes == passes_before


def test_flattened_pdf_bytes_no_relayout(tmp_path):
    compiled = pagedoc.compile_document(_doc(tmp_path))
    passes_before = compiled._build.composition.layout_passes
    flat = compiled.flattened_pdf_bytes(dpi=96)
    assert flat.startswith(b"%PDF")
    assert flat != compiled.pdf_bytes()
    assert compiled._build.composition.layout_passes == passes_before


def test_flatten_dpi_validation(tmp_path):
    compiled = pagedoc.compile_document(_doc(tmp_path))
    for bad in (0, -1, "72", 2.5, True):
        with pytest.raises(PageDocError):
            compiled.flattened_pdf_bytes(dpi=bad)


# ---------------- inspection schema -----------------------------------------


def test_inspection_schema_valid(tmp_path):
    report = pagedoc.inspect_document(_doc(tmp_path))
    payload = report.to_dict()
    assert payload["schema_version"] == INSPECTION_SCHEMA_VERSION == 1
    assert report.document_id == "doc"
    assert report.pages_logical == 1 == report.pages_physical
    assert report.all_fit is True
    assert payload["diagnostics"] == []
    page = payload["pages"][0]
    for key in (
        "blocks_expected",
        "blocks_rendered",
        "blocks_missing",
        "overflow_px",
        "resolved",
    ):
        assert key in page
    assert page["blocks_expected"] >= 1
    assert page["blocks_missing"] == 0
    # deterministic serialization
    assert report.to_json() == report.to_json()
    assert report.to_json().endswith("\n")
    assert json.loads(report.to_json()) == payload
    # to_dict returns an equivalent independent copy
    assert report.to_dict() == payload
    payload["document"] = "mutated"
    assert report.to_dict()["document"] == "doc"


def test_inspection_failure_schema():
    report = pagedoc.inspect_document(OVERFLOW_PROSE)
    payload = report.to_dict()
    assert payload["all_fit"] is False
    assert payload["diagnostics"], "build failure must appear in inspection"
    d = payload["diagnostics"][0]
    assert set(d) == {"path", "line", "col", "message"}
    assert payload["pages"][0]["fit"] is False


def test_all_fit_reflects_diagnostics():
    # all_fit must never be true while build diagnostics exist
    report = pagedoc.inspect_document(OVERFLOW_PROSE)
    compiled = pagedoc.compile_document(OVERFLOW_PROSE)
    assert report.all_fit == compiled.fits is False


# ---------------- CLI / API parity -------------------------------------------


def test_cli_api_parity(tmp_path, capsys):
    manifest = str(_doc(tmp_path / "d1"))
    cli_html = tmp_path / "cli.html"
    cli_pdf = tmp_path / "cli.pdf"
    cli_flat = tmp_path / "cli.flat.pdf"
    assert (
        cli_main(
            [
                "render",
                manifest,
                "--html-out",
                str(cli_html),
                "--pdf-out",
                str(cli_pdf),
                "--flattened-pdf-out",
                str(cli_flat),
                "--flatten-dpi",
                "96",
            ]
        )
        == 0
    )
    capsys.readouterr()

    assert cli_main(["inspect", manifest, "--json"]) == 0
    cli_inspect = json.loads(capsys.readouterr().out)

    compiled = pagedoc.compile_document(manifest)
    assert cli_html.read_bytes() == compiled.html.encode("utf-8")
    assert cli_pdf.read_bytes() == compiled.pdf_bytes()
    assert cli_flat.read_bytes() == compiled.flattened_pdf_bytes(dpi=96)
    assert cli_inspect == compiled.inspection.to_dict()

    capsys.readouterr()
    assert cli_main(["lint", manifest]) == 0
    assert "OK" in capsys.readouterr().out


def test_cli_failure_paths(tmp_path, capsys):
    pdf_out = tmp_path / "nope.pdf"
    assert cli_main(["render", OVERFLOW_PROSE, "--pdf-out", str(pdf_out)]) == 1
    assert not pdf_out.exists()
    assert cli_main(["inspect", OVERFLOW_PROSE]) == 1
    capsys.readouterr()


# ---------------- composition rename regression -----------------------------


def test_composition_renamed_fixture_selections():
    report = pagedoc.inspect_document(COMPOSITION)
    payload = report.to_dict()
    assert payload["pages_logical"] == 6 == payload["pages_physical"]
    assert payload["all_fit"] is True
    comp = payload["composition"]
    assert comp["layout_passes"] == 19
    assert sum(p["evaluated"] for p in comp["pages"]) == 19
    expected = {
        "cmp-compare-recovery": {"compare": "vertical"},
        "cmp-localized-auto": {"compare": "vertical", "flow": "horizontal"},
        "cmp-row-recovery": {"row": "wide-right"},
        "cmp-mixed-recovery": {"row": "wide-right", "compare": "vertical"},
        "cmp-flow-recovery": {"flow": "vertical"},
        "cmp-long-compare-containment": {"compare": "vertical"},
    }
    for pt in comp["pages"]:
        node_component = {
            d["node_id"]: d["component"] for d in pt["decisions"]
        }
        actual = {
            node_component[key.rsplit(":", 1)[0]]: value
            for key, value in (pt["selected"] or {}).items()
        }
        assert actual == expected[pt["page_id"]], pt["page_id"]
