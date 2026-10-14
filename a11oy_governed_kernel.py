# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
a11oy_governed_kernel.py — a PERSISTENT, sandboxed Python kernel for the governed
code-as-action loop.

THE NOVELTY (vs a11oy_code_engine._sandbox_exec, which is single-shot):
    _sandbox_exec spawns a FRESH `python -I -S` subprocess per call and forbids file
    writes — nothing survives between calls. This kernel keeps ONE long-lived worker
    process per run_id whose globals() namespace PERSISTS across cells, so a variable
    defined in a compose cell is still bound in a later inspect/revise cell. That is
    SpatialClaw's persistent-kernel property — made sandboxed and governed.

ISOLATION (honest label, restricted-subprocess tier — NOT container/seccomp here).
The worker reuses the hardened single-shot engine's controls from
a11oy_code_engine (imported, never copied: that file is byte-locked with
killinchu) and FAILS CLOSED: if any control below cannot be established, no
worker is kept and no cell runs (execution_attempted=False).
    - separate worker process, never in the server process
    - launched with `-I -S` (isolated interpreter, no site) + an explicitly
      constructed minimal env (no inherited secrets / no HF token / no signing key)
    - refused when the server runs as root (_parent_identity)
    - MANDATORY rlimits planned in the parent and applied + read back in the child
      before exec (_plan_mandatory_rlimits / _apply_mandatory_rlimits): RLIMIT_CPU
      (worker lifetime), RLIMIT_AS (address space), RLIMIT_CORE=0,
      RLIMIT_FSIZE=0 and RLIMIT_NPROC=0. Any failure aborts the child before exec.
    - a per-run `unshare --user --map-current-user --net` user + network
      namespace. The worker's first act is the engine's attestation (_ATTEST_SRC):
      new namespaces, the server's own non-root uid, zero capabilities and a
      refused fork(). The parent re-checks it and sends no cell until it passes.
    - BLAS/OpenMP pinned to one thread so numpy imports under RLIMIT_NPROC=0
    - socket monkeypatched in the worker (in-process, best effort, on top of the
      namespace)
    - per-cell wall-clock timeout; on breach the worker is killed and the run is
      marked DEGRADED — never a fabricated success
    Resource controls only: no seccomp, chroot, mount namespace or container. A
    cell runs as the server's uid and could read what that uid can read; the hard
    gate (below) bans file, env and /proc reach. Container/microVM = ROADMAP.

The HARD security gate (a11oy_code_engine.hard_security_screen) decides what is
ALLOWED to run BEFORE a cell reaches this kernel — the kernel only EXECUTES already
allowed code. Variables never leave the sandbox raw: var_summary() exposes only
{type, len/shape, repr<=200ch, sha256} digests of new/changed top-level names.

Stdlib only (no new pip installs in the slim image).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import threading
import time
import uuid
from typing import Any, Optional

import a11oy_code_engine as _engine

# Honest isolation label — kept faithful to a11oy_code_engine._sandbox_exec's wording.
# It describes an ATTESTED worker; a refused worker reports REFUSED_ISOLATION instead.
ISOLATION_LABEL = (
    "restricted subprocess: persistent worker as the server's own non-root uid in a "
    "per-run user + network namespace (unshare --user --map-current-user --net), "
    "mandatory CPU+memory+core+fsize+nproc rlimits (fail closed); before any cell ran "
    "the worker attested new namespaces, its uid, zero capabilities and a refused "
    "fork(). Single-threaded BLAS, per-cell wall-clock timeout, minimal env (no "
    "secrets), isolated interpreter (-I -S). Resource controls only: no seccomp, "
    "filesystem or container isolation; a cell runs as the server's uid."
)
REFUSED_ISOLATION = "UNAVAILABLE — fail closed: no isolated worker; no cell executed"

# Default per-cell limits (mirror a11oy_code_engine._sandbox_exec discipline).
DEFAULT_TIMEOUT_S = 6
# RLIMIT_CPU for the whole persistent worker (CPU seconds across all of its cells);
# the per-cell wall-clock timeout is the per-cell bound.
WORKER_CPU_S = 3600
# How long the parent waits for the worker's isolation attestation line.
ATTEST_TIMEOUT_S = 5
# Address-space (RLIMIT_AS) ceiling. Higher than the single-shot engine's 256MB
# because numpy maps substantial *virtual* address space at import in an isolated
# interpreter; still a hard bound (a runaway allocation hits MemoryError, not OOM).
DEFAULT_MEM_MB = 1024

# The driver program the worker runs. It imports numpy as a pre-bound trusted name
# (so agent cells COMPOSE over `np` without an `import`, while `import socket` etc.
# stay banned by the gate), then reads {code} commands on stdin and replies on stdout
# with stdout capture + a var-summary digest. Variables live in one persistent dict.
_WORKER_SRC = r'''
import sys, io, json, hashlib, contextlib, builtins

def _no_net(*a, **k):
    raise OSError("network disabled in a11oy governed kernel")
try:
    import socket as _s
    _s.socket = _no_net
    _s.create_connection = _no_net
    _s.socketpair = _no_net
except Exception:
    pass

# `-S` disables site, so the trusted scientific lib (numpy) is not on sys.path.
# Add ONLY the known stdlib site-packages dir back (explicit, no env-driven path,
# no user-site) so the agent can COMPOSE over a pre-bound `np` without an `import`,
# while `import socket` / file / env reach stay banned by the hard gate.
try:
    _spkg = __SITE_PACKAGES__
    if _spkg and _spkg not in sys.path:
        sys.path.append(_spkg)
except Exception:
    pass

_NS = {"__name__": "__a11oy_cell__", "__builtins__": builtins}
try:
    import numpy as np
    _NS["np"] = np
    _NS["numpy"] = np
except Exception:
    pass

def _digest(obj):
    try:
        raw = repr(obj).encode("utf-8", "replace")
    except Exception:
        raw = b"<unreprable>"
    return hashlib.sha256(raw).hexdigest()

def _summ(ns):
    out = {}
    for k, v in list(ns.items()):
        if k.startswith("__") or k in ("np", "numpy"):
            continue
        if callable(v) and getattr(v, "__module__", None) in (None, "builtins"):
            continue
        info = {"type": type(v).__name__, "sha256": _digest(v)}
        shp = getattr(v, "shape", None)
        if shp is not None:
            info["shape"] = list(shp) if hasattr(shp, "__iter__") else shp
        else:
            try:
                info["len"] = len(v)
            except Exception:
                pass
        try:
            info["repr"] = repr(v)[:200]
        except Exception:
            info["repr"] = "<unreprable>"
        out[k] = info
    return out

def _run(code):
    before = set(_NS.keys())
    buf = io.StringIO()
    err = ""
    ok = True
    try:
        compiled = compile(code, "<a11oy_cell>", "exec")
        with contextlib.redirect_stdout(buf):
            exec(compiled, _NS, _NS)
    except Exception as e:
        ok = False
        err = "%s: %s" % (type(e).__name__, e)
    after = _summ(_NS)
    changed = sorted(k for k in after.keys() if k not in before or k in _NS)
    return {
        "ok": ok,
        "stdout": buf.getvalue()[:8000],
        "stderr": err[:4000],
        "vars": after,
        "new_or_changed": sorted(k for k in after.keys() if k not in before),
    }

def main():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            cmd = json.loads(line)
        except Exception:
            sys.stdout.write(json.dumps({"ok": False, "stderr": "bad command json"}) + "\n")
            sys.stdout.flush()
            continue
        if cmd.get("op") == "ping":
            res = {"ok": True, "vars": _summ(_NS)}
        elif cmd.get("op") == "exec":
            res = _run(cmd.get("code") or "")
        else:
            res = {"ok": False, "stderr": "unknown op"}
        sys.stdout.write(json.dumps(res) + "\n")
        sys.stdout.flush()

main()
'''


def _child_limits(res, plan):
    """The worker child's preexec hook: the hardened engine's MANDATORY limit hook.
    It applies and reads back every planned limit and RAISES on any failure, so
    CPython aborts the child before exec and no worker (and no cell) ever runs
    without its limits. There is deliberately no try/except here."""
    def _apply():
        _engine._apply_mandatory_rlimits(res, plan)
    return _apply


def isolation_prerequisites() -> dict:
    """Host-level isolation state for a status surface, without starting a worker.
    READY_TO_PROBE is not an isolation claim: every worker must still attest before
    it receives a cell. Anything else means every cell is refused on this host."""
    cap = _engine.sandbox_capability()
    ready = cap.get("state") == "READY_TO_PROBE"
    return {"state": cap.get("state"), "missing": list(cap.get("missing") or []),
            "isolation": ISOLATION_LABEL if ready else REFUSED_ISOLATION,
            "note": ("each worker attests its isolation before its first cell; a worker "
                     "that does not attest is killed and the cell is refused") if ready else
                    "isolation prerequisites are absent, so every cell is refused"}


def _refusal(error: str, stderr: str = "") -> dict:
    """The kernel's DENY shape: no isolated worker exists, so no cell ran."""
    return {"ok": False, "executed": False, "execution_attempted": False,
            "execution_state": "UNAVAILABLE", "degraded": True, "error": error,
            "stdout": "", "stderr": (stderr or error)[:4000], "exit": -1,
            "isolation": REFUSED_ISOLATION, "wall_s": 0.0}


def _read_line(stream, timeout_s: float):
    """One line from `stream`, or None when none arrives within timeout_s."""
    holder: dict[str, Any] = {}
    done = threading.Event()

    def _read():
        try:
            holder["line"] = stream.readline()
        except Exception as e:  # noqa: BLE001
            holder["error"] = type(e).__name__
        finally:
            done.set()

    threading.Thread(target=_read, daemon=True).start()
    if not done.wait(timeout=timeout_s):
        return None
    return holder.get("line") or ""


class GovernedKernel:
    """One persistent, sandboxed worker process per run_id. Variables persist across
    exec_cell() calls. NEVER raises into the server; a dead/timed-out worker yields a
    DEGRADED result, not a fabricated success."""

    def __init__(self, run_id: str, timeout_s: int = DEFAULT_TIMEOUT_S,
                 mem_mb: int = DEFAULT_MEM_MB):
        self.run_id = run_id
        self.timeout_s = int(timeout_s)
        self.mem_mb = int(mem_mb)
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()
        self._last_vars: dict[str, Any] = {}
        self._cells_run = 0
        self._spawned_at: Optional[float] = None
        self._degraded = False
        # True only while the live worker is one that passed its isolation attestation.
        self._attested = False
        self._refusal: Optional[dict] = None
        # Registry bookkeeping for capacity eviction. _state_lock makes "evict only
        # while idle" and "never start a cell on an evicted kernel" one atomic check.
        self._state_lock = threading.Lock()
        self._busy = 0
        self._evicted = False
        self.last_used = time.time()

    # -- lifecycle --------------------------------------------------------
    def spawn(self) -> dict:
        """Start the worker and keep it ONLY if it attested its isolation. Returns
        {"ok": True, "pid", "attested": True} or the refusal shape (_refusal) with
        execution_attempted=False. Never raises into the server."""
        with self._lock:
            if self._proc and self._proc.poll() is None:
                return {"ok": True, "already": True, "attested": self._attested}
            self._proc = None
            self._attested = False
            try:
                proc, refusal = self._start_attested_worker()
            except Exception as e:  # noqa: BLE001 — never crash the server on spawn
                proc, refusal = None, _refusal(
                    "sandbox unavailable: kernel spawn failed (%s)" % type(e).__name__)
            self._spawned_at = time.time()
            if refusal is not None:
                self._degraded = True
                self._refusal = refusal
                return refusal
            self._proc = proc
            self._attested = True
            self._degraded = False
            self._refusal = None
            return {"ok": True, "pid": proc.pid, "attested": True}

    def _start_attested_worker(self):
        """(proc, None) for a worker that attested, else (None, refusal). Every
        prerequisite is checked BEFORE a process exists; a worker that fails its
        attestation is killed before any cell is sent to it."""
        capability = _engine.sandbox_capability()
        if capability.get("state") != "READY_TO_PROBE":
            return None, _refusal("fixed sandbox isolation prerequisites unavailable",
                                  "missing: %s" % ", ".join(capability.get("missing") or []))
        res, plan, refusal = _engine._plan_mandatory_rlimits(WORKER_CPU_S, self.mem_mb)
        if refusal:
            return None, _refusal(refusal)
        identity, refusal = _engine._parent_identity()
        if refusal:
            return None, _refusal(refusal)

        env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
               "HOME": "/tmp", "no_proxy": "*", "PYTHONUNBUFFERED": "1",
               # pin BLAS/OpenMP to a single thread: under RLIMIT_NPROC=0 a BLAS
               # thread pool cannot be created and OpenBLAS would abort the import.
               "OPENBLAS_NUM_THREADS": "1", "OMP_NUM_THREADS": "1",
               "MKL_NUM_THREADS": "1", "NUMEXPR_NUM_THREADS": "1"}
        # Resolve the trusted-lib site-packages dir in the PARENT (where numpy is
        # installed) and bake it as a literal into the worker source — the worker
        # itself never reads an env var to find it (keeps `-I` isolation honest).
        try:
            import numpy as _np_parent
            _spkg = os.path.dirname(os.path.dirname(_np_parent.__file__))
        except Exception:
            _spkg = ""
        # The engine's attestation runs FIRST in the worker, before the driver loop
        # can read any cell; it exits the worker when any isolation check fails.
        worker_src = _engine._ATTEST_SRC + _WORKER_SRC.replace("__SITE_PACKAGES__",
                                                               json.dumps(_spkg))
        want = [identity["net"], identity["user"], str(identity["uid"])]
        try:
            proc = subprocess.Popen(
                [_engine._UNSHARE, *_engine._UNSHARE_FLAGS, "--",
                 sys.executable, "-I", "-S", "-c", worker_src, *want],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL, text=True, env=env, close_fds=True,
                preexec_fn=_child_limits(res, plan),
            )
        except subprocess.SubprocessError:
            # CPython raises a bare SubprocessError when preexec_fn raised in the
            # forked child; the child exits before exec, so nothing ran.
            return None, _refusal(_engine._LIMIT_HOOK_FAILED_ERROR)
        except Exception as e:  # noqa: BLE001
            return None, _refusal("sandbox unavailable: the kernel worker could not be "
                                  "started (%s: %s)" % (type(e).__name__, e))

        try:
            line = _read_line(proc.stdout, ATTEST_TIMEOUT_S)
            if line is None:
                self._discard(proc)
                return None, _refusal("sandbox unavailable: the kernel worker did not attest "
                                      "its isolation within %ss; no cell ran" % ATTEST_TIMEOUT_S)
            marker, problems, _rest = _engine._attestation(line.encode("utf-8", "replace"),
                                                           identity)
        except Exception:
            self._discard(proc)
            raise
        if marker is None or problems:
            self._discard(proc)
            return None, _refusal("sandbox unavailable: the kernel worker did not attest "
                                  "its isolation; no cell ran", "; ".join(problems))
        return proc, None

    @staticmethod
    def _discard(proc) -> None:
        try:
            proc.kill()
        except Exception:
            pass
        try:
            proc.wait(timeout=2)
        except Exception:
            pass

    def alive(self) -> bool:
        return bool(self._proc and self._proc.poll() is None)

    def touch(self) -> None:
        self.last_used = time.time()

    def is_dead(self) -> bool:
        """Spawned (or spawn attempted) and no longer running. A cold kernel that has
        not run its first cell yet is not dead."""
        return (self._spawned_at is not None or self._degraded) and not self.alive()

    def try_evict(self) -> bool:
        """Mark evicted iff no cell is running. The caller removes it from the
        registry and kills the worker."""
        with self._state_lock:
            if self._busy:
                return False
            self._evicted = True
            return True

    def kill(self) -> None:
        with self._lock:
            if self._proc:
                try:
                    self._proc.kill()
                except Exception:
                    pass
                self._proc = None
            self._attested = False

    # -- execution --------------------------------------------------------
    def exec_cell(self, code: str) -> dict:
        """Execute ALREADY-ALLOWED code in the persistent worker. The hard gate runs
        in a11oy_code_as_action BEFORE this is ever called; this method assumes the
        cell passed the gate. Enforces a per-cell wall-clock timeout; on breach the
        worker is killed and the run is DEGRADED (no fabricated success)."""
        with self._state_lock:
            if self._evicted:
                return {"ok": False, "executed": False, "execution_attempted": False,
                        "degraded": True,
                        "stderr": ("kernel was evicted to free capacity before this cell "
                                   "ran — NOT executed"),
                        "isolation": "not executed — kernel evicted", "wall_s": 0.0}
            self._busy += 1
            self.last_used = time.time()
        try:
            return self._exec_cell(code)
        finally:
            with self._state_lock:
                self._busy -= 1
                self.last_used = time.time()

    def _exec_cell(self, code: str) -> dict:
        if not self.alive():
            # cold or previously killed — (re)spawn a fresh, re-attested worker.
            spawned = self.spawn()
            if not spawned.get("ok"):
                return dict(spawned)
        if not (self.alive() and self._attested):
            self._degraded = True
            return _refusal("sandbox unavailable: no attested kernel worker is running; "
                            "the cell was NOT executed")

        t0 = time.time()
        result_holder: dict[str, Any] = {}
        done = threading.Event()

        def _io():
            try:
                assert self._proc and self._proc.stdin and self._proc.stdout
                self._proc.stdin.write(json.dumps({"op": "exec", "code": code}) + "\n")
                self._proc.stdin.flush()
                line = self._proc.stdout.readline()
                result_holder["line"] = line
            except Exception as e:  # noqa: BLE001
                result_holder["error"] = type(e).__name__
            finally:
                done.set()

        th = threading.Thread(target=_io, daemon=True)
        th.start()
        finished = done.wait(timeout=self.timeout_s)
        wall_s = round(time.time() - t0, 6)

        if not finished:
            # cell exceeded its wall-clock budget — kill the worker, mark DEGRADED.
            self.kill()
            self._degraded = True
            return {"ok": False, "degraded": True, "timeout": True,
                    "execution_attempted": True,
                    "stderr": "cell exceeded %ss wall-clock budget — worker killed"
                              % self.timeout_s,
                    "isolation": ISOLATION_LABEL, "wall_s": wall_s}

        line = result_holder.get("line")
        if not line:
            self.kill()
            self._degraded = True
            return {"ok": False, "degraded": True, "execution_attempted": True,
                    "stderr": "kernel produced no result (worker died: %s)"
                              % result_holder.get("error", "unknown"),
                    "isolation": ISOLATION_LABEL, "wall_s": wall_s}
        try:
            res = json.loads(line)
        except Exception:
            return {"ok": False, "degraded": True, "execution_attempted": True,
                    "stderr": "kernel result not json",
                    "isolation": ISOLATION_LABEL, "wall_s": wall_s}

        self._last_vars = res.get("vars", {}) or {}
        self._cells_run += 1
        res["isolation"] = ISOLATION_LABEL
        res["execution_attempted"] = True
        res["wall_s"] = wall_s
        res["exit"] = 0 if res.get("ok") else 1
        return res

    # -- inspection -------------------------------------------------------
    def var_summary(self) -> dict:
        """Hashed/summarized digests of persistent top-level vars (the INSPECT
        channel). Raw objects never leave the sandbox."""
        return dict(self._last_vars)

    def status(self) -> dict:
        return {
            "run_id": self.run_id,
            "alive": self.alive(),
            "degraded": self._degraded,
            "cells_run": self._cells_run,
            "spawned_at": self._spawned_at,
            "var_names": sorted(self._last_vars.keys()),
            "var_summary": dict(self._last_vars),
            "attested": bool(self._attested and self.alive()),
            "refusal": (self._refusal or {}).get("error"),
            "isolation": ISOLATION_LABEL if self._attested and self.alive() else (
                REFUSED_ISOLATION if self._refusal else
                "not started: the worker attests its isolation when its first cell runs"),
            "limits": {"per_cell_timeout_s": self.timeout_s, "mem_mb": self.mem_mb,
                       "worker_cpu_s": WORKER_CPU_S,
                       "mandatory_rlimits": list(_engine._MANDATORY_RLIMITS),
                       "tier": "restricted subprocess (container/microVM = ROADMAP)"},
        }


# ---------------------------------------------------------------------------
# Process-wide registry of live kernels, one per run_id.
# ---------------------------------------------------------------------------
_KERNELS: dict[str, GovernedKernel] = {}
_DEFAULT_MAX_KERNELS = 4


def _max_kernels_from_env() -> int:
    try:
        return max(1, int(str(os.environ.get("A11OY_MAX_KERNELS", "")).strip()
                          or _DEFAULT_MAX_KERNELS))
    except (TypeError, ValueError):
        return _DEFAULT_MAX_KERNELS


MAX_KERNELS = _max_kernels_from_env()
_REG_LOCK = threading.Lock()


def new_run_id() -> str:
    return "gck_" + uuid.uuid4().hex[:16]


def _free_slots_locked() -> list[GovernedKernel]:
    """With _REG_LOCK held and the registry full: drop every idle dead kernel, then
    (if still full) the least-recently-used idle kernel. A kernel mid-cell is never
    evicted. Returns the evicted kernels so the caller kills them outside the lock."""
    evicted: list[GovernedKernel] = []
    for rid, k in list(_KERNELS.items()):
        if k.is_dead() and k.try_evict():
            evicted.append(_KERNELS.pop(rid))
    if len(_KERNELS) >= MAX_KERNELS:
        for rid, k in sorted(_KERNELS.items(), key=lambda kv: kv[1].last_used):
            if k.try_evict():
                evicted.append(_KERNELS.pop(rid))
                break
    return evicted


def get_kernel(run_id: str, create: bool = False,
               timeout_s: int = DEFAULT_TIMEOUT_S,
               mem_mb: int = DEFAULT_MEM_MB) -> Optional[GovernedKernel]:
    """Return the kernel for run_id (creating it when asked). At MAX_KERNELS, dead
    and then least-recently-used idle kernels are evicted first; None means every
    slot is executing a cell right now (the caller answers an honest 429)."""
    evicted: list[GovernedKernel] = []
    with _REG_LOCK:
        k = _KERNELS.get(run_id)
        if k is not None:
            k.touch()
        elif create:
            if len(_KERNELS) >= MAX_KERNELS:
                evicted = _free_slots_locked()
            if len(_KERNELS) < MAX_KERNELS:
                k = GovernedKernel(run_id, timeout_s=timeout_s, mem_mb=mem_mb)
                _KERNELS[run_id] = k
    for old in evicted:
        old.kill()
    return k


def drop_kernel(run_id: str) -> None:
    with _REG_LOCK:
        k = _KERNELS.pop(run_id, None)
    if k:
        with k._state_lock:
            k._evicted = True  # a stale handle must not respawn an untracked worker
        k.kill()


if __name__ == "__main__":
    # Self-test: persistence across cells + network-deny.
    k = GovernedKernel(new_run_id())
    print("spawn:", k.spawn())
    print("cell1:", k.exec_cell("a = np.arange(10)\nprint(int(a.sum()))"))
    print("cell2 (reuses a):", k.exec_cell("b = a[a > 5]\nprint(b.tolist())"))
    print("net-deny:", k.exec_cell("import socket; socket.socket()"))
    print("status:", json.dumps(k.status(), default=str)[:400])
    k.kill()
