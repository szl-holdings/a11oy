"""Tests for rosie.console — spans, mesh, version, telemetry, health.

Covers the Span Explorer fixture, mesh-health aggregation, build identity in
/healthz, structured JSON logging, and the OTel span context manager's
graceful-degradation path.
"""

import importlib
import json
import logging

import pytest

from src.console import health, mesh, spans, telemetry, version
from src.console.receipt_verifier import sign_payload


# ── Span Explorer ───────────────────────────────────────────────────────────
class TestSpans:
    def test_default_count(self):
        assert len(spans.generate_spans()) == spans.DEFAULT_SPAN_COUNT

    def test_generation_is_deterministic(self):
        assert spans.generate_spans(40) == spans.generate_spans(40)

    def test_span_ids_unique_and_zero_padded(self):
        out = spans.generate_spans(20)
        ids = [s.span_id for s in out]
        assert len(set(ids)) == 20
        assert out[0].span_id == "span-0000"

    def test_components_cycle_over_all_five(self):
        out = spans.generate_spans(10)
        assert {s.component for s in out} == set(spans.COMPONENTS)

    def test_status_only_ok_or_error(self):
        assert {s.status for s in spans.generate_spans(50)} <= {"ok", "error"}

    def test_negative_count_raises(self):
        with pytest.raises(ValueError):
            spans.generate_spans(-1)

    def test_filter_by_component(self):
        out = spans.filter_spans(spans.generate_spans(), component="sentra")
        assert out and all(s.component == "sentra" for s in out)

    def test_filter_by_status_and_limit(self):
        out = spans.filter_spans(spans.generate_spans(), status="error", limit=3)
        assert len(out) <= 3
        assert all(s.status == "error" for s in out)

    def test_filter_negative_limit_raises(self):
        with pytest.raises(ValueError):
            spans.filter_spans(spans.generate_spans(), limit=-2)

    def test_provenance_marks_synthetic(self):
        prov = spans.provenance()
        assert prov["live"] is False
        assert prov["source"] == "synthetic-fixture"


# ── Mesh health ───────────────────────────────────────────────────────────────
class TestMesh:
    def test_reports_all_five_components(self):
        result = mesh.mesh_health(spans.generate_spans())
        assert [c.component for c in result.components] == list(spans.COMPONENTS)

    def test_totals_are_consistent(self):
        fixture = spans.generate_spans(50)
        result = mesh.mesh_health(fixture)
        assert result.total_spans == 50
        assert result.total_errors == sum(c.error_count for c in result.components)

    def test_component_with_no_spans_is_healthy_zero(self):
        ch = mesh.component_health("ghost", [])
        assert ch.total_spans == 0
        assert ch.error_rate_pct == 0.0
        assert ch.healthy is True

    def test_error_rate_drives_health_flag(self):
        fixture = spans.generate_spans(50)
        for c in mesh.mesh_health(fixture).components:
            assert c.healthy == (c.error_rate_pct < mesh.GREEN_THRESHOLD_PCT)

    def test_as_dict_round_trips_json(self):
        d = mesh.mesh_health(spans.generate_spans()).as_dict()
        assert json.loads(json.dumps(d))["total_spans"] == spans.DEFAULT_SPAN_COUNT


# ── Build identity / version ──────────────────────────────────────────────────
class TestVersion:
    def test_env_sha_takes_priority(self, monkeypatch):
        monkeypatch.setenv("ROSIE_GIT_SHA", "deadbeefcafe1234")
        importlib.reload(version)
        try:
            info = version.build_info()
            assert info["gitSha"] == "deadbeefcafe1234"
            assert info["gitShaShort"] == "deadbeefcafe"
        finally:
            monkeypatch.delenv("ROSIE_GIT_SHA", raising=False)
            importlib.reload(version)

    def test_boot_ts_is_iso_z(self):
        assert version.BOOT_TS.endswith("Z")
        assert "T" in version.BOOT_TS

    def test_build_info_has_required_fields(self):
        info = version.build_info()
        assert {"service", "version", "gitSha", "gitShaShort", "bootTs"} <= set(info)
        assert info["service"] == "rosie"


# ── Structured logging ────────────────────────────────────────────────────────
class TestTelemetryLogging:
    def test_json_formatter_emits_valid_json(self):
        rec = logging.makeLogRecord(
            {"name": "rosie", "levelno": logging.INFO, "levelname": "INFO", "msg": "hi"}
        )
        out = telemetry.JsonLogFormatter().format(rec)
        parsed = json.loads(out)
        assert parsed["msg"] == "hi"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "rosie"
        assert parsed["ts"].endswith("Z")

    def test_extra_fields_merged_into_json(self):
        logger = telemetry.configure_logging(force=True)
        rec = logger.makeRecord(
            "rosie", logging.INFO, "f", 1, "msg", None, None,
            extra={"verdict": "valid", "ok": True},
        )
        parsed = json.loads(telemetry.JsonLogFormatter().format(rec))
        assert parsed["verdict"] == "valid"
        assert parsed["ok"] is True

    def test_configure_logging_idempotent(self):
        a = telemetry.configure_logging()
        b = telemetry.configure_logging()
        assert a is b
        assert len(a.handlers) == 1


# ── OTel span graceful degradation ────────────────────────────────────────────
class TestTelemetrySpan:
    def test_span_noop_when_otel_disabled(self, monkeypatch):
        monkeypatch.delenv("ROSIE_OTEL_ENABLED", raising=False)
        assert telemetry.otel_active() is False
        with telemetry.span("unit_test", k="v") as s:
            assert s is None  # degraded path yields None

    def test_otel_active_false_without_env_even_if_installed(self, monkeypatch):
        monkeypatch.delenv("ROSIE_OTEL_ENABLED", raising=False)
        assert telemetry.otel_active() is False

    def test_span_body_executes_in_both_paths(self):
        ran = []
        with telemetry.span("unit_test"):
            ran.append(1)
        assert ran == [1]


# ── Health surface ─────────────────────────────────────────────────────────────
class TestHealth:
    def test_healthz_payload_shape(self):
        p = health.health_payload()
        assert p["ok"] is True
        assert p["service"] == "rosie"
        assert "gitSha" in p and "bootTs" in p
        assert isinstance(p["otel"], bool)
        assert p["components"] == list(spans.COMPONENTS)
        assert "overall_error_rate_pct" in p["mesh"]

    def test_mesh_query_endpoint(self):
        d = health.mesh_query()
        assert d["total_spans"] == spans.DEFAULT_SPAN_COUNT
        assert len(d["components"]) == 5

    def test_verify_receipt_endpoint_valid(self):
        env_json = json.dumps(sign_payload({"receipt_id": "r1"}))
        out = health.verify_receipt(env_json)
        assert out["ok"] is True
        assert out["verdict"] == "valid"

    def test_verify_receipt_endpoint_malformed(self):
        out = health.verify_receipt("{bad")
        assert out["ok"] is False
        assert out["verdict"] == "malformed"

    def test_spans_view_includes_provenance(self):
        out = health.spans_view(limit=5)
        assert out["count"] == 5
        assert out["provenance"]["live"] is False
