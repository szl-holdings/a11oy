# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED — 749 declarations / 14 unique axioms / 163 sorries.
# Authored by Yachay (CTO) — Sentra Rekor: REAL log fetch + Merkle proof verify.
"""
sentra.rekor — fetch a real Sigstore Rekor transparency-log entry by index and
verify its Merkle inclusion proof by RECOMPUTING the root from the leaf + audit
path (RFC 6962 §2.1.1), not by trusting the server.

Endpoint:  https://rekor.sigstore.dev/api/v1/log/entries?logIndex=<n>

The leaf hash is computed per RFC 6962 as SHA-256 of (0x00 || entry_body_bytes),
where entry_body_bytes is the base64-decoded `body` of the log entry. We then
walk the `inclusionProof.hashes` audit path using the entry's `logIndex within
the tree` (proof.logIndex) and `treeSize` to reproduce the root hash and compare
it against `inclusionProof.rootHash`.

HONESTY: real network fetch (httpx), real SHA-256 Merkle math. If egress is
blocked the verifier reports `verified=None` with the honest error — never a
fake `verified=True`.
"""
from __future__ import annotations

import base64
import hashlib
from typing import Any

REKOR_BASE = "https://rekor.sigstore.dev"


def _sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()


def leaf_hash(entry_body_b64: str) -> bytes:
    """RFC 6962 leaf hash: SHA-256(0x00 || body)."""
    body = base64.b64decode(entry_body_b64)
    return _sha256(b"\x00" + body)


def _node_hash(left: bytes, right: bytes) -> bytes:
    """RFC 6962 interior node: SHA-256(0x01 || left || right)."""
    return _sha256(b"\x01" + left + right)


def verify_inclusion(leaf: bytes, index: int, tree_size: int, proof_hashes: list[bytes]) -> bytes:
    """Recompute the Merkle root from a leaf + audit path (RFC 6962 §2.1.1).

    Returns the computed root hash bytes. Raises ValueError on malformed input.
    """
    if index >= tree_size or index < 0:
        raise ValueError(f"index {index} out of range for tree_size {tree_size}")
    node = leaf
    last_node = tree_size - 1
    i = index
    proof = list(proof_hashes)
    while last_node > 0:
        if not proof:
            raise ValueError("audit path exhausted before reaching root")
        if i % 2 == 1:  # right child
            node = _node_hash(proof.pop(0), node)
        elif i < last_node:  # left child with a right sibling
            node = _node_hash(node, proof.pop(0))
        else:
            # left child, no sibling at this level — promote up
            pass
        i //= 2
        last_node //= 2
    if proof:
        raise ValueError("audit path has leftover hashes")
    return node


def fetch_entry(log_index: int, timeout: float = 20.0) -> dict[str, Any]:
    """Fetch a Rekor log entry by global logIndex. Real network call."""
    import httpx
    url = f"{REKOR_BASE}/api/v1/log/entries?logIndex={int(log_index)}"
    with httpx.Client(follow_redirects=True, timeout=timeout) as client:
        r = client.get(url, headers={"Accept": "application/json"})
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, dict) or not data:
        raise ValueError("empty Rekor response")
    # response is {uuid: {body, logIndex, verification:{inclusionProof:{...}}, ...}}
    uuid, entry = next(iter(data.items()))
    return {"uuid": uuid, "entry": entry, "url": url}


def verify_log_index(log_index: int, timeout: float = 20.0) -> dict[str, Any]:
    """Fetch entry `log_index` and verify its inclusion proof by recomputing the
    Merkle root. Returns a structured verdict (never raises into caller)."""
    out: dict[str, Any] = {"log_index": log_index, "rekor": REKOR_BASE}
    try:
        fetched = fetch_entry(log_index, timeout=timeout)
    except Exception as e:
        return {**out, "verified": None, "reason": f"fetch failed ({type(e).__name__}: {e})"}
    entry = fetched["entry"]
    out["uuid"] = fetched["uuid"]
    out["fetch_url"] = fetched["url"]
    try:
        body_b64 = entry["body"]
        ip = entry["verification"]["inclusionProof"]
        tree_size = int(ip["treeSize"])
        proof_index = int(ip["logIndex"])  # index within the tree for the proof
        root_hex = ip["rootHash"]
        hashes_hex = ip["hashes"]
        checkpoint = ip.get("checkpoint")
    except Exception as e:
        return {**out, "verified": False, "reason": f"malformed inclusion proof: {e}"}

    try:
        leaf = leaf_hash(body_b64)
        proof = [bytes.fromhex(h) for h in hashes_hex]
        computed = verify_inclusion(leaf, proof_index, tree_size, proof)
        computed_hex = computed.hex()
        verified = (computed_hex == root_hex)
        return {
            **out,
            "verified": verified,
            "tree_size": tree_size,
            "proof_index": proof_index,
            "audit_path_len": len(hashes_hex),
            "leaf_hash_sha256": leaf.hex(),
            "computed_root": computed_hex,
            "server_root": root_hex,
            "checkpoint_present": bool(checkpoint),
            "method": "RFC 6962 inclusion proof — root recomputed from leaf+path",
            "doctrine": "v11",
        }
    except Exception as e:
        return {**out, "verified": False, "reason": f"merkle verification error: {type(e).__name__}: {e}"}


__all__ = [
    "REKOR_BASE",
    "leaf_hash",
    "verify_inclusion",
    "fetch_entry",
    "verify_log_index",
]


# ─────────────────────────────────────────────────────────────────────────────
# Doctrine v11 LOCKED — 749 declarations / 14 unique axioms (15 raw, 1 dup) /
# 163 sorries (112 baseline + 51 Putnam). Kernel commit c7c0ba17.
# Λ = Conjecture 1 (NOT a theorem). SLSA L1 (honest). Real in-toto SLSA
# Provenance v1 attestation is emitted as a signed provenance artifact; this is
# NOT a claim of any graded build level beyond L1.
# HONESTY OVER CHECKLIST — no mocks; real Ed25519, real DSSE PAE bytes, real
# Rekor Merkle inclusion proofs. Signed-off per DCO in the commit trailer.
# ─────────────────────────────────────────────────────────────────────────────
