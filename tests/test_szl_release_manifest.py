"""tests/test_szl_release_manifest.py — #3770 manifest + promotion gate tests.

Regression coverage for the #3768 PUBLICATION_LAG repro the owner reported on
2026-11-19: a runtime whose git commit MATCHES the manifest but reports NO
frontend/API hashes and no model/deployment identity previously produced NO
findings. It must now produce blocking findings and BLOCK promotion.

Run: python -m unittest tests.test_szl_release_manifest  (or via pytest).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import szl_release_manifest as srm  # noqa: E402

COMMIT = "9467fa988ff63c919954adbd8e23e930412321b5"
FRONT_SHA = "a" * 64
API_SHA = "b" * 64
MODEL_ID = "SZL-Khipu-1.5B-Q4_K_M.gguf@sha256:" + "c" * 64
DEPLOY_ID = "ghcr.io/szl-holdings/a11oy@sha256:" + "d" * 64


def _manifest(status="GENERATED", runtime=None, commit=COMMIT):
    return {
        "kind": srm.KIND,
        "status": status,
        "source_commit": commit,
        "runtime": runtime or {},
        "release_id": "test-release",
    }


def _runtime(commit=COMMIT, **overrides):
    base = {
        "source_commit": commit,
        "served_frontend_sha256": FRONT_SHA,
        "api_contract_sha256": API_SHA,
        "model_identity": MODEL_ID,
        "deployment_identity": DEPLOY_ID,
        "release_id": "test-release",
    }
    base.update(overrides)
    return base


class PublicationLagRepro(unittest.TestCase):
    """#3768 repro: matching commit, no reported hashes — must BLOCK."""

    def setUp(self):
        os.environ.pop("SZL_SERVED_FRONTEND_SHA256", None)
        os.environ.pop("SZL_API_CONTRACT_SHA256", None)
        os.environ.pop("SZL_MODEL_IDENTITY", None)
        os.environ.pop("SZL_DEPLOYMENT_IDENTITY", None)

    def test_matching_commit_without_hashes_blocks(self):
        manifest = _manifest(runtime={
            "served_frontend_sha256": FRONT_SHA,
            "api_contract_sha256": API_SHA,
            "model_identity": MODEL_ID,
            "deployment_identity": DEPLOY_ID,
        })
        runtime = _runtime(
            served_frontend_sha256=srm.UNKNOWN,
            api_contract_sha256=srm.UNKNOWN,
            model_identity=srm.UNKNOWN,
            deployment_identity=srm.UNKNOWN,
        )
        findings = srm.compare_runtime(manifest, runtime)
        kinds = {f["kind"] for f in findings}
        self.assertIn("PUBLICATION_LAG", kinds)  # the previously silent case
        gate = srm.promotion_gate(manifest, runtime)
        self.assertEqual(gate["decision"], "BLOCKED")
        self.assertTrue(any(f["kind"] == "PUBLICATION_LAG" for f in gate["blocking_findings"]))

    def test_findings_never_empty_when_evidence_missing(self):
        manifest = _manifest()
        runtime = _runtime(source_commit=srm.UNKNOWN)
        self.assertNotEqual(srm.compare_runtime(manifest, runtime), [])


class PromotionGateTests(unittest.TestCase):
    def test_complete_match_passes(self):
        manifest = _manifest(runtime={
            "served_frontend_sha256": FRONT_SHA,
            "api_contract_sha256": API_SHA,
            "model_identity": MODEL_ID,
            "deployment_identity": DEPLOY_ID,
        })
        gate = srm.promotion_gate(manifest, _runtime())
        self.assertEqual(gate["decision"], "PASS")
        self.assertEqual(gate["blocking_findings"], [])

    def test_mismatch_blocks(self):
        manifest = _manifest(runtime={
            "served_frontend_sha256": "e" * 64,
            "api_contract_sha256": API_SHA,
            "model_identity": MODEL_ID,
            "deployment_identity": DEPLOY_ID,
        })
        gate = srm.promotion_gate(manifest, _runtime())
        self.assertEqual(gate["decision"], "BLOCKED")
        self.assertTrue(any(f["kind"] == "SERVED_FRONTEND_SHA256_MISMATCH"
                            for f in gate["blocking_findings"]))

    def test_commit_mismatch_blocks(self):
        manifest = _manifest()
        gate = srm.promotion_gate(manifest, _runtime(commit="f" * 40))
        self.assertEqual(gate["decision"], "BLOCKED")

    def test_unknown_never_passes(self):
        manifest = _manifest(status=srm._PLACEHOLDER_STATUS)
        gate = srm.promotion_gate(manifest, _runtime(
            served_frontend_sha256=srm.UNKNOWN))
        self.assertEqual(gate["decision"], "BLOCKED")


class ManifestLoadingTests(unittest.TestCase):
    def test_absent_manifest_fails_closed(self):
        loaded = srm.load_manifest(path=REPO_ROOT / "does-not-exist.json")
        self.assertEqual(loaded["status"], "UNAVAILABLE")
        gate = srm.promotion_gate(loaded, _runtime())
        self.assertEqual(gate["decision"], "BLOCKED")
        self.assertTrue(any(f["kind"] == "MANIFEST_UNAVAILABLE"
                            for f in gate["blocking_findings"]))

    def test_placeholder_blocks(self):
        loaded = srm.load_manifest(path=REPO_ROOT / "release-manifest.json")
        self.assertEqual(loaded["status"], srm._PLACEHOLDER_STATUS)
        gate = srm.promotion_gate(loaded, _runtime())
        self.assertEqual(gate["decision"], "BLOCKED")
        self.assertTrue(any(f["kind"] == "MANIFEST_PLACEHOLDER"
                            for f in gate["blocking_findings"]))

    def test_malformed_manifest_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{not json", encoding="utf-8")
            loaded = srm.load_manifest(path=bad)
            self.assertEqual(loaded["status"], "UNAVAILABLE")


class GeneratorTests(unittest.TestCase):
    def test_missing_reported_honestly(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "api-contract.md"
            doc.write_text("# contract\n", encoding="utf-8")
            manifest, missing = srm.generate_manifest(api_contract_doc_path=doc)
            self.assertEqual(manifest["source"]["git_commit"], srm.UNKNOWN)
            self.assertIn("source.git_commit", missing)
            for key in srm.REQUIRED_RUNTIME_EVIDENCE:
                if key != "api_contract_sha256":
                    self.assertIn("runtime." + key, missing)

    def test_api_contract_hash_measured(self):
        with tempfile.TemporaryDirectory() as tmp:
            doc = Path(tmp) / "api-contract.md"
            doc.write_text("hello", encoding="utf-8")
            manifest, missing = srm.generate_manifest(api_contract_doc_path=doc)
            expected = srm.sha256_file(doc)
            self.assertEqual(manifest["runtime"]["api_contract_sha256"], expected)
            self.assertNotIn("runtime.api_contract_sha256", missing)
            self.assertEqual(manifest["api_contract_source"], "docs/api-contract.md")


if __name__ == "__main__":
    unittest.main()


def test_published_leading_dot_manifest_is_preferred(tmp_path, monkeypatch):
    """#3770: the publisher-generated copy wins over the committed placeholder."""
    import importlib
    import shutil
    module_dir = tmp_path / "pkg"
    module_dir.mkdir()
    shutil.copy(srm.__file__, module_dir / "szl_release_manifest.py")
    monkeypatch.delenv("SZL_RELEASE_MANIFEST_PATH", raising=False)
    monkeypatch.syspath_prepend(str(module_dir))
    spec = importlib.util.spec_from_file_location("_srm_copy", module_dir / "szl_release_manifest.py")
    copy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(copy)
    assert copy.manifest_path().name == "release-manifest.json"
    (module_dir / ".szl-release-manifest.json").write_text("{}", encoding="utf-8")
    assert copy.manifest_path().name == ".szl-release-manifest.json"
    monkeypatch.setenv("SZL_RELEASE_MANIFEST_PATH", str(tmp_path / "x.json"))
    assert copy.manifest_path() == tmp_path / "x.json"
