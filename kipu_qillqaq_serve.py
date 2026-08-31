"""a11oy ADDITIVE router — mounts KIPU + QILLQAQ at /v1/kipu, /v1/qillqaq, /v1/kipu/healthz.

Self-contained APIRouter following the WAYRA / a11oy.code pattern in serve.py: import,
include_router BEFORE the SPA catch-all, wrap in try/except so a missing dep can never take
down the SPA. The `kipu_qillqaq` package is vendored alongside this file in the Space root.

Endpoints (all read-only / in-memory; ADDITIVE, no existing route touched):
  GET  /v1/kipu/healthz          -> {"ok": true, "substrate_version": "<kipu_qillqaq.__version__>"}
  GET  /v1/kipu/stats            -> KIPU pool stats (store backend, cell count, RS code)
  POST /v1/kipu/write            -> write a ReceiptCell {organ, kind, payload}; gated nowhere here
  GET  /v1/kipu/read/{cid}       -> read a cell by content address
  GET  /v1/qillqaq/manifest      -> QILLQAQ engine manifest (16 booted organ genomes)
  GET  /v1/qillqaq/organ/{name}  -> one organ's genome info + authorization surface
"""

from __future__ import annotations

import sys
from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter()

# Boot the engine once at import. The package is vendored next to this file in the Space.
try:
    import kipu_qillqaq
    from kipu_qillqaq import QillqaqEngine, KipuPool, ReceiptCell

    _ENGINE = QillqaqEngine(pool=KipuPool(path="/tmp/kipu_a11oy", durability=True))
    _ENGINE.boot_packaged()
    _SUBSTRATE_VERSION = kipu_qillqaq.__version__
    print(f"[kipu_qillqaq] substrate v{_SUBSTRATE_VERSION}, "
          f"{_ENGINE.manifest()['count']} organs booted", file=sys.stderr)
except Exception as _e:  # pragma: no cover
    _ENGINE = None
    _SUBSTRATE_VERSION = None
    print(f"[kipu_qillqaq] NOT mounted ({_e!r})", file=sys.stderr)


@router.get("/v1/kipu/healthz")
def kipu_healthz():
    return {
        "ok": _ENGINE is not None,
        "substrate": "KIPU",
        "engine": "QILLQAQ",
        "substrate_version": _SUBSTRATE_VERSION,
        "organs": _ENGINE.manifest()["count"] if _ENGINE else 0,
    }


@router.get("/v1/kipu/stats")
def kipu_stats():
    if _ENGINE is None:
        return JSONResponse({"error": "substrate unavailable"}, status_code=503)
    return _ENGINE.pool.stats()


@router.post("/v1/kipu/write")
def kipu_write(body: dict):
    if _ENGINE is None:
        return JSONResponse({"error": "substrate unavailable"}, status_code=503)
    cell = ReceiptCell(organ=body.get("organ", "anon"),
                       kind=body.get("kind", "note"),
                       payload=body.get("payload", {}))
    cid = _ENGINE.pool.write(cell)
    return {"cid": cid, "verify": cell.verify()}


@router.get("/v1/kipu/read/{cid}")
def kipu_read(cid: str):
    if _ENGINE is None:
        return JSONResponse({"error": "substrate unavailable"}, status_code=503)
    cell = _ENGINE.pool.read(cid, reader="a11oy")
    if cell is None:
        return JSONResponse({"error": "not found"}, status_code=404)
    return cell.to_dict()


@router.get("/v1/qillqaq/manifest")
def qillqaq_manifest():
    if _ENGINE is None:
        return JSONResponse({"error": "engine unavailable"}, status_code=503)
    return _ENGINE.manifest()


@router.get("/v1/qillqaq/organ/{name}")
def qillqaq_organ(name: str):
    if _ENGINE is None:
        return JSONResponse({"error": "engine unavailable"}, status_code=503)
    agent = _ENGINE.agents.get(name.upper())
    if agent is None:
        return JSONResponse({"error": f"no organ '{name}'"}, status_code=404)
    return agent.info()
