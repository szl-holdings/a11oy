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
import json
import os
import re
import sys
from datetime import datetime, timezone
from typing import Any

from szl_content_address import sha256_content_address

KEYID = "szlholdings-cosign"
KHIPU_PAYLOAD_TYPE = "application/vnd.szl.khipu+json"
COSIGN_PUB_FINGERPRINT_ENV = "SZL_COSIGN_PUB_SHA256"  # optional pin

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

# Runtime secret names accepted by the shared loader.  Khipu signing remains
# fail-closed unless that loader reports a persistent source; its non-strict
# ephemeral key is still used as the live public alias and by other receipt
# surfaces in this process.
PRIVATE_KEY_ENV_VARS = (
    "SZL_COSIGN_PRIVATE_PEM",
    "SZL_COSIGN_PRIVATE_KEY_PEM",
    "A11OY_RECEIPT_KEY_PEM",
    "szlcosig",
    "szlcosig1",
    "SZLCOSIG",
    "SZLCOSIG1",
)
LEGACY_KEYID = KEYID
VERIFY_KEY_BUNDLE_ENV = "A11OY_RECEIPT_VERIFY_KEYS_PEM"
VERIFY_KEY_PATHS_ENV = "A11OY_RECEIPT_VERIFY_KEY_PATHS"


def _load_shared_key():
    """Return the process-wide signer tuple without exposing key material."""
    try:
        from a11oy_signing_key import load_signing_key
        return load_signing_key()
    except Exception as e:
        return None, "", "unavailable", "shared key load failed: %s" % type(e).__name__


def _load_private_key():
    """Return only a persistent shared P-256 signer.

    The process-wide loader may produce an honest boot-ephemeral identity for
    non-strict receipt surfaces. Khipu keeps its established no-secret
    contract: without a persistent configured source it emits UNSIGNED.
    """
    private_key, _public_pem, source, _error = _load_shared_key()
    if not (
        private_key is not None
        and isinstance(source, str)
        and source.startswith("persistent:")
    ):
        return None
    return private_key


def active_public_key_pem() -> str:
    """Return the exact public key exposed by the shared live aliases."""
    _private_key, public_pem, _source, _error = _load_shared_key()
    return public_pem or ""


def _pem_blocks(value: str) -> list[str]:
    return [
        block.strip() + "\n"
        for block in re.findall(
            r"-----BEGIN PUBLIC KEY-----.*?-----END PUBLIC KEY-----",
            value or "",
            flags=re.DOTALL,
        )
    ]


def _configured_verification_pems() -> list[str]:
    """Load explicitly retained public keys; private material is never read."""
    pems = _pem_blocks(os.environ.get(VERIFY_KEY_BUNDLE_ENV, ""))
    raw_paths = os.environ.get(VERIFY_KEY_PATHS_ENV, "")
    for path in (item.strip() for item in raw_paths.split(os.pathsep)):
        if not path:
            continue
        try:
            with open(path, "r", encoding="utf-8") as handle:
                pems.extend(_pem_blocks(handle.read()))
        except Exception:
            continue
    return pems


def _public_key_record(public_pem: str, source: str):
    if not public_pem:
        return None
    try:
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        public_key = serialization.load_pem_public_key(public_pem.encode("utf-8"))
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            return None
        if getattr(public_key.curve, "name", "") != "secp256r1":
            return None
        normalized = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("ascii")
        fingerprint = sha256_content_address(
            normalized.strip().encode("ascii"), purpose="public-key"
        )
        return {
            "fingerprint": fingerprint,
            "public_key": public_key,
            "public_pem": normalized,
            "source": source,
        }
    except Exception:
        return None


def _verification_keyring() -> list[dict[str, Any]]:
    """Return active, embedded-historical, and operator-retained public keys."""
    candidates = [
        (active_public_key_pem(), "active"),
        (COSIGN_PUBLIC_PEM, "embedded-historical"),
    ]
    candidates.extend(
        (pem, "operator-retained") for pem in _configured_verification_pems()
    )
    records: list[dict[str, Any]] = []
    seen: set[str] = set()
    for public_pem, source in candidates:
        record = _public_key_record(public_pem, source)
        if record is None or record["fingerprint"] in seen:
            continue
        seen.add(record["fingerprint"])
        records.append(record)
    return records


def active_keyid() -> str:
    record = _public_key_record(active_public_key_pem(), "active")
    return record["fingerprint"] if record is not None else ""


def signing_available() -> bool:
    return _load_private_key() is not None


def public_key_fingerprint() -> str:
    return active_keyid()


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
    sig = priv.sign(to_sign, ec.ECDSA(hashes.SHA256()))
    env["signatures"] = [{"sig": base64.b64encode(sig).decode("ascii"), "keyid": active_keyid()}]
    env["signed"] = True
    env["honesty"] = ("REAL — ECDSA-P256-SHA256 over DSSE PAE; verifiable by "
                      "`cosign verify-blob --key cosign.pub` and by the /khipu/verify endpoint.")
    env["verify_key_url"] = PUB_KEY_URL
    return env


def verify_envelope(env: dict[str, Any]) -> dict[str, Any]:
    """Verify a DSSE envelope against the identified retained P-256 key.

    New envelopes carry the SHA-256 public-key fingerprint as keyid.
    Historical envelopes using szlholdings-cosign are tried against the
    bounded keyring so a configured rotation does not invalidate old receipts.
    """
    active_id = active_keyid()
    out: dict[str, Any] = {
        "keyid_expected": active_id or LEGACY_KEYID,
        "pub_fingerprint_sha256": active_id or None,
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
        out["pae_sha256"] = sha256_content_address(
            to_verify, purpose="dsse-pae"
        )
        ring = _verification_keyring()
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature
        results = []
        any_ok = False
        verified_fingerprint = None
        for signature in sigs:
            sig_b64 = signature.get("sig", "")
            keyid = str(signature.get("keyid", ""))
            requested_fingerprint = (
                keyid.split(":", 1)[1]
                if keyid.startswith("sha256:")
                else keyid
            )
            if keyid == LEGACY_KEYID:
                candidates = ring
            else:
                candidates = [
                    record
                    for record in ring
                    if record["fingerprint"] == requested_fingerprint
                ]
            if not candidates:
                results.append({
                    "keyid": keyid,
                    "verified": False,
                    "reason": "unexpected or unavailable keyid",
                })
                continue
            try:
                signature_bytes = base64.b64decode(sig_b64)
            except Exception:
                results.append({
                    "keyid": keyid,
                    "verified": False,
                    "reason": "signature decode error",
                })
                continue
            matched = None
            for record in candidates:
                try:
                    record["public_key"].verify(
                        signature_bytes,
                        to_verify,
                        ec.ECDSA(hashes.SHA256()),
                    )
                    matched = record
                    break
                except InvalidSignature:
                    continue
                except Exception as e:
                    print(
                        f"[dsse] signature verify error: {e!r}",
                        file=sys.stderr,
                    )
            if matched is None:
                results.append({
                    "keyid": keyid,
                    "verified": False,
                    "reason": "signature mismatch",
                })
                continue
            results.append({
                "keyid": keyid,
                "verified": True,
                "pub_fingerprint_sha256": matched["fingerprint"],
                "key_source": matched["source"],
            })
            any_ok = True
            verified_fingerprint = matched["fingerprint"]
        try:
            out["payload_decoded"] = json.loads(body)
        except Exception:
            pass
        if verified_fingerprint:
            out["pub_fingerprint_sha256"] = verified_fingerprint
        return {
            **out,
            "verified": any_ok,
            "signatures": results,
            "payloadType": payload_type,
        }
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
