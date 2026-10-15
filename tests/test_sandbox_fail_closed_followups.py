#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Fail-closed tests for the two code paths that used to claim isolation without
enforcing it: the persistent governed kernel and the orchestrator's shell_exec.

Invariant (the same as the hardened engine, tests/test_code_engine_mandatory_limits.py):
every mandatory child rlimit (CPU, AS, CORE, FSIZE, NPROC) is applied and read back
in the child before exec, the child runs in a per-run user + network namespace and
attests it before any user input reaches it, and if any of that cannot be
established nothing runs and the result says ``execution_attempted=False``.

Both paths reuse the engine's helpers (``_plan_mandatory_rlimits``,
``_apply_mandatory_rlimits``, ``_parent_identity``, ``_ATTEST_SRC``,
``_attestation``, ``_launch``); a11oy_code_engine.py is byte-locked shared source,
so it is imported, never copied, and these tests patch the engine module.

Safety of this module: ``subprocess.Popen`` and ``subprocess.run`` are replaced by
fakes that model CPython's fork -> preexec_fn -> exec contract without creating a
process, and the ``resource`` module is replaced by an inert fake, so no real
process starts and no real limit changes. The one exception is
``test_real_host_kernel_*``: on a Linux host that permits the isolation it starts a
real attested worker and runs an inert arithmetic cell; elsewhere it asserts the
refusal shape instead.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_TMP = tempfile.mkdtemp(prefix="a11oy-sandbox-followups-")
os.environ.setdefault("A11OY_CODE_DB", str(Path(_TMP) / "code.db"))
os.environ.setdefault("A11OY_CODE_SANDBOX", str(Path(_TMP) / "sandbox"))
os.environ.setdefault("A11OY_REACT_DB", str(Path(_TMP) / "react.sqlite3"))

import a11oy_code_engine as engine  # noqa: E402
import a11oy_code_orchestrator as orchestrator  # noqa: E402
import a11oy_governed_kernel as gk  # noqa: E402

INF = -1
MIB = 1024 * 1024
MANDATORY = ("RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_CORE", "RLIMIT_FSIZE", "RLIMIT_NPROC")
_IDS = {"RLIMIT_CPU": 0, "RLIMIT_FSIZE": 1, "RLIMIT_CORE": 4, "RLIMIT_NPROC": 6, "RLIMIT_AS": 9}
FAKE_UNSHARE = "/usr/bin/unshare"
TOKEN = "SZL_NETNS_READY"
PARENT = {"uid": 1000, "net": "net:[4026531833]", "user": "user:[4026531837]"}
WANT = [PARENT["net"], PARENT["user"], str(PARENT["uid"])]
UNSHARE_PREFIX = [FAKE_UNSHARE, "--user", "--map-current-user", "--net", "--"]


class FakeResource:
    """Inert stand-in for the POSIX ``resource`` module. Never touches real limits."""

    RLIM_INFINITY = INF

    def __init__(self, *, missing=(), setrlimit_raises=(), not_in_effect=()):
        for name, rid in _IDS.items():
            if name not in missing:
                setattr(self, name, rid)
        self._names = {rid: name for name, rid in _IDS.items()}
        self.limits = {rid: (INF, INF) for rid in _IDS.values()}
        self.setrlimit_raises = set(setrlimit_raises)
        self.not_in_effect = set(not_in_effect)
        self.set_calls = []

    def getrlimit(self, rid):
        return self.limits[rid]

    def setrlimit(self, rid, limits):
        name = self._names[rid]
        self.set_calls.append((name, tuple(limits)))
        if name in self.setrlimit_raises:
            raise ValueError("simulated setrlimit failure for %s" % name)
        if name in self.not_in_effect:
            return  # reports success, but the limit does not take effect
        self.limits[rid] = tuple(limits)


def good_attestation(want):
    return {"net": "net:[4026533469]", "user": "user:[4026533468]",
            "uid": int(want[2]), "euid": int(want[2]), "uid_map": [want[2], want[2], "1"],
            "cap_eff": "0000000000000000", "cap_prm": "0000000000000000",
            "fork": "refused:11", "ok": True}


def attestation_line(want, overrides=None) -> str:
    marker = good_attestation(want)
    marker.update(overrides or {})
    return TOKEN + " " + json.dumps(marker, sort_keys=True) + "\n"


class _Stdin:
    def __init__(self, worker):
        self.worker = worker

    def write(self, data):
        self.worker.cells.append(json.loads(data))
        self.worker.out.put(json.dumps({"ok": True, "stdout": "2\n", "stderr": "",
                                        "vars": {}, "new_or_changed": []}) + "\n")

    def flush(self):
        pass


class _Stdout:
    def __init__(self, worker):
        self.worker = worker

    def readline(self):
        return self.worker.out.get(timeout=5)


class FakeWorker:
    """A text-mode persistent worker: first line is its attestation, then one JSON
    result line per command written to stdin."""

    def __init__(self, first_line):
        self.cells = []
        self.killed = False
        self.out = queue.Queue()
        self.out.put(first_line)
        self.stdin, self.stdout = _Stdin(self), _Stdout(self)
        self.pid = 4242
        self.returncode = None

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        return self.returncode


class KernelLauncher:
    """Models CPython's POSIX Popen contract for the kernel worker: fork, then
    preexec_fn in the child (raising aborts before exec), then exec."""

    def __init__(self):
        self.calls, self.execs, self.workers = [], [], []
        self.first_line = None  # None = a good attestation for the argv's WANT
        self.overrides = None

    def popen(self, args, **kwargs):
        self.calls.append({"args": list(args), **kwargs})
        hook = kwargs.get("preexec_fn")
        if hook is not None:
            try:
                hook()
            except Exception as exc:
                raise subprocess.SubprocessError("Exception occurred in preexec_fn.") from exc
        self.execs.append(list(args))
        line = (self.first_line if self.first_line is not None
                else attestation_line(list(args)[-3:], self.overrides))
        worker = FakeWorker(line)
        self.workers.append(worker)
        return worker


def _no_run(*_a, **_k):
    raise AssertionError("subprocess.run must never be reached: every launch is gated")


@pytest.fixture(autouse=True)
def no_real_processes(monkeypatch):
    monkeypatch.setattr(subprocess, "run", _no_run)


def _install(monkeypatch, res, *, posix=True, identity=None):
    monkeypatch.setattr(engine, "_IS_POSIX", posix)
    monkeypatch.setattr(engine, "resource", res)
    monkeypatch.setattr(engine, "_UNSHARE", FAKE_UNSHARE if posix else None)
    found = (dict(PARENT), None) if identity is None else identity
    monkeypatch.setattr(engine, "_parent_identity", lambda: found)
    return res


@pytest.fixture
def kernel_launcher(monkeypatch):
    fake = KernelLauncher()
    monkeypatch.setattr(gk.subprocess, "Popen", fake.popen)
    return fake


def _assert_kernel_refused(out):
    assert out["ok"] is False
    assert out["executed"] is False
    assert out["execution_attempted"] is False
    assert out["execution_state"] == "UNAVAILABLE"
    assert out["stdout"] == ""
    assert out["isolation"] == gk.REFUSED_ISOLATION


# --------------------------------------------------------------------------
# Governed kernel: every mandatory limit is applied in the child or nothing runs.
# --------------------------------------------------------------------------
def test_kernel_hook_is_the_engines_and_raises_instead_of_swallowing():
    """Regression: _child_limits used to wrap every setrlimit in `except Exception:
    pass`, so a worker could run with no memory or CPU limit at all."""
    plan = [(n, _IDS[n], (0, 0)) for n in MANDATORY]
    raising = FakeResource(setrlimit_raises=("RLIMIT_AS",))
    with pytest.raises(ValueError, match="RLIMIT_AS"):
        gk._child_limits(raising, plan)()
    silent = FakeResource(not_in_effect=("RLIMIT_CORE",))
    with pytest.raises(OSError, match="RLIMIT_CORE is not in effect"):
        gk._child_limits(silent, plan)()


@pytest.mark.parametrize("name", MANDATORY)
def test_kernel_setrlimit_failure_never_starts_a_worker(monkeypatch, kernel_launcher, name):
    res = _install(monkeypatch, FakeResource(setrlimit_raises=(name,)))
    k = gk.GovernedKernel("rq-limit")

    out = k.exec_cell("print(1 + 1)")

    _assert_kernel_refused(out)
    assert out["error"] == engine._LIMIT_HOOK_FAILED_ERROR
    assert len(kernel_launcher.calls) == 1 and kernel_launcher.execs == []
    assert res.set_calls[-1][0] == name
    assert k.alive() is False and k.status()["attested"] is False
    assert k.status()["refusal"] == engine._LIMIT_HOOK_FAILED_ERROR


@pytest.mark.parametrize("name", MANDATORY)
def test_kernel_limit_not_in_effect_never_starts_a_worker(monkeypatch, kernel_launcher, name):
    _install(monkeypatch, FakeResource(not_in_effect=(name,)))

    out = gk.GovernedKernel("rq-readback").exec_cell("print(1 + 1)")

    _assert_kernel_refused(out)
    assert out["error"] == engine._LIMIT_HOOK_FAILED_ERROR
    assert kernel_launcher.execs == []


@pytest.mark.parametrize("name", MANDATORY)
def test_kernel_unsupported_limit_refuses_before_any_process(monkeypatch, kernel_launcher, name):
    res = _install(monkeypatch, FakeResource(missing=(name,)))

    out = gk.GovernedKernel("rq-missing").exec_cell("print(1 + 1)")

    _assert_kernel_refused(out)
    assert out["error"] == ("sandbox unavailable: mandatory rlimit %s is not supported on "
                            "this platform" % name)
    assert kernel_launcher.calls == [] and res.set_calls == []


@pytest.mark.parametrize("posix, res", [(True, None), (False, FakeResource())])
def test_kernel_without_isolation_prerequisites_refuses(monkeypatch, kernel_launcher, posix, res):
    _install(monkeypatch, res, posix=posix)

    out = gk.GovernedKernel("rq-prereq").exec_cell("print(1 + 1)")

    _assert_kernel_refused(out)
    assert out["error"] == "fixed sandbox isolation prerequisites unavailable"
    assert kernel_launcher.calls == []


def test_kernel_root_server_is_refused(monkeypatch, kernel_launcher):
    reason = "sandbox unavailable: the server runs as root; test"
    _install(monkeypatch, FakeResource(), identity=(None, reason))

    out = gk.GovernedKernel("rq-root").exec_cell("print(1 + 1)")

    _assert_kernel_refused(out)
    assert out["error"] == reason
    assert kernel_launcher.calls == []


@pytest.mark.parametrize("override, problem", [
    ({"net": PARENT["net"]}, "no new network namespace"),
    ({"user": PARENT["user"]}, "no new user namespace"),
    ({"fork": "allowed"}, "fork() was not refused with EAGAIN"),
    ({"cap_eff": "000001ffffffffff"}, "the child holds capabilities (cap_eff)"),
    ({"uid": 1001}, "the child does not run as the server's own uid"),
    ({"ok": False}, "the child's own isolation self-check failed"),
])
def test_kernel_worker_that_fails_attestation_never_receives_a_cell(
        monkeypatch, kernel_launcher, override, problem):
    _install(monkeypatch, FakeResource())
    kernel_launcher.overrides = override

    out = gk.GovernedKernel("rq-attest").exec_cell("print(1 + 1)")

    _assert_kernel_refused(out)
    assert "did not attest" in out["error"]
    assert problem in out["stderr"]
    worker = kernel_launcher.workers[0]
    assert worker.killed is True
    assert worker.cells == []


def test_kernel_worker_without_any_attestation_line_is_refused(monkeypatch, kernel_launcher):
    _install(monkeypatch, FakeResource())
    kernel_launcher.first_line = ""  # unshare(1) failed before exec'ing python: EOF

    out = gk.GovernedKernel("rq-eof").exec_cell("print(1 + 1)")

    _assert_kernel_refused(out)
    assert "the child wrote no isolation attestation" in out["stderr"]
    assert kernel_launcher.workers[0].cells == []


def test_kernel_runs_cells_only_in_an_attested_worker_under_every_limit(monkeypatch, kernel_launcher):
    res = _install(monkeypatch, FakeResource())
    k = gk.GovernedKernel("rq-ok", mem_mb=1024)

    out = k.exec_cell("print(1 + 1)")

    assert out["ok"] is True
    assert out["execution_attempted"] is True
    assert out["isolation"] == gk.ISOLATION_LABEL
    assert out["stdout"] == "2\n"
    assert res.set_calls == [("RLIMIT_CPU", (gk.WORKER_CPU_S, gk.WORKER_CPU_S)),
                             ("RLIMIT_AS", (1024 * MIB, 1024 * MIB)),
                             ("RLIMIT_CORE", (0, 0)),
                             ("RLIMIT_FSIZE", (0, 0)),
                             ("RLIMIT_NPROC", (0, 0))]
    call = kernel_launcher.calls[0]
    assert call["args"][:9] == UNSHARE_PREFIX + [sys.executable, "-I", "-S", "-c"]
    assert call["args"][-3:] == WANT
    # The engine's attestation is the worker's first act, ahead of the driver loop.
    assert call["args"][9].startswith(engine._ATTEST_SRC)
    assert "def main():" in call["args"][9][len(engine._ATTEST_SRC):]
    assert call["env"]["OPENBLAS_NUM_THREADS"] == "1"
    assert not any(key.startswith(("HF_", "A11OY_", "SZL_")) for key in call["env"])
    assert kernel_launcher.workers[0].cells == [{"op": "exec", "code": "print(1 + 1)"}]
    status = k.status()
    assert status["attested"] is True and status["refusal"] is None
    assert status["limits"]["mandatory_rlimits"] == list(MANDATORY)


def test_kernel_isolation_labels_claim_only_what_is_enforced():
    for label in (gk.ISOLATION_LABEL, gk.REFUSED_ISOLATION):
        low = label.lower()
        assert "network disabled" not in low
        assert "full seccomp" not in low and "tower/uds pod" not in low
    low = gk.ISOLATION_LABEL.lower()
    for needle in ("user + network namespace", "attested", "nproc", "fail closed",
                   "no seccomp", "filesystem", "non-root uid"):
        assert needle in low
    doc = (gk.__doc__ or "").lower()
    assert "cannot fork a network helper" not in doc


def _loopback_listener():
    import socket

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)
    return srv


def test_real_host_kernel_attests_or_refuses_honestly():
    """No fakes: on a Linux host that permits unprivileged user + network
    namespaces, a real worker attests and runs inert cells, and the network
    boundary is the namespace itself: the raw ``_socket`` module (which the
    in-process monkeypatch does not cover) cannot reach a listener on the
    server's own loopback. Anywhere else the kernel refuses with
    execution_attempted=False and never runs the cell."""
    k = gk.GovernedKernel(gk.new_run_id(), timeout_s=20)
    srv = _loopback_listener()
    try:
        out = k.exec_cell("x = 6 * 7\nprint(x)")
        if out.get("execution_attempted") is False:
            _assert_kernel_refused(out)
            pytest.skip("host refuses kernel isolation (honest refusal): %s" % out["error"])
        assert out["ok"] is True, out
        assert out["stdout"].strip() == "42"
        assert out["isolation"] == gk.ISOLATION_LABEL
        assert k.status()["attested"] is True
        probe = k.exec_cell(
            "_o = __import__('os')\n"
            "print(_o.readlink('/proc/self/ns/net'))\n"
            "_r = __import__('_socket')\n"
            "_c = _r.socket(_r.AF_INET, _r.SOCK_STREAM)\n"
            "_c.settimeout(2)\n"
            "try:\n"
            "    _c.connect(('127.0.0.1', %d))\n"
            "    print('CONNECTED')\n"
            "except OSError as e:\n"
            "    print('BLOCKED', e.errno)\n" % srv.getsockname()[1])
        assert probe["ok"] is True, probe
        ns_line, verdict = probe["stdout"].strip().splitlines()
        assert ns_line != os.readlink("/proc/self/ns/net")
        assert verdict.startswith("BLOCKED"), probe["stdout"]
        assert k.exec_cell("print(x)")["stdout"].strip() == "42"  # state persisted
    finally:
        srv.close()
        k.kill()


# --------------------------------------------------------------------------
# shell_exec: "no network" is now enforced by the engine's attested namespace.
# --------------------------------------------------------------------------
class ShellLauncher:
    """Bytes-mode, single-shot child for engine._launch, modelling the same
    fork -> preexec_fn -> exec contract."""

    def __init__(self):
        self.calls, self.execs = [], []
        self.overrides = None
        self.no_attestation = False

    def popen(self, args, **kwargs):
        self.calls.append({"args": list(args), **kwargs})
        hook = kwargs.get("preexec_fn")
        if hook is not None:
            try:
                hook()
            except Exception as exc:
                raise subprocess.SubprocessError("Exception occurred in preexec_fn.") from exc
        self.execs.append(list(args))
        return _ShellProc(self, list(args))


class _ShellProc:
    def __init__(self, launcher, args):
        self.launcher, self.args, self.returncode = launcher, args, None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def kill(self):
        pass

    def communicate(self, timeout=None):
        if self.launcher.no_attestation:
            self.returncode = 1
            return b"", b"unshare: unshare failed: Operation not permitted\n"
        want = self.args[self.args.index("-c") + 2:self.args.index("-c") + 5]
        line = attestation_line(want, self.launcher.overrides).encode()
        if json.loads(line.split(b" ", 1)[1])["ok"] is not True:
            self.returncode = 97
            return line, b""
        self.returncode = 0
        return line + b"listing\n", b""


@pytest.fixture
def shell_launcher(monkeypatch):
    fake = ShellLauncher()
    monkeypatch.setattr(engine.subprocess, "Popen", fake.popen)
    monkeypatch.setattr(shutil, "which", lambda name, path=None: "/usr/bin/" + name)
    return fake


def _assert_shell_refused(out):
    assert out["execution_attempted"] is False
    assert out["execution_state"] == "UNAVAILABLE"
    assert out["stdout"] == ""
    assert out["isolation"] == orchestrator.SHELL_REFUSED_ISOLATION


@pytest.mark.parametrize("posix, res", [(True, None), (False, FakeResource())])
def test_shell_without_network_namespace_never_runs(monkeypatch, shell_launcher, posix, res):
    """Regression: shell_exec claimed 'no network' and ran the command with plain
    subprocess.run in the server's own network namespace."""
    _install(monkeypatch, res, posix=posix)

    out = orchestrator._tool_shell("ls -la")

    _assert_shell_refused(out)
    assert out["error"] == "fixed sandbox isolation prerequisites unavailable"
    assert shell_launcher.calls == []


@pytest.mark.parametrize("name", MANDATORY)
def test_shell_limit_failure_never_runs(monkeypatch, shell_launcher, name):
    _install(monkeypatch, FakeResource(setrlimit_raises=(name,)))

    out = orchestrator._tool_shell("ls -la")

    _assert_shell_refused(out)
    assert out["error"] == engine._LIMIT_HOOK_FAILED_ERROR
    assert shell_launcher.execs == []


def test_shell_root_server_is_refused(monkeypatch, shell_launcher):
    reason = "sandbox unavailable: the server runs as root; test"
    _install(monkeypatch, FakeResource(), identity=(None, reason))

    out = orchestrator._tool_shell("ls")

    _assert_shell_refused(out)
    assert out["error"] == reason
    assert shell_launcher.calls == []


@pytest.mark.parametrize("override", [{"net": PARENT["net"]}, {"fork": "allowed", "ok": False},
                                      {"ok": False}])
def test_shell_child_that_fails_attestation_never_execs_the_command(
        monkeypatch, shell_launcher, override):
    _install(monkeypatch, FakeResource())
    shell_launcher.overrides = override

    out = orchestrator._tool_shell("cat notes.txt")

    if override.get("ok") is False:
        _assert_shell_refused(out)
        assert "did not attest" in out["error"]
    else:
        # The child's own self-check passed (so it exec'd), but the parent cannot
        # confirm it: reported as executed WITHOUT the isolation claim.
        assert out["execution_attempted"] is True
        assert out["execution_state"] == "UNVERIFIED"
        assert out["isolation"].startswith("UNVERIFIED")
        assert "no new network namespace" in out["error"]


def test_shell_without_attestation_line_is_refused(monkeypatch, shell_launcher):
    _install(monkeypatch, FakeResource())
    shell_launcher.no_attestation = True

    out = orchestrator._tool_shell("ls")

    _assert_shell_refused(out)
    assert "Operation not permitted" in out["stderr"]


def test_shell_runs_in_the_attested_namespace_under_every_limit(monkeypatch, shell_launcher):
    res = _install(monkeypatch, FakeResource())

    out = orchestrator._tool_shell("ls -la")

    assert out["execution_attempted"] is True
    assert out["code"] == 0
    assert out["stdout"] == "listing\n"  # the attestation line is stripped
    assert TOKEN not in out["stdout"]
    assert out["isolation"] == orchestrator.SHELL_ISOLATION
    assert res.set_calls == [("RLIMIT_CPU", (30, 30)), ("RLIMIT_AS", (256 * MIB, 256 * MIB)),
                             ("RLIMIT_CORE", (0, 0)), ("RLIMIT_FSIZE", (0, 0)),
                             ("RLIMIT_NPROC", (0, 0))]
    args = shell_launcher.calls[0]["args"]
    assert args == UNSHARE_PREFIX + [sys.executable, "-I", "-S", "-c",
                                     engine._ATTEST_SRC + orchestrator._SHELL_EXEC_STUB,
                                     *WANT, "/usr/bin/ls", "-la"]
    assert shell_launcher.calls[0]["cwd"] == str(orchestrator.SANDBOX_DIR)
    assert shell_launcher.calls[0]["stdin"] == subprocess.DEVNULL


_SHELL_NET_PROBE = (
    "import os, socket, sys\n"
    "print(os.readlink('/proc/self/ns/net'))\n"
    "try:\n"
    "    socket.create_connection(('127.0.0.1', int(sys.argv[1])), timeout=2).close()\n"
    "    print('CONNECTED')\n"
    "except OSError as e:\n"
    "    print('BLOCKED', e.errno)\n"
)


def test_real_host_shell_denies_the_network_or_refuses_honestly():
    """No fakes: shell_exec's "no network" is the attested namespace, not a label.
    A real allow-listed python3 child cannot reach a listener on the server's own
    loopback; a host without the isolation refuses and never runs the command."""
    orchestrator.SANDBOX_DIR.mkdir(parents=True, exist_ok=True)
    (orchestrator.SANDBOX_DIR / "net_probe.py").write_text(_SHELL_NET_PROBE, encoding="utf-8")
    srv = _loopback_listener()
    try:
        out = orchestrator._tool_shell("python3 net_probe.py %d" % srv.getsockname()[1])
        if out.get("execution_attempted") is False:
            _assert_shell_refused(out)
            pytest.skip("host refuses shell isolation (honest refusal): %s" % out["error"])
        assert out["isolation"] == orchestrator.SHELL_ISOLATION, out
        assert out["code"] == 0, out
        ns_line, verdict = out["stdout"].strip().splitlines()
        assert ns_line != os.readlink("/proc/self/ns/net")
        assert verdict.startswith("BLOCKED"), out["stdout"]
        assert TOKEN not in out["stdout"]
    finally:
        srv.close()


def test_shell_allow_list_is_still_checked_first(monkeypatch, shell_launcher):
    _install(monkeypatch, FakeResource())

    out = orchestrator._tool_shell("curl https://example.invalid")

    assert "not in allow-list" in out["error"]
    assert shell_launcher.calls == []


def test_shell_and_runner_labels_are_truthful():
    tools = {t["function"]["name"]: t["function"]["description"] for t in orchestrator.TOOL_SCHEMAS}
    shell = tools["shell_exec"].lower()
    assert "sandboxed dir (no network" not in shell
    assert "network namespace" in shell and "not a filesystem sandbox" in shell
    assert "not sandboxed" in tools["run_tests"].lower()
    low = orchestrator.SHELL_ISOLATION.lower()
    for needle in ("network namespace", "fail closed", "not a filesystem sandbox",
                   "no seccomp", "unix sockets"):
        assert needle in low
    boundary = orchestrator.RUN_BOUNDARY.lower()
    assert "not sandboxed" in boundary and "no network isolation" in boundary
    assert "isolated dir" not in boundary
    assert "sandboxed shell" not in orchestrator.DEFAULT_SYSTEM_PROMPT


# --------------------------------------------------------------------------
# /kernel/{run_id}/exec now runs the hard security screen it claimed to run.
# --------------------------------------------------------------------------
def test_kernel_route_runs_the_hard_security_screen_before_any_kernel(monkeypatch):
    from unittest.mock import patch

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import szl_operator_auth as opauth

    monkeypatch.setenv(opauth.OPERATOR_KEY_ENV, "op-test-secret-not-real")
    monkeypatch.setenv(opauth.SECOND_APPROVER_KEY_ENV, "approver-test-secret-not-real")
    headers = {"Authorization": "Bearer op-test-secret-not-real",
               opauth.SECOND_APPROVER_HEADER: "approver-test-secret-not-real"}
    app = FastAPI()
    orchestrator.attach(app)
    client = TestClient(app)
    with patch.object(gk, "get_kernel") as get_kernel, \
            patch.object(orchestrator, "puriq_decide") as gate:
        r = client.post("/api/a11oy/code/kernel/rq1/exec", headers=headers,
                        json={"code": "import socket\nsocket.create_connection(('x', 80))"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "BLOCKED" and body["executed"] is False
    assert "hard security gate DENIED" in body["error"]
    get_kernel.assert_not_called()
    gate.assert_not_called()


# --------------------------------------------------------------------------
# Status surfaces report the host's real isolation state.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("posix, res, ready", [(True, FakeResource(), True), (True, None, False),
                                               (False, FakeResource(), False)])
def test_code_as_action_status_reports_the_host_isolation_state(monkeypatch, posix, res, ready):
    """Regression: /agent/code/status always answered the attested-worker label,
    even on a host where every cell is refused."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    import a11oy_code_as_action as gcak

    _install(monkeypatch, res, posix=posix)
    app = FastAPI()
    gcak.register(app, "a11oy", lambda body: {"signed": False})
    body = TestClient(app).get("/api/a11oy/v1/agent/code/status").json()

    want = gk.ISOLATION_LABEL if ready else gk.REFUSED_ISOLATION
    assert body["isolation"] == want
    assert body["isolation_prerequisites"]["state"] == ("READY_TO_PROBE" if ready else "UNAVAILABLE")
    assert gk.isolation_prerequisites()["isolation"] == want


# --------------------------------------------------------------------------
# /v1/code/* never selects an unreviewed engine copy.
# --------------------------------------------------------------------------
def test_served_code_engine_is_always_the_vendored_byte_locked_module():
    """Regression: serve.py preferred an installed szl_substrate engine whenever it
    carried allow_exec. That copy has no attested network namespace, so selecting
    it would have served /v1/code/* without the isolation the kernel and shell_exec
    enforce. Every binding of the served engine must be the vendored module."""
    import ast

    tree = ast.parse((ROOT / "serve.py").read_text(encoding="utf-8"))
    engine_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            engine_imports += [(None, a.name, a.asname) for a in node.names
                               if a.name.endswith("a11oy_code_engine")]
        elif isinstance(node, ast.ImportFrom):
            engine_imports += [(node.module, a.name, a.asname) for a in node.names
                               if a.name == "a11oy_code_engine"
                               or (node.module or "").endswith("a11oy_code_engine")]
    assert engine_imports == [(None, "a11oy_code_engine", "_a11oy_code")]