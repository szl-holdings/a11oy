#!/usr/bin/env python3
"""verify_chain_offline.py — offline verifier for SZL DSSE receipt chains.

Verifies a published receipt bundle with NO network access:

  1. Every DSSE envelope signature is checked against a trusted local
     public key (ECDSA P-256 / SHA-256, the estate signing scheme —
     Sigstore cosign default).
  2. The hash chain is replayed: each beat's payload carries
     prev_beat_hash == prior beat_hash, where
     beat_hash = sha256(PAE(payloadType, payload)).
  3. The final beat_hash must equal the bundle's expected root.

Fails closed: any signature, link, digest, or canonical-encoding
mismatch aborts with CHAIN FAILED and a non-zero exit code.

Usage:
  python examples/verify_chain_offline.py \
      --bundle examples/offline-verify-sample/bundle.json \
      --pubkey examples/offline-verify-sample/pubkey.pem

Exit codes: 0 = CHAIN OK (and, with --manifest, SIGNER ANCHORED),
            1 = verification failed, 2 = usage/IO error,
            3 = SIGNER UNKNOWN (integrity OK, key not in the trust manifest; abstain),
            4 = SIGNER REVOKED / NOT VALID AT SIGNING TIME (manifest lifecycle),
            5 = STALE (integrity OK, newest beat older than --max-age-days; abstain).
Precedence when several apply: 1 > 4 > 3 > 5 > 0.
Only dependency: `cryptography` (already used by szl-receipt / szl_dsse.py).
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography import x509  # noqa: F401  (imported for parity with szl_dsse)
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

LEGACY_KEYIDS = {"szlholdings-cosign"}
GENESIS_ZERO = "0" * 64
KEY_STATUSES = {"active", "retired", "revoked"}

EXIT_OK, EXIT_FAIL, EXIT_USAGE = 0, 1, 2
EXIT_SIGNER_UNKNOWN, EXIT_SIGNER_INVALID, EXIT_STALE = 3, 4, 5


class ChainError(Exception):
    """Any verification failure. Fail closed."""


def pae(payload_type: bytes, body: bytes) -> bytes:
    """DSSE v1 pre-auth encoding: "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body."""
    return (
        b"DSSEv1 "
        + str(len(payload_type)).encode("ascii")
        + b" "
        + payload_type
        + b" "
        + str(len(body)).encode("ascii")
        + b" "
        + body
    )


def canonical_json(obj) -> bytes:
    """Canonical JSON: sorted keys, tight separators, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def normalize_pem(pem_bytes: bytes) -> bytes:
    """Normalize a PEM for fingerprinting: LF endings, single trailing newline."""
    text = pem_bytes.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    return (text.strip() + "\n").encode("utf-8")


def key_fingerprint(pem_bytes: bytes) -> str:
    """Estate keyid convention: SHA-256 of the normalized public PEM."""
    return hashlib.sha256(normalize_pem(pem_bytes)).hexdigest()


def key_fingerprints(pem_bytes: bytes) -> set:
    """Every fingerprint spelling in use for one key.

    The offline sample uses SHA-256 of the normalized PEM *with* a trailing
    newline (key_fingerprint above). The live runtime signer (szl_dsse
    public_key_fingerprint) and .github/cosign-keys/MANIFEST.json use SHA-256 of
    the stripped PEM *without* it. Both name the same key, so both are accepted
    as a keyid match; neither changes what the signature check proves.
    """
    stripped = normalize_pem(pem_bytes).rstrip(b"\n")
    return {key_fingerprint(pem_bytes), hashlib.sha256(stripped).hexdigest()}


def manifest_entry(pem_bytes: bytes, manifest: dict):
    """Return (name, entry) for the manifest entry whose fingerprint names this key."""
    if not isinstance(manifest, dict):
        raise ChainError("trust manifest must be a JSON object")
    organs = manifest.get("organs", {})
    if not isinstance(organs, dict):
        raise ChainError("trust manifest organs must be a JSON object")
    # Validate the entire trust-root structure before using any entry.
    # An invalid, unrelated entry cannot be ignored by finding the key first.
    for name, entry in organs.items():
        if not isinstance(entry, dict):
            raise ChainError(f"trust manifest organ {name!r} must be a JSON object")
        fingerprint = entry.get("fingerprint_sha256")
        if fingerprint is not None and not isinstance(fingerprint, str):
            raise ChainError(f"trust manifest organ {name!r} has non-string fingerprint")
    fprs = key_fingerprints(pem_bytes)
    for name, entry in organs.items():
        if entry.get("fingerprint_sha256") in fprs:
            return name, entry
    return None, None


def manifest_signer(pem_bytes: bytes, manifest: dict):
    """Return the manifest entry name whose fingerprint names this key, else None."""
    return manifest_entry(pem_bytes, manifest)[0]


def parse_ts(value, what: str) -> datetime:
    """Parse an RFC 3339 UTC timestamp ('...Z' or '+00:00'). Fail closed otherwise."""
    if not isinstance(value, str) or not value:
        raise ChainError(f"{what}: missing or non-string timestamp")
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ChainError(f"{what}: {value!r} is not an RFC 3339 timestamp")
    if dt.tzinfo is None:
        raise ChainError(f"{what}: {value!r} has no timezone (UTC required)")
    return dt.astimezone(timezone.utc)


def lifecycle_problem(entry: dict, first_ts: datetime, last_ts: datetime):
    """Check optional key-lifecycle fields on a manifest entry.

    Optional fields (manifest v1 entries without them behave as before):
      status      "active" (default) | "retired" | "revoked"
      not_before  RFC 3339; no beat may claim to be signed earlier
      not_after   RFC 3339; no beat may claim to be signed later (set on retirement)
      revoked_at  RFC 3339; informational - a revoked key fails regardless of beat
                  times, because beat timestamps are self-asserted by the signer and a
                  compromised key can backdate them.
    Returns (verdict, message) or (None, None). Unknown status values fail closed.
    """
    status = entry.get("status", "active")
    if not isinstance(status, str) or status not in KEY_STATUSES:
        return "SIGNER_NOT_VALID_AT_TIME", f"unrecognized key status {status!r} (fail closed)"
    if status == "revoked":
        when = entry.get("revoked_at") or "unknown time"
        return "SIGNER_REVOKED", f"key revoked at {when}; do not trust receipts it signed"
    nb, na = entry.get("not_before"), entry.get("not_after")
    if nb is not None and first_ts < parse_ts(nb, "manifest not_before"):
        return "SIGNER_NOT_VALID_AT_TIME", f"earliest beat {first_ts.isoformat()} is before key not_before {nb}"
    if na is not None and last_ts > parse_ts(na, "manifest not_after"):
        return "SIGNER_NOT_VALID_AT_TIME", f"latest beat {last_ts.isoformat()} is after key not_after {na}"
    if status == "retired" and na is None:
        return "SIGNER_NOT_VALID_AT_TIME", "key is retired but has no not_after; cannot bound its validity"
    return None, None


def load_public_key(path: Path):
    pem = path.read_bytes()
    try:
        key = serialization.load_pem_public_key(pem)
    except ValueError as exc:
        raise ChainError(f"{path}: not a valid PEM public key ({exc})")
    if not isinstance(key, ec.EllipticCurvePublicKey) or not isinstance(
        key.curve, ec.SECP256R1
    ):
        raise ChainError(f"{path}: trusted key is not ECDSA P-256 (secp256r1)")
    return key, pem


def verify_signature(envelope: dict, pubkey, pem: bytes, strict_keyid: bool) -> str:
    payload_type = envelope.get("payloadType")
    if not isinstance(payload_type, str) or not payload_type:
        raise ChainError("envelope missing payloadType")
    payload_b64 = envelope.get("payload")
    if not isinstance(payload_b64, str):
        raise ChainError("envelope missing payload")
    try:
        body = base64.b64decode(payload_b64, validate=True)
    except binascii.Error as exc:
        raise ChainError(f"payload is not valid base64 ({exc})")

    sigs = envelope.get("signatures") or []
    if not sigs:
        raise ChainError("envelope has no signatures")

    pae_bytes = pae(payload_type.encode("utf-8"), body)
    fpr = key_fingerprint(pem)
    keyid_note = ""
    verified = False
    last_err = "no signatures"
    for entry in sigs:
        sig_b64 = entry.get("sig")
        if not isinstance(sig_b64, str):
            continue
        try:
            sig = base64.b64decode(sig_b64, validate=True)
        except binascii.Error:
            last_err = "signature not valid base64"
            continue
        try:
            pubkey.verify(sig, pae_bytes, ec.ECDSA(hashes.SHA256()))
            verified = True
        except InvalidSignature:
            last_err = "ECDSA signature invalid"
            continue
        keyid = entry.get("keyid", "")
        if keyid == fpr or keyid in key_fingerprints(pem):
            keyid_note = "keyid matches key fingerprint"
        elif keyid in LEGACY_KEYIDS:
            keyid_note = f"legacy keyid {keyid!r} accepted (signature is what matters)"
        elif strict_keyid:
            raise ChainError(
                f"keyid {keyid!r} does not match trusted key fingerprint {fpr[:16]}…"
            )
        else:
            keyid_note = f"WARNING: keyid {keyid!r} != fingerprint {fpr[:16]}…"
        break
    if not verified:
        raise ChainError(last_err)
    return payload_type, body, keyid_note


def verify_chain(bundle: dict, pubkey, pem: bytes, strict_keyid: bool,
                 strict_canonical: bool, quiet: bool) -> dict:
    payload_type = bundle.get("payloadType")
    beats = bundle.get("beats")
    if not payload_type or not isinstance(beats, list) or not beats:
        raise ChainError("bundle must declare payloadType and a non-empty beats[] array")
    expected_root = (bundle.get("expected_root") or "").lower().removeprefix("sha256:")
    if len(expected_root) != 64:
        raise ChainError("bundle expected_root must be a 64-char sha256 hex digest")
    genesis = (bundle.get("genesis") or GENESIS_ZERO).lower().removeprefix("sha256:")

    running = genesis
    n = len(beats)
    stamps = []
    previous_stamp = None
    for i, env in enumerate(beats):
        pt, body, keyid_note = verify_signature(env, pubkey, pem, strict_keyid)
        if pt != payload_type:
            raise ChainError(
                f"beat {i}: payloadType {pt!r} != bundle payloadType {payload_type!r}"
            )
        try:
            payload_obj = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ChainError(f"beat {i}: payload is not UTF-8 JSON ({exc})")
        for field in ("seq", "prev_beat_hash", "receipt", "ts"):
            if field not in payload_obj:
                raise ChainError(f"beat {i}: payload missing field {field!r}")
        # Validate every signed beat, not only first/last. This ensures the
        # bounds are sufficient for subsequent manifest window checks.
        stamp = parse_ts(payload_obj["ts"], f"beat {i} ts")
        if previous_stamp is not None and stamp < previous_stamp:
            raise ChainError(f"beat {i}: timestamp predates the prior signed beat")
        previous_stamp = stamp
        stamps.append(payload_obj["ts"])
        if payload_obj["seq"] != i:
            raise ChainError(f"beat {i}: seq {payload_obj['seq']} != position {i}")
        if strict_canonical and canonical_json(payload_obj) != body:
            raise ChainError(f"beat {i}: payload is not canonical JSON (reorder/whitespace)")
        prev = str(payload_obj["prev_beat_hash"]).lower().removeprefix("sha256:")
        if prev != running:
            raise ChainError(f"beat {i}: prev_beat_hash breaks chain link")
        beat_hash = hashlib.sha256(pae(pt.encode("utf-8"), body)).hexdigest()
        if not quiet:
            print(f"[beat {i:>3}/{n}] sig OK · link OK · hash {beat_hash[:16]}…"
                  + (f" ({keyid_note})" if i == 0 and keyid_note else ""))
        running = beat_hash

    if running != expected_root:
        raise ChainError(
            f"chain root {running[:16]}… != expected_root {expected_root[:16]}…"
        )
    return {"beats": n, "root": running, "fingerprint": key_fingerprint(pem),
            "first_ts": stamps[0], "last_ts": stamps[-1]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Offline verifier for SZL DSSE receipt chains.")
    ap.add_argument("--bundle", required=True, type=Path, help="receipt bundle JSON")
    ap.add_argument("--pubkey", required=True, type=Path, help="trusted signer public key (PEM, P-256)")
    ap.add_argument("--strict-keyid", action="store_true",
                    help="require keyid == sha256(normalized PEM) (legacy keyids rejected)")
    ap.add_argument("--no-canonical-check", action="store_true",
                    help="skip canonical-JSON byte check on payloads")
    ap.add_argument("--quiet", action="store_true", help="suppress per-beat lines")
    ap.add_argument("--json", action="store_true", help="emit machine-readable verdict")
    ap.add_argument("--manifest", type=Path,
                    help="org trust manifest (.github/cosign-keys/MANIFEST.json); "
                         "if the key is not listed, report SIGNER UNKNOWN and exit 3; "
                         "honours optional status/not_before/not_after (exit 4)")
    ap.add_argument("--max-age-days", type=float, default=None,
                    help="report STALE (exit 5) if the newest beat is older than this")
    ap.add_argument("--now", default=None,
                    help="RFC 3339 'current time' for --max-age-days (testing/replay)")
    args = ap.parse_args(argv)

    def usage_error(message) -> int:
        if args.json:
            print(json.dumps({"ok": False, "verdict": "USAGE",
                              "exit_code": EXIT_USAGE, "error": str(message)}))
        else:
            print(f"error: {message}", file=sys.stderr)
        return EXIT_USAGE

    if args.max_age_days is not None and (
        not math.isfinite(args.max_age_days) or args.max_age_days < 0
    ):
        return usage_error("--max-age-days must be a finite nonnegative number")
    try:
        now_override = parse_ts(args.now, "--now") if args.now is not None else None
    except ChainError as exc:
        return usage_error(exc)

    try:
        bundle = json.loads(args.bundle.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot load bundle {args.bundle}: {exc}", file=sys.stderr)
        return 2
    try:
        pubkey, pem = load_public_key(args.pubkey)
    except (OSError, ChainError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    try:
        result = verify_chain(bundle, pubkey, pem,
                              strict_keyid=args.strict_keyid,
                              strict_canonical=not args.no_canonical_check,
                              quiet=args.quiet or args.json)
    except ChainError as exc:
        if args.json:
            print(json.dumps({"ok": False, "verdict": "FAIL", "exit_code": EXIT_FAIL,
                              "error": str(exc)}))
        else:
            print(f"CHAIN FAILED — {exc}", file=sys.stderr)
        return EXIT_FAIL

    verdict, code, notes = "PASS", EXIT_OK, []
    signer = None
    try:
        first = parse_ts(result["first_ts"], "beat 0 ts")
        last = parse_ts(result["last_ts"], f"beat {result['beats'] - 1} ts")
        stale = False
        if args.max_age_days is not None:
            now = now_override if now_override is not None else datetime.now(timezone.utc)
            age = now - last
            if age > timedelta(days=args.max_age_days):
                stale = True
                notes.append(f"newest beat is {age.days} days old (> {args.max_age_days:g})")
        if args.manifest is not None:
            try:
                manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"error: cannot load manifest {args.manifest}: {exc}", file=sys.stderr)
                return EXIT_USAGE
            signer, entry = manifest_entry(pem, manifest)
            if signer is None:
                verdict, code = "SIGNER_UNKNOWN", EXIT_SIGNER_UNKNOWN
            else:
                bad, msg = lifecycle_problem(entry, first, last)
                if bad:
                    verdict, code = bad, EXIT_SIGNER_INVALID
                    notes.append(msg)
        if stale and code == EXIT_OK:
            verdict, code = "STALE", EXIT_STALE
    except ChainError as exc:
        # At this stage the signed bundle has passed verification; the only
        # possible timestamp parse errors come from caller/trust-root metadata.
        return usage_error(exc)

    if args.json:
        out = {"ok": True, **result, "verdict": verdict, "exit_code": code}
        if args.manifest is not None:
            out["signer"] = signer or "UNKNOWN"
            out["signer_anchored"] = verdict in ("PASS", "STALE") and bool(signer)
        if notes:
            out["notes"] = notes
        print(json.dumps(out))
    else:
        print(f"CHAIN OK — {result['beats']} beats verified, root sha256:{result['root']}")
        print(f"signer fingerprint (sha256 of normalized PEM): {result['fingerprint']}")
        if args.manifest is not None:
            if verdict == "SIGNER_UNKNOWN":
                print("SIGNER UNKNOWN — integrity verified, but this key is not in the "
                      "trust manifest; treat the receipts as unauthenticated (abstain)")
            elif verdict == "SIGNER_REVOKED":
                print(f"SIGNER REVOKED — {signer!r}: {notes[-1]}")
            elif verdict == "SIGNER_NOT_VALID_AT_TIME":
                print(f"SIGNER NOT VALID AT SIGNING TIME — {signer!r}: {notes[-1]}")
            else:
                print(f"SIGNER ANCHORED — key listed in manifest as {signer!r}")
        if verdict == "STALE":
            print(f"STALE — {notes[0]}; integrity holds, but re-fetch a current "
                  "bundle before relying on it (abstain)")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
