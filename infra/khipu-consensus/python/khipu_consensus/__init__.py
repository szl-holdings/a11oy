# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
khipu-consensus — Byzantine-fault-tolerant multi-party signed agreement.

The category: multi-party-witnessed AI. Each witness ("organ") signs an action
hash with its own ECDSA-P256 key. >= threshold valid `allow` signatures over the
same action hash ⇒ the action is CANONICAL (BFT n witnesses, f = n - threshold
tolerated faults; 3-of-4 tolerates 1). Every per-witness signature is
ECDSA-P256-SHA256 over the DSSE (Dead-Simple-Signing-Envelope) Pre-Authentication
Encoding, so it is verifiable by `cosign verify-blob --key <witness>.pub`.

Reference implementation. Mirrors typescript/ and go/ byte-for-byte on the same
deterministic test vectors (testdata/vectors.json).
"""
from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional

ORGAN_VERDICT_PAYLOAD_TYPE = "application/vnd.szl.khipu.organ-verdict+json"
__version__ = "0.1.0"


def canonical_json(obj) -> bytes:
    """Deterministic canonical JSON: sorted keys, compact separators, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def pae(payload_type: str, body: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (DSSEv1)."""
    t = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(t)).encode() + b" " + t + b" " + str(len(body)).encode() + b" " + body


@dataclass
class OrganVerdict:
    organ: str
    keyid: str
    payload_type: str
    payload_b64: str          # base64 of the canonical signed statement
    signature_b64: str        # base64 of the ECDSA-P256-SHA256 signature over PAE
    verdict: str = "allow"    # informational; the authoritative verdict is inside payload
    reason: str = ""

    @staticmethod
    def from_dict(d: dict) -> "OrganVerdict":
        return OrganVerdict(
            organ=d.get("organ", ""),
            keyid=d.get("keyid", ""),
            payload_type=d.get("payloadType", ORGAN_VERDICT_PAYLOAD_TYPE),
            payload_b64=d.get("payload", ""),
            signature_b64=d.get("signature", ""),
            verdict=d.get("verdict", "allow"),
            reason=d.get("reason", ""),
        )


@dataclass
class OrganCheck:
    organ: str
    keyid: str
    valid: bool
    verdict: Optional[str]
    action_hash_match: bool
    counts: bool
    reason: str = ""


@dataclass
class ConsensusResult:
    action_hash: str
    threshold: int
    n: int
    consensus_count: int
    decision: str
    checks: list = field(default_factory=list)

    @property
    def khipu_consensus(self) -> str:
        return f"{self.consensus_count}-of-{self.n}"


def sign_verdict(organ: str, action_hash: str, verdict: str, private_key_pem: str,
                 reason: str = "", lean_sha: str = "", ts: str = "") -> dict:
    """Produce a DSSE-signed organ verdict dict (the wire shape)."""
    from cryptography.hazmat.primitives.serialization import load_pem_private_key
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    from datetime import datetime, timezone

    keyid = f"{organ}-cosign"
    statement = {
        "schema": "szl.khipu.organ_verdict/v1", "organ": organ, "keyid": keyid,
        "action_hash": action_hash, "verdict": verdict, "reason": reason,
        "lean_sha": lean_sha, "ts": ts or datetime.now(timezone.utc).isoformat(),
    }
    body = canonical_json(statement)
    priv = load_pem_private_key(private_key_pem.encode(), password=None)
    sig = priv.sign(pae(ORGAN_VERDICT_PAYLOAD_TYPE, body), ec.ECDSA(hashes.SHA256()))
    return {
        "organ": organ, "keyid": keyid, "payloadType": ORGAN_VERDICT_PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode(), "signature": base64.b64encode(sig).decode(),
        "verdict": verdict, "reason": reason,
    }


def verify_verdict(v: OrganVerdict, public_key_pem: str, action_hash: str) -> OrganCheck:
    """Verify one organ's signature against its public key, and check that the
    signed action_hash and verdict are internally consistent."""
    from cryptography.hazmat.primitives.serialization import load_pem_public_key
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives import hashes
    from cryptography.exceptions import InvalidSignature

    if not v.payload_b64 or not v.signature_b64:
        return OrganCheck(v.organ, v.keyid, False, None, False, False, "missing payload/signature")
    try:
        body = base64.b64decode(v.payload_b64)
        to_verify = pae(v.payload_type, body)
        pub = load_pem_public_key(public_key_pem.encode())
        try:
            pub.verify(base64.b64decode(v.signature_b64), to_verify, ec.ECDSA(hashes.SHA256()))
        except InvalidSignature:
            return OrganCheck(v.organ, v.keyid, False, None, False, False, "signature mismatch")
        decoded = json.loads(body)
        ah_match = decoded.get("action_hash") == action_hash
        verdict = decoded.get("verdict")
        counts = ah_match and verdict == "allow"
        return OrganCheck(v.organ, v.keyid, True, verdict, ah_match, counts)
    except Exception as e:
        return OrganCheck(v.organ, v.keyid, False, None, False, False, f"{type(e).__name__}: {e}")


def tally(action_hash: str, verdicts: list, pubkeys: dict,
          threshold: int = 3, n: int = 4) -> ConsensusResult:
    """Count valid + allow signatures over `action_hash`; apply the BFT threshold.

    verdicts: list of dict|OrganVerdict|None (None = abstain/timeout).
    pubkeys : {organ: PEM}.
    """
    checks = []
    count = 0
    for item in verdicts:
        if item is None:
            checks.append(OrganCheck(None, None, False, None, False, False, "abstain/timeout"))
            continue
        v = item if isinstance(item, OrganVerdict) else OrganVerdict.from_dict(item)
        pem = pubkeys.get(v.organ, "")
        if not pem:
            checks.append(OrganCheck(v.organ, v.keyid, False, None, False, False, "no public key"))
            continue
        chk = verify_verdict(v, pem, action_hash)
        checks.append(chk)
        if chk.counts:
            count += 1
    decision = "canonical" if count >= threshold else "rejected"
    return ConsensusResult(action_hash, threshold, n, count, decision, checks)
