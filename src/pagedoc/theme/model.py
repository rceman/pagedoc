"""Fixed-page theme model.

A theme owns all physical geometry: page size, named regions, spacing
tokens, split ratios and fonts. Authored ``*.book.md`` source never
carries pixel geometry (THEME_SPEC.md).
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Rect:
    """A named page region, in theme units (px)."""

    x: float
    y: float
    width: float
    height: float


@dataclass(frozen=True)
class FontSpec:
    """One typography role. ``source`` is a local file inside the theme
    directory; when absent the family falls back to system fonts."""

    family: str
    source: str | None = None


@dataclass(frozen=True)
class Theme:
    """A validated fixed-page theme."""

    id: str
    page_width: float
    page_height: float
    regions: dict[str, Rect] = field(default_factory=dict)
    spacing: dict[str, float] = field(default_factory=dict)
    splits: dict[str, tuple[float, ...]] = field(default_factory=dict)
    fonts: dict[str, FontSpec] = field(default_factory=dict)
    css: str = ""
    base_dir: str | None = None  # filesystem dir for font/css resolution

    @property
    def content_region(self) -> Rect:
        return self.regions["content"]

    def spacing_token(self, name: str, default: float = 0.0) -> float:
        return self.spacing.get(name, default)

    @property
    def typography_portable(self) -> bool:
        """True when every font role is backed by a pinned local font file.

        System-font themes are allowed but their layout metrics may vary
        across hosts (THEME_SPEC.md portability contract).
        """

        return bool(self.fonts) and all(f.source for f in self.fonts.values())
