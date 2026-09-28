"""Theme loading and validation (M2 fixed-page model).

Manifest ``theme`` values:

- missing / ``default`` / ``builtin``: the packaged reference theme
  (``pagedoc/theme/builtin/``);
- a path (relative to the document manifest) to a ``theme.yaml``.

Everything a theme references (css, font sources) is local; nothing is
fetched remotely.
"""

from __future__ import annotations

import os
from importlib import resources

import yaml

from ..errors import Diagnostic, PageDocError
from .model import FontSpec, Rect, Theme

_BUILTIN_DIR = resources.files("pagedoc.theme").joinpath("builtin")


def load_theme(value: str | None, manifest_dir: str) -> Theme:
    if value in (None, "default", "builtin"):
        return _load_theme_text(
            theme_text=(_BUILTIN_DIR / "theme.yaml").read_text(encoding="utf-8"),
            theme_path="builtin:theme.yaml",
            theme_dir=str(_BUILTIN_DIR),
        )
    theme_path = os.path.normpath(os.path.join(manifest_dir, value))
    if not os.path.isfile(theme_path):
        raise PageDocError(
            Diagnostic(theme_path, 1, 1, f"theme manifest not found: '{value}'")
        )
    with open(theme_path, "r", encoding="utf-8") as f:
        text = f.read()
    return _load_theme_text(text, theme_path, os.path.dirname(theme_path))


def _err(path: str, message: str) -> PageDocError:
    return PageDocError(Diagnostic(path, 1, 1, message))


def _load_theme_text(theme_text: str, theme_path: str, theme_dir: str) -> Theme:
    try:
        data = yaml.safe_load(theme_text)
    except yaml.YAMLError as e:
        raise _err(theme_path, f"invalid theme manifest: {e}") from e
    if not isinstance(data, dict):
        raise _err(theme_path, "theme manifest must be a YAML mapping")
    theme_id = data.get("id")
    if not isinstance(theme_id, str) or not theme_id:
        raise _err(theme_path, "theme manifest requires an 'id' string")

    page = data.get("page")
    if not isinstance(page, dict):
        raise _err(theme_path, "theme requires a 'page' mapping")
    unit = page.get("unit", "px")
    if unit != "px":
        raise _err(theme_path, f"theme page unit must be 'px'; found '{unit}'")
    width = _positive_number(page, "width", theme_path, "page")
    height = _positive_number(page, "height", theme_path, "page")

    regions_raw = data.get("regions")
    if not isinstance(regions_raw, dict):
        raise _err(theme_path, "theme requires a 'regions' mapping")
    regions: dict[str, Rect] = {}
    for name, r in regions_raw.items():
        if not isinstance(r, dict):
            raise _err(theme_path, f"region '{name}' must be a mapping")
        rect = Rect(
            x=_number(r, "x", theme_path, f"regions.{name}"),
            y=_number(r, "y", theme_path, f"regions.{name}"),
            width=_positive_number(r, "width", theme_path, f"regions.{name}"),
            height=_positive_number(r, "height", theme_path, f"regions.{name}"),
        )
        if rect.x + rect.width > width:
            raise _err(
                theme_path,
                f"region '{name}' extends past the right page edge "
                f"(x={rect.x:g} + width={rect.width:g} > page width {width:g})",
            )
        if rect.y + rect.height > height:
            raise _err(
                theme_path,
                f"region '{name}' extends past the bottom page edge "
                f"(y={rect.y:g} + height={rect.height:g} > page height {height:g})",
            )
        regions[str(name)] = rect
    if "content" not in regions:
        raise _err(theme_path, "theme regions must define 'content'")

    spacing: dict[str, float] = {}
    for k, v in (data.get("spacing") or {}).items():
        if not isinstance(v, (int, float)) or v < 0:
            raise _err(theme_path, f"spacing '{k}' must be a non-negative number")
        spacing[str(k)] = float(v)

    splits: dict[str, tuple[float, ...]] = {}
    for k, v in (data.get("splits") or {}).items():
        if not isinstance(v, list) or len(v) < 2 or not all(
            isinstance(x, (int, float)) and x > 0 for x in v
        ):
            raise _err(theme_path, f"split '{k}' must be a list of positive numbers")
        splits[str(k)] = tuple(float(x) for x in v)

    fonts: dict[str, FontSpec] = {}
    for k, v in (data.get("fonts") or {}).items():
        if not isinstance(v, dict) or not isinstance(v.get("family"), str):
            raise _err(theme_path, f"font role '{k}' requires a 'family' string")
        source = v.get("source")
        if source is not None:
            if not isinstance(source, str):
                raise _err(theme_path, f"font role '{k}' source must be a string")
            if _is_remote(source):
                raise _err(theme_path, f"font role '{k}' source must be a local file")
            font_path = os.path.normpath(os.path.join(theme_dir, source))
            if not os.path.isfile(font_path):
                raise _err(theme_path, f"font file not found: '{source}'")
        fonts[str(k)] = FontSpec(family=v["family"], source=source)

    css_ref = data.get("css")
    css_text = ""
    if css_ref is not None:
        if not isinstance(css_ref, str) or _is_remote(css_ref):
            raise _err(theme_path, "theme 'css' must be a local file path")
        css_path = os.path.normpath(os.path.join(theme_dir, css_ref))
        if not os.path.isfile(css_path):
            raise _err(theme_path, f"theme CSS file not found: '{css_ref}'")
        with open(css_path, "r", encoding="utf-8") as f:
            css_text = f.read()

    return Theme(
        id=theme_id,
        page_width=width,
        page_height=height,
        regions=regions,
        spacing=spacing,
        splits=splits,
        fonts=fonts,
        css=css_text,
        base_dir=theme_dir,
    )


def _is_remote(value: str) -> bool:
    return "://" in value or value.startswith("//")


def _number(mapping: dict, key: str, path: str, ctx: str) -> float:
    v = mapping.get(key)
    if not isinstance(v, (int, float)) or isinstance(v, bool) or v < 0:
        raise _err(path, f"{ctx}.{key} must be a non-negative number")
    return float(v)


def _positive_number(mapping: dict, key: str, path: str, ctx: str) -> float:
    v = _number(mapping, key, path, ctx)
    if v <= 0:
        raise _err(path, f"{ctx}.{key} must be positive")
    return v


def theme_geometry_css(theme: Theme, base_dir: str | None = None) -> str:
    """Generate the geometry-owned rules from a validated theme.

    Theme values become generated CSS — authored source stays free of
    pixel geometry while the generated document carries exact placement.
    ``base_dir`` is the document base directory used to express local
    font sources as relative URLs (never absolute machine paths).
    """

    w, h = theme.page_width, theme.page_height
    lines = [
        f"@page {{ size: {w:g}px {h:g}px; margin: 0; }}",
        f".pd-page {{ width: {w:g}px; height: {h:g}px; }}",
    ]
    for name in sorted(theme.regions):
        r = theme.regions[name]
        lines.append(
            f".pd-region-{name} {{ left: {r.x:g}px; top: {r.y:g}px; "
            f"width: {r.width:g}px; height: {r.height:g}px; }}"
        )
    if theme.spacing.get("block") is not None:
        b = theme.spacing["block"]
        lines.append(f".pd-page-content > * {{ margin-bottom: {b:g}px; }}")
    if theme.spacing.get("row-gap") is not None:
        g = theme.spacing["row-gap"]
        lines.append(f".pd-row {{ gap: {g:g}px; }}")
        lines.append(f".pd-flow-steps {{ gap: {g:g}px; }}")
    for name, ratios in sorted(theme.splits.items()):
        for idx, ratio in enumerate(ratios):
            sel = ":first-child" if idx == 0 else ":last-child"
            if len(ratios) > 2:
                sel = f":nth-child({idx + 1})"
            lines.append(
                f".pd-row--split-{name} .pd-row-cell{sel} {{ flex: {ratio:g} 1 0; }}"
            )
    for role, font in sorted(theme.fonts.items()):
        if font.source:
            src = font.source
            if base_dir and theme.base_dir:
                src = os.path.relpath(
                    os.path.join(theme.base_dir, font.source), base_dir
                ).replace(os.sep, "/")
            lines.append(
                f"@font-face {{ font-family: 'pd-{role}'; "
                f"src: url('{src}'); }}"
            )
            lines.append(
                f":root {{ --pd-font-{role}: 'pd-{role}', {font.family}; }}"
            )
        else:
            lines.append(f":root {{ --pd-font-{role}: {font.family}; }}")
    return "\n".join(lines)
