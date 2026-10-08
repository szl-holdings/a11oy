"""Independent HMAC protocol cases; ephemeral test keys are never installation keys."""

from email.message import Message
import hashlib
import hmac
import json
import secrets
from unittest import mock

import pytest
import szl_meter_access as auth


BASE_TIME = 1_800_000_000_000_000_000


def signed(key, *, client="reader", method="GET", target="/metrics",
           audience="https://meter2.a-11-oy.com", stamp=BASE_TIME + 1, nonce=None):
    nonce = nonce or secrets.token_hex(16)
    stamp = str(stamp)
    message = "\n".join(("szl-meter-hmac-v1", method, target, audience, client, stamp, nonce)).encode("ascii")
    headers = Message()
    headers["Host"] = audience.split("://", 1)[1]
    for name, value in zip(("X-SZL-Meter-Client", "X-SZL-Meter-Time", "X-SZL-Meter-Nonce",
                            "X-SZL-Meter-Signature"),
                           (client, stamp, nonce, hmac.new(bytes.fromhex(key), message, hashlib.sha256).hexdigest())):
        headers[name] = value
    return headers


@pytest.fixture
def protocol():
    key = secrets.token_hex(32)
    now = [BASE_TIME]
    verifier = auth.MeterRequestVerifier("https://meter2.a-11-oy.com", json.dumps({"reader": key}),
                                         clock=lambda: now[0], capacity=2)
    now[0] += 100
    return key, now, verifier


def test_valid_get_then_replay_is_denied(protocol):
    key, _, verifier = protocol
    headers = signed(key)
    assert verifier.accepts("GET", "/metrics", headers)
    assert not verifier.accepts("GET", "/metrics", headers)


@pytest.mark.parametrize("changes", [{"method": "POST"}, {"target": "/"},
                                     {"target": "/metrics?scope=private"},
                                     {"audience": "https://meter.a-11-oy.com"},
                                     {"client": "other-reader"}])
def test_mac_binds_method_exact_target_audience_and_client(protocol, changes):
    key, _, verifier = protocol
    assert not verifier.accepts("GET", "/metrics", signed(key, **changes))


@pytest.mark.parametrize("target", ["/metrics?x=1", "//metrics", "/metrics/", "https://meter2.a-11-oy.com/metrics"])
def test_unknown_targets_never_gain_authentication(protocol, target):
    key, _, verifier = protocol
    assert not verifier.accepts("GET", target, signed(key, target=target))


@pytest.mark.parametrize("stamp", [BASE_TIME - 1, BASE_TIME + 101, BASE_TIME - 30_000_000_001])
def test_pre_start_future_and_expired_timestamps_deny(protocol, stamp):
    key, _, verifier = protocol
    assert not verifier.accepts("GET", "/metrics", signed(key, stamp=stamp))


def test_restart_rejects_previously_signed_request(protocol):
    key, now, verifier = protocol
    headers = signed(key)
    assert verifier.accepts("GET", "/metrics", headers)
    now[0] += 1
    successor = auth.MeterRequestVerifier("https://meter2.a-11-oy.com", json.dumps({"reader": key}),
                                        clock=lambda: now[0])
    assert not successor.accepts("GET", "/metrics", headers)


def test_bad_mac_does_not_consume_nonce(protocol):
    key, _, verifier = protocol
    nonce = secrets.token_hex(16)
    assert not verifier.accepts("GET", "/metrics", signed(secrets.token_hex(32), nonce=nonce))
    assert verifier.accepts("GET", "/metrics", signed(key, nonce=nonce))


def test_replay_cache_capacity_denies_instead_of_evicting_live_nonces(protocol):
    key, now, verifier = protocol
    first = signed(key)
    assert verifier.accepts("GET", "/metrics", first)
    assert verifier.accepts("GET", "/metrics", signed(key))
    assert not verifier.accepts("GET", "/metrics", signed(key))
    assert not verifier.accepts("GET", "/metrics", first)
    now[0] += 30_000_000_001
    assert verifier.accepts("GET", "/metrics", signed(key, stamp=now[0]))
    assert not verifier.accepts("GET", "/metrics", first)


def test_clock_rollback_denies_even_a_new_valid_mac(protocol):
    key, now, verifier = protocol
    assert verifier.accepts("GET", "/metrics", signed(key))
    now[0] -= 1
    assert not verifier.accepts("GET", "/metrics", signed(key, stamp=now[0]))


@pytest.mark.parametrize("raw", ["", "{}", "[]", "null", '{"reader":"bad"}',
                                '{"reader":"bad","reader":"other"}'])
def test_invalid_key_configuration_is_redacted(raw):
    with pytest.raises(auth.MeterAuthConfigurationError) as error:
        auth.MeterRequestVerifier("https://meter2.a-11-oy.com", raw)
    assert "bad" not in str(error.value) and "other" not in str(error.value)


def test_per_client_keys_must_be_distinct():
    key = secrets.token_hex(32)
    with pytest.raises(auth.MeterAuthConfigurationError):
        auth.MeterRequestVerifier("https://meter2.a-11-oy.com", json.dumps({"one": key, "two": key}))


@pytest.mark.parametrize("url", ["http://meter2.a-11-oy.com/metrics", "http://100.64.0.1:9471/",
                                "https://reader@meter2.a-11-oy.com/", "https://meter2.a-11-oy.com/#fragment"])
def test_insecure_or_ambiguous_transport_denies_before_network(monkeypatch, url):
    with mock.patch.object(auth.urllib.request, "build_opener", side_effect=AssertionError("network")):
        with pytest.raises(auth.MeterAuthConfigurationError):
            auth.open_meter_get(url, timeout=1)


def test_native_client_signs_real_exact_target_and_never_returns_key(monkeypatch):
    key = secrets.token_hex(32)
    origin = "https://meter2.a-11-oy.com"
    monkeypatch.setenv("SZL_METER_HMAC_TARGETS", json.dumps({origin: {"client_id": "reader", "key_hex": key}}))
    verifier = auth.MeterRequestVerifier(origin, json.dumps({"reader": key}))
    headers = Message()
    headers["Host"] = "meter2.a-11-oy.com"
    for name, value in auth.meter_request_headers(origin + "/metrics").items():
        headers[name] = value
    assert verifier.accepts("GET", "/metrics", headers)
    assert key not in str(headers)
    assert not verifier.accepts("GET", "/", headers)


def test_valid_mac_cannot_change_actual_request_authority(protocol):
    key, _, verifier = protocol
    headers = signed(key)
    headers.replace_header("Host", "other-meter.test")
    assert not verifier.accepts("GET", "/metrics", headers)


def test_caller_headers_cannot_override_authentication_or_host(monkeypatch):
    origin = "https://meter2.a-11-oy.com"
    key = secrets.token_hex(32)
    monkeypatch.setenv("SZL_METER_HMAC_TARGETS", json.dumps({origin: {
        "client_id": "reader", "key_hex": key}}))
    captured = []
    class Opener:
        def open(self, request, *, timeout):
            captured.append(request)
            return object()
    monkeypatch.setattr(auth.urllib.request, "build_opener", lambda *handlers: Opener())
    auth.open_meter_get(origin + "/metrics", timeout=1, headers={
        "Host": "other-meter.test", "X-SZL-Meter-Client": "forged-client",
        "X-SZL-Meter-Signature": "forged-signature", "CF-Access-Client-Secret": "caller-secret"})
    observed = {name.lower(): value for name, value in captured[0].header_items()}
    assert "host" not in observed
    assert observed["x-szl-meter-client"] == "reader"
    assert observed["x-szl-meter-signature"] != "forged-signature"
    assert observed.get("cf-access-client-secret") != "caller-secret"


def test_invalid_unused_target_config_also_denies_before_network(monkeypatch):
    origin = "https://meter2.a-11-oy.com"
    monkeypatch.setenv("SZL_METER_HMAC_TARGETS", json.dumps({
        origin: {"client_id": "reader", "key_hex": secrets.token_hex(32)},
        "https://other-meter.test": {"client_id": "reader", "key_hex": "invalid"}}))
    with mock.patch.object(auth.urllib.request, "build_opener", side_effect=AssertionError("network")):
        with pytest.raises(auth.MeterAuthConfigurationError):
            auth.open_meter_get(origin + "/metrics", timeout=1)
