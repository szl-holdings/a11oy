"""Adversarial source-only checks for the A11oy one-manifest release gate.

No endpoints, credentials, provider writes or deployment tools.
"""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import szl_release_manifest as srm

COMMIT = "a" * 40
FRONT = "b" * 64
API = "c" * 64
MODEL = "SZL-Khipu-Q4.gguf@sha256:" + "d" * 64
DEPLOY = "ghcr.io/szl-holdings/a11oy@sha256:" + "e" * 64


def runtime_values():
    return {
        "served_frontend_sha256": FRONT,
        "api_contract_sha256": API,
        "model_identity": MODEL,
        "deployment_identity": DEPLOY,
    }


def source_manifest():
    return {"status": "GENERATED", "source_commit": COMMIT, "runtime": runtime_values()}


def live_evidence():
    return {"source_commit": COMMIT, **runtime_values()}


def gate_for(manifest, runtime=None):
    return srm.promotion_gate(manifest, runtime or live_evidence())


class ReleaseManifestFailClosedTests(unittest.TestCase):
    def test_exact_valid_manifest_still_passes(self):
        result = gate_for(source_manifest())
        self.assertEqual(result["decision"], "PASS")
        self.assertFalse(result["blocking_findings"])

    def test_invalid_loaded_status_is_never_promoted(self):
        for status in ("PROMOTE_ANYWAY", "bogus", "", None, 1, True, ["GENERATED"]):
            with self.subTest(status=status), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "bad-status.json"
                path.write_text(
                    json.dumps(
                        {
                            "kind": srm.KIND,
                            "status": status,
                            "release_id": "test",
                            "source": {"git_commit": COMMIT, "git_ref": "main"},
                            "runtime": runtime_values(),
                        }
                    ),
                    encoding="utf-8",
                )
                loaded = srm.load_manifest(path)
                self.assertEqual(loaded["status"], "UNAVAILABLE")
                self.assertEqual(gate_for(loaded)["decision"], "BLOCKED")

    def test_invalid_direct_status_is_hard_hold(self):
        for status in ("GARBAGE", "UNKNOWN", None, [], {}, True, 1):
            with self.subTest(status=status):
                obj = source_manifest()
                obj["status"] = status
                result = gate_for(obj)
                self.assertEqual(result["decision"], "BLOCKED")
                self.assertTrue(
                    any(
                        v["kind"] == "MANIFEST_STATUS_INVALID"
                        for v in result["blocking_findings"]
                    )
                )

    def test_invalid_source_commits_do_not_match(self):
        for value in (
            "abc",
            "f" * 39,
            "z" * 40,
            "ABC" * 13 + "A",
            True,
            {"rev": COMMIT},
            ["a" * 40],
            123,
        ):
            with self.subTest(value=value):
                obj = source_manifest()
                obj["source_commit"] = value
                runtime = live_evidence()
                runtime["source_commit"] = value
                result = gate_for(obj, runtime)
                self.assertEqual(result["decision"], "BLOCKED")
                self.assertTrue(
                    any(
                        v["kind"] == "SOURCE_COMMIT_FORMAT_INVALID"
                        for v in result["blocking_findings"]
                    )
                )

    def test_invalid_equal_sha_digests_are_rejected(self):
        for key in ("served_frontend_sha256", "api_contract_sha256"):
            for value in (
                "fake",
                "0" * 64,
                "G" * 64,
                "f" * 63,
                "0x" + "f" * 64,
                "f" * 64 + "\n",
                True,
                17,
                {},
                [],
            ):
                with self.subTest(key=key, value=value):
                    obj = source_manifest()
                    obj["runtime"][key] = value
                    runtime = live_evidence()
                    runtime[key] = value
                    result = gate_for(obj, runtime)
                    self.assertEqual(result["decision"], "BLOCKED")
                    self.assertFalse(
                        any(
                            v["kind"] == key.upper() + "_MATCH"
                            for v in result["blocking_findings"]
                        )
                    )

    def test_nonstring_and_unpinned_model_identity_never_pass(self):
        for key in ("model_identity", "deployment_identity"):
            for value in (
                True,
                100,
                {},
                {"name": "model"},
                [],
                ["model"],
                "model",
                "model@latest",
                "model@sha256:" + "0" * 63,
                "model@sha256:" + "f" * 64 + "\n",
            ):
                with self.subTest(key=key, value=value):
                    obj = source_manifest()
                    obj["runtime"][key] = value
                    runtime = live_evidence()
                    runtime[key] = value
                    result = gate_for(obj, runtime)
                    self.assertEqual(result["decision"], "BLOCKED")
                    self.assertTrue(
                        any(
                            v["kind"].endswith("_INVALID")
                            for v in result["blocking_findings"]
                        )
                    )

    def test_runtime_type_invalid_even_if_manifest_valid(self):
        obj = source_manifest()
        runtime = live_evidence()
        runtime["model_identity"] = {"not": "text"}
        result = gate_for(obj, runtime)
        self.assertEqual(result["decision"], "BLOCKED")

    def test_manifest_type_invalid_even_if_runtime_valid(self):
        obj = source_manifest()
        obj["runtime"]["deployment_identity"] = ["bad"]
        result = gate_for(obj)
        self.assertEqual(result["decision"], "BLOCKED")
        self.assertTrue(
            any(
                v["kind"] == "MANIFEST_DEPLOYMENT_IDENTITY_INVALID"
                for v in result["blocking_findings"]
            )
        )

    def test_duplicate_status_and_nested_digest_keys_refused(self):
        original = source_manifest()
        for raw in (
            '{"kind":"szl.release-manifest/v1","status":"GENERATED","status":"GARBAGE"}',
            '{"kind":"szl.release-manifest/v1","status":"GENERATED",'
            '"source":{"git_commit":"a","git_commit":"b"}}',
            '{"kind":"szl.release-manifest/v1","status":"GENERATED",'
            '"runtime":{"api_contract_sha256":"a","api_contract_sha256":"b"}}',
        ):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "duplicate.json"
                path.write_text(raw, encoding="utf-8")
                loaded = srm.load_manifest(path)
                self.assertEqual(loaded["status"], "UNAVAILABLE")
                self.assertEqual(gate_for(loaded)["decision"], "BLOCKED")
        self.assertEqual(gate_for(original)["decision"], "PASS")

    def test_generator_refuses_unpinned_model_and_deployment(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "api.md"
            front = Path(tmp) / "frontend.html"
            doc.write_text("api", encoding="utf-8")
            front.write_text("frontend", encoding="utf-8")
            obj, missing = srm.generate_manifest(
                commit=COMMIT,
                api_contract_doc_path=doc,
                served_artifact_path=str(front),
                model_identity="model@latest",
                deployment_identity="ghcr.io/org/image:latest",
            )
            self.assertIn("runtime.model_identity", missing)
            self.assertIn("runtime.deployment_identity", missing)
            self.assertEqual(obj["status"], "GENERATED")
            self.assertEqual(
                gate_for(
                    {
                        "status": "GENERATED",
                        "source_commit": COMMIT,
                        "runtime": obj["runtime"],
                    }
                )["decision"],
                "BLOCKED",
            )

    def test_generator_accepts_pinned_identity_forms(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "api.md"
            front = Path(tmp) / "front"
            doc.write_bytes(b"api")
            front.write_bytes(b"frontend")
            obj, missing = srm.generate_manifest(
                commit=COMMIT,
                api_contract_doc_path=doc,
                served_artifact_path=str(front),
                model_identity="org/adapter@" + "f" * 40,
                deployment_identity=DEPLOY,
            )
            self.assertNotIn("runtime.model_identity", missing)
            self.assertNotIn("runtime.deployment_identity", missing)
            result = gate_for(
                {
                    "status": "GENERATED",
                    "source_commit": COMMIT,
                    "runtime": obj["runtime"],
                },
                {"source_commit": COMMIT, **obj["runtime"]},
            )
            self.assertEqual(result["decision"], "PASS")

    def test_invalid_env_label_not_measured(self):
        with patch.dict(
            "os.environ",
            {
                "SZL_SERVED_FRONTEND_SHA256": "fake",
                "SZL_API_CONTRACT_SHA256": API,
                "SZL_MODEL_IDENTITY": "model@latest",
                "SZL_DEPLOYMENT_IDENTITY": DEPLOY,
            },
            clear=False,
        ):
            result = srm.runtime_evidence()
        self.assertEqual(result["_labels"]["served_frontend_sha256"], srm.UNKNOWN)
        self.assertEqual(result["_labels"]["model_identity"], srm.UNKNOWN)
        self.assertEqual(result["_labels"]["api_contract_sha256"], "MEASURED_ENV")
        self.assertEqual(result["_labels"]["deployment_identity"], "MEASURED_ENV")


if __name__ == "__main__":
    unittest.main()
