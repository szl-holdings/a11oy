#!/usr/bin/env python3
# Signed-off-by: Forge (Replit task agent) <forge@szl-holdings>
"""Re-verify guard for the a11oy verifiable-corpus signed receipts.

Self-contained against the published records + the pinned public key, so it does
NOT depend on an expiring artifact. For every receipt it re-checks:
  * content-address integrity: id == sha256(canon({source,kind,content=payload}))
    (fail-loud on any tampered byte),
  * the DSSE signature still verifies over its PAE:
      - ecdsa-p256-dsse-pae : signatures[].sig vs the pinned cosign.pub,
      - sigstore-keyless-dsse: the bundle's dsseEnvelope sig vs its leaf cert,
        with the cert SAN matching the szl-holdings identity regex,
  * head-consistency: head.count == #records, head.last_id == last record id,
    no duplicate record ids / receipt_uids,
  * baseline floor: total >= reverify.min_receipts (an emptied corpus must NOT
    pass green). Empty corpus + no floor = honest soft-pass.

This complements rekor-recheck.yml (which re-checks Rekor transparency-log
inclusion); here we re-check the embedded signatures + integrity from the
published corpus alone.

Exit: 0 ok/soft-pass | 1 tamper/sig-fail/floor/head-mismatch | 2 auth/unreachable.

The crypto is isolated in `verify_record_signature`; the chain/integrity logic
is pure stdlib and `verify_fn` is injectable so the self-test runs offline.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys

import szl_corpus_guard_common as common
from szl_corpus_guard_common import (
    AuthError, Unreachable, EXIT_OK, EXIT_VIOLATION, EXIT_ERROR,
)


# --------------------------------------------------------------------------- #
# Signature verification (lazy cryptography import)                           #
# --------------------------------------------------------------------------- #
def _load_pub(pem: str):
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    return load_pem_public_key(pem.encode("utf-8"))


def _ecdsa_verify(pub, sig: bytes, msg: bytes) -> None:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    pub.verify(sig, msg, ec.ECDSA(hashes.SHA256()))


def verify_record_signature(rec, *, pubkey_pem, identity_regex):
    """Return (ok:bool, reason:str). Raises nothing for a bad signature —
    a failed verify is a finding, not an exception."""
    payload = rec.get("payload", {})
    scheme = payload.get("scheme")
    env = payload.get("envelope")
    if not scheme or not isinstance(env, dict):
        return False, "missing scheme/envelope"

    try:
        if scheme == "ecdsa-p256-dsse-pae":
            body = base64.b64decode(env["payload"])
            pae = common.dsse_pae(env["payloadType"], body)
            pub = _load_pub(pubkey_pem)
            sigs = env.get("signatures") or []
            if not sigs:
                return False, "no signatures"
            from cryptography.exceptions import InvalidSignature
            for s in sigs:
                try:
                    _ecdsa_verify(pub, base64.b64decode(s["sig"]), pae)
                except InvalidSignature:
                    return False, "ecdsa signature does not verify"
            return True, "ecdsa-p256 ok"

        if scheme == "sigstore-keyless-dsse":
            from cryptography import x509
            from cryptography.exceptions import InvalidSignature
            bundle = env.get("_sigstore", {}).get("bundle")
            if not bundle:
                return False, "missing sigstore bundle"
            vm = bundle.get("verificationMaterial", {})
            cert_b64 = (vm.get("certificate", {}) or {}).get("rawBytes")
            if not cert_b64:
                chain = (vm.get("x509CertificateChain", {}) or {}).get(
                    "certificates", [])
                cert_b64 = chain[0]["rawBytes"] if chain else None
            if not cert_b64:
                return False, "no leaf certificate in bundle"
            cert = x509.load_der_x509_certificate(base64.b64decode(cert_b64))
            san = cert.extensions.get_extension_for_class(
                x509.SubjectAlternativeName).value
            uris = san.get_values_for_type(x509.UniformResourceIdentifier)
            if not any(re.search(identity_regex, u) for u in uris):
                return False, "cert SAN %r does not match identity" % uris
            de = bundle.get("dsseEnvelope")
            if not de:
                return False, "bundle has no dsseEnvelope"
            body = base64.b64decode(de["payload"])
            pae = common.dsse_pae(de["payloadType"], body)
            sigs = de.get("signatures") or []
            if not sigs:
                return False, "no dsse signatures in bundle"
            try:
                _ecdsa_verify(cert.public_key(),
                              base64.b64decode(sigs[0]["sig"]), pae)
            except InvalidSignature:
                return False, "sigstore signature does not verify"
            return True, "sigstore-keyless ok"

        return False, "unknown scheme %r" % scheme
    except Exception as e:  # malformed envelope structure
        return False, "verify error: %s" % e


# --------------------------------------------------------------------------- #
# Core checker (stdlib; verify_fn injectable)                                  #
# --------------------------------------------------------------------------- #
def check_corpus(records, head, *, pubkey_pem, identity_regex, min_receipts,
                 allowed_schemes, verify_fn=verify_record_signature):
    """Return (exit_code, report:dict)."""
    findings = []
    n = len(records)
    if n == 0:
        if min_receipts <= 0:
            return EXIT_OK, {"checked": 0, "soft_pass": True, "findings": []}
        findings.append("empty corpus but floor=%d" % min_receipts)
        return EXIT_VIOLATION, {"checked": 0, "findings": findings}

    if n < min_receipts:
        findings.append("floor: %d records < min %d" % (n, min_receipts))

    seen_ids = set()
    seen_uids = set()
    for i, rec in enumerate(records):
        rid = rec.get("id")
        src = rec.get("source")
        kind = rec.get("kind")
        payload = rec.get("payload")
        if rid is None or src is None or kind is None or payload is None:
            findings.append("record %d missing schema fields" % i)
            continue
        if rid in seen_ids:
            findings.append("duplicate record id %s" % rid[:16])
        seen_ids.add(rid)
        # content-address integrity
        recomputed = common.content_address(src, kind, payload)
        if recomputed != rid:
            findings.append("record %d id mismatch (tamper): %s != %s"
                            % (i, rid[:16], recomputed[:16]))
            continue
        uid = payload.get("receipt_uid")
        if uid is not None:
            if uid in seen_uids:
                findings.append("duplicate receipt_uid %s" % str(uid)[:16])
            seen_uids.add(uid)
        scheme = payload.get("scheme")
        if allowed_schemes and scheme not in allowed_schemes:
            findings.append("record %d disallowed scheme %r" % (i, scheme))
            continue
        ok, reason = verify_fn(rec, pubkey_pem=pubkey_pem,
                               identity_regex=identity_regex)
        if not ok:
            findings.append("record %d (%s) signature: %s" % (i, rid[:12], reason))

    # head consistency
    if head is not None:
        hc = head.get("count")
        if hc is not None and int(hc) != n:
            findings.append("head.count=%s != records=%d" % (hc, n))
        last_id = head.get("last_id")
        if last_id is not None and records and records[-1].get("id") != last_id:
            findings.append("head.last_id != last record id")

    code = EXIT_VIOLATION if findings else EXIT_OK
    return code, {"checked": n, "soft_pass": False, "findings": findings}


# --------------------------------------------------------------------------- #
# Live fetch + main                                                            #
# --------------------------------------------------------------------------- #
def fetch_corpus(cfg, token):
    rv = cfg["reverify"]
    repo_id = rv["repo_id"]
    prefix = rv["prefix"]
    head_url = common.resolve_url(cfg["hf_resolve_base"], repo_id,
                                  "%s/head.json" % prefix)
    head = common.fetch_json(head_url, token)
    records = []
    shards = []
    if head and isinstance(head.get("shards"), list) and head["shards"]:
        shards = head["shards"]
    if not shards:
        # Fall back to listing-free convention: a single dated shard may exist;
        # without a shard list we cannot enumerate, so head must list them.
        shards = []
    for shard in shards:
        url = common.resolve_url(cfg["hf_resolve_base"], repo_id,
                                 "%s/%s" % (prefix, shard))
        recs = common.fetch_ndjson(url, token)
        if recs:
            records.extend(recs)
    return records, head


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(
        os.path.dirname(__file__), "..", ".github", "hf-corpus-guards.json"))
    ap.add_argument("--summary-out", default="")
    args = ap.parse_args(argv)

    with open(args.config, "r", encoding="utf-8") as fh:
        cfg = json.load(fh)
    token = os.environ.get("HF_TOKEN") or os.environ.get("HF_ORG_TOKEN") or None
    rv = cfg["reverify"]

    try:
        records, head = fetch_corpus(cfg, token)
    except AuthError as e:
        print("REVERIFY ERROR — auth: %s" % e)
        return EXIT_ERROR
    except Unreachable as e:
        print("REVERIFY ERROR — unreachable: %s" % e)
        return EXIT_ERROR

    # cross-check pinned pubkey against the live URL when reachable (advisory).
    pub_pem = cfg["cosign_pub_pem"]
    pub_note = "pinned"
    try:
        live = common.fetch_text(cfg["cosign_pub_url"], None)
        if live and live.strip() and live.strip() != pub_pem.strip():
            pub_note = "WARNING: pinned cosign.pub differs from live URL"
    except (AuthError, Unreachable):
        pub_note = "pinned (live cross-check unreachable)"

    code, report = check_corpus(
        records, head,
        pubkey_pem=pub_pem,
        identity_regex=cfg.get("sigstore_identity_regex", ""),
        min_receipts=int(rv.get("min_receipts", 0)),
        allowed_schemes=rv.get("allowed_schemes"),
    )
    report["pubkey"] = pub_note
    summary = {"guard": "hf-corpus-reverify", "exit": code, "report": report}
    text = json.dumps(summary, indent=2)
    print(text)
    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    if code == EXIT_OK:
        print("REVERIFY OK — %d receipt(s) re-verified (or soft-pass)."
              % report.get("checked", 0))
    else:
        print("REVERIFY VIOLATION — %s" % "; ".join(report["findings"]))
    return code


if __name__ == "__main__":
    sys.exit(main())
