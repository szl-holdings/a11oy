#!/usr/bin/env python3
# Signed-off-by: Forge (Replit task agent) <forge@szl-holdings>
"""One-shot repair for the a11oy verifiable-corpus re-verify incident (#325).

Two published ecdsa-p256-dsse-pae receipts were signed by a transient/rotated
key (matching the live org cosign.pub) instead of the PINNED corpus key
(.github/hf-corpus-guards.json -> cosign_pub_pem), so the daily re-verify guard
(scripts/check_hf_corpus_reverify.py) fails them every run. The honest fix is to
remove ONLY those receipts from the published corpus using the repo's own bucket
tooling and recount head.json -- never by weakening the guard, lowering the
floor, or allow-listing the bad ids.

What it does (authoritatively, using the guard's OWN verify code):
  * reads every receipt shard + head.json straight from the HF dataset,
  * recomputes, with check_hf_corpus_reverify.verify_record_signature against the
    pinned cosign.pub, the EXACT set of ecdsa records the guard would fail,
  * removes ONLY those records (kept records stay byte-identical -- we drop whole
    NDJSON lines, never re-serialize them),
  * recomputes head.json (count/last_id/last_ts/shards) exactly as
    szl_hf_bucket._commit_pending would, and
  * commits the rewritten shard(s) + head.json in ONE commit via the bucket's
    own _HFTransport, using the repo's HF write token.

Safety rails (fail-loud, refuse rather than damage):
  * DRY-RUN by default; mutation requires BOTH --apply and --confirm.
  * NEVER removes a record that verifies against the pinned key.
  * Refuses if removing would drop the corpus below reverify.min_receipts.
  * Refuses if the recomputed set does not match the expected count (--expect).
  * Refuses if no write token is present.

Exit: 0 ok (dry-run report or applied) | 1 refused/precondition-failed | 2 auth/unreachable.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

# repo root on path so we can import the bucket transport + the guard's verifier.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (_ROOT, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import szl_corpus_guard_common as common  # noqa: E402
from szl_corpus_guard_common import AuthError, Unreachable  # noqa: E402
from check_hf_corpus_reverify import verify_record_signature  # noqa: E402

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_ERROR = 2


def _load_cfg(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _read_shard_lines(transport, shard):
    """Return the raw (stripped, non-empty) NDJSON lines of a shard, in order."""
    blob = transport.read_file(shard) or b""
    out = []
    for line in blob.decode("utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(line)
    return out


def _recompute_head(repo_id, prefix, shards, shard_lines):
    """Mirror szl_hf_bucket._commit_pending head computation over the POST-repair
    shard contents. count = total kept lines; last_id/last_ts = last line of the
    last shard (shards already sorted)."""
    total = 0
    last_id = last_ts = None
    for shard in shards:
        for line in shard_lines.get(shard, []):
            total += 1
            try:
                obj = json.loads(line)
                last_id, last_ts = obj.get("id"), obj.get("ts")
            except ValueError:
                pass
    return {
        "schema": "szl.hf.bucket.head/v1",
        "repo_id": repo_id,
        "prefix": prefix,
        "count": total,
        "last_id": last_id,
        "last_ts": last_ts,
        "shards": shards,
        "updated_at": common.now_utc().strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default=os.path.join(
        _ROOT, ".github", "hf-corpus-guards.json"))
    ap.add_argument("--apply", action="store_true",
                    help="actually rewrite shards + head (default: dry-run)")
    ap.add_argument("--confirm", action="store_true",
                    help="required alongside --apply to mutate the corpus")
    ap.add_argument("--expect", type=int, default=-1,
                    help="refuse unless exactly this many records would be removed")
    args = ap.parse_args(argv)

    cfg = _load_cfg(args.config)
    rv = cfg["reverify"]
    repo_id = rv["repo_id"]
    prefix = rv["prefix"]
    min_receipts = int(rv.get("min_receipts", 0))
    pub_pem = cfg["cosign_pub_pem"]
    identity_regex = cfg.get("sigstore_identity_regex", "")

    token = os.environ.get("HF_ORG_TOKEN") or os.environ.get(
        "HF_WRITE_TOKEN") or os.environ.get("HF_TOKEN")

    # Build the transport (lazy huggingface_hub import lives inside it).
    try:
        from szl_hf_bucket import _HFTransport
    except Exception as exc:  # pragma: no cover - import guard
        print("REPAIR ERROR — cannot import bucket transport: %s" % exc)
        return EXIT_ERROR
    transport = _HFTransport(repo_id, token)

    # 1) Read all shards from head (root-relative paths) + recompute the bad set.
    try:
        head_blob = transport.read_file("%s/head.json" % prefix)
        head = json.loads(head_blob.decode("utf-8")) if head_blob else None
        shards = sorted(transport.list_files(prefix))
        shards = [s for s in shards if s.endswith(".ndjson")]
    except Exception as exc:
        msg = str(exc).lower()
        if "401" in msg or "403" in msg or "auth" in msg:
            print("REPAIR ERROR — auth: %s" % exc)
            return EXIT_ERROR
        print("REPAIR ERROR — unreachable: %s" % exc)
        return EXIT_ERROR

    shard_lines = {}
    bad = []   # (shard, lineno, id, receipt_uid, reason)
    kept_total = 0
    for shard in shards:
        try:
            lines = _read_shard_lines(transport, shard)
        except Exception as exc:
            print("REPAIR ERROR — cannot read shard %s: %s" % (shard, exc))
            return EXIT_ERROR
        kept = []
        for i, line in enumerate(lines):
            try:
                rec = json.loads(line)
            except ValueError:
                # a malformed line is itself a finding; keep it (do not silently
                # drop) so a human notices, but it is NOT what we are repairing.
                kept.append(line)
                continue
            payload = rec.get("payload", {}) or {}
            scheme = payload.get("scheme")
            if scheme == "ecdsa-p256-dsse-pae":
                ok, reason = verify_record_signature(
                    rec, pubkey_pem=pub_pem, identity_regex=identity_regex)
                if not ok:
                    bad.append((shard, i, (rec.get("id") or "")[:16],
                                str(payload.get("receipt_uid"))[:16], reason))
                    continue  # drop ONLY this line
            kept.append(line)
        shard_lines[shard] = kept
        kept_total += len(kept)

    n_bad = len(bad)
    report = {
        "repo_id": repo_id,
        "prefix": prefix,
        "shards": shards,
        "records_before": kept_total + n_bad,
        "to_remove": n_bad,
        "records_after": kept_total,
        "min_receipts": min_receipts,
        "removals": [
            {"shard": s, "line": i, "id": rid, "receipt_uid": uid, "reason": r}
            for (s, i, rid, uid, r) in bad
        ],
    }
    print(json.dumps(report, indent=2))

    # 2) Preconditions — refuse rather than damage.
    if n_bad == 0:
        print("REPAIR OK — nothing to remove; all ecdsa receipts already "
              "verify against the pinned key.")
        return EXIT_OK
    if args.expect >= 0 and n_bad != args.expect:
        print("REPAIR REFUSED — expected to remove %d but found %d; aborting "
              "(re-run with the right --expect once you've reviewed the report)."
              % (args.expect, n_bad))
        return EXIT_REFUSED
    if kept_total < min_receipts:
        print("REPAIR REFUSED — removing %d would leave %d records, below the "
              "floor of %d." % (n_bad, kept_total, min_receipts))
        return EXIT_REFUSED

    if not (args.apply and args.confirm):
        print("DRY-RUN — would remove %d record(s) and recount head.json "
              "(%d -> %d). Re-run with --apply --confirm to mutate."
              % (n_bad, kept_total + n_bad, kept_total))
        return EXIT_OK

    if not token:
        print("REPAIR REFUSED — no HF write token "
              "(HF_ORG_TOKEN / HF_WRITE_TOKEN / HF_TOKEN) present.")
        return EXIT_REFUSED

    # 3) Build the commit: rewrite only the affected shards + head.json.
    affected = sorted({s for (s, *_ ) in bad})
    operations = []
    for shard in affected:
        kept = shard_lines.get(shard, [])
        payload = (("\n".join(kept) + "\n").encode("utf-8")) if kept else b""
        operations.append((shard, payload))
    new_head = _recompute_head(repo_id, prefix, shards, shard_lines)
    operations.append(("%s/head.json" % prefix,
                       common.canonical_bytes(new_head) + b"\n"))

    msg = ("corpus(repair): drop %d non-pinned-key receipt(s); recount head "
           "(#325)" % n_bad)
    try:
        oid = transport.commit(operations, msg)
    except Exception as exc:
        m = str(exc).lower()
        if "401" in m or "403" in m or "auth" in m:
            print("REPAIR ERROR — auth on commit: %s" % exc)
            return EXIT_ERROR
        print("REPAIR ERROR — commit failed: %s" % exc)
        return EXIT_ERROR

    print("REPAIR APPLIED — commit %s; removed %d receipt(s); head.count now %d "
          "(last_id=%s)." % (oid, n_bad, new_head["count"], new_head["last_id"]))
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
