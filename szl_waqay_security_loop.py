"""Waqay Security Loop: a pure, proposal-only remediation control model.

This module is intentionally narrow.  It does not scan source code, patch a
repository, publish an artifact, or operate a deployment.  It normalizes a
small fleet catalog, derives evidence-bound findings from exact component
matches, evaluates fail-closed admission gates, and emits replayable receipts
for a bounded remediation proposal.

Truth boundary
--------------
* Every transition is ``PROPOSAL_ONLY`` and declares ``effectors = 0``.
* A content digest is tamper evidence, not a cryptographic signature.
* DSSE signing is an optional caller-provided hook.  With no signer, the
  envelope is explicitly ``UNSIGNED_NO_SIGNER_AVAILABLE``.
* Gate success permits only the *next proposal state*.  It never authorizes an
  external mutation.

The implementation is standard-library only and performs no network, process,
filesystem, registry, source-control, or deployment calls.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
from dataclasses import asdict, dataclass, replace
from enum import Enum
from typing import Any, Callable, Iterable, Mapping, Sequence


SCHEMA_VERSION = "szl.waqay.security-loop.v1"
RECEIPT_PAYLOAD_TYPE = "application/vnd.szl.waqay-transition+json"
MODE = "PROPOSAL_ONLY"
EFFECTOR_COUNT = 0
MAX_FINDINGS = 128
MAX_AFFECTED_DEPLOYMENTS = 100
MAX_PLAN_BATCHES = 10
MAX_BATCH_SIZE = 25
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """Raised when caller input violates the deterministic contract."""


class TransitionDenied(ContractError):
    """Raised when a state transition or gate is fail-closed."""


class EvidenceState(str, Enum):
    MEASURED = "MEASURED"
    VERIFIED = "VERIFIED"
    SUPPORTED = "SUPPORTED"
    MODELED = "MODELED"
    UNVERIFIED = "UNVERIFIED"
    UNAVAILABLE = "UNAVAILABLE"
    REFUTED = "REFUTED"


class LoopState(str, Enum):
    DETECTED = "DETECTED"
    VALIDATED = "VALIDATED"
    REMEDIATION_PROPOSED = "REMEDIATION_PROPOSED"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    RECALL_PROPOSED = "RECALL_PROPOSED"
    ROLLOFF_PROPOSED = "ROLLOFF_PROPOSED"


class PlanKind(str, Enum):
    RECALL = "RECALL"
    ROLLOFF = "ROLLOFF"


@dataclass(frozen=True)
class Component:
    name: str
    version: str
    purl: str


@dataclass(frozen=True)
class Artifact:
    artifact_digest: str
    sbom_digest: str
    provenance_digest: str
    signature_state: EvidenceState
    components: tuple[Component, ...]


@dataclass(frozen=True)
class Deployment:
    deployment_id: str
    artifact_digest: str
    environment: str
    owner_identity: str
    rollback_digest: str


@dataclass(frozen=True)
class FleetCatalog:
    observed_at: str
    artifacts: tuple[Artifact, ...]
    deployments: tuple[Deployment, ...]
    schema_version: str = SCHEMA_VERSION


@dataclass(frozen=True)
class Advisory:
    advisory_id: str
    component_name: str
    affected_versions: tuple[str, ...]
    severity: str
    evidence_digest: str
    source_uri: str


@dataclass(frozen=True)
class Finding:
    finding_id: str
    advisory_id: str
    component_name: str
    component_version: str
    artifact_digest: str
    affected_deployments: tuple[str, ...]
    advisory_evidence_digest: str
    evidence_state: EvidenceState


@dataclass(frozen=True)
class GateInputs:
    """Measured facts presented to the fail-closed proposal gate.

    Booleans are deliberately explicit.  A missing or unknown fact must be
    represented as ``False`` rather than inferred from another field.
    """

    sbom_verified: bool
    vulnerability_validated: bool
    provenance_verified: bool
    artifact_signature_verified: bool
    principal_verified: bool
    human_approval_verified: bool
    rollback_target_previously_admitted: bool
    graph_trust: str
    unresolved_contradiction: bool
    principal_id: str
    approval_id: str
    validation_evidence_digest: str


@dataclass(frozen=True)
class GateResult:
    gate_id: str
    passed: bool
    evidence_state: EvidenceState
    detail: str


@dataclass(frozen=True)
class RemediationPlan:
    plan_id: str
    kind: PlanKind
    finding_id: str
    target_artifact_digest: str
    rollback_digest: str
    deployment_ids: tuple[str, ...]
    batches: tuple[tuple[str, ...], ...]
    max_parallel: int
    stop_on_failed_health_gate: bool
    effectors: int = EFFECTOR_COUNT
    mode: str = MODE


@dataclass(frozen=True)
class LoopRecord:
    finding: Finding
    state: LoopState
    sequence: int
    last_receipt_digest: str | None = None
    mode: str = MODE
    effectors: int = EFFECTOR_COUNT


DsseSigner = Callable[[Mapping[str, Any], str], Mapping[str, Any]]


def canonical_json(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for hashing and replay."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _require_text(value: str, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContractError(f"{name} must be a non-empty string")
    return value.strip()


def _require_sha256(value: str, name: str) -> str:
    value = _require_text(value, name).lower()
    if not _SHA256_RE.fullmatch(value):
        raise ContractError(f"{name} must be a lowercase SHA-256 hex digest")
    return value


def _sorted_unique(values: Iterable[str], name: str) -> tuple[str, ...]:
    cleaned = tuple(sorted({_require_text(v, name) for v in values}))
    if not cleaned:
        raise ContractError(f"{name} must contain at least one value")
    return cleaned


def normalize_catalog(catalog: FleetCatalog) -> FleetCatalog:
    """Validate and canonically order a fleet catalog.

    Duplicate artifact or deployment identifiers are rejected rather than
    silently merged.  Every deployment must reference a catalog artifact, and
    every rollback digest must also be present in the catalog.
    """

    if catalog.schema_version != SCHEMA_VERSION:
        raise ContractError(f"unsupported schema_version: {catalog.schema_version}")
    _require_text(catalog.observed_at, "observed_at")

    artifact_ids: set[str] = set()
    artifacts: list[Artifact] = []
    for artifact in catalog.artifacts:
        artifact_digest = _require_sha256(artifact.artifact_digest, "artifact_digest")
        if artifact_digest in artifact_ids:
            raise ContractError(f"duplicate artifact_digest: {artifact_digest}")
        artifact_ids.add(artifact_digest)
        sbom_digest = _require_sha256(artifact.sbom_digest, "sbom_digest")
        provenance_digest = _require_sha256(artifact.provenance_digest, "provenance_digest")
        if not isinstance(artifact.signature_state, EvidenceState):
            raise ContractError("signature_state must be an EvidenceState")
        seen_components: set[tuple[str, str, str]] = set()
        components: list[Component] = []
        for component in artifact.components:
            key = (
                _require_text(component.name, "component.name"),
                _require_text(component.version, "component.version"),
                _require_text(component.purl, "component.purl"),
            )
            if key in seen_components:
                raise ContractError(f"duplicate component in artifact {artifact_digest}: {key}")
            seen_components.add(key)
            components.append(Component(*key))
        if not components:
            raise ContractError(f"artifact {artifact_digest} has no SBOM components")
        artifacts.append(
            replace(
                artifact,
                artifact_digest=artifact_digest,
                sbom_digest=sbom_digest,
                provenance_digest=provenance_digest,
                components=tuple(sorted(components, key=lambda c: (c.purl, c.version, c.name))),
            )
        )

    if not artifacts:
        raise ContractError("catalog must contain at least one artifact")

    deployment_ids: set[str] = set()
    deployments: list[Deployment] = []
    for deployment in catalog.deployments:
        deployment_id = _require_text(deployment.deployment_id, "deployment_id")
        if deployment_id in deployment_ids:
            raise ContractError(f"duplicate deployment_id: {deployment_id}")
        deployment_ids.add(deployment_id)
        artifact_digest = _require_sha256(deployment.artifact_digest, "deployment.artifact_digest")
        rollback_digest = _require_sha256(deployment.rollback_digest, "deployment.rollback_digest")
        if artifact_digest not in artifact_ids:
            raise ContractError(f"deployment {deployment_id} references unknown artifact")
        if rollback_digest not in artifact_ids:
            raise ContractError(f"deployment {deployment_id} rollback digest is not admitted")
        deployments.append(
            replace(
                deployment,
                deployment_id=deployment_id,
                artifact_digest=artifact_digest,
                rollback_digest=rollback_digest,
                environment=_require_text(deployment.environment, "environment"),
                owner_identity=_require_text(deployment.owner_identity, "owner_identity"),
            )
        )

    return FleetCatalog(
        observed_at=catalog.observed_at,
        artifacts=tuple(sorted(artifacts, key=lambda a: a.artifact_digest)),
        deployments=tuple(sorted(deployments, key=lambda d: d.deployment_id)),
    )


def catalog_payload(catalog: FleetCatalog) -> dict[str, Any]:
    normalized = normalize_catalog(catalog)
    return _jsonable(normalized)


def catalog_digest(catalog: FleetCatalog) -> str:
    return sha256_json(catalog_payload(catalog))


def security_loop_manifest() -> dict[str, Any]:
    """Return a deterministic public contract suitable for a read-only route."""

    return {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "effectors": EFFECTOR_COUNT,
        "external_mutations": "DISABLED",
        "state_machine": [state.value for state in LoopState],
        "gate_ids": [result.gate_id for result in evaluate_gates(_manifest_gate_fixture())],
        "bounds": {
            "max_findings": MAX_FINDINGS,
            "max_affected_deployments": MAX_AFFECTED_DEPLOYMENTS,
            "max_plan_batches": MAX_PLAN_BATCHES,
            "max_batch_size": MAX_BATCH_SIZE,
        },
        "receipt": {
            "content_addressed": True,
            "payload_type": RECEIPT_PAYLOAD_TYPE,
            "signature_default": "UNSIGNED_NO_SIGNER_AVAILABLE",
            "signature_verification": "EXTERNAL_VERIFIER_REQUIRED",
        },
        "truth_boundary": (
            "Gate success permits only the next proposal state; this module has no external effectors."
        ),
    }


def _manifest_gate_fixture() -> GateInputs:
    """Internal false fixture used only to enumerate the stable gate contract."""

    return GateInputs(
        sbom_verified=False,
        vulnerability_validated=False,
        provenance_verified=False,
        artifact_signature_verified=False,
        principal_verified=False,
        human_approval_verified=False,
        rollback_target_previously_admitted=False,
        graph_trust=EvidenceState.UNAVAILABLE.value,
        unresolved_contradiction=True,
        principal_id="unavailable",
        approval_id="unavailable",
        validation_evidence_digest="",
    )


def detect_findings(
    catalog: FleetCatalog,
    advisories: Sequence[Advisory],
    *,
    max_findings: int = MAX_FINDINGS,
) -> tuple[Finding, ...]:
    """Derive deterministic findings from exact name/version matches.

    This is deliberately not a semantic version-range evaluator.  Advisory
    adapters must normalize affected versions to explicit values first.
    """

    normalized = normalize_catalog(catalog)
    if not 1 <= max_findings <= MAX_FINDINGS:
        raise ContractError(f"max_findings must be between 1 and {MAX_FINDINGS}")

    deployments_by_artifact: dict[str, tuple[str, ...]] = {}
    for artifact in normalized.artifacts:
        deployments_by_artifact[artifact.artifact_digest] = tuple(
            d.deployment_id
            for d in normalized.deployments
            if d.artifact_digest == artifact.artifact_digest
        )

    normalized_advisories: list[Advisory] = []
    advisory_ids: set[str] = set()
    for advisory in advisories:
        advisory_id = _require_text(advisory.advisory_id, "advisory_id")
        if advisory_id in advisory_ids:
            raise ContractError(f"duplicate advisory_id: {advisory_id}")
        advisory_ids.add(advisory_id)
        versions = _sorted_unique(advisory.affected_versions, "affected_versions")
        normalized_advisories.append(
            replace(
                advisory,
                advisory_id=advisory_id,
                component_name=_require_text(advisory.component_name, "component_name"),
                affected_versions=versions,
                severity=_require_text(advisory.severity, "severity").upper(),
                evidence_digest=_require_sha256(advisory.evidence_digest, "advisory.evidence_digest"),
                source_uri=_require_text(advisory.source_uri, "source_uri"),
            )
        )

    findings: list[Finding] = []
    for advisory in sorted(normalized_advisories, key=lambda a: a.advisory_id):
        versions = set(advisory.affected_versions)
        for artifact in normalized.artifacts:
            for component in artifact.components:
                if component.name != advisory.component_name or component.version not in versions:
                    continue
                subject = {
                    "advisory_id": advisory.advisory_id,
                    "component_name": component.name,
                    "component_version": component.version,
                    "artifact_digest": artifact.artifact_digest,
                    "advisory_evidence_digest": advisory.evidence_digest,
                }
                findings.append(
                    Finding(
                        finding_id="waqay:" + sha256_json(subject),
                        advisory_id=advisory.advisory_id,
                        component_name=component.name,
                        component_version=component.version,
                        artifact_digest=artifact.artifact_digest,
                        affected_deployments=deployments_by_artifact[artifact.artifact_digest],
                        advisory_evidence_digest=advisory.evidence_digest,
                        evidence_state=EvidenceState.MEASURED,
                    )
                )
                if len(findings) > max_findings:
                    raise ContractError("finding bound exceeded; narrow the advisory or catalog scope")
    return tuple(sorted(findings, key=lambda f: f.finding_id))


def evaluate_gates(gates: GateInputs) -> tuple[GateResult, ...]:
    """Evaluate independent, explicit proposal gates without aggregation loss."""

    validation_digest_ok = bool(_SHA256_RE.fullmatch(gates.validation_evidence_digest.lower()))
    principal_present = bool(gates.principal_id.strip())
    approval_present = bool(gates.approval_id.strip())
    trust_ok = gates.graph_trust in {EvidenceState.VERIFIED.value, EvidenceState.MEASURED.value}
    checks = (
        ("SBOM_VERIFIED", gates.sbom_verified, "SBOM digest independently verified"),
        ("VULNERABILITY_VALIDATED", gates.vulnerability_validated and validation_digest_ok,
         "technical witness has a valid content digest"),
        ("PROVENANCE_VERIFIED", gates.provenance_verified, "build provenance verified"),
        ("ARTIFACT_SIGNATURE_VERIFIED", gates.artifact_signature_verified, "artifact signature verified"),
        ("PRINCIPAL_VERIFIED", gates.principal_verified and principal_present, "principal identity verified"),
        ("HUMAN_APPROVAL_VERIFIED", gates.human_approval_verified and approval_present,
         "human approval evidence verified"),
        ("ROLLBACK_ADMITTED", gates.rollback_target_previously_admitted,
         "rollback target was previously admitted"),
        ("GRAPH_TRUST", trust_ok, "query-specific graph trust is measured or verified"),
        ("NO_UNRESOLVED_CONTRADICTION", not gates.unresolved_contradiction,
         "no unresolved contradiction affects the target"),
    )
    return tuple(
        GateResult(
            gate_id=gate_id,
            passed=passed,
            evidence_state=EvidenceState.VERIFIED if passed else EvidenceState.UNVERIFIED,
            detail=detail if passed else f"BLOCKED: {detail}",
        )
        for gate_id, passed, detail in checks
    )


def _all_gates_pass(results: Sequence[GateResult]) -> bool:
    return bool(results) and all(result.passed for result in results)


def make_plan(
    *,
    kind: PlanKind,
    finding: Finding,
    target_artifact_digest: str,
    rollback_digest: str,
    deployment_ids: Sequence[str],
    batch_size: int = 10,
    max_parallel: int = 2,
) -> RemediationPlan:
    """Create a bounded plan description; never invoke an effector."""

    target = _require_sha256(target_artifact_digest, "target_artifact_digest")
    rollback = _require_sha256(rollback_digest, "rollback_digest")
    deployments = _sorted_unique(deployment_ids, "deployment_ids")
    if deployments != tuple(sorted(finding.affected_deployments)):
        raise ContractError("plan deployment set must exactly match the finding blast radius")
    if len(deployments) > MAX_AFFECTED_DEPLOYMENTS:
        raise ContractError("affected deployment bound exceeded")
    if not 1 <= batch_size <= MAX_BATCH_SIZE:
        raise ContractError(f"batch_size must be between 1 and {MAX_BATCH_SIZE}")
    if not 1 <= max_parallel <= batch_size:
        raise ContractError("max_parallel must be between 1 and batch_size")
    batches = tuple(
        deployments[index:index + batch_size]
        for index in range(0, len(deployments), batch_size)
    )
    if len(batches) > MAX_PLAN_BATCHES:
        raise ContractError("plan batch bound exceeded")
    plan_subject = {
        "kind": kind.value,
        "finding_id": finding.finding_id,
        "target_artifact_digest": target,
        "rollback_digest": rollback,
        "deployment_ids": deployments,
        "batches": batches,
        "max_parallel": max_parallel,
        "mode": MODE,
        "effectors": EFFECTOR_COUNT,
    }
    return RemediationPlan(
        plan_id="waqay-plan:" + sha256_json(plan_subject),
        kind=kind,
        finding_id=finding.finding_id,
        target_artifact_digest=target,
        rollback_digest=rollback,
        deployment_ids=deployments,
        batches=batches,
        max_parallel=max_parallel,
        stop_on_failed_health_gate=True,
    )


_ALLOWED_TRANSITIONS: dict[LoopState, frozenset[LoopState]] = {
    LoopState.DETECTED: frozenset({LoopState.VALIDATED}),
    LoopState.VALIDATED: frozenset({LoopState.REMEDIATION_PROPOSED}),
    LoopState.REMEDIATION_PROPOSED: frozenset({LoopState.APPROVAL_REQUIRED}),
    LoopState.APPROVAL_REQUIRED: frozenset({LoopState.RECALL_PROPOSED}),
    LoopState.RECALL_PROPOSED: frozenset({LoopState.ROLLOFF_PROPOSED}),
    LoopState.ROLLOFF_PROPOSED: frozenset(),
}


def start_record(finding: Finding) -> LoopRecord:
    if not finding.finding_id.startswith("waqay:"):
        raise ContractError("finding_id must be content-addressed by this contract")
    return LoopRecord(finding=finding, state=LoopState.DETECTED, sequence=0)


def transition(
    record: LoopRecord,
    next_state: LoopState,
    *,
    observed_at: str,
    rationale: str,
    gates: GateInputs | None = None,
    plan: RemediationPlan | None = None,
    signer: DsseSigner | None = None,
) -> tuple[LoopRecord, dict[str, Any]]:
    """Return a new immutable record and a replayable transition receipt.

    Gate policy:
    * ``VALIDATED`` requires reproducible vulnerability evidence.
    * ``APPROVAL_REQUIRED`` records that approval is required, not granted.
    * recall/rolloff proposals require every supply-chain, identity, graph, and
      rollback gate, plus a matching bounded plan.
    """

    if next_state not in _ALLOWED_TRANSITIONS[record.state]:
        raise TransitionDenied(f"transition {record.state.value} -> {next_state.value} is not allowed")
    _require_text(observed_at, "observed_at")
    rationale = _require_text(rationale, "rationale")
    gate_results = evaluate_gates(gates) if gates is not None else tuple()

    if next_state is LoopState.VALIDATED:
        if gates is None:
            raise TransitionDenied("VALIDATED requires gate evidence")
        required = next(result for result in gate_results if result.gate_id == "VULNERABILITY_VALIDATED")
        if not required.passed:
            raise TransitionDenied("vulnerability validation evidence is missing or invalid")

    if next_state in {LoopState.RECALL_PROPOSED, LoopState.ROLLOFF_PROPOSED}:
        if gates is None or not _all_gates_pass(gate_results):
            raise TransitionDenied("all safety, identity, provenance, and rollback gates must pass")
        if plan is None:
            raise TransitionDenied("recall/rolloff proposal requires a bounded plan")
        expected_kind = PlanKind.RECALL if next_state is LoopState.RECALL_PROPOSED else PlanKind.ROLLOFF
        if plan.kind is not expected_kind:
            raise TransitionDenied(f"{next_state.value} requires a {expected_kind.value} plan")
        if plan.finding_id != record.finding.finding_id:
            raise TransitionDenied("plan finding does not match record finding")
        if plan.mode != MODE or plan.effectors != EFFECTOR_COUNT:
            raise TransitionDenied("plan must remain proposal-only with zero effectors")

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "mode": MODE,
        "effectors": EFFECTOR_COUNT,
        "sequence": record.sequence + 1,
        "observed_at": observed_at,
        "finding_id": record.finding.finding_id,
        "from_state": record.state.value,
        "to_state": next_state.value,
        "rationale": rationale,
        "previous_receipt_digest": record.last_receipt_digest,
        "gate_results": [_jsonable(result) for result in gate_results],
        "plan": _jsonable(plan) if plan is not None else None,
        "truth_labels": {
            "external_mutation": "NOT_PERFORMED",
            "authorization_scope": "NEXT_PROPOSAL_STATE_ONLY",
            "model_output": "NOT_USED_BY_CORE_STATE_MACHINE",
            "signature_claim": "DETERMINED_BY_DSSE_ENVELOPE",
        },
    }
    receipt_digest = sha256_json(payload)
    envelope = _make_dsse_envelope(payload, signer)
    receipt = {
        "receipt_digest": receipt_digest,
        "payload": payload,
        "dsse_envelope": envelope,
    }
    updated = LoopRecord(
        finding=record.finding,
        state=next_state,
        sequence=record.sequence + 1,
        last_receipt_digest=receipt_digest,
    )
    return updated, receipt


def _make_dsse_envelope(payload: Mapping[str, Any], signer: DsseSigner | None) -> dict[str, Any]:
    body = canonical_json(payload)
    encoded = base64.b64encode(body).decode("ascii")
    if signer is None:
        return {
            "payloadType": RECEIPT_PAYLOAD_TYPE,
            "payload": encoded,
            "signatures": [],
            "signed": False,
            "verification_state": "UNSIGNED_NO_SIGNER_AVAILABLE",
            "honesty": "No signer hook supplied; no signature fabricated.",
        }
    envelope = dict(signer(payload, RECEIPT_PAYLOAD_TYPE))
    if envelope.get("payloadType") != RECEIPT_PAYLOAD_TYPE or envelope.get("payload") != encoded:
        raise ContractError("DSSE signer returned an envelope for different payload bytes")
    signatures = envelope.get("signatures")
    envelope["signed"] = bool(signatures)
    envelope["verification_state"] = (
        "SIGNED_NOT_VERIFIED_BY_THIS_MODULE" if signatures else "UNSIGNED_SIGNER_RETURNED_NO_SIGNATURE"
    )
    return envelope


def szl_dsse_signer_hook(payload: Mapping[str, Any], payload_type: str) -> Mapping[str, Any]:
    """Optional adapter to the repository's existing DSSE implementation.

    Import is delayed so the core control model remains standalone.  The
    existing signer already returns an honest unsigned envelope when its
    runtime secret is absent.
    """

    from szl_dsse import sign_payload  # type: ignore

    return sign_payload(payload, payload_type)


def verify_receipt(receipt: Mapping[str, Any]) -> dict[str, Any]:
    """Verify content address and DSSE payload binding without trusting a key."""

    try:
        payload = receipt["payload"]
        expected = sha256_json(payload)
        digest_ok = receipt.get("receipt_digest") == expected
        envelope = receipt["dsse_envelope"]
        payload_bytes = base64.b64decode(envelope["payload"], validate=True)
        envelope_payload_ok = payload_bytes == canonical_json(payload)
        payload_type_ok = envelope.get("payloadType") == RECEIPT_PAYLOAD_TYPE
        truth_ok = payload.get("mode") == MODE and payload.get("effectors") == EFFECTOR_COUNT
        return {
            "valid": digest_ok and envelope_payload_ok and payload_type_ok and truth_ok,
            "digest_ok": digest_ok,
            "envelope_payload_ok": envelope_payload_ok,
            "payload_type_ok": payload_type_ok,
            "proposal_only_ok": truth_ok,
            "signature_verified": False,
            "signature_note": "Signature verification requires an independent configured verifier.",
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return {"valid": False, "reason": f"malformed receipt: {type(exc).__name__}"}


def replay_receipts(finding: Finding, receipts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Replay an ordered receipt chain and reconstruct its final proposal state."""

    state = LoopState.DETECTED
    previous: str | None = None
    expected_sequence = 1
    for receipt in receipts:
        verdict = verify_receipt(receipt)
        if not verdict.get("valid"):
            return {"valid": False, "sequence": expected_sequence, "reason": "receipt verification failed"}
        payload = receipt["payload"]
        try:
            from_state = LoopState(payload["from_state"])
            to_state = LoopState(payload["to_state"])
        except (KeyError, ValueError):
            return {"valid": False, "sequence": expected_sequence, "reason": "unknown transition state"}
        if payload.get("sequence") != expected_sequence:
            return {"valid": False, "sequence": expected_sequence, "reason": "sequence mismatch"}
        if payload.get("finding_id") != finding.finding_id:
            return {"valid": False, "sequence": expected_sequence, "reason": "finding mismatch"}
        if payload.get("previous_receipt_digest") != previous:
            return {"valid": False, "sequence": expected_sequence, "reason": "receipt chain mismatch"}
        if from_state is not state or to_state not in _ALLOWED_TRANSITIONS[state]:
            return {"valid": False, "sequence": expected_sequence, "reason": "state transition mismatch"}
        gate_results = payload.get("gate_results")
        if not isinstance(gate_results, list):
            return {"valid": False, "sequence": expected_sequence, "reason": "gate results malformed"}
        gate_map = {
            item.get("gate_id"): item.get("passed")
            for item in gate_results
            if isinstance(item, Mapping)
        }
        if to_state is LoopState.VALIDATED and gate_map.get("VULNERABILITY_VALIDATED") is not True:
            return {"valid": False, "sequence": expected_sequence, "reason": "validation gate not satisfied"}
        if to_state in {LoopState.RECALL_PROPOSED, LoopState.ROLLOFF_PROPOSED}:
            required_gate_ids = set(security_loop_manifest()["gate_ids"])
            if set(gate_map) != required_gate_ids or not all(gate_map.values()):
                return {"valid": False, "sequence": expected_sequence, "reason": "proposal gates not satisfied"}
            plan = payload.get("plan")
            expected_kind = "RECALL" if to_state is LoopState.RECALL_PROPOSED else "ROLLOFF"
            if not isinstance(plan, Mapping) or plan.get("kind") != expected_kind:
                return {"valid": False, "sequence": expected_sequence, "reason": "plan kind mismatch"}
            if plan.get("finding_id") != finding.finding_id:
                return {"valid": False, "sequence": expected_sequence, "reason": "plan finding mismatch"}
            if plan.get("mode") != MODE or plan.get("effectors") != EFFECTOR_COUNT:
                return {"valid": False, "sequence": expected_sequence, "reason": "plan truth boundary mismatch"}
        state = to_state
        previous = receipt["receipt_digest"]
        expected_sequence += 1
    return {
        "valid": True,
        "finding_id": finding.finding_id,
        "final_state": state.value,
        "receipt_count": len(receipts),
        "last_receipt_digest": previous,
        "mode": MODE,
        "effectors": EFFECTOR_COUNT,
        "verification_scope": "STRUCTURAL_CONTENT_AND_TRANSITION_ONLY",
        "signature_verified": False,
    }


def _jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


__all__ = [
    "Advisory",
    "Artifact",
    "Component",
    "ContractError",
    "Deployment",
    "DsseSigner",
    "EFFECTOR_COUNT",
    "EvidenceState",
    "FleetCatalog",
    "Finding",
    "GateInputs",
    "GateResult",
    "LoopRecord",
    "LoopState",
    "MAX_AFFECTED_DEPLOYMENTS",
    "MODE",
    "PlanKind",
    "RemediationPlan",
    "SCHEMA_VERSION",
    "TransitionDenied",
    "canonical_json",
    "catalog_digest",
    "catalog_payload",
    "detect_findings",
    "evaluate_gates",
    "make_plan",
    "normalize_catalog",
    "replay_receipts",
    "security_loop_manifest",
    "sha256_json",
    "start_record",
    "szl_dsse_signer_hook",
    "transition",
    "verify_receipt",
]
