"""M2 layout tests — all fit/overflow assertions go through the real
WeasyPrint layout (the authoritative engine), not CSS string matching."""

import os

import pytest

from pagedoc.backends import weasyprint
from pagedoc.document import load_document
from pagedoc.pipeline import build_document
from pagedoc.registry import get_registry
from pagedoc.theme.loader import load_theme

from conftest import FIXTURES, REPO_ROOT, write_page

GALLERY = os.path.join(REPO_ROOT, "examples", "layout-gallery")
OVERFLOW = os.path.join(FIXTURES, "overflow")


def _build_doc(tmp_path, page_texts: list[str]):
    os.makedirs(tmp_path / "pages", exist_ok=True)
    lines = ["id: d", "title: Doc", "theme: default", "pages:"]
    for i, body in enumerate(page_texts):
        name = f"pages/{i:02d}.book.md"
        fm = f"---\nid: page-{i}\ngroup: G\ntitle: P{i}\n---\n"
        write_page(tmp_path, body, name=name, fm=fm)
        lines.append(f"  - {name}")
    manifest = tmp_path / "document.yaml"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    doc = load_document(str(manifest), get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    return doc, build_document(doc, theme, get_registry())


def test_one_logical_page_one_physical_page(tmp_path):
    doc, build = _build_doc(tmp_path, ["Hello page.\n"])
    assert build.layout.physical_page_count == 1
    assert build.layout.pages[0].fits


def test_multi_page_physical_count(tmp_path):
    doc, build = _build_doc(tmp_path, ["First.\n", "Second.\n", "Third.\n"])
    assert build.layout.physical_page_count == 3
    assert [p.page_id for p in build.layout.pages] == [pg.page_id for pg in doc.pages]


def test_block_count_and_metrics(tmp_path):
    doc, build = _build_doc(
        tmp_path, ["One.\n\nTwo.\n\n<note>\nn\n</note>\n"]
    )
    pl = build.layout.pages[0]
    assert pl.block_count == 3
    assert 0 < pl.content_used < pl.content_available
    assert pl.overflow_px == 0


def test_data_pd_node_mapping(tmp_path):
    doc, build = _build_doc(tmp_path, ["Hello.\n\n<request>\nGET /x\n</request>\n"])
    html = build.html
    assert 'data-pd-node="p0"' in html  # page
    assert 'data-pd-node="p0n1"' in html  # first block
    ids = {b.node_id for b in build.layout.pages[0].blocks}
    assert ids  # placements recorded
    ref = build.node_map["p0n1"]
    assert ref.node.source.start_line == 7


def test_node_ids_stable_across_renders(tmp_path):
    doc, theme = _doc_theme(tmp_path, ["Hi.\n\n<request>\nGET /x\n</request>\n"])
    from pagedoc.render.html import render_document

    r1 = render_document(doc, theme)
    r2 = render_document(doc, theme)
    assert r1.html == r2.html
    assert sorted(r1.node_map) == sorted(r2.node_map)


def _doc_theme(tmp_path, page_texts):
    os.makedirs(tmp_path / "pages", exist_ok=True)
    lines = ["id: d", "title: Doc", "theme: default", "pages:"]
    for i, body in enumerate(page_texts):
        name = f"pages/{i:02d}.book.md"
        write_page(tmp_path, body, name=name)
        lines.append(f"  - {name}")
    manifest = tmp_path / "document.yaml"
    manifest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    doc = load_document(str(manifest), get_registry())
    return doc, load_theme(doc.theme, doc.manifest_dir)


def test_fixed_page_shell_html(tmp_path):
    doc, theme = _doc_theme(tmp_path, ["Hello.\n"])
    from pagedoc.render.html import render_document

    html = render_document(doc, theme).html
    assert 'class="pd-region pd-region-header"' in html
    assert 'class="pd-region pd-region-content pd-page-content"' in html
    assert 'class="pd-region pd-region-footer"' in html
    assert f"size: {theme.page_width:g}px {theme.page_height:g}px" in html
    assert f"width: {theme.page_width:g}px; height: {theme.page_height:g}px" in html
    # theme regions emitted as CSS, not inline author geometry
    assert 'left: 64px' in html
    assert 'Page 1 / 1' not in html  # footer uses "1 / 1"


# ---------------- row splits ----------------------------------------------


def _resolved(build, node_id, key):
    return build.resolved.get(f"{node_id}:{key}")


def test_row_split_presets_render(tmp_path):
    for split in ("equal", "wide-left", "wide-right"):
        _, build = _build_doc(
            tmp_path / split,
            [
                f'<row split="{split}">\n<request>\nA\n</request>\n'
                "<response>\nB\n</response>\n</row>\n"
            ],
        )
        assert f'pd-row--split-{split}' in build.html
        page = build.layout.pages[0]
        assert page.fits
        row_nid = next(
            n for n, r in build.node_map.items()
            if getattr(r.node, "name", None) == "row"
        )
        assert _resolved(build, row_nid, "split") == split


def test_row_auto_rules(tmp_path):
    cases = [
        ("request", "note", "wide-left"),
        ("note", "request", "wide-right"),
        ("request", "response", "equal"),
        ("media", "note", "wide-left"),
        ("note", "note", "equal"),
    ]
    for i, (a, b, expected) in enumerate(cases):
        d = tmp_path / f"c{i}"
        os.makedirs(d / "pages", exist_ok=True)
        src = {"request": "<request>\nx\n</request>", "response": "<response>\nx\n</response>",
               "note": "<note>\nx\n</note>"}
        if "media" in (a, b):
            (d / "pages").mkdir(exist_ok=True)
            (d / "a.png").write_bytes(b"x")
            src["media"] = '<media src="../a.png" alt="x">\n</media>'
        body = f"<row>\n{src[a]}\n{src[b]}\n</row>\n"
        write_page(d, body, name="pages/p.book.md")
        (d / "document.yaml").write_text(
            "id: d\ntitle: D\npages:\n  - pages/p.book.md\n", encoding="utf-8")
        doc = load_document(str(d / "document.yaml"), get_registry())
        theme = load_theme(doc.theme, doc.manifest_dir)
        build = build_document(doc, theme)
        row_nid = next(
            n for n, r in build.node_map.items()
            if getattr(r.node, "name", None) == "row"
        )
        assert _resolved(build, row_nid, "split") == expected, (a, b)


# ---------------- compare / flow ------------------------------------------


def test_compare_horizontal(tmp_path):
    _, build = _build_doc(
        tmp_path,
        ['<compare layout="horizontal">\n<result>\nA\n</result>\n'
         "<result>\nB\n</result>\n</compare>\n"],
    )
    nid = _by_name(build, "compare")
    assert _resolved(build, nid, "layout") == "horizontal"
    assert "pd-compare--layout-horizontal" in build.html
    assert build.layout.pages[0].fits


def test_compare_vertical(tmp_path):
    _, build = _build_doc(
        tmp_path,
        ['<compare layout="vertical">\n<result>\nA\n</result>\n'
         "<result>\nB\n</result>\n</compare>\n"],
    )
    assert "pd-compare--layout-vertical" in build.html
    assert _resolved(build, _by_name(build, "compare"), "layout") == "vertical"


def _by_name(build, name):
    return next(
        n for n, r in build.node_map.items()
        if getattr(r.node, "name", None) == name
    )


def test_compare_auto_prefers_horizontal(tmp_path):
    _, build = _build_doc(
        tmp_path,
        ["<compare>\n<result>\nshort\n</result>\n<result>\nalso short\n</result>\n</compare>\n"],
    )
    assert _resolved(build, _by_name(build, "compare"), "layout") == "horizontal"
    assert build.layout.pages[0].fits


def test_compare_auto_flips_to_vertical_on_fit(tmp_path):
    tall = "\n\n".join(
        f"Verification point {i} covering several aspects of expected behavior."
        for i in range(20)
    )
    body = (
        '<compare layout="auto" labels="Expected|Actual">\n'
        f"<result>\n{tall}\n</result>\n<result>\nOK\n</result>\n</compare>\n"
    )
    _, build = _build_doc(tmp_path, [body])
    nid = _by_name(build, "compare")
    assert _resolved(build, nid, "layout") == "vertical"
    assert build.layout.pages[0].fits
    assert build.diagnostics == []


def test_flow_horizontal_and_vertical(tmp_path):
    for layout in ("horizontal", "vertical"):
        d = tmp_path / layout
        steps = "".join(
            f'<step label="S{i}">\ntext {i}\n</step>\n' for i in range(3)
        )
        _, build = _build_doc(d, [f'<flow layout="{layout}">\n{steps}</flow>\n'])
        nid = _by_name(build, "flow")
        assert _resolved(build, nid, "layout") == layout
        assert f"pd-flow--layout-{layout}" in build.html


def test_flow_auto(tmp_path):
    steps = "".join(f'<step label="S{i}">\nt{i}\n</step>\n' for i in range(4))
    _, build = _build_doc(tmp_path, [f"<flow>\n{steps}</flow>\n"])
    nid = _by_name(build, "flow")
    resolved = _resolved(build, nid, "layout")
    assert resolved in ("horizontal", "vertical")
    assert build.layout.pages[0].fits


# ---------------- media ---------------------------------------------------


def test_media_contain_and_cover(tmp_path):
    (tmp_path / "pages").mkdir()
    import struct, zlib

    def _png(path):
        # minimal valid 1x1 PNG
        sig = b"\x89PNG\r\n\x1a\n"
        def chunk(t, d):
            c = struct.pack(">I", len(d)) + t + d
            return c + struct.pack(">I", zlib.crc32(t + d))
        ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        idat = chunk(b"IDAT", zlib.compress(b"\x00\xff\x00\x00"))
        iend = chunk(b"IEND", b"")
        path.write_bytes(sig + ihdr + idat + iend)

    _png(tmp_path / "pic.png")
    for fit in ("contain", "cover"):
        d = tmp_path / fit
        (d / "pages").mkdir(parents=True)
        (d / "pic.png").write_bytes((tmp_path / "pic.png").read_bytes())
        write_page(d, f'<media src="../pic.png" alt="A" fit="{fit}">\ncap\n</media>\n',
                   name="pages/p.book.md")
        (d / "document.yaml").write_text(
            "id: d\ntitle: D\npages:\n  - pages/p.book.md\n", encoding="utf-8")
        doc = load_document(str(d / "document.yaml"), get_registry())
        theme = load_theme(doc.theme, doc.manifest_dir)
        build = build_document(doc, theme)
        assert build.diagnostics == []
        assert f"pd-media--fit-{fit}" in build.html
        assert 'src="pic.png"' in build.html
        assert build.layout.pages[0].fits


# ---------------- overflow -------------------------------------------------


@pytest.mark.parametrize("fixture", ["prose", "table", "code", "row", "compare"])
def test_overflow_fixtures_fail_with_source_location(fixture):
    manifest = os.path.join(OVERFLOW, fixture, "document.yaml")
    doc = load_document(manifest, get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    assert build.diagnostics, fixture
    d = build.diagnostics[0]
    assert "overflow" in d.message or "exceeds" in d.message
    assert d.path.endswith(".book.md")
    assert d.line > 0
    # still exactly one physical page — no silent spill
    assert build.layout.physical_page_count == 1


def test_overflow_diagnostic_names_component():
    manifest = os.path.join(OVERFLOW, "code", "document.yaml")
    doc = load_document(manifest, get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    assert "<request>" in build.diagnostics[0].message


def test_fit_page_does_not_fail(tmp_path):
    _, build = _build_doc(tmp_path, ["short\n"])
    assert build.diagnostics == []
    assert build.layout.pages[0].fits


# ---------------- fonts ---------------------------------------------------


def _write_test_font(path):
    """Build a minimal valid TTF via fontTools (a WeasyPrint dependency)."""

    from fontTools.fontBuilder import FontBuilder
    from fontTools.pens.ttGlyphPen import TTGlyphPen

    fb = FontBuilder(1024)
    fb.setupGlyphOrder([".notdef", "A"])
    fb.setupCharacterMap({65: "A"})
    pen = TTGlyphPen(None)
    gnotdef = pen.glyph()
    pen = TTGlyphPen(None)
    pen.moveTo((50, 0))
    pen.lineTo((250, 700))
    pen.lineTo((450, 0))
    pen.closePath()
    fb.setupGlyf({".notdef": gnotdef, "A": pen.glyph()})
    fb.setupHorizontalMetrics({".notdef": (500, 0), "A": (550, 0)})
    fb.setupHorizontalHeader(ascent=800, descent=-200)
    fb.setupNameTable({"familyName": "PDTest", "styleName": "Regular"})
    fb.setupOS2()
    fb.setupPost()
    fb.setupHead()
    fb.save(str(path))


def test_theme_local_font_used_in_render(tmp_path):
    font_path = tmp_path / "PDTest.ttf"
    _write_test_font(font_path)
    (tmp_path / "theme.css").write_text("body {}", encoding="utf-8")
    (tmp_path / "theme.yaml").write_text(
        "id: t\n"
        "page: {width: 794, height: 1123, unit: px}\n"
        "regions:\n"
        "  content: {x: 64, y: 116, width: 666, height: 900}\n"
        "fonts:\n  prose: {family: \"'PDTest'\", source: PDTest.ttf}\n"
        "css: theme.css\n",
        encoding="utf-8",
    )
    (tmp_path / "pages").mkdir(exist_ok=True)
    write_page(tmp_path, "AAAA\n", name="pages/p.book.md")
    (tmp_path / "document.yaml").write_text(
        "id: d\ntitle: D\ntheme: theme.yaml\npages:\n  - pages/p.book.md\n",
        encoding="utf-8",
    )
    doc = load_document(str(tmp_path / "document.yaml"), get_registry())
    theme = load_theme(doc.theme, doc.manifest_dir)
    build = build_document(doc, theme)
    assert "@font-face" in build.html
    assert "url('PDTest.ttf')" in build.html
    assert build.diagnostics == []
    data = weasyprint.pdf_bytes(build.html, base_url=doc.manifest_dir)
    assert data.startswith(b"%PDF-")
