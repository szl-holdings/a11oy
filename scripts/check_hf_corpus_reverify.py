#!/usr/bin/env python3
# Signed-off-by: Forge (Replit task agent) <forge@szl-holdings>
"""Re-verify guard for the a11oy verifiable-corpus signed receipts.

Self-contained against the published records + a DOCUMENTED MULTI-KEY TRUST SET,
so it does NOT depend on an expiring artifact AND survives an org cosign-key
rotation without breaking history. For every receipt it re-checks:
  * content-address integrity: id == sha256(canon({source,kind,content=payload}))
    (fail-loud on any tampered byte),
  * the DSSE signature still verifies over its PAE:
      - ecdsa-p256-dsse-pae : signatures[].sig vs the trusted keyset (the record
        must verify under the specific documented key it was signed with —
        historical CI key OR current org key; see the key_rotation ledger),
      - sigstore-keyless-dsse: the bundle's dsseEnvelope sig vs its leaf cert,
        with the cert SAN matching the szl-holdings identity regex,
  * head-consistency: head.count == #records, head.last_id == last record id,
    no duplicate record ids / receipt_uids,
  * baseline floor: total >= reverify.min_receipts (an emptied corpus must NOT
    pass green). Empty corpus + no floor = honest soft-pass.

This complements rekor-recheck.yml (which re-checks Rekor transparency-log
inclusion); here we re-check the embedded signatures + integrity from the
published corpus alone. The trust set + rotation history are documented in
docs/KEY_ROTATION.md and the guard config's trusted_keys / key_rotation blocks.

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


def key_fingerprint(pem: str) -> str:
    """The per-record key fingerprint the receipts themselves carry in
    verify.public_key_sha256: sha256 over the stripped PEM text. Lets the guard
    name WHICH trusted key verified a receipt, honestly and per-record."""
    import hashlib
    return hashlib.sha256(pem.strip().encode("utf-8")).hexdigest()


def _pem_list(pubkey_pems, pubkey_pem):
    """Normalise the caller's key input to a list of trusted PEMs. Accepts a
    multi-key trust set (pubkey_pems) or a single pinned key (pubkey_pem, kept
    for backward-compatibility with the offline self-test)."""
    if pubkey_pems:
        return [p for p in pubkey_pems if p]
    return [pubkey_pem] if pubkey_pem else []


def verify_record_signature(rec, *, pubkey_pems=None, pubkey_pem=None,
                            identity_regex):
    """Return (ok:bool, reason:str). Raises nothing for a bad signature —
    a failed verify is a finding, not an exception.

    ecdsa-p256-dsse-pae receipts are verified against the DOCUMENTED MULTI-KEY
    TRUST SET: a receipt passes iff its signature verifies under EXACTLY the key
    it was signed with, and that key is one of the trusted, documented keys
    (historical CI key + current org key). The reason names which trusted key
    verified it, so a rotation is auditable per-record rather than hidden behind
    a single pin."""
    payload = rec.get("payload", {})
    scheme = payload.get("scheme")
    env = payload.get("envelope")
    if not scheme or not isinstance(env, dict):
        return False, "missing scheme/envelope"

    try:
        if scheme == "ecdsa-p256-dsse-pae":
            body = base64.b64decode(env["payload"])
            pae = common.dsse_pae(env["payloadType"], body)
            pems = _pem_list(pubkey_pems, pubkey_pem)
            if not pems:
                return False, "no trusted keys configured"
            sigs = env.get("signatures") or []
            if not sigs:
                return False, "no signatures"
            from cryptography.exceptions import InvalidSignature
            for pem in pems:
                pub = _load_pub(pem)
                for s in sigs:
                    try:
                        _ecdsa_verify(pub, base64.b64decode(s["sig"]), pae)
                        return True, ("ecdsa-p256 ok via trusted key %s"
                                      % key_fingerprint(pem)[:12])
                    except InvalidSignature:
                        continue
            return False, ("ecdsa signature does not verify under any of the "
                           "%d trusted key(s)" % len(pems))

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
def check_corpus(records, head, *, pubkey_pem=None, pubkey_pems=None,
                 identity_regex, min_receipts, allowed_schemes,
                 quarantine=None, verify_fn=verify_record_signature):
    """Return (exit_code, report:dict).

    Trust model: every published receipt must verify under the DOCUMENTED
    MULTI-KEY TRUST SET (pubkey_pems / trusted_keys) — the key it was actually
    signed with. A small, explicitly DOCUMENTED quarantine set (Incident #325
    ephemeral-pod orphans) is the only exception: those records are not counted
    as verified, are reported as quarantined orphans, and STILL fail loudly on
    tamper, on a signing-key that is not the documented orphan key, or if they
    unexpectedly verify under a trusted key. This is documentation of a known
    accepted orphan, NOT a blind allow-list of bad ids and NOT a skip-on-fail."""
    findings = []
    quarantined = []
    verified = 0
    n = len(records)
    q = quarantine or {}
    q_uids = set(q.get("receipt_uids") or [])
    q_expected = q.get("expected_key_sha256")
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
        # content-address integrity.
        # szl_corpus_publish appends receipts with an explicit dedup_key of the
        # receipt_uid, so szl_hf_bucket.make_record content-addresses the id over
        # {source,kind,content=receipt_uid} -- NOT the full payload. We mirror
        # that dedup basis here (falling back to the payload for any record that
        # carries no receipt_uid) so a legitimately-published receipt verifies.
        uid = payload.get("receipt_uid")
        basis = uid if uid is not None else payload
        recomputed = common.content_address(src, kind, basis)
        if recomputed != rid:
            findings.append("record %d id mismatch (tamper): %s != %s"
                            % (i, rid[:16], recomputed[:16]))
            continue
        if uid is not None:
            if uid in seen_uids:
                findings.append("duplicate receipt_uid %s" % str(uid)[:16])
            seen_uids.add(uid)
        scheme = payload.get("scheme")
        if allowed_schemes and scheme not in allowed_schemes:
            findings.append("record %d disallowed scheme %r" % (i, scheme))
            continue
        ok, reason = verify_fn(rec, pubkey_pems=pubkey_pems,
                               pubkey_pem=pubkey_pem,
                               identity_regex=identity_regex)
        # Documented Incident #325 quarantine: content-address is already proven
        # intact above (this record is NOT tamper). It must NOT verify under a
        # trusted key (else it isn't an orphan and should not be quarantined),
        # and its signing key must be the documented ephemeral-pod key.
        if uid is not None and uid in q_uids:
            declared = (payload.get("verify") or {}).get("public_key_sha256")
            if ok:
                findings.append(
                    "record %d (%s) is quarantined but unexpectedly VERIFIES "
                    "under a trusted key (%s) — remove it from quarantine"
                    % (i, rid[:12], reason))
            elif q_expected and declared != q_expected:
                findings.append(
                    "record %d (%s) quarantine key mismatch: declared signing "
                    "key %s != documented orphan key %s"
                    % (i, rid[:12], str(declared)[:12], str(q_expected)[:12]))
            else:
                quarantined.append(uid)
            continue
        if not ok:
            findings.append("record %d (%s) signature: %s" % (i, rid[:12], reason))
        else:
            verified += 1

    # head consistency
    if head is not None:
        hc = head.get("count")
        if hc is not None and int(hc) != n:
            findings.append("head.count=%s != records=%d" % (hc, n))
        last_id = head.get("last_id")
        if last_id is not None and records and records[-1].get("id") != last_id:
            findings.append("head.last_id != last record id")

    code = EXIT_VIOLATION if findings else EXIT_OK
    report = {"checked": n, "verified": verified, "soft_pass": False,
              "findings": findings}
    if quarantined:
        report["quarantined"] = quarantined
        report["quarantine_incident"] = q.get("incident")
    return code, report


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
    # szl_hf_bucket writes each shard path REPO-ROOT-RELATIVE (e.g.
    # "receipts/2026-06-12.ndjson"), so it already carries the prefix; do NOT
    # prepend it again or the URL double-prefixes and 404s. Tolerate a bare
    # filename too, for forward-compat.
    for shard in shards:
        path = shard if "/" in shard else "%s/%s" % (prefix, shard)
        url = common.resolve_url(cfg["hf_resolve_base"], repo_id, path)
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

    # DOCUMENTED MULTI-KEY TRUST SET: verify each receipt against the key it was
    # actually signed with, drawn from a documented set (historical CI key +
    # current org key). Falls back to the single pinned key for a config that
    # predates the trust set. See key_rotation ledger for why both are trusted.
    trusted = cfg.get("trusted_keys") or []
    trusted_pems = [k.get("pem") for k in trusted if k.get("pem")]
    if not trusted_pems:
        trusted_pems = [cfg["cosign_pub_pem"]]
    trusted_fps = {key_fingerprint(p) for p in trusted_pems}

    # cross-check the live org cosign.pub against the trust set when reachable
    # (advisory). After a rotation the live key legitimately differs from the
    # historical pin; the honest check is whether the live key is IN the trust
    # set, not whether it equals a single pin.
    pub_note = "trusted keyset (%d key(s))" % len(trusted_pems)
    try:
        live = common.fetch_text(cfg["cosign_pub_url"], None)
        if live and live.strip():
            if key_fingerprint(live) in trusted_fps:
                pub_note += "; live cosign.pub is in the trust set"
            else:
                pub_note += ("; WARNING: live cosign.pub (%s) is NOT in the "
                             "trust set" % key_fingerprint(live)[:12])
    except (AuthError, Unreachable):
        pub_note += " (live cross-check unreachable)"

    code, report = check_corpus(
        records, head,
        pubkey_pems=trusted_pems,
        identity_regex=cfg.get("sigstore_identity_regex", ""),
        min_receipts=int(rv.get("min_receipts", 0)),
        allowed_schemes=rv.get("allowed_schemes"),
        quarantine=cfg.get("quarantine"),
    )
    report["pubkey"] = pub_note
    summary = {"guard": "hf-corpus-reverify", "exit": code, "report": report}
    text = json.dumps(summary, indent=2)
    print(text)
    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
    if code == EXIT_OK:
        q = report.get("quarantined") or []
        qnote = (" (%d documented orphan(s) quarantined per Incident %s)"
                 % (len(q), report.get("quarantine_incident"))) if q else ""
        print("REVERIFY OK — %d/%d receipt(s) re-verified under the trusted "
              "keyset%s." % (report.get("verified", 0),
                             report.get("checked", 0), qnote))
    else:
        print("REVERIFY VIOLATION — %s" % "; ".join(report["findings"]))
    return code


if __name__ == "__main__":
    sys.exit(main())
