# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_pnt_limits_wired — the UNIFIED /pnt/limits index wires all four pillars honestly.

Doctrine v11 (HARD): every asserted number is MEASURED/MODELED/SAMPLE-labelled and
DERIVED from CITED physics — NEVER a fabricated value. These tests therefore assert
STRUCTURE + physical-sanity inequalities (finite, positive, bound-ordering), never a
hand-typed magic constant.

Covers the F1 fix:
  * compute_bounds now wires to the pure-stdlib szl_pinn_bounds engine (Landauer 1961 /
    Margolus-Levitin 1998 / Bremermann 1962 / Bekenstein 1981 / Bekenstein-Hawking 1975).
  * quantum_sensor, pnt_resilience, nav_coasting all report wired:true.
  * In a numpy-LESS environment (the HF web image) the numpy-dependent Dev2/Dev3 engines
    cannot import; the pillars MUST still wire via this layer's own pure-stdlib closed-form
    derivation (via == "closed_form_stdlib"), with real MODELED numbers, never a false
    green and never a fabricated number. This is the exact regression the live endpoint hit.

Pure stdlib. Run: python3 test_pnt_limits_wired.py   (or: pytest test_pnt_limits_wired.py)
"""
from __future__ import annotations

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import fundamental_limits as fl  # noqa: E402
import szl_pnt_mesh as mesh  # noqa: E402

KINDS = ("compute_bounds", "quantum_sensor", "pnt_resilience", "nav_coasting")


def _finite_pos(x) -> bool:
    return isinstance(x, (int, float)) and math.isfinite(x) and x > 0


def _walk_numbers(obj):
    """Yield every numeric leaf in a nested dict/list — used to assert NO NaN/inf leaks."""
    if isinstance(obj, bool):
        return
    if isinstance(obj, (int, float)):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _walk_numbers(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield from _walk_numbers(v)


# --------------------------------------------------------------------------- #
# 1. All four pillars wired in the dev environment (engines importable).       #
# --------------------------------------------------------------------------- #
def test_all_four_pillars_wired():
    pillars = fl.status()["pillars"]
    assert set(pillars) == set(KINDS)
    for kind in KINDS:
        assert pillars[kind]["wired"] is True, f"{kind} not wired: {pillars[kind]}"
        assert pillars[kind]["via"] in ("engine", "closed_form_stdlib")


def test_certify_returns_wired_true_per_pillar():
    for kind in KINDS:
        cert = fl.certify(kind)
        assert cert["wired"] is True, f"{kind} certify not wired: {cert.get('note')}"
        assert cert["label"] in ("MEASURED", "MODELED", "SAMPLE"), cert["label"]
        assert cert["result"] is not None


# --------------------------------------------------------------------------- #
# 2. compute_bounds — the DARPA-critical pillar: real closed-form physics.      #
#    Bounds are CITED established physics; we assert the inequalities/formulas, #
#    never a fabricated constant.                                              #
# --------------------------------------------------------------------------- #
def test_compute_bounds_is_real_closed_form_physics():
    cert = fl.certify("compute_bounds")
    assert cert["wired"] is True
    r = cert["result"]
    # Landauer floor kT·ln2 per erased bit, ML 4E/h, Bremermann c²/h·m — all finite, > 0.
    assert _finite_pos(r["landauer_floor_joules"])
    assert _finite_pos(r["margolus_levitin_max_ops_per_s"])
    assert _finite_pos(r["bremermann_max_ops_per_s"])
    assert _finite_pos(r["bekenstein_max_info_bits"])
    # The honest SAMPLE job sits ABOVE the Landauer floor and UNDER the ML/Brem/Bek ceilings.
    assert r["physically_bounded"] is True
    assert r["landauer_multiple_above_floor"] >= 1.0
    assert r["margolus_levitin_headroom_fraction"] <= 1.0
    assert r["bremermann_headroom_fraction"] <= 1.0
    assert r["bekenstein_under_ceiling"] is True


def test_compute_bounds_landauer_formula_checkable():
    """Independently recompute kT·ln2·N and confirm the engine matches — closed-form,
    no fabricated number. Constants are SI-exact (CODATA)."""
    import szl_pinn_bounds as pb
    T, N = 350.0, 1e14
    expected = pb.K_B * T * pb.LN2 * N
    assert math.isclose(pb.landauer_floor_joules(T, N), expected, rel_tol=1e-12)
    # And the unified certificate carries that same floor for the SAMPLE job (T=350, N=1e14).
    r = fl.certify("compute_bounds")["result"]
    assert math.isclose(r["landauer_floor_joules"], expected, rel_tol=1e-9)


def test_compute_bounds_energy_is_derived_not_claimed():
    """Joules are DERIVED = MEASURED power × MEASURED time — the honest inverse of a
    free-energy claim, never an independent assertion."""
    r = fl.certify("compute_bounds", avg_power_w=700.0, wall_time_s=10.0)["result"]
    assert math.isclose(r["energy_joules_derived"], 700.0 * 10.0, rel_tol=1e-9)
    assert r["honest_inverse_of_free_energy"] is True


# --------------------------------------------------------------------------- #
# 3. The numpy-LESS HF image regression: pillars still wire via closed-form.   #
# --------------------------------------------------------------------------- #
_NUMPY_LESS_PROBE = r"""
import sys, json
sys.modules["numpy"] = None  # any import of numpy now raises ModuleNotFoundError
sys.path.insert(0, {here!r})
import fundamental_limits as fl
kinds = ("compute_bounds", "quantum_sensor", "pnt_resilience", "nav_coasting")
print(json.dumps({{
    "pillars": fl.status()["pillars"],
    "certs": {{k: fl.certify(k) for k in kinds}},
}}, default=str))
"""


def _reload_without_numpy():
    """Run fundamental_limits in a FRESH subprocess with numpy unimportable (HF image).

    A subprocess gives true isolation: making numpy unimportable in-process and reloading
    risks corrupting the parent interpreter's cached modules for the other tests. The
    child reports the pillars + per-kind certificates as JSON.
    """
    import subprocess
    out = subprocess.run(
        [sys.executable, "-c", _NUMPY_LESS_PROBE.format(here=HERE)],
        capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, f"numpy-less probe failed:\n{out.stderr}"
    data = json.loads(out.stdout)
    return data["pillars"], data["certs"]


def test_numpy_less_image_still_wires_all_pillars():
    pillars, certs = _reload_without_numpy()
    for kind in KINDS:
        assert pillars[kind]["wired"] is True, f"{kind} dropped to wired:false w/o numpy"
        assert certs[kind]["wired"] is True
    # The numpy-dependent engines fall back to this layer's stdlib closed form — and say so.
    assert pillars["pnt_resilience"]["via"] == "closed_form_stdlib"
    assert pillars["nav_coasting"]["via"] == "closed_form_stdlib"
    # The stdlib engines (compute, sensor) keep working regardless of numpy.
    assert pillars["compute_bounds"]["via"] == "engine"
    assert pillars["quantum_sensor"]["via"] == "engine"


def test_numpy_less_closed_form_numbers_finite_and_sane():
    _, certs = _reload_without_numpy()
    # nav_coasting: position error grows, is finite & positive, and quantum beats classical.
    nav = certs["nav_coasting"]["result"]
    assert _finite_pos(nav["quantum"]["position_error_m"])
    assert _finite_pos(nav["classical"]["position_error_m"])
    assert nav["quantum_over_classical_improvement_factor"] > 1.0
    # pnt_resilience: a real deny-by-default verdict (no inputs -> NOMINAL, advisory).
    res = certs["pnt_resilience"]["result"]
    assert res["verdict"] in ("NOMINAL", "SUSPECT", "SPOOF_LIKELY")
    assert res["n_layers_flagged"] >= 0
    # No NaN / inf leaked into any pillar result.
    for kind in KINDS:
        for x in _walk_numbers(certs[kind]["result"]):
            assert math.isfinite(x), f"non-finite number in {kind}: {x}"


# --------------------------------------------------------------------------- #
# 4. Doctrine honesty carried; nothing fabricated.                             #
# --------------------------------------------------------------------------- #
def test_doctrine_labels_and_no_fabrication():
    for kind in KINDS:
        cert = fl.certify(kind)
        assert "free-energy" in cert["doctrine"].lower()
        assert "advisory" in cert["lambda_note"].lower()
        assert cert["honest_inverse_of_free_energy"] is True
    # Status reports the labels vocabulary including the honest NOT_MODELED escape hatch.
    labels = fl.status()["labels"]
    assert "NOT_MODELED" in labels and "MODELED" in labels


def test_mesh_limits_handler_surfaces_all_wired():
    """The live /pnt/limits handler must report all four pillars wired:true."""
    def _body(resp):
        b = getattr(resp, "body", resp)
        if isinstance(b, (bytes, bytearray)):
            return json.loads(b.decode())
        if isinstance(b, str):
            return json.loads(b)
        return b

    lim = _body(mesh._h_limits({}))
    assert "pillars" in lim, lim
    for kind in KINDS:
        assert lim["pillars"][kind]["wired"] is True, f"{kind} not wired at /pnt/limits"
    assert "free-energy" in lim["doctrine"].lower()


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
        print(f"  ok  {fn.__name__}")
    print(f"\n{passed}/{len(fns)} tests passed.")
    return passed == len(fns)


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
