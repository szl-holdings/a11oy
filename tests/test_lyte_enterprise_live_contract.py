# SPDX-License-Identifier: Apache-2.0
"""Behavioral negative controls for the canonical Lyte live verifier.

Fixtures exercise the verifier, not the forecasting algorithm. A separate
source-pinned integration run checks these expectations against the Lyte app.
"""
from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("lyte_live_test", ROOT / "scripts/lyte_enterprise_live_contract.py")
assert SPEC is not None and SPEC.loader is not None
CONTRACT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTRACT)
REVISION = "7cd4305014ee638f773d6e128f345ad6a545be58"
PREFIX = "/api/lyte/v2"


class FixtureTransport:
    def __init__(self, mutation=None):
        self.mutation = mutation
        self.calls = []
        self.receipt_reads = 0

    def json(self, path, *, method="GET", payload=None, **kwargs):
        self.calls.append((method, path))
        status, body = self.response(path, payload)
        if self.mutation:
            status, body = self.mutation(path, payload, status, body)
        return status, body

    def response(self, path, payload):
        if path in CONTRACT.IDENTITY_PATHS:
            return 200, {
                "source_repository": "szl-holdings/lyte-services", "source_revision": REVISION,
                "runtime_repository": "szl-holdings/lyte-services", "runtime_source_revision": REVISION,
                "version": "4.0.0", "effectors_enabled": False, "human_approval_required": True,
                "ok": True, "service": "lyte-signal-lattice", "ready": True,
                "checks": {"database": "READY"}, "source_binding": {"bindings_agree": True},
                "build": {"state": "OBSERVED", "revision": REVISION},
                "schema": "szl.lyte-build/v2", "data_mode": "SAMPLE",
                "persistence": {"state": "READY", "tenant_workspace_scoped": True},
            }
        name = path.removeprefix(PREFIX + "/")
        if name == "catalog":
            return 200, {"lenses": [{"id": x} for x in ("service", "journey", "business", "agent", "delivery", "decision")],
                         "effectors_enabled": False, "data_mode": "SAMPLE"}
        if name == "capabilities":
            return 200, {"operational": ["living_anatomy", "second_brain", "hatun_review", "deterministic_ask_lyte", "tenant_workspace_isolation"], "effectors_enabled": False}
        if name == "anatomy":
            return 200, {"stages": list(range(9)), "machine_enforced": True, "effectors_enabled": False}
        if name == "formulas":
            return 200, {"formulas": [{"can_authorize": False, "can_be_sole_allow_basis": False}], "lambda_status": "CONJECTURE_1_ADVISORY", "formula_output_can_authorize": False}
        if name == "sources":
            return 200, {"arbitrary_url_fetch": False}
        if name == "second-brain":
            return 200, {"count": 1, "raw_session_token_recorded": False, "scope_digest_exposed": False, "items": [{"receipt_hash": "a" * 64}]}
        if name == "receipts":
            self.receipt_reads += 1
            return 200, {"count": 1}
        if name in CONTRACT.ENTITY_PATHS:
            return 200, {"items": [], "count": 0, "data_mode": "SAMPLE"}
        if name == "ask":
            return 200, {"truth_label": "MODELED", "confidence_basis": "DETERMINISTIC_QUERY_MATCH", "evidence_receipt_ids": ["b" * 64], "formula_ids": [], "causality_claimed": False, "can_execute": False}
        if name == "hatun/evaluate":
            return 200, {"decision": "DENY" if payload.get("requests_execution") else "REVIEW", "can_authorize": False, "can_execute": False, "effectors_enabled": False}
        if name == "analyze":
            return 503, {"detail": "authentication unavailable; request denied"}
        if name.startswith("github/"):
            return 200, {"read_only": True, "receipt_persisted": False, "persistence_requires_authenticated_ingest": True, "arbitrary_url_fetch": False, "truth_label": "REPORTED"}
        if name == "forecast":
            if payload.get("provider") == "granite":
                return 503, {"detail": "Granite provider is not admitted in this deployment"}
            if payload["horizon"] == 0 or all(v is None for v in payload["values"]) or len(payload["quantiles"]) > 99:
                return 422, {"detail": "invalid forecast request"}
            values = payload["values"]
            processed = [10.0, 11.0, 11.0, 13.0, 14.0]
            qs = payload["quantiles"]
            keys = ["q10", "q50", "q90"] if len(qs) == 3 else ["q10.1", "q10.4", "q50", "q90"]
            points = [{"step": step, "quantiles": {key: float(step + i) for i, key in enumerate(keys)}} for step in range(1, 4)]
            raw = {"contract": "szl.lyte.forecast-loom/v1", **payload}
            return 200, {"points": points, "execution_authority": "NONE", "receipt": {
                "contract": "szl.lyte.forecast-loom/v1", "provider": "szl.robust-drift/v1",
                "signal_id": payload["signal_id"], "horizon": 3, "quantiles": qs,
                "input_sha256": CONTRACT.digest({**raw, "values": processed}),
                "raw_input_sha256": CONTRACT.digest(raw), "output_sha256": CONTRACT.digest(points),
                "context_points": 5, "original_context_points": 5, "truncated_points": 0,
                "imputed_points": int(None in values),
            }}
        raise AssertionError(f"unexpected verifier path: {path}")

    def text(self, path):
        if path == "/":
            return 200, ('Business Observability Command id="ask-open" id="main-content" '
                         'href="/static/lyte/styles.css" src="/static/lyte/app.js" viewport-fit=cover')
        if path.endswith(".css"):
            return 200, "prefers-reduced-motion forced-colors focus-visible"
        if path.endswith(".js"):
            return 200, "/* fixture */" * 20
        raise AssertionError(path)


def verify(transport):
    return CONTRACT.verify_current_contract(transport.json, transport.text, revision=REVISION, version="4.0.0")


def test_complete_fixture_passes_without_production_admission():
    transport = FixtureTransport()
    result = verify(transport)
    assert result["complete"] is True, result["failed_checks"]
    assert result["production_telemetry_verified"] is False
    assert result["production_granite_admitted"] is False
    assert result["execution_authority"] == "NONE"
    assert len(result["checks"]) >= 50
    assert not any("/v3/" in path for _, path in transport.calls)
    assert not any("/ingest/" in path for _, path in transport.calls)


@pytest.mark.parametrize("path,field,value", [
    ("/api/build-info", "schema", "szl.build-info/v1"),
    ("/api/build-info", "source_revision", "a" * 40),
    ("/api/source", "runtime_source_revision", "b" * 40),
    ("/healthz", "effectors_enabled", True),
    ("/healthz", "human_approval_required", False),
    ("/healthz", "ok", False),
    ("/readyz", "ready", False),
    ("/readyz", "checks", {"database": "UNAVAILABLE"}),
    ("/api/build-info", "source_binding", {"bindings_agree": False}),
    (PREFIX + "/catalog", "lenses", []),
    (PREFIX + "/catalog", "data_mode", "REAL_ONLY"),
    (PREFIX + "/capabilities", "operational", []),
    (PREFIX + "/anatomy", "machine_enforced", False),
    (PREFIX + "/formulas", "formula_output_can_authorize", True),
    (PREFIX + "/formulas", "lambda_status", "THEOREM"),
    (PREFIX + "/sources", "arbitrary_url_fetch", True),
    (PREFIX + "/second-brain", "items", []),
    (PREFIX + "/second-brain", "raw_session_token_recorded", True),
    (PREFIX + "/second-brain", "scope_digest_exposed", True),
    (PREFIX + "/ask", "causality_claimed", True),
    (PREFIX + "/ask", "evidence_receipt_ids", []),
    (PREFIX + "/hatun/evaluate", "can_execute", True),
    (PREFIX + "/hatun/evaluate", "can_authorize", True),
    (PREFIX + "/github/szl-holdings/lyte-services", "receipt_persisted", True),
    (PREFIX + "/analyze", "detail", "unrelated failure"),
])
def test_each_contract_drift_fails_closed(path, field, value):
    def mutate(observed, payload, status, body):
        if observed == path:
            body[field] = value
        return status, body
    result = verify(FixtureTransport(mutate))
    assert result["complete"] is False
    assert result["failed_checks"]


@pytest.mark.parametrize("mode", ["hash", "input_hash", "raw_hash", "crossing", "collision", "authority", "provider", "missing_step"])
def test_forged_forecast_evidence_cannot_pass(mode):
    def mutate(path, payload, status, body):
        if path.endswith("/forecast") and status == 200:
            if mode == "hash": body["receipt"]["output_sha256"] = "f" * 64
            elif mode == "input_hash": body["receipt"]["input_sha256"] = "e" * 64
            elif mode == "raw_hash": body["receipt"]["raw_input_sha256"] = "d" * 64
            elif mode == "authority": body["execution_authority"] = "ALLOW"
            elif mode == "provider": body["receipt"]["provider"] = "unknown"
            elif mode == "missing_step": body["points"].pop()
            elif mode == "collision": body["points"][0]["quantiles"].pop(next(iter(body["points"][0]["quantiles"])))
            elif mode == "crossing":
                first = next(iter(body["points"][0]["quantiles"]))
                body["points"][0]["quantiles"][first] = 1000.0
                body["receipt"]["output_sha256"] = CONTRACT.digest(body["points"])
        return status, body
    assert verify(FixtureTransport(mutate))["complete"] is False


def test_unrelated_granite_503_is_not_admission_evidence():
    def mutate(path, payload, status, body):
        if payload and payload.get("provider") == "granite":
            return 503, {"detail": "model loading failed"}
        return status, body
    assert verify(FixtureTransport(mutate))["complete"] is False


def test_html_200_is_not_a_json_api_success():
    def mutate(path, payload, status, body):
        return (200, "<html>fallback</html>") if path == "/api/build-info" else (status, body)
    assert verify(FixtureTransport(mutate))["complete"] is False


def test_public_receipt_side_effect_is_detected():
    transport = FixtureTransport()
    def mutate(path, payload, status, body):
        if path == PREFIX + "/receipts" and transport.receipt_reads > 1:
            body["count"] += 1
        return status, body
    transport.mutation = mutate
    assert verify(transport)["complete"] is False


def test_missing_responsive_asset_fails_closed():
    transport = FixtureTransport()
    original = transport.text
    transport.text = lambda path: (404, "") if path.endswith(".css") else original(path)
    assert verify(transport)["complete"] is False


def test_returned_fixture_mutations_do_not_leak_between_runs():
    first = verify(FixtureTransport())
    second = verify(FixtureTransport())
    assert copy.deepcopy(first) == second
