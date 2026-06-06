#!/usr/bin/env python3
"""
hello-mesh/enroll.py
Doctrine-gated enrollment (Invention 5: Doctrine-Gated Certificate Enrollment).

Enrolls this node in the formation.  The formation key proof HMAC binds
doctrine_version and kernel_commit — a node cannot claim doctrine 749/14/163
without it being cryptographically verifiable.

Doctrine: v11 LOCKED 749/14/163 · Kernel commit c7c0ba17 · SLSA L1

DCO:
  Signed-off-by: Yachay <yachay@szlholdings.ai>
  Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
"""

import os
import sys
import hmac
import hashlib
from datetime import datetime, timezone

# ── Locked constants — NEVER MODIFY without new doctrine release ──
DOCTRINE_VERSION = "749/14/163"
KERNEL_COMMIT    = "c7c0ba17"
SLSA_LEVEL       = "L1"
SECTION_889_VENDORS = ["Huawei", "ZTE", "Hytera", "Hikvision", "Dahua"]


def compute_node_id(pubkey_bytes: bytes) -> str:
    """NodeID = SHA-256(raw Ed25519 public key bytes), hex-encoded."""
    return hashlib.sha256(pubkey_bytes).hexdigest()


def compute_formation_key_proof(
    formation_key: bytes,
    node_id: str,
    timestamp_utc: str,
    doctrine_version: str,
    kernel_commit: str,
) -> str:
    """
    HMAC-SHA256(formation_key, node_id || timestamp_utc || doctrine_version || kernel_commit)

    Doctrine_version and kernel_commit are inside the HMAC message.
    A node cannot alter its doctrine claim after computing this proof
    without invalidating the HMAC — requires knowledge of formation_key.

    See spec/05-doctrine-gated-enrollment.md §2.
    """
    message = (node_id + timestamp_utc + doctrine_version + kernel_commit).encode()
    return hmac.new(formation_key, message, hashlib.sha256).hexdigest()


def main() -> int:
    mesh_addr      = os.environ.get("SZL_MESH_ADDR", "localhost:50052")
    formation_id   = os.environ.get("SZL_FORMATION_ID", "hello-formation-001")
    formation_key  = os.environ.get("SZL_FORMATION_KEY", "").encode()

    if not formation_key:
        print("ERROR: SZL_FORMATION_KEY environment variable not set.")
        print("       Set it to the pre-deployed formation key for this mission.")
        return 1

    # Load Ed25519 public key
    pubkey_path = os.path.join(os.path.dirname(__file__), "node_pub.pem")
    if not os.path.exists(pubkey_path):
        print(f"ERROR: {pubkey_path} not found.")
        print("       Generate with: openssl genpkey -algorithm Ed25519 -out node_key.pem")
        print("                      openssl pkey -in node_key.pem -pubout -out node_pub.pem")
        return 1

    with open(pubkey_path, "rb") as f:
        pubkey_pem = f.read()

    node_id = compute_node_id(pubkey_pem)
    timestamp_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Compute doctrine-bound formation key proof (Invention 5)
    proof = compute_formation_key_proof(
        formation_key,
        node_id,
        timestamp_utc,
        DOCTRINE_VERSION,  # LOCKED
        KERNEL_COMMIT,     # LOCKED
    )

    print("=" * 60)
    print("SZL-MESH Doctrine-Gated Enrollment (Invention 5)")
    print("=" * 60)
    print(f"  formation_id:     {formation_id}")
    print(f"  node_id:          {node_id}")
    print(f"  doctrine_version: {DOCTRINE_VERSION}  (LOCKED)")
    print(f"  kernel_commit:    {KERNEL_COMMIT}  (LOCKED)")
    print(f"  slsa_level:       {SLSA_LEVEL}")
    print(f"  formation_proof:  {proof}")
    print(f"  timestamp_utc:    {timestamp_utc}")
    print()
    print("Section 889 self-attestation:")
    for v in SECTION_889_VENDORS:
        print(f"  ✗  {v}  — excluded from formation")
    print()

    # In production: call EnrollNode gRPC
    # channel = grpc.insecure_channel(mesh_addr)
    # stub = SzlMeshNodeStub(channel)
    # response = stub.EnrollNode(EnrollNodeRequest(
    #     node_id=node_id,
    #     ed25519_public_key=pubkey_raw_bytes,
    #     formation_key_proof=proof,
    #     timestamp_utc=timestamp_utc,
    #     doctrine_claim=DoctrineClaimProof(
    #         doctrine_version=DOCTRINE_VERSION,
    #         kernel_commit=KERNEL_COMMIT,
    #         slsa_level=SLSA_LEVEL,
    #     ),
    #     section_889=Section889Attestation(
    #         vendor_exclusion_confirmed=True,
    #         hardware_vendor="",
    #         attestation_method="self_report",
    #     ),
    # ))
    # if response.success:
    #     with open("node_cert.der", "wb") as f:
    #         f.write(response.node_certificate)
    #     print(f"Enrolled successfully. Certificate: node_cert.der")
    # else:
    #     print(f"Enrollment failed: {response.failure_reason}")
    #     return 1

    print("[STUB] EnrollNode gRPC call — proto stubs not yet generated.")
    print("       In production, this call goes to szl-mesh-node on", mesh_addr)
    print("       peat-gateway validates the doctrine proof and issues a")
    print("       Formation CA-signed Node Certificate (90-day TTL).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
