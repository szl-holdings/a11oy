from __future__ import annotations

import asyncio
import base64
import hashlib
import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_ayllu
import a11oy_code_orchestrator as orchestrator
import a11oy_org_rag as rag
from ayllu import backend
from ayllu.model_binding import persona_binding


ROOT = Path(__file__).resolve().parents[1]


def test_exact_ollama_tag_attestation_binds_runtime_identity(monkeypatch):
    monkeypatch.setattr(
        orchestrator, "_serving_base",
        lambda: ("http://127.0.0.1:11434/v1", True),
    )

    def fake_json(url, *, body=None, timeout=2.0, allow_private=False):
        del timeout
        assert allow_private is True
        if url.endswith("/models"):
            return {"data": [{"id": "receiptagent:latest"}, {"id": "khipu:latest"}]}
        if url.endswith("/api/tags"):
            return {"models": [{
                "name": "khipu:latest", "digest": "e" * 64, "size": 42,
            }]}
        assert url == "http://127.0.0.1:11434/api/show" and body == {
            "model": "khipu:latest"}
        return {
            "modelfile": "FROM /models/blobs/sha256-" + "a" * 64,
            "template": "template",
            "parameters": "temperature 0",
            "system": "handles only",
            "details": {
                "format": "gguf", "family": "qwen2",
                "parameter_size": "1.5B", "quantization_level": "Q4_K_M",
            },
            "model_info": {"general.architecture": "qwen2"},
        }

    monkeypatch.setattr(orchestrator, "_endpoint_json", fake_json)
    att = orchestrator.attest_local_model("BrainNavigator-v1")
    assert att["available"] is True
    assert att["served_model"] == "khipu:latest"
    assert att["state"] == "TAG_ATTESTED_ARTIFACT_UNBOUND"
    assert att["weights_blob_sha256"] == "a" * 64
    assert att["modelfile_layer_sha256"] == ["a" * 64]
    assert att["runtime_model_digest"] == "e" * 64
    assert len(att["model_manifest_sha256"]) == 64
    assert len(att["modelfile_sha256"]) == 64
    assert len(att["model_info_sha256"]) == 64
    assert att["model_details"]["quantization_level"] == "Q4_K_M"
    unsigned = dict(att)
    digest = unsigned.pop("attestation_sha256")
    assert digest == hashlib.sha256(json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode("utf-8")).hexdigest()


def test_live_endpoint_without_exact_profile_tag_fails_closed(monkeypatch):
    monkeypatch.setattr(
        orchestrator, "_serving_base",
        lambda: ("http://127.0.0.1:11434/v1", True),
    )
    monkeypatch.setattr(
        orchestrator, "_endpoint_json",
        lambda *_args, **_kwargs: {"data": [{"id": "szl1:latest"}]},
    )
    att = orchestrator.attest_local_model("ReceiptAgent-v1")
    assert att["available"] is False
    assert att["state"] == "MODEL_TAG_MISSING"
    assert att["expected_model"] == "receiptagent:latest"


def test_profile_tag_comparison_is_case_sensitive(monkeypatch):
    monkeypatch.setattr(
        orchestrator, "_serving_base",
        lambda: ("http://127.0.0.1:11434/v1", True),
    )
    monkeypatch.setattr(
        orchestrator, "_endpoint_json",
        lambda *_args, **_kwargs: {"data": [{"id": "Khipu:latest"}]},
    )
    att = orchestrator.attest_local_model("BrainNavigator-v1")
    assert att["available"] is False
    assert att["state"] == "MODEL_TAG_MISSING"


def test_all_modelfile_layers_are_bound_not_first_regex_only(monkeypatch):
    monkeypatch.setattr(
        orchestrator, "_serving_base",
        lambda: ("http://127.0.0.1:11434/v1", True),
    )

    def fake_json(url, **_kwargs):
        if url.endswith("/models"):
            return {"data": [{"id": "khipu:latest"}]}
        if url.endswith("/api/show"):
            return {"modelfile": (
                "FROM sha256:" + "a" * 64 + "\nADAPTER sha256-" + "b" * 64)}
        return {"models": []}

    monkeypatch.setattr(orchestrator, "_endpoint_json", fake_json)
    att = orchestrator.attest_local_model("BrainNavigator-v1")
    assert att["modelfile_layer_sha256"] == ["a" * 64, "b" * 64]
    assert att["weights_blob_sha256"] is None


def test_model_probe_uses_bounded_transport_with_explicit_private_opt_in(monkeypatch):
    import szl_provider_http

    observed = {}

    def fake_http(url, **kwargs):
        observed["url"] = url
        observed.update(kwargs)
        return {"data": []}, None

    monkeypatch.setattr(szl_provider_http, "http_json", fake_http)
    assert orchestrator._endpoint_json(
        "http://127.0.0.1:11434/v1/models", allow_private=True) == {"data": []}
    assert observed["allow_private"] is True
    assert observed["max_response_bytes"] == 4 * 1024 * 1024
    assert observed["max_redirects"] == 2


def test_local_liveness_probe_uses_same_guarded_private_path(monkeypatch):
    observed = {}

    def fake_endpoint(url, **kwargs):
        observed["url"] = url
        observed.update(kwargs)
        return {"data": []}

    monkeypatch.setattr(orchestrator, "_endpoint_json", fake_endpoint)
    assert orchestrator._local_endpoint_reachable(
        "http://127.0.0.1:11434/v1") is True
    assert observed["url"].endswith("/v1/models")
    assert observed["allow_private"] is True


def test_brain_context_exposes_handles_and_digests_but_not_node_text(monkeypatch):
    monkeypatch.setattr(orchestrator, "_agent_rag_query", lambda *_args, **_kwargs: {
        "ok": True,
        "i_dont_know": False,
        "lambda_floor": 0.4,
        "dense_used": False,
        "chunks": [{
            "node_id": "node-1", "chunk_id": "chunk-1", "title": "Lambda note",
            "repo": "a11oy", "path": "proofs/lambda.md", "corpus": "proof",
            "lambda": 0.81, "scores": {"lexical": 1.0}, "sha256": "b" * 64,
            "text": "PRIVATE NODE CONTENT MUST STAY IN CONTROLLER",
            "evidence": {
                "path": "a11oy/proofs/lambda.md", "source": "gh:szl-holdings/a11oy",
                "citation": "gh:szl-holdings/a11oy/proofs/lambda.md",
            },
        }],
    })
    context = orchestrator.agent_rag_context("lambda proof")
    assert context["ready"] is True
    assert context["content_access"] == "HANDLES_ONLY"
    serialized = json.dumps(context)
    assert "PRIVATE NODE CONTENT" not in serialized
    assert context["handles"][0]["nodeId"] == "node-1"
    assert len(context["evidence_set_sha256"]) == 64


def test_brain_context_abstains_when_controller_evidence_digest_conflicts(monkeypatch):
    monkeypatch.setattr(orchestrator, "_agent_rag_query", lambda *_args, **_kwargs: {
        "ok": True,
        "i_dont_know": False,
        "evidence_set": [{"node_id": "node-1", "sha256": "a" * 64}],
        "evidence_set_sha256": "f" * 64,
        "chunks": [{
            "node_id": "node-1", "chunk_id": "chunk-1", "title": "node",
            "repo": "szl-holdings/a11oy", "path": "README.md",
            "corpus": "github", "lambda": 0.9, "sha256": "a" * 64,
        }],
    })
    context = orchestrator.agent_rag_context("verify this")
    assert context["ready"] is False
    assert context["state"] == "ABSTAIN_EVIDENCE_DIGEST_CONFLICT"
    assert context["evidence_digest_matches"] is False


def test_brain_context_requires_exact_handle_evidence_set_equivalence(monkeypatch):
    evidence_set = [{
        "rank": 1, "node_id": "different-node", "chunk_id": "chunk-1",
        "sha256": "a" * 64,
    }]
    monkeypatch.setattr(orchestrator, "_agent_rag_query", lambda *_args, **_kwargs: {
        "ok": True,
        "i_dont_know": False,
        "evidence_set": evidence_set,
        "evidence_set_sha256": hashlib.sha256(json.dumps(
            evidence_set, sort_keys=True, separators=(",", ":"),
            ensure_ascii=False).encode()).hexdigest(),
        "chunks": [{
            "node_id": "node-1", "chunk_id": "chunk-1", "title": "node",
            "repo": "a11oy", "path": "README.md", "corpus": "github",
            "lambda": 0.9, "sha256": "a" * 64,
        }],
    })
    context = orchestrator.agent_rag_context("verify this")
    assert context["ready"] is False
    assert context["evidence_digest_matches"] is True
    assert context["handle_evidence_set_equivalent"] is False
    assert context["state"] == "ABSTAIN_HANDLE_EVIDENCE_SET_MISMATCH"


def test_handle_digest_tamper_changes_grounding_and_binding_digests():
    common = {
        "schema": "szl.brain.navigator-context/v1",
        "state": "GROUNDED_HANDLES_READY",
        "content_access": "HANDLES_ONLY",
        "evidence_set_sha256": "a" * 64,
        "augmented_prompt_sha256": "b" * 64,
        "handle_evidence_set_equivalent": True,
        "grounded_count": 1,
    }
    first = persona_binding(
        "Maskaq", actual_model="khipu:latest",
        model_attestation={"served_model": "khipu:latest"},
        grounding={**common, "handles_sha256": "c" * 64},
    )
    tampered = persona_binding(
        "Maskaq", actual_model="khipu:latest",
        model_attestation={"served_model": "khipu:latest"},
        grounding={**common, "handles_sha256": "d" * 64},
    )
    assert first["model_identity_reconciled"] is True
    assert first["grounding_sha256"] != tampered["grounding_sha256"]
    assert hashlib.sha256(json.dumps(
        first, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode()).hexdigest() != hashlib.sha256(json.dumps(
        tampered, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode()).hexdigest()


def test_maskaq_routes_to_khipu_with_controller_handles(monkeypatch):
    captured = {}
    grounding = {
        "schema": "szl.brain.navigator-context/v1",
        "state": "GROUNDED_HANDLES_READY",
        "ready": True,
        "content_access": "HANDLES_ONLY",
        "handles": [{"nodeId": "node-1", "sha256": "c" * 64}],
        "evidence": [{"node_id": "node-1", "sha256": "c" * 64}],
        "evidence_set_sha256": "d" * 64,
        "grounded_count": 1,
    }
    monkeypatch.setattr(orchestrator, "agent_rag_context", lambda *_args, **_kwargs: grounding)

    async def fake_complete(messages, **kwargs):
        captured["messages"] = messages
        captured["kwargs"] = kwargs
        return {
            "text": '{"decision":"PLAN","citedNodeIds":["node-1"]}',
            "model": "khipu:latest", "stub": False,
            "model_attestation": {"state": "TAG_ATTESTED_ARTIFACT_UNBOUND"},
        }

    monkeypatch.setattr(orchestrator, "agent_model_complete", fake_complete)
    result = asyncio.run(backend.model_complete(
        "system", "find lambda", persona="Maskaq", max_tokens=64))
    assert result["model"] == "khipu:latest"
    assert result["grounding"]["evidence_set_sha256"] == "d" * 64
    assert captured["kwargs"]["local_profile"] == "BrainNavigator-v1"
    assert "node-1" in captured["messages"][1]["content"]
    assert len(result["grounding"]["augmented_prompt_sha256"]) == 64
    assert result["grounding"]["citation_validation"]["state"] == (
        "CITATIONS_WITHIN_OFFERED_HANDLES")


def test_maskaq_refuses_model_citation_outside_offered_handles(monkeypatch):
    grounding = {
        "schema": "szl.brain.navigator-context/v1",
        "state": "GROUNDED_HANDLES_READY",
        "ready": True,
        "content_access": "HANDLES_ONLY",
        "handles": [{"nodeId": "node-1", "sha256": "c" * 64}],
        "evidence": [{"node_id": "node-1", "sha256": "c" * 64}],
        "evidence_set_sha256": "d" * 64,
        "handles_sha256": "e" * 64,
        "grounded_count": 1,
    }
    monkeypatch.setattr(
        orchestrator, "agent_rag_context", lambda *_args, **_kwargs: grounding)

    async def fake_complete(*_args, **_kwargs):
        return {
            "text": '{"decision":"PLAN","citedNodeIds":["node-999"]}',
            "model": "khipu:latest", "stub": False,
            "model_attestation": {"served_model": "khipu:latest"},
        }

    monkeypatch.setattr(orchestrator, "agent_model_complete", fake_complete)
    result = asyncio.run(backend.model_complete(
        "system", "find lambda", persona="Maskaq", max_tokens=64))
    assert result["text"] is None
    assert result["stub"] is True
    assert result["grounding"]["citation_validation"]["state"] == (
        "UNKNOWN_CITATION_REFUSED")
    assert len(result["raw_model_output_sha256"]) == 64


def test_local_response_model_must_match_attested_tag_case_sensitively(monkeypatch):
    monkeypatch.setattr(orchestrator, "inference_backend_ready", lambda: True)
    monkeypatch.setattr(
        orchestrator, "_serving_base",
        lambda: ("http://127.0.0.1:11434/v1", True))
    monkeypatch.setattr(orchestrator, "route", lambda *_args, **_kwargs: {
        "model": "unused", "fallbacks": []})
    monkeypatch.setattr(orchestrator, "_get_client", lambda: object())
    monkeypatch.setattr(orchestrator, "attest_local_model", lambda *_args, **_kwargs: {
        "available": True, "served_model": "khipu:latest",
        "state": "TAG_ATTESTED_ARTIFACT_UNBOUND",
    })

    async def mismatched(*_args, **_kwargs):
        return {"choices": [{"message": {"content": "must not escape"}}]}, "Khipu:latest"

    monkeypatch.setattr(orchestrator, "_call_model_resilient", mismatched)
    monkeypatch.setattr(orchestrator, "_emit_turn_receipt", lambda *_a, **_k: None)
    result = asyncio.run(orchestrator.agent_model_complete(
        [{"role": "user", "content": "q"}], local_profile="BrainNavigator-v1"))
    assert result["text"] is None
    assert result["stub"] is True
    assert result["model_identity_state"] == "RESPONSE_TAG_MISMATCH"


def test_runtime_signed_envelope_declares_matching_key_route(monkeypatch):
    monkeypatch.setattr(a11oy_ayllu, "_dsse", None)
    raw = base64.b64encode(b"{}").decode("ascii")
    envelope = a11oy_ayllu._make_receipt(
        {"x": 1}, sign_fn=lambda _payload: {
            "payloadType": "application/vnd.szl.receipt+json",
            "payload": raw,
            "signatures": [{"sig": "AA==", "keyid": "boot"}],
            "signed": True,
        })
    assert envelope["verify_key_url"] == "/api/a11oy/cosign.pub"
    assert envelope["key_scope"] == "PROCESS_BOOT_EPHEMERAL"


def test_none_answer_is_not_hashed_as_honesty_text(monkeypatch):
    async def no_answer(*_args, **_kwargs):
        return {
            "text": None, "model": "khipu:latest", "stub": True,
            "honesty": "retrieval did not clear the evidence floor",
            "grounding": {"state": "ABSTAIN_NO_GROUNDED_HANDLES"},
        }

    monkeypatch.setattr(a11oy_ayllu._backend, "model_complete", no_answer)
    monkeypatch.setattr(a11oy_ayllu, "_make_receipt", lambda payload, sign_fn=None: payload)
    a11oy_ayllu._ASK_BUCKET._hits.clear()
    app = FastAPI()
    a11oy_ayllu.register(app, ns="a11oy")
    response = TestClient(app).post(
        "/api/a11oy/v1/ayllu/ask",
        json={"persona": "Maskaq", "prompt": "unsupported query"},
    )
    assert response.status_code == 200
    receipt = response.json()["receipt"]
    assert receipt["answer_present"] is False
    assert receipt["answer_sha256"] is None
    assert receipt["output_sha256"] is None
    assert receipt["honesty_sha256"] == hashlib.sha256(
        b"retrieval did not clear the evidence floor").hexdigest()
    assert len(receipt["turn_output_sha256"]) == 64


def test_persisted_brain_state_rehydrates_after_process_reset(monkeypatch, tmp_path):
    db_path = tmp_path / "brain.sqlite3"
    monkeypatch.setattr(rag, "RAG_DB_PATH", str(db_path))
    graph = rag.OrgGraph()
    graph.add_node("repo", "repo", repo="a11oy")
    graph.add_node("node", "file", repo="a11oy", path="README.md")
    graph.add_edge("repo", "node", "documents")
    meta = {"built": True, "mode": "seed", "ts": 1.0, "repos": 1, "chunks": 1}
    conn = rag._db()
    rag._init_schema(conn)
    rag._persist_runtime_state(conn, graph, meta)
    conn.close()

    monkeypatch.setattr(rag, "_GRAPH", rag.OrgGraph())
    monkeypatch.setattr(rag, "_BUILD_META", {"built": False})
    monkeypatch.setattr(rag, "_REHYDRATE_ATTEMPTED", False)
    status = rag.status()
    assert status["built"] is True
    assert status["rehydrated_from_sqlite"] is True
    assert rag.graph_dict()["node_count"] == 2


def test_live_verification_summary_preserves_claim_boundaries():
    report = json.loads(
        (ROOT / "attestations" / "forge-second-brain-local-2026-07-15.json")
        .read_text(encoding="utf-8")
    )
    assert report["all_checks_passed"] is True
    assert all(turn["dsse_verified"] for turn in report["turns"].values())
    assert report["claims_boundary"]["artifact_identity_bound"] is False
    assert report["claims_boundary"]["model_promoted"] is False
    assert report["claims_boundary"]["training_triggered"] is False
