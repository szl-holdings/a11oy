from __future__ import annotations

"""Fourfold signed commit-reveal council with portable transcript verification.

The protocol is deliberately stronger than a majority vote. Four registered
specialists commit before reveal, every statement is signed and bound to one
case/policy/subject, correlation is measured across declared independence axes,
valid vetoes fail closed, and opposition is retained in an append-only Minority
Truth Vault. The portable settlement includes enough structured transcript data
for an offline verifier to replay the deterministic decision without private
reasoning or raw evidence.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable, Mapping, Sequence

from .canonical import digest_object, isoformat_utc, parse_utc, require_digest
from .deliberation import MinorityTruthVault
from .diversity import DiversityReport, compile_diversity
from .enums import CouncilRole, CouncilState, CouncilVote, RiskClass
from .errors import IntegrityError, ValidationError
from .models import CouncilAssessment, CouncilCase, CouncilIdentity, CouncilPolicy, CouncilResult
from .proof import Ed25519Signer, PublicVerifier, verify_signed_object

COMMITMENT_CONTENT_TYPE = "application/vnd.szl.council.commitment+json"
ASSESSMENT_CONTENT_TYPE = "application/vnd.szl.council.assessment+json"
RESULT_CONTENT_TYPE = "application/vnd.szl.council.result+json"
SETTLEMENT_SCHEMA = "szl.council-settlement/v2"


@dataclass(frozen=True, slots=True)
class RevealedAssessment:
    assessment: CouncilAssessment
    salt: str
    signed_assessment: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class CouncilEvaluation:
    state: CouncilState
    support_roles: tuple[CouncilRole, ...]
    oppose_roles: tuple[CouncilRole, ...]
    abstain_roles: tuple[CouncilRole, ...]
    veto_roles: tuple[CouncilRole, ...]
    missing_roles: tuple[CouncilRole, ...]
    reason_codes: tuple[str, ...]
    minority_evidence_digests: tuple[str, ...]
    received_support: int
    required_support: int
    diversity: DiversityReport


class CouncilRegistry:
    def __init__(self, identities: Iterable[CouncilIdentity], *, at: str | datetime) -> None:
        members = tuple(identities)
        if len(members) != 4:
            raise ValidationError("Fourfold registry requires exactly four identities")
        member_ids = [item.member_id for item in members]
        key_ids = [item.key_id for item in members]
        roles = [item.role for item in members]
        if len(set(member_ids)) != 4:
            raise ValidationError("council member identities must be unique")
        if len(set(key_ids)) != 4:
            raise ValidationError("one signing key cannot register as multiple specialists")
        if set(roles) != set(CouncilRole):
            raise ValidationError("registry must contain exactly one identity for each Fourfold role")
        if any(not item.active_at(at) for item in members):
            raise ValidationError("all registered identities must be active at session time")
        self.identities = {item.role: item for item in members}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any], *, at: str | datetime) -> "CouncilRegistry":
        if value.get("schema") != "szl.council-registry/v1":
            raise ValidationError("unsupported Council registry schema")
        raw_identities = value.get("identities")
        if not isinstance(raw_identities, list):
            raise ValidationError("Council registry identities must be a list")
        registry = cls((CouncilIdentity.from_dict(item) for item in raw_identities), at=at)
        if registry.to_dict() != dict(value):
            raise IntegrityError("Council registry is noncanonical or has a digest mismatch")
        return registry

    def verifier_for(self, role: CouncilRole) -> PublicVerifier:
        identity = self.identities[role]
        return PublicVerifier(key_id=identity.key_id, public_key=identity.public_key)

    def to_dict(self) -> dict[str, Any]:
        body = {
            "schema": "szl.council-registry/v1",
            "identities": [self.identities[role].to_dict() for role in CouncilRole],
        }
        return {**body, "registry_digest": digest_object(body)}


def commitment_payload(assessment: CouncilAssessment, salt: str) -> dict[str, Any]:
    if not isinstance(salt, str) or len(salt) < 16 or len(salt) > 256:
        raise ValidationError("commitment salt must be a 16..256 character string")
    opening = {"assessment": assessment.to_dict(), "salt": salt}
    return {
        "schema": "szl.council-commitment/v1",
        "case_id": assessment.case_id,
        "member_id": assessment.member_id,
        "role": assessment.role.value,
        "policy_digest": assessment.policy_digest,
        "subject_digest": assessment.subject_digest,
        "assessment_commitment": digest_object(opening),
        "issued_at": assessment.issued_at,
        "expires_at": assessment.expires_at,
    }


def sign_commitment(assessment: CouncilAssessment, salt: str, signer: Ed25519Signer) -> dict[str, Any]:
    return signer.sign_object(commitment_payload(assessment, salt), payload_type=COMMITMENT_CONTENT_TYPE)


def sign_assessment(assessment: CouncilAssessment, signer: Ed25519Signer) -> dict[str, Any]:
    return signer.sign_object(assessment.to_dict(), payload_type=ASSESSMENT_CONTENT_TYPE)


def _commitment_set_digest(
    case: CouncilCase,
    policy: CouncilPolicy,
    commitments: Mapping[CouncilRole, Mapping[str, Any]],
) -> str:
    body = {
        "schema": "szl.council-commitment-set/v1",
        "case_digest": case.digest,
        "policy_digest": policy.digest,
        "commitments": {
            role.value: digest_object(commitments[role])
            for role in CouncilRole
        },
    }
    return digest_object(body)


def _transcript_digest(
    *,
    case: CouncilCase,
    policy: CouncilPolicy,
    registry_digest: str,
    commitment_set_digest: str,
    commitments: Mapping[CouncilRole, Mapping[str, Any]],
    assessments: Mapping[CouncilRole, CouncilAssessment],
    minority_vault_head: str | None,
) -> str:
    body = {
        "schema": "szl.council-transcript/v1",
        "case_digest": case.digest,
        "policy_digest": policy.digest,
        "registry_digest": registry_digest,
        "commitment_set_digest": commitment_set_digest,
        "commitments": {
            role.value: digest_object(commitments[role])
            for role in sorted(commitments, key=lambda item: item.value)
        },
        "assessments": {
            role.value: assessments[role].digest
            for role in sorted(assessments, key=lambda item: item.value)
        },
        "minority_vault_head": minority_vault_head,
    }
    return digest_object(body)


def _evaluate_council(
    *,
    case: CouncilCase,
    policy: CouncilPolicy,
    identities: Sequence[CouncilIdentity],
    assessments: Mapping[CouncilRole, CouncilAssessment],
) -> CouncilEvaluation:
    missing = tuple(sorted(set(CouncilRole) - set(assessments), key=lambda item: item.value))
    diversity = compile_diversity(identities, policy)
    supports = tuple(role for role, assessment in assessments.items() if assessment.vote == CouncilVote.SUPPORT)
    opposes = tuple(role for role, assessment in assessments.items() if assessment.vote == CouncilVote.OPPOSE)
    abstains = tuple(role for role, assessment in assessments.items() if assessment.vote == CouncilVote.ABSTAIN)
    vetoes = tuple(role for role, assessment in assessments.items() if assessment.vote == CouncilVote.VETO)
    minority = tuple(
        sorted(
            {
                digest
                for role, assessment in assessments.items()
                if role in set(opposes) | set(vetoes)
                for digest in assessment.counterevidence_digests
            }
        )
    )
    required_support = (
        policy.high_critical_support_threshold
        if case.risk_class in {RiskClass.HIGH, RiskClass.CRITICAL}
        else policy.low_medium_support_threshold
    )
    reasons: list[str] = []

    if missing:
        state = CouncilState.INSUFFICIENT
        reasons.append("COUNCIL_REVEAL_SET_INCOMPLETE")
    elif not diversity.requirements_met:
        state = CouncilState.INSUFFICIENT
        reasons.extend(diversity.failed_requirements)
    elif CouncilRole.AUTHORITY in vetoes or CouncilRole.AUTHORITY in opposes:
        state = CouncilState.BLOCKED
        reasons.append("AUTHORITY_DENIED")
    elif policy.sentinel_veto_categorical and CouncilRole.SENTINEL in vetoes:
        state = CouncilState.BLOCKED
        reasons.append("SENTINEL_CATEGORICAL_VETO")
    elif policy.verifier_veto_categorical and CouncilRole.VERIFIER in vetoes:
        state = CouncilState.BLOCKED
        reasons.append("VERIFIER_CATEGORICAL_VETO")
    elif vetoes:
        state = CouncilState.BLOCKED
        reasons.append("SPECIALIST_VETO")
    elif opposes and supports:
        state = CouncilState.CONFLICT
        reasons.append("SIGNED_SUPPORT_AND_OPPOSITION")
    elif opposes:
        state = CouncilState.BLOCKED
        reasons.append("UNOPPOSED_SPECIALIST_REJECTION")
    elif abstains:
        state = CouncilState.REQUIRE_HUMAN
        reasons.append("SPECIALIST_ABSTENTION")
    elif policy.require_authority_support and CouncilRole.AUTHORITY not in supports:
        state = CouncilState.REQUIRE_HUMAN
        reasons.append("AUTHORITY_SUPPORT_REQUIRED")
    elif policy.require_verifier_support and CouncilRole.VERIFIER not in supports:
        state = CouncilState.REQUIRE_HUMAN
        reasons.append("VERIFIER_SUPPORT_REQUIRED")
    elif case.value_claimed and policy.require_value_support_when_claimed and CouncilRole.VALUE not in supports:
        state = CouncilState.REQUIRE_HUMAN
        reasons.append("VALUE_SUPPORT_REQUIRED_FOR_VALUE_CLAIM")
    elif len(supports) < required_support:
        state = CouncilState.REQUIRE_HUMAN
        reasons.append("SUPPORT_THRESHOLD_NOT_MET")
    else:
        state = CouncilState.QUORUM_VERIFIED
        reasons.append("FOURFOLD_POLICY_SATISFIED")

    return CouncilEvaluation(
        state=state,
        support_roles=supports,
        oppose_roles=opposes,
        abstain_roles=abstains,
        veto_roles=vetoes,
        missing_roles=missing,
        reason_codes=tuple(sorted(set(reasons))),
        minority_evidence_digests=minority,
        received_support=len(supports),
        required_support=required_support,
        diversity=diversity,
    )


def _result_from_evaluation(
    *,
    case: CouncilCase,
    policy: CouncilPolicy,
    evaluation: CouncilEvaluation,
    transcript_digest: str,
    issued_at: str,
) -> CouncilResult:
    return CouncilResult(
        case_id=case.case_id,
        state=evaluation.state,
        verified=evaluation.state == CouncilState.QUORUM_VERIFIED,
        support_roles=evaluation.support_roles,
        oppose_roles=evaluation.oppose_roles,
        abstain_roles=evaluation.abstain_roles,
        veto_roles=evaluation.veto_roles,
        missing_roles=evaluation.missing_roles,
        reason_codes=evaluation.reason_codes,
        minority_evidence_digests=evaluation.minority_evidence_digests,
        received_support=evaluation.received_support,
        required_support=evaluation.required_support,
        diversity=evaluation.diversity.to_dict(),
        policy_digest=policy.digest,
        subject_digest=case.digest,
        transcript_digest=transcript_digest,
        issued_at=issued_at,
    )


class CouncilSession:
    def __init__(
        self,
        case: CouncilCase,
        policy: CouncilPolicy,
        identities: Iterable[CouncilIdentity],
        *,
        session_time: str | datetime,
    ) -> None:
        self.case = case
        self.policy = policy
        self.session_time = isoformat_utc(session_time)
        if case.policy_digest != policy.digest:
            raise ValidationError("case policy digest does not match exact Council policy")
        self.registry = CouncilRegistry(identities, at=self.session_time)
        self._commitments: dict[CouncilRole, dict[str, Any]] = {}
        self._commitment_payloads: dict[CouncilRole, dict[str, Any]] = {}
        self._reveals: dict[CouncilRole, RevealedAssessment] = {}
        self._reveal_order: list[CouncilRole] = []
        self._sealed_digest: str | None = None
        self.minority_vault = MinorityTruthVault()

    def submit_commitment(self, role: CouncilRole | str, signed_commitment: Mapping[str, Any]) -> str:
        role = CouncilRole(role)
        if self._sealed_digest is not None:
            raise IntegrityError("commitment set is sealed")
        if role in self._commitments:
            raise IntegrityError("role already submitted a commitment")
        identity = self.registry.identities[role]
        payload = verify_signed_object(
            signed_commitment,
            self.registry.verifier_for(role),
            expected_payload_type=COMMITMENT_CONTENT_TYPE,
        )
        if payload.get("schema") != "szl.council-commitment/v1":
            raise IntegrityError("unsupported Council commitment schema")
        expected = {
            "case_id": self.case.case_id,
            "member_id": identity.member_id,
            "role": role.value,
            "policy_digest": self.policy.digest,
            "subject_digest": self.case.digest,
        }
        for key, value in expected.items():
            if payload.get(key) != value:
                raise IntegrityError(f"commitment {key} binding mismatch")
        if parse_utc(payload["issued_at"]) > parse_utc(self.session_time):
            raise IntegrityError("commitment cannot be issued after session time")
        if parse_utc(payload["expires_at"]) <= parse_utc(self.session_time):
            raise IntegrityError("commitment is expired")
        require_digest(payload.get("assessment_commitment", ""), field="assessment_commitment")
        self._commitments[role] = dict(signed_commitment)
        self._commitment_payloads[role] = payload
        return digest_object(signed_commitment)

    def seal_commitments(self) -> str:
        missing = sorted(set(CouncilRole) - set(self._commitments), key=lambda item: item.value)
        if missing:
            raise IntegrityError("cannot seal incomplete commitment set: " + ",".join(item.value for item in missing))
        self._sealed_digest = _commitment_set_digest(self.case, self.policy, self._commitments)
        return self._sealed_digest

    def reveal(
        self,
        role: CouncilRole | str,
        assessment: CouncilAssessment,
        salt: str,
        signed_assessment: Mapping[str, Any],
    ) -> str:
        role = CouncilRole(role)
        if self._sealed_digest is None:
            raise IntegrityError("all commitments must be sealed before reveal")
        if role in self._reveals:
            raise IntegrityError("role already revealed")
        identity = self.registry.identities[role]
        if assessment.role != role or assessment.member_id != identity.member_id:
            raise IntegrityError("assessment role or identity mismatch")
        if assessment.case_id != self.case.case_id:
            raise IntegrityError("assessment case mismatch")
        if assessment.policy_digest != self.policy.digest:
            raise IntegrityError("assessment policy drift")
        if assessment.subject_digest != self.case.digest:
            raise IntegrityError("assessment subject mismatch")
        if not assessment.active_at(self.session_time):
            raise IntegrityError("assessment is not active at session time")
        payload = verify_signed_object(
            signed_assessment,
            self.registry.verifier_for(role),
            expected_payload_type=ASSESSMENT_CONTENT_TYPE,
        )
        if payload != assessment.to_dict():
            raise IntegrityError("signed assessment bytes do not match revealed assessment")
        observed_opening = digest_object({"assessment": assessment.to_dict(), "salt": salt})
        expected_opening = self._commitment_payloads[role]["assessment_commitment"]
        if observed_opening != expected_opening:
            raise IntegrityError("assessment reveal does not open the prior commitment")
        expected_commitment = commitment_payload(assessment, salt)
        if expected_commitment != self._commitment_payloads[role]:
            raise IntegrityError("revealed assessment metadata does not match the committed statement")
        self._reveals[role] = RevealedAssessment(assessment, salt, dict(signed_assessment))
        self._reveal_order.append(role)
        if assessment.vote in {CouncilVote.OPPOSE, CouncilVote.VETO}:
            self.minority_vault.preserve(
                case_id=self.case.case_id,
                role=role.value,
                vote=assessment.vote.value,
                assessment_digest=assessment.digest,
                counterevidence_digests=assessment.counterevidence_digests,
                reason_codes=assessment.reason_codes,
                observed_at=self.session_time,
            )
        return assessment.digest

    def settle(self, aggregator: Ed25519Signer, *, issued_at: str | datetime | None = None) -> dict[str, Any]:
        if self._sealed_digest is None:
            raise IntegrityError("commitment set must be sealed before settlement")
        timestamp = isoformat_utc(issued_at or self.session_time)
        if parse_utc(timestamp) < parse_utc(self.session_time):
            raise ValidationError("Council result cannot predate the session")
        identities = [self.registry.identities[role] for role in CouncilRole]
        assessments = {role: revealed.assessment for role, revealed in self._reveals.items()}
        evaluation = _evaluate_council(
            case=self.case,
            policy=self.policy,
            identities=identities,
            assessments=assessments,
        )
        vault_verification = self.minority_vault.verify()
        if vault_verification["status"] != "PASS":
            raise IntegrityError("Minority Truth Vault failed self-verification")
        transcript_digest = _transcript_digest(
            case=self.case,
            policy=self.policy,
            registry_digest=self.registry.to_dict()["registry_digest"],
            commitment_set_digest=self._sealed_digest,
            commitments=self._commitments,
            assessments=assessments,
            minority_vault_head=vault_verification["head_digest"],
        )
        result = _result_from_evaluation(
            case=self.case,
            policy=self.policy,
            evaluation=evaluation,
            transcript_digest=transcript_digest,
            issued_at=timestamp,
        )
        signed_result = aggregator.sign_object(result.to_dict(), payload_type=RESULT_CONTENT_TYPE)
        body = {
            "schema": SETTLEMENT_SCHEMA,
            "session_time": self.session_time,
            "case": self.case.to_dict(),
            "policy": self.policy.to_dict(),
            "result": result.to_dict(),
            "result_digest": result.digest,
            "signed_result": signed_result,
            "aggregator": aggregator.verifier().to_dict(),
            "registry": self.registry.to_dict(),
            "commitment_set_digest": self._sealed_digest,
            "commitments": {
                role.value: self._commitments[role]
                for role in CouncilRole
            },
            "reveal_order": [role.value for role in self._reveal_order],
            "reveals": {
                role.value: {
                    "assessment": revealed.assessment.to_dict(),
                    "salt": revealed.salt,
                    "signed_assessment": dict(revealed.signed_assessment),
                }
                for role, revealed in self._reveals.items()
            },
            "minority_truth_vault": {
                "entries": list(self.minority_vault.entries()),
                "verification": vault_verification,
            },
            "private_reasoning_included": False,
            "raw_evidence_included": False,
        }
        return {**body, "settlement_digest": digest_object(body)}


def _verify_role_mapping(value: Any, *, field: str, require_all: bool) -> dict[CouncilRole, Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        raise IntegrityError(f"{field} must be a role-keyed mapping")
    result: dict[CouncilRole, Mapping[str, Any]] = {}
    for key, item in value.items():
        try:
            role = CouncilRole(str(key))
        except ValueError as exc:
            raise IntegrityError(f"{field} contains an unknown role") from exc
        if role in result or not isinstance(item, Mapping):
            raise IntegrityError(f"{field} contains a duplicate or invalid role entry")
        result[role] = item
    if require_all and set(result) != set(CouncilRole):
        raise IntegrityError(f"{field} must contain all Fourfold roles")
    return result


def verify_settlement(settlement: Mapping[str, Any]) -> dict[str, Any]:
    """Replay and verify a complete portable Fourfold settlement.

    A passing report proves the included signatures, bindings, commit/reveal
    openings, registry/correlation inputs, Minority Truth chain, deterministic
    decision, transcript digest, and aggregate result. It does not prove that the
    declared operators, providers, evidence domains, or model families are truly
    independent in production; that requires external identity and topology
    evidence.
    """

    errors: list[str] = []
    checks: list[dict[str, Any]] = []

    def check(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})
        if not ok:
            errors.append(name)

    try:
        if settlement.get("schema") != SETTLEMENT_SCHEMA:
            raise IntegrityError("unsupported Council settlement schema")
        body = {key: value for key, value in settlement.items() if key != "settlement_digest"}
        check(
            "SETTLEMENT_DIGEST",
            settlement.get("settlement_digest") == digest_object(body),
            "portable settlement content address",
        )
        check("PRIVATE_REASONING_EXCLUDED", settlement.get("private_reasoning_included") is False)
        check("RAW_EVIDENCE_EXCLUDED", settlement.get("raw_evidence_included") is False)

        session_time = isoformat_utc(settlement["session_time"])
        case = CouncilCase.from_dict(settlement["case"])
        policy = CouncilPolicy.from_dict(settlement["policy"])
        check("CASE_CANONICAL", case.to_dict() == settlement["case"])
        check("POLICY_CANONICAL", policy.to_dict() == settlement["policy"])
        check("CASE_POLICY_BINDING", case.policy_digest == policy.digest)

        registry = CouncilRegistry.from_dict(settlement["registry"], at=session_time)
        registry_dict = registry.to_dict()
        check("REGISTRY_CANONICAL", registry_dict == settlement["registry"])

        commitments = _verify_role_mapping(settlement["commitments"], field="commitments", require_all=True)
        commitment_payloads: dict[CouncilRole, dict[str, Any]] = {}
        for role in CouncilRole:
            payload = verify_signed_object(
                commitments[role],
                registry.verifier_for(role),
                expected_payload_type=COMMITMENT_CONTENT_TYPE,
            )
            if payload.get("schema") != "szl.council-commitment/v1":
                raise IntegrityError("unsupported commitment schema")
            identity = registry.identities[role]
            expected_bindings = {
                "case_id": case.case_id,
                "member_id": identity.member_id,
                "role": role.value,
                "policy_digest": policy.digest,
                "subject_digest": case.digest,
            }
            if any(payload.get(key) != value for key, value in expected_bindings.items()):
                raise IntegrityError(f"{role.value} commitment binding mismatch")
            if parse_utc(payload["issued_at"]) > parse_utc(session_time):
                raise IntegrityError(f"{role.value} commitment issued after session")
            if parse_utc(payload["expires_at"]) <= parse_utc(session_time):
                raise IntegrityError(f"{role.value} commitment expired at session")
            require_digest(payload.get("assessment_commitment", ""), field="assessment_commitment")
            commitment_payloads[role] = payload
            check(f"COMMITMENT_SIGNATURE_{role.value}", True)

        observed_commitment_set = _commitment_set_digest(case, policy, commitments)
        check(
            "COMMITMENT_SET_DIGEST",
            observed_commitment_set == settlement.get("commitment_set_digest"),
        )

        reveals_raw = _verify_role_mapping(settlement["reveals"], field="reveals", require_all=False)
        raw_order = settlement.get("reveal_order")
        if not isinstance(raw_order, list):
            raise IntegrityError("reveal_order must be a list")
        reveal_order: list[CouncilRole] = []
        for value in raw_order:
            role = CouncilRole(str(value))
            if role in reveal_order:
                raise IntegrityError("reveal_order contains duplicates")
            reveal_order.append(role)
        if set(reveal_order) != set(reveals_raw):
            raise IntegrityError("reveal_order does not match reveal set")

        assessments: dict[CouncilRole, CouncilAssessment] = {}
        vault = MinorityTruthVault()
        for role in reveal_order:
            reveal = reveals_raw[role]
            if set(reveal) != {"assessment", "salt", "signed_assessment"}:
                raise IntegrityError(f"{role.value} reveal has noncanonical fields")
            assessment = CouncilAssessment.from_dict(reveal["assessment"])
            if assessment.to_dict() != reveal["assessment"]:
                raise IntegrityError(f"{role.value} assessment is noncanonical")
            identity = registry.identities[role]
            if assessment.role != role or assessment.member_id != identity.member_id:
                raise IntegrityError(f"{role.value} reveal identity mismatch")
            if assessment.case_id != case.case_id or assessment.policy_digest != policy.digest:
                raise IntegrityError(f"{role.value} reveal case/policy mismatch")
            if assessment.subject_digest != case.digest or not assessment.active_at(session_time):
                raise IntegrityError(f"{role.value} reveal subject/time mismatch")
            signed_payload = verify_signed_object(
                reveal["signed_assessment"],
                registry.verifier_for(role),
                expected_payload_type=ASSESSMENT_CONTENT_TYPE,
            )
            if signed_payload != assessment.to_dict():
                raise IntegrityError(f"{role.value} signed assessment mismatch")
            salt = reveal["salt"]
            expected_commitment = commitment_payload(assessment, salt)
            if expected_commitment != commitment_payloads[role]:
                raise IntegrityError(f"{role.value} reveal does not open its exact commitment")
            assessments[role] = assessment
            if assessment.vote in {CouncilVote.OPPOSE, CouncilVote.VETO}:
                vault.preserve(
                    case_id=case.case_id,
                    role=role.value,
                    vote=assessment.vote.value,
                    assessment_digest=assessment.digest,
                    counterevidence_digests=assessment.counterevidence_digests,
                    reason_codes=assessment.reason_codes,
                    observed_at=session_time,
                )
            check(f"ASSESSMENT_SIGNATURE_AND_OPENING_{role.value}", True)

        expected_vault = {
            "entries": list(vault.entries()),
            "verification": vault.verify(),
        }
        check("MINORITY_TRUTH_VAULT", expected_vault == settlement.get("minority_truth_vault"))

        transcript_digest = _transcript_digest(
            case=case,
            policy=policy,
            registry_digest=registry_dict["registry_digest"],
            commitment_set_digest=observed_commitment_set,
            commitments=commitments,
            assessments=assessments,
            minority_vault_head=vault.verify()["head_digest"],
        )

        aggregator_data = settlement["aggregator"]
        if not isinstance(aggregator_data, Mapping) or aggregator_data.get("algorithm") != "Ed25519":
            raise IntegrityError("invalid aggregate verifier metadata")
        verifier = PublicVerifier(
            key_id=aggregator_data["key_id"],
            public_key=aggregator_data["public_key"],
        )
        signed_payload = verify_signed_object(
            settlement["signed_result"], verifier, expected_payload_type=RESULT_CONTENT_TYPE
        )
        result = CouncilResult.from_dict(signed_payload)
        check("SIGNED_RESULT_PAYLOAD", result.to_dict() == settlement.get("result"))
        check("RESULT_DIGEST", result.digest == settlement.get("result_digest"))
        check("TRANSCRIPT_DIGEST", result.transcript_digest == transcript_digest)
        check("RESULT_CASE_BINDING", result.case_id == case.case_id and result.subject_digest == case.digest)
        check("RESULT_POLICY_BINDING", result.policy_digest == policy.digest)
        check("RESULT_NOT_BEFORE_SESSION", parse_utc(result.issued_at) >= parse_utc(session_time))

        evaluation = _evaluate_council(
            case=case,
            policy=policy,
            identities=[registry.identities[role] for role in CouncilRole],
            assessments=assessments,
        )
        expected_result = _result_from_evaluation(
            case=case,
            policy=policy,
            evaluation=evaluation,
            transcript_digest=transcript_digest,
            issued_at=result.issued_at,
        )
        check("DETERMINISTIC_DECISION_REPLAY", expected_result.to_dict() == result.to_dict())
    except Exception as exc:
        errors.append(f"SETTLEMENT_VERIFICATION_ERROR:{type(exc).__name__}")
        checks.append(
            {
                "name": "SETTLEMENT_VERIFICATION_EXCEPTION",
                "ok": False,
                "detail": f"{type(exc).__name__}:{exc}",
            }
        )

    return {
        "schema": "szl.council-settlement-verification/v2",
        "status": "PASS" if not errors else "FAIL",
        "checks": checks,
        "errors": errors,
        "portable_transcript_replayed": not errors,
        "production_independence_verified": False,
        "assurance_scope": "CRYPTOGRAPHIC_AND_DETERMINISTIC_TRANSCRIPT_REPLAY_ONLY",
    }
