"""PageDoc — deterministic Markdown-first authoring and fixed-page
rendering engine.

Supported public surface (see docs/PUBLIC_API.md):

    import pagedoc

    compiled = pagedoc.compile_document("document.yaml")
    report   = pagedoc.inspect_document("document.yaml")
    lint     = pagedoc.lint_document("document.yaml")

Everything else in the package is internal implementation detail and
may change between versions.
"""

from importlib import metadata as _metadata

from .api import (
    ArtifactInfo,
    CompiledDocument,
    InspectionReport,
    LintResult,
    compile_document,
    inspect_document,
    lint_document,
)
from .errors import Diagnostic, PageDocError

try:
    __version__ = _metadata.version("pagedoc")
except _metadata.PackageNotFoundError:  # source tree without install
    __version__ = "0.1.0"

__all__ = [
    "ArtifactInfo",
    "CompiledDocument",
    "Diagnostic",
    "InspectionReport",
    "LintResult",
    "PageDocError",
    "__version__",
    "compile_document",
    "inspect_document",
    "lint_document",
]
