"""
szl_lake_ingest.py — Unified Receipt Ledger ingest router for the a11oy Space
Doctrine v11 LOCKED 749/14/163 | kernel c7c0ba17 | Λ = Conjecture 1 (OPEN)

Vendored + adapted from szl-holdings/szl-lake (szl_lake_server.py routes), same
org, Apache-2.0 — vendored as a per-file copy rather than a cross-repo dependency
so the import resolves offline in the a11oy HF Space image.

Mounts the Unified Receipt Ledger onto the LIVE a11oy FastAPI app under
/api/lake/v1 so a11oy is the one durable sink every SZL component POSTs to:

  POST /api/lake/v1/receipts     ingest one receipt (JSON object), a JSON array,
                                 or an NDJSON batch (Content-Type x-ndjson)
  GET  /api/lake/v1/receipts     query: ?organ=&since=&limit=
  GET  /api/lake/v1/chain/head   per-organ Khipu chain head + count: ?organ=
  GET  /api/lake/v1/health       store reachable, total + per-organ counts

Routing: raw Starlette Route objects inserted at the HEAD of app.router.routes —
the PROVEN serve.py pattern (szl_governed_api.register) so the new namespace wins
over the /api/a11oy/{path:path} Node proxy + the /{full_path:path} SPA catch-all.

DURABILITY (honest) — the a11oy Space runs storage=None / cpu-basic, so the local
$SZL_LAKE_DIR NDJSON store (szl_lake_store.ReceiptLedger) backs the live API for
the CURRENT process only and resets on every Space rebuild. To make receipts
survive rebuilds, EVERY receipt is ALSO mirrored fire-and-forget to the durable HF
dataset SZLHOLDINGS/a11oy-verifiable-corpus (prefix ``lake/``) via the existing
szl_hf_bucket.HFBucket (debounced background commit using the HF_TOKEN already in
the Space env). The mirror NEVER blocks a governed turn and NEVER raises — a
dataset hiccup degrades honestly (status recorded, receipt still served locally).

On boot, hydrate_from_dataset() replays the mirrored receipts back through the
local ledger so the in-process Khipu chain head is reconstructed from the durable
dataset (best-effort, in a daemon thread; honest no-op when huggingface_hub / the
token / the repo are absent). See HYDRATE/ROADMAP notes inline.

stdlib + (optional) szl_hf_bucket. Apache-2.0 — SZL Holdings 2026.
"""
# NOTE: deliberately NO `from __future__ import annotations` here — this file
# defines Starlette route handlers (KNOWN_GOTCHAS #3: lazy PEP-563 annotations
# break FastAPI/Pydantic validation at runtime).

import json
import os
import sys
import threading

from szl_lake_store import get_default_ledger

API_PREFIX = "/api/lake/v1"

# Durable mirror target — the existing public "verify-it-yourself" dataset.
CORPUS_REPO_DEFAULT = "SZLHOLDINGS/a11oy-verifiable-corpus"
# Dataset directory (prefix) for the unified-ledger receipt stream, kept separate
# from the existing receipts/ theorems/ formulas/ prefixes used by szl_corpus_publish.
LAKE_PREFIX = "lake"
# Documented env contract — the one sink URL other components (ouroboros / hatun /
# router / mesh / vsp-otel / trust) POST to. The parent sets the Space env var;
# this is the code-level default + documentation anchor.
RECEIPT_SINK_URL = "https://szlholdings-a11oy.hf.space/api/lake/v1"

_bucket = None
_bucket_lock = threading.Lock()
_hydrated = False
_hydrate_lock = threading.Lock()


def corpus_repo():
    return os.environ.get("SZL_CORPUS_REPO") or CORPUS_REPO_DEFAULT


def _get_bucket():
    """Cached HFBucket for the durable dataset mirror. Returns None (honest
    degrade) when huggingface_hub / token / repo are unavailable — never raises."""
    global _bucket
    with _bucket_lock:
        if _bucket is not None:
            return _bucket
        try:
            from szl_hf_bucket import HFBucket  # lazy: heavy-ish import
        except Exception:
            return None
        try:
            b = HFBucket(repo_id=corpus_repo(), source="a11oy", prefix=LAKE_PREFIX)
            b.start()
        except Exception:
            return None
        _bucket = b
        return b


def _mirror_to_dataset(receipt):
    """Fire-and-forget durable mirror of one receipt to the HF dataset.

    HFBucket.append writes to a local queue file (fast, no network) and nudges a
    debounced background flusher, so this does not block the caller's hot path.
    Never raises; returns an honest status dict."""
    try:
        b = _get_bucket()
        if b is None:
            return {"ok": False, "reason": "hf dataset mirror unavailable "
                    "(no HF_TOKEN / repo / huggingface_hub) — local-only this process"}
        res = b.append(receipt, kind="lake_receipt")
        return {"ok": True, "queued": res.get("queued"), "state": res.get("state")}
    except Exception as e:  # never raise into a governed turn
        return {"ok": False, "reason": "mirror error: %r" % (e,)}


def record_receipt(receipt, organ="a11oy"):
    """In-process ingest — the entry point a11oy's own governed turns call.

    Appends to the local durable ledger (idempotent on receipt id/hash) AND
    mirrors to the HF dataset for cross-rebuild durability. Non-blocking, never
    raises. Returns the ledger append result with a ``mirror`` status attached."""
    try:
        if not isinstance(receipt, dict):
            return {"accepted": False, "error": "receipt must be a JSON object"}
        rec = dict(receipt)
        rec.setdefault("organ", organ)
        result = get_default_ledger().append(rec)
        result["mirror"] = _mirror_to_dataset(rec)
        return result
    except Exception as e:  # honest, non-blocking
        return {"accepted": False, "error": "record_receipt failed: %r" % (e,)}


def hydrate_from_dataset(limit=0):
    """Reconstruct the in-process Khipu chain by replaying the durable dataset.

    Pulls the mirrored receipts from SZLHOLDINGS/a11oy-verifiable-corpus (prefix
    lake/) and re-appends each through the local ledger. The per-organ chain_hash
    is a deterministic function of (prev_hash, receipt_id, organ, ts, chain_index),
    so replaying the same receipts in order rebuilds the identical chain head;
    ledger.append is idempotent on receipt id/hash, so re-hydration is safe.

    Best-effort and honest: returns a status dict, never raises. Honest no-op
    when the dataset is unreachable (no token / repo / huggingface_hub).

    ROADMAP: this replays the FULL stream each boot. For a large ledger this
    should be bounded by reading the committed head.json chain-state + only the
    tail shards rather than read_all(); tracked as a follow-up. The mirror itself
    (write durability) is LIVE — this hydrate is the read-back half.
    """
    global _hydrated
    with _hydrate_lock:
        if _hydrated:
            return {"ok": True, "already": True}
        b = _get_bucket()
        if b is None:
            return {"ok": False, "reason": "dataset unreachable — chain starts empty this process"}
        replayed = duplicates = 0
        try:
            records = b.read_all()
            if limit:
                records = records[-int(limit):]
            led = get_default_ledger()
            for rec in records:
                payload = rec.get("payload") if isinstance(rec, dict) else None
                if not isinstance(payload, dict):
                    continue
                r = led.append(payload)
                if r.get("accepted"):
                    replayed += 1
                elif r.get("duplicate"):
                    duplicates += 1
            _hydrated = True
            return {"ok": True, "replayed": replayed, "duplicates": duplicates}
        except Exception as e:
            return {"ok": False, "reason": "hydrate error: %r" % (e,)}


def _parse_body(raw, content_type):
    """Parse a request body into a list of receipt dicts.

    Supports a single JSON object, a JSON array of objects, or NDJSON (one JSON
    object per line — signalled by content-type or detected heuristically)."""
    text = raw.decode("utf-8").strip()
    if not text:
        raise ValueError("empty request body")

    ct = (content_type or "").lower()
    is_ndjson = "ndjson" in ct

    if not is_ndjson:
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            is_ndjson = True  # fall through to line parsing
        else:
            if isinstance(parsed, dict):
                return [parsed]
            if isinstance(parsed, list):
                if not all(isinstance(x, dict) for x in parsed):
                    raise ValueError("JSON array must contain only objects")
                return parsed
            raise ValueError("body must be a JSON object, array, or NDJSON")

    receipts = []
    for n, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError("NDJSON line %d is not valid JSON: %s" % (n, e))
        if not isinstance(obj, dict):
            raise ValueError("NDJSON line %d is not a JSON object" % n)
        receipts.append(obj)
    if not receipts:
        raise ValueError("no receipts found in body")
    return receipts


def register(app, ns="a11oy"):  # pragma: no cover
    """Attach the Unified Receipt Ledger ingest surface to the live a11oy app.

    Routes are inserted at the HEAD of app.router.routes (the proven serve.py
    pattern) so /api/lake/v1/* wins over the Node proxy + SPA catch-all. Honest
    degrade: if Starlette is absent, returns the app unchanged (never raises)."""
    try:
        from starlette.routing import Route
        from starlette.responses import JSONResponse
    except Exception:
        return {"registered": [], "status": "starlette-absent"}

    async def _post_receipts(request):
        raw = await request.body()
        try:
            receipts = _parse_body(raw, request.headers.get("content-type", ""))
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        led = get_default_ledger()
        try:
            if len(receipts) == 1:
                result = led.append(receipts[0])
                result["mirror"] = _mirror_to_dataset(receipts[0])
                status = 200 if (result["accepted"] or result["duplicate"]) else 400
                return JSONResponse(result, status_code=status)
            batch = led.append_batch(receipts)
            for r in receipts:
                _mirror_to_dataset(r)
            return JSONResponse(batch, status_code=200)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def _get_receipts(request):
        qp = request.query_params
        organ = qp.get("organ")
        since = qp.get("since")
        try:
            limit = int(qp.get("limit", "100"))
        except (TypeError, ValueError):
            limit = 100
        limit = max(0, min(limit, 10000))
        try:
            results = get_default_ledger().query(organ=organ, since=since, limit=limit)
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)
        return JSONResponse({"organ": organ, "since": since, "limit": limit,
                             "count": len(results), "results": results})

    async def _chain_head(request):
        organ = request.query_params.get("organ")
        if not organ:
            return JSONResponse({"error": "missing required query param 'organ'"}, status_code=400)
        try:
            return JSONResponse(get_default_ledger().chain_head(organ))
        except ValueError as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def _health(request=None):
        return JSONResponse(get_default_ledger().health())

    # Register the canonical /api/lake/v1/* paths (the form documented in the env
    # contract) plus the post-strip /v1/lake/* alias, mirroring the multi-form
    # registration szl_governed_api uses so it wins regardless of front-door strip.
    routes = [
        (API_PREFIX + "/receipts",   _post_receipts, ["POST"]),
        (API_PREFIX + "/receipts",   _get_receipts,  ["GET"]),
        (API_PREFIX + "/chain/head", _chain_head,    ["GET"]),
        (API_PREFIX + "/health",     _health,        ["GET"]),
        ("/v1/lake/receipts",        _post_receipts, ["POST"]),
        ("/v1/lake/receipts",        _get_receipts,  ["GET"]),
        ("/v1/lake/chain/head",      _chain_head,    ["GET"]),
        ("/v1/lake/health",          _health,        ["GET"]),
    ]
    registered = []
    for path, fn, methods in routes:
        app.router.routes.insert(0, Route(path, fn, methods=methods))
        registered.append("%s %s" % ("/".join(methods), path))

    # Kick off boot-time hydrate in a daemon thread so a slow/unreachable dataset
    # never delays app startup. Honest no-op when the dataset is unavailable.
    try:
        threading.Thread(target=hydrate_from_dataset, name="szl-lake-hydrate",
                         daemon=True).start()
    except Exception as e:
        print("[a11oy] lake hydrate thread NOT started: %r" % (e,), file=sys.stderr)

    return {"registered": registered, "status": "ok", "sink": RECEIPT_SINK_URL}
