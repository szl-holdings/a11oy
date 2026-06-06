#!/usr/bin/env python3
"""
hello-mesh/hello_mesh.py
Write a receipted CRDT state change to SZL-MESH (Inventions 1 & 2).

Doctrine: v11 LOCKED 749/14/163 · Kernel commit c7c0ba17 · SLSA L1

DCO:
  Signed-off-by: Yachay <yachay@szlholdings.ai>
  Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""

import os
import sys
import json
import base64
import hashlib
from datetime import datetime, timezone

# ── Locked constants — NEVER MODIFY without new doctrine release ──
DOCTRINE_VERSION = "749/14/163"
KERNEL_COMMIT    = "c7c0ba17"
SLSA_LEVEL       = "L1"
SECTION_889_VENDORS = ["Huawei", "ZTE", "Hytera", "Hikvision", "Dahua"]


def build_state_transition_statement(
    crdt_doc_id: str,
    change_hash: str,
    from_heads: list[str],
    to_heads: list[str],
    node_id: str,
    transition_class: str = "PLATFORM_STATUS",
) -> dict:
    """
    Constructs the StateTransitionStatement payload for a DSSE receipt.
    See spec/01-dsse-receipts.md §3 for field semantics.

    Invention 1: Doctrine-Pinned DSSE Receipts on CRDT State Transitions.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "type": "szl-mesh/state-transition/v1",
        "doctrine_version": DOCTRINE_VERSION,   # LOCKED — never change
        "kernel_commit": KERNEL_COMMIT,          # LOCKED — never change
        "crdt_document_id": crdt_doc_id,
        "change_hash": change_hash,
        "from_state_head": from_heads,
        "to_state_head": to_heads,
        "transition_class": transition_class,
        "node_id": node_id,
        "timestamp_utc": now_utc,
        "policy_context": {
            "section_889_vendors": SECTION_889_VENDORS,  # exactly 5
            "slsa_level": SLSA_LEVEL,
        },
    }


def pae(payload_type: str, payload: bytes) -> bytes:
    """
    DSSE Pre-Authentication Encoding (PAE).
    PAE(type, body) = "DSSEv1" SP LEN(type) SP type SP LEN(body) SP body
    Reference: https://github.com/secure-systems-lab/dsse/blob/master/protocol.md
    """
    def enc_len(s: bytes) -> bytes:
        return str(len(s)).encode()

    t = payload_type.encode()
    return b" ".join([b"DSSEv1", enc_len(t), t, enc_len(payload), payload])


def build_dsse_envelope(stmt: dict, node_id: str) -> dict:
    """
    Wraps the StateTransitionStatement in a DSSE envelope.
    In production: sign pae(payload_type, payload) with Ed25519 private key.
    This stub returns a placeholder signature for demonstration.
    """
    payload_type = "application/vnd.szl.mesh.state-transition+json"
    stmt_json = json.dumps(stmt, separators=(",", ":")).encode()
    payload_b64 = base64.urlsafe_b64encode(stmt_json).decode().rstrip("=")

    signing_input = pae(payload_type, stmt_json)

    # TODO: replace with actual Ed25519 sign(signing_input, private_key)
    # from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    # sig_bytes = private_key.sign(signing_input)
    sig_placeholder = hashlib.sha256(signing_input).hexdigest()
    sig_b64 = base64.urlsafe_b64encode(sig_placeholder.encode()).decode()

    return {
        "payloadType": payload_type,
        "payload": payload_b64,
        "signatures": [
            {
                "keyid": node_id,
                "sig": sig_b64,
                # NOTE: placeholder — production must use real Ed25519 sig
            }
        ],
    }


def main() -> int:
    print("=" * 60)
    print("SZL-MESH Hello-World Example")
    print(f"  Doctrine: {DOCTRINE_VERSION}  (Invention 1: DSSE Receipts)")
    print(f"  Kernel:   {KERNEL_COMMIT}")
    print(f"  SLSA:     {SLSA_LEVEL}")
    print("=" * 60)
    print()

    # ── Simulate a CRDT Automerge change ─────────────────────────
    change_data = json.dumps({
        "platform_id": "node-alpha",
        "status": "ONLINE",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }).encode()

    change_hash = hashlib.sha256(change_data).hexdigest()
    node_id     = hashlib.sha256(b"hello-mesh-demo-pubkey").hexdigest()
    from_heads  = ["0000000000000000000000000000000000000000000000000000000000000000"]
    to_heads    = [change_hash]

    print(f"[1/4] Simulated CRDT change:")
    print(f"      change_hash = {change_hash}")
    print()

    # ── Build StateTransitionStatement ───────────────────────────
    stmt = build_state_transition_statement(
        crdt_doc_id="hello-formation-001/platforms",
        change_hash=change_hash,
        from_heads=from_heads,
        to_heads=to_heads,
        node_id=node_id,
        transition_class="PLATFORM_STATUS",
    )

    print("[2/4] StateTransitionStatement (Invention 1):")
    print(json.dumps(stmt, indent=2))
    print()

    # ── Wrap in DSSE envelope ─────────────────────────────────────
    envelope = build_dsse_envelope(stmt, node_id)

    print("[3/4] DSSE Envelope:")
    print(f"      payloadType: {envelope['payloadType']}")
    print(f"      payload:     {envelope['payload'][:48]}...")
    print(f"      keyid:       {envelope['signatures'][0]['keyid'][:16]}...")
    print(f"      sig:         {envelope['signatures'][0]['sig'][:32]}...")
    print(f"      NOTE: sig is a placeholder — production requires real Ed25519")
    print()

    # ── Describe two-track classification ────────────────────────
    print("[4/4] Two-Track State (Invention 2):")
    print("      With a valid Ed25519 signature (production), this change")
    print("      passes Receipt Gate validation and appears on:")
    print("        AUTHORIZED track → GetAuthorizedPlatforms RPC")
    print("        Rosie: solid indicator — actionable for command decisions")
    print()
    print("      Without valid signature (this demo):")
    print("        OBSERVED track  → GetObservedPlatforms RPC")
    print("        Rosie: dashed indicator — situational awareness only")
    print()

    print("=" * 60)
    print("Sentra governance event would emit (Invention 7):")
    sentra_event = {
        "event_type": "szl_mesh_state_transition",
        "formation_id": "hello-formation-001",
        "change_hash": change_hash,
        "receipt_status": "AUTHORIZED",  # if sig were real
        "corroboration_status": "PENDING",
        "track": "AUTHORIZED",
        "transition_class": "PLATFORM_STATUS",
        "doctrine_version": DOCTRINE_VERSION,
        "kernel_commit": KERNEL_COMMIT,
        "latency_ms": 0,
    }
    print(json.dumps(sentra_event, indent=2))
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
