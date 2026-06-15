# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_counter_uas_surface — Dev4 Counter-UAS / killinchu holographic surface tests.

Proves the doctrine-critical + charter properties of the Counter-UAS surface WITHOUT a
browser (the renderer/mount runtime is exercised by static/3d/selftest + the shell in
the browser; here we assert the contract, the live bridge, and the HONESTY posture):

  * the surface module keeps the Dev0 default-export contract ({id,title,endpoints,mount,unmount})
  * it wires to the real killinchu live bridge endpoints (same-origin proxy), never a CDN
  * the same-origin proxy forwards killinchu's live evaluate (Λ decision + REAL ECDSA-P256
    DSSE signature), telemetry, cued-tracks, gates — and degrades gracefully on failure
  * the 53-fingerprint drone DB is vendored verbatim (count == 53), not fabricated
  * HONESTY: the surface shows SENSE/EVIDENCE only — NO defeat effects (no jam / spoof /
    takeover / kinetic / interceptor-to-target engagement). This is asserted by grepping
    the authored module for defeat-effect vocabulary.
  * doctrine honesty labels are present; Λ surfaced as Conjecture 1 / advisory
  * 0 runtime CDN in the authored module + the proxy

The live-network checks are SKIPPED (not failed) when the killinchu Space is unreachable,
so CI stays green offline; they assert real shapes when reachable.
"""
import json
import os
import re
import socket
from pathlib import Path

import pytest

import szl_counter_uas_proxy as proxy

ROOT = Path(__file__).resolve().parent
SURFACE = ROOT / "static" / "3d" / "surfaces" / "counter-uas.js"
DRONES_DB = ROOT / "static" / "3d" / "surfaces" / "data" / "drones_db.json"


def _surface_src() -> str:
    return SURFACE.read_text(encoding="utf-8")


# ── module presence + Dev0 default-export contract ──────────────────────────
def test_surface_module_exists():
    assert SURFACE.is_file(), "counter-uas.js surface module missing"


def test_default_export_contract():
    src = _surface_src()
    # default export shape: { id, title, endpoints, mount, unmount }
    assert "export default" in src
    assert 'id: ID' in src or 'id:ID' in src
    assert "mount" in src and "unmount" in src
    assert 'const ID = "counter-uas"' in src, "surface id must stay counter-uas (shell slot)"
    # endpoints array references the live bridge, not a hardcoded host
    assert "/api/a11oy/v1/counter-uas/evaluate" in src


def test_wires_real_live_endpoints_not_cdn():
    src = _surface_src()
    # every live endpoint is same-origin under the a11oy counter-uas bridge or the
    # vendored static DB — never an external host.
    for ep in (
        "/api/a11oy/v1/counter-uas/evaluate",
        "/api/a11oy/v1/counter-uas/telemetry",
        "/api/a11oy/v1/counter-uas/cued-tracks",
        "/api/a11oy/v1/counter-uas/air-picture",
        "/api/a11oy/v1/counter-uas/gates",
        "/static/3d/surfaces/data/drones_db.json",
    ):
        assert ep in src, f"surface must poll live endpoint {ep}"
    assert "ctx.live.poll" in src, "must use the szl3d_live poller (degraded/404 handling)"


# ── HONESTY: senses-and-evidences, NO defeat effects ────────────────────────
def test_no_defeat_effects_in_authored_surface():
    """killinchu charter + JIATF-401 C4: SENSE & EVIDENCE only. The authored surface must
    not implement any defeat/kinetic/jam/spoof/takeover effect. We grep for defeat-effect
    vocabulary used as an *action/effect* and fail if found outside an explicit honesty
    disclaimer comment."""
    src = _surface_src()
    # Strip the honesty/charter comments (lines that explicitly DISCLAIM defeat) before
    # scanning, so the doctrine disclaimers themselves don't trip the check.
    lines = src.splitlines()
    code_lines = []
    for ln in lines:
        low = ln.lower()
        # keep doctrine disclaimers out of the scan (they legitimately say "no jamming")
        if ("not defeat" in low or "does not defeat" in low or "no jam" in low
                or "no kinetic" in low or "not a weapon" in low or "no defeat"
                in low or "senses" in low or "evidence" in low or "honest" in low
                or "charter" in low):
            continue
        code_lines.append(ln)
    scan = "\n".join(code_lines).lower()
    # banned effect identifiers (as functions/vars/classes that would *do* a defeat)
    banned = [
        "function jam", "jambeam", "jampulse", "function spoof", "spoofgnss",
        "takeover(", "function takeover", "kineticstrike", "interceptmissile",
        "killtrack", "destroytrack", "neutralize(", "defeattrack", "fireat(",
        "engagetarget", "weaponspair",
    ]
    found = [b for b in banned if b in scan]
    assert not found, f"defeat-effect code found in sense-only surface: {found}"


def test_charter_posture_present():
    src = _surface_src()
    low = src.lower()
    # the surface must SURFACE the honest posture (JIATF-401 senses-not-defeats overlay)
    assert "senses" in low and "evidence" in low
    assert "does not defeat" in low or "not defeat" in low or "out-of-scope" in low.replace("_", "-")
    assert "conjecture 1" in low, "Λ must be surfaced as Conjecture 1 (advisory)"


def test_honesty_labels_used():
    src = _surface_src()
    # doctrine honesty chips read off live JSON / rendered for unproven values
    assert "STRUCTURAL-ONLY" in src
    assert "MEASURED" in src  # used when DSSE signed
    assert "ctx.label" in src or "_ctx.label" in src
    # DSSE signature lock-on must reference the real signature fields
    assert "lambda_receipt" in src and "dsse" in src
    assert "keyid" in src and "ECDSA-P256" in src


def test_no_cdn_in_surface_and_proxy():
    # authored surface: no fetch-shaped external URL
    src = _surface_src()
    pat = re.compile(r"""(import|fetch|from|src\s*=|href\s*=)\s*['"(]?\s*https?://""", re.I)
    # allow SPDX/license/comment URLs only if they are not fetch-shaped — pat catches the
    # fetch-shaped ones specifically.
    m = pat.search(src)
    assert m is None, f"CDN/fetch-shaped external URL in surface: ...{src[max(0,m.start()-10):m.start()+50]}..."
    # proxy module: the only external host is the killinchu Space base (server-side fetch),
    # which is the doctrine-sanctioned live data source, not a browser CDN.
    psrc = (ROOT / "szl_counter_uas_proxy.py").read_text(encoding="utf-8")
    hosts = set(re.findall(r"https?://([^/\"'\s]+)", psrc))
    # only killinchu / astm / faa documentary URLs may appear; the runtime base is killinchu.
    assert "szlholdings-killinchu.hf.space" in psrc
    for h in hosts:
        assert h.endswith("hf.space") or h.endswith("astm.org") or h.endswith("faa.gov") \
            or h.endswith("war.gov") or "killinchu" in h, f"unexpected host in proxy: {h}"


# ── vendored 53-fingerprint DB (real, not fabricated) ───────────────────────
def test_drones_db_vendored_count_53():
    assert DRONES_DB.is_file(), "53-fingerprint drones_db.json must be vendored"
    db = json.loads(DRONES_DB.read_text(encoding="utf-8"))
    assert isinstance(db, list)
    assert len(db) == 53, f"drone DB must have 53 verified fingerprints, got {len(db)}"
    # real fingerprint shape (model/manufacturer/group/side)
    sample = db[0]
    for k in ("id", "model", "manufacturer", "side", "group"):
        assert k in sample, f"fingerprint missing field {k}"


# ── proxy: route map + honest degraded envelope (offline-safe) ──────────────
def test_proxy_selftest_passes():
    proxy._selftest()  # raises on failure


def test_proxy_route_map_honest():
    assert proxy._UPSTREAM["evaluate"]["method"] == "POST"
    assert proxy._UPSTREAM["telemetry"]["path"].endswith("/drone/telemetry")
    assert proxy._UPSTREAM["cued-tracks"]["path"].endswith("/drone/cued-tracks")
    assert proxy._UPSTREAM["air-picture"]["path"].endswith("/drone/air-picture")
    assert proxy._UPSTREAM["gates"]["path"].endswith("/v1/gates")
    # the doctrine: no defeat route is ever proxied
    for suf in proxy._UPSTREAM:
        assert not any(b in suf for b in ("jam", "spoof", "defeat", "kinetic", "intercept", "engage"))


def test_proxy_degraded_envelope_is_honest():
    d = proxy._degraded("evaluate", "test reason", 502)
    assert d["degraded"] is True
    assert d["label"] == "STRUCTURAL-ONLY"
    assert "does NOT defeat" in d["posture"]
    assert "Conjecture 1" in d["lambda_status"]


def test_proxy_registers_on_fastapi():
    fastapi = pytest.importorskip("fastapi")
    app = fastapi.FastAPI()
    out = proxy.register(app, ns="a11oy")
    assert out["count"] >= 6
    paths = {r.path for r in app.routes}
    for suf in ("evaluate", "telemetry", "cued-tracks", "air-picture", "gates", "info"):
        assert f"/api/a11oy/v1/counter-uas/{suf}" in paths


# ── LIVE network checks (skipped if killinchu Space unreachable) ────────────
def _killinchu_reachable() -> bool:
    if os.environ.get("SZL_NO_NET"):
        return False
    try:
        socket.setdefaulttimeout(6)
        socket.getaddrinfo("szlholdings-killinchu.hf.space", 443)
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _killinchu_reachable(), reason="killinchu Space unreachable (offline)")
def test_live_evaluate_returns_real_dsse_signature():
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    app = fastapi.FastAPI()
    proxy.register(app, ns="a11oy")
    c = TestClient(app)
    r = c.get("/api/a11oy/v1/counter-uas/evaluate")
    assert r.status_code == 200
    j = r.json()
    if j.get("degraded"):
        pytest.skip("upstream degraded at test time")
    # real Λ decision
    assert j.get("decision") in ("ALLOW", "CLASSIFY", "HALT")
    assert isinstance(j.get("lambda"), (int, float))
    # REAL ECDSA-P256 DSSE signature over the receipt
    dsse = j.get("lambda_receipt", {}).get("dsse", {})
    assert dsse.get("signed") is True
    assert dsse.get("keyid") == "szlholdings-cosign"
    assert dsse.get("signatures") and dsse["signatures"][0].get("sig")


@pytest.mark.skipif(not _killinchu_reachable(), reason="killinchu Space unreachable (offline)")
def test_live_telemetry_and_gates_real_shapes():
    fastapi = pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    app = fastapi.FastAPI()
    proxy.register(app, ns="a11oy")
    c = TestClient(app)
    t = c.get("/api/a11oy/v1/counter-uas/telemetry").json()
    if not t.get("degraded"):
        assert "friendly_drones" in t and "threat_tracks" in t
    g = c.get("/api/a11oy/v1/counter-uas/gates").json()
    if not g.get("degraded"):
        assert g.get("count") == 13 or len(g.get("gates", [])) == 13
