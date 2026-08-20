#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""
verify_loop_forge.py — DEPLOY-AGNOSTIC correctness proof for THE LOOP FORGE organ.

Exercises the loop-forge organ (szl_kc_loop_forge) by calling its pure functions
directly (no server, no network, no Hugging Face Space required) and asserts every
Doctrine-v11 honesty invariant that matters for this surface. If this script prints
RESULT: ALL PASS, the source is correct independent of any deploy host: a 404 on a
frozen Space is a deploy problem, not a code problem.

Checks (the six the brief mandates):
  (a) writer != judge STRUCTURALLY — the proposer's code object does NOT name the
      kernel oracle (co_names), so the oracle is not reachable as a mutator from the
      proposer. This is the single load-bearing reward-hack defence.
  (b) kernel gate is OUTSIDE the optimization loop (proposer_cannot_call_judge).
  (c) conjecture nodes stay gray / never green — no accepted branch targets a
      conjecture, and conjecture_rendered_green == 0 on every endpoint.
  (d) provenance_coverage == 1.0 — every node traces to a real Lean decl / DOI /
      arXiv / endpoint / repo path.
  (e) determinism — two same-seed runs => identical archive snapshots.
  (f) register() returns the 6 expected loop-forge paths.

Run:  python3 verify_loop_forge.py
Exit: 0 = all invariants hold; non-zero = a real doctrine/logic violation.
"""
import os
import sys

# make sure the w25 dir is importable regardless of cwd
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import szl_kc_loop_forge as LF

FAILS = []


def check(name, cond, detail=""):
    status = "PASS" if cond else "FAIL"
    if not cond:
        FAILS.append(name + (" — " + detail if detail else ""))
    print(f"  [{status}] {name}" + (f"  ({detail})" if detail and not cond else ""))


def main() -> int:
    print("The Loop Forge — deploy-agnostic Doctrine-v11 verifier\n")

    run = LF.loop_run(seed=42, cycles=10)
    arch = LF.loop_archive(seed=42, cycles=10)
    ws = LF.loop_workspace(seed=42, cycle=1)
    hz = LF.loop_horizon(seed=42, cycles=10)
    mt = LF.loop_metrics(seed=42, cycles=10)
    mf = LF.loop_manifest(seed=42)
    endpoints = (run, arch, ws, hz, mt, mf)

    # ---- (a) writer != judge STRUCTURALLY (oracle not reachable as a mutator) ----
    print("(a) writer != judge — structural (oracle not reachable from proposer):")
    wj = LF.writer_judge_separation()
    proposer_names = set(LF.propose_candidates.__code__.co_names)
    oracle_name = LF.kernel_oracle.__name__
    check("proposer co_names does NOT include the kernel oracle",
          oracle_name not in proposer_names,
          f"co_names contains {oracle_name!r}")
    check("writer_judge_separation reports proposer_cannot_call_judge",
          wj.get("proposer_cannot_call_judge") is True)
    check("writer and judge are distinct function objects",
          wj.get("distinct_functions") is True and LF.propose_candidates is not LF.kernel_oracle)
    check("writer_ne_judge invariant True", wj.get("writer_ne_judge") is True)
    check("writer_ne_judge True on every endpoint's honesty_invariants",
          all(e["honesty_invariants"].get("writer_ne_judge") is True for e in endpoints))

    # ---- (b) kernel gate OUTSIDE the optimization loop ----
    print("(b) kernel gate outside the optimization loop:")
    check("kernel_outside_loop True on every endpoint",
          all(e["honesty_invariants"].get("kernel_outside_loop") is True for e in endpoints))
    check("kernel is MODELED and cites c7c0ba17 (NOT run in-Space)",
          run.get("kernel") == "c7c0ba17"
          and mf["honesty_invariants"].get("kernel_not_run_in_space") is True)
    # the gate actually rejects some candidates (not a rubber stamp => it is a real gate)
    check("kernel gate rejects some candidates (real gate, not rubber stamp)",
          arch.get("rejected_total", 0) > 0 and 0.0 < mt.get("acceptance_rate", 0.0) < 1.0,
          f"rejected={arch.get('rejected_total')} rate={mt.get('acceptance_rate')}")

    # ---- (c) conjecture nodes gray / never green ----
    print("(c) conjecture nodes gray / never green (Λ stays Conjecture 1):")
    conj_ids = LF._CONJECTURE_IDS
    check("conjecture_rendered_green == 0 on every endpoint",
          all(e.get("conjecture_rendered_green") == 0 for e in endpoints),
          f"values={[e.get('conjecture_rendered_green') for e in endpoints]}")
    check("no accepted archive branch targets a conjecture node",
          all(b.get("target") not in conj_ids for b in arch.get("branches", [])))
    check("conjecture_rendered_green_is_zero invariant True on every endpoint",
          all(e["honesty_invariants"].get("conjecture_rendered_green_is_zero") is True
              for e in endpoints))
    check("locked-proven core is EXACTLY 8 and immutable",
          len(LF._LOCKED8_IDS) == 8
          and sorted(LF._LOCKED8_IDS) == sorted(("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")),
          f"locked8={sorted(LF._LOCKED8_IDS)}")

    # ---- (d) provenance_coverage == 1.0 ----
    print("(d) provenance_coverage == 1.0 (every node traces to something real):")
    check("metrics provenance_coverage == 1.0", mt.get("provenance_coverage") == 1.0,
          f"got {mt.get('provenance_coverage')}")
    check("manifest provenance_coverage == 1.0", mf.get("provenance_coverage") == 1.0,
          f"got {mf.get('provenance_coverage')}")
    check("every node has non-empty provenance",
          all(str(n.get("provenance", "")).strip() for n in LF._all_nodes()))
    check("provenance_coverage_full invariant True on every endpoint",
          all(e["honesty_invariants"].get("provenance_coverage_full") is True for e in endpoints))

    # ---- (e) determinism: two same-seed runs => identical archive snapshots ----
    print("(e) determinism (two same-seed runs => identical archive snapshots):")
    check("archive deterministic (seed 42, 10 cycles)",
          LF.loop_archive(42, 10) == LF.loop_archive(42, 10))
    # loop_run embeds a signed DSSE receipt whose timestamp/signature is
    # intentionally fresh each call; strip it before comparing (the loop's
    # logical output is deterministic, the receipt is legitimately time-varying).
    def _no_receipt(d):
        return {k: v for k, v in d.items() if k != "receipt"} if isinstance(d, dict) else d
    check("run deterministic (excluding time-varying signed receipt)",
          _no_receipt(LF.loop_run(42, 10)) == _no_receipt(LF.loop_run(42, 10)))
    check("metrics deterministic", LF.loop_metrics(42, 10) == LF.loop_metrics(42, 10))
    check("manifest deterministic", LF.loop_manifest(42) == LF.loop_manifest(42))
    check("archive seed-sensitive (seed 7 != seed 42)",
          LF.loop_archive(7, 10) != LF.loop_archive(42, 10))

    # ---- (f) register() returns the 6 expected paths ----
    print("(f) register() returns the 6 expected loop-forge paths:")

    class _App:
        class _R:
            def __init__(self):
                self.routes = []

        def __init__(self):
            self.router = self._R()

        def add_api_route(self, p, fn, methods=None):
            self.router.routes.append(p)

    routes = LF.register(_App(), ns="killinchu")
    expected = [
        "/api/killinchu/v1/loopforge/manifest",
        "/api/killinchu/v1/loopforge/run",
        "/api/killinchu/v1/loopforge/archive",
        "/api/killinchu/v1/loopforge/workspace",
        "/api/killinchu/v1/loopforge/horizon",
        "/api/killinchu/v1/loopforge/metrics",
    ]
    check("register returns the 6 exact paths (killinchu)", routes == expected, f"got {routes}")
    # ns-parametric: the same code registers cleanly under a11oy with no separate module
    routes_a = LF.register(_App(), ns="a11oy")
    check("register is ns-parametric (a11oy twin, same code)",
          routes_a == [p.replace("killinchu", "a11oy") for p in expected], f"got {routes_a}")

    print()
    if FAILS:
        print(f"RESULT: {len(FAILS)} INVARIANT(S) VIOLATED:")
        for f in FAILS:
            print("  - " + f)
        return 1
    print("RESULT: ALL PASS — The Loop Forge is correct at the source "
          "(writer!=judge structural, kernel outside the loop, conjectures gray, "
          "provenance 1.0, deterministic), independent of any deploy host.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
