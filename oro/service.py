# SPDX-License-Identifier: Apache-2.0
"""ORO application service: admission, execution, evidence, and certificates."""
from __future__ import annotations

import re
from dataclasses import asdict
from typing import Any, Callable, Mapping, Sequence

from .core import (
    CODEX_SCHEMA,
    ORBIT_KINDS,
    Allocation,
    Arrival,
    BarrierEngine,
    CodexManifest,
    InvariantBinding,
    OROContractError,
    OROStateError,
    Rank,
    RegisteredInvariant,
    RoleSpec,
    ReceiptSigner,
    allocate_rank,
    canonical_json,
    digest_bytes,
    parse_utc,
    receipt_digest,
    semantic_hash,
    utc_now,
)
from .store import OROStore

FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


def _binding(
    invariant_id: str,
    evaluator: Callable[[Mapping[str, Any]], tuple[bool, str]],
    *,
    source_contract: str,
    golden_vectors: Sequence[Mapping[str, Any]],
) -> RegisteredInvariant:
    version = "1.0.0"
    binding = InvariantBinding(
        invariant_id=invariant_id,
        version=version,
        source_blob_digest=digest_bytes(source_contract.encode("utf-8")),
        implementation_digest=digest_bytes(
            f"oro/service.py:{invariant_id}:{version}:{evaluator.__name__}".encode("utf-8")
        ),
        input_schema="szl.oro.merged-participant-payload/v1",
        golden_vectors_digest=digest_bytes(canonical_json(list(golden_vectors))),
        blocking=True,
    )
    return RegisteredInvariant(binding=binding, evaluator=evaluator)


def _participant_payloads(merged: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    participants = merged.get("participants")
    if not isinstance(participants, list):
        return []
    payloads: list[Mapping[str, Any]] = []
    for item in participants:
        if not isinstance(item, Mapping) or not isinstance(item.get("payload"), Mapping):
            return []
        payloads.append(item["payload"])
    return payloads


def _total_provenance(merged: Mapping[str, Any]) -> tuple[bool, str]:
    payloads = _participant_payloads(merged)
    if not payloads:
        return False, "no participant payloads"
    for payload in payloads:
        provenance = payload.get("provenance")
        if not isinstance(provenance, list) or not provenance:
            return False, "participant payload has no provenance records"
        for record in provenance:
            if not isinstance(record, Mapping):
                return False, "provenance record is not an object"
            if not isinstance(record.get("span_id"), str) or not record["span_id"]:
                return False, "provenance span_id is missing"
            if not isinstance(record.get("digest"), str) or not SHA256_RE.fullmatch(record["digest"]):
                return False, "provenance digest is not sha256-bound"
    return True, "every participant payload has total sha256-bound provenance"


def _citation_retrieval(merged: Mapping[str, Any]) -> tuple[bool, str]:
    for payload in _participant_payloads(merged):
        retrieved = payload.get("retrieved_span_ids", [])
        citations = payload.get("citation_span_ids", [])
        if not isinstance(retrieved, list) or not all(isinstance(value, str) for value in retrieved):
            return False, "retrieved_span_ids is malformed"
        if not isinstance(citations, list) or not all(isinstance(value, str) for value in citations):
            return False, "citation_span_ids is malformed"
        missing = sorted(set(citations) - set(retrieved))
        if missing:
            return False, "citations reference unretrieved spans"
    return True, "all cited spans were retrieved"


def _canonical_units_and_money(merged: Mapping[str, Any]) -> tuple[bool, str]:
    def walk(value: Any, path: str = "$") -> tuple[bool, str]:
        if isinstance(value, float):
            return False, f"binary float found at {path}"
        if isinstance(value, Mapping):
            for key, child in value.items():
                if not isinstance(key, str):
                    return False, f"non-string JSON key at {path}"
                lowered = key.lower()
                if any(token in lowered for token in ("money", "amount", "price", "cost")):
                    if isinstance(child, bool) or not isinstance(child, (int, str, Mapping, list, type(None))):
                        return False, f"non-canonical money representation at {path}.{key}"
                if lowered.endswith("_micros") and (isinstance(child, bool) or not isinstance(child, int)):
                    return False, f"micros value is not an integer at {path}.{key}"
                passed, detail = walk(child, f"{path}.{key}")
                if not passed:
                    return passed, detail
        elif isinstance(value, list):
            for index, child in enumerate(value):
                passed, detail = walk(child, f"{path}[{index}]")
                if not passed:
                    return passed, detail
        return True, "canonical"

    for payload in _participant_payloads(merged):
        passed, detail = walk(payload)
        if not passed:
            return passed, detail
        measurements = payload.get("measurements", [])
        if measurements is not None:
            if not isinstance(measurements, list):
                return False, "measurements must be an array"
            for item in measurements:
                if not isinstance(item, Mapping):
                    return False, "measurement is not an object"
                if not isinstance(item.get("unit"), str) or not item["unit"].strip():
                    return False, "measurement unit is missing"
                value = item.get("value_micros")
                if isinstance(value, bool) or not isinstance(value, int):
                    return False, "measurement value_micros must be integer"
    return True, "money and measurements use canonical integer/declared-unit forms"


def _utc_boundaries(merged: Mapping[str, Any]) -> tuple[bool, str]:
    def walk(value: Any, path: str = "$") -> tuple[bool, str]:
        if isinstance(value, Mapping):
            for key, child in value.items():
                if isinstance(key, str) and (
                    key.lower().endswith("_at") or key.lower().endswith("timestamp")
                ):
                    if not isinstance(child, str):
                        return False, f"boundary timestamp is not text at {path}.{key}"
                    try:
                        parse_utc(child)
                    except OROContractError:
                        return False, f"boundary timestamp is not UTC at {path}.{key}"
                passed, detail = walk(child, f"{path}.{key}")
                if not passed:
                    return passed, detail
        elif isinstance(value, list):
            for index, child in enumerate(value):
                passed, detail = walk(child, f"{path}[{index}]")
                if not passed:
                    return passed, detail
        return True, "UTC"

    for payload in _participant_payloads(merged):
        passed, detail = walk(payload)
        if not passed:
            return passed, detail
    return True, "all declared boundary timestamps are UTC"


def _scoped_authorization(merged: Mapping[str, Any]) -> tuple[bool, str]:
    for payload in _participant_payloads(merged):
        authorization = payload.get("authorization")
        if not isinstance(authorization, Mapping):
            return False, "authorization object is missing"
        for key in ("subject", "scope", "expires_at", "grant_digest"):
            if not isinstance(authorization.get(key), str) or not authorization[key]:
                return False, f"authorization {key} is missing"
        try:
            parse_utc(authorization["expires_at"])
        except OROContractError:
            return False, "authorization expiry is not UTC"
        if not SHA256_RE.fullmatch(authorization["grant_digest"]):
            return False, "authorization grant is not sha256-bound"
    return True, "every participant carries a scoped, expiring authorization grant"


def _evaluator_and_authors(merged: Mapping[str, Any]) -> tuple[bool, str]:
    evaluator_digests: set[str] = set()
    for payload in _participant_payloads(merged):
        evaluator = payload.get("evaluator_digest")
        if not isinstance(evaluator, str) or not SHA256_RE.fullmatch(evaluator):
            return False, "evaluator digest is missing or malformed"
        evaluator_digests.add(evaluator)
        candidate_author = payload.get("candidate_author")
        evaluator_author = payload.get("evaluator_author")
        if not isinstance(candidate_author, str) or not isinstance(evaluator_author, str):
            return False, "candidate/evaluator authors are missing"
        if candidate_author == evaluator_author:
            return False, "candidate attempts to self-evaluate"
    if len(evaluator_digests) != 1:
        return False, "participants disagree on immutable evaluator digest"
    return True, "evaluator is immutable and candidate/evaluator authors are separate"


def _protected_paths_and_formula(merged: Mapping[str, Any]) -> tuple[bool, str]:
    for payload in _participant_payloads(merged):
        if payload.get("protected_paths_changed") is not False:
            return False, "protected paths were changed or not explicitly proven unchanged"
        formula_commit = payload.get("formula_commit")
        if not isinstance(formula_commit, str) or not FULL_SHA_RE.fullmatch(formula_commit):
            return False, "canonical formula commit is not a full Git SHA"
    return True, "protected paths are unchanged and formula commit is exact"


def _complete_lineage(merged: Mapping[str, Any]) -> tuple[bool, str]:
    for payload in _participant_payloads(merged):
        lineage = payload.get("lineage")
        if not isinstance(lineage, Mapping):
            return False, "orbit lineage is missing"
        for key in ("orbit_id", "parent_digest", "source_revision"):
            if not isinstance(lineage.get(key), str) or not lineage[key]:
                return False, f"lineage {key} is missing"
        if not SHA256_RE.fullmatch(lineage["parent_digest"]):
            return False, "lineage parent_digest is not sha256-bound"
        if not FULL_SHA_RE.fullmatch(lineage["source_revision"]):
            return False, "lineage source_revision is not a full Git SHA"
        sequence = lineage.get("sequence")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
            return False, "lineage sequence is malformed"
    return True, "every participant carries complete source-bound orbit lineage"


def invariant_registry() -> Mapping[tuple[str, str], RegisteredInvariant]:
    specs = (
        _binding(
            "total-provenance",
            _total_provenance,
            source_contract="Every participant has non-empty provenance records with span_id and sha256 digest.",
            golden_vectors=({"provenance": [{"span_id": "s1", "digest": "sha256:" + "0" * 64}]},),
        ),
        _binding(
            "no-unretrieved-citation",
            _citation_retrieval,
            source_contract="citation_span_ids must be a subset of retrieved_span_ids.",
            golden_vectors=({"retrieved_span_ids": ["s1"], "citation_span_ids": ["s1"]},),
        ),
        _binding(
            "canonical-units-money",
            _canonical_units_and_money,
            source_contract="No binary float; money and measurements use integer micros and declared units.",
            golden_vectors=({"amount_micros": 1, "measurements": [{"unit": "ms", "value_micros": 1}]},),
        ),
        _binding(
            "utc-boundaries",
            _utc_boundaries,
            source_contract="Fields ending in _at or timestamp are RFC3339-style UTC values ending in Z.",
            golden_vectors=({"observed_at": "2026-01-01T00:00:00.000Z"},),
        ),
        _binding(
            "scoped-authorization",
            _scoped_authorization,
            source_contract="Each participant carries subject, scope, UTC expiry, and sha256-bound grant.",
            golden_vectors=({"authorization": {"subject": "x", "scope": "read", "expires_at": "2026-01-01T00:00:00.000Z", "grant_digest": "sha256:" + "0" * 64}},),
        ),
        _binding(
            "immutable-evaluator-no-self-certification",
            _evaluator_and_authors,
            source_contract="One immutable evaluator digest; candidate and evaluator authors differ.",
            golden_vectors=({"evaluator_digest": "sha256:" + "0" * 64, "candidate_author": "a", "evaluator_author": "b"},),
        ),
        _binding(
            "protected-paths-canonical-formula",
            _protected_paths_and_formula,
            source_contract="Protected paths unchanged; formula commit is a lowercase full Git SHA.",
            golden_vectors=({"protected_paths_changed": False, "formula_commit": "0" * 40},),
        ),
        _binding(
            "complete-orbit-lineage",
            _complete_lineage,
            source_contract="Orbit lineage binds orbit ID, sequence, parent digest, and source revision.",
            golden_vectors=({"lineage": {"orbit_id": "o", "sequence": 0, "parent_digest": "sha256:" + "0" * 64, "source_revision": "0" * 40}},),
        ),
    )
    return {(item.binding.invariant_id, item.binding.version): item for item in specs}


def baseline_codex() -> CodexManifest:
    registry = invariant_registry()
    return CodexManifest(
        schema=CODEX_SCHEMA,
        codex_id="szl-oro-baseline",
        version="1.0.0",
        invariants=tuple(
            registry[key].binding for key in sorted(registry)
        ),
    )


def role_cells() -> tuple[RoleSpec, ...]:
    return (
        RoleSpec(
            name="scout",
            orbit_kinds=("discovery",),
            tools=("github-read", "gitlab-read", "official-docs-read", "publication-read"),
            mcp_servers=("read-only-sources",),
            handoffs=("architect", "sentinel"),
        ),
        RoleSpec(
            name="architect",
            orbit_kinds=("discovery", "evolution"),
            tools=("repository-read", "design-record-write"),
            mcp_servers=("read-only-sources", "isolated-worktree"),
            handoffs=("builder", "verifier"),
        ),
        RoleSpec(
            name="builder",
            orbit_kinds=("evolution", "task"),
            tools=("isolated-worktree-write", "test-runner"),
            mcp_servers=("isolated-worktree",),
            handoffs=("verifier", "sentinel"),
            may_write_candidate=True,
        ),
        RoleSpec(
            name="verifier",
            orbit_kinds=("evolution", "task"),
            tools=("repository-read", "test-runner", "evidence-write"),
            mcp_servers=("verification",),
            handoffs=("sentinel", "integrator"),
            may_evaluate=True,
        ),
        RoleSpec(
            name="sentinel",
            orbit_kinds=("discovery", "evolution", "task"),
            tools=("policy-read", "security-scan", "evidence-write"),
            mcp_servers=("verification",),
            handoffs=("integrator",),
            may_evaluate=True,
        ),
        RoleSpec(
            name="integrator",
            orbit_kinds=("task",),
            tools=("evidence-read", "approval-write", "pull-request-open"),
            mcp_servers=("protected-delivery",),
            handoffs=(),
            may_approve=True,
        ),
    )


class OROService:
    def __init__(
        self,
        *,
        store: OROStore,
        signer: ReceiptSigner | None,
        production: bool,
    ) -> None:
        self.store = store
        self.production = bool(production)
        self.signer = signer
        self.registry = invariant_registry()
        self.engine = BarrierEngine(
            invariant_registry=self.registry,
            signer=signer,
            production=self.production,
        )

    @property
    def codex(self) -> CodexManifest:
        return baseline_codex()

    def contract(self) -> Mapping[str, Any]:
        return {
            "schema": "szl.oro-runtime-contract/v1",
            "rank_schema": "szl.oro-rank/v1",
            "codex": self.codex.as_dict(),
            "codex_digest": self.codex.digest,
            "orbit_kinds": sorted(ORBIT_KINDS),
            "roles": [asdict(role) for role in role_cells()],
            "release_effector": "ABSENT",
            "normal_termination": "STRUCTURAL_RANK_DECREASE",
            "recursion_limit": "DEFECT_BACKSTOP_ONLY",
            "runtime_enforced": "MEASURED_ONLY_AFTER_PROTECTED_LIVE_READBACK",
            "well_founded_termination": "MODELED",
            "machine_checked_termination": "NOT_PROVED",
            "global_action_optimality": "NOT_CLAIMED",
        }

    def readiness(self) -> Mapping[str, Any]:
        storage = self.store.integrity()
        signer_identity = (
            dict(self.signer.identity)
            if self.signer is not None
            else {"state": "UNAVAILABLE" if self.production else "UNSIGNED_NON_PRODUCTION"}
        )
        signer_ready = self.signer is not None or not self.production
        ready = bool(storage.get("ready")) and signer_ready
        return {
            "ready": ready,
            "state": "READY" if ready else "UNAVAILABLE",
            "production": self.production,
            "storage": storage,
            "signer": signer_identity,
            "codex_digest": self.codex.digest,
            "rank_schema": "szl.oro-rank/v1",
        }

    def create_plan(self, raw: Mapping[str, Any]) -> Mapping[str, Any]:
        if not isinstance(raw, Mapping):
            raise OROContractError("plan must be an object")
        allowed = {
            "plan_id", "orbit_kind", "objective", "rank", "expected_participants",
            "codex", "candidate_author", "evaluator_author", "created_at",
            "requested_effectors", "source_revision", "theorem_binding",
        }
        extra = set(raw) - allowed
        required = allowed - {"requested_effectors", "theorem_binding"}
        missing = required - set(raw)
        if extra:
            raise OROContractError(f"unknown plan fields: {sorted(extra)}")
        if missing:
            raise OROContractError(f"missing plan fields: {sorted(missing)}")
        plan_id = str(raw["plan_id"]).strip()
        if not plan_id or len(plan_id) > 256:
            raise OROContractError("plan_id is missing or too long")
        orbit_kind = str(raw["orbit_kind"]).lower()
        if orbit_kind not in ORBIT_KINDS:
            raise OROContractError("unsupported orbit_kind")
        objective = str(raw["objective"]).strip()
        if not objective or len(objective) > 4096:
            raise OROContractError("objective is missing or too long")
        rank = Rank.parse(raw["rank"])
        participants = raw["expected_participants"]
        if not isinstance(participants, list) or not participants:
            raise OROContractError("expected_participants must be a non-empty array")
        if not all(isinstance(value, str) and value.strip() for value in participants):
            raise OROContractError("participant IDs must be non-empty strings")
        participants = sorted(value.strip() for value in participants)
        if len(participants) != len(set(participants)):
            raise OROContractError("participant IDs must be unique")
        codex = CodexManifest.parse(raw["codex"])
        if codex != self.codex:
            raise OROContractError("plan Codex does not match the admitted local predicate binding")
        candidate_author = str(raw["candidate_author"]).strip()
        evaluator_author = str(raw["evaluator_author"]).strip()
        if not candidate_author or not evaluator_author or candidate_author == evaluator_author:
            raise OROContractError("candidate and evaluator authors must be non-empty and independent")
        parse_utc(raw["created_at"])
        source_revision = str(raw["source_revision"]).lower()
        if not FULL_SHA_RE.fullmatch(source_revision):
            raise OROContractError("source_revision must be a lowercase full Git SHA")
        effectors = raw.get("requested_effectors", [])
        if not isinstance(effectors, list) or not all(isinstance(value, str) for value in effectors):
            raise OROContractError("requested_effectors must be a string array")
        if any(value.lower() in {"release", "merge", "deploy-production", "direct-main"} for value in effectors):
            raise OROContractError("an ORO plan cannot create a release or bypass protected delivery")
        if orbit_kind == "discovery" and effectors:
            raise OROContractError("discovery orbit is read-only")
        theorem_binding = raw.get("theorem_binding")
        if theorem_binding is not None and not isinstance(theorem_binding, Mapping):
            raise OROContractError("theorem_binding must be an object or null")
        admitted: dict[str, Any] = {
            "schema": "szl.oro-plan/v1",
            "plan_id": plan_id,
            "orbit_kind": orbit_kind,
            "objective": objective,
            "rank": rank.as_dict(),
            "expected_participants": participants,
            "codex": codex.as_dict(),
            "candidate_author": candidate_author,
            "evaluator_author": evaluator_author,
            "created_at": raw["created_at"],
            "requested_effectors": sorted(set(effectors)),
            "source_revision": source_revision,
            "theorem_binding": dict(theorem_binding) if theorem_binding is not None else None,
        }
        admitted["plan_digest"] = receipt_digest(admitted)
        return self.store.create_plan(admitted)

    def execute_plan(self, plan_id: str, raw: Mapping[str, Any]) -> Mapping[str, Any]:
        plan = self.store.get_plan(plan_id)
        if plan is None:
            raise OROStateError("plan does not exist")
        body = plan["body"]
        if not isinstance(raw, Mapping):
            raise OROContractError("execution request must be an object")
        allowed = {
            "orbit_id", "barrier_id", "generation", "expires_at", "rank_after",
            "objective_converged", "arrivals", "children", "lineage", "theorem_binding",
        }
        extra = set(raw) - allowed
        required = allowed - {"children", "theorem_binding"}
        missing = required - set(raw)
        if extra:
            raise OROContractError(f"unknown execution fields: {sorted(extra)}")
        if missing:
            raise OROContractError(f"missing execution fields: {sorted(missing)}")
        orbit_id = str(raw["orbit_id"]).strip()
        barrier_id = str(raw["barrier_id"]).strip()
        if not orbit_id or not barrier_id:
            raise OROContractError("orbit_id and barrier_id are required")
        generation = raw["generation"]
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 0:
            raise OROContractError("generation must be a non-negative integer")
        parse_utc(raw["expires_at"])
        if plan["status"] in {"COMPLETE", "REFUSED"}:
            raise OROStateError("plan is terminal and cannot execute another barrier")
        durable_orbit = self.store.get_orbit(orbit_id)
        if durable_orbit is None:
            if generation != 0:
                raise OROStateError("new orbit must begin at generation zero")
            rank_before = Rank.parse(body["rank"])
        else:
            if durable_orbit["plan_id"] != plan_id:
                raise OROStateError("orbit is bound to a different plan")
            if durable_orbit["status"] != "RUNNING":
                raise OROStateError("orbit is terminal and cannot execute another barrier")
            if int(durable_orbit["generation"]) != generation:
                raise OROStateError("execution generation does not match durable orbit generation")
            rank_before = Rank.parse(durable_orbit["current_rank"])
        rank_after = Rank.parse(raw["rank_after"])
        if not isinstance(raw["objective_converged"], bool):
            raise OROContractError("objective_converged must be boolean")
        if not isinstance(raw["arrivals"], list):
            raise OROContractError("arrivals must be an array")
        arrivals = tuple(Arrival.parse(item) for item in raw["arrivals"])
        if not isinstance(raw["lineage"], Mapping):
            raise OROContractError("lineage must be an object")
        theorem_binding = raw.get("theorem_binding", body.get("theorem_binding"))
        if theorem_binding is not None and not isinstance(theorem_binding, Mapping):
            raise OROContractError("theorem_binding must be an object or null")

        allocation_receipt: Mapping[str, Any] | None = None
        children = raw.get("children")
        if children is not None:
            if not isinstance(children, list):
                raise OROContractError("children must be an array")
            parsed_children = tuple(
                Allocation(child_id=item["child_id"], rank=Rank.parse(item["rank"]))
                for item in children
                if isinstance(item, Mapping) and set(item) == {"child_id", "rank"}
            )
            if len(parsed_children) != len(children):
                raise OROContractError("each child must contain exactly child_id and rank")
            allocation_receipt = allocate_rank(rank_before, parsed_children)

        existing_orbit = durable_orbit
        self.store.create_orbit(
            orbit_id=orbit_id,
            plan_id=plan_id,
            generation=generation,
            rank=rank_before,
        )
        if existing_orbit is None:
            intent_body = {
                "schema": "szl.oro-intent-certificate/v1",
                "plan_id": plan_id,
                "plan_digest": body["plan_digest"],
                "orbit_id": orbit_id,
                "generation": generation,
                "source_revision": body["source_revision"],
                "effectors": body["requested_effectors"],
                "release_authority": "ABSENT",
            }
            self.store.create_certificate(
                certificate_id=f"intent:{orbit_id}",
                orbit_id=orbit_id,
                kind="intent",
                body=intent_body,
            )

        try:
            decision = self.engine.evaluate(
                barrier_id=barrier_id,
                orbit_id=orbit_id,
                generation=generation,
                expected_participants=body["expected_participants"],
                arrivals=arrivals,
                expires_at=raw["expires_at"],
                rank_before=rank_before,
                rank_after=rank_after,
                objective_converged=raw["objective_converged"],
                codex=CodexManifest.parse(body["codex"]),
                allocation_receipt=allocation_receipt,
                lineage=raw["lineage"],
                theorem_binding=theorem_binding,
                seen_semantic_hash=lambda digest: self.store.seen_semantic_hash(orbit_id, digest),
            )
        except (OROContractError, OROStateError) as exc:
            self.store.record_negative(
                plan_id=plan_id,
                orbit_id=orbit_id,
                barrier_id=barrier_id,
                reason=str(exc),
                evidence={
                    "schema": "szl.oro-negative-result/v1",
                    "error_class": type(exc).__name__,
                    "request_digest": semantic_hash(raw),
                    "generated_at": utc_now(),
                },
            )
            raise

        durable_arrivals = [
            {
                "participant_id": item.participant_id,
                "payload_digest": item.digest,
                "payload": item.payload,
                "received_at": item.received_at,
            }
            for item in arrivals
        ]
        barrier = self.store.persist_barrier(
            plan_id=plan_id,
            arrivals=durable_arrivals,
            allocation_receipt=allocation_receipt,
            decision=decision,
        )
        if decision.decision in {"COMPLETE", "REFUSE"}:
            kind = "completion" if decision.decision == "COMPLETE" else "refusal"
            certificate_body = {
                "schema": f"szl.oro-{kind}-certificate/v1",
                "plan_id": plan_id,
                "orbit_id": orbit_id,
                "barrier_id": barrier_id,
                "decision": decision.decision,
                "reason": decision.reason,
                "receipt_digest": decision.receipt["receipt_digest"],
                "semantic_hash": decision.semantic_digest,
                "rank_after": rank_after.as_dict(),
                "source_revision": body["source_revision"],
                "release_created": False,
            }
            certificate = self.store.create_certificate(
                certificate_id=f"{kind}:{barrier_id}",
                orbit_id=orbit_id,
                kind=kind,
                body=certificate_body,
            )
        else:
            certificate = None
        if decision.decision == "REFUSE":
            self.store.record_negative(
                plan_id=plan_id,
                orbit_id=orbit_id,
                barrier_id=barrier_id,
                reason=decision.reason,
                evidence={
                    "schema": "szl.oro-negative-result/v1",
                    "receipt_digest": decision.receipt["receipt_digest"],
                    "semantic_hash": decision.semantic_digest,
                    "generated_at": utc_now(),
                },
            )
        return {
            "plan_id": plan_id,
            "orbit": self.store.get_orbit(orbit_id),
            "barrier": barrier,
            "certificate": certificate,
        }
