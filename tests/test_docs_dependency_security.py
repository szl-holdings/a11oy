#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Manifest/lock regressions; these are not deployed-bundle or browser proofs."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_json(relative):
    return json.loads((ROOT / relative).read_text(encoding="utf-8"))


def test_unused_maplibre_is_not_declared_in_mirrored_web_manifest():
    manifest = read_json("web/package.json")
    for section in ("dependencies", "devDependencies", "optionalDependencies"):
        assert "maplibre-gl" not in manifest.get(section, {})
    # This removal is valid only while the mirrored source has no consumer.
    for path in (ROOT / "web" / "src").rglob("*"):
        if path.suffix in {".ts", ".tsx", ".js", ".jsx", ".mjs", ".css"}:
            assert "maplibre-gl" not in path.read_text(encoding="utf-8"), path


def test_docs_lodash_override_covers_every_locked_copy():
    manifest = read_json("docs/site/package.json")
    packages = read_json("docs/site/package-lock.json")["packages"]
    assert manifest["overrides"]["lodash-es"] == "4.18.1"
    copies = [entry for path, entry in packages.items()
              if path.endswith("node_modules/lodash-es")]
    assert copies, "the test must inspect an actual resolved lodash-es package"
    assert all(entry["version"] == "4.18.1" for entry in copies)
    assert all(entry["integrity"].startswith("sha512-") for entry in copies)


def test_docs_mermaid_remains_in_the_plugins_supported_major():
    manifest = read_json("docs/site/package.json")
    packages = read_json("docs/site/package-lock.json")["packages"]
    assert manifest["devDependencies"]["mermaid"] == "^11.17.2"
    assert packages[""]["devDependencies"]["mermaid"] == "^11.17.2"
    assert packages["node_modules/mermaid"]["version"].startswith("11.")
    plugin = packages["node_modules/vitepress-plugin-mermaid"]
    assert plugin["peerDependencies"]["mermaid"] == "10 || 11"
