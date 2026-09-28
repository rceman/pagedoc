"""Structured diagnostics for authoring errors.

Diagnostics are testable values; the CLI formats them for display.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Diagnostic:
    """A single authoring error tied to a source location."""

    path: str
    line: int
    col: int
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}:{self.col}: {self.message}"


class PageDocError(Exception):
    """Raised when parsing/validation fails with structured diagnostics."""

    def __init__(self, diagnostics: Diagnostic | list[Diagnostic]) -> None:
        if isinstance(diagnostics, Diagnostic):
            diagnostics = [diagnostics]
        self.diagnostics: list[Diagnostic] = list(diagnostics)
        super().__init__("; ".join(d.format() for d in self.diagnostics))
