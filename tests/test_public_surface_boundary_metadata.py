#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed source contract for public-surface boundary metadata."""

from html.parser import HTMLParser
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BOUNDARY_NAME = "szl-evidence-boundary"
BOUNDARIES = {
    "pages/killinchu.html": (
        "szl.public-surface-boundary/v1;surface=killinchu-console;"
        "effectors=SIMULATED;authorization=UNAVAILABLE"
    ),
    "pages/command-center.html": (
        "szl.public-surface-boundary/v1;surface=a11oy-command;"
        "origin=MODELED;energy=UNAVAILABLE;signer=UNAVAILABLE"
    ),
}


class BoundaryMetadataParser(HTMLParser):
    """Collect source declarations without making rendering claims."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_head = False
        self.head_count = 0
        self.declarations: list[tuple[str | None, bool, bool]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag == "head":
            self.head_count += 1
            self.in_head = True
            return
        if tag != "meta":
            return

        names = [value for key, value in attrs if key == "name"]
        if BOUNDARY_NAME not in names:
            return
        contents = [value for key, value in attrs if key == "content"]
        attributes_are_unique = (
            names == [BOUNDARY_NAME]
            and len(contents) == 1
            and contents[0] is not None
        )
        content = contents[0] if len(contents) == 1 else None
        self.declarations.append((content, self.in_head, attributes_are_unique))

    def handle_startendtag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        if tag == "head":
            self.in_head = False


def assert_exact_boundary(source: str, expected_content: str) -> None:
    """Require one exact declaration in head; establish source presence only."""

    parser = BoundaryMetadataParser()
    parser.feed(source)
    parser.close()
    assert parser.head_count == 1, "exactly one head element is required"
    assert len(parser.declarations) == 1, (
        "exactly one szl-evidence-boundary declaration is required"
    )
    content, in_head, attributes_are_unique = parser.declarations[0]
    assert in_head, "szl-evidence-boundary must be declared in head"
    assert attributes_are_unique, (
        "szl-evidence-boundary name and content attributes must be unique"
    )
    assert content == expected_content, "szl-evidence-boundary content mismatch"


def test_source_pages_have_one_exact_declared_boundary() -> None:
    for relative_path, expected_content in BOUNDARIES.items():
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        assert_exact_boundary(source, expected_content)


@pytest.mark.parametrize(
    ("source", "message"),
    [
        ("<html><head></head><body></body></html>", "exactly one"),
        (
            "<html><head>"
            f'<meta name="{BOUNDARY_NAME}" content="expected">'
            f'<meta name="{BOUNDARY_NAME}" content="expected">'
            "</head><body></body></html>",
            "exactly one",
        ),
        (
            "<html><head>"
            f'<meta name="{BOUNDARY_NAME}" content="changed">'
            "</head><body></body></html>",
            "content mismatch",
        ),
        (
            "<html><head></head><body>"
            f'<meta name="{BOUNDARY_NAME}" content="expected">'
            "</body></html>",
            "declared in head",
        ),
    ],
)
def test_invalid_boundary_declarations_fail_closed(source: str, message: str) -> None:
    with pytest.raises(AssertionError, match=message):
        assert_exact_boundary(source, "expected")
