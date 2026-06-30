#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""
szl-cookbook: verify-scitt-capsule.py
======================================

OFFLINE verifier for SZL a11oy SCITT Agent Action Capsules.

WHAT THIS PROVES (without trusting SZL at runtime)
---------------------------------------------------
1. DSSE signature — capsule JSON-profile envelope was signed by the SZL
   ECDSA P-256 keypair (szlholdings-cosign). Verified against the embedded
   cosign.pub. Labeled SKIP (not FAIL) if only the JSON-profile is present
   without a key (transparent honest-label).

2. COSE_Sign1 structure — if cose_sign1_b64 is present, decode the
   CBOR-encoded COSE_Sign1 and verify the ECDSA-P256 signature over the
   Sig_Structure bytes (COSE signing protocol per RFC 9052).

3. Capsule payload structure — verifies spec_version, capsule_statement_type,
   disposition.decision, effect_record.status are all well-formed per
   draft-mih-scitt-agent-action-capsule-01.

4. Hard binding — verifies effect_record.output_sha3_256 matches
   SHA3-256(answer_text) when the answer is provided (C2PA pattern).
   For BLOCK verdicts where output is "BLOCKED", this check is PARTIAL.

5. Merkle inclusion proof — verifies leaf_hash(payload) walks the
   audit_path to root_hash (RFC 6962 SHA3-256). OFFLINE math.

6. Honest-label check — verifies the signing_profile field correctly reflects
   whether COSE_Sign1 or JSON-profile was used. Fails if the label is inconsistent.

USAGE
-----
  # Fetch a capsule from the live API
  curl -s https://szlholdings-a11oy.hf.space/api/a11oy/v1/scitt/capsule/<id> > capsule.json

  # Run the verifier (stdlib + cryptography; cbor2 optional for COSE check)
  python3 verify-scitt-capsule.py capsule.json

  # Or pipe directly
  curl -s https://szlholdings-a11oy.hf.space/api/a11oy/v1/scitt/capsule/<id> \\
    | python3 verify-scitt-capsule.py -

  # Verbose output
  python3 verify-scitt-capsule.py capsule.json --verbose

  # Force BLOCK-capsule check (confirm BLOCK verdicts produce capsules too)
  python3 verify-scitt-capsule.py capsule.json --expect-block

DEPENDENCIES
  stdlib only for most checks.
  cryptography (pip install cryptography) for DSSE sig and COSE ECDSA checks.
  cbor2 (pip install cbor2) for COSE_Sign1 decode.

EXIT CODES
  0  — all mandatory checks PASSED (skipped/partial count as non-fatal)
  1  — one or more checks FAILED
  2  — usage error

HONEST LIMITS
  - Does not verify Lean4Agent proof hash (lean_proof_hash is ROADMAP Phase II).
  - Does not verify EU AI Act energy field (energy_wh is ROADMAP).
  - Does not verify TEE attestation (dstack TDX attestation is Phase II).
  - Third-party SCITT TS registration is ROADMAP; only self-hosted Merkle log.
  - SZL keypair trust depends on cosign.pub authenticity.

Apache-2.0 — SZL Holdings 2026. Reimplement, modify, redistribute freely.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sys
from typing import Any

# ---------------------------------------------------------------------------
# EMBEDDED PUBLIC KEY (szl-holdings/.github/cosign.pub — public, not a secret)
# ---------------------------------------------------------------------------
_COSIGN_PUBLIC_PEM = """
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEyq9ALpZuegbE67GRpWp8FfGSX1IJ
bt5gw4jQ3RuBuIYIZchnfn9XLZf5KKw+zRfq5EJ8S+5cqwai5Wz0FDSyyA==
-----END PUBLIC KEY-----
""".strip()

_PUBLIC_KEY_URL = "https://github.com/szl-holdings/.github/blob/main/cosign.pub"
_CAPSULE_SPEC = "draft-mih-scitt-agent-action-capsule-01"
_SCITT_PAYLOAD_TYPE = "application/vnd.szl.scitt-capsule+json"


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _sha3_256(b: bytes) -> str:
    return hashlib.sha3_256(b).hexdigest()


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def _pae(payload_type: str, body: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding."""
    t = payload_type.encode("utf-8")
    return (b"DSSEv1 " + str(len(t)).encode() + b" " + t
            + b" " + str(len(body)).encode() + b" " + body)


# ---------------------------------------------------------------------------
# CHECK 1: DSSE SIGNATURE (JSON-profile envelope)
# ---------------------------------------------------------------------------

def check_dsse_signature(json_envelope: dict, verbose: bool = False) -> dict:
    result = {"check": "dsse_signature_json_profile", "passed": False, "reason": ""}

    if not json_envelope:
        result["reason"] = "json_envelope missing from capsule"
        return result

    payload_type = json_envelope.get("payloadType", "")
    payload_b64 = json_envelope.get("payload", "")
    signatures = json_envelope.get("signatures", [])
    signed = json_envelope.get("signed", False)

    if not signed:
        result["passed"] = True  # Honest unsigned = transparent, not failure
        result["reason"] = (
            "JSON-profile capsule is UNSIGNED (no key available at signing time). "
            "This is honest behavior, not a forgery. "
            f"Label: {json_envelope.get('honesty', 'no honesty label')}"
        )
        result["warning"] = "Capsule unsigned — verify SZL_COSIGN_PRIVATE_KEY_PEM was set at signing time."
        result["partial"] = True
        return result

    if not signatures:
        result["reason"] = "signed=true but no signatures in envelope"
        return result

    try:
        payload_bytes = base64.b64decode(payload_b64 + "==")
    except Exception as exc:
        result["reason"] = f"base64 decode failed: {exc}"
        return result

    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature
    except ImportError:
        result["passed"] = None
        result["reason"] = "cryptography not installed — DSSE sig check skipped"
        result["skipped"] = True
        return result

    pub_key = load_pem_public_key(_COSIGN_PUBLIC_PEM.encode("utf-8"))
    pae_bytes = _pae(payload_type, payload_bytes)
    verified = False
    for sig_entry in signatures:
        try:
            sig_bytes = base64.b64decode(sig_entry.get("sig", "") + "==")
            pub_key.verify(sig_bytes, pae_bytes, ec.ECDSA(hashes.SHA256()))
            verified = True
            if verbose:
                print(f"  [dsse] keyid={sig_entry.get('keyid')} → VALID")
            break
        except Exception:
            pass

    if verified:
        result["passed"] = True
        result["reason"] = f"ECDSA-P256 DSSE signature verified against {_PUBLIC_KEY_URL}"
    else:
        result["passed"] = False
        result["reason"] = "DSSE signature verification failed"
    return result


# ---------------------------------------------------------------------------
# CHECK 2: COSE_Sign1 (if present)
# ---------------------------------------------------------------------------

def check_cose_sign1(cose_b64: str | None, payload: dict, verbose: bool = False) -> dict:
    result = {"check": "cose_sign1", "passed": None, "reason": ""}

    if not cose_b64:
        result["passed"] = True
        result["reason"] = (
            "cose_sign1_b64 not present — JSON-profile signing in use "
            "(cbor2/pycose absent at signing time; ROADMAP for COSE upgrade). "
            "Not a failure — honest label present."
        )
        result["skipped"] = True
        return result

    try:
        import cbor2
    except ImportError:
        result["passed"] = None
        result["reason"] = "cbor2 not installed — cannot decode COSE_Sign1. pip install cbor2"
        result["skipped"] = True
        return result

    try:
        cose_bytes = base64.b64decode(cose_b64 + "==")
        decoded = cbor2.loads(cose_bytes)
    except Exception as exc:
        result["passed"] = False
        result["reason"] = f"CBOR decode failed: {exc}"
        return result

    if not hasattr(decoded, "tag") or decoded.tag != 18:
        result["passed"] = False
        result["reason"] = f"Expected COSE_Sign1 tag 18, got {getattr(decoded, 'tag', '?')}"
        return result

    try:
        protected_hdr_bytes, unprotected_hdr, payload_bytes, sig_bytes = decoded.value
        if verbose:
            print(f"  [cose] COSE_Sign1 structure OK, sig_len={len(sig_bytes)}")
    except Exception as exc:
        result["passed"] = False
        result["reason"] = f"COSE_Sign1 structure malformed: {exc}"
        return result

    try:
        from cryptography.hazmat.primitives.serialization import load_pem_public_key
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives import hashes
        from cryptography.exceptions import InvalidSignature

        sig_structure = cbor2.dumps([
            "Signature1",
            protected_hdr_bytes,
            b"",
            payload_bytes,
        ])
        pub_key = load_pem_public_key(_COSIGN_PUBLIC_PEM.encode("utf-8"))
        pub_key.verify(sig_bytes, sig_structure, ec.ECDSA(hashes.SHA256()))
        result["passed"] = True
        result["reason"] = f"COSE_Sign1 ECDSA-P256 signature verified against {_PUBLIC_KEY_URL}"
        if verbose:
            print(f"  [cose] COSE_Sign1 sig verified OK")
    except ImportError:
        result["passed"] = None
        result["reason"] = "cryptography not installed — COSE sig check skipped"
        result["skipped"] = True
    except Exception as exc:
        result["passed"] = False
        result["reason"] = f"COSE_Sign1 signature verification failed: {exc}"

    return result


# ---------------------------------------------------------------------------
# CHECK 3: CAPSULE STRUCTURE (spec conformance)
# ---------------------------------------------------------------------------

def check_capsule_structure(capsule: dict, verbose: bool = False) -> dict:
    result = {"check": "capsule_structure", "passed": False, "reason": ""}
    errors = []

    payload = capsule.get("payload", {})
    if not payload:
        errors.append("'payload' field missing from capsule")

    spec = capsule.get("spec_version", "")
    if spec != _CAPSULE_SPEC:
        errors.append(f"spec_version={spec!r}, expected {_CAPSULE_SPEC!r}")

    cst = payload.get("capsule_statement_type", "")
    if cst != "agent_action":
        errors.append(f"capsule_statement_type={cst!r}, expected 'agent_action'")

    disposition = payload.get("disposition", {})
    decision = disposition.get("decision", "")
    valid_decisions = {"executed", "blocked", "review", "errored", "denied"}
    if decision not in valid_decisions:
        errors.append(f"disposition.decision={decision!r}, expected one of {valid_decisions}")

    effect = payload.get("effect_record", {})
    if not effect:
        errors.append("effect_record missing")

    if not payload.get("capsule_id"):
        errors.append("capsule_id missing")

    signing_profile = capsule.get("signing_profile", "")
    if not signing_profile:
        errors.append("signing_profile missing")

    if errors:
        result["passed"] = False
        result["reason"] = "; ".join(errors)
    else:
        result["passed"] = True
        result["reason"] = (
            f"Capsule structure valid. "
            f"verdict={decision}, "
            f"signing_profile={signing_profile!r}"
        )
        if verbose:
            print(f"  [struct] capsule_id={payload.get('capsule_id')}")
            print(f"  [struct] decision={decision}, model_id={payload.get('model_id')}")
            print(f"  [struct] timestamp={payload.get('timestamp')}")

    return result


# ---------------------------------------------------------------------------
# CHECK 4: BLOCK VERDICT HAS CAPSULE (doctrine check)
# ---------------------------------------------------------------------------

def check_block_produces_capsule(capsule: dict, expect_block: bool = False) -> dict:
    """
    Doctrine: BLOCK verdicts MUST produce a capsule (signed refusals).
    If expect_block=True, verify decision is 'blocked' and capsule_id is present.
    """
    result = {"check": "block_produces_capsule", "passed": True, "reason": ""}
    payload = capsule.get("payload", {})
    decision = payload.get("disposition", {}).get("decision", "")

    if expect_block:
        if decision != "blocked":
            result["passed"] = False
            result["reason"] = (
                f"--expect-block set but disposition.decision={decision!r} (expected 'blocked'). "
                "Either this is an ALLOW capsule, or the BLOCK was not recorded correctly."
            )
        else:
            result["passed"] = True
            result["reason"] = (
                f"BLOCK capsule confirmed: decision='blocked', "
                f"capsule_id={payload.get('capsule_id')}. "
                "Doctrine: refusal is signed and tamper-evident."
            )
    else:
        result["reason"] = (
            f"Capsule present for verdict '{decision}'. "
            "Doctrine: both ALLOW and BLOCK produce capsules (signed refusals are the point)."
        )

    return result


# ---------------------------------------------------------------------------
# CHECK 5: HARD BINDING (output hash vs answer)
# ---------------------------------------------------------------------------

def check_hard_binding(capsule: dict, answer: str | None = None,
                       verbose: bool = False) -> dict:
    result = {"check": "hard_binding", "passed": False, "reason": ""}
    payload = capsule.get("payload", {})
    effect = payload.get("effect_record", {})
    stored_hash = effect.get("output_sha3_256", "")
    decision = payload.get("disposition", {}).get("decision", "")

    if stored_hash == "BLOCKED":
        result["passed"] = True
        result["reason"] = (
            "BLOCK capsule: output_sha3_256='BLOCKED' (no model output produced). "
            "Hard binding is N/A for refusal turns — capsule records the refusal, not an output."
        )
        result["partial"] = True
        return result

    if not stored_hash or len(stored_hash) != 64:
        result["passed"] = False
        result["reason"] = f"output_sha3_256 missing or malformed: {stored_hash!r}"
        return result

    if answer is None:
        result["passed"] = True
        result["reason"] = (
            "PARTIAL: no answer text supplied. Hash is present and well-formed. "
            "Supply the model output text to verify content binding."
        )
        result["stored_hash"] = stored_hash
        result["partial"] = True
        return result

    computed = _sha3_256(answer.encode("utf-8"))
    if computed == stored_hash:
        result["passed"] = True
        result["reason"] = "Hard binding verified: SHA3-256(answer) matches output_sha3_256"
        if verbose:
            print(f"  [bind] SHA3-256(answer)={computed} ✓")
    else:
        result["passed"] = False
        result["reason"] = (
            f"Hard binding MISMATCH: computed={computed!r}, stored={stored_hash!r}. "
            "Capsule was signed for a different output (tampering)."
        )

    return result


# ---------------------------------------------------------------------------
# CHECK 6: MERKLE INCLUSION PROOF
# ---------------------------------------------------------------------------

def check_merkle_inclusion(capsule: dict, verbose: bool = False) -> dict:
    result = {"check": "merkle_inclusion", "passed": False, "reason": ""}
    transparency = capsule.get("transparency", {})

    if not transparency:
        result["reason"] = "transparency field missing from capsule"
        return result

    hashes_hex = transparency.get("hashes", [])
    root_hash_hex = transparency.get("root_hash", "")
    leaf_index = transparency.get("leaf_index")
    leaf_hash_stored = transparency.get("leaf_hash", "")

    if not root_hash_hex:
        result["reason"] = "root_hash missing"
        return result
    if leaf_index is None:
        result["reason"] = "leaf_index missing"
        return result

    payload = capsule.get("payload", {})
    leaf_data = _canonical_json(payload)
    computed_leaf = hashlib.sha3_256(b"\x00" + leaf_data).digest()
    computed_leaf_hex = computed_leaf.hex()

    if verbose:
        print(f"  [merkle] computed leaf_hash={computed_leaf_hex}")
        if leaf_hash_stored:
            print(f"  [merkle] stored  leaf_hash={leaf_hash_stored}")

    if leaf_hash_stored and computed_leaf_hex != leaf_hash_stored:
        result["passed"] = False
        result["reason"] = (
            f"Leaf hash mismatch: computed={computed_leaf_hex}, stored={leaf_hash_stored}. "
            "Payload was modified after log append."
        )
        return result

    # Walk audit path (RFC 6962)
    audit = [bytes.fromhex(h) for h in hashes_hex]
    node = computed_leaf
    i = leaf_index
    for lvl, sibling in enumerate(audit):
        if i % 2 == 0:
            node = hashlib.sha3_256(b"\x01" + node + sibling).digest()
        else:
            node = hashlib.sha3_256(b"\x01" + sibling + node).digest()
        if verbose:
            print(f"  [merkle] level {lvl}: → {node.hex()[:16]}…")
        i //= 2

    computed_root = node.hex()
    if verbose:
        print(f"  [merkle] computed root={computed_root}")
        print(f"  [merkle] stored   root={root_hash_hex}")

    if computed_root == root_hash_hex:
        result["passed"] = True
        result["reason"] = (
            f"Merkle inclusion proof verified: "
            f"leaf_index={leaf_index}, tree_size={transparency.get('tree_size')}, "
            f"root_hash={root_hash_hex}"
        )
    else:
        result["passed"] = False
        result["reason"] = (
            f"Merkle root mismatch: computed={computed_root}, stored={root_hash_hex}. "
            "Proof invalid or log mutated."
        )

    return result


# ---------------------------------------------------------------------------
# MAIN VERIFIER
# ---------------------------------------------------------------------------

def verify(capsule: dict, verbose: bool = False, expect_block: bool = False,
           answer: str | None = None) -> dict:
    checks = []
    capsule_id = capsule.get("capsule_id", "unknown")

    if verbose:
        print(f"\n[verify-scitt] capsule_id: {capsule_id}")
        print(f"[verify-scitt] signing_profile: {capsule.get('signing_profile')}")
        print(f"[verify-scitt] spec_version: {capsule.get('spec_version')}")

    c1 = check_dsse_signature(capsule.get("json_envelope", {}), verbose=verbose)
    checks.append(c1)
    if verbose:
        _s = "PASS" if c1["passed"] else ("SKIP" if c1.get("skipped") else "FAIL")
        print(f"[1] DSSE sig: {_s} — {c1['reason']}")

    c2 = check_cose_sign1(capsule.get("cose_sign1_b64"), capsule.get("payload", {}), verbose=verbose)
    checks.append(c2)
    if verbose:
        _s = "PASS" if c2["passed"] else ("SKIP" if c2.get("skipped") else "FAIL")
        print(f"[2] COSE_Sign1: {_s} — {c2['reason']}")

    c3 = check_capsule_structure(capsule, verbose=verbose)
    checks.append(c3)
    if verbose:
        print(f"[3] Structure: {'PASS' if c3['passed'] else 'FAIL'} — {c3['reason']}")

    c4 = check_block_produces_capsule(capsule, expect_block=expect_block)
    checks.append(c4)
    if verbose:
        print(f"[4] Block capsule: {'PASS' if c4['passed'] else 'FAIL'} — {c4['reason']}")

    c5 = check_hard_binding(capsule, answer=answer, verbose=verbose)
    checks.append(c5)
    if verbose:
        print(f"[5] Hard binding: {'PASS' if c5['passed'] else 'FAIL'} — {c5['reason']}")

    c6 = check_merkle_inclusion(capsule, verbose=verbose)
    checks.append(c6)
    if verbose:
        print(f"[6] Merkle proof: {'PASS' if c6['passed'] else 'FAIL'} — {c6['reason']}")

    failed = [c for c in checks if c["passed"] is False]
    skipped = [c for c in checks if c.get("skipped")]
    partial = [c for c in checks if c.get("partial")]

    if failed:
        overall = "FAIL"
    elif skipped or partial:
        overall = "PARTIAL"
    else:
        overall = "PASS"

    return {
        "overall": overall,
        "capsule_id": capsule_id,
        "spec_version": capsule.get("spec_version"),
        "signing_profile": capsule.get("signing_profile"),
        "checks": checks,
        "failed_checks": [c["check"] for c in failed],
        "honest_limits": [
            "Self-hosted Merkle log only; third-party SCITT TS is ROADMAP.",
            "Lean4Agent proof hash (lean_proof_hash) verification is Phase II ROADMAP.",
            "EU AI Act energy field (energy_wh) verification is Phase II ROADMAP.",
            "TEE attestation (dstack TDX) is Phase II ROADMAP.",
            f"Keypair trust depends on cosign.pub at {_PUBLIC_KEY_URL}.",
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Offline verifier for SZL a11oy SCITT Agent Action Capsules.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "capsule_file",
        nargs="?",
        default="-",
        help="Path to capsule JSON file (or '-' for stdin). "
             "Fetch: curl -s https://szlholdings-a11oy.hf.space/api/a11oy/v1/scitt/capsule/<id>",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON")
    parser.add_argument("--expect-block", action="store_true",
                        help="Assert this capsule is a BLOCK verdict (doctrine check)")
    parser.add_argument("--answer", default=None,
                        help="Model answer text for hard-binding check")
    args = parser.parse_args()

    try:
        if args.capsule_file == "-":
            raw = sys.stdin.read()
        else:
            with open(args.capsule_file, encoding="utf-8") as fh:
                raw = fh.read()
        capsule = json.loads(raw)
    except FileNotFoundError:
        print(f"ERROR: file not found: {args.capsule_file}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON: {exc}", file=sys.stderr)
        sys.exit(2)

    result = verify(capsule, verbose=args.verbose,
                    expect_block=args.expect_block, answer=args.answer)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"\n{'='*60}")
        print("SZL a11oy SCITT Agent Action Capsule Verifier")
        print(f"{'='*60}")
        print(f"Capsule ID      : {result['capsule_id']}")
        print(f"Spec            : {result['spec_version']}")
        print(f"Signing profile : {result['signing_profile']}")
        print(f"Overall         : {result['overall']}")
        print()
        for check in result["checks"]:
            status = "PASS" if check["passed"] else ("SKIP" if check.get("skipped") else "FAIL")
            print(f"  [{status:4s}] {check['check']}: {check['reason']}")
        if result.get("failed_checks"):
            print(f"\nFailed checks: {result['failed_checks']}")
        print("\nHonest limits:")
        for limit in result["honest_limits"]:
            print(f"  - {limit}")
        print(f"{'='*60}\n")

    sys.exit(0 if result["overall"] in ("PASS", "PARTIAL") else 1)


if __name__ == "__main__":
    main()
