# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Fail-closed tests for the code engine's MANDATORY sandbox rlimits and its
attested, unprivileged child.

Invariant: if any mandatory child rlimit (CPU, AS, CORE, FSIZE, NPROC) cannot be
applied, if the server runs as root, or if a child cannot attest new user and
network namespaces, the server's own non-root uid, zero capabilities and a
refused fork(), the code never runs and the sandbox returns its DENY shape with
``execution_attempted=False``. A run is reported as executed only when the code
child attested, i.e. reached the user code. There is no silent "run without
limits" path and no "executed" verdict for a child that never started.

Ported from szl-holdings/szl-substrate ``tests/test_code_engine_mandatory_limits.py``
(merged as 85445fde, PR #31). All 35 of its cases are kept by name. Their
invariant is kept too, with one stated change: the two ``governed_turn``
``..._is_a_signed_deny`` cases assert a signed NOT_EXECUTED refusal (the gate
still says ALLOW), not substrate's gate DENY. This engine copy differs from
substrate's in these places, so some fixtures and assertions are adapted beyond
the import:
  * the module global is ``resource`` (substrate: ``_resource``), and execution
    also needs the fixed ``unshare`` prerequisite and a non-root server, so
    ``_install`` patches ``resource``, ``_IS_POSIX``, ``_UNSHARE`` and
    ``_parent_identity``;
  * every run first launches an ``unshare --user --map-current-user --net`` probe
    under the SAME mandatory limit hook, then the code. ``FakeLauncher`` answers
    the probe and writes each child's attestation line, so a passing run makes
    two launches (each applying all five limits) and ``code_execs`` counts only
    the user-code launch;
  * missing POSIX/resource is refused by the existing ``sandbox_capability`` gate,
    whose DENY shape is unchanged; ``governed_turn`` needs ``allow_exec=True`` (the
    two-person chokepoint) to reach the sandbox.

Safety of this test module itself:
  * no real process is ever started: ``subprocess.Popen`` is replaced by
    ``FakeLauncher``, which models CPython's POSIX contract (fork -> preexec_fn in
    the child -> exec) without creating a process, and ``subprocess.run`` is
    replaced by a recorder that fails the test if it is ever reached;
  * no real rlimit is ever changed: the ``resource`` module is replaced by the inert
    ``FakeResource``; the POSIX-only tests against the real host only read;
  * no model endpoint is reachable: ``_model_configured`` is forced False and
    ``_hf_chat`` fails the test if called;
  * the only code strings are inert, hand-written fixtures (``INERT_FIXTURE`` and
    the engine's own deterministic ``_local_code`` template). Nothing is executed.
"""

from __future__ import annotations

import errno
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import a11oy_code_engine as code_engine

INERT_FIXTURE = "print('inert hand-written fixture')\n"
INF = -1
MANDATORY = ("RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_CORE", "RLIMIT_FSIZE", "RLIMIT_NPROC")
_IDS = {"RLIMIT_CPU": 0, "RLIMIT_FSIZE": 1, "RLIMIT_CORE": 4, "RLIMIT_NPROC": 6, "RLIMIT_AS": 9}
MIB = 1024 * 1024
FAKE_UNSHARE = "/usr/bin/unshare"
PROBE_TOKEN = "SZL_NETNS_READY"
NOT_EXECUTED_UNAVAILABLE = "NOT_EXECUTED — sandbox UNAVAILABLE on this host"
PARENT = {"uid": 1000, "net": "net:[4026531833]", "user": "user:[4026531837]"}
WANT = [PARENT["net"], PARENT["user"], str(PARENT["uid"])]
UNSHARE_PREFIX = [FAKE_UNSHARE, "--user", "--map-current-user", "--net", "--"]


class FakeResource:
    """Inert stand-in for the POSIX ``resource`` module. Never touches real limits."""

    RLIM_INFINITY = INF

    def __init__(self, *, missing=(), getrlimit_raises=(), setrlimit_raises=(),
                 not_in_effect=(), soft=None, hard=None, fail_from_call=None):
        for name, rid in _IDS.items():
            if name not in missing:
                setattr(self, name, rid)
        self._names = {rid: name for name, rid in _IDS.items()}
        self.limits = {rid: ((soft or {}).get(name, INF), (hard or {}).get(name, INF))
                       for name, rid in _IDS.items()}
        self.getrlimit_raises = set(getrlimit_raises)
        self.setrlimit_raises = set(setrlimit_raises)
        self.not_in_effect = set(not_in_effect)
        # a11oy only: fail every setrlimit from this 0-based call index onward, so a
        # later child (the code run) can fail after an earlier one (the probe) passed.
        self.fail_from_call = fail_from_call
        self.set_calls = []

    def getrlimit(self, rid):
        name = self._names[rid]
        if name in self.getrlimit_raises:
            raise OSError(22, "simulated getrlimit failure for %s" % name)
        return self.limits[rid]

    def setrlimit(self, rid, limits):
        name = self._names[rid]
        index = len(self.set_calls)
        self.set_calls.append((name, tuple(limits)))
        if name in self.setrlimit_raises:
            raise ValueError("simulated setrlimit failure for %s" % name)
        if self.fail_from_call is not None and index >= self.fail_from_call:
            raise ValueError("simulated setrlimit failure for %s" % name)
        if name in self.not_in_effect:
            return  # reports success but the limit does not take effect
        self.limits[rid] = tuple(limits)

    def applied(self):
        """Names whose setrlimit call actually took effect, in call order."""
        return [n for i, (n, _) in enumerate(self.set_calls)
                if n not in self.setrlimit_raises and n not in self.not_in_effect
                and (self.fail_from_call is None or i < self.fail_from_call)]


def _is_probe(args) -> bool:
    return "-c" in args and any(PROBE_TOKEN in str(a) for a in args)


def good_attestation(want):
    """What a correctly isolated child writes as its first stdout line."""
    return {"net": "net:[4026533469]", "user": "user:[4026533468]",
            "uid": int(want[2]), "euid": int(want[2]), "uid_map": [want[2], want[2], "1"],
            "cap_eff": "0000000000000000", "cap_prm": "0000000000000000",
            "fork": "refused:11", "ok": True}


class FakeProcess:
    def __init__(self, launcher, args, kind):
        self.launcher, self.args, self.kind = launcher, args, kind
        self.returncode = None
        self._timed_out_once = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def kill(self):
        self.launcher.kills.append(self.kind)

    def communicate(self, timeout=None):
        launcher = self.launcher
        raises = launcher.communicate_raises.get(self.kind)
        if raises is not None:
            raise raises
        if self.kind in launcher.times_out and not self._timed_out_once:
            self._timed_out_once = True
            raise subprocess.TimeoutExpired(self.args, timeout)
        if self.kind in launcher.no_attestation:
            # unshare(1) failed before it exec'd python: no attestation line at all.
            self.returncode = 1
            return b"", b"unshare: unshare failed: No space left on device\n"
        marker = good_attestation(self.args[-3:])
        marker.update(launcher.attestation_overrides.get(self.kind, {}))
        line = (PROBE_TOKEN + " " + json.dumps(marker, sort_keys=True) + "\n").encode()
        if self.kind == "probe" or marker.get("ok") is not True:
            # The child's own self-check exits before user code when it fails.
            self.returncode = 0 if marker.get("ok") is True else 97
            return line, b""
        launcher.code_execs.append(list(self.args))
        self.returncode = 0
        return line + b"inert fixture output\n", b""


class FakeLauncher:
    """Models CPython's POSIX ``subprocess.Popen`` contract without creating a process.

    ``calls`` records each fork; ``preexec_fn`` then runs "in the child". If it
    raises, CPython reports ``SubprocessError('Exception occurred in preexec_fn.')``
    and the program is never exec'd. ``launch_raises`` models a fork or exec
    failure, which CPython raises from ``Popen`` before any program runs.
    ``execs`` records only the programs that would actually have started;
    ``code_execs`` is the subset that would have reached the generated code (the
    code child, after its attestation passed)."""

    def __init__(self):
        self.calls = []
        self.execs = []
        self.code_execs = []
        self.run_calls = []
        self.kills = []
        self.probe_ready = True
        self.launch_raises = {}
        self.communicate_raises = {}
        self.times_out = set()
        self.no_attestation = set()
        self.attestation_overrides = {}

    @property
    def probe_times_out(self):
        return "probe" in self.times_out

    @probe_times_out.setter
    def probe_times_out(self, value):
        (self.times_out.add if value else self.times_out.discard)("probe")

    def popen(self, args, **kwargs):
        kind = "probe" if _is_probe(args) else "code"
        self.calls.append({"args": list(args), **kwargs})
        hook = kwargs.get("preexec_fn")
        if hook is not None:
            try:
                hook()
            except Exception as exc:
                raise subprocess.SubprocessError("Exception occurred in preexec_fn.") from exc
        if kind in self.launch_raises:
            raise self.launch_raises[kind]
        self.execs.append(list(args))
        if kind == "probe" and not self.probe_ready:
            self.no_attestation.add("probe")
        return FakeProcess(self, list(args), kind)

    def run(self, *args, **kwargs):
        self.run_calls.append((args, kwargs))
        raise AssertionError("subprocess.run must never be reached in these tests")


@pytest.fixture(autouse=True)
def offline(monkeypatch):
    """No test in this module may reach a model endpoint."""
    monkeypatch.setattr(code_engine, "_model_configured", lambda: False)

    def _no_model(*_a, **_k):
        raise AssertionError("model endpoint must not be called in tests")

    monkeypatch.setattr(code_engine, "_hf_chat", _no_model)


@pytest.fixture(autouse=True)
def launcher(monkeypatch):
    """No test in this module may start a real process."""
    fake = FakeLauncher()
    monkeypatch.setattr(code_engine.subprocess, "Popen", fake.popen)
    monkeypatch.setattr(code_engine.subprocess, "run", fake.run)
    yield fake
    assert fake.run_calls == []


def _install(monkeypatch, res, *, posix=True, identity=None):
    monkeypatch.setattr(code_engine, "_IS_POSIX", posix)
    monkeypatch.setattr(code_engine, "resource", res)
    monkeypatch.setattr(code_engine, "_UNSHARE", FAKE_UNSHARE if posix else None)
    found = (dict(PARENT), None) if identity is None else identity
    monkeypatch.setattr(code_engine, "_parent_identity", lambda: found)
    return res


def _assert_denied(result, *, capability_gate=False):
    assert result["ok"] is False
    assert result["execution_attempted"] is False
    assert result["execution_state"] == "UNAVAILABLE"
    assert result["exit"] == -1
    assert result["stdout"] == ""
    if capability_gate:
        # The existing fixed-prerequisite refusal, unchanged by this port.
        assert result["error"] == "fixed sandbox isolation prerequisites unavailable"
        assert result["isolation"] == "UNAVAILABLE — no code executed"
    else:
        assert result["error"].startswith("sandbox unavailable:")
        assert "fail closed" in result["isolation"]


def _signing_sink():
    signed = {}

    def sign(payload):
        signed.update(payload)
        return {"signed": True, "signatures": ["test-signature"]}

    return signed, sign


def _governed(sign):
    return code_engine.governed_turn("code", "calculate fibonacci numbers", sign,
                                     "test-issuer", sandbox=True, allow_exec=True)


def _assert_signed_not_executed(run, signed, *, status=NOT_EXECUTED_UNAVAILABLE):
    assert run["decision"] == "ALLOW"  # the gate allowed it; the sandbox refused it
    assert run["executed"] is False
    assert run["execution_status"] == status
    assert run["sandbox"]["executed"] is False
    assert "ran in the governed sandbox" not in run["summary"]
    assert signed["executed"] is False
    assert signed["execution_status"] == status
    assert run["receipt_chain"][-1]["body"]["executed"] is False
    assert code_engine.verify_run(run)["chain_intact"] is True


# --------------------------------------------------------------------------
# Parent-side preflight: the subprocess launcher is never called.
# --------------------------------------------------------------------------
def test_resource_module_missing_denies_before_launch(monkeypatch, launcher):
    _install(monkeypatch, None)

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    _assert_denied(result, capability_gate=True)
    assert "POSIX_RESOURCE_LIMITS" in result["capability"]["missing"]
    assert code_engine._plan_mandatory_rlimits(6, 256) == (
        None, None, "sandbox unavailable: POSIX resource limits are required")
    assert launcher.calls == []


def test_non_posix_platform_denies_before_launch(monkeypatch, launcher):
    res = _install(monkeypatch, FakeResource(), posix=False)

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    _assert_denied(result, capability_gate=True)
    assert "POSIX_HOST" in result["capability"]["missing"]
    assert code_engine._plan_mandatory_rlimits(6, 256) == (
        None, None, "sandbox unavailable: POSIX resource limits are required")
    assert launcher.calls == []
    assert res.set_calls == []


@pytest.mark.parametrize("name", MANDATORY)
def test_unsupported_mandatory_rlimit_denies_before_launch(monkeypatch, launcher, name):
    res = _install(monkeypatch, FakeResource(missing=(name,)))

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    _assert_denied(result)
    assert result["error"] == (
        "sandbox unavailable: mandatory rlimit %s is not supported on this platform" % name)
    assert launcher.calls == []
    assert res.set_calls == []


@pytest.mark.parametrize("name", MANDATORY)
def test_unreadable_mandatory_rlimit_denies_before_launch(monkeypatch, launcher, name):
    res = _install(monkeypatch, FakeResource(getrlimit_raises=(name,)))

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    _assert_denied(result)
    assert result["error"] == (
        "sandbox unavailable: mandatory rlimit %s cannot be read (OSError)" % name)
    assert launcher.calls == []
    assert res.set_calls == []


@pytest.mark.parametrize("fn", ["getrlimit", "setrlimit"])
def test_missing_rlimit_function_denies_before_launch(monkeypatch, launcher, fn):
    res = FakeResource()
    setattr(res, fn, None)
    _install(monkeypatch, res)

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    _assert_denied(result)
    assert "resource.%s is unavailable" % fn in result["error"]
    assert launcher.calls == []


def test_missing_rlim_infinity_denies_before_launch(monkeypatch, launcher):
    res = FakeResource()
    res.RLIM_INFINITY = None
    _install(monkeypatch, res)

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    _assert_denied(result)
    assert "RLIM_INFINITY is unavailable" in result["error"]
    assert launcher.calls == []


# --------------------------------------------------------------------------
# Child-side hook: a setrlimit failure aborts the child before exec.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("name", MANDATORY)
def test_setrlimit_raising_never_reaches_exec(monkeypatch, launcher, name):
    res = _install(monkeypatch, FakeResource(setrlimit_raises=(name,)))

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    _assert_denied(result)
    assert result["error"] == code_engine._LIMIT_HOOK_FAILED_ERROR
    # The fork is modelled honestly (one launcher call: the probe child), but exec
    # never happens, so neither the probe nor the code runs.
    assert len(launcher.calls) == 1
    assert launcher.execs == []
    assert res.set_calls[-1][0] == name  # the failing limit was the last one attempted


def test_partial_application_failure_never_reaches_exec(monkeypatch, launcher):
    """CPU, AS and CORE apply, then FSIZE fails: NPROC is never attempted and the
    program never runs with the partial set."""
    res = _install(monkeypatch, FakeResource(setrlimit_raises=("RLIMIT_FSIZE",)))

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    _assert_denied(result)
    assert res.applied() == ["RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_CORE"]
    assert [n for n, _ in res.set_calls] == [
        "RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_CORE", "RLIMIT_FSIZE"]
    assert launcher.execs == []


def test_nproc_failure_is_no_longer_swallowed(monkeypatch, launcher):
    """Regression: RLIMIT_NPROC used to sit in its own swallow-all try/except, so a
    failure there still ran the code with no process limit."""
    res = _install(monkeypatch, FakeResource(setrlimit_raises=("RLIMIT_NPROC",)))

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    _assert_denied(result)
    assert res.applied() == ["RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_CORE", "RLIMIT_FSIZE"]
    assert launcher.execs == []


@pytest.mark.parametrize("name", MANDATORY)
def test_limit_not_in_effect_after_setrlimit_never_reaches_exec(monkeypatch, launcher, name):
    """setrlimit reports success but the read-back shows the limit is not in force."""
    _install(monkeypatch, FakeResource(not_in_effect=(name,)))

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    _assert_denied(result)
    assert result["error"] == code_engine._LIMIT_HOOK_FAILED_ERROR
    assert launcher.execs == []


def test_hook_raises_instead_of_swallowing():
    plan = [(n, _IDS[n], (0, 0)) for n in MANDATORY]

    raising = FakeResource(setrlimit_raises=("RLIMIT_AS",))
    with pytest.raises(ValueError, match="RLIMIT_AS"):
        code_engine._apply_mandatory_rlimits(raising, plan)
    assert raising.applied() == ["RLIMIT_CPU"]

    silent = FakeResource(not_in_effect=("RLIMIT_CORE",))
    with pytest.raises(OSError, match="RLIMIT_CORE is not in effect"):
        code_engine._apply_mandatory_rlimits(silent, plan)


# --------------------------------------------------------------------------
# Success path: every limit applies, then (and only then) the program runs.
# --------------------------------------------------------------------------
def test_all_mandatory_limits_applied_then_launches(monkeypatch, launcher):
    res = _install(monkeypatch, FakeResource())

    result = code_engine._sandbox_exec(INERT_FIXTURE, timeout_s=6, mem_mb=256)

    assert result["ok"] is True
    assert result["execution_attempted"] is True
    assert result["exit"] == 0
    assert result["stdout"] == "inert fixture output\n"
    per_child = [
        ("RLIMIT_CPU", (6, 6)),
        ("RLIMIT_AS", (256 * MIB, 256 * MIB)),
        ("RLIMIT_CORE", (0, 0)),
        ("RLIMIT_FSIZE", (0, 0)),
        ("RLIMIT_NPROC", (0, 0)),
    ]
    # The probe child and the code child each apply (and read back) all five.
    assert res.set_calls == per_child + per_child
    assert len(launcher.calls) == 2 and len(launcher.execs) == 2
    assert len(launcher.code_execs) == 1
    assert all(c["preexec_fn"] is not None for c in launcher.calls)
    probe = launcher.calls[0]["args"]
    assert _is_probe(probe)
    assert probe == UNSHARE_PREFIX + [sys.executable, "-I", "-S", "-c",
                                      code_engine._ATTEST_SRC] + WANT
    call = launcher.calls[1]
    main = Path(call["args"][8])
    assert call["args"] == UNSHARE_PREFIX + [sys.executable, "-I", "-S", str(main)] + WANT
    assert main.name == "main.py" and str(main.parent) == call["cwd"]
    assert set(call["env"]) == {"PATH", "PYTHONDONTWRITEBYTECODE", "HOME", "no_proxy",
                                "PYTHONUNBUFFERED"}
    # The attestation line is the child's, not the user's: it is stripped.
    assert PROBE_TOKEN not in result["stdout"]


def test_inherited_limits_are_never_loosened(monkeypatch, launcher):
    """A server already running under tighter limits keeps them in the child: the
    plan takes the stricter value, so setrlimit is always a permitted lowering."""
    res = _install(monkeypatch, FakeResource(
        soft={"RLIMIT_CPU": 1}, hard={"RLIMIT_CPU": 2, "RLIMIT_AS": 128 * MIB}))

    result = code_engine._sandbox_exec(INERT_FIXTURE, timeout_s=6, mem_mb=256)

    assert result["execution_attempted"] is True
    assert dict(res.set_calls)["RLIMIT_CPU"] == (1, 2)
    assert dict(res.set_calls)["RLIMIT_AS"] == (128 * MIB, 128 * MIB)
    assert len(launcher.code_execs) == 1


def test_preflight_with_real_resource_module_is_read_only():
    """On a POSIX host the real preflight plans every mandatory limit and changes
    nothing in the test process (it only calls getrlimit)."""
    resource = pytest.importorskip("resource")
    if not code_engine._IS_POSIX:  # pragma: no cover - platform dependent
        pytest.skip("POSIX only")
    names = [n for n in MANDATORY if hasattr(resource, n)]
    before = {n: resource.getrlimit(getattr(resource, n)) for n in names}

    res, plan, refusal = code_engine._plan_mandatory_rlimits(6, 256)

    after = {n: resource.getrlimit(getattr(resource, n)) for n in names}
    assert after == before
    if len(names) == len(MANDATORY):
        assert refusal is None and res is resource
        assert [p[0] for p in plan] == list(MANDATORY)
    else:  # pragma: no cover - a platform without one of the constants must deny
        assert refusal is not None and plan is None


# --------------------------------------------------------------------------
# governed_turn: code execution goes through the same mandatory-limit gate.
# allow_exec=True is the two-person chokepoint; without it the sandbox is never
# reached. A sandbox refusal keeps the gate's ALLOW but is signed as NOT_EXECUTED
# with the refusal reason; no code runs.
# --------------------------------------------------------------------------
def test_governed_turn_partial_platform_support_is_a_signed_deny(monkeypatch, launcher):
    _install(monkeypatch, FakeResource(missing=("RLIMIT_NPROC",)))
    signed, sign = _signing_sink()

    run = code_engine.governed_turn("code", "calculate fibonacci numbers", sign,
                                    "test-issuer", sandbox=True, allow_exec=True)

    reason = "sandbox unavailable: mandatory rlimit RLIMIT_NPROC is not supported on this platform"
    assert launcher.calls == []
    assert run["decision"] == "ALLOW"  # the gate allowed it; the sandbox refused it
    assert run["executed"] is False
    assert run["execution_status"] == NOT_EXECUTED_UNAVAILABLE
    assert run["sandbox"]["execution_attempted"] is False
    assert run["sandbox"]["error"] == reason
    assert "Nothing ran" in run["summary"] and reason in run["summary"]
    assert "ran in the governed sandbox" not in run["summary"]
    assert signed["executed"] is False
    assert signed["execution_status"] == NOT_EXECUTED_UNAVAILABLE
    assert signed["sandbox_execution_attempted"] is False
    assert signed["sandbox_error"] == reason
    assert run["receipt_chain"][-1]["body"]["executed"] is False
    assert code_engine.verify_run(run)["chain_intact"] is True


def test_governed_turn_hook_failure_is_a_signed_deny(monkeypatch, launcher):
    _install(monkeypatch, FakeResource(setrlimit_raises=("RLIMIT_CPU",)))
    signed, sign = _signing_sink()

    run = code_engine.governed_turn("code", "calculate fibonacci numbers", sign,
                                    "test-issuer", sandbox=True, allow_exec=True)

    assert launcher.execs == []
    assert run["executed"] is False
    assert run["execution_status"] == NOT_EXECUTED_UNAVAILABLE
    assert run["sandbox"]["execution_attempted"] is False
    assert run["sandbox"]["error"] == code_engine._LIMIT_HOOK_FAILED_ERROR
    assert "then ran in the governed sandbox" not in run["summary"]
    assert signed["executed"] is False
    assert signed["sandbox_execution_attempted"] is False
    assert signed["sandbox_error"] == code_engine._LIMIT_HOOK_FAILED_ERROR
    assert code_engine.verify_run(run)["chain_intact"] is True


def test_governed_turn_runs_only_after_every_limit_applies(monkeypatch, launcher):
    res = _install(monkeypatch, FakeResource())
    signed, sign = _signing_sink()

    run = code_engine.governed_turn("code", "calculate fibonacci numbers", sign,
                                    "test-issuer", sandbox=True, allow_exec=True)

    assert run["decision"] == "ALLOW"
    assert run["emitted"] is True
    assert res.applied() == list(MANDATORY) * 2  # probe child, then code child
    assert len(launcher.code_execs) == 1
    assert run["executed"] is True
    assert run["sandbox"]["execution_attempted"] is True
    assert signed["sandbox_execution_attempted"] is True
    assert signed["executed"] is True


def test_governed_turn_without_sandbox_never_launches(monkeypatch, launcher):
    _install(monkeypatch, FakeResource())
    _, sign = _signing_sink()

    run = code_engine.governed_turn("code", "calculate fibonacci numbers", sign,
                                    "test-issuer", sandbox=False, allow_exec=True)

    assert launcher.calls == []
    assert run["sandbox"] is None


# --------------------------------------------------------------------------
# a11oy-specific cases (beyond the 35 ported from substrate): the unshare --net
# probe runs under the same mandatory hook, and no label claims seccomp/container.
# --------------------------------------------------------------------------
def test_code_child_hook_failure_after_probe_never_runs_code(monkeypatch, launcher):
    """The probe child applies all five limits; the code child then fails on its
    first one. The code is still never exec'd: both launches are gated."""
    res = _install(monkeypatch, FakeResource(fail_from_call=len(MANDATORY)))

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    _assert_denied(result)
    assert result["error"] == code_engine._LIMIT_HOOK_FAILED_ERROR
    assert len(launcher.calls) == 2
    assert len(launcher.execs) == 1 and _is_probe(launcher.execs[0])
    assert launcher.code_execs == []
    assert res.applied() == list(MANDATORY)


def test_probe_without_network_namespace_never_runs_code(monkeypatch, launcher):
    _install(monkeypatch, FakeResource())
    launcher.probe_ready = False

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    assert result["ok"] is False
    assert result["execution_attempted"] is False
    assert result["execution_state"] == "UNAVAILABLE"
    assert result["error"] == "network namespace probe failed"
    assert len(launcher.calls) == 1
    assert launcher.code_execs == []


def test_probe_timeout_is_a_denial_not_a_code_timeout(monkeypatch, launcher):
    _install(monkeypatch, FakeResource())
    launcher.probe_times_out = True

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    assert result["ok"] is False
    assert result["execution_attempted"] is False
    assert result["execution_state"] == "UNAVAILABLE"
    assert result["error"] == "network namespace probe timed out"
    assert result["exit"] == -1
    assert len(launcher.calls) == 1
    assert launcher.code_execs == []


def test_isolation_labels_claim_no_seccomp_or_container_isolation(monkeypatch, launcher):
    _install(monkeypatch, FakeResource())

    labels = [
        code_engine._sandbox_exec(INERT_FIXTURE)["isolation"],
        code_engine.capabilities("test-issuer")["honesty"]["sandbox"],
    ]
    monkeypatch.setattr(code_engine, "_LOCAL_MODEL_CMD", "")
    monkeypatch.setattr(code_engine, "_HF_TOKEN", "")
    labels.append(code_engine._backend_label()["sandbox_isolation"])

    for label in labels:
        low = label.lower()
        assert "full seccomp" not in low
        assert "tower/uds pod" not in low
        assert "no seccomp" in low or "not a seccomp" in low
        assert "rlimit" in low
        # The process limit is claimed only together with what makes it bind.
        assert "non-root uid" in low
        assert "user + network namespace" in low
        assert "attest" in low
        assert "filesystem" in low


# --------------------------------------------------------------------------
# Launch-stage truth: a run is "executed" only when the code child attested.
# A child that never started, or never reached its attestation, is a refusal
# with execution_attempted=False, and governed_turn signs NOT_EXECUTED.
# --------------------------------------------------------------------------
@pytest.mark.parametrize("kind", ["probe", "code"])
def test_launch_oserror_is_a_signed_refusal_not_an_execution(monkeypatch, launcher, kind):
    """fork() EAGAIN while starting either child: nothing was exec'd, so nothing ran."""
    _install(monkeypatch, FakeResource())
    launcher.launch_raises[kind] = BlockingIOError(errno.EAGAIN, "Resource temporarily unavailable")

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    _assert_denied(result)
    assert "could not be started (BlockingIOError" in result["error"]
    assert launcher.code_execs == []

    signed, sign = _signing_sink()
    run = _governed(sign)
    _assert_signed_not_executed(run, signed)
    assert signed["sandbox_execution_attempted"] is False
    assert "could not be started" in signed["sandbox_error"]
    assert launcher.code_execs == []


def test_code_child_without_attestation_is_not_executed(monkeypatch, launcher):
    """unshare(1) exits before exec'ing python (e.g. netns creation refused under
    load after the probe passed): the child wrote no attestation, so no user code
    ran and the run is not reported as executed."""
    _install(monkeypatch, FakeResource())
    launcher.no_attestation.add("code")

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    assert result["ok"] is False
    assert result["execution_attempted"] is False
    assert result["execution_state"] == "UNAVAILABLE"
    assert "did not attest" in result["error"]
    assert "No space left on device" in result["stderr"]
    assert result["exit"] == 1
    assert launcher.code_execs == []

    signed, sign = _signing_sink()
    run = _governed(sign)
    _assert_signed_not_executed(run, signed)
    assert signed["sandbox_execution_attempted"] is False


def test_code_child_self_check_failure_never_reaches_user_code(monkeypatch, launcher):
    _install(monkeypatch, FakeResource())
    launcher.attestation_overrides["code"] = {"fork": "allowed", "ok": False}

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    assert result["execution_attempted"] is False
    assert result["execution_state"] == "UNAVAILABLE"
    assert "fork() was not refused" in result["stderr"]
    assert result["exit"] == 97
    assert launcher.code_execs == []


@pytest.mark.parametrize("override, problem", [
    ({"net": PARENT["net"]}, "no new network namespace"),
    ({"user": PARENT["user"]}, "no new user namespace"),
    ({"uid": 0, "euid": 0, "uid_map": ["0", "0", "1"]}, "the child runs as root"),
    ({"uid": 1001}, "the child does not run as the server's own uid"),
    ({"uid_map": ["0", "1000", "1"]}, "the child does not run as the server's own uid"),
    ({"cap_eff": "000001ffffffffff"}, "the child holds capabilities (cap_eff)"),
    ({"cap_prm": "0000000000200000"}, "the child holds capabilities (cap_prm)"),
    ({"cap_eff": "unreadable"}, "the child's cap_eff is unreadable"),
    ({"fork": "allowed"}, "fork() was not refused with EAGAIN"),
    ({"fork": "refused:12"}, "fork() was not refused with EAGAIN"),
    ({"ok": False}, "the child's own isolation self-check failed"),
])
def test_probe_attestation_must_prove_the_boundary(monkeypatch, launcher, override, problem):
    """The parent re-checks every attested property itself; any gap is a refusal
    before the code child is ever started."""
    _install(monkeypatch, FakeResource())
    launcher.attestation_overrides["probe"] = override

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    assert result["execution_attempted"] is False
    assert result["execution_state"] == "UNAVAILABLE"
    assert result["error"] == "network namespace probe failed"
    assert problem in result["stderr"]
    assert len(launcher.calls) == 1
    assert launcher.code_execs == []


def test_attestation_mismatch_after_self_check_is_executed_but_unverified(monkeypatch, launcher):
    """If the child's self-check passed (so the code ran) but the parent cannot
    confirm the attestation, the run is reported as executed WITHOUT the isolation
    claim, never as an isolated success."""
    _install(monkeypatch, FakeResource())
    launcher.attestation_overrides["code"] = {"net": PARENT["net"]}

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    assert result["ok"] is False
    assert result["execution_attempted"] is True
    assert result["execution_state"] == "UNVERIFIED"
    assert result["isolation"].startswith("UNVERIFIED")
    assert "no new network namespace" in result["error"]

    signed, sign = _signing_sink()
    run = _governed(sign)
    assert run["executed"] is True
    assert run["execution_status"] == "EXECUTED — sandbox isolation NOT verified"
    assert "ran in the governed sandbox" not in run["summary"]
    assert "unisolated" in run["summary"]
    assert signed["executed"] is True
    assert signed["execution_status"] == "EXECUTED — sandbox isolation NOT verified"
    assert signed["sandbox_execution_attempted"] is True


def test_failure_after_the_code_child_started_is_unknown_not_executed(monkeypatch, launcher):
    _install(monkeypatch, FakeResource())
    launcher.communicate_raises["code"] = OSError(errno.EIO, "simulated pipe failure")

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    assert result["ok"] is False
    assert result["execution_attempted"] is None
    assert result["execution_state"] == "UNVERIFIED"
    assert launcher.kills == ["code"]

    signed, sign = _signing_sink()
    run = _governed(sign)
    status = "UNVERIFIED — sandbox error after launch; whether the code ran is unknown"
    assert run["executed"] is False
    assert run["execution_status"] == status
    assert "Nothing ran" not in run["summary"]
    assert "ran in the governed sandbox" not in run["summary"]
    assert signed["executed"] is False
    assert signed["execution_status"] == status
    assert signed["sandbox_execution_attempted"] is None


def test_code_timeout_after_attestation_is_an_executed_timeout(monkeypatch, launcher):
    _install(monkeypatch, FakeResource())
    launcher.times_out.add("code")

    result = code_engine._sandbox_exec(INERT_FIXTURE, timeout_s=6)

    assert result["ok"] is False
    assert result["execution_attempted"] is True
    assert result["exit"] == -9
    assert result["stderr"].startswith("timeout after 6s (killed)")
    assert launcher.kills == ["code"]


def test_code_timeout_without_attestation_is_a_refusal(monkeypatch, launcher):
    _install(monkeypatch, FakeResource())
    launcher.times_out.add("code")
    launcher.no_attestation.add("code")

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    assert result["execution_attempted"] is False
    assert result["execution_state"] == "UNAVAILABLE"
    assert launcher.code_execs == []


def test_governed_turn_never_reports_execution_without_an_explicit_attempt(monkeypatch):
    """A sandbox result that omits execution_attempted is not an execution."""
    monkeypatch.setattr(code_engine, "_sandbox_exec", lambda *a, **k: {
        "ok": False, "stdout": "", "stderr": "sandbox error: legacy shape", "exit": -1,
        "isolation": "sandboxed (restricted subprocess)"})
    signed, sign = _signing_sink()

    run = _governed(sign)

    _assert_signed_not_executed(run, signed)
    assert signed["sandbox_execution_attempted"] is None


# --------------------------------------------------------------------------
# Privilege: RLIMIT_NPROC does not bind a root-owned child, so a root server is
# refused before any process starts, and the uid is checked through uid_map.
# --------------------------------------------------------------------------
def test_root_server_is_refused_before_launch(monkeypatch, launcher):
    reason = ("sandbox unavailable: the server runs as root; Linux does not apply "
              "RLIMIT_NPROC to a root-owned child, so code is refused")
    res = _install(monkeypatch, FakeResource(), identity=(None, reason))

    result = code_engine._sandbox_exec(INERT_FIXTURE)

    _assert_denied(result)
    assert result["error"] == reason
    assert launcher.calls == []
    assert res.set_calls == []

    signed, sign = _signing_sink()
    run = _governed(sign)
    _assert_signed_not_executed(run, signed)
    assert signed["sandbox_error"] == reason


class _UidMap:
    def __init__(self, text):
        self.text = text

    def __call__(self, path, *a, **k):
        assert path == "/proc/self/uid_map"
        if self.text is None:
            raise PermissionError(13, "simulated")
        import io
        return io.StringIO(self.text)


@pytest.mark.parametrize("uid, uid_map, refused", [
    (0, "0 0 4294967295\n", "the server runs as root"),
    (1000, "0 0 4294967295\n", None),
    (1000, "0 100000 65536\n", None),
    (1000, "1000 0 1\n", "maps to root"),
    (1000, "0 0 10\n", "maps to root (or to nothing)"),
    (1000, None, "cannot be read (PermissionError)"),
    (1000, "garbage\n", "cannot be read (ValueError)"),
])
def test_parent_identity_refuses_root_and_unmapped_uids(monkeypatch, uid, uid_map, refused):
    monkeypatch.setattr(code_engine.os, "getuid", lambda: uid, raising=False)
    monkeypatch.setattr(code_engine.os, "geteuid", lambda: uid, raising=False)
    monkeypatch.setattr(code_engine.os, "readlink",
                        lambda p: {"/proc/self/ns/net": PARENT["net"],
                                   "/proc/self/ns/user": PARENT["user"]}[p])
    monkeypatch.setattr(code_engine, "open", _UidMap(uid_map), raising=False)

    identity, refusal = code_engine._parent_identity()

    if refused is None:
        assert refusal is None
        assert identity == {"uid": uid, "net": PARENT["net"], "user": PARENT["user"]}
    else:
        assert identity is None
        assert refusal.startswith("sandbox unavailable:") and refused in refusal


@pytest.mark.parametrize("timeout_s, mem_mb", [
    (-1, 256), (0, 256), (6, -1), (6, 0), (True, 256), (6.5, 256), ("6", 256),
])
def test_non_positive_or_non_integer_mandates_are_refused(monkeypatch, launcher, timeout_s, mem_mb):
    """-1 equals RLIM_INFINITY on Linux CPython and would plan an unlimited CPU limit."""
    res = _install(monkeypatch, FakeResource())

    plan = code_engine._plan_mandatory_rlimits(timeout_s, mem_mb)
    result = code_engine._sandbox_exec(INERT_FIXTURE, timeout_s=timeout_s, mem_mb=mem_mb)

    assert plan[0] is None and plan[1] is None and "positive integers" in plan[2]
    _assert_denied(result)
    assert launcher.calls == []
    assert res.set_calls == []


def test_unshare_comes_only_from_fixed_root_owned_system_paths(monkeypatch, tmp_path):
    """A writable `unshare` shim, whether first on PATH or at a candidate path, is
    never accepted as the namespace boundary."""
    assert code_engine._UNSHARE_CANDIDATES == ("/usr/bin/unshare", "/bin/unshare")
    shim = tmp_path / "unshare"
    shim.write_text("#!/bin/sh\nexec \"$@\"\n")
    os.chmod(shim, 0o777)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ.get("PATH", ""))
    monkeypatch.setattr(code_engine, "_IS_POSIX", True)
    found = code_engine._fixed_unshare()
    assert found in (None, "/usr/bin/unshare", "/bin/unshare")
    monkeypatch.setattr(code_engine, "_UNSHARE_CANDIDATES", (str(shim),))
    assert code_engine._fixed_unshare() is None
    monkeypatch.setattr(code_engine, "_IS_POSIX", False)
    assert code_engine._fixed_unshare() is None


def test_attestation_source_checks_what_the_parent_checks():
    """The child's self-check (which gates the user code) covers every property the
    parent re-checks, so a passing child and a refusing parent cannot disagree on
    a well-formed attestation."""
    src = code_engine._ATTEST_SRC
    compile(src, "<attest>", "exec")
    for needle in ("/proc/self/ns/net", "/proc/self/ns/user", "/proc/self/uid_map",
                   "CapEff", "CapPrm", "os.fork()", "refused:11", "want[2] != '0'",
                   "os._exit(97)", "sys.stdout.flush()", PROBE_TOKEN):
        assert needle in src


def test_real_host_identity_is_read_only_and_refuses_root():
    """On a POSIX host the real identity check only reads, and refuses uid 0."""
    if not code_engine._IS_POSIX or not os.path.exists("/proc/self/uid_map"):
        pytest.skip("Linux /proc only")
    identity, refusal = code_engine._parent_identity()
    if os.geteuid() == 0:
        assert identity is None and "runs as root" in refusal
    elif refusal is None:
        assert identity["uid"] == os.geteuid()
        assert identity["net"].startswith("net:[") and identity["user"].startswith("user:[")
