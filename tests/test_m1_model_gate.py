#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Focused contract, honesty, and assembled-route tests for the M1 gate."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from starlette.testclient import TestClient

import serve
import szl_m1_model_gate as gate


ROOT = Path(__file__).resolve().parents[1]
CLIENT = TestClient(serve.app)
ROUTES = {"/api/a11oy/v1/models/m1", "/api/a11oy/v1/models/m1/infer", "/models/m1"}


def _write(path: Path, value: bytes) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)
    return {"path": path.name, "bytes": len(value), "sha256": hashlib.sha256(value).hexdigest()}


def _write_json(path: Path, value: dict) -> dict:
    raw = (json.dumps(value, indent=2) + "\n").encode("utf-8")
    return _write(path, raw)


def _write_jsonl(path: Path, values: list[dict]) -> dict:
    raw = ("\n".join(json.dumps(value, sort_keys=True, separators=(",", ":")) for value in values) + "\n").encode("utf-8")
    return _write(path, raw)


def _spec(root: Path, relative: str, value: bytes) -> dict:
    path = root / relative
    result = _write(path, value)
    result["path"] = relative
    return result


def _fixture(tmp_path: Path, monkeypatch) -> dict:
    meta = tmp_path / "meta"
    base = tmp_path / "base"
    run = tmp_path / "run"
    base_identity = {
        "repository": "fixture/base", "revision": "a" * 40,
        "architecture": "FixtureLM", "license": "Apache-2.0",
        "license_evidence": "REPORTED_CACHED_AND_OFFICIAL_CARD",
    }
    base_files = [
        _spec(base, "config.json", b'{"model_type":"fixture"}\n'),
        _spec(base, "model.safetensors", b"fixture-base-weights"),
        _spec(base, "tokenizer.json", b'{"version":"1.0"}\n'),
    ]
    adapter_files = [
        _spec(run, "adapter/adapter_config.json", b'{"r":8}\n'),
        _spec(run, "adapter/adapter_model.safetensors", b"fixture-adapter-weights"),
        _spec(run, "adapter/tokenizer.json", b'{"version":"1.0-adapter"}\n'),
    ]
    candidate = {
        "schema": "szl.hf-model-candidate/v1", "candidate_id": "fixture-m1",
        "release_state": "NOT_PROMOTED", "quality_claim": "NOT_ESTABLISHED",
        "base": base_identity,
    }
    evaluation = {
        "schema": "szl.model-evaluation-manifest/v1", "candidate_id": "fixture-m1",
        "evaluation_state": "INCOMPLETE", "promotion_decision": "NOT_PROMOTED",
        "measured": {"offline_reload": {"state": "PASS"}},
        "required_unrun_suites": ["FROZEN_UNSEEN_BASE_VS_ADAPTER"],
    }
    candidate_spec = _write_json(meta / "candidate-manifest.json", candidate)
    evaluation_spec = _write_json(meta / "evaluation-manifest.json", evaluation)
    evaluation_receipt_id = f"m1-evaluation:sha256:{evaluation_spec['sha256']}"
    brain_rows = []
    for index, (role, decision, license_state, split) in enumerate((
        ("DISTINCT_ARTIFACT", "QUARANTINE", "VERSIONED_REPOSITORY_LICENSE", "QUARANTINE"),
        ("ATTRIBUTION_METADATA", "QUARANTINE", "UNKNOWN_ITEM_LEVEL_LICENSE", "QUARANTINE"),
    )):
        text = f"fixture Brain row {index}"
        receipt_id = f"brain-node:sha256:{index + 1:064x}"
        brain_rows.append({
            "schema": "szl.m1-brain-ingest-decision/v1", "receipt_id": receipt_id,
            "brain_anatomy_receipt_id": receipt_id, "node_id": f"fixture-node-{index}",
            "canonical_artifact_id": f"fixture-node-{index}" if role == "DISTINCT_ARTIFACT" else None,
            "artifact_role": role, "kind": "formula" if index == 0 else "person",
            "source_family": "fixture-raw-formula" if index == 0 else "fixture-person",
            "source_family_split": split, "provenance": {"source": "fixture"},
            "license": {"state": license_state}, "freshness": {"state": "VERSION_BOUND_NOT_TIME_FRESH"},
            "safety_decision": "ALLOW_VERSIONED_LOCAL_METADATA" if index == 0 else "QUARANTINE_PERSON_METADATA",
            "training_decision": decision, "training_eligible": False,
            "formula_id": "FX0" if index == 0 else None,
            "formula_status": "KERNEL_ACCEPTED" if index == 0 else None,
            "formula_receipt_id": f"formula:sha256:{10:064x}" if index == 0 else None,
            "evaluation_receipt_id": evaluation_receipt_id, "canonical_text": text,
            "canonical_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        })
    formula_rows = []
    roles = {
        "KERNEL_ACCEPTED": "HOLDOUT_POSITIVE", "CONDITIONAL": "HOLDOUT_ABSTENTION",
        "OPEN": "HOLDOUT_ABSTENTION", "REFUTED": "HOLDOUT_NEGATIVE",
    }
    for index, (status, role) in enumerate(roles.items()):
        text = f"fixture formula {status}"
        receipt_id = f"formula:sha256:{index + 10:064x}"
        formula_rows.append({
            "schema": "szl.m1-formula-curriculum-decision/v1", "receipt_id": receipt_id,
            "formula_receipt_id": receipt_id,
            "brain_anatomy_receipt_id": brain_rows[0]["receipt_id"] if index == 0 else None,
            "formula_id": f"FX{index}", "source_family": f"fixture-formula-{index}",
            "source_family_split": "HOLDOUT", "formula_status": status,
            "training_decision": role, "abstention_required": status in {"OPEN", "CONDITIONAL"},
            "negative_example": status == "REFUTED", "provenance": {"source": "fixture"},
            "license": {"state": "VERSIONED_REPOSITORY_LICENSE"},
            "freshness": {"state": "VERSION_BOUND_NOT_TIME_FRESH"},
            "safety_decision": "ALLOW_HOLDOUT_ONLY", "evaluation_receipt_id": evaluation_receipt_id,
            "canonical_text": text, "canonical_text_sha256": hashlib.sha256(text.encode()).hexdigest(),
        })
    brain_ledger_spec = _write_jsonl(meta / "brain-ingest-ledger.jsonl", brain_rows)
    formula_ledger_spec = _write_jsonl(meta / "formula-curriculum-ledger.jsonl", formula_rows)
    brain_ledger_spec["rows"] = 2
    formula_ledger_spec["rows"] = 4
    corpus_summary = {
        "schema": "szl.m1-corpus-ingestion-manifest/v1", "candidate_id": "fixture-m1",
        "release_state": "NOT_PROMOTED", "training_state": "NOT_RUN",
        "training_relation": "PROPOSAL_ONLY_NOT_USED_BY_EXISTING_ADAPTER", "quality_claim": "NOT_ESTABLISHED",
        "source_snapshot": {"raw_node_count": 2, "distinct_artifact_count": 1, "person_metadata_count": 1},
        "ledgers": {
            "brain_nodes": {**brain_ledger_spec, "rows": 2, "schema": "szl.m1-brain-ingest-decision/v1"},
            "formulas": {**formula_ledger_spec, "rows": 4, "schema": "szl.m1-formula-curriculum-decision/v1"},
        },
        "coverage": {
            "node_decisions_total": 2, "node_decisions_expected": 2, "node_decision_coverage": 1.0,
            "distinct_artifacts": 1, "person_metadata": 1, "quarantined_or_excluded_nodes": 2,
            "raw_nodes_training_quarantined": 2, "training_eligible_nodes": 0,
            "formula_records_current_versioned_sources": 4,
            "formula_requested_200_claim": "NOT_VERIFIED_BY_CURRENT_VERSIONED_SOURCES",
            "formula_status": {status: 1 for status in roles}, "abstention_examples": 2, "negative_examples": 1,
        },
        "source_family_split": {
            "fixture-person": {"split": "QUARANTINE", "rows": 1},
            "fixture-raw-formula": {"split": "QUARANTINE", "rows": 1},
            **{f"fixture-formula-{index}": {"split": "HOLDOUT", "rows": 1} for index in range(4)},
        },
        "resulting_evaluation_receipt": {
            "receipt_id": evaluation_receipt_id, "path": "evaluation-manifest.json",
            "bytes": evaluation_spec["bytes"], "sha256": evaluation_spec["sha256"],
            "state": "INCOMPLETE", "promotion_decision": "NOT_PROMOTED",
        },
    }
    corpus_spec = _write_json(meta / "corpus-ingestion-manifest.json", corpus_summary)
    candidate["full_corpus_proposal"] = {
        "relation": "PROPOSAL_ONLY_NOT_USED_BY_EXISTING_ADAPTER",
        "manifest_path": corpus_spec["path"], "manifest_sha256": corpus_spec["sha256"],
        "brain_raw_nodes": 2, "brain_distinct_artifacts": 1, "formula_records": 4,
        "training_state": "NOT_RUN",
    }
    candidate_spec = _write_json(meta / "candidate-manifest.json", candidate)
    training = {
        "schema": "szl.bounded-lora-training-receipt/v1", "state": "COMPLETED",
        "evidence_label": "MEASURED", "receipt_sha256": "b" * 64,
        "base_model": {"repo": base_identity["repository"], "revision": base_identity["revision"],
                       "network_download_allowed": False},
        "evaluation": {"quality_claim": "NOT_ESTABLISHED"},
        "artifacts": {"promotion_state": "NOT_PROMOTED", "files": adapter_files},
    }
    training_spec = _write_json(run / "training_receipt.json", training)
    training_spec["internal_sha256"] = "b" * 64
    adapter_sha = next(item["sha256"] for item in adapter_files if item["path"].endswith("adapter_model.safetensors"))
    reload_receipt = {
        "schema": "szl.adapter-reload-smoke/v1", "state": "PASS", "offline": True,
        "adapter_model_sha256": adapter_sha, "generated_text_sha256": "c" * 64,
    }
    reload_spec = _write_json(run / "adapter_reload_smoke.json", reload_receipt)
    manifest = {
        "schema": "szl.m1-operational-manifest/v1", "candidate_id": "fixture-m1",
        "release_state": "NOT_PROMOTED", "quality_claim": "NOT_ESTABLISHED",
        "provider": {"id": "a11oy.m1.local-peft/v1", "transport": "IN_PROCESS_ONLY",
                     "network_allowed": False, "expected_gpu_name": "Fixture GPU"},
        "inference_policy": {"tier": "EXPERIMENTAL_LOCAL_ONLY", "production_eligible": False,
                             "max_prompt_chars": 2048, "max_new_tokens": 128,
                             "max_request_bytes": 32768, "concurrency": 1},
        "gpu_admission": {"minimum_free_memory_mib": 100, "maximum_utilization_pct": 25,
                          "maximum_temperature_c": 75},
        "corpus_policy": {"expected_raw_nodes": 2, "expected_distinct_artifacts": 1,
                           "expected_formula_records": 4, "require_full_decision_coverage": True,
                           "require_source_family_isolation": True, "allow_unknown_license_for_training": False,
                           "require_raw_brain_training_quarantine": True,
                           "training_relation": "PROPOSAL_ONLY_NOT_USED_BY_EXISTING_ADAPTER"},
        "base": {**base_identity, "files": base_files}, "adapter": {"files": adapter_files},
        "evidence": {"candidate_manifest": candidate_spec, "evaluation_manifest": evaluation_spec,
                     "corpus_ingestion_manifest": corpus_spec, "brain_ingest_ledger": brain_ledger_spec,
                     "formula_curriculum_ledger": formula_ledger_spec,
                     "training_receipt": training_spec, "reload_receipt": reload_spec},
    }
    _write_json(meta / "operational-manifest.json", manifest)
    monkeypatch.setattr(gate, "MANIFEST_DIR", meta)
    monkeypatch.setattr(gate, "MANIFEST_PATH", meta / "operational-manifest.json")
    monkeypatch.setenv("A11OY_M1_RUN_ROOT", str(run))
    monkeypatch.setenv("A11OY_M1_BASE_SNAPSHOT", str(base))
    monkeypatch.setenv("A11OY_M1_PROVIDER_ID", "a11oy.m1.local-peft/v1")
    monkeypatch.delenv("A11OY_M1_BASE_URL", raising=False)
    monkeypatch.setattr(gate, "_runtime_provider", lambda _: gate._result(
        gate.PASS, "fixture local provider verified", provider_id="a11oy.m1.local-peft/v1",
        transport="IN_PROCESS_ONLY", network_allowed=False,
    ))
    monkeypatch.setattr(gate, "_gpu_admission", lambda _: gate._result(
        gate.PASS, "fixture GPU admitted", telemetry={"name": "Fixture GPU"},
    ))
    return {"manifest": manifest, "base": base, "run": run, "meta": meta,
            "brain_ledger": meta / "brain-ingest-ledger.jsonl"}


def _payload(**overrides) -> dict:
    payload = {
        "schema": gate.INFER_SCHEMA, "prompt": "State the evidence boundary.",
        "max_new_tokens": 32, "temperature": 0, "requested_tier": "EXPERIMENTAL_LOCAL_ONLY",
        "provider_id": "a11oy.m1.local-peft/v1",
    }
    payload.update(overrides)
    return payload


def test_unconfigured_candidate_is_structured_unavailable_never_production(monkeypatch):
    monkeypatch.delenv("A11OY_M1_RUN_ROOT", raising=False)
    monkeypatch.delenv("A11OY_M1_BASE_SNAPSHOT", raising=False)
    monkeypatch.delenv("A11OY_M1_PROVIDER_ID", raising=False)
    status = gate.operational_status()
    assert status["operational_state"] in (gate.UNAVAILABLE, gate.BLOCKED)
    assert status["release_state"] == "NOT_PROMOTED"
    assert status["production_eligible"] is False
    assert status["inference_mode"] == "DISABLED"
    assert status["stages"]["inference"]["production"] == "BLOCKED"


def test_exact_artifact_receipt_and_gpu_chain_enables_only_experimental(tmp_path, monkeypatch):
    _fixture(tmp_path, monkeypatch)
    status = gate.operational_status()
    assert status["operational_state"] == gate.READY
    assert status["stages"]["weights"]["state"] == gate.PASS
    assert status["stages"]["corpus"]["state"] == "FULL_DECISION_LEDGER_VERIFIED"
    assert status["corpus_coverage"]["node_decisions_total"] == 2
    assert status["corpus_coverage"]["quarantined_or_excluded_nodes"] == 2
    assert status["stages"]["load"]["state"] == "READY_TO_LOAD"
    assert status["stages"]["evaluation"]["state"] == "EVIDENCE_VERIFIED_WITH_LIMITS"
    assert status["stages"]["inference"]["state"] == "ENABLED_EXPERIMENTAL_LOCAL_ONLY"
    assert status["checks"]["evaluation_receipt"]["quality_claim"] == "NOT_ESTABLISHED"
    assert status["production_eligible"] is False


def test_tampered_adapter_fails_closed_before_inference(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, monkeypatch)
    (fixture["run"] / "adapter" / "adapter_model.safetensors").write_bytes(b"tampered-adapter-weights")
    called = False

    def never_called(*_):
        nonlocal called
        called = True
        return "forbidden"

    monkeypatch.setattr(gate, "_local_peft_inference", never_called)
    result, code = gate.run_inference(_payload())
    assert code == 409
    assert result["state"] == gate.BLOCKED
    assert result["inference"] is None
    assert called is False


def test_bounded_inference_returns_receipt_but_retains_not_promoted(tmp_path, monkeypatch):
    _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(gate, "_local_peft_inference", lambda parsed, manifest: "Evidence is bounded.")
    response = CLIENT.post("/api/a11oy/v1/models/m1/infer", json=_payload())
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "RESULT"
    assert body["release_state"] == "NOT_PROMOTED"
    assert body["quality_claim"] == "NOT_ESTABLISHED"
    assert body["production_eligible"] is False
    assert body["inference"]["text"] == "Evidence is bounded."
    assert body["receipt"]["signature_state"] == "UNSIGNED_DETERMINISTIC_DIGEST_ONLY"
    assert body["receipt"]["network"] == "DISABLED"
    assert body["receipt"]["corpus_receipt_id"].startswith("m1-corpus:sha256:")
    assert body["receipt"]["evaluation_receipt_id"].startswith("m1-evaluation:sha256:")
    assert body["receipt"]["corpus_relation"] == "PROPOSAL_ONLY_NOT_USED_BY_EXISTING_ADAPTER"


def test_tampered_corpus_row_fails_closed_before_inference(tmp_path, monkeypatch):
    fixture = _fixture(tmp_path, monkeypatch)
    with fixture["brain_ledger"].open("ab") as stream:
        stream.write(b'{"tampered":true}\n')
    called = False

    def never_called(*_):
        nonlocal called
        called = True
        return "forbidden"

    monkeypatch.setattr(gate, "_local_peft_inference", never_called)
    result, code = gate.run_inference(_payload())
    assert code == 409
    assert result["state"] == gate.BLOCKED
    assert result["inference"] is None
    assert called is False


def test_production_provider_mismatch_hidden_fields_and_oversize_are_rejected(tmp_path, monkeypatch):
    _fixture(tmp_path, monkeypatch)
    production = CLIENT.post("/api/a11oy/v1/models/m1/infer", json=_payload(requested_tier="PRODUCTION"))
    assert production.status_code == 422
    assert production.json()["release_state"] == "NOT_PROMOTED"

    mismatch = CLIENT.post("/api/a11oy/v1/models/m1/infer", json=_payload(provider_id="remote-provider"))
    assert mismatch.status_code == 422
    hidden = _payload(url="https://must-not-fetch.invalid")
    assert CLIENT.post("/api/a11oy/v1/models/m1/infer", json=hidden).status_code == 422
    oversize = CLIENT.post(
        "/api/a11oy/v1/models/m1/infer", content=b'{"padding":"' + b"x" * 32768 + b'"}',
        headers={"content-type": "application/json"},
    )
    assert oversize.status_code == 422


def test_provider_identity_and_gpu_policy_fail_closed(monkeypatch):
    manifest = json.loads((ROOT / "model_release" / "m1" / "operational-manifest.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(gate.importlib.util, "find_spec", lambda _: object())
    monkeypatch.setenv("A11OY_M1_PROVIDER_ID", "wrong")
    assert gate._runtime_provider(manifest)["state"] == gate.BLOCKED
    monkeypatch.setenv("A11OY_M1_PROVIDER_ID", manifest["provider"]["id"])
    monkeypatch.setenv("A11OY_M1_BASE_URL", "http://127.0.0.1:9999")
    assert gate._runtime_provider(manifest)["state"] == gate.BLOCKED
    monkeypatch.delenv("A11OY_M1_BASE_URL")
    assert gate._runtime_provider(manifest)["state"] == gate.PASS

    monkeypatch.setattr(gate, "_gpu_snapshot", lambda: gate._result(
        gate.PASS, "measured", index="0", name=manifest["provider"]["expected_gpu_name"],
        total_memory_mib=8151, free_memory_mib=300, utilization_pct=100, temperature_c=64,
    ))
    admission = gate._gpu_admission(manifest)
    assert admission["state"] == gate.BLOCKED
    assert "insufficient free GPU memory" in admission["reason"]
    assert "utilization" in admission["reason"]


def test_routes_precede_catchalls_and_docker_bundles_contract_not_weights():
    ordered = [getattr(route, "path", None) for route in serve.app.router.routes]
    assert ROUTES <= set(ordered)
    proxy = ordered.index("/api/a11oy/{path:path}")
    spa = ordered.index("/{full_path:path}")
    assert all(ordered.index(route) < proxy and ordered.index(route) < spa for route in ROUTES)
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY szl_m1_model_gate.py ./" in dockerfile
    assert "COPY szl_m1_corpus_manifest.py ./" in dockerfile
    assert "COPY model_release/m1/ ./model_release/m1/" in dockerfile
    assert "web/m1-model.html" in dockerfile
    assert "adapter_model.safetensors" not in dockerfile
    source = (ROOT / "szl_m1_model_gate.py").read_text(encoding="utf-8")
    assert "local_files_only=True" in source
    assert "http://" not in source and "https://" not in source


def test_m1_page_and_status_receive_enforced_security_headers():
    for path in ("/models/m1", "/api/a11oy/v1/models/m1"):
        response = CLIENT.get(path)
        assert response.status_code == 200
        assert response.headers["x-content-type-options"] == "nosniff"
        assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
        assert response.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
        assert "frame-ancestors 'self'" in response.headers["content-security-policy"]


def test_committed_full_corpus_ledgers_are_exact_complete_and_not_promoted():
    manifest = json.loads((ROOT / "model_release" / "m1" / "operational-manifest.json").read_text(encoding="utf-8"))
    evidence = gate._corpus_evidence(manifest)
    assert evidence["state"] == gate.PASS
    coverage = evidence["coverage"]
    assert coverage["node_decisions_total"] == 9464
    assert coverage["node_decision_coverage"] == 1.0
    assert coverage["distinct_artifacts"] == 4229
    assert coverage["person_metadata"] == 5235
    assert coverage["quarantined_or_excluded_nodes"] == 9464
    assert coverage["raw_nodes_training_quarantined"] == 9464
    assert coverage["training_eligible_nodes"] == 0
    assert coverage["node_decisions"] == {"QUARANTINE": 9464}
    assert coverage["formula_records_current_versioned_sources"] == 123
    assert coverage["formula_requested_200_claim"] == "NOT_VERIFIED_BY_CURRENT_VERSIONED_SOURCES"
    assert coverage["formula_status"] == {
        "CONDITIONAL": 0, "KERNEL_ACCEPTED": 8, "OPEN": 115, "REFUTED": 0,
    }
    assert coverage["abstention_examples"] == 115
    assert coverage["negative_examples"] == 0
    assert evidence["training_state"] == "NOT_RUN"
    assert evidence["release_state"] == "NOT_PROMOTED"
    assert evidence["quality_claim"] == "NOT_ESTABLISHED"
    assert evidence["brain_ledger"]["rows"] == 9464
    assert evidence["brain_ledger"]["distinct_artifact_rows"] == 4229
    assert evidence["formula_ledger"]["rows"] == 123
