#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Real Byzantine simulation for the wired UDS-mesh formulas.

Scenario (no mocks): 5 organs vote on a cross-organ verdict. 4 agree on ALLOW, 1 organ
is byzantine and votes HALT. We assert:
  * the PAC-Bayes + Byzantine quorum gate MERGES on the 4-organ majority (2f+1=3 ≤ 4),
  * the single byzantine organ is flagged,
  * a REAL BLS12-381 aggregate signature over the Khipu chain root verifies via
    FastAggregateVerify (one check for the whole co-signing set), and tampering fails,
  * the Welford streaming accumulator tracks fan-out latency and flags an outlier.

Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem).
"""
from __future__ import annotations

import hashlib
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from mesh.formulas import pac_bayes_quorum as pbq
from mesh.formulas import bls_aggregate as blsagg
from mesh.formulas import welford_streaming as wstream
from mesh.sdk import mesh as mesh_sdk


ORGANS = ["a11oy", "sentra", "amaru", "killinchu", "rosie"]


def _scenario_verdicts():
    # 4 organs ALLOW, rosie is byzantine and votes HALT.
    v = {o: "ALLOW" for o in ORGANS}
    v["rosie"] = "HALT"
    return v


def test_quorum_merges_majority_flags_byzantine():
    q = pbq.byzantine_quorum(_scenario_verdicts(), f=1)
    assert q["bft_feasible"] is True          # 5 ≥ 3·1+1
    assert q["quorum_met"] is True            # 4 agree ≥ 2f+1=3
    assert q["merged_decision"] == "ALLOW"
    assert q["suspected_byzantine"] == ["rosie"]
    assert q["verdict"] == "MERGE"


def test_gate_merge_allows_with_confidence():
    g = pbq.gate_merge(_scenario_verdicts(), f=1, n_obs=128, confidence_floor=0.5)
    assert g["allow_merge"] is True
    assert g["merged_decision"] == "ALLOW"
    assert 0.0 <= g["pac_bayes"]["confidence_lower_bound"] <= 1.0


def test_gate_refuses_without_quorum():
    # 3 organs, 1 fault requested → not feasible (3 < 3·1+1=4)
    g = pbq.gate_merge({"a11oy": "ALLOW", "sentra": "HALT", "amaru": "ALLOW"}, f=1)
    assert g["quorum"]["bft_feasible"] is False
    assert g["allow_merge"] is False


def test_real_bls12_381_aggregate_verifies():
    if not blsagg.AVAILABLE:
        pytest.skip("py_ecc not installed in this env; CI installs it (honest skip)")
    chain_root = hashlib.sha256(b"cross-organ-khipu-chain-root").hexdigest()
    cosigners = ["a11oy", "sentra", "amaru", "killinchu"]  # 4 ≥ 3 → aggregate
    res = blsagg.cosign_chain(cosigners, chain_root)
    assert res["available"] is True and res["signed"] is True
    assert res["aggregate_verified"] is True
    assert res["aggregated"] is True
    # Independent verification path.
    assert blsagg.verify_aggregate(cosigners, chain_root, res["aggregate_signature"]) is True
    # Tampering: a different chain root must NOT verify under the same aggregate sig.
    assert blsagg.verify_aggregate(cosigners, chain_root[:-1] + "0",
                                   res["aggregate_signature"]) is False


def test_welford_streaming_flags_outlier():
    s = wstream.StreamingStats(z_threshold=3.0)
    # Real latency stream around 20ms, then a 200ms spike.
    for x in [19.5, 20.1, 20.0, 19.8, 20.3, 19.9, 20.2, 20.0, 19.7, 20.1]:
        s.observe(x)
    spike = s.observe(200.0)
    assert spike["anomaly"] is True
    assert spike["count"] == 11


def test_mesh_governance_end_to_end():
    gov = mesh_sdk.MeshGovernance(f=1, confidence_floor=0.5)
    for lat in [21.0, 19.0, 20.5, 20.0]:
        gov.observe_fanout(lat)
    chain_root = hashlib.sha256(b"mesh-decide-cycle-1").hexdigest()
    out = gov.decide_and_cosign(_scenario_verdicts(), chain_root, n_obs=128)
    assert out["value"] is True
    assert out["merged_decision"] == "ALLOW"
    if blsagg.AVAILABLE:
        assert out["cosign"]["aggregate_verified"] is True
    else:
        assert out["cosign"]["signed"] is False  # honest: no fake signature
    assert out["fanout_stats"]["count"] == 4
    idx = mesh_sdk.MeshGovernance.formulas_index()
    assert {f["name"] for f in idx} == {"pac_bayes_quorum", "bls_aggregate", "welford_streaming"}


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("PASS", name)
    print("ALL MESH FORMULA TESTS PASSED")
