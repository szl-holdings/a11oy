#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""
szl_rekor_anchor -- live Sigstore Rekor public transparency-log anchor.

Layer: provenance.  Read-path only (NO signing on GET; see provenance rule).

Surfaces the REAL, independently Merkle-verifiable state of the public
Sigstore Rekor good-instance, plus an RFC 6962 inclusion verifier that
RECOMPUTES the Merkle root from a leaf + audit path (it does not trust the
server's `verified` field).

Endpoints (mounted before the SPA catch-all):
  GET /api/a11oy/v1/rekor/log              -> live tree state (treeSize, rootHash, STH)
  GET /api/a11oy/v1/rekor/verify/{index}   -> fetch entry + recompute Merkle root

HONESTY: a11oy's own receipts are signed/hash-chained in-image (szl_dsse +
szl_khipu) and are NOT yet submitted to this public log -- that anchoring is
ROADMAP. What is MEASURED here is the live public log root and a real RFC 6962
inclusion proof recomputed locally. If egress is blocked the log is reported
`reachable:false` and verify returns `verified:None` -- never a fabricated true.
The Merkle math mirrors Lean formula F15 (Rekor Merkle Inclusion, structural).
"""
import base64
import hashlib
import time
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse

REKOR_BASE = "https://rekor.sigstore.dev"
_UA = {"User-Agent": "a11oy-provenance/1.0 (+https://szlholdings-a11oy.hf.space) rekor-anchor",
       "Accept": "application/json"}
_TTL = 300.0
_TIMEOUT = 10.0
_CACHE: dict[str, dict] = {}

DOCTRINE = {
    "locked_proven": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "lambda": "Conjecture 1 (advisory)",
    "slsa": "L1 honest; L2 build-attested; L3 ROADMAP",
    "anchoring": "a11oy receipt -> public Rekor submission is ROADMAP; in-image DSSE+khipu chain is live",
    "merkle_formula": "F15 Rekor Merkle Inclusion (structural)",
}


def _sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def leaf_hash(entry_body_b64: str) -> bytes:
    """RFC 6962 leaf hash: SHA-256(0x00 || body)."""
    return _sha256(b"\x00" + base64.b64decode(entry_body_b64))


def _node_hash(left: bytes, right: bytes) -> bytes:
    """RFC 6962 interior node: SHA-256(0x01 || left || right)."""
    return _sha256(b"\x01" + left + right)


def verify_inclusion(leaf: bytes, index: int, tree_size: int, proof_hashes: list) -> bytes:
    """Recompute the Merkle root from a leaf + audit path (RFC 6962 2.1.1)."""
    if index >= tree_size or index < 0:
        raise ValueError("index %d out of range for tree_size %d" % (index, tree_size))
    node = leaf
    last_node = tree_size - 1
    i = index
    proof = list(proof_hashes)
    while last_node > 0:
        if not proof:
            raise ValueError("audit path exhausted before reaching root")
        if i % 2 == 1:
            node = _node_hash(proof.pop(0), node)
        elif i < last_node:
            node = _node_hash(node, proof.pop(0))
        i //= 2
        last_node //= 2
    if proof:
        raise ValueError("audit path has leftover hashes")
    return node


def fetch_log_state(timeout: float = _TIMEOUT) -> dict:
    """Live Rekor tree head: treeSize + rootHash + signedTreeHead. Cached + honest fallback."""
    now = time.time()
    rec = _CACHE.get("log")
    if rec and (now - rec["fetched_at"]) < _TTL and rec.get("reachable"):
        return {**rec["value"], "reachable": True, "freshness": "cached",
                "age_s": round(now - rec["fetched_at"], 1)}
    try:
        import httpx
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=_UA) as client:
            r = client.get(REKOR_BASE + "/api/v1/log")
            r.raise_for_status()
            d = r.json()
        value = {
            "tree_size": d.get("treeSize"),
            "root_hash": d.get("rootHash"),
            "tree_id": d.get("treeID"),
            "signed_tree_head_present": bool(d.get("signedTreeHead")),
            "source": REKOR_BASE + "/api/v1/log",
            "label": "MEASURED",
        }
        _CACHE["log"] = {"value": value, "fetched_at": now, "reachable": True}
        return {**value, "reachable": True, "freshness": "live", "age_s": 0}
    except Exception as e:
        if rec:
            return {**rec["value"], "reachable": False, "freshness": "stale",
                    "age_s": round(now - rec["fetched_at"], 1), "error": str(e)[:160]}
        return {"reachable": False, "label": "UNREACHABLE", "source": REKOR_BASE + "/api/v1/log",
                "error": str(e)[:160],
                "note": "public Rekor log unreachable from this host (egress) -- honest fallback"}


def verify_log_index(log_index: int, timeout: float = _TIMEOUT) -> dict:
    """Fetch entry `log_index`, recompute its Merkle root, compare to server root."""
    out: dict[str, Any] = {"log_index": log_index, "rekor": REKOR_BASE,
                           "method": "RFC 6962 inclusion -- root recomputed from leaf+path"}
    try:
        import httpx
        url = REKOR_BASE + "/api/v1/log/entries?logIndex=%d" % int(log_index)
        with httpx.Client(follow_redirects=True, timeout=timeout, headers=_UA) as client:
            r = client.get(url)
            r.raise_for_status()
            data = r.json()
        if not isinstance(data, dict) or not data:
            return {**out, "verified": None, "reason": "empty Rekor response"}
        uuid, entry = next(iter(data.items()))
        out["uuid"] = uuid
        out["fetch_url"] = url
    except Exception as e:
        return {**out, "verified": None, "reason": "fetch failed (%s: %s)" % (type(e).__name__, e)}
    try:
        ip = entry["verification"]["inclusionProof"]
        tree_size = int(ip["treeSize"])
        proof_index = int(ip["logIndex"])
        root_hex = ip["rootHash"]
        hashes_hex = ip["hashes"]
        leaf = leaf_hash(entry["body"])
        computed = verify_inclusion(leaf, proof_index, tree_size, [bytes.fromhex(h) for h in hashes_hex])
        computed_hex = computed.hex()
        return {
            **out,
            "verified": (computed_hex == root_hex),
            "tree_size": tree_size,
            "proof_index": proof_index,
            "audit_path_len": len(hashes_hex),
            "leaf_hash_sha256": leaf.hex(),
            "computed_root": computed_hex,
            "server_root": root_hex,
            "checkpoint_present": bool(ip.get("checkpoint")),
            "label": "MEASURED",
        }
    except Exception as e:
        return {**out, "verified": False, "reason": "merkle error: %s: %s" % (type(e).__name__, e)}


def register(app: FastAPI, ns: str = "a11oy") -> dict:
    base = "/api/" + ns + "/v1/rekor"
    _n_before = len(app.router.routes)

    @app.get(base + "/log", include_in_schema=False)
    async def _rekor_log():
        return JSONResponse({"surface": "rekor-log", "log": fetch_log_state(), "doctrine": DOCTRINE})

    @app.get(base + "/verify/{log_index}", include_in_schema=False)
    async def _rekor_verify(log_index: int):
        return JSONResponse({"surface": "rekor-verify", "result": verify_log_index(log_index),
                             "doctrine": DOCTRINE})

    @app.get(base + "/healthz", include_in_schema=False)
    async def _rekor_hz():
        return JSONResponse({"ok": True, "module": "szl_rekor_anchor", "base": base,
                             "doctrine": DOCTRINE})

    moved = -1
    try:
        _new = app.router.routes[_n_before:]
        del app.router.routes[_n_before:]
        app.router.routes[0:0] = _new
        moved = len(_new)
    except Exception as _e:
        import sys as _s
        print("[a11oy] rekor-anchor route reorder failed (non-fatal): %r" % _e, file=_s.stderr)

    return {"mounted": base, "moved": moved}


__all__ = ["REKOR_BASE", "leaf_hash", "verify_inclusion", "fetch_log_state",
           "verify_log_index", "register"]
