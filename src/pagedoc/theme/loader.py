"""Theme loading for M1.

Supported values for the manifest ``theme`` key:

- missing / ``default`` / ``builtin``: the built-in reference theme;
- a path to a ``theme.yaml`` manifest (relative to the document
  manifest) with ``id`` and ``css`` keys. The CSS file is local and is
  inlined into generated HTML; nothing is fetched remotely.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import yaml

from ..errors import Diagnostic, PageDocError
from .default import DEFAULT_CSS


@dataclass(frozen=True)
class Theme:
    id: str
    css: str


def load_theme(value: str | None, manifest_dir: str) -> Theme:
    if value in (None, "default", "builtin"):
        return Theme(id="default", css=DEFAULT_CSS)
    theme_path = os.path.normpath(os.path.join(manifest_dir, value))
    if not os.path.isfile(theme_path):
        raise PageDocError(
            Diagnostic(theme_path, 1, 1, f"theme manifest not found: '{value}'")
        )
    try:
        with open(theme_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f.read())
    except yaml.YAMLError as e:
        raise PageDocError(
            Diagnostic(theme_path, 1, 1, f"invalid theme manifest: {e}")
        ) from e
    if not isinstance(data, dict) or not isinstance(data.get("id"), str):
        raise PageDocError(
            Diagnostic(theme_path, 1, 1, "theme manifest requires an 'id' string")
        )
    css_ref = data.get("css")
    css_text = ""
    if css_ref is not None:
        if not isinstance(css_ref, str):
            raise PageDocError(
                Diagnostic(theme_path, 1, 1, "theme key 'css' must be a string path")
            )
        css_path = os.path.normpath(os.path.join(os.path.dirname(theme_path), css_ref))
        if not os.path.isfile(css_path):
            raise PageDocError(
                Diagnostic(theme_path, 1, 1, f"theme CSS file not found: '{css_ref}'")
            )
        with open(css_path, "r", encoding="utf-8") as f:
            css_text = f.read()
    return Theme(id=data["id"], css=css_text)
