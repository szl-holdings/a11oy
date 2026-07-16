"""Focused security and honesty checks for the VSP OpenTelemetry boundary."""

from vsp_otel import middleware as otel


class _DummyApp:
    title = "A11oy"

    def __init__(self):
        self.middlewares = []

    def middleware(self, kind):
        assert kind == "http"

        def decorate(fn):
            self.middlewares.append(fn)
            return fn

        return decorate


def test_traceparent_accepts_strict_v00_lowercase_only():
    valid = "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
    assert otel.parse_traceparent(valid)["sampled"] is True
    assert otel.parse_traceparent(valid[:-2] + "00")["sampled"] is False
    assert otel.parse_traceparent(valid.replace("abcdef", "ABCDEF")) is None
    assert otel.parse_traceparent("01" + valid[2:]) is None
    assert otel.parse_traceparent("ff" + valid[2:]) is None
    assert otel.parse_traceparent(valid[:-2] + "03") is None
    assert otel.parse_traceparent(valid.replace("0123456789abcdef0123456789abcdef", "0" * 32)) is None


def test_endpoint_policy_is_private_fail_closed_and_secret_free():
    assert otel._endpoint_policy(None)["state"] == "NOT-CONFIGURED"
    local = otel._endpoint_policy("http://127.0.0.1:4317")
    assert local["allowed"] is True and local["reason"] == "LOOPBACK"
    assert local["fingerprint"] and len(local["fingerprint"]) == 16
    private = otel._endpoint_policy("http://10.10.0.4:4317")
    assert private["allowed"] is True and private["reason"] == "PRIVATE-IP"
    ipv6 = otel._endpoint_policy("http://[::1]:4317")
    assert ipv6["allowed"] is True and ipv6["endpoint"] == "http://[::1]:4317"
    assert otel._endpoint_policy("http://0.0.0.0:4317")["state"] == "POLICY-DENIED"
    assert otel._endpoint_policy("http://169.254.1.1:4317")["state"] == "POLICY-DENIED"
    assert otel._endpoint_policy("https://8.8.8.8:4317")["state"] == "POLICY-DENIED"
    assert otel._endpoint_policy("https://user:secret@localhost:4317")["state"] == "POLICY-DENIED"
    assert otel._endpoint_policy("https://localhost:4317/v1/traces")["state"] == "POLICY-DENIED"


def test_dns_endpoint_requires_exact_operator_allowlist():
    denied = otel._endpoint_policy("https://collector.internal:4317", allowed_hosts="")
    assert denied["allowed"] is False
    allowed = otel._endpoint_policy(
        "https://collector.internal:4317", allowed_hosts="collector.internal"
    )
    assert allowed["allowed"] is True
    assert allowed["reason"] == "OPERATOR-ALLOWLISTED-DNS"
    assert "collector.internal" not in allowed["fingerprint"]


def test_status_separates_propagation_from_export_and_redacts_endpoint():
    app = _DummyApp()
    otel.install(app, service_name="test", endpoint=None)
    got = otel.status(app)
    assert got["propagation"] == "READY"
    assert got["export"] == "IN-PROCESS-ONLY"
    assert got["endpoint"]["state"] == "NOT-CONFIGURED"
    assert got["receipt_minted"] is False
    assert "http" not in str(got)
    assert len(app.middlewares) == 1
    otel.install(app, service_name="test", endpoint=None)
    assert len(app.middlewares) == 1
