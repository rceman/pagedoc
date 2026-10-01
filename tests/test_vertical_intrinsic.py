"""Theme conformance: vertical compare/flow must stack children at
intrinsic height — never shrink/escape into sibling content (M3.2 fix
for the flex-direction=column + flex:1 1 0 overlap defect)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(__file__))
from conftest import DEFAULT_FM, REPO_ROOT, write_page  # noqa: E402

from pagedoc.document import load_document  # noqa: E402
from pagedoc.pipeline import build_document  # noqa: E402
from pagedoc.registry import get_registry  # noqa: E402
from pagedoc.theme.loader import load_theme  # noqa: E402

BOOK_THEME = os.path.join(
    REPO_ROOT, "examples", "themes", "book-v2-reference", "theme.yaml"
)


def _build(tmp_path, body, theme_ref="default"):
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir(exist_ok=True)
    write_page(tmp_path, body, name="pages/p0.book.md")
    (tmp_path / "document.yaml").write_text(
        f"id: d\ntitle: D\ntheme: {theme_ref}\npages:\n  - pages/p0.book.md\n",
        encoding="utf-8",
    )
    doc = load_document(str(tmp_path / "document.yaml"), get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    return doc, build_document(doc, theme)


def _boxes_by_class(build, cls):
    """Locate rendered boxes carrying a CSS class on a physical page."""
    from pagedoc.backends.weasyprint import _attrib, _walk

    out = []
    page = build.rendered._document.pages[0]
    for box, _d in _walk(page._page_box):
        if "::" in str(getattr(box, "element_tag", "")):
            continue  # pseudo-element placeholders share the class
        classes = str(_attrib(box).get("class", "")).split()
        if cls in classes:
            out.append(box)
    return out


def _descendant_bottom(box):
    from pagedoc.backends.weasyprint import _walk

    return max(b.position_y + b.height for b, _ in _walk(box))


UNBALANCED_COMPARE = (
    '<compare layout="vertical" labels="A|B">\n'
    "<result>\n"
    + "\n\n".join(
        f"Finding {i}: a long paragraph that must occupy several "
        "rendered lines inside the first compare side."
        for i in range(10)
    )
    + "\n</result>\n<result>\nShort.\n</result>\n</compare>\n"
)

UNBALANCED_FLOW = (
    '<flow layout="vertical">\n'
    + '<step label="One">\n'
    + "\n\n".join(
        f"Detail {i}: extensive verification text occupying many lines."
        for i in range(8)
    )
    + "\n</step>\n"
    + '<step label="Two">\nDone.\n</step>\n'
    + '<step label="Three">\nAlso done.\n</step>\n'
    + "</flow>\n"
)


@pytest.mark.parametrize(
    "theme_ref", ["default", BOOK_THEME], ids=["builtin", "book-v2"]
)
def test_vertical_compare_sides_stack_intrinsically(tmp_path, theme_ref):
    """Unbalanced vertical compare: side B starts below ALL of side A's
    rendered descendants; nothing from A crosses into B."""
    _, build = _build(tmp_path, UNBALANCED_COMPARE, theme_ref)
    sides = sorted(_boxes_by_class(build, "pd-compare-side"),
                   key=lambda b: b.position_y)
    assert len(sides) == 2
    a, b = sides
    a_bottom = _descendant_bottom(a)
    assert b.position_y >= a_bottom - 0.5, (
        f"side B top {b.position_y} < side A descendant bottom {a_bottom}"
    )


@pytest.mark.parametrize(
    "theme_ref", ["default", BOOK_THEME], ids=["builtin", "book-v2"]
)
def test_vertical_flow_steps_stack_intrinsically(tmp_path, theme_ref):
    """Unbalanced vertical flow: each step starts below the previous
    step's actual descendants."""
    _, build = _build(tmp_path, UNBALANCED_FLOW, theme_ref)
    steps = sorted(_boxes_by_class(build, "pd-step"),
                   key=lambda b: b.position_y)
    assert len(steps) == 3
    for prev, nxt in zip(steps, steps[1:]):
        assert nxt.position_y >= _descendant_bottom(prev) - 0.5


@pytest.mark.parametrize(
    "theme_ref", ["default", BOOK_THEME], ids=["builtin", "book-v2"]
)
def test_horizontal_compare_still_shares_width(tmp_path, theme_ref):
    """Horizontal regression: sides still split the row width."""
    body = (
        '<compare layout="horizontal" labels="A|B">\n'
        "<result>\nside a\n</result>\n<result>\nside b\n</result>\n"
        "</compare>\n"
    )
    _, build = _build(tmp_path, body, theme_ref)
    sides = sorted(_boxes_by_class(build, "pd-compare-side"),
                   key=lambda b: b.position_x)
    assert len(sides) == 2
    assert abs(sides[0].width - sides[1].width) < 2.0
    assert sides[1].position_x > sides[0].position_x


@pytest.mark.parametrize(
    "theme_ref", ["default", BOOK_THEME], ids=["builtin", "book-v2"]
)
def test_horizontal_flow_still_shares_width(tmp_path, theme_ref):
    body = (
        '<flow layout="horizontal">\n'
        '<step label="1">\nprepare\n</step>\n<step label="2">\nverify\n</step>\n'
        "</flow>\n"
    )
    _, build = _build(tmp_path, body, theme_ref)
    steps = sorted(_boxes_by_class(build, "pd-step"),
                   key=lambda b: b.position_x)
    assert len(steps) == 2
    assert abs(steps[0].width - steps[1].width) < 2.0
    assert steps[1].position_x > steps[0].position_x


# ---------------- PDF-level overlap regression ----------------------------


def test_gallery_page6_no_text_overlap_pdf():
    """The reviewed defect: the corrected vertical compare on
    cmp-long-compare-containment must have no inter-side text overlap in the emitted
    PDF (MuPDF text boxes)."""

    import pymupdf

    doc = load_document(
        os.path.join(
            REPO_ROOT,
            "examples/composition-gallery/document.yaml",
        ),
        get_registry(),
    )
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    import io

    pdf = pymupdf.open(stream=build.rendered.pdf_bytes(),
                       filetype="pdf")
    page = pdf[5]
    assert page.get_label() is not None
    words = page.get_text("words")
    # 'AFTER' label marks the top of the second compare side
    after = [w for w in words if w[4] == "AFTER"]
    assert after, "AFTER label missing"
    side2_top = min(w[1] for w in after)
    side1 = [w for w in words if w[3] <= side2_top + 0.1]
    side2 = [w for w in words if w[1] >= side2_top - 0.1]
    first_bottom = max(w[3] for w in side1)
    second_top = min(w[1] for w in side2)
    assert second_top >= first_bottom - 0.5
    # no inter-side text intersection anywhere
    for w2 in side2:
        for w1 in side1:
            assert not (
                w1[1] < w2[3] - 0.5 and w2[1] < w1[3] - 0.5
                and w1[0] < w2[2] - 1 and w2[0] < w1[2] - 1
            ), f"{w1[4]!r} overlaps {w2[4]!r}"
    migrated = [w for w in words if w[4] == "Migrated."]
    checklist17 = [
        w for w in words if w[4] == "17:"
    ]
    assert migrated and checklist17
    assert all(m[1] >= max(c[3] for c in checklist17) - 0.5 or
               m[1] > max(c[3] for c in checklist17)
               for m in migrated)


# ---------------- trace outcomes ------------------------------------------


def test_outcome_selected(tmp_path):
    from test_composition import _build, _tall_paras

    body = (
        '<compare layout="auto" labels="A|B">\n'
        f"<result>\n{_tall_paras(20)}\n</result>\n<result>\nOK\n</result>\n</compare>\n"
    )
    _, build = _build(tmp_path, [body])
    pt = build.composition.pages[0]
    d = pt.to_dict()
    assert d["triggered"] and d["evaluated"] > 0
    assert d.get("selected")
    assert d["outcome"] == "selected"


def test_outcome_no_fit(tmp_path):
    from test_composition import _build, _tall_paras

    huge = _tall_paras(60)
    body = (
        '<compare layout="auto" labels="A|B">\n'
        f"<result>\n{huge}\n</result>\n<result>\n{huge}\n</result>\n</compare>\n"
    )
    _, build = _build(tmp_path, [body])
    d = build.composition.pages[0].to_dict()
    assert d["outcome"] == "no-fit"
    assert d.get("selected") is None and d.get("best_non_fitting")


def test_outcome_too_many_candidates(tmp_path):
    from test_composition import _build, _tall_paras

    blocks = "\n".join(
        '<compare layout="auto" labels="A|B">\n'
        f"<result>\n{_tall_paras(20)}\n</result>\n<result>\nOK\n</result>\n</compare>"
        for _ in range(5)
    )
    _, build = _build(tmp_path, [blocks])
    d = build.composition.pages[0].to_dict()
    assert d["outcome"] == "too-many-candidates"


def test_fitting_page_absent_from_trace(tmp_path):
    from test_composition import _build

    _, build = _build(tmp_path, ["A normal fitting page.\n"])
    assert build.composition.pages == []
    assert build.composition.layout_passes == 1
