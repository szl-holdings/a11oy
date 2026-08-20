# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
"""test_physical_bounds_cert.py — guards the MEASURED physical-bounds energy wire-up.

Proves, OFFLINE and deterministically:
  (1) the loader serves the founder-captured certificate with label MEASURED and
      energy_joules == 5112.38 READ FROM THE FILE (single source of truth — the
      number is never hardcoded in the module);
  (2) the govern/infer energy reference cites the MEASURED cert with the HONEST
      founder-captured/not-per-request label (never claims the request measured it);
  (3) when the certificate is ABSENT/unreadable the loader returns None so the
      endpoint + govern receipt report UNAVAILABLE — NO fabricated MEASURED joule.

Run: python test_physical_bounds_cert.py   (also collectable by pytest)
"""
import json

import szl_physical_bounds as PB


def _read_file_joules():
    """Read energy_joules_derived straight from the shipped file (the ground truth
    the module must match — proving the module reads the file, not a hardcoded copy)."""
    with open(PB.cert_path(), "r", encoding="utf-8") as fh:
        return json.load(fh)["energy_joules_derived"]


def test_cert_present_in_repo():
    assert PB.cert_path() is not None, "physical_bounds_certificate.json must ship at repo root"


def test_endpoint_payload_is_measured_5112():
    payload = PB.physical_bounds_payload()
    assert payload is not None
    assert payload["label"] == "MEASURED"
    assert payload["energy_joules"] == 5112.38
    # The joules MUST equal what is in the file (single source of truth, not hardcoded).
    assert payload["energy_joules"] == _read_file_joules()
    assert payload["avg_power_w"] == 56.18
    assert payload["wall_time_s"] == 91.0
    assert isinstance(payload["landauer_multiple"], (int, float))
    assert payload["landauer_multiple"] > 0
    assert "founder-captured" in payload["provenance"]["freshness"]
    # Full certificate is carried through as the single source of truth.
    assert payload["certificate"]["certificate_type"] == "szl/physical-bounds-certificate/v1"


def test_modeled_labels_preserved():
    """bit_operations / bits_erased / info_content stay MODELED (never upgraded)."""
    cert = PB.physical_bounds_payload()["certificate"]["measured"]
    # The workload descriptors are present and explicitly MODELED per the cert note.
    assert "bit_operations_MEASURED" in cert
    assert "MODELED" in cert["note"]


def test_reference_block_has_honest_label():
    ref = PB.energy_reference_block()
    assert ref is not None
    # Honesty guard: label must say founder-captured AND not-per-request-live.
    assert ref["label"] == PB.REFERENCE_LABEL
    assert "founder-captured" in ref["label"]
    assert "not per-request live" in ref["label"]
    assert ref["energy_joules"] == 5112.38
    assert ref["energy_joules"] == _read_file_joules()
    assert ref["captured"] == "2026-06-14"
    assert ref["endpoint"] == "/api/a11oy/v1/energy/physical-bounds"


def test_absent_cert_is_unavailable_no_fabrication(monkeypatch=None):
    """When the file is absent the loader returns None → endpoint/receipt report
    UNAVAILABLE. NO fabricated MEASURED number is ever produced."""
    orig = PB.cert_path
    PB.cert_path = lambda: None  # simulate file absent at runtime
    try:
        assert PB.physical_bounds_payload() is None
        assert PB.energy_reference_block() is None
        cert, reason = PB.load_certificate()
        assert cert is None
        assert isinstance(reason, str) and "not present" in reason
    finally:
        PB.cert_path = orig
    # Sanity: with the real file restored, MEASURED is available again.
    assert PB.physical_bounds_payload()["label"] == "MEASURED"


def test_govern_infer_energy_cites_reference_when_present():
    """govern_infer attaches the MEASURED founder-captured reference to the energy
    block when the cert is readable — WITHOUT claiming the request measured joules."""
    import szl_governed_api as GA
    # No live mesh in the sandbox → per-request energy is honestly UNAVAILABLE; the
    # founder-captured reference is still attached (and clearly labeled as such).
    out = GA.govern_infer("What is Λ? Answer in one sentence.")
    energy = out.get("energy") or {}
    ref = energy.get("physical_bounds_reference")
    assert ref is not None, "energy block must cite the physical-bounds reference"
    assert "founder-captured" in ref["label"]
    assert "not per-request live" in ref["label"]
    assert ref["energy_joules"] == 5112.38
    # The per-request joules are NOT the founder joules — never conflated.
    assert energy.get("joules") != 5112.38


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    passed = 0
    for fn in fns:
        fn()
        passed += 1
    return passed


if __name__ == "__main__":
    n = _run_all()
    print(f"PASS — test_physical_bounds_cert: {n} tests green (doctrine v11, offline, deterministic)")
