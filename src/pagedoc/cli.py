"""PageDoc command line interface.

Commands:

- ``pagedoc lint <document.yaml>``
- ``pagedoc ast <page.book.md>``
- ``pagedoc render <document.yaml> --html-out <path>``

Authoring failures print ``path:line:col: message`` diagnostics and exit
non-zero; Python tracebacks only appear with ``--verbose``.
"""

from __future__ import annotations

import argparse
import os
import sys
import traceback

from .ast import dumps_page
from .document import load_document
from .errors import PageDocError
from .parser import parse_page_file
from .registry import get_registry
from .render.html import render_document
from .theme.loader import load_theme
from .validation import validate_page


def _print_diagnostics(error: PageDocError) -> None:
    for diag in error.diagnostics:
        print(diag.format(), file=sys.stderr)


def _cmd_lint(args: argparse.Namespace) -> int:
    registry = get_registry()
    try:
        doc = load_document(args.document, registry)
    except PageDocError as e:
        _print_diagnostics(e)
        return 1
    print(f"{args.document}: OK ({len(doc.pages)} page{'s' if len(doc.pages) != 1 else ''})")
    return 0


def _cmd_ast(args: argparse.Namespace) -> int:
    registry = get_registry()
    try:
        page = parse_page_file(args.page, registry)
        diags = validate_page(page, registry)
        if diags:
            raise PageDocError(diags)
    except PageDocError as e:
        _print_diagnostics(e)
        return 1
    sys.stdout.write(dumps_page(page))
    return 0


def _cmd_render(args: argparse.Namespace) -> int:
    registry = get_registry()
    try:
        doc = load_document(args.document, registry)
        theme = load_theme(doc.theme, doc.manifest_dir)
        html_text = render_document(doc, theme, registry)
    except PageDocError as e:
        _print_diagnostics(e)
        return 1
    out_dir = os.path.dirname(args.html_out)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.html_out, "w", encoding="utf-8", newline="\n") as f:
        f.write(html_text)
    print(f"wrote {args.html_out} ({len(doc.pages)} page{'s' if len(doc.pages) != 1 else ''})")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pagedoc", description="PageDoc M1 toolchain")
    parser.add_argument("--verbose", action="store_true", help="show tracebacks for internal errors")
    sub = parser.add_subparsers(dest="command", required=True)

    p_lint = sub.add_parser("lint", help="validate a document manifest and its pages")
    p_lint.add_argument("document", help="path to document.yaml")
    p_lint.set_defaults(func=_cmd_lint)

    p_ast = sub.add_parser("ast", help="print the serialized AST for one page")
    p_ast.add_argument("page", help="path to a .book.md page")
    p_ast.set_defaults(func=_cmd_ast)

    p_render = sub.add_parser("render", help="render a document to HTML")
    p_render.add_argument("document", help="path to document.yaml")
    p_render.add_argument("--html-out", required=True, help="output HTML file path")
    p_render.set_defaults(func=_cmd_render)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except PageDocError as e:
        _print_diagnostics(e)
        return 1
    except Exception:
        if getattr(args, "verbose", False):
            traceback.print_exc()
        else:
            print("error: internal failure (re-run with --verbose for a traceback)", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
