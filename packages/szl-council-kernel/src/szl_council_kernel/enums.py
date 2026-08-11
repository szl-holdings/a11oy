from enum import Enum


class StrEnum(str, Enum):
    def __str__(self) -> str:
        return self.value


class RiskClass(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class BlastRadius(StrEnum):
    SANDBOX = "SANDBOX"
    SINGLE_TARGET = "SINGLE_TARGET"
    MULTI_TARGET = "MULTI_TARGET"
    CROSS_SYSTEM = "CROSS_SYSTEM"


class AutonomyLevel(StrEnum):
    A0_OBSERVE = "A0_OBSERVE"
    A1_PROPOSE = "A1_PROPOSE"
    A2_REVERSIBLE = "A2_REVERSIBLE"
    A3_BOUNDED_PRODUCTION = "A3_BOUNDED_PRODUCTION"
    A4_CROSS_SYSTEM = "A4_CROSS_SYSTEM"
    A5_SELF_MODIFYING = "A5_SELF_MODIFYING"


class CouncilRole(StrEnum):
    AUTHORITY = "AUTHORITY"
    SENTINEL = "SENTINEL"
    VERIFIER = "VERIFIER"
    VALUE = "VALUE"


class CouncilVote(StrEnum):
    SUPPORT = "SUPPORT"
    OPPOSE = "OPPOSE"
    ABSTAIN = "ABSTAIN"
    VETO = "VETO"


class CouncilState(StrEnum):
    QUORUM_VERIFIED = "QUORUM_VERIFIED"
    REQUIRE_HUMAN = "REQUIRE_HUMAN"
    BLOCKED = "BLOCKED"
    CONFLICT = "CONFLICT"
    INSUFFICIENT = "INSUFFICIENT"
    INVALID = "INVALID"


class ReleaseDecision(StrEnum):
    ACT = "ACT"
    ESCALATE = "ESCALATE"
    BLOCK = "BLOCK"


class WorkflowState(StrEnum):
    CREATED = "CREATED"
    RESEARCHING = "RESEARCHING"
    DELIBERATING = "DELIBERATING"
    GATED = "GATED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    SETTLED = "SETTLED"
    ROLLED_BACK = "ROLLED_BACK"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


class ActionKind(StrEnum):
    FILE_WRITE = "FILE_WRITE"
    FILE_APPEND = "FILE_APPEND"
    FILE_DELETE = "FILE_DELETE"

    @property
    def capability(self) -> str:
        return {
            ActionKind.FILE_WRITE: "file:write",
            ActionKind.FILE_APPEND: "file:append",
            ActionKind.FILE_DELETE: "file:delete",
        }[self]


class EvidenceTier(StrEnum):
    UNKNOWN = "UNKNOWN"
    REPORTED = "REPORTED"
    SIMULATED = "SIMULATED"
    MEASURED = "MEASURED"
    VERIFIED = "VERIFIED"


class FoundryStage(StrEnum):
    DISCOVERED = "DISCOVERED"
    QUARANTINED = "QUARANTINED"
    RIGHTS_REVIEWED = "RIGHTS_REVIEWED"
    REVISION_PINNED = "REVISION_PINNED"
    SAFETY_REVIEWED = "SAFETY_REVIEWED"
    CLAIMS_EXTRACTED = "CLAIMS_EXTRACTED"
    REPRODUCED = "REPRODUCED"
    BENCHMARKED = "BENCHMARKED"
    DESIGN_REVIEWED = "DESIGN_REVIEWED"
    PROMOTED = "PROMOTED"
    REJECTED = "REJECTED"
