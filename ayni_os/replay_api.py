"""AYNI-OS HTTP API — verifiable state at any past moment + reciprocity + flow.

Endpoints (ADDITIVE; do not touch existing a11oy routes):
  GET /v1/ayni             -> per-organ Ayni coefficients + T24 deficit report
  GET /v1/replay?at=<ts>   -> verifiable reconstructed state at past timestamp T
                              (event-sourcing replay; honest naming)
  GET /v1/tinkuy           -> current Kuramoto order parameter r + flow state

Uses FastAPI if available; otherwise exposes a pure-stdlib WSGI/dispatch `handle()`
so the logic is testable and runnable without extra deps (open-source only).
"""
from __future__ import annotations

import json
from dataclasses import asdict
from typing import Optional

from .ledger import ReciprocityLedger, ORGANS
from .checkpoint import CheckpointStore
from .rewind import reconstruct_at
from .reciprocity_monitor import scan
from .tinkuy import TinkuyMonitor


class AyniService:
    """Holds the live ledger, checkpoint store, and tinkuy monitor."""

    def __init__(self, ledger: Optional[ReciprocityLedger] = None,
                 store: Optional[CheckpointStore] = None,
                 tinkuy: Optional[TinkuyMonitor] = None) -> None:
        self.ledger = ledger or ReciprocityLedger()
        self.store = store or CheckpointStore()
        self.tinkuy = tinkuy or TinkuyMonitor()

    # ---- endpoint logic (framework-agnostic) ---------------------------
    def get_ayni(self) -> dict:
        report = scan(self.ledger)
        return {
            "alphas": report.alphas,
            "deficits": [asdict(d) for d in report.deficits],
            "halt": report.halt,
            "tripwire": "T24",
            "alpha_min": 0.45,
            "alpha_balanced": 0.5,
        }

    def get_replay(self, at: float) -> dict:
        st = reconstruct_at(self.ledger, target_ts=float(at), store=self.store)
        d = asdict(st)
        d["mechanism"] = "event-sourcing-replay"   # honest: NOT time travel
        d["chain_verified"] = st.chain_ok
        return d

    def get_tinkuy(self) -> dict:
        st = self.tinkuy.state()
        d = asdict(st)
        d["model"] = "kuramoto-1975-order-parameter"
        return d

    # ---- stdlib dispatcher (no framework needed) -----------------------
    def handle(self, path: str, query: Optional[dict] = None) -> tuple[int, dict]:
        query = query or {}
        if path == "/v1/ayni":
            return 200, self.get_ayni()
        if path == "/v1/replay":
            if "at" not in query:
                return 400, {"error": "missing required query param 'at' (timestamp)"}
            return 200, self.get_replay(query["at"])
        if path == "/v1/tinkuy":
            return 200, self.get_tinkuy()
        return 404, {"error": f"no route {path}"}


def build_fastapi_app(service: Optional[AyniService] = None):
    """Return a FastAPI app if FastAPI is installed; else None."""
    try:
        from fastapi import FastAPI, Query
    except Exception:
        return None
    svc = service or AyniService()
    app = FastAPI(title="AYNI-OS", version="1.0-additive")

    @app.get("/v1/ayni")
    def ayni():                       # noqa: ANN202
        return svc.get_ayni()

    @app.get("/v1/replay")
    def replay(at: float = Query(...)):   # noqa: ANN202
        return svc.get_replay(at)

    @app.get("/v1/tinkuy")
    def tinkuy():                     # noqa: ANN202
        return svc.get_tinkuy()

    return app
