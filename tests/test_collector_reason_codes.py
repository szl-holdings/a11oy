# SPDX-License-Identifier: Apache-2.0
"""Collector diagnostic reason codes: fixture-only, no network, no secrets.

Every failing path below stops before any HTTP request is sent.
"""
import importlib.util, io, json, os, sys, tempfile, unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
PINS = json.dumps({"schema": "szl.execution-authority-pins/v1", "approval_public_pem": "fixture-a",
                   "approval_key_id": "fixture-approval", "runtime_public_pem": "fixture-r",
                   "runtime_key_id": "fixture-runtime"})


def load():
    spec = importlib.util.spec_from_file_location("collector_reason_test", ROOT / ".github/scripts/collect_execution_readiness.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CollectorReasonCodes(unittest.TestCase):
    def setUp(self):
        self.c = load()
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "never-created"

    def tearDown(self):
        self.tmp.cleanup()

    def run_main(self, runtime_sha, boot, nonce, env):
        argv = ["collector", "--source-sha", "a" * 40, "--runtime-sha", runtime_sha, "--boot-id", boot,
                "--run-nonce", nonce, "--out-dir", str(self.out)]
        err = io.StringIO()
        with mock.patch.object(sys, "argv", argv), mock.patch.dict(os.environ, env, clear=True), redirect_stderr(err):
            code = self.c.main()
        self.assertFalse(self.out.exists())
        result = json.loads(err.getvalue().strip().splitlines()[-1])
        self.assertEqual(code, 2)
        self.assertIs(result["collected"], False)
        self.assertIs(result["execution_authorized"], False)
        self.assertEqual(set(result), {"collected", "error", "execution_authorized"})
        return result

    def test_unset_context_code_unchanged(self):
        out = self.run_main("", "", "", {})
        self.assertEqual(out, {"collected": False, "error": "EXECUTION_CONTEXT_REQUIRED", "execution_authorized": False})

    def test_missing_pins_code_unchanged(self):
        out = self.run_main("b" * 40, "boot", "c" * 64, {})
        self.assertEqual(out["error"], "INDEPENDENT_AUTHORITY_PINS_REQUIRED")

    def test_malformed_pins_is_named_not_masked(self):
        out = self.run_main("b" * 40, "boot", "c" * 64, {"A11OY_EXECUTION_AUTHORITY_PINS_JSON": "{"})
        self.assertEqual(out["error"], "INVALID_JSON")

    def test_gate_revision_rejection_is_named_not_masked(self):
        out = self.run_main("not-a-revision", "boot", "c" * 64, {"A11OY_EXECUTION_AUTHORITY_PINS_JSON": PINS})
        self.assertEqual(out["error"], "EXACT_EXECUTION_REVISIONS_REQUIRED")

    def test_reason_never_echoes_a_secret_value(self):
        secret = "FIXTURE_TENANT_VALUE"
        for exc in (self.c.CollectionBlocked(secret), self.c.gate.CombinedEvidenceError(secret),
                    self.c.gate.acceptance.EvidenceError(secret)):
            self.assertEqual(self.c._safe_reason(exc, ("", secret)), "EXECUTION_EXPORT_COLLECTION_UNAVAILABLE")

    def test_free_text_and_uncoded_errors_stay_masked(self):
        self.assertEqual(self.c._safe_reason(self.c.CollectionBlocked("lower case detail")), "EXECUTION_EXPORT_COLLECTION_UNAVAILABLE")
        self.assertEqual(self.c._safe_reason(RuntimeError("UPPER_CASE_TEXT")), "EXECUTION_EXPORT_COLLECTION_UNAVAILABLE")
        self.assertEqual(self.c._safe_reason(ImportError("x")), "EXECUTION_EXPORT_CLIENT_IMPORT_FAILED")

    def test_bracket_movement_has_fixed_classes_without_releasing_state(self):
        base = {
            "source_revision": "a" * 40,
            "runtime_revision": "b" * 40,
            "runtime_boot_id": "DO_NOT_REPORT_BOOT",
            "storage_epoch": 7,
            "storage_sequence": 11,
            "store_snapshots": {"series_a": "DO_NOT_REPORT_HASH"},
            "series_store_id": "DO_NOT_REPORT_INSTANCE",
            "series_chain_head": "c" * 64,
            "series_receipt_count": 10,
            "series_last_sequence": 10,
        }
        self.assertIsNone(self.c.bracket_drift_reason(base, dict(base)))
        for field, new_value, expected in (
            ("runtime_boot_id", "DO_NOT_REPORT_OTHER_BOOT",
             "BRACKET_RUNTIME_IDENTITY_CHANGED"),
            ("storage_epoch", 8, "BRACKET_STORAGE_FENCE_CHANGED"),
            ("storage_sequence", 12, "BRACKET_STORAGE_CHECKPOINT_CHANGED"),
            ("series_receipt_count", 11, "BRACKET_STORAGE_CHECKPOINT_CHANGED"),
            ("series_chain_head", "d" * 64, "BRACKET_STORAGE_CHECKPOINT_CHANGED"),
            ("store_snapshots", {"series_a": "DO_NOT_REPORT_OTHER_HASH"},
             "BRACKET_STORE_SNAPSHOTS_CHANGED"),
        ):
            with self.subTest(field=field):
                moved = dict(base, **{field: new_value})
                code = self.c.bracket_drift_reason(base, moved)
                self.assertEqual(code, expected)
                self.assertTrue(code.isupper())
                self.assertNotIn("DO_NOT_REPORT", code)
                self.assertEqual(
                    self.c._safe_reason(self.c.CollectionBlocked(code), ("DO_NOT_REPORT",)),
                    code,
                )

    def test_multiple_or_unrecognized_bracket_changes_fail_closed(self):
        before = {
            "source_revision": "a" * 40,
            "runtime_revision": "b" * 40,
            "runtime_boot_id": "boot",
            "storage_epoch": 7,
            "storage_sequence": 11,
            "store_snapshots": {"series_a": "0000"},
            "series_store_id": "store",
            "series_chain_head": "c" * 64,
            "series_receipt_count": 10,
            "series_last_sequence": 10,
        }
        after = dict(before, storage_sequence=12, storage_epoch=9)
        self.assertEqual(self.c.bracket_drift_reason(before, after),
                         "SOURCE_RUNTIME_OR_STORAGE_CHANGED")
        self.assertEqual(self.c.bracket_drift_reason(before, {"extra": "untrusted"}),
                         "SOURCE_RUNTIME_OR_STORAGE_CHANGED")
        self.assertEqual(self.c.bracket_drift_reason(before, None),
                         "SOURCE_RUNTIME_OR_STORAGE_CHANGED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
