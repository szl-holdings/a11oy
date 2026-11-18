#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Obligation graphs and three-valued evaluation: PROVEN, REFUTED, UNRESOLVED.

A decision (for example, admitting a model for deployment) is decomposed into
obligations: the questions whose answers the decision depends on. The engine
never answers a question with a guess. Each obligation gets exactly one of
three verdicts, and UNRESOLVED always carries the information needed to see
what would resolve it.
"""

from __future__ import annotations

from dataclasses import dataclass

from .records import STANCE_REFUTES, STANCE_SUPPORTS, WitnessTier, check_record, parse_instant

VERDICT_PROVEN = "PROVEN"
VERDICT_REFUTED = "REFUTED"
VERDICT_UNRESOLVED = "UNRESOLVED"
ALL_VERDICTS = frozenset({VERDICT_PROVEN, VERDICT_REFUTED, VERDICT_UNRESOLVED})


class GraphInvalid(ValueError):
    """The obligation graph itself is malformed; evaluation is refused."""


@dataclass(frozen=True)
class Obligation:
    """One question the decision depends on, with its evidence requirements."""

    obligation_id: str
    question: str
    required_tier: str
    freshness_seconds: int | None = None
    blocking: bool = True
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class ObligationGraph:
    """A decision decomposed into validated, dependency-ordered obligations."""

    decision_id: str
    decision_statement: str
    decision_value: float
    obligations: tuple[Obligation, ...]

    def __post_init__(self) -> None:
        if not self.obligations:
            raise GraphInvalid("obligation graph must contain at least one obligation")
        ids = [item.obligation_id for item in self.obligations]
        if len(ids) != len(set(ids)):
            raise GraphInvalid("obligation ids must be unique")
        known = set(ids)
        for item in self.obligations:
            if item.required_tier not in WitnessTier.__members__:
                raise GraphInvalid(f"unknown required tier {item.required_tier!r}")
            for dep in item.depends_on:
                if dep not in known:
                    raise GraphInvalid(
                        f"obligation {item.obligation_id} depends on unknown {dep!r}"
                    )
        self._assert_acyclic()

    def _assert_acyclic(self) -> None:
        visiting: set[str] = set()
        done: set[str] = set()

        def visit(node: str) -> None:
            if node in done:
                return
            if node in visiting:
                raise GraphInvalid("obligation dependency cycle detected")
            visiting.add(node)
            obligation = self.obligation_by_id(node)
            for dep in obligation.depends_on:
                visit(dep)
            visiting.discard(node)
            done.add(node)

        for item in self.obligations:
            visit(item.obligation_id)

    def obligation_by_id(self, obligation_id: str) -> Obligation:
        for item in self.obligations:
            if item.obligation_id == obligation_id:
                return item
        raise GraphInvalid(f"unknown obligation {obligation_id!r}")

    def topological_order(self) -> tuple[str, ...]:
        """Kahn ordering so dependencies are always evaluated before dependents."""
        remaining = {item.obligation_id: set(item.depends_on) for item in self.obligations}
        order: list[str] = []
        while remaining:
            ready = sorted(name for name, deps in remaining.items() if not deps)
            if not ready:
                raise GraphInvalid("obligation dependency cycle detected")
            for name in ready:
                order.append(name)
                del remaining[name]
            for deps in remaining.values():
                deps.difference_update(ready)
        return tuple(order)


@dataclass(frozen=True)
class ObligationVerdict:
    """The three-valued answer for one obligation, with its receipts."""

    obligation_id: str
    question: str
    verdict: str
    blocking: bool
    supporting_records: tuple[str, ...]
    refuting_records: tuple[str, ...]
    notes: tuple[str, ...]


@dataclass(frozen=True)
class Evaluation:
    """Full evaluation of one decision against one evidence bundle."""

    decision_id: str
    decision_statement: str
    decision_value: float
    evaluated_at: str
    verdicts: dict[str, ObligationVerdict]
    anomalies: tuple[str, ...]

    def blocking_unresolved(self) -> tuple[str, ...]:
        return tuple(
            item.obligation_id
            for item in self.verdicts.values()
            if item.blocking and item.verdict != VERDICT_PROVEN
        )

    def refuted(self) -> tuple[str, ...]:
        return tuple(
            item.obligation_id for item in self.verdicts.values() if item.verdict == VERDICT_REFUTED
        )


def evaluate(graph: ObligationGraph, records, policy, evaluated_at: str) -> Evaluation:
    """Evaluate every obligation with fail-closed, dependency-aware semantics.

    Rules, in order of precedence:
    1. An inadmissible record influences nothing; every rejection is noted.
    2. One admissible refuter makes the obligation REFUTED, even if supporters
       also exist. Evidence against a claim outweighs evidence for it.
    3. PROVEN requires at least one admissible supporter AND every dependency
       PROVEN. Anything else is UNRESOLVED, never a guess.
    """
    anomalies: list[str] = []
    by_obligation: dict[str, list] = {item.obligation_id: [] for item in graph.obligations}
    seen_ids: set[str] = set()
    for record in records:
        if record.record_id in seen_ids:
            anomalies.append(f"duplicate record id {record.record_id}; ignoring later copies")
            continue
        seen_ids.add(record.record_id)
        if record.obligation_id in by_obligation:
            by_obligation[record.obligation_id].append(record)
        else:
            anomalies.append(
                f"record {record.record_id} names unknown obligation "
                f"{record.obligation_id!r}; ignored"
            )

    verdicts: dict[str, ObligationVerdict] = {}
    for obligation_id in graph.topological_order():
        obligation = graph.obligation_by_id(obligation_id)
        notes: list[str] = []
        supporters: list[str] = []
        refuters: list[str] = []
        for record in by_obligation[obligation_id]:
            check = check_record(
                record,
                required_tier=WitnessTier[obligation.required_tier],
                freshness_seconds=obligation.freshness_seconds,
                evaluated_at=evaluated_at,
                policy=policy,
            )
            notes.extend(check.notes)
            if not check.admissible:
                continue
            if record.stance == STANCE_REFUTES:
                refuters.append(record.record_id)
            elif record.stance == STANCE_SUPPORTS:
                supporters.append(record.record_id)

        unresolved_deps = [
            dep for dep in obligation.depends_on if verdicts[dep].verdict != VERDICT_PROVEN
        ]
        if refuters:
            verdict = VERDICT_REFUTED
        elif supporters and not unresolved_deps:
            verdict = VERDICT_PROVEN
        else:
            verdict = VERDICT_UNRESOLVED
            if unresolved_deps and supporters:
                notes.append(
                    "evidence present but dependencies unresolved: "
                    + ", ".join(unresolved_deps)
                )
            elif unresolved_deps:
                notes.append("dependencies unresolved: " + ", ".join(unresolved_deps))
            elif not supporters:
                notes.append(
                    "no admissible supporting evidence for this obligation at "
                    f"required tier {obligation.required_tier}"
                )
        verdicts[obligation_id] = ObligationVerdict(
            obligation_id=obligation_id,
            question=obligation.question,
            verdict=verdict,
            blocking=obligation.blocking,
            supporting_records=tuple(sorted(supporters)),
            refuting_records=tuple(sorted(refuters)),
            notes=tuple(notes),
        )

    return Evaluation(
        decision_id=graph.decision_id,
        decision_statement=graph.decision_statement,
        decision_value=graph.decision_value,
        evaluated_at=evaluated_at,
        verdicts=verdicts,
        anomalies=tuple(anomalies),
    )


def evaluation_instant(evaluation: Evaluation) -> int:
    return parse_instant(evaluation.evaluated_at)
