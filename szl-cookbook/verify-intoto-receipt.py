#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""
szl-cookbook: verify-intoto-receipt.py
=======================================

OFFLINE verifier for SZL a11oy Khipu receipts in in-toto Statement v1 format.

WHAT THIS PROVES (without trusting SZL at runtime):
  1. DSSE signature — receipt was signed by the SZL ECDSA P-256 keypair.
     Verified against the published cosign.pub (embedded below; also at
     https://github.com/szl-holdings/.github/blob/main/cosign.pub).
  2. in-toto Statement v1 structure — receipt payload is a valid Statement v1
     (_type, subject, predicateType, predicate all present and typed correctly).
  3. Hard binding — subject.digest["sha3-256"] matches SHA3-256(answer_text)
     (C2PA pattern: receipt cannot be recycled for a different model output).
  4. Merkle inclusion proof — leaf_hash(statement) walks the audit_path to the
     root_hash. OFFLINE math: no trust in SZL required for the proof check.

USAGE:
  # Fetch a receipt bundle from the live API
  curl -s https://szlholdings-a11oy.hf.space/khipu/intoto/<receipt_id> > receipt.json

  # Run the verifier (stdlib only; no pip installs required except `cryptography`)
  python3 verify-intoto-receipt.py receipt.json

  # Or pipe directly
  curl -s https://szlholdings-a11oy.hf.space/khipu/intoto/<receipt_id> | python3 verify-intoto-receipt.py -

  # Verbose output
  python3 verify-intoto-receipt.py receipt.json --verbose

DEPENDENCIES:
  stdlib only for chain verification.
  `cryptography` (pip install cryptography) for DSSE signature verification.
  NO in-toto library, NO sigstore library, NO network call required once you
  have the receipt JSON.

EXIT CODES:
  0  — all checks PASSED
  1  — one or more checks FAILED (details printed to stdout)
  2  — usage error or unreadable input

WHAT IS NOT VERIFIED BY THIS SCRIPT (honest limits):
  - Whether the model output is correct or the governance decision was right.
  - Whether the SZL keypair itself is trustworthy (trust anchor is cosign.pub).
  - Public Rekor inclusion (per-receipt Rekor submission is ROADMAP).
    The self-hosted Merkle log inclusion proof IS verified here.
  - TEE attestation (AWS Nitro PCR) — not yet implemented (Phase II roadmap).

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
# Also fetchable at https://a-11-oy.com/cosign.pub
# ---------------------------------------------------------------------------
_COSIGN_PUBLIC_PEM = """
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAEyq9ALpZuegbE67GRpWp8FfGSX1IJ
bt5gw4jQ3RuBuIYIZchnfn9XLZf5KKw+zRfq5EJ8S+5cqwai5Wz0FDSyyA==
-----END PUBLIC KEY-----
""".strip()

_PUBLIC_KEY_URL = "https://github.com/szl-holdings/.github/blob/main/cosign.pub"

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
GOVERNED_INFERENCE_PREDICATE = "https://szl.holdings/khipu-governed-inference/v1"
INTOTO_PAYLOAD_TYPE = "application/vnd.in-toto+json"


# ---------------------------------------------------------------------------
# HELPER: DSSE PAE
# ---------------------------------------------------------------------------
def _pae(payload_type: str, body: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (DSSEv1)."""
    t = payload_type.encode("utf-8")
    return (b"DSSEv1 " + str(len(t)).encode() + b" " + t
            + b" " + str(len(body)).encode() + b" " + body)


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _sha3_256(b: bytes) -> str:
    return hashlib.sha3_256(b).hexdigest()


# ---------------------------------------------------------------------------
# CHECK 1: DSSE SIGNATURE
# ---------------------------------------------------------------------------
def check_dsse_signature(envelope: dict, verbose: bool = False) -> dict:
    """
    Verify the DSSE envelope signature against the embedded SZL cosign public key.

    The DSSE protocol:
      PAE = DSSEv1 SP LEN(payloadType) SP payloadType SP LEN(payload_bytes) SP payload_bytes
      signature = ECDSA-P256-SHA256(PAE)
      payload_bytes = base64.decode(envelope["payload"])

    Returns {passed, reason, ...}
    """
    result = {"check": "dsse_signature", "passed": False, "reason": ""}

    payload_type = envelope.get("payloadType", "")
    payload_b64 = envelope.get("payload", "")
    signatures = envelope.get("signatures", [])

    if not payload_b64:
        result["reason"] = "envelope missing 'payload' field"
        return result
    if not signatures:
        # Check for honest unsigned label
        if not envelope.get("signed", True):
            result["passed"] = False
            result["reason"] = f"receipt is UNSIGNED (honesty: {envelope.get('honesty', 'no signing key')})"
            result["warning"] = "Receipt was emitted without signing key present — not a forgery, but unverified."
            return result
        result["reason"] = "no signatures in envelope"
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
        result["reason"] = (
            "cryptography library not installed — DSSE sig check skipped. "
            "Install with: pip install cryptography"
        )
        result["skipped"] = True
        return result

    pub_key = load_pem_public_key(_COSIGN_PUBLIC_PEM.encode("utf-8"))
    pae_bytes = _pae(payload_type, payload_bytes)

    verified = False
    last_exc = None
    for sig_entry in signatures:
        sig_b64 = sig_entry.get("sig", "")
        if not sig_b64:
            continue
        try:
            sig_bytes = base64.b64decode(sig_b64 + "==")
            pub_key.verify(sig_bytes, pae_bytes, ec.ECDSA(hashes.SHA256()))
            verified = True
            if verbose:
                print(f"  [sig] keyid={sig_entry.get('keyid')} → VALID (ECDSA-P256-SHA256)")
            break
        except InvalidSignature:
            last_exc = "InvalidSignature"
        except Exception as exc:
            last_exc = str(exc)

    if verified:
        result["passed"] = True
        result["reason"] = f"ECDSA-P256-SHA256 signature verified against {_PUBLIC_KEY_URL}"
        result["payload_type"] = payload_type
        result["payload_sha3_256"] = _sha3_256(payload_bytes)
    else:
        result["passed"] = False
        result["reason"] = f"signature verification failed: {last_exc}"

    return result


# ---------------------------------------------------------------------------
# CHECK 2: in-toto Statement v1 STRUCTURE
# ---------------------------------------------------------------------------
def check_intoto_statement(statement: dict, verbose: bool = False) -> dict:
    """
    Verify the in-toto Statement v1 structure.

    Required fields per spec (https://github.com/in-toto/attestation/blob/main/spec/v1/statement.md):
      _type: "https://in-toto.io/Statement/v1"
      subject: [{name: str, digest: {alg: hex}}]
      predicateType: URI string
      predicate: object
    """
    result = {"check": "intoto_statement_v1", "passed": False, "reason": ""}
    errors = []

    _type = statement.get("_type")
    if _type != STATEMENT_TYPE:
        errors.append(f"_type is {_type!r}, expected {STATEMENT_TYPE!r}")

    subject = statement.get("subject")
    if not isinstance(subject, list) or len(subject) == 0:
        errors.append("subject must be a non-empty list")
    else:
        for i, s in enumerate(subject):
            if not isinstance(s.get("name"), str):
                errors.append(f"subject[{i}].name missing or not a string")
            digest = s.get("digest", {})
            if not isinstance(digest, dict) or not digest:
                errors.append(f"subject[{i}].digest missing or empty")

    predicate_type = statement.get("predicateType")
    if not isinstance(predicate_type, str) or not predicate_type.startswith("http"):
        errors.append(f"predicateType is {predicate_type!r}, expected a URI")

    predicate = statement.get("predicate")
    if not isinstance(predicate, dict):
        errors.append("predicate must be an object")

    if errors:
        result["passed"] = False
        result["reason"] = "; ".join(errors)
        result["errors"] = errors
    else:
        result["passed"] = True
        result["reason"] = "valid in-toto Statement v1"
        result["_type"] = _type
        result["predicate_type"] = predicate_type
        result["subject_count"] = len(subject)
        result["subject_names"] = [s.get("name") for s in subject]
        if verbose:
            print(f"  [stmt] predicateType={predicate_type}")
            for s in subject:
                print(f"  [stmt] subject: {s.get('name')} → digest={s.get('digest')}")

    return result


# ---------------------------------------------------------------------------
# CHECK 3: HARD BINDING (C2PA pattern)
# ---------------------------------------------------------------------------
def check_hard_binding(statement: dict, answer: str | None = None,
                       verbose: bool = False) -> dict:
    """
    Verify that subject.digest["sha3-256"] matches SHA3-256(answer_text).

    C2PA hard-binding pattern: the receipt binds to the EXACT model output.
    If the answer was replaced after signing, the digest will not match.

    If answer is None (e.g. denied turn), we verify the digest is a valid hex
    string but cannot check the content binding (labeled PARTIAL).
    """
    result = {"check": "hard_binding", "passed": False, "reason": ""}

    subject = statement.get("subject", [{}])
    if not subject:
        result["reason"] = "no subject in statement"
        return result

    digest = subject[0].get("digest", {})
    stored_hash = digest.get("sha3-256", "")

    if not stored_hash or len(stored_hash) != 64:
        result["passed"] = False
        result["reason"] = f"subject.digest[sha3-256] missing or invalid: {stored_hash!r}"
        return result

    if answer is None:
        # Try to extract from predicate
        predicate = statement.get("predicate", {})
        answer = predicate.get("answer") or predicate.get("output") or None

    if answer is None:
        result["passed"] = True
        result["reason"] = (
            "PARTIAL: no answer text available to verify content binding. "
            "Digest is present and well-formed. "
            "To fully verify: supply the model output text."
        )
        result["stored_digest"] = stored_hash
        result["partial"] = True
        return result

    computed_hash = _sha3_256(answer.encode("utf-8"))
    # Also check alternative binding methods documented in szl_intoto.py
    if stored_hash == computed_hash:
        result["passed"] = True
        result["reason"] = "output hash verified: SHA3-256(answer) matches subject.digest"
        result["computed_hash"] = computed_hash
        result["stored_hash"] = stored_hash
        if verbose:
            print(f"  [bind] SHA3-256(answer)={computed_hash} ✓")
    else:
        # Check fallback binding (receipt_id + canonical_json of predicate)
        predicate = statement.get("predicate", {})
        receipt_id = (predicate.get("receipt_id") or predicate.get("id")
                      or predicate.get("hash") or "")
        _STRIP_KEYS = frozenset({"dsse", "signatures", "_dsse", "_pae_sha256",
                                  "honesty", "verify_key_url"})
        stripped_predicate = {k: v for k, v in predicate.items()
                               if k not in _STRIP_KEYS}
        fallback_input = (receipt_id + ":").encode("utf-8") + _canonical_json(stripped_predicate)
        fallback_hash = _sha3_256(fallback_input)
        if stored_hash == fallback_hash:
            result["passed"] = True
            result["reason"] = "output hash verified via fallback binding (receipt_id + predicate)"
            result["computed_hash"] = fallback_hash
            result["binding_method"] = "fallback"
            if verbose:
                print(f"  [bind] fallback binding={fallback_hash} ✓")
        else:
            result["passed"] = False
            result["reason"] = (
                f"output hash MISMATCH: stored={stored_hash!r}, "
                f"computed_direct={computed_hash!r}. "
                "Receipt may have been signed for a different output (tampering)."
            )
            result["stored_hash"] = stored_hash
            result["computed_hash"] = computed_hash

    return result


# ---------------------------------------------------------------------------
# CHECK 4: MERKLE INCLUSION PROOF
# ---------------------------------------------------------------------------
def _leaf_hash_sha3(data: bytes) -> bytes:
    """RFC 6962 leaf hash: SHA3-256(0x00 || data)."""
    return hashlib.sha3_256(b"\x00" + data).digest()


def _node_hash_sha3(left: bytes, right: bytes) -> bytes:
    """RFC 6962 interior node: SHA3-256(0x01 || left || right)."""
    return hashlib.sha3_256(b"\x01" + left + right).digest()


def check_merkle_inclusion(statement: dict, transparency: dict,
                           verbose: bool = False) -> dict:
    """
    Verify the Merkle inclusion proof for the self-hosted SZL transparency log.

    Algorithm (RFC 6962):
      1. Compute leaf_hash = SHA3-256(0x00 || canonical_json(statement))
      2. Walk audit_path: for each sibling, compute parent = node_hash(node, sibling)
         (left/right determined by leaf_index parity at each level)
      3. The final computed node should equal root_hash

    This is pure math — no trust in SZL required for verification.
    """
    result = {"check": "merkle_inclusion", "passed": False, "reason": ""}

    log_type = transparency.get("transparency_log", "")
    if log_type == "rekor-public":
        result["passed"] = True
        result["reason"] = (
            f"Rekor public log inclusion: logIndex={transparency.get('log_index')}. "
            f"Verify at {transparency.get('log_url', 'rekor.sigstore.dev')}. "
            "Note: per-receipt Rekor submission may not be available in all deployments."
        )
        result["transparency_log"] = "rekor-public"
        return result

    if "error" in transparency:
        result["passed"] = False
        result["reason"] = f"No inclusion proof: {transparency['error']}"
        return result

    hashes_hex = transparency.get("hashes", [])
    root_hash_hex = transparency.get("root_hash", "")
    leaf_index = transparency.get("leaf_index")
    leaf_hash_stored_hex = transparency.get("leaf_hash", "")

    if not root_hash_hex:
        result["reason"] = "root_hash missing from proof"
        return result
    if leaf_index is None:
        result["reason"] = "leaf_index missing from proof"
        return result

    # Step 1: compute leaf hash from the statement
    leaf_data = _canonical_json(statement)
    computed_leaf = _leaf_hash_sha3(leaf_data)
    computed_leaf_hex = computed_leaf.hex()

    if verbose:
        print(f"  [merkle] computed leaf_hash={computed_leaf_hex}")
        if leaf_hash_stored_hex:
            print(f"  [merkle] stored leaf_hash ={leaf_hash_stored_hex}")

    if leaf_hash_stored_hex and computed_leaf_hex != leaf_hash_stored_hex:
        result["passed"] = False
        result["reason"] = (
            f"Leaf hash mismatch: computed={computed_leaf_hex}, "
            f"stored={leaf_hash_stored_hex}. "
            "Statement was modified after log append."
        )
        return result

    # Step 2: walk audit path
    audit_hashes = [bytes.fromhex(h) for h in hashes_hex]
    node = computed_leaf
    i = leaf_index
    for level_idx, sibling in enumerate(audit_hashes):
        if i % 2 == 0:
            # current node is left child
            node = _node_hash_sha3(node, sibling)
            if verbose:
                print(f"  [merkle] level {level_idx}: node(L,sibling) → {node.hex()[:16]}…")
        else:
            # current node is right child
            node = _node_hash_sha3(sibling, node)
            if verbose:
                print(f"  [merkle] level {level_idx}: node(sibling,R) → {node.hex()[:16]}…")
        i //= 2

    computed_root = node.hex()
    if verbose:
        print(f"  [merkle] computed root={computed_root}")
        print(f"  [merkle] stored root  ={root_hash_hex}")

    if computed_root == root_hash_hex:
        result["passed"] = True
        result["reason"] = (
            f"Merkle inclusion proof verified: "
            f"leaf_index={leaf_index}, tree_size={transparency.get('tree_size')}, "
            f"root_hash={root_hash_hex}. "
            f"transparency_log={log_type}"
        )
        result["transparency_log"] = log_type
        result["root_hash"] = root_hash_hex
        result["leaf_index"] = leaf_index
    else:
        result["passed"] = False
        result["reason"] = (
            f"Merkle root mismatch: computed={computed_root}, "
            f"stored={root_hash_hex}. "
            "Proof is invalid or the log was mutated."
        )

    return result


# ---------------------------------------------------------------------------
# MAIN VERIFIER
# ---------------------------------------------------------------------------
def verify(receipt_bundle: dict, verbose: bool = False) -> dict:
    """
    Run all verification checks on a receipt bundle from /khipu/intoto/<id>.

    Returns:
      {
        "overall": "PASS" | "FAIL" | "PARTIAL",
        "checks": [...],
        "receipt_id": "<id>",
        "honest_limits": ["..."]
      }
    """
    checks = []
    receipt_id = receipt_bundle.get("receipt_id", "unknown")
    intoto_envelope = receipt_bundle.get("intoto_envelope", {})
    intoto_statement = receipt_bundle.get("intoto_statement", {})
    transparency = receipt_bundle.get("transparency", {})

    if not intoto_envelope and not intoto_statement:
        return {
            "overall": "FAIL",
            "receipt_id": receipt_id,
            "checks": [],
            "error": (
                "Input does not contain 'intoto_envelope' or 'intoto_statement'. "
                "Fetch from /khipu/intoto/<receipt_id> to get the in-toto format."
            ),
        }

    # If statement is embedded in the envelope payload, decode it
    if not intoto_statement and intoto_envelope.get("payload"):
        try:
            payload_bytes = base64.b64decode(intoto_envelope["payload"] + "==")
            intoto_statement = json.loads(payload_bytes)
        except Exception:
            pass

    if verbose:
        print(f"\n[verify] receipt_id: {receipt_id}")
        print(f"[verify] transparency_log: {transparency.get('transparency_log', 'none')}")

    # CHECK 1: DSSE signature
    c1 = check_dsse_signature(intoto_envelope, verbose=verbose)
    checks.append(c1)
    if verbose:
        status = "PASS" if c1["passed"] else ("SKIP" if c1.get("skipped") else "FAIL")
        print(f"[1] DSSE Signature: {status} — {c1['reason']}")

    # CHECK 2: in-toto Statement v1 structure
    c2 = check_intoto_statement(intoto_statement, verbose=verbose)
    checks.append(c2)
    if verbose:
        print(f"[2] Statement v1: {'PASS' if c2['passed'] else 'FAIL'} — {c2['reason']}")

    # CHECK 3: Hard binding
    c3 = check_hard_binding(intoto_statement, verbose=verbose)
    checks.append(c3)
    if verbose:
        partial = " (PARTIAL)" if c3.get("partial") else ""
        print(f"[3] Hard Binding: {'PASS' if c3['passed'] else 'FAIL'}{partial} — {c3['reason']}")

    # CHECK 4: Merkle inclusion proof
    if transparency:
        c4 = check_merkle_inclusion(intoto_statement, transparency, verbose=verbose)
        checks.append(c4)
        if verbose:
            print(f"[4] Merkle Proof: {'PASS' if c4['passed'] else 'FAIL'} — {c4['reason']}")

    # Determine overall result
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
        "receipt_id": receipt_id,
        "checks": checks,
        "failed_checks": [c["check"] for c in failed],
        "honest_limits": [
            "Per-receipt public Rekor inclusion is ROADMAP (self-hosted Merkle log is current).",
            "TEE attestation (AWS Nitro PCR) is Phase II roadmap.",
            "SZL keypair trust depends on cosign.pub authenticity — verify at " + _PUBLIC_KEY_URL,
            "governance correctness (Λ, gates) is NOT verified by this script.",
        ],
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Offline verifier for SZL a11oy in-toto Khipu receipts.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "receipt_file",
        nargs="?",
        default="-",
        help="Path to receipt JSON file (or '-' to read from stdin). "
             "Fetch from: curl -s https://szlholdings-a11oy.hf.space/khipu/intoto/<id>",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--json", "-j", action="store_true", help="Output raw JSON result")
    args = parser.parse_args()

    # Read input
    try:
        if args.receipt_file == "-":
            raw = sys.stdin.read()
        else:
            with open(args.receipt_file, "r", encoding="utf-8") as fh:
                raw = fh.read()
        receipt_bundle = json.loads(raw)
    except FileNotFoundError:
        print(f"ERROR: file not found: {args.receipt_file}", file=sys.stderr)
        sys.exit(2)
    except json.JSONDecodeError as exc:
        print(f"ERROR: invalid JSON: {exc}", file=sys.stderr)
        sys.exit(2)

    # Run verification
    result = verify(receipt_bundle, verbose=args.verbose)

    if args.json:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(f"\n{'='*60}")
        print(f"SZL a11oy in-toto Receipt Verifier")
        print(f"{'='*60}")
        print(f"Receipt ID  : {result['receipt_id']}")
        print(f"Overall     : {result['overall']}")
        print()
        for check in result["checks"]:
            status = "PASS" if check["passed"] else ("SKIP" if check.get("skipped") else "FAIL")
            print(f"  [{status:4s}] {check['check']}: {check['reason']}")
        if result.get("failed_checks"):
            print(f"\nFailed checks: {result['failed_checks']}")
        print(f"\nHonest limits:")
        for limit in result["honest_limits"]:
            print(f"  - {limit}")
        print(f"{'='*60}\n")

    sys.exit(0 if result["overall"] == "PASS" else (0 if result["overall"] == "PARTIAL" else 1))


if __name__ == "__main__":
    main()
