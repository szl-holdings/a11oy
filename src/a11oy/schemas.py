"""Pydantic v2 models for the szl.dev/GovernedAction/v1 predicate and receipt.

These models are the code-level expression of the CANON laws:

  - Law 3: ``Actor.is_service_account`` is pinned to ``Literal[False]`` so a
    receipt structurally cannot erase the natural persons involved
    (EU AI Act Art. 12(3)(d) posture).
  - Law 4: a predicate with no evidence must carry ``completeness:
    INCOMPLETE``; enforced by a model validator, not by prose.
  - Law 6: four never-collapsed side-effect classes; the most restrictive
    class wins (see policy.py for the ordering).
  - Anti-backdating: every receipt records an RFC 3161 token field and the
    host NTP state. Presence is required by the schema; *strength* is judged
    by the verifier, so a receipt recorded during a TSA outage still records
    the truth (the literal string ``UNAVAILABLE``) instead of going blank.

The JSON Schema twin of the predicate lives at repo root as
``predicate.schema.json`` and must be kept in lockstep with this file.
"""

from __future__ import annotations

import base64
import hashlib
import re
from enum import Enum
from typing import Literal, Optional

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

PREDICATE_TYPE = "szl.dev/GovernedAction/v1"
TIME_PROOF_UNAVAILABLE = "UNAVAILABLE"

_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_B64_RE = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")


class SideEffectClass(str, Enum):
    """The four never-collapsed side-effect classes (CANON Law 6)."""

    READ_ONLY = "READ_ONLY"
    REVERSIBLE = "REVERSIBLE"
    EXTERNAL_VISIBLE = "EXTERNAL_VISIBLE"
    IRREVERSIBLE = "IRREVERSIBLE"


# Most-restrictive-wins ordering. Higher number = more restrictive.
RESTRICTIVENESS = {
    SideEffectClass.READ_ONLY: 0,
    SideEffectClass.REVERSIBLE: 1,
    SideEffectClass.EXTERNAL_VISIBLE: 2,
    SideEffectClass.IRREVERSIBLE: 3,
}


def most_restrictive(classes: list[SideEffectClass]) -> SideEffectClass:
    """Return the most restrictive of a non-empty list of side-effect classes."""
    if not classes:
        raise ValueError("most_restrictive requires at least one class")
    return max(classes, key=lambda c: RESTRICTIVENESS[c])


class Completeness(str, Enum):
    COMPLETE = "COMPLETE"
    INCOMPLETE = "INCOMPLETE"


class Actor(BaseModel):
    """The natural person responsible for the action (CANON Law 3)."""

    model_config = ConfigDict(extra="forbid")

    actor_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    is_service_account: Literal[False] = False


class EvidenceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(min_length=1)
    kind: str = Field(min_length=1)
    sha256: str
    uri: Optional[str] = None
    description: Optional[str] = None

    @field_validator("sha256")
    @classmethod
    def _sha256_hex(cls, value: str) -> str:
        if not _SHA256_HEX_RE.match(value):
            raise ValueError("sha256 must be 64 lowercase hex characters")
        return value


class RedactionCommitment(BaseModel):
    """Salted-hash commitment to a redacted field's plaintext.

    Closes the redaction-removes-exculpatory-evidence hole (CANON section 11):
    the receipt proves a specific plaintext existed without revealing it.
    """

    model_config = ConfigDict(extra="forbid")

    commitment_id: str = Field(min_length=1)
    field_path: str = Field(min_length=1)
    salt_b64: str
    sha256_b64: str

    @field_validator("salt_b64", "sha256_b64")
    @classmethod
    def _b64(cls, value: str) -> str:
        if not _B64_RE.match(value) or len(value) % 4 != 0:
            raise ValueError("must be canonical base64")
        return value

    @staticmethod
    def compute_digest(plaintext: bytes, salt: bytes) -> bytes:
        return hashlib.sha256(salt + b"\x00" + plaintext).digest()

    @classmethod
    def create(
        cls, commitment_id: str, field_path: str, plaintext: bytes, salt: bytes
    ) -> "RedactionCommitment":
        if len(salt) < 16:
            raise ValueError("salt must be at least 16 bytes")
        return cls(
            commitment_id=commitment_id,
            field_path=field_path,
            salt_b64=base64.b64encode(salt).decode("ascii"),
            sha256_b64=base64.b64encode(cls.compute_digest(plaintext, salt)).decode("ascii"),
        )

    def verify(self, plaintext: bytes) -> bool:
        salt = base64.b64decode(self.salt_b64)
        expected = base64.b64decode(self.sha256_b64)
        return self.compute_digest(plaintext, salt) == expected


class GovernedActionPredicate(BaseModel):
    """The szl.dev/GovernedAction/v1 predicate."""

    model_config = ConfigDict(extra="forbid")

    predicate_type: Literal["szl.dev/GovernedAction/v1"] = PREDICATE_TYPE
    action_id: str = Field(min_length=1)
    actor: Actor
    action_type: str = Field(min_length=1)
    side_effect_class: SideEffectClass
    evidence: list[EvidenceItem]
    completeness: Completeness
    redaction_commitments: list[RedactionCommitment]
    rfc3161_token: str = Field(min_length=1)
    ntp_synced: bool

    @model_validator(mode="after")
    def _law4_missing_evidence_is_incomplete(self) -> "GovernedActionPredicate":
        if not self.evidence and self.completeness is Completeness.COMPLETE:
            raise ValueError(
                "CANON Law 4: a predicate with no evidence is INCOMPLETE, "
                "never COMPLETE"
            )
        return self


class PolicyDecisionRecord(BaseModel):
    """The policy engine's decision, recorded on the receipt."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["ALLOW", "DENY"]
    reason: str = Field(min_length=1)
    first_match_rule: Optional[str]
    matched_rules: list[str]
    evidence_obligations: list[str]
    effective_side_effect_class: SideEffectClass
    requires_human_approval: bool


class HumanApproval(BaseModel):
    """Approval by a named natural person (never a service account)."""

    model_config = ConfigDict(extra="forbid")

    approver: Actor
    approved_at: AwareDatetime
    rationale: str = Field(min_length=1)


class ObservationWindow(BaseModel):
    """Post-deploy observation window (locked wedge, stage 8)."""

    model_config = ConfigDict(extra="forbid")

    start: AwareDatetime
    end: AwareDatetime

    @model_validator(mode="after")
    def _end_after_start(self) -> "ObservationWindow":
        if self.end <= self.start:
            raise ValueError("observation window end must be after start")
        return self


class GovernedActionReceipt(BaseModel):
    """What the signature actually covers: predicate plus decision context."""

    model_config = ConfigDict(extra="forbid")

    receipt_id: str = Field(min_length=1)
    predicate: GovernedActionPredicate
    decision: PolicyDecisionRecord
    human_approval: Optional[HumanApproval]
    observation_window: ObservationWindow
    retention_days: int = Field(ge=180)  # CANON Law 10: 6-month floor, 180 days
    issued_at: AwareDatetime
    generator: str = Field(min_length=1)

    @model_validator(mode="after")
    def _approval_present_when_required(self) -> "GovernedActionReceipt":
        if (
            self.decision.decision == "ALLOW"
            and self.decision.requires_human_approval
            and self.human_approval is None
        ):
            raise ValueError(
                "CANON Law 6: this action requires human approval; an ALLOW "
                "receipt without a HumanApproval record is invalid"
            )
        if (
            self.predicate.side_effect_class is SideEffectClass.IRREVERSIBLE
            and self.decision.decision == "ALLOW"
            and self.human_approval is None
        ):
            raise ValueError(
                "CANON Law 6: IRREVERSIBLE actions always require human approval"
            )
        return self
