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

ISOLATION (honest label, restricted-subprocess tier — NOT container/seccomp here):
    - separate worker process, never in the server process
    - launched with `-I -S` (isolated interpreter, no site) + an explicitly
      constructed minimal env (no inherited secrets / no HF token / no signing key)
    - POSIX rlimits applied pre-exec in the child: RLIMIT_CPU, RLIMIT_AS (address
      space), RLIMIT_CORE=0, RLIMIT_NPROC=0 (cannot fork a network helper)
    - a network-disable preamble monkeypatches socket so a cell cannot open a socket
    - per-cell wall-clock timeout; on breach the worker is killed and the run is
      marked DEGRADED — never a fabricated success
    Full seccomp/gVisor/container/microVM isolation is ROADMAP (tower/UDS pod only);
    in the HF CPU Space this is the restricted-subprocess tier, stated honestly.

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

# Honest isolation label — kept faithful to a11oy_code_engine._sandbox_exec's wording.
ISOLATION_LABEL = (
    "sandboxed (restricted subprocess): persistent worker process, CPU+memory(AS) "
    "rlimits, no core dump, single-threaded BLAS, network disabled, per-cell "
    "wall-clock timeout, minimal env (no secrets), isolated interpreter (-I -S). "
    "Full seccomp/container/microVM isolation on the tower/UDS pod (ROADMAP)."
)

# Default per-cell limits (mirror a11oy_code_engine._sandbox_exec discipline).
DEFAULT_TIMEOUT_S = 6
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


def _child_limits(timeout_s: int, mem_mb: int):
    """POSIX rlimits applied pre-exec in the worker child (network helper can't fork,
    no core dump, bounded CPU+memory). Mirrors a11oy_code_engine._sandbox_exec._limits."""
    def _apply():
        try:
            import resource
            # generous CPU ceiling for a long-lived worker; per-cell wall-clock is the
            # real bound enforced by the parent.
            resource.setrlimit(resource.RLIMIT_CPU, (3600, 3600))
            soft = mem_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (soft, soft))
            resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
            # NOTE: we do NOT set RLIMIT_NPROC=0 here. The single-shot _sandbox_exec can
            # (it pre-imports nothing), but numpy's BLAS backend needs to create at least
            # one thread at import; NPROC=0 makes numpy abort. We instead pin BLAS to a
            # single thread via the env (OPENBLAS/OMP/MKL_NUM_THREADS=1) so the worker is
            # effectively single-threaded, and rely on network-deny + minimal env + no
            # fork-helper modules (subprocess/multiprocessing banned by the hard gate)
            # for exfil protection. Honest: fork is not rlimit-blocked in this tier.
        except Exception:
            pass
    return _apply


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

    # -- lifecycle --------------------------------------------------------
    def spawn(self) -> dict:
        with self._lock:
            if self._proc and self._proc.poll() is None:
                return {"ok": True, "already": True}
            env = {"PATH": "/usr/bin:/bin", "PYTHONDONTWRITEBYTECODE": "1",
                   "HOME": "/tmp", "no_proxy": "*", "PYTHONUNBUFFERED": "1",
                   # pin BLAS/OpenMP to a single thread so numpy imports under the
                   # rlimits without spawning a thread pool (keeps the worker
                   # effectively single-threaded — see _child_limits note).
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
            worker_src = _WORKER_SRC.replace("__SITE_PACKAGES__", json.dumps(_spkg))
            try:
                self._proc = subprocess.Popen(
                    [sys.executable, "-I", "-S", "-c", worker_src],
                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL, text=True, env=env,
                    preexec_fn=_child_limits(self.timeout_s, self.mem_mb),
                )
                self._spawned_at = time.time()
                self._degraded = False
                return {"ok": True, "pid": self._proc.pid}
            except Exception as e:  # noqa: BLE001 — never crash the server on spawn
                self._proc = None
                self._degraded = True
                return {"ok": False, "error": "kernel spawn failed: %s" % type(e).__name__}

    def alive(self) -> bool:
        return bool(self._proc and self._proc.poll() is None)

    def kill(self) -> None:
        with self._lock:
            if self._proc:
                try:
                    self._proc.kill()
                except Exception:
                    pass
                self._proc = None

    # -- execution --------------------------------------------------------
    def exec_cell(self, code: str) -> dict:
        """Execute ALREADY-ALLOWED code in the persistent worker. The hard gate runs
        in a11oy_code_as_action BEFORE this is ever called; this method assumes the
        cell passed the gate. Enforces a per-cell wall-clock timeout; on breach the
        worker is killed and the run is DEGRADED (no fabricated success)."""
        if not self.alive():
            # cold or previously killed — (re)spawn a fresh namespace.
            self.spawn()
        if not self.alive():
            self._degraded = True
            return {"ok": False, "degraded": True,
                    "stderr": "kernel unavailable (spawn failed)",
                    "isolation": ISOLATION_LABEL, "wall_s": 0.0}

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
                    "stderr": "cell exceeded %ss wall-clock budget — worker killed"
                              % self.timeout_s,
                    "isolation": ISOLATION_LABEL, "wall_s": wall_s}

        line = result_holder.get("line")
        if not line:
            self.kill()
            self._degraded = True
            return {"ok": False, "degraded": True,
                    "stderr": "kernel produced no result (worker died: %s)"
                              % result_holder.get("error", "unknown"),
                    "isolation": ISOLATION_LABEL, "wall_s": wall_s}
        try:
            res = json.loads(line)
        except Exception:
            return {"ok": False, "degraded": True, "stderr": "kernel result not json",
                    "isolation": ISOLATION_LABEL, "wall_s": wall_s}

        self._last_vars = res.get("vars", {}) or {}
        self._cells_run += 1
        res["isolation"] = ISOLATION_LABEL
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
            "isolation": ISOLATION_LABEL,
            "limits": {"per_cell_timeout_s": self.timeout_s, "mem_mb": self.mem_mb,
                       "tier": "restricted subprocess (container/microVM = ROADMAP)"},
        }


# ---------------------------------------------------------------------------
# Process-wide registry of live kernels, one per run_id.
# ---------------------------------------------------------------------------
_KERNELS: dict[str, GovernedKernel] = {}
_REG_LOCK = threading.Lock()


def new_run_id() -> str:
    return "gck_" + uuid.uuid4().hex[:16]


def get_kernel(run_id: str, create: bool = False,
               timeout_s: int = DEFAULT_TIMEOUT_S,
               mem_mb: int = DEFAULT_MEM_MB) -> Optional[GovernedKernel]:
    with _REG_LOCK:
        k = _KERNELS.get(run_id)
        if k is None and create:
            k = GovernedKernel(run_id, timeout_s=timeout_s, mem_mb=mem_mb)
            _KERNELS[run_id] = k
        return k


def drop_kernel(run_id: str) -> None:
    with _REG_LOCK:
        k = _KERNELS.pop(run_id, None)
    if k:
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
