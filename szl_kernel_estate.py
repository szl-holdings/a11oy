# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Stephen P. Lutar · ORCID 0009-0001-0110-4173
"""a11oy kernel-estate organ: actually import+call SZL kernels.

Additive register(app) surface. Missing packages stay UNAVAILABLE — never
fake-green. joblib/pickle are quarantined. GPU cubins are UNAVAILABLE unless
CUDA is really present. Does not add torch to the request path: probes are
optional imports.
"""
from __future__ import annotations

import importlib
import os
import sys
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI
from fastapi.responses import JSONResponse

DOCTRINE = {
    "version": "v11",
    "lambda": "Conjecture 1",
    "locked_proven": 8,
    "joblib": "QUARANTINED",
    "pickle": "QUARANTINED",
}

ESTATE: Tuple[Dict[str, str], ...] = (
    {"key": "szl-kernels", "module": "szl_kernels", "hub_id": "SZLHOLDINGS/szl-kernels", "probe": "selfcheck"},
    {"key": "szl-governed-norm", "module": "szl_governed_norm", "hub_id": "SZLHOLDINGS/szl-governed-norm", "probe": "selfcheck"},
    {"key": "szl-lambda-gate", "module": "szl_lambda_gate", "hub_id": "SZLHOLDINGS/szl-lambda-gate", "probe": "selfcheck"},
    {"key": "governed-inference-meter", "module": "governed_inference_meter", "hub_id": "SZLHOLDINGS/governed-inference-meter", "probe": "selfcheck"},
    {"key": "szl-receipt-attn", "module": "szl_receipt_attn", "hub_id": "SZLHOLDINGS/szl-receipt-attn", "probe": "selfcheck"},
    {"key": "szl-maskmod", "module": "szl_maskmod", "hub_id": "SZLHOLDINGS/szl-maskmod", "probe": "selfcheck"},
    {"key": "szl-block-kv", "module": "szl_block_kv", "hub_id": "SZLHOLDINGS/szl-block-kv", "probe": "selfcheck"},
    {"key": "YARQA-ATTN", "module": "yarqa_attn", "hub_id": "SZLHOLDINGS/YARQA-ATTN", "probe": "selfcheck"},
    {"key": "szl-ouroboros", "module": "szl_ouroboros", "hub_id": "SZLHOLDINGS/szl-ouroboros", "probe": "selfcheck"},
    {"key": "szl-invariants", "module": "szl_invariants", "hub_id": "SZLHOLDINGS/szl-invariants", "probe": "selfcheck"},
    {"key": "szl-formulas", "module": "szl_formulas", "hub_id": "SZLHOLDINGS/szl-formulas", "probe": "selfcheck"},
    {"key": "szl-blocked", "module": "szl_blocked", "hub_id": "SZLHOLDINGS/szl-blocked", "probe": "selfcheck"},
    {"key": "szl-govsign", "module": "szl_govsign", "hub_id": "SZLHOLDINGS/szl-govsign", "probe": "selfcheck"},
    {"key": "szl-provctl", "module": "szl_provctl", "hub_id": "SZLHOLDINGS/szl-provctl", "probe": "selfcheck"},
    {"key": "szl-nemo", "module": "szl_nemo", "hub_id": "SZLHOLDINGS/szl-nemo", "probe": "rule_check"},
    {"key": "szl-serve", "module": "szl_serve", "hub_id": "SZLHOLDINGS/szl-serve", "probe": "selfcheck"},
)


def list_estate() -> List[Dict[str, str]]:
    return [dict(e) for e in ESTATE]


def cuda_status() -> Dict[str, Any]:
    try:
        import torch  # type: ignore

        if bool(torch.cuda.is_available()):
            try:
                name = str(torch.cuda.get_device_name(0))
            except Exception:
                name = "cuda:0"
            return {"status": "LIVE", "device": name}
    except Exception as exc:
        return {
            "status": "UNAVAILABLE",
            "reason": f"{type(exc).__name__}: {exc}",
            "note": "GPU kernels stay ROADMAP; no fake CUDA",
        }
    return {
        "status": "UNAVAILABLE",
        "reason": "torch.cuda.is_available() is False",
        "note": "GPU kernels stay ROADMAP; no fake CUDA",
    }


def _extend_sys_path() -> None:
    extra = os.environ.get("SZL_KERNEL_PATHS", "")
    if not extra:
        return
    for raw in extra.split(os.pathsep):
        path = raw.strip()
        if path and path not in sys.path:
            sys.path.insert(0, path)


def _summarize(result: Any) -> Any:
    if result is None or isinstance(result, (str, int, float, bool)):
        return result
    if isinstance(result, tuple) and len(result) == 2 and isinstance(result[0], bool):
        ok, violated = result
        return {"ok": ok, "violated": list(violated) if violated is not None else []}
    if isinstance(result, dict):
        out: Dict[str, Any] = {}
        for key in ("ok", "version", "label", "path", "lambda", "note"):
            if key in result:
                out[key] = result[key]
        if "ok" not in out and "arithmetic_ok" in result:
            out["ok"] = bool(result["arithmetic_ok"])
        return out or {"keys": sorted(result.keys())[:12]}
    return type(result).__name__


def _call_probe(mod: Any, probe: str) -> Any:
    if probe == "rule_check":
        return getattr(mod, "rule_check")(
            "hello", "this is MEASURED software, not a score"
        )
    fn = getattr(mod, probe, None)
    if fn is None:
        raise AttributeError(f"{getattr(mod, '__name__', '?')} has no {probe}()")
    return fn()


def probe_member(entry: Dict[str, str]) -> Dict[str, Any]:
    rec = dict(entry)
    rec["joblib"] = "QUARANTINED"
    rec["pickle"] = "QUARANTINED"
    try:
        mod = importlib.import_module(entry["module"])
    except Exception as exc:
        rec.update(
            {
                "status": "UNAVAILABLE",
                "called": False,
                "reason": f"{type(exc).__name__}: {exc}",
            }
        )
        return rec
    try:
        result = _call_probe(mod, entry["probe"])
        rec.update(
            {
                "status": "LIVE",
                "via": f"{entry['module']}.{entry['probe']}",
                "called": True,
                "probe_result": _summarize(result),
            }
        )
        return rec
    except Exception as exc:
        rec.update(
            {
                "status": "UNAVAILABLE",
                "called": True,
                "reason": f"{type(exc).__name__}: {exc}",
            }
        )
        return rec


def probe_estate() -> Dict[str, Any]:
    _extend_sys_path()
    kernels = [probe_member(dict(e)) for e in ESTATE]
    live = sum(1 for k in kernels if k.get("status") == "LIVE")
    return {
        "ok": True,
        "live": live,
        "enumerated": len(kernels),
        "cuda": cuda_status(),
        "doctrine": DOCTRINE,
        "joblib": "QUARANTINED",
        "pickle": "QUARANTINED",
        "lambda": "Conjecture 1 (advisory)",
        "kernels": kernels,
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    @app.get(f"/api/{ns}/v1/kernel-estate", include_in_schema=False)
    async def _estate() -> JSONResponse:
        return JSONResponse(probe_estate())

    @app.get(f"/api/{ns}/v1/kernel-estate/{{key}}", include_in_schema=False)
    async def _one(key: str) -> JSONResponse:
        entry: Optional[Dict[str, str]] = next(
            (dict(e) for e in ESTATE if e["key"] == key), None
        )
        if entry is None:
            return JSONResponse(
                {"status": "UNAVAILABLE", "reason": f"unknown kernel {key!r}"},
                status_code=404,
            )
        _extend_sys_path()
        return JSONResponse(probe_member(entry))

    return (
        f"kernel-estate mounted: GET /api/{ns}/v1/kernel-estate "
        f"({len(ESTATE)} kernels; import+call or honest UNAVAILABLE)"
    )
