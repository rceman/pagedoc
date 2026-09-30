"""Build orchestration: validated document -> HTML -> backend layout ->
diagnostics.

The authoritative layout path (ARCHITECTURE.md section 9): generated
HTML/CSS is rendered by the backend; the returned ``RenderedDocument``
is both what diagnostics measure and what PDF serialization emits.
There is no second layout pass to produce output.

``auto`` values for ``row split`` / ``compare layout`` / ``flow layout``
resolve by real fit. The first pass renders every auto decision at its
registry-preferred value. Pages that then overflow enter a bounded,
page-local exact search over candidate assignments (composition.py);
each candidate is evaluated by a real backend layout pass and the
deterministic winner is re-rendered once as the final authoritative
document. Pages that fit in the first pass are never recomposed.
"""

from __future__ import annotations

import os
import pathlib
from dataclasses import dataclass, field

from .backends.base import DocumentLayout, RenderedDocument
from .composition import (
    MAX_COMPOSITION_CANDIDATES_PER_PAGE,
    CompositionPageTrace,
    CompositionTrace,
    candidate_space_size,
    deviation_count,
    discover_auto_decisions,
    enumerate_assignments,
    evaluate_candidate,
    page_layout_for,
    select_best_non_fitting,
    select_winner,
)
from .document import Document
from .errors import Diagnostic
from .registry import ComponentSpec, get_registry
from .render.context import NodeRef, RenderResult
from .render.html import render_document
from .theme.model import Theme


@dataclass
class BuildResult:
    html: str
    node_map: dict[str, NodeRef]
    resolved: dict[str, str]
    layout: DocumentLayout
    # The measured backend document — serialize THIS for PDF output.
    rendered: RenderedDocument | None = None
    diagnostics: list[Diagnostic] = field(default_factory=list)
    composition: CompositionTrace = field(default_factory=CompositionTrace)

    @property
    def fits(self) -> bool:
        return not self.diagnostics


def _base_url(manifest_dir: str) -> str:
    return pathlib.Path(os.path.abspath(manifest_dir)).as_uri() + "/"


def build_document(
    document: Document,
    theme: Theme,
    registry: dict[str, ComponentSpec] | None = None,
) -> BuildResult:
    """Render HTML, measure with the backend, recover overflow via bounded
    auto-composition search, produce diagnostics."""

    from .backends import weasyprint  # lazy: keeps lint/ast CLI fast

    reg = registry if registry is not None else get_registry()
    base_url = _base_url(document.manifest_dir)
    trace = CompositionTrace()
    renders: dict[tuple, tuple[RenderResult, RenderedDocument]] = {}

    def do_render(resolutions: dict[str, str] | None = None):
        key = tuple(sorted((resolutions or {}).items()))
        if key not in renders:
            render = render_document(document, theme, reg, resolutions=resolutions)
            rendered = weasyprint.render(render.html, base_url)
            renders[key] = (render, rendered)
            trace.layout_passes += 1
        return renders[key]

    render, rendered = do_render()
    preferred_map: dict[str, str] = {}
    expected_blocks = {
        p.index: len(document.pages[p.index].children)
        for p in rendered.layout.pages
        if p.index < len(document.pages)
    }

    def page_ok(pl) -> bool:
        return pl.fits and pl.block_count == expected_blocks.get(pl.index, -1)

    trace.initial_fits = all(
        page_ok(p) for p in rendered.layout.pages
    ) and rendered.layout.physical_page_count == len(document.pages)

    if not trace.initial_fits:
        decisions_by_page = discover_auto_decisions(render, theme)
        failing = [p for p in rendered.layout.pages if not page_ok(p)]
        overflow_diags: list[Diagnostic] = []

        for pl in failing:
            decisions = decisions_by_page.get(pl.index, [])
            if not decisions:
                continue  # nothing auto to try — stays an overflow error
            page_trace = CompositionPageTrace(
                page_index=pl.index,
                page_id=pl.page_id or f"page-{pl.index}",
                decisions=decisions,
                candidate_space=candidate_space_size(decisions),
            )
            trace.pages.append(page_trace)
            if page_trace.candidate_space > MAX_COMPOSITION_CANDIDATES_PER_PAGE:
                page_trace.outcome = "too-many-candidates"
                first = decisions[0]
                src = (
                    render.node_map[first.node_id].node.source.path
                    if first.node_id in render.node_map
                    else document.manifest_path
                )
                locs = ", ".join(
                    f"{d.node_id} line {d.line}" for d in decisions
                )
                overflow_diags.append(
                    Diagnostic(
                        src,
                        first.line,
                        first.col,
                        f"page '{pl.page_id}' has too many automatic composition "
                        f"combinations ({len(decisions)} auto decisions, "
                        f"{page_trace.candidate_space} assignments > "
                        f"{MAX_COMPOSITION_CANDIDATES_PER_PAGE}); make one or more "
                        f"row split / compare layout / flow layout choices "
                        f"explicit (auto nodes: {locs})",
                    )
                )
                continue

            assignments = enumerate_assignments(decisions)
            page_trace.evaluated = len(assignments)
            exp = expected_blocks.get(pl.index)
            for order, assignment in enumerate(assignments):
                # Evaluate under resolutions already selected for earlier
                # pages: a block that cannot be placed escapes onto the
                # next physical page and would contaminate this page's
                # measurement. The preferred assignment is re-measured
                # whenever the accumulated map is non-empty.
                combined = {**preferred_map, **assignment}
                if order == 0 and not preferred_map:
                    pl_c = pl  # preferred already measured cleanly
                else:
                    _, cand_rendered = do_render(combined)
                    pl_c = page_layout_for(cand_rendered.layout, pl.index)
                ev = evaluate_candidate(
                    pl_c, assignment, decisions, order,
                    expected_blocks=exp,
                )
                page_trace.candidates.append(ev)

            winner = select_winner(page_trace.candidates)
            if winner is not None:
                page_trace.selected = dict(winner.resolutions)
                page_trace.selected_deviation_count = winner.deviation_count
                page_trace.outcome = "selected"
                preferred_map.update(winner.resolutions)
            else:
                page_trace.outcome = "no-fit"
                best = select_best_non_fitting(page_trace.candidates)
                if best is not None:
                    page_trace.best_non_fitting = dict(best.resolutions)
                first = decisions[0]
                overflow_diags.append(
                    Diagnostic(
                        render.node_map[first.node_id].node.source.path,
                        first.line,
                        first.col,
                        f"automatic composition evaluated "
                        f"{page_trace.evaluated} assignments for page "
                        f"'{pl.page_id}'; none fit this page",
                    )
                )

        if preferred_map:
            render, rendered = do_render(preferred_map)
            # Stability check: the combined render must confirm every
            # searched page's page-local evaluation.
            for pt in trace.pages:
                if pt.selected is None:
                    continue
                pl_f = page_layout_for(rendered.layout, pt.page_index)
                if pl_f is None or not page_ok(pl_f):
                    overflow_diags.append(
                        Diagnostic(
                            document.manifest_path,
                            1,
                            1,
                            f"internal composition-stability error: page "
                            f"'{pt.page_id}' selected assignment did not "
                            f"reproduce in the final render",
                        )
                    )
        diagnostics = _layout_diagnostics(
            document, rendered.layout, render.node_map
        )
        diagnostics.extend(
            _dropped_block_diagnostics(document, rendered.layout)
        )
        diagnostics.extend(overflow_diags)
    else:
        diagnostics = _layout_diagnostics(
            document, rendered.layout, render.node_map
        )

    return BuildResult(
        html=render.html,
        node_map=render.node_map,
        resolved=render.resolved,
        layout=rendered.layout,
        rendered=rendered,
        diagnostics=diagnostics,
        composition=trace,
    )


def _dropped_block_diagnostics(
    document: Document, layout: DocumentLayout
) -> list[Diagnostic]:
    """The backend can silently drop a monolithic block that has no
    fragmentainer left; missing authored content is an error, never a fit."""

    diagnostics: list[Diagnostic] = []
    for pl in layout.pages:
        if pl.index >= len(document.pages):
            continue
        expected = len(document.pages[pl.index].children)
        if pl.block_count >= expected:
            continue
        page_node = document.pages[pl.index]
        diagnostics.append(
            Diagnostic(
                page_node.source.path,
                page_node.source.start_line,
                1,
                f"page '{pl.page_id or page_node.page_id}' rendered "
                f"{pl.block_count} of {expected} authored top-level blocks; "
                f"{expected - pl.block_count} block(s) could not be placed "
                f"on the fixed page",
            )
        )
    return diagnostics


def _layout_diagnostics(
    document: Document, layout: DocumentLayout, node_map: dict[str, NodeRef]
) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    expected = len(document.pages)
    if layout.physical_page_count != expected:
        diagnostics.append(
            Diagnostic(
                document.manifest_path,
                1,
                1,
                f"document produced {layout.physical_page_count} physical pages "
                f"for {expected} authored pages; each .book.md page must fit one physical page",
            )
        )
    for pl in layout.pages:
        page_node = document.pages[pl.index] if pl.index < expected else None
        page_id = pl.page_id or (page_node.page_id if page_node else f"page-{pl.index}")
        src_path = page_node.source.path if page_node else document.manifest_path
        if pl.overflow_px > 0 or pl.width_overflow_px > 0:
            # Attribute to the deepest authored node whose rendered bounds
            # actually cross the region boundary.
            ref = node_map.get(pl.overflow_node_id or pl.last_block_id or "")
            line = ref.node.source.start_line if ref else 1
            col = ref.node.source.start_col if ref else 1
            desc = _block_desc(ref)
            if pl.overflow_axis == "horizontal" or (
                pl.overflow_axis is None and pl.width_overflow_px > 0
            ):
                amount = pl.width_overflow_px
                axis = "content region width"
            else:
                amount = pl.overflow_px
                axis = "content region"
            diagnostics.append(
                Diagnostic(
                    src_path,
                    line,
                    col,
                    f"page '{page_id}' exceeds {axis} by {amount:.0f}px; "
                    f"overflowing block: {desc} starting at line {line}",
                )
            )
    return diagnostics


def _block_desc(ref: NodeRef | None) -> str:
    if ref is None:
        return "unknown block"
    node = ref.node
    name = getattr(node, "name", None) or getattr(node, "type", "block")
    if getattr(node, "name", None):
        return f"<{name}>"
    return f"markdown {name}"
