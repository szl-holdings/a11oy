# SPDX-License-Identifier: Apache-2.0
"""Fail-closed unit checks for the Yupaq governed computation plane."""

from __future__ import annotations

import copy
import threading
import unittest

import szl_yupaq_compute as compute


def job(job_id: str = "compute-test-1") -> dict:
    return {
        "schema": compute.JOB_SCHEMA,
        "job_id": job_id,
        "operation": "formula.org_lambda.weighted_geomean",
        "inputs": {"axes": [0.81, 0.64], "weights": [0.5, 0.5]},
        "resource_budget": {"max_runtime_ms": 2_000, "max_output_bytes": 64 * 1024},
    }


class YupaqComputeTests(unittest.TestCase):
    def setUp(self) -> None:
        with compute._STORE_LOCK:
            compute._STORE.clear()
            compute._REQUEST_BINDINGS.clear()

    def test_lambda_is_computed_but_never_promoted_to_proof(self) -> None:
        record = compute.run_job(job(), persist=False)
        self.assertEqual(record["result"]["state"], "COMPLETED")
        output = record["result"]["output"]
        self.assertAlmostEqual(output["value"], 0.72)
        self.assertEqual(output["uniqueness"], "CONJECTURE_1_OPEN")
        self.assertEqual(output["proof_transfer"], "DENIED_NAMESPACE_SCOPED")
        self.assertEqual(record["result"]["proof_uplift"], 0)
        self.assertEqual(record["lake"]["state"], "NOT_REQUESTED")

    def test_unknown_fields_code_paths_urls_and_operations_are_rejected(self) -> None:
        for field, value in (
            ("code", "print('no')"),
            ("path", "C:/secret"),
            ("url", "https://example.com"),
            ("package", "untrusted"),
            ("command", "whoami"),
        ):
            payload = job(f"reject-{field}")
            payload["inputs"][field] = value
            with self.assertRaises(compute.ContractError):
                compute.parse_job(payload)

        payload = job("reject-operation")
        payload["operation"] = "python.eval"
        with self.assertRaises(compute.ContractError):
            compute.parse_job(payload)

    def test_job_id_is_idempotent_and_cannot_be_rebound(self) -> None:
        first = compute.run_job(job("same-id"), persist=False)
        replay = compute.run_job(job("same-id"), persist=False)
        self.assertFalse(first["idempotent_replay"])
        self.assertTrue(replay["idempotent_replay"])

        changed = job("same-id")
        changed["inputs"]["axes"] = [0.5, 0.5]
        with self.assertRaises(compute.ContractError):
            compute.run_job(changed, persist=False)

    def test_receipt_binds_request_and_result_and_unsigned_is_not_valid(self) -> None:
        record = compute.run_job(job("receipt-test"), persist=False)
        verdict = compute.verify_job_record(record)
        self.assertTrue(verdict["request_hash_match"])
        self.assertTrue(verdict["result_hash_match"])
        self.assertTrue(verdict["receipt_links_match"])
        if not verdict["signature_verified"]:
            self.assertFalse(verdict["valid"])
            self.assertFalse(verdict["unsigned_records_are_valid"])

        tampered = copy.deepcopy(record)
        tampered["result"]["output"]["value"] = 0.99
        tampered_verdict = compute.verify_job_record(tampered)
        self.assertFalse(tampered_verdict["result_hash_match"])
        self.assertFalse(tampered_verdict["valid"])

        semantic_tamper = copy.deepcopy(record)
        semantic_tamper["receipt"]["operation"] = "brain.corpus.inventory"
        semantic_verdict = compute.verify_job_record(semantic_tamper)
        self.assertFalse(semantic_verdict["receipt_digest_match"])
        self.assertFalse(semantic_verdict["semantic_links_match"])
        self.assertFalse(semantic_verdict["valid"])

        top_level_job_tamper = copy.deepcopy(record)
        top_level_job_tamper["job_id"] = "different-job"
        top_level_verdict = compute.verify_job_record(top_level_job_tamper)
        self.assertFalse(top_level_verdict["semantic_links_match"])
        self.assertFalse(top_level_verdict["valid"])

        request_link_tamper = copy.deepcopy(record)
        request_link_tamper["result"]["request_sha256"] = "0" * 64
        request_link_verdict = compute.verify_job_record(request_link_tamper)
        self.assertFalse(request_link_verdict["result_hash_match"])
        self.assertFalse(request_link_verdict["semantic_links_match"])
        self.assertFalse(request_link_verdict["valid"])

        evidence_label_tamper = copy.deepcopy(record)
        evidence_label_tamper["result"]["evidence_label"] = "CONFLICT"
        evidence_label_verdict = compute.verify_job_record(evidence_label_tamper)
        self.assertFalse(evidence_label_verdict["result_hash_match"])
        self.assertFalse(evidence_label_verdict["semantic_links_match"])
        self.assertFalse(evidence_label_verdict["valid"])

    def test_concurrent_same_id_executes_once(self) -> None:
        original = compute._execute
        started = threading.Event()
        release = threading.Event()
        calls = {"count": 0}

        def slow_execute(*args, **kwargs):
            calls["count"] += 1
            started.set()
            release.wait(timeout=2)
            return original(*args, **kwargs)

        first_result = {}
        first_error = {}

        def first_run():
            try:
                first_result["value"] = compute.run_job(
                    job("concurrent-id"), persist=False)
            except Exception as exc:  # pragma: no cover - asserted below
                first_error["value"] = exc

        compute._execute = slow_execute
        try:
            thread = threading.Thread(target=first_run)
            thread.start()
            self.assertTrue(started.wait(timeout=2))
            with self.assertRaisesRegex(compute.ContractError, "already in progress"):
                compute.run_job(job("concurrent-id"), persist=False)
            release.set()
            thread.join(timeout=2)
        finally:
            compute._execute = original
            release.set()
        self.assertFalse(first_error)
        self.assertIn("value", first_result)
        self.assertEqual(calls["count"], 1)

    def test_inventory_accounting_does_not_invent_200_formulas_or_trainable_brain(self) -> None:
        status = compute.capabilities()
        self.assertEqual(status["brain_nodes"], 9464)
        self.assertEqual(status["brain_nodes_in_gradients"], 0)
        accounting = status["formula_accounting"]
        self.assertEqual(accounting["requested_200"], "NOT_VERIFIED")
        self.assertEqual(accounting["thesis_extracted"], 100)
        self.assertEqual(accounting["crosswalk_rows"], 146)
        self.assertEqual(accounting["holdout_rows"], 148)
        self.assertEqual(accounting["train_rows"], 0)
        self.assertEqual(accounting["lean_declarations"], 269)
        self.assertEqual(
            status["lanes"]["szl_lake"],
            "BEST_EFFORT_LOCAL_KHIPU_APPEND_REDEPLOY_DURABILITY_NOT_VERIFIED",
        )
        self.assertEqual(status["lanes"]["invariant"], "NOT_WIRED_TO_RUN_JOB")

    def test_external_numerics_preserves_unavailable_or_result_state(self) -> None:
        payload = {
            "schema": compute.JOB_SCHEMA,
            "job_id": "numerics-test",
            "operation": "numerics.external.run",
            "inputs": {
                "engine": "octave",
                "request": {
                    "schema": "szl.numerics.request/v1",
                    "request_id": "numerics-test",
                    "operation": "MATRIX_SOLVE",
                    "inputs": {"matrix": [[2, 0], [0, 4]], "rhs": [2, 8]},
                    "tolerance": {"absolute": 1e-9, "relative": 1e-9},
                },
            },
            "resource_budget": {"max_runtime_ms": 8_000, "max_output_bytes": 64 * 1024},
        }
        record = compute.run_job(payload, persist=False)
        self.assertIn(record["result"]["state"], {"COMPLETED", "UNAVAILABLE"})
        self.assertEqual(record["result"]["proof_uplift"], 0)
        self.assertEqual(record["result"]["trust_uplift"], 0)


if __name__ == "__main__":
    unittest.main()
