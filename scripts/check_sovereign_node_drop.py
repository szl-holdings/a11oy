#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries.
# Λ = Conjecture 1 (Λ-Aggregator Uniqueness; NOT a closed theorem).
"""
check_sovereign_node_drop.py — honest "a home sovereign-GPU node just dropped" detector.

WHY (the observability gap this closes):
  The 3-node sovereign GPU mesh (rtx-betterwithage laptop, omen-betterwithage
  always-on home brain, chaski tailnet node) already reports honest per-node
  reachability via the hardened compute-pool prober
  (GET /api/a11oy/v1/compute-pool-hardened, served by szl_backend_hardening.py).
  That prober does a REAL TCP connect per node THIS request and never fabricates
  state — a timeout/refusal is reachable=False with the real reason.

  What was MISSING is a *signal on the edge*: the founder had no way to learn the
  instant a previously-reachable home node went unreachable. A node that is
  legitimately off (laptop traveling, chaski Repl stopped) must read as a clean
  "offline", NOT an alarm — so a plain "any node is down" check would be a
  permanent false alarm (the laptop is usually off). The honest signal is the
  TRANSITION: a node that WAS reachable on the previous sweep and is now
  unreachable. That, and only that, is "a home node just dropped".

WHAT THIS DOES (no new always-on poller; piggybacks the EXISTING probe):
  1. GET the hardened compute-pool surface from the BOX target (a11oy.net) — the
     box is the Tailscale peer, so it is the ONLY vantage point where the
     tailnet GPU nodes are genuinely reachable. (The HF Space is off-tailnet and
     reports every GPU node unreachable by construction; probing it would be a
     false-alarm machine, so it is deliberately NOT the drop target.)
  2. Load the PREVIOUS sweep snapshot (a small JSON the caller persists between
     runs — in CI, on the orphan `status` branch, exactly like status-page.yml).
  3. For each SOVEREIGN node the endpoint reports (sovereign==true, kind contains
     "gpu"), classify the transition honestly:
        - was reachable, now reachable      -> "up"        (no signal)
        - was unreachable, now unreachable   -> "offline"   (clean, no signal)
        - NEVER SEEN before, now unreachable -> "never-seen" (NO alarm — could be
                                                 a node legitimately never started)
        - never seen / was up, now reachable -> "recovered"/"up" (no alarm)
        - WAS reachable, now UNREACHABLE     -> "DROPPED"   (THE signal)
  4. Exit non-zero ONLY if >=1 sovereign node DROPPED. Print a per-node table and
     write a fresh snapshot (--write-snapshot) for the next run to compare against.

HONESTY / DOCTRINE v11 (binding, by construction):
  - reachable is consumed VERBATIM from the live hardened probe — never re-derived,
    never fabricated here. This script only DIFFS two real probe snapshots.
  - "never-seen" is distinguished from "was-up-now-down": a first-ever-unreachable
    node is NOT alarmed (it may just be off), so a brand-new or always-off node
    can never trigger a phantom drop.
  - It is REPORT-ONLY. It NEVER restarts, wakes, or touches founder hardware — it
    GETs a read-only endpoint and prints/exits. No auto-remediation, ever.
  - Λ = Conjecture 1 (open); locked = 8; no key committed; no fused-VRAM claim.
  - Stdlib only (urllib, json, argparse) — runs on a clean ubuntu-latest with no
    pip install and no third-party action (org policy: github-owned actions only).

Usage:
  check_sovereign_node_drop.py \
      --target https://a11oy.net \
      --prev-snapshot /path/to/prev.json   # absent/empty on first run -> all "never-seen"
      --write-snapshot /path/to/next.json \
      --summary-file /tmp/node-drop.json \
      [--attempts 3] [--sleep 10] [--timeout 20]
Exit: 0 = no sovereign node dropped (incl. clean offline / never-seen);
      1 = >=1 sovereign node transitioned reachable->unreachable (DROPPED);
      2 = usage/operational error (could not obtain a live probe at all).
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

HARDENED_PATH = "/api/a11oy/v1/compute-pool-hardened"


def _now_iso() -> str:
    import datetime
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def is_sovereign_gpu(node):
    """A node we treat as a 'home sovereign GPU' for drop purposes.

    Honest + table-agnostic: we key on the node's OWN declared properties
    (sovereign flag + a gpu kind), NOT a hardcoded name list, so the detector
    automatically covers omen-betterwithage once the box node table lists it,
    and never alarms on hosted-inference fallbacks (groq/nim/hf) or the CPU host.
    """
    if not isinstance(node, dict):
        return False
    if not bool(node.get("sovereign", False)):
        return False
    kind = str(node.get("kind", "")).lower()
    return "gpu" in kind


def fetch_pool(base, timeout):
    """GET the hardened compute-pool surface. Returns (nodes_by_name, err).

    nodes_by_name: {name: {reachable: bool, detail, kind, sovereign, endpoint}}.
    Never raises; a transport/HTTP/JSON failure returns ({}, reason).
    """
    url = base.rstrip("/") + HARDENED_PATH
    headers = {"User-Agent": "sovereign-node-drop/1.0", "Accept": "application/json"}
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.getcode()
            ct = resp.headers.get("Content-Type", "")
            raw = resp.read()
    except urllib.error.HTTPError as exc:
        return {}, "HTTP %s" % exc.code
    except Exception as exc:  # noqa: BLE001 — URLError / timeout / DNS / TLS
        return {}, "request error: %s" % exc
    if code != 200:
        return {}, "HTTP %s (want 200)" % code
    if "application/json" not in (ct or "").lower():
        return {}, "content-type '%s' is not application/json (likely SPA HTML)" % (ct or "none")
    try:
        data = json.loads(raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return {}, "body is not valid JSON: %s" % exc
    if not isinstance(data, dict) or not isinstance(data.get("nodes"), list):
        return {}, "payload has no nodes[] array"
    by_name = {}
    for n in data["nodes"]:
        if not isinstance(n, dict) or "name" not in n:
            continue
        by_name[n["name"]] = {
            "reachable": bool(n.get("reachable", False)),
            "detail": n.get("detail"),
            "kind": n.get("kind"),
            "sovereign": bool(n.get("sovereign", False)),
            "endpoint": n.get("endpoint"),
        }
    if not by_name:
        return {}, "nodes[] present but empty"
    return by_name, None


def classify(prev_reachable, now_reachable):
    """Pure transition classifier. prev_reachable is None when the node was
    never seen in the previous snapshot. Returns one of:
    'dropped' | 'recovered' | 'up' | 'offline' | 'never-seen'."""
    if prev_reachable is None:
        # First time we have ever seen this node. A node that is off right now is
        # NOT a drop (it may legitimately have never been started) -> never-seen.
        return "up" if now_reachable else "never-seen"
    if prev_reachable and not now_reachable:
        return "dropped"
    if (not prev_reachable) and now_reachable:
        return "recovered"
    return "up" if now_reachable else "offline"


def diff_snapshots(prev_nodes, now_nodes):
    """Diff sovereign GPU nodes between a previous snapshot and the live sweep.

    prev_nodes / now_nodes: {name: {reachable: bool, ...}}.
    Returns (rows, dropped) where rows is a list of per-node dicts and dropped is
    the subset whose transition == 'dropped'. Only sovereign-GPU nodes are
    considered (hosted fallbacks and the CPU host are never alarmed)."""
    rows = []
    dropped = []
    for name, now in sorted(now_nodes.items()):
        if not is_sovereign_gpu(now):
            continue
        prev = prev_nodes.get(name)
        prev_reachable = None if not isinstance(prev, dict) else bool(prev.get("reachable"))
        now_reachable = bool(now.get("reachable"))
        state = classify(prev_reachable, now_reachable)
        row = {
            "name": name,
            "kind": now.get("kind"),
            "endpoint": now.get("endpoint"),
            "prev_reachable": prev_reachable,
            "now_reachable": now_reachable,
            "transition": state,
            "detail": now.get("detail"),
        }
        rows.append(row)
        if state == "dropped":
            dropped.append(row)
    return rows, dropped


def load_prev(path):
    """Load the previous snapshot. Missing/empty/unreadable -> {} (first run:
    every node is 'never-seen', which never alarms — honest cold start)."""
    if not path:
        return {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception:  # noqa: BLE001 — first run / corrupt file -> clean cold start
        return {}
    nodes = data.get("nodes") if isinstance(data, dict) else None
    return nodes if isinstance(nodes, dict) else {}


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Honest sovereign-GPU node-drop detector (reachable->unreachable transition)."
    )
    ap.add_argument("--target", default="https://a11oy.net",
                    help="Base URL of the BOX (tailnet peer) serving the hardened compute-pool.")
    ap.add_argument("--prev-snapshot", default="",
                    help="Path to the previous sweep snapshot JSON (absent on first run).")
    ap.add_argument("--write-snapshot", default="",
                    help="Path to write the fresh sweep snapshot for the next run.")
    ap.add_argument("--summary-file", default="",
                    help="Optional path to write a JSON result summary (for the alert step).")
    ap.add_argument("--attempts", type=int, default=3,
                    help="Retry attempts to obtain a live probe (default 3).")
    ap.add_argument("--sleep", type=float, default=10.0,
                    help="Seconds between retries (default 10).")
    ap.add_argument("--timeout", type=float, default=20.0,
                    help="Per-request timeout seconds (default 20).")
    args = ap.parse_args(argv)

    # Obtain a live sweep with bounded retries so a transient box rebuild/restart
    # (a 5xx/000 while the Space respins) does not masquerade as a node drop.
    now_nodes = {}
    last_err = "no attempt made"
    for attempt in range(1, args.attempts + 1):
        now_nodes, err = fetch_pool(args.target, args.timeout)
        if err is None and now_nodes:
            last_err = None
            break
        last_err = err or "empty node set"
        if attempt < args.attempts:
            time.sleep(args.sleep)

    if last_err is not None:
        # We could NOT get a live probe at all. This is an OPERATIONAL error
        # (endpoint down), NOT a node-drop signal — we deliberately do not claim a
        # drop we cannot substantiate. Exit 2 (a11oy-api-health already alarms a
        # dead endpoint); we stay honest and make no node-state claim.
        print("ERROR: could not obtain a live compute-pool sweep from %s%s: %s"
              % (args.target, HARDENED_PATH, last_err), file=sys.stderr)
        summary = {
            "ok": False, "target": args.target, "error": last_err,
            "checked_at": _now_iso(), "dropped": [], "rows": [],
            "doctrine": {"lambda": "Conjecture 1", "locked": 8,
                         "reachability": "real probe only — never fabricated",
                         "report_only": True},
        }
        if args.summary_file:
            with open(args.summary_file, "w", encoding="utf-8") as fh:
                json.dump(summary, fh, indent=2)
        return 2

    prev_nodes = load_prev(args.prev_snapshot)
    rows, dropped = diff_snapshots(prev_nodes, now_nodes)

    cold_start = not prev_nodes
    print("sovereign-GPU node-drop check — target %s%s%s"
          % (args.target, HARDENED_PATH, "  [COLD START: no previous snapshot]" if cold_start else ""))
    if not rows:
        print("  (no sovereign-GPU nodes reported by the endpoint this sweep)")
    for r in rows:
        flag = {
            "dropped": "DROPPED ", "recovered": "recovered", "up": "up      ",
            "offline": "offline ", "never-seen": "never-seen",
        }.get(r["transition"], r["transition"])
        print("  %-9s %-20s prev=%-5s now=%-5s  %s"
              % (flag, r["name"], str(r["prev_reachable"]), str(r["now_reachable"]),
                 r.get("detail") or ""))

    n_dropped = len(dropped)
    print("\nRESULT: sovereign_gpu_checked=%d dropped=%d%s"
          % (len(rows), n_dropped, "  (clean — no home node dropped)" if n_dropped == 0 else ""))

    # Write the fresh snapshot for the NEXT run to diff against. We persist ALL
    # nodes (not just sovereign) so future logic can extend; only the sovereign
    # subset is ever alarmed. The snapshot is pure real probe output.
    if args.write_snapshot:
        snap = {"checked_at": _now_iso(), "target": args.target, "nodes": now_nodes}
        with open(args.write_snapshot, "w", encoding="utf-8") as fh:
            json.dump(snap, fh, indent=2)
        print("Wrote snapshot -> %s" % args.write_snapshot)

    summary = {
        "ok": n_dropped == 0,
        "target": args.target,
        "checked_at": _now_iso(),
        "cold_start": cold_start,
        "sovereign_gpu_checked": len(rows),
        "dropped": dropped,
        "rows": rows,
        "doctrine": {"lambda": "Conjecture 1", "locked": 8,
                     "reachability": "real probe only — never fabricated",
                     "report_only": True, "key_committed": False},
    }
    if args.summary_file:
        with open(args.summary_file, "w", encoding="utf-8") as fh:
            json.dump(summary, fh, indent=2)
        print("Wrote summary -> %s" % args.summary_file)

    return 1 if n_dropped else 0


if __name__ == "__main__":
    sys.exit(main())
