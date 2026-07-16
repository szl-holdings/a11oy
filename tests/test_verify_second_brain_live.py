from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("cryptography")

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

from scripts import verify_second_brain_live as verifier


FIXED_NOW = dt.datetime(2026, 7, 15, 12, 0, tzinfo=dt.timezone.utc)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


class FakeLiveA11oy:
    def __init__(self) -> None:
        self.private_key = ec.generate_private_key(ec.SECP256R1())
        self.public_pem = self.private_key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.fingerprint = hashlib.sha256(self.public_pem.strip()).hexdigest()
        self.keyid = self.fingerprint[:16]
        self.binding_contract = {
            "runtime_backend": {
                "forge_profiles": {
                    "profiles": {
                        "BrainNavigator-v1": {
                            "available": True,
                            "expected_model": "khipu:latest",
                            "served_model": "khipu:latest",
                        },
                        "ReceiptAgent-v1": {
                            "available": True,
                            "expected_model": "receiptagent:latest",
                            "served_model": "receiptagent:latest",
                        },
                    }
                }
            }
        }
        self.second_brain = {
            "schema": verifier.SECOND_BRAIN_SCHEMA,
            "system_id": "SZL-Khipu-Second-Brain-v1",
            "state": "READY_FOR_GROUNDED_NAVIGATION_ARTIFACT_UNBOUND",
            "ready_for_grounded_navigation": True,
            "signer_ready_this_request": True,
            "profile": {
                "expected_model": "khipu:latest",
                "served_model": "khipu:latest",
                "exact_tag_observed": True,
            },
            "memory": {
                "built": True,
                "document_count": 29,
                "chunk_count": 290,
                "node_count": 629,
                "edge_count": 670,
            },
            "training_boundary": {
                "raw_brain_nodes_observed": 9464,
                "raw_brain_nodes_admitted_to_gradients": 0,
            },
        }
        self.rag_status = {
            "built": True,
            "brain_handle_plane": {"count": 9464},
        }
        self.turns = {
            "Maskaq": self._turn(
                "Maskaq", verifier.MASKAQ_PROMPT,
                "BrainNavigator-v1", "khipu:latest", grounded=True,
            ),
            "Yupaq": self._turn(
                "Yupaq", verifier.YUPAQ_PROMPT,
                "ReceiptAgent-v1", "receiptagent:latest", grounded=False,
            ),
        }

    def _sign(self, payload: dict[str, Any]) -> dict[str, Any]:
        identity = {
            "keyid": self.keyid,
            "verify_key_url": verifier.VERIFY_KEY_PATH,
            "key_scope": "PROCESS_BOOT_EPHEMERAL",
            "key_lifetime": "UNTIL_PROCESS_RESTART",
            "key_fingerprint_sha256": self.fingerprint,
        }
        signed_payload = {**payload, "_signing_identity": identity}
        body = _canonical(signed_payload)
        pae = verifier._pae(verifier.RECEIPT_PAYLOAD_TYPE, body)
        signature = self.private_key.sign(pae, ec.ECDSA(hashes.SHA256()))
        return {
            "payloadType": verifier.RECEIPT_PAYLOAD_TYPE,
            "payload": base64.b64encode(body).decode("ascii"),
            "signatures": [{
                "keyid": self.keyid,
                "sig": base64.b64encode(signature).decode("ascii"),
            }],
            "signed": True,
            "_pae_sha256": hashlib.sha256(pae).hexdigest(),
            "verify_key_url": verifier.VERIFY_KEY_PATH,
            "key_scope": "PROCESS_BOOT_EPHEMERAL",
            "key_lifetime": "UNTIL_PROCESS_RESTART",
            "key_fingerprint_sha256": self.fingerprint,
        }

    def _turn(
        self,
        persona: str,
        prompt: str,
        profile: str,
        model: str,
        *,
        grounded: bool,
    ) -> dict[str, Any]:
        attestation = {
            "available": True,
            "expected_model": model,
            "served_model": model,
            "model_manifest_sha256": "1" * 64,
            "modelfile_sha256": "2" * 64,
            "modelfile_layer_sha256": ["3" * 64],
        }
        grounding = None
        binding_grounding = None
        if grounded:
            handles = [{
                "nodeId": "brain-node:one",
                "chunkId": "chunk-one",
                "title": "Provenance admission",
                "repo": "a11oy",
                "path": "model_release/m1/brain-ingest-ledger.jsonl",
                "corpus": "brain-handle-plane",
                "lambda": 0.9,
                "scores": {"lexical": 1.0},
                "sha256": "a" * 64,
            }]
            evidence = [{
                "node_id": "brain-node:one",
                "chunk_id": "chunk-one",
                "sha256": "a" * 64,
                "path": "model_release/m1/brain-ingest-ledger.jsonl",
                "source": "m1-ledger",
                "citation": "brain-node:one",
            }]
            cited = ["brain-node:one"]
            validation = {
                "state": "CITATIONS_WITHIN_OFFERED_HANDLES",
                "cited_node_ids": cited,
                "cited_node_ids_sha256": verifier._sha256_json(cited),
            }
            augmented = (
                prompt
                + "\n\nCANDIDATE_HANDLES_JSON (controller-provided; no node content):\n"
                + json.dumps(handles, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=False)
                + "\nReturn a retrieval plan using only offered nodeId values. "
                  "If none supports the query, return ABSTAIN with zero citations."
            )
            grounding = {
                "schema": "szl.brain.navigator-context/v1",
                "state": "GROUNDED_HANDLES_READY",
                "ready": True,
                "content_access": "HANDLES_ONLY",
                "query_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
                "handles": handles,
                "evidence": evidence,
                "evidence_set_sha256": verifier._sha256_json(evidence),
                "handles_sha256": verifier._sha256_json(handles),
                "augmented_prompt_sha256": hashlib.sha256(augmented.encode()).hexdigest(),
                "handle_evidence_set_equivalent": True,
                "grounded_count": 1,
                "citation_validation": validation,
            }
            binding_grounding = {
                "schema": grounding["schema"],
                "state": grounding["state"],
                "content_access": grounding["content_access"],
                "query_sha256": grounding["query_sha256"],
                "evidence_set_sha256": grounding["evidence_set_sha256"],
                "handles_sha256": grounding["handles_sha256"],
                "augmented_prompt_sha256": grounding["augmented_prompt_sha256"],
                "handle_evidence_set_equivalent": True,
                "citation_validation": validation,
                "rejected_model_output_sha256": None,
                "grounded_count": 1,
            }
            answer = json.dumps({
                "decision": "PLAN",
                "citedNodeIds": cited,
            }, separators=(",", ":"))
        else:
            answer = "Proposal only: verify rights, source revision, and contamination receipt."

        binding = {
            "schema": "szl.ayllu.model-family-binding/v1",
            "persona": persona,
            "family_id": "SZL-Forge-1.5B",
            "primary_profile": profile,
            "actual_model": model,
            "attested_served_model": model,
            "model_identity_reconciled": True,
            "model_attestation": attestation,
            "model_attestation_sha256": verifier._sha256_json(attestation),
            "grounding": binding_grounding,
            "grounding_sha256": (
                verifier._sha256_json(binding_grounding)
                if binding_grounding is not None else None
            ),
        }
        honesty = "answer produced by a11oy's model backend"
        turn = {
            "persona": persona,
            "answer": answer,
            "model": model,
            "stub": False,
            "timeout": False,
            "honesty": honesty,
            "model_binding": binding,
            "model_attestation": attestation,
            "grounding": grounding,
        }
        ask_id = f"ask-{persona.lower()}"
        receipt = {
            "ask_id": ask_id,
            "persona": persona,
            "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            "answer_present": True,
            "answer_sha256": hashlib.sha256(answer.encode()).hexdigest(),
            "output_sha256": hashlib.sha256(answer.encode()).hexdigest(),
            "honesty_sha256": hashlib.sha256(honesty.encode()).hexdigest(),
            "turn_output_sha256": verifier._sha256_json({
                "answer": answer,
                "honesty": honesty,
                "stub": False,
                "timeout": False,
                "model": model,
            }),
            "model": model,
            "profile_intent": profile,
            "model_binding_sha256": verifier._sha256_json(binding),
            "model_attestation_sha256": verifier._sha256_json(attestation),
            "grounding_sha256": binding["grounding_sha256"],
            "evidence_set_sha256": (
                grounding["evidence_set_sha256"] if grounding else None
            ),
            "handles_sha256": grounding["handles_sha256"] if grounding else None,
            "augmented_prompt_sha256": (
                grounding["augmented_prompt_sha256"] if grounding else None
            ),
            "citation_validation_sha256": (
                verifier._sha256_json(grounding["citation_validation"])
                if grounding else None
            ),
        }
        return {"ask_id": ask_id, "turn": turn, "receipt": self._sign(receipt)}

    def bytes(self, method: str, path: str) -> bytes:
        assert (method, path) == ("GET", verifier.VERIFY_KEY_PATH)
        return self.public_pem

    def json(self, method: str, path: str, payload: Any = None) -> dict[str, Any]:
        if (method, path) == ("GET", "/api/a11oy/v1/ayllu/second-brain"):
            return self.second_brain
        if (method, path) == ("GET", "/api/a11oy/v1/ayllu/model-binding"):
            return self.binding_contract
        if (method, path) == ("GET", "/api/a11oy/code/rag/status"):
            return self.rag_status
        if (method, path) == ("POST", "/api/a11oy/v1/ayllu/ask"):
            assert payload["prompt"] in {verifier.MASKAQ_PROMPT, verifier.YUPAQ_PROMPT}
            return self.turns[payload["persona"]]
        raise AssertionError((method, path))


def test_verifier_passes_and_writes_content_addressed_privacy_safe_summary(tmp_path: Path):
    live = FakeLiveA11oy()
    summary = verifier.verify_live(
        "http://127.0.0.1:8765", client=live, now=lambda: FIXED_NOW)
    assert summary["verification_state"] == "PASS"
    assert summary["second_brain"]["handle_plane"]["state"] == "VERIFIED"
    assert [turn["exact_served_model"] for turn in summary["turns"]] == [
        "khipu:latest", "receiptagent:latest"]
    rendered = json.dumps(summary)
    assert verifier.MASKAQ_PROMPT not in rendered
    assert verifier.YUPAQ_PROMPT not in rendered
    assert "Proposal only:" not in rendered

    target = verifier.write_content_addressed(summary, tmp_path / "proof")
    assert target.exists()
    assert target.stem.endswith(hashlib.sha256(target.read_bytes()).hexdigest())
    assert verifier.write_content_addressed(summary, tmp_path / "proof") == target


def test_unknown_maskaq_citation_fails_closed_without_artifact(tmp_path: Path):
    live = FakeLiveA11oy()
    turn = live.turns["Maskaq"]["turn"]
    answer = '{"decision":"PLAN","citedNodeIds":["not-offered"]}'
    turn["answer"] = answer
    signed_payload = json.loads(base64.b64decode(
        live.turns["Maskaq"]["receipt"]["payload"]))
    signed_payload.pop("_signing_identity")
    signed_payload["answer_sha256"] = hashlib.sha256(answer.encode()).hexdigest()
    signed_payload["output_sha256"] = hashlib.sha256(answer.encode()).hexdigest()
    signed_payload["turn_output_sha256"] = verifier._sha256_json({
        "answer": answer,
        "honesty": turn["honesty"],
        "stub": False,
        "timeout": False,
        "model": turn["model"],
    })
    live.turns["Maskaq"]["receipt"] = live._sign(signed_payload)
    with pytest.raises(verifier.VerificationError, match="unoffered"):
        summary = verifier.verify_live(
            "http://127.0.0.1:8765", client=live, now=lambda: FIXED_NOW)
        verifier.write_content_addressed(summary, tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists()


def test_signed_signer_metadata_substitution_is_rejected():
    live = FakeLiveA11oy()
    live.turns["Yupaq"]["receipt"]["key_fingerprint_sha256"] = "0" * 64
    with pytest.raises(verifier.VerificationError, match="envelope metadata mismatch"):
        verifier.verify_live(
            "http://127.0.0.1:8765", client=live, now=lambda: FIXED_NOW)


def test_cryptographic_signature_tamper_is_rejected():
    live = FakeLiveA11oy()
    receipt = live.turns["Maskaq"]["receipt"]
    signature = bytearray(base64.b64decode(receipt["signatures"][0]["sig"]))
    signature[-1] ^= 1
    receipt["signatures"][0]["sig"] = base64.b64encode(signature).decode("ascii")
    with pytest.raises(verifier.VerificationError, match="signature verification failed"):
        verifier.verify_live(
            "http://127.0.0.1:8765", client=live, now=lambda: FIXED_NOW)


def test_handle_plane_count_mismatch_is_rejected():
    live = FakeLiveA11oy()
    live.rag_status["brain_handle_plane"]["count"] = 9463
    with pytest.raises(verifier.VerificationError, match="expected 9464"):
        verifier.verify_live(
            "http://127.0.0.1:8765", client=live, now=lambda: FIXED_NOW)


def test_loopback_only_url_rejects_remote_and_embedded_credentials():
    with pytest.raises(verifier.VerificationError, match="loopback"):
        verifier.HTTPClient("https://a-11-oy.com", 1)
    with pytest.raises(verifier.VerificationError, match="credentials"):
        verifier.HTTPClient("http://user:pass@127.0.0.1:8765", 1)
    with pytest.raises(verifier.VerificationError, match="must be an origin"):
        verifier.HTTPClient("http://127.0.0.1:8765/path?token=forbidden", 1)
