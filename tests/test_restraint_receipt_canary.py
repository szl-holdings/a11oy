#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline adversarial checks: ephemeral test keys and no live transport."""
import base64
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

import httpx
import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("restraint_canary_under_test",
                                            ROOT / ".github/scripts/restraint_receipt_canary.py")
canary = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = canary
spec.loader.exec_module(canary)
SOURCE, RUNTIME, BOOT = "a" * 40, "b" * 40, "boot_" + "c" * 32
TOKEN = "test-only-operator-value-never-a-production-credential"


def public(key):
    pem = key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo)
    return pem, hashlib.sha256(pem.strip()).hexdigest()


@pytest.fixture
def fixture():
    key = ec.generate_private_key(ec.SECP256R1())
    approval = ec.generate_private_key(ec.SECP256R1())
    pem, pin = public(key)
    approval_pem, approval_pin = public(approval)
    env = {"A11OY_EXECUTION_HF_REVISION": RUNTIME, "A11OY_EXECUTION_BOOT_ID": BOOT,
           "A11OY_EXECUTION_AUTHORITY_PINS_JSON": json.dumps({
               "schema": "szl.execution-authority-pins/v1",
               "approval_public_pem": approval_pem.decode(), "approval_key_id": approval_pin,
               "runtime_public_pem": pem.decode(), "runtime_key_id": pin})}
    context = canary.context_from_environment(SOURCE, env)
    payload = {"kind": "restraint.decision", "task_digest": hashlib.sha256(canary.TASK.encode()).hexdigest(),
               "intensity": "full", "doctrine": "v11"}

    def signed(value=None):
        body = dict(payload if value is None else value)
        body["_signing_identity"] = {"keyid": pin}
        encoded = canary.evidence.canonical(body)
        kind = canary.PAYLOAD_TYPE.encode()
        pae = b"DSSEv1 " + str(len(kind)).encode() + b" " + kind + b" " + str(len(encoded)).encode() + b" " + encoded
        envelope = {"_dsse": "DSSEv1", "signed": True, "payloadType": canary.PAYLOAD_TYPE,
                    "payload": base64.b64encode(encoded).decode(),
                    "signatures": [{"keyid": pin, "sig": base64.b64encode(key.sign(pae, ec.ECDSA(hashes.SHA256()))).decode()}]}
        return {"signed_receipt": envelope, "receipt_payload": dict(payload if value is None else value)}

    return context, env, signed, payload


class ByteStream(httpx.SyncByteStream):
    def __init__(self, raw):
        self.raw = raw

    def __iter__(self):
        yield self.raw


class Server:
    def __init__(self, context, response):
        self.context, self.response = context, response
        self.calls = []
        self.change = None
        self.info_reads = 0
        self.clock_value = 0.0

    def handle(self, request):
        self.calls.append(request)
        url = str(request.url)
        if url == canary.HF_INFO:
            result = {"id": "SZLHOLDINGS/a11oy", "sdk": "docker", "private": False,
                      "sha": RUNTIME, "runtime": {"stage": "RUNNING", "sha": RUNTIME}}
        elif url == canary.BUILD:
            result = {"build": {"revision": SOURCE}}
        elif url == canary.STATUS:
            result = {"schema": "szl.series-a-status/v1", "source_revision": SOURCE,
                      "runtime_boot_id": BOOT, "signing_key_source": "persistent:env:SZL_COSIGN_PRIVATE_PEM"}
        elif url == canary.INFO:
            self.info_reads += 1
            observed = self.info_reads > 1
            digest = canary.evidence.digest(canary.evidence.canonical(self.response["signed_receipt"]))
            result = {"signer_health": {"identity": self.context.key_id, "identity_checked": True,
                       "ready": observed, "observed_this_process": observed,
                       "last_verified_identity": self.context.key_id if observed else None},
                      "receipt_verification": {"observed_this_process": observed,
                       "cryptographically_verified": observed, "signature_count": 1 if observed else 0,
                       "method": "ECDSA-P256-SHA256 DSSE PAE" if observed else None,
                       "receipt_sha256": digest if observed else None}}
        elif url == canary.EVALUATE:
            assert request.method == "POST"
            assert json.loads(request.content) == canary.BODY
            assert request.headers["authorization"] == "Bearer " + TOKEN
            result = copy.deepcopy(self.response)
        else:
            pytest.fail("unexpected URL")
        if request.method == "GET":
            assert "authorization" not in request.headers
        status, headers = 200, {"content-type": "application/json"}
        if self.change:
            status, result, headers = self.change(self, request, status, result, headers)
        raw = canary.evidence.canonical(result)
        headers.setdefault("content-length", str(len(raw)))
        return httpx.Response(status, headers=headers, stream=ByteStream(raw))


def execute(fixture, change=None, response=None):
    context, _, signed, _ = fixture
    server = Server(context, response or signed())
    server.change = change
    client = httpx.Client(transport=httpx.MockTransport(server.handle))
    bounded = canary.BoundedClient(client, TOKEN, clock=lambda: server.clock_value)
    return server, bounded, context


def test_one_fixed_post_and_independent_verified_readback(fixture):
    server, bounded, context = execute(fixture)
    result = canary.run_canary(bounded, context)
    assert result["state"] == "VERIFIED"
    assert result["requests"] == 9 and result["post_attempts"] == 1
    assert [r.method for r in server.calls].count("POST") == 1
    assert result["execution_authorized"] is False and result["release_qualified"] is False
    assert TOKEN not in json.dumps(result)
    canary.evidence.verify(result["signed_receipt"], canary.PAYLOAD_TYPE,
                           context.public_key, context.key_id)


@pytest.mark.parametrize("url,field", [(canary.HF_INFO, "hf"), (canary.BUILD, "source"), (canary.STATUS, "boot")])
@pytest.mark.parametrize("after", [False, True])
def test_identity_drift_aborts_without_an_additional_post(fixture, url, field, after):
    def change(server, request, status, result, headers):
        posted = any(r.method == "POST" for r in server.calls)
        if str(request.url) == url and posted == after:
            if field == "hf":
                result["runtime"]["sha"] = "d" * 40
            elif field == "source":
                result["build"]["revision"] = "d" * 40
            else:
                result["runtime_boot_id"] = "boot_" + "d" * 32
        return status, result, headers
    server, bounded, context = execute(fixture, change)
    with pytest.raises(canary.CanaryBlocked, match="IDENTITY_MISMATCH"):
        canary.run_canary(bounded, context)
    assert bounded.post_attempts == int(after)


@pytest.mark.parametrize("after", [False, True])
def test_hf_hub_and_runtime_agreement_cannot_replace_pinned_revision(fixture, after):
    """Both HF revisions can agree yet differ from the operator-approved runtime pin."""
    def change(server, request, status, result, headers):
        posted = any(r.method == "POST" for r in server.calls)
        if str(request.url) == canary.HF_INFO and posted == after:
            result["sha"] = result["runtime"]["sha"] = "d" * 40
        return status, result, headers

    server, bounded, context = execute(fixture, change)
    with pytest.raises(canary.CanaryBlocked, match="HF_IDENTITY_MISMATCH"):
        canary.run_canary(bounded, context)
    assert bounded.post_attempts == int(after)
    assert [r.method for r in server.calls].count("POST") == int(after)


@pytest.mark.parametrize("attack", ["signature", "payload", "wrong_task", "wrong_key", "reflected_token"])
def test_invalid_signed_response_never_establishes_success(fixture, attack):
    context, _, signed, payload = fixture
    response = signed()
    if attack == "signature":
        response["signed_receipt"]["signatures"][0]["sig"] = base64.b64encode(b"invalid").decode()
    elif attack == "payload":
        response["receipt_payload"]["intensity"] = "ultra"
    elif attack == "wrong_task":
        response = signed({**payload, "task_digest": "0" * 64})
    elif attack == "wrong_key":
        response["signed_receipt"]["signatures"][0]["keyid"] = "0" * 64
    else:
        response = signed({**payload, "why": TOKEN})
    _, bounded, context = execute(fixture, response=response)
    with pytest.raises((canary.CanaryBlocked, canary.evidence.EvidenceError)):
        canary.run_canary(bounded, context)
    assert bounded.post_attempts == 1 and bounded.requests == 5


@pytest.mark.parametrize("status", [301, 302, 307, 308, 401, 403, 500])
def test_redirect_or_failed_auth_stops_without_retry(fixture, status):
    def change(server, request, original, result, headers):
        if request.method == "POST":
            return status, {"error": "blocked"}, {**headers, "location": "https://example.invalid/steal"}
        return original, result, headers
    server, bounded, context = execute(fixture, change)
    with pytest.raises(canary.CanaryBlocked, match="HTTP_RESPONSE_REJECTED"):
        canary.run_canary(bounded, context)
    assert bounded.post_attempts == 1 and len(server.calls) == 5
    assert all(str(r.url).startswith((canary.ORIGIN, canary.HF_INFO)) for r in server.calls)


def test_timeout_after_post_reservation_is_not_retried(fixture):
    def change(server, request, status, result, headers):
        if request.method == "POST":
            raise httpx.ReadTimeout("untrusted exception " + TOKEN, request=request)
        return status, result, headers
    _, bounded, context = execute(fixture, change)
    with pytest.raises(canary.CanaryBlocked, match="HTTP_TIMEOUT_NO_RETRY") as exc:
        canary.run_canary(bounded, context)
    assert TOKEN not in str(exc.value)
    assert bounded.post_attempts == 1 and bounded.requests == 5
    with pytest.raises(canary.CanaryBlocked, match="POST_ALREADY_ATTEMPTED"):
        bounded.fetch("POST", canary.EVALUATE)


def test_aggregate_deadline_and_request_limit(fixture):
    server, bounded, context = execute(fixture)
    server.clock_value = canary.TOTAL_SECONDS + 1
    with pytest.raises(canary.CanaryBlocked, match="DEADLINE_EXCEEDED"):
        canary.run_canary(bounded, context)
    assert not server.calls
    server.clock_value = 0
    bounded.requests = canary.MAX_REQUESTS
    with pytest.raises(canary.CanaryBlocked, match="REQUEST_BUDGET_EXHAUSTED"):
        bounded.fetch("GET", canary.INFO)


def test_late_post_response_is_not_accepted_or_retried(fixture):
    def change(server, request, status, result, headers):
        if request.method == "POST":
            server.clock_value = canary.TOTAL_SECONDS + 1
        return status, result, headers
    _, bounded, context = execute(fixture, change)
    with pytest.raises(canary.CanaryBlocked, match="DEADLINE_EXCEEDED"):
        canary.run_canary(bounded, context)
    assert bounded.post_attempts == 1 and bounded.requests == 5


def test_replayed_receipt_does_not_count_as_a_new_observation(fixture):
    def change(server, request, status, result, headers):
        if str(request.url) == canary.INFO and server.info_reads == 1:
            result["receipt_verification"]["receipt_sha256"] = canary.evidence.digest(
                canary.evidence.canonical(server.response["signed_receipt"]))
        return status, result, headers
    _, bounded, context = execute(fixture, change)
    with pytest.raises(canary.CanaryBlocked, match="OBSERVATION_NOT_ADVANCED"):
        canary.run_canary(bounded, context)
    assert bounded.post_attempts == 1


@pytest.mark.parametrize("attack", ["stale_receipt", "fingerprint", "oversize", "encoding"])
def test_readback_and_body_boundaries(fixture, attack):
    def change(server, request, status, result, headers):
        if str(request.url) == canary.INFO and server.info_reads == 2:
            if attack == "stale_receipt":
                result["receipt_verification"]["receipt_sha256"] = "0" * 64
            elif attack == "fingerprint":
                result["signer_health"]["identity"] = "0" * 64
            elif attack == "oversize":
                headers["content-length"] = str(canary.MAX_BYTES + 1)
            else:
                headers["content-encoding"] = "gzip"
        return status, result, headers
    _, bounded, context = execute(fixture, change)
    with pytest.raises(canary.CanaryBlocked):
        canary.run_canary(bounded, context)
    assert bounded.post_attempts == 1


def test_configuration_never_learns_a_key_or_revision_from_a_response(fixture):
    _, env, _, _ = fixture
    for name in ("A11OY_EXECUTION_HF_REVISION", "A11OY_EXECUTION_BOOT_ID", "A11OY_EXECUTION_AUTHORITY_PINS_JSON"):
        with pytest.raises((canary.CanaryBlocked, canary.evidence.EvidenceError)):
            canary.context_from_environment(SOURCE, {**env, name: ""})
    pins = json.loads(env["A11OY_EXECUTION_AUTHORITY_PINS_JSON"])
    pins["runtime_key_id"] = "0" * 64
    with pytest.raises(canary.evidence.EvidenceError, match="PUBLIC_KEY_PIN_MISMATCH"):
        canary.context_from_environment(SOURCE, {**env, "A11OY_EXECUTION_AUTHORITY_PINS_JSON": json.dumps(pins)})


def test_duplicate_json_is_rejected_without_dispatch():
    raw = b'{"id":1,"id":2}'
    client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(
        200, headers={"content-type": "application/json"}, stream=ByteStream(raw))))
    bounded = canary.BoundedClient(client, TOKEN)
    with pytest.raises(canary.evidence.EvidenceError):
        bounded.fetch("GET", canary.HF_INFO)
    assert bounded.post_attempts == 0


def test_cli_requires_explicit_execution_before_constructing_transport(tmp_path, monkeypatch):
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: pytest.fail("network client created"))
    output = tmp_path / "result.json"
    assert canary.main(["--source-sha", SOURCE, "--output", str(output)]) == 2
    result = json.loads(output.read_text())
    assert result["error"] == "EXPLICIT_EXECUTION_REQUIRED"
    assert result["post_effect"] == "NOT_DISPATCHED"


def test_unexpected_routes_are_rejected_before_a_request(fixture):
    server, bounded, _ = execute(fixture)
    for method, url in [("POST", canary.INFO), ("GET", "http://szlholdings-a11oy.hf.space/api/build-info"),
                        ("POST", canary.ORIGIN + "/api/a11oy/v1/energy/operator/start")]:
        with pytest.raises(canary.CanaryBlocked, match="FIXED_ROUTE_REQUIRED"):
            bounded.fetch(method, url)
    assert not server.calls


def test_failed_readback_retains_a_verified_receipt_without_claiming_success(fixture, tmp_path, monkeypatch):
    context, env, signed, _ = fixture
    server = Server(context, signed())
    def change(server, request, status, result, headers):
        if str(request.url) == canary.INFO and server.info_reads == 2:
            result["receipt_verification"]["receipt_sha256"] = "0" * 64
        return status, result, headers
    server.change = change
    client = httpx.Client(transport=httpx.MockTransport(server.handle))
    def configured_client(**kwargs):
        assert kwargs == {"follow_redirects": False, "trust_env": True}
        return client
    monkeypatch.setattr(httpx, "Client", configured_client)
    for name, value in {**env, "A11OY_CODE_ADMIN_KEY": TOKEN}.items():
        monkeypatch.setenv(name, value)
    output = tmp_path / "failed-canary.json"
    assert canary.main(["--source-sha", SOURCE, "--output", str(output), "--execute"]) == 2
    result = json.loads(output.read_text())
    assert result["state"] == "BLOCKED" and result["error"] == "RECEIPT_READBACK_MISMATCH"
    assert result["post_attempts"] == 1 and result["release_qualified"] is False
    assert result["verified_but_unqualified_receipt"]["qualified"] is False
    assert TOKEN not in output.read_text()
