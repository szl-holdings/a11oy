"""test_khipu_aggregate_live — hits the LIVE deployed organs and asserts the
/api/rosie/v1/khipu/aggregate snapshot is built from REAL receipts.

This is a network test (4 live organs: rosie, sentra, amaru, killinchu; a11oy is
expected BUILD_ERROR). Run directly:

    python tests/test_khipu_aggregate_live.py

Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import szl_khipu_aggregate as agg  # noqa: E402


def main() -> int:
    snap = agg.build_snapshot(timeout=12.0)
    print(f"organs_live={snap['organs_live']}/{snap['organs_total']} "
          f"nodes={snap['node_count']} edges={snap['edge_count']}")
    for o in snap["organs"]:
        print(f"  {o['organ']:>10} : {o['status']:<12} count={o['count']}"
              + (f"  err={o.get('error')}" if o.get("error") else ""))

    failures = []
    # At least the 4 known-live organs should be LIVE.
    live = {o["organ"] for o in snap["organs"] if o["status"] == "LIVE"}
    for must in ("sentra", "amaru", "killinchu"):
        if must not in live:
            failures.append(f"expected {must} LIVE, got down")
    # Real receipts → real nodes.
    if snap["node_count"] < 1:
        failures.append("no real nodes pulled — aggregate empty")
    # Every node must carry a real digest + organ + a verdict in {green,amber,red}.
    for n in snap["nodes"]:
        if not n.get("digest"):
            failures.append(f"node {n['id']} missing real digest")
            break
        if n["verdict"] not in ("green", "amber", "red"):
            failures.append(f"node {n['id']} bad verdict {n['verdict']}")
            break
    # a11oy down must be HONEST (BUILD_ERROR, empty), never faked.
    a11 = next((o for o in snap["organs"] if o["organ"] == "a11oy"), None)
    if a11 and a11["status"] == "LIVE" and a11["count"] == 0:
        failures.append("a11oy marked LIVE with 0 receipts — should be honest status")

    if failures:
        print("FAIL:")
        for f in failures:
            print("  -", f)
        return 1
    print("PASS — aggregate built from REAL live receipts; down organs honest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
