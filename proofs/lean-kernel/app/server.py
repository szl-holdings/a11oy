#!/usr/bin/env python3
"""SZLHOLDINGS/lean-kernel — live Lean/Lake verification kernel.

FastAPI service that:
  - clones / uses the pinned lutar-lean repo,
  - runs `lake build` on demand (streaming),
  - serves canonical numbers LIVE from lean_numbers.py,
  - exposes the theorem table (PROVEN/AXIOM/SORRY + file:line),
  - verifies Λ-receipts against the canonical geometric-mean definition,
  - serves + exercises the 10 golden reference vectors.

HONESTY: if `lake build` fails (e.g. no Mathlib cache / low disk on the box),
healthz and the UI report the failure verbatim. Nothing is faked green.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import subprocess
import time
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

APP_DIR = Path(__file__).resolve().parent
REPO_DIR = Path(os.environ.get("LUTAR_REPO", "/opt/lutar-lean"))
DATA_DIR = APP_DIR / "data"
ELAN_BIN = os.environ.get("ELAN_BIN", "/root/.elan/bin")
os.environ["PATH"] = f"{ELAN_BIN}:{os.environ.get('PATH','')}"

REF_VECTORS_PATH = REPO_DIR / "reference-vectors.json"
if not REF_VECTORS_PATH.exists():
    REF_VECTORS_PATH = DATA_DIR / "reference-vectors.json"

# Cache of last build result (build is expensive; numbers are recomputed live).
_BUILD_STATE: dict = {"status": "unknown", "ran_at": None, "duration_s": None,
                      "exit_code": None, "tail": ""}

app = FastAPI(title="SZLHOLDINGS lean-kernel", version="1.0.0")


# --------------------------------------------------------------------------
# Canonical Λ — geometric mean (matches Lutar/Invariant.lean & lambda-spec.md)
# --------------------------------------------------------------------------
def compute_lambda(values: list[float]) -> float:
    if not values:
        return 0.0
    for v in values:
        if not math.isfinite(v) or v < 0:
            return 0.0
        if v == 0:
            return 0.0
    k = len(values)
    log_sum = sum(math.log(v) for v in values)
    return math.exp(log_sum / k)


def _run(cmd: list[str], cwd: Path, timeout: int = 60) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                          timeout=timeout)


def _repo_sha() -> str:
    try:
        r = _run(["git", "rev-parse", "HEAD"], REPO_DIR, timeout=15)
        return r.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# --------------------------------------------------------------------------
# GET /api/lean/healthz
# --------------------------------------------------------------------------
@app.get("/api/lean/healthz")
def healthz():
    return JSONResponse({
        "ok": True,
        "service": "SZLHOLDINGS/lean-kernel",
        "repo": "szl-holdings/lutar-lean",
        "repo_present": REPO_DIR.exists(),
        "repo_sha": _repo_sha(),
        "toolchain": _toolchain(),
        "build": _BUILD_STATE,
        "ts": int(time.time()),
    })


def _toolchain() -> str:
    tc = REPO_DIR / "lean-toolchain"
    if tc.exists():
        return tc.read_text().strip()
    return "unknown"


# --------------------------------------------------------------------------
# GET /api/lean/numbers  — LIVE from lean_numbers.py against current commit
# --------------------------------------------------------------------------
@app.get("/api/lean/numbers")
def numbers():
    try:
        r = _run(["python3", str(APP_DIR / "lean_numbers.py"),
                  "--repo-path", str(REPO_DIR)], APP_DIR, timeout=60)
        data = json.loads(r.stdout)
        data["live"] = True
        return JSONResponse(data)
    except Exception as e:
        return JSONResponse({"error": str(e), "live": False}, status_code=500)


# --------------------------------------------------------------------------
# GET /api/lean/theorems  — full classified table
# --------------------------------------------------------------------------
@app.get("/api/lean/theorems")
def theorems():
    try:
        r = _run(["python3", str(APP_DIR / "theorem_scan.py"), str(REPO_DIR)],
                 APP_DIR, timeout=60)
        return JSONResponse(json.loads(r.stdout))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# --------------------------------------------------------------------------
# POST /api/lean/verify  — verify a Λ-receipt against the canonical definition
# --------------------------------------------------------------------------
@app.post("/api/lean/verify")
async def verify(request: Request):
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"verified": False, "reason": "invalid JSON"},
                            status_code=400)

    axes = body.get("axes")
    claimed = body.get("lambda", body.get("Lambda"))
    if axes is None:
        return JSONResponse({"verified": False, "reason": "missing 'axes'"},
                            status_code=400)
    if isinstance(axes, dict):
        values = [float(v) for v in axes.values()]
    elif isinstance(axes, list):
        values = [float(v) for v in axes]
    else:
        return JSONResponse({"verified": False, "reason": "'axes' must be list or object"},
                            status_code=400)

    recomputed = compute_lambda(values)
    if claimed is None:
        return JSONResponse({
            "verified": None,
            "recomputed_lambda": recomputed,
            "reason": "no claimed lambda to check; returning canonical recompute",
            "theorem": "Lutar.Invariant.Λ_def (closed form (∏xᵢ)^(1/k))",
        })
    tol_abs, tol_rel = 1e-12, 1e-9
    diff = abs(recomputed - float(claimed))
    ok = diff <= tol_abs + tol_rel * max(abs(recomputed), abs(float(claimed)))
    # which theorem confirms it
    if all(v == values[0] for v in values):
        thm = "Lutar.a3_normalize_proof (Λ k (const c) = c)"
    elif min(values) == 0:
        thm = "Lutar.Invariant.Λ_def + zero-pinning (any axis 0 ⇒ Λ=0)"
    else:
        thm = "Lutar.Invariant.Λ_def (closed-form geomean) + Lutar.min_le_Λ/Λ_le_max bound"
    return JSONResponse({
        "verified": bool(ok),
        "claimed_lambda": float(claimed),
        "recomputed_lambda": recomputed,
        "abs_diff": diff,
        "tolerance": {"abs": tol_abs, "rel": tol_rel},
        "theorem": thm,
        "definition": "Λ_k(x) = (∏ xᵢ)^(1/k)  (unweighted geometric mean)",
    })


# --------------------------------------------------------------------------
# GET /api/lean/build  — trigger `lake build`, stream output (SSE)
# --------------------------------------------------------------------------
@app.get("/api/lean/build")
async def build(stream: bool = True):
    if not stream:
        res = await _do_build_collect()
        return JSONResponse(res)

    async def gen():
        start = time.time()
        yield _sse({"event": "start", "msg": "lake build starting", "cwd": str(REPO_DIR)})
        if not REPO_DIR.exists():
            yield _sse({"event": "error", "msg": "repo not present"})
            return
        proc = await asyncio.create_subprocess_exec(
            f"{ELAN_BIN}/lake", "build",
            cwd=str(REPO_DIR),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env={**os.environ},
        )
        tail = []
        assert proc.stdout
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip("\n")
            tail.append(line)
            tail[:] = tail[-200:]
            yield _sse({"event": "line", "line": line})
        rc = await proc.wait()
        dur = round(time.time() - start, 2)
        status = "pass" if rc == 0 else "fail"
        _BUILD_STATE.update({"status": status, "ran_at": int(time.time()),
                             "duration_s": dur, "exit_code": rc,
                             "tail": "\n".join(tail[-40:])})
        yield _sse({"event": "done", "status": status, "exit_code": rc,
                    "duration_s": dur})

    return StreamingResponse(gen(), media_type="text/event-stream")


async def _do_build_collect() -> dict:
    start = time.time()
    if not REPO_DIR.exists():
        return {"status": "fail", "reason": "repo not present"}
    proc = await asyncio.create_subprocess_exec(
        f"{ELAN_BIN}/lake", "build",
        cwd=str(REPO_DIR),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        env={**os.environ},
    )
    out, _ = await proc.communicate()
    rc = proc.returncode
    dur = round(time.time() - start, 2)
    status = "pass" if rc == 0 else "fail"
    tail = "\n".join(out.decode(errors="replace").splitlines()[-40:])
    _BUILD_STATE.update({"status": status, "ran_at": int(time.time()),
                         "duration_s": dur, "exit_code": rc, "tail": tail})
    return {"status": status, "exit_code": rc, "duration_s": dur, "tail": tail}


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


# --------------------------------------------------------------------------
# GET /api/lean/vectors  — the 10 golden reference vectors
# --------------------------------------------------------------------------
@app.get("/api/lean/vectors")
def vectors():
    try:
        return JSONResponse(json.loads(REF_VECTORS_PATH.read_text()))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


# --------------------------------------------------------------------------
# POST /api/lean/vectors/exercise — recompute each vector's Λ, pass/fail vs pinned
# --------------------------------------------------------------------------
@app.post("/api/lean/vectors/exercise")
def exercise_vectors():
    try:
        spec = json.loads(REF_VECTORS_PATH.read_text())
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)
    tol_abs = spec.get("toleranceAbs", 1e-12)
    tol_rel = spec.get("toleranceRel", 1e-9)
    results = []
    all_pass = True
    for v in spec.get("vectors", []):
        recomputed = compute_lambda([float(a) for a in v["axes"]])
        pinned = float(v["lambda"])
        diff = abs(recomputed - pinned)
        ok = diff <= tol_abs + tol_rel * max(abs(recomputed), abs(pinned))
        all_pass = all_pass and ok
        results.append({"id": v["id"], "pinned_lambda": pinned,
                        "recomputed_lambda": recomputed, "abs_diff": diff,
                        "pass": ok})
    return JSONResponse({
        "definition": spec.get("formula", "Λ_k(x) = (∏ xᵢ)^(1/k)"),
        "tolerance": {"abs": tol_abs, "rel": tol_rel},
        "all_pass": all_pass,
        "count": len(results),
        "results": results,
    })


# --------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
@app.get("/api/lean/", response_class=HTMLResponse)
def ui():
    return (APP_DIR / "index.html").read_text()
