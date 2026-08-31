"""a11oy.receipts — GovernedAction/v1 predicate build + DSSE-style sign.

Envelope shape follows in-toto Statement + DSSE signing. For production,
bind to the maintained `in-toto-attestation` PyPI package — do NOT ship
this hand-rolled crypto path as the final signer. It exists so the payload
runs anywhere and the demo is verifiable today.

Honesty rules enforced here (not in prose):
  * completeness=COMPLETE with any unsatisfied obligation raises.
  * An approval whose principal is a service account raises (Art. 12(3)(d)).
  * The signature scheme actually used is recorded on the envelope.
"""
from __future__ import annotations

import base64
import datetime
import hashlib
import hmac as hmac_mod
import json
import os
from pathlib import Path

PAYLOAD_TYPE = "application/vnd.in-toto+json"
PREDICATE_TYPE = "https://szl.dev/GovernedAction/v1"
STATEMENT_TYPE = "https://in-toto.io/Statement/v1"


class HonestyViolation(Exception):
    """A receipt that would overstate the truth is refused at construction."""


def canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def pae(payload_type: str, payload: bytes) -> bytes:
    """DSSE Pre-Authentication Encoding, spec-exact:
    "DSSEv1" SP <len(type)> SP <type> SP <len(payload)> SP <payload>"""
    return (
        b"DSSEv1 "
        + str(len(payload_type)).encode() + b" " + payload_type.encode()
        + b" " + str(len(payload)).encode() + b" " + payload
    )


# ---------------------------------------------------------------- keys ----

class Signer:
    """Ed25519 when `cryptography` is available; otherwise HMAC-SHA256 in
    explicitly-labelled demo mode. The scheme is always disclosed."""

    def __init__(self, keystore: Path):
        self.keystore = Path(keystore)
        self.keystore.mkdir(parents=True, exist_ok=True)
        self.scheme = None
        self._ed_private = None
        self._ed_public_pem: str | None = None
        self._hmac_key: bytes | None = None
        self._load_or_create()

    def _load_or_create(self):
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            from cryptography.hazmat.primitives import serialization
            priv_path = self.keystore / "ed25519_private.pem"
            pub_path = self.keystore / "ed25519_public.pem"
            if priv_path.exists():
                self._ed_private = serialization.load_pem_private_key(priv_path.read_bytes(), password=None)
                self._ed_public_pem = pub_path.read_text()
            else:
                self._ed_private = Ed25519PrivateKey.generate()
                priv_path.write_bytes(self._ed_private.private_bytes(
                    serialization.Encoding.PEM,
                    serialization.PrivateFormat.PKCS8,
                    serialization.NoEncryption(),
                ))
                os.chmod(priv_path, 0o600)
                pub = self._ed_private.public_key().public_bytes(
                    serialization.Encoding.PEM,
                    serialization.PublicFormat.SubjectPublicKeyInfo,
                )
                pub_path.write_bytes(pub)
                self._ed_public_pem = pub.decode()
            self.scheme = "ed25519"
            return
        except ImportError:
            pass
        # Demo fallback — labelled, never silent.
        key_path = self.keystore / "hmac_demo.key"
        if key_path.exists():
            self._hmac_key = key_path.read_bytes()
        else:
            self._hmac_key = os.urandom(32)
            key_path.write_bytes(self._hmac_key)
            os.chmod(key_path, 0o600)
        self.scheme = "hmac-sha256-demo"

    @property
    def keyid(self) -> str:
        if self.scheme == "ed25519":
            return "szl-ed25519-" + sha256_hex(self._ed_public_pem.encode())[:12]
        return "szl-hmac-demo-" + sha256_hex(self._hmac_key)[:12]

    def public_descriptor(self) -> dict:
        if self.scheme == "ed25519":
            return {"scheme": "ed25519", "keyid": self.keyid, "public_key_pem": self._ed_public_pem}
        return {
            "scheme": "hmac-sha256-demo", "keyid": self.keyid,
            "limitation": "DEMO ONLY — symmetric demo secret, not a production signing identity. "
                          "Bind in-toto-attestation + a real KMS/HSM before any external claim.",
        }

    def sign(self, data: bytes) -> bytes:
        if self.scheme == "ed25519":
            return self._ed_private.sign(data)
        return hmac_mod.new(self._hmac_key, data, hashlib.sha256).digest()

    def verify(self, data: bytes, sig: bytes) -> bool:
        if self.scheme == "ed25519":
            try:
                from cryptography.exceptions import InvalidSignature
                self._ed_private.public_key().verify(sig, data)
                return True
            except Exception:
                return False
        return hmac_mod.compare_digest(
            hmac_mod.new(self._hmac_key, data, hashlib.sha256).digest(), sig
        )


# ------------------------------------------------------------ predicate ----

def build_predicate(
    *,
    action: dict,
    actor: dict,
    authority: dict,
    evidence: dict,
    approval: dict | None = None,
    limitations: list[str] | None = None,
    context: dict | None = None,
) -> dict:
    if not authority.get("evaluated_before_execution"):
        raise HonestyViolation("authority.evaluated_before_execution must be true — post-hoc logs are not governance")
    obligations = evidence.get("obligations", [])
    completeness = evidence.get("completeness", "INCOMPLETE")
    if completeness == "COMPLETE" and any(not o.get("satisfied") for o in obligations):
        raise HonestyViolation("completeness=COMPLETE with unsatisfied obligations")
    if completeness not in ("COMPLETE", "INCOMPLETE"):
        raise HonestyViolation(f"completeness must be COMPLETE|INCOMPLETE, got {completeness!r}")
    if approval is not None:
        principal = approval.get("principal", {})
        if principal.get("is_service_account") is True:
            raise HonestyViolation(
                "approval principal is_service_account=true — Article 12(3)(d) requires a natural person"
            )
    return {
        "action": action,
        "actor": actor,
        "authority": authority,
        "evidence": evidence,
        "approval": approval,
        "limitations": limitations or [],
        "context": context or {},
        "timestamp": {"utc": datetime.datetime.now(datetime.timezone.utc).isoformat(), "ntp_synced": None},
    }


def sign_envelope(predicate: dict, signer: Signer) -> dict:
    statement = {
        "_type": STATEMENT_TYPE,
        "predicateType": PREDICATE_TYPE,
        "subject": [{"name": predicate["action"].get("id", "action"),
                     "digest": {"sha256": sha256_hex(canonical(predicate["action"]))}}],
        "predicate": predicate,
    }
    payload = canonical(statement)
    sig = signer.sign(pae(PAYLOAD_TYPE, payload))
    envelope = {
        "payloadType": PAYLOAD_TYPE,
        "payload": base64.b64encode(payload).decode(),
        "signatures": [{
            "keyid": signer.keyid,
            "scheme": signer.scheme,
            "sig": base64.b64encode(sig).decode(),
        }],
        "signer": signer.public_descriptor(),
    }
    if signer.scheme != "ed25519":
        envelope.setdefault("limitations", []).append(
            "Signed with hmac-sha256-demo — demo mode, not a production identity."
        )
    return envelope


def decode_statement(envelope: dict) -> dict:
    return json.loads(base64.b64decode(envelope["payload"]))
