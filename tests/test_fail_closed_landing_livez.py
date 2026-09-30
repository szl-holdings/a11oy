# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Fail-closed: HTTP 200 is REACHABLE; livez is process liveness only.

Catch/missing evidence is UNAVAILABLE. Lambda is Conjecture 1. No fabricated
MEASURED/LIVE/ATO/joules.
"""
from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

import szl_runtime_contracts as contracts

ROOT = Path(__file__).resolve().parents[1]
LANDING = ROOT / "a11oy_landing.html"
HOLO_OPS = ROOT / "console" / "3d" / "holographic.html"
RELOCK = ROOT / ".github" / "scripts" / "verify_canonical_a11oy.py"
CONSOLES = (
    ROOT / "console" / "index.html",
    ROOT / "pages" / "console.html",
    ROOT / "pages_console.html",
)


def test_console_mesh_org_catch_is_unavailable() -> None:
    for path in CONSOLES:
        text = path.read_text(encoding="utf-8")
        assert 'badge b-live">ok' not in text.split("async function mesh_load()", 1)[1].split(
            "async function lambda_load()", 1
        )[0].split("}catch(e){", 1)[1], path
        org = text.split("async function organism_load()", 1)[1]
        org_catch = org.split("}catch(e){", 1)[1].split("async function chain_load()", 1)[0]
        assert 'badge b-live">ok' not in org_catch, path
        assert "b-err\">UNAVAILABLE" in org_catch, path
        assert "status:'ok',latency_ms:0,http_code:200" not in text, path


def test_landing_http_200_is_reachable_not_measured() -> None:
    landing = LANDING.read_text(encoding="utf-8")
    assert "HTTP 200 is REACHABLE" in landing
    assert "HTTP 200 is not MEASURED" in landing
    assert "Read live from a running endpoint this session" not in landing
    assert 'liveChip("overview")' not in landing
    assert 'liveChip("genome")' not in landing
    assert 'liveChip("lambda/org")' not in landing
    assert 'grayChip("REACHABLE · overview")' in landing
    assert 'grayChip("REACHABLE · genome")' in landing
    assert 'grayChip("REACHABLE · lambda/org")' in landing
    assert 'pulseState("health", "MEASURED"' not in landing
    assert 'pulseState("ledger", "MEASURED"' not in landing
    assert 'chip.className = "chip live"' not in landing
    assert "RUNTIME REACHABLE" in landing
    assert 'state === "LIVE" || state === "REACHABLE"' not in landing
    amber = landing.split("amberStates", 1)[1].split(";", 1)[0]
    assert '"REACHABLE"' in amber
    assert 'grayChip("SNAPSHOT "+observed+" · DIGEST OK · HTTP 200 is REACHABLE")' in landing
    assert 'grayChip("MEASURED · SNAPSHOT "+observed+" · DIGEST OK")' not in landing


def test_livez_is_process_alive_not_production_live() -> None:
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse

    app = FastAPI()

    @app.get("/{full_path:path}")
    async def spa(full_path: str):
        return HTMLResponse("<html></html>")

    contracts.register(app)
    body = TestClient(app).get("/api/livez").json()
    assert body["status"] == "PROCESS_ALIVE"
    assert body["production_ready"] is False
    assert body["receipt_minted"] is False
    assert "process liveness only" in body["scope"]
    assert body["status"] != "LIVE"
    assert body["status"] != "MEASURED"


def test_holographic_ops_accepts_process_alive_not_live() -> None:
    text = HOLO_OPS.read_text(encoding="utf-8")
    assert 'p.status==="LIVE"' not in text
    assert 'p.status==="PROCESS_ALIVE"' in text
    assert "p.production_ready===false" in text
    assert "p.receipt_minted===false" in text
    assert "Process liveness" in text
    assert 'pill.textContent=ok?"LIVE"' not in text
    assert 'pill.textContent=ok?"PROCESS_UP":"UNAVAILABLE"' in text
    assert 'def.id==="livez"' in text


def test_relock_requires_process_alive_not_live() -> None:
    src = RELOCK.read_text(encoding="utf-8")
    assert 'payload.get("status") != "LIVE"' not in src
    assert 'payload.get("status") != "PROCESS_ALIVE"' in src
    assert 'payload.get("production_ready") is not False' in src
    assert "liveness route is not process-only/read-only" in src
    assert "liveness route is not LIVE/read-only" not in src
