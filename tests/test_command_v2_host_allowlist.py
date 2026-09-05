# SPDX-License-Identifier: Apache-2.0
"""Command v2 must never trust a hostname merely because it ends in brand text."""
from __future__ import annotations

from pathlib import Path

PAGE = Path("pages/command-v2.html")


def test_same_origin_api_selection_uses_an_exact_host_allowlist() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "const SAME_ORIGIN_HOSTS = new Set([" in source
    for hostname in (
        '"a-11-oy.com"',
        '"www.a-11-oy.com"',
        '"szlholdings-a11oy.hf.space"',
    ):
        assert hostname in source
    assert "SAME_ORIGIN_HOSTS.has(location.hostname.toLowerCase())" in source

    # These substring tests admit attacker-controlled prefixes such as
    # evil-a-11-oy.com and unrelated hosts containing hf.space in a label.
    assert 'endsWith("a-11-oy.com")' not in source
    assert 'includes("hf.space")' not in source


def test_unknown_hosts_fall_back_to_the_canonical_product_origin() -> None:
    source = PAGE.read_text(encoding="utf-8")
    expected = '''const ORIGIN = SAME_ORIGIN_HOSTS.has(location.hostname.toLowerCase())
  ? ""
  : "https://a-11-oy.com";'''
    assert expected in source
    assert "https://a11oy.com" not in source
