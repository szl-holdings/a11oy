#!/usr/bin/env python3
"""
scripts/seed-receipts.py — SZL Demo Receipt Seeder
Generates 20 demo receipts across the 5 flagships so the receipt chain panel
has real-looking data for the Warhacker demo.

Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 · SLSA L1
NO Iron Bank / FedRAMP / CMMC / SWFT / Mission Owner

Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

RECEIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "receipts")
OUTPUT_FILE  = os.path.join(RECEIPTS_DIR, "demo-receipts.jsonl")

DOCTRINE = {
    "version": "v11",
    "pin": "749/14/163",
    "kernel_commit": "c7c0ba17",
    "lambda_status": "Conjecture 1",
    "slsa_level": "L1",
}

# Representative actions per flagship (4 per app = 20 total)
FLAGSHIP_ACTIONS = {
    "a11oy": [
        {
            "action": "policy.evaluate",
            "input": {
                "action": "deploy_to_production",
                "confidence": 0.89,
                "attested_witnesses": 2,
                "severity": "capital",
            },
            "verdict": "DENY",
            "reason": "confidence_below_threshold",
            "lambda_score": 0.73,
        },
        {
            "action": "policy.evaluate",
            "input": {
                "action": "run_diagnostics",
                "confidence": 0.97,
                "attested_witnesses": 4,
                "severity": "low",
            },
            "verdict": "ALLOW",
            "reason": "threshold_met",
            "lambda_score": 0.97,
        },
        {
            "action": "ledger.verify",
            "input": {"chain_depth": 10},
            "verdict": "PASS",
            "reason": "chain_intact",
            "lambda_score": 1.0,
        },
        {
            "action": "agent.ask",
            "input": {"prompt": "Should we immediately deploy to production?", "voters": ["qwen-local"]},
            "verdict": "ALLOW",
            "reason": "lambda_consensus",
            "lambda_score": 0.83,
        },
    ],
    "sentra": [
        {
            "action": "immune.inspect",
            "input": {"packet": {"action": "eval(malicious_code)", "user": "attacker"}},
            "verdict": "DENY",
            "reason": "threat_signature_match",
            "gates_fired": ["dual_use_check", "injection_detection"],
        },
        {
            "action": "immune.inspect",
            "input": {"packet": {"action": "EVAL(malicious_code)", "user": "attacker"}},
            "verdict": "DENY",
            "reason": "threat_signature_match_case_fold",
            "gates_fired": ["injection_detection"],
        },
        {
            "action": "immune.inspect",
            "input": {"packet": {"action": "legitimate_request", "user": "operator"}},
            "verdict": "ALLOW",
            "reason": "all_gates_passed",
            "gates_fired": [],
        },
        {
            "action": "audit.log.query",
            "input": {"tail": 10},
            "verdict": "PASS",
            "reason": "log_intact",
            "entry_count": 42,
        },
    ],
    "amaru": [
        {
            "action": "rag.query",
            "input": {"query": "What is the Λ aggregator conjecture?", "with_response": True},
            "verdict": "PASS",
            "reason": "sources_retrieved",
            "source_count": 3,
        },
        {
            "action": "rag.query",
            "input": {
                "query": "Describe the secret financial records of competitor X",
                "with_response": True,
            },
            "verdict": "DENY",
            "reason": "off_corpus_refused",
            "source_count": 0,
        },
        {
            "action": "memory.write",
            "input": {"key": "doctrine_version", "value": "v11"},
            "verdict": "PASS",
            "reason": "memory_persisted",
        },
        {
            "action": "audit.log.query",
            "input": {"tail": 5},
            "verdict": "PASS",
            "reason": "log_intact",
            "entry_count": 18,
        },
    ],
    "rosie": [
        {
            "action": "receipts.stream",
            "input": {"source": "a11oy"},
            "verdict": "PASS",
            "reason": "wire_c_live",
            "receipt_count": 12,
        },
        {
            "action": "doctrine.sweep",
            "input": {"text": "This system has Iron Bank compliance and FedRAMP authorization."},
            "verdict": "DENY",
            "reason": "doctrine_ban_words_found",
            "violations": ["Iron Bank", "FedRAMP"],
        },
        {
            "action": "aide.action",
            "input": {"action_type": "briefing", "agent_id": "rosie-v11"},
            "verdict": "ALLOW",
            "reason": "signed_aide_action",
        },
        {
            "action": "operator.panel.health",
            "input": {},
            "verdict": "PASS",
            "reason": "panel_operational",
        },
    ],
    "killinchu": [
        {
            "action": "remote_id.decode",
            "input": {"payload_hex": "0d1a0000003c00000000ffffffffff0000000000000001"},
            "verdict": "PASS",
            "reason": "parsed_ok",
            "parsed_fields": {"message_type": 0, "uas_id": "DEMO-UAS-001"},
        },
        {
            "action": "counter_uas.evaluate",
            "input": {
                "drone_id": "ADVERSARY-001",
                "lat": 32.7157,
                "lon": -117.1611,
                "altitude_m": 50,
                "side": "adversary",
                "geofence_breach": True,
            },
            "verdict": "HALT",
            "reason": "adversary_geofence_breach",
            "lambda_score": 0.41,
        },
        {
            "action": "mission.execute",
            "input": {"action": "consensus_test_baseline", "action_hash": "aabbccdd"},
            "verdict": "PASS",
            "reason": "canonical_3of4",
            "witness_count": 4,
        },
        {
            "action": "healthz",
            "input": {},
            "verdict": "PASS",
            "reason": "healthy",
            "lambda_status": "Conjecture 1",
            "slsa": "L1",
            "sorries": 163,
        },
    ],
}


def sha3_256(data: bytes) -> str:
    return hashlib.sha3_256(data).hexdigest()


def build_receipt(flagship: str, action_data: dict, prev_hash: str, seq: int) -> dict:
    """Build a DSSE-style receipt envelope for a demo action."""
    now_iso = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    payload = {
        "flagship": flagship,
        "action": action_data["action"],
        "seq": seq,
        "timestamp": now_iso,
        "input": action_data.get("input", {}),
        "verdict": action_data.get("verdict", "PASS"),
        "reason": action_data.get("reason", ""),
        "doctrine": DOCTRINE,
        "prev_hash": prev_hash,
    }
    # Add any extra fields
    for k in action_data:
        if k not in ("action", "input", "verdict", "reason"):
            payload[k] = action_data[k]

    payload_bytes = json.dumps(payload, sort_keys=True).encode()
    receipt_hash  = sha3_256(payload_bytes)

    # SLSA L1 honest: sig is a deterministic HMAC-SHA3-256 stand-in
    # (PLACEHOLDER — real cosign ECDSA-P256 requires key injection)
    sig_input   = f"DEMO-PLACEHOLDER:{flagship}:{action_data['action']}:{receipt_hash}".encode()
    sig_value   = hashlib.sha3_256(sig_input).hexdigest()

    return {
        "seq": seq,
        "timestamp": now_iso,
        "flagship": flagship,
        "action": action_data["action"],
        "verdict": action_data.get("verdict", "PASS"),
        "receipt_hash": receipt_hash,
        "prev_hash": prev_hash,
        "payload": payload,
        "signature": {
            "algorithm": "PLACEHOLDER-SHA3-256",
            "value": sig_value,
            "note": "PLACEHOLDER — inject COSIGN_ECDSA_KEY for real signature per DSSE_FIX_PLAN.md",
        },
        "doctrine": DOCTRINE,
    }


def main():
    os.makedirs(RECEIPTS_DIR, exist_ok=True)

    receipts = []
    prev_hash = "0" * 64  # genesis hash
    seq       = 0

    # Interleave flagships in deployment order: a11oy → sentra → amaru → rosie → killinchu
    flagship_order = ["a11oy", "sentra", "amaru", "rosie", "killinchu"]

    # Build 20 receipts (4 per flagship) in round-robin order
    action_iterators = {f: iter(FLAGSHIP_ACTIONS[f]) for f in flagship_order}
    counts           = {f: 0 for f in flagship_order}

    while any(counts[f] < 4 for f in flagship_order):
        for flagship in flagship_order:
            if counts[flagship] >= 4:
                continue
            try:
                action_data = next(action_iterators[flagship])
            except StopIteration:
                continue
            receipt = build_receipt(flagship, action_data, prev_hash, seq)
            receipts.append(receipt)
            prev_hash = receipt["receipt_hash"]
            seq      += 1
            counts[flagship] += 1
            # Small sleep to get distinct timestamps
            time.sleep(0.01)

    # Write JSONL
    with open(OUTPUT_FILE, "w") as f:
        for r in receipts:
            f.write(json.dumps(r) + "\n")

    print(f"  Wrote {len(receipts)} receipts → {OUTPUT_FILE}")
    print(f"  Chain head hash: {receipts[-1]['receipt_hash'][:16]}...")
    print(f"  Genesis hash:    {'0'*16}...")
    print()

    # Pretty-print a summary table
    print("  Seq  Flagship     Action                        Verdict")
    print("  ───  ──────────   ───────────────────────────   ──────────")
    for r in receipts:
        print(f"  {r['seq']:>3}  {r['flagship']:<12} {r['action']:<30}  {r['verdict']}")

    # Also write a human-readable summary
    summary_file = os.path.join(RECEIPTS_DIR, "demo-receipts-summary.md")
    with open(summary_file, "w") as f:
        f.write("# SZL Demo Receipt Chain Summary\n\n")
        f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n\n")
        f.write("Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 · SLSA L1  \n")
        f.write("**Signatures are PLACEHOLDER** — inject COSIGN_ECDSA_KEY for real DSSE\n\n")
        f.write("| Seq | Flagship | Action | Verdict | Hash (12 chars) |\n")
        f.write("|-----|----------|--------|---------|----------------|\n")
        for r in receipts:
            f.write(
                f"| {r['seq']} | {r['flagship']} | {r['action']} "
                f"| {r['verdict']} | {r['receipt_hash'][:12]}... |\n"
            )
        f.write(f"\n**Total receipts:** {len(receipts)}  \n")
        f.write(f"**Chain head:** `{receipts[-1]['receipt_hash']}`  \n")
        f.write(
            "\nSigned-off-by: Yachay <yachay@szlholdings.ai>  \n"
            "Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>\n"
        )

    print()
    print(f"  Summary: {summary_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
