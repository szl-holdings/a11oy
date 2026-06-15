#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries.
# Λ = Conjecture 1.
"""
test_check_sovereign_node_drop.py — offline self-test for the node-drop detector.

Proves the detector is HONEST by construction:
  - a sovereign node that was reachable and is now unreachable  -> DROPPED (exit 1)
  - a sovereign node that was off and is still off              -> offline (NO alarm)
  - a sovereign node NEVER seen before, now off                 -> never-seen (NO alarm)
  - a sovereign node that recovered (off -> up)                 -> recovered (NO alarm)
  - hosted-inference / CPU nodes going down                     -> never alarmed
  - the cold start (no previous snapshot) never alarms anything

Pure stdlib; no network. Mirrors test_check_a11oy_api_health.py. Run in CI before
the live probe so a logic regression is caught even when no node is actually down.
"""
from __future__ import annotations

import sys

import check_sovereign_node_drop as m


def _run():
    checks = []

    def chk(name, cond):
        checks.append((name, bool(cond)))

    # --- classify(): the five transitions, pure ------------------------------
    chk("classify_dropped", m.classify(True, False) == "dropped")
    chk("classify_recovered", m.classify(False, True) == "recovered")
    chk("classify_up", m.classify(True, True) == "up")
    chk("classify_offline", m.classify(False, False) == "offline")
    chk("classify_never_seen_off", m.classify(None, False) == "never-seen")
    chk("classify_never_seen_up", m.classify(None, True) == "up")

    # --- is_sovereign_gpu(): only sovereign + gpu kind qualifies -------------
    chk("sov_gpu_true", m.is_sovereign_gpu({"sovereign": True, "kind": "sovereign-gpu"}))
    chk("sov_tailnet_gpu_true", m.is_sovereign_gpu({"sovereign": True, "kind": "tailnet-gpu"}))
    chk("sov_cpu_false", not m.is_sovereign_gpu({"sovereign": True, "kind": "cpu"}))
    chk("sov_hosted_false", not m.is_sovereign_gpu({"sovereign": False, "kind": "hosted-inference"}))
    chk("sov_nonsov_gpu_false", not m.is_sovereign_gpu({"sovereign": False, "kind": "tailnet-gpu"}))

    # --- diff_snapshots(): the home brain drops -> exactly one DROPPED -------
    prev = {
        "hetzner-box-cpu": {"reachable": True, "sovereign": True, "kind": "cpu"},
        "rtx-betterwithage": {"reachable": False, "sovereign": True, "kind": "sovereign-gpu"},
        "omen-betterwithage": {"reachable": True, "sovereign": True, "kind": "sovereign-gpu"},
        "chaski": {"reachable": True, "sovereign": False, "kind": "tailnet-gpu"},
        "groq": {"reachable": True, "sovereign": False, "kind": "hosted-inference"},
    }
    now = {
        "hetzner-box-cpu": {"reachable": True, "sovereign": True, "kind": "cpu"},
        # laptop still off -> offline, no alarm
        "rtx-betterwithage": {"reachable": False, "sovereign": True, "kind": "sovereign-gpu", "detail": "timeout"},
        # ALWAYS-ON HOME BRAIN went unreachable -> DROPPED
        "omen-betterwithage": {"reachable": False, "sovereign": True, "kind": "sovereign-gpu", "detail": "timeout"},
        # chaski went down but it is NOT sovereign -> still surfaced as a row, classified dropped
        "chaski": {"reachable": False, "sovereign": False, "kind": "tailnet-gpu", "detail": "timeout"},
        # a brand-new sovereign GPU appears, off -> never-seen, no alarm
        "new-rig": {"reachable": False, "sovereign": True, "kind": "sovereign-gpu"},
        "groq": {"reachable": True, "sovereign": False, "kind": "hosted-inference"},
    }
    rows, dropped = m.diff_snapshots(prev, now)
    by = {r["name"]: r for r in rows}
    chk("omen_dropped", by["omen-betterwithage"]["transition"] == "dropped")
    chk("rtx_offline_not_alarmed", by["rtx-betterwithage"]["transition"] == "offline")
    chk("newrig_never_seen", by["new-rig"]["transition"] == "never-seen")
    # chaski is tailnet-gpu (sovereign:false) -> by-policy NOT in the sovereign set,
    # so it is not even a row here (only sovereign GPUs are diffed/alarmed).
    chk("chaski_not_in_sovereign_set", "chaski" not in by)
    chk("groq_never_alarmed", "groq" not in by)
    chk("cpu_never_alarmed", "hetzner-box-cpu" not in by)
    chk("exactly_one_dropped", len(dropped) == 1 and dropped[0]["name"] == "omen-betterwithage")

    # --- cold start: no previous snapshot -> every node never-seen, ZERO drops
    rows2, dropped2 = m.diff_snapshots({}, now)
    chk("cold_start_no_drop", len(dropped2) == 0)
    chk("cold_start_all_never_seen_or_up",
        all(r["transition"] in ("never-seen", "up") for r in rows2))

    # --- a node that stays up across both sweeps -> no alarm -----------------
    rows3, dropped3 = m.diff_snapshots(
        {"omen-betterwithage": {"reachable": True, "sovereign": True, "kind": "sovereign-gpu"}},
        {"omen-betterwithage": {"reachable": True, "sovereign": True, "kind": "sovereign-gpu"}},
    )
    chk("steady_up_no_drop", len(dropped3) == 0 and rows3[0]["transition"] == "up")

    # --- recovery (was down, now up) is NOT a drop ---------------------------
    rows4, dropped4 = m.diff_snapshots(
        {"omen-betterwithage": {"reachable": False, "sovereign": True, "kind": "sovereign-gpu"}},
        {"omen-betterwithage": {"reachable": True, "sovereign": True, "kind": "sovereign-gpu"}},
    )
    chk("recovery_no_drop", len(dropped4) == 0 and rows4[0]["transition"] == "recovered")

    ok = all(p for _, p in checks)
    print("sovereign-node-drop detector self-test: %d checks, %s"
          % (len(checks), "ALL PASS" if ok else "FAILURES"))
    for name, passed in checks:
        if not passed:
            print("  FAIL: %s" % name)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(_run())
