# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v13
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""
szl_intoto_routes.py — FastAPI/Starlette endpoints for in-toto receipt views
and transparency log inclusion proofs.

ADDITIVE — mounts new routes, does NOT modify existing /khipu/* endpoints.

ENDPOINTS:
  GET  /khipu/intoto/<receipt_id>
       Returns the in-toto Statement v1 + DSSE envelope for a stored receipt.
       Looks up the receipt from the in-memory KhipuDAG organs first, then the
       szl_lake_store ReceiptLedger (disk). Honors back-compat: the original
       receipt JSON is also returned under "receipt" key.

  GET  /api/lake/v1/proof/<receipt_id>
       Returns the Merkle inclusion proof for a receipt from the self-hosted
       transparency log (szl_intoto.SZLMerkleLog). Third-party verifiable.

  GET  /api/lake/v1/log
       Current state of the self-hosted Merkle log (tree size, root hash).

  GET  /api/a11oy/v1/verify/intoto
       Documentation endpoint: explains what is now third-party-verifiable vs
       what is roadmap. Returns verification instructions and example curl commands.

HONEST LABELS (never weaken):
  - transparency_log: "rekor-public" only if actually submitted to Rekor.
  - transparency_log: "szl-lake-merkle (self-hosted)" for self-hosted log.
  - Every response declares its honesty constraints.

Stdlib + szl_intoto + szl_dsse + szl_khipu + szl_lake_store. No new pip deps.
"""
from __future__ import annotations

import json
import os
from typing import Any

# ---------------------------------------------------------------------------
# REGISTER
# ---------------------------------------------------------------------------

def register(app, ns: str = "a11oy") -> dict:  # pragma: no cover
    """Attach in-toto receipt + transparency log endpoints to the a11oy FastAPI app.

    Inserts routes at HEAD of router (before SPA catch-all), following the
    established register() contract in the a11oy codebase.
    """
    try:
        from starlette.routing import Route
        from starlette.responses import JSONResponse
    except Exception:
        return {"registered": [], "status": "starlette-absent"}

    # ------------------------------------------------------------------
    # Lazy imports (guarded — missing modules degrade gracefully)
    # ------------------------------------------------------------------
    try:
        import szl_intoto as _intoto
    except ImportError:
        _intoto = None

    try:
        import szl_khipu as _khipu
    except ImportError:
        _khipu = None

    try:
        import szl_lake_store as _lake
        _ledger = _lake.ReceiptLedger()
    except ImportError:
        _lake = None
        _ledger = None

    # ------------------------------------------------------------------
    # Helper: look up a receipt by ID across all organs + lake
    # ------------------------------------------------------------------
    def _find_receipt(receipt_id: str) -> dict | None:
        """Search KhipuDAG organs then disk ledger for receipt_id."""
        # 1) Check in-memory KhipuDAG
        if _khipu is not None:
            try:
                for (organ, ns_key), dag in _khipu._REGISTRY.items():
                    for r in dag._chain:
                        rid = (r.get("receipt_id") or r.get("id")
                               or r.get("hash") or r.get("digest") or "")
                        if rid == receipt_id:
                            return r
            except Exception:
                pass

        # 2) Check disk ledger
        if _ledger is not None:
            try:
                envelopes = _ledger.query(limit=10000)
                for env in envelopes:
                    rid = env.get("receipt_id", "")
                    if rid == receipt_id:
                        return env.get("receipt", env)
            except Exception:
                pass

        return None

    # ------------------------------------------------------------------
    # GET /khipu/intoto/<receipt_id>
    # ------------------------------------------------------------------
    async def _khipu_intoto(request):
        if _intoto is None:
            return JSONResponse(
                {"error": "szl_intoto module not available", "receipt_id": None},
                status_code=503,
            )
        receipt_id = request.path_params.get("receipt_id", "")
        if not receipt_id:
            return JSONResponse({"error": "receipt_id required"}, status_code=400)

        receipt = _find_receipt(receipt_id)
        if receipt is None:
            return JSONResponse(
                {"error": "receipt not found", "receipt_id": receipt_id,
                 "honesty": "Receipt not found in any in-memory organ or disk ledger. "
                             "It may belong to a prior process run."},
                status_code=404,
            )

        # Build in-toto attestation (use Merkle log only; Rekor submit is async roadmap)
        try:
            attestation = _intoto.attest_receipt(receipt, try_rekor=False)
        except Exception as exc:
            return JSONResponse(
                {"error": f"attestation failed: {exc!r}", "receipt_id": receipt_id},
                status_code=500,
            )

        return JSONResponse({
            "receipt_id": receipt_id,
            "intoto_statement": attestation["intoto_statement"],
            "intoto_envelope": attestation["intoto_envelope"],
            "transparency": attestation["transparency"],
            "receipt": receipt,  # back-compat: original receipt preserved
            "_version": attestation["_version"],
            "honesty": (
                "in-toto Statement v1 with payloadType=application/vnd.in-toto+json. "
                "Subject digest binds to model output (C2PA hard-binding). "
                "predicateType=https://szl.holdings/khipu-governed-inference/v1. "
                "transparency_log field declares the log used honestly."
            ),
        })

    # ------------------------------------------------------------------
    # GET /api/lake/v1/proof/<receipt_id>
    # ------------------------------------------------------------------
    async def _lake_proof(request):
        if _intoto is None:
            return JSONResponse(
                {"error": "szl_intoto module not available"}, status_code=503
            )
        receipt_id = request.path_params.get("receipt_id", "")
        if not receipt_id:
            return JSONResponse({"error": "receipt_id required"}, status_code=400)

        proof = _intoto.get_inclusion_proof(receipt_id)
        return JSONResponse(proof)

    # ------------------------------------------------------------------
    # GET /api/lake/v1/log
    # ------------------------------------------------------------------
    async def _lake_log(request):
        if _intoto is None:
            return JSONResponse(
                {"error": "szl_intoto module not available"}, status_code=503
            )
        return JSONResponse(_intoto.merkle_log_state())

    # ------------------------------------------------------------------
    # GET /api/a11oy/v1/verify/intoto
    # ------------------------------------------------------------------
    async def _verify_intoto_docs(request):
        pub_key_url = "https://github.com/szl-holdings/.github/blob/main/cosign.pub"
        return JSONResponse({
            "title": "SZL a11oy in-toto Verification Guide",
            "what_is_now_verifiable": {
                "1_dsse_signature": {
                    "status": "LIVE",
                    "description": (
                        "Every receipt is DSSE-signed with the SZL ECDSA P-256 keypair. "
                        "payloadType is now 'application/vnd.in-toto+json'. "
                        "Verifiable with standard cosign verify-blob."
                    ),
                    "command": (
                        "cosign verify-blob "
                        "--key https://a-11-oy.com/cosign.pub "
                        "--bundle <receipt.bundle.json> "
                        "<statement.json>"
                    ),
                },
                "2_intoto_statement": {
                    "status": "LIVE",
                    "description": (
                        "Receipt payload is now a valid in-toto Statement v1: "
                        "{_type: https://in-toto.io/Statement/v1, "
                        "subject:[{name, digest:{sha3-256:<output_hash>}}], "
                        "predicateType: https://szl.holdings/khipu-governed-inference/v1, "
                        "predicate:{...all governance/Λ/energy/gate fields...}}. "
                        "Standard tools (cosign verify-attestation, Ratify) can parse the envelope."
                    ),
                    "fetch_endpoint": "/khipu/intoto/<receipt_id>",
                },
                "3_hard_binding": {
                    "status": "LIVE",
                    "description": (
                        "Subject digest is SHA3-256 of the model output content. "
                        "C2PA hard-binding pattern: receipt cannot be recycled for a different output. "
                        "Verifiable offline: compute SHA3-256(answer_text) and compare to statement.subject[0].digest."
                    ),
                },
                "4_merkle_inclusion_proof": {
                    "status": "LIVE (self-hosted)",
                    "description": (
                        "Every receipt is appended to the SZL self-hosted Merkle transparency log "
                        "(RFC 6962 SHA3-256 leaf/node hashing). "
                        "Inclusion proofs retrievable at /api/lake/v1/proof/<receipt_id>. "
                        "Third-party verifiable: compute leaf_hash(statement), walk audit_path, "
                        "check against root_hash. NO trust in SZL required for the math."
                    ),
                    "proof_endpoint": "/api/lake/v1/proof/<receipt_id>",
                    "log_endpoint": "/api/lake/v1/log",
                    "honest_label": "szl-lake-merkle (self-hosted) — NOT Sigstore public Rekor",
                },
                "5_sha3_chain": {
                    "status": "LIVE",
                    "description": (
                        "SHA3-256 prev_hash chain from genesis. "
                        "Tamper-evident linked list verifiable by replaying the NDJSON stream. "
                        "Chain verification endpoint: /khipu/verify/<digest>"
                    ),
                },
            },
            "what_is_roadmap": {
                "per_receipt_public_rekor": {
                    "status": "ROADMAP",
                    "description": (
                        "Public Rekor submission per inference receipt "
                        "(transparency_log: rekor-public). "
                        "Blocked by: HF Space egress restrictions may prevent live Rekor POSTs "
                        "during inference. Planned path: CI batch job submits each receipt "
                        "to rekor.sigstore.dev on Lake publish, stores logIndex back in NDJSON. "
                        "The self-hosted Merkle log bridges this gap with the SAME math."
                    ),
                    "unblock_path": (
                        "Add SZL_REKOR_SUBMIT=1 env var to HF Space; "
                        "szl_intoto.submit_to_rekor() is wired and will attempt live submission. "
                        "If HF egress allows it, transparency_log automatically upgrades to rekor-public."
                    ),
                },
                "slsa_l2_container": {
                    "status": "ROADMAP",
                    "description": (
                        "SLSA Build L2 provenance for the container via GitHub Actions OIDC "
                        "(actions/attest-build-provenance@v2). ~3 lines of YAML. "
                        "Currently SLSA L1 (Rekor entry 1710339915 for container build)."
                    ),
                },
                "tee_attestation": {
                    "status": "ROADMAP (Phase II)",
                    "description": (
                        "TEE remote attestation (AWS Nitro PCR measurements / Intel TDX) — "
                        "proves WHICH model ran in WHICH environment without trusting SZL. "
                        "Required for court-martial-grade DoD audit trail."
                    ),
                },
            },
            "verify_offline_recipe": (
                "szl-cookbook/verify-intoto-receipt.py — "
                "Apache-2.0 offline verifier: verifies DSSE sig with cosign.pub, "
                "checks in-toto Statement structure, checks Merkle inclusion proof. "
                "NO network call required after downloading the receipt + proof."
            ),
            "public_key_url": pub_key_url,
            "cosign_pub_endpoint": "/cosign.pub",
        })

    # ------------------------------------------------------------------
    # Route registration
    # ------------------------------------------------------------------
    paths = [
        ("/khipu/intoto/{receipt_id}", _khipu_intoto, ["GET"]),
        ("/api/a11oy/v1/khipu/intoto/{receipt_id}", _khipu_intoto, ["GET"]),
        ("/api/lake/v1/proof/{receipt_id}", _lake_proof, ["GET"]),
        ("/api/lake/v1/log", _lake_log, ["GET"]),
        ("/api/a11oy/v1/verify/intoto", _verify_intoto_docs, ["GET"]),
        ("/v1/verify/intoto", _verify_intoto_docs, ["GET"]),
    ]

    registered = []
    for path, fn, methods in paths:
        try:
            from starlette.routing import Route as _Route
            app.router.routes.insert(0, _Route(path, fn, methods=methods))
            registered.append(path)
        except Exception:
            pass

    return {"registered": registered, "status": "ok"}
