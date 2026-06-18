# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_pinn_bounds — honesty + bound-inequality tests for the a11oy PINN/bounds mesh.

These assert the doctrine-critical properties of szl_pinn_bounds.certify_job():
  * energy is DERIVED = MEASURED power × MEASURED time (never an independent claim)
  * the honest SAMPLE job is physically bounded (above Landauer, under ML/Brem/Bek)
  * an adversarial BELOW-Landauer-floor job is HONESTLY flagged NOT bounded
  * the live mesh certificate AGREES with the on-metal engine artifact (if present)
  * the certificate carries the no-free-energy doctrine + Λ-advisory label and is UNSIGNED
"""
import json
import os

import szl_pinn_bounds as m

_SAMPLE_KEYS = ("avg_power_w", "wall_time_s", "temperature_k", "bit_operations",
                "bits_erased", "info_content_bits", "device_mass_kg", "device_radius_m")


def _sample_cert():
    return m.certify_job(**{k: m._SAMPLE_JOB[k] for k in _SAMPLE_KEYS})


def test_selftest_passes():
    out = m._selftest()
    assert out["ok"] is True
    assert all(v is True for v in out.values())


def test_energy_is_derived_power_times_time():
    c = _sample_cert()
    assert abs(c["energy_joules_derived"] - 700.0 * 10.0) < 1e-9


def test_sample_job_physically_bounded():
    c = _sample_cert()
    assert c["physically_bounded"] is True
    assert c["landauer_multiple_above_floor"] >= 1.0
    assert c["margolus_levitin_headroom_fraction"] <= 1.0
    assert c["bremermann_headroom_fraction"] <= 1.0
    assert c["bekenstein_under_ceiling"] is True


def test_below_floor_job_flagged_unbounded():
    """The HONEST INVERSE of free-energy: a job claiming to erase bits below the
    Landauer floor cannot be physically bounded — the certifier must say so."""
    bad = m.certify_job(avg_power_w=1e-30, wall_time_s=1.0, temperature_k=350.0,
                        bit_operations=1.0, bits_erased=1e14, info_content_bits=1.0,
                        device_mass_kg=2.0, device_radius_m=0.15)
    assert bad["physically_bounded"] is False
    assert bad["landauer_multiple_above_floor"] < 1.0


def test_no_free_energy_doctrine_and_lambda_advisory():
    c = _sample_cert()
    assert c["honest_inverse_of_free_energy"] is True
    assert "free-energy" in c["doctrine"].lower()
    assert "advisory" in c["lambda_note"].lower()
    assert "proven trust" not in c["lambda_note"].lower().replace("not 'proven trust'", "")
    # UNSIGNED here — signing is the khipu/szl_lake DSSE path; never fabricated.
    assert c["signature"] is None


def test_certificate_is_sample_labeled():
    c = _sample_cert()
    assert "SAMPLE" in str(c["measured"]["label"]).upper()


def test_inputs_hash_is_content_addressed():
    c1 = _sample_cert()
    c2 = _sample_cert()
    assert c1["inputs_hash"] == c2["inputs_hash"]  # deterministic over MEASURED inputs
    assert c1["inputs_hash"].startswith("sha256:")
    # a different job → a different hash
    c3 = m.certify_job(avg_power_w=300, wall_time_s=5, temperature_k=340,
                       bit_operations=2e15, bits_erased=5e13, info_content_bits=8e11,
                       device_mass_kg=2.0, device_radius_m=0.15)
    assert c3["inputs_hash"] != c1["inputs_hash"]


def test_mesh_matches_on_metal_artifact_if_present():
    """If the on-metal engine artifact is committed, the stdlib mesh certifier must
    reproduce its derived bounds EXACTLY (same SI constants, same formulas)."""
    art_path = os.path.join(os.path.dirname(os.path.abspath(m.__file__)),
                            "physical_bounds_certificate.json")
    if not os.path.isfile(art_path):
        return  # nothing to compare against in this environment — not a failure
    with open(art_path) as fh:
        art = json.load(fh)
    c = _sample_cert()
    for key in ("energy_joules_derived", "landauer_floor_joules",
                "landauer_multiple_above_floor", "margolus_levitin_max_ops_per_s",
                "bremermann_max_ops_per_s", "bekenstein_max_info_bits",
                "bekenstein_hawking_ceiling_bits"):
        a, b = float(art[key]), float(c[key])
        assert abs(a - b) <= abs(a) * 1e-9 + 1e-12, (key, a, b)
    assert art["physically_bounded"] == c["physically_bounded"]


def test_register_adds_pinn_routes():
    """register() must add the five /api/<ns>/v1/pinn/* routes onto a FastAPI app."""
    try:
        from fastapi import FastAPI
    except Exception:
        return  # FastAPI not installed in this env — skip, not a failure
    app = FastAPI()
    added = m.register(app, ns="a11oy")
    assert "/api/a11oy/v1/pinn" in added
    assert "/api/a11oy/v1/pinn/certify" in added
    assert "/api/a11oy/v1/pinn/certificate" in added
    assert "/api/a11oy/v1/pinn/solve" in added
    assert "/api/a11oy/v1/pinn/residual" in added
    paths = {r.path for r in app.router.routes if hasattr(r, "path")}
    for p in added:
        assert p in paths


def test_served_decision_trail_has_no_private_address():
    """The committed on-metal artifact + the served /pinn/solve trail must not leak
    a sovereign GPU's tailnet address (Doctrine v11: hide private addressing,
    change no true/false fact — same leak class as the compute-pool egress scrub)."""
    import re
    # 1. The committed artifact itself is clean (defense at the data).
    art = os.path.join(os.path.dirname(os.path.abspath(m.__file__)),
                       "agentic_decision_trail.json")
    if os.path.isfile(art):
        raw = open(art).read()
        assert "100.125.77.31" not in raw, "committed trail artifact leaks a tailnet IP"
        assert not re.search(r"100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d", raw), \
            "committed trail artifact leaks a 100.64/10 tailnet IP"

    # 2. The read boundary scrubs any private address (defense at egress) so EVERY
    #    trail consumer is leak-safe even if a future artifact embeds an address.
    trail = m._trail_or_none()
    if trail is not None:
        blob = json.dumps(trail)
        for tok in ("100.125.77.31", ":11434", ":9471", "167.233.50.75"):
            assert tok not in blob, f"served decision trail leaks {tok!r}"
        assert not re.search(r"100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\.\d", blob), \
            "served decision trail leaks a 100.64/10 tailnet IP"
        # Honest facts survive: the GPU model + node name remain, joules untouched.
        gpu = trail.get("energy_measurement", {}).get("gpu", "")
        assert "betterwithage" in gpu and "RTX 5050" in gpu


def test_scrub_private_addrs_preserves_honest_content():
    """_scrub_private_addrs strips ONLY the address, leaving honest text intact."""
    s = m._scrub_private_addrs
    assert s("RTX 5050 (betterwithage, tailnet 100.125.77.31)") == "RTX 5050 (betterwithage)"
    assert s("probe http://100.70.130.45:11434 timed out") == "probe (private) timed out"
    assert s("box 167.233.50.75 reachable") == "box (private) reachable"
    # Public DNS + non-address content untouched.
    assert s("router.huggingface.co/v1") == "router.huggingface.co/v1"
    assert s({"a": ["x tailnet 100.96.129.45", 42, True]}) == {"a": ["x", 42, True]}


if __name__ == "__main__":
    # allow running without pytest
    import traceback
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        try:
            fn()
            passed += 1
            print(f"PASS {fn.__name__}")
        except Exception:
            print(f"FAIL {fn.__name__}")
            traceback.print_exc()
    print(f"\n{passed}/{len(fns)} passed")
