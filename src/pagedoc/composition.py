"""Bounded per-component auto composition search (M3.1).

When the preferred composition of a page overflows, authored ``auto``
values (``row split``, ``compare layout``, ``flow layout``) become
candidates evaluated through the authoritative backend — never through
Python-side text measurement.

Contract:

- page-local: only decisions on a failing page participate, and each
  failing page is solved independently;
- bounded: the exact Cartesian product of candidate values, hard limit
  ``MAX_COMPOSITION_CANDIDATES_PER_PAGE`` complete assignments;
- deterministic: preferred candidate first, documented ordering for
  the rest, and a stable lexicographic winner rule — fitting beats
  non-fitting, then fewest deviations from preferred, then lowest real
  ``content_used``, then stable assignment order;
- explicit authored values never participate and are never overridden.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product
from typing import Any, Union

from .ast import ComponentNode, MarkdownNode, PageNode
from .backends.base import DocumentLayout, PageLayout
from .registry import ComponentSpec
from .render.context import NodeRef, RenderResult
from .theme.model import Theme

MAX_COMPOSITION_CANDIDATES_PER_PAGE = 24

# Stable, documented candidate orders (preferred always first).
_ROW_ORDER = ("equal", "wide-left", "wide-right")
_ORIENTATIONS = ("horizontal", "vertical")


@dataclass(frozen=True)
class AutoDecision:
    """One authored ``auto`` value that may vary during overflow recovery."""

    node_id: str
    page_index: int
    page_id: str
    component: str  # "row" | "compare" | "flow"
    property: str  # "split" | "layout"
    preferred: str
    candidates: tuple[str, ...]  # preferred first
    line: int
    col: int

    @property
    def key(self) -> str:
        return f"{self.node_id}:{self.property}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "component": self.component,
            "property": self.property,
            "preferred": self.preferred,
            "candidates": list(self.candidates),
            "line": self.line,
            "col": self.col,
        }


@dataclass
class CandidateEvaluation:
    """Measured result for one complete assignment on one page."""

    resolutions: dict[str, str]
    fits: bool
    overflow_px: float
    width_overflow_px: float
    content_used: float | None
    content_available: float | None
    deviation_count: int
    order_index: int  # position in the deterministic enumeration
    blocks_rendered: int | None = None
    blocks_missing: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolutions": dict(sorted(self.resolutions.items())),
            "fits": self.fits,
            "blocks_rendered": self.blocks_rendered,
            "blocks_missing": self.blocks_missing,
            "overflow_px": round(self.overflow_px, 1),
            "width_overflow_px": round(self.width_overflow_px, 1),
            "content_used_px": (
                round(self.content_used, 1)
                if self.content_used is not None
                else None
            ),
            "content_available_px": (
                round(self.content_available, 1)
                if self.content_available is not None
                else None
            ),
            "deviation_count": self.deviation_count,
        }


@dataclass
class CompositionPageTrace:
    page_index: int
    page_id: str
    decisions: list[AutoDecision] = field(default_factory=list)
    candidate_space: int = 0
    evaluated: int = 0
    selected: dict[str, str] | None = None
    selected_deviation_count: int = 0
    candidates: list[CandidateEvaluation] = field(default_factory=list)
    best_non_fitting: dict[str, str] | None = None
    outcome: str = "not-searched"  # searched | too-many-candidates

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "page_index": self.page_index,
            "page_id": self.page_id,
            "triggered": True,
            "decisions": [x.to_dict() for x in self.decisions],
            "candidate_space": self.candidate_space,
            "evaluated": self.evaluated,
            "candidates": [c.to_dict() for c in self.candidates],
            "outcome": self.outcome,
        }
        if self.selected is not None:
            d["selected"] = dict(sorted(self.selected.items()))
            d["selected_deviation_count"] = self.selected_deviation_count
        if self.best_non_fitting is not None:
            d["best_non_fitting"] = dict(sorted(self.best_non_fitting.items()))
        return d


@dataclass
class CompositionTrace:
    """Deterministic record of what the composition engine did."""

    mode: str = "auto-overflow-recovery"
    initial_fits: bool = True
    layout_passes: int = 0
    pages: list[CompositionPageTrace] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "initial_fits": self.initial_fits,
            "layout_passes": self.layout_passes,
            "pages": [p.to_dict() for p in self.pages],
        }


def _row_candidates(preferred: str, theme: Theme) -> tuple[str, ...]:
    available = [p for p in _ROW_ORDER if p in theme.splits]
    rest = [p for p in available if p != preferred]
    return (preferred, *rest)


def _layout_candidates(preferred: str) -> tuple[str, ...]:
    rest = [o for o in _ORIENTATIONS if o != preferred]
    return (preferred, *rest)


def discover_auto_decisions(
    render: RenderResult, theme: Theme
) -> dict[int, list[AutoDecision]]:
    """Collect authored ``auto`` decisions per logical page.

    Only nodes whose authored attribute is literally ``auto`` become
    decisions; explicit values are immutable by contract. ``node_map``
    preserves document order, so the decision list is deterministic.
    """

    out: dict[int, list[AutoDecision]] = {}
    for node_id, ref in render.node_map.items():
        node: Union[PageNode, ComponentNode, MarkdownNode] = ref.node
        name = getattr(node, "name", None)
        if name not in ("row", "compare", "flow"):
            continue
        assert isinstance(node, ComponentNode)
        if name == "row":
            prop, authored = "split", str(node.attrs.get("split", "auto"))
            if authored != "auto":
                continue
            preferred = render.resolved.get(f"{node_id}:split", "equal")
            candidates = _row_candidates(preferred, theme)
        else:
            prop, authored = "layout", str(node.attrs.get("layout", "auto"))
            if authored != "auto":
                continue
            preferred = render.resolved.get(f"{node_id}:layout", "horizontal")
            candidates = _layout_candidates(preferred)
        src = node.source
        out.setdefault(ref.page_index, []).append(
            AutoDecision(
                node_id=node_id,
                page_index=ref.page_index,
                page_id=ref.page_id,
                component=name,
                property=prop,
                preferred=preferred,
                candidates=candidates,
                line=src.start_line,
                col=src.start_col,
            )
        )
    return out


def enumerate_assignments(
    decisions: list[AutoDecision],
) -> list[dict[str, str]]:
    """Deterministic Cartesian enumeration; index 0 is the preferred
    assignment (every decision's candidates start with preferred)."""

    keys = [d.key for d in decisions]
    pools = [d.candidates for d in decisions]
    return [dict(zip(keys, combo)) for combo in product(*pools)]


def candidate_space_size(decisions: list[AutoDecision]) -> int:
    size = 1
    for d in decisions:
        size *= len(d.candidates)
    return size


def deviation_count(assignment: dict[str, str], decisions: list[AutoDecision]) -> int:
    return sum(1 for d in decisions if assignment.get(d.key) != d.preferred)


def rank_fitting(ev: CandidateEvaluation) -> tuple:
    return (ev.deviation_count, ev.content_used or 0.0, ev.order_index)


def rank_non_fitting(ev: CandidateEvaluation) -> tuple:
    # Dropped authored blocks count as the worst form of non-fit.
    total_overflow = (
        ev.overflow_px + ev.width_overflow_px + ev.blocks_missing * 100000.0
    )
    return (
        total_overflow,
        ev.deviation_count,
        ev.content_used or 0.0,
        ev.order_index,
    )


def select_winner(
    evaluations: list[CandidateEvaluation],
) -> CandidateEvaluation | None:
    fitting = [e for e in evaluations if e.fits]
    if not fitting:
        return None
    return min(fitting, key=rank_fitting)


def select_best_non_fitting(
    evaluations: list[CandidateEvaluation],
) -> CandidateEvaluation | None:
    non = [e for e in evaluations if not e.fits]
    if not non:
        return None
    return min(non, key=rank_non_fitting)


def page_layout_for(layout: DocumentLayout, page_index: int) -> PageLayout | None:
    for p in layout.pages:
        if p.index == page_index:
            return p
    return None


def evaluate_candidate(
    page_layout: PageLayout | None,
    assignment: dict[str, str],
    decisions: list[AutoDecision],
    order_index: int,
    expected_blocks: int | None = None,
) -> CandidateEvaluation:
    """Score a measured page for one assignment.

    ``fits`` additionally requires every authored top-level block to be
    present: the backend can silently drop a monolithic block that has
    no fragmentainer left, and missing authored content is never a fit.
    """

    pl = page_layout
    missing = 0
    if expected_blocks is not None and pl is not None:
        missing = max(0, expected_blocks - pl.block_count)
    return CandidateEvaluation(
        resolutions=assignment,
        fits=bool(pl.fits and missing == 0) if pl else False,
        overflow_px=pl.overflow_px if pl else float("inf"),
        width_overflow_px=pl.width_overflow_px if pl else float("inf"),
        content_used=pl.content_used if pl else None,
        content_available=pl.content_available if pl else None,
        deviation_count=deviation_count(assignment, decisions),
        order_index=order_index,
        blocks_rendered=pl.block_count if pl else 0,
        blocks_missing=missing,
    )
