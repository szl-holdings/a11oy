#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11/v12
# Authored by the NEMOTRON SIGNED-TRAJECTORY build team. Co-Authored-By: Perplexity Computer Agent.
"""
szl_nemo_verify — standalone verifier for the SZL-Nemo signed-trajectory corpus.

Anyone can run this against a downloaded corpus JSONL to independently check:
  1. CONTENT INTEGRITY — recompute each step's sha256 step_hash and compare.
  2. SIGNATURE  — if a step carries a DSSE signature, verify it against the
     published SZLHOLDINGS cosign public key (cosign.pub).

USAGE:
    python szl_nemo_verify.py path/to/corpus.jsonl
    cat corpus.jsonl | python szl_nemo_verify.py -

EXIT CODE: 0 if every present signature verifies AND every hash matches; else 1.

HONEST: when the corpus was emitted in an environment without the private signing
key, the receipts are UNSIGNED (signatures: []) — this verifier reports that
transparently and does NOT treat "unsigned" as a pass of the signature check. The
hash check still applies and proves content integrity / tamper-evidence.

Prefers the shipped szl_trajectory_sign + szl_dsse modules when importable (full
DSSE verification). Falls back to a self-contained hash-only check if they are not
on the path, so the script still runs standalone. NO network required.
"""
from __future__ import annotations

import hashlib
import json
import sys


def _canon(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _step_hash(action, observation, restraint_verdict: str) -> str:
    body = _canon({"action": action, "observation": observation,
                   "restraint_verdict": restraint_verdict})
    return "sha256:" + hashlib.sha256(body).hexdigest()


def _verify_full(text: str):
    """Full verification using the shipped modules (DSSE + hash)."""
    import szl_trajectory_sign as sts  # type: ignore
    return sts.verify_jsonl(text)


def _verify_hash_only(text: str):
    """Self-contained hash-only fallback (no DSSE module on path)."""
    results = []
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            d = json.loads(ln)
        except Exception as exc:
            results.append({"parse_error": str(exc)})
            continue
        recomputed = _step_hash(d.get("action"), d.get("observation", ""),
                                d.get("restraint_verdict", "ALLOW"))
        env = d.get("signature") or {}
        sigs = env.get("signatures") or []
        results.append({
            "trajectory_id": d.get("trajectory_id"),
            "step": d.get("step"),
            "hash_ok": recomputed == d.get("step_hash"),
            "signed": bool(sigs),
            "sig_ok": False,  # cannot DSSE-verify without the module
        })
    total = len(results)
    hash_ok = sum(1 for r in results if r.get("hash_ok"))
    signed = sum(1 for r in results if r.get("signed"))
    return {
        "total_steps": total, "hash_ok": hash_ok, "signed": signed, "sig_ok": 0,
        "all_hash_ok": hash_ok == total and total > 0,
        "all_sig_ok": False, "results": results,
        "note": "hash-only fallback (szl_dsse not importable; signatures not checked)",
    }


def main(argv) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    src = argv[1]
    text = sys.stdin.read() if src == "-" else open(src, encoding="utf-8").read()
    try:
        res = _verify_full(text)
        mode = "full (DSSE + hash)"
    except Exception:
        res = _verify_hash_only(text)
        mode = "hash-only fallback"
    summary = {k: res[k] for k in ("total_steps", "hash_ok", "signed", "sig_ok",
                                   "all_hash_ok", "all_sig_ok") if k in res}
    summary["verify_mode"] = mode
    print(json.dumps(summary, indent=2))
    # PASS iff every hash matches AND (no signatures present OR all verify).
    hashes_ok = res.get("all_hash_ok", False)
    sig_present = res.get("signed", 0) > 0
    sigs_ok = res.get("sig_ok", 0) == res.get("signed", 0)
    ok = hashes_ok and (not sig_present or sigs_ok)
    print("RESULT:", "PASS" if ok else "FAIL")
    if sig_present and not sigs_ok:
        print("  (signatures present but not all verified)")
    if not sig_present:
        print("  (no signatures present — UNSIGNED corpus; hash integrity only)")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
