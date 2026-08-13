from __future__ import annotations

import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / ".github" / "scripts" / "verify_hf_frontdoor_delta.py"
SPEC = importlib.util.spec_from_file_location("verify_hf_frontdoor_delta", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class JsonOpener:
    def __init__(self, payloads: list[object]) -> None:
        self.payloads = [json.dumps(payload).encode() for payload in payloads]

    def __call__(self, _request, timeout: int):
        if timeout != 30 or not self.payloads:
            raise AssertionError("unexpected timeout")
        return io.BytesIO(self.payloads.pop(0))


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(root), *args],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
        encoding="utf-8",
    ).stdout.strip()


class ProtectedFrontdoorAdmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.base = cls.root / "base"
        cls.candidate = cls.root / "candidate"
        cls.base.mkdir()
        git(cls.base, "init")
        git(cls.base, "config", "user.name", "Fixture")
        git(cls.base, "config", "user.email", "fixture@example.test")
        for relative in MODULE.MONITORED_PATHS:
            path = cls.base / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("<!doctype html><html>old</html>\n", encoding="utf-8")
        git(cls.base, "add", ".")
        git(cls.base, "commit", "-m", "base")
        cls.base_sha = git(cls.base, "rev-parse", "HEAD")
        subprocess.run(
            ["git", "clone", "--quiet", str(cls.base), str(cls.candidate)],
            check=True,
        )
        git(cls.candidate, "config", "user.name", "Fixture")
        git(cls.candidate, "config", "user.email", "fixture@example.test")
        target = cls.candidate / "pages" / "console.html"
        target.write_text(
            "<!doctype html><html>Valid UTF-8: — Λ © · ≥</html>\n",
            encoding="utf-8",
        )
        git(cls.candidate, "add", ".")
        git(cls.candidate, "commit", "-m", "candidate")
        cls.seed_head_sha = git(cls.candidate, "rev-parse", "HEAD")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.temp.cleanup()

    def setUp(self) -> None:
        git(self.candidate, "reset", "--hard", self.seed_head_sha)
        git(self.candidate, "clean", "-fdx")
        self.head_sha = self.seed_head_sha
        self.event = self.root / "event.json"
        self.event.write_text(json.dumps(self.event_payload()), encoding="utf-8")

    def event_payload(self, **pull_overrides: object) -> dict[str, object]:
        pull: dict[str, object] = {
            "number": 17,
            "state": "open",
            "base": {
                "ref": "main",
                "sha": self.base_sha,
                "repo": {"full_name": "szl-holdings/a11oy"},
            },
            "head": {
                "ref": "fixture",
                "sha": self.head_sha,
                "repo": {"full_name": "szl-holdings/a11oy"},
            },
        }
        pull.update(pull_overrides)
        return {
            "action": "synchronize",
            "repository": {"full_name": "szl-holdings/a11oy"},
            "pull_request": pull,
        }

    def live_payload(self, **pull_overrides: object) -> dict[str, object]:
        payload = dict(self.event_payload()["pull_request"])
        payload.update(pull_overrides)
        return payload

    def opener(self, live: object | None = None) -> JsonOpener:
        return JsonOpener(
            [
                self.live_payload() if live is None else live,
                {"object": {"sha": self.base_sha}},
                [{"number": 17, "state": "open"}],
            ]
        )

    def test_exact_digest_bound_frontdoor_delta_passes(self) -> None:
        report = MODULE.admit(
            event_path=self.event,
            base_root=self.base,
            candidate_root=self.candidate,
            opener=self.opener(),
        )
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["changed_paths"], ["pages/console.html"])
        self.assertTrue(report["post_merge_publication_required"])
        receipt = report["files"]["pages/console.html"]
        self.assertRegex(receipt["sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(receipt["git_blob"], r"^[0-9a-f]{40}$")

    def test_candidate_controller_or_workflow_change_fails(self) -> None:
        target = self.candidate / ".github" / "scripts" / "verify_hf_frontdoor_delta.py"
        target.parent.mkdir(parents=True)
        target.write_text("print('candidate code')\n", encoding="utf-8")
        git(self.candidate, "add", ".")
        git(self.candidate, "commit", "-m", "replace controller")
        self.head_sha = git(self.candidate, "rev-parse", "HEAD")
        self.event.write_text(json.dumps(self.event_payload()), encoding="utf-8")
        with self.assertRaisesRegex(
            MODULE.AdmissionError, "modifications only|must be isolated"
        ):
            MODULE.admit(
                event_path=self.event,
                base_root=self.base,
                candidate_root=self.candidate,
                opener=self.opener(),
            )

    def test_ordinary_non_frontdoor_delta_passes_without_publication_claim(self) -> None:
        git(self.candidate, "reset", "--hard", self.base_sha)
        ordinary = self.candidate / "docs" / "ordinary.md"
        ordinary.parent.mkdir(parents=True)
        ordinary.write_text("ordinary source change\n", encoding="utf-8")
        git(self.candidate, "add", ".")
        git(self.candidate, "commit", "-m", "ordinary")
        self.head_sha = git(self.candidate, "rev-parse", "HEAD")
        self.event.write_text(json.dumps(self.event_payload()), encoding="utf-8")
        report = MODULE.admit(
            event_path=self.event,
            base_root=self.base,
            candidate_root=self.candidate,
            opener=self.opener(),
        )
        self.assertEqual(report["changed_paths"], [])
        self.assertEqual(report["unmanaged_path_count"], 1)
        self.assertFalse(report["post_merge_publication_required"])

    def test_mixed_managed_and_ordinary_delta_fails(self) -> None:
        ordinary = self.candidate / "docs" / "ordinary.md"
        ordinary.parent.mkdir(parents=True)
        ordinary.write_text("mixed source change\n", encoding="utf-8")
        git(self.candidate, "add", ".")
        git(self.candidate, "commit", "-m", "mixed")
        with self.assertRaisesRegex(MODULE.AdmissionError, "must be isolated"):
            MODULE.classify_delta(self.base, self.candidate)

    def test_more_than_300_paths_cannot_hide_a_managed_delta(self) -> None:
        bulk = self.candidate / "bulk"
        bulk.mkdir()
        for index in range(350):
            (bulk / f"ordinary-{index:03d}.txt").write_text(
                f"{index}\n", encoding="utf-8"
            )
        git(self.candidate, "add", ".")
        git(self.candidate, "commit", "-m", "large mixed delta")
        with self.assertRaisesRegex(MODULE.AdmissionError, "must be isolated"):
            MODULE.classify_delta(self.base, self.candidate)

    def test_fork_head_is_valid_inert_data(self) -> None:
        payload = self.event_payload(
            head={
                "ref": "fixture",
                "sha": self.head_sha,
                "repo": {"full_name": "contributor/a11oy"},
            }
        )
        self.event.write_text(json.dumps(payload), encoding="utf-8")
        live = dict(payload["pull_request"])
        report = MODULE.admit(
            event_path=self.event,
            base_root=self.base,
            candidate_root=self.candidate,
            opener=JsonOpener(
                [
                    live,
                    {"object": {"sha": self.base_sha}},
                    [{"number": 17, "state": "open"}],
                ]
            ),
        )
        self.assertEqual(report["head_repo"], "contributor/a11oy")

    def test_stale_shared_or_retargeted_pr_fails(self) -> None:
        for broken in (
            self.live_payload(head={"sha": "f" * 40, "repo": {"full_name": "szl-holdings/a11oy"}}),
            self.live_payload(state="closed"),
            self.live_payload(base={"ref": "release", "sha": self.base_sha, "repo": {"full_name": "szl-holdings/a11oy"}}),
        ):
            with self.subTest(broken=broken), self.assertRaises(MODULE.AdmissionError):
                MODULE.admit(
                    event_path=self.event,
                    base_root=self.base,
                    candidate_root=self.candidate,
                    opener=self.opener(broken),
                )

    def test_malformed_incomplete_or_wrong_event_fails(self) -> None:
        payloads = (
            [],
            {"action": "synchronize"},
            {**self.event_payload(), "action": "closed"},
            {**self.event_payload(), "repository": {"full_name": "attacker/fork"}},
        )
        for payload in payloads:
            self.event.write_text(json.dumps(payload), encoding="utf-8")
            with self.subTest(payload=payload), self.assertRaises(MODULE.AdmissionError):
                MODULE.parse_event(self.event)

    def test_invalid_utf8_bom_mojibake_and_incomplete_html_fail(self) -> None:
        target = self.candidate / "pages" / "console.html"
        fixtures = (
            b"\xff<html></html>",
            b"\xef\xbb\xbf<html></html>",
            "<html>broken â€” Î› Â©</html>".encode(),
            b"not html",
            b"<html></html>" + b"x" * MODULE.MAX_FILE_BYTES,
        )
        for raw in fixtures:
            target.write_bytes(raw)
            with self.subTest(size=len(raw)), self.assertRaises(MODULE.AdmissionError):
                MODULE.validate_frontdoor(target)

    def test_deletion_and_too_many_paths_fail(self) -> None:
        (self.candidate / "pages" / "console.html").unlink()
        git(self.candidate, "add", "-A")
        git(self.candidate, "commit", "-m", "delete")
        with self.assertRaises(MODULE.AdmissionError):
            MODULE.classify_delta(self.base, self.candidate)

    def test_symlink_frontdoor_fails(self) -> None:
        target = self.candidate / "pages" / "console.html"
        target.unlink()
        try:
            target.symlink_to(self.candidate / "a11oy_landing.html")
        except OSError:
            self.skipTest("symlink creation is unavailable on this host")
        with self.assertRaisesRegex(MODULE.AdmissionError, "not a regular file"):
            MODULE.validate_frontdoor(target)

    def test_stale_protected_main_and_shared_head_fail(self) -> None:
        live = self.live_payload()
        for opener in (
            JsonOpener(
                [live, {"object": {"sha": "f" * 40}}, [{"number": 17, "state": "open"}]]
            ),
            JsonOpener(
                [
                    live,
                    {"object": {"sha": self.base_sha}},
                    [{"number": 17, "state": "open"}, {"number": 18, "state": "open"}],
                ]
            ),
        ):
            with self.assertRaises(MODULE.AdmissionError):
                MODULE.admit(
                    event_path=self.event,
                    base_root=self.base,
                    candidate_root=self.candidate,
                    opener=opener,
                )

    def test_incomplete_head_association_page_fails_closed(self) -> None:
        associations = [{"number": 17, "state": "open"}] + [
            {"number": number, "state": "closed"} for number in range(18, 117)
        ]
        with self.assertRaisesRegex(MODULE.AdmissionError, "not provably complete"):
            MODULE.admit(
                event_path=self.event,
                base_root=self.base,
                candidate_root=self.candidate,
                opener=JsonOpener(
                    [
                        self.live_payload(),
                        {"object": {"sha": self.base_sha}},
                        associations,
                    ]
                ),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
