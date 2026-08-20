"""Quarantined research normalization and promotion gates.

This module does not fetch remote content. Callers provide immutable source
records and content hashes. Promotion remains blocked until rights, evidence,
and reproduction contracts pass.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import re
from typing import Any, Iterable, Mapping, Sequence

from .kernel import HashChainLedger, canonical_json, sha256_text


_HEX_40_OR_64 = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_ARXIV_REVISION = re.compile(r"^\d{4}\.\d{4,5}v[1-9]\d*$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SourceKind(str, Enum):
    GITHUB = "GITHUB"
    GITLAB = "GITLAB"
    ARXIV = "ARXIV"
    PUBLICATION = "PUBLICATION"


class RightsStatus(str, Enum):
    ALLOWED = "ALLOWED"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


class ReproductionState(str, Enum):
    NOT_RUN = "NOT_RUN"
    PASS = "PASS"
    FAIL = "FAIL"


class PromotionState(str, Enum):
    QUARANTINED = "QUARANTINED"
    ELIGIBLE = "ELIGIBLE"
    BLOCKED = "BLOCKED"


def _nonempty(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware")
    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class ResearchSource:
    source_id: str
    kind: SourceKind
    uri: str
    immutable_revision: str
    content_sha256: str
    retrieved_at: datetime
    rights_status: RightsStatus
    license_expression: str | None = None

    def __post_init__(self) -> None:
        _nonempty("source_id", self.source_id)
        _nonempty("uri", self.uri)
        _nonempty("immutable_revision", self.immutable_revision)
        if not _SHA256.fullmatch(self.content_sha256):
            raise ValueError("content_sha256 must be lowercase SHA-256 hex")
        _utc(self.retrieved_at)
        if self.license_expression is not None:
            _nonempty("license_expression", self.license_expression)
        if self.kind in (SourceKind.GITHUB, SourceKind.GITLAB):
            if not _HEX_40_OR_64.fullmatch(self.immutable_revision):
                raise ValueError("Git source revisions must be full 40- or 64-digit commit hashes")
        elif self.kind is SourceKind.ARXIV:
            if not _ARXIV_REVISION.fullmatch(self.immutable_revision):
                raise ValueError("arXiv revisions must include an explicit version suffix")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "kind": self.kind.value,
            "uri": self.uri,
            "immutable_revision": self.immutable_revision,
            "content_sha256": self.content_sha256,
            "retrieved_at": _utc(self.retrieved_at).isoformat().replace("+00:00", "Z"),
            "rights_status": self.rights_status.value,
            "license_expression": self.license_expression,
        }

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.canonical_dict()))


@dataclass(frozen=True, slots=True)
class ResearchArtifact:
    artifact_id: str
    source: ResearchSource
    normalized_summary: str
    extracted_claims: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    reproduction_state: ReproductionState
    reproducer_digest: str | None = None
    limitations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _nonempty("artifact_id", self.artifact_id)
        _nonempty("normalized_summary", self.normalized_summary)
        for name in ("extracted_claims", "evidence_refs", "limitations"):
            values = getattr(self, name)
            if any(not isinstance(value, str) or not value.strip() for value in values):
                raise ValueError(f"{name} must contain non-empty strings")
        if self.reproduction_state is ReproductionState.PASS:
            if self.reproducer_digest is None or not _SHA256.fullmatch(self.reproducer_digest):
                raise ValueError("a passing reproduction requires a SHA-256 reproducer digest")
        elif self.reproducer_digest is not None and not _SHA256.fullmatch(self.reproducer_digest):
            raise ValueError("reproducer_digest must be lowercase SHA-256 hex")

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "source": self.source.canonical_dict(),
            "normalized_summary": self.normalized_summary,
            "extracted_claims": list(self.extracted_claims),
            "evidence_refs": list(self.evidence_refs),
            "reproduction_state": self.reproduction_state.value,
            "reproducer_digest": self.reproducer_digest,
            "limitations": list(self.limitations),
        }

    @property
    def digest(self) -> str:
        return sha256_text(canonical_json(self.canonical_dict()))


@dataclass(frozen=True, slots=True)
class ResearchPolicy:
    allowed_rights: frozenset[RightsStatus] = field(
        default_factory=lambda: frozenset({RightsStatus.ALLOWED})
    )
    required_reproduction: ReproductionState = ReproductionState.PASS
    minimum_evidence_refs: int = 1
    require_license_expression: bool = True

    def __post_init__(self) -> None:
        if not self.allowed_rights:
            raise ValueError("at least one rights status must be allowed")
        if self.minimum_evidence_refs < 0:
            raise ValueError("minimum evidence count cannot be negative")


@dataclass(frozen=True, slots=True)
class ResearchDisposition:
    artifact_digest: str
    state: PromotionState
    reasons: tuple[str, ...]
    disposition_digest: str

    def canonical_dict(self) -> dict[str, Any]:
        return {
            "artifact_digest": self.artifact_digest,
            "state": self.state.value,
            "reasons": list(self.reasons),
            "disposition_digest": self.disposition_digest,
        }


class ResearchFoundry:
    """Admit research to quarantine and compile promotion eligibility."""

    def __init__(
        self,
        policy: ResearchPolicy | None = None,
        ledger: HashChainLedger | None = None,
    ) -> None:
        self.policy = policy or ResearchPolicy()
        self.ledger = ledger or HashChainLedger()
        self._artifacts: dict[str, ResearchArtifact] = {}
        self._dispositions: dict[str, ResearchDisposition] = {}

    @property
    def artifacts(self) -> Mapping[str, ResearchArtifact]:
        return dict(self._artifacts)

    @property
    def dispositions(self) -> Mapping[str, ResearchDisposition]:
        return dict(self._dispositions)

    def admit(self, artifact: ResearchArtifact) -> ResearchDisposition:
        existing = self._artifacts.get(artifact.artifact_id)
        if existing is not None and existing.digest != artifact.digest:
            raise ValueError("artifact_id already names different content")
        self._artifacts[artifact.artifact_id] = artifact
        disposition = self._compile_disposition(artifact, admitted_only=True)
        self._dispositions[artifact.artifact_id] = disposition
        self.ledger.append(
            "research.admitted",
            {
                "artifact_id": artifact.artifact_id,
                "artifact_digest": artifact.digest,
                "state": disposition.state.value,
            },
        )
        return disposition

    def evaluate_for_promotion(self, artifact_id: str) -> ResearchDisposition:
        artifact = self._artifacts.get(artifact_id)
        if artifact is None:
            raise KeyError(f"unknown artifact_id: {artifact_id}")
        disposition = self._compile_disposition(artifact, admitted_only=False)
        self._dispositions[artifact_id] = disposition
        self.ledger.append(
            "research.evaluated",
            {
                "artifact_id": artifact_id,
                "artifact_digest": artifact.digest,
                "state": disposition.state.value,
                "disposition_digest": disposition.disposition_digest,
            },
        )
        return disposition

    def _compile_disposition(
        self,
        artifact: ResearchArtifact,
        *,
        admitted_only: bool,
    ) -> ResearchDisposition:
        reasons: list[str] = []
        if artifact.source.rights_status not in self.policy.allowed_rights:
            reasons.append("source rights are not allowed by policy")
        if self.policy.require_license_expression and artifact.source.license_expression is None:
            reasons.append("source license expression is absent")
        if len(artifact.evidence_refs) < self.policy.minimum_evidence_refs:
            reasons.append("artifact evidence count is below policy")
        if artifact.reproduction_state is not self.policy.required_reproduction:
            reasons.append("artifact reproduction state does not satisfy policy")
        if not artifact.extracted_claims:
            reasons.append("artifact contains no extracted claims")

        if admitted_only:
            state = PromotionState.QUARANTINED
            if reasons:
                reasons.insert(0, "artifact admitted to quarantine with unresolved gates")
            else:
                reasons.append("artifact admitted to quarantine pending explicit promotion evaluation")
        else:
            state = PromotionState.BLOCKED if reasons else PromotionState.ELIGIBLE
            if not reasons:
                reasons.append("rights, evidence, reproduction, and claim gates passed")

        body = {
            "artifact_digest": artifact.digest,
            "state": state.value,
            "reasons": reasons,
        }
        return ResearchDisposition(
            artifact_digest=artifact.digest,
            state=state,
            reasons=tuple(reasons),
            disposition_digest=sha256_text(canonical_json(body)),
        )


def source_bundle_digest(sources: Iterable[ResearchSource]) -> str:
    ordered = sorted(
        (source.canonical_dict() for source in sources),
        key=lambda value: (value["kind"], value["source_id"]),
    )
    return sha256_text(canonical_json(ordered))


def artifact_bundle_digest(artifacts: Sequence[ResearchArtifact]) -> str:
    ordered = sorted(
        (artifact.canonical_dict() for artifact in artifacts),
        key=lambda value: value["artifact_id"],
    )
    return sha256_text(canonical_json(ordered))
