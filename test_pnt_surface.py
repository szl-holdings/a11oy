# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_pnt_surface — Dev3 PNT / Quantum-Nav holographic surface tests.

Doctrine v11 contract for static/3d/surfaces/pnt.js:

  * the surface module default-exports the {id,title,endpoints,mount,unmount} contract
    and keeps the toolkit's required tokens (ctx.live.poll, STRUCTURAL-ONLY, mount/unmount)
  * it WIRES the four REAL PNT endpoints (sensor/coast/resilience/limits) — never hardcodes
    a telemetry value
  * 0 runtime CDN in the authored surface + harness
  * MOUNT TEST (headless, real module): feeds the EXACT live JSON the real szl_pnt_mesh
    handlers produce, asserts the surface reads the honesty label (MODELED) straight off the
    JSON onto its HUD/badge, never fabricates a MEASURED, degrades on 404 without crashing,
    and tears down cleanly on unmount. (Runs under Node when present; honest skip otherwise.)

The live JSON is captured from the genuine handlers in szl_pnt_mesh — the shapes are real,
not invented by the test. This is the "mounts + polls real endpoints + honest MODELED
labels + 0 CDN" requirement in the Dev3 spec, executed against the real surface.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

BASE = Path(__file__).resolve().parent
SURFACE = BASE / "static" / "3d" / "surfaces" / "pnt.js"
HARNESS = BASE / "static" / "3d" / "selftest" / "pnt_mount_harness.mjs"

sys.path.insert(0, str(BASE))
import szl_pnt_mesh as mesh  # noqa: E402


def _body(resp):
    b = getattr(resp, "body", resp)
    if isinstance(b, (bytes, bytearray)):
        return json.loads(b.decode())
    if isinstance(b, str):
        return json.loads(b)
    return b


# --------------------------------------------------------------------------- #
# static contract                                                             #
# --------------------------------------------------------------------------- #
def test_surface_file_exists():
    assert SURFACE.is_file(), "surfaces/pnt.js missing"


def test_surface_keeps_toolkit_contract_tokens():
    src = SURFACE.read_text(encoding="utf-8")
    assert "export default" in src
    assert "function mount" in src and "function unmount" in src
    assert "ctx.live.poll" in src or "live.poll" in src
    assert "STRUCTURAL-ONLY" in src  # honest doctrine token retained
    # default export carries the contract id + endpoints
    assert 'id: ID' in src or '"pnt"' in src


def test_surface_wires_all_four_real_endpoints():
    src = SURFACE.read_text(encoding="utf-8")
    for ep in ("/api/a11oy/v1/pnt/sensor", "/api/a11oy/v1/pnt/coast",
               "/api/a11oy/v1/pnt/resilience", "/api/a11oy/v1/pnt/limits"):
        assert ep in src, f"surface does not wire live endpoint {ep}"


def test_surface_no_runtime_cdn():
    import re
    src = SURFACE.read_text(encoding="utf-8") + HARNESS.read_text(encoding="utf-8")
    # fetch-shaped external URLs are forbidden (doctrine v11: 0 runtime CDN)
    bad = [
        re.compile(r"""\bimport\b[^;\n]*\bfrom\s*['"]https?://""", re.I),
        re.compile(r"""\bimport\s*\(\s*['"]https?://""", re.I),
        re.compile(r"""\bfetch\s*\(\s*['"`]https?://""", re.I),
        re.compile(r"""<script[^>]*\bsrc\s*=\s*['"]https?://""", re.I),
    ]
    for pat in bad:
        assert not pat.search(src), f"runtime-CDN reference matched {pat.pattern}"


def test_surface_does_not_hardcode_telemetry():
    """The honest values must come from the live JSON, not be baked into the module.

    We assert the closed-form output magnitudes (e.g. the default k_eff ~1.6e7) are NOT
    present as literals in the source — the surface must read them at runtime."""
    src = SURFACE.read_text(encoding="utf-8")
    assert "16110731" not in src      # default k_eff value
    assert "8.778084" not in src      # default accel ASD value
    assert "113920" not in src        # default improvement factor


# --------------------------------------------------------------------------- #
# live JSON shape (real handlers) — the contract the surface reads            #
# --------------------------------------------------------------------------- #
def _live_payload():
    return {
        "sensor": _body(mesh._h_sensor({})),
        "coast": _body(mesh._h_coast({"coast_time_s": "60"})),
        "resilience": _body(mesh._h_resilience({})),
        "limits": _body(mesh._h_limits({})),
    }


def test_live_sensor_is_modeled_with_sql_fields():
    s = _body(mesh._h_sensor({}))
    assert s["label"] == "MODELED"
    cf = s["closed_form_stdlib"]
    for k in ("k_eff_per_m", "shot_noise_phase_rad",
              "per_shot_accel_sensitivity_m_s2", "accel_asd_m_s2_per_sqrt_hz"):
        assert k in cf and isinstance(cf[k], (int, float))
    assert cf["at_or_above_standard_quantum_limit"] is True or s.get("at_or_above_standard_quantum_limit")
    assert "MEASURED" not in s["status"]  # honest: NOT flown hardware


def test_live_coast_classical_vs_quantum_modeled():
    c = _body(mesh._h_coast({"coast_time_s": "60"}))["closed_form_stdlib"]
    assert c["label"] == "MODELED"
    assert c["classical"]["position_error_m"] > c["quantum"]["position_error_m"]
    assert c["quantum_over_classical_improvement_factor"] > 1.0


def test_live_limits_four_pillars_present():
    lim = _body(mesh._h_limits({}))
    pil = lim.get("pillars")
    # either the unified library is importable (pillars dict) or honest not-importable
    if pil is not None:
        for name in ("compute_bounds", "quantum_sensor", "pnt_resilience", "nav_coasting"):
            assert name in pil
            assert "wired" in pil[name]
    else:
        assert lim.get("status") == "UNIFIED_LIBRARY_NOT_IMPORTABLE"


# --------------------------------------------------------------------------- #
# headless mount test against the REAL module (Node harness)                  #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(shutil.which("node") is None, reason="node not available for headless mount harness")
def test_headless_mount_reads_modeled_label_and_degrades(tmp_path):
    payload = tmp_path / "live.json"
    payload.write_text(json.dumps(_live_payload()), encoding="utf-8")
    proc = subprocess.run(
        ["node", str(HARNESS), str(payload)],
        cwd=str(BASE), capture_output=True, text=True, timeout=60,
    )
    out = proc.stdout.strip() or proc.stderr.strip()
    assert proc.returncode == 0, f"mount harness failed:\n{out}\n{proc.stderr}"
    res = json.loads(proc.stdout)
    assert res["ok"], f"harness checks failed: {res.get('errors')}"
    # the doctrine-critical checks specifically:
    for must in ("polls_sensor", "polls_coast", "polls_resilience", "polls_limits",
                 "sensor_badge_label_modeled", "hud_shows_modeled",
                 "hud_no_fabricated_measured", "degraded_no_crash",
                 "all_polls_stopped", "overlay_removed", "post_unmount_frame_safe"):
        assert res["checks"].get(must) is True, f"missing/false check: {must}"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
