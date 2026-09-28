"""Registry-driven structural validation.

All component rules come from registry descriptors; this module adds the
cross-node checks (nesting, child counts, component-specific semantic
contracts like browser's single-URL body and media's local-asset rule).
"""

from __future__ import annotations

import os
import re

from .ast import ComponentNode, PageChild, PageNode
from .errors import Diagnostic
from .registry import ROOT_PARENT, BodyMode, ComponentSpec

_REMOTE_SRC_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def validate_page(
    page: PageNode, registry: dict[str, ComponentSpec]
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for child in page.children:
        if isinstance(child, ComponentNode):
            _validate_component(child, ROOT_PARENT, registry, diagnostics)
    return diagnostics


def _validate_component(
    node: ComponentNode,
    parent: str,
    registry: dict[str, ComponentSpec],
    diagnostics: list[Diagnostic],
) -> None:
    spec = registry[node.name]
    span = node.source

    if parent not in spec.allowed_parents:
        allowed = ", ".join(sorted(spec.allowed_parents))
        diagnostics.append(
            Diagnostic(
                span.path,
                span.start_line,
                span.start_col,
                f"component <{node.name}> is not allowed inside '{parent}'; allowed parents: {allowed}",
            )
        )

    if spec.body_mode is BodyMode.CHILDREN:
        children = node.children or []
        _check_children(node, spec, children, registry, diagnostics)

    if node.name == "compare":
        _check_compare_labels(node, diagnostics)
    elif node.name == "browser":
        _check_browser_body(node, diagnostics)
    elif node.name == "media":
        _check_media_src(node, diagnostics)


def _check_children(
    node: ComponentNode,
    spec: ComponentSpec,
    children: list[ComponentNode],
    registry: dict[str, ComponentSpec],
    diagnostics: list[Diagnostic],
) -> None:
    span = node.source
    count = len(children)
    if spec.min_children == spec.max_children:
        if count != spec.min_children:
            diagnostics.append(
                Diagnostic(
                    span.path,
                    span.start_line,
                    span.start_col,
                    f"{node.name} requires exactly {spec.min_children} children; found {count}",
                )
            )
    elif not (spec.min_children <= count <= (spec.max_children or count)):
        diagnostics.append(
            Diagnostic(
                span.path,
                span.start_line,
                span.start_col,
                f"{node.name} requires between {spec.min_children} and {spec.max_children} children; found {count}",
            )
        )
    for child in children:
        if child.name not in spec.allowed_children:
            diagnostics.append(
                Diagnostic(
                    child.source.path,
                    child.source.start_line,
                    child.source.start_col,
                    f"component <{child.name}> is not allowed inside <{node.name}>",
                )
            )
        _validate_component(child, node.name, registry, diagnostics)


def _check_compare_labels(node: ComponentNode, diagnostics: list[Diagnostic]) -> None:
    labels = node.attrs.get("labels")
    if labels is None:
        return
    parts = str(labels).split("|")
    if len(parts) != 2 or not all(p.strip() for p in parts):
        diagnostics.append(
            Diagnostic(
                node.source.path,
                node.source.start_line,
                node.source.start_col,
                "compare attribute 'labels' must contain two labels separated by '|'",
            )
        )


def _check_browser_body(node: ComponentNode, diagnostics: list[Diagnostic]) -> None:
    raw = node.raw or ""
    non_empty = [line for line in raw.split("\n") if line.strip()]
    if len(non_empty) != 1:
        diagnostics.append(
            Diagnostic(
                node.source.path,
                node.source.start_line,
                node.source.start_col,
                f"browser requires exactly one non-empty URL line; found {len(non_empty)}",
            )
        )


def _check_media_src(node: ComponentNode, diagnostics: list[Diagnostic]) -> None:
    src = str(node.attrs.get("src", ""))
    span = node.source
    if _REMOTE_SRC_RE.match(src) or src.startswith("//"):
        diagnostics.append(
            Diagnostic(
                span.path,
                span.start_line,
                span.start_col,
                f"media src '{src}' must be a local path; remote assets are never fetched",
            )
        )
        return
    base_dir = os.path.dirname(span.path)
    resolved = os.path.normpath(os.path.join(base_dir, src))
    if not os.path.isfile(resolved):
        diagnostics.append(
            Diagnostic(
                span.path,
                span.start_line,
                span.start_col,
                f"media asset not found: '{src}'",
            )
        )


def lint_diagnostics(page: PageNode, registry: dict[str, ComponentSpec]) -> list[Diagnostic]:
    return validate_page(page, registry)
