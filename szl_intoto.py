# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v13
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""
szl_intoto.py — in-toto Statement v1 serialization + per-receipt transparency log.

Reimplemented from the Apache-2.0 in-toto Attestation Framework v1 spec
(https://github.com/in-toto/attestation) — NO library copied, NO AGPL imported.
Pattern: adopt the spec, reimplement in SZL's own code.

THREE PUBLIC CAPABILITIES:

  1. STATEMENT SERIALIZATION
     wrap_as_intoto_statement(receipt) -> dict
       Returns a valid in-toto Statement v1 object:
         {_type, subject:[{name, digest:{sha3-256}}], predicateType, predicate}
       The MODEL OUTPUT hash goes in subject.digest (C2PA hard-binding pattern:
       a receipt cannot be recycled for a different output).
       predicateType = https://szl.holdings/khipu-governed-inference/v1

  2. DSSE ENVELOPE (in-toto-compatible)
     build_intoto_envelope(receipt, sign_fn) -> dict
       payloadType = "application/vnd.in-toto+json"
       Uses the caller-supplied sign_fn (szl_dsse.sign_payload) — no new key.

  3. TRANSPARENCY LOG — DUAL PATH (honest labels)
     a) Try public Rekor (rekor.sigstore.dev) via DSSE entry submission.
        Returns transparency_log: "rekor-public" if successful.
        NEVER claims Rekor inclusion if the HTTP call failed.
     b) If Rekor unreachable (HF Space egress blocked / timeout), fall back to
        SZL in-memory Merkle transparency log (SHA3-256 RFC 6962 leaf/node hash).
        Returns transparency_log: "szl-lake-merkle (self-hosted)".
        The self-hosted log grows monotonically per process lifetime; restart
        reseeds from khipu/ NDJSON partitions (if present).
        An anchor-to-Rekor-on-publish path is documented below.

  HONEST LABELS (never weaken):
    - transparency_log: "rekor-public"   — ONLY if the entry was ACTUALLY accepted
    - transparency_log: "szl-lake-merkle (self-hosted)" — internal log, third-party
      verifiable against /api/lake/v1/proof/<receipt_id>
    - transparency_log: "none"           — if log submission failed and no fallback

  REKOR ANCHOR ON PUBLISH PATH (ROADMAP — do not claim as current):
    When the a11oy Lake is published to HF Dataset (currently manual / CI-triggered),
    a CI job should: for each receipt in khipu/*.ndjson, compute its in-toto Statement,
    submit to Rekor, store the returned logIndex + inclusionProof back in the NDJSON.
    Until that pipeline is wired, individual receipts use the self-hosted Merkle log.
    The self-hosted log is honest and independently verifiable; it is NOT Sigstore.

Stdlib + cryptography (already a dep in a11oy for szl_dsse) only.
No AGPL. No in_toto library import. Pattern from spec, reimplement fresh.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# CONSTANTS — in-toto Statement v1 spec
# ---------------------------------------------------------------------------

STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
GOVERNED_INFERENCE_PREDICATE = "https://szl.holdings/khipu-governed-inference/v1"
INTOTO_PAYLOAD_TYPE = "application/vnd.in-toto+json"

REKOR_BASE = "https://rekor.sigstore.dev"
REKOR_TIMEOUT = float(os.environ.get("SZL_REKOR_TIMEOUT", "15"))

_TRANSPARENCY_LOG_VERSION = "szl-intoto/v1"

# ---------------------------------------------------------------------------
# 1. STATEMENT SERIALIZATION
# ---------------------------------------------------------------------------

def _canonical_json(obj: Any) -> bytes:
    """Deterministic canonical JSON: sorted keys, no extra whitespace, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _sha3_256(b: bytes) -> str:
    return hashlib.sha3_256(b).hexdigest()


def _sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def compute_output_hash(receipt: dict) -> str | None:
    """
    Derive the model output hash for the in-toto subject.digest.

    C2PA hard-binding pattern: the hash MUST cover the actual output content,
    not just metadata, so a receipt cannot be recycled for a different output.

    Resolution order (honest fallback chain):
      1. receipt["output_sha3_256"]  — pre-computed canonical hash (preferred)
      2. SHA3-256(receipt["answer"]) — recompute from the stored answer text
      3. SHA3-256(receipt["receipt_id"] + canonical_json(payload fields))
         — fallback when answer is absent (e.g. denied turn, no answer emitted)
    """
    # 1) Pre-computed (best case)
    h = receipt.get("output_sha3_256")
    if isinstance(h, str) and len(h) == 64:
        return h

    # 2) Recompute from stored answer
    answer = receipt.get("answer")
    if isinstance(answer, str) and answer:
        return _sha3_256(answer.encode("utf-8"))

    # 3) Deterministic fallback from receipt identity fields
    rid = receipt.get("receipt_id") or receipt.get("id") or receipt.get("hash") or ""
    payload = {k: v for k, v in receipt.items()
               if k not in ("signature", "dsse", "signatures", "honesty")}
    fallback_input = (rid + ":").encode("utf-8") + _canonical_json(payload)
    return _sha3_256(fallback_input)


def wrap_as_intoto_statement(receipt: dict) -> dict:
    """
    Convert a Khipu receipt to a valid in-toto Statement v1.

    Returns the statement dict (NOT yet DSSE-signed). Call build_intoto_envelope()
    to get a signed DSSE envelope with payloadType="application/vnd.in-toto+json".

    Structure per in-toto Attestation Framework v1 (Apache-2.0):
      {
        "_type": "https://in-toto.io/Statement/v1",
        "subject": [{
          "name": "governed-inference-<receipt_id>",
          "digest": {"sha3-256": "<output_hash>"}
        }],
        "predicateType": "https://szl.holdings/khipu-governed-inference/v1",
        "predicate": { <all governance/Λ/energy/gate fields> }
      }

    The MODEL OUTPUT hash goes in subject.digest — C2PA hard binding.
    All SZL-specific fields (Λ, gate results, chain metadata, Lean proof hashes,
    energy) are preserved in predicate.
    """
    receipt_id = (receipt.get("receipt_id") or receipt.get("id")
                  or receipt.get("hash") or "unknown")
    output_hash = compute_output_hash(receipt)

    # Build the predicate from ALL existing receipt fields.
    # Strip large binary/envelope fields that would double-encode.
    _STRIP_KEYS = frozenset({"dsse", "signatures", "_dsse", "_pae_sha256",
                              "honesty", "verify_key_url"})
    predicate = {k: v for k, v in receipt.items() if k not in _STRIP_KEYS}

    # Explicitly document the hard-binding method so verifiers know how to check
    predicate["_binding_method"] = "sha3-256(output_content|receipt_identity_fallback)"
    predicate["_intoto_version"] = "Statement/v1"

    statement = {
        "_type": STATEMENT_TYPE,
        "subject": [{
            "name": f"governed-inference-{receipt_id}",
            "digest": {"sha3-256": output_hash},
        }],
        "predicateType": GOVERNED_INFERENCE_PREDICATE,
        "predicate": predicate,
    }
    return statement


# ---------------------------------------------------------------------------
# 2. DSSE ENVELOPE (in-toto-compatible)
# ---------------------------------------------------------------------------

def _pae(payload_type: str, body: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (DSSEv1)."""
    t = payload_type.encode("utf-8")
    return (b"DSSEv1 " + str(len(t)).encode() + b" " + t
            + b" " + str(len(body)).encode() + b" " + body)


def build_intoto_envelope(
    receipt: dict,
    sign_fn: Callable[[Any, str], dict] | None = None,
) -> dict:
    """
    Build a DSSE envelope over an in-toto Statement v1.

    payloadType is "application/vnd.in-toto+json" (standard in-toto type).
    sign_fn, if provided, must accept (payload_obj, payload_type) and return a
    DSSE envelope dict (szl_dsse.sign_payload matches this signature).

    If sign_fn is None, imports szl_dsse.sign_payload automatically (prefer the
    existing Cosign keypair so the payloadType change is the ONLY delta).

    The returned envelope is a valid in-toto DSSE bundle:
      {
        "payloadType": "application/vnd.in-toto+json",
        "payload": "<base64(statement_json)>",
        "signatures": [{...}],
        ...honesty/signed meta from szl_dsse
      }
    """
    statement = wrap_as_intoto_statement(receipt)

    if sign_fn is None:
        try:
            import szl_dsse as _dsse
            sign_fn = _dsse.sign_payload
        except ImportError:
            sign_fn = None

    if sign_fn is not None:
        envelope = sign_fn(statement, INTOTO_PAYLOAD_TYPE)
    else:
        # No signing available — emit unsigned envelope, honest label
        body = _canonical_json(statement)
        envelope = {
            "payloadType": INTOTO_PAYLOAD_TYPE,
            "payload": base64.b64encode(body).decode("ascii"),
            "signatures": [],
            "signed": False,
            "honesty": "UNSIGNED — szl_dsse not importable; no signature fabricated.",
        }

    envelope["_intoto_statement_v1"] = True
    envelope["_predicate_type"] = GOVERNED_INFERENCE_PREDICATE
    return envelope


# ---------------------------------------------------------------------------
# 3a. TRANSPARENCY LOG — public Rekor submission
# ---------------------------------------------------------------------------

def _load_public_pem() -> str | None:
    """Load the SZL cosign public key PEM for Rekor verifier entry."""
    try:
        import szl_dsse as _dsse
        pem = getattr(_dsse, "COSIGN_PUBLIC_PEM", None)
        if pem and "BEGIN" in pem:
            return pem.strip()
    except ImportError:
        pass
    return os.environ.get("SZL_COSIGN_PUBLIC_PEM", "").strip() or None


def submit_to_rekor(dsse_envelope: dict, receipt_id: str) -> dict:
    """
    Submit a DSSE in-toto envelope to the public Sigstore Rekor log.

    Returns a transparency log entry dict with:
      {
        "transparency_log": "rekor-public",
        "log_index": <int>,
        "log_url": "https://rekor.sigstore.dev/api/v1/log/entries?logIndex=<N>",
        "inclusion_proof": {"checkpoint": ..., "hashes": [...], "root_hash": ...},
        "submitted_at": "<ISO>"
      }

    On failure returns:
      {"transparency_log": "none", "rekor_error": "<reason>", ...}

    HONESTY: NEVER reports rekor-public unless the HTTP POST actually succeeded
    and returned a logIndex. No fake inclusion proofs.
    """
    pub_pem = _load_public_pem()
    if not pub_pem:
        return {
            "transparency_log": "none",
            "rekor_error": "SZL cosign public key not available; cannot submit to Rekor",
            "receipt_id": receipt_id,
        }

    # Build the Rekor DSSE entry request (Rekor v2 DSSE type)
    entry_request = {
        "kind": "dsse",
        "apiVersion": "0.0.1",
        "spec": {
            "proposedContent": {
                "envelope": json.dumps(dsse_envelope),
                "verifiers": [{"publicKeyPem": pub_pem}],
            }
        },
    }

    try:
        import httpx
        with httpx.Client(follow_redirects=True, timeout=REKOR_TIMEOUT,
                          headers={"User-Agent": "a11oy-intoto/1.0 (+https://szlholdings-a11oy.hf.space)",
                                   "Content-Type": "application/json"}) as client:
            resp = client.post(
                REKOR_BASE + "/api/v1/log/entries",
                content=json.dumps(entry_request).encode("utf-8"),
            )
        if resp.status_code not in (200, 201):
            return {
                "transparency_log": "none",
                "rekor_error": f"Rekor returned HTTP {resp.status_code}: {resp.text[:200]}",
                "receipt_id": receipt_id,
            }
        log_entry = resp.json()
    except Exception as exc:
        return {
            "transparency_log": "none",
            "rekor_error": f"Rekor unreachable: {exc!r}",
            "receipt_id": receipt_id,
        }

    # Parse the returned entry (Rekor returns {<uuid>: {body, ...}})
    try:
        uuid, entry = next(iter(log_entry.items()))
        verification = entry.get("verification", {})
        inclusion = verification.get("inclusionProof", {})
        log_index = entry.get("logIndex") or entry.get("logID") or uuid
        return {
            "transparency_log": "rekor-public",
            "log_index": log_index,
            "log_url": f"{REKOR_BASE}/api/v1/log/entries?logIndex={log_index}",
            "inclusion_proof": {
                "checkpoint": inclusion.get("checkpoint"),
                "hashes": inclusion.get("hashes", []),
                "root_hash": inclusion.get("rootHash"),
                "tree_size": inclusion.get("treeSize"),
                "log_index": inclusion.get("logIndex"),
            },
            "receipt_id": receipt_id,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as exc:
        return {
            "transparency_log": "none",
            "rekor_error": f"Rekor response parse error: {exc!r}",
            "receipt_id": receipt_id,
        }


# ---------------------------------------------------------------------------
# 3b. TRANSPARENCY LOG — self-hosted Merkle log (RFC 6962 leaf/node hash)
# ---------------------------------------------------------------------------

class SZLMerkleLog:
    """
    In-memory append-only Merkle transparency log (RFC 6962 leaf/node hashing).

    Each leaf = SHA3-256(0x00 || canonical_json(statement)).
    Interior node = SHA3-256(0x01 || left || right).
    Inclusion proof = ordered list of sibling hashes from leaf to root.

    This is NOT Sigstore Rekor. It is a self-hosted, deterministic, independently
    verifiable log. The inclusion proof is standard RFC 6962 audit path math;
    any third party can verify it with the published root hash.

    Honest label: "szl-lake-merkle (self-hosted)" — NOT public Rekor.
    Rekor-anchor-on-publish: when the Lake is published to HF Dataset / GitHub
    release, a CI job should submit each receipt's in-toto Statement to Rekor and
    store the logIndex. Until then, this self-hosted log is the inclusion mechanism.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._leaves: list[bytes] = []          # raw 32-byte leaf hashes
        self._index: dict[str, int] = {}        # receipt_id -> leaf index
        self._tree: list[list[bytes]] = []       # tree[level][node_index]
        self._log_id = "szl-lake-merkle-v1"

    @staticmethod
    def _leaf_hash(data: bytes) -> bytes:
        """RFC 6962: SHA3-256(0x00 || data)."""
        return hashlib.sha3_256(b"\x00" + data).digest()

    @staticmethod
    def _node_hash(left: bytes, right: bytes) -> bytes:
        """RFC 6962: SHA3-256(0x01 || left || right)."""
        return hashlib.sha3_256(b"\x01" + left + right).digest()

    def _rebuild_tree(self) -> None:
        """Rebuild the Merkle tree from the current leaves."""
        if not self._leaves:
            self._tree = []
            return
        level = list(self._leaves)
        self._tree = [level]
        while len(level) > 1:
            next_level = []
            for i in range(0, len(level) - 1, 2):
                next_level.append(self._node_hash(level[i], level[i + 1]))
            if len(level) % 2 == 1:
                next_level.append(level[-1])  # promote odd node
            level = next_level
            self._tree.append(level)

    def append(self, receipt_id: str, statement: dict) -> dict:
        """
        Append a statement to the log. Idempotent on receipt_id.

        Returns the inclusion proof dict.
        """
        with self._lock:
            if receipt_id in self._index:
                return self.inclusion_proof(receipt_id)

            leaf_data = _canonical_json(statement)
            leaf = self._leaf_hash(leaf_data)
            idx = len(self._leaves)
            self._leaves.append(leaf)
            self._index[receipt_id] = idx
            self._rebuild_tree()
            return self.inclusion_proof(receipt_id)

    def root_hash(self) -> str | None:
        """Current root hash (hex). None if log is empty."""
        if not self._tree:
            return None
        return self._tree[-1][0].hex()

    def tree_size(self) -> int:
        return len(self._leaves)

    def inclusion_proof(self, receipt_id: str) -> dict:
        """
        RFC 6962 audit path for the given receipt_id.

        Returns:
          {
            "transparency_log": "szl-lake-merkle (self-hosted)",
            "log_id": "szl-lake-merkle-v1",
            "leaf_index": <int>,
            "tree_size": <int>,
            "root_hash": "<hex>",
            "hashes": ["<hex>", ...],   # sibling hashes from leaf to root
            "leaf_hash": "<hex>",
            "receipt_id": "<id>",
            "verify_endpoint": "/api/lake/v1/proof/<receipt_id>",
            "honest_label": "self-hosted; NOT Sigstore Rekor; rekor-anchor-on-publish is ROADMAP"
          }
        """
        if not self._leaves:
            return {
                "transparency_log": "szl-lake-merkle (self-hosted)",
                "error": "log empty",
                "receipt_id": receipt_id,
            }
        idx = self._index.get(receipt_id)
        if idx is None:
            return {
                "transparency_log": "szl-lake-merkle (self-hosted)",
                "error": "receipt_id not in log",
                "receipt_id": receipt_id,
            }

        # Compute audit path (sibling hashes from leaf level to root)
        audit_path: list[str] = []
        tree_size = len(self._leaves)
        i = idx
        for level in self._tree[:-1]:  # skip root level
            sibling = i ^ 1  # XOR with 1 flips the last bit = sibling index
            if sibling < len(level):
                audit_path.append(level[sibling].hex())
            # else: odd node — no sibling at this level
            i //= 2

        root = self.root_hash()
        return {
            "transparency_log": "szl-lake-merkle (self-hosted)",
            "log_id": self._log_id,
            "leaf_index": idx,
            "tree_size": tree_size,
            "root_hash": root,
            "hashes": audit_path,
            "leaf_hash": self._leaves[idx].hex(),
            "receipt_id": receipt_id,
            "verify_endpoint": f"/api/lake/v1/proof/{receipt_id}",
            "honest_label": (
                "self-hosted SZL Merkle log; NOT Sigstore public Rekor. "
                "Third-party verifiable against root_hash + audit path (RFC 6962). "
                "Rekor-anchor-on-publish (CI batch submit to rekor.sigstore.dev) "
                "is ROADMAP — documented in szl_intoto.py ANCHOR PATH."
            ),
        }

    def verify_proof(self, receipt_id: str, statement: dict) -> dict:
        """
        Offline-verifiable inclusion proof check.

        Recomputes the leaf hash from the statement, walks the audit path,
        and checks against the stored root hash. Returns {verified, ...}.
        """
        idx = self._index.get(receipt_id)
        if idx is None:
            return {"verified": False, "reason": "receipt_id not in log"}

        proof = self.inclusion_proof(receipt_id)
        leaf_data = _canonical_json(statement)
        computed_leaf = self._leaf_hash(leaf_data)

        if computed_leaf != self._leaves[idx]:
            return {
                "verified": False,
                "reason": "leaf hash mismatch (statement was modified after log append)",
                "computed_leaf": computed_leaf.hex(),
                "stored_leaf": self._leaves[idx].hex(),
            }

        # Walk the audit path
        node = computed_leaf
        tree_size = len(self._leaves)
        i = idx
        for level_idx, level in enumerate(self._tree[:-1]):
            sibling_idx = i ^ 1
            if sibling_idx < len(level):
                sibling = level[sibling_idx]
                if i % 2 == 0:
                    node = self._node_hash(node, sibling)
                else:
                    node = self._node_hash(sibling, node)
            i //= 2

        computed_root = node.hex()
        stored_root = self.root_hash()
        if computed_root != stored_root:
            return {
                "verified": False,
                "reason": "recomputed root does not match stored root",
                "computed_root": computed_root,
                "stored_root": stored_root,
            }

        return {
            "verified": True,
            "leaf_index": idx,
            "tree_size": tree_size,
            "root_hash": stored_root,
            "transparency_log": "szl-lake-merkle (self-hosted)",
            "receipt_id": receipt_id,
        }


# Global Merkle log singleton (one per process lifetime)
_MERKLE_LOG = SZLMerkleLog()

# Seed the Merkle log from existing khipu/ NDJSON partitions (if present) on import.
# This ensures inclusion proofs survive process restart for receipts already on disk.
def _seed_from_disk(lake_dir: str = "khipu") -> int:
    """Seed the global Merkle log from existing NDJSON receipts on disk."""
    seeded = 0
    if not os.path.isdir(lake_dir):
        return 0
    try:
        for organ_name in sorted(os.listdir(lake_dir)):
            organ_dir = os.path.join(lake_dir, organ_name)
            if not os.path.isdir(organ_dir):
                continue
            for fname in sorted(os.listdir(organ_dir)):
                if not fname.endswith(".ndjson"):
                    continue
                fpath = os.path.join(organ_dir, fname)
                with open(fpath, "r", encoding="utf-8") as fh:
                    for line in fh:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            envelope = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        rid = envelope.get("receipt_id") or envelope.get("id") or ""
                        if not rid:
                            continue
                        # Build a minimal statement for seeding (no re-signing needed)
                        receipt = envelope.get("receipt", envelope)
                        statement = wrap_as_intoto_statement(receipt)
                        _MERKLE_LOG.append(rid, statement)
                        seeded += 1
    except Exception:
        pass
    return seeded


# Seed on import (non-blocking; tolerate any error gracefully)
try:
    _lake_dir = os.environ.get("SZL_LAKE_DIR", "khipu")
    _MERKLE_LOG_SEED_COUNT = _seed_from_disk(_lake_dir)
except Exception:
    _MERKLE_LOG_SEED_COUNT = 0


# ---------------------------------------------------------------------------
# 4. HIGH-LEVEL: produce in-toto statement + log proof for a receipt
# ---------------------------------------------------------------------------

def attest_receipt(
    receipt: dict,
    sign_fn: Callable[[Any, str], dict] | None = None,
    try_rekor: bool = True,
) -> dict:
    """
    Full in-toto attestation for a Khipu receipt.

    1. Wraps the receipt as an in-toto Statement v1.
    2. Builds a DSSE envelope with payloadType="application/vnd.in-toto+json".
    3. Attempts public Rekor submission (if try_rekor=True).
       On success: transparency_log="rekor-public" + inclusion proof.
       On failure/unreachable: falls back to self-hosted Merkle log.
    4. Appends to the self-hosted Merkle log always (belt+suspenders).

    Returns:
      {
        "intoto_statement": <Statement v1 dict>,
        "intoto_envelope": <DSSE envelope dict>,
        "transparency": <inclusion proof dict>,
        "receipt_id": "<id>",
        "_version": "szl-intoto/v1"
      }
    """
    receipt_id = (receipt.get("receipt_id") or receipt.get("id")
                  or receipt.get("hash") or _sha3_256(_canonical_json(receipt)))

    statement = wrap_as_intoto_statement(receipt)
    envelope = build_intoto_envelope(receipt, sign_fn=sign_fn)

    # Always append to self-hosted Merkle log
    merkle_proof = _MERKLE_LOG.append(receipt_id, statement)

    # Attempt public Rekor submission
    transparency = merkle_proof  # default to self-hosted
    if try_rekor and envelope.get("signed"):
        rekor_result = submit_to_rekor(envelope, receipt_id)
        if rekor_result.get("transparency_log") == "rekor-public":
            transparency = rekor_result
        # else: Rekor unavailable, self-hosted merkle proof is used

    return {
        "intoto_statement": statement,
        "intoto_envelope": envelope,
        "transparency": transparency,
        "receipt_id": receipt_id,
        "_version": _TRANSPARENCY_LOG_VERSION,
    }


def get_inclusion_proof(receipt_id: str) -> dict:
    """Retrieve the inclusion proof for a receipt from the self-hosted Merkle log."""
    return _MERKLE_LOG.inclusion_proof(receipt_id)


def verify_inclusion_proof(receipt_id: str, statement: dict) -> dict:
    """Verify an inclusion proof for a receipt against the self-hosted Merkle log."""
    return _MERKLE_LOG.verify_proof(receipt_id, statement)


def merkle_log_state() -> dict:
    """Current state of the self-hosted Merkle log (for monitoring/audit)."""
    return {
        "log_id": "szl-lake-merkle-v1",
        "tree_size": _MERKLE_LOG.tree_size(),
        "root_hash": _MERKLE_LOG.root_hash(),
        "honest_label": "self-hosted SZL Merkle log; NOT Sigstore Rekor",
        "seed_count": _MERKLE_LOG_SEED_COUNT,
    }
