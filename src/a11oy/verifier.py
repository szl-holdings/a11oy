"""OfflineVerifier: checks a11oy receipts with no network and no vendor.

CANON Law 4: missing evidence means INCOMPLETE, never PASS — enforced here,
in code, not in prose.

CANON Law 5: signature is not truth. This verifier keeps two separate
ledgers and never merges them:
  - signature_valid: cryptographic integrity of the artifact (was it altered?)
  - claim_state:     PASS / INCOMPLETE / FAIL — is the recorded claim sound?

An artifact with a valid signature and missing evidence is INCOMPLETE, not
VALID. An artifact with a broken signature is INVALID no matter how complete
its evidence is. A one-byte alteration anywhere in the signed payload breaks
the signature and flips the verdict to INVALID.
"""

from __future__ import annotations

import base64
import binascii
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from pydantic import ValidationError

from .schemas import (
    Completeness,
    GovernedActionReceipt,
    SideEffectClass,
    TIME_PROOF_UNAVAILABLE,
)
from .signing import DEMO_PAYLOAD_TYPE, DemoEd25519Backend


class ClaimState(str, Enum):
    PASS = "PASS"
    INCOMPLETE = "INCOMPLETE"
    FAIL = "FAIL"


class TimeStrength(str, Enum):
    STRONG = "STRONG"  # RFC 3161 token present and host clock NTP-synced
    WEAK = "WEAK"  # recorded truthfully as unavailable — an audited gap


@dataclass
class VerificationResult:
    """What verify() returns. signature_valid and claim_state stay separate."""

    signature_valid: bool
    claim_state: ClaimState
    verdict: str  # VALID | INCOMPLETE | INVALID
    time_strength: TimeStrength
    backend: str
    keyid: Optional[str]
    problems: list[str] = field(default_factory=list)


class OfflineVerifier:
    """Verifies demo-backend envelopes and (via check_claims) any receipt."""

    def __init__(self, public_keys: dict[str, bytes]):
        # keyid -> raw Ed25519 public key bytes (demo backend key registry)
        self._public_keys = dict(public_keys)

    # -- claim truth (backend-independent) --------------------------------

    def check_claims(
        self,
        receipt_dict: dict,
        required_obligations: tuple[str, ...] = (),
        require_strong_time: bool = False,
    ) -> tuple[ClaimState, TimeStrength, list[str]]:
        """Evaluate claim truth for a decoded receipt. Never sees signatures."""
        problems: list[str] = []

        actor = receipt_dict.get("predicate", {}).get("actor", {})
        if actor.get("is_service_account") is not False:
            # CANON Law 3: receipts record natural persons. Hard FAIL.
            problems.append("actor.is_service_account is not false (Law 3)")

        try:
            receipt = GovernedActionReceipt.model_validate(receipt_dict)
        except ValidationError as exc:
            problems.append(f"receipt failed schema validation: {exc.error_count()} error(s)")
            for err in exc.errors()[:5]:
                loc = ".".join(str(part) for part in err["loc"])
                problems.append(f"  {loc}: {err['msg']}")
            return ClaimState.FAIL, TimeStrength.WEAK, problems

        predicate = receipt.predicate

        # Evidence obligations (accumulated by the policy engine) must be met.
        present_kinds = {item.kind for item in predicate.evidence}
        missing = [o for o in required_obligations if o not in present_kinds]
        if missing:
            problems.append(f"missing evidence obligations: {', '.join(missing)}")

        # Claimed completeness vs actual evidence (CANON Law 4).
        if not predicate.evidence:
            problems.append("no evidence items on the predicate")
        if predicate.completeness is Completeness.INCOMPLETE:
            problems.append("predicate declares completeness INCOMPLETE")

        # Time integrity: recorded always; strength judged here.
        if (
            predicate.rfc3161_token != TIME_PROOF_UNAVAILABLE
            and predicate.ntp_synced is True
        ):
            time_strength = TimeStrength.STRONG
        else:
            time_strength = TimeStrength.WEAK
            if require_strong_time:
                problems.append(
                    "strong time proof required by this profile but recorded as "
                    "UNAVAILABLE or NTP-unsynced"
                )

        # Side-effect sanity: IRREVERSIBLE actions must carry human approval.
        if (
            predicate.side_effect_class is SideEffectClass.IRREVERSIBLE
            and receipt.decision.decision == "ALLOW"
            and receipt.human_approval is None
        ):
            problems.append("IRREVERSIBLE action ALLOWed without human approval")

        if any("Law 3" in p for p in problems) or "schema validation" in " ".join(problems):
            return ClaimState.FAIL, time_strength, problems
        if problems:
            return ClaimState.INCOMPLETE, time_strength, problems
        return ClaimState.PASS, time_strength, problems

    # -- envelope verification (demo backend) ------------------------------

    def verify_envelope(
        self,
        envelope: dict,
        required_obligations: tuple[str, ...] = (),
        require_strong_time: bool = False,
    ) -> VerificationResult:
        backend = envelope.get("backend", "unknown")
        keyid: Optional[str] = None
        signature_valid = False
        problems: list[str] = []
        payload: Optional[bytes] = None

        if envelope.get("payloadType") != DEMO_PAYLOAD_TYPE:
            problems.append(f"unexpected payloadType {envelope.get('payloadType')!r}")
        else:
            signatures = envelope.get("signatures") or []
            if len(signatures) != 1:
                problems.append("demo envelopes carry exactly one signature")
            else:
                keyid = signatures[0].get("keyid")
                public_key = self._public_keys.get(keyid)
                if public_key is None:
                    problems.append(f"no public key registered for keyid {keyid!r}")
                else:
                    try:
                        payload = base64.b64decode(envelope["payload"], validate=True)
                        signature = base64.b64decode(signatures[0]["sig"], validate=True)
                    except (KeyError, binascii.Error) as exc:
                        problems.append(f"envelope encoding error: {exc}")
                    else:
                        signature_valid = DemoEd25519Backend.verify_signature(
                            envelope["payloadType"], payload, signature, public_key
                        )
                        if not signature_valid:
                            problems.append(
                                "signature does not verify (artifact altered or wrong key)"
                            )

        if payload is not None:
            try:
                receipt_dict = json.loads(payload.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                receipt_dict = None
                problems.append("payload is not valid JSON")
        else:
            receipt_dict = None

        if receipt_dict is None:
            claim_state, time_strength = ClaimState.FAIL, TimeStrength.WEAK
        else:
            claim_state, time_strength, claim_problems = self.check_claims(
                receipt_dict, required_obligations, require_strong_time
            )
            problems.extend(claim_problems)

        # Verdict: integrity and truth combined, but reported separately above.
        if not signature_valid or claim_state is ClaimState.FAIL:
            verdict = "INVALID"
        elif claim_state is ClaimState.INCOMPLETE:
            verdict = "INCOMPLETE"  # Law 4: never PASS with missing evidence
        else:
            verdict = "VALID"
        return VerificationResult(
            signature_valid=signature_valid,
            claim_state=claim_state,
            verdict=verdict,
            time_strength=time_strength,
            backend=backend,
            keyid=keyid,
            problems=problems,
        )
