"""Offline contract tests for the fail-closed 26-Space qualification harness."""

import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_hf_spaces_operational import (
    ContractError,
    HttpResponse,
    UNKNOWN,
    load_manifest,
    qualify,
    validate_manifest,
)

MANIFEST_PATH = ROOT / "huggingface" / "space-operational-manifest.json"


class FakeTransport:
    def __init__(self, manifest):
        self.metadata = {}
        self.responses = {}
        for space in manifest["spaces"]:
            revision = space["exact_revision"]["expected"]
            if revision == UNKNOWN:
                revision = (space["name"].encode("utf-8").hex() + "0" * 40)[:40]
            self.metadata[space["repo_id"]] = {
                "sha": revision,
                "runtime": {"stage": "RUNNING"},
            }

    @staticmethod
    def _response(status, payload=None, content_type="application/json", url=""):
        if payload is None:
            body = b"ok"
        else:
            body = json.dumps(payload).encode("utf-8")
        return HttpResponse(status, {"content-type": content_type}, body, url)

    def request(self, method, url, timeout, body=None, headers=None):
        override = self.responses.get((method, url))
        if isinstance(override, list):
            override = override.pop(0)
        if isinstance(override, Exception):
            raise override
        if override is not None:
            return override
        api_prefix = "https://huggingface.co/api/spaces/"
        if url.startswith(api_prefix):
            repo_id = url[len(api_prefix) :]
            return self._response(200, self.metadata[repo_id], url=url)
        return self._response(200, None, "text/html; charset=utf-8", url)


class SpaceQualificationContractTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest(MANIFEST_PATH)
        self.transport = FakeTransport(self.manifest)

    def run_qualification(self, manifest=None):
        return qualify(
            manifest or self.manifest,
            self.transport,
            attempts=1,
            timeout=0.1,
            sleep_s=0,
            max_workers=4,
        )

    def test_manifest_is_exactly_the_canonical_26_space_inventory(self):
        validate_manifest(self.manifest)
        self.assertEqual(26, len(self.manifest["spaces"]))
        self.assertEqual(26, len({row["name"] for row in self.manifest["spaces"]}))

    def test_happy_contract_requires_every_space_and_preserves_unknown_inference(self):
        receipt = self.run_qualification()
        self.assertEqual("PASS", receipt["overall_status"])
        self.assertEqual(26, receipt["passed_spaces"])
        self.assertEqual(0, receipt["failed_spaces"])
        self.assertFalse(receipt["majority_threshold"])
        self.assertTrue(receipt["complete_estate"])
        self.assertTrue(
            all(
                row["inference_receipt"]["status"] == UNKNOWN
                for row in receipt["spaces"]
            )
        )

    def test_missing_space_is_a_contract_refusal(self):
        broken = copy.deepcopy(self.manifest)
        broken["spaces"].pop()
        with self.assertRaisesRegex(ContractError, "exactly equal canonical inventory"):
            validate_manifest(broken)

    def test_stale_pinned_revision_fails_the_estate(self):
        self.transport.metadata["SZLHOLDINGS/a11oy"]["sha"] = "b" * 40
        receipt = self.run_qualification()
        a11oy = next(row for row in receipt["spaces"] if row["name"] == "a11oy")
        self.assertEqual("FAIL", receipt["overall_status"])
        self.assertEqual("FAIL", a11oy["exact_revision_receipt"]["status"])
        self.assertIn("a11oy", receipt["failed_space_names"])

    def test_one_failed_required_tab_fails_without_a_majority_threshold(self):
        url = "https://szlholdings-a11oy.hf.space/console"
        self.transport.responses[("GET", url)] = FakeTransport._response(
            503, None, "text/plain", url
        )
        receipt = self.run_qualification()
        a11oy = next(row for row in receipt["spaces"] if row["name"] == "a11oy")
        console = next(row for row in a11oy["path_receipts"] if row["path"] == "/console")
        self.assertEqual("FAIL", receipt["overall_status"])
        self.assertEqual(1, receipt["failed_spaces"])
        self.assertEqual("FAIL", console["status"])

    def test_transient_http_failure_is_bounded_and_can_recover(self):
        url = "https://szlholdings-a11oy.hf.space/console"
        self.transport.responses[("GET", url)] = [
            FakeTransport._response(503, None, "text/plain", url),
            FakeTransport._response(200, None, "text/html", url),
        ]
        receipt = qualify(
            self.manifest,
            self.transport,
            attempts=2,
            timeout=0.1,
            sleep_s=0,
            max_workers=4,
        )
        a11oy = next(row for row in receipt["spaces"] if row["name"] == "a11oy")
        console = next(row for row in a11oy["path_receipts"] if row["path"] == "/console")
        self.assertEqual("PASS", receipt["overall_status"])
        self.assertEqual(2, console["attempts"])

    def test_non_running_dynamic_space_fails_closed(self):
        self.transport.metadata["SZLHOLDINGS/cosmos"]["runtime"]["stage"] = "STOPPED"
        receipt = self.run_qualification()
        cosmos = next(row for row in receipt["spaces"] if row["name"] == "cosmos")
        self.assertEqual("FAIL", receipt["overall_status"])
        self.assertEqual("FAIL", cosmos["runtime_receipt"]["status"])

    def test_required_inference_rejects_wrong_exact_served_model(self):
        manifest = copy.deepcopy(self.manifest)
        immune = next(row for row in manifest["spaces"] if row["name"] == "immune")
        immune["inference"] = {
            "policy": "REQUIRED",
            "path": "/api/infer",
            "method": "POST",
            "request_body": {"input": "qualification"},
            "expected_model": "SZLHOLDINGS/immune-frontier",
            "expected_revision": "c" * 40,
            "response_model_field": "model",
            "response_revision_field": "revision",
            "required_json_keys": ["model", "revision", "output"],
        }
        url = "https://szlholdings-immune.hf.space/api/infer"
        self.transport.responses[("POST", url)] = FakeTransport._response(
            200,
            {"model": "someone-else/model", "revision": "c" * 40, "output": "x"},
            url=url,
        )
        receipt = self.run_qualification(manifest)
        immune_receipt = next(row for row in receipt["spaces"] if row["name"] == "immune")
        self.assertEqual("FAIL", receipt["overall_status"])
        self.assertEqual("FAIL", immune_receipt["inference_receipt"]["status"])
        self.assertIn("model expected", immune_receipt["inference_receipt"]["error"])

    def test_unknown_requested_space_is_refused(self):
        with self.assertRaisesRegex(ContractError, "unknown --only"):
            qualify(
                self.manifest,
                self.transport,
                attempts=1,
                timeout=0.1,
                sleep_s=0,
                only={"not-a-space"},
            )

    def test_shared_signing_action_is_invocation_isolated_and_backward_compatible(self):
        action = (ROOT / ".github" / "actions" / "sign-receipts" / "action.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("governance-out-dir:", action)
        self.assertIn('default: "attestations/governance"', action)
        self.assertIn("sign-khipu:", action)
        self.assertIn('default: "true"', action)
        self.assertIn("khipu-out-dir:", action)
        self.assertIn('default: "attestations/khipu"', action)
        self.assertIn('--out-dir "${{ inputs.governance-out-dir }}"', action)
        self.assertIn("if: inputs.sign-khipu == 'true'", action)
        self.assertIn('--out-dir "${{ inputs.khipu-out-dir }}"', action)

        verification = action.split(
            "- name: Independently verify only envelopes minted by this invocation", 1
        )[1]
        self.assertIn("steps.locate.outputs.governance_envelope", verification)
        self.assertIn("steps.khipu.outputs.khipu_envelope", verification)
        self.assertNotIn("attestations/governance/*.dsse.json", verification)
        self.assertNotIn("attestations/khipu/*.dsse.json", verification)

    def test_hf_workflow_uses_dedicated_dsse_directory_without_khipu_side_effect(self):
        workflow = (ROOT / ".github" / "workflows" / "hf-space-qualification.yml").read_text(
            encoding="utf-8"
        )
        dedicated = (
            "evidence/hf-space-qualification/dsse/"
            "${{ github.run_id }}-${{ github.run_attempt }}"
        )
        self.assertIn(f"governance-out-dir: {dedicated}", workflow)
        self.assertIn('sign-khipu: "false"', workflow)
        self.assertIn(f"{dedicated}/*.dsse.json", workflow)
        self.assertNotIn("attestations/governance/*.dsse.json", workflow)
        self.assertNotIn("attestations/khipu/*.dsse.json", workflow)


if __name__ == "__main__":
    unittest.main(verbosity=2)
