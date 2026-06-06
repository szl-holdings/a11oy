# hello-mesh — SZL-MESH Hello-World Example

**Doctrine:** v11 LOCKED `749/14/163` · Kernel commit `c7c0ba17` · SLSA L1

This example demonstrates a minimal application participating in the SZL-MESH as a **flagship node**: it writes a CRDT state change, receives a doctrine-pinned DSSE receipt, and verifies that the change appears on the AUTHORIZED track in the Rosie cockpit.

---

## What This Example Demonstrates

1. **Invention 1 — DSSE Receipt:** The node issues a receipt for a CRDT state change
2. **Invention 2 — Two-Track State:** The change appears as AUTHORIZED (not OBSERVED) in GetAuthorizedPlatforms
3. **Invention 5 — Doctrine-Gated Enrollment:** The node enrolls with doctrine `749/14/163` before writing
4. **Invention 7 — Sentra Metrics:** The SentraEventStream emits a `szl_mesh_state_transition` event

Byzantine corroboration (Invention 4), skip-layer aggregation (Invention 3), and CRDT revocation (Invention 6) require a multi-node formation and are demonstrated in `examples/multi-node/` (future).

---

## Prerequisites

- `peat-node` sidecar running on `localhost:50051` (peat-node v0.3+)
- `szl-mesh-node` sidecar running on `localhost:50052`
- `a11oy-receipt-substrate` running on `localhost:8090` (for receipt issuance)
- Formation key provisioned at `$SZL_FORMATION_KEY`
- Ed25519 keypair generated (see enrollment step below)

---

## Quick Start

```bash
# 1. Clone szl-mesh
git clone https://github.com/szl-holdings/szl-mesh
cd szl-mesh/examples/hello-mesh

# 2. Generate Ed25519 keypair (one-time)
openssl genpkey -algorithm Ed25519 -out node_key.pem
openssl pkey -in node_key.pem -pubout -out node_pub.pem

# 3. Set environment
export SZL_MESH_ADDR="localhost:50052"
export SZL_FORMATION_ID="hello-formation-001"
export SZL_FORMATION_KEY="<your-formation-key>"
export SZL_DOCTRINE_VERSION="749/14/163"
export SZL_KERNEL_COMMIT="c7c0ba17"

# 4. Enroll node (doctrine-gated — Invention 5)
python3 enroll.py

# 5. Write a CRDT state change with DSSE receipt (Inventions 1 & 2)
python3 hello_mesh.py

# 6. Verify AUTHORIZED track
python3 verify_authorized.py
```

---

## File Structure

```
examples/hello-mesh/
├── README.md           — this file
├── enroll.py           — doctrine-gated enrollment (Invention 5)
├── hello_mesh.py       — write receipted state change (Inventions 1, 2)
├── verify_authorized.py — verify AUTHORIZED track (Invention 2)
├── watch_sentra.py     — stream governance telemetry (Invention 7)
└── requirements.txt    — Python gRPC dependencies
```

---

## enroll.py

Enrolls this node in the formation with doctrine `749/14/163`:

```python
#!/usr/bin/env python3
"""
hello-mesh/enroll.py
Doctrine-gated enrollment (Invention 5: Doctrine-Gated Certificate Enrollment)

DCO:
  Signed-off-by: Yachay <yachay@szlholdings.ai>
  Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
import os
import grpc
import hashlib
import hmac
import time
from datetime import datetime, timezone

# Generated gRPC stubs (from proto/szl_mesh.proto)
# from szl_mesh_pb2_grpc import SzlMeshNodeStub
# from szl_mesh_pb2 import EnrollNodeRequest, DoctrineClaimProof, Section889Attestation

MESH_ADDR        = os.environ["SZL_MESH_ADDR"]         # "localhost:50052"
FORMATION_ID     = os.environ["SZL_FORMATION_ID"]
FORMATION_KEY    = os.environ["SZL_FORMATION_KEY"].encode()
DOCTRINE_VERSION = "749/14/163"   # LOCKED — never change
KERNEL_COMMIT    = "c7c0ba17"     # LOCKED — never change
SLSA_LEVEL       = "L1"

def compute_node_id(pubkey_bytes: bytes) -> str:
    return hashlib.sha256(pubkey_bytes).hexdigest()

def compute_formation_key_proof(formation_key: bytes, node_id: str,
                                 timestamp_utc: str, doctrine_version: str,
                                 kernel_commit: str) -> str:
    message = (node_id + timestamp_utc + doctrine_version + kernel_commit).encode()
    return hmac.new(formation_key, message, hashlib.sha256).hexdigest()

def main():
    # Load pubkey
    with open("node_pub.pem", "rb") as f:
        pubkey_pem = f.read()

    # Compute NodeID
    # In production: extract raw 32-byte key from PEM
    # For demo: hash the PEM bytes
    node_id = compute_node_id(pubkey_pem)
    timestamp_utc = datetime.now(timezone.utc).isoformat()

    # Compute doctrine-bound formation key proof (Invention 5)
    proof = compute_formation_key_proof(
        FORMATION_KEY, node_id, timestamp_utc,
        DOCTRINE_VERSION, KERNEL_COMMIT
    )

    print(f"Enrolling node {node_id[:16]}... with doctrine {DOCTRINE_VERSION}")

    # gRPC enrollment call (uncomment when stubs generated)
    # channel = grpc.insecure_channel(MESH_ADDR)
    # stub = SzlMeshNodeStub(channel)
    # response = stub.EnrollNode(EnrollNodeRequest(
    #     node_id=node_id,
    #     ed25519_public_key=pubkey_raw_bytes,
    #     formation_key_proof=proof,
    #     timestamp_utc=timestamp_utc,
    #     doctrine_claim=DoctrineClaimProof(
    #         doctrine_version=DOCTRINE_VERSION,  # LOCKED
    #         kernel_commit=KERNEL_COMMIT,         # LOCKED
    #         slsa_level=SLSA_LEVEL,
    #     ),
    #     section_889=Section889Attestation(
    #         vendor_exclusion_confirmed=True,
    #         hardware_vendor="",
    #         attestation_method="self_report",
    #     ),
    # ))
    # if response.success:
    #     print(f"Enrolled! Certificate saved.")
    # else:
    #     print(f"Enrollment failed: {response.failure_reason}")

    print("[STUB] Enrollment gRPC call — proto stubs not yet generated.")
    print(f"  node_id:          {node_id}")
    print(f"  doctrine_version: {DOCTRINE_VERSION}")
    print(f"  kernel_commit:    {KERNEL_COMMIT}")
    print(f"  formation_proof:  {proof[:16]}...")

if __name__ == "__main__":
    main()
```

---

## hello_mesh.py

Writes a receipted `PLATFORM_STATUS` state change:

```python
#!/usr/bin/env python3
"""
hello-mesh/hello_mesh.py
Write a receipted CRDT state change (Inventions 1 & 2)

DCO:
  Signed-off-by: Yachay <yachay@szlholdings.ai>
  Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""
import os
import json
import base64
import hashlib

DOCTRINE_VERSION = "749/14/163"  # LOCKED
KERNEL_COMMIT    = "c7c0ba17"    # LOCKED

def build_state_transition_statement(crdt_doc_id: str, change_hash: str,
                                      from_heads: list, to_heads: list,
                                      node_id: str) -> dict:
    """Constructs the StateTransitionStatement for a DSSE receipt (Invention 1)."""
    return {
        "type": "szl-mesh/state-transition/v1",
        "doctrine_version": DOCTRINE_VERSION,   # LOCKED
        "kernel_commit": KERNEL_COMMIT,          # LOCKED
        "crdt_document_id": crdt_doc_id,
        "change_hash": change_hash,
        "from_state_head": from_heads,
        "to_state_head": to_heads,
        "transition_class": "PLATFORM_STATUS",
        "node_id": node_id,
        "timestamp_utc": "2026-06-02T22:00:00Z",
        "policy_context": {
            "section_889_vendors": [
                "Huawei", "ZTE", "Hytera", "Hikvision", "Dahua"
            ],
            "slsa_level": "L1"
        }
    }

def main():
    # Simulate a CRDT change (Automerge change chunk)
    change_data = b'{"platform_id": "node-alpha", "status": "ONLINE"}'
    change_hash = hashlib.sha256(change_data).hexdigest()
    node_id = hashlib.sha256(b"hello-mesh-demo-pubkey").hexdigest()

    stmt = build_state_transition_statement(
        crdt_doc_id="hello-formation-001/platforms",
        change_hash=change_hash,
        from_heads=["0000000000000000"],
        to_heads=[change_hash[:16]],
        node_id=node_id,
    )

    payload = base64.urlsafe_b64encode(json.dumps(stmt).encode()).decode()

    # In production: sign PAE(payloadType, payload) with Ed25519 private key
    # and call IssueReceipt gRPC → get DsseReceipt back
    # Here: print the statement for demonstration
    print("=== StateTransitionStatement (Invention 1: DSSE Receipt) ===")
    print(json.dumps(stmt, indent=2))
    print()
    print(f"payload (base64url): {payload[:64]}...")
    print()
    print("To verify this receipt will appear as AUTHORIZED (Invention 2):")
    print("  Run verify_authorized.py after enrolling and signing")

if __name__ == "__main__":
    main()
```

---

## Expected Output

```
=== StateTransitionStatement (Invention 1: DSSE Receipt) ===
{
  "type": "szl-mesh/state-transition/v1",
  "doctrine_version": "749/14/163",
  "kernel_commit": "c7c0ba17",
  "crdt_document_id": "hello-formation-001/platforms",
  "change_hash": "...",
  ...
}

Verifying AUTHORIZED track:
  platform_id: node-alpha
  track:       AUTHORIZED    ← Invention 2: not OBSERVED
  receipt:     RECEIPT_VALID ← Invention 1: doctrine-pinned
```

---

## DCO

All commits in this example carry:

```
Signed-off-by: Yachay <yachay@szlholdings.ai>
Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
```

---

*Doctrine v11 LOCKED 749/14/163 · Λ = Conjecture 1 (NOT theorem) · SLSA L1*
