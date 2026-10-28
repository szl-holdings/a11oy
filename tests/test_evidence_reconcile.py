import json
import tempfile
import unittest
from pathlib import Path

from tools.evidence_reconcile import reconcile


class EvidenceReconciliationTests(unittest.TestCase):
    def _inputs(self, root: Path) -> dict[str, Path]:
        values = {
            "summary": {
                "canonical_main": "main-sha",
                "runtime_identity": {"source_revision": "runtime-sha"},
                "acceptance_tests_run": 0,
                "acceptance_disposition": "BLOCKED",
            },
            "manifest": {
                "github_main": {"sha": "main-sha"},
                "latest_hf_sync": [{"headSha": "hf-sha"}],
            },
            "preservation_gap": {"blocker": "REAL_POST_RESTART_VERIFIER_NOT_WIRED"},
            "authority_review": {
                "live_acceptance": "NOT RUN",
                "execution_authorized": False,
                "runtime_admission": "BLOCKED",
                "storage_admission": "BLOCKED",
            },
            "gpu_preflight": {
                "gpu_allocation_admitted": False,
                "workload_launched": False,
                "vm_mutations": False,
            },
        }
        paths = {}
        for name, value in values.items():
            path = root / f"{name}.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            paths[name] = path
        return paths

    def test_reconciles_without_authority_or_provider_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self._inputs(Path(directory))
            report = reconcile(
                summary_path=paths["summary"],
                manifest_path=paths["manifest"],
                gap_path=paths["preservation_gap"],
                authority_path=paths["authority_review"],
                gpu_path=paths["gpu_preflight"],
            )
        self.assertEqual(report["evidence_class"], "MEASURED")
        self.assertTrue(report["protected_main"]["equal"])
        self.assertFalse(report["runtime_hf_binding"]["equal"])
        self.assertFalse(report["authority"]["execution_authorized"])
        self.assertEqual(report["acceptance"]["live_status"], "NOT RUN")
        self.assertEqual(report["provider_writes"], 0)

    def test_missing_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self._inputs(Path(directory))
            paths["summary"].unlink()
            with self.assertRaises(FileNotFoundError):
                reconcile(
                    summary_path=paths["summary"],
                    manifest_path=paths["manifest"],
                    gap_path=paths["preservation_gap"],
                    authority_path=paths["authority_review"],
                    gpu_path=paths["gpu_preflight"],
                )

    def test_symlink_input_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = self._inputs(Path(directory))
            alias = Path(directory) / "alias.json"
            try:
                alias.symlink_to(paths["summary"])
            except (OSError, NotImplementedError):
                self.skipTest("symlinks unavailable on this host")
            paths["summary"] = alias
            with self.assertRaises(FileNotFoundError):
                reconcile(
                    summary_path=paths["summary"],
                    manifest_path=paths["manifest"],
                    gap_path=paths["preservation_gap"],
                    authority_path=paths["authority_review"],
                    gpu_path=paths["gpu_preflight"],
                )


if __name__ == "__main__":
    unittest.main()
