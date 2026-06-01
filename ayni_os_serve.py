"""a11oy ADDITIVE router — mounts AYNI-OS at /v1/ayni, /v1/replay, /v1/tinkuy.

Self-contained APIRouter following the kipu_qillqaq_serve.py / WAYRA pattern: import,
include_router BEFORE the SPA catch-all, wrap in try/except so a missing dep can never
take down the SPA. The `ayni_os` package is vendored alongside this file in the Space.

HONEST NAMING (Zero-Bandaid Law):
- "/v1/replay?at=<ts>" reconstructs past state by EVENT-SOURCING REPLAY of signed KIPU
  receipts — NOT "quantum time-travel". No physics claim.
- "Ayni" is a GAME-THEORY primitive: direct reciprocity (Axelrod & Hamilton 1981;
  Trivers 1971). No mysticism.
- "Tinkuy" is the KURAMOTO (1975) order parameter r across organ phases. No mysticism.

LOCKED preserved: 749/14/163, 13-axis yuyay_v3, replay bacf5443…631fc5,
A2=IsHomogeneous, A4=IsBounded, SLSA L1, Λ Conjecture 1. ADDITIVE only.

Endpoints (read-only / in-memory; ADDITIVE, no existing route touched):
  GET /v1/ayni             -> per-organ Ayni coefficients + HUKLLA T24 deficit report
  GET /v1/replay?at=<ts>   -> verifiable reconstructed state at past timestamp T
  GET /v1/tinkuy           -> current Kuramoto order parameter r + flow state
  GET /v1/ayni/healthz     -> liveness + LOCKED-numbers echo
"""
from __future__ import annotations

import math
import sys
import time

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter()

try:
    from ayni_os.ledger import ReciprocityLedger, ORGANS
    from ayni_os.checkpoint import CheckpointStore
    from ayni_os.tinkuy import TinkuyMonitor
    from ayni_os.replay_api import AyniService

    # Live in-memory demo state so the tab renders meaningful numbers. A real
    # deployment would feed this from the KIPU receipt stream; this is a seeded,
    # honest, balanced ledger for visualization.
    _LED = ReciprocityLedger()
    _t = time.time() - 3600
    _LED.record_exchange(taker="amaru", giver="sentra", resource="gpu_min",
                         amount=12.0, pair_id="seed1", ts=_t)
    _LED.record_exchange(taker="rosie", giver="vessels", resource="tokens",
                         amount=8.0, pair_id="seed2", ts=_t + 600)
    _LED.reciprocate(organ="sentra", resource="gpu_min", amount=12.0,
                     pair_id="seed1", ts=_t + 1200)
    _LED.reciprocate(organ="amaru", resource="gpu_min", amount=12.0,
                     pair_id="seed1b", ts=_t + 1300)
    _LED.reciprocate(organ="rosie", resource="tokens", amount=8.0,
                     pair_id="seed2", ts=_t + 1400)
    _LED.reciprocate(organ="vessels", resource="tokens", amount=8.0,
                     pair_id="seed2b", ts=_t + 1500)
    _STORE = CheckpointStore()
    _STORE.force_checkpoint(_LED, at_ts=_t + 1000)
    _TINKUY = TinkuyMonitor()
    for _i, _o in enumerate(ORGANS):
        _TINKUY.set_phase(_o, 0.02 * _i)   # near-coherent -> flow demo
    _SVC = AyniService(ledger=_LED, store=_STORE, tinkuy=_TINKUY)
    _OK = True
    print("[ayni_os] AYNI-OS mounted at /v1/ayni + /v1/replay + /v1/tinkuy",
          file=sys.stderr)
except Exception as _e:  # pragma: no cover
    _SVC = None
    _OK = False
    print(f"[ayni_os] NOT mounted ({_e!r})", file=sys.stderr)


@router.get("/v1/ayni/healthz")
def ayni_healthz():
    return {
        "ok": _OK,
        "module": "AYNI-OS",
        "framing": "game-theory primitive (Axelrod-Hamilton 1981); NOT mystical",
        "locked_numbers": {"declarations": 749, "unique_axioms": 14, "sorries": 163,
                           "yuyay_v3_axes": 13},
        "yuyay_v3_replay_hash":
            "bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5",
    }


@router.get("/v1/ayni")
def ayni():
    if _SVC is None:
        return JSONResponse({"error": "AYNI-OS unavailable"}, status_code=503)
    return _SVC.get_ayni()


@router.get("/v1/replay")
def replay(at: float = Query(..., description="target unix timestamp T")):
    if _SVC is None:
        return JSONResponse({"error": "AYNI-OS unavailable"}, status_code=503)
    return _SVC.get_replay(at)


@router.get("/v1/tinkuy")
def tinkuy():
    if _SVC is None:
        return JSONResponse({"error": "AYNI-OS unavailable"}, status_code=503)
    return _SVC.get_tinkuy()
