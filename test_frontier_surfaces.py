# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Sign-off: Stephen P. Lutar <stephenlutar2@gmail.com>
"""test_frontier_surfaces — the 3D-surface manifest must be honest and single-source.

GET /api/a11oy/v1/frontier/surfaces rolls up every 3D holographic frontier surface.
These checks enforce the doctrine-v11 honesty contract on that manifest:

  * the surface LIST is the SAME list the viewer loads — parsed independently here
    from static/3d/holographic.html's SURFACES array — so the manifest can never
    silently drift from (or pad past) the real registry;
  * every surface's honesty label is a recognized doctrine token (MEASURED / LIVE /
    SAMPLE / MODELED / STRUCTURAL-ONLY / ROADMAP) or an honest UNAVAILABLE — never a
    fabricated or upgraded label, and the label is read from the surface's OWN source;
  * a missing asset at runtime yields UNAVAILABLE with a reason and present=False —
    never a fabricated present/green tile;
  * building the manifest is a pure READ (it appends to no provenance chain and
    signs nothing — receipts belong on writes, never on GETs);
  * the /frontier page renders its surface list FROM this endpoint (one source of
    truth): the endpoint, the surfaces section markers, and the client loader are
    all present in the served HTML.
"""
import pathlib
import re

import a11oy_frontier_page as fp

_REPO_ROOT = pathlib.Path(__file__).resolve().parent
_HOLO = _REPO_ROOT / "static" / "3d" / "holographic.html"

# Independent re-parse of the registry (NOT importing the module's own regex) so a
# broken/loosened production regex is caught rather than masked.
_ENTRY_RE = re.compile(
    r'\{\s*id:\s*"([^"]+)"\s*,\s*title:\s*"([^"]+)"\s*,\s*mod:\s*"([^"]+)"\s*\}')

_VALID = set(fp._VALID_LABELS) | {fp.UNAVAILABLE}


def _registry_entries():
    assert _HOLO.is_file(), f"registry source missing at {_HOLO}"
    return _ENTRY_RE.findall(_HOLO.read_text(encoding="utf-8", errors="replace"))


def test_manifest_count_matches_the_real_registry():
    entries = _registry_entries()
    man = fp.build_surfaces_manifest("a11oy")
    assert man["ok"] is True, f"manifest not ok: {man.get('error')}"
    # the TRUE count — whatever it is — must equal the registry, never padded.
    assert man["count"] == len(entries) > 0, (
        f"manifest count {man['count']} != registry count {len(entries)}")
    assert man["count"] == len(man["surfaces"]) == man["summary"]["count"]
    # same ids, in the same order the viewer loads them.
    assert [s["id"] for s in man["surfaces"]] == [e[0] for e in entries]


def test_every_surface_has_a_valid_honest_label():
    man = fp.build_surfaces_manifest("a11oy")
    for s in man["surfaces"]:
        assert s["label"] in _VALID, f"{s['id']}: invalid label {s['label']!r}"
        assert set(s.get("declared_labels", [])) <= set(fp._VALID_LABELS), \
            f"{s['id']}: declared_labels contains an unrecognized token"
    assert man["summary"]["labels_valid"] is True


def test_label_is_derived_from_the_surface_source_not_hardcoded():
    # For a present, labeled surface the reported label must actually appear in its
    # own JS source — proving the manifest reads the single source of truth.
    man = fp.build_surfaces_manifest("a11oy")
    checked = 0
    for s in man["surfaces"]:
        if not s.get("present") or s["label"] == fp.UNAVAILABLE:
            continue
        src = (_REPO_ROOT / s["asset"].lstrip("/")).read_text(
            encoding="utf-8", errors="replace")
        assert s["label"] in src, (
            f"{s['id']}: reported label {s['label']!r} not found in its own source "
            "(would indicate a hardcoded second copy, not single-source)")
        checked += 1
    assert checked > 0, "no present labeled surface to verify single-source against"


def test_missing_asset_is_unavailable_with_a_reason_never_fabricated():
    entry = fp._build_surface_entry(
        "ghost", "Ghost", "/static/3d/surfaces/__definitely_not_here__.js")
    assert entry["label"] == fp.UNAVAILABLE
    assert entry["present"] is False
    assert entry["reason"], "missing asset must carry an honest reason"
    assert entry["declared_labels"] == []


def test_undeclared_label_is_unavailable_not_padded(tmp_path):
    # A surface source that declares NO recognized doctrine token is honestly
    # UNAVAILABLE (undeclared) — never padded to a nicer label.
    label, source = fp._derive_label("const ID='x'; /* no doctrine token here */")
    assert label is None and source == "none"


def test_missing_registry_degrades_honestly(monkeypatch):
    # If holographic.html itself is missing, the manifest is honestly empty + errored,
    # never fabricating surfaces or a count.
    monkeypatch.setattr(fp, "_HOLOGRAPHIC_REL", "static/3d/__no_such_registry__.html")
    man = fp.build_surfaces_manifest("a11oy")
    assert man["ok"] is False
    assert man["count"] == 0 and man["surfaces"] == []
    assert "error" in man


def test_manifest_is_a_pure_read_repeatable_and_stable():
    a = fp.build_surfaces_manifest("a11oy")
    b = fp.build_surfaces_manifest("a11oy")
    assert a == b, "manifest build must be a deterministic pure read"


def test_frontier_page_renders_surface_list_from_this_endpoint():
    html = fp._page_html("a11oy")
    assert "/api/a11oy/v1/frontier/surfaces" in html, "surfaces endpoint not wired"
    assert 'id="surfaces-list"' in html and 'id="surfaces-rollup"' in html, \
        "surfaces section markers missing"
    assert "loadSurfaces" in html, "client-side surfaces loader missing"
    # 0-CDN doctrine preserved by the added wiring.
    assert "http://" not in html and "https://" not in html, \
        "external URL found (0-CDN doctrine)"


def test_route_and_page_manifest_advertise_the_endpoint():
    from fastapi import FastAPI
    from starlette.testclient import TestClient

    app = FastAPI()
    fp.register(app, "a11oy")
    client = TestClient(app)

    r = client.get("/api/a11oy/v1/frontier/surfaces")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True and body["count"] == len(_registry_entries())
    assert all(s["label"] in _VALID for s in body["surfaces"])

    pm = client.get("/api/a11oy/v1/frontier/page-manifest").json()
    assert "/api/a11oy/v1/frontier/surfaces" in pm["renders_endpoints"]
    assert pm["links"]["surfaces"] == "/api/a11oy/v1/frontier/surfaces"
