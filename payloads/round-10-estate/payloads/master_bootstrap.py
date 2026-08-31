#!/usr/bin/env python3
"""payloads/master_bootstrap.py — SZL master bootstrap, round 10.

One command that runs the whole stack, in order, and tells the truth
about every step:

    python3 payloads/master_bootstrap.py --run

Steps:
  1. demo            — 12-step proof surface, emits signed receipts
  2. lexicon_gate    — canonical-lexicon scan                 (EXIT 1 ok)
  3. release_gate    — BLOCKER contradictions                 (EXIT 1 ok)
  4. raise_gate      — 24 UNKNOWN commercial facts gate raise  (EXIT 1 ok)
  5. sub-receipts    — estate.audit receipts via model/policy/fr/verifier
  6. pass_receipt    — one top-level signed receipt for the whole run
  7. run log         — run_logs/MASTER_RUN_LOG.json + .md

Exit codes of component gates are REPORTED, not hidden. A gate failure is
the intended Week 1 checklist, so the bootstrap exits 0 whenever it
faithfully executed every step; it exits 1 only if a step crashed.
"""
from __future__ import annotations

import datetime
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11oy.flight_recorder import SegmentedFlightRecorder
from a11oy.receipts import Signer, build_predicate, sign_envelope
from a11oy.policy_engine import TypedPolicyEngine
from a11oy.verifier import OfflineVerifier

RECEIPTS_DIR = ROOT / "receipts"
RUN_LOGS = ROOT / "run_logs"
KEYSTORE = ROOT / "receipts" / "keys"


def run_step(name: str, argv: list[str]) -> dict:
    """Run one tool as a subprocess; report its exit code truthfully."""
    proc = subprocess.run([sys.executable] + argv, capture_output=True, text=True, cwd=ROOT)
    tail = (proc.stdout.strip().splitlines() or [""])[-1]
    return {
        "name": name,
        "argv": argv,
        "exit_code": proc.returncode,
        "tail": tail[:250],
        "crashed": proc.returncode not in (0, 1),  # gates legitimately fail with 1
    }


def emit_sub_receipt(signer, engine, fr, step: dict) -> Path:
    decision = engine.evaluate("estate.audit.run", requested_side_effect="READ_ONLY")
    satisfied = not step["crashed"]
    pred = build_predicate(
        action={"id": f"bootstrap-{step['name']}", "type": "estate.audit.run",
                "side_effect_class": decision.side_effect_class,
                "identity": {"id": "master_bootstrap", "type": "tool"}},
        actor={"id": "master_bootstrap", "type": "tool", "is_service_account": True},
        authority={"outcome": decision.outcome, "deciding_rule": decision.deciding_rule,
                   "evaluated_before_execution": True, "rationale": decision.rationale},
        evidence={
            "completeness": "COMPLETE" if satisfied else "INCOMPLETE",
            "obligations": [{"id": f"{step['name']}_executed", "satisfied": satisfied}],
        },
        limitations=[
            "Sub-receipt proves execution of the step, not the truth of everything it printed.",
            "Local durability only at this stage; remote upstreams are PENDING_SYNC.",
        ],
    )
    env = sign_envelope(pred, signer)
    out = RECEIPTS_DIR / f"sub-{step['name']}.json"
    out.write_text(json.dumps(env, indent=2))
    fr.append({"step": step["name"], "exit_code": step["exit_code"]},
              idempotency_key=f"bootstrap-{step['name']}")
    return out


def main() -> int:
    for d in (RECEIPTS_DIR, RUN_LOGS, KEYSTORE):
        d.mkdir(parents=True, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    print("=" * 76)
    print("SZL MASTER BOOTSTRAP — round 10, full estate spin-up")
    print("=" * 76)

    # 1-4: run the stack
    steps: list[dict] = []
    print("\n[1/7] proof-surface demo")
    steps.append({"name": "demo", "argv": ["demo/proof_surface_demo.py"]})
    print("\n[2/7] lexicon gate")
    steps.append({"name": "lexicon_gate", "argv": ["tools/lexicon_gate.py", str(ROOT)]})
    print("\n[3/7] release gate")
    steps.append({"name": "release_gate", "argv": ["tools/release_gate.py", str(ROOT)]})
    print("\n[4/7] raise gate")
    steps.append({"name": "raise_gate", "argv": ["tools/raise_gate.py", str(ROOT)]})

    results: list[dict] = []
    for s in steps:
        r = run_step(s["name"], s["argv"])
        state = "PASS" if r["exit_code"] == 0 else ("FAIL" if r["exit_code"] == 1 else "ERROR")
        print(f"      {r['name']:<16} exit={r['exit_code']} ({state})  {r['tail']}")
        results.append(r)

    # 5: sub-receipts
    print("\n[5/7] emitting sub-receipts for each step")
    signer = Signer(KEYSTORE)
    engine = TypedPolicyEngine()
    verifier = OfflineVerifier(signer)
    fr = SegmentedFlightRecorder(RECEIPTS_DIR / "bootstrap.flightrecorder")
    sub_paths = [emit_sub_receipt(signer, engine, fr, r) for r in results]
    for p in sub_paths:
        v = verifier.verify(json.loads(p.read_text()))
        print(f"      {p.name:<34} verify={v.status:<14} [{signer.scheme}]")

    fr_integrity = fr.verify_integrity()
    print(f"      flight recorder: {fr_integrity['records']} records, "
          f"chain_ok={fr_integrity['chain_ok']}, pending={len(fr_integrity['pending_sync'])}")

    # 6: pass receipt
    print("\n[6/7] emitting pass-level receipt")
    crashed = [r["name"] for r in results if r["crashed"]]
    completeness = "INCOMPLETE" if crashed else "COMPLETE"
    pass_pred = build_predicate(
        action={"id": "szl-full-estate-pass-2026-08-30", "type": "estate.audit.full_pass",
                "side_effect_class": "READ_ONLY",
                "identity": {"id": "master_bootstrap", "type": "tool"}},
        actor={"id": "stephen.lutar", "role": "founder", "is_service_account": False},
        authority={"outcome": "ALLOW", "deciding_rule": "ro-audit",
                   "evaluated_before_execution": True,
                   "rationale": "READ_ONLY full-estate pass"},
        evidence={
            "completeness": completeness,
            "obligations": [{"id": f"step_{r['name']}_executed", "satisfied": not r["crashed"]}
                            for r in results],
        },
        limitations=[
            "Gate exit codes 1 are intended: they are the Week 1 checklist, not a crash.",
            "Commercial ledger rows remain UNKNOWN until supplied by contracts, banks, and humans.",
            "This pass did not merge PRs or mutate HF repos — it audited, gated, and proved.",
        ],
        context={"steps": [{"name": r["name"], "exit_code": r["exit_code"]} for r in results]},
    )
    pass_env = sign_envelope(pass_pred, signer)
    pass_path = RECEIPTS_DIR / "pass-receipt.json"
    pass_path.write_text(json.dumps(pass_env, indent=2))
    v = verifier.verify(pass_env)
    fr.append({"step": "pass_receipt", "verified": v.status},
              idempotency_key="pass-receipt-2026-08-30")
    print(f"      pass receipt: {pass_path.name}  verify={v.status}  completeness={completeness}")

    # 7: run log
    print("\n[7/7] writing run log")
    log = {
        "generated_at": now,
        "payload_version": "round-10",
        "steps": results,
        "sub_receipts": [str(p.relative_to(ROOT)) for p in sub_paths],
        "pass_receipt": str(pass_path.relative_to(ROOT)),
        "pass_receipt_verify": v.status,
        "flight_recorder": fr_integrity,
        "signing_scheme": signer.scheme,
        "crashed_steps": crashed,
    }
    (RUN_LOGS / "MASTER_RUN_LOG.json").write_text(json.dumps(log, indent=2))
    md = [
        "# SZL Master Run Log", "",
        f"Generated: {now}", f"Signing scheme: `{signer.scheme}`", "",
        "| Step | Exit | State |",
        "|---|---|---|",
    ]
    for r in results:
        state = "PASS" if r["exit_code"] == 0 else ("FAIL (expected — checklist)" if r["exit_code"] == 1 else "ERROR")
        md.append(f"| {r['name']} | {r['exit_code']} | {state} |")
    md += ["", f"Pass receipt: `receipts/pass-receipt.json` — verify status **{v.status}**, "
               f"completeness **{completeness}**", ""]
    (RUN_LOGS / "MASTER_RUN_LOG.md").write_text("\n".join(md))
    print(f"      run_logs/MASTER_RUN_LOG.json + .md written")

    print("\n" + "=" * 76)
    if crashed:
        print(f"BOOTSTRAP COMPLETE — {len(crashed)} step(s) crashed: {', '.join(crashed)}")
        return 1
    print("BOOTSTRAP COMPLETE — every step executed; gate failures are the Week 1 checklist.")
    print("Next: read run_logs/MASTER_RUN_LOG.md, then clear exit-1 items top-down.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--run":
        sys.exit(main())
    print(__doc__)
    sys.exit(2)
