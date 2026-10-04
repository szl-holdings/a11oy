"""Offline tests for the bounded live-proof transport and receipt check.

No network: every provider response is a local fake opener.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import io
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

SCRIPT = Path(__file__).with_name("hf_live_proof_bounds.py")
SPEC = importlib.util.spec_from_file_location("hf_live_proof_bounds_under_test", SCRIPT)
assert SPEC and SPEC.loader
bounds = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bounds)

SPACE_URL = "https://szlholdings-a11oy.hf.space/api/a11oy/v1/honest"
HF_RUNTIME = "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy/runtime"
PROVIDER_BODY = b'{"error":"Traceback (most recent call last): internal provider detail hf_leak"}'


class Resp:
    def __init__(self, url, payload=None, status=200, raw=None):
        self._url = url
        self.status = status
        self._body = raw if raw is not None else json.dumps(payload).encode("utf-8")

    def read(self, *_size):
        return self._body

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        return False


def http_error(url, status, *, retry_after=None):
    headers = {"Retry-After": str(retry_after)} if retry_after is not None else {}
    return HTTPError(url, status, "provider reason text", headers, io.BytesIO(PROVIDER_BODY))


class Opener:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.requests = []

    def open(self, request, timeout=None):
        self.requests.append(request)
        outcome = self.outcomes[min(len(self.requests) - 1, len(self.outcomes) - 1)]
        if callable(outcome):
            outcome = outcome(request)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


def transport(outcomes, *, deadline=600, clock=None):
    clock = clock or Clock()
    opener = Opener(outcomes)
    return bounds.BoundedTransport(
        deadline_seconds=deadline, opener=opener, sleep=clock.sleep, clock=clock
    ), opener, clock


def test_bounds_are_the_reviewed_constants():
    assert bounds.CANONICAL_ORIGIN == "https://szlholdings-a11oy.hf.space"
    assert bounds.CANONICAL_SPACE == "SZLHOLDINGS/a11oy"
    assert bounds.GDW_NAMESPACE == "a11oy"
    assert bounds.MAX_ATTEMPTS == 8
    assert bounds.RETRY_WINDOW_SECONDS == 600
    assert set(bounds.TRANSIENT_HTTP_STATUSES) == {429, 502, 503, 504}
    assert bounds.PINNED_RUNTIME_KEY_PATH == "ayllu/keys/council-runtime-2026-07-21.pub"


def test_provider_error_is_typed_and_cannot_be_absorbed_by_polling():
    error = bounds.ProofBoundaryError("PROVIDER_TERMINAL_STATE")
    assert bounds.is_hard_failure(error) is True
    assert bounds.diagnostic_code(error, "RESTART_PROOF_TIMEOUT") == "PROVIDER_TERMINAL_STATE"
    assert str(error) == "PROVIDER_TERMINAL_STATE"
    assert bounds.TERMINAL_PROVIDER_ERROR_STAGES == {
        "RUNTIME_ERROR", "BUILD_ERROR", "CONFIG_ERROR", "NO_APP_FILE",
    }


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_redirect_status_is_rejected_without_following(status):
    t, opener, _ = transport([http_error(SPACE_URL, status)])
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        t.request("GET", SPACE_URL)
    assert excinfo.value.code == "REDIRECT_REJECTED"
    assert len(opener.requests) == 1


def test_silently_followed_redirect_is_rejected():
    t, _, _ = transport([lambda req: Resp("https://evil.example/api/x", {"ok": True})])
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        t.request("GET", SPACE_URL)
    assert excinfo.value.code == "REDIRECT_REJECTED"


def test_default_opener_refuses_redirects():
    # Returning None makes urllib surface the 3xx as HTTPError instead of following.
    handler = bounds._RefuseRedirect()
    assert handler.redirect_request(None, None, 302, "Found", {}, "https://evil.example/") is None
    assert any(isinstance(h, bounds._RefuseRedirect) for h in bounds.default_opener().handlers)


def test_provider_body_is_never_echoed():
    t, _, _ = transport([http_error(SPACE_URL, 500)])
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        t.request("GET", SPACE_URL)
    error = excinfo.value
    rendered = f"{error} {error!r} {error.args} {json.dumps(t.log)}"
    assert error.code == "HTTP_STATUS_REJECTED"
    assert error.http_status == 500
    for fragment in ("Traceback", "provider detail", "hf_leak", "provider reason text"):
        assert fragment not in rendered
    assert error.__cause__ is None and error.__suppress_context__ is True


def test_non_json_success_body_is_a_fixed_code():
    t, _, _ = transport([lambda req: Resp(req.full_url, raw=b"<html>oops hf_leak</html>")])
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        t.request("GET", SPACE_URL)
    assert excinfo.value.code == "RESPONSE_NOT_JSON"
    assert "hf_leak" not in repr(excinfo.value)


def test_oversized_body_is_rejected():
    big = b"[" + b"0," * (bounds.MAX_RESPONSE_BYTES // 2 + 8) + b"0]"
    t, _, _ = transport([lambda req: Resp(req.full_url, raw=big)])
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        t.request("GET", SPACE_URL)
    assert excinfo.value.code == "RESPONSE_TOO_LARGE"


@pytest.mark.parametrize("status", [429, 502, 503, 504])
def test_retry_is_capped_at_eight_attempts(status):
    t, opener, _ = transport([http_error(SPACE_URL, status)])
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        t.request("GET", SPACE_URL)
    assert excinfo.value.code == "TRANSIENT_RETRY_EXHAUSTED"
    assert len(opener.requests) == 8


def test_transient_then_success_is_admitted():
    t, opener, _ = transport([
        http_error(SPACE_URL, 503),
        http_error(SPACE_URL, 429, retry_after=3),
        lambda req: Resp(req.full_url, {"git_sha": "a" * 40}),
    ])
    assert t.request("GET", SPACE_URL) == (200, {"git_sha": "a" * 40})
    assert len(opener.requests) == 3


@pytest.mark.parametrize("status", [400, 401, 403, 404, 409, 422, 500])
def test_non_transient_status_fails_closed_first_time(status):
    t, opener, _ = transport([http_error(SPACE_URL, status)])
    with pytest.raises(bounds.ProofBoundaryError):
        t.request("GET", SPACE_URL)
    assert len(opener.requests) == 1


def test_transport_error_is_not_retried():
    t, opener, _ = transport([URLError("dns failure with detail hf_leak")])
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        t.request("GET", SPACE_URL)
    assert excinfo.value.code == "TRANSPORT_UNAVAILABLE"
    assert "hf_leak" not in repr(excinfo.value)
    assert len(opener.requests) == 1


def test_retry_window_is_ten_minutes_even_with_attempts_left():
    clock = Clock()

    def slow_503(request):
        clock.now += 200  # each slow provider answer consumes window time
        return http_error(request.full_url, 503, retry_after=60)

    t, opener, _ = transport([slow_503], deadline=3600, clock=clock)
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        t.request("GET", SPACE_URL)
    assert excinfo.value.code == "TRANSIENT_RETRY_EXHAUSTED"
    assert len(opener.requests) == 3  # 200, 460, 720 >= 600 -> stop before attempt 4
    assert clock.now < 800


def test_retry_after_is_capped():
    t, opener, clock = transport([http_error(SPACE_URL, 429, retry_after=100000)])
    with pytest.raises(bounds.ProofBoundaryError):
        t.request("GET", SPACE_URL)
    assert clock.now <= 7 * bounds.RETRY_AFTER_CAP_SECONDS


def test_deadline_is_shared_and_enforced():
    clock = Clock()
    t, opener, _ = transport([http_error(SPACE_URL, 503, retry_after=30)], deadline=45, clock=clock)
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        t.request("GET", SPACE_URL)
    assert excinfo.value.code == "DEADLINE_EXHAUSTED"
    assert clock.now <= 45
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        t.request("GET", SPACE_URL)
    assert excinfo.value.code == "DEADLINE_EXHAUSTED"
    assert bounds.is_hard_failure(excinfo.value)


@pytest.mark.parametrize(
    "url",
    [
        "http://szlholdings-a11oy.hf.space/api/a11oy/v1/honest",
        "https://SZLHOLDINGS-A11OY.hf.space/api/a11oy/v1/honest",
        "https://szlholdings-a11oy.hf.space.evil.example/api/x",
        "https://evil.example/?h=szlholdings-a11oy.hf.space",
        "https://user@szlholdings-a11oy.hf.space/api/x",
        "https://szlholdings-a11oy.hf.space:444/api/x",
        "https://szlholdings-a11oy.hf.space/",
        "https://szlholdings-a11oy.hf.space/api/../admin",
        "https://szlholdings-a11oy.hf.space/api/%2e%2e/x",
        "https://a-11-oy.com/api/a11oy/v1/honest",
        "https://huggingface.co/api/spaces/SZLHOLDINGS/other/restart",
        "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy-staging/restart",
        "https://huggingface.co/api/spaces/szlholdings/a11oy/restart",
        "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy/secrets?x=1",
        "https://huggingface.co/api/models/SZLHOLDINGS/a11oy",
        "https://hf.co/api/spaces/SZLHOLDINGS/a11oy/restart",
    ],
)
def test_wrong_host_or_path_is_rejected_before_network(url):
    t, opener, _ = transport([lambda req: Resp(req.full_url, {"ok": True})])
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        t.request("GET", url)
    assert excinfo.value.code == "DESTINATION_REJECTED"
    assert opener.requests == []


def test_admitted_destinations_pass_exactly():
    assert bounds.check_destination(SPACE_URL) == SPACE_URL
    assert bounds.check_destination(HF_RUNTIME) == HF_RUNTIME
    assert bounds.require_canonical_origin("https://szlholdings-a11oy.hf.space") == bounds.CANONICAL_ORIGIN
    for origin in ("https://szlholdings-a11oy.hf.space/", "https://szlholdings-a11oy.hf.space.evil.example"):
        with pytest.raises(bounds.ProofBoundaryError):
            bounds.require_canonical_origin(origin)


def test_only_get_and_post_are_admitted():
    t, opener, _ = transport([lambda req: Resp(req.full_url, {})])
    for method in ("PUT", "DELETE", "PATCH"):
        with pytest.raises(bounds.ProofBoundaryError) as excinfo:
            t.request(method, HF_RUNTIME)
        assert excinfo.value.code == "EFFECT_SCOPE_REJECTED"
    assert opener.requests == []


@pytest.mark.parametrize("repo_id", ["SZLHOLDINGS/other", "szlholdings/a11oy", "SZLHOLDINGS/a11oy ", ""])
def test_wrong_space_id_is_rejected(repo_id):
    t, opener, _ = transport([lambda req: Resp(req.full_url, {"stage": "RUNNING"})])
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        bounds.ScopedSpaceControl(t, "tok", repo_id)
    assert excinfo.value.code == "SPACE_SCOPE_REJECTED"
    control = bounds.ScopedSpaceControl(t, "tok")
    for call in (control.get_space_runtime, control.pause_space, control.restart_space):
        with pytest.raises(bounds.ProofBoundaryError) as excinfo:
            call(repo_id=repo_id)
        assert excinfo.value.code == "SPACE_SCOPE_REJECTED"
    assert opener.requests == []
    assert control.effects == []


def test_space_control_has_no_other_capability_and_no_factory_reboot():
    t, opener, _ = transport([lambda req: Resp(req.full_url, {})])
    control = bounds.ScopedSpaceControl(t, "tok")
    for name in ("delete_space_secret", "add_space_secret", "add_space_variable",
                 "delete_space_storage", "request_space_hardware", "upload_file", "delete_repo"):
        with pytest.raises(bounds.ProofBoundaryError) as excinfo:
            getattr(control, name)
        assert excinfo.value.code == "EFFECT_SCOPE_REJECTED"
    with pytest.raises(bounds.ProofBoundaryError):
        control.restart_space(repo_id="SZLHOLDINGS/a11oy", factory_reboot=True)
    assert opener.requests == []


def test_space_control_calls_only_the_canonical_endpoints_and_never_retries_effects():
    t, opener, _ = transport([
        lambda req: Resp(req.full_url, {"stage": "RUNNING"}),
        http_error(HF_RUNTIME, 503),
    ])
    control = bounds.ScopedSpaceControl(t, "tok")
    assert control.get_space_runtime(repo_id="SZLHOLDINGS/a11oy") == {"stage": "RUNNING"}
    with pytest.raises(bounds.ProofBoundaryError):
        control.restart_space(repo_id="SZLHOLDINGS/a11oy")
    assert [r.full_url for r in opener.requests] == [
        "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy/runtime",
        "https://huggingface.co/api/spaces/SZLHOLDINGS/a11oy/restart",
    ]
    assert control.effects == [{"effect": "restart_space", "repo_id": "SZLHOLDINGS/a11oy"}]


def _envelope(private_key, body=b'{"receipt":1}'):
    sig = private_key.sign(bounds.dsse_pae(bounds.KHIPU_PAYLOAD_TYPE, body), ec.ECDSA(hashes.SHA256()))
    return {
        "payloadType": bounds.KHIPU_PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode("ascii"),
        "signed": True,
        "signatures": [{"sig": base64.b64encode(sig).decode("ascii"), "keyid": "k"}],
    }


def _der(private_key):
    return private_key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)


def test_pinned_key_file_matches_the_reviewed_fingerprint():
    der = bounds._load_pinned_key_der(bounds.REPO_ROOT)
    assert hashlib.sha256(der).hexdigest() == bounds.PINNED_RUNTIME_KEY_DER_SHA256


def test_signature_by_the_pinned_key_verifies():
    key = ec.generate_private_key(ec.SECP256R1())
    result = bounds.verify_envelope_against_pinned_key(_envelope(key), public_key_der=_der(key))
    assert result["signature_verified"] is True
    assert result["verified_against"] == bounds.PINNED_RUNTIME_KEY_PATH


def test_receipt_signature_mismatch_is_rejected():
    signer = ec.generate_private_key(ec.SECP256R1())
    other = ec.generate_private_key(ec.SECP256R1())
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        bounds.verify_envelope_against_pinned_key(_envelope(signer), public_key_der=_der(other))
    assert excinfo.value.code == "RECEIPT_SIGNATURE_INVALID"
    # And against the real pinned key.
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        bounds.verify_envelope_against_pinned_key(_envelope(signer))
    assert excinfo.value.code == "RECEIPT_SIGNATURE_INVALID"


def test_tampered_payload_or_wrong_type_is_rejected():
    key = ec.generate_private_key(ec.SECP256R1())
    envelope = _envelope(key)
    envelope["payload"] = base64.b64encode(b'{"receipt":2}').decode("ascii")
    with pytest.raises(bounds.ProofBoundaryError):
        bounds.verify_envelope_against_pinned_key(envelope, public_key_der=_der(key))
    envelope = _envelope(key)
    envelope["payloadType"] = "application/other"
    with pytest.raises(bounds.ProofBoundaryError):
        bounds.verify_envelope_against_pinned_key(envelope, public_key_der=_der(key))


def test_unsigned_receipt_is_rejected():
    with pytest.raises(bounds.ProofBoundaryError) as excinfo:
        bounds.verify_envelope_against_pinned_key(
            {"payloadType": bounds.KHIPU_PAYLOAD_TYPE, "payload": "e30=", "signed": False,
             "signatures": []})
    assert excinfo.value.code == "RECEIPT_UNSIGNED"


def test_bounded_report_redacts_prose_and_caps_shape():
    report = bounds.bounded_report({
        "code": "LIVE_PROOF_PASSED",
        "sha": "a" * 40,
        "message": "Traceback: something failed with token",
        "nested": {"x": [1, 2, "ok"]},
        "bad key!": "dropped",
    })
    assert report["code"] == "LIVE_PROOF_PASSED"
    assert report["sha"] == "a" * 40
    assert report["message"] == "[REDACTED_TEXT]"
    assert "bad key!" not in report
    assert len(bounds.bounded_report(list(range(100)))) == 32
