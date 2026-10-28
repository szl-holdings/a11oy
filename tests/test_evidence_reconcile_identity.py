#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Identity form, binding level and pin type checks for tools/evidence_reconcile.py."""

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import evidence_reconcile
from tools.evidence_reconcile import compare_identity, reconcile


# The identity sources emit lowercase hex: GitHub's branch API (lowercased by
# scripts/verify_estate_release_train.py), `gh run list --json headSha`, and
# SZL_GIT_SHA from $GITHUB_SHA. Synthetic values keep these tests free of
# real revisions.
MAIN = hashlib.sha1(b"protected-main").hexdigest()
RUNTIME = hashlib.sha1(b"runtime-source").hexdigest()
OTHER = hashlib.sha1(b"other-revision").hexdigest()
MAIN_256 = hashlib.sha256(b"protected-main").hexdigest()
OTHER_256 = hashlib.sha256(b"other-revision").hexdigest()

# "unknown" is the Dockerfile default for SZL_GIT_SHA and "UNKNOWN" is the
# fallback several modules print when it is unset.
PLACEHOLDERS = ("UNKNOWN", "unknown", "null", "None", "main-sha", "HEAD", "0" * 40, "0" * 64)


def _values(main=MAIN, manifest_main=MAIN, runtime=RUNTIME, hf=RUNTIME):
    return {
        "summary": {
            "canonical_main": main,
            "runtime_identity": {"source_revision": runtime},
            "acceptance_tests_run": 0,
            "acceptance_disposition": "BLOCKED",
        },
        "manifest": {
            "github_main": {"sha": manifest_main},
            "latest_hf_sync": [{"headSha": hf}],
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


def _write(root: Path, values) -> dict[str, Path]:
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


def _all_pins(paths: dict[str, Path]) -> dict[str, str]:
    return {name: _sha(path) for name, path in paths.items()}


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


UNKNOWN = {"status": "UNKNOWN", "equal": False}


class IdentityFormTests(unittest.TestCase):
    def test_equal_placeholders_are_unknown_not_match(self):
        for value in PLACEHOLDERS:
            with self.subTest(value=value):
                self.assertEqual(compare_identity(value, value), UNKNOWN)

    def test_equal_placeholders_in_inputs_never_reach_a_matched_level(self):
        for value in ("UNKNOWN", "unknown", "null"):
            values = _values(main=value, manifest_main=value, runtime=value, hf=value)
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                paths = _write(Path(directory), values)
                for pins in (None, _all_pins(paths)):
                    report = _run(paths, pinned_digests=pins)
                    self.assertEqual(report["protected_main"]["status"], "UNKNOWN")
                    self.assertEqual(report["runtime_hf_binding"]["status"], "UNKNOWN")
                    self.assertFalse(report["protected_main"]["equal"])
                    self.assertEqual(report["binding"]["level"], "UNKNOWN")

    def test_non_canonical_hex_is_unknown(self):
        for left, right in (
            (MAIN.upper(), MAIN.upper()),
            (MAIN.upper(), MAIN),
            (" " + MAIN, " " + MAIN),
            (MAIN + "\n", MAIN + "\n"),
            (MAIN[:7], MAIN[:7]),
            (MAIN[:39], MAIN[:39]),
            (MAIN + "0", MAIN + "0"),
            (MAIN_256.upper(), MAIN_256.upper()),
        ):
            with self.subTest(left=left, right=right):
                self.assertEqual(compare_identity(left, right), UNKNOWN)

    def test_identities_of_different_lengths_are_unknown(self):
        self.assertEqual(compare_identity(MAIN, MAIN_256), UNKNOWN)
        self.assertEqual(compare_identity(MAIN_256, MAIN), UNKNOWN)

    def test_lowercase_hex_identities_match_and_mismatch(self):
        self.assertEqual(compare_identity(MAIN, MAIN), {"status": "MATCH", "equal": True})
        self.assertEqual(compare_identity(MAIN, OTHER), {"status": "MISMATCH", "equal": False})
        self.assertEqual(compare_identity(MAIN_256, MAIN_256), {"status": "MATCH", "equal": True})
        self.assertEqual(compare_identity(MAIN_256, OTHER_256),
                         {"status": "MISMATCH", "equal": False})


class BindingLevelTests(unittest.TestCase):
    def test_consistent_identities_with_all_pins_matched(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write(Path(directory), _values())
            report = _run(paths, pinned_digests=_all_pins(paths))
        self.assertEqual(report["protected_main"]["status"], "MATCH")
        self.assertEqual(report["runtime_hf_binding"]["status"], "MATCH")
        self.assertEqual(report["binding"]["level"], "PINNED_DIGESTS_MATCHED")
        self.assertFalse(report["binding"]["authenticated"])

    def test_runtime_drift_with_all_pins_matched_is_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write(Path(directory), _values(hf=OTHER))
            report = _run(paths, pinned_digests=_all_pins(paths))
        self.assertEqual({f["digest_status"] for f in report["files"].values()}, {"MATCHED"})
        self.assertEqual(report["runtime_hf_binding"]["status"], "MISMATCH")
        self.assertEqual(report["binding"]["level"], "IDENTITY_MISMATCH")
        self.assertFalse(report["binding"]["authenticated"])

    def test_protected_main_mismatch_with_all_pins_matched_is_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write(Path(directory), _values(manifest_main=OTHER))
            report = _run(paths, pinned_digests=_all_pins(paths))
        self.assertEqual(report["protected_main"]["status"], "MISMATCH")
        self.assertEqual(report["binding"]["level"], "IDENTITY_MISMATCH")

    def test_identity_mismatch_without_pins_is_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            report = _run(_write(Path(directory), _values(hf=OTHER)))
        self.assertEqual(report["binding"]["level"], "IDENTITY_MISMATCH")

    def test_identity_mismatch_outranks_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            values = _values(main=None, manifest_main=None, hf=OTHER)
            report = _run(_write(Path(directory), values))
        self.assertEqual(report["protected_main"]["status"], "UNKNOWN")
        self.assertEqual(report["runtime_hf_binding"]["status"], "MISMATCH")
        self.assertEqual(report["binding"]["level"], "IDENTITY_MISMATCH")

    def test_pinned_digest_mismatch_outranks_identity_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = _write(Path(directory), _values(hf=OTHER))
            pins = _all_pins(paths)
            pins["manifest"] = "0" * 64
            report = _run(paths, pinned_digests=pins)
        self.assertEqual(report["binding"]["level"], "PINNED_DIGEST_MISMATCH")

    def test_command_line_reports_identity_mismatch_with_matching_pin_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = _write(root, _values(hf=OTHER))
            pins = root / "pins.json"
            pins.write_text(json.dumps(_all_pins(paths)), encoding="utf-8")
            output = root / "out" / "report.json"
            with mock.patch("sys.argv", _argv(paths, output, "--pinned-digests", str(pins))), \
                    mock.patch("builtins.print"):
                code = evidence_reconcile.main()
            report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(report["binding"]["level"], "IDENTITY_MISMATCH")


if __name__ == "__main__":
    unittest.main()
