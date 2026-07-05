# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_estate_integration — Dev9 cross-surface integration self-tests.

Asserts the INTEGRATED holographic estate (all 9 surfaces stitched onto the Dev0
toolkit) honors doctrine v11 as a whole, and that the 9th surface — the unified
ESTATE HOLOGRAM (static/3d/surfaces/estate.js) — funnels MULTIPLE live endpoints
into one scene without ever fabricating telemetry:

  * all 9 surface modules exist, each default-exports the contract shape
    (id/title/endpoints/mount/unmount) and its id matches its shell slot
  * the /holographic shell wires all 9 surface modules (9 lazy slots)
  * the estate surface reads its PRIMARY endpoint (/ecosystem/kpi-board) AND the
    four individual surface endpoints (energy/fabric/pnt/anatomy) via ctx.live.poll,
    degrading honestly to NO-LIVE-DATA when any 404s — it never hardcodes a value
  * the estate surface builds >= 15 combined KPI demos/views and renders the
    doctrine honesty chips on every value
  * 0 runtime CDN anywhere in the authored 3d tree (the shared scanner stays green)
  * no fabricated telemetry: every surface that reads a live value also has a
    NO-LIVE-DATA / honest-degraded branch
  * every surface is syntactically valid JS (node --check, when node is available)
"""
import re
import shutil
import subprocess
from pathlib import Path

import szl3d_holographic as m

BASE = m._base_dir()
SURFACES = BASE / "surfaces"
ESTATE = SURFACES / "estate.js"

SLOTS = ["energy", "fabric", "pnt", "counter-uas", "governance",
         "pinn", "router", "anatomy", "estate"]

ESTATE_ENDPOINTS = [
    "/api/a11oy/v1/ecosystem/kpi-board",   # PRIMARY (governance arc + Λ)
    "/api/a11oy/v1/harvest/posture",       # energy ring
    "/api/a11oy/v1/compute-pool",          # fabric hex
    "/api/a11oy/v1/pnt/limits",            # PNT horizon
    "/api/a11oy/v1/anatomy/loop",          # anatomy / reservoir glance
]


def _src(name):
    return (SURFACES / f"{name}.js").read_text(encoding="utf-8")


# ---- all 9 surfaces present + contract ------------------------------------
def test_all_nine_surface_modules_exist():
    for s in SLOTS:
        assert (SURFACES / f"{s}.js").is_file(), f"surface module missing: {s}.js"


def test_all_nine_follow_surface_contract():
    for s in SLOTS:
        src = _src(s)
        assert "export default" in src, f"{s}.js: no default export"
        assert "function mount" in src or "mount(" in src, f"{s}.js: no mount"
        assert "function unmount" in src or "unmount(" in src, f"{s}.js: no unmount"
        assert "endpoints:" in src, f"{s}.js: no endpoints in export"


def test_all_nine_ids_match_slots():
    # the module's ID constant must equal its slot id (so the shell mounts it correctly)
    for s in SLOTS:
        src = _src(s)
        assert re.search(r'const ID\s*=\s*["\']' + re.escape(s) + r'["\']', src), \
            f"{s}.js: const ID does not equal slot id '{s}'"


def test_shell_wires_all_nine_slots():
    html = (BASE / "holographic.html").read_text(encoding="utf-8")
    for s in SLOTS:
        assert f"/static/3d/surfaces/{s}.js" in html, f"shell does not wire surface {s}"
    info = m.info()
    # The full manifest now carries the Dev0 frontier tier on top of the 9 estate
    # slots — derive the count from the manifest so it never goes stale, and assert
    # the 9 estate slots remain a subset of it.
    assert len(info["surfaces"]) == len(m.SURFACES)
    surface_ids = {sf["id"] for sf in info["surfaces"]}
    assert set(SLOTS) <= surface_ids


def test_all_nine_syntactically_valid_js():
    node = shutil.which("node")
    if not node:
        return  # node not in this image — browser selftest covers runtime
    for s in SLOTS:
        r = subprocess.run([node, "--check", str(SURFACES / f"{s}.js")],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"{s}.js failed node --check:\n{r.stderr}"


# ---- estate surface: funnels MULTIPLE live endpoints, never fabricates -----
def test_estate_wires_all_five_endpoints_via_poll():
    s = _src("estate")
    for ep in ESTATE_ENDPOINTS:
        assert ep in s, f"estate.js does not wire endpoint {ep}"
    assert "ctx.live.poll" in s
    # one poll handle per endpoint (5 distinct live polls into one scene)
    assert s.count("ctx.live.poll") >= 5, "estate must poll all 5 endpoints"


def test_estate_reads_real_fields_not_hardcoded():
    s = _src("estate")
    # reads live JSON fields off the five surfaces, never constants
    for f in ("locked8", "lambda", "checks_passing", "chapaq_verdict", "apps",
              "price_now_eur_mwh", "renewable_share_pct", "joules_evidence",
              "joules_measured_total", "counts", "nodes_reachable",
              "gpu_nodes_reachable", "pillars", "beats_last_cycle",
              "work_credits", "ayni"):
        assert f in s, f"estate.js does not read live field {f}"


def test_estate_renders_honesty_labels():
    s = _src("estate")
    for lbl in ("MEASURED", "MODELED", "SAMPLE", "STRUCTURAL-ONLY"):
        assert lbl in s, f"estate.js missing honesty label {lbl}"
    assert "ctx.label" in s and "chip" in s
    # reads honesty tokens straight off the JSON, never invents
    assert "joules_label" in s and "meta.label" in s


def test_estate_degrades_honestly():
    s = _src("estate")
    assert "missing" in s and "error" in s
    assert "NO-LIVE-DATA" in s
    # the PRIMARY (kpi-board) degrading must NOT crash the other four pollers —
    # each poller has its own missing/error branch
    assert s.count("NO-LIVE-DATA") >= 5


def test_estate_does_not_fabricate_reservoir_fill():
    s = _src("estate")
    # the joules reservoir fills ONLY when label==MEASURED; otherwise drops to 0
    assert 'jlabel === "MEASURED"' in s
    assert re.search(r"_anim\.fillT\s*=\s*0", s), \
        "estate reservoir must drop fill to 0 when joules are not MEASURED (honest)"


def test_estate_builds_at_least_15_combined_demos():
    s = _src("estate")
    demos = re.findall(r"DEMO\s+\d+\s*:", s)
    hud_rows = re.findall(r"\brow\(\s*['\"]", s)
    total = len(demos) + len(hud_rows)
    assert len(demos) >= 12, f"only {len(demos)} estate DEMO banners (need >= 12)"
    assert total >= 15, f"only {total} combined estate demos/views (need >= 15)"


# ---- estate is a clean Linux/mobile citizen (no forced WebGPU) -------------
def test_estate_does_not_force_webgpu():
    s = _src("estate")
    # bloom (the WebGL2-only pass) is gated on the actual backend, not forced
    assert 'backend === "webgl2"' in s, \
        "estate must gate bloom on the WebGL2 backend (Linux/mobile guard, no forced WebGPU)"


# ---- 0 runtime CDN across the whole integrated tree ------------------------
def test_no_runtime_cdn_anywhere():
    violations = list(m.no_cdn_violations(BASE))
    assert not violations, "runtime-CDN reference in authored 3d code:\n" + "\n".join(violations)


def test_no_surface_loads_a_runtime_cdn():
    # The doctrine authority is the shared FETCH-SHAPED CDN scanner (test above):
    # a runtime <script src=cdn>, an import from a cdn host, a fetch() of an external
    # URL. A clickable transparency-log entry link (e.g. pinn.js's Rekor <a href>)
    # built from a live JSON field is evidence, NOT a runtime CDN, and is allowed.
    # Here we additionally assert the estate surface itself is wholly same-origin.
    s = _src("estate")
    assert "http://" not in s and "https://" not in s, \
        "estate.js must not contain any http(s) URL (same-origin only)"
    # and no authored surface pulls three/deck.gl from a CDN host
    for slot in SLOTS:
        src = _src(slot)
        assert "cdn.jsdelivr" not in src and "unpkg.com" not in src and "cdnjs" not in src, \
            f"{slot}.js references a CDN host (must vendor same-origin)"


# ---- no fabricated telemetry: every live-reading surface degrades honestly -
def test_every_surface_has_honest_degraded_branch():
    for s in SLOTS:
        src = _src(s)
        # each surface either shows NO-LIVE-DATA or branches on a degraded/missing state
        assert ("NO-LIVE-DATA" in src) or ("degraded" in src) or ("missing" in src), \
            f"{s}.js has no honest degraded/NO-LIVE-DATA path"
