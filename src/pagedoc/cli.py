"""PageDoc command line interface.

    pagedoc lint <document.yaml>               validate only
    pagedoc ast <page.book.md>                 inspect/emit AST JSON
    pagedoc render <document.yaml>             --html-out/--pdf-out (>=1)
    pagedoc inspect <document.yaml> [--json]   deterministic layout report

The CLI is a thin adapter over the supported public API
(pagedoc.compile_document / inspect_document / lint_document); it owns
no parallel document/theme/build orchestration. ``ast`` is a developer
command and may use the parser directly.

Authoring and layout failures are reported as path:line:col diagnostics
without Python tracebacks (--verbose/-v shows the traceback for debugging).
"""

from __future__ import annotations

import argparse
import sys
import traceback

from .api import compile_document, inspect_document, lint_document
from .ast import dumps_page
from .errors import PageDocError
from .parser import parse_page_file
from .registry import get_registry
from .validation import validate_page


def _print_diagnostics(e: PageDocError) -> None:
    for d in e.diagnostics:
        print(f"{d.path}:{d.line}:{d.col}: {d.message}", file=sys.stderr)


def _cmd_lint(args) -> int:
    try:
        result = lint_document(args.document)
    except PageDocError as e:
        _print_diagnostics(e)
        return 1
    print(f"{args.document}: OK ({result.page_count} pages)")
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
    if not args.html_out and not args.pdf_out and not args.flattened_pdf_out:
        print(
            "render: at least one of --html-out/--pdf-out/--flattened-pdf-out is required",
            file=sys.stderr,
        )
        return 1
    try:
        compiled = compile_document(args.document)
    except PageDocError as e:
        _print_diagnostics(e)
        return 1
    if args.html_out:
        compiled.write_html(args.html_out)
        print(f"wrote {args.html_out} ({compiled.pages_logical} pages)")
    if not compiled.fits:
        _print_diagnostics(PageDocError(list(compiled.diagnostics)))
        return 1
    if args.pdf_out:
        compiled.write_pdf(args.pdf_out)
        print(f"wrote {args.pdf_out} ({compiled.pages_logical} pages)")
    if args.flattened_pdf_out:
        try:
            compiled.write_flattened_pdf(
                args.flattened_pdf_out, dpi=args.flatten_dpi
            )
        except PageDocError as e:
            _print_diagnostics(e)
            return 1
        print(
            f"wrote {args.flattened_pdf_out} ({compiled.pages_logical} pages, "
            f"{args.flatten_dpi} dpi, experimental)"
        )
    return 0


def _cmd_inspect(args) -> int:
    try:
        report = inspect_document(args.document)
    except PageDocError as e:
        _print_diagnostics(e)
        return 1
    payload = report.to_dict()
    if args.json:
        sys.stdout.write(report.to_json())
    else:
        print(
            f"document: {report.document_id} "
            f"({report.pages_physical} physical pages)"
        )
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
        comp = payload["composition"]
        if comp["pages"]:
            print(f"  Composition ({comp['mode']}, {comp['layout_passes']} layout passes):")
            for pt in comp["pages"]:
                print(
                    f"    page {pt['page_id']}: {pt['candidate_space']} candidate"
                    f" assignments, {pt['evaluated']} evaluated"
                )
                if pt.get("selected"):
                    changes = [
                        f"{k}={v}" for k, v in pt["selected"].items()
                    ]
                    print(
                        f"      selected {', '.join(changes)} "
                        f"({pt['selected_deviation_count']} preferred "
                        f"deviation{'s' if pt['selected_deviation_count'] != 1 else ''})"
                    )
                elif pt["outcome"] == "too-many-candidates":
                    print("      too many combinations; make choices explicit")
                else:
                    print("      no fitting assignment found")
    for d in payload["diagnostics"]:
        print(f"{d['path']}:{d['line']}:{d['col']}: {d['message']}", file=sys.stderr)
    return 0 if report.all_fit else 1


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
    pr.add_argument(
        "--flattened-pdf-out",
        metavar="PATH",
        help="EXPERIMENTAL pixel-locked PDF rasterized from the validated vector PDF",
    )
    pr.add_argument(
        "--flatten-dpi",
        metavar="DPI",
        type=int,
        default=144,
        help="raster resolution for --flattened-pdf-out (default 144)",
    )
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
