# PageDoc Public Python API (M3.2)

`import pagedoc` is the supported integration surface. Everything else —
parser, theme loader, pipeline internals, backend adapters — is private
implementation detail and may change between versions.

```python
import pagedoc

compiled = pagedoc.compile_document("document.yaml")

if not compiled.fits:
    for d in compiled.diagnostics:
        print(d.format())
    raise SystemExit(1)

artifact = compiled.write_pdf("dist/book.pdf")
print(artifact.sha256)
```

## Top-level exports

```python
pagedoc.compile_document(manifest_path) -> CompiledDocument
pagedoc.inspect_document(manifest_path) -> InspectionReport
pagedoc.lint_document(manifest_path)    -> LintResult

pagedoc.CompiledDocument
pagedoc.InspectionReport
pagedoc.LintResult
pagedoc.ArtifactInfo
pagedoc.PageDocError
pagedoc.Diagnostic
pagedoc.__version__
```

`manifest_path` accepts `str` or `os.PathLike`. All functions are
silent (no stdout/stderr), never mutate the process working directory,
and never fetch remote assets — page, theme, font, and media paths
resolve relative to their documented owners.

Parse/validation/theme errors raise `PageDocError` carrying structured
`Diagnostic` values. Layout/composition failures instead return a
`CompiledDocument` with `fits == False` so callers can inspect them
programmatically.

## CompiledDocument

```python
compiled.document_id       # str
compiled.theme_id          # str
compiled.pages_logical     # authored page count
compiled.pages_physical    # emitted page count (always equal on success)
compiled.fits              # True only when there are no build diagnostics
compiled.diagnostics       # tuple[Diagnostic, ...]
compiled.html              # deterministic HTML — also available when
                           # the build does NOT fit (debugging artifact)
compiled.inspection        # InspectionReport

compiled.pdf_bytes()                        # canonical vector PDF
compiled.flattened_pdf_bytes(dpi=144)       # optional raster derivative

compiled.write_html(path)                   # -> ArtifactInfo
compiled.write_pdf(path)                    # -> ArtifactInfo
compiled.write_flattened_pdf(path, dpi=144) # -> ArtifactInfo
```

The vector PDF is the canonical layout artifact: it is serialized from
the same measured backend document that diagnostics inspected — calling
`pdf_bytes()` or `write_pdf()` never triggers a second layout pass.
`flattened_pdf_bytes`/`write_flattened_pdf` rasterize that vector PDF
(`pagedoc[raster]` extras: PDFium → PNG → img2pdf); they never re-lay
out HTML.

Invalid builds (`fits == False`) refuse final PDF emission:
`pdf_bytes`, `flattened_pdf_bytes`, `write_pdf`, and
`write_flattened_pdf` raise `PageDocError` with the build diagnostics.
`html` and `write_html` remain available so failures can be debugged.

## ArtifactInfo

```python
artifact = compiled.write_pdf("dist/book.pdf")

artifact.kind    # "html" | "pdf" | "flattened-pdf"
artifact.path    # final path as written
artifact.bytes   # exact byte count
artifact.sha256  # SHA-256 of the exact bytes written
```

Writes are atomic: bytes go to a temporary file in the destination
directory, are fsync'd, and are published via `os.replace`. Missing
parent directories are created; a failed write never leaves a partial
final file. Artifact metadata contains no timestamps or host data.

## InspectionReport

```python
report = compiled.inspection
# or: report = pagedoc.inspect_document("document.yaml")

payload = report.to_dict()   # deterministic dict, schema_version == 1
text    = report.to_json()   # sort_keys=True, trailing newline
```

Schema v1 payload keys: `schema_version`, `document`, `manifest`,
`theme`, `typography_portable`, `pages_logical`, `pages_physical`,
`all_fit`, `composition`, `diagnostics`, `pages`.

`all_fit` mirrors `CompiledDocument.fits`: true only when the build
produced no diagnostics (overflow, dropped/missing authored blocks,
and composition search failures all count). Each page entry carries
`blocks_expected`, `blocks_rendered`, and `blocks_missing`; a page's
`fit` is false when authored top-level blocks were dropped by the
backend.

## lint_document

```python
result = pagedoc.lint_document("document.yaml")
result.document_id, result.title, result.manifest_path, result.page_count
```

Lint validates the manifest, page parsing, and the component registry —
no layout backend is invoked. Failures raise `PageDocError`.

## Relationship to the CLI

`pagedoc lint`, `pagedoc render`, and `pagedoc inspect` are thin
adapters over this API and produce byte-identical artifacts. Only
`pagedoc ast` uses parser internals directly (AST developer tooling).
