#!/usr/bin/env python3
# Signed-off-by: Forge (Replit task agent) <forge@szl-holdings>
"""Negative-fixture self-test for the re-verify guard.

Chain / content-address / head / floor logic is exercised with a STUBBED
verify_fn so it runs offline (sandbox cannot pip-install cryptography). A real
ECDSA-P256 DSSE sign+verify path runs only if `cryptography` is importable
(it is in CI), and is skipped cleanly otherwise.

Run by file path:  python3 test_check_hf_corpus_reverify.py
"""
from __future__ import annotations

import base64
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import szl_corpus_guard_common as common  # noqa: E402
import check_hf_corpus_reverify as rv  # noqa: E402
from szl_corpus_guard_common import EXIT_OK, EXIT_VIOLATION  # noqa: E402

FAILURES = []


def check(name, cond):
    if cond:
        print("  ok  - %s" % name)
    else:
        print("  FAIL- %s" % name)
        FAILURES.append(name)


def make_rec(source, kind, payload):
    # Mirror szl_corpus_publish: receipts are appended with an explicit
    # dedup_key of the receipt_uid, so the content-address basis is the uid
    # (not the full payload). Fall back to the payload when no uid is present.
    basis = payload.get("receipt_uid") if isinstance(payload, dict) \
        and payload.get("receipt_uid") is not None else payload
    return {"id": common.content_address(source, kind, basis),
            "source": source, "kind": kind, "payload": payload}


def stub_ok(rec, **kw):
    return True, "stub ok"


def stub_bad(rec, **kw):
    return False, "stub forced fail"


def good_payload(uid):
    return {"scheme": "ecdsa-p256-dsse-pae", "receipt_uid": uid,
            "envelope": {"payloadType": "t", "payload": "e30=",
                         "signatures": [{"sig": "AA=="}]}}


def base_records():
    r1 = make_rec("a11oy", "release-receipt", good_payload("u1"))
    r2 = make_rec("a11oy", "release-receipt", good_payload("u2"))
    return [r1, r2]


def head_for(records):
    return {"count": len(records), "last_id": records[-1]["id"]}


SCHEMES = ["ecdsa-p256-dsse-pae", "sigstore-keyless-dsse"]


def run(records, head, min_receipts=2, verify_fn=stub_ok):
    return rv.check_corpus(records, head, pubkey_pem="PEM",
                           identity_regex="^https://github.com/szl-holdings/.*",
                           min_receipts=min_receipts, allowed_schemes=SCHEMES,
                           verify_fn=verify_fn)


def main():
    recs = base_records()
    head = head_for(recs)

    code, rep = run(recs, head)
    check("clean corpus is OK", code == EXIT_OK and rep["checked"] == 2)

    # content-address tamper: mutate payload AFTER id was computed
    tampered = base_records()
    tampered[0]["payload"]["receipt_uid"] = "MUTATED"
    code, rep = run(tampered, head_for(tampered))
    check("payload tamper -> VIOLATION (crypto-free)",
          code == EXIT_VIOLATION and any("tamper" in f for f in rep["findings"]))

    # signature failure (stub) -> VIOLATION
    code, rep = run(recs, head, verify_fn=stub_bad)
    check("sig fail -> VIOLATION",
          code == EXIT_VIOLATION and any("signature" in f for f in rep["findings"]))

    # empty + floor>0 -> VIOLATION
    code, rep = run([], None, min_receipts=2)
    check("empty+floor -> VIOLATION", code == EXIT_VIOLATION)

    # empty + floor 0 -> soft-pass OK
    code, rep = run([], None, min_receipts=0)
    check("empty+no-floor -> soft-pass OK",
          code == EXIT_OK and rep.get("soft_pass") is True)

    # below floor -> VIOLATION
    code, rep = run([recs[0]], head_for([recs[0]]), min_receipts=2)
    check("below floor -> VIOLATION",
          code == EXIT_VIOLATION and any("floor" in f for f in rep["findings"]))

    # head.count mismatch -> VIOLATION
    code, rep = run(recs, {"count": 99, "last_id": recs[-1]["id"]})
    check("head.count mismatch -> VIOLATION",
          code == EXIT_VIOLATION and any("head.count" in f for f in rep["findings"]))

    # head.last_id mismatch -> VIOLATION
    code, rep = run(recs, {"count": 2, "last_id": "deadbeef"})
    check("head.last_id mismatch -> VIOLATION",
          code == EXIT_VIOLATION and any("last_id" in f for f in rep["findings"]))

    # duplicate id -> VIOLATION
    dup = [recs[0], recs[0]]
    code, rep = run(dup, head_for(dup))
    check("duplicate id -> VIOLATION",
          code == EXIT_VIOLATION and any("duplicate" in f for f in rep["findings"]))

    # disallowed scheme -> VIOLATION
    bad_scheme = make_rec("a11oy", "release-receipt",
                          {"scheme": "rot13", "envelope": {}})
    code, rep = run([bad_scheme, recs[1]], head_for([bad_scheme, recs[1]]))
    check("disallowed scheme -> VIOLATION",
          code == EXIT_VIOLATION and any("scheme" in f for f in rep["findings"]))

    real_crypto_path()
    fetch_corpus_shard_path()

    print()
    if FAILURES:
        print("REVERIFY SELF-TEST FAILED: %d" % len(FAILURES))
        return 1
    print("REVERIFY SELF-TEST PASSED")
    return 0


def fetch_corpus_shard_path():
    """fetch_corpus must NOT double-prefix repo-root-relative shard paths.

    Regression: head.json from szl_hf_bucket lists shards as
    "receipts/2026-06-12.ndjson" (already prefixed). Re-prepending the prefix
    produced "receipts/receipts/..." -> 404 -> a false 'empty corpus'.
    """
    cfg = {
        "hf_resolve_base":
            "https://hf/datasets/{repo_id}/resolve/main/{path}",
        "reverify": {"repo_id": "SZLHOLDINGS/a11oy-verifiable-corpus",
                     "prefix": "receipts"},
    }
    requested = []

    def fake_json(url, token):
        requested.append(url)
        return {"count": 1, "shards": ["receipts/2026-06-12.ndjson"]}

    def fake_ndjson(url, token):
        requested.append(url)
        # only the correctly-built (single-prefix) URL yields records
        if url.endswith("/resolve/main/receipts/2026-06-12.ndjson"):
            return [{"id": "x"}]
        return None

    orig_j, orig_n = common.fetch_json, common.fetch_ndjson
    common.fetch_json, common.fetch_ndjson = fake_json, fake_ndjson
    try:
        records, head = rv.fetch_corpus(cfg, None)
    finally:
        common.fetch_json, common.fetch_ndjson = orig_j, orig_n

    check("fetch_corpus does not double-prefix shard path",
          all("receipts/receipts/" not in u for u in requested))
    check("fetch_corpus enumerates the real shard -> 1 record",
          len(records) == 1)


def real_crypto_path():
    """Real ECDSA-P256 DSSE sign+verify, only if cryptography is present."""
    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import ec
    except Exception:
        print("  skip- real-crypto path (cryptography not installed)")
        return

    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo).decode()

    body = b'{"hello":"world"}'
    ptype = "application/vnd.in-toto+json"
    pae = common.dsse_pae(ptype, body)
    sig = key.sign(pae, ec.ECDSA(hashes.SHA256()))
    env = {"payloadType": ptype, "payload": base64.b64encode(body).decode(),
           "signatures": [{"sig": base64.b64encode(sig).decode()}]}
    rec = {"payload": {"scheme": "ecdsa-p256-dsse-pae", "envelope": env}}

    ok, reason = rv.verify_record_signature(rec, pubkey_pem=pem,
                                            identity_regex="")
    check("real ECDSA sign+verify -> ok", ok)

    # flip the signed body without re-signing -> must fail
    bad_env = dict(env)
    bad_env["payload"] = base64.b64encode(b'{"hello":"tampered"}').decode()
    bad_rec = {"payload": {"scheme": "ecdsa-p256-dsse-pae", "envelope": bad_env}}
    ok2, reason2 = rv.verify_record_signature(bad_rec, pubkey_pem=pem,
                                              identity_regex="")
    check("real ECDSA tamper -> fail", not ok2)


if __name__ == "__main__":
    sys.exit(main())
