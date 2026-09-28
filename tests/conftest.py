"""Shared test helpers."""

from __future__ import annotations

import pytest

from pagedoc.parser import parse_page_file, parse_page_text
from pagedoc.registry import get_registry

DEFAULT_FM = """\
---
id: test-page
group: Guide
title: Test Page
---
"""


@pytest.fixture
def registry():
    return get_registry()


def parse_body(body: str, path: str = "test.book.md"):
    """Parse a page whose body is ``body`` with default front matter."""

    return parse_page_text(DEFAULT_FM + "\n" + body, path, get_registry())


def write_page(tmp_path, body: str, name: str = "page.book.md", fm: str = DEFAULT_FM):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(fm + "\n" + body, encoding="utf-8")
    return str(path)
