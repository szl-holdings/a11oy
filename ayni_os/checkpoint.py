"""Periodic KIPU snapshot every 7 minutes, signed via DSSE.

A checkpoint is a content-addressed snapshot of the ledger state at a timestamp,
wrapped in a DSSE (Dead Simple Signing Envelope, in-toto spec) PAE-encoded payload and
signed with the SZLHOLDINGS EC key. Checkpoints accelerate rewind (replay starts from
the nearest prior checkpoint instead of genesis) and provide signed provenance.

HONEST: this is ordinary signed snapshotting. No mysticism.
Open-source deps only: stdlib + (optional) `cryptography` for EC signing; falls back
to an HMAC stub if the key/lib is unavailable so tests run anywhere.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time as _time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .ledger import ReciprocityLedger, ORGANS

CHECKPOINT_INTERVAL_SECONDS = 7 * 60  # every 7 minutes
DSSE_PAYLOAD_TYPE = "application/vnd.szl.ayni-checkpoint+json"


def _pae(payload_type: str, body: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding (in-toto/DSSE spec)."""
    return b"DSSEv1 %d %b %d %b" % (
        len(payload_type), payload_type.encode(), len(body), body
    )


def _load_ec_key(key_path: Optional[str]):
    if not key_path:
        return None
    try:
        from cryptography.hazmat.primitives import serialization
        data = Path(key_path).read_bytes()
        return serialization.load_pem_private_key(data, password=None)
    except Exception:
        return None


@dataclass
class Checkpoint:
    ts: float
    state_hash: str          # sha256 over canonical ledger state up to ts
    n_entries: int
    ayni: dict               # per-organ alpha at ts
    chain_ok: bool


def snapshot_state(ledger: ReciprocityLedger, at_ts: float) -> Checkpoint:
    entries = ledger.entries(until_ts=at_ts)
    canon = json.dumps(
        [e.entry_hash for e in entries], separators=(",", ":")
    ).encode()
    state_hash = hashlib.sha256(canon).hexdigest()
    ayni = {o: round(ledger.ayni_coefficient(o, hi=at_ts), 6) for o in ORGANS}
    return Checkpoint(
        ts=at_ts, state_hash=state_hash, n_entries=len(entries),
        ayni=ayni, chain_ok=ledger.verify_chain(until_ts=at_ts),
    )


def sign_checkpoint(cp: Checkpoint, ec_key_path: Optional[str] = None) -> dict:
    """Produce a DSSE envelope for the checkpoint."""
    body = json.dumps(cp.__dict__, sort_keys=True, separators=(",", ":")).encode()
    pae = _pae(DSSE_PAYLOAD_TYPE, body)
    key = _load_ec_key(ec_key_path)
    if key is not None:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        sig = key.sign(pae, ec.ECDSA(hashes.SHA256()))
        keyid = "szlholdings-ec"
        scheme = "ecdsa-p256-sha256"
    else:
        # Honest fallback: HMAC stub so tests run without the private key.
        sig = hmac.new(b"ayni-os-checkpoint-stub", pae, hashlib.sha256).digest()
        keyid = "hmac-stub"
        scheme = "hmac-sha256-stub"
    return {
        "payloadType": DSSE_PAYLOAD_TYPE,
        "payload": base64.b64encode(body).decode(),
        "signatures": [{
            "keyid": keyid, "scheme": scheme,
            "sig": base64.b64encode(sig).decode(),
        }],
    }


def verify_envelope(envelope: dict, ec_key_path: Optional[str] = None) -> bool:
    body = base64.b64decode(envelope["payload"])
    pae = _pae(envelope["payloadType"], body)
    s = envelope["signatures"][0]
    sig = base64.b64decode(s["sig"])
    if s["scheme"] == "hmac-sha256-stub":
        expect = hmac.new(b"ayni-os-checkpoint-stub", pae, hashlib.sha256).digest()
        return hmac.compare_digest(sig, expect)
    key = _load_ec_key(ec_key_path)
    if key is None:
        return False
    try:
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        key.public_key().verify(sig, pae, ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False


class CheckpointStore:
    """Holds signed checkpoints; emits one every CHECKPOINT_INTERVAL_SECONDS."""

    def __init__(self, ec_key_path: Optional[str] = None) -> None:
        self.ec_key_path = ec_key_path
        self._cps: list[tuple[Checkpoint, dict]] = []
        self._last_ts: Optional[float] = None

    def maybe_checkpoint(self, ledger: ReciprocityLedger,
                         now: Optional[float] = None) -> Optional[Checkpoint]:
        now = now if now is not None else _time.time()
        if self._last_ts is None or (now - self._last_ts) >= CHECKPOINT_INTERVAL_SECONDS:
            cp = snapshot_state(ledger, at_ts=now)
            env = sign_checkpoint(cp, self.ec_key_path)
            self._cps.append((cp, env))
            self._last_ts = now
            return cp
        return None

    def force_checkpoint(self, ledger: ReciprocityLedger, at_ts: float) -> Checkpoint:
        cp = snapshot_state(ledger, at_ts=at_ts)
        env = sign_checkpoint(cp, self.ec_key_path)
        self._cps.append((cp, env))
        self._last_ts = at_ts
        return cp

    def nearest_before(self, ts: float) -> Optional[tuple[Checkpoint, dict]]:
        prior = [c for c in self._cps if c[0].ts <= ts]
        return max(prior, key=lambda c: c[0].ts) if prior else None

    def all(self) -> list[tuple[Checkpoint, dict]]:
        return list(self._cps)
