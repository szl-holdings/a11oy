# SPDX-License-Identifier: Apache-2.0
"""Deterministic ORO rank, Codex, role, and barrier contracts.

Normal termination is structural: every continuing loop-closing barrier must
replace the current rank with a strictly smaller rank. A recursion limit may
still exist in an outer worker as a defect backstop, but it is not the normal
stopping mechanism implemented here.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol, Sequence

RANK_SCHEMA = "szl.oro-rank/v1"
ALLOCATION_SCHEMA = "szl.oro-rank-allocation/v1"
CODEX_SCHEMA = "szl.oro-codex/v1"
BARRIER_SCHEMA = "szl.oro-barrier/v1"
RECEIPT_SCHEMA = "szl.oro-barrier-receipt/v1"
DSSE_PAYLOAD_TYPE = "application/vnd.szl.oro.barrier-receipt.v1+json"
MAX_COMPONENT = (1 << 63) - 1
MAX_ARRIVAL_BYTES = 256 * 1024
SEMANTIC_DOMAIN = b"SZL-ORO-SEMANTIC-v1\x00"
RECEIPT_DOMAIN = b"SZL-ORO-RECEIPT-v1\x00"
ORBIT_KINDS = frozenset({"discovery", "evolution", "task"})
ROLE_NAMES = frozenset({"scout", "architect", "builder", "verifier", "sentinel", "integrator"})


class OROContractError(ValueError):
    """An input violated a closed ORO contract."""


class OROStateError(RuntimeError):
    """A durable-state or transition invariant failed."""


class OROSignerUnavailable(OROStateError):
    """A governed signer required for a production write is unavailable."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise OROContractError("timestamp must be UTC and end in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise OROContractError("invalid UTC timestamp") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise OROContractError("timestamp must be UTC")
    return parsed


def canonical_json(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise OROContractError("value is not canonical-JSON encodable") from exc


def digest_bytes(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def semantic_hash(value: Any) -> str:
    return digest_bytes(SEMANTIC_DOMAIN + canonical_json(value))


def receipt_digest(value: Any) -> str:
    return digest_bytes(RECEIPT_DOMAIN + canonical_json(value))


def _strict_component(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise OROContractError(f"{name} must be an integer, not bool/float")
    if value < 0:
        raise OROContractError(f"{name} must be non-negative")
    if value > MAX_COMPONENT:
        raise OROContractError(f"{name} exceeds signed 64-bit bound")
    return value


def _nonempty(name: str, value: Any, *, maximum: int = 512) -> str:
    if not isinstance(value, str) or not value.strip():
        raise OROContractError(f"{name} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > maximum:
        raise OROContractError(f"{name} exceeds length bound")
    return normalized


def _sha256(name: str, value: Any) -> str:
    text = _nonempty(name, value, maximum=80)
    if len(text) != 71 or not text.startswith("sha256:"):
        raise OROContractError(f"{name} must be a full sha256 digest")
    try:
        int(text[7:], 16)
    except ValueError as exc:
        raise OROContractError(f"{name} is not hexadecimal") from exc
    return text.lower()


@dataclass(frozen=True)
class Rank:
    obligations: int
    evidence_deficits: int
    budget_units: int
    turns: int
    schema: str = RANK_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != RANK_SCHEMA:
            raise OROContractError(f"unsupported rank schema: {self.schema}")
        for name in ("obligations", "evidence_deficits", "budget_units", "turns"):
            _strict_component(name, getattr(self, name))

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> "Rank":
        if not isinstance(value, Mapping):
            raise OROContractError("rank must be an object")
        allowed = {"schema", "obligations", "evidence_deficits", "budget_units", "turns"}
        extra = set(value) - allowed
        missing = {"obligations", "evidence_deficits", "budget_units", "turns"} - set(value)
        if extra:
            raise OROContractError(f"unknown rank fields: {sorted(extra)}")
        if missing:
            raise OROContractError(f"missing rank fields: {sorted(missing)}")
        return cls(
            schema=value.get("schema", RANK_SCHEMA),
            obligations=_strict_component("obligations", value["obligations"]),
            evidence_deficits=_strict_component("evidence_deficits", value["evidence_deficits"]),
            budget_units=_strict_component("budget_units", value["budget_units"]),
            turns=_strict_component("turns", value["turns"]),
        )

    def vector(self) -> tuple[int, int, int, int]:
        return (self.obligations, self.evidence_deficits, self.budget_units, self.turns)

    def strictly_decreases_to(self, other: "Rank") -> bool:
        if not isinstance(other, Rank):
            raise OROContractError("rank comparison requires another Rank")
        return other.vector() < self.vector()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Allocation:
    child_id: str
    rank: Rank

    def __post_init__(self) -> None:
        object.__setattr__(self, "child_id", _nonempty("child_id", self.child_id))
        if not isinstance(self.rank, Rank):
            raise OROContractError("allocation rank must be a Rank")


def allocate_rank(parent: Rank, allocations: Sequence[Allocation]) -> dict[str, Any]:
    """Validate a conservative multiset replacement of one parent rank.

    The parent consumes one control turn before fan-out. Every child must be
    strictly below the parent and aggregate child components may not exceed the
    parent's remaining authority. This is a concrete finite-multiset extension:
    one element is replaced only by finitely many smaller elements.
    """
    if not isinstance(parent, Rank):
        raise OROContractError("parent must be a Rank")
    if not allocations:
        raise OROContractError("fan-out requires at least one child")
    if parent.turns == 0:
        raise OROContractError("parent has no turn available for fan-out")
    ids = [item.child_id for item in allocations]
    if len(ids) != len(set(ids)):
        raise OROContractError("fan-out child IDs must be unique")
    if any(not parent.strictly_decreases_to(item.rank) for item in allocations):
        raise OROContractError("every child rank must be strictly below its parent")

    totals = {
        "obligations": sum(item.rank.obligations for item in allocations),
        "evidence_deficits": sum(item.rank.evidence_deficits for item in allocations),
        "budget_units": sum(item.rank.budget_units for item in allocations),
        "turns": sum(item.rank.turns for item in allocations),
    }
    limits = {
        "obligations": parent.obligations,
        "evidence_deficits": parent.evidence_deficits,
        "budget_units": parent.budget_units,
        "turns": parent.turns - 1,
    }
    violations = sorted(name for name, total in totals.items() if total > limits[name])
    if violations:
        raise OROContractError("fan-out mints authority: " + ", ".join(violations))
    body: dict[str, Any] = {
        "schema": ALLOCATION_SCHEMA,
        "rank_version": RANK_SCHEMA,
        "parent": parent.as_dict(),
        "consumed_parent_turns": 1,
        "children": [
            {"child_id": item.child_id, "rank": item.rank.as_dict()}
            for item in sorted(allocations, key=lambda value: value.child_id)
        ],
        "totals": totals,
        "limits_after_parent_turn": limits,
        "finite_multiset_replacement": True,
        "conserved": True,
    }
    body["digest"] = receipt_digest(body)
    return body


@dataclass(frozen=True)
class RoleSpec:
    name: str
    orbit_kinds: tuple[str, ...]
    tools: tuple[str, ...] = ()
    mcp_servers: tuple[str, ...] = ()
    handoffs: tuple[str, ...] = ()
    may_write_candidate: bool = False
    may_evaluate: bool = False
    may_approve: bool = False
    may_release: bool = False

    def __post_init__(self) -> None:
        name = _nonempty("role name", self.name).lower()
        if name not in ROLE_NAMES:
            raise OROContractError(f"unsupported role: {name}")
        object.__setattr__(self, "name", name)
        kinds = tuple(_nonempty("orbit kind", value).lower() for value in self.orbit_kinds)
        if not kinds or any(value not in ORBIT_KINDS for value in kinds):
            raise OROContractError("role must select supported orbit kinds")
        object.__setattr__(self, "orbit_kinds", kinds)
        for field_name in ("tools", "mcp_servers", "handoffs"):
            values = tuple(_nonempty(field_name, value) for value in getattr(self, field_name))
            if len(values) != len(set(values)):
                raise OROContractError(f"{field_name} entries must be unique")
            object.__setattr__(self, field_name, values)
        if self.may_release:
            raise OROContractError("ORO task roles cannot create a release")
        if self.may_write_candidate and self.may_approve:
            raise OROContractError("a candidate writer cannot approve its own role")
        if self.may_evaluate and self.may_approve:
            raise OROContractError("an evaluator cannot approve its own role")

    def clone(self, **changes: Any) -> "RoleSpec":
        """Deep-replace mutable configuration before constructing a new frozen role."""
        values = copy.deepcopy(asdict(self))
        values.update(copy.deepcopy(changes))
        for key in ("orbit_kinds", "tools", "mcp_servers", "handoffs"):
            if key in values:
                values[key] = tuple(values[key])
        return RoleSpec(**values)


@dataclass(frozen=True)
class InvariantBinding:
    invariant_id: str
    version: str
    source_blob_digest: str
    implementation_digest: str
    input_schema: str
    golden_vectors_digest: str
    blocking: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "invariant_id", _nonempty("invariant_id", self.invariant_id))
        object.__setattr__(self, "version", _nonempty("version", self.version, maximum=64))
        object.__setattr__(self, "source_blob_digest", _sha256("source_blob_digest", self.source_blob_digest))
        object.__setattr__(self, "implementation_digest", _sha256("implementation_digest", self.implementation_digest))
        object.__setattr__(self, "golden_vectors_digest", _sha256("golden_vectors_digest", self.golden_vectors_digest))
        object.__setattr__(self, "input_schema", _nonempty("input_schema", self.input_schema))
        if not isinstance(self.blocking, bool):
            raise OROContractError("blocking must be boolean")

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> "InvariantBinding":
        if not isinstance(value, Mapping):
            raise OROContractError("invariant binding must be an object")
        allowed = {
            "invariant_id", "version", "source_blob_digest", "implementation_digest",
            "input_schema", "golden_vectors_digest", "blocking",
        }
        extra = set(value) - allowed
        required = allowed - {"blocking"}
        missing = required - set(value)
        if extra:
            raise OROContractError(f"unknown invariant fields: {sorted(extra)}")
        if missing:
            raise OROContractError(f"missing invariant fields: {sorted(missing)}")
        return cls(
            invariant_id=value["invariant_id"],
            version=value["version"],
            source_blob_digest=value["source_blob_digest"],
            implementation_digest=value["implementation_digest"],
            input_schema=value["input_schema"],
            golden_vectors_digest=value["golden_vectors_digest"],
            blocking=value.get("blocking", True),
        )

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CodexManifest:
    codex_id: str
    version: str
    invariants: tuple[InvariantBinding, ...]
    schema: str = CODEX_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != CODEX_SCHEMA:
            raise OROContractError(f"unsupported Codex schema: {self.schema}")
        object.__setattr__(self, "codex_id", _nonempty("codex_id", self.codex_id))
        object.__setattr__(self, "version", _nonempty("Codex version", self.version, maximum=64))
        if not self.invariants:
            raise OROContractError("Codex must select at least one invariant")
        keys = [(item.invariant_id, item.version) for item in self.invariants]
        if len(keys) != len(set(keys)):
            raise OROContractError("Codex invariant selections must be unique")

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> "CodexManifest":
        if not isinstance(value, Mapping):
            raise OROContractError("Codex must be an object")
        allowed = {"schema", "codex_id", "version", "invariants"}
        extra = set(value) - allowed
        if extra:
            raise OROContractError(f"Codex contains non-data or unknown fields: {sorted(extra)}")
        if any(name not in value for name in ("codex_id", "version", "invariants")):
            raise OROContractError("Codex identity, version, and invariants are required")
        raw = value["invariants"]
        if not isinstance(raw, list):
            raise OROContractError("Codex invariants must be an array")
        return cls(
            schema=value.get("schema", CODEX_SCHEMA),
            codex_id=value["codex_id"],
            version=value["version"],
            invariants=tuple(InvariantBinding.parse(item) for item in raw),
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "codex_id": self.codex_id,
            "version": self.version,
            "invariants": [item.as_dict() for item in self.invariants],
        }

    @property
    def digest(self) -> str:
        return receipt_digest(self.as_dict())


InvariantEvaluator = Callable[[Mapping[str, Any]], tuple[bool, str]]


@dataclass(frozen=True)
class RegisteredInvariant:
    binding: InvariantBinding
    evaluator: InvariantEvaluator = field(compare=False, repr=False)


@dataclass(frozen=True)
class Arrival:
    participant_id: str
    generation: int
    payload: Mapping[str, Any]
    received_at: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "participant_id", _nonempty("participant_id", self.participant_id))
        _strict_component("generation", self.generation)
        if not isinstance(self.payload, Mapping):
            raise OROContractError("arrival payload must be an object")
        if len(canonical_json(self.payload)) > MAX_ARRIVAL_BYTES:
            raise OROContractError("arrival payload exceeds response-size bound")
        parse_utc(self.received_at)

    @property
    def digest(self) -> str:
        return semantic_hash(self.payload)

    @classmethod
    def parse(cls, value: Mapping[str, Any]) -> "Arrival":
        if not isinstance(value, Mapping):
            raise OROContractError("arrival must be an object")
        allowed = {"participant_id", "generation", "payload", "received_at"}
        extra = set(value) - allowed
        missing = allowed - set(value)
        if extra:
            raise OROContractError(f"unknown arrival fields: {sorted(extra)}")
        if missing:
            raise OROContractError(f"missing arrival fields: {sorted(missing)}")
        return cls(
            participant_id=value["participant_id"],
            generation=value["generation"],
            payload=value["payload"],
            received_at=value["received_at"],
        )


class ReceiptSigner(Protocol):
    @property
    def identity(self) -> Mapping[str, Any]: ...

    def sign(self, payload_type: str, payload: bytes) -> Mapping[str, Any]: ...


@dataclass(frozen=True)
class BarrierDecision:
    barrier_id: str
    orbit_id: str
    generation: int
    decision: str
    reason: str
    semantic_digest: str
    rank_before: Rank
    rank_after: Rank
    objective_converged: bool
    invariant_results: tuple[Mapping[str, Any], ...]
    receipt: Mapping[str, Any]
    envelope: Mapping[str, Any]

    def __post_init__(self) -> None:
        if self.decision not in {"CONTINUE", "COMPLETE", "REFUSE"}:
            raise OROContractError("unsupported barrier decision")


class BarrierEngine:
    """Evaluate one loop-closing barrier after reducers have merged."""

    def __init__(
        self,
        *,
        invariant_registry: Mapping[tuple[str, str], RegisteredInvariant],
        signer: ReceiptSigner | None,
        production: bool,
    ) -> None:
        self._registry = dict(invariant_registry)
        self._signer = signer
        self.production = bool(production)
        if self.production and signer is None:
            raise OROSignerUnavailable("production ORO requires a governed signer")

    def _deduplicate(
        self,
        arrivals: Sequence[Arrival],
        *,
        expected_participants: frozenset[str],
        generation: int,
        expires_at: datetime,
        evaluated_at: datetime,
    ) -> tuple[Arrival, ...]:
        by_id: dict[str, Arrival] = {}
        for arrival in arrivals:
            if arrival.participant_id not in expected_participants:
                raise OROContractError(f"unexpected participant: {arrival.participant_id}")
            if arrival.generation != generation:
                raise OROContractError("arrival generation does not match barrier generation")
            received_at = parse_utc(arrival.received_at)
            if received_at > evaluated_at:
                raise OROContractError("arrival was received after barrier evaluation")
            if received_at > expires_at:
                raise OROContractError("arrival was received after absolute barrier TTL")
            previous = by_id.get(arrival.participant_id)
            if previous is not None and previous.digest != arrival.digest:
                raise OROContractError("conflicting duplicate arrival")
            by_id[arrival.participant_id] = previous or arrival
        missing = sorted(expected_participants - set(by_id))
        if missing:
            raise OROContractError(f"barrier is missing participants: {missing}")
        return tuple(by_id[key] for key in sorted(by_id))

    def _evaluate_invariants(
        self,
        codex: CodexManifest,
        merged_payload: Mapping[str, Any],
    ) -> tuple[Mapping[str, Any], ...]:
        results: list[Mapping[str, Any]] = []
        for selected in codex.invariants:
            registered = self._registry.get((selected.invariant_id, selected.version))
            if registered is None:
                raise OROStateError(
                    f"Codex selects unregistered invariant {selected.invariant_id}@{selected.version}"
                )
            if registered.binding != selected:
                raise OROStateError(
                    f"registered invariant binding drift: {selected.invariant_id}@{selected.version}"
                )
            passed, detail = registered.evaluator(merged_payload)
            if not isinstance(passed, bool) or not isinstance(detail, str):
                raise OROStateError("invariant evaluator returned a malformed result")
            results.append(
                {
                    **selected.as_dict(),
                    "passed": passed,
                    "detail": detail[:2048],
                }
            )
        return tuple(results)

    def evaluate(
        self,
        *,
        barrier_id: str,
        orbit_id: str,
        generation: int,
        expected_participants: Sequence[str],
        arrivals: Sequence[Arrival],
        expires_at: str,
        rank_before: Rank,
        rank_after: Rank,
        objective_converged: bool,
        codex: CodexManifest,
        allocation_receipt: Mapping[str, Any] | None,
        lineage: Mapping[str, Any],
        theorem_binding: Mapping[str, Any] | None,
        seen_semantic_hash: Callable[[str], bool],
        now: str | None = None,
    ) -> BarrierDecision:
        barrier_id = _nonempty("barrier_id", barrier_id)
        orbit_id = _nonempty("orbit_id", orbit_id)
        generation = _strict_component("generation", generation)
        if not isinstance(objective_converged, bool):
            raise OROContractError("objective_converged must be boolean")
        if not isinstance(lineage, Mapping):
            raise OROContractError("lineage must be an object")
        if theorem_binding is not None and not isinstance(theorem_binding, Mapping):
            raise OROContractError("theorem_binding must be an object or null")
        participants = frozenset(_nonempty("participant", value) for value in expected_participants)
        if not participants:
            raise OROContractError("barrier requires expected participants")
        if len(participants) != len(tuple(expected_participants)):
            raise OROContractError("expected participant IDs must be unique")
        expiry = parse_utc(expires_at)
        evaluation_time = now or utc_now()
        observed_now = parse_utc(evaluation_time)
        if observed_now > expiry:
            raise OROContractError("absolute barrier TTL has expired")

        unique = self._deduplicate(
            arrivals,
            expected_participants=participants,
            generation=generation,
            expires_at=expiry,
            evaluated_at=observed_now,
        )
        merged_payload: Mapping[str, Any] = {
            "schema": BARRIER_SCHEMA,
            "orbit_id": orbit_id,
            "generation": generation,
            "evaluated_at": evaluation_time,
            "participants": [
                {
                    "participant_id": arrival.participant_id,
                    "payload": arrival.payload,
                    "payload_digest": arrival.digest,
                    "received_at": arrival.received_at,
                }
                for arrival in unique
            ],
        }
        semantic_payload = {
            "schema": "szl.oro-semantic-state/v1",
            "participants": [
                {
                    "participant_id": arrival.participant_id,
                    "payload": arrival.payload,
                    "payload_digest": arrival.digest,
                }
                for arrival in unique
            ],
        }
        digest = semantic_hash(semantic_payload)
        if seen_semantic_hash(digest):
            invariant_results: tuple[Mapping[str, Any], ...] = ()
            decision = "REFUSE"
            reason = "semantic cycle detected"
        else:
            invariant_results = self._evaluate_invariants(codex, merged_payload)
            failed = [
                item["invariant_id"]
                for item in invariant_results
                if item["blocking"] and not item["passed"]
            ]
            if failed:
                decision = "REFUSE"
                reason = "blocking invariants failed: " + ", ".join(sorted(failed))
            elif objective_converged:
                decision = "COMPLETE"
                reason = "objective convergence declared and all blocking invariants passed"
            elif not rank_before.strictly_decreases_to(rank_after):
                decision = "REFUSE"
                reason = "rank did not strictly decrease at the loop-closing barrier"
            else:
                decision = "CONTINUE"
                reason = "rank strictly decreased and all blocking invariants passed"

        receipt_body: dict[str, Any] = {
            "schema": RECEIPT_SCHEMA,
            "barrier_id": barrier_id,
            "orbit_id": orbit_id,
            "generation": generation,
            "generated_at": evaluation_time,
            "expires_at": expires_at,
            "decision": decision,
            "reason": reason,
            "semantic_hash": digest,
            "rank_before": rank_before.as_dict(),
            "rank_after": rank_after.as_dict(),
            "rank_version": RANK_SCHEMA,
            "objective_converged": objective_converged,
            "codex": codex.as_dict(),
            "codex_digest": codex.digest,
            "allocation_receipt": allocation_receipt,
            "lineage": dict(lineage),
            "theorem_binding": dict(theorem_binding) if theorem_binding is not None else None,
            "invariant_results": list(invariant_results),
            "participants": [
                {"participant_id": item.participant_id, "arrival_digest": item.digest}
                for item in unique
            ],
            "derived_descendants_valid": decision != "REFUSE",
        }
        receipt_body["receipt_digest"] = receipt_digest(receipt_body)
        payload = canonical_json(receipt_body)
        if self._signer is None:
            envelope: Mapping[str, Any] = {
                "payloadType": DSSE_PAYLOAD_TYPE,
                "payload": base64.b64encode(payload).decode("ascii"),
                "signatures": [],
                "signer": {"state": "UNSIGNED_NON_PRODUCTION"},
            }
        else:
            envelope = self._signer.sign(DSSE_PAYLOAD_TYPE, payload)
            if not isinstance(envelope, Mapping) or not envelope.get("signatures"):
                raise OROStateError("governed signer returned no DSSE signature")
        return BarrierDecision(
            barrier_id=barrier_id,
            orbit_id=orbit_id,
            generation=generation,
            decision=decision,
            reason=reason,
            semantic_digest=digest,
            rank_before=rank_before,
            rank_after=rank_after,
            objective_converged=objective_converged,
            invariant_results=invariant_results,
            receipt=receipt_body,
            envelope=envelope,
        )
