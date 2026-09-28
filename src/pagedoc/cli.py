"""PageDoc command line interface.

    pagedoc lint <document.yaml>               validate only
    pagedoc ast <page.book.md>                 inspect/emit AST JSON
    pagedoc render <document.yaml>             --html-out/--pdf-out (>=1)
    pagedoc inspect <document.yaml> [--json]   deterministic layout report

Authoring and layout failures are reported as path:line:col diagnostics
without Python tracebacks (--verbose/-v shows the traceback for debugging).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from typing import Any

from .ast import dumps_page
from .document import load_document
from .errors import PageDocError
from .parser import parse_page_file
from .pipeline import BuildResult, build_document
from .registry import get_registry
from .theme.loader import load_theme
from .validation import validate_page


def _print_diagnostics(e: PageDocError) -> None:
    for d in e.diagnostics:
        print(f"{d.path}:{d.line}:{d.col}: {d.message}", file=sys.stderr)


def _print_diagnostic_list(diagnostics) -> None:
    for d in diagnostics:
        print(f"{d.path}:{d.line}:{d.col}: {d.message}", file=sys.stderr)


def _cmd_lint(args) -> int:
    try:
        doc = load_document(args.document, get_registry())
    except PageDocError as e:
        _print_diagnostics(e)
        return 1
    print(f"{args.document}: OK ({len(doc.pages)} pages)")
    return 0


def _cmd_ast(args) -> int:
    registry = get_registry()
    try:
        page = parse_page_file(args.page, registry)
        diags = validate_page(page, registry)
        if diags:
            raise PageDocError(*diags)
    except PageDocError as e:
        _print_diagnostics(e)
        return 1
    sys.stdout.write(dumps_page(page))
    return 0


def _cmd_render(args) -> int:
    if not args.html_out and not args.pdf_out:
        print("render: at least one of --html-out/--pdf-out is required", file=sys.stderr)
        return 1
    registry = get_registry()
    try:
        doc = load_document(args.document, registry)
        theme = load_theme(doc.theme, doc.manifest_dir)
        build = build_document(doc, theme, registry)
    except PageDocError as e:
        _print_diagnostics(e)
        return 1
    if args.html_out:
        out_dir = os.path.dirname(args.html_out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        with open(args.html_out, "w", encoding="utf-8", newline="\n") as f:
            f.write(build.html)
        print(f"wrote {args.html_out} ({len(doc.pages)} pages)")
    if build.diagnostics:
        _print_diagnostic_list(build.diagnostics)
        return 1
    if args.pdf_out:
        from .backends import weasyprint

        out_dir = os.path.dirname(args.pdf_out)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        weasyprint.write_pdf(build.html, _base_url_for(doc), args.pdf_out)
        print(f"wrote {args.pdf_out} ({len(doc.pages)} pages)")
    return 0


def _base_url_for(doc) -> str:
    import pathlib

    return pathlib.Path(os.path.abspath(doc.manifest_dir)).as_uri() + "/"


def _inspect_payload(doc, build: BuildResult) -> dict[str, Any]:
    pages: list[dict[str, Any]] = []
    for pl in build.layout.pages:
        resolved: dict[str, str] = {}
        for key, value in sorted(build.resolved.items()):
            node_id, what = key.rsplit(":", 1)
            ref = build.node_map.get(node_id)
            if ref is not None and ref.page_index == pl.index:
                resolved[node_id] = value
        pages.append(
            {
                "index": pl.index,
                "page_id": pl.page_id,
                "fit": pl.fits,
                "blocks": pl.block_count,
                "content_used_px": (
                    round(pl.content_used, 1) if pl.content_used is not None else None
                ),
                "content_available_px": (
                    round(pl.content_available, 1)
                    if pl.content_available is not None
                    else None
                ),
                "overflow_px": round(pl.overflow_px, 1),
                "width_overflow_px": round(pl.width_overflow_px, 1),
                "last_block": pl.last_block_id,
                "resolved": resolved,
            }
        )
    return {
        "document": doc.doc_id,
        "manifest": doc.manifest_path,
        "pages_logical": len(doc.pages),
        "pages_physical": build.layout.physical_page_count,
        "all_fit": build.layout.all_fit
        and build.layout.physical_page_count == len(doc.pages),
        "pages": pages,
    }


def _cmd_inspect(args) -> int:
    registry = get_registry()
    try:
        doc = load_document(args.document, registry)
        theme = load_theme(doc.theme, doc.manifest_dir)
        build = build_document(doc, theme, registry)
    except PageDocError as e:
        _print_diagnostics(e)
        return 1
    payload = _inspect_payload(doc, build)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(f"document: {doc.doc_id} ({payload['pages_physical']} physical pages)")
        for p in payload["pages"]:
            fit = "PASS" if p["fit"] else "FAIL"
            used = p["content_used_px"]
            avail = p["content_available_px"]
            metrics = ""
            if used is not None and avail is not None:
                metrics = f"  used={used:.0f}px/{avail:.0f}px"
                if p["overflow_px"]:
                    metrics += f"  overflow={p['overflow_px']:.0f}px"
                if p["width_overflow_px"]:
                    metrics += f"  width-overflow={p['width_overflow_px']:.0f}px"
            resolved = (
                "  " + ", ".join(f"{k}={v}" for k, v in sorted(p["resolved"].items()))
                if p["resolved"]
                else ""
            )
            print(f"  page {p['index']}: {p['page_id']}  fit={fit}  blocks={p['blocks']}{metrics}{resolved}")
    if build.diagnostics:
        _print_diagnostic_list(build.diagnostics)
    return 0 if payload["all_fit"] else 1


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pagedoc", description=__doc__)
    p.add_argument("-v", "--verbose", action="store_true", help="show tracebacks on error")
    sub = p.add_subparsers(dest="command", required=True)

    pl = sub.add_parser("lint", help="validate a document")
    pl.add_argument("document")
    pl.set_defaults(func=_cmd_lint)

    pa = sub.add_parser("ast", help="emit deterministic AST JSON for one page")
    pa.add_argument("page")
    pa.set_defaults(func=_cmd_ast)

    pr = sub.add_parser("render", help="render a document")
    pr.add_argument("document")
    pr.add_argument("--html-out", metavar="PATH")
    pr.add_argument("--pdf-out", metavar="PATH")
    pr.set_defaults(func=_cmd_render)

    pi = sub.add_parser("inspect", help="report measured layout per page")
    pi.add_argument("document")
    pi.add_argument("--json", action="store_true", help="machine-readable output")
    pi.set_defaults(func=_cmd_inspect)
    return p


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if getattr(args, "verbose", False):
        return args.func(args)
    try:
        return args.func(args)
    except PageDocError as e:
        _print_diagnostics(e)
        return 1
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    except Exception:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
