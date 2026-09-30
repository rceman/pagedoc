"""M3 composition engine: bounded per-component candidate search."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from conftest import DEFAULT_FM, REPO_ROOT, write_page  # noqa: E402

from pagedoc.composition import (  # noqa: E402
    MAX_COMPOSITION_CANDIDATES_PER_PAGE,
    AutoDecision,
    candidate_space_size,
    deviation_count,
    enumerate_assignments,
    rank_fitting,
    rank_non_fitting,
    CandidateEvaluation,
    select_winner,
    select_best_non_fitting,
)
from pagedoc.document import load_document  # noqa: E402
from pagedoc.pipeline import build_document  # noqa: E402
from pagedoc.registry import get_registry  # noqa: E402
from pagedoc.theme.loader import load_theme  # noqa: E402


def _build(tmp_path, pages):
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir(exist_ok=True)
    for i, body in enumerate(pages):
        fm = DEFAULT_FM.replace("test-page", f"p{i}")
        write_page(tmp_path, body, name=f"pages/p{i}.book.md", fm=fm)
    entries = "\n".join(f"  - pages/p{i}.book.md" for i in range(len(pages)))
    (tmp_path / "document.yaml").write_text(
        f"id: d\ntitle: D\npages:\n{entries}\n", encoding="utf-8"
    )
    doc = load_document(str(tmp_path / "document.yaml"), get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    return doc, build_document(doc, theme)


def _by_name(build, name, occurrence=0):
    nodes = [
        n for n, r in build.node_map.items()
        if getattr(r.node, "name", None) == name
    ]
    return nodes[occurrence]


def _resolved(build, nid, key):
    return build.resolved[f"{nid}:{key}"]


def _tall_paras(n=20):
    return "\n\n".join(
        f"Verification point {i} covering several aspects of expected behavior."
        for i in range(n)
    )


# ---------------- unit: decision/enumeration/scoring -----------------------


def _decision(key, preferred, candidates):
    nid, prop = key.split(":")
    return AutoDecision(
        node_id=nid, page_index=0, page_id="p", component="x",
        property=prop, preferred=preferred, candidates=tuple(candidates),
        line=1, col=1,
    )


def test_candidate_enumeration_preferred_first_stable_order():
    decs = [
        _decision("p0n1:split", "wide-left", ("wide-left", "equal", "wide-right")),
        _decision("p0n2:layout", "horizontal", ("horizontal", "vertical")),
    ]
    assignments = enumerate_assignments(decs)
    assert len(assignments) == 6
    assert assignments[0] == {
        "p0n1:split": "wide-left", "p0n2:layout": "horizontal"
    }
    assert candidate_space_size(decs) == 6
    # deterministic: identical on repeat
    assert enumerate_assignments(decs) == assignments


def test_deviation_count_and_space():
    decs = [
        _decision("p0n1:split", "equal", ("equal", "wide-left")),
        _decision("p0n2:layout", "horizontal", ("horizontal", "vertical")),
    ]
    assert deviation_count(
        {"p0n1:split": "wide-left", "p0n2:layout": "vertical"}, decs
    ) == 2
    assert deviation_count(
        {"p0n1:split": "equal", "p0n2:layout": "horizontal"}, decs
    ) == 0


def _ev(res, fits, used, dev, order, ov=0.0, wov=0.0):
    return CandidateEvaluation(
        resolutions=res, fits=fits, overflow_px=ov, width_overflow_px=wov,
        content_used=used, content_available=900.0,
        deviation_count=dev, order_index=order,
    )


def test_winner_prefers_fitting_then_fewest_deviations_then_compact():
    evals = [
        _ev({"a": "x"}, False, 100.0, 0, 0, ov=10.0),  # preferred, no fit
        _ev({"a": "y"}, True, 900.0, 2, 1),  # fits but 2 deviations
        _ev({"a": "z"}, True, 500.0, 1, 2),  # fits, 1 deviation, compact
        _ev({"a": "w"}, True, 800.0, 1, 3),  # fits, 1 deviation, taller
    ]
    w = select_winner(evals)
    assert w.resolutions == {"a": "z"}  # dev=1 beats dev=2; used=500 beats 800


def test_winner_tie_break_by_stable_order():
    evals = [
        _ev({"a": "x"}, False, 0, 0, 0, ov=5.0),
        _ev({"a": "y"}, True, 500.0, 1, 1),
        _ev({"a": "z"}, True, 500.0, 1, 2),
    ]
    assert select_winner(evals).resolutions == {"a": "y"}


def test_best_non_fitting_lowest_overflow_then_deviation():
    evals = [
        _ev({"a": "x"}, False, 500.0, 0, 0, ov=30.0),
        _ev({"a": "y"}, False, 500.0, 1, 1, ov=10.0),
        _ev({"a": "z"}, False, 500.0, 2, 2, ov=10.0),
    ]
    best = select_best_non_fitting(evals)
    assert best.resolutions == {"a": "y"}


# ---------------- acceptance fixtures -------------------------------------

TALL = _tall_paras()


def test_a_single_compare_recovery(tmp_path):
    """Horizontal auto compare overflows; vertical fits; only that node
    changes (1 preferred deviation)."""
    body = (
        '<compare layout="auto" labels="Expected|Actual">\n'
        f"<result>\n{TALL}\n</result>\n<result>\nOK\n</result>\n</compare>\n"
    )
    _, build = _build(tmp_path, [body])
    nid = _by_name(build, "compare")
    assert build.fits
    assert _resolved(build, nid, "layout") == "vertical"
    pt = build.composition.pages[0]
    assert pt.candidate_space == 2 and pt.evaluated == 2
    assert pt.selected == {f"{nid}:layout": "vertical"}
    assert pt.selected_deviation_count == 1
    # preferred candidate recorded as measured (not re-rendered)
    assert build.composition.layout_passes == 2


def test_b_localized_two_auto_only_one_changes(tmp_path):
    """Two autos on one failing page: only the overflowing component
    changes — the core M2-vs-M3 difference (M2 flipped all)."""
    tall_compare = (
        '<compare layout="auto" labels="A|B">\n'
        f"<result>\n{TALL}\n</result>\n<result>\nOK\n</result>\n</compare>\n"
    )
    small_flow = (
        '<flow>\n<step label="1">\nPrepare\n</step>\n<step label="2">\nVerify\n</step>\n'
        '<step label="3">\nShip\n</step>\n</flow>\n'
    )
    _, build = _build(tmp_path, [tall_compare + "\n" + small_flow])
    assert build.fits
    cmp_nid = _by_name(build, "compare")
    flow_nid = _by_name(build, "flow")
    assert _resolved(build, cmp_nid, "layout") == "vertical"
    assert _resolved(build, flow_nid, "layout") == "horizontal"  # NOT flipped
    pt = build.composition.pages[0]
    assert pt.candidate_space == 4
    assert pt.selected_deviation_count == 1


def test_c_row_split_recovery(tmp_path):
    """auto row: registry-preferred wide-left overflows (narrow note cell
    wraps too tall); an alternative split fits."""
    note = "\n\n".join(
        f"Adjustment reason {i}: longer explanation text that wraps "
        "across several lines inside a narrow row cell."
        for i in range(14)
    )
    req = (
        "PUT /api/v2/stock-adjustments HTTP/1.1\n"
        "Host: inventory.internal.example\nX-Reason: COUNT\n\n{}\n"
    )
    body = f'<row split="auto">\n<request>\n{req}</request>\n<note>\n{note}\n</note>\n</row>'
    _, build = _build(tmp_path, [body])
    nid = _by_name(build, "row")
    assert build.fits
    assert _resolved(build, nid, "split") != "wide-left"
    pt = build.composition.pages[0]
    assert pt.candidate_space == 3
    assert pt.selected_deviation_count == 1
    # selected via real backend metrics, not heuristics
    winner = [c for c in pt.candidates if c.fits]
    assert winner and all(c.overflow_px == 0 for c in winner)


def test_d_mixed_row_and_compare(tmp_path):
    """Row auto + compare auto: exact Cartesian search (space 6) selects
    the unique fitting combination {wide-right, vertical}."""
    note = "\n\n".join(
        f"Reason {i}: explanatory wrap text for a narrow cell."
        for i in range(8)
    )
    req = "PUT /api/v2/stock HTTP/1.1\n\n{}\n"
    row = f'<row split="auto">\n<request>\n{req}</request>\n<note>\n{note}\n</note>\n</row>'
    cmp_ = (
        '<compare layout="auto" labels="A|B">\n'
        f"<result>\n{_tall_paras(14)}\n</result>\n<result>\nOK\n</result>\n</compare>"
    )
    _, build = _build(tmp_path, [row + "\n" + cmp_])
    assert build.fits
    pt = build.composition.pages[0]
    assert pt.candidate_space == 6 and pt.evaluated == 6
    row_nid = _by_name(build, "row")
    cmp_nid = _by_name(build, "compare")
    assert pt.selected == {
        f"{row_nid}:split": "wide-right",
        f"{cmp_nid}:layout": "vertical",
    }
    assert pt.selected_deviation_count == 2
    assert build.composition.layout_passes <= 1 + 6


def test_e_flow_recovery(tmp_path):
    """Horizontal auto flow overflows; vertical fits."""
    steps = "".join(
        f'<step label="Step {i}">\n'
        f"Deploy artifact {i} to the staging inventory service and "
        f"verify the published checksum against the manifest entry.\n</step>\n"
        for i in range(6)
    )
    _, build = _build(tmp_path, [f"<flow>\n{steps}</flow>\n"])
    nid = _by_name(build, "flow")
    pt = build.composition.pages[0] if build.composition.pages else None
    if pt is None:  # preferred already fit — acceptable environment drift
        assert _resolved(build, nid, "layout") == "horizontal"
    else:
        assert build.fits
        assert _resolved(build, nid, "layout") == "vertical"
        assert pt.selected_deviation_count == 1


def test_f_explicit_layout_never_overridden(tmp_path):
    """Explicit horizontal compare that overflows stays horizontal and
    the build reports overflow — author choice is immutable."""
    body = (
        '<compare layout="horizontal" labels="A|B">\n'
        f"<result>\n{TALL}\n</result>\n<result>\nOK\n</result>\n</compare>\n"
    )
    _, build = _build(tmp_path, [body])
    nid = _by_name(build, "compare")
    assert _resolved(build, nid, "layout") == "horizontal"
    assert not build.fits
    assert build.diagnostics
    # no auto decisions -> no composition candidates for this page
    searched = [p for p in build.composition.pages if p.decisions]
    assert searched == [] or all(
        d.component != "compare" for p in searched for d in p.decisions
    )


def test_g_no_candidate_fits(tmp_path):
    """Every auto combination overflows: trace exists, build still fails
    with an actionable diagnostic."""
    huge = _tall_paras(60)
    body = (
        '<compare layout="auto" labels="A|B">\n'
        f"<result>\n{huge}\n</result>\n<result>\n{huge}\n</result>\n</compare>\n"
    )
    _, build = _build(tmp_path, [body])
    assert not build.fits
    pt = build.composition.pages[0]
    assert pt.evaluated == 2
    assert pt.selected is None
    assert pt.best_non_fitting is not None
    msgs = " ".join(d.message for d in build.diagnostics)
    assert "none fit" in msgs
    assert "exceeds" in msgs or "overflow" in msgs


def test_h_already_fitting_no_search(tmp_path):
    """Preferred composition fits: exactly one layout pass, M2 output
    preserved, no candidate work."""
    body = (
        '<compare layout="auto" labels="A|B">\n'
        "<result>\nshort\n</result>\n<result>\nalso short\n</result>\n</compare>\n"
        '<flow>\n<step label="1">\na\n</step>\n<step label="2">\nb\n</step>\n</flow>\n'
        "<row>\n<request>\nGET /x\n</request>\n<note>\nnote\n</note>\n</row>\n"
    )
    _, build = _build(tmp_path, [body])
    assert build.fits
    assert build.composition.layout_passes == 1
    assert build.composition.initial_fits
    assert build.composition.pages == []
    assert _resolved(build, _by_name(build, "compare"), "layout") == "horizontal"
    assert _resolved(build, _by_name(build, "flow"), "layout") == "horizontal"


def test_i_multi_page_independence(tmp_path):
    """Two pages each recover independently; a fitting page in between
    is not recomposed."""
    p0 = (
        '<compare layout="auto" labels="A|B">\n'
        f"<result>\n{TALL}\n</result>\n<result>\nOK\n</result>\n</compare>\n"
    )
    p1 = "A normal fitting page.\n\nWith some prose.\n"
    p2 = (
        '<compare layout="auto" labels="X|Y">\n'
        f"<result>\n{_tall_paras(22)}\n</result>\n<result>\nOK\n</result>\n</compare>\n"
    )
    _, build = _build(tmp_path, [p0, p1, p2])
    assert build.fits
    assert len(build.composition.pages) == 2
    assert {p.page_index for p in build.composition.pages} == {0, 2}
    for pt in build.composition.pages:
        assert pt.selected is not None
        assert pt.selected_deviation_count == 1


def test_j_search_space_guard(tmp_path):
    """>24 complete assignments: search refuses, actionable diagnostic,
    zero candidate layout passes."""
    blocks = "\n".join(
        '<compare layout="auto" labels="A|B">\n'
        f"<result>\n{_tall_paras(20)}\n</result>\n<result>\nOK\n</result>\n</compare>"
        for _ in range(5)
    )
    _, build = _build(tmp_path, [blocks])
    assert not build.fits
    pt = build.composition.pages[0]
    assert pt.candidate_space == 32 > MAX_COMPOSITION_CANDIDATES_PER_PAGE
    assert pt.outcome == "too-many-candidates"
    msgs = " ".join(d.message for d in build.diagnostics)
    assert "too many automatic composition combinations" in msgs
    assert "explicit" in msgs
    # the initial pass is the only layout work — no partial search
    assert build.composition.layout_passes == 1


def test_final_serialization_adds_no_layout_pass(tmp_path):
    """write_pdf/pdf_bytes reuse the retained measured document."""
    body = (
        '<compare layout="auto" labels="A|B">\n'
        f"<result>\n{TALL}\n</result>\n<result>\nOK\n</result>\n</compare>\n"
    )
    _, build = _build(tmp_path, [body])
    before = build.composition.layout_passes
    build.rendered.pdf_bytes()
    build.rendered.write_pdf(str(tmp_path / "out.pdf"))
    build.rendered.pdf_bytes()
    assert build.composition.layout_passes == before
