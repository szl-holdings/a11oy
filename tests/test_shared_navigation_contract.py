# SPDX-License-Identifier: Apache-2.0
"""Prevent high-value standalone surfaces from becoming dead ends."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SURFACES = (
    ROOT / "console" / "static" / "viz" / "router" / "index.html",
    ROOT / "pages" / "superpowers.html",
    ROOT / "pages" / "observability.html",
)


def test_standalone_surfaces_expose_shared_navigation() -> None:
    for path in SURFACES:
        html = path.read_text(encoding="utf-8")
        assert 'aria-label="a11oy navigation"' in html, path
        for href in ("/", "/ecosystem", "/anatomy-v5", "/console"):
            assert f'href="{href}"' in html, (path, href)
