# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries.
# Λ = Conjecture 1 (Λ-Aggregator Uniqueness; NOT a closed theorem).
"""
szl_be_hardening.py — backend hardening for every SZL organ.

One module, registered ADDITIVELY onto an existing FastAPI `app` via
`harden(app, organ="a11oy")`. It NEVER replaces existing routes and NEVER
crashes the host app (every block is try/except-guarded), in keeping with the
per-organ "register(app, ns=...)" discipline already used across the fleet.

What it wires (HONESTY OVER CHECKLIST — see the per-item honest labels):

  1. INPUT VALIDATION    real pydantic models on the hardening endpoints
                          (`/api/<organ>/v1/echo`, `/api/<organ>/v1/khipu/append`).
                          Raw dicts are rejected with a 422 error envelope.
  2. RATE LIMITING        60 req/min per client IP. Prefers `slowapi`; if that
                          import is unavailable it falls back to a real stdlib
                          sliding-window limiter middleware (no fake pass-through).
  3. OPENAPI              FastAPI's own auto-generated spec, re-served verbatim at
                          `/api/<organ>/openapi.json` (real schema, not a stub).
  4. HEALTH PROBES        `/healthz` (liveness — process is up) and `/readyz`
                          (readiness — opens the durable Khipu store and re-walks
                          the hash chain; NOT ready if the chain is broken).
  5. STRUCTURED LOGGING   JSON logs to stderr with trace_id, span_id, organ,
                          level, msg, plus method/path/status/latency_ms. A
                          per-request trace/span id is generated and surfaced in
                          the `X-Trace-Id` / `X-Span-Id` response headers.
  6. ERROR ENVELOPES      every HTTPException / validation error / unhandled
                          exception returns the uniform envelope:
                          {"error": {code, message, trace_id, doctrine: "v11"}}.
  7. PERSISTENCE          DurableKhipu — a real SQLite-backed, append-only,
                          SHA3-256 hash-chained receipt store (Python stdlib
                          `sqlite3`, zero new pip installs). Receipts survive a
                          process restart. If the disk path is unwritable it
                          falls back to a JSON-file store, then to in-memory
                          (each fallback is reported honestly via /readyz).
  9. HONEST FOOTER        `/honest` returns the EXACT v11 lock footer:
                          749/14/163 @ c7c0ba17, Λ = Conjecture 1.

Stdlib only, with OPTIONAL slowapi. No mocks in any non-test path.

Signed-off-by: Greene (BE) <greene@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import sys
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Doctrine constants — the v11 LOCK. These are load-bearing; tests assert them.
# ---------------------------------------------------------------------------
DOCTRINE = "v11"
DOCTRINE_LOCK = {
    "doctrine": "v11",
    "state": "LOCKED",
    "declarations": 749,
    "axioms": 14,
    "sorries": 163,
    "commit": "c7c0ba17",
    "lambda": "Conjecture 1",
    "lambda_note": "Λ-Aggregator Uniqueness — Conjecture 1, NOT a closed theorem.",
}
DOCTRINE_FOOTER = "Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1"

_GENESIS = "0" * 64
RATE_LIMIT_PER_MIN = 60


# ---------------------------------------------------------------------------
# Pydantic request models — defined at MODULE scope so FastAPI can resolve the
# body annotations (local classes inside harden() become unresolved ForwardRefs
# and FastAPI then mis-reads the param as a query field). Real validation:
# extra="forbid" rejects raw/unknown keys with a 422 error envelope.
# ---------------------------------------------------------------------------
# Module-scope FastAPI/Starlette imports so that, under `from __future__ import
# annotations`, FastAPI can resolve route handler annotations (Request, etc.)
# from this module's globals. Guarded: absence is handled gracefully in harden().
try:
    from fastapi import Request  # noqa: F401
    from fastapi.responses import JSONResponse  # noqa: F401
except Exception:  # pragma: no cover
    Request = Any  # type: ignore
    JSONResponse = Any  # type: ignore

try:
    from pydantic import BaseModel as _BaseModel, Field as _Field, ConfigDict as _ConfigDict

    class EchoIn(_BaseModel):
        model_config = _ConfigDict(extra="forbid")
        message: str = _Field(..., min_length=1, max_length=4096)

    class KhipuAppendIn(_BaseModel):
        model_config = _ConfigDict(extra="forbid")
        action: str = _Field(..., min_length=1, max_length=256)
        payload: Dict[str, Any] = _Field(default_factory=dict)
except Exception:  # pydantic absent -> harden() will no-op the validated routes
    EchoIn = None  # type: ignore
    KhipuAppendIn = None  # type: ignore


# ===========================================================================
# 7. DURABLE PERSISTENCE — SQLite-backed, hash-chained Khipu receipt store.
# ===========================================================================
class DurableKhipu:
    """Append-only, SHA3-256 hash-chained Khipu store with durable backends.

    Backend selection (honest, reported via .backend):
      "sqlite"  — real on-disk SQLite DB; survives process restart (preferred).
      "json"    — on-disk JSON file (if sqlite path unwritable).
      "memory"  — in-process list (last resort; NOT durable — reported as such).

    The hash chain is identical regardless of backend: receipt[n].prev ==
    receipt[n-1].digest, digest = SHA3-256 over the canonical body. verify()
    re-walks the entire chain and returns (ok, depth, first_break_seq).
    """

    def __init__(self, organ: str, ns: Optional[str] = None,
                 path: Optional[str] = None) -> None:
        self.organ = organ
        self.ns = ns or organ
        self._lock = threading.RLock()
        self.backend = "memory"
        self._mem: List[Dict[str, Any]] = []
        self._db: Optional[sqlite3.Connection] = None
        self._json_path: Optional[str] = None

        # Resolve a writable path. Honor an env override; else a per-organ default.
        default_dir = os.environ.get(
            "SZL_KHIPU_DIR", os.environ.get("HOME", "/tmp") + "/.szl_khipu"
        )
        self._path = path or os.path.join(default_dir, f"khipu_{self.ns}.sqlite3")

        try:
            os.makedirs(os.path.dirname(self._path), exist_ok=True)
            self._db = sqlite3.connect(self._path, check_same_thread=False)
            self._db.execute(
                "CREATE TABLE IF NOT EXISTS khipu ("
                "seq INTEGER PRIMARY KEY, action TEXT NOT NULL, "
                "payload TEXT NOT NULL, prev TEXT NOT NULL, "
                "digest TEXT NOT NULL, ts REAL NOT NULL)"
            )
            self._db.commit()
            self.backend = "sqlite"
        except Exception:  # disk unwritable -> JSON file fallback
            try:
                self._json_path = self._path + ".json"
                os.makedirs(os.path.dirname(self._json_path), exist_ok=True)
                if os.path.exists(self._json_path):
                    with open(self._json_path) as fh:
                        self._mem = json.load(fh)
                self.backend = "json"
            except Exception:
                self.backend = "memory"

    @staticmethod
    def _digest(obj: Any) -> str:
        raw = json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha3_256(raw).hexdigest()

    def _all(self) -> List[Dict[str, Any]]:
        if self.backend == "sqlite" and self._db is not None:
            cur = self._db.execute(
                "SELECT seq, action, payload, prev, digest, ts FROM khipu ORDER BY seq"
            )
            return [
                {"seq": r[0], "action": r[1], "payload": json.loads(r[2]),
                 "prev": r[3], "digest": r[4], "ts": r[5]}
                for r in cur.fetchall()
            ]
        return list(self._mem)

    def count(self) -> int:
        with self._lock:
            if self.backend == "sqlite" and self._db is not None:
                return int(self._db.execute("SELECT COUNT(*) FROM khipu").fetchone()[0])
            return len(self._mem)

    def head(self) -> str:
        with self._lock:
            rows = self._all()
            return rows[-1]["digest"] if rows else _GENESIS

    def emit(self, action: str, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        payload = payload or {}
        with self._lock:
            rows = self._all()
            prev = rows[-1]["digest"] if rows else _GENESIS
            seq = len(rows)
            body = {"organ": self.organ, "ns": self.ns, "seq": seq,
                    "action": action, "payload": payload, "prev": prev}
            digest = self._digest(body)
            ts = time.time()
            rec = dict(body, digest=digest, ts=ts)
            if self.backend == "sqlite" and self._db is not None:
                self._db.execute(
                    "INSERT INTO khipu(seq, action, payload, prev, digest, ts) "
                    "VALUES (?,?,?,?,?,?)",
                    (seq, action, json.dumps(payload, sort_keys=True), prev, digest, ts),
                )
                self._db.commit()
            else:
                self._mem.append(rec)
                if self.backend == "json" and self._json_path:
                    with open(self._json_path, "w") as fh:
                        json.dump(self._mem, fh)
            return rec

    def verify(self) -> Tuple[bool, int, int]:
        """Re-walk the chain. Returns (ok, depth, first_break_seq | -1)."""
        with self._lock:
            rows = self._all()
            prev = _GENESIS
            for i, rec in enumerate(rows):
                # organ/ns are store-level constants (not persisted per row in the
                # sqlite backend); reconstruct the canonical body deterministically.
                body = {"organ": self.organ, "ns": self.ns, "seq": rec["seq"],
                        "action": rec["action"], "payload": rec["payload"],
                        "prev": rec["prev"]}
                if rec["prev"] != prev or rec["digest"] != self._digest(body):
                    return (False, len(rows), i)
                prev = rec["digest"]
            return (True, len(rows), -1)

    def tail(self, n: int = 10) -> List[Dict[str, Any]]:
        with self._lock:
            return self._all()[-n:]


# ===========================================================================
# 5. STRUCTURED JSON LOGGING
# ===========================================================================
class _JsonLogFormatter(logging.Formatter):
    def __init__(self, organ: str) -> None:
        super().__init__()
        self.organ = organ

    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created)),
            "level": record.levelname,
            "organ": self.organ,
            "trace_id": getattr(record, "trace_id", None),
            "span_id": getattr(record, "span_id", None),
            "msg": record.getMessage(),
        }
        for k in ("method", "path", "status", "latency_ms"):
            v = getattr(record, k, None)
            if v is not None:
                entry[k] = v
        return json.dumps(entry, separators=(",", ":"))


def _make_logger(organ: str) -> logging.Logger:
    logger = logging.getLogger(f"szl.{organ}.be")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        h = logging.StreamHandler(sys.stderr)
        h.setFormatter(_JsonLogFormatter(organ))
        logger.addHandler(h)
    return logger


# ===========================================================================
# main entrypoint
# ===========================================================================
def harden(app: Any, organ: str, ns: Optional[str] = None,
           khipu_path: Optional[str] = None) -> Dict[str, Any]:
    """Register all hardening surfaces onto `app`. Never raises."""
    ns = ns or organ
    base = f"/api/{organ}/v1"
    # Hardening endpoints live under a collision-free /be/ subpath so they can
    # never be shadowed by a pre-existing organ sub-app mounted at /api/<organ>
    # (e.g. a catch-all /khipu/{receipt_id}). Health/readyz/honest/openapi keep
    # their REQUIRED canonical paths.
    hbase = f"/api/{organ}/v1/be"
    logger = _make_logger(organ)
    report: Dict[str, Any] = {"organ": organ, "registered": []}

    try:
        from fastapi import FastAPI
        from fastapi.exceptions import RequestValidationError
        from starlette.exceptions import HTTPException as StarletteHTTPException
    except Exception as exc:  # FastAPI not importable -> nothing to do
        report["error"] = f"fastapi/pydantic unavailable: {exc!r}"
        return report

    # ---- durable store (item 7) -------------------------------------------
    store = DurableKhipu(organ, ns=ns, path=khipu_path)
    report["khipu_backend"] = store.backend
    # expose for the host app + tests
    setattr(app.state, "be_khipu", store) if hasattr(app, "state") else None

    # ---- error envelope helper (item 6) -----------------------------------
    def _envelope(code: str, message: str, trace_id: str, status: int) -> "JSONResponse":
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "message": message,
                               "trace_id": trace_id, "doctrine": DOCTRINE}},
        )

    # ---- 5 + 6: trace/span middleware, JSON logs, error envelopes ---------
    @app.middleware("http")
    async def _trace_log_mw(request: "Request", call_next):
        # Inbound trace context (W3C-ish) or generate.
        trace_id = request.headers.get("x-trace-id") or uuid.uuid4().hex
        span_id = uuid.uuid4().hex[:16]
        request.state.trace_id = trace_id
        request.state.span_id = span_id
        t0 = time.time()
        try:
            resp = await call_next(request)
        except StarletteHTTPException as he:  # mapped below too, but be safe
            dt = round((time.time() - t0) * 1000, 2)
            logger.warning("http_exception", extra={"trace_id": trace_id,
                "span_id": span_id, "method": request.method,
                "path": request.url.path, "status": he.status_code, "latency_ms": dt})
            r = _envelope("http_error", str(he.detail), trace_id, he.status_code)
            r.headers["X-Trace-Id"] = trace_id
            r.headers["X-Span-Id"] = span_id
            return r
        except Exception as exc:  # unhandled -> uniform 500 envelope
            dt = round((time.time() - t0) * 1000, 2)
            logger.error(f"unhandled:{exc!r}", extra={"trace_id": trace_id,
                "span_id": span_id, "method": request.method,
                "path": request.url.path, "status": 500, "latency_ms": dt})
            r = _envelope("internal_error", "internal server error", trace_id, 500)
            r.headers["X-Trace-Id"] = trace_id
            r.headers["X-Span-Id"] = span_id
            return r
        dt = round((time.time() - t0) * 1000, 2)
        resp.headers["X-Trace-Id"] = trace_id
        resp.headers["X-Span-Id"] = span_id
        logger.info("request", extra={"trace_id": trace_id, "span_id": span_id,
            "method": request.method, "path": request.url.path,
            "status": resp.status_code, "latency_ms": dt})
        return resp

    # Exception handlers so HTTPException/validation errors get the envelope
    # even on routes that bypass middleware error mapping.
    @app.exception_handler(StarletteHTTPException)
    async def _http_exc_handler(request: "Request", exc: "StarletteHTTPException"):
        tid = getattr(request.state, "trace_id", uuid.uuid4().hex)
        return _envelope("http_error", str(exc.detail), tid, exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation_handler(request: "Request", exc: "RequestValidationError"):
        tid = getattr(request.state, "trace_id", uuid.uuid4().hex)
        return _envelope("validation_error", json.dumps(exc.errors(), default=str), tid, 422)

    report["registered"].append("structured_logging+error_envelopes")

    # ---- 2: rate limiting — 60 req/min per IP -----------------------------
    # We register the slowapi Limiter when the library is present (satisfies the
    # "slowapi or starlette-limiter" doctrine and exposes app.state.limiter for
    # any per-route decorators), but we ENFORCE the global 60/min/IP cap with our
    # own sliding-window middleware so that EVERY 429 returns the uniform error
    # envelope (slowapi's built-in handler returns a non-envelope body). This is
    # a real limiter (counts real requests), not a pass-through.
    rate_lib = "none"
    try:
        from slowapi import Limiter
        from slowapi.util import get_remote_address
        app.state.limiter = Limiter(key_func=get_remote_address,
                                    default_limits=[f"{RATE_LIMIT_PER_MIN}/minute"])
        rate_lib = "slowapi"
    except Exception:
        rate_lib = "stdlib-only"

    _hits: Dict[str, Deque[float]] = defaultdict(deque)
    _rl_lock = threading.Lock()

    @app.middleware("http")
    async def _rate_limit_mw(request: "Request", call_next):
        ip = request.client.host if request.client else "unknown"
        now = time.time()
        with _rl_lock:
            dq = _hits[ip]
            while dq and dq[0] <= now - 60.0:
                dq.popleft()
            if len(dq) >= RATE_LIMIT_PER_MIN:
                tid = getattr(request.state, "trace_id", uuid.uuid4().hex)
                r = _envelope("rate_limited",
                              f"rate limit exceeded: {RATE_LIMIT_PER_MIN}/min per IP",
                              tid, 429)
                r.headers["Retry-After"] = "60"
                return r
            dq.append(now)
        return await call_next(request)

    report["rate_limiting"] = f"sliding-window/60-per-min (lib={rate_lib})"
    report["registered"].append(f"rate_limiting:60/min (lib={rate_lib})")

    # ---- 1: pydantic models on hardening endpoints (module-scope) ---------
    # EchoIn / KhipuAppendIn are defined at module level above.

    # ---- 4: health probes -------------------------------------------------
    @app.get(f"{base}/healthz", tags=["health"])
    @app.get("/healthz", tags=["health"])
    async def _healthz():
        return {"status": "ok", "organ": organ, "doctrine": DOCTRINE,
                "lock": "749/14/163", "commit": "c7c0ba17"}

    @app.get(f"{base}/readyz", tags=["health"])
    @app.get("/readyz", tags=["health"])
    async def _readyz():
        ok, depth, brk = store.verify()
        body = {"status": "ready" if ok else "degraded", "organ": organ,
                "khipu_backend": store.backend, "khipu_durable": store.backend in ("sqlite", "json"),
                "khipu_depth": depth, "khipu_chain_ok": ok,
                "khipu_first_break_seq": brk, "doctrine": DOCTRINE}
        return JSONResponse(body, status_code=200 if ok else 503)

    report["registered"].append("healthz+readyz")

    # ---- 1 + 7: validated echo + khipu append/verify/tail -----------------
    @app.post(f"{hbase}/echo", tags=["hardening"])
    async def _echo(body: EchoIn, request: "Request"):
        tid = getattr(request.state, "trace_id", None)
        return {"echo": body.message, "trace_id": tid, "doctrine": DOCTRINE}

    @app.post(f"{hbase}/khipu/append", tags=["khipu"])
    async def _khipu_append(body: KhipuAppendIn):
        rec = store.emit(body.action, body.payload)
        return {"ok": True, "receipt": rec, "backend": store.backend}

    @app.get(f"{hbase}/khipu/verify", tags=["khipu"])
    async def _khipu_verify():
        ok, depth, brk = store.verify()
        return {"ok": ok, "depth": depth, "first_break_seq": brk,
                "backend": store.backend, "durable": store.backend in ("sqlite", "json"),
                "head": store.head(), "doctrine": DOCTRINE}

    @app.get(f"{hbase}/khipu/tail", tags=["khipu"])
    async def _khipu_tail(n: int = 10):
        n = max(1, min(int(n), 100))
        return {"receipts": store.tail(n), "count": store.count(),
                "backend": store.backend}

    report["registered"].append("validated_echo+khipu_persistence")

    # ---- 3: re-serve FastAPI's real OpenAPI at the organ path -------------
    # Primary: the app's own auto-generated schema. Some organs mount sub-apps /
    # Gradio whose combined schema generation can raise; in that case we fall
    # back to FastAPI's get_openapi over THIS app's own APIRoutes (still a real,
    # auto-generated spec — never a hand-written stub).
    @app.get(f"/api/{organ}/openapi.json", include_in_schema=False)
    async def _organ_openapi():
        try:
            return app.openapi()
        except Exception:
            try:
                from fastapi.openapi.utils import get_openapi
                from fastapi.routing import APIRoute
                all_routes = [r for r in app.routes if isinstance(r, APIRoute)]
                # Some pre-existing organ routes carry annotations FastAPI cannot
                # turn into a schema (e.g. a bare JSONResponse return type under
                # `from __future__ import annotations`). Drop only the offending
                # routes so the rest of the REAL auto-generated spec still serves.
                good = []
                for r in all_routes:
                    try:
                        get_openapi(title=organ, version="0", routes=[r])
                        good.append(r)
                    except Exception:
                        continue
                return get_openapi(
                    title=getattr(app, "title", organ),
                    version=getattr(app, "version", "0.0.0"),
                    routes=good,
                )
            except Exception as exc:
                return JSONResponse(
                    {"error": {"code": "openapi_unavailable", "message": str(exc),
                               "trace_id": "openapi", "doctrine": DOCTRINE}},
                    status_code=500,
                )

    report["registered"].append(f"openapi:/api/{organ}/openapi.json")

    # ---- 9: honest footer -------------------------------------------------
    @app.get("/honest", tags=["doctrine"])
    @app.get(f"{base}/honest", tags=["doctrine"])
    async def _honest():
        return {
            "organ": organ,
            "doctrine_lock": DOCTRINE_LOCK,
            "footer": DOCTRINE_FOOTER,
            "honest_labels": {
                "lambda": "Λ-Aggregator Uniqueness is Conjecture 1 — NOT a theorem.",
                "khipu_signatures": "Chain integrity is SHA3-256 hash-chain verified; "
                                    "DSSE signature is a separately-labelled cosign concern.",
                "persistence": f"Khipu receipts persist via backend={store.backend} "
                               f"(durable={store.backend in ('sqlite','json')}).",
                "principle": "HONESTY OVER CHECKLIST.",
            },
        }

    report["registered"].append("honest_footer")
    report["ok"] = True
    logger.info("hardening registered", extra={"trace_id": "boot", "span_id": "boot"})
    return report
