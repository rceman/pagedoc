"""Document manifest loading and document-level validation.

A manifest is YAML with required keys ``id``, ``title`` and ``pages``
(page paths resolved relative to the manifest file). ``theme`` is
optional and selects the reference theme by name or a theme.yaml path.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field

import yaml

from .ast import PageNode
from .errors import Diagnostic, PageDocError
from .parser import parse_page_file
from .registry import ComponentSpec, get_registry
from .validation import validate_page


@dataclass
class Document:
    """A loaded and validated PageDoc document."""

    manifest_path: str
    manifest_dir: str
    doc_id: str
    title: str
    theme: str | None
    page_paths: list[str]
    pages: list[PageNode] = field(default_factory=list)


@dataclass
class _Manifest:
    doc_id: str
    title: str
    theme: str | None
    pages: list[str]


def _load_manifest(manifest_path: str) -> _Manifest:
    try:
        with open(manifest_path, "r", encoding="utf-8-sig") as f:
            data = yaml.safe_load(f.read())
    except FileNotFoundError as e:
        raise PageDocError(
            Diagnostic(manifest_path, 1, 1, f"manifest file not found: {manifest_path}")
        ) from e
    except yaml.YAMLError as e:
        raise PageDocError(
            Diagnostic(manifest_path, 1, 1, f"invalid YAML manifest: {e}")
        ) from e
    if not isinstance(data, dict):
        raise PageDocError(
            Diagnostic(manifest_path, 1, 1, "document manifest must be a YAML mapping")
        )
    for key in ("id", "title"):
        if not isinstance(data.get(key), str) or not data[key]:
            raise PageDocError(
                Diagnostic(manifest_path, 1, 1, f"manifest requires a non-empty string key '{key}'")
            )
    pages = data.get("pages")
    if not isinstance(pages, list) or not all(isinstance(p, str) for p in pages):
        raise PageDocError(
            Diagnostic(manifest_path, 1, 1, "manifest key 'pages' must be a list of page paths")
        )
    theme = data.get("theme")
    if theme is not None and not isinstance(theme, str):
        raise PageDocError(
            Diagnostic(manifest_path, 1, 1, "manifest key 'theme' must be a string")
        )
    return _Manifest(doc_id=data["id"], title=data["title"], theme=theme, pages=pages)


def load_document(
    manifest_path: str, registry: dict[str, ComponentSpec] | None = None
) -> Document:
    """Load a manifest and parse+validate every page.

    Raises ``PageDocError`` carrying all collected diagnostics so the CLI
    can report every page error in one pass.
    """

    reg = registry if registry is not None else get_registry()
    manifest_path = os.path.normpath(manifest_path)
    manifest_dir = os.path.dirname(manifest_path) or "."
    manifest = _load_manifest(manifest_path)

    diagnostics: list[Diagnostic] = []
    seen_paths: set[str] = set()
    page_paths: list[str] = []
    for entry in manifest.pages:
        resolved = os.path.normpath(os.path.join(manifest_dir, entry))
        if resolved in seen_paths:
            diagnostics.append(
                Diagnostic(manifest_path, 1, 1, f"duplicate page path in manifest: '{entry}'")
            )
            continue
        seen_paths.add(resolved)
        page_paths.append(resolved)

    pages: list[PageNode] = []
    seen_ids: dict[str, str] = {}
    for page_path in page_paths:
        if not os.path.isfile(page_path):
            diagnostics.append(
                Diagnostic(manifest_path, 1, 1, f"page file not found: '{page_path}'")
            )
            continue
        try:
            page = parse_page_file(page_path, reg)
        except PageDocError as e:
            diagnostics.extend(e.diagnostics)
            continue
        diagnostics.extend(validate_page(page, reg))
        page_id = page.page_id
        if page_id in seen_ids:
            diagnostics.append(
                Diagnostic(
                    page.source.path,
                    page.source.start_line,
                    1,
                    f"duplicate page id '{page_id}'; already used by '{seen_ids[page_id]}'",
                )
            )
        else:
            seen_ids[page_id] = page.source.path
        pages.append(page)

    if diagnostics:
        raise PageDocError(diagnostics)

    return Document(
        manifest_path=manifest_path,
        manifest_dir=manifest_dir,
        doc_id=manifest.doc_id,
        title=manifest.title,
        theme=manifest.theme,
        page_paths=page_paths,
        pages=pages,
    )
