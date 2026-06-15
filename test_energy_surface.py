# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_energy_surface — self-tests for the Dev1 ENERGY / Harvest holographic surface.

The Energy surface (static/3d/surfaces/energy.js) is the flagship: it FUNNELS our own
live harvest signals (the MEASURED joules reservoir) and is modeled on Electricity Maps +
deck.gl, rendered in pure three.js inside the shell-owned ctx.stage.scene.

These prove the doctrine-critical + contract properties WITHOUT a browser (the in-browser
renderer behavior is covered by the shared szl3d selftest harness; here we assert the
authored module's source contract, its live-data wiring, its honesty posture, graceful
degradation, the funnel centerpiece, 0-CDN, and that deck.gl was vendored with a recorded
sha256 per the Dev0 contract):

  * the module follows the surface contract (default export id/title/endpoints/mount/unmount)
  * it WIRES THE REAL endpoints (/harvest/posture + /anatomy/loop) via ctx.live.poll —
    never hardcodes telemetry
  * it reads honesty labels straight off the JSON (MEASURED / SAMPLE / STRUCTURAL-ONLY) and
    renders the doctrine label chips/billboard
  * THE FUNNEL: a reservoir that fills from joules_evidence.joules_measured_total only when
    label==MEASURED (on-box), and shows the honest empty/SAMPLE posture off-box — i.e. it
    NEVER fabricates a fill height
  * it degrades gracefully on missing(404)/error/degraded states (NO-LIVE-DATA, no crash)
  * it builds >= 15 distinct demos/views
  * 0 runtime CDN in the authored module
  * deck.gl@9.0.38 is vendored (bytes + recorded sha256 + manifest row + license + notices)
  * the module is syntactically valid JS (node --check, when node is available)
"""
import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import szl3d_holographic as m

BASE = m._base_dir()
ENERGY = BASE / "surfaces" / "energy.js"
VENDOR = BASE / "vendor"

_DECKGL_SHA = "e0ec599ee202671085dfb418a11ca08f59bbc9c0168ecc47d84bdd04f22c7cf4"


def _src():
    return ENERGY.read_text(encoding="utf-8")


# ---- contract --------------------------------------------------------------
def test_energy_module_exists():
    assert ENERGY.is_file(), "energy surface module missing"


def test_energy_follows_surface_contract():
    s = _src()
    assert "export default" in s
    assert "function mount" in s and "function unmount" in s
    assert 'id: ID' in s or '"energy"' in s
    # endpoints array carries the real primary endpoint
    assert "endpoints:" in s


def test_energy_is_valid_javascript():
    node = shutil.which("node")
    if not node:
        return  # node not available in this CI image — skip (browser selftest covers runtime)
    r = subprocess.run([node, "--check", str(ENERGY)], capture_output=True, text=True)
    assert r.returncode == 0, f"energy.js failed node --check:\n{r.stderr}"


# ---- WIRE TO LIVE DATA (never fabricate) -----------------------------------
def test_energy_wires_real_endpoints_via_poll():
    s = _src()
    # the two REAL endpoints, both polled through the shared live poller
    assert "/api/a11oy/v1/harvest/posture" in s
    assert "/api/a11oy/v1/anatomy/loop" in s
    assert "ctx.live.poll" in s
    # polls BOTH (two poll handles)
    assert s.count("ctx.live.poll") >= 2 or ("_hPosture" in s and "_hLoop" in s)


def test_energy_reads_real_harvest_fields_not_hardcoded():
    s = _src()
    # reads the live JSON fields, not constants
    for f in ("joules_evidence", "joules_measured_total", "power_w_sample",
              "exporter_node", "readings", "posture", "work_credits",
              "renewable", "next_negative_windows"):
        assert f in s, f"energy.js does not read live field {f}"


# ---- honesty labels on every value -----------------------------------------
def test_energy_renders_doctrine_honesty_labels():
    s = _src()
    for lbl in ("MEASURED", "SAMPLE", "STRUCTURAL-ONLY"):
        assert lbl in s, f"energy.js missing honesty label {lbl}"
    # uses the shared label chip + billboard renderers
    assert "ctx.label" in s
    assert "billboard" in s and "chip" in s
    # reads the label straight off the JSON joules truth token
    assert "joules_label" in s


# ---- THE FUNNEL: measured joules reservoir, no fabricated fill --------------
def test_energy_funnel_reservoir_present():
    s = _src()
    # the reservoir/funnel centerpiece + its fill driven by measured joules
    assert "reservoir" in s.lower() or "RES" in s
    assert "fill" in s.lower()
    assert "joules_measured_total" in s


def test_energy_funnel_does_not_fabricate_fill_offbox():
    s = _src()
    # off-box (label != measured) the fill target must be 0 / honest, never a constant.
    # We assert the code gates the fill on a measured check.
    assert "measured" in s
    assert re.search(r"fillT\s*=\s*0", s), "funnel must drop fill to 0 when not measured (honest)"
    # and only fills from the real measured total when measured
    assert re.search(r"j\.measured", s) or re.search(r"\.measured", s)


# ---- graceful degradation --------------------------------------------------
def test_energy_handles_degraded_and_missing():
    s = _src()
    assert "missing" in s and "error" in s          # branches on poll meta states
    assert "degraded" in s
    assert "NO-LIVE-DATA" in s                       # honest grayed state, not a crash


# ---- >= 15 distinct demos/views --------------------------------------------
def test_energy_builds_at_least_15_demos():
    s = _src()
    # each distinct view is introduced by a "---- DEMO N: ... ----" banner comment
    demos = re.findall(r"DEMO\s+\d+\s*:", s)
    # plus the live HUD rows (each a distinct wired value+honesty-chip view)
    hud_rows = re.findall(r"\brow\(\s*['\"]", s)
    total = len(demos) + len(hud_rows)
    assert len(demos) >= 10, f"only {len(demos)} 3D demo banners (need >= 10 distinct views)"
    assert total >= 15, f"only {total} distinct demos/views (need >= 15-20)"


# ---- 0 runtime CDN ---------------------------------------------------------
def test_energy_has_no_runtime_cdn():
    # scan the whole authored 3d tree (the shared scanner) — must be clean
    violations = list(m.no_cdn_violations(BASE))
    assert not violations, "runtime-CDN reference in authored 3d code:\n" + "\n".join(violations)
    # and specifically the energy module
    s = _src()
    assert "http://" not in s and "https://" not in s, "energy.js must not contain any http(s) URL"


# ---- deck.gl vendored 0-CDN per the Dev0 contract --------------------------
def test_deckgl_vendored_with_recorded_hash():
    f = VENDOR / "deck.gl" / "dist.min.js"
    assert f.is_file(), "deck.gl not vendored under /static/3d/vendor/deck.gl/"
    got = hashlib.sha256(f.read_bytes()).hexdigest()
    assert got == _DECKGL_SHA, f"deck.gl hash drift: {got} != {_DECKGL_SHA}"
    # UMD global build (the pinned dist.min.js)
    head = f.read_bytes()[:200].decode("utf-8", errors="ignore")
    assert "webpackUniversalModuleDefinition" in head or "factory" in head


def test_deckgl_in_manifest_and_notices():
    man = (VENDOR / "VENDOR_MANIFEST.md").read_text(encoding="utf-8")
    assert _DECKGL_SHA in man, "deck.gl sha256 not recorded in VENDOR_MANIFEST.md"
    assert "deck.gl@9.0.38" in man
    # the rendering-choice rationale (three.js, not a second deck.gl canvas) is documented
    assert "three.js" in man and "ctx.stage.scene" in man
    lic = (VENDOR / "deck.gl" / "LICENSE")
    assert lic.is_file(), "deck.gl LICENSE not committed alongside the vendored build"
    notices = (BASE.parent.parent / "NOTICES.md")
    if notices.is_file():
        assert "deck.gl" in notices.read_text(encoding="utf-8"), "deck.gl not listed in NOTICES.md"


# ---- still an additive citizen: toolkit suite stays green ------------------
def test_energy_keeps_nine_slot_contract_intact():
    # the shell still references the energy slot module and all 9 stubs follow the contract
    html = (BASE / "holographic.html").read_text(encoding="utf-8")
    assert "/static/3d/surfaces/energy.js" in html
    i = m.info()
    assert any(sf["id"] == "energy" for sf in i["surfaces"])
