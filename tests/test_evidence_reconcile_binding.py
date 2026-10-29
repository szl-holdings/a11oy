import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import evidence_reconcile
from tools.evidence_reconcile import reconcile


BASE = {
    "summary": {
        "canonical_main": "a" * 40,
        "runtime_identity": {"source_revision": "b" * 40},
        "acceptance_tests_run": 0,
        "acceptance_disposition": "BLOCKED",
    },
    "manifest": {
        "github_main": {"sha": "a" * 40},
        "latest_hf_sync": [{"headSha": "b" * 40}],
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


def _write(root: Path, overrides=None) -> dict[str, Path]:
    values = json.loads(json.dumps(BASE))
    values.update(overrides or {})
    paths = {}
    for name, value in values.items():
        path = root / f"{name}.json"
        path.write_text(json.dumps(value), encoding="utf-8")
        paths[name] = path
    return paths


def _run(paths: dict[str, Path], **kwargs):
    return reconcile(
        summary_path=paths["summary"],
        manifest_path=paths["manifest"],
        gap_path=paths["preservation_gap"],
        authority_path=paths["authority_review"],
        gpu_path=paths["gpu_preflight"],
        **kwargs,
    )


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


class IdentityComparisonTests(unittest.TestCase):
    def test_missing_main_identities_are_unknown_not_equal(self):
        summary = dict(BASE["summary"])
        del summary["canonical_main"]
        manifest = dict(BASE["manifest"], github_main={})
        with tempfile.TemporaryDirectory() as directory:
            report = _run(_write(Path(directory), {"summary": summary, "manifest": manifest}))
        self.assertFalse(report["protected_main"]["equal"])
        self.assertEqual(report["protected_main"]["status"], "UNKNOWN")
        self.assertEqual(report["binding"]["level"], "UNKNOWN")

    def test_empty_or_non_text_identities_are_unknown(self):
        for left, right in (("", ""), ("   ", "   "), (123, 123), (None, None)):
            summary = dict(BASE["summary"], canonical_main=left)
            manifest = dict(BASE["manifest"], github_main={"sha": right})
            with self.subTest(left=left), tempfile.TemporaryDirectory() as directory:
                report = _run(_write(Path(directory), {"summary": summary, "manifest": manifest}))
                self.assertEqual(report["protected_main"]["status"], "UNKNOWN")
                self.assertFalse(report["protected_main"]["equal"])

    def test_missing_runtime_and_hf_identities_are_unknown(self):
        summary = dict(BASE["summary"], runtime_identity={})
        manifest = dict(BASE["manifest"], latest_hf_sync=[])
        with tempfile.TemporaryDirectory() as directory:
            report = _run(_write(Path(directory), {"summary": summary, "manifest": manifest}))
        self.assertEqual(report["runtime_hf_binding"]["status"], "UNKNOWN")
        self.assertFalse(report["runtime_hf_binding"]["equal"])

    def test_known_identities_report_match_and_mismatch(self):
        manifest = dict(BASE["manifest"], latest_hf_sync=[{"headSha": "c" * 40}])
        with tempfile.TemporaryDirectory() as directory:
            report = _run(_write(Path(directory), {"manifest": manifest}))
        self.assertEqual(report["protected_main"]["status"], "MATCH")
        self.assertTrue(report["protected_main"]["equal"])
        self.assertEqual(report["runtime_hf_binding"]["status"], "MISMATCH")
        self.assertFalse(report["runtime_hf_binding"]["equal"])
        self.assertEqual(report["binding"]["level"], "IDENTITY_MISMATCH")
        self.assertFalse(report["binding"]["authenticated"])


class SingleReadTests(unittest.TestCase):
    def test_reported_digest_is_of_the_bytes_that_were_parsed(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write(Path(directory))
            parsed_digest = _sha(paths["summary"])
            real_loads = json.loads
            replaced = []

            def loads_then_replace(data, *args, **kwargs):
                value = real_loads(data, *args, **kwargs)
                if not replaced:  # swap the first file right after it is parsed
                    replaced.append(True)
                    paths["summary"].write_text('{"replaced": true}', encoding="utf-8")
                return value

            with mock.patch.object(evidence_reconcile.json, "loads", side_effect=loads_then_replace):
                report = _run(paths)
        self.assertTrue(replaced)
        self.assertEqual(report["files"]["summary"]["sha256"], parsed_digest)


class PinnedDigestTests(unittest.TestCase):
    def test_matching_pins_are_reported_but_never_authenticated(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write(Path(directory))
            pins = {name: _sha(path).lower() for name, path in paths.items()}
            report = _run(paths, pinned_digests=pins)
        self.assertEqual({f["digest_status"] for f in report["files"].values()}, {"MATCHED"})
        self.assertEqual(report["binding"]["level"], "PINNED_DIGESTS_MATCHED")
        self.assertFalse(report["binding"]["authenticated"])

    def test_pin_mismatch_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write(Path(directory))
            pins = {name: _sha(path) for name, path in paths.items()}
            pins["manifest"] = "0" * 64
            report = _run(paths, pinned_digests=pins)
        self.assertEqual(report["files"]["manifest"]["digest_status"], "MISMATCHED")
        self.assertEqual(report["files"]["summary"]["digest_status"], "MATCHED")
        self.assertEqual(report["binding"]["level"], "PINNED_DIGEST_MISMATCH")

    def test_partial_pins_stay_local_consistency(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write(Path(directory))
            report = _run(paths, pinned_digests={"summary": _sha(paths["summary"])})
        self.assertEqual(report["files"]["summary"]["digest_status"], "MATCHED")
        self.assertEqual(report["files"]["manifest"]["digest_status"], "NOT_PINNED")
        self.assertEqual(report["binding"]["level"], "LOCAL_CONSISTENCY")

    def test_malformed_or_unknown_pins_are_rejected(self):
        for pins in ({"summary": "abc"}, {"summary": 7}, {"summary": "g" * 64},
                     {"not_an_input": "0" * 64}):
            with self.subTest(pins=pins), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(ValueError):
                    _run(_write(Path(directory)), pinned_digests=pins)


class MalformedInputTests(unittest.TestCase):
    def test_non_object_or_invalid_json_is_rejected(self):
        for text in ("not json", "[1, 2]", '"text"'):
            with self.subTest(text=text), tempfile.TemporaryDirectory() as directory:
                paths = _write(Path(directory))
                paths["summary"].write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    _run(paths)


class CommandLineTests(unittest.TestCase):
    @staticmethod
    def _argv(paths: dict[str, Path], output: Path, *extra: str) -> list[str]:
        return [
            "evidence_reconcile",
            "--summary", str(paths["summary"]),
            "--manifest", str(paths["manifest"]),
            "--preservation-gap", str(paths["preservation_gap"]),
            "--authority-review", str(paths["authority_review"]),
            "--gpu-preflight", str(paths["gpu_preflight"]),
            "--output", str(output),
            *extra,
        ]

    def test_pinned_digest_file_is_applied(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _write(root)
            pins = root / "pins.json"
            pins.write_text(json.dumps({n: _sha(p) for n, p in paths.items()}), encoding="utf-8")
            output = root / "out" / "report.json"
            with mock.patch("sys.argv", self._argv(paths, output, "--pinned-digests", str(pins))), \
                    mock.patch("builtins.print"):
                code = evidence_reconcile.main()
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(report["binding"]["level"], "PINNED_DIGESTS_MATCHED")

    def test_bad_pinned_digest_file_blocks_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _write(root)
            pins = root / "pins.json"
            pins.write_text(json.dumps({"summary": "abc"}), encoding="utf-8")
            output = root / "report.json"
            with mock.patch("sys.argv", self._argv(paths, output, "--pinned-digests", str(pins))), \
                    mock.patch("builtins.print") as printed:
                code = evidence_reconcile.main()
            self.assertEqual(code, 2)
            self.assertFalse(output.exists())
            self.assertIn('"BLOCKED"', printed.call_args[0][0])


if __name__ == "__main__":
    unittest.main()
