"""Supported public integration API (M3.2).

This module is the only supported entry point for consumer projects:

    compiled = pagedoc.compile_document("document.yaml")
    report   = pagedoc.inspect_document("document.yaml")
    lint     = pagedoc.lint_document("document.yaml")

Callers never orchestrate parser/theme/backend internals. The vector
PDF derived from the retained, measured backend document is the
canonical artifact; the flattened PDF is an optional raster derivative
(``pagedoc[raster]``).

Contract:

- public functions accept ``str`` / ``os.PathLike`` manifest paths;
- public functions never print, never change cwd, never fetch network;
- parse/validation/theme errors raise ``PageDocError`` carrying
  structured ``Diagnostic`` values;
- layout/composition failures return a ``CompiledDocument`` whose
  ``fits`` is False, whose ``diagnostics``/``inspection`` are
  inspectable, and which refuses final PDF emission;
- artifact writes are atomic (temp file + ``os.replace``) and return
  immutable ``ArtifactInfo`` metadata (path, bytes, SHA-256).
"""

from __future__ import annotations

import hashlib
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Union

from .document import Document, load_document
from .errors import Diagnostic, PageDocError
from .inspection import InspectionReport, build_inspection
from .pipeline import BuildResult, build_document
from .theme.loader import load_theme
from .theme.model import Theme

PathLike = Union[str, os.PathLike]


# ---------------------------------------------------------------------------
# artifact writing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArtifactInfo:
    """Metadata for one emitted artifact file."""

    kind: str  # "html" | "pdf" | "flattened-pdf"
    path: str
    bytes: int
    sha256: str


def _atomic_write(path: PathLike, data: bytes) -> str:
    """Write ``data`` to ``path`` atomically.

    The final path only appears after the complete bytes exist: a
    temporary file in the destination directory is fsync'd, then
    ``os.replace`` publishes it. Missing parents are created; temporary
    files are removed on failure. Returns the final path string.
    """

    out = os.fspath(path)
    parent = os.path.dirname(os.path.abspath(out))
    os.makedirs(parent, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".pagedoc-", dir=parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, out)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return out


def _write_artifact(path: PathLike, data: bytes, kind: str) -> ArtifactInfo:
    out = _atomic_write(path, data)
    return ArtifactInfo(
        kind=kind,
        path=out,
        bytes=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


# ---------------------------------------------------------------------------
# lint
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class LintResult:
    """Manifest+page validation result (no layout backend involved)."""

    document_id: str
    title: str
    manifest_path: str
    page_count: int


def lint_document(manifest_path: PathLike) -> LintResult:
    """Load and validate a document manifest + pages.

    Raises ``PageDocError`` with structured diagnostics on failure.
    Never prints; never touches the working directory.
    """

    doc = load_document(os.fspath(manifest_path))
    return LintResult(
        document_id=doc.doc_id,
        title=doc.title,
        manifest_path=doc.manifest_path,
        page_count=len(doc.pages),
    )


# ---------------------------------------------------------------------------
# compile
# ---------------------------------------------------------------------------


class CompiledDocument:
    """A compiled document: deterministic HTML + measured layout.

    Internal references are private; consumers interact only through the
    public properties/methods below.
    """

    __slots__ = ("_document", "_theme", "_build", "_inspection")

    def __init__(
        self, document: Document, theme: Theme, build: BuildResult
    ) -> None:
        self._document = document
        self._theme = theme
        self._build = build
        self._inspection: InspectionReport | None = None

    # ---- identity ---------------------------------------------------------
    @property
    def document_id(self) -> str:
        return self._document.doc_id

    @property
    def theme_id(self) -> str:
        return self._theme.id

    # ---- shape ------------------------------------------------------------
    @property
    def pages_logical(self) -> int:
        return len(self._document.pages)

    @property
    def pages_physical(self) -> int:
        return self._build.layout.physical_page_count

    @property
    def fits(self) -> bool:
        return self._build.fits

    @property
    def diagnostics(self) -> tuple[Diagnostic, ...]:
        return tuple(self._build.diagnostics)

    # ---- artifacts --------------------------------------------------------
    @property
    def html(self) -> str:
        """Deterministic generated HTML — available even when the build
        does not fit, so callers can inspect failures."""
        return self._build.html

    @property
    def inspection(self) -> InspectionReport:
        if self._inspection is None:
            self._inspection = InspectionReport(
                build_inspection(self._document, self._build, self._theme)
            )
        return self._inspection

    def _require_fits(self) -> None:
        if not self._build.fits:
            raise PageDocError(list(self._build.diagnostics))

    def pdf_bytes(self) -> bytes:
        """Canonical vector PDF bytes — the measured document, never
        re-laid-out. Refuses emission for a non-fitting build."""
        self._require_fits()
        assert self._build.rendered is not None
        return self._build.rendered.pdf_bytes()

    def flattened_pdf_bytes(self, *, dpi: int = 144) -> bytes:
        """Raster-flattened derivative of the canonical vector PDF.

        Requires the optional ``pagedoc[raster]`` dependencies. Never
        performs a second HTML layout pass.
        """
        self._require_fits()
        assert self._build.rendered is not None
        from .flatten import flatten_document_pdf_bytes

        return flatten_document_pdf_bytes(self._build.rendered, dpi=dpi)

    def write_html(self, path: PathLike) -> ArtifactInfo:
        """Atomically write the deterministic HTML (allowed for
        non-fitting builds as a debugging artifact)."""
        return _write_artifact(path, self._build.html.encode("utf-8"), "html")

    def write_pdf(self, path: PathLike) -> ArtifactInfo:
        return _write_artifact(path, self.pdf_bytes(), "pdf")

    def write_flattened_pdf(
        self, path: PathLike, *, dpi: int = 144
    ) -> ArtifactInfo:
        return _write_artifact(
            path, self.flattened_pdf_bytes(dpi=dpi), "flattened-pdf"
        )


def compile_document(manifest_path: PathLike) -> CompiledDocument:
    """Compile a PageDoc manifest into a public CompiledDocument.

    Runs the full authoritative pipeline — parse, validate, theme load,
    HTML render, backend layout, M3 composition recovery — and retains
    the measured backend document for serialization.
    """

    doc = load_document(os.fspath(manifest_path))
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    return CompiledDocument(doc, theme, build)


def inspect_document(manifest_path: PathLike) -> InspectionReport:
    """Compile and return the deterministic inspection report."""

    return compile_document(manifest_path).inspection
