"""Component registry: the canonical v1 component contract.

Every consumer (parser, validator, renderer, CLI) reads component rules
from these descriptors. Nothing else may hardcode per-component
structural rules.

Body modes (AUTHORING_SPEC.md section 6):

- ``raw``: preserved authored text; no recursive parsing.
- ``markdown``: body is parsed as Markdown.
- ``children``: body holds registered child components only.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .errors import Diagnostic


class BodyMode(str, Enum):
    RAW = "raw"
    MARKDOWN = "markdown"
    CHILDREN = "children"


@dataclass(frozen=True)
class AttributeSpec:
    """One allowed attribute on a component."""

    name: str
    required: bool = False
    default: Any = None
    enum: tuple[str, ...] | None = None


# Pseudo-parent name for a component placed at page root.
ROOT_PARENT = "page"

#: Components that may appear at page root and inside containers.
TOP_LEVEL_COMPONENTS: frozenset[str] = frozenset(
    {
        "request",
        "response",
        "browser",
        "note",
        "result",
        "compare",
        "flow",
        "media",
        "row",
    }
)


@dataclass(frozen=True)
class ComponentSpec:
    """Registry descriptor for one component (COMPONENTS.md section 13)."""

    name: str
    body_mode: BodyMode
    attributes: dict[str, AttributeSpec] = field(default_factory=dict)
    allowed_parents: frozenset[str] = frozenset()
    allowed_children: frozenset[str] = frozenset()
    min_children: int = 0
    max_children: int | None = None
    css_class: str = ""
    renderer: str = ""
    layout_hints: dict[str, Any] = field(default_factory=dict)

    def resolve_attributes(
        self, authored: dict[str, Any], span_path: str, line: int, col: int
    ) -> dict[str, Any]:
        """Check authored attributes against this spec and apply defaults.

        Raises ``PageDocError`` on unknown, missing or invalid attributes.
        """
        from .errors import PageDocError

        resolved: dict[str, Any] = {}
        for key, value in authored.items():
            spec = self.attributes.get(key)
            if spec is None:
                known = ", ".join(sorted(self.attributes)) or "none"
                raise PageDocError(
                    Diagnostic(
                        span_path,
                        line,
                        col,
                        f"unknown attribute '{key}' on <{self.name}>; allowed: {known}",
                    )
                )
            if spec.enum is not None and value not in spec.enum:
                allowed = "|".join(spec.enum)
                raise PageDocError(
                    Diagnostic(
                        span_path,
                        line,
                        col,
                        f"attribute '{key}' on <{self.name}> must be one of {allowed}; found '{value}'",
                    )
                )
            resolved[key] = value
        for key, spec in self.attributes.items():
            if key in resolved:
                continue
            if spec.required:
                raise PageDocError(
                    Diagnostic(
                        span_path,
                        line,
                        col,
                        f"<{self.name}> requires attribute '{key}'",
                    )
                )
            if spec.default is not None:
                resolved[key] = spec.default
        return resolved


def _attrs(*specs: AttributeSpec) -> dict[str, AttributeSpec]:
    return {s.name: s for s in specs}


def _registry() -> dict[str, ComponentSpec]:
    container_children = TOP_LEVEL_COMPONENTS
    top_parents = frozenset({ROOT_PARENT, "row", "compare"})
    specs = [
        ComponentSpec(
            name="request",
            body_mode=BodyMode.RAW,
            attributes=_attrs(
                AttributeSpec("title"),
                AttributeSpec("lang", default="http"),
            ),
            allowed_parents=top_parents,
            css_class="pd-request",
            renderer="request",
        ),
        ComponentSpec(
            name="response",
            body_mode=BodyMode.RAW,
            attributes=_attrs(
                AttributeSpec("title"),
                AttributeSpec("status"),
                AttributeSpec("lang", default="auto"),
            ),
            allowed_parents=top_parents,
            css_class="pd-response",
            renderer="response",
        ),
        ComponentSpec(
            name="browser",
            body_mode=BodyMode.RAW,
            attributes=_attrs(
                AttributeSpec("title"),
                AttributeSpec("status"),
            ),
            allowed_parents=top_parents,
            css_class="pd-browser",
            renderer="browser",
        ),
        ComponentSpec(
            name="note",
            body_mode=BodyMode.MARKDOWN,
            attributes=_attrs(
                AttributeSpec("tone", default="note", enum=("note", "warning")),
                AttributeSpec("title"),
            ),
            allowed_parents=top_parents,
            css_class="pd-note",
            renderer="note",
        ),
        ComponentSpec(
            name="result",
            body_mode=BodyMode.MARKDOWN,
            attributes=_attrs(AttributeSpec("title"),),
            allowed_parents=top_parents,
            css_class="pd-result",
            renderer="result",
        ),
        ComponentSpec(
            name="row",
            body_mode=BodyMode.CHILDREN,
            attributes=_attrs(
                AttributeSpec(
                    "split",
                    default="auto",
                    enum=("auto", "equal", "wide-left", "wide-right"),
                ),
                AttributeSpec("align", default="start", enum=("start", "stretch")),
            ),
            allowed_parents=top_parents,
            allowed_children=container_children,
            min_children=2,
            max_children=2,
            css_class="pd-row",
            renderer="row",
            layout_hints={
                "auto_split": "equal",
                # Ordered child-type pairs -> preset, resolved
                # deterministically at render time (no backend needed).
                "auto_split_rules": {
                    ("request", "response"): "equal",
                    ("response", "request"): "equal",
                    ("request", "note"): "wide-left",
                    ("response", "note"): "wide-left",
                    ("note", "request"): "wide-right",
                    ("note", "response"): "wide-right",
                    ("media", "note"): "wide-left",
                    ("note", "media"): "wide-right",
                },
            },
        ),
        ComponentSpec(
            name="compare",
            body_mode=BodyMode.CHILDREN,
            attributes=_attrs(
                AttributeSpec("labels"),
                AttributeSpec(
                    "layout", default="auto", enum=("auto", "horizontal", "vertical")
                ),
            ),
            allowed_parents=top_parents,
            allowed_children=container_children,
            min_children=2,
            max_children=2,
            css_class="pd-compare",
            renderer="compare",
            layout_hints={"auto_layout": "horizontal"},
        ),
        ComponentSpec(
            name="flow",
            body_mode=BodyMode.CHILDREN,
            attributes=_attrs(
                AttributeSpec(
                    "layout", default="auto", enum=("auto", "horizontal", "vertical")
                ),
                AttributeSpec("title"),
            ),
            allowed_parents=top_parents,
            allowed_children=frozenset({"step"}),
            min_children=2,
            max_children=6,
            css_class="pd-flow",
            renderer="flow",
            layout_hints={"auto_layout": "horizontal"},
        ),
        ComponentSpec(
            name="media",
            body_mode=BodyMode.MARKDOWN,
            attributes=_attrs(
                AttributeSpec("src", required=True),
                AttributeSpec("alt", required=True),
                AttributeSpec("fit", default="contain", enum=("contain", "cover")),
                AttributeSpec("title"),
            ),
            allowed_parents=top_parents,
            css_class="pd-media",
            renderer="media",
        ),
        ComponentSpec(
            name="step",
            body_mode=BodyMode.MARKDOWN,
            attributes=_attrs(AttributeSpec("label", required=True),),
            allowed_parents=frozenset({"flow"}),
            css_class="pd-step",
            renderer="step",
        ),
    ]
    return {s.name: s for s in specs}


def get_registry() -> dict[str, ComponentSpec]:
    """Return the immutable v1 registry (fresh mapping of frozen specs)."""

    return _registry()


def registered_names(registry: dict[str, ComponentSpec] | None = None) -> frozenset[str]:
    reg = registry if registry is not None else get_registry()
    return frozenset(reg)


def iter_specs(registry: dict[str, ComponentSpec]) -> Iterable[ComponentSpec]:
    return registry.values()
