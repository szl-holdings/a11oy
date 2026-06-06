# SPDX-License-Identifier: Apache-2.0
"""Reference CLI verifier: khipu-verify <receipt.json> <pubkeys-dir>.

receipt.json: {action|action_hash, threshold?, n?, signatures|signatures_received:[...]}
pubkeys-dir : directory containing <organ>.pub PEM files (or <organ>.test.pub).
"""
import json
import os
import sys

from . import tally


def main(argv=None):
    argv = argv or sys.argv[1:]
    if len(argv) < 2:
        print("usage: khipu-verify <receipt.json> <pubkeys-dir>", file=sys.stderr)
        return 2
    receipt = json.load(open(argv[0]))
    pkdir = argv[1]
    action = receipt.get("action") or receipt.get("action_hash")
    sigs = receipt.get("signatures") or receipt.get("signatures_received") or []
    pubkeys = {}
    for s in sigs:
        if not s:
            continue
        organ = s.get("organ")
        for cand in (f"{organ}.pub", f"{organ}.test.pub"):
            p = os.path.join(pkdir, cand)
            if os.path.isfile(p):
                pubkeys[organ] = open(p).read()
                break
    r = tally(action, sigs, pubkeys, threshold=int(receipt.get("threshold", 3)),
              n=int(receipt.get("n", 4)))
    print(json.dumps({"consensus": r.khipu_consensus, "decision": r.decision,
                      "consensus_count": r.consensus_count, "threshold": r.threshold}, indent=2))
    return 0 if r.decision == "canonical" else 1


if __name__ == "__main__":
    raise SystemExit(main())
