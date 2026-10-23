#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""SIMULATED verifier fixtures through the real registered code/verify handler.

No keys or signature bytes are generated. The verifier double accepts explicitly
admitted fixture bytes only; these tests establish binding logic, not cryptography.
"""
import asyncio
import base64
import json
import socket
import sys
from pathlib import Path

import pytest
import httpx
from starlette.applications import Starlette

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import a11oy_code_engine as engine


@pytest.fixture(scope="session")
def offline_loop():
    # Windows creates its internal socketpair when constructing the event loop.
    # Construct it before denying sockets; HTTP requests use ASGITransport only.
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


class FixtureVerifier:
    def __init__(self):
        self.admitted = set()

    def capture(self, payload):
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False).encode()
        env = {"payloadType": "application/vnd.szl.receipt+json",
               "payload": base64.b64encode(raw).decode(), "signed": True,
               "signatures": [], "fixture_class": "SIMULATED"}
        self.admit(env)
        return env

    def admit(self, env):
        self.admitted.add((env.get("payloadType"), env.get("payload")))

    def __call__(self, env):
        return {"signature_valid": (env.get("payloadType"), env.get("payload")) in self.admitted,
                "detail": "SIMULATED fixture verdict; no cryptographic verification"}


@pytest.fixture
def sample(monkeypatch, offline_loop):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("network, model, or sandbox execution is forbidden")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(engine, "_model_configured", lambda: False)
    monkeypatch.setattr(engine, "_hf_chat", forbidden)
    monkeypatch.setattr(engine, "_sandbox_exec", forbidden)
    monkeypatch.setattr(engine, "_backend_label", lambda: {"model_serving": "SIMULATED"})
    monkeypatch.setattr(engine, "_roster", lambda: (engine._FALLBACK_ROSTER, "SIMULATED"))
    monkeypatch.setattr(engine, "_retrieve_with_identity", lambda *_a, **_k: ([], {"backend": "SIMULATED"}))
    monkeypatch.setattr(sys.modules[__name__], "_offline_loop", offline_loop, raising=False)
    verifier = FixtureVerifier()
    run = engine.governed_turn("chat", "fixture caf\u00e9", verifier.capture, "a11oy", sandbox=False)
    return run, verifier


def post(run, verifier, wrapped=True):
    def forbidden_signer(_payload):
        raise AssertionError("verification must never invoke the signer")

    app = Starlette()
    engine.register(app, "a11oy", forbidden_signer, verify_fn=verifier)
    async def request():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),
                                     base_url="http://in-process.invalid") as client:
            return await client.post("/api/a11oy/v1/code/verify",
                                     json={"run": run} if wrapped else run)
    response = _offline_loop.run_until_complete(request())
    assert response.status_code == 200
    return response.json()


def admit_payload(run, verifier, mutate):
    payload = json.loads(base64.b64decode(run["signed_receipt"]["payload"]))
    mutate(payload)
    run["signed_receipt"] = verifier.capture(payload)


def rehash(run):
    prev = "GENESIS"
    for record in run["receipt_chain"]:
        record["prev_hash"] = prev
        record["hash"] = engine._sha({k: record[k] for k in ("seq", "kind", "body", "prev_hash")})
        prev = record["hash"]
    run["chain_final_hash"] = prev
    run["chain_depth"] = len(run["receipt_chain"])


def test_current_producer_prefix_and_terminal_are_bound(sample):
    run, verifier = sample
    signed = json.loads(base64.b64decode(run["signed_receipt"]["payload"]))
    assert signed["chain_depth"] == len(run["receipt_chain"]) - 1
    assert signed["chain_final_hash"] == run["receipt_chain"][-2]["hash"]
    result = post(run, verifier)
    assert all(result[k] is True for k in ("chain_intact", "signature_valid", "payload_bound", "verified"))


def test_unwrapped_current_run_remains_supported(sample):
    run, verifier = sample
    assert post(run, verifier, wrapped=False)["verified"] is True


@pytest.mark.parametrize("value", [None, [], "fixture", 3])
def test_nonobject_request_fails_closed(sample, value):
    _, verifier = sample
    assert post(value, verifier, wrapped=False)["verified"] is False


@pytest.mark.parametrize("field,value", [("chain_depth", 999), ("chain_depth", True),
                                        ("chain_final_hash", "0" * 64)])
def test_full_chain_summary_mismatch_fails(sample, field, value):
    run, verifier = sample
    run[field] = value
    result = post(run, verifier)
    assert result["chain_intact"] is True
    assert result["verified"] is False


def test_rehashed_nonsequential_record_is_not_a_chain(sample):
    run, verifier = sample
    run["receipt_chain"][0]["seq"] = 9
    rehash(run)
    assert post(run, verifier)["chain_intact"] is False


def test_empty_chain_cannot_borrow_valid_envelope(sample):
    run, verifier = sample
    run["receipt_chain"] = []
    result = post(run, verifier)
    assert result["signature_valid"] is True
    assert result["chain_intact"] is False
    assert result["verified"] is False


def test_cross_run_substitution_with_valid_other_envelope(sample):
    run, verifier = sample
    other = engine.governed_turn("chat", "different fixture", verifier.capture, "a11oy", sandbox=False)
    run["signed_receipt"] = other["signed_receipt"]
    result = post(run, verifier)
    assert result["chain_intact"] is True
    assert result["signature_valid"] is True
    assert result["verified"] is False
    assert result["payload_bound"] is False


@pytest.mark.parametrize("remove", [1, 2, 4])
def test_truncation_with_recomputed_summary_fails(sample, remove):
    run, verifier = sample
    run["receipt_chain"] = run["receipt_chain"][:-remove]
    rehash(run)
    result = post(run, verifier)
    assert result["chain_intact"] is True
    assert result["signature_valid"] is True
    assert result["verified"] is False


def test_rehashed_substituted_chain_fails_binding(sample):
    run, verifier = sample
    run["receipt_chain"][0]["body"]["query"] = "substitution"
    rehash(run)
    result = post(run, verifier)
    assert result["chain_intact"] is True
    assert result["signature_valid"] is True
    assert result["payload_bound"] is False


@pytest.mark.parametrize("field,value", [("chain_final_hash", "0" * 64), ("chain_depth", True),
                                        ("chain_depth", 0), ("chain_depth", 6)])
def test_valid_fixture_envelope_with_wrong_prefix_rejected(sample, field, value):
    run, verifier = sample
    admit_payload(run, verifier, lambda p: p.update({field: value}))
    result = post(run, verifier)
    assert result["signature_valid"] is True
    assert result["payload_bound"] is False


@pytest.mark.parametrize("value", [True, "0", [], {}, 0.5])
def test_malformed_signed_exit_domain_rejected(sample, value):
    run, verifier = sample
    admit_payload(run, verifier, lambda p: p.update(sandbox_exit=value))
    run["receipt_chain"][-1]["body"]["sandbox_exit"] = value
    rehash(run)
    assert post(run, verifier)["verified"] is False


@pytest.mark.parametrize("field", ["run_id", "mode", "issuer", "decision", "execution_status"])
def test_wrong_run_context_or_outcome_rejected(sample, field):
    run, verifier = sample
    run[field] = "wrong-context"
    result = post(run, verifier)
    assert result["chain_intact"] is True
    assert result["signature_valid"] is True
    assert result["verified"] is False


@pytest.mark.parametrize("field", ["run_id", "mode", "issuer", "chain_depth", "chain_final_hash"])
def test_missing_context_or_summary_rejected(sample, field):
    run, verifier = sample
    del run[field]
    assert post(run, verifier)["verified"] is False


@pytest.mark.parametrize("change", ["outcome", "extra", "kind", "bool-as-int"])
def test_rehashed_terminal_cannot_change_signed_outcome(sample, change):
    run, verifier = sample
    terminal = run["receipt_chain"][-1]
    if change == "outcome":
        terminal["body"]["executed"] = not terminal["body"]["executed"]
    elif change == "extra":
        terminal["body"]["unbound_claim"] = "fixture"
    elif change == "kind":
        terminal["kind"] = "other"
    else:
        terminal["body"]["signed"] = 1
    rehash(run)
    result = post(run, verifier)
    assert result["chain_intact"] is True
    assert result["signature_valid"] is True
    assert result["payload_bound"] is False


def test_missing_verifier_does_not_trust_signed_flag(sample):
    run, _ = sample
    result = post(run, None)
    assert result["chain_intact"] is True
    assert result["signature_valid"] is False
    assert result["verified"] is False


@pytest.mark.parametrize("verdict", [None, {}, {"signature_valid": "true"}, {"signature_valid": 1}])
def test_invalid_verifier_verdict_fails_closed(sample, verdict):
    run, _ = sample
    assert post(run, lambda _env: verdict)["verified"] is False


def test_verifier_exception_does_not_leak_details(sample):
    run, _ = sample
    def broken(_env):
        raise ValueError("PRIVATE_FIXTURE_SENTINEL")
    result = post(run, broken)
    assert result["verified"] is False
    assert "PRIVATE_FIXTURE_SENTINEL" not in json.dumps(result)


def test_wrong_payload_type_can_be_signature_valid_but_not_bound(sample):
    run, verifier = sample
    run["signed_receipt"]["payloadType"] = "application/other+json"
    verifier.admit(run["signed_receipt"])
    result = post(run, verifier)
    assert result["signature_valid"] is True
    assert result["payload_bound"] is False


@pytest.mark.parametrize("raw", [b'{}', b'[]', b'{"x":1,"x":2}', b'{"x":NaN}', b'\xff', b' { }'])
def test_malformed_or_unbound_payload_rejected(sample, raw):
    run, verifier = sample
    run["signed_receipt"]["payload"] = base64.b64encode(raw).decode()
    verifier.admit(run["signed_receipt"])
    assert post(run, verifier)["verified"] is False


@pytest.mark.parametrize("chain", [None, {}, [None], [{}], [{"seq": True, "kind": "x", "body": {}}]])
def test_malformed_chain_fails_closed_without_http_500(sample, chain):
    run, verifier = sample
    run["receipt_chain"] = chain
    result = post(run, verifier)
    assert result["chain_intact"] is False
    assert result["verified"] is False


def test_unsigned_producer_remains_unverified(sample):
    run, verifier = sample
    run["signed_receipt"]["signed"] = False
    run["receipt_chain"][-1]["body"]["signed"] = False
    rehash(run)
    result = post(run, lambda _env: {"signature_valid": False})
    assert result["chain_intact"] is True
    assert result["signature_valid"] is False
    assert result["verified"] is False


def test_hash_tamper_remains_distinct_from_signature(sample):
    run, verifier = sample
    run["receipt_chain"][0]["hash"] = "0" * 64
    result = post(run, verifier)
    assert result["chain_intact"] is False
    assert result["signature_valid"] is True
    assert result["verified"] is False


def test_declared_verification_flags_do_not_authorize(sample):
    run, _ = sample
    run.update(verified=True, chain_verified=True)
    assert post(run, None)["verified"] is False
