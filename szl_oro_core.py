# SPDX-License-Identifier: Apache-2.0
"""ORO core: deterministic obligation-ranked orbit governance.

This module is pure control-plane logic. It owns rank validation, conserved
fan-out, semantic hashing, barrier decisions, and the durable SQLite evidence
ledger. It does not perform network calls or external mutations.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

RANK_SCHEMA = "szl.oro-rank/v1"
BARRIER_SCHEMA = "szl.oro-barrier/v1"
RECEIPT_SCHEMA = "szl.oro-barrier-receipt/v1"
MAX_COMPONENT = (1 << 63) - 1
MAX_RESPONSE_BYTES = 256 * 1024
SEMANTIC_DOMAIN = b"SZL-ORO-SEMANTIC-v1\x00"


class OROContractError(ValueError):
    """Input violated an ORO closed contract."""


class OROStateError(RuntimeError):
    """Durable-state or transition invariant failed."""


class OROSignerUnavailable(OROStateError):
    """A governed signer required for a production write was unavailable."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_digest(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def semantic_hash(value: Any) -> str:
    return sha256_digest(SEMANTIC_DOMAIN + canonical_json(value))


def _strict_component(name: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise OROContractError(f"{name} must be an integer, not bool/float")
    if value < 0:
        raise OROContractError(f"{name} must be non-negative")
    if value > MAX_COMPONENT:
        raise OROContractError(f"{name} exceeds signed 64-bit bound")
    return value


@dataclass(frozen=True, order=True)
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
        if extra:
            raise OROContractError(f"unknown rank fields: {sorted(extra)}")
        return cls(
            schema=value.get("schema", RANK_SCHEMA),
            obligations=_strict_component("obligations", value.get("obligations")),
            evidence_deficits=_strict_component("evidence_deficits", value.get("evidence_deficits")),
            budget_units=_strict_component("budget_units", value.get("budget_units")),
            turns=_strict_component("turns", value.get("turns")),
        )

    def vector(self) -> tuple[int, int, int, int]:
        return (self.obligations, self.evidence_deficits, self.budget_units, self.turns)

    def strictly_decreases_to(self, other: "Rank") -> bool:
        return other.vector() < self.vector()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Allocation:
    child_id: str
    rank: Rank

    def __post_init__(self) -> None:
        if not isinstance(self.child_id, str) or not self.child_id.strip():
            raise OROContractError("child_id must be a non-empty string")


def validate_conserved_fanout(parent: Rank, allocations: Sequence[Allocation]) -> dict[str, Any]:
    if not allocations:
        raise OROContractError("fan-out requires at least one child")
    child_ids = [item.child_id for item in allocations]
    if len(set(child_ids)) != len(child_ids):
        raise OROContractError("fan-out child IDs must be unique")
    if parent.turns == 0:
        raise OROContractError("parent has no control turn available for fan-out")

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
    violations = [name for name, total in totals.items() if total > limits[name]]
    if violations:
        raise OROContractError(
            "fan-out mints rank authority: " + ", ".join(sorted(violations))
        )
    receipt = {
        "schema": "szl.oro-rank-allocation/v1",
        "parent": parent.as_dict(),
        "consumed_parent_turns": 1,
        "children": [
            {"child_id": item.child_id, "rank": item.rank.as_dict()} for item in allocations
        ],
        "totals": totals,
        "limits_after_parent_turn": limits,
        "conserved": True,
    }
    receipt["digest"] = semantic_hash(receipt)
    return receipt


@dataclass(frozen=True)
class InvariantSpec:
    invariant_id: str
    version: str
    source_blob_digest: str
    implementation_digest: str
    input_schema: str
    golden_vectors_digest: str
    evaluator: Callable[[Mapping[str, Any]], tuple[bool, str]]

    def __post_init__(self) -> None:
        for name in (
            "invariant_id",
            "version",
            "source_blob_digest",
            "implementation_digest",
            "input_schema",
            "golden_vectors_digest",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise OROContractError(f"{name} must be non-empty")
        for digest_name in ("source_blob_digest", "implementation_digest", "golden_vectors_digest"):
            if not getattr(self, digest_name).startswith("sha256:"):
                raise OROContractError(f"{digest_name} must be sha256-bound")


@dataclass(frozen=True)
class Arrival:
    participant_id: str
    generation: int
    payload: Mapping[str, Any]
    received_at: str

    def __post_init__(self) -> None:
        if not self.participant_id:
            raise OROContractError("participant_id is required")
        _strict_component("generation", self.generation)
        if not isinstance(self.payload, Mapping):
            raise OROContractError("arrival payload must be an object")
        if len(canonical_json(self.payload)) > MAX_RESPONSE_BYTES:
            raise OROContractError("arrival payload exceeds response-size bound")
        _parse_utc(self.received_at)

    @property
    def digest(self) -> str:
        return semantic_hash(self.payload)


def _parse_utc(value: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise OROContractError("timestamp must be UTC and end in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise OROContractError("invalid UTC timestamp") from exc
    if parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
        raise OROContractError("timestamp must be UTC")
    return parsed


class OROStore:
    """Strict SQLite evidence store for the first ORO release."""

    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(str(self.path))
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    def close(self) -> None:
        self.connection.close()

    def _migrate(self) -> None:
        version = int(self.connection.execute("PRAGMA user_version").fetchone()[0])
        if version not in (0, self.SCHEMA_VERSION):
            raise OROStateError(f"unsupported ORO database schema version: {version}")
        if version == 0:
            self.connection.executescript(
                """
                CREATE TABLE orbit_runs (
                    orbit_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    generation INTEGER NOT NULL CHECK(generation >= 0),
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    candidate_author TEXT NOT NULL,
                    evaluator_author TEXT NOT NULL
                ) STRICT;
                CREATE TABLE barriers (
                    barrier_id TEXT PRIMARY KEY,
                    orbit_id TEXT NOT NULL REFERENCES orbit_runs(orbit_id),
                    generation INTEGER NOT NULL CHECK(generation >= 0),
                    rank_before_json TEXT NOT NULL,
                    rank_after_json TEXT NOT NULL,
                    semantic_hash TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    receipt_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                ) STRICT;
                CREATE TABLE rank_allocations (
                    allocation_digest TEXT PRIMARY KEY,
                    orbit_id TEXT NOT NULL REFERENCES orbit_runs(orbit_id),
                    receipt_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                ) STRICT;
                CREATE TABLE invariant_results (
                    barrier_id TEXT NOT NULL REFERENCES barriers(barrier_id),
                    invariant_id TEXT NOT NULL,
                    version TEXT NOT NULL,
                    passed INTEGER NOT NULL CHECK(passed IN (0, 1)),
                    detail TEXT NOT NULL,
                    implementation_digest TEXT NOT NULL,
                    PRIMARY KEY (barrier_id, invariant_id)
                ) STRICT;
                CREATE TABLE semantic_hashes (
                    orbit_id TEXT NOT NULL REFERENCES orbit_runs(orbit_id),
                    semantic_hash TEXT NOT NULL,
                    generation INTEGER NOT NULL CHECK(generation >= 0),
                    PRIMARY KEY (orbit_id, semantic_hash)
                ) STRICT;
                CREATE TABLE negative_results (
                    id INTEGER PRIMARY KEY,
                    orbit_id TEXT NOT NULL REFERENCES orbit_runs(orbit_id),
                    barrier_id TEXT,
                    reason TEXT NOT NULL,
                    evidence_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                ) STRICT;
                CREATE TABLE approvals (
                    barrier_id TEXT NOT NULL REFERENCES barriers(barrier_id),
                    approver TEXT NOT NULL,
                    approval_digest TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (barrier_id, approver)
                ) STRICT;
                CREATE TABLE certificates (
                    certificate_id TEXT PRIMARY KEY,
                    orbit_id TEXT NOT NULL REFERENCES orbit_runs(orbit_id),
                    kind TEXT NOT NULL CHECK(kind IN ('completion','refusal','intent')),
                    body_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                ) STRICT;
                PRAGMA user_version=1;
                """
            )
            self.connection.commit()

    def create_orbit(
        self,
        *,
        orbit_id: str,
        plan_id: str,
        generation: int,
        candidate_author: str,
        evaluator_author: str,
    ) -> None:
        if not orbit_id or not plan_id or not candidate_author or not evaluator_author:
            raise OROContractError("orbit identity and author fields are required")
        _strict_component("generation", generation)
        if candidate_author == evaluator_author:
            raise OROContractError("candidate and evaluator authors must be independent")
        try:
            self.connection.execute(
                "INSERT INTO orbit_runs VALUES (?, ?, ?, ?, ?, ?, ?)",
                (orbit_id, plan_id, generation, "RUNNING", utc_now(), candidate_author, evaluator_author),
            )
            self.connection.commit()
        except sqlite3.IntegrityError as exc:
            raise OROStateError(f"orbit already exists or violates storage contract: {orbit_id}") from exc

    def orbit(self, orbit_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM orbit_runs WHERE orbit_id=?", (orbit_id,)
        ).fetchone()
        return dict(row) if row else None

    def has_semantic_hash(self, orbit_id: str, digest: str) -> bool:
        row = self.connection.execute(
            "SELECT 1 FROM semantic_hashes WHERE orbit_id=? AND semantic_hash=?",
            (orbit_id, digest),
        ).fetchone()
        return row is not None

    def record_allocation(self, orbit_id: str, receipt: Mapping[str, Any]) -> None:
        digest = str(receipt.get("digest", ""))
        self.connection.execute(
            "INSERT OR IGNORE INTO rank_allocations VALUES (?, ?, ?, ?)",
            (digest, orbit_id, canonical_json(receipt).decode("utf-8"), utc_now()),
        )
        self.connection.commit()

    def record_barrier(
        self,
        *,
        barrier_id: str,
        orbit_id: str,
        generation: int,
        rank_before: Rank,
        rank_after: Rank,
        digest: str,
        decision: str,
        reason: str,
        receipt: Mapping[str, Any],
        invariant_results: Sequence[Mapping[str, Any]],
    ) -> None:
        with self.connection:
            self.connection.execute(
                "INSERT INTO barriers VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    barrier_id,
                    orbit_id,
                    generation,
                    canonical_json(rank_before.as_dict()).decode("utf-8"),
                    canonical_json(rank_after.as_dict()).decode("utf-8"),
                    digest,
                    decision,
                    reason,
                    canonical_json(receipt).decode("utf-8"),
                    utc_now(),
                ),
            )
            self.connection.execute(
                "INSERT INTO semantic_hashes VALUES (?, ?, ?)",
                (orbit_id, digest, generation),
            )
            for item in invariant_results:
                self.connection.execute(
                    "INSERT INTO invariant_results VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        barrier_id,
                        item["invariant_id"],
                        item["version"],
                        1 if item["passed"] else 0,
                        item["detail"],
                        item["implementation_digest"],
                    ),
                )

    def record_negative(self, orbit_id: str, reason: str, evidence: Mapping[str, Any], barrier_id: str | None = None) -> None:
        self.connection.execute(
            "INSERT INTO negative_results(orbit_id, barrier_id, reason, evidence_json, created_at) VALUES (?, ?, ?, ?, ?)",
            (orbit_id, barrier_id, reason, canonical_json(evidence).decode("utf-8"), utc_now()),
        )
        self.connection.commit()

    def approve(self, barrier_id: str, approver: str, approval: Mapping[str, Any]) -> str:
        row = self.connection.execute(
            """SELECT o.candidate_author, o.evaluator_author
               FROM barriers b JOIN orbit_runs o ON o.orbit_id=b.orbit_id
               WHERE b.barrier_id=?""",
            (barrier_id,),
        ).fetchone()
        if row is None:
            raise OROStateError("barrier does not exist")
        if approver in {row["candidate_author"], row["evaluator_author"]}:
            raise OROContractError("approver must be independent of candidate and evaluator authors")
        digest = semantic_hash(approval)
        self.connection.execute(
            "INSERT OR IGNORE INTO approvals VALUES (?, ?, ?, ?)",
            (barrier_id, approver, digest, utc_now()),
        )
        self.connection.commit()
        return digest

    def barrier(self, barrier_id: str) -> dict[str, Any] | None:
        row = self.connection.execute(
            "SELECT * FROM barriers WHERE barrier_id=?", (barrier_id,)
        ).fetchone()
        return dict(row) if row else None


class BarrierEngine:
    def __init__(
        self,
        *,
        store: OROStore,
        invariants: Sequence[InvariantSpec],
        signer: Callable[[bytes], Mapping[str, Any]] | None = None,
        production: bool = False,
    ) -> None:
        self.store = store
        self.invariants = tuple(invariants)
        ids = [item.invariant_id for item in self.invariants]
        if len(ids) != len(set(ids)):
            raise OROContractError("invariant IDs must be unique")
        self.signer = signer
        self.production = production
        if production and signer is None:
            raise OROSignerUnavailable("production ORO requires a governed signer")

    def evaluate(
        self,
        *,
        barrier_id: str,
        orbit_id: str,
        generation: int,
        expected_participants: Iterable[str],
        arrivals: Sequence[Arrival],
        rank_before: Rank,
        rank_after: Rank,
        objective_converged: bool,
        expires_at: str,
        theorem_binding: Mapping[str, Any],
    ) -> dict[str, Any]:
        orbit = self.store.orbit(orbit_id)
        if orbit is None:
            raise OROStateError("orbit does not exist")
        if generation != orbit["generation"]:
            raise OROContractError("barrier generation does not match orbit generation")
        expiry = _parse_utc(expires_at)
        if datetime.now(timezone.utc) > expiry:
            raise OROContractError("barrier TTL expired")

        expected = set(expected_participants)
        if not expected:
            raise OROContractError("barrier participant set must be non-empty")
        by_participant: dict[str, Arrival] = {}
        for arrival in arrivals:
            if arrival.generation != generation:
                raise OROContractError("arrival generation mismatch")
            if arrival.participant_id not in expected:
                raise OROContractError("arrival participant is not a barrier member")
            prior = by_participant.get(arrival.participant_id)
            if prior is not None and prior.digest != arrival.digest:
                raise OROContractError("conflicting duplicate barrier arrival")
            by_participant[arrival.participant_id] = arrival
        missing = sorted(expected - set(by_participant))
        if missing:
            raise OROContractError(f"missing barrier participants: {missing}")

        merged = {
            participant: by_participant[participant].payload
            for participant in sorted(by_participant)
        }
        digest = semantic_hash({"generation": generation, "merged": merged})
        if self.store.has_semantic_hash(orbit_id, digest):
            self.store.record_negative(
                orbit_id,
                "semantic cycle detected",
                {"semantic_hash": digest, "generation": generation},
            )
            raise OROStateError("semantic cycle detected")

        invariant_results: list[dict[str, Any]] = []
        for spec in self.invariants:
            passed, detail = spec.evaluator(merged)
            invariant_results.append(
                {
                    "invariant_id": spec.invariant_id,
                    "version": spec.version,
                    "passed": bool(passed),
                    "detail": str(detail),
                    "source_blob_digest": spec.source_blob_digest,
                    "implementation_digest": spec.implementation_digest,
                    "input_schema": spec.input_schema,
                    "golden_vectors_digest": spec.golden_vectors_digest,
                }
            )

        failing = [item["invariant_id"] for item in invariant_results if not item["passed"]]
        rank_ok = objective_converged or rank_before.strictly_decreases_to(rank_after)
        if failing:
            decision = "HALT"
            reason = "blocking invariant failure: " + ", ".join(failing)
        elif not rank_ok:
            decision = "HALT"
            reason = "rank did not strictly decrease"
        elif objective_converged:
            decision = "COMPLETE"
            reason = "objective convergence declared with blocking invariants satisfied"
        else:
            decision = "CONTINUE"
            reason = "blocking invariants satisfied and rank strictly decreased"

        payload = {
            "schema": RECEIPT_SCHEMA,
            "barrier_id": barrier_id,
            "orbit_id": orbit_id,
            "generation": generation,
            "semantic_hash": digest,
            "rank_before": rank_before.as_dict(),
            "rank_after": rank_after.as_dict(),
            "rank_decreased": rank_before.strictly_decreases_to(rank_after),
            "objective_converged": bool(objective_converged),
            "decision": decision,
            "reason": reason,
            "invariants": invariant_results,
            "theorem_binding": dict(theorem_binding),
            "created_at": utc_now(),
        }
        payload_bytes = canonical_json(payload)
        if self.signer is None:
            signed = {
                "mode": "PROPOSAL_ONLY",
                "payload_digest": sha256_digest(payload_bytes),
                "signature": None,
            }
        else:
            signed = dict(self.signer(payload_bytes))
            if not signed:
                raise OROSignerUnavailable("governed signer returned no receipt")
        receipt = {**payload, "signature_envelope": signed}

        self.store.record_barrier(
            barrier_id=barrier_id,
            orbit_id=orbit_id,
            generation=generation,
            rank_before=rank_before,
            rank_after=rank_after,
            digest=digest,
            decision=decision,
            reason=reason,
            receipt=receipt,
            invariant_results=invariant_results,
        )
        if decision == "HALT":
            self.store.record_negative(
                orbit_id,
                reason,
                {"barrier_id": barrier_id, "semantic_hash": digest, "invariants": invariant_results},
                barrier_id=barrier_id,
            )
        return receipt
