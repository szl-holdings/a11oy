#!/usr/bin/env python3
"""a11oy_verify.py — single-file, stdlib-only verifier for a11oy receipt bundles.

SZL Holdings / a11oy payload 05. Binding source of truth: CANON.md
(especially section 3, the Laws). This file is the reference verifier the
open strategy gives away (CANON section 2): any auditor with a bare python3
and no pip can run it:

    python3 a11oy_verify.py <receipt_bundle.json>

It prints one verdict line per check and a final verdict of PASS, INCOMPLETE,
or FAIL, with exit codes 0, 2, and 1 respectively.

Checks implemented (verifier laws, CANON section 3):

  a. Structural validation of the szl.dev/GovernedAction/v1 predicate
     (fields per CANON sections 2 and 11): action_id, actor with
     is_service_account pinned to the literal false, side_effect_class in the
     four never-collapsed classes, evidence list, completeness in
     {COMPLETE, INCOMPLETE}, redaction_commitments, rfc3161_token,
     ntp_synced. Duplicate JSON keys are rejected: canonical JSON cannot
     contain them, so a document that has them was not produced by a
     conforming issuer.
  b. Missing evidence implies INCOMPLETE, never PASS (Law 4). Declared
     completeness INCOMPLETE caps the verdict at INCOMPLETE. Evidence that
     fails its own recorded sha256 is an integrity failure.
  c. actor.is_service_account must be literally false or the verdict is FAIL
     (Law 3). Not truthy, not absent: false.
  d. Integrity recompute: canonical JSON (RFC 8785 style: sorted keys, no
     whitespace, UTF-8) over each receipt payload, SHA-256, compared against
     the recorded payload_sha256. A one-byte tamper flips the verdict to FAIL.
  e. Signature check: if the bundle carries an Ed25519 DSSE signature, the
     PAE is reconstructed exactly — b'DSSE' + 4-byte big-endian length of the
     payload type + payload type + 4-byte big-endian length of the payload +
     payload — and verified with the cryptography package if it is importable.
     If cryptography is not importable, the check prints
     SIGNATURE_UNVERIFIED_NO_CRYPTO and counts toward INCOMPLETE: this file
     never reports PASS on a signature it did not actually verify.
  f. Chain/sequence check across receipts: sequence numbers must start at 1
     and increment by exactly 1; prev_payload_sha256 must equal the recomputed
     payload hash of the previous receipt. Gaps or reordering are FAIL.
  g. Redaction commitments: for every commitment with a disclosed plaintext
     in the bundle's redaction_disclosures table, recompute
     SHA-256(salt || 0x00 || plaintext) and compare (Law: the commitment
     proves the plaintext existed; a wrong recomputation means the disclosure
     does not match what was committed). Commitments without a disclosure are
     reported as UNVERIFIED_NO_DISCLOSURE and count toward INCOMPLETE, so
     redaction can never silently strengthen a verdict.
  h. Honest time: rfc3161_token absent or recorded UNAVAILABLE, or
     ntp_synced not true, caps the verdict at INCOMPLETE with the reason
     printed. Time that cannot be proven is disclosed, never hidden.

CANON Law 5: signature is not truth. Signature validity and claim truth are
evaluated and printed as separate ledgers; a valid signature over a claim
with missing evidence is INCOMPLETE, not PASS.

Usage:
    python3 a11oy_verify.py <receipt_bundle.json>   verify one bundle
    python3 a11oy_verify.py --self-test [dir]        fabricate a valid bundle,
        tamper it six ways, assert each tamper is caught with the right
        verdict, and (if dir is given, default ./test_vectors) write the eight
        JSON bundles for third-party reproduction.

Exit codes: 0 PASS, 1 FAIL, 2 INCOMPLETE, 3 usage/IO error (not a verdict).

This file is a verifier, not production signing code. CANON section 2: the
production signing path is the maintained in-toto-attestation package; the
DSSE/PAE verification here is a verification-only reimplementation, which is
the legitimate side of the line — verifying a standard envelope is what an
auditor does.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import copy
import hashlib
import json
import struct
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.0.0"
PREDICATE_TYPE = "szl.dev/GovernedAction/v1"
BUNDLE_TYPE = "szl.dev/GovernedActionBundle/v1"
TIME_PROOF_UNAVAILABLE = "UNAVAILABLE"
SIDE_EFFECT_CLASSES = ("READ_ONLY", "REVERSIBLE", "EXTERNAL_VISIBLE", "IRREVERSIBLE")
COMPLETENESS_STATES = ("COMPLETE", "INCOMPLETE")
DECISIONS = ("ALLOW", "DENY")
RETENTION_FLOOR_DAYS = 180  # CANON Law 10: 6-month floor, expressed as 180 days

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_INCOMPLETE = 2
EXIT_USAGE = 3

_SHA256_HEX_LEN = 64
_LEN = struct.Struct(">I")


# ---------------------------------------------------------------------------
# Verdict bookkeeping
# ---------------------------------------------------------------------------


class Ledger:
    """Collects check lines and derives the final verdict.

    Levels: INFO (does not move the verdict), INC (caps at INCOMPLETE),
    FAIL (forces FAIL). Verdict rule: any FAIL => FAIL; else any INC =>
    INCOMPLETE; else PASS. There is no path to PASS that skips a check:
    every mandatory check appends exactly one line.
    """

    def __init__(self) -> None:
        self.lines: list[tuple[str, str, str]] = []  # (level, check, detail)

    def info(self, check: str, detail: str) -> None:
        self.lines.append(("INFO", check, detail))

    def inc(self, check: str, detail: str) -> None:
        self.lines.append(("INC", check, detail))

    def fail(self, check: str, detail: str) -> None:
        self.lines.append(("FAIL", check, detail))

    @property
    def has_fail(self) -> bool:
        return any(level == "FAIL" for level, _, _ in self.lines)

    @property
    def has_inc(self) -> bool:
        return any(level == "INC" for level, _, _ in self.lines)

    @property
    def verdict(self) -> str:
        if self.has_fail:
            return "FAIL"
        if self.has_inc:
            return "INCOMPLETE"
        return "PASS"

    @property
    def exit_code(self) -> int:
        return {"PASS": EXIT_PASS, "FAIL": EXIT_FAIL, "INCOMPLETE": EXIT_INCOMPLETE}[
            self.verdict
        ]

    def render(self) -> str:
        out = []
        for level, check, detail in self.lines:
            label = {"INFO": "PASS", "INC": "INCOMPLETE", "FAIL": "FAIL"}[level]
            out.append(f"[{label:10}] {check}: {detail}")
        return "\n".join(out)


# ---------------------------------------------------------------------------
# Canonical JSON (RFC 8785 style subset) and strict loading
# ---------------------------------------------------------------------------


def canonical_json(obj) -> bytes:
    """Deterministic JSON: sorted keys, no whitespace, UTF-8.

    Numbers must round-trip through Python's JSON model (int, or float
    formatted by repr); issuers of GovernedAction receipts produce only
    strings, booleans, integers, null, arrays, and objects. Reject anything
    else rather than guess.
    """
    return _canonical(obj).encode("utf-8")


def _canonical(obj) -> str:
    if obj is None:
        return "null"
    if obj is True:
        return "true"
    if obj is False:
        return "false"
    if isinstance(obj, int):
        return str(obj)
    if isinstance(obj, float):
        if obj != obj or obj in (float("inf"), float("-inf")):
            raise ValueError("non-finite float cannot be canonicalized")
        return repr(obj)
    if isinstance(obj, str):
        return json.dumps(obj, ensure_ascii=False)
    if isinstance(obj, list):
        return "[" + ",".join(_canonical(item) for item in obj) + "]"
    if isinstance(obj, dict):
        parts = []
        for key in sorted(obj.keys()):
            if not isinstance(key, str):
                raise ValueError("canonical JSON requires string keys")
            parts.append(json.dumps(key, ensure_ascii=False) + ":" + _canonical(obj[key]))
        return "{" + ",".join(parts) + "}"
    raise ValueError(f"type {type(obj).__name__} cannot be canonicalized")


class _DuplicateKeyError(ValueError):
    pass


def _no_duplicate_keys(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise _DuplicateKeyError(f"duplicate JSON key {key!r}")
        obj[key] = value
    return obj


def strict_json_loads(text: str):
    """Parse JSON, rejecting duplicate keys.

    Canonical JSON never contains duplicate keys; a document that has them
    was not produced by a conforming issuer, and accepting it would let a
    smuggled second value shadow the hashed one.
    """
    return json.loads(text, object_pairs_hook=_no_duplicate_keys)


# ---------------------------------------------------------------------------
# DSSE PAE + Ed25519 verification (cryptography optional)
# ---------------------------------------------------------------------------


def pae(payload_type: bytes, payload: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding, exactly as specified:

    b'DSSE' + 4-byte BE len(type) + type + 4-byte BE len(payload) + payload
    """
    return (
        b"DSSE"
        + _LEN.pack(len(payload_type))
        + payload_type
        + _LEN.pack(len(payload))
        + payload
    )


def _try_import_ed25519():
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return None
    return Ed25519PublicKey


def verify_dsse_signature(payload_type: str, payload: bytes, sig_b64: str, key_b64: str):
    """Returns (status, detail).

    status is one of: 'valid', 'invalid', 'no_crypto', 'malformed'.
    """
    try:
        signature = base64.b64decode(sig_b64, validate=True)
        public_raw = base64.b64decode(key_b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        return "malformed", f"base64 decode failed: {exc}"
    if len(public_raw) != 32:
        return "malformed", f"Ed25519 public key must be 32 bytes, got {len(public_raw)}"
    if len(signature) != 64:
        return "malformed", f"Ed25519 signature must be 64 bytes, got {len(signature)}"
    Ed25519PublicKey = _try_import_ed25519()
    if Ed25519PublicKey is None:
        return (
            "no_crypto",
            "SIGNATURE_UNVERIFIED_NO_CRYPTO: the cryptography package is not "
            "importable on this host; signature not verified and never assumed",
        )
    try:
        key = Ed25519PublicKey.from_public_bytes(public_raw)
        key.verify(signature, pae(payload_type.encode("utf-8"), payload))
        return "valid", "Ed25519 signature over DSSE PAE verifies"
    except Exception:
        return "invalid", "signature does not verify (artifact altered or wrong key)"


# ---------------------------------------------------------------------------
# Structural validation of the GovernedAction/v1 predicate
# ---------------------------------------------------------------------------


def _is_sha256_hex(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == _SHA256_HEX_LEN
        and all(c in "0123456789abcdef" for c in value)
    )


def _is_nonempty_str(value) -> bool:
    return isinstance(value, str) and len(value) > 0


def check_predicate_structure(pred, ledger: Ledger, where: str) -> bool:
    """Validate predicate fields per CANON sections 2/11. Returns True if the
    predicate is structurally sound enough for deeper checks."""
    ok = True
    check = f"structure[{where}]"

    def bad(detail: str) -> None:
        nonlocal ok
        ok = False
        ledger.fail(check, detail)

    if not isinstance(pred, dict):
        ledger.fail(check, "predicate is not an object")
        return False

    if pred.get("predicate_type") != PREDICATE_TYPE:
        bad(f"predicate_type is {pred.get('predicate_type')!r}, required {PREDICATE_TYPE!r}")
    if not _is_nonempty_str(pred.get("action_id")):
        bad("action_id missing or not a non-empty string")
    if not _is_nonempty_str(pred.get("action_type")):
        bad("action_type missing or not a non-empty string")

    actor = pred.get("actor")
    if not isinstance(actor, dict):
        bad("actor missing or not an object")
    else:
        if not _is_nonempty_str(actor.get("actor_id")):
            bad("actor.actor_id missing or not a non-empty string")
        if not _is_nonempty_str(actor.get("display_name")):
            bad("actor.display_name missing or not a non-empty string")
        # CANON Law 3: literally false. Checked here as structure and again
        # as its own named check so the verdict line is unmistakable.
        if actor.get("is_service_account") is not False:
            bad(
                f"actor.is_service_account is {actor.get('is_service_account')!r}; "
                "the literal false is required (Law 3: receipts record natural persons)"
            )

    sec = pred.get("side_effect_class")
    if sec not in SIDE_EFFECT_CLASSES:
        bad(
            f"side_effect_class {sec!r} not in the four never-collapsed classes "
            f"{SIDE_EFFECT_CLASSES} (Law 6)"
        )

    evidence = pred.get("evidence")
    if not isinstance(evidence, list):
        bad("evidence missing or not a list")
    else:
        for i, item in enumerate(evidence):
            if not isinstance(item, dict):
                bad(f"evidence[{i}] is not an object")
                continue
            if not _is_nonempty_str(item.get("evidence_id")):
                bad(f"evidence[{i}].evidence_id missing or empty")
            if not _is_nonempty_str(item.get("kind")):
                bad(f"evidence[{i}].kind missing or empty")
            if not _is_sha256_hex(item.get("sha256")):
                bad(f"evidence[{i}].sha256 is not 64 lowercase hex characters")

    completeness = pred.get("completeness")
    if completeness not in COMPLETENESS_STATES:
        bad(f"completeness {completeness!r} not in {COMPLETENESS_STATES}")
    if isinstance(evidence, list) and not evidence and completeness == "COMPLETE":
        bad("evidence is empty but completeness is COMPLETE (Law 4 violation, structural)")

    rcs = pred.get("redaction_commitments")
    if not isinstance(rcs, list):
        bad("redaction_commitments missing or not a list")
    else:
        for i, rc in enumerate(rcs):
            if not isinstance(rc, dict):
                bad(f"redaction_commitments[{i}] is not an object")
                continue
            for field_name in ("commitment_id", "field_path"):
                if not _is_nonempty_str(rc.get(field_name)):
                    bad(f"redaction_commitments[{i}].{field_name} missing or empty")
            for field_name in ("salt_b64", "sha256_b64"):
                value = rc.get(field_name)
                if not isinstance(value, str):
                    bad(f"redaction_commitments[{i}].{field_name} missing or not a string")
                    continue
                try:
                    base64.b64decode(value, validate=True)
                except (binascii.Error, ValueError):
                    bad(f"redaction_commitments[{i}].{field_name} is not valid base64")

    # rfc3161_token and ntp_synced: absence is a time-strength matter
    # (check h), not a hard structural failure — a receipt recorded during a
    # TSA outage must still parse. But the wrong *type* is structural.
    if "rfc3161_token" in pred and not isinstance(pred.get("rfc3161_token"), str):
        bad("rfc3161_token present but not a string")
    if "ntp_synced" in pred and not isinstance(pred.get("ntp_synced"), bool):
        bad("ntp_synced present but not a boolean")

    if ok:
        ledger.info(check, "predicate structurally valid (szl.dev/GovernedAction/v1)")
    return ok


def check_receipt_envelope_fields(receipt: dict, ledger: Ledger, where: str) -> None:
    """Receipt-level fields around the predicate."""
    check = f"receipt[{where}]"
    ok = True
    if not _is_nonempty_str(receipt.get("receipt_id")):
        ok = False
        ledger.fail(check, "receipt_id missing or empty")
    decision = receipt.get("decision")
    if not isinstance(decision, dict) or decision.get("decision") not in DECISIONS:
        ok = False
        ledger.fail(check, f"decision.decision not in {DECISIONS}")
    retention = receipt.get("retention_days")
    if not isinstance(retention, int) or isinstance(retention, bool):
        ok = False
        ledger.fail(check, "retention_days missing or not an integer")
    elif retention < RETENTION_FLOOR_DAYS:
        ok = False
        ledger.fail(
            check,
            f"retention_days {retention} below the 180-day floor (Law 10)",
        )
    if not _is_nonempty_str(receipt.get("issued_at")):
        ok = False
        ledger.fail(check, "issued_at missing or empty")
    # CANON Law 6: IRREVERSIBLE always requires human approval.
    pred = receipt.get("predicate") if isinstance(receipt.get("predicate"), dict) else {}
    if (
        pred.get("side_effect_class") == "IRREVERSIBLE"
        and isinstance(decision, dict)
        and decision.get("decision") == "ALLOW"
        and receipt.get("human_approval") is None
    ):
        ok = False
        ledger.fail(check, "IRREVERSIBLE action ALLOWed without human approval (Law 6)")
    if ok:
        ledger.info(check, "receipt envelope fields valid")


# ---------------------------------------------------------------------------
# The named law checks
# ---------------------------------------------------------------------------


def check_law3_service_account(pred: dict, ledger: Ledger, where: str) -> None:
    """CANON Law 3 as a standalone verdict line: literally false, or FAIL."""
    value = (pred.get("actor") or {}).get("is_service_account")
    if value is False:
        ledger.info(f"law3-natural-person[{where}]", "actor.is_service_account is false")
    else:
        ledger.fail(
            f"law3-natural-person[{where}]",
            f"actor.is_service_account is {value!r}, not the literal false — "
            "a receipt cannot erase the natural persons involved",
        )


def check_law4_evidence(receipt: dict, pred: dict, ledger: Ledger, where: str) -> None:
    """CANON Law 4: missing evidence implies INCOMPLETE, never PASS."""
    check = f"law4-evidence[{where}]"
    evidence = pred.get("evidence") if isinstance(pred.get("evidence"), list) else []
    obligations = []
    decision = receipt.get("decision")
    if isinstance(decision, dict) and isinstance(decision.get("evidence_obligations"), list):
        obligations = [o for o in decision["evidence_obligations"] if isinstance(o, str)]

    missing = []
    if obligations:
        present_kinds = {
            item.get("kind") for item in evidence if isinstance(item, dict)
        }
        missing = [o for o in obligations if o not in present_kinds]

    if not evidence:
        ledger.inc(check, "no evidence items on the predicate — INCOMPLETE, never PASS")
        return
    if missing:
        ledger.inc(
            check,
            f"missing evidence obligations: {', '.join(missing)} — INCOMPLETE, never PASS",
        )
        return
    if pred.get("completeness") == "INCOMPLETE":
        ledger.inc(
            check,
            "predicate declares completeness INCOMPLETE — verdict capped at INCOMPLETE",
        )
        return
    ledger.info(check, f"{len(evidence)} evidence item(s); all declared obligations present")


def check_honest_time(pred: dict, ledger: Ledger, where: str) -> None:
    """Check (h): weak time proof caps the verdict at INCOMPLETE."""
    check = f"honest-time[{where}]"
    token = pred.get("rfc3161_token")
    ntp = pred.get("ntp_synced")
    reasons = []
    if token is None:
        reasons.append("rfc3161_token absent")
    elif token == TIME_PROOF_UNAVAILABLE:
        reasons.append("rfc3161_token recorded as UNAVAILABLE")
    if ntp is not True:
        reasons.append(f"ntp_synced is {ntp!r}, not true")
    if reasons:
        ledger.inc(
            check,
            "weak time proof (" + "; ".join(reasons) + ") — disclosed, never hidden; "
            "verdict capped at INCOMPLETE",
        )
    else:
        ledger.info(check, "RFC 3161 token present and host clock NTP-synced")


def check_redaction_commitments(
    pred: dict, disclosures: dict, ledger: Ledger, where: str
) -> None:
    """Check (g): recompute salted-hash commitments against disclosed plaintexts."""
    rcs = pred.get("redaction_commitments")
    if not isinstance(rcs, list) or not rcs:
        ledger.info(f"redaction[{where}]", "no redaction commitments on this predicate")
        return
    for rc in rcs:
        if not isinstance(rc, dict):
            continue  # structural check already flagged it
        cid = rc.get("commitment_id", "?")
        check = f"redaction[{where}:{cid}]"
        disclosure = disclosures.get(cid)
        if disclosure is None:
            ledger.inc(
                check,
                "UNVERIFIED_NO_DISCLOSURE: commitment present but the bundle carries "
                "no disclosed plaintext for it — redaction cannot silently "
                "strengthen a verdict; capped at INCOMPLETE",
            )
            continue
        if not isinstance(disclosure, dict) or not isinstance(disclosure.get("plaintext_b64"), str):
            ledger.fail(check, "disclosure entry malformed (plaintext_b64 missing)")
            continue
        try:
            salt = base64.b64decode(rc.get("salt_b64", ""), validate=True)
            committed = base64.b64decode(rc.get("sha256_b64", ""), validate=True)
            plaintext = base64.b64decode(disclosure["plaintext_b64"], validate=True)
        except (binascii.Error, ValueError) as exc:
            ledger.fail(check, f"base64 decode failed: {exc}")
            continue
        recomputed = hashlib.sha256(salt + b"\x00" + plaintext).digest()
        if recomputed == committed:
            ledger.info(
                check,
                f"recomputed SHA-256(salt||0x00||plaintext) matches commitment for "
                f"{rc.get('field_path', '?')}",
            )
        else:
            ledger.fail(
                check,
                "disclosed plaintext does NOT match the committed hash — the "
                "commitment and the disclosure disagree (tamper or substitution)",
            )


# ---------------------------------------------------------------------------
# Bundle-level verification
# ---------------------------------------------------------------------------


def _payload_of(receipt_entry: dict):
    """Return (payload_dict, error). The payload is receipt['payload'] if
    present, else the receipt entry itself minus verifier-side wrapper keys."""
    if not isinstance(receipt_entry, dict):
        return None, "receipt entry is not an object"
    payload = receipt_entry.get("payload")
    if payload is None:
        # bare receipt: the entry minus wrapper keys IS the payload
        payload = {
            k: v
            for k, v in receipt_entry.items()
            if k not in ("payload_sha256", "signature", "chain")
        }
    if not isinstance(payload, dict):
        return None, "payload is not an object"
    return payload, None


def verify_bundle(bundle: dict, ledger: Ledger) -> None:
    # -- bundle envelope -----------------------------------------------------
    if not isinstance(bundle, dict):
        ledger.fail("bundle", "top level is not a JSON object")
        return
    if bundle.get("bundle_type") != BUNDLE_TYPE:
        ledger.fail(
            "bundle", f"bundle_type is {bundle.get('bundle_type')!r}, required {BUNDLE_TYPE!r}"
        )
    else:
        ledger.info("bundle", f"bundle_type {BUNDLE_TYPE}")
    receipts = bundle.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        ledger.fail("bundle", "receipts missing, not a list, or empty")
        return
    disclosures = bundle.get("redaction_disclosures")
    if disclosures is None:
        disclosures = {}
    if not isinstance(disclosures, dict):
        ledger.fail("bundle", "redaction_disclosures present but not an object")
        disclosures = {}

    payload_hashes: list[str | None] = []
    sequences: list[int | None] = []

    for index, entry in enumerate(receipts):
        where = f"{index}"
        payload, error = _payload_of(entry)
        if payload is None:
            ledger.fail(f"payload[{where}]", error)
            payload_hashes.append(None)
            sequences.append(None)
            continue

        # (a) structure + receipt-level fields
        pred = payload.get("predicate")
        struct_ok = isinstance(pred, dict) and check_predicate_structure(pred, ledger, where)
        check_receipt_envelope_fields(payload, ledger, where)

        # (c) Law 3 as its own verdict line
        if isinstance(pred, dict):
            check_law3_service_account(pred, ledger, where)

        # (d) integrity recompute
        recorded = entry.get("payload_sha256")
        check = f"integrity[{where}]"
        recomputed = None
        try:
            recomputed = hashlib.sha256(canonical_json(payload)).hexdigest()
        except ValueError as exc:
            ledger.fail(check, f"payload cannot be canonicalized: {exc}")
        if recomputed is not None:
            if not _is_sha256_hex(recorded):
                ledger.fail(check, "recorded payload_sha256 missing or not 64 lowercase hex")
            elif recorded != recomputed:
                ledger.fail(
                    check,
                    f"recomputed {recomputed[:16]}... != recorded {recorded[:16]}... "
                    "— artifact altered",
                )
            else:
                ledger.info(check, f"canonical JSON -> SHA-256 matches recorded hash")
        payload_hashes.append(recomputed if recomputed == recorded else None)

        # evidence item self-hashes
        if isinstance(pred, dict) and isinstance(pred.get("evidence"), list):
            for i, item in enumerate(pred["evidence"]):
                if not isinstance(item, dict):
                    continue
                content_b64 = item.get("content_b64")
                if content_b64 is None:
                    continue
                echeck = f"evidence-integrity[{where}:{item.get('evidence_id', i)}]"
                try:
                    content = base64.b64decode(content_b64, validate=True)
                except (binascii.Error, ValueError) as exc:
                    ledger.fail(echeck, f"content_b64 decode failed: {exc}")
                    continue
                if hashlib.sha256(content).hexdigest() == item.get("sha256"):
                    ledger.info(echeck, "disclosed evidence content matches recorded sha256")
                else:
                    ledger.fail(echeck, "disclosed evidence content does NOT match recorded sha256")

        # (b) Law 4
        if struct_ok:
            check_law4_evidence(payload, pred, ledger, where)

        # (g) redaction commitments
        if isinstance(pred, dict):
            check_redaction_commitments(pred, disclosures, ledger, where)

        # (h) honest time
        if isinstance(pred, dict):
            check_honest_time(pred, ledger, where)

        # (e) signature
        sig = entry.get("signature")
        check = f"signature[{where}]"
        if sig is None:
            ledger.inc(
                check,
                "UNSIGNED: no signature on this receipt — integrity rests on the "
                "payload hash alone; capped at INCOMPLETE",
            )
        elif not isinstance(sig, dict):
            ledger.fail(check, "signature present but not an object")
        elif sig.get("scheme") != "ed25519-dsse":
            ledger.inc(
                check,
                f"signature scheme {sig.get('scheme')!r} not verifiable by this "
                "reference verifier — counted as unverified, capped at INCOMPLETE",
            )
        else:
            try:
                payload_bytes = canonical_json(payload)
            except ValueError as exc:
                ledger.fail(check, f"payload cannot be canonicalized for PAE: {exc}")
                sequences.append(_seq_of(entry, ledger, where))
                continue
            status, detail = verify_dsse_signature(
                sig.get("payload_type", ""),
                payload_bytes,
                sig.get("sig_b64", ""),
                sig.get("public_key_b64", ""),
            )
            if status == "valid":
                ledger.info(check, detail)
            elif status == "no_crypto":
                ledger.inc(check, detail + " — capped at INCOMPLETE")
            else:
                ledger.fail(check, detail)

        sequences.append(_seq_of(entry, ledger, where))

    # (f) chain / sequence across receipts
    check = "chain"
    if len(receipts) == 1:
        seqs = [s for s in sequences if s is not None]
        if sequences and sequences[0] not in (None, 1):
            ledger.fail(check, f"single-receipt bundle has sequence {sequences[0]}, expected 1")
        else:
            ledger.info(check, "single receipt; no chain to check")
        return
    problems = []
    if any(s is None for s in sequences):
        problems.append("at least one receipt is missing a chain.sequence")
    else:
        if sequences[0] != 1:
            problems.append(f"chain starts at sequence {sequences[0]}, expected 1")
        for i in range(1, len(sequences)):
            if sequences[i] != sequences[i - 1] + 1:
                problems.append(
                    f"sequence gap or reordering between receipts {i - 1} and {i}: "
                    f"{sequences[i - 1]} -> {sequences[i]}"
                )
    for i in range(1, len(receipts)):
        entry = receipts[i]
        chain = entry.get("chain") if isinstance(entry, dict) else None
        prev_recorded = chain.get("prev_payload_sha256") if isinstance(chain, dict) else None
        prev_actual = payload_hashes[i - 1]
        if prev_recorded is None:
            problems.append(f"receipt {i} carries no prev_payload_sha256 link")
        elif prev_actual is None:
            problems.append(
                f"receipt {i - 1} payload hash did not verify; cannot confirm link from receipt {i}"
            )
        elif prev_recorded != prev_actual:
            problems.append(
                f"receipt {i} prev_payload_sha256 does not match receipt {i - 1} — chain broken"
            )
    if problems:
        for p in problems:
            ledger.fail(check, p)
    else:
        ledger.info(
            check,
            f"{len(receipts)} receipts, sequences 1..{len(receipts)}, all prev-hash links verified",
        )


def _seq_of(entry: dict, ledger: Ledger, where: str):
    chain = entry.get("chain")
    if chain is None:
        return None
    if not isinstance(chain, dict) or not isinstance(chain.get("sequence"), int) or isinstance(
        chain.get("sequence"), bool
    ):
        ledger.fail(f"chain[{where}]", "chain present but sequence missing or not an integer")
        return None
    return chain["sequence"]


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def verify_file(path: Path) -> tuple[Ledger, int]:
    ledger = Ledger()
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"a11oy_verify: cannot read {path}: {exc}", file=sys.stderr)
        return ledger, EXIT_USAGE
    try:
        bundle = strict_json_loads(text)
    except _DuplicateKeyError as exc:
        ledger.fail("parse", f"{exc} — canonical JSON never contains duplicate keys")
        bundle = None
    except ValueError as exc:
        print(f"a11oy_verify: {path} is not valid JSON: {exc}", file=sys.stderr)
        return ledger, EXIT_USAGE
    if bundle is not None:
        verify_bundle(bundle, ledger)
    print(f"a11oy_verify {VERSION} — {path}")
    print(ledger.render())
    print(f"FINAL: {ledger.verdict}")
    return ledger, ledger.exit_code


# ---------------------------------------------------------------------------
# Self-test: fabricate a valid bundle, tamper it six ways, assert verdicts
# ---------------------------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def _redaction_commitment(commitment_id: str, field_path: str, plaintext: bytes, salt: bytes):
    digest = hashlib.sha256(salt + b"\x00" + plaintext).digest()
    return (
        {
            "commitment_id": commitment_id,
            "field_path": field_path,
            "salt_b64": _b64(salt),
            "sha256_b64": _b64(digest),
        },
        {commitment_id: {"plaintext_b64": _b64(plaintext)}},
    )


def _demo_receipt(action_id: str, issued_at: str, strong_time: bool = True) -> dict:
    """A receipt payload shaped exactly like the master predicate/receipt."""
    rc, disclosure = _redaction_commitment(
        f"rc-{action_id}", "$.predicate.action_id", action_id.encode("utf-8"), b"salt-" + action_id.encode("utf-8").ljust(11, b"0")[:11]
    )
    evidence_content = f"evidence for {action_id}".encode("utf-8")
    return {
        "receipt_id": f"rcpt-{action_id}",
        "predicate": {
            "predicate_type": PREDICATE_TYPE,
            "action_id": action_id,
            "actor": {
                "actor_id": "u-stephen-lutar",
                "display_name": "Stephen Lutar",
                "is_service_account": False,
            },
            "action_type": "deploy.patch",
            "side_effect_class": "REVERSIBLE",
            "evidence": [
                {
                    "evidence_id": "ev-git-diff",
                    "kind": "git-diff-hash",
                    "sha256": hashlib.sha256(evidence_content).hexdigest(),
                    "content_b64": _b64(evidence_content),
                },
                {
                    "evidence_id": "ev-test-output",
                    "kind": "test-output-hash",
                    "sha256": hashlib.sha256(b"pytest: 16/16 OK").hexdigest(),
                },
            ],
            "completeness": "COMPLETE",
            "redaction_commitments": [rc],
            "rfc3161_token": _b64(b"self-test-tsa-token") if strong_time else TIME_PROOF_UNAVAILABLE,
            "ntp_synced": strong_time,
        },
        "decision": {
            "decision": "ALLOW",
            "reason": "matched rule allow-deploy",
            "first_match_rule": "allow-deploy",
            "matched_rules": ["allow-deploy"],
            "evidence_obligations": ["git-diff-hash", "test-output-hash"],
            "effective_side_effect_class": "REVERSIBLE",
            "requires_human_approval": True,
        },
        "human_approval": {
            "approver": {
                "actor_id": "u-stephen-lutar",
                "display_name": "Stephen Lutar",
                "is_service_account": False,
            },
            "approved_at": issued_at,
            "rationale": "diff reviewed, tests passed, rollback plan attached",
        },
        "observation_window": {"start": issued_at, "end": issued_at},
        "retention_days": RETENTION_FLOOR_DAYS,
        "issued_at": issued_at,
        "generator": f"a11oy_verify self-test/{VERSION}",
    }, disclosure


def _sign_entry(entry: dict, private_key) -> None:
    """Attach an ed25519-dsse signature to a receipt entry (PAE-exact)."""
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PublicFormat,
    )

    payload_bytes = canonical_json(entry["payload"])
    payload_type = "application/vnd.in-toto+json"
    signature = private_key.sign(pae(payload_type.encode("utf-8"), payload_bytes))
    public_raw = private_key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    entry["signature"] = {
        "scheme": "ed25519-dsse",
        "payload_type": payload_type,
        "sig_b64": _b64(signature),
        "public_key_b64": _b64(public_raw),
        "keyid": hashlib.sha256(public_raw).hexdigest()[:16],
    }


def _build_valid_bundle(count: int = 1):
    """Build a well-formed bundle of `count` chained receipts, signed if
    cryptography is available. Returns (bundle, disclosures)."""
    from datetime import timedelta

    disclosures = {}
    entries = []
    private_key = None
    Ed25519PrivateKey = None
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as _E

        Ed25519PrivateKey = _E
        private_key = _E.generate()
    except ImportError:
        pass

    base_time = datetime(2026, 8, 30, 12, 0, 0, tzinfo=timezone.utc)
    prev_hash = None
    for i in range(count):
        action_id = f"act-self-test-{i + 1:04d}"
        issued = (base_time + timedelta(minutes=i)).isoformat().replace("+00:00", "Z")
        payload, disclosure = _demo_receipt(action_id, issued)
        disclosures.update({k: v for k, v in disclosure.items()})
        entry = {"payload": payload}
        entry["payload_sha256"] = hashlib.sha256(canonical_json(payload)).hexdigest()
        entry["chain"] = {"sequence": i + 1, "prev_payload_sha256": prev_hash}
        prev_hash = entry["payload_sha256"]
        if private_key is not None:
            _sign_entry(entry, private_key)
        entries.append(entry)

    return {
        "bundle_type": BUNDLE_TYPE,
        "bundle_id": f"bundle-{uuid.uuid4()}",
        "created_at": base_time.isoformat().replace("+00:00", "Z"),
        "generator": f"a11oy_verify self-test/{VERSION}",
        "receipts": entries,
        "redaction_disclosures": disclosures,
    }


def _verdict_of(bundle: dict) -> str:
    ledger = Ledger()
    verify_bundle(bundle, ledger)
    return ledger.verdict


def _tamper_byte_flip(bundle: dict) -> dict:
    """Exactly one byte of the first receipt's payload changed (the last
    character of action_id), with the recorded hash and signature left stale —
    integrity recompute must catch it."""
    t = copy.deepcopy(bundle)
    pred = t["receipts"][0]["payload"]["predicate"]
    pred["action_id"] = pred["action_id"][:-1] + "X"  # one byte
    return t


def _tamper_evidence_removal(bundle: dict) -> dict:
    """Strip all evidence and re-hash honestly: a well-formed bundle whose
    claim is unsupported — Law 4 must cap it at INCOMPLETE, never PASS."""
    t = copy.deepcopy(bundle)
    for entry in t["receipts"]:
        pred = entry["payload"]["predicate"]
        pred["evidence"] = []
        pred["completeness"] = "INCOMPLETE"
        entry["payload_sha256"] = hashlib.sha256(canonical_json(entry["payload"])).hexdigest()
        entry.pop("signature", None)  # cannot re-sign; unsigned is itself INCOMPLETE
    return t


def _tamper_service_account(bundle: dict) -> dict:
    t = copy.deepcopy(bundle)
    t["receipts"][0]["payload"]["predicate"]["actor"]["is_service_account"] = True
    t["receipts"][0]["payload_sha256"] = hashlib.sha256(
        canonical_json(t["receipts"][0]["payload"])
    ).hexdigest()
    t["receipts"][0].pop("signature", None)
    return t


def _tamper_sequence_gap(bundle: dict) -> dict:
    """A three-receipt chain with the middle receipt removed: 1 -> 3."""
    t = copy.deepcopy(bundle)
    t["receipts"] = [t["receipts"][0], t["receipts"][2]]
    return t


def _tamper_redaction_cheat(bundle: dict) -> dict:
    """Substitute a different plaintext under an existing commitment: the
    recomputed digest must not match."""
    t = copy.deepcopy(bundle)
    cid = t["receipts"][0]["payload"]["predicate"]["redaction_commitments"][0]["commitment_id"]
    t["redaction_disclosures"][cid] = {"plaintext_b64": _b64(b"act-forged-9999")}
    return t


def _tamper_weak_time(bundle: dict) -> dict:
    t = copy.deepcopy(bundle)
    for entry in t["receipts"]:
        pred = entry["payload"]["predicate"]
        pred["rfc3161_token"] = TIME_PROOF_UNAVAILABLE
        pred["ntp_synced"] = False
        entry["payload_sha256"] = hashlib.sha256(canonical_json(entry["payload"])).hexdigest()
        entry.pop("signature", None)
    return t


def run_self_test(out_dir: Path | None) -> int:
    print(f"a11oy_verify {VERSION} --self-test")
    if _try_import_ed25519() is None:
        print(
            "note: cryptography not importable; self-test bundles will be UNSIGNED "
            "and the valid bundle's expected verdict degrades to INCOMPLETE"
        )
    have_crypto = _try_import_ed25519() is not None

    cases: list[tuple[str, dict, str]] = []
    valid_single = _build_valid_bundle(1)
    valid_chain = _build_valid_bundle(3)

    cases.append(("valid", valid_single, "PASS" if have_crypto else "INCOMPLETE"))
    cases.append(("tampered_byte_flip", _tamper_byte_flip(valid_single), "FAIL"))
    cases.append(("tampered_evidence_removal", _tamper_evidence_removal(valid_single), "INCOMPLETE"))
    cases.append(("tampered_service_account", _tamper_service_account(valid_single), "FAIL"))
    cases.append(("tampered_sequence_gap", _tamper_sequence_gap(valid_chain), "FAIL"))
    cases.append(("tampered_redaction_cheat", _tamper_redaction_cheat(valid_single), "FAIL"))
    cases.append(("tampered_weak_time", _tamper_weak_time(valid_single), "INCOMPLETE"))
    cases.append(("valid_chain", valid_chain, "PASS" if have_crypto else "INCOMPLETE"))

    failures = 0
    written = []
    for name, bundle, expected in cases:
        actual = _verdict_of(bundle)
        ok = actual == expected
        if not ok:
            failures += 1
        print(f"{'ok  ' if ok else 'BAD '} {name:28} expected {expected:10} got {actual}")
        if out_dir is not None:
            out_dir.mkdir(parents=True, exist_ok=True)
            path = out_dir / f"{name}.json"
            path.write_text(
                json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            written.append(path)

    if out_dir is not None:
        manifest = {
            "bundle_type": "szl.dev/VerifierTestVectorManifest/v1",
            "generator": f"a11oy_verify self-test/{VERSION}",
            "note": "Verdicts below assume the cryptography package is importable. "
            "On a bare python3 the signature check reports "
            "SIGNATURE_UNVERIFIED_NO_CRYPTO and signed-bundle verdicts degrade "
            "from PASS to INCOMPLETE — never to a wrong PASS.",
            "vectors": [
                {"file": f"{name}.json", "expected_verdict": expected}
                for name, _, expected in cases
            ],
        }
        manifest_path = out_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        written.append(manifest_path)
        for path in written:
            print(f"wrote {path}")

    if failures:
        print(f"SELF-TEST FAIL: {failures} case(s) produced the wrong verdict")
        return EXIT_FAIL
    print(f"SELF-TEST PASS: {len(cases)}/{len(cases)} cases produced the expected verdict")
    return EXIT_PASS


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline verifier for a11oy receipt bundles (szl.dev/GovernedAction/v1)."
    )
    parser.add_argument("bundle", nargs="?", help="path to a receipt bundle JSON file")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="fabricate a valid bundle, tamper it six ways, assert verdicts",
    )
    parser.add_argument(
        "--vectors-out",
        default=None,
        help="with --self-test: directory for the eight test-vector bundles "
        "(default: ./test_vectors)",
    )
    parser.add_argument("--version", action="version", version=f"a11oy_verify {VERSION}")
    args = parser.parse_args(argv)

    if args.self_test:
        out_dir = Path(args.vectors_out) if args.vectors_out else Path("test_vectors")
        return run_self_test(out_dir)
    if not args.bundle:
        parser.print_help()
        return EXIT_USAGE
    _, code = verify_file(Path(args.bundle))
    return code


if __name__ == "__main__":
    sys.exit(main())
