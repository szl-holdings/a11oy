#!/usr/bin/env python3
"""Adversarial stdlib tests for immutable HF repository parity admission."""

from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "verify_hf_repository_parity.py"
SPEC = importlib.util.spec_from_file_location("verify_hf_repository_parity", MODULE_PATH)
assert SPEC and SPEC.loader
parity = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(parity)

GITHUB_REF = "a" * 40
HF_REF = "b" * 40
REASON = "Candidate source bytes are intentionally ahead of the deployed Space."


def report_for(accepted: dict[str, str]) -> dict[str, object]:
    findings: list[dict[str, object]] = [
        {
            "kind": "drift",
            "path": path,
            "severity": "warn",
            "reason": reason,
        }
        for path, reason in accepted.items()
    ]
    findings.append(dict(parity.EXPECTED_COMPATIBILITY_WARNING))
    return {
        "status": "ok",
        "error_count": 0,
        "warn_count": len(findings),
        "files_compared": 1184,
        "github_ref": GITHUB_REF,
        "hf_ref": HF_REF,
        "findings": findings,
    }


class ParityAdmissionTest(unittest.TestCase):
    def test_strict_allowlist_snapshot_accepts_normalized_paths(self) -> None:
        raw = json.dumps(
            {"accepted_divergences": {"pages/console.html": REASON}}
        ).encode("utf-8")
        self.assertEqual(
            parity.parse_allowlist_snapshot(raw),
            {"pages/console.html": REASON},
        )

    def test_allowlist_rejects_duplicate_keys_bom_and_unsafe_paths(self) -> None:
        fixtures = (
            b'\xef\xbb\xbf{"accepted_divergences": {}}',
            b'{"accepted_divergences":{"a":"one","a":"two"}}',
            b'{"accepted_divergences":{"../escape":"reason"}}',
            b'{"accepted_divergences":{".well-known/security.txt":"reason"}}',
            b'{"accepted_divergences":{"pages\\\\console.html":"reason"}}',
        )
        for raw in fixtures:
            with self.subTest(raw=raw):
                with self.assertRaises(parity.ParityError):
                    parity.parse_allowlist_snapshot(raw)

    def test_candidate_cannot_broaden_comparator_exclusions(self) -> None:
        safe = json.dumps(
            {
                "ignore_paths": ["console/assets/**"],
                "ignore_extensions": [".png"],
                "accepted_divergences": {"pages/console.html": REASON},
            }
        ).encode("utf-8")
        self.assertEqual(
            parity.parse_allowlist_snapshot(safe),
            {"pages/console.html": REASON},
        )

        attacks = (
            {"ignore_paths": ["**"], "accepted_divergences": {}},
            {"ignore_extensions": [".html"], "accepted_divergences": {}},
            {
                "ignore_paths": ["console/assets/**", "console/assets/**"],
                "accepted_divergences": {},
            },
            {"future_exclusion_policy": ["**"], "accepted_divergences": {}},
        )
        for attack in attacks:
            with self.subTest(attack=attack):
                with self.assertRaises(parity.ParityError):
                    parity.parse_allowlist_snapshot(json.dumps(attack).encode("utf-8"))

    def test_candidate_allowlist_must_be_same_checkout_and_exact_head(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            expected = root / parity.ALLOWLIST_RELATIVE_PATH
            expected.parent.mkdir(parents=True)
            expected.write_text(
                json.dumps({"accepted_divergences": {}}), encoding="utf-8"
            )
            outside = root / "outside.json"
            outside.write_text(json.dumps({"accepted_divergences": {}}), encoding="utf-8")
            with mock.patch.object(parity, "REPO_ROOT", root):
                with self.assertRaises(parity.ParityError):
                    parity.load_candidate_allowlist(
                        outside,
                        github_ref=GITHUB_REF,
                        head_resolver=lambda _: GITHUB_REF,
                    )
                with self.assertRaises(parity.ParityError):
                    parity.load_candidate_allowlist(
                        expected,
                        github_ref=GITHUB_REF,
                        head_resolver=lambda _: "c" * 40,
                    )

    def test_candidate_allowlist_must_match_admitted_commit_blob(self) -> None:
        raw = json.dumps({"accepted_divergences": {}}).encode("utf-8")
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            expected = root / parity.ALLOWLIST_RELATIVE_PATH
            expected.parent.mkdir(parents=True)
            expected.write_bytes(raw)
            with mock.patch.object(parity, "REPO_ROOT", root):
                observed, accepted = parity.load_candidate_allowlist(
                    expected,
                    github_ref=GITHUB_REF,
                    head_resolver=lambda _: GITHUB_REF,
                    blob_resolver=lambda _root, _ref, _path: raw,
                )
                self.assertEqual(observed, raw)
                self.assertEqual(accepted, {})

                expected.write_bytes(b'{"accepted_divergences":{"hidden":"drift"}}')
                with self.assertRaises(parity.ParityError):
                    parity.load_candidate_allowlist(
                        expected,
                        github_ref=GITHUB_REF,
                        head_resolver=lambda _: GITHUB_REF,
                        blob_resolver=lambda _root, _ref, _path: raw,
                    )

    def test_repository_identity_is_canonical(self) -> None:
        parity.validate_repository_identity(
            parity.CANONICAL_GITHUB_REPO,
            parity.CANONICAL_HF_REPO,
        )
        for github_repo, hf_repo in (
            ("attacker/repo", parity.CANONICAL_HF_REPO),
            (parity.CANONICAL_GITHUB_REPO, "attacker/space"),
        ):
            with self.subTest(github_repo=github_repo, hf_repo=hf_repo):
                with self.assertRaises(parity.ParityError):
                    parity.validate_repository_identity(github_repo, hf_repo)

    def test_comparator_consumes_private_snapshot_not_mutated_source(self) -> None:
        original = b'{"accepted_divergences":{"pages/console.html":"reason"}}'
        observed: dict[str, object] = {}

        def runner(command: list[str], *, check: bool) -> None:
            self.assertTrue(check)
            index = command.index("--allow")
            snapshot = Path(command[index + 1])
            observed["path"] = snapshot
            observed["bytes"] = snapshot.read_bytes()

        parity.run_comparator(["python", "comparator.py"], allow_bytes=original, runner=runner)
        self.assertEqual(observed["bytes"], original)
        self.assertFalse(Path(observed["path"]).exists())

    def test_report_must_exactly_match_allowlist_and_reason(self) -> None:
        accepted = {"pages/console.html": REASON}
        parity.validate_report(
            report_for(accepted),
            github_ref=GITHUB_REF,
            hf_ref=HF_REF,
            accepted_divergences=accepted,
        )

        attacks = []
        stale = report_for(accepted)
        stale["findings"] = [dict(parity.EXPECTED_COMPATIBILITY_WARNING)]
        stale["warn_count"] = 1
        attacks.append(stale)

        wrong_reason = report_for(accepted)
        wrong_reason["findings"][0]["reason"] = "different"
        attacks.append(wrong_reason)

        unlisted = report_for(accepted)
        unlisted["findings"].insert(
            0,
            {
                "kind": "drift",
                "path": "pages/new.html",
                "severity": "warn",
                "reason": "unbound",
            },
        )
        unlisted["warn_count"] = 3
        attacks.append(unlisted)

        error_severity = report_for(accepted)
        error_severity["findings"][0]["severity"] = "error"
        attacks.append(error_severity)

        duplicate = report_for(accepted)
        duplicate["findings"].insert(1, dict(duplicate["findings"][0]))
        duplicate["warn_count"] = 3
        attacks.append(duplicate)

        for attack in attacks:
            with self.subTest(attack=attack):
                with self.assertRaises(parity.ParityError):
                    parity.validate_report(
                        attack,
                        github_ref=GITHUB_REF,
                        hf_ref=HF_REF,
                        accepted_divergences=accepted,
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
