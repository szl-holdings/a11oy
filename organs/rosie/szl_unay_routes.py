# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries · 13-axis
# Signed: Yachay.  git trailer: Perplexity Computer Agent
"""
szl_unay_routes.py — ADDITIVE FastAPI module mounting UNAY + Khipu-LMDB v2 organs.

Single integration point (mirrors szl_live_wires / szl_khipu_os):

    import szl_unay_routes
    szl_unay_routes.register(app, ns="rosie")

Routes added (per namespace `ns`), ALL under /api/{ns}/v2/* (NEW namespace — never
collides with the existing /api/{ns}/v1/* routes; ADDITIVE only):

  UNAY (receipt-keyed semantic memory):
    GET  /api/{ns}/v2/unay/healthz         — 200 + version string
    GET  /api/{ns}/v2/unay/stats           — store stats (backend, totals, head)
    POST /api/{ns}/v2/unay/remember        — {text, meta?} -> receipt
    POST /api/{ns}/v2/unay/recall          — {q|query, k?} -> ranked memories
    GET  /api/{ns}/v2/unay/recall?q=...     — GET form for quick curl checks
    GET  /api/{ns}/v2/unay/verify          — append-only chain integrity

  KHIPU-LMDB (durable hash-chained receipts):
    GET  /api/{ns}/v2/khipu/lmdb/stats     — entry count + DB path (durable)
    POST /api/{ns}/v2/khipu/lmdb/append    — {action, payload?} -> receipt
    GET  /api/{ns}/v2/khipu/lmdb/verify    — full on-disk chain re-walk
    GET  /api/{ns}/v2/khipu/lmdb/tail?n=   — last n receipts

  REPLICATION (inbound accepted; outbound DISABLED by default):
    POST /api/{ns}/v2/khipu/replicate      — accept inbound receipts (verified)
    GET  /api/{ns}/v2/khipu/replicate/status

Persistence paths default to /data (HF Spaces persistent disk) when writable,
else a local dir, so the LMDB file SURVIVES Space rebuilds where /data persists,
and at minimum survives in-process restarts within a build.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any, Dict, List

try:
    from fastapi import Request
    from fastapi.responses import JSONResponse
except Exception:  # pragma: no cover
    Request = JSONResponse = None  # type: ignore

# Make sibling modules importable whether they sit beside this file or on path.
_HERE = os.path.dirname(os.path.abspath(__file__))
for _p in (_HERE, os.path.dirname(_HERE)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import szl_unay  # noqa: E402
import szl_khipu_lmdb  # noqa: E402
import szl_khipu_replicate  # noqa: E402


async def _safe_json_dict(request: Any):
    """Parse a JSON request body, tolerating empty / malformed / wrong-type input.

    Returns ``(body, None)`` on a valid JSON object, or ``(None, response)`` with a
    clean 400 otherwise. Guards the unguarded ``await request.json()`` pattern that
    otherwise surfaces as an opaque HTTP 500 on bad input.
    """
    try:
        body = await request.json()
    except Exception:
        return None, JSONResponse({"error": "invalid JSON body"}, status_code=400)
    if not isinstance(body, dict):
        return None, JSONResponse({"error": "body must be a JSON object"}, status_code=400)
    return body, None


def _pick_data_dir() -> str:
    """Pick a writable runtime directory for the live DBs.

    Priority: $UNAY_DATA_DIR, $ROSIE_DATA_DIR, /data, /home/user/data, ./_unay_data,
    /tmp/unay_data. NOTE: on an HF Space WITHOUT persistent storage these paths are
    ephemeral across REBUILDS (but durable across in-container restarts). Cross-
    rebuild durability is provided separately by _restore_snapshot() seeding the
    LMDB from a snapshot committed in the repo at /_unay_snapshot (honest: the repo
    is the durable store when no persistent disk is attached).
    """
    cands = [
        os.environ.get("UNAY_DATA_DIR"),
        os.environ.get("ROSIE_DATA_DIR"),
        "/data",
        "/home/user/data",
        os.path.join(_HERE, "_unay_data"),
        "/tmp/unay_data",
    ]
    for cand in cands:
        if not cand:
            continue
        try:
            os.makedirs(cand, exist_ok=True)
            testf = os.path.join(cand, ".wtest")
            with open(testf, "w") as f:
                f.write("ok")
            os.remove(testf)
            return cand
        except Exception:
            continue
    return "/tmp"


def _restore_snapshot(lmdb_path: str, ns: str) -> bool:
    """Seed the live LMDB dir from a repo-committed snapshot, if one exists.

    On a Space without persistent storage, the repo is the only thing that
    survives a rebuild. We commit a snapshot of the LMDB (data.mdb) into the repo
    under _unay_snapshot/khipu_lmdb_<ns>/ at deploy time; at BOOT this copies it
    into the live (ephemeral) data dir so the receipts are present after every
    rebuild. This is real durable persistence backed by git object storage.
    """
    snap = os.path.join(_HERE, "_unay_snapshot", f"khipu_lmdb_{ns}")
    src = os.path.join(snap, "data.mdb")
    dst = os.path.join(lmdb_path, "data.mdb")
    try:
        if os.path.exists(src) and not os.path.exists(dst):
            os.makedirs(lmdb_path, exist_ok=True)
            import shutil
            shutil.copy(src, dst)
            return True
    except Exception:
        pass
    return False


def register(app: Any, ns: str = "szl") -> Dict[str, Any]:
    """Mount UNAY + Khipu-LMDB v2 routes on `app` under /api/{ns}/v2/*."""
    if Request is None:
        return {"registered": False, "reason": "fastapi not available"}

    data_dir = _pick_data_dir()
    unay_path = os.path.join(data_dir, f"unay_{ns}.sqlite")
    lmdb_path = os.path.join(data_dir, f"khipu_lmdb_{ns}")
    repl_path = os.path.join(data_dir, f"khipu_repl_{ns}")

    # Seed the LMDB from a repo-committed snapshot (survives rebuilds where the
    # filesystem does not). No-op if no snapshot is present in the repo.
    snapshot_restored = _restore_snapshot(lmdb_path, ns)

    store = szl_unay.UnayStore(path=unay_path, organ="unay", ns=ns)
    klmdb = szl_khipu_lmdb.KhipuLMDB(path=lmdb_path, organ="khipu", ns=ns)
    # inbound replication mirror — separate LMDB, never spliced into primary
    repl_store = szl_khipu_lmdb.KhipuLMDB(path=repl_path, organ="khipu-repl", ns=ns)

    def _source_fn(since_seq: int) -> List[Dict[str, Any]]:
        out = []
        total = klmdb.stats()["entries"]
        for s in range(since_seq, total):
            r = klmdb.get_by_seq(s)
            if r:
                out.append(r)
        return out

    replicator = szl_khipu_replicate.Replicator(
        local_organ=ns, peers=[], source_fn=_source_fn
    )

    # ---------------------------------------------------------------- UNAY
    @app.get(f"/api/{ns}/v2/unay/healthz")
    async def unay_healthz() -> Any:  # noqa: ANN401
        return JSONResponse({"ok": True, "version": szl_unay.__version__, "organ": "unay", "ns": ns})

    @app.get(f"/api/{ns}/v2/unay/stats")
    async def unay_stats() -> Any:  # noqa: ANN401
        return JSONResponse(store.stats())

    @app.post(f"/api/{ns}/v2/unay/remember")
    async def unay_remember(request: Request) -> Any:  # noqa: ANN401
        body, _err = await _safe_json_dict(request)
        if _err is not None:
            return _err
        text = body.get("text", "")
        if not text:
            return JSONResponse({"error": "text required"}, status_code=400)
        rcpt = store.remember(text, meta=body.get("meta") or {}, vector=body.get("vector"))
        return JSONResponse(rcpt)

    async def _do_recall(query: str, k: int) -> Any:
        if not query:
            return JSONResponse({"error": "q/query required"}, status_code=400)
        results = store.recall(query, k=k)
        return JSONResponse({"query": query, "k": k, "results": results, "backend": store.backend})

    @app.post(f"/api/{ns}/v2/unay/recall")
    async def unay_recall_post(request: Request) -> Any:  # noqa: ANN401
        body, _err = await _safe_json_dict(request)
        if _err is not None:
            return _err
        query = body.get("q") or body.get("query") or ""
        return await _do_recall(query, int(body.get("k", 5)))

    @app.get(f"/api/{ns}/v2/unay/recall")
    async def unay_recall_get(q: str = "", k: int = 5) -> Any:  # noqa: ANN401
        return await _do_recall(q, int(k))

    @app.get(f"/api/{ns}/v2/unay/verify")
    async def unay_verify() -> Any:  # noqa: ANN401
        return JSONResponse(store.verify_chain())

    # ---------------------------------------------------------- KHIPU-LMDB
    @app.get(f"/api/{ns}/v2/khipu/lmdb/stats")
    async def khipu_lmdb_stats() -> Any:  # noqa: ANN401
        return JSONResponse(klmdb.stats())

    @app.post(f"/api/{ns}/v2/khipu/lmdb/append")
    async def khipu_lmdb_append(request: Request) -> Any:  # noqa: ANN401
        body, _err = await _safe_json_dict(request)
        if _err is not None:
            return _err
        action = body.get("action", "note")
        rcpt = klmdb.append(action, payload=body.get("payload") or {})
        return JSONResponse(rcpt)

    @app.get(f"/api/{ns}/v2/khipu/lmdb/verify")
    async def khipu_lmdb_verify() -> Any:  # noqa: ANN401
        return JSONResponse(klmdb.verify())

    @app.get(f"/api/{ns}/v2/khipu/lmdb/tail")
    async def khipu_lmdb_tail(n: int = 10) -> Any:  # noqa: ANN401
        return JSONResponse({"tail": klmdb.tail(int(n))})

    # ----------------------------------------------------------- REPLICATION
    @app.post(f"/api/{ns}/v2/khipu/replicate")
    async def khipu_replicate(request: Request) -> Any:  # noqa: ANN401
        body, _err = await _safe_json_dict(request)
        if _err is not None:
            return _err
        receipts = body.get("receipts", [])
        if not isinstance(receipts, list):
            return JSONResponse({"error": "receipts must be a list"}, status_code=400)
        accepted, rejected = 0, 0
        for r in receipts:
            if not isinstance(r, dict) or "digest" not in r:
                rejected += 1
                continue
            if szl_khipu_replicate.verify_inbound(r):
                if repl_store.get_by_receipt(r["digest"]) is None:
                    repl_store.append("replicated", payload={"origin": r})
                accepted += 1
            else:
                rejected += 1
        return JSONResponse(
            {"accepted": accepted, "rejected": rejected, "mirror_entries": repl_store.stats()["entries"]}
        )

    @app.get(f"/api/{ns}/v2/khipu/replicate/status")
    async def khipu_replicate_status() -> Any:  # noqa: ANN401
        return JSONResponse(replicator.status())

    return {
        "registered": True,
        "ns": ns,
        "data_dir": data_dir,
        "unay_backend": store.backend,
        "lmdb_version": ".".join(str(x) for x in __import__("lmdb").version()),
        "replication_enabled": replicator.enabled,
        "snapshot_restored": snapshot_restored,
        "lmdb_entries_at_boot": klmdb.stats()["entries"],
    }
