#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Lifecycle contracts and credential-free native Job inheritance canaries."""
import ctypes
from ctypes import wintypes
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("gateway_windows_bootstrap", HERE / "windows-bootstrap.py")
bootstrap = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bootstrap)


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.home = Path(self.folder.name)
        (self.home / "logs").mkdir()
        self.launcher = self.home / "windows-bootstrap.py"
        self.launcher.write_text("# fixture launcher\n", encoding="utf-8")
        self.source = (HERE / "windows-supervisor.py").read_bytes()
        (self.home / "windows-supervisor.py").write_bytes(self.source)
        self.events = []
        self.attempts = []
        self.delays = []

    def emit(self, phase, **fields):
        self.events.append((phase, fields))

    def factory(self, codes, *, start_error=False, cleanup_error=False):
        owner = self

        class Attempt:
            def __init__(self):
                self.pid = 100 + len(owner.attempts)
                self.number = len(owner.attempts)
                self.cleaned = False
                owner.attempts.append(self)

            def start(self, command, cwd, out, err):
                self.command, self.cwd, self.out, self.err = command, cwd, out, err
                owner.events.append(("native_start", {"number": self.number}))
                if start_error:
                    raise OSError("synthetic launch error")

            def wait(self):
                owner.events.append(("native_wait", {"number": self.number}))
                return codes[self.number]

            def cleanup(self):
                owner.events.append(("native_cleanup", {"number": self.number}))
                self.cleaned = True
                if cleanup_error:
                    raise bootstrap.BootstrapBlocked("OWNED_JOB_CLEANUP_TIMEOUT")
                return {"process_wait_completed": True, "active_processes": 0, "job_closed": True}

        return Attempt

    def sleep(self, seconds):
        self.assertTrue(self.attempts[-1].cleaned)
        self.assertTrue(self.attempts[-1].out.closed)
        self.assertTrue(self.attempts[-1].err.closed)
        self.delays.append(seconds)
        self.events.append(("sleep", {"seconds": seconds}))

    def run_recovery(self, codes, **options):
        return bootstrap.recover(self.launcher, self.emit,
                                 attempt_factory=self.factory(codes, **options), sleep=self.sleep)

    def test_four_total_attempts_three_delays_and_fresh_logs(self):
        self.assertEqual(self.run_recovery([1, 1, 1, 1]), 1)
        self.assertEqual(len(self.attempts), 4)
        self.assertEqual(self.delays, [60, 60, 60])
        identities = [fields["attempt_id"] for phase, fields in self.events if phase == "attempt"]
        self.assertEqual(len(set(identities)), 4)
        self.assertEqual(len(list((self.home / "logs").glob("*-supervisor.stdout"))), 4)
        phases = [phase for phase, _ in self.events]
        for index, phase in enumerate(phases):
            if phase == "sleep":
                self.assertEqual(phases[index - 2:index], ["closed", "backoff"])
        for attempt in self.attempts:
            self.assertEqual(attempt.command[:4], [sys.executable, "-I", "-B", "-u"])

    def test_clean_exit_still_cleans_and_never_retries(self):
        self.assertEqual(self.run_recovery([0]), 0)
        self.assertEqual(len(self.attempts), 1)
        self.assertTrue(self.attempts[0].cleaned)
        self.assertEqual(self.delays, [])

    def test_failure_then_clean_exit_uses_only_one_retry(self):
        self.assertEqual(self.run_recovery([1, 0]), 0)
        self.assertEqual(len(self.attempts), 2)
        self.assertEqual(self.delays, [60])
        self.assertTrue(all(attempt.cleaned for attempt in self.attempts))

    def test_cleanup_failure_blocks_next_attempt(self):
        with self.assertRaisesRegex(bootstrap.BootstrapBlocked, "CLEANUP_TIMEOUT"):
            self.run_recovery([1], cleanup_error=True)
        self.assertEqual(len(self.attempts), 1)
        self.assertEqual(self.delays, [])
        self.assertTrue(self.attempts[0].out.closed)

    def test_clean_exit_with_cleanup_failure_is_not_success(self):
        with self.assertRaises(bootstrap.BootstrapBlocked):
            self.run_recovery([0], cleanup_error=True)
        self.assertEqual(self.delays, [])

    def test_launch_failure_still_closes_job_without_retry(self):
        with self.assertRaises(OSError):
            self.run_recovery([1], start_error=True)
        self.assertTrue(self.attempts[0].cleaned)
        self.assertEqual(self.delays, [])

    def test_logging_failure_after_launch_cleans_without_retry(self):
        def failed_log(phase, **fields):
            if phase == "started":
                raise OSError("synthetic log failure")
        with self.assertRaises(OSError):
            bootstrap.recover(self.launcher, failed_log,
                              attempt_factory=self.factory([1]), sleep=self.sleep)
        self.assertTrue(self.attempts[0].cleaned)
        self.assertTrue(self.attempts[0].err.closed)
        self.assertEqual(self.delays, [])

    def test_pin_is_rechecked_after_cleanup_before_next_launch(self):
        def change_after_cleanup(seconds):
            self.sleep(seconds)
            (self.home / "windows-supervisor.py").write_bytes(b"changed")
        with self.assertRaisesRegex(bootstrap.BootstrapBlocked, "PIN_MISMATCH"):
            bootstrap.recover(self.launcher, self.emit,
                              attempt_factory=self.factory([1]), sleep=change_after_cleanup)
        self.assertEqual(len(self.attempts), 1)

    def test_both_explicit_filename_layouts(self):
        self.assertEqual(bootstrap.supervisor_for(self.launcher).name, "windows-supervisor.py")
        installed = self.home / "bootstrap.py"
        installed.write_text("# fixture launcher\n", encoding="utf-8")
        (self.home / "supervisor.py").write_bytes(self.source)
        self.assertEqual(bootstrap.supervisor_for(installed).name, "supervisor.py")

    def test_unknown_launcher_name_is_rejected(self):
        unknown = self.home / "other.py"
        unknown.write_text("# fixture launcher\n", encoding="utf-8")
        with self.assertRaisesRegex(bootstrap.BootstrapBlocked, "LAYOUT_INVALID"):
            bootstrap.supervisor_for(unknown)

    def test_missing_supervisor_cannot_fall_back_to_other_layout(self):
        (self.home / "windows-supervisor.py").unlink()
        (self.home / "supervisor.py").write_bytes(self.source)
        with self.assertRaisesRegex(bootstrap.BootstrapBlocked, "PATH_INVALID"):
            bootstrap.supervisor_for(self.launcher)

    def test_pin_mismatch_launches_nothing(self):
        (self.home / "windows-supervisor.py").write_bytes(self.source + b"\n")
        with self.assertRaisesRegex(bootstrap.BootstrapBlocked, "PIN_MISMATCH"):
            self.run_recovery([1])
        self.assertEqual(self.attempts, [])

    def test_invalid_log_directory_launches_nothing(self):
        (self.home / "logs").rmdir()
        with self.assertRaisesRegex(bootstrap.BootstrapBlocked, "LOG_DIRECTORY_INVALID"):
            self.run_recovery([1])
        self.assertEqual(self.attempts, [])


@unittest.skipUnless(os.name == "nt", "native Windows Job canary")
class NativeJobTests(unittest.TestCase):
    def wait_for_file(self, path):
        deadline = time.monotonic() + 10
        while True:
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError):
                if time.monotonic() >= deadline:
                    self.fail("native canary did not publish its nonsecret PID record")
                time.sleep(0.05)

    def held_process(self, kernel, pid):
        kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x00100000 | 0x1000, False, pid)
        self.assertTrue(handle)
        return handle

    def assert_member(self, kernel, process, job):
        kernel.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE,
                                         ctypes.POINTER(wintypes.BOOL)]
        kernel.IsProcessInJob.restype = wintypes.BOOL
        member = wintypes.BOOL()
        self.assertTrue(kernel.IsProcessInJob(process, job, ctypes.byref(member)))
        self.assertTrue(member.value)

    def native_canary(self, nested):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            report = home / "child.json"
            module_path = str(HERE / "windows-bootstrap.py")
            # The only children are inert sleepers. No gateway, network, keys or task changes.
            common = (
                "import ctypes,json,os,subprocess,sys,time\n"
                "from pathlib import Path\n"
                f"report=Path({str(report)!r})\n"
            )
            if nested:
                program = common + (
                    "import importlib.util\n"
                    f"spec=importlib.util.spec_from_file_location('canary_bootstrap',{module_path!r})\n"
                    "mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)\n"
                    "inner=mod._OwnedAttempt()\n"
                    "out=open(report.parent/'inner.stdout','xb');err=open(report.parent/'inner.stderr','xb')\n"
                    "inner.start([sys.executable,'-I','-B','-c','import time;time.sleep(60)'],report.parent,out,err)\n"
                    "report.write_text(json.dumps({'parent':os.getpid(),'child':inner.pid}),encoding='utf-8')\n"
                    "time.sleep(60)\n"
                )
            else:
                program = common + (
                    "child=subprocess.Popen([sys.executable,'-I','-B','-c','import time;time.sleep(60)'])\n"
                    "report.write_text(json.dumps({'parent':os.getpid(),'child':child.pid}),encoding='utf-8')\n"
                    "raise SystemExit(1)\n"
                )
            attempt = bootstrap._OwnedAttempt()
            held = None
            try:
                with (home / "stdout").open("xb") as out, (home / "stderr").open("xb") as err:
                    attempt.start([sys.executable, "-I", "-B", "-c", program], home, out, err)
                    observed = self.wait_for_file(report)
                    self.assertEqual(observed["parent"], attempt.pid)
                    held = self.held_process(attempt.kernel, observed["child"])
                    self.assert_member(attempt.kernel, held, attempt.job)
                    if not nested:
                        self.assertEqual(attempt.wait(), 1)
                        self.assertEqual(attempt.kernel.WaitForSingleObject(held, 0), 258)
                    cleanup = attempt.cleanup()
                    self.assertEqual(cleanup, {"process_wait_completed": True,
                                               "active_processes": 0, "job_closed": True})
                    self.assertEqual(attempt.kernel.WaitForSingleObject(held, 0), 0)
                    self.assertIsNone(attempt.job)
                    self.assertIsNone(attempt.process)
            finally:
                if attempt.job is not None:
                    attempt.cleanup()
                if held is not None:
                    attempt.kernel.CloseHandle(held)

    def test_unobserved_short_lived_member_refuses_cleanup_qualification(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            report = home / "completed-child.json"
            program = (
                "import json,os,subprocess,sys\n"
                "from pathlib import Path\n"
                "child=subprocess.Popen([sys.executable,'-I','-B','-c','pass'])\n"
                "child.wait()\n"
                f"Path({str(report)!r}).write_text(json.dumps({{'child':child.pid}}),encoding='utf-8')\n"
                "raise SystemExit(1)\n"
            )
            attempt = bootstrap._OwnedAttempt()
            try:
                with (home / "stdout").open("xb") as out, (home / "stderr").open("xb") as err:
                    attempt.start([sys.executable, "-I", "-B", "-c", program], home, out, err)
                    self.wait_for_file(report)
                    self.assertEqual(attempt.wait(), 1)
                    with self.assertRaisesRegex(bootstrap.BootstrapBlocked, "CENSUS_INCOMPLETE"):
                        attempt.cleanup()
                    self.assertIsNone(attempt.job)
                    self.assertIsNone(attempt.process)
            finally:
                if attempt.job is not None:
                    attempt.cleanup()

    def test_orphaned_grandchild_is_dead_before_job_closure(self):
        self.native_canary(nested=False)

    def test_nested_job_child_and_grandchild_are_closed(self):
        self.native_canary(nested=True)


class RefusalClassificationTests(unittest.TestCase):
    """Bootstrap #3565 port: pinned refusals classify once, never retry, never leak."""

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.home = Path(self.folder.name)
        (self.home / "logs").mkdir()
        self.launcher = self.home / "windows-bootstrap.py"
        self.launcher.write_text("# fixture launcher\n", encoding="utf-8")
        self.source = (HERE / "windows-supervisor.py").read_bytes()
        (self.home / "windows-supervisor.py").write_bytes(self.source)
        self.events = []
        self.attempts = []
        self.delays = []
        self.refusals = []

    def emit(self, phase, **fields):
        self.events.append((phase, fields))

    def factory(self, codes):
        owner = self

        class Attempt:
            def __init__(self):
                self.number = len(owner.attempts)
                self.pid = 100 + len(owner.attempts)
                owner.attempts.append(self)

            def start(self, command, cwd, out, err):
                if self.number < len(owner.refusals) and owner.refusals[self.number]:
                    err.write(owner.refusals[self.number].encode("utf-8"))

            def wait(self):
                return codes[self.number]

            def cleanup(self):
                return {"process_wait_completed": True,
                        "active_processes": 0, "job_closed": True}

        return Attempt

    def sleep(self, seconds):
        self.delays.append(seconds)
        self.events.append(("sleep", {"seconds": seconds}))

    def run_recovery(self, codes, refusals):
        self.refusals = refusals
        return bootstrap.recover(self.launcher, self.emit,
                                 attempt_factory=self.factory(codes), sleep=self.sleep)

    def assert_no_refusal_text_leaked(self, message):
        for phase, fields in self.events:
            blob = json.dumps(fields)
            self.assertNotIn(message, blob)
            self.assertNotIn("fixture-private", blob)

    def test_known_refusal_classifies_once_and_never_retries(self):
        for message, code in {
            "Pinned source mismatch": "SOURCE_PIN_MISMATCH",
            "Pinned SSH configuration mismatch": "SSH_CONFIG_PIN_MISMATCH",
            "Existing listener preserved; startup refused": "EXISTING_LISTENER_PRESERVED",
            "Invalid private gateway credential": "INVALID_GATEWAY_CREDENTIAL",
        }.items():
            with self.subTest(code=code):
                self.events = []
                self.attempts = []
                self.delays = []
                self.assertEqual(self.run_recovery([1], [message]), 1)
                self.assertEqual(len(self.attempts), 1)
                self.assertEqual(self.delays, [])
                refusals = [f for phase, f in self.events if phase == "refusal"]
                self.assertEqual(len(refusals), 1)
                self.assertEqual(refusals[0]["failure_code"], code)
                self.assertIs(refusals[0]["signed"], False)
                self.assertEqual(refusals[0]["retries_remaining"], 3)
                self.assert_no_refusal_text_leaked(message)

    def test_unclassified_failure_still_spends_the_full_budget(self):
        self.assertEqual(
            self.run_recovery([1, 1, 1, 1],
                               ["Traceback (most recent call last):",
                                "fixture-private-value-must-not-appear", "", ""]), 1)
        self.assertEqual(len(self.attempts), 4)
        self.assertEqual(self.delays, [60, 60, 60])
        self.assertEqual(
            [phase for phase, _ in self.events if phase == "refusal"], [])
        self.assert_no_refusal_text_leaked("fixture-private")

    def test_clean_exit_emits_no_refusal_record(self):
        self.assertEqual(self.run_recovery([0], [""]), 0)
        self.assertEqual(
            [phase for phase, _ in self.events if phase == "refusal"], [])


if __name__ == "__main__":
    unittest.main()
