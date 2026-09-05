# SPDX-License-Identifier: Apache-2.0
"""Adversarial regressions for the Codex findings left after PR #1986."""
from __future__ import annotations

import threading
import time
from pathlib import Path

import szl_agentic_loop as loop
import szl_immune as immune


ROOT = Path(__file__).resolve().parents[1]


def _signed_payload(request_id: str) -> dict:
    return {
        "requestId": request_id,
        "program": "lorenz",
        "mode": "OP",
        "steps": 320,
        "agent": {
            "nexus": {
                "requestId": request_id,
                "program": "lorenz",
                "mode": "OP",
                "steps": 320,
                "inputHash": "a" * 64,
                "outputHash": "b" * 64,
                "invariantsHold": True,
                "final": {"x": 1.0, "y": 2.0, "z": 3.0},
            }
        },
    }


def _run_lorenz(payload_mutator) -> dict:
    seen: dict[str, str] = {}

    def post(_url: str, body: dict):
        seen["request_id"] = body["requestId"]
        return 201, {
            "requestId": body["requestId"],
            "governed": {
                "pass": True,
                "receipt": {"payloadType": "application/vnd.in-toto+json"},
            },
        }, None

    def verify(_receipt: dict):
        payload = _signed_payload(seen["request_id"])
        payload_mutator(payload, seen["request_id"])
        return {
            "verified": True,
            "keyid_expected": "active-key",
            "payload_decoded": payload,
        }

    return immune._nexus_lorenz(post=post, verify=verify)


def test_nested_nexus_identity_cannot_inherit_a_trusted_outer_request() -> None:
    def substitute_nested(payload: dict, _request_id: str) -> None:
        payload["agent"]["nexus"]["requestId"] = "substituted-execution"

    result = _run_lorenz(substitute_nested)
    assert result["sealed"] is False
    assert result["receipt_verification"]["verified"] is True
    assert result["receipt_verification"]["request_binding"] is False


def test_conflicting_outer_and_nested_duplicates_fail_closed() -> None:
    def conflict_outer(payload: dict, _request_id: str) -> None:
        payload["requestId"] = "conflicting-outer-request"

    result = _run_lorenz(conflict_outer)
    assert result["sealed"] is False
    assert result["receipt_verification"]["request_binding"] is False


def test_receipt_verification_reports_the_key_that_actually_verified() -> None:
    verdict = immune._verify_nexus_receipt(
        {"payloadType": "application/vnd.in-toto+json"},
        verify=lambda _receipt: {
            "verified": True,
            "keyid_expected": "current-active-key",
            "signatures": [
                {
                    "keyid": "retained-rotation-key",
                    "verified": True,
                    "verified_by_keyid": "retained-rotation-key",
                }
            ],
            "payload_decoded": {"agent": {"nexus": {}}},
        },
    )
    assert verdict["verified"] is True
    assert verdict["keyid"] == "retained-rotation-key"


class _SlowChain(list):
    def __getitem__(self, index):
        time.sleep(0.002)
        return super().__getitem__(index)


def test_run_chain_atomic_append_prevents_concurrent_lineage_forks() -> None:
    chain = _SlowChain()
    lock = threading.Lock()
    workers = 24
    barrier = threading.Barrier(workers)

    def append(index: int) -> None:
        barrier.wait()
        loop._append_run_record(
            chain,
            lock,
            {
                "run_id": f"run-{index}",
                "final_hash": f"hash-{index}",
                "decision": "ALLOW",
            },
        )

    threads = [threading.Thread(target=append, args=(index,)) for index in range(workers)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
        assert not thread.is_alive()

    assert len(chain) == workers
    assert chain[0]["prev_run_hash"] == "GENESIS"
    for previous, current in zip(chain, chain[1:]):
        assert current["prev_run_hash"] == previous["final_hash"]


def test_ouroboros_ui_sends_session_only_operator_authority() -> None:
    source = (ROOT / "src/pages/Ouroboros.tsx").read_text(encoding="utf-8")
    assert 'type="password"' in source
    assert "Authorization: `Bearer ${bearer}`" in source
    assert "setOperatorToken('')" in source
    assert "localStorage" not in source
    assert "sessionStorage" not in source
