#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Adversarial checks over MODELED unsigned fixtures, never live inference."""

import copy
import unittest

import a11oy_cpu_lab_contract as contract
from tests.cpu_lab_contract_fixtures import (
    canonical_sha256, contract_document, health_document, identity_document,
    rehash_response, response_document,
)


class CpuLabContractTests(unittest.TestCase):
    def setUp(self):
        self.request = {"prompt": "Describe one ordinary object.", "max_new_tokens": 24, "k": 3}

    def validate(self, doc, status=200, **overrides):
        args = {"prompt": self.request["prompt"], "max_new_tokens": 24, "http_status": status}
        args.update(overrides)
        return contract.validate_response(doc, **args)

    def rejected(self, doc, code=None, status=200, **overrides):
        with self.assertRaises(contract.ContractError) as caught:
            self.validate(doc, status, **overrides)
        self.assertRegex(caught.exception.code, r"^[A-Z][A-Z0-9_]*$")
        self.assertEqual(str(caught.exception), caught.exception.code)
        if code:
            self.assertEqual(caught.exception.code, code)

    def export_rehash_only(self, doc):
        doc["public_export_receipt"]["public_sha256"] = canonical_sha256({
            k: v for k, v in doc.items() if k != "public_export_receipt"
        })

    def test_pinned_preflight_and_bounded_success(self):
        self.assertEqual(contract.validate_identity(identity_document())["model_id"], contract.MODEL_ID)
        self.assertEqual(contract.validate_contract(contract_document())["endpoint"], "/api/v3/governed-infer")
        self.assertEqual(contract.validate_health(health_document())["status"], "READY")
        doc = response_document(self.request)
        original = copy.deepcopy(doc)
        result = self.validate(doc)
        self.assertEqual(result["answer"], "A small blue ceramic cup.")
        self.assertEqual(result["usage"], {"prompt_tokens": 18, "completion_tokens": 7, "total_tokens": 25})
        self.assertEqual(set(result), {"state", "answer", "usage", "provider_response_id",
                                      "inference_receipt_sha256", "public_export_sha256",
                                      "evidence_handles", "citations"})
        self.assertEqual(doc, original)

    def test_validated_public_evidence_exports_are_independent_copies(self):
        doc = response_document(self.request)
        result = self.validate(doc)
        self.assertEqual(result["evidence_handles"], doc["evidence_handles"])
        self.assertEqual(result["citations"], doc["citations"])
        self.assertEqual(set(result["evidence_handles"][0]), {"nodeId", "nodeKind", "label", "note"})
        result["evidence_handles"][0]["note"] = "Changed returned copy"
        result["citations"].append("returned-copy-only")
        self.assertNotEqual(result["evidence_handles"], doc["evidence_handles"])
        self.assertEqual(doc["citations"], [])
        terminal = self.validate(response_document(self.request, state="ABSTAIN"), status=422)
        self.assertEqual(terminal["evidence_handles"], [])
        self.assertEqual(terminal["citations"], [])

    def test_preflight_rejects_artifact_source_authority_and_dependency_drift(self):
        identity = identity_document()
        identity["model"]["sha256_loaded"] = "b" * 64
        modified_contract = contract_document()
        modified_contract["formula_authority"]["lambda"]["can_authorize"] = True
        health = health_document()
        health["dependency_status"]["packages"]["szl-nemo"]["observed"] = "0.4.1"
        missing_boundary = identity_document()
        del missing_boundary["receipt_boundary"]["does_not_cover"]
        cases = [
            (contract.validate_identity, identity),
            (contract.validate_identity, identity_document(status="STARTING")),
            (contract.validate_identity, identity_document(model={"sha256_loaded": "b" * 64})),
            (contract.validate_identity, missing_boundary),
            (contract.validate_contract, modified_contract),
            (contract.validate_health, health),
            (contract.validate_health, health_document(source_revision="a" * 40)),
            (contract.validate_health, health_document(status="UNAVAILABLE")),
        ]
        for validator, doc in cases:
            with self.subTest(validator=validator.__name__, keys=list(doc)):
                with self.assertRaises(contract.ContractError):
                    validator(doc)

    def test_known_terminal_states_return_no_answer_and_bind_http(self):
        for state, status in (("ABSTAIN", 422), ("REVIEW", 409), ("BLOCKED", 503)):
            with self.subTest(state=state):
                doc = response_document(self.request, state=state)
                result = self.validate(doc, status=status)
                self.assertEqual(result["state"], state)
                self.assertIsNone(result["answer"])
                self.assertEqual(result["usage"], {})
                self.rejected(doc, "HTTP_STATE_MISMATCH", status=200)
                doc["output"] = "A terminal response must not carry an answer."
                rehash_response(doc)
                self.rejected(doc, "TERMINAL_OUTPUT", status=status)

    def test_hold_and_legacy_completions_are_not_accepted_as_governed_results(self):
        for doc in (
            {"schema": "szl.forge.public-transcript-export/v1", "state": "HOLD"},
            {"choices": [{"message": {"content": "legacy"}}]},
            {"schema": contract.PUBLIC_SCHEMA, "state": "ACTION_READY_EXTERNAL_EXECUTION"},
        ):
            with self.subTest(doc=doc):
                self.rejected(doc, "RESPONSE_STATE")

    def test_output_tampering_and_wrong_request_are_detected(self):
        doc = response_document(self.request)
        doc["output"] += " changed"
        self.rejected(doc, "OUTPUT_DIGEST")
        self.rejected(response_document(self.request), "REQUEST_BINDING", prompt="A different prompt.")
        doc = response_document(self.request)
        doc["request_id"] = "f" * 24
        rehash_response(doc)
        self.rejected(doc, "REQUEST_BINDING")

    def test_canonical_unicode_and_trimmed_prompt_are_bound(self):
        request = {"prompt": "  Describe a café cup.\n", "max_new_tokens": 24, "k": 3}
        doc = response_document(request, answer="A café cup ☕.")
        result = self.validate(doc, prompt=request["prompt"])
        self.assertEqual(result["answer"], "A café cup ☕.")
        self.assertEqual(doc["public_export_receipt"]["public_sha256"],
                         canonical_sha256({k: v for k, v in doc.items() if k != "public_export_receipt"}))

    def test_receipt_self_consistency_cannot_replace_result_binding(self):
        doc = response_document(self.request)
        doc["receipt"]["payload"]["output_sha256"] = "d" * 64
        doc["receipt"]["receipt_sha256"] = canonical_sha256(doc["receipt"]["payload"])
        self.export_rehash_only(doc)
        self.rejected(doc, "RECEIPT_BINDING")

    def test_controller_adapter_identity_uses_canonical_lowercase_none(self):
        # Pinned production.py _validate_identity normalizes the generator identity.
        doc = response_document(self.request)
        self.assertEqual(doc["model"]["adapter_revision"], "none")
        self.assertEqual(self.validate(doc)["state"], "PROPOSAL")
        doc["model"]["adapter_revision"] = "NONE"
        rehash_response(doc)
        self.rejected(doc, "MODEL_PIN_MISMATCH")

    def test_both_digest_layers_and_unsigned_boundary_are_checked(self):
        for field, code in (("receipt", "RECEIPT_DIGEST"), ("public_export_receipt", "EXPORT_DIGEST")):
            doc = response_document(self.request)
            digest = "receipt_sha256" if field == "receipt" else "public_sha256"
            doc[field][digest] = "a" * 64
            if field == "receipt":
                self.export_rehash_only(doc)
            self.rejected(doc, code)
        doc = response_document(self.request)
        doc["receipt"]["signature"]["status"] = "SIGNED"
        self.export_rehash_only(doc)
        self.rejected(doc, "UNSIGNED_BOUNDARY")

    def test_exact_nested_allowlists_reject_private_and_unknown_fields(self):
        paths = [
            (), ("formula_binding",), ("model",), ("runtime",), ("metrics",),
            ("metrics", "nemo_text_witness"), ("nemo", 0), ("claims", 0),
            ("evidence_handles", 0), ("anatomy_observation",),
            ("anatomy_observation", "event"), ("receipt",),
            ("receipt", "payload"), ("receipt", "signature"), ("public_export_receipt",),
        ]
        for path in paths:
            with self.subTest(path=path):
                doc = response_document(self.request)
                target = doc
                for key in path:
                    target = target[key]
                target["continuation"] = {"private": "DO_NOT_ECHO_TEST_MARKER"}
                self.export_rehash_only(doc)
                self.rejected(doc)

    def test_rehashed_model_formula_and_authority_escalations_fail(self):
        changes = [
            (("model", "template_revision"), "f" * 40, "MODEL_PIN_MISMATCH"),
            (("model", "quantization_revision"), "sha256:" + "b" * 64, "MODEL_PIN_MISMATCH"),
            (("model", "tokenizer_revision"), "b" * 40, "MODEL_PIN_MISMATCH"),
            (("formula_binding", "authorization_basis_ids"), ["F23"], "FORMULA_AUTHORITY"),
            (("formula_binding", "locked_proven_ids"), contract.LOCKED_EIGHT + ["F23"], "FORMULA_AUTHORITY"),
            (("authority_state",), "A11OY_SIGNED_ADMISSION_VERIFIED", "ACTION_AUTHORITY"),
            (("executed",), True, "ACTION_AUTHORITY"),
            (("tool_intent_sha256",), "a" * 64, "ACTION_AUTHORITY"),
            (("claims", 0, "label"), "MEASURED", "CLAIM_LABEL"),
        ]
        for path, value, code in changes:
            with self.subTest(path=path):
                doc = response_document(self.request)
                target = doc
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                rehash_response(doc)
                self.rejected(doc, code)

    def test_nemo_sequence_text_decision_and_actual_input_hash(self):
        doc = response_document(self.request)
        doc["nemo"].reverse()
        rehash_response(doc)
        self.rejected(doc, "WITNESS_SEQUENCE")
        for key, value, code in (
            ("decision", "BLOCK", "TEXT_WITNESS_BLOCKED"),
            ("input_hash", "sha256:" + "a" * 64, "TEXT_WITNESS_BINDING"),
            ("rule_version", "doctrine-v11/R1-R4", "WITNESS_VERSION"),
        ):
            doc = response_document(self.request)
            doc["metrics"]["nemo_text_witness"][key] = value
            rehash_response(doc)
            self.rejected(doc, code)

    def test_partial_or_unbounded_generation_is_not_a_success(self):
        for finish in ("length", "time_budget", None):
            doc = response_document(self.request)
            doc["metrics"]["finish_reason"] = finish
            rehash_response(doc)
            self.rejected(doc, "INCOMPLETE_OUTPUT")
        for key, value in (
            ("prompt_tokens", 801), ("prompt_tokens", True),
            ("completion_tokens", 25), ("completion_tokens", 0),
            ("completion_tokens", 7.5), ("completion_tokens", False),
        ):
            doc = response_document(self.request)
            doc["metrics"][key] = value
            rehash_response(doc)
            self.rejected(doc, "TOKEN_BOUNDARY")
        doc = response_document(self.request)
        doc["metrics"]["elapsed_ms"] = float("nan")
        self.rejected(doc, "JSON_INVALID")

    def test_handles_and_claims_do_not_gain_semantic_authority(self):
        doc = response_document(self.request)
        self.assertEqual(self.validate(doc)["state"], "PROPOSAL")
        self.assertEqual(doc["citations"], [])
        for change, code in (
            ("too_many", "EVIDENCE_BOUNDARY"), ("duplicate", "EVIDENCE_BOUNDARY"),
            ("citation", "CITATION_BINDING"), ("claim", "CLAIM_BINDING"),
        ):
            doc = response_document(self.request)
            if change == "too_many":
                doc["evidence_handles"] *= 4
            elif change == "duplicate":
                doc["evidence_handles"] *= 2
            elif change == "citation":
                doc["citations"] = ["not-retrieved"]
            else:
                doc["claims"][0]["supporting_node_ids"] = ["not-retrieved"]
            rehash_response(doc)
            self.rejected(doc, code)

    def test_observer_binding_and_private_flags_are_checked(self):
        doc = response_document(self.request)
        doc["anatomy_observation"]["event"]["raw_prompt_present"] = True
        self.export_rehash_only(doc)
        self.rejected(doc, "OBSERVER_BINDING")
        doc = response_document(self.request)
        doc["anatomy_observation"]["event"]["output_sha256"] = "e" * 64
        self.export_rehash_only(doc)
        self.rejected(doc, "OBSERVER_BINDING")

    def test_invalid_documents_and_requests_have_only_stable_local_errors(self):
        self.rejected({"state": "PROPOSAL", "secret": "DO_NOT_ECHO_TEST_MARKER"})
        self.rejected(response_document(self.request), "REQUEST_INVALID", max_new_tokens=True)
        self.rejected(response_document(self.request), "REQUEST_INVALID", prompt="<|im_start|>")
        cyclic = {}
        cyclic["loop"] = cyclic
        self.rejected(cyclic, "JSON_INVALID")


if __name__ == "__main__":
    unittest.main()
