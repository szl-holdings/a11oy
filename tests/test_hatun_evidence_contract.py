# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Hatun's GET surfaces report only evidence already produced by a write.

The tests use a fresh in-process application and a counting signer. They prove
that evidence reads never invoke the signer, empty state stays UNKNOWN, actual
governed-run receipts populate the bounded feed, and the page does not paint a
signer or intact chain unconditionally.
"""
from pathlib import Path

from starlette.applications import Starlette
from starlette.testclient import TestClient

import szl_agentic_loop as loop


ROOT = Path(__file__).resolve().parents[1]


class CountingSigner:
    def __init__(self):
        self.calls = 0

    def __call__(self, payload):
        self.calls += 1
        return {
            "signed": True,
            "payloadType": "application/vnd.szl.receipt+json",
            "payload": "observed-payload",
            "signatures": [{"keyid": "test", "sig": "observed-signature"}],
        }


def _verify(envelope):
    return {
        "signature_valid": bool(envelope.get("signed") and envelope.get("signatures")),
        "detail": "test verifier observed signature bytes",
    }


def _client(signer=None, verifier=_verify):
    signer = signer or CountingSigner()
    app = Starlette()
    wired = loop.register(
        app,
        "a11oy",
        signer,
        verify_fn=verifier,
        signer_label="test observed signer",
    )
    return TestClient(app), signer, wired


def test_empty_reads_stay_unknown_and_never_mint():
    client, signer, wired = _client()
    assert "/api/hatun/evidence" in wired["registered"]
    assert "/api/hatun/invocations" in wired["registered"]

    evidence = client.get("/api/hatun/evidence")
    feed = client.get("/api/hatun/invocations")

    assert evidence.status_code == 200
    assert feed.status_code == 200
    assert evidence.headers["cache-control"] == "no-store"
    assert feed.headers["cache-control"] == "no-store"
    assert signer.calls == 0

    body = evidence.json()
    assert body["read_only"] is True
    assert body["get_mints_receipt"] is False
    assert body["signer"] == {"status": "UNKNOWN", "label": None}
    assert body["receipt_chain"]["status"] == "UNKNOWN"
    assert body["receipt_chain"]["observed_receipts"] == 0

    feed_body = feed.json()
    assert feed_body["namespace"] == "a11oy"
    assert feed_body["status"] == "UNKNOWN"
    assert feed_body["items"] == []
    assert feed_body["ephemeral"] is True


def test_actual_governed_run_populates_verified_receipt_summary_without_read_side_effects():
    client, signer, _ = _client()
    run_response = client.post(
        "/api/a11oy/v1/agent/run",
        json={"action": "summarize a public report", "severity": "low",
              "confidence": 0.9, "reversible": True},
    )
    assert run_response.status_code == 200
    run = run_response.json()
    assert signer.calls == 1

    feed = client.get("/api/hatun/invocations").json()
    evidence = client.get("/api/hatun/evidence").json()
    assert signer.calls == 1, "GET evidence reads must not call the signer"

    assert feed["status"] == "OBSERVED"
    assert feed["count"] == 1
    item = feed["items"][0]
    assert item["namespace"] == "a11oy"
    assert item["run_id"] == run["run_id"]
    assert item["receipt_hash"] == run["chain_final_hash"]
    assert item["chain_depth"] == run["chain_depth"]
    assert item["tool"] == "policy_check"
    assert item["source"] == "governed_agent_run_receipt"
    assert item["chain_status"] == "OBSERVED_INTACT"
    assert item["signature_status"] == "VERIFIED"
    assert item["signer"] == "test observed signer"
    assert "action" not in item and "query" not in item

    assert evidence["signer"] == {
        "status": "OBSERVED_VERIFIED",
        "label": "test observed signer",
    }
    assert evidence["receipt_chain"]["status"] == "OBSERVED_INTACT"
    assert evidence["receipt_chain"]["latest_receipt_hash"] == run["chain_final_hash"]


def test_present_signature_without_verifier_is_not_promoted_to_verified():
    client, signer, _ = _client(verifier=None)
    client.post("/api/a11oy/v1/agent/run", json={"action": "read status"})
    item = client.get("/api/hatun/invocations").json()["items"][0]
    evidence = client.get("/api/hatun/evidence").json()

    assert signer.calls == 1
    assert item["signature_status"] == "PRESENT_UNVERIFIED"
    assert item["signer"] is None
    assert evidence["signer"] == {"status": "UNVERIFIED", "label": None}


def test_signer_failure_remains_unsigned_and_unavailable():
    calls = {"count": 0}

    def failing_signer(_payload):
        calls["count"] += 1
        raise RuntimeError("signer unavailable")

    client, _, _ = _client(signer=failing_signer, verifier=_verify)
    run = client.post("/api/a11oy/v1/agent/run", json={"action": "read status"}).json()
    item = client.get("/api/hatun/invocations").json()["items"][0]
    evidence = client.get("/api/hatun/evidence").json()

    assert calls["count"] == 1
    assert run["signer"] is None
    assert run["signer_claim_status"] == "UNAVAILABLE"
    assert "UNSIGNED" in run["summary"]
    assert item["signature_status"] == "UNAVAILABLE"
    assert item["signer"] is None
    assert evidence["signer"] == {"status": "UNAVAILABLE", "label": None}


def test_feed_is_bounded_and_newest_first(monkeypatch):
    monkeypatch.setattr(loop, "_HATUN_FEED_LIMIT", 2)
    client, signer, _ = _client()
    run_ids = []
    for index in range(3):
        response = client.post(
            "/api/a11oy/v1/agent/run",
            json={"action": "read status %d" % index},
        )
        run_ids.append(response.json()["run_id"])

    feed = client.get("/api/hatun/invocations").json()
    assert signer.calls == 3
    assert feed["limit"] == 2
    assert feed["count"] == 2
    assert [item["run_id"] for item in feed["items"]] == list(reversed(run_ids[-2:]))


def test_hatun_page_labels_fallback_and_unknown_states_honestly():
    page = (ROOT / "pages" / "hatun-mcp.html").read_text(encoding="utf-8")

    assert "STATIC FALLBACK" in page
    assert "RUNTIME DECLARED" in page
    assert "UNKNOWN" in page
    assert "UNAVAILABLE" in page
    assert "get_mints_receipt" not in page  # UI consumes contract; it does not invent it
    assert "hash-chained receipts ✓" not in page
    assert "Each MCP call appends" not in page
    assert "in-image ECDSA-P256 (see /cosign.pub)" not in page
    assert "table-wrap" in page
    assert "overflow-x:auto" in page
