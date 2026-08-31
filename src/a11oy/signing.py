"""Receipt signing for a11oy.

PRODUCTION PATH — InTotoDsseBackend
-----------------------------------
Envelope: in-toto ITE-6 attestation (CNCF-governed) with DSSE signing, built
with the maintained libraries (CANON section 2 — do NOT hand-roll DSSE/PAE
in production code):

    pip install "in-toto-attestation>=0.9.3" "securesystemslib>=1.0"

  - ``in_toto_attestation.v1.statement.Statement`` /
    ``resource_descriptor.ResourceDescriptor`` build and validate the
    in-toto v1 Statement carrying the ``szl.dev/GovernedAction/v1``
    predicate.
  - ``securesystemslib.dsse.Envelope`` computes the PAE and wraps the
    payload; ``securesystemslib.signer.CryptoSigner`` (Ed25519) signs it;
    ``Envelope.verify`` checks it offline.

Both imports are lazy so this module loads on a fresh clone; calling the
production backend without the dependencies raises a RuntimeError naming
the exact pip line above.

DEMO PATH — DemoEd25519Backend
------------------------------
A teaching-grade backend (CANON section 2 permits a teaching implementation
outside production, clearly marked). It exists so the 12-step acceptance
demo and the offline verifier run on a fresh clone before the production
dependencies are provisioned. Its envelope format
(``application/szl.a11oy-demo+json``) is NOT DSSE and its receipts are NOT
production receipts; the verifier reports the backend of every artifact it
checks, and customer-facing artifacts must use the production path.
"""

from __future__ import annotations

import base64
import hashlib
import json
import struct
from typing import Optional

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

PREDICATE_TYPE = "szl.dev/GovernedAction/v1"
INTOTO_STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
INTOTO_PAYLOAD_TYPE = "application/vnd.in-toto+json"
DEMO_PAYLOAD_TYPE = "application/szl.a11oy-demo+json"
PRODUCTION_PIP_LINE = 'pip install "in-toto-attestation>=0.9.3" "securesystemslib>=1.0"'


def canonical_json(obj: dict) -> bytes:
    """Deterministic JSON encoding used wherever bytes are signed or hashed."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


# ---------------------------------------------------------------------------
# Production path: in-toto ITE-6 Statement + DSSE envelope (CANON section 2)
# ---------------------------------------------------------------------------


def _require_production_deps():
    try:
        from google.protobuf import json_format  # noqa: F401
        from in_toto_attestation.v1 import resource_descriptor, statement  # noqa: F401
        from securesystemslib.dsse import Envelope  # noqa: F401
        from securesystemslib.signer import CryptoSigner  # noqa: F401
    except ImportError as exc:
        raise RuntimeError(
            "the production signing path requires the maintained in-toto and "
            f"DSSE libraries. Install them with:\n    {PRODUCTION_PIP_LINE}"
        ) from exc


class InTotoDsseBackend:
    """Production signing: in-toto v1 Statement in a DSSE envelope."""

    name = "in-toto-ite6+dsse"

    def __init__(self) -> None:
        _require_production_deps()
        from securesystemslib.signer import CryptoSigner

        self._signer = CryptoSigner.generate_ed25519()

    @property
    def public_key(self):
        """The securesystemslib Key for this backend's signer."""
        return self._signer.public_key

    def build_statement(self, receipt_dict: dict, predicate_dict: dict):
        """Build and validate an in-toto v1 Statement for a receipt.

        The statement subject binds the attestation to the predicate content
        by sha256; the predicate dict is embedded as the Statement predicate.
        """
        _require_production_deps()
        from in_toto_attestation.v1.resource_descriptor import ResourceDescriptor
        from in_toto_attestation.v1.statement import Statement

        predicate_digest = hashlib.sha256(canonical_json(predicate_dict)).hexdigest()
        subject = ResourceDescriptor(
            name=f"governed-action/{receipt_dict['predicate']['action_id']}",
            digest={"sha256": predicate_digest},
        )
        stmt = Statement([subject.pb], PREDICATE_TYPE, predicate_dict)
        stmt.validate()
        return stmt

    def sign(self, receipt_dict: dict) -> dict:
        """Return a DSSE envelope dict over the in-toto Statement."""
        from google.protobuf import json_format
        from securesystemslib.dsse import Envelope

        stmt = self.build_statement(receipt_dict, receipt_dict["predicate"])
        payload = json_format.MessageToJson(stmt.pb).encode("utf-8")
        envelope = Envelope(payload=payload, payload_type=INTOTO_PAYLOAD_TYPE, signatures={})
        envelope.sign(self._signer)
        return envelope.to_dict()

    @staticmethod
    def verify(envelope_dict: dict, public_keys: list, threshold: int = 1) -> dict:
        """Verify a DSSE envelope offline; return the statement as a dict.

        Raises securesystemslib.exceptions.VerificationError (or ValueError)
        if signature validity cannot be established. Signature validity is
        integrity only — it says nothing about whether the claim is true
        (CANON Law 5); claim truth is the OfflineVerifier's job.
        """
        _require_production_deps()
        from google.protobuf import json_format
        from in_toto_attestation.v1 import statement_pb2
        from in_toto_attestation.v1.statement import Statement
        from securesystemslib.dsse import Envelope

        envelope = Envelope.from_dict(envelope_dict)
        envelope.verify(public_keys, threshold)
        pb = statement_pb2.Statement()
        json_format.Parse(envelope.payload.decode("utf-8"), pb)
        stmt = Statement.copy_from_pb(pb)
        stmt.validate()
        return json_format.MessageToDict(stmt.pb)


# ---------------------------------------------------------------------------
# Demo path: plainly-labeled Ed25519 teaching backend (NOT DSSE, NOT prod)
# ---------------------------------------------------------------------------

_DEMO_DOMAIN = b"A11OY-DEMO-V1"
_LEN = struct.Struct(">I")


def demo_signed_bytes(payload_type: str, payload: bytes) -> bytes:
    """Domain-separated, length-prefixed bytes that the demo backend signs.

    Deliberately NOT the DSSE PAE: the demo envelope must never be mistaken
    for the production in-toto/DSSE envelope.
    """
    pt = payload_type.encode("utf-8")
    return _DEMO_DOMAIN + _LEN.pack(len(pt)) + pt + _LEN.pack(len(payload)) + payload


class DemoEd25519Backend:
    """Ed25519 signing for the acceptance demo. NOT the production path."""

    name = "a11oy-demo-ed25519"

    def __init__(self, private_key: Optional[Ed25519PrivateKey] = None):
        self._private = private_key or Ed25519PrivateKey.generate()
        raw_pub = self._private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
        self.keyid = hashlib.sha256(raw_pub).hexdigest()[:16]
        self.public_key_raw = raw_pub

    def export_private_pem(self) -> bytes:
        return self._private.private_bytes(
            Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()
        )

    def sign(self, receipt_dict: dict) -> dict:
        payload = canonical_json(receipt_dict)
        signature = self._private.sign(demo_signed_bytes(DEMO_PAYLOAD_TYPE, payload))
        return {
            "payloadType": DEMO_PAYLOAD_TYPE,
            "payload": base64.b64encode(payload).decode("ascii"),
            "signatures": [
                {"keyid": self.keyid, "sig": base64.b64encode(signature).decode("ascii")}
            ],
            "backend": self.name,
        }

    @staticmethod
    def verify_signature(
        payload_type: str, payload: bytes, signature: bytes, public_key_raw: bytes
    ) -> bool:
        try:
            Ed25519PublicKey.from_public_bytes(public_key_raw).verify(
                signature, demo_signed_bytes(payload_type, payload)
            )
            return True
        except Exception:
            return False
