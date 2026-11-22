#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Flip-a-byte contract for the universal Khipu verifier (szl_khipu_verify).

Mutates a stored receipt inside an isolated registry and requires the served
verdict to be FAIL. Scope pinned here on purpose: verify_digest walks from
genesis up to the target receipt only, so a digest that sits before the
tampered row still reads PASS; the whole-chain break is reported by /organs
and /chain/{organ}.
"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import szl_khipu
import szl_khipu_verify

ORGAN = "tamper_probe"
PREFIXES = ["/v1/khipu", "/api/a11oy/v1/khipu"]
UNKNOWN = "ab" * 32


@pytest.fixture
def probe(monkeypatch):
    monkeypatch.setattr(szl_khipu, "_REGISTRY", {})
    app = FastAPI()
    szl_khipu_verify.register(app)
    dag = szl_khipu.get_dag(ORGAN)
    receipts = [dag.emit(f"probe.step{i}", {"k": i}) for i in range(3)]
    return TestClient(app), dag, receipts


def _flip_hex(value: str) -> str:
    return ("1" if value[0] == "0" else "0") + value[1:]


def _organ_entry(client: TestClient, prefix: str) -> dict:
    body = client.get(f"{prefix}/organs").json()
    mine = [o for o in body["organs"] if o.get("organ") == ORGAN]
    assert len(mine) == 1, body
    return mine[0]


@pytest.mark.parametrize("prefix", PREFIXES)
def test_untampered_head_passes(probe, prefix) -> None:
    client, _dag, receipts = probe
    head = receipts[-1]["digest"]

    got = client.get(f"{prefix}/verify/{head}")
    assert got.status_code == 200
    assert got.headers["x-szl-khipu-verdict"] == "PASS"
    body = got.json()
    assert body["verdict"] == "PASS"
    assert body["digest_matches"] is True
    assert body["chain_to_genesis_verified"] is True

    posted = client.post(f"{prefix}/verify", json={"digest": head})
    assert posted.status_code == 200
    assert posted.headers["x-szl-khipu-verdict"] == "PASS"
    assert posted.json()["verdict"] == "PASS"
    assert posted.json()["digest_matches"] is True
    assert posted.json()["chain_to_genesis_verified"] is True

    entry = _organ_entry(client, prefix)
    assert entry["links_intact"] is True
    assert entry["broken_at"] is None


@pytest.mark.parametrize("prefix", PREFIXES)
def test_flipped_payload_digest_fails_head(probe, prefix) -> None:
    client, dag, receipts = probe
    dag._chain[1]["payload_digest"] = _flip_hex(dag._chain[1]["payload_digest"])

    got = client.get(f"{prefix}/verify/{receipts[-1]['digest']}")
    assert got.status_code == 200
    assert got.headers["x-szl-khipu-verdict"] == "FAIL"
    body = got.json()
    assert body["verdict"] == "FAIL"
    assert body["chain_to_genesis_verified"] is False
    assert "digest mismatch at seq 1" in body["broken_link"]

    entry = _organ_entry(client, prefix)
    assert entry["links_intact"] is False
    assert entry["broken_at"] == 1

    chain = client.get(f"{prefix}/chain/{ORGAN}")
    assert chain.status_code == 200
    assert chain.json()["chain_verified"] is False

    # Scope, not a whole-chain claim: the walk stops at the target receipt, so a
    # digest before the tampered row is still PASS.
    before = client.get(f"{prefix}/verify/{receipts[0]['digest']}")
    assert before.headers["x-szl-khipu-verdict"] == "PASS"
    assert before.json()["verdict"] == "PASS"


@pytest.mark.parametrize("prefix", PREFIXES)
def test_rewritten_prev_fails_head(probe, prefix) -> None:
    client, dag, receipts = probe
    dag._chain[1]["prev"] = "f" * 64

    got = client.get(f"{prefix}/verify/{receipts[-1]['digest']}")
    assert got.headers["x-szl-khipu-verdict"] == "FAIL"
    body = got.json()
    assert body["verdict"] == "FAIL"
    assert body["chain_to_genesis_verified"] is False
    assert "prev-link mismatch at seq 1" in body["broken_link"]


@pytest.mark.parametrize("prefix", PREFIXES)
def test_unknown_digest_is_not_found(probe, prefix) -> None:
    client, _dag, _receipts = probe

    # The digest route answers 200 with a computed NOT_FOUND verdict, not a 404.
    got = client.get(f"{prefix}/verify/{UNKNOWN}")
    assert got.status_code == 200
    assert got.headers["x-szl-khipu-verdict"] == "NOT_FOUND"
    body = got.json()
    assert body["verdict"] == "NOT_FOUND"
    assert body["found"] is False
    assert body["digest_matches"] is None

    posted = client.post(f"{prefix}/verify", json={"digest": UNKNOWN})
    assert posted.json()["found"] is False
    assert posted.json()["verdict"] == "NOT_FOUND"

    missing = client.get(f"{prefix}/chain/nope")
    assert missing.status_code == 404
    assert missing.json()["found"] is False


def test_module_selftest_runs_isolated(monkeypatch) -> None:
    monkeypatch.setattr(szl_khipu, "_REGISTRY", {})
    assert szl_khipu_verify._selftest() == {
        "pass_real_digest": True,
        "pass_head_any_organ": True,
        "not_found_honest": True,
        "tamper_changes_seal": True,
        "organs_and_chain": True,
        "no_codename_leak": True,
    }
