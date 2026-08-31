"""Deterministic conformance tests for the ReceiptAgent runtime boundary."""

from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import importlib.util
import json
import unittest
from pathlib import Path

from tests.test_receipt_agent_release_program import validate


ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "model_release" / "receipt-agent" / "receipt_runtime.py"
SCHEMA_PATH = ROOT / "model_release" / "receipt-agent" / "receipt-agent-output.schema.json"

SPEC = importlib.util.spec_from_file_location("szl_receipt_runtime", RUNTIME_PATH)
assert SPEC and SPEC.loader
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class ReceiptAgentRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        self.draft = {
            "schema_version": "szl.forge-receipt-draft.v1",
            "status": "ANSWER_PROPOSED",
            "answer": "The admitted fixture supports this bounded answer.",
            "evidence_ids": ["fixture:eval/admitted"],
            "formula_refs": [],
            "uncertainty": {"band": "LOW", "basis": "Model draft; runtime validation required."},
            "abstention": {"required": False, "code": "NONE", "detail": "No model-side abstention."},
            "tool_proposal": {"state": "NONE", "tool_id": None, "arguments": None},
        }
        self.request = {"request_id": "req-1", "question": "What does the fixture support?"}
        self.evidence = {
            "fixture:eval/admitted": {
                "final_evidence_id": "artifact:fixture-eval-admitted",
                "content_sha256": "a" * 64,
                "support_role": "SUPPORTS",
                "admission_state": "ADMITTED_REFERENCE",
                "freshness_state": "NOT_APPLICABLE",
                "source_uri": "https://a-11-oy.com/evidence/fixture-eval-admitted",
            }
        }
        self.policy = {"policy_id": "policy:test-v1", "allowed_tool_ids": ["brain.query"]}
        self.identity = {
            "candidate_id": "SZL-Forge-1.5B-ReceiptAgent-v1",
            "release_state": "EXPERIMENTAL",
            "base_repository": "unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit",
            "base_revision": "d2f2dd02b071701d5100a04a7a49d6fb0bd305b7",
            "adapter_sha256": "b" * 64,
        }
        self.calibration = {"confidence": 0.81, "basis": "Frozen held-out calibration receipt."}
        self.receipt_key = b"0123456789abcdef0123456789abcdef"

    def _receipt(
        self,
        *,
        draft: dict[str, object] | None = None,
        policy: dict[str, object] | None = None,
        overrides: dict[str, object] | None = None,
    ) -> dict[str, object]:
        draft = draft or self.draft
        policy = policy or self.policy
        resolved = [
            {
                "evidence_id": "artifact:fixture-eval-admitted",
                "content_sha256": "a" * 64,
                "support_role": "SUPPORTS",
                "admission_state": "ADMITTED_REFERENCE",
                "source_uri": "https://a-11-oy.com/evidence/fixture-eval-admitted",
            }
        ]
        final_tool = {
            "state": draft["tool_proposal"]["state"],
            "tool_id": draft["tool_proposal"]["tool_id"],
            "arguments_sha256": (
                runtime.canonical_sha256(draft["tool_proposal"]["arguments"])
                if draft["tool_proposal"]["state"] == "PROPOSED"
                else None
            ),
            "requires_human_approval": True,
            "execution_receipt_id": None,
        }
        binding = {
            "schema_version": "szl.receipt-agent-binding.v1",
            "draft_sha256": runtime.canonical_sha256(draft),
            "answer_sha256": runtime.canonical_sha256(draft["answer"]),
            "model_identity_sha256": runtime.canonical_sha256(self.identity),
            "request_sha256": runtime.canonical_sha256(self.request),
            "evidence_set_sha256": runtime.canonical_sha256(resolved),
            "formula_set_sha256": runtime.canonical_sha256([]),
            "calibration_sha256": runtime.canonical_sha256(self.calibration),
            "tool_proposal_sha256": runtime.canonical_sha256(final_tool),
            "policy_snapshot_sha256": runtime.canonical_sha256(policy),
        }
        payload = {
            "schema_version": "szl.receipt-agent-verifier-result.v1",
            "receipt_id": "receipt:verified-test-0001",
            "nonce": "nonce-test-0000000001",
            "binding_payload_sha256": runtime.canonical_sha256(binding),
            **{key: value for key, value in binding.items() if key != "schema_version"},
        }
        if overrides:
            payload.update(overrides)
        payload_bytes = runtime.canonical_bytes(payload)
        signature = hmac.new(
            self.receipt_key,
            runtime._dsse_pae(runtime.RECEIPT_PAYLOAD_TYPE, payload_bytes),
            hashlib.sha256,
        ).digest()
        return {
            "payloadType": runtime.RECEIPT_PAYLOAD_TYPE,
            "payload": base64.b64encode(payload_bytes).decode("ascii"),
            "signatures": [
                {
                    "keyid": "test-hmac-v1",
                    "scheme": "hmac-sha256",
                    "sig": base64.b64encode(signature).decode("ascii"),
                }
            ],
        }

    def test_answer_requires_external_verified_receipt(self) -> None:
        unsigned = runtime.finalize_draft(
            self.draft,
            request=self.request,
            evidence_catalog=self.evidence,
            formula_catalog={},
            policy_snapshot=self.policy,
            model_identity=self.identity,
            calibration=self.calibration,
        )
        self.assertEqual(unsigned["status"], "ABSTAINED")
        self.assertEqual(unsigned["abstention"]["code"], "RECEIPT_INVALID")
        validate(unsigned, self.schema)

        signed = runtime.finalize_draft(
            self.draft,
            request=self.request,
            evidence_catalog=self.evidence,
            formula_catalog={},
            policy_snapshot=self.policy,
            model_identity=self.identity,
            calibration=self.calibration,
            receipt_envelope=self._receipt(),
            receipt_hmac_key=self.receipt_key,
            replay_guard=runtime.ReceiptReplayGuard(),
        )
        self.assertEqual(signed["status"], "ANSWERED")
        self.assertEqual(signed["receipt_binding"]["state"], "SIGNED")
        self.assertEqual(signed["evidence"][0]["evidence_id"], "artifact:fixture-eval-admitted")
        validate(signed, self.schema)

    def test_non_admitted_evidence_fails_closed(self) -> None:
        catalog = copy.deepcopy(self.evidence)
        catalog["fixture:eval/admitted"]["admission_state"] = "QUARANTINED"
        result = runtime.finalize_draft(
            self.draft,
            request=self.request,
            evidence_catalog=catalog,
            formula_catalog={},
            policy_snapshot=self.policy,
            model_identity=self.identity,
            calibration=self.calibration,
            receipt_envelope=self._receipt(),
            receipt_hmac_key=self.receipt_key,
            replay_guard=runtime.ReceiptReplayGuard(),
        )
        self.assertEqual(result["status"], "ABSTAINED")
        self.assertEqual(result["abstention"]["code"], "EVIDENCE_NOT_ADMITTED")
        validate(result, self.schema)

    def test_receipt_hash_mismatch_is_refused(self) -> None:
        bad = self._receipt(overrides={"policy_snapshot_sha256": "f" * 64})
        with self.assertRaises(runtime.ReceiptRuntimeError):
            runtime.finalize_draft(
                self.draft,
                request=self.request,
                evidence_catalog=self.evidence,
                formula_catalog={},
                policy_snapshot=self.policy,
                model_identity=self.identity,
                calibration=self.calibration,
                receipt_envelope=bad,
                receipt_hmac_key=self.receipt_key,
                replay_guard=runtime.ReceiptReplayGuard(),
            )

    def test_kernel_status_requires_verified_semantic_binding(self) -> None:
        draft = copy.deepcopy(self.draft)
        draft["formula_refs"] = [
            {
                "namespace": "szl:test",
                "formula_id": "F1",
                "claimed_status": "KERNEL_ACCEPTED",
            }
        ]
        catalog = {
            "szl:test::F1": {
                "status": "KERNEL_ACCEPTED",
                "formula_receipt_sha256": "c" * 64,
            }
        }
        result = runtime.finalize_draft(
            draft,
            request=self.request,
            evidence_catalog=self.evidence,
            formula_catalog=catalog,
            policy_snapshot=self.policy,
            model_identity=self.identity,
            calibration=self.calibration,
        )
        self.assertEqual(result["status"], "ABSTAINED")
        self.assertEqual(result["abstention"]["code"], "FORMULA_NAMESPACE_CONFLICT")
        validate(result, self.schema)

    def test_tool_policy_and_argument_binding_are_external(self) -> None:
        proposed = copy.deepcopy(self.draft)
        proposed["tool_proposal"] = {
            "state": "PROPOSED",
            "tool_id": "brain.query",
            "arguments": {"query": "fixture"},
        }
        denied_policy = {"policy_id": "policy:deny", "allowed_tool_ids": []}
        denied = runtime.finalize_draft(
            proposed,
            request=self.request,
            evidence_catalog=self.evidence,
            formula_catalog={},
            policy_snapshot=denied_policy,
            model_identity=self.identity,
            calibration=self.calibration,
        )
        self.assertEqual(denied["abstention"]["code"], "POLICY_DENIED")

        allowed = runtime.finalize_draft(
            proposed,
            request=self.request,
            evidence_catalog=self.evidence,
            formula_catalog={},
            policy_snapshot=self.policy,
            model_identity=self.identity,
            calibration=self.calibration,
            receipt_envelope=self._receipt(draft=proposed),
            receipt_hmac_key=self.receipt_key,
            replay_guard=runtime.ReceiptReplayGuard(),
        )
        self.assertEqual(allowed["tool_proposal"]["state"], "PROPOSED")
        self.assertEqual(
            allowed["tool_proposal"]["arguments_sha256"],
            runtime.canonical_sha256({"query": "fixture"}),
        )
        self.assertIsNone(allowed["tool_proposal"]["execution_receipt_id"])
        validate(allowed, self.schema)

    def test_finalization_is_deterministic(self) -> None:
        common = dict(
            request=self.request,
            evidence_catalog=self.evidence,
            formula_catalog={},
            policy_snapshot=self.policy,
            model_identity=self.identity,
            calibration=self.calibration,
            receipt_envelope=self._receipt(),
            receipt_hmac_key=self.receipt_key,
        )
        first = runtime.finalize_draft(self.draft, **common, replay_guard=runtime.ReceiptReplayGuard())
        second = runtime.finalize_draft(self.draft, **common, replay_guard=runtime.ReceiptReplayGuard())
        self.assertEqual(first, second)

    def test_receipt_is_single_use_and_binds_draft_model_formula_calibration_and_tool(self) -> None:
        envelope = self._receipt()
        guard = runtime.ReceiptReplayGuard()
        runtime.finalize_draft(
            self.draft,
            request=self.request,
            evidence_catalog=self.evidence,
            formula_catalog={},
            policy_snapshot=self.policy,
            model_identity=self.identity,
            calibration=self.calibration,
            receipt_envelope=envelope,
            receipt_hmac_key=self.receipt_key,
            replay_guard=guard,
        )
        with self.assertRaises(runtime.ReceiptRuntimeError):
            runtime.finalize_draft(
                self.draft,
                request=self.request,
                evidence_catalog=self.evidence,
                formula_catalog={},
                policy_snapshot=self.policy,
                model_identity=self.identity,
                calibration=self.calibration,
                receipt_envelope=envelope,
                receipt_hmac_key=self.receipt_key,
                replay_guard=guard,
            )

        changed = copy.deepcopy(self.draft)
        changed["answer"] = "A swapped answer."
        with self.assertRaises(runtime.ReceiptRuntimeError):
            runtime.finalize_draft(
                changed,
                request=self.request,
                evidence_catalog=self.evidence,
                formula_catalog={},
                policy_snapshot=self.policy,
                model_identity=self.identity,
                calibration=self.calibration,
                receipt_envelope=envelope,
                receipt_hmac_key=self.receipt_key,
                replay_guard=runtime.ReceiptReplayGuard(),
            )


if __name__ == "__main__":
    unittest.main()
