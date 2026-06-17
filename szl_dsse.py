# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11/v12
# Authored by Yachay (CTO) — Provenance Hardening: PLACEHOLDER -> REAL.
"""
szl_dsse — DSSE (in-toto/Dead-Simple-Signing-Envelope) signing + verification
for SZL Khipu receipts, backed by the SZLHOLDINGS **Cosign** keypair.

  Spec sources baked in:
    - DSSE protocol (secure-systems-lab/dsse) — PAE pre-authentication encoding:
        PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
        SIGNATURE       = Sign(PAE(UTF8(payloadType), SERIALIZED_BODY))
    - Sigstore Cosign (docs.sigstore.dev/cosign) — key-based blob signing:
        cosign sign-blob   --key cosign.key  <blob>   (ECDSA P-256 over SHA-256)
        cosign verify-blob --key cosign.pub  --signature <sig> <blob>

  KEY MODEL (honest):
    - The canonical signing key is the SZLHOLDINGS Cosign keypair generated with
      `cosign generate-key-pair` (imported from an OpenSSL P-256 EC key).
    - cosign.pub is published at szl-holdings/.github/cosign.pub (PUBLIC).
    - The PRIVATE key is delivered to each Space ONLY as a runtime secret
      env var `SZL_COSIGN_PRIVATE_PEM` (PKCS8 PEM). It is NEVER committed to a
      repo (HF or GitHub). If the secret is absent the module reports
      `signing_available=false` and emits a clearly-labelled UNSIGNED receipt —
      it NEVER fabricates a signature.
    - In-Space signing uses the Python `cryptography` lib over the DSSE PAE
      bytes. This is byte-for-byte verifiable by the `cosign` CLI (proven:
      cosign verify-blob accepts the cryptography-produced ECDSA-SHA256 sig,
      and Python verifies cosign-produced sigs — full round-trip equivalence).

  payloadType for Khipu receipts: "application/vnd.szl.khipu+json"
  keyid: "szlholdings-cosign"
"""
# ---------------------------------------------------------------------------
# DEVELOPER ORIENTATION (added by Perplexity Computer Agent, 2026-06)
# Purpose:       DSSE (Dead-Simple-Signing-Envelope) signing + verification for
#                SZL Khipu receipts, backed by the SZLHOLDINGS Cosign keypair.
# Key entry pts: sign_payload(payload_obj, payload_type) -> DSSE envelope dict
#                verify_envelope(env) -> verdict dict
#                sign_khipu_receipt(receipt) -> receipt dict with DSSE envelope
#                signing_available() -> bool (False if no private key secret)
# Related mods:  szl_khipu.py (DAG that stores receipts),
#                szl_wire.py (Wire F uses this to sign cross-pod receipts),
#                szl_be_hardening.py (DurableKhipu stores signed receipts)
# Doctrine note: Private key is RUNTIME SECRET ONLY (SZL_COSIGN_PRIVATE_KEY_PEM).
#                NEVER commit it. Absent = PLACEHOLDER mode (honest, no fabrication).
#                Public key is embedded in COSIGN_PUBLIC_PEM for offline verification.
# PAE spec:      DSSEv1 SP LEN(type) SP type SP LEN(body) SP body
# ---------------------------------------------------------------------------
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

KEYID = "szlholdings-cosign"
KHIPU_PAYLOAD_TYPE = "application/vnd.szl.khipu+json"
COSIGN_PUB_FINGERPRINT_ENV = "SZL_COSIGN_PUB_SHA256"  # optional pin

# The published public key (szl-holdings/.github/cosign.pub). Embedded so the
# /khipu/verify endpoint can verify WITHOUT a network call. This is PUBLIC data.
COSIGN_PUBLIC_PEM = """
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEtl5xy+0MtSix5CRNrpDLnSSsrLUw
a+am+cePik15VKZVz5tMz4OsR9MJY6QcNA5NNJibEoIToALy0KXA+XeO7g==
-----END PUBLIC KEY-----
"""

PUB_KEY_URL = "https://github.com/szl-holdings/.github/blob/main/cosign.pub"

# ---------------------------------------------------------------------------
# Canonical JSON  +  DSSE PAE
# ---------------------------------------------------------------------------

def canonical_json(obj: Any) -> bytes:
    """Deterministic canonical JSON: sorted keys, no extra whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pae(payload_type: str, body: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (DSSEv1)."""
    t = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" " + str(len(body)).encode() + b" " + body


# ---------------------------------------------------------------------------
# Key loading (private = runtime secret; public = embedded)
# ---------------------------------------------------------------------------

# Runtime secret env var names, in resolution order. The canonical name is
# SZL_COSIGN_PRIVATE_KEY_PEM (Kubernetes secretKeyRef + GitHub org secret); the
# established SZL_COSIGN_PRIVATE_PEM is kept as a backward-compatible fallback.
# NEITHER is ever committed — both are runtime-only secrets.
PRIVATE_KEY_ENV_VARS = ("SZL_COSIGN_PRIVATE_KEY_PEM", "SZL_COSIGN_PRIVATE_PEM", "szlcosig", "szlcosig1", "SZLCOSIG", "SZLCOSIG1")


def _load_private_key():
    """Load the Cosign EC private key from the runtime secret.

    Resolution order (additive, never raises into the request path):
      1. SZL_COSIGN_PRIVATE_KEY_PEM   (canonical — k8s secretKeyRef / org secret)
      2. SZL_COSIGN_PRIVATE_PEM       (legacy szlholdings-cosign fallback)

    Returns None if no secret is present or the value is invalid — the caller
    then emits an honest UNSIGNED envelope. NEVER fabricates a key."""
    pem = None
    for _name in PRIVATE_KEY_ENV_VARS:
        val = os.environ.get(_name)
        if val:
            pem = val
            break
    if not pem:
        return None
    try:
        # Allow the secret to be provided base64-wrapped (HF UI friendliness)
        if "BEGIN" not in pem:
            pem = base64.b64decode(pem).decode("utf-8")
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        return load_pem_private_key(pem.encode("utf-8"), password=None)
    except Exception:
        return None


def _load_public_key():
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    return load_pem_public_key(COSIGN_PUBLIC_PEM.encode("utf-8"))


def signing_available() -> bool:
    return _load_private_key() is not None


def public_key_fingerprint() -> str:
    return hashlib.sha256(COSIGN_PUBLIC_PEM.strip().encode()).hexdigest()


# ---------------------------------------------------------------------------
# Sign / Verify
# ---------------------------------------------------------------------------

def sign_payload(payload_obj: Any, payload_type: str = KHIPU_PAYLOAD_TYPE) -> dict[str, Any]:
    """Produce a DSSE envelope over the canonical JSON of `payload_obj`.

    Returns the DSSE envelope dict:
      {payload(b64), payloadType, signatures:[{sig(b64), keyid}], ...meta}
    If no private key is present, returns an UNSIGNED envelope with an explicit
    honesty marker (NO fabricated signature)."""
    body = canonical_json(payload_obj)
    to_sign = pae(payload_type, body)
    env: dict[str, Any] = {
        "payloadType": payload_type,
        "payload": base64.b64encode(body).decode("ascii"),
        "_dsse": "DSSEv1",
        "_pae_sha256": hashlib.sha256(to_sign).hexdigest(),
        "_signed_at": datetime.now(timezone.utc).isoformat(),
    }
    priv = _load_private_key()
    if priv is None:
        env["signatures"] = []
        env["honesty"] = ("UNSIGNED — neither SZL_COSIGN_PRIVATE_KEY_PEM nor "
                          "SZL_COSIGN_PRIVATE_PEM secret present in this runtime; "
                          "no signature fabricated.")
        env["signed"] = False
        return env
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    sig = priv.sign(to_sign, ec.ECDSA(hashes.SHA256()))
    env["signatures"] = [{"sig": base64.b64encode(sig).decode("ascii"), "keyid": KEYID}]
    env["signed"] = True
    env["honesty"] = ("REAL — ECDSA-P256-SHA256 over DSSE PAE; verifiable by "
                      "`cosign verify-blob --key cosign.pub` and by the /khipu/verify endpoint.")
    env["verify_key_url"] = PUB_KEY_URL
    return env


def verify_envelope(env: dict[str, Any]) -> dict[str, Any]:
    """Verify a DSSE envelope's signature against the SZLHOLDINGS cosign.pub.

    Recomputes PAE over the embedded payload + payloadType and checks the
    ECDSA signature. Returns a structured verdict (never raises)."""
    out: dict[str, Any] = {"keyid_expected": KEYID, "pub_fingerprint_sha256": public_key_fingerprint(),
                           "verify_key_url": PUB_KEY_URL}
    try:
        payload_b64 = env.get("payload")
        payload_type = env.get("payloadType")
        sigs = env.get("signatures") or []
        if not payload_b64 or not payload_type:
            return {**out, "verified": False, "reason": "missing payload/payloadType"}
        if not sigs:
            return {**out, "verified": False, "reason": "no signatures (unsigned envelope)"}
        body = base64.b64decode(payload_b64)
        to_verify = pae(payload_type, body)
        out["pae_sha256"] = hashlib.sha256(to_verify).hexdigest()
        pub = _load_public_key()
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature
        results = []
        any_ok = False
        for s in sigs:
            sig_b64 = s.get("sig", "")
            keyid = s.get("keyid", "")
            try:
                sig = base64.b64decode(sig_b64)
                pub.verify(sig, to_verify, ec.ECDSA(hashes.SHA256()))
                results.append({"keyid": keyid, "verified": True})
                any_ok = True
            except InvalidSignature:
                results.append({"keyid": keyid, "verified": False, "reason": "signature mismatch"})
            except Exception as e:  # malformed sig
                print(f"[dsse] signature verify error: {e!r}", file=sys.stderr)
                results.append({"keyid": keyid, "verified": False, "reason": "signature verify error"})
        # Optionally decode the payload back for the caller's convenience
        try:
            out["payload_decoded"] = json.loads(body)
        except Exception:
            pass
        return {**out, "verified": any_ok, "signatures": results,
                "payloadType": payload_type}
    except Exception as e:
        print(f"[dsse] verify_envelope error: {e!r}", file=sys.stderr)
        return {**out, "verified": False, "reason": "verification error"}


# ---------------------------------------------------------------------------
# Convenience: build a full signed Khipu receipt dict
# ---------------------------------------------------------------------------

def _normalize_neuro_citations(neuro_citations: Any) -> list[dict[str, Any]]:
    """Coerce a neuro_citations argument into a list of {doi,label} dicts.

    Accepts None (-> []), a list of dicts, or a list of bare DOI strings.
    Each citation is normalized to a dict carrying at least a `doi` key and a
    human-readable `label` (defaults to the DOI if no label supplied). This is
    the cognitive-neuroscience provenance channel added for the Hickok ingest
    (Lutar Anchors A36/A37/A38) — see DOI 10.1038/nrn2113 (Hickok & Poeppel
    2007, dual-stream model)."""
    if not neuro_citations:
        return []
    out: list[dict[str, Any]] = []
    for c in neuro_citations:
        if isinstance(c, str):
            out.append({"doi": c, "label": c})
        elif isinstance(c, dict):
            doi = c.get("doi", "")
            label = c.get("label") or doi
            entry = {"doi": doi, "label": label}
            # Preserve any extra provenance fields the caller supplied.
            for k, v in c.items():
                if k not in entry:
                    entry[k] = v
            out.append(entry)
    return out


def sign_khipu_receipt(receipt: dict[str, Any],
                       neuro_citations: Any = None) -> dict[str, Any]:
    """Return {receipt, dsse} where dsse is the DSSE envelope over the receipt.

    Task E (Hickok ingest): every receipt now carries a `neuro_citations` list
    (default empty). Each entry is `{doi, label}`. This embeds cognitive-
    neuroscience provenance directly into the signed payload so the DSSE
    envelope cryptographically commits to the citation set. Callers that pass
    nothing keep the prior behaviour (empty list, no semantic change)."""
    # ADDITIVE: never overwrite a neuro_citations the caller already placed on
    # the receipt; merge the explicit argument in front of any existing list.
    existing = receipt.get("neuro_citations")
    merged = _normalize_neuro_citations(neuro_citations) + _normalize_neuro_citations(existing)
    # de-dup on doi while preserving order
    seen: set = set()
    deduped: list[dict[str, Any]] = []
    for c in merged:
        key = c.get("doi", "")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(c)
    receipt["neuro_citations"] = deduped
    env = sign_payload(receipt, KHIPU_PAYLOAD_TYPE)
    # Verifiable-corpus hook (additive, off hot path, never raises): publish the
    # signed receipt to the public dataset. Skips unsigned/placeholder envelopes.
    try:
        import szl_corpus_publish as _corpus
        _corpus.on_new_receipt(env, extra={"surface": "khipu"})
    except Exception:
        pass
    return {"receipt": receipt, "dsse": env}
