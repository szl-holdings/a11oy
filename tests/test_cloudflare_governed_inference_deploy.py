#!/usr/bin/env python3
"""Network-free contracts for the governed Cloudflare inference deployer."""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "deploy_cloudflare_governed_inference.py"
spec = importlib.util.spec_from_file_location("deploy_cf_inference", SCRIPT)
assert spec and spec.loader
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)

REVISION = "a" * 40
TARGET = deploy.script_name(REVISION)


class GovernedInferenceDeploymentContract(unittest.TestCase):
    def test_versioned_script_name_and_binding_metadata(self) -> None:
        self.assertEqual(
            TARGET,
            "szl-a11oy-governed-inference-aaaaaaaaaaaaaaaa",
        )
        metadata = deploy.worker_metadata(REVISION)
        self.assertEqual(metadata["main_module"], "worker.mjs")
        self.assertIn({"type": "ai", "name": "AI"}, metadata["bindings"])
        self.assertIn(
            {
                "type": "plain_text",
                "name": "SZL_SOURCE_REVISION",
                "text": REVISION,
            },
            metadata["bindings"],
        )
        body, boundary = deploy.multipart_module(b"export default {};", REVISION)
        self.assertIn(boundary.encode("utf-8"), body)
        self.assertIn(b'"type":"ai"', body)
        self.assertIn(b'"name":"SZL_SOURCE_REVISION"', body)
        self.assertIn(REVISION.encode("ascii"), body)
        self.assertNotIn(b"token", body.lower())

    def test_route_plan_creates_only_exact_v2_route(self) -> None:
        plan = deploy.route_plan(
            [
                {
                    "id": "root-route",
                    "pattern": "a-11-oy.com/*",
                    "script": "szl-a11oy-product-edge-v3",
                }
            ],
            TARGET,
        )
        self.assertEqual(plan["action"], "create")
        self.assertEqual(plan["pattern"], "a-11-oy.com/api/v2/*")
        self.assertIsNone(plan["prior_script"])

    def test_route_plan_updates_only_owned_versioned_script(self) -> None:
        prior = "szl-a11oy-governed-inference-bbbbbbbbbbbbbbbb"
        plan = deploy.route_plan(
            [
                {
                    "id": "governed-route",
                    "pattern": deploy.ROUTE_PATTERN,
                    "script": prior,
                }
            ],
            TARGET,
        )
        self.assertEqual(plan["action"], "update")
        self.assertEqual(plan["prior_script"], prior)
        self.assertEqual(plan["route_id"], "governed-route")

        noop = deploy.route_plan(
            [
                {
                    "id": "governed-route",
                    "pattern": deploy.ROUTE_PATTERN,
                    "script": TARGET,
                }
            ],
            TARGET,
        )
        self.assertEqual(noop["action"], "verify-noop")

    def test_foreign_or_duplicate_route_fails_closed(self) -> None:
        with self.assertRaisesRegex(deploy.DeployError, "foreign script"):
            deploy.route_plan(
                [
                    {
                        "id": "foreign",
                        "pattern": deploy.ROUTE_PATTERN,
                        "script": "unrelated-worker",
                    }
                ],
                TARGET,
            )
        with self.assertRaisesRegex(deploy.DeployError, "duplicate"):
            deploy.route_plan(
                [
                    {
                        "id": "one",
                        "pattern": deploy.ROUTE_PATTERN,
                        "script": TARGET,
                    },
                    {
                        "id": "two",
                        "pattern": deploy.ROUTE_PATTERN,
                        "script": TARGET,
                    },
                ],
                TARGET,
            )

    def test_route_application_uses_exact_pattern_and_script(self) -> None:
        plan = {
            "action": "create",
            "pattern": deploy.ROUTE_PATTERN,
            "route_id": None,
            "prior_script": None,
            "target_script": TARGET,
        }
        with mock.patch.object(
            deploy,
            "request_json",
            return_value={
                "success": True,
                "result": {
                    "id": "new-route",
                    "pattern": deploy.ROUTE_PATTERN,
                    "script": TARGET,
                },
            },
        ) as request:
            result = deploy.apply_route_plan("zone", "secret", plan)
        self.assertEqual(result["state"], "CREATED")
        request.assert_called_once_with(
            "POST",
            "/zones/zone/workers/routes",
            bearer="secret",
            payload={
                "pattern": deploy.ROUTE_PATTERN,
                "script": TARGET,
            },
        )

    def test_rollback_restores_owned_prior_script(self) -> None:
        prior = "szl-a11oy-governed-inference-bbbbbbbbbbbbbbbb"
        plan = {
            "action": "update",
            "pattern": deploy.ROUTE_PATTERN,
            "route_id": "route",
            "prior_script": prior,
            "target_script": TARGET,
        }
        applied = {
            "state": "UPDATED",
            "route_id": "route",
            "script": TARGET,
            "pattern": deploy.ROUTE_PATTERN,
        }
        with mock.patch.object(
            deploy,
            "request_json",
            return_value={
                "success": True,
                "result": {
                    "id": "route",
                    "pattern": deploy.ROUTE_PATTERN,
                    "script": prior,
                },
            },
        ) as request:
            result = deploy.rollback_route(
                "zone",
                "secret",
                plan,
                applied,
            )
        self.assertEqual(result["state"], "PRIOR_SCRIPT_RESTORED")
        request.assert_called_once_with(
            "PUT",
            "/zones/zone/workers/routes/route",
            bearer="secret",
            payload={
                "pattern": deploy.ROUTE_PATTERN,
                "script": prior,
            },
        )

    def test_created_route_rollback_deletes_only_created_route(self) -> None:
        plan = {
            "action": "create",
            "pattern": deploy.ROUTE_PATTERN,
            "route_id": None,
            "prior_script": None,
            "target_script": TARGET,
        }
        applied = {
            "state": "CREATED",
            "route_id": "created",
            "script": TARGET,
            "pattern": deploy.ROUTE_PATTERN,
        }
        with mock.patch.object(
            deploy,
            "request_json",
            return_value={"success": True, "result": None},
        ) as request:
            result = deploy.rollback_route(
                "zone",
                "secret",
                plan,
                applied,
            )
        self.assertEqual(result["state"], "CREATED_ROUTE_REMOVED")
        request.assert_called_once_with(
            "DELETE",
            "/zones/zone/workers/routes/created",
            bearer="secret",
        )

    @staticmethod
    def _valid_payloads() -> tuple[dict, dict, dict, dict]:
        health = {
            "status": "READY",
            "source_revision": REVISION,
            "ai_binding": True,
            "doctrine": {"state": "LOCKED"},
            "owned_model_served": False,
            "action_authority": "NONE",
        }
        contract = {
            "schema": deploy.EXPECTED_CONTRACT_SCHEMA,
            "source_revision": REVISION,
            "runtime": {
                "tools": False,
                "action_authority": "NONE",
                "output_state": "PROPOSAL_ONLY",
            },
            "owned_model": {"served_by_this_runtime": False},
            "governance": {
                "lambda": {
                    "status": "CONJECTURE_1_ADVISORY",
                    "can_authorize": False,
                }
            },
        }
        receipt_payload = {
            "schema": deploy.EXPECTED_RECEIPT_SCHEMA,
            "source_revision": REVISION,
            "prompt_sha256": deploy.sha256_text(deploy.PROBE_PROMPT),
            "output_sha256": deploy.sha256_text("Proposal [E0]."),
            "executed": False,
        }
        receipt = {
            "schema": deploy.EXPECTED_RECEIPT_SCHEMA,
            "payload": receipt_payload,
            "receipt_sha256": deploy.sha256_text(
                deploy.canonical_json(receipt_payload)
            ),
            "signature": {
                "status": "UNSIGNED_EDGE",
                "durable": False,
                "must_be_signed_before_consequential_action": True,
            },
        }
        inference = {
            "schema": deploy.EXPECTED_RESPONSE_SCHEMA,
            "source_revision": REVISION,
            "state": "PROPOSAL",
            "output": "Proposal [E0].",
            "output_sha256": deploy.sha256_text("Proposal [E0]."),
            "executed": False,
            "authority_state": "NO_ACTION_AUTHORITY",
            "tool_execution": False,
            "model": {
                "candidate": "@cf/zai-org/glm-4.7-flash",
                "kind": "CLOUDFLARE_HOSTED_EXTERNAL_CANDIDATE",
                "owned_model_served": False,
            },
            "formula_authority": {
                "locked_proven_ids": deploy.LOCKED_FORMULAS,
                "lambda": {
                    "status": "CONJECTURE_1_ADVISORY",
                    "can_authorize": False,
                },
            },
            "nemo": [
                {
                    "stage": "PRE_GENERATION",
                    "decision": "ALLOW_PROPOSAL_ONLY",
                },
                {
                    "stage": "POST_GENERATION",
                    "decision": "ALLOW_PROPOSAL_ONLY",
                },
            ],
            "receipt": receipt,
            "anatomy_observation": {
                "delivery": "DELIVERED_INLINE",
                "observer_authority": "NONE",
                "persistence": "EPHEMERAL_ISOLATE_NO_DURABLE_BINDING",
                "event": {
                    "raw_prompt_present": False,
                    "private_reasoning_present": False,
                },
            },
            "evidence_handles": [{"id": "E0"}],
            "citations": ["E0"],
            "second_brain": {"state": "NOT_READY"},
        }
        headers = {
            "x-szl-edge": deploy.EDGE_MARKER,
            "x-szl-governed-inference": "v1",
        }
        return health, contract, inference, headers

    def test_live_proof_validator_checks_receipt_and_authority(self) -> None:
        health, contract, inference, headers = self._valid_payloads()
        summary = deploy.validate_probe_payload(
            health,
            contract,
            inference,
            headers,
            source_revision=REVISION,
        )
        self.assertEqual(summary["health"], "READY")
        self.assertEqual(summary["action_authority"], False)
        self.assertEqual(summary["owned_model_served"], False)
        self.assertEqual(summary["raw_prompt_persisted_in_receipt"], False)

    def test_live_proof_rejects_digest_or_action_drift(self) -> None:
        health, contract, inference, headers = self._valid_payloads()
        inference["receipt"]["receipt_sha256"] = "0" * 64
        with self.assertRaisesRegex(deploy.DeployError, "digest mismatch"):
            deploy.validate_probe_payload(
                health,
                contract,
                inference,
                headers,
                source_revision=REVISION,
            )

        health, contract, inference, headers = self._valid_payloads()
        inference["executed"] = True
        with self.assertRaisesRegex(deploy.DeployError, "executed an action"):
            deploy.validate_probe_payload(
                health,
                contract,
                inference,
                headers,
                source_revision=REVISION,
            )

    def test_prior_script_retirement_never_deletes_referenced_script(self) -> None:
        prior = "szl-a11oy-governed-inference-bbbbbbbbbbbbbbbb"
        with (
            mock.patch.object(
                deploy,
                "fetch_routes",
                return_value=[
                    {
                        "id": "other",
                        "pattern": "a-11-oy.com/api/v2/legacy/*",
                        "script": prior,
                    }
                ],
            ),
            mock.patch.object(deploy, "delete_worker") as delete_worker,
        ):
            result = deploy.retire_prior_script(
                "account",
                "zone",
                "secret",
                prior,
                TARGET,
            )
        self.assertEqual(result["state"], "RETAINED_REFERENCED")
        delete_worker.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
