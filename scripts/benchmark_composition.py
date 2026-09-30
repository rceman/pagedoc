#!/usr/bin/env python3
"""Local composition benchmark — tooling, not a CI gate.

Reports wall-clock timings and authoritative layout-pass counts for the
baseline layout gallery (preferred composition, no search) and the
composition gallery (bounded per-component candidate search).

Usage:

    .venv/bin/python scripts/benchmark_composition.py
"""

from __future__ import annotations

import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from pagedoc.document import load_document
from pagedoc.pipeline import build_document
from pagedoc.registry import get_registry
from pagedoc.render.html import render_document
from pagedoc.theme.loader import load_theme

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOCS = {
    "layout-gallery": os.path.join(
        REPO, "examples", "layout-gallery", "document.yaml"
    ),
    "composition-gallery": os.path.join(
        REPO, "examples", "composition-gallery", "document.yaml"
    ),
}


def timed(fn):
    t0 = time.perf_counter()
    out = fn()
    return out, time.perf_counter() - t0


def bench(manifest: str) -> dict:
    doc, t_parse = timed(
        lambda: load_document(manifest, get_registry())
    )
    theme, t_theme = timed(lambda: load_theme(doc.theme, doc.manifest_dir))
    render, t_html = timed(lambda: render_document(doc, theme))
    build, t_layout = timed(lambda: build_document(doc, theme))
    pdf, t_pdf = timed(lambda: build.rendered.pdf_bytes())
    comp = build.composition
    return {
        "manifest": os.path.relpath(manifest, REPO),
        "pages_logical": len(doc.pages),
        "pages_physical": build.layout.physical_page_count,
        "all_fit": not build.diagnostics,
        "timings_s": {
            "parse": round(t_parse, 3),
            "theme_load": round(t_theme, 3),
            "html_render": round(t_html, 3),
            "layout_and_compose": round(t_layout, 3),
            "pdf_serialize": round(t_pdf, 3),
        },
        "layout_passes": comp.layout_passes,
        "pages_searched": len(comp.pages),
        "candidates_evaluated": sum(p.evaluated for p in comp.pages),
        "pdf_bytes": len(pdf),
    }


def main() -> int:
    results = {name: bench(path) for name, path in DOCS.items()}
    print(json.dumps(results, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
