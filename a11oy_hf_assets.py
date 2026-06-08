#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""a11oy_hf_assets.py — canonical HF-asset instill layer (server-side, honest).

ADDITIVE, self-contained. Registers a small read-only surface that makes the
Knowledge / Brain / Evidence / RAG tabs reference REAL Hugging Face org assets
(SZLHOLDINGS/*) via their resolve URLs. Fetches are SERVER-SIDE with a short
timeout and an honest in-memory cache: a degraded fetch returns the last-known
payload tagged source="cached", and a never-fetched asset returns
source="pending" — never fabricated data.

The canonical asset map mirrors team/HF_ASSET_MANIFEST.json. Each entry names the
dataset, what it is, the a11oy tab + killinchu tab that expose it, and the real
resolve URL(s). This module is consumed by both a11oy and killinchu (same file).

ROUTES (all GET, additive; namespace /api/<ns>/v1/assets/*):
  /api/<ns>/v1/assets/manifest          -> the canonical asset map (no fetch)
  /api/<ns>/v1/assets/{key}             -> server-side fetch of the asset's
                                            primary resolve URL (honest degrade)

Doctrine v11: locked-proven = EXACTLY 5 {F1,F11,F12,F18,F19}; Λ = Conjecture 1;
SLSA L1 honest + L2 build-attestation present; no fabricated data; 0 runtime CDN
(this is a server-side fetch, not a browser CDN load).
Signed-off-by: Opus 4.8 (Dev3 — HF assets instill). Apache-2.0.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from typing import Any

_ORG = "SZLHOLDINGS"
_DS = f"https://huggingface.co/datasets/{_ORG}"

def _ds(repo: str, path: str) -> str:
    return f"{_DS}/{repo}/resolve/main/{path}"

# Canonical asset map: key -> {what, a11oy, killinchu, resolve(list), kind}
# Mirrors team/HF_ASSET_MANIFEST.json (the authoritative copy).
ASSETS: dict[str, dict[str, Any]] = {
    "rag-corpus": {
        "what": "Agentic-RAG corpus (762 chunks) + per-organ FAISS indexes (bge-base-en-v1.5).",
        "a11oy": "Knowledge / RAG (ask)", "killinchu": "Knowledge & Formulas (edge RAG)",
        "resolve": [_ds("rag-corpus-v1", "indexes/manifest.json"), _ds("rag-corpus-v1", "corpus.jsonl")],
        "kind": "json"},
    "lean-proofs": {
        "what": "Lean 4 theorem library (70 files) for the Ouroboros Invariant programme.",
        "a11oy": "Formulas / Lambda", "killinchu": "13-axis Λ / Edge Formulas",
        "resolve": [_ds("lean-proofs-v1", "Lutar/Bound.lean")], "kind": "text"},
    "canonical-formulas": {
        "what": "Canonical formula registry — 21 typed Python formulas + Lean obligations.",
        "a11oy": "Formulas (kbformulas)", "killinchu": "13-axis Λ",
        "resolve": [_ds("canonical-formulas-v1", "code/lean/Formulas.lean")], "kind": "text"},
    "thesis-formula-index": {
        "what": "Thesis → formula → Lean-theorem index map.",
        "a11oy": "Knowledge Ontology / Formulas", "killinchu": "Knowledge & Formulas",
        "resolve": [_ds("thesis-formula-index", "data/thesis_formula_index.json")], "kind": "json"},
    "lean-theorem-tree": {
        "what": "Lean theorem dependency tree (theorem → deps, axioms used).",
        "a11oy": "Lambda / Formulas lineage", "killinchu": "13-axis Λ lean-receipt trace",
        "resolve": [_ds("lean-theorem-tree", "data/lean_theorem_tree.json")], "kind": "json"},
    "lake-receipts": {
        "what": "szl-lake append-only DSSE receipt + attestation lake (cosign/SLSA innovations).",
        "a11oy": "Receipt Ledger / Signed Receipts", "killinchu": "DSSE Verifier / Receipts",
        "resolve": [_ds("szl-lake", "attestations/innovations/inn-01-khipuemitmonotone.json")], "kind": "json"},
    "evidence": {
        "what": "szl-evidence — 455 audit artifacts, DSSE receipts, CI attestations, closeout reports.",
        "a11oy": "Signed Receipts / Evidence", "killinchu": "Evidence / DSSE Verifier",
        "resolve": [_ds("szl-evidence", "README.md")], "kind": "text"},
    "governance-receipts": {
        "what": "UDS governance receipts (extended DSSE attestations).",
        "a11oy": "Signed Receipts / Readiness", "killinchu": "DSSE Verifier / Readiness",
        "resolve": [_ds("uds-governance-receipts", "extended-attestations.jsonl")], "kind": "jsonl"},
    "spans-receipts": {
        "what": "UDS OTel span + receipt samples + JSON schemas.",
        "a11oy": "MELT / Observability", "killinchu": "MELT",
        "resolve": [_ds("uds-spans-receipts", "schemas/span_schema.json"),
                    _ds("uds-spans-receipts", "data/spans_sample.jsonl")], "kind": "json"},
    "k-verify": {
        "what": "K-Verify benchmark — 100 verifiability/refusal items.",
        "a11oy": "What We Claim / Arena", "killinchu": "Threat DB / Model eval",
        "resolve": [_ds("k-verify-benchmark-v1", "k_verify_v1.manifest.json")], "kind": "json"},
    "yuyay-axis-labels": {
        "what": "Yuyay-v3 13-axis label dataset (non-compensatory gate).",
        "a11oy": "Lambda / Safety Gates", "killinchu": "13-axis Λ (Trust)",
        "resolve": [_ds("yuyay-v3-axis-labels-v1", "stats.json")], "kind": "json"},
    "doctrine": {
        "what": "Locked governance doctrine v10+v11 (13-axis yuyay_v3 canonical).",
        "a11oy": "Safety Gates / What We Claim", "killinchu": "ROE / Safety",
        "resolve": [_ds("doctrine-v10-v11", "README.md")], "kind": "text"},
    "thesis-corpus": {
        "what": "Thesis corpus v18 — extracted claims + per-version Lean delta ledger.",
        "a11oy": "Knowledge Ontology / What We Claim", "killinchu": "Anatomy / About",
        "resolve": [_ds("thesis-corpus-v18", "claims_v18_extracted.json")], "kind": "json"},
}

# in-memory cache: key -> {payload, ts, source}
_CACHE: dict[str, dict[str, Any]] = {}
_TIMEOUT = 8


def _fetch(url: str) -> tuple[str | None, str]:
    """Fetch a resolve URL server-side. Returns (text, status)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "a11oy-hf-assets/1.0"})
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
            data = r.read(262144)  # cap 256KB per fetch (manifests/cards only)
            return data.decode("utf-8", "replace"), "live"
    except Exception as e:  # honest degrade
        return None, f"error:{type(e).__name__}"


def asset_status(key: str) -> dict[str, Any]:
    """Return an asset descriptor + a server-side fetched preview (honest degrade)."""
    a = ASSETS.get(key)
    if not a:
        return {"error": "unknown asset key", "known": sorted(ASSETS)}
    url = a["resolve"][0]
    text, st = _fetch(url)
    if text is not None:
        # store a trimmed cache (first 4KB) so degrade returns last-known
        _CACHE[key] = {"preview": text[:4096], "ts": time.time(), "source": "live", "url": url}
        source = "live"; preview = text[:4096]
    elif key in _CACHE:
        source = "cached"; preview = _CACHE[key]["preview"]
    else:
        source = "pending"; preview = None
    return {
        "key": key, "what": a["what"], "a11oy_tab": a["a11oy"], "killinchu_tab": a["killinchu"],
        "resolve": a["resolve"], "kind": a["kind"], "source": source,
        "fetch_status": st, "preview": preview,
        "doctrine": {"version": "v11", "lambda": "Conjecture 1",
                     "locked_proven": ["F1", "F11", "F12", "F18", "F19"]},
    }


def manifest() -> dict[str, Any]:
    return {
        "org": _ORG, "count": len(ASSETS),
        "assets": {k: {"what": v["what"], "a11oy": v["a11oy"], "killinchu": v["killinchu"],
                       "resolve": v["resolve"], "kind": v["kind"]} for k, v in ASSETS.items()},
        "note": "Server-side fetched on demand; honest live|cached|pending. 0 browser CDN.",
        "doctrine": {"version": "v11", "lambda": "Conjecture 1",
                     "locked_proven": ["F1", "F11", "F12", "F18", "F19"]},
    }


def register(app, ns: str = "a11oy") -> str:
    try:
        from fastapi.responses import JSONResponse
        from starlette.responses import Response  # noqa
    except Exception as e:  # pragma: no cover
        return f"unavailable: {e!r}"

    n_before = len(app.router.routes)
    base = f"/api/{ns}/v1/assets"

    @app.get(base + "/manifest")
    async def _assets_manifest() -> "JSONResponse":  # noqa
        return JSONResponse(manifest())

    @app.get(base + "/{key}")
    async def _asset_one(key: str) -> "JSONResponse":  # noqa
        return JSONResponse(asset_status(key))

    new = app.router.routes[n_before:]
    del app.router.routes[n_before:]
    app.router.routes[0:0] = new
    print(f"[{ns}] HF assets instill registered: {base}/manifest + /{{key}} "
          f"({len(ASSETS)} assets) [moved {len(new)} routes to front]", file=sys.stderr)
    return f"ok: {len(ASSETS)} assets, {len(new)} routes"


if __name__ == "__main__":
    print(json.dumps(manifest(), indent=2))
