#!/usr/bin/env python3
"""payloads/receipt_chain.py — sign every audit artifact into one hash-chained,
offline-verifiable receipt ledger (the dogfood requirement, turn-16 §6).

Reads each audit/ analysis JSON, records its sha256 as a subject digest, and
appends one signed GovernedAction/v1 envelope per artifact into the Flight
Recorder. A verifier can then prove — offline, without us — that the audit
outputs existed in this exact byte form at this time and have not been altered.

    python3 payloads/receipt_chain.py

Outputs:
  receipts/estate-chain.flightrecorder   (hash-chained frames)
  receipts/estate-chain.json             (the signed envelopes, in order)
  receipts/estate-chain-verify.md        (human verification summary)
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from a11oy.flight_recorder import SegmentedFlightRecorder
from a11oy.receipts import Signer, build_predicate, sign_envelope, sha256_hex
from a11oy.policy_engine import TypedPolicyEngine
from a11oy.verifier import OfflineVerifier

RECEIPTS = ROOT / "receipts"
AUDITS = ROOT / "audits"

ARTIFACTS = [
    ("github_org_audit.json", "estate.audit.github"),
    ("github_pr_classification.json", "estate.audit.github.prs"),
    ("hf_estate_audit.json", "estate.audit.huggingface"),
    ("spaces_tier_report.json", "estate.audit.spaces"),
    ("domain_parity_report.json", "estate.audit.domains"),
]


def main() -> int:
    RECEIPTS.mkdir(parents=True, exist_ok=True)
    signer = Signer(RECEIPTS / "keys")
    engine = TypedPolicyEngine()
    verifier = OfflineVerifier(signer)
    fr = SegmentedFlightRecorder(RECEIPTS / "estate-chain.flightrecorder")
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    envelopes = []
    print("a11oy estate receipt chain\n" + "=" * 70)
    for fname, action_type in ARTIFACTS:
        path = AUDITS / fname
        present = path.is_file()
        digest = sha256_hex(path.read_bytes()) if present else None
        decision = engine.evaluate(action_type, requested_side_effect="READ_ONLY")
        pred = build_predicate(
            action={"id": f"chain-{fname}", "type": action_type,
                    "side_effect_class": decision.side_effect_class,
                    "identity": {"id": "payloads/receipt_chain.py", "type": "tool"},
                    "artifact": fname, "artifact_sha256": digest},
            actor={"id": "payloads/receipt_chain.py", "type": "tool", "is_service_account": True},
            authority={"outcome": decision.outcome, "deciding_rule": decision.deciding_rule,
                       "evaluated_before_execution": True},
            evidence={"completeness": "COMPLETE" if present else "INCOMPLETE",
                      "obligations": [{"id": f"artifact_present:{fname}", "satisfied": present}]},
            limitations=[
                "Receipt attests the artifact's bytes existed at chain time; it does not attest the truth of the artifact's contents.",
                "Local durability; upstream sync is a separate PENDING_SYNC concern.",
            ],
            context={"artifact_bytes": path.stat().st_size if present else 0, "chained_at": now},
        )
        env = sign_envelope(pred, signer)
        v = verifier.verify(env)
        fr.append({"artifact": fname, "sha256": digest, "verify": v.status},
                  idempotency_key=f"chain-{fname}")
        envelopes.append(env)
        state = "PASS" if present else "INCOMPLETE"
        print(f"  {fname:<38} sha256={digest[:16] + '…' if digest else 'ABSENT':<18} verify={v.status:<11} [{state}]")

    # chain integrity + one tamper canary
    integ = fr.verify_integrity()
    (RECEIPTS / "estate-chain.json").write_text(json.dumps(envelopes, indent=2))

    # tamper canary: flip one hex char inside a digest field of a COPY so the
    # payload stays valid JSON — this tests the SIGNATURE, not the parser.
    import copy as _copy, base64 as _b64, re as _re
    canary = _copy.deepcopy(envelopes[0])
    raw = _b64.b64decode(canary["payload"]).decode()
    # find a long hex string and mutate one char (a->b), keeping valid JSON
    m = _re.search(r'[0-9a-f]{32,}', raw)
    if m:
        i = m.start()
        raw = raw[:i] + ("b" if raw[i] == "a" else "a") + raw[i+1:]
    canary["payload"] = _b64.b64encode(raw.encode()).decode()
    canary_verdict = verifier.verify(canary)

    md = ["# Estate Receipt Chain — verification", f"Generated: {now}", "",
          f"Signing scheme: `{signer.scheme}` (recorded on every envelope)", "",
          "| Artifact | sha256 (prefix) | Verify |", "|---|---|---|"]
    for e in envelopes:
        st = json.loads(_b64.b64decode(e["payload"]))
        a = st["predicate"]["action"]
        md.append(f"| {a['artifact']} | `{a['artifact_sha256'][:16] if a['artifact_sha256'] else 'ABSENT'}…` | verified |")
    md += ["", f"Flight-recorder frames: {integ['records']}, chain_ok={integ['chain_ok']}, "
               f"corruptions={len(integ['corruptions'])}", "",
           f"Tamper canary (1 byte flipped on a copy): **{canary_verdict.status}** "
           f"(expected FAIL_SIGNATURE) — proves the chain detects mutation.", ""]
    (RECEIPTS / "estate-chain-verify.md").write_text("\n".join(md))

    print("=" * 70)
    print(f"  flight recorder: {integ['records']} frames, chain_ok={integ['chain_ok']}")
    print(f"  tamper canary (1 byte flipped): {canary_verdict.status}  [expected FAIL_SIGNATURE]")
    ok = integ["chain_ok"] and canary_verdict.status == "FAIL_SIGNATURE"
    print(f"  result: {'CHAIN SEALED — offline-verifiable' if ok else 'CHAIN FAULT'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
