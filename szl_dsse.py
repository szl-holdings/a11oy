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
    - The active runtime public key is published at /cosign.pub (PUBLIC); the
      embedded organization key remains an offline/historical fallback only.
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
  keyid: SHA-256(normalized public PEM); legacy "szlholdings-cosign" accepted
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
# Doctrine note: Private key is RUNTIME SECRET ONLY (SZL_COSIGN_PRIVATE_PEM or
#                the supported compatibility/mounted shared-signer sources).
#                NEVER commit it. Absent = PLACEHOLDER mode (honest, no fabrication).
#                Active public key is derived from the runtime signer; the embedded
#                COSIGN_PUBLIC_PEM remains the no-secret offline fallback.
# PAE spec:      DSSEv1 SP LEN(type) SP type SP LEN(body) SP body
# ---------------------------------------------------------------------------
# INTEROP NOTE — relationship to the shared `szl-receipt` lib (v0.1.0):
#   szl_dsse and szl-receipt share the SAME crypto primitive end-to-end —
#   DSSEv1 PAE, ECDSA-P256 over SHA-256, sorted-key canonical JSON — so the
#   "one signing flag" doctrine already holds at the ALGORITHM level. They are
#   intentionally NOT merged because they differ at the schema/key-model level:
#     - payloadType: this module pins "application/vnd.szl.khipu+json" and a
#       signatures[] array with keyid; szl-receipt uses a single `signature`
#       field + organ/digest/algo and "application/vnd.szl.receipt+json".
#     - key model: this module is bound to the published SZLHOLDINGS *Cosign*
#       keypair (cosign.pub) so receipts stay verifiable by `cosign verify-blob`
#       and Rekor; szl-receipt uses configurable/ephemeral keys.
#   Swapping to szl-receipt would change the on-the-wire receipt format and
#   break cosign/Rekor verification of existing Khipu receipts. Decision:
#   KEEP szl_dsse as the canonical cosign/Rekor-backed Khipu signer; the shared
#   lib remains canonical for non-Khipu organ receipts. Duplication is the
#   PAE/sign/verify helpers (~3 small fns), documented rather than force-merged.
# ---------------------------------------------------------------------------
from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
import threading
from datetime import datetime, timezone
from typing import Any

from szl_content_address import sha256_content_address

KEYID = "szlholdings-cosign"
KHIPU_PAYLOAD_TYPE = "application/vnd.szl.khipu+json"
COSIGN_PUB_FINGERPRINT_ENV = "SZL_COSIGN_PUB_SHA256"  # optional pin
TRUSTED_PUBLIC_PEMS_ENV = "SZL_COSIGN_TRUSTED_PUBLIC_PEMS"
MAX_TRUSTED_PUBLIC_KEYS = 32
MAX_TRUSTED_PUBLIC_PEMS_BYTES = 16 * 1024

# The published public key (szl-holdings/.github/cosign.pub). Embedded so the
# /khipu/verify endpoint can verify WITHOUT a network call. This is PUBLIC data.
COSIGN_PUBLIC_PEM = """
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEyq9ALpZuegbE67GRpWp8FfGSX1IJ
bt5gw4jQ3RuBuIYIZchnfn9XLZf5KKw+zRfq5EJ8S+5cqwai5Wz0FDSyyA==
-----END PUBLIC KEY-----
"""

PUB_KEY_URL = "/cosign.pub"

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
# Key loading (private = runtime secret; public = active or embedded fallback)
# ---------------------------------------------------------------------------

# Runtime secret env var names, in resolution order. A11oy's shared signer uses
# SZL_COSIGN_PRIVATE_PEM; the older *_KEY_PEM spelling and legacy aliases remain
# compatible fallbacks.
# NEITHER is ever committed — both are runtime-only secrets.
PRIVATE_KEY_ENV_VARS = ("SZL_COSIGN_PRIVATE_PEM", "SZL_COSIGN_PRIVATE_KEY_PEM", "szlcosig", "szlcosig1", "SZLCOSIG", "SZLCOSIG1")
_RUNTIME_PUBLIC_KEYS: dict[str, str] = {}
_RUNTIME_PUBLIC_KEYS_LOCK = threading.Lock()
_ACTIVE_RUNTIME_KEYID: str | None = None


def _load_private_key():
    """Load the Cosign EC private key from the runtime secret.

    Resolution order (additive, never raises into the request path):
      1. A persistent source accepted by the shared A11oy signer.
      2. Legacy/base64-wrapped inline environment spellings.

    Returns None if no secret is present or the value is invalid — the caller
    then emits an honest UNSIGNED envelope. NEVER fabricates a key."""
    try:
        from a11oy_signing_key import load_signing_key

        private_key, _, source, _ = load_signing_key()
        if private_key is not None and source.startswith("persistent:"):
            return private_key
    except Exception:
        pass

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
        from cryptography.hazmat.primitives.asymmetric import ec
        private_key = load_pem_private_key(pem.encode("utf-8"), password=None)
        if not isinstance(private_key, ec.EllipticCurvePrivateKey):
            return None
        if getattr(private_key.curve, "name", "") != "secp256r1":
            return None
        return private_key
    except Exception:
        return None


def _normalize_public_key_pem(public_pem: str) -> str:
    """Validate and normalize a PUBLIC ECDSA P-256 key as SPKI PEM."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    public_key = serialization.load_pem_public_key(public_pem.encode("utf-8"))
    if not isinstance(public_key, ec.EllipticCurvePublicKey):
        raise ValueError("trusted public key is not ECDSA")
    if getattr(public_key.curve, "name", "") != "secp256r1":
        raise ValueError("trusted public key is not P-256")
    return public_key.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def keyid_for_public_pem(public_pem: str) -> str:
    """Return the receipt key identifier for a normalized PUBLIC PEM."""
    normalized = _normalize_public_key_pem(public_pem)
    return hashlib.sha256(normalized.strip().encode("ascii")).hexdigest()


def configure_runtime_public_key(public_pem: str) -> str:
    """Trust and activate the public half injected by the shared signer.

    Previously configured runtime keys remain trusted for the process lifetime
    so an in-process signer rotation cannot invalidate already-issued receipts.
    Cross-restart retention is explicit through
    ``SZL_COSIGN_TRUSTED_PUBLIC_PEMS``.
    """
    global _ACTIVE_RUNTIME_KEYID
    normalized = _normalize_public_key_pem(public_pem)
    keyid = keyid_for_public_pem(normalized)
    with _RUNTIME_PUBLIC_KEYS_LOCK:
        _RUNTIME_PUBLIC_KEYS[keyid] = normalized
        _ACTIVE_RUNTIME_KEYID = keyid
    return keyid


def _public_pem_for_private_key(private_key) -> str:
    from cryptography.hazmat.primitives import serialization

    return private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def _configured_trusted_public_pems() -> list[tuple[str | None, str]]:
    """Parse retained PUBLIC keys without raising into verification paths."""
    raw = os.environ.get(TRUSTED_PUBLIC_PEMS_ENV, "").strip()
    if not raw:
        return []
    if len(raw.encode("utf-8")) > MAX_TRUSTED_PUBLIC_PEMS_BYTES:
        return []
    try:
        value = json.loads(raw)
    except Exception:
        return []
    if isinstance(value, list):
        return [
            (None, pem) for pem in value if isinstance(pem, str)
        ][:MAX_TRUSTED_PUBLIC_KEYS]
    if isinstance(value, dict):
        return [
            (str(alias), pem)
            for alias, pem in value.items()
            if isinstance(pem, str)
        ][:MAX_TRUSTED_PUBLIC_KEYS]
    return []


def _trusted_public_key_pems() -> dict[str, str]:
    """Build the operator-controlled verification keyring.

    The ring contains the embedded historical key, retained public-only
    rotation keys, every runtime-injected key seen in this process, and the
    active private signer's public half. Receipt contents never add trust.
    """
    trusted: dict[str, str] = {}

    def add(public_pem: str, aliases: tuple[str, ...] = ()) -> None:
        try:
            normalized = _normalize_public_key_pem(public_pem)
            fingerprint = keyid_for_public_pem(normalized)
        except Exception:
            return
        trusted[fingerprint] = normalized
        for alias in aliases:
            if alias:
                trusted[alias] = normalized

    add(COSIGN_PUBLIC_PEM, (KEYID,))
    for alias, public_pem in _configured_trusted_public_pems():
        add(public_pem, ((alias,) if alias else ()))
    with _RUNTIME_PUBLIC_KEYS_LOCK:
        runtime_keys = dict(_RUNTIME_PUBLIC_KEYS)
    for keyid, public_pem in runtime_keys.items():
        add(public_pem, (keyid,))
    private_key = _load_private_key()
    if private_key is not None:
        public_pem = _public_pem_for_private_key(private_key)
        add(public_pem, (keyid_for_public_pem(public_pem),))
    add(active_public_key_pem())
    return trusted


def active_public_key_pem() -> str:
    """Return the public half of the active runtime signer.

    When a private runtime secret is configured, deriving its public key keeps
    newly emitted receipts, the in-process verifier, and the live public-key
    routes cryptographically aligned. With no runtime signer, preserve the
    published organization key as the historical/offline verification fallback.
    """
    private_key = _load_private_key()
    if private_key is not None:
        return _public_pem_for_private_key(private_key)
    with _RUNTIME_PUBLIC_KEYS_LOCK:
        active_keyid = _ACTIVE_RUNTIME_KEYID
        active_public_pem = (
            _RUNTIME_PUBLIC_KEYS.get(active_keyid, "")
            if active_keyid
            else ""
        )
    if active_public_pem:
        return active_public_pem
    try:
        from a11oy_signing_key import load_signing_key

        _, shared_public_pem, source, _ = load_signing_key()
        if shared_public_pem and source != "unavailable":
            return _normalize_public_key_pem(shared_public_pem)
    except Exception:
        pass
    return _normalize_public_key_pem(COSIGN_PUBLIC_PEM)


def _load_public_key():
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    return load_pem_public_key(active_public_key_pem().encode("utf-8"))


def signing_available() -> bool:
    return _load_private_key() is not None


def public_key_fingerprint() -> str:
    return sha256_content_address(
        active_public_key_pem().strip().encode(), purpose="public-key"
    )


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
        "_pae_sha256": sha256_content_address(to_sign, purpose="dsse-pae"),
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
    public_pem = _public_pem_for_private_key(priv)
    keyid = configure_runtime_public_key(public_pem)
    sig = priv.sign(to_sign, ec.ECDSA(hashes.SHA256()))
    env["signatures"] = [{"sig": base64.b64encode(sig).decode("ascii"), "keyid": keyid}]
    env["signed"] = True
    env["honesty"] = ("REAL — ECDSA-P256-SHA256 over DSSE PAE; verifiable by "
                      "`cosign verify-blob --key cosign.pub` and by the /khipu/verify endpoint.")
    env["verify_key_url"] = PUB_KEY_URL
    return env


def verify_envelope(env: dict[str, Any]) -> dict[str, Any]:
    """Verify a DSSE envelope's signature against the SZLHOLDINGS cosign.pub.

    Recomputes PAE over the embedded payload + payloadType and checks the
    ECDSA signature. Returns a structured verdict (never raises)."""
    active_keyid = keyid_for_public_pem(active_public_key_pem())
    trusted_pems = _trusted_public_key_pems()
    trusted_keyids = sorted({
        keyid_for_public_pem(public_pem)
        for public_pem in trusted_pems.values()
    })
    out: dict[str, Any] = {
        "keyid_expected": active_keyid,
        "keyid_legacy": KEYID,
        "keyids_trusted": trusted_keyids,
        "pub_fingerprint_sha256": public_key_fingerprint(),
        "verify_key_url": PUB_KEY_URL,
    }
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
        out["pae_sha256"] = sha256_content_address(to_verify, purpose="dsse-pae")
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature
        results = []
        any_ok = False
        for s in sigs:
            sig_b64 = s.get("sig", "")
            keyid = s.get("keyid", "")
            if keyid == KEYID:
                candidate_pems = {
                    keyid_for_public_pem(public_pem): public_pem
                    for public_pem in trusted_pems.values()
                }
            elif keyid in trusted_pems:
                candidate_pems = {
                    keyid_for_public_pem(trusted_pems[keyid]): trusted_pems[keyid]
                }
            else:
                results.append({
                    "keyid": keyid,
                    "verified": False,
                    "reason": "unexpected keyid",
                })
                continue
            signature_verified = False
            try:
                sig = base64.b64decode(sig_b64, validate=True)
                for candidate_keyid, candidate_pem in candidate_pems.items():
                    pub = load_pem_public_key(candidate_pem.encode("ascii"))
                    try:
                        pub.verify(sig, to_verify, ec.ECDSA(hashes.SHA256()))
                    except InvalidSignature:
                        continue
                    results.append({
                        "keyid": keyid,
                        "verified": True,
                        "verified_by_keyid": candidate_keyid,
                    })
                    any_ok = True
                    signature_verified = True
                    break
                if not signature_verified:
                    results.append({
                        "keyid": keyid,
                        "verified": False,
                        "reason": "signature mismatch",
                    })
            except Exception as e:  # malformed sig or trusted-key parse failure
                print(f"[dsse] signature verify error: {type(e).__name__}", file=sys.stderr)
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
