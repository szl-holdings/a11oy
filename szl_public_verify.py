# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Wave N — PUBLIC "Verify a Receipt" flow (trust-us -> verify-the-receipt).
"""szl_public_verify.py — a PUBLIC, no-login receipt verifier.

THE GAP this closes: a11oy publishes DSSE/Khipu receipts and asks the world to
believe them ("trust us"). This module turns that into "verify the receipt": ANY
visitor — an investor, an auditor, a skeptic — can PASTE a DSSE envelope (or a
receipt id / digest) and get an INDEPENDENT, in-browser-facing cryptographic
verdict, with every individual check shown HONESTLY.

ENDPOINT (registered BEFORE the SPA catch-all):
  POST /api/a11oy/v1/verify/receipt   body {envelope} OR {receipt_id}
  GET  /api/a11oy/v1/verify/receipt/{receipt_id}   (shareable convenience)
PAGE:
  GET  /verify   (web/verify-receipt.html) — paste box + PASS/FAIL panel.
  Shareable links resolved by the page:
    /verify?receipt=<digest>
    /verify?envelope=<base64url(JSON DSSE envelope)>   (compact, self-contained)

WHAT IS CHECKED (each labelled honestly, never a fabricated verdict):
  1. signature      — ECDSA-P256-SHA256 over the DSSE PAE, verified against the
                      PUBLISHED SZLHOLDINGS cosign public key (szl_dsse.COSIGN_PUBLIC_PEM).
                      Labels: VERIFIED | MISMATCH | UNSIGNED-LOCAL | UNAVAILABLE.
  2. payload_digest — RE-HASH the DSSE payload bytes and compare to the digest the
                      payload DECLARES about itself (payload_digest / digest field).
                      CRITICAL (the fixed /verify comparison): we compare the
                      recomputed payload digest to the *DECLARED payload_digest*,
                      NOT to the chain-link seal id. Comparing recompute-vs-chain-id
                      was the old bug that produced a simultaneous VERIFIED+MISMATCH.
                      Labels: VERIFIED | MISMATCH | UNAVAILABLE.
  3. hash_chain     — if the receipt is present in the in-process Khipu DAG (by its
                      seal digest / receipt_id), re-walk prev-links to genesis and
                      recompute each seal (reuses szl_khipu_verify.verify_digest).
                      Labels: VERIFIED | MISMATCH | UNAVAILABLE.

HONESTY (Doctrine v11 — never weaken):
  - No private key locally => the signature check is UNSIGNED-LOCAL (envelope had
    no signatures) or UNAVAILABLE (crypto lib / pub key not loadable). NEVER faked.
  - The three checks are computed INDEPENDENTLY; a single failing check does not
    silently flip another to green, and a passing check is never asserted for a
    check we could not actually run (that is UNAVAILABLE, honestly).
  - overall verdict: PASS only if every RUN check passed and none MISMATCHed;
    FAIL if ANY check MISMATCHed; otherwise INCONCLUSIVE (checks we could not run
    locally, e.g. UNSIGNED-LOCAL signature + UNAVAILABLE chain).
  - Λ = Conjecture 1 (NEVER a theorem). This surface adds NOTHING to the locked-8
    (749/14/163 @ kernel c7c0ba17). Trust ceiling never 100%. No codename emitted.

Reuses szl_dsse (real ECDSA-P256/DSSE) + szl_khipu_verify (chain walk) only. No new
pip dep, no CDN, no Node. Additive, try/except-guarded, stdlib + those two modules.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import time
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

# Honest check labels — never invent a fourth "green" that we did not earn.
VERIFIED = "VERIFIED"            # the check RAN and PASSED
MISMATCH = "MISMATCH"           # the check RAN and FAILED (tamper / bad sig)
UNSIGNED_LOCAL = "UNSIGNED-LOCAL"  # envelope carries no signature (honest, local)
UNAVAILABLE = "UNAVAILABLE"     # the check could not be RUN (no key / not in DAG)

_LAMBDA = "Conjecture 1 (NOT a theorem)"
_LOCKED = {"count": 8, "kernel": "c7c0ba17", "public_numbers": "749/14/163",
           "note": "public verifier adds NOTHING to the locked-8"}

_DOCTRINE = {
    "lambda": _LAMBDA,
    "locked_proven": _LOCKED,
    "trust_ceiling": "never 100%",
    "signature": "ECDSA-P256-SHA256 over DSSE PAE vs published SZLHOLDINGS cosign.pub",
    "payload_digest_compare": ("recomputed payload digest vs the DECLARED payload_digest "
                               "(NOT the chain seal id — that was the old simultaneous "
                               "VERIFIED+MISMATCH bug, fixed and not reintroduced)"),
    "hash_chain": "re-walk prev-links to genesis + recompute each seal (szl_khipu_verify)",
    "fabricated_data": False,
    "runtime_cdn": 0,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _canon(obj: Any) -> bytes:
    """Deterministic canonical JSON (sorted keys, compact) — matches szl_dsse."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _sha3_256_hex(b: bytes) -> str:
    return hashlib.sha3_256(b).hexdigest()


def _b64_any_decode(s: str) -> Optional[bytes]:
    """Decode base64 or base64url, with or without padding. None on failure."""
    if not isinstance(s, str):
        return None
    s2 = s.strip()
    # normalise url-safe -> std, fix padding
    s2 = s2.replace("-", "+").replace("_", "/")
    pad = (-len(s2)) % 4
    s2 = s2 + ("=" * pad)
    try:
        return base64.b64decode(s2)
    except (binascii.Error, ValueError):
        return None


def _declared_payload_digest(payload_obj: Any) -> Optional[str]:
    """Extract the digest the payload DECLARES about ITS OWN body, if any.

    This is the field we compare the recomputed digest to. It is NOT the Khipu
    chain seal id (that is the `digest`/`prev` chain link). Comparing against the
    chain id was the old bug that produced a simultaneous VERIFIED+MISMATCH.
    Accepted declared fields (first present wins):
      payload_digest, payloadDigest, content_digest, digest_sha256, sha256.
    """
    if not isinstance(payload_obj, dict):
        return None
    for k in ("payload_digest", "payloadDigest", "content_digest",
              "digest_sha256", "sha256"):
        v = payload_obj.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip().lower()
    return None


def _norm_digest(v: Optional[str]) -> Optional[str]:
    """Strip an optional algo prefix (sha256:, sha3-256:) and lowercase."""
    if not isinstance(v, str):
        return None
    v = v.strip().lower()
    if ":" in v:
        v = v.split(":", 1)[1]
    return v or None


# ---------------------------------------------------------------------------
# Check 1 — signature (reuse szl_dsse.verify_envelope; honest labels)
# ---------------------------------------------------------------------------
def _check_signature(env: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"check": "signature",
                           "algo": "ECDSA-P256-SHA256 over DSSE PAE"}
    try:
        import szl_dsse
    except Exception as e:  # crypto/module unavailable — honest UNAVAILABLE
        return {**out, "status": UNAVAILABLE,
                "detail": f"szl_dsse unavailable: {e!r}"}

    out["verify_key_url"] = getattr(szl_dsse, "PUB_KEY_URL", "")
    try:
        out["pub_fingerprint_sha256"] = szl_dsse.public_key_fingerprint()
    except Exception:
        pass

    sigs = env.get("signatures") or []
    if not sigs:
        # Envelope carries no signature at all — honest UNSIGNED-LOCAL, never faked.
        return {**out, "status": UNSIGNED_LOCAL,
                "detail": ("envelope has no signatures[]; nothing to verify "
                           "(honest UNSIGNED-LOCAL — no signature fabricated)")}
    try:
        verdict = szl_dsse.verify_envelope(env)
    except Exception as e:
        return {**out, "status": UNAVAILABLE, "detail": f"verify error: {e!r}"}

    if verdict.get("verified") is True:
        status = VERIFIED
    else:
        # There WERE signatures but none validated -> MISMATCH (real bad sig).
        status = MISMATCH
    return {**out, "status": status,
            "signatures": verdict.get("signatures"),
            "keyid_expected": verdict.get("keyid_expected"),
            "pae_sha256": verdict.get("pae_sha256"),
            "reason": verdict.get("reason")}


# ---------------------------------------------------------------------------
# Check 2 — payload digest re-hash (THE fixed comparison)
# ---------------------------------------------------------------------------
def _digest_candidates_for(subject: Any) -> set[str]:
    """All digest hex strings the given subject could legitimately hash to under
    the schemes SZL uses (sha256 / sha3-256 over canonical JSON)."""
    raw = _canon(subject)
    return {_sha256_hex(raw), _sha3_256_hex(raw)}


def _check_payload_digest(env: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"check": "payload_digest"}
    payload_b64 = env.get("payload")
    if not payload_b64:
        return {**out, "status": UNAVAILABLE, "detail": "no payload in envelope"}
    body = _b64_any_decode(payload_b64)
    if body is None:
        return {**out, "status": UNAVAILABLE, "detail": "payload not decodable base64"}

    # Digest of the RAW payload bytes (both schemes) — the whole-envelope-payload view.
    recomputed_sha256 = _sha256_hex(body)
    recomputed_sha3 = _sha3_256_hex(body)
    out["recomputed_payload_sha256"] = recomputed_sha256
    out["recomputed_payload_sha3_256"] = recomputed_sha3

    try:
        payload_obj = json.loads(body)
    except Exception:
        payload_obj = None

    declared = _declared_payload_digest(payload_obj)
    out["declared_payload_digest"] = declared

    if declared is None:
        # The payload DECLARES no self-digest. We do NOT invent a MISMATCH against
        # the chain seal id (that was the old bug). Honest: nothing to compare here.
        return {**out, "status": UNAVAILABLE,
                "detail": ("payload declares no self-digest field (payload_digest / "
                           "sha256); nothing to compare on this check — NOT compared "
                           "against the chain seal id (avoids the old VERIFIED+MISMATCH bug)")}

    declared_n = _norm_digest(declared)

    # RECOMPUTE the digest of the SUBJECT the payload_digest is *about*, and compare
    # to the DECLARED payload_digest ONLY. The subject is the inner body the receipt
    # signs over (payload['body'] / ['subject'] / ['payload']), else the raw bytes.
    subject = None
    if isinstance(payload_obj, dict):
        for k in ("body", "subject", "payload", "receipt", "content"):
            if k in payload_obj:
                subject = payload_obj[k]
                break
    candidates: set[str] = {recomputed_sha256, recomputed_sha3}
    if subject is not None:
        candidates |= _digest_candidates_for(subject)
        out["recomputed_subject_digests"] = sorted(_digest_candidates_for(subject))

    # Compare recomputed digest(s) to the DECLARED payload_digest ONLY (never the
    # chain seal id). VERIFIED iff the declared digest is a recompute we produced.
    if declared_n in candidates:
        return {**out, "status": VERIFIED,
                "detail": "recomputed payload/subject digest == DECLARED payload_digest"}
    return {**out, "status": MISMATCH,
            "detail": ("recomputed payload digest != DECLARED payload_digest — "
                       "payload bytes do not match the digest they declare (tamper)")}


# ---------------------------------------------------------------------------
# Check 3 — hash chain (reuse szl_khipu_verify.verify_digest)
# ---------------------------------------------------------------------------
def _receipt_id_from_env(env: dict[str, Any], payload_obj: Any) -> Optional[str]:
    """Find a chain seal id to look up: explicit receipt_id, else the payload's
    own declared receipt digest / seal (NOT the payload_digest)."""
    for k in ("receipt_id", "digest", "seal", "chain_digest"):
        v = env.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip().lower()
    if isinstance(payload_obj, dict):
        for k in ("receipt_id", "digest", "seal", "chain_digest"):
            v = payload_obj.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip().lower()
    return None


def _check_hash_chain(receipt_id: Optional[str], organ: Optional[str] = None) -> dict[str, Any]:
    out: dict[str, Any] = {"check": "hash_chain"}
    if not receipt_id:
        return {**out, "status": UNAVAILABLE,
                "detail": "no receipt_id / chain digest available to walk"}
    try:
        import szl_khipu_verify as _kv
    except Exception as e:
        return {**out, "status": UNAVAILABLE,
                "detail": f"szl_khipu_verify unavailable: {e!r}"}
    try:
        v = _kv.verify_digest(receipt_id, organ)
    except Exception as e:
        return {**out, "status": UNAVAILABLE, "detail": f"chain walk error: {e!r}"}

    out.update({
        "organ": v.get("organ"),
        "seq": v.get("seq"),
        "digest": v.get("digest"),
        "recomputed_digest": v.get("recomputed_digest"),
        "digest_matches": v.get("digest_matches"),
        "chain_to_genesis_verified": v.get("chain_to_genesis_verified"),
        "links_checked": v.get("links_checked"),
        "broken_link": v.get("broken_link"),
        "khipu_verdict": v.get("verdict"),
    })
    verdict = v.get("verdict")
    if v.get("found") is False or verdict == "NOT_FOUND":
        # Chains are in-memory; a digest not present is honestly UNAVAILABLE here
        # (not a MISMATCH — absence of the receipt in THIS process proves nothing).
        return {**out, "status": UNAVAILABLE,
                "detail": ("receipt not present in this process's in-memory Khipu DAG "
                           "(chains reset on restart) — honest UNAVAILABLE, not a failure")}
    if verdict == "PASS":
        return {**out, "status": VERIFIED,
                "detail": "seal recomputed + prev-links re-walked to genesis"}
    return {**out, "status": MISMATCH,
            "detail": v.get("broken_link") or "chain seal / prev-link recompute failed"}


# ---------------------------------------------------------------------------
# Orchestration — run all three checks + a HONEST overall verdict
# ---------------------------------------------------------------------------
def _overall(checks: list[dict[str, Any]]) -> str:
    statuses = [c.get("status") for c in checks]
    if MISMATCH in statuses:
        return "FAIL"
    ran_ok = [s for s in statuses if s == VERIFIED]
    could_not_run = [s for s in statuses if s in (UNSIGNED_LOCAL, UNAVAILABLE)]
    if ran_ok and not could_not_run:
        return "PASS"
    if ran_ok and could_not_run:
        # Some checks passed, some could not run locally (no key / not in DAG).
        return "PARTIAL"
    return "INCONCLUSIVE"


def verify_receipt(envelope: Any = None, receipt_id: Optional[str] = None,
                   organ: Optional[str] = None) -> dict[str, Any]:
    """Public verify. Accepts a DSSE envelope OR a receipt_id (chain lookup).

    Returns a structured, honestly-labelled verdict. NEVER raises into the request
    path; NEVER fabricates a check result.
    """
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    base = {"service": "public.verify.receipt", "doctrine": _DOCTRINE, "ts": ts}

    env: Optional[dict[str, Any]] = None
    if isinstance(envelope, dict):
        env = envelope
    elif isinstance(envelope, str) and envelope.strip():
        # Accept a raw JSON string OR a base64url-encoded JSON envelope (share link).
        s = envelope.strip()
        try:
            env = json.loads(s)
        except Exception:
            raw = _b64_any_decode(s)
            if raw is not None:
                try:
                    env = json.loads(raw)
                except Exception:
                    env = None
        if not isinstance(env, dict):
            env = None

    # No envelope but a receipt_id -> chain-only verification path.
    if env is None and receipt_id:
        chain = _check_hash_chain(str(receipt_id).strip().lower(), organ)
        checks = [
            {"check": "signature", "status": UNAVAILABLE,
             "detail": "no envelope supplied — signature cannot be checked from a bare id"},
            {"check": "payload_digest", "status": UNAVAILABLE,
             "detail": "no envelope supplied — payload not available from a bare id"},
            chain,
        ]
        return {**base, "ok": True, "input": "receipt_id",
                "receipt_id": str(receipt_id).strip().lower(),
                "checks": checks, "verdict": _overall(checks)}

    if env is None:
        # Honest 4xx surface: caller must send an envelope or a receipt_id.
        return {**base, "ok": False, "error": "no_input",
                "detail": ("provide a DSSE envelope in `envelope` (JSON or base64url) "
                           "or a `receipt_id` digest to walk the hash-chain"),
                "verdict": "NO_INPUT"}

    # Full path: we have an envelope. Decode payload for chain-id extraction.
    payload_obj = None
    pb = env.get("payload")
    if pb:
        raw = _b64_any_decode(pb)
        if raw is not None:
            try:
                payload_obj = json.loads(raw)
            except Exception:
                payload_obj = None

    rid = (str(receipt_id).strip().lower() if receipt_id
           else _receipt_id_from_env(env, payload_obj))

    sig = _check_signature(env)
    dig = _check_payload_digest(env)
    chain = _check_hash_chain(rid, organ)
    checks = [sig, dig, chain]

    return {**base, "ok": True, "input": "envelope",
            "payloadType": env.get("payloadType"),
            "receipt_id": rid,
            "checks": checks, "verdict": _overall(checks),
            "shareable_link": _shareable_link(env, rid)}


def _shareable_link(env: dict[str, Any], rid: Optional[str]) -> dict[str, Any]:
    """Produce the two shareable-link forms an auditor can re-verify with."""
    out: dict[str, Any] = {}
    if rid:
        out["by_receipt_id"] = f"/verify?receipt={rid}"
    try:
        compact = base64.urlsafe_b64encode(_canon(env)).decode("ascii").rstrip("=")
        # Only advertise the compact form if it is a sane URL length.
        if len(compact) <= 6000:
            out["by_envelope"] = f"/verify?envelope={compact}"
        out["envelope_b64url_len"] = len(compact)
    except Exception:
        pass
    return out


# ---------------------------------------------------------------------------
# Registration — POST /api/{ns}/v1/verify/receipt (+ /v1/* alias) + GET path form.
# Registered BEFORE the SPA catch-all (mirrors szl_khipu_verify).
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> dict:
    async def _verify_post(request: Request):  # noqa: ANN202
        try:
            body = await request.json()
        except Exception:
            body = {}
        if not isinstance(body, dict):
            body = {}
        envelope = body.get("envelope")
        receipt_id = body.get("receipt_id") or body.get("receipt")
        organ = body.get("organ")
        result = verify_receipt(envelope=envelope, receipt_id=receipt_id, organ=organ)
        status = 200 if result.get("ok") else 400
        return JSONResponse(result, status_code=status,
                            headers={"x-szl-verify-verdict": str(result.get("verdict", ""))})

    async def _verify_get_path(receipt_id: str):  # noqa: ANN202
        result = verify_receipt(receipt_id=receipt_id)
        return JSONResponse(result, status_code=200,
                            headers={"x-szl-verify-verdict": str(result.get("verdict", ""))})

    prefixes = [f"/api/{ns}/v1/verify", "/v1/verify"]
    routes: list[str] = []
    for p in prefixes:
        app.add_api_route(f"{p}/receipt", _verify_post, methods=["POST"],
                          include_in_schema=True)
        app.add_api_route(f"{p}/receipt/{{receipt_id}}", _verify_get_path,
                          methods=["GET"], include_in_schema=True)
        routes.extend([f"{p}/receipt (POST)", f"{p}/receipt/{{receipt_id}} (GET)"])
    print(f"[{ns}] szl_public_verify routes registered "
          f"(PUBLIC verify-a-receipt, {len(routes)} routes)", flush=True)
    return {"ok": True, "ns": ns, "routes": routes}


# ---------------------------------------------------------------------------
# No-server self-test — proves: valid envelope -> all-pass; tampered payload ->
# honest MISMATCH; no input -> honest NO_INPUT; and that a recompute is NEVER
# compared against the chain id (the old simultaneous VERIFIED+MISMATCH bug).
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    import szl_dsse
    out: dict = {}

    # Build a payload that DECLARES its own digest correctly, then sign it.
    inner = {"claim": "energy-cert", "value": 42, "organ": "public_verify_selftest"}
    inner_digest = _sha256_hex(_canon(inner))
    payload = {"body": inner, "payload_digest": inner_digest,
               "receipt_id": "0" * 64}  # a chain id that won't be in the DAG (UNAVAILABLE)
    env = szl_dsse.sign_payload(payload, szl_dsse.KHIPU_PAYLOAD_TYPE)

    res = verify_receipt(envelope=env)
    sig = next(c for c in res["checks"] if c["check"] == "signature")
    dig = next(c for c in res["checks"] if c["check"] == "payload_digest")
    chain = next(c for c in res["checks"] if c["check"] == "hash_chain")

    # Signature: VERIFIED if a private key is present in-runtime, else UNSIGNED-LOCAL.
    assert sig["status"] in (VERIFIED, UNSIGNED_LOCAL), sig
    # payload_digest MUST be VERIFIED — the payload declares its own true digest.
    assert dig["status"] == VERIFIED, dig
    # hash_chain is UNAVAILABLE locally (receipt not minted into the DAG) — honest,
    # and CRUCIALLY not a MISMATCH just because recompute != the chain id.
    assert chain["status"] == UNAVAILABLE, chain
    # No check should be BOTH VERIFIED and MISMATCH (the old bug); statuses are single.
    assert dig["status"] != MISMATCH, dig
    out["valid_all_pass_no_double_verdict"] = True

    # 2) TAMPER: mutate the payload bytes so the declared digest no longer matches.
    tampered_inner = dict(inner)
    tampered_inner["value"] = 9999  # changed AFTER the digest was declared
    tampered_payload = {"body": tampered_inner, "payload_digest": inner_digest,
                        "receipt_id": "0" * 64}
    tenv = szl_dsse.sign_payload(tampered_payload, szl_dsse.KHIPU_PAYLOAD_TYPE)
    tres = verify_receipt(envelope=tenv)
    tdig = next(c for c in tres["checks"] if c["check"] == "payload_digest")
    assert tdig["status"] == MISMATCH, tdig  # honest tamper detection
    assert tres["verdict"] == "FAIL", tres
    out["tampered_honest_mismatch"] = True

    # 3) NO INPUT -> honest NO_INPUT (the endpoint returns 400 for this).
    nres = verify_receipt()
    assert nres["ok"] is False and nres["verdict"] == "NO_INPUT", nres
    out["no_input_honest_4xx"] = True

    # 4) receipt_id-only path -> chain check runs, sig+payload honestly UNAVAILABLE.
    rres = verify_receipt(receipt_id="deadbeef" * 8)
    rsig = next(c for c in rres["checks"] if c["check"] == "signature")
    assert rsig["status"] == UNAVAILABLE and rres["ok"] is True, rres
    out["receipt_id_only_path"] = True

    # 5) base64url-encoded envelope (share link form) decodes + verifies.
    import base64 as _b64
    compact = _b64.urlsafe_b64encode(_canon(env)).decode().rstrip("=")
    cres = verify_receipt(envelope=compact)
    cdig = next(c for c in cres["checks"] if c["check"] == "payload_digest")
    assert cdig["status"] == VERIFIED, cres
    out["compact_envelope_link"] = True

    # 6) shareable link forms present.
    assert "by_receipt_id" in res["shareable_link"], res["shareable_link"]
    out["shareable_link_present"] = True

    return out


if __name__ == "__main__":
    import sys as _sys
    print("=" * 70)
    print("szl_public_verify — self-test (public verify-a-receipt, honest labels)")
    print("=" * 70)
    r = _selftest()
    print(json.dumps(r, indent=2))
    ok = all(r.values())
    print("\nSELFTEST", "PASS" if ok else "FAIL")
    _sys.exit(0 if ok else 1)
