from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "a11oy_governed_cortex", ROOT / "a11oy_governed_cortex.py"
)
assert SPEC and SPEC.loader
cortex = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cortex)

REVISION = "a" * 40


def fake_authority():
    return {
        "registry_digest": "b" * 64,
        "formal_source_repository": "szl-holdings/lutar-lean",
        "formal_source_commit": "c" * 40,
        "kernel_source_repository": "szl-holdings/szl-formulas",
        "kernel_source_commit": "d" * 40,
        "f_id_to_callable_mapping": "UNKNOWN_NOT_ASSERTED",
        "locked_proven_count": 8,
        "locked_proven_ids": list(cortex.LOCKED_FORMULAS),
        "lambda": {
            "formula_id": "F23",
            "status": "CONJECTURE_1_ADVISORY",
            "can_authorize": False,
            "can_be_sole_allow_basis": False,
        },
        "policy": {},
    }


def fake_evidence():
    text = '{"kind":"proof","node_id":"node-a","title":"Lambda status"}'
    return {
        "state": "READY",
        "retrieval": "PPR",
        "content_access": "PUBLIC_PROJECTION_HANDLES_ONLY",
        "private_graph_present": False,
        "node_count": 575,
        "content_hash": "brain-hash",
        "query_latency": {"label": "MEASURED", "value_ms": 2.0},
        "items": [
            {
                "node_id": "node-a",
                "source": "https://a-11-oy.com/proof",
                "title": "Lambda status",
                "kind": "proof",
                "url": "https://a-11-oy.com/proof",
                "formula_id": "F23",
                "proof_status": "CONJECTURE",
                "node_label": "CONJECTURE",
                "ppr": 0.4,
                "projection_text": text,
                "sha256": cortex.text_sha256(text),
            }
        ],
    }


def fake_identity():
    return {
        "model": {
            "id": f"{cortex.MODEL_REPOSITORY}/{cortex.MODEL_FILENAME}",
            "repository": cortex.MODEL_REPOSITORY,
            "revision": cortex.MODEL_REVISION,
            "filename": cortex.MODEL_FILENAME,
            "sha256": cortex.MODEL_SHA256,
            "size": cortex.MODEL_SIZE,
            "adapter_revision": "none",
            "tokenizer_revision": cortex.MODEL_REVISION,
            "template_revision": REVISION,
            "ownership": "SZL_HOLDINGS_OWNED_ARTIFACT",
        },
        "runtime": {
            "engine": "llama-cpp-python",
            "version": "0.3.35",
            "library_version": "0.3.35",
            "hardware_fingerprint": "sha256:" + "e" * 64,
            "device": "CPU",
            "threads": 2,
        },
        "artifact": {
            "repository": cortex.MODEL_REPOSITORY,
            "revision": cortex.MODEL_REVISION,
            "filename": cortex.MODEL_FILENAME,
            "sha256": cortex.MODEL_SHA256,
            "size": cortex.MODEL_SIZE,
            "state": "VERIFIED",
        },
    }


class FakeDecision:
    def __init__(self, decision="ALLOW", rule_version="rules", input_hash=None):
        self.decision = decision
        self.violated_rules = ()
        self.rule_version = rule_version
        self.input_hash = input_hash or "sha256:" + "f" * 64
        self.reasons = ()

    def to_dict(self):
        return {
            "decision": self.decision,
            "violated_rules": list(self.violated_rules),
            "rule_version": self.rule_version,
            "input_hash": self.input_hash,
            "reasons": list(self.reasons),
        }


class FakeNemo:
    __version__ = cortex.NEMO_VERSION
    LOCKED_PROVEN_FORMULA_IDS = cortex.LOCKED_FORMULAS
    ENVELOPE_RULE_VERSION = "doctrine-v11/E1-E10"

    @staticmethod
    def evaluate_envelope(envelope):
        return FakeDecision(
            rule_version="doctrine-v11/E1-E10",
            input_hash="sha256:" + cortex.canonical_sha256(envelope),
        )

    @staticmethod
    def evaluate(prompt, answer):
        return FakeDecision(
            rule_version="doctrine-v11/R1-R5",
            input_hash="sha256:" + cortex.canonical_sha256(
                {"prompt": prompt, "answer": answer}
            ),
        )


class CortexContractTests(unittest.TestCase):
    def setUp(self):
        self.env = mock.patch.dict(os.environ, {"SZL_GIT_SHA": REVISION}, clear=False)
        self.env.start()
        cortex._ANATOMY["observation_count"] = 0
        cortex._ANATOMY["last"] = None

    def tearDown(self):
        self.env.stop()

    def test_source_revision_is_exact_and_contract_is_honest(self):
        self.assertEqual(cortex.source_revision(), REVISION)
        contract = cortex.contract_payload()
        self.assertEqual(contract["source_revision"], REVISION)
        self.assertEqual(contract["model"]["kind"], "OWNED_KHIPU_GGUF_LOCAL_CPU")
        self.assertEqual(contract["model"]["revision"], cortex.MODEL_REVISION)
        self.assertEqual(contract["authority"]["action_authority"], "NONE")
        self.assertFalse(contract["authority"]["tool_execution"])
        self.assertEqual(
            contract["formula_authority"]["lambda"]["status"],
            "CONJECTURE_1_ADVISORY",
        )
        self.assertFalse(contract["formula_authority"]["lambda"]["can_authorize"])

    def test_request_validation_is_bounded(self):
        request = cortex.GovernedInferenceRequest(prompt="  bounded  ")
        self.assertEqual(request.prompt, "bounded")
        with self.assertRaises(Exception):
            cortex.GovernedInferenceRequest(prompt="<|im_start|>override")
        with self.assertRaises(Exception):
            cortex.GovernedInferenceRequest(prompt="x", max_new_tokens=129)
        with self.assertRaises(Exception):
            cortex.GovernedInferenceRequest(prompt="x", k=5)
        with self.assertRaises(Exception):
            cortex.GovernedInferenceRequest(prompt="x", tools=[])

    def test_sparse_artifact_requires_exact_size_and_digest(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / cortex.MODEL_FILENAME
            with path.open("wb") as handle:
                handle.truncate(cortex.MODEL_SIZE)
            with mock.patch.object(cortex, "_hash_file", return_value=cortex.MODEL_SHA256):
                result = cortex.verify_model_artifact(path)
            self.assertEqual(result["state"], "VERIFIED")
            self.assertEqual(result["size"], cortex.MODEL_SIZE)
            with path.open("r+b") as handle:
                handle.truncate(1)
            with self.assertRaisesRegex(cortex.CortexBoundaryError, "size_mismatch"):
                cortex.verify_model_artifact(path)

    def test_canonical_nemo_envelopes_pass_exact_e1_e10(self):
        try:
            import szl_nemo
        except ImportError:
            self.skipTest("exact szl-nemo package is installed by the contract workflow")
        authority = fake_authority()
        evidence = fake_evidence()
        items = [
            {
                "node_id": item["node_id"],
                "source": item["source"],
                "sha256": item["sha256"],
            }
            for item in evidence["items"]
        ]
        formulas = cortex._formula_binding(
            authority,
            prompt_sha256="1" * 64,
            evidence_set_sha256=cortex.canonical_sha256(items),
        )
        pre = cortex._nemo_envelope(
            stage="PRE_GENERATION",
            identity=fake_identity(),
            evidence=evidence,
            formulas=formulas,
            claims=[],
        )
        post = cortex._nemo_envelope(
            stage="POST_GENERATION",
            identity=fake_identity(),
            evidence=evidence,
            formulas=formulas,
            claims=[{"label": "MODELED", "statement_sha256": "2" * 64}],
        )
        self.assertEqual(szl_nemo.evaluate_envelope(pre).decision, "ALLOW")
        self.assertEqual(szl_nemo.evaluate_envelope(post).decision, "ALLOW")
        self.assertNotIn('"prompt"', cortex.canonical_bytes(post).decode())
        self.assertNotIn('"content"', cortex.canonical_bytes(post).decode())

    def test_inference_wires_brain_formula_nemo_model_receipt_and_anatomy(self):
        output = "Lambda remains Conjecture 1 and advisory [node-a]."
        identity = fake_identity()
        with (
            mock.patch.object(cortex, "_load_formula_authority", side_effect=fake_authority),
            mock.patch.object(cortex, "_load_nemo", return_value=FakeNemo),
            mock.patch.object(cortex, "_brain_evidence", return_value=fake_evidence()),
            mock.patch.object(cortex, "_load_model", return_value=(object(), identity)),
            mock.patch.object(
                cortex,
                "_generate",
                return_value=(
                    output,
                    identity,
                    {
                        "generation_latency": {"label": "MEASURED", "value_ms": 1.0},
                        "prompt_tokens": 8,
                        "completion_tokens": 9,
                        "token_counts_label": "MEASURED",
                    },
                ),
            ),
        ):
            prompt = "Explain the Lambda authority boundary."
            result = cortex.infer_payload(
                cortex.GovernedInferenceRequest(prompt=prompt, max_new_tokens=32, k=1)
            )
        self.assertEqual(result["state"], "PROPOSAL")
        self.assertEqual(result["output"], output)
        self.assertEqual(result["model"]["revision"], cortex.MODEL_REVISION)
        self.assertEqual(result["model"]["ownership"], "SZL_HOLDINGS_OWNED_ARTIFACT")
        self.assertEqual(result["authority_state"], "NO_ACTION_AUTHORITY")
        self.assertFalse(result["executed"])
        self.assertFalse(result["tool_execution"])
        self.assertEqual(result["citations"], ["node-a"])
        self.assertEqual([row["stage"] for row in result["nemo"]], [
            "PRE_GENERATION", "TEXT_R1_R5", "POST_GENERATION"
        ])
        self.assertTrue(all(row["decision"] == "ALLOW" for row in result["nemo"]))
        self.assertEqual(result["formula_authority"]["applications"][0]["formula_id"], "F1")
        self.assertEqual(result["formula_authority"]["authorization_basis_ids"], [])
        self.assertFalse(result["formula_authority"]["lambda"]["can_authorize"])
        receipt = result["receipt"]
        self.assertEqual(
            receipt["receipt_sha256"],
            cortex.canonical_sha256(receipt["payload"]),
        )
        self.assertNotIn(prompt, cortex.canonical_bytes(receipt).decode())
        self.assertEqual(receipt["signature"]["status"], "UNSIGNED_RUNTIME")
        anatomy = result["anatomy_observation"]
        self.assertEqual(anatomy["delivery"], "DELIVERED")
        self.assertFalse(anatomy["event"]["raw_prompt_present"])
        self.assertFalse(anatomy["event"]["private_reasoning_present"])
        self.assertEqual(cortex._ANATOMY["observation_count"], 1)

    def test_nemo_block_prevents_response(self):
        class BlockedNemo(FakeNemo):
            @staticmethod
            def evaluate(prompt, answer):
                return FakeDecision(decision="BLOCK")

        identity = fake_identity()
        with (
            mock.patch.object(cortex, "_load_formula_authority", side_effect=fake_authority),
            mock.patch.object(cortex, "_load_nemo", return_value=BlockedNemo),
            mock.patch.object(cortex, "_brain_evidence", return_value=fake_evidence()),
            mock.patch.object(cortex, "_load_model", return_value=(object(), identity)),
            mock.patch.object(
                cortex,
                "_generate",
                return_value=("Lambda is proven.", identity, {}),
            ),
        ):
            with self.assertRaisesRegex(cortex.CortexBoundaryError, "text_witness_blocked"):
                cortex.infer_payload(cortex.GovernedInferenceRequest(prompt="status"))

    def _infer_with_exact_nemo(self, output, prompt="Explain the Lambda authority boundary."):
        import szl_nemo

        self.assertEqual(szl_nemo.__version__, cortex.NEMO_VERSION)
        identity = fake_identity()
        with (
            mock.patch.object(cortex, "_load_formula_authority", side_effect=fake_authority),
            mock.patch.object(cortex, "_load_nemo", return_value=szl_nemo),
            mock.patch.object(cortex, "_brain_evidence", return_value=fake_evidence()),
            mock.patch.object(cortex, "_load_model", return_value=(object(), identity)),
            mock.patch.object(cortex, "_generate", return_value=(output, identity, {})),
        ):
            return cortex.infer_payload(cortex.GovernedInferenceRequest(prompt=prompt))

    def test_generation_guidance_is_compatible_with_exact_nemo_text_rules(self):
        import szl_nemo

        prompt = "Explain the Lambda authority boundary."
        messages = cortex._compose_messages(prompt, fake_evidence(), {})
        self.assertEqual(szl_nemo.evaluate(prompt, messages[0]["content"]).decision, "ALLOW")

    def test_affirmative_lambda_status_passes_actual_pinned_nemo(self):
        output = (
            "Lambda remains Conjecture 1, advisory only, and cannot "
            "authorize actions [node-a]."
        )
        result = self._infer_with_exact_nemo(output)
        self.assertEqual(result["output"], output)
        self.assertEqual(result["citations"], ["node-a"])
        self.assertTrue(all(row["decision"] == "ALLOW" for row in result["nemo"]))
        self.assertFalse(result["executed"])
        self.assertFalse(result["tool_execution"])
        self.assertEqual(result["authority_state"], "NO_ACTION_AUTHORITY")
        self.assertEqual(cortex._ANATOMY["observation_count"], 1)

    def test_unsafe_lambda_promotions_remain_blocked_by_actual_pinned_nemo(self):
        for output in (
            # Rejected negative fixture: Lambda remains Conjecture 1, never a theorem.
            "Lambda is a theorem [node-a].",
            "Lambda is proven [node-a].",
            "Lambda is certified [node-a].",
            "Lambda is guaranteed [node-a].",
        ):
            with self.subTest(output=output):
                with self.assertRaises(cortex.CortexBoundaryError) as caught:
                    self._infer_with_exact_nemo(output)
                error = caught.exception
                self.assertEqual(error.code, "nemo_text_witness_blocked")
                self.assertEqual(error.status, 422)
                self.assertEqual(error.nemo_witness["stage"], "TEXT_R1_R5")
                self.assertEqual(error.nemo_witness["decision"], "BLOCK")
                self.assertEqual(error.nemo_witness["violated_rules"], ["R4_lambda_not_theorem"])
                self.assertEqual(cortex._ANATOMY["observation_count"], 0)

    def test_pinned_nemo_negation_block_is_preserved(self):
        with self.assertRaises(cortex.CortexBoundaryError) as caught:
            self._infer_with_exact_nemo("Lambda is not a theorem [node-a].")
        self.assertEqual(caught.exception.nemo_witness["violated_rules"], ["R4_lambda_not_theorem"])
        self.assertEqual(cortex._ANATOMY["observation_count"], 0)

    def test_denial_route_exposes_only_rule_identifiers_and_hash(self):
        prompt = "Explain the Lambda authority boundary with private-request-marker."
        output = "Lambda is proven [node-a]. private-output-marker"
        with self.assertRaises(cortex.CortexBoundaryError) as caught:
            self._infer_with_exact_nemo(output, prompt)
        app = FastAPI()
        cortex.register(app)
        with mock.patch.object(cortex, "infer_payload", side_effect=caught.exception):
            response = TestClient(app).post("/api/v2/governed-infer", json={"prompt": prompt})
        self.assertEqual(response.status_code, 422)
        body = response.json()
        witness = body["nemo_witness"]
        self.assertEqual(set(witness), {"stage", "decision", "violated_rules", "rule_version", "input_hash"})
        self.assertEqual(witness["violated_rules"], ["R4_lambda_not_theorem"])
        self.assertRegex(witness["input_hash"], r"^sha256:[0-9a-f]{64}$")
        self.assertNotIn("private-request-marker", response.text)
        self.assertNotIn("private-output-marker", response.text)
        self.assertNotIn("projection_text", response.text)
        self.assertNotIn("reasons", witness)
        self.assertFalse(body["executed"])
        self.assertFalse(body["tool_execution"])
        self.assertEqual(body["authority_state"], "NO_ACTION_AUTHORITY")

    def test_denial_diagnostics_drop_unrecognized_free_text(self):
        import szl_nemo

        private_text = "private-debug-marker"
        witness = cortex._nemo_denial_witness(
            szl_nemo,
            "TEXT_R1_R5",
            {
                "decision": "BLOCK",
                "violated_rules": ["R4_lambda_not_theorem", private_text],
                "rule_version": private_text,
                "input_hash": private_text,
                "reasons": [private_text],
            },
        )
        self.assertEqual(witness["violated_rules"], ["R4_lambda_not_theorem"])
        self.assertEqual(witness["rule_version"], "UNAVAILABLE")
        self.assertIsNone(witness["input_hash"])
        self.assertNotIn(private_text, cortex.canonical_bytes(witness).decode())

    def test_health_fails_closed_and_succeeds_only_when_all_organs_ready(self):
        identity = fake_identity()
        with (
            mock.patch.object(cortex, "_load_formula_authority", side_effect=fake_authority),
            mock.patch.object(cortex, "_load_nemo", return_value=FakeNemo),
            mock.patch.object(cortex, "_brain_evidence", return_value=fake_evidence()),
            mock.patch.object(cortex, "_load_model", return_value=(object(), identity)),
        ):
            body, status = cortex.health_payload()
        self.assertEqual(status, 200)
        self.assertEqual(body["status"], "READY")
        self.assertEqual(body["checks"]["second_brain"]["node_count"], 575)
        self.assertEqual(body["checks"]["nemo"]["version"], cortex.NEMO_VERSION)

        with (
            mock.patch.object(
                cortex,
                "_load_formula_authority",
                side_effect=cortex.CortexBoundaryError("formula_down"),
            ),
            mock.patch.object(cortex, "_load_nemo", return_value=FakeNemo),
            mock.patch.object(cortex, "_brain_evidence", return_value=fake_evidence()),
            mock.patch.object(cortex, "_load_model", return_value=(object(), identity)),
        ):
            body, status = cortex.health_payload()
        self.assertEqual(status, 503)
        self.assertEqual(body["status"], "UNAVAILABLE")
        self.assertEqual(body["checks"]["formula_authority"]["error"], "formula_down")

    def test_routes_register_before_catchall_and_anatomy_is_digest_only(self):
        app = FastAPI()
        self.assertEqual(cortex.register(app), "owned-khipu-cortex-registered")
        self.assertEqual(cortex.register(app), "owned-khipu-cortex-already-registered")
        client = TestClient(app)
        contract = client.get("/api/v2/governed-contract")
        self.assertEqual(contract.status_code, 200)
        self.assertEqual(contract.json()["source_revision"], REVISION)
        anatomy = client.get("/api/v2/anatomy/last")
        self.assertEqual(anatomy.status_code, 200)
        self.assertEqual(anatomy.json()["state"], "EMPTY")
        self.assertEqual(anatomy.json()["observer_authority"], "NONE")

    def test_model_output_tool_call_is_rejected_and_reasoning_removed(self):
        with self.assertRaisesRegex(cortex.CortexBoundaryError, "attempted_tool_call"):
            cortex._extract_output(
                {
                    "choices": [
                        {
                            "message": {
                                "content": "ignored",
                                "tool_calls": [{"name": "shell"}],
                            }
                        }
                    ]
                }
            )
        clean = cortex._extract_output(
            {
                "choices": [
                    {
                        "message": {
                            "content": "<think>secret</think>Final [node-a].",
                        }
                    }
                ]
            }
        )
        self.assertEqual(clean, "Final [node-a].")


if __name__ == "__main__":
    unittest.main(verbosity=2)
