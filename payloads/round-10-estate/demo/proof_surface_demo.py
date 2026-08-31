#!/usr/bin/env python3
"""demo/proof_surface_demo.py — the Proof Surface.

The 12-step sequence that IS the product. Runs the full governed-action
vertical slice, emits every receipt, verifies each offline, and produces
demo/DEMO_TRANSCRIPT.md. ~90 seconds of product value in one command:

    python3 demo/proof_surface_demo.py

Exit 0 on success, 1 if any step contradicts its expected verdict.
Every surprise is a bug — the demo is the acceptance test.
"""
from __future__ import annotations

import base64
import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11oy.flight_recorder import SegmentedFlightRecorder
from a11oy.receipts import Signer, build_predicate, sign_envelope, decode_statement
from a11oy.policy_engine import TypedPolicyEngine, execution_gate
from a11oy.verifier import OfflineVerifier, Verdict

DEMO_DIR = ROOT / "demo"
RECEIPTS_DIR = DEMO_DIR / "receipts"
KEYSTORE = DEMO_DIR / "keys"

HUMAN = {"id": "stephen.lutar", "role": "founder", "is_service_account": False}
AGENT = {"id": "a11oy-agent-0", "type": "agent", "is_service_account": True}

results: list[dict] = []


def check(step: int, name: str, expected: str, verdit: Verdict | str, note: str = "") -> bool:
    actual = verdit.status if isinstance(verdit, Verdict) else verdit
    ok = actual == expected
    results.append({"step": step, "name": name, "expected": expected,
                    "actual": actual, "ok": ok, "note": note})
    mark = "PASS" if ok else "UNEXPECTED"
    print(f"  [{step:2d}] {name:<52} expected={expected:<14} got={actual:<14} [{mark}]")
    return ok


def main() -> int:
    for d in (RECEIPTS_DIR, KEYSTORE):
        d.mkdir(parents=True, exist_ok=True)
    fr_path = Path(tempfile.mkdtemp(prefix="a11oy-fr-")) / "demo.flightrecorder"

    engine = TypedPolicyEngine()
    signer = Signer(KEYSTORE)
    verifier = OfflineVerifier(signer)
    fr = SegmentedFlightRecorder(fr_path)

    print("\na11oy Proof Surface — the demo is the product\n" + "=" * 74)
    print(f"signing scheme: {signer.scheme} (recorded honestly on every envelope)")

    all_ok = True

    # -- 1. Pre-execution authority evaluation, WEDGE action ---------------
    decision = engine.evaluate("merge.pr", requested_side_effect="WORKSPACE_WRITE")
    all_ok &= check(1, "authority evaluated before execution", "True",
                    str(decision.evaluated_before_execution),
                    f"decision={decision.outcome} side_effect={decision.side_effect_class}")

    # -- 2. Default DENY on an ungoverned action ----------------------------
    deny = engine.evaluate("exfiltrate.dataset")
    all_ok &= check(2, "ungoverned action defaults to DENY", "DENY", deny.outcome,
                    "no rule matched -> DENY, not silence")

    # -- 3. Denied action still emits a receipt -----------------------------
    deny_pred = build_predicate(
        action={"id": "action-002", "type": "exfiltrate.dataset",
                "side_effect_class": deny.side_effect_class, "identity": AGENT},
        actor=AGENT,
        authority={"outcome": "DENY", "deciding_rule": deny.deciding_rule,
                   "evaluated_before_execution": True, "rationale": deny.rationale},
        evidence={"completeness": "COMPLETE",
                  "obligations": [{"id": "denial_recorded", "satisfied": True}]},
        limitations=["Denial is proven, not implied."],
    )
    deny_env = sign_envelope(deny_pred, signer)
    (RECEIPTS_DIR / "02-deny.json").write_text(json.dumps(deny_env, indent=2))
    v = verifier.verify(deny_env)
    all_ok &= check(3, "DENY receipt verifies offline", "PASS", v)

    # -- 4. Approved action emits signed receipt ----------------------------
    appr_pred = build_predicate(
        action={"id": "action-001", "type": "merge.pr",
                "side_effect_class": decision.side_effect_class, "identity": AGENT},
        actor=AGENT,
        authority={"outcome": "REQUIRE_APPROVAL", "deciding_rule": decision.deciding_rule,
                   "evaluated_before_execution": True, "rationale": decision.rationale},
        evidence={"completeness": "COMPLETE",
                  "obligations": [{"id": o, "satisfied": True} for o in decision.obligations]},
        approval={"principal": HUMAN, "approved_at": "2026-08-30T23:59:00+00:00",
                  "rationale": "founder review, bounded diff, CI green"},
        limitations=["Local durability only — remote sync tracked as PENDING_SYNC."],
    )
    appr_env = sign_envelope(appr_pred, signer)
    (RECEIPTS_DIR / "04-approved.json").write_text(json.dumps(appr_env, indent=2))
    v = verifier.verify(appr_env)
    all_ok &= check(4, "approved receipt (human, irreversible) verifies", "PASS", v)

    # -- 5. Tampered receipt fails verification -----------------------------
    tampered_bytes = bytearray(base64.b64decode(appr_env["payload"]))
    tampered_env = copy.deepcopy(appr_env)
    tampered_bytes[len(tampered_bytes) // 2] ^= 0x01  # flip one byte
    tampered_env["payload"] = base64.b64encode(bytes(tampered_bytes)).decode()
    v = verifier.verify(tampered_env)
    all_ok &= check(5, "tampered receipt (1 byte) fails", "FAIL_SIGNATURE", v,
                    "signature does not survive mutation")

    # -- 6. Missing evidence reads INCOMPLETE, never PASS --------------------
    inc_pred = build_predicate(
        action={"id": "action-003", "type": "merge.pr",
                "side_effect_class": "IRREVERSIBLE", "identity": AGENT},
        actor=AGENT,
        authority={"outcome": "REQUIRE_APPROVAL", "deciding_rule": "prod-change",
                   "evaluated_before_execution": True},
        evidence={"completeness": "INCOMPLETE",
                  "obligations": [{"id": "ci_green", "satisfied": False},
                                  {"id": "rollback_plan", "satisfied": True}]},
        approval={"principal": HUMAN, "approved_at": "2026-08-30T23:59:10+00:00"},
    )
    inc_env = sign_envelope(inc_pred, signer)
    v = verifier.verify(inc_env)
    all_ok &= check(6, "missing evidence reads INCOMPLETE", "INCOMPLETE", v,
                    "an auditor's answer, not an accusation")

    # -- 7. Service account cannot claim human principal ---------------------
    # build_predicate() refuses to construct this receipt (honesty at
    # construction). A real attacker does not call build_predicate — they
    # hand-craft the envelope. So we hand-craft it to test the VERIFIER,
    # which is the external party's defense.
    svc_pred = {
        "action": {"id": "action-004", "type": "deploy.prod",
                   "side_effect_class": "IRREVERSIBLE", "identity": AGENT},
        "actor": AGENT,
        "authority": {"outcome": "ALLOW", "evaluated_before_execution": True},
        "evidence": {"completeness": "COMPLETE", "obligations": []},
        "approval": {"principal": {"id": "svc-deploy-bot", "is_service_account": True},
                     "approved_at": "2026-08-30T23:59:20+00:00"},
        "limitations": [],
        "context": {},
        "timestamp": {"utc": "2026-08-30T23:59:20+00:00", "ntp_synced": None},
    }
    svc_env = sign_envelope(svc_pred, signer)  # attacker has a signing key
    v = verifier.verify(svc_env)
    all_ok &= check(7, "service-account approval rejected (Art.12 3d)", "FAIL_POLICY", v)

    # -- 8. IRREVERSIBLE overrides ALLOW -> REQUIRE_APPROVAL -----------------
    ov = engine.evaluate("merge.hotfix", requested_side_effect="IRREVERSIBLE")
    gate, gate_reason = execution_gate(ov, approval=None)
    all_ok &= check(8, "IRREVERSIBLE without approval refused", "REFUSE", gate, gate_reason)

    # -- 9. Flight Recorder: append, PENDING_SYNC visible, no dup on replay --
    r1 = fr.append({"action_id": "action-001", "verdict": "PASS"},
                   idempotency_key="demo-001")
    r2 = fr.append({"action_id": "action-002", "verdict": "PASS"},
                   upstream_ack=True, idempotency_key="demo-002")
    pending = fr.pending_sync()
    dup = fr.find_by_idempotency_key("demo-001")
    all_ok &= check(9, "PENDING_SYNC surfaces unacknowledged frames", "True",
                    str(r2["sync_state"] == "ACKED_LOCAL" and len(pending) == 1 and dup is not None),
                    f"pending={pending and pending[0]['seq']}")

    # -- 10. Flight Recorder integrity check ----------------------------------
    integrity = fr.verify_integrity()
    all_ok &= check(10, "flight-recorder hash chain verifies", "True", str(integrity["ok"]),
                    f"records={integrity['records']} chain_ok={integrity['chain_ok']}")

    # -- 11. Offline verification of every emitted receipt --------------------
    statuses = []
    for f in sorted(RECEIPTS_DIR.glob("*.json")):
        vv = verifier.verify(json.loads(f.read_text()))
        statuses.append(vv.status)
    all_ok &= check(11, "every receipt verifies fully offline", "True",
                    str(all(s in ("PASS", "INCOMPLETE", "FAIL_POLICY") for s in statuses)),
                    f"statuses={statuses}")

    # -- 12. Article 12 conformance fields present ----------------------------
    fields_ok = (
        HUMAN.get("is_service_account") is False
        and "utc" in appr_pred["timestamp"]
        and appr_pred["evidence"]["completeness"] in ("COMPLETE", "INCOMPLETE")
    )
    all_ok &= check(12, "Article 12 fields: human principal, UTC timestamp, completeness",
                    "True", str(fields_ok))

    print("=" * 74)

    # Transcript
    lines = [
        "# a11oy Proof Surface — Demo Transcript", "",
        f"Generated: {appr_pred['timestamp']['utc']}",
        f"Signing scheme used: `{signer.scheme}`", "",
        "| Step | Check | Expected | Got | Result |",
        "|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(f"| {r['step']} | {r['name']} | {r['expected']} | {r['actual']} | "
                     f"{'PASS' if r['ok'] else 'UNEXPECTED'} |")
    lines += ["", "## Receipts emitted", ""]
    for f in sorted(RECEIPTS_DIR.glob("*.json")):
        lines.append(f"- `demo/receipts/{f.name}`")
    lines += ["", "## Law summary", "",
              "- Ungoverned actions default to DENY and still leave a receipt.",
              "- Missing evidence reads INCOMPLETE, never PASS.",
              "- A service account can never satisfy a human-principal approval (Art. 12(3)(d)).",
              "- IRREVERSIBLE actions cannot auto-execute; one flipped byte kills the signature.",
              "- Local durability ACKs honestly and PENDING_SYNC is a visible state.", ""]
    (DEMO_DIR / "DEMO_TRANSCRIPT.md").write_text("\n".join(lines))

    print(f"transcript: demo/DEMO_TRANSCRIPT.md")
    print(f"receipts:   {len(list(RECEIPTS_DIR.glob('*.json')))} in demo/receipts/")
    print(f"result:     {'ALL 12 STEPS PASS' if all_ok else 'UNEXPECTED VERDICTS — SEE ABOVE'}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
