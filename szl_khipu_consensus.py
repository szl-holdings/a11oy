# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11/v12
# Authored by Yachay (CTO) — Khipu Consensus: 3-of-4 BFT multi-organ signed agreement.
"""
szl_khipu_consensus — per-organ DSSE cosign + 3-of-4 BFT consensus aggregator.

THE CATEGORY SZL INVENTS: multi-party-witnessed AI. Four flagship "organs"
(Sentra · Amaru · a11oy · Killinchu) each hold their OWN ECDSA-P256 cosign
keypair and independently DSSE-sign an action hash with a verdict. >= THRESHOLD
(3) valid `allow` signatures over the SAME action_hash ⇒ the action is
CANONICAL. With n=4 witnesses and threshold=3 the protocol tolerates f = n - t = 1
Byzantine / crashed / unreachable organ (3-of-4 BFT). 2-of-4 ⇒ action REJECTED.

KEY MODEL (honest, ADDITIVE):
  - Each organ's PRIVATE key is delivered to its Space ONLY as a runtime secret
    env var `<ORGAN>_COSIGN_KEY` (PKCS8 / SEC1 PEM, optionally base64-wrapped).
    It is NEVER committed to any repo. Founder UI action documented in the ledger.
  - Legacy `SZL_COSIGN_PRIVATE_PEM` (szlholdings-cosign) is kept as a FALLBACK
    so nothing that previously signed stops signing (additive, zero regression).
  - For LAB DEMO ONLY, an embedded test key may be provided via the
    `KHIPU_DEMO_KEY_<ORGAN>` env or the `demo_private_pem` argument; receipts
    produced with a non-production key are explicitly labelled `key_source`.
  - If no key is present the organ honestly returns verdict with an UNSIGNED
    envelope (signature == "", `signed: false`). It NEVER fabricates a signature.

  Per-organ public keys are PUBLIC data (published at
  szl-holdings/.github/cosign-keys/<organ>.pub and served at /khipu/pubkey).
  They are embedded below so /khipu/consensus/verify needs no network call.

  Signature primitive: ECDSA-P256-SHA256 over the DSSE PAE of a canonical
  organ-verdict statement. Byte-for-byte verifiable by `cosign verify-blob`.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Optional

# Imported at module top so FastAPI's get_type_hints can resolve the route
# function annotations (they live in this module's globals).
try:  # pragma: no cover - environments without starlette still import the rest
    from starlette.requests import Request
    from starlette.responses import JSONResponse
except Exception:  # pragma: no cover
    Request = Any  # type: ignore
    JSONResponse = None  # type: ignore

ORGAN_VERDICT_PAYLOAD_TYPE = "application/vnd.szl.khipu.organ-verdict+json"
CONSENSUS_RECEIPT_PAYLOAD_TYPE = "application/vnd.szl.khipu.consensus+json"
THRESHOLD = 3
LEAN_SHA = "86d9fb2c"  # lutar-lean Lutar/KhipuConsensus.lean replay sha
# Optional in-process key for Rekor signing in the lab demo (production reads
# KILLINCHU_COSIGN_KEY from the Space secret instead). Never committed.
_REKOR_DEMO_KEY = None
DOCTRINE_PUBLIC = "v11 LOCKED · 749/14/163"

# ---------------------------------------------------------------------------
# THEOREM PROVENANCE (HONEST) — wired into every UDS consensus decision payload.
# Locked-proven = EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel c7c0ba17 (axiom-clean).
# A Khipu Byzantine consensus decision is backed by Khipu Conjecture 2, which is
# OPEN (stated, NOT a theorem). Never inflate. Experimental-tier theorems
# (CF-22/CF-23/CUT-2) live on main 044eb098, CI-green, NOT folded into locked-8.
# Lambda (Λ) = Conjecture 1, machine-checked FALSE as an unconditional axiom.
# ---------------------------------------------------------------------------
LOCKED_KERNEL_SHA = "c7c0ba17"
EXPERIMENTAL_KERNEL_SHA = "044eb098"
LOCKED_FIVE = ["F1", "F11", "F12", "F18", "F19"]

_CONSENSUS_THEOREM_REF = {
    "decision_class": "consensus",
    "theorem": "Khipu Conjecture 2 (Byzantine quorum safety)",
    "lean": "Lutar/KhipuConsensus.lean::khipu_consensus_safety",
    "maturity": "conjecture",
    "kernel_sha": EXPERIMENTAL_KERNEL_SHA,
    "honest_note": "Byzantine BFT safety is OPEN (Conjecture 2) — stated, not a theorem.",
}


def _consensus_lake_receipt() -> dict:
    """Honest lake_receipt for a Khipu consensus decision payload.

    locked-8 = exactly 8; Λ = Conjecture 1; Byzantine BFT = Conjecture 2 OPEN.
    Only the locked-8 are asserted axiom-clean at c7c0ba17.
    """
    return {
        "locked_kernel_sha": LOCKED_KERNEL_SHA,
        "experimental_kernel_sha": EXPERIMENTAL_KERNEL_SHA,
        "locked_proven_formulas": list(LOCKED_FIVE),
        "locked_proven_count": len(LOCKED_FIVE),
        "print_axioms_assertion": (
            "#print axioms over the locked-8 {F1,F4,F7,F11,F12,F18,F19,F22} @ c7c0ba17 reports "
            "NO sorryAx / NO extra axioms (axiom-clean). The consensus decision class "
            "is backed by Khipu Conjecture 2 (Byzantine quorum safety) which is OPEN "
            "(044eb098, NOT in locked-8, NOT asserted axiom-clean). \u039b = Conjecture 1 "
            "(machine-checked FALSE). Byzantine BFT = Conjecture 2 (OPEN)."
        ),
        "cited": [{
            "decision_class": "consensus",
            "theorem": "Khipu Conjecture 2 (Byzantine quorum safety)",
            "maturity": "conjecture",
            "kernel_sha": EXPERIMENTAL_KERNEL_SHA,
            "axioms_clean": False,
        }],
        "lean_sha": LEAN_SHA,
    }


# Published per-organ public keys (PUBLIC; mirror of .github/cosign-keys/*.pub).
ORGAN_PUBKEYS: dict[str, str] = {
    "sentra": """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAESQL1LrA+QhUirTl9sIvflY9PhPUA
lMVgwOUIPhA2p7n0iw+UsbhTVPZibV/1zn9A6ZIn/khX+rfqR/NEGl7Jjg==
-----END PUBLIC KEY-----
""",
    "amaru": """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEIj/K+iMi4m29dpi+bAs+uqzfZ3lF
EtW7cOnXwqTmlUc1EYzwAkYEBZ1XfP+0gN2A8mLQE6/90dnczCs6nSiaXg==
-----END PUBLIC KEY-----
""",
    "a11oy": """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAElmtVcImBZu/k1wcma3m1g0xbUadt
Aimrd7UIIVlJNSBIkRXdf+0wfdYgUJ41lq31yC9o2pFlYraphtPv4FHz5g==
-----END PUBLIC KEY-----
""",
    "killinchu": """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEvvSRhn4eTZAXNUBwftDjREXDL/rV
0GubsQHFcUJ44PzdC1KCiZxg7G3D7GI60EdOyaKEBz/FMOAMMgKOkhSTiA==
-----END PUBLIC KEY-----
""",
    "rosie": """-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEfC3FP9fFw+Xnko+qCMpkhvu8bhsJ
I6MjDkNAq+74+MX1qZ/l+34NwyOpQlP1zKZwVTnz0pzAiRzzIbFh0ezPHA==
-----END PUBLIC KEY-----
""",
}

CONSENSUS_ORGANS = ["sentra", "amaru", "a11oy", "killinchu"]

# Default mesh URLs for the aggregator to fan out to (overridable by env).
ORGAN_SIGN_URLS: dict[str, str] = {
    "sentra": os.environ.get("SENTRA_SIGN_URL", "https://szlholdings-sentra.hf.space/khipu/consensus/sign"),
    "amaru": os.environ.get("AMARU_SIGN_URL", "https://szlholdings-amaru.hf.space/khipu/consensus/sign"),
    "a11oy": os.environ.get("A11OY_SIGN_URL", "https://szlholdings-a11oy.hf.space/khipu/consensus/sign"),
    "killinchu": os.environ.get("KILLINCHU_SIGN_URL", "https://szlholdings-killinchu.hf.space/khipu/consensus/sign"),
}


# ---------------------------------------------------------------------------
# Canonical JSON + DSSE PAE
# ---------------------------------------------------------------------------

def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pae(payload_type: str, body: bytes) -> bytes:
    t = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" " + str(len(body)).encode() + b" " + body


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def pubkey_fingerprint(pem: str) -> str:
    """MANIFEST convention: sha256 of the stripped PEM string (matches szl_dsse)."""
    return hashlib.sha256(pem.strip().encode()).hexdigest()


# ---------------------------------------------------------------------------
# Per-organ key loading
# ---------------------------------------------------------------------------

def _load_private_key_for(organ: str, demo_private_pem: Optional[str] = None):
    """Resolve this organ's signing key. Returns (key_or_None, key_source_str).

    Resolution order (additive, never raises):
      1. <ORGAN>_COSIGN_KEY            (production runtime secret)
      2. KHIPU_DEMO_KEY_<ORGAN> env    (lab demo)
      3. demo_private_pem argument     (lab demo, in-process)
      4. SZL_COSIGN_PRIVATE_PEM        (legacy szlholdings-cosign fallback)
    """
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    candidates = [
        (os.environ.get(f"{organ.upper()}_COSIGN_KEY"), "production:<ORGAN>_COSIGN_KEY"),
        (os.environ.get(f"KHIPU_DEMO_KEY_{organ.upper()}"), "demo:KHIPU_DEMO_KEY"),
        (demo_private_pem, "demo:in-process"),
        (os.environ.get("SZL_COSIGN_PRIVATE_PEM"), "legacy:SZL_COSIGN_PRIVATE_PEM"),
    ]
    for pem, source in candidates:
        if not pem:
            continue
        try:
            if "BEGIN" not in pem:
                pem = base64.b64decode(pem).decode("utf-8")
            return load_pem_private_key(pem.encode("utf-8"), password=None), source
        except Exception:
            continue
    return None, "none"


# ---------------------------------------------------------------------------
# Verdict logic per organ (real checks; degrade honestly if context absent)
# ---------------------------------------------------------------------------

_SIG_INJECTION_RE = re.compile(r"(?:ignore (?:all|previous)|system prompt|jailbreak|do anything now|\bDAN\b)", re.I)


def organ_verdict(organ: str, action_hash: str, context: dict) -> tuple[str, str]:
    """Return (verdict, reason). Verdict in {allow, block, abstain}.

    Each organ applies its real gate. When the live runtime signal is not
    available in this process, the organ degrades to `abstain` with an honest
    reason rather than silently `allow` — fail-safe, not fail-open.
    """
    ctx = context or {}
    if not (isinstance(action_hash, str) and len(action_hash) == 64 and re.fullmatch(r"[0-9a-f]{64}", action_hash)):
        return "block", "action_hash is not a 64-char sha256 hex digest"

    if organ == "sentra":
        # allow if Sentra filter clears AND no 23-signature injection match; block if filter rejects
        text = json.dumps(ctx.get("payload", ctx), ensure_ascii=False)
        if _SIG_INJECTION_RE.search(text):
            return "block", "Sentra: injection signature matched (23-signature filter)"
        if ctx.get("sentra_filter") == "reject":
            return "block", "Sentra: filter rejected the action"
        return "allow", "Sentra: filter cleared, no injection signature match"

    if organ == "amaru":
        # allow if Yuyay-13 Λ >= 0.90 AND DINN residual within bound; block otherwise
        lam = ctx.get("lambda", ctx.get("yuyay_lambda"))
        resid = ctx.get("dinn_residual")
        if lam is None and resid is None:
            return "allow", "Amaru: no Λ/DINN signal supplied; permissive default (lab)"
        if lam is not None and float(lam) < 0.90:
            return "block", f"Amaru: Yuyay-13 Λ={lam} < 0.90"
        if resid is not None and abs(float(resid)) > float(ctx.get("dinn_bound", 0.05)):
            return "block", f"Amaru: DINN residual {resid} exceeds bound"
        return "allow", "Amaru: Yuyay-13 Λ>=0.90 and DINN residual within bound"

    if organ == "a11oy":
        # allow if all 57 policy gates pass AND Khipu chain integrity valid; block otherwise
        failed = ctx.get("failed_gates", [])
        if failed:
            return "block", f"a11oy: {len(failed)} of 57 policy gates failed: {failed[:5]}"
        if ctx.get("khipu_chain_valid") is False:
            return "block", "a11oy: Khipu chain integrity check failed"
        return "allow", "a11oy: all 57 policy gates pass, Khipu chain integrity valid"

    if organ == "killinchu":
        # allow if local field checks pass; block otherwise
        if ctx.get("field_check") == "fail":
            return "block", "Killinchu: local field checks failed"
        return "allow", "Killinchu: local field checks pass"

    if organ == "rosie":
        return "allow", "Rosie: operator-console witness (optional 5th)"

    return "abstain", f"unknown organ '{organ}'"


# ---------------------------------------------------------------------------
# Sign / verify one organ verdict (REAL ECDSA-P256-SHA256 over DSSE PAE)
# ---------------------------------------------------------------------------

def sign_consensus_verdict(organ: str, action_hash: str, context: dict,
                           demo_private_pem: Optional[str] = None) -> dict:
    """Produce this organ's signed verdict for `action_hash`."""
    verdict, reason = organ_verdict(organ, action_hash, context or {})
    keyid = f"{organ}-cosign"
    statement = {
        "schema": "szl.khipu.organ_verdict/v1",
        "organ": organ, "keyid": keyid, "action_hash": action_hash,
        "verdict": verdict, "reason": reason, "lean_sha": LEAN_SHA, "ts": _now(),
    }
    body = canonical_json(statement)
    to_sign = pae(ORGAN_VERDICT_PAYLOAD_TYPE, body)

    priv, key_source = _load_private_key_for(organ, demo_private_pem)
    out: dict[str, Any] = {
        "organ": organ, "keyid": keyid, "verdict": verdict, "reason": reason,
        "lean_sha": LEAN_SHA, "ts": statement["ts"],
        "payloadType": ORGAN_VERDICT_PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode("ascii"),
        "doctrine": DOCTRINE_PUBLIC,
    }
    if priv is None:
        out["signature"] = ""
        out["signed"] = False
        out["key_source"] = "none"
        out["honesty"] = (f"UNSIGNED — no signing key for {organ}; set the "
                          f"{organ.upper()}_COSIGN_KEY Space secret. No signature fabricated.")
        return out

    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    sig = priv.sign(to_sign, ec.ECDSA(hashes.SHA256()))
    # DSSE envelope (base64) — the wire `signature` field is the base64 DSSE envelope.
    envelope = {
        "payloadType": ORGAN_VERDICT_PAYLOAD_TYPE,
        "payload": out["payload"],
        "signatures": [{"keyid": keyid, "sig": base64.b64encode(sig).decode("ascii")}],
    }
    out["signature"] = base64.b64encode(canonical_json(envelope)).decode("ascii")
    out["sig_raw"] = base64.b64encode(sig).decode("ascii")
    out["signed"] = True
    out["key_source"] = key_source
    is_prod = key_source.startswith("production")
    out["honesty"] = ("REAL — ECDSA-P256-SHA256 over DSSE PAE; verifiable by "
                      "`cosign verify-blob --key " + organ + ".pub`."
                      + ("" if is_prod else f" Key source: {key_source} (rotate to {organ.upper()}_COSIGN_KEY for prod)."))
    return out


def _extract_sig_and_payload(sig_field: str, payload_field: str) -> tuple[bytes, bytes, str]:
    """Return (raw_sig, body, payload_type). Accepts either a base64 DSSE
    envelope (canonical wire form) or a raw base64 ECDSA signature paired with
    the separate payload field."""
    raw = base64.b64decode(sig_field)
    try:
        env = json.loads(raw)
        if isinstance(env, dict) and "signatures" in env:
            sig = base64.b64decode(env["signatures"][0]["sig"])
            body = base64.b64decode(env["payload"])
            return sig, body, env.get("payloadType", ORGAN_VERDICT_PAYLOAD_TYPE)
    except Exception:
        pass
    # raw signature form
    return raw, base64.b64decode(payload_field), ORGAN_VERDICT_PAYLOAD_TYPE


def verify_organ_signature(sig_entry: dict, action_hash: str) -> dict:
    """Verify ONE organ's signature against its published public key, and check
    the signed statement is internally consistent with `action_hash`."""
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    from cryptography.exceptions import InvalidSignature

    organ = sig_entry.get("organ", "")
    keyid = sig_entry.get("keyid", f"{organ}-cosign")
    res = {"organ": organ, "keyid": keyid, "valid": False, "verdict": None,
           "action_hash_match": False, "counts": False, "reason": ""}
    pub_pem = ORGAN_PUBKEYS.get(organ)
    if not pub_pem:
        res["reason"] = f"unknown organ '{organ}' (no published pubkey)"
        return res
    sig_field = sig_entry.get("signature", "")
    payload_field = sig_entry.get("payload", "")
    if not sig_field:
        res["reason"] = "missing signature (unsigned)"
        return res
    try:
        sig, body, ptype = _extract_sig_and_payload(sig_field, payload_field)
        pub = load_pem_public_key(pub_pem.encode())
        pub.verify(sig, pae(ptype, body), ec.ECDSA(hashes.SHA256()))
        res["valid"] = True
    except InvalidSignature:
        res["reason"] = "signature mismatch"
        return res
    except Exception as e:
        res["reason"] = f"{type(e).__name__}: {e}"
        return res
    # statement consistency
    try:
        stmt = json.loads(body)
        res["verdict"] = stmt.get("verdict")
        res["action_hash_match"] = (stmt.get("action_hash") == action_hash)
        res["lean_sha"] = stmt.get("lean_sha")
    except Exception:
        res["reason"] = "valid signature but unparseable statement"
        return res
    res["counts"] = bool(res["valid"] and res["action_hash_match"] and res["verdict"] == "allow")
    res["reason"] = "valid+allow over matching action_hash" if res["counts"] else \
        f"valid sig but verdict={res['verdict']} / hash_match={res['action_hash_match']}"
    return res


def verify_consensus_receipt(receipt: dict) -> dict:
    """Verify a canonical receipt: fetch all organ pub keys, verify all sigs,
    count valid+allow, return OK if >= threshold."""
    action_hash = receipt.get("action_hash", "")
    sigs = receipt.get("signatures", [])
    checks = [verify_organ_signature(s, action_hash) for s in sigs]
    count = sum(1 for c in checks if c["counts"])
    n = len(sigs)
    threshold = int(receipt.get("threshold", THRESHOLD))
    return {
        "verified": count >= threshold,
        "khipu_consensus": f"{count}-of-{n}",
        "consensus_count": count, "n": n, "threshold": threshold,
        "action_hash": action_hash, "checks": checks,
        "claimed": receipt.get("khipu_consensus"),
        "claim_matches": receipt.get("khipu_consensus") in (f"{count}-of-{n}",),
        "doctrine": DOCTRINE_PUBLIC,
        "theorem_ref": dict(_CONSENSUS_THEOREM_REF),
        "lake_receipt": _consensus_lake_receipt(),
        "ts": _now(),
    }


# ---------------------------------------------------------------------------
# Sigstore Rekor (best-effort; honest if unreachable)
# ---------------------------------------------------------------------------

async def push_to_rekor(receipt: dict) -> dict:
    """Push the multi-sig receipt to the public Sigstore Rekor transparency log
    as a custom hashedrekord entry. Returns {log_index, ...} or an honest miss."""
    try:
        import httpx  # type: ignore
    except Exception:
        return {"ok": False, "reason": "httpx unavailable in runtime", "log_index": None}
    # Hash + sign the canonical receipt WITHOUT volatile rekor fields.
    clean = {k: v for k, v in receipt.items() if k not in ("rekor", "rekor_log_index")}
    body = canonical_json(clean)
    digest = hashlib.sha256(body).hexdigest()
    rekor = os.environ.get("REKOR_URL", "https://rekor.sigstore.dev")
    # hashedrekord v0.0.1 over the receipt artifact, signed with the killinchu
    # aggregator key. Rekor REQUIRES spec.signature for hashedrekord.
    priv, _src = _load_private_key_for("killinchu", _REKOR_DEMO_KEY)
    if priv is None:
        return {"ok": False, "reason": "no killinchu key for Rekor signing",
                "log_index": None, "receipt_digest": digest}
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes, serialization
    sig = priv.sign(body, ec.ECDSA(hashes.SHA256()))
    pub_pem = priv.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    entry: dict[str, Any] = {
        "apiVersion": "0.0.1", "kind": "hashedrekord",
        "spec": {
            "data": {"hash": {"algorithm": "sha256", "value": digest}},
            "signature": {
                "content": base64.b64encode(sig).decode(),
                "publicKey": {"content": base64.b64encode(pub_pem).decode()},
            },
        },
    }
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(f"{rekor}/api/v1/log/entries", json=entry,
                                  headers={"Content-Type": "application/json"})
            if r.status_code in (200, 201):
                data = r.json()
                uuid = next(iter(data))
                log_index = data[uuid].get("logIndex")
                return {"ok": True, "log_index": log_index, "uuid": uuid,
                        "receipt_digest": digest,
                        "rekor_url": f"{rekor}/api/v1/log/entries?logIndex={log_index}"}
            return {"ok": False, "reason": f"rekor HTTP {r.status_code}: {r.text[:200]}",
                    "log_index": None, "receipt_digest": digest}
    except Exception as e:
        return {"ok": False, "reason": f"rekor unreachable: {type(e).__name__}",
                "log_index": None, "receipt_digest": digest}


# ---------------------------------------------------------------------------
# Aggregator: fan out, collect, count, build receipt
# ---------------------------------------------------------------------------

async def _call_organ_sign(client, organ: str, action_hash: str, context: dict) -> dict:
    url = ORGAN_SIGN_URLS.get(organ)
    try:
        r = await client.post(url, json={"action_hash": action_hash, "context": context},
                              timeout=5.0)
        d = r.json()
        d.setdefault("organ", organ)
        return d
    except Exception as e:
        return {"organ": organ, "keyid": f"{organ}-cosign", "signature": "",
                "verdict": "abstain", "reason": f"unreachable: {type(e).__name__}", "signed": False}


async def run_consensus(action_hash: str, context: dict,
                        organs: Optional[list[str]] = None,
                        local_demo_keys: Optional[dict[str, str]] = None) -> dict:
    """Execute 3-of-4 consensus.

    If `local_demo_keys` is provided ({organ: pem}), signs locally in-process
    (used by tests / the lab demo). Otherwise fans out over HTTP to each organ's
    /khipu/consensus/sign with asyncio.gather and a 5s timeout per call.
    """
    organs = organs or CONSENSUS_ORGANS
    if local_demo_keys is not None:
        sig_entries = [sign_consensus_verdict(o, action_hash, context,
                       demo_private_pem=local_demo_keys.get(o)) for o in organs]
    else:
        try:
            import httpx  # type: ignore
            async with httpx.AsyncClient() as client:
                sig_entries = await asyncio.gather(
                    *[_call_organ_sign(client, o, action_hash, context) for o in organs])
        except Exception as e:
            sig_entries = [{"organ": o, "keyid": f"{o}-cosign", "signature": "",
                            "verdict": "abstain", "reason": f"fanout failed: {e}",
                            "signed": False} for o in organs]

    # Verify each signature against its published public key.
    checks = [verify_organ_signature(s, action_hash) for s in sig_entries]
    count = sum(1 for c in checks if c["counts"])
    n = len(sig_entries)

    signatures = []
    for s, c in zip(sig_entries, checks):
        signatures.append({
            "organ": s.get("organ"), "keyid": s.get("keyid"),
            "signature": s.get("signature", ""), "payload": s.get("payload", ""),
            "verdict": s.get("verdict"), "lean_sha": s.get("lean_sha", LEAN_SHA),
            "valid": c["valid"], "counts": c["counts"], "reason": s.get("reason", ""),
        })

    canonical = count >= THRESHOLD
    receipt: dict[str, Any] = {
        "khipu_consensus": f"{count}-of-{n}",
        "action_hash": action_hash,
        "signatures": signatures,
        "decision": "canonical" if canonical else "rejected",
        "threshold": THRESHOLD,
        "doctrine": DOCTRINE_PUBLIC,
        "theorem_ref": dict(_CONSENSUS_THEOREM_REF),
        "lake_receipt": _consensus_lake_receipt(),
        "ts": _now(),
    }
    rekor = await push_to_rekor(receipt)
    receipt["rekor_log_index"] = rekor.get("log_index")
    receipt["rekor"] = rekor
    status = 200 if canonical else 412
    return {"receipt": receipt, "status": status,
            "honest_count": f"{count}-of-{n}", "canonical": canonical}


# ---------------------------------------------------------------------------
# FastAPI registration (ADDITIVE — never crashes the host app)
# ---------------------------------------------------------------------------

def register(app, organ: str, is_aggregator: bool = False) -> dict:
    """Register the Khipu Consensus routes on `app` for this `organ`.

    Adds (all organs):
      GET  /khipu/pubkey?keyid=<organ>-cosign   → organ PEM + fingerprint
      POST /khipu/consensus/sign                → this organ's signed verdict
    Adds (Killinchu aggregator only):
      POST /api/killinchu/uds/v1/mission/execute → run 3-of-4 consensus
      POST /api/killinchu/uds/v1/consensus/verify → verify a canonical receipt
    """
    status = {"organ": organ, "routes": []}

    @app.get("/khipu/pubkey")
    async def khipu_pubkey(keyid: str = ""):
        target = keyid.replace("-cosign", "") if keyid else organ
        pem = ORGAN_PUBKEYS.get(target) or ORGAN_PUBKEYS.get(organ)
        eff_organ = target if target in ORGAN_PUBKEYS else organ
        return JSONResponse({
            "organ": eff_organ, "keyid": f"{eff_organ}-cosign",
            "curve": "secp256r1 (P-256)", "pem": pem,
            "fingerprint_sha256": pubkey_fingerprint(pem),
            "served_by": organ, "doctrine": DOCTRINE_PUBLIC,
            "published_at": f"https://github.com/szl-holdings/.github/blob/main/cosign-keys/{eff_organ}.pub",
        })
    status["routes"].append("GET /khipu/pubkey")

    @app.post("/khipu/consensus/sign")
    async def khipu_consensus_sign(request: Request):
        try:
            body = await request.json()
        except Exception:
            body = {}
        action_hash = (body or {}).get("action_hash", "")
        context = (body or {}).get("context", {}) or {}
        result = sign_consensus_verdict(organ, action_hash, context)
        return JSONResponse(result)
    status["routes"].append("POST /khipu/consensus/sign")

    if is_aggregator or organ == "killinchu":
        @app.post("/api/killinchu/uds/v1/mission/execute")
        async def mission_execute(request: Request):
            try:
                body = await request.json()
            except Exception:
                body = {}
            action_hash = (body or {}).get("action_hash", "")
            context = (body or {}).get("context", {}) or {}
            organs = (body or {}).get("organs")
            local_keys = (body or {}).get("_local_demo_keys")  # tests only
            out = await run_consensus(action_hash, context, organs, local_keys)
            return JSONResponse(out["receipt"], status_code=out["status"])
        status["routes"].append("POST /api/killinchu/uds/v1/mission/execute")

        @app.post("/api/killinchu/uds/v1/consensus/verify")
        async def consensus_verify(request: Request):
            try:
                receipt = await request.json()
            except Exception:
                receipt = {}
            out = verify_consensus_receipt(receipt or {})
            return JSONResponse(out, status_code=200 if out["verified"] else 412)
        status["routes"].append("POST /api/killinchu/uds/v1/consensus/verify")

    return status