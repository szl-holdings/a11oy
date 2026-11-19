#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Execute the exact deploy-window script with only curl and python stubbed.

WINDOW_RUN is held byte-equal to hf-sync.yml by the preflight exact-step
contract in test_hf_manual_prerequisites_workflow, so these cases exercise the
shipped shell, not a copy. Nothing here reaches a network or a provider.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tests.test_hf_manual_prerequisites_workflow import WINDOW_ENV, WINDOW_RUN  # noqa: E402

LIVE = "a" * 40
MAIN = "b" * 40
HOLD = "::error::PUBLICATION_HELD_AUTOMATIC_RELEASE_FREEZE"


def run_window(*, stage="RUNNING", dispatch="false", freeze=None, live=None):
    bash = shutil.which("bash")
    python3 = shutil.which("python3")
    if bash is None or python3 is None:
        raise unittest.SkipTest("bash and python3 are required to execute the window script")
    with tempfile.TemporaryDirectory() as work:
        root = Path(work)
        stubs = root / "bin"
        stubs.mkdir()
        calls = root / "python-calls.log"
        served = LIVE if live is None else live
        (stubs / "curl").write_text(
            "#!/bin/sh\nprintf '%s' '{\"build\": {\"revision\": \"" + served + "\"}}'\n")
        (stubs / "python").write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >> " + str(calls) + "\n")
        (stubs / "python3").write_text("#!/bin/sh\nexec " + python3 + " \"$@\"\n")
        for stub in stubs.iterdir():
            stub.chmod(0o755)
        output = root / "github-output"
        output.write_text("")
        env = {"PATH": str(stubs) + os.pathsep + "/usr/bin:/bin", "STAGE": stage,
               "DISPATCH_WINDOW": dispatch, "GITHUB_SHA": MAIN, "GITHUB_OUTPUT": str(output),
               "RUNNER_TEMP": str(root), "CANONICAL_ORIGIN": "https://example.invalid"}
        if freeze is not None:
            env["RELEASE_FREEZE"] = freeze
        done = subprocess.run([bash, "-c", WINDOW_RUN], env=env, capture_output=True,
                              text=True, timeout=60, check=False)
        invoked = calls.read_text() if calls.exists() else ""
        return done.returncode, done.stdout + done.stderr, output.read_text(), invoked


class AutomaticReleaseFreezeTests(unittest.TestCase):
    def test_freeze_is_read_from_its_own_repository_variable(self):
        self.assertEqual(WINDOW_ENV["RELEASE_FREEZE"], "${{ vars.A11OY_AUTOMATIC_RELEASE_FREEZE }}")

    def test_unset_or_false_freeze_keeps_fenced_admission_path(self):
        for freeze in (None, "", "false"):
            with self.subTest(freeze=freeze):
                code, text, _, invoked = run_window(freeze=freeze)
                self.assertEqual(code, 0, text)
                self.assertIn("capture --origin", invoked)
                self.assertIn("--expected-live-sha " + LIVE, invoked)
                self.assertNotIn(HOLD, text)

    def test_any_other_freeze_value_holds_before_capture_or_admission(self):
        for freeze in ("true", "TRUE", "1", "yes", "review-2026-11-19"):
            with self.subTest(freeze=freeze):
                code, text, output, invoked = run_window(freeze=freeze)
                self.assertEqual(code, 1)
                self.assertIn(HOLD, text)
                self.assertEqual(invoked, "")
                self.assertNotIn("open=true", output)

    def test_freeze_leaves_explicit_operator_paths_and_current_main_unchanged(self):
        self.assertEqual(run_window(stage="PAUSED", freeze="true")[0::2], (0, "open=true\n"))
        self.assertEqual(run_window(dispatch="true", freeze="true")[0::2], (0, "open=true\n"))
        self.assertEqual(run_window(freeze="true", live=MAIN)[0::2], (0, "open=false\n"))

    def test_freeze_with_unreadable_live_revision_still_fails_closed(self):
        code, text, output, invoked = run_window(freeze="true", live="")
        self.assertEqual(code, 1)
        self.assertIn("PUBLICATION_BLOCKED_DEPLOY_WINDOW_CLOSED", text)
        self.assertEqual((output, invoked), ("", ""))


if __name__ == "__main__":
    unittest.main(verbosity=2)
