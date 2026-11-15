#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Monetized product surfaces: real backends for the x402 rules (2026-11-06).

Boots the REAL app in-process (no mocks, no network) and asserts each surface:
  1. 200 on good requests - never a 500 or bare 422
  2. honest-label vocabulary on every label field
  3. measured values are genuinely computed (Burgers refinement, Duffing sign)
  4. negative input -> honest 404, never a 500
  5. Lambda stays advisory (never "green")
"""

import json

import pytest
from starlette.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    import serve
    with TestClient(serve.app) as c:
        yield c


HONEST = {"LIVE", "SAMPLE", "SIMULATED", "MODELED", "CACHED", "PROVEN", "CONJECTURE",
          "MEASURED", "UNAVAILABLE", "REPLAY", "HEURISTIC", "DERIVED", "EXPERIMENTAL",
          "REPORTED"}


def _assert_honest_labels(payload):
    for key in ("label", "honesty_label", "data_label"):
        value = payload.get(key)
        if isinstance(value, str):
            assert value.upper() in HONEST, f"non-honest label {key}={value}"


def test_acoustic_index(client):
    r = client.get("/v1/acoustic/")
    assert r.status_code == 200
    d = r.json()
    assert d["schema"] == "szl.acoustic.index/v1"
    _assert_honest_labels(d)
    assert set(d["endpoints"]) == {"burgers", "duffing", "ns_pathway"}


def test_acoustic_burgers_measured(client):
    r = client.get("/v1/acoustic/burgers")
    assert r.status_code == 200
    d = r.json()
    _assert_honest_labels(d)
    result = d["result"]
    assert len(result["errors_l1"]) == 3
    # fixed CFL across grids; errors are genuinely computed vs the exact solution
    assert result["cfl"] == 0.4
    assert all(e > 0 for e in result["errors_l1"])
    assert result["errors_l1"][0] > result["errors_l1"][1] > result["errors_l1"][2]
    assert d["proof_status"] in ("PROVEN", "NOT_ESTABLISHED")
    assert d["proof_status"] == ("PROVEN" if result["refinement_holds"] else "NOT_ESTABLISHED")


def test_acoustic_duffing_measured(client):
    r = client.get("/v1/acoustic/duffing")
    assert r.status_code == 200
    d = r.json()
    _assert_honest_labels(d)
    # beta is genuinely fitted by least squares and recovers the generating sign
    assert d["result"]["beta_true"] == 1.0
    assert d["result"]["beta_fit"] > 0.5
    assert d["proof_status"] in ("PROVEN", "NOT_ESTABLISHED")
    assert d["proof_status"] == ("PROVEN" if d["result"]["sign_recovered"] else "NOT_ESTABLISHED")


def test_acoustic_ns_pathway_labels_verbatim(client):
    r = client.get("/v1/acoustic/ns-pathway")
    assert r.status_code == 200
    d = r.json()
    _assert_honest_labels(d)
    assert d["label"] == "MODELED"
    labels = {v["label"] for v in d["operating_values"].values()}
    assert labels <= {"HYPOTHESIS_UNVERIFIED", "NOT_ESTABLISHED", "HYPOTHESIS_FROM_PROVED_PROPERTY"}
    assert "MEASURED" not in json.dumps(d["operating_values"])


def test_acoustic_index_does_not_call_the_declared_pathway_measured(client):
    d = client.get("/v1/acoustic/").json()
    assert d["label"] == "DERIVED"
    assert "ns-pathway returns declared operating values" in d["note"]


_PAYMENT_SPOOF = {
    "payment-signature": "not-a-real-signature",
    "x-payment-verified": "true",
}


def test_burgers_is_the_supported_paid_read_and_mints_no_receipt(client):
    """GET /v1/acoustic/burgers is the supported acoustic check.

    Origin does not read a payment header, does not mint a receipt, and does
    not treat a spoofed payment header as settlement. POST is the wrong method.
    """
    plain = client.get("/v1/acoustic/burgers")
    spoofed = client.get("/v1/acoustic/burgers", headers=_PAYMENT_SPOOF)
    assert plain.status_code == 200
    assert spoofed.status_code == 200
    body = plain.json()
    assert body["label"] == "MEASURED"
    assert body["result"]["refinement_holds"] is True
    assert "receipt" not in body and "signature" not in body
    assert "payment-response" not in {k.lower() for k in plain.headers}
    assert spoofed.json()["result"]["errors_l1"] == body["result"]["errors_l1"]
    assert "settlement" not in spoofed.text.lower()
    wrong = client.post("/v1/acoustic/burgers", json={})
    assert wrong.status_code == 405


def test_dataset_catalog(client):
    r = client.get("/v1/data/")
    assert r.status_code == 200
    d = r.json()
    _assert_honest_labels(d)
    assert d["access"] == "PUBLIC_READ"
    names = [x["name"] for x in d["datasets"]]
    assert "model-eval-receipts" in names
    for x in d["datasets"]:
        assert x["resolve_url"].startswith("https://huggingface.co/datasets/SZLHOLDINGS/")


def test_dataset_entry_and_negative(client):
    r = client.get("/v1/data/reasoning-puzzles-sft-v1")
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "reasoning-puzzles-sft-v1"
    assert d["examples"] == 242
    # negative: unknown dataset -> honest 404, never 500
    r404 = client.get("/v1/data/does-not-exist")
    assert r404.status_code == 404
    assert r404.json()["reason"] == "unknown dataset"


def test_experimental_index(client):
    r = client.get("/api/a11oy/v1/experimental/")
    assert r.status_code == 200
    d = r.json()
    _assert_honest_labels(d)
    assert d["lean_scope"]["theorems_ci_green"] == 36
    assert "green" not in str(d.get("surfaces", {}).get("lambda", "")).lower() or \
        "never green" in d["surfaces"]["lambda"].lower()
