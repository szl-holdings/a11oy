#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Bounded transport recovery; bootstrap evidence is unsigned, never authority."""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

SUPERVISOR_SHA256 = "d09f82606c5b2af2e9c6311ee412b8f8340172400583227bf011534a3b28e41c"
MAX_ATTEMPTS = 4
RETRY_SECONDS = 60
CLEANUP_SECONDS = 15
MAX_TRACKED_PROCESSES = 128
LAYOUTS = {
    "windows-bootstrap.py": "windows-supervisor.py",
    "bootstrap.py": "supervisor.py",
}


class BootstrapBlocked(RuntimeError):
    pass


def supervisor_for(launcher):
    launcher = Path(launcher).absolute()
    name = LAYOUTS.get(launcher.name)
    if name is None or launcher.is_symlink() or not launcher.is_file():
        raise BootstrapBlocked("BOOTSTRAP_LAYOUT_INVALID")
    supervisor = launcher.parent / name
    if supervisor.is_symlink() or not supervisor.is_file():
        raise BootstrapBlocked("SUPERVISOR_PATH_INVALID")
    if hashlib.sha256(supervisor.read_bytes()).hexdigest() != SUPERVISOR_SHA256:
        raise BootstrapBlocked("SUPERVISOR_PIN_MISMATCH")
    return supervisor


def attempt_id(number):
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return f"{stamp}-attempt-{number}-{uuid.uuid4().hex[:12]}"


class _BasicLimits(ctypes.Structure):
    _fields_ = [
        ("ProcessTime", ctypes.c_int64), ("JobTime", ctypes.c_int64),
        ("Flags", wintypes.DWORD), ("MinWS", ctypes.c_size_t),
        ("MaxWS", ctypes.c_size_t), ("ActiveLimit", wintypes.DWORD),
        ("Affinity", ctypes.c_size_t), ("Priority", wintypes.DWORD),
        ("Scheduling", wintypes.DWORD),
    ]


class _IoCounters(ctypes.Structure):
    _fields_ = [(name, ctypes.c_uint64) for name in
                ("ReadOps", "WriteOps", "OtherOps", "ReadBytes", "WriteBytes", "OtherBytes")]


class _ExtendedLimits(ctypes.Structure):
    _fields_ = [
        ("Basic", _BasicLimits), ("Io", _IoCounters),
        ("ProcessMemory", ctypes.c_size_t), ("JobMemory", ctypes.c_size_t),
        ("PeakProcess", ctypes.c_size_t), ("PeakJob", ctypes.c_size_t),
    ]


class _Accounting(ctypes.Structure):
    _fields_ = [
        ("TotalUserTime", ctypes.c_int64), ("TotalKernelTime", ctypes.c_int64),
        ("PeriodUserTime", ctypes.c_int64), ("PeriodKernelTime", ctypes.c_int64),
        ("PageFaults", wintypes.DWORD), ("TotalProcesses", wintypes.DWORD),
        ("ActiveProcesses", wintypes.DWORD), ("TerminatedProcesses", wintypes.DWORD),
    ]


class _ProcessIds(ctypes.Structure):
    _fields_ = [
        ("Assigned", wintypes.DWORD), ("Listed", wintypes.DWORD),
        ("Ids", ctypes.c_size_t * MAX_TRACKED_PROCESSES),
    ]


class _StartupInfo(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD), ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR), ("lpTitle", wintypes.LPWSTR),
        ("dwX", wintypes.DWORD), ("dwY", wintypes.DWORD),
        ("dwXSize", wintypes.DWORD), ("dwYSize", wintypes.DWORD),
        ("dwXCountChars", wintypes.DWORD), ("dwYCountChars", wintypes.DWORD),
        ("dwFillAttribute", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("wShowWindow", wintypes.WORD), ("cbReserved2", wintypes.WORD),
        ("lpReserved2", ctypes.POINTER(wintypes.BYTE)),
        ("hStdInput", wintypes.HANDLE), ("hStdOutput", wintypes.HANDLE),
        ("hStdError", wintypes.HANDLE),
    ]


class _StartupInfoEx(ctypes.Structure):
    _fields_ = [("StartupInfo", _StartupInfo), ("lpAttributeList", ctypes.c_void_p)]


class _ProcessInfo(ctypes.Structure):
    _fields_ = [
        ("hProcess", wintypes.HANDLE), ("hThread", wintypes.HANDLE),
        ("dwProcessId", wintypes.DWORD), ("dwThreadId", wintypes.DWORD),
    ]


def _kernel():
    if os.name != "nt":
        raise BootstrapBlocked("NATIVE_WINDOWS_REQUIRED")
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    handle = wintypes.HANDLE
    pointer = ctypes.c_void_p
    dword = wintypes.DWORD
    signatures = {
        "CreateJobObjectW": ([pointer, wintypes.LPCWSTR], handle),
        "SetInformationJobObject": ([handle, ctypes.c_int, pointer, dword], wintypes.BOOL),
        "QueryInformationJobObject": ([handle, ctypes.c_int, pointer, dword, pointer], wintypes.BOOL),
        "TerminateJobObject": ([handle, wintypes.UINT], wintypes.BOOL),
        "CloseHandle": ([handle], wintypes.BOOL),
        "GetCurrentProcess": ([], handle),
        "OpenProcess": ([dword, wintypes.BOOL, dword], handle),
        "IsProcessInJob": ([handle, handle, ctypes.POINTER(wintypes.BOOL)], wintypes.BOOL),
        "DuplicateHandle": ([handle, handle, handle, ctypes.POINTER(handle),
                             dword, wintypes.BOOL, dword], wintypes.BOOL),
        "InitializeProcThreadAttributeList": ([pointer, dword, dword,
                                               ctypes.POINTER(ctypes.c_size_t)], wintypes.BOOL),
        "UpdateProcThreadAttribute": ([pointer, dword, ctypes.c_size_t, pointer,
                                       ctypes.c_size_t, pointer, pointer], wintypes.BOOL),
        "DeleteProcThreadAttributeList": ([pointer], None),
        "CreateProcessW": ([wintypes.LPCWSTR, wintypes.LPWSTR, pointer, pointer,
                            wintypes.BOOL, dword, pointer, wintypes.LPCWSTR,
                            pointer, ctypes.POINTER(_ProcessInfo)], wintypes.BOOL),
        "WaitForSingleObject": ([handle, dword], dword),
        "GetExitCodeProcess": ([handle, ctypes.POINTER(dword)], wintypes.BOOL),
    }
    for name, (arguments, result) in signatures.items():
        function = getattr(kernel, name)
        function.argtypes = arguments
        function.restype = result
    return kernel


def _require(result):
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())


class _OwnedAttempt:
    """One noninheritable kill-on-close Job, retained until verified cleanup."""

    def __init__(self):
        self.kernel = _kernel()
        self.job = None
        self.process = None
        self.thread = None
        self.pid = None
        self.members = {}
        self.job = self.kernel.CreateJobObjectW(None, None)
        _require(self.job)
        try:
            limits = _ExtendedLimits()
            limits.Basic.Flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE, no breakaway.
            _require(self.kernel.SetInformationJobObject(
                self.job, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
        except BaseException:
            self.kernel.CloseHandle(self.job)
            self.job = None
            raise

    def start(self, command, cwd, stdout, stderr):
        import msvcrt
        attributes = None
        duplicates = []
        attribute_initialized = False
        try:
            with open(os.devnull, "rb") as stdin:
                current = self.kernel.GetCurrentProcess()
                for stream in (stdin, stdout, stderr):
                    duplicate = wintypes.HANDLE()
                    _require(self.kernel.DuplicateHandle(
                        current, wintypes.HANDLE(msvcrt.get_osfhandle(stream.fileno())),
                        current, ctypes.byref(duplicate), 0, True, 2))
                    duplicates.append(duplicate.value)
            inherited = (wintypes.HANDLE * 3)(*duplicates)
            jobs = (wintypes.HANDLE * 1)(self.job)
            size = ctypes.c_size_t()
            self.kernel.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
            if not size.value:
                raise BootstrapBlocked("PROCESS_ATTRIBUTE_SIZE_UNAVAILABLE")
            attributes = ctypes.create_string_buffer(size.value)
            _require(self.kernel.InitializeProcThreadAttributeList(
                attributes, 2, 0, ctypes.byref(size)))
            attribute_initialized = True
            _require(self.kernel.UpdateProcThreadAttribute(
                attributes, 0, 0x00020002, inherited, ctypes.sizeof(inherited), None, None))
            # Windows 10+ assigns this Job before the initial thread can execute.
            # There is deliberately no spawn-then-AssignProcessToJobObject fallback.
            _require(self.kernel.UpdateProcThreadAttribute(
                attributes, 0, 0x0002000D, jobs, ctypes.sizeof(jobs), None, None))
            startup = _StartupInfoEx()
            startup.StartupInfo.cb = ctypes.sizeof(startup)
            startup.StartupInfo.dwFlags = 0x100  # STARTF_USESTDHANDLES
            startup.StartupInfo.hStdInput = duplicates[0]
            startup.StartupInfo.hStdOutput = duplicates[1]
            startup.StartupInfo.hStdError = duplicates[2]
            startup.lpAttributeList = ctypes.cast(attributes, ctypes.c_void_p).value
            info = _ProcessInfo()
            command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
            _require(self.kernel.CreateProcessW(
                command[0], command_line, None, None, True,
                0x08000000 | 0x00080000, None, str(cwd),
                ctypes.byref(startup), ctypes.byref(info)))
            self.process, self.thread, self.pid = info.hProcess, info.hThread, info.dwProcessId
            self.members[self.pid] = self.process
            _require(self.kernel.CloseHandle(self.thread))
            self.thread = None
        finally:
            if attribute_initialized:
                self.kernel.DeleteProcThreadAttributeList(attributes)
            for handle in duplicates:
                _require(self.kernel.CloseHandle(handle))

    def member_ids(self):
        identifiers = _ProcessIds()
        if not self.kernel.QueryInformationJobObject(
                self.job, 3, ctypes.byref(identifiers), ctypes.sizeof(identifiers), None):
            raise BootstrapBlocked("OWNED_JOB_CENSUS_UNAVAILABLE")
        if identifiers.Listed > MAX_TRACKED_PROCESSES:
            raise BootstrapBlocked("OWNED_JOB_CENSUS_LIMIT")
        return tuple(identifiers.Ids[:identifiers.Listed])

    def capture_members(self):
        for pid in self.member_ids():
            if pid in self.members:
                continue
            if len(self.members) >= MAX_TRACKED_PROCESSES:
                raise BootstrapBlocked("OWNED_JOB_CENSUS_LIMIT")
            handle = self.kernel.OpenProcess(0x00100000 | 0x1000, False, pid)
            if not handle:
                continue
            member = wintypes.BOOL()
            try:
                _require(self.kernel.IsProcessInJob(handle, self.job, ctypes.byref(member)))
                if member.value:
                    self.members[pid] = handle
                    handle = None
            finally:
                if handle is not None:
                    _require(self.kernel.CloseHandle(handle))

    def accounting(self):
        accounting = _Accounting()
        _require(self.kernel.QueryInformationJobObject(
            self.job, 1, ctypes.byref(accounting), ctypes.sizeof(accounting), None))
        return accounting

    def wait(self):
        if self.process is None:
            raise BootstrapBlocked("SUPERVISOR_PROCESS_UNAVAILABLE")
        while True:
            self.capture_members()
            result = self.kernel.WaitForSingleObject(self.process, 100)
            if result == 0:
                self.capture_members()
                code = wintypes.DWORD()
                _require(self.kernel.GetExitCodeProcess(self.process, ctypes.byref(code)))
                return code.value
            if result != 258:
                raise BootstrapBlocked("SUPERVISOR_WAIT_FAILED")

    def cleanup(self):
        if self.job is None:
            raise BootstrapBlocked("OWNED_JOB_UNAVAILABLE")
        census_error = None
        try:
            try:
                self.capture_members()
            except Exception as exc:
                census_error = exc
            _require(self.kernel.TerminateJobObject(self.job, 1))
            deadline = time.monotonic() + CLEANUP_SECONDS
            for handle in self.members.values():
                remaining = max(0, int((deadline - time.monotonic()) * 1000))
                if self.kernel.WaitForSingleObject(handle, remaining) != 0:
                    raise BootstrapBlocked("OWNED_MEMBER_CLEANUP_WAIT_FAILED")
            if census_error is not None:
                raise census_error
            while True:
                accounting = self.accounting()
                # Retained handles prevent PID reuse. A missed or late process makes
                # the lifetime census incomplete even if active membership is empty.
                if accounting.TotalProcesses != len(self.members):
                    raise BootstrapBlocked("OWNED_MEMBER_CENSUS_INCOMPLETE")
                if accounting.ActiveProcesses == 0 and not self.member_ids():
                    break
                if time.monotonic() >= deadline:
                    raise BootstrapBlocked("OWNED_JOB_CLEANUP_TIMEOUT")
                time.sleep(0.05)
            for pid, handle in tuple(self.members.items()):
                _require(self.kernel.CloseHandle(handle))
                del self.members[pid]
            self.process = None
            _require(self.kernel.CloseHandle(self.job))
            self.job = None
            return {"process_wait_completed": True, "active_processes": 0, "job_closed": True}
        finally:
            # Unproven cleanup is terminal; closing the sole Job handle still kills members.
            for handle in self.members.values():
                self.kernel.CloseHandle(handle)
            self.members.clear()
            self.process = None
            for attribute in ("thread", "job"):
                handle = getattr(self, attribute)
                if handle is not None:
                    self.kernel.CloseHandle(handle)
                    setattr(self, attribute, None)


def recover(launcher, emit, *, attempt_factory=_OwnedAttempt, sleep=time.sleep):
    launcher = Path(launcher).absolute()
    home = launcher.parent
    logs = home / "logs"
    if logs.is_symlink() or not logs.is_dir():
        raise BootstrapBlocked("LOG_DIRECTORY_INVALID")
    for number in range(1, MAX_ATTEMPTS + 1):
        supervisor = supervisor_for(launcher)
        identity = attempt_id(number)
        emit("attempt", attempt=number, attempt_id=identity,
             supervisor=supervisor.name, supervisor_sha256=SUPERVISOR_SHA256)
        with (logs / (identity + "-supervisor.stdout")).open("xb") as out, (
                logs / (identity + "-supervisor.stderr")).open("xb") as err:
            owned = attempt_factory()
            try:
                owned.start([sys.executable, "-I", "-B", "-u", str(supervisor)], home, out, err)
                emit("started", attempt=number, attempt_id=identity, supervisor_pid=owned.pid)
                code = owned.wait()
            finally:
                cleanup = owned.cleanup()
            emit("closed", attempt=number, attempt_id=identity, exit_code=code, **cleanup)
        if code == 0:
            return 0
        if number == MAX_ATTEMPTS:
            emit("budget_exhausted", attempts=MAX_ATTEMPTS)
            return 1
        emit("backoff", attempt=number, seconds=RETRY_SECONDS)
        sleep(RETRY_SECONDS)
    raise AssertionError("bounded attempt loop did not terminate")


def main():
    if len(sys.argv) != 1:
        return 2
    home = Path(__file__).absolute().parent
    logs = home / "logs"
    try:
        if logs.is_symlink() or not logs.is_dir():
            return 1
        with (logs / (attempt_id(0) + "-bootstrap.jsonl")).open("x", encoding="utf-8") as stream:
            def emit(phase, **fields):
                record = {
                    "schema": "szl.vm-gateway-bootstrap/v1",
                    "at_utc": datetime.now(timezone.utc).isoformat(),
                    "phase": phase, "bootstrap_pid": os.getpid(),
                    "signature_status": "UNSIGNED", "execution_authority": False,
                    "production_acceptance": "BLOCKED", **fields,
                }
                stream.write(json.dumps(record, sort_keys=True, allow_nan=False) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            try:
                return recover(__file__, emit)
            except Exception as exc:
                emit("blocked", error_type=type(exc).__name__)
                return 1
    except Exception:
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
