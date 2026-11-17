#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Metadata and explicit retirement for the legacy Khipu CPU-lab proxy.

GET/HEAD status is local metadata only. POST chat returns 410 without reading,
forwarding or recording a prompt. Generation requires an authenticated request
and explicit public-prompt acknowledgement at the existing Atelier CPU-lab
turn route. This compatibility module never probes inference or mints receipts.
Lambda uniqueness remains Conjecture 1.
"""
import sys
from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse

_HERE = Path(__file__).parent.resolve()
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from packages.inference.src.voters.khipu_gguf import (
    KHIPU_LAB_V1,
    KHIPU_RETIRED_REASON,
    khipu_pin,
    khipu_successor,
)
from szl_be_hardening import DOCTRINE_LOCK

_STATUS_PATH = "/api/a11oy/v1/khipu/status"
_CHAT_PATH = "/api/a11oy/v1/khipu/chat"
_CANONICAL_LOCKED_FORMULA_IDS = frozenset({"F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"})
_CANONICAL_LOCKED_FORMULA_COUNT = len(_CANONICAL_LOCKED_FORMULA_IDS)


def _doctrine_status() -> dict:
    """Copy the lock only when it is exactly the canonical locked-eight set."""
    doctrine = DOCTRINE_LOCK if isinstance(DOCTRINE_LOCK, dict) else {}
    raw_ids = doctrine.get("locked_formula_ids")
    ids = list(raw_ids) if isinstance(raw_ids, list) else []
    count = doctrine.get("locked_formula_count")
    lambda_value = doctrine.get("lambda")
    valid = (
        doctrine.get("doctrine") == "v11"
        and doctrine.get("state") == "LOCKED"
        and count == _CANONICAL_LOCKED_FORMULA_COUNT
        and not isinstance(count, bool)
        and len(ids) == count
        and all(isinstance(item, str) for item in ids)
        and frozenset(ids) == _CANONICAL_LOCKED_FORMULA_IDS
    )
    if not valid:
        count = None
        ids = []
    return {
        "version": doctrine.get("doctrine") if valid else "UNAVAILABLE",
        "state": "LOCKED" if valid else "UNAVAILABLE",
        "source": "szl_be_hardening.DOCTRINE_LOCK",
        "locked_formula_count": count,
        "locked_formula_ids": ids,
        "lambda": lambda_value if isinstance(lambda_value, str) else "UNAVAILABLE",
    }


def _honesty() -> dict:
    return {
        "lab": "RETIRED generation route; metadata only, runtime not probed",
        "lab_v1": KHIPU_LAB_V1,
        "gpu_inference_endpoint": "ROADMAP",
        "forge_lab": "SNAPSHOT — not a trainer, not Serve Studio",
        "energy_attested_runs": "UNAVAILABLE",
        "ask_and_act": "not a live control plane",
        "killinchu_detector": "SIMULATED",
        "lambda": "Conjecture 1",
        "tokens_per_second": "not reported",
        "signing": "UNAVAILABLE — upstream signature state is not verified by this proxy",
    }


def _retirement() -> dict:
    return {
        "ok": False,
        "state": "RETIRED",
        "lab_status": "RETIRED",
        "error": KHIPU_RETIRED_REASON,
        "successor": khipu_successor(),
        "operational": False,
        "inference_performed": False,
        "receipt_emitted": False,
        "automatically_forwarded": False,
        "text": None,
        "signature": "UNKNOWN",
        "record_sha256": "UNKNOWN",
        "usage": {},
        "usage_label": "UNAVAILABLE",
        "elapsed_ms": None,
        "elapsed_ms_label": "UNAVAILABLE",
        "receipt_evidence_label": "UNAVAILABLE",
        "signature_evidence_label": "UNAVAILABLE",
        "record_hash_evidence_label": "UNAVAILABLE",
        "pin": khipu_pin(),
        "honesty": _honesty(),
        "doctrine": _doctrine_status(),
    }


async def _handle_status(request: Request) -> JSONResponse:
    payload = {
        **_retirement(),
        "healthz": None,
        "health_observation": "NOT_PROBED",
        "measured_probe": {"label": "UNAVAILABLE", "reason": "retired route; no inference performed"},
    }
    return JSONResponse(payload, headers={"Cache-Control": "no-store"})


async def _handle_chat(request: Request) -> JSONResponse:
    # Do not consume or forward a legacy body: it carries no current consent.
    return JSONResponse(
        {**_retirement(), "http_status": 410},
        status_code=410,
        headers={"Cache-Control": "no-store"},
    )


def register(app) -> str:
    """Mount one retirement route per path before the SPA fallback."""
    paths = {_STATUS_PATH, _CHAT_PATH}
    app.router.routes[:] = [
        route for route in app.router.routes
        if getattr(route, "path", None) not in paths
    ]
    app.add_api_route(_STATUS_PATH, _handle_status, methods=["GET", "HEAD"], include_in_schema=False)
    app.add_api_route(_CHAT_PATH, _handle_chat, methods=["POST"], include_in_schema=False)
    for target in (_STATUS_PATH, _CHAT_PATH):
        for index, route in enumerate(app.router.routes):
            if getattr(route, "path", None) == target:
                app.router.routes.insert(0, app.router.routes.pop(index))
                break
    return (
        "%s + %s (legacy generation RETIRED; no forwarding; "
        "metadata only; Lambda=Conjecture 1)"
        % (_STATUS_PATH, _CHAT_PATH)
    )


if __name__ == "__main__":
    from fastapi import FastAPI, Request
    from starlette.testclient import TestClient

    app = FastAPI()

    async def _ok_status(request: Request):
        return JSONResponse({"lab_status": "READY"})

    app.add_api_route(_STATUS_PATH, _ok_status, methods=["GET"])
    st = register(app)
    assert _STATUS_PATH in st and _CHAT_PATH in st
    c = TestClient(app)
    r = c.get(_STATUS_PATH)
    assert r.status_code == 200
    print("a11oy_khipu_chat: ALL OK — %s" % st)
