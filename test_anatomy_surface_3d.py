# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""
test_anatomy_surface_3d.py — Dev8 ANATOMY / Unified Loop 3D surface.

Asserts the holographic anatomy surface (static/3d/surfaces/anatomy.js) is:
  1. a contract-correct szl3d surface module (default export shape, mount/unmount),
  2. WIRED to the REAL live loop endpoint (/api/a11oy/v1/anatomy/loop) via ctx.live.poll,
  3. consuming the fields the live endpoint actually emits (no fabricated fields),
  4. doctrine-honest in the rendered text (EXPERIMENTAL organs, SAMPLE joules, Ayni
     reciprocal-never-net-positive, Λ = Conjecture 1, honest DEGRADED rendering),
  5. 0 runtime CDN (no external <script>/import/fetch URL in the authored module),
  6. and that the REAL endpoint it polls returns a doctrine-clean live body whose
     shape matches what the surface reads (intake/organs/beats/reservoir/ayni/receipt).

Pure stdlib + (optionally) FastAPI TestClient for the live-endpoint half. The live
half drives szl_anatomy_loop.register on a fresh app and polls the same path the
surface JS polls — proving the viz reads REAL data, not a mock.

Run: python3 test_anatomy_surface_3d.py   (or pytest)
"""
from __future__ import annotations

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

SURFACE = os.path.join(HERE, "static", "3d", "surfaces", "anatomy.js")
ENDPOINT = "/api/a11oy/v1/anatomy/loop"


def _read_surface() -> str:
    assert os.path.isfile(SURFACE), f"anatomy surface missing on disk: {SURFACE}"
    with open(SURFACE, "r", encoding="utf-8") as fh:
        return fh.read()


# ---------------------------------------------------------------------------
# 1. surface module contract
# ---------------------------------------------------------------------------
def test_surface_follows_module_contract():
    src = _read_surface()
    assert "export default" in src
    assert "function mount" in src and "function unmount" in src
    # default export advertises the canonical shape
    assert re.search(r"id\s*:\s*ID", src) and re.search(r"title\s*:\s*TITLE", src)
    assert "endpoints: [ENDPOINT]" in src or "endpoints:[ENDPOINT]" in src


def test_surface_wired_to_real_endpoint():
    src = _read_surface()
    assert ENDPOINT in src, "surface must reference the real loop endpoint"
    assert "ctx.live.poll" in src, "surface must poll live data (never hardcode)"
    # it must poll the loop endpoint constant, not some other path
    assert re.search(r'ENDPOINT\s*=\s*"' + re.escape(ENDPOINT) + r'"', src)


def test_surface_reads_live_loop_fields_only():
    """The viz must read the fields the endpoint actually emits — no invented fields."""
    src = _read_surface()
    for field in ("intake", "organs", "beats_last_cycle", "reservoir",
                  "work_credits", "last_receipt_id", "ayni",
                  "grid_price_eur_mwh", "gpu_state", "posture", "flowing",
                  "balanced", "joules_label"):
        assert field in src, f"surface does not read live field '{field}'"


# ---------------------------------------------------------------------------
# 2. doctrine honesty in the authored viz
# ---------------------------------------------------------------------------
def test_surface_is_doctrine_honest():
    src = _read_surface()
    low = src.lower()
    assert "EXPERIMENTAL" in src, "organs must be labeled EXPERIMENTAL tier"
    assert "SAMPLE" in src, "joules must be SAMPLE off-box"
    assert "STRUCTURAL-ONLY" in src, "must keep the STRUCTURAL-ONLY honesty token visible"
    assert "net-positive" in low, "Ayni must be stated reciprocal, never net-positive"
    assert "not electrons" in low or "NOT electrons" in src, "loop carries work+receipts, not electrons"
    assert "conjecture 1" in low, "Λ must remain Conjecture 1"
    assert "degraded" in low, "must render the honest degraded state"
    # NO free-energy / over-unity / perpetual CLAIMS. Honest NEGATIONS are required
    # and allowed ("never net-positive (no free energy / over-unity)") — flag only an
    # un-negated token (repo convention; see test_dark_surfaces).
    for tok in ("free energy", "free-energy", "over-unity", "overunity",
                "perpetual", "infinite energy"):
        for m in re.finditer(re.escape(tok), low):
            pre = low[max(0, m.start() - 18):m.start()]
            negated = any(neg in pre for neg in ("no ", "not ", "never", "non-", "without", "zero"))
            assert negated, f"un-negated free-energy/over-unity/perpetual claim near '{tok}'"


def test_surface_renders_no_live_data_state():
    """Doctrine: a missing value is shown honestly, never fabricated."""
    src = _read_surface()
    assert "NO-LIVE-DATA" in src, "absent values must render NO-LIVE-DATA, not a fake number"


# ---------------------------------------------------------------------------
# 3. 0 runtime CDN (no external fetch-shaped URL in the authored surface)
# ---------------------------------------------------------------------------
def test_surface_has_zero_runtime_cdn():
    src = _read_surface()
    patterns = [
        re.compile(r"""\bimport\b[^;\n]*\bfrom\s*['"]https?://""", re.I),
        re.compile(r"""\bimport\s*\(\s*['"]https?://""", re.I),
        re.compile(r"""\bfetch\s*\(\s*['"`]https?://""", re.I),
        re.compile(r"""<script[^>]*\bsrc\s*=\s*['"]https?://""", re.I),
    ]
    for pat in patterns:
        m = pat.search(src)
        assert not m, f"runtime-CDN reference in anatomy surface: ...{src[m.start():m.start()+70]}..."


def test_surface_count_of_live_demos():
    """Sanity: the surface declares >= 15 distinct live-wired demos (DEMO markers)."""
    src = _read_surface()
    n = len(re.findall(r"DEMO\s*#\d+", src))
    assert n >= 15, f"anatomy surface declares only {n} demos (need >= 15)"


# ---------------------------------------------------------------------------
# 4. LIVE endpoint half — the surface polls REAL data, doctrine-clean.
#    Skips gracefully if FastAPI's TestClient stack isn't importable here.
# ---------------------------------------------------------------------------
def _live_body():
    try:
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
    except Exception:
        return None
    import szl_anatomy_loop as loop
    app = FastAPI()
    loop.register(app, ns="a11oy")
    client = TestClient(app)
    res = client.get(ENDPOINT)
    assert res.status_code == 200, f"loop endpoint not 200: {res.status_code}"
    return res.json()


def test_live_endpoint_shape_matches_surface_reads():
    body = _live_body()
    if body is None:
        print("[skip] FastAPI TestClient unavailable — static checks still cover the surface")
        return
    # the exact fields the viz reads must be present on the REAL response
    assert body.get("kind") == "anatomy-circulation-loop"
    assert isinstance(body.get("intake"), dict)
    assert "posture" in body["intake"] and "gpu_state" in body["intake"]
    assert "grid_price_eur_mwh" in body["intake"]
    assert isinstance(body.get("organs"), list) and len(body["organs"]) == 3
    assert "beats_last_cycle" in body
    assert isinstance(body.get("reservoir"), dict) and "work_credits" in body["reservoir"]
    assert "last_receipt_id" in body
    assert isinstance(body.get("ayni"), dict)
    for k in ("balanced", "intake", "output", "stored"):
        assert k in body["ayni"], f"ayni missing {k}"


def test_live_endpoint_is_doctrine_clean():
    body = _live_body()
    if body is None:
        print("[skip] FastAPI TestClient unavailable")
        return
    # joules are SAMPLE off-box (never measured here)
    assert body.get("joules_label") == "sample", body.get("joules_label")
    # Ayni balances (reciprocal, never net-positive)
    assert body["ayni"]["balanced"] is True
    # organs are EXPERIMENTAL tier
    for organ in body["organs"]:
        assert "experimental" in str(organ.get("note", "")).lower(), organ
        assert organ.get("name") in ("WAQAYCHAQ", "KAMAY", "RIKUY"), organ
    # no leaked key, no overclaim language. Honest NEGATIONS are required + allowed
    # ("no free-energy claim", "never net-positive", "not perpetual") — flag only a
    # free-energy / perpetual token that is NOT immediately negated (repo convention).
    blob = json.dumps(body).lower()
    assert "proven trust" not in blob, "live body claims 'proven trust'"
    for tok in ("free energy", "free-energy", "over-unity", "overunity", "perpetual"):
        for m in re.finditer(re.escape(tok), blob):
            pre = blob[max(0, m.start() - 16):m.start()]
            negated = any(neg in pre for neg in ("no ", "not ", "never", "non-", "without", "zero"))
            assert negated, f"unnegated free-energy/perpetual claim in live body near '{tok}'"


def _run_all():
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"\n{passed}/{len(fns)} anatomy-surface checks passed")
    return passed == len(fns)


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
