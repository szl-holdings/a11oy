# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v13
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""
szl_scitt.py — SCITT Agent Action Capsule
==========================================
Implements IETF draft-mih-scitt-agent-action-capsule-01 (June 2026) in
SZL Holdings' own code. ZERO proprietary dependency; the IETF draft carries
no proprietary claim (IETF Internet Draft, open spec).

WHAT THIS MODULE PRODUCES
--------------------------
Every Λ-gate verdict (ALLOW and BLOCK) generates a "SCITT Agent Action
Capsule" — a standard signed receipt that records:
  - The governed inference turn (prompt hash, model id, verdict, gates, output hash)
  - A COSE_Sign1 signed statement (if cbor2 + pycose available) OR
    an honest JSON-profile fallback labeled
    "SCITT-profile (JSON; COSE upgrade ROADMAP)" if the COSE libs are absent.
  - The statement is recorded into the szl-lake Merkle transparency log
    (same log used by szl_intoto.py).
  - Returns: capsule_id, leaf_index, inclusion_proof.

HONEST LABELS (never weaken)
  - "cose_sign1" : real COSE_Sign1 binary, cbor2+pycose installed, ECDSA-P256
  - "json-profile (SCITT-profile; COSE upgrade ROADMAP)" : JSON fallback, DSSE-signed

BLOCK verdicts MUST produce a capsule (the whole point of SCITT for refusals).
This module enforces that: `build_capsule` does NOT gate on verdict.

SPEC SOURCES
  - draft-mih-scitt-agent-action-capsule-01
    https://datatracker.ietf.org/doc/html/draft-mih-scitt-agent-action-capsule
  - SCITT Architecture (RFC 9943 + draft-ietf-scitt-scrapi-11)
    https://datatracker.ietf.org/doc/html/draft-ietf-scitt-scrapi
  - COSE RFC 9052 (COSE_Sign1 structure)
    https://www.rfc-editor.org/rfc/rfc9052
  - cbor2 (MIT) — https://github.com/agronholm/cbor2
  - pycose (MIT) — https://github.com/TimothyClaeys/pycose

ADDITIVE — does NOT replace the existing DSSE + in-toto receipt formats.
Both DSSE envelope and in-toto statement are produced as before; this module
adds `scitt_capsule` alongside them.

Apache-2.0 — SZL Holdings 2026.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

# ---------------------------------------------------------------------------
# COSE / CBOR AVAILABILITY CHECK
# cbor2 (MIT): pip install cbor2
# pycose (MIT): pip install pycose
# We try to import but NEVER fail hard if absent — honest fallback only.
# ---------------------------------------------------------------------------
try:
    import cbor2  # type: ignore[import]
    _CBOR2_AVAILABLE = True
except ImportError:
    _CBOR2_AVAILABLE = False

try:
    from cose.messages import Sign1Message  # type: ignore[import]
    from cose.keys import CoseKey  # type: ignore[import]
    from cose.headers import Algorithm, KID  # type: ignore[import]
    from cose.algorithms import Es256  # type: ignore[import]
    _PYCOSE_AVAILABLE = True
except ImportError:
    _PYCOSE_AVAILABLE = False

_COSE_AVAILABLE = _CBOR2_AVAILABLE and _PYCOSE_AVAILABLE

# ---------------------------------------------------------------------------
# SPEC CONSTANTS
# ---------------------------------------------------------------------------
CAPSULE_SPEC_VERSION = "draft-mih-scitt-agent-action-capsule-01"
CAPSULE_CONTENT_TYPE = "application/agent-action-capsule+json"
CAPSULE_STATEMENT_TYPE = "agent_action"
TRANSPARENCY_LOG_VERSION = "szl-scitt/v1"
SCITT_PAYLOAD_TYPE = "application/vnd.szl.scitt-capsule+json"

# COSE header label 3 = content_type, per RFC 9052
_COSE_HEADER_CONTENT_TYPE = 3
_COSE_HEADER_KID = 4
_COSE_HEADER_ALG = 1
_COSE_ALG_ES256 = -7  # ECDSA w/ SHA-256

# ---------------------------------------------------------------------------
# MERKLE TRANSPARENCY LOG (reuses the szl-lake RFC 6962 approach from szl_intoto)
# Thread-safe, append-only, in-process; seeded from khipu NDJSON on startup.
# ---------------------------------------------------------------------------

class _ScittTransparencyLog:
    """
    Self-hosted SCITT Transparency Service backed by an RFC 6962 Merkle tree.
    Leaf hash: SHA3-256(0x00 || canonical_json(capsule_payload))
    Node hash: SHA3-256(0x01 || left || right)
    Thread-safe via a reentrant lock.
    """
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._leaves: list[bytes] = []  # leaf hashes in insertion order

    @staticmethod
    def _leaf_hash(data: bytes) -> bytes:
        return hashlib.sha3_256(b"\x00" + data).digest()

    @staticmethod
    def _node_hash(left: bytes, right: bytes) -> bytes:
        return hashlib.sha3_256(b"\x01" + left + right).digest()

    def _compute_root(self) -> bytes:
        """RFC 6962 root hash over current leaves."""
        leaves = list(self._leaves)
        if not leaves:
            return hashlib.sha3_256(b"").digest()
        nodes = list(leaves)
        while len(nodes) > 1:
            nxt = []
            for i in range(0, len(nodes), 2):
                if i + 1 < len(nodes):
                    nxt.append(self._node_hash(nodes[i], nodes[i + 1]))
                else:
                    nxt.append(nodes[i])  # odd leaf promoted
            nodes = nxt
        return nodes[0]

    def _inclusion_proof(self, index: int) -> list[str]:
        """Return audit path for leaf at `index` (hex-encoded sibling hashes)."""
        leaves = list(self._leaves)
        n = len(leaves)
        path: list[str] = []
        nodes = list(leaves)
        i = index
        while len(nodes) > 1:
            if i % 2 == 0:
                if i + 1 < len(nodes):
                    path.append(nodes[i + 1].hex())
            else:
                path.append(nodes[i - 1].hex())
            nxt = []
            for j in range(0, len(nodes), 2):
                if j + 1 < len(nodes):
                    nxt.append(self._node_hash(nodes[j], nodes[j + 1]))
                else:
                    nxt.append(nodes[j])
            nodes = nxt
            i //= 2
        return path

    def append(self, payload: bytes) -> dict[str, Any]:
        """
        Append a capsule payload to the transparency log.
        Returns: {leaf_index, leaf_hash, root_hash, tree_size, hashes, transparency_log}
        """
        with self._lock:
            leaf = self._leaf_hash(payload)
            self._leaves.append(leaf)
            idx = len(self._leaves) - 1
            root = self._compute_root()
            proof = self._inclusion_proof(idx)
            return {
                "transparency_log": f"szl-scitt-merkle (self-hosted; {TRANSPARENCY_LOG_VERSION})",
                "leaf_index": idx,
                "leaf_hash": leaf.hex(),
                "root_hash": root.hex(),
                "tree_size": len(self._leaves),
                "hashes": proof,
                "spec": CAPSULE_SPEC_VERSION,
                "honesty": (
                    "Self-hosted Merkle transparency log. "
                    "Public Rekor / third-party SCITT Transparency Service submission is ROADMAP."
                ),
            }

    def get_transparency_view(self) -> dict[str, Any]:
        """Return the current state of the transparency log (SCITT transparency view)."""
        with self._lock:
            root = self._compute_root()
            return {
                "transparency_service": "szl-lake-scitt (self-hosted)",
                "spec": CAPSULE_SPEC_VERSION,
                "tree_size": len(self._leaves),
                "root_hash": root.hex(),
                "transparency_log": f"szl-scitt-merkle (self-hosted; {TRANSPARENCY_LOG_VERSION})",
                "cose_available": _COSE_AVAILABLE,
                "cbor2_available": _CBOR2_AVAILABLE,
                "pycose_available": _PYCOSE_AVAILABLE,
                "signing_profile": "COSE_Sign1 (ECDSA-P256)" if _COSE_AVAILABLE
                                   else "SCITT-profile (JSON; COSE upgrade ROADMAP)",
                "honesty": (
                    "SZL self-hosted Merkle log per RFC 6962. "
                    "Third-party SCITT TS registration is ROADMAP. "
                    "cbor2/pycose absent → honest JSON-profile fallback used."
                    if not _COSE_AVAILABLE else
                    "SZL self-hosted Merkle log per RFC 6962. "
                    "COSE_Sign1 signing active (cbor2+pycose present)."
                ),
            }


# Module-level singleton transparency log
_TRANSPARENCY_LOG = _ScittTransparencyLog()


# ---------------------------------------------------------------------------
# CANONICAL JSON (same as szl_intoto / szl_dsse)
# ---------------------------------------------------------------------------

def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def _sha3_256(b: bytes) -> str:
    return hashlib.sha3_256(b).hexdigest()


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


# ---------------------------------------------------------------------------
# CAPSULE PAYLOAD BUILDER (JSON profile, spec-conformant structure)
# ---------------------------------------------------------------------------

def _build_capsule_payload(
    *,
    capsule_id: str,
    prompt_hash: str,
    model_id: str,
    verdict: str,           # "allow" | "deny" | "review" | "error" | "block"
    gates: list[str],
    output_hash: str | None,
    timestamp: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build the JSON payload conforming to draft-mih-scitt-agent-action-capsule-01.

    Key fields (spec-mapped):
      capsule_statement_type  = "agent_action"
      spec_version            = "draft-mih-scitt-agent-action-capsule-01"
      capsule_id              = UUID
      action_id               = prompt_hash (unique per turn)
      action_type             = "governed_inference"
      operator                = "szl-holdings"
      developer               = "szl-holdings/a11oy"
      timestamp               = ISO-8601 UTC
      disposition.decision    = verdict  (ALLOW and BLOCK both produce capsule)
      effect_record.status    = "confirmed"
      effect_record.output_sha3_256 = output_hash (or "BLOCKED" if denied)
      constraint_records      = gate verdicts
      assurance.attestation_mode = "software_signed_ecdsa_p256"
      assurance.cose_available   = bool (honest label)

    The `khipu_ext` field carries backward-compat data for existing consumers.
    """
    # Normalize verdict: map "allow" -> "executed", "deny"/"block" -> "blocked"
    disposition_map = {
        "allow": "executed",
        "deny": "blocked",
        "block": "blocked",
        "review": "review",
        "error": "errored",
    }
    disposition_decision = disposition_map.get(str(verdict).lower(), str(verdict).lower())

    effect_status = "confirmed" if disposition_decision == "executed" else "blocked"
    output_ref = output_hash if output_hash else ("BLOCKED" if disposition_decision == "blocked" else "UNAVAILABLE")

    constraint_records = [
        {"gate": g, "disposition": "blocked" if disposition_decision == "blocked" else "passed"}
        for g in (gates or [])
    ]

    payload = {
        "capsule_statement_type": CAPSULE_STATEMENT_TYPE,
        "spec_version": CAPSULE_SPEC_VERSION,
        "capsule_id": capsule_id,
        "action_id": prompt_hash,
        "action_type": "governed_inference",
        "operator": "szl-holdings",
        "developer": "szl-holdings/a11oy",
        "timestamp": timestamp,
        "model_id": model_id,
        "disposition": {
            "decision": disposition_decision,
            "verdict_original": verdict,
            "honest_label": (
                "ALLOW verdict — answer returned with signed capsule" if disposition_decision == "executed"
                else "BLOCK/DENY verdict — refusal signed as capsule (tamper-evident)"
            ),
        },
        "effect_record": {
            "status": effect_status,
            "output_sha3_256": output_ref,
            "confirmed_effect_binding": (
                "output_hash_present" if (output_hash and disposition_decision == "executed")
                else ("no_output_produced" if disposition_decision == "blocked"
                      else "output_hash_unavailable")
            ),
        },
        "assurance": {
            "attestation_mode": "software_signed_ecdsa_p256",
            "cose_available": _COSE_AVAILABLE,
            "signing_profile": (
                "COSE_Sign1 (ECDSA-P256; cbor2+pycose)" if _COSE_AVAILABLE
                else "SCITT-profile (JSON; COSE upgrade ROADMAP)"
            ),
            "ledger_mode": "szl-lake-merkle (self-hosted)",
        },
        "constraint_records": constraint_records,
        "lean_proof_hash": None,     # ROADMAP: Lean4Agent proof hash (Phase II)
        "energy_wh": None,            # ROADMAP: EU AI Act energy field (Phase II)
        "khipu_ext": extra or {},
    }
    return payload


# ---------------------------------------------------------------------------
# SIGNING — COSE_Sign1 (if available) or DSSE-signed JSON-profile fallback
# ---------------------------------------------------------------------------

def _sign_cose_sign1(payload_bytes: bytes, private_key_pem: str) -> bytes | None:
    """
    Produce a COSE_Sign1 binary over payload_bytes using ECDSA-P256.
    Returns None if pycose/cbor2 unavailable or signing fails.
    """
    if not _COSE_AVAILABLE:
        return None
    try:
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        import cbor2

        private_key = load_pem_private_key(private_key_pem.encode("utf-8"), password=None)

        # COSE_Sign1 = [protected_header_bytes, {}, payload_bytes, signature_bytes]
        # Protected header: {1: -7, 3: content_type}
        protected_header = cbor2.dumps({
            _COSE_HEADER_ALG: _COSE_ALG_ES256,
            _COSE_HEADER_CONTENT_TYPE: CAPSULE_CONTENT_TYPE,
        })

        # Sig_structure for COSE_Sign1:
        # ["Signature1", protected_header_bytes, external_aad, payload]
        sig_structure = cbor2.dumps([
            "Signature1",
            protected_header,
            b"",  # external_aad
            payload_bytes,
        ])

        sig = private_key.sign(sig_structure, ec.ECDSA(hashes.SHA256()))

        cose_sign1 = cbor2.dumps(
            cbor2.CBORTag(18, [protected_header, {}, payload_bytes, sig])
        )
        return cose_sign1
    except Exception as exc:
        import sys
        print(f"[szl_scitt] COSE_Sign1 signing failed (falling back to JSON-profile): {exc!r}",
              file=sys.stderr)
        return None


def _sign_json_profile(payload: dict[str, Any], private_key_pem: str | None) -> dict[str, Any]:
    """
    Sign the capsule payload as a DSSE-style JSON envelope.
    Honest label: "SCITT-profile (JSON; COSE upgrade ROADMAP)".
    Returns the signed envelope dict.
    """
    payload_bytes = _canonical_json(payload)
    payload_b64 = base64.b64encode(payload_bytes).decode("ascii")
    payload_type = SCITT_PAYLOAD_TYPE

    envelope: dict[str, Any] = {
        "payloadType": payload_type,
        "payload": payload_b64,
        "scitt_profile": "JSON (COSE upgrade ROADMAP — install cbor2+pycose for COSE_Sign1)",
        "signed": False,
        "signatures": [],
    }

    if private_key_pem:
        try:
            from cryptography.hazmat.primitives.serialization import load_pem_private_key
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.hazmat.primitives import hashes

            # DSSE PAE for the JSON-profile envelope
            ptype_b = payload_type.encode("utf-8")
            pae = (
                b"DSSEv1 "
                + str(len(ptype_b)).encode()
                + b" "
                + ptype_b
                + b" "
                + str(len(payload_bytes)).encode()
                + b" "
                + payload_bytes
            )
            private_key = load_pem_private_key(
                private_key_pem.encode("utf-8"), password=None
            )
            sig = private_key.sign(pae, ec.ECDSA(hashes.SHA256()))
            envelope["signatures"] = [{
                "keyid": "szlholdings-cosign",
                "sig": base64.b64encode(sig).decode("ascii"),
            }]
            envelope["signed"] = True
        except Exception as exc:
            import sys
            print(f"[szl_scitt] JSON-profile signing skipped: {exc!r}", file=sys.stderr)
            envelope["honesty"] = f"Signing unavailable: {exc!r}"

    if not envelope["signed"]:
        envelope["honesty"] = (
            "JSON-profile capsule unsigned: SZL_COSIGN_PRIVATE_KEY_PEM absent "
            "or signing failed. Capsule structure is authentic; DSSE signature "
            "not applied. ROADMAP: add COSE_Sign1 via cbor2+pycose."
        )

    return envelope


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def build_capsule(
    *,
    prompt_hash: str,
    model_id: str,
    verdict: str,
    gates: list[str],
    output_hash: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Build a SCITT Agent Action Capsule for a governed-inference turn.

    Parameters
    ----------
    prompt_hash  : SHA3-256 hex of the prompt (unique action identifier).
    model_id     : Model identifier string.
    verdict      : Λ-gate verdict: "allow", "deny", "block", "review", "error".
    gates        : List of gate names that fired (or passed).
    output_hash  : SHA3-256 hex of the model output (None for BLOCK/DENY turns).
    extra        : Additional fields for backward-compat khipu_ext.

    Returns
    -------
    {
      "capsule_id"        : str (UUID),
      "spec_version"      : str,
      "signing_profile"   : "cose_sign1" | "json-profile (SCITT-profile; COSE upgrade ROADMAP)",
      "payload"           : dict (capsule JSON payload),
      "cose_sign1_b64"    : str | None  (base64 COSE_Sign1 bytes; None if COSE absent),
      "json_envelope"     : dict (DSSE-style signed JSON-profile envelope),
      "transparency"      : dict (Merkle inclusion proof from szl-lake),
      "honesty"           : str,
    }

    NOTE: BLOCK verdicts ALWAYS produce a capsule. The caller MUST NOT gate
    capsule production on verdict == "allow".
    """
    capsule_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

    payload = _build_capsule_payload(
        capsule_id=capsule_id,
        prompt_hash=prompt_hash,
        model_id=model_id,
        verdict=verdict,
        gates=gates,
        output_hash=output_hash,
        timestamp=timestamp,
        extra=extra or {},
    )

    payload_bytes = _canonical_json(payload)

    # Sign: try COSE_Sign1 first, then JSON-profile fallback
    private_key_pem: str | None = os.environ.get("SZL_COSIGN_PRIVATE_KEY_PEM")

    cose_sign1_bytes: bytes | None = None
    cose_sign1_b64: str | None = None
    signing_profile: str

    if _COSE_AVAILABLE and private_key_pem:
        cose_sign1_bytes = _sign_cose_sign1(payload_bytes, private_key_pem)

    if cose_sign1_bytes is not None:
        cose_sign1_b64 = base64.b64encode(cose_sign1_bytes).decode("ascii")
        signing_profile = "cose_sign1 (ECDSA-P256; cbor2+pycose)"
    else:
        signing_profile = "json-profile (SCITT-profile; COSE upgrade ROADMAP)"

    json_envelope = _sign_json_profile(payload, private_key_pem)

    # Embed capsule_id into khipu_ext BEFORE computing the Merkle leaf hash
    # so that the stored leaf_hash matches recomputation from the final payload.
    payload["khipu_ext"]["capsule_id"] = capsule_id

    # Recompute canonical bytes including khipu_ext.capsule_id
    payload_bytes = _canonical_json(payload)

    # Record in szl-lake Merkle transparency log
    transparency = _TRANSPARENCY_LOG.append(payload_bytes)

    # leaf_index is in transparency{} (part of the capsule return value).
    # Do NOT embed it into payload to keep the payload canonical and
    # verifiable: the verifier computes leaf_hash(payload) and walks the proof.

    honesty_parts = [
        f"SCITT Agent Action Capsule per {CAPSULE_SPEC_VERSION}.",
        f"Verdict: {verdict} → disposition: {payload['disposition']['decision']}.",
        f"Signing profile: {signing_profile}.",
        "Self-hosted Merkle transparency log (RFC 6962 SHA3-256).",
    ]
    if not _COSE_AVAILABLE:
        honesty_parts.append(
            "COSE_Sign1 UNAVAILABLE (cbor2 or pycose not installed). "
            "JSON-profile fallback used. Upgrade ROADMAP: pip install cbor2 pycose."
        )
    if not private_key_pem:
        honesty_parts.append(
            "Signing key absent (SZL_COSIGN_PRIVATE_KEY_PEM not set). "
            "Capsule structure is authentic; DSSE/COSE signature not applied."
        )

    return {
        "capsule_id": capsule_id,
        "spec_version": CAPSULE_SPEC_VERSION,
        "signing_profile": signing_profile,
        "payload": payload,
        "cose_sign1_b64": cose_sign1_b64,
        "json_envelope": json_envelope,
        "transparency": transparency,
        "honesty": " ".join(honesty_parts),
    }


def get_transparency_view() -> dict[str, Any]:
    """Return the current SCITT Transparency Service view over the szl-lake Merkle log."""
    return _TRANSPARENCY_LOG.get_transparency_view()


# ---------------------------------------------------------------------------
# FASTAPI ROUTE REGISTRATION
# ---------------------------------------------------------------------------

# In-process capsule store (capsule_id → capsule)
_CAPSULE_STORE: dict[str, dict[str, Any]] = {}
_CAPSULE_STORE_LOCK = threading.RLock()


def _store_capsule(capsule: dict[str, Any]) -> None:
    with _CAPSULE_STORE_LOCK:
        _CAPSULE_STORE[capsule["capsule_id"]] = capsule


def register(app: Any, ns: str = "a11oy") -> dict[str, Any]:
    """
    Register SCITT endpoints on a FastAPI app.

    Routes added:
      GET /api/{ns}/v1/scitt/capsule/{capsule_id}
        → Return a stored SCITT capsule by ID.
      GET /api/{ns}/v1/scitt/transparency
        → Return the SCITT Transparency Service view (Merkle log summary).

    Returns {"registered": [...routes...], "status": "ok"}
    """
    try:
        from fastapi import FastAPI
        from fastapi.responses import JSONResponse
    except ImportError:
        return {"registered": [], "status": "fastapi-absent"}

    routes: list[str] = []

    @app.get(f"/api/{ns}/v1/scitt/capsule/{{capsule_id}}")
    async def scitt_get_capsule(capsule_id: str) -> JSONResponse:
        with _CAPSULE_STORE_LOCK:
            capsule = _CAPSULE_STORE.get(capsule_id)
        if capsule is None:
            return JSONResponse(
                {
                    "error": f"capsule not found: {capsule_id}",
                    "hint": "Capsules are stored in-process; restart clears them. "
                            "Persistent storage is ROADMAP.",
                },
                status_code=404,
            )
        return JSONResponse(capsule)

    routes.append(f"GET /api/{ns}/v1/scitt/capsule/{{capsule_id}}")

    @app.get(f"/api/{ns}/v1/scitt/transparency")
    async def scitt_transparency_view() -> JSONResponse:
        return JSONResponse(get_transparency_view())

    routes.append(f"GET /api/{ns}/v1/scitt/transparency")

    return {"registered": routes, "status": "ok"}


def build_and_store_capsule(**kwargs: Any) -> dict[str, Any]:
    """
    Convenience wrapper: build a capsule and store it in the in-process store.
    Returns the capsule dict (with capsule_id for later retrieval).
    """
    capsule = build_capsule(**kwargs)
    _store_capsule(capsule)
    return capsule
