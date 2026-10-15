#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Offline, synthetic paired test of a literal source-bound proposal gate.

Taxonomy: governance research harness. This is not a serving route, model
evaluation, semantic entailment checker, receipt signer, or authority grant.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, replace
from typing import Mapping, Sequence


SCHEMA = "szl.paired-source-invalidation/v1"
SEED = "szl-paired-source-invalidation-20261014-v1"
MUTATIONS = (
    "missing_support_span",
    "stale_proposal_hash",
    "conflicting_assertion",
    "relevant_but_insufficient",
)
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _line(**fields: str) -> str:
    return json.dumps(fields, sort_keys=True, separators=(",", ":"))


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    """Reject ambiguous keys in every JSON object, including nested objects."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


@dataclass(frozen=True)
class Proposal:
    claim_id: str
    answer: str
    source_id: str
    source_sha256: str


@dataclass(frozen=True)
class Source:
    source_id: str
    content: str
    selected_spans: tuple[str, ...]


@dataclass(frozen=True)
class Case:
    pair_id: str
    mutation: str
    proposal: Proposal
    sources: tuple[Source, ...]
    expected_hashes: Mapping[str, str]
    training_eligible: bool = False


@dataclass(frozen=True)
class Decision:
    action: str
    reason: str


def proposal_only(proposal: Proposal) -> Decision:
    """Explicitly simulated baseline: answer without examining any evidence."""
    if not all((proposal.claim_id, proposal.answer, proposal.source_id)):
        return Decision("ABSTAIN", "INVALID_PROPOSAL")
    return Decision("ANSWER", "PROPOSAL_ONLY")


def source_bound_gate(case: Case) -> Decision:
    """Check a literal structured claim against externally supplied hash anchors.

    The hash map is an input, not an authenticated receipt. A live system would
    need independent source admission and anchoring before this check has value.
    """
    proposal = case.proposal
    if not all(isinstance(value, str) and value for value in (
        proposal.claim_id, proposal.answer, proposal.source_id,
    )) or not isinstance(proposal.source_sha256, str) or not _SHA256.fullmatch(
        proposal.source_sha256
    ):
        return Decision("ABSTAIN", "INVALID_PROPOSAL")

    sources = {source.source_id: source for source in case.sources}
    if (len(sources) != len(case.sources)
            or set(sources) != set(case.expected_hashes)
            or proposal.source_id not in sources):
        return Decision("ABSTAIN", "SOURCE_SET_MISMATCH")

    for source_id, source in sources.items():
        expected = case.expected_hashes[source_id]
        if not isinstance(expected, str) or not _SHA256.fullmatch(expected):
            return Decision("ABSTAIN", "INVALID_ANCHOR")
        if _sha(source.content) != expected:
            return Decision("ABSTAIN", "SOURCE_HASH_MISMATCH")
    if case.expected_hashes[proposal.source_id] != proposal.source_sha256:
        return Decision("ABSTAIN", "PROPOSAL_HASH_MISMATCH")

    assertions: set[str] = set()
    cited_assertions: set[str] = set()
    for source in case.sources:
        lines = {}
        for line in source.content.splitlines():
            try:
                claim = json.loads(line, object_pairs_hook=_unique_object)
            except ValueError:
                return Decision("ABSTAIN", "INVALID_SOURCE_CONTENT")
            if not isinstance(claim, dict) or claim.get("kind") not in (
                "assertion", "context", "revision"
            ) or not isinstance(claim.get("claim_id"), str):
                return Decision("ABSTAIN", "INVALID_SOURCE_CONTENT")
            if claim["kind"] == "assertion":
                answer = claim.get("answer")
                if not isinstance(answer, str) or not answer:
                    return Decision("ABSTAIN", "INVALID_SOURCE_CONTENT")
                if claim["claim_id"] == proposal.claim_id:
                    assertions.add(answer)
            lines[line] = claim
        for span in source.selected_spans:
            if not isinstance(span, str) or span not in lines:
                return Decision("ABSTAIN", "SPAN_NOT_IN_SOURCE")
            claim = lines[span]
            if (source.source_id == proposal.source_id
                    and claim["kind"] == "assertion"
                    and claim["claim_id"] == proposal.claim_id):
                cited_assertions.add(claim["answer"])

    if len(assertions) > 1:
        return Decision("ABSTAIN", "CONFLICTING_ASSERTIONS")
    if proposal.answer not in cited_assertions:
        return Decision("ABSTAIN", "NO_SELECTED_SUPPORT")
    return Decision("ANSWER", "LITERAL_SOURCE_MATCH")


def fixture_pairs(per_mutation: int = 30) -> tuple[tuple[Case, Case], ...]:
    """Generate frozen synthetic pairs; the labels never enter the gate."""
    if per_mutation < 1:
        raise ValueError("per_mutation must be positive")
    pairs = []
    for mutation in MUTATIONS:
        for index in range(per_mutation):
            pair_id = f"{mutation}:{index:03d}"
            claim_id = f"synthetic-claim-{_sha(SEED + pair_id)[:16]}"
            answer = f"value-{_sha(pair_id + SEED)[16:28]}"
            source_id = f"source-{pair_id}"
            support = _line(kind="assertion", claim_id=claim_id, answer=answer)
            context = _line(kind="context", claim_id=claim_id,
                            note="topic present; no answer asserted")
            content = support + "\n" + context
            source = Source(source_id, content, (support,))
            digest = _sha(content)
            proposal = Proposal(claim_id, answer, source_id, digest)
            supported = Case(pair_id, mutation, proposal, (source,),
                             {source_id: digest})

            if mutation == "missing_support_span":
                invalid = replace(supported, sources=(replace(source, selected_spans=()),))
            elif mutation == "relevant_but_insufficient":
                invalid = replace(supported, sources=(replace(source,
                    selected_spans=(context,)),))
            elif mutation == "stale_proposal_hash":
                revised = replace(source, content=content + "\n" +
                                  _line(kind="revision", claim_id=claim_id))
                invalid = replace(supported, sources=(revised,),
                                  expected_hashes={source_id: _sha(revised.content)})
            else:
                conflict_id = f"conflict-{pair_id}"
                conflict_span = _line(kind="assertion", claim_id=claim_id,
                                      answer=answer + "-different")
                conflict = Source(conflict_id, conflict_span, (conflict_span,))
                invalid = replace(supported, sources=(source, conflict),
                                  expected_hashes={source_id: digest,
                                                   conflict_id: _sha(conflict_span)})
            pairs.append((supported, invalid))
    return tuple(pairs)


def run_experiment(per_mutation: int = 30) -> dict[str, object]:
    """Return counts from this run, with no provider call or written artifact."""
    pairs = fixture_pairs(per_mutation)
    results = {mode: {"pairs": 0, "supported_retained": 0,
                      "invalidated_denied": 0, "paired_reversals": 0}
               for mode in MUTATIONS}
    baseline_invalidated_answers = 0
    baseline_supported_answers = 0
    for supported, invalid in pairs:
        if supported.training_eligible or invalid.training_eligible:
            raise ValueError("evaluation fixtures cannot be trainable")
        if supported.proposal != invalid.proposal:
            raise ValueError("paired proposal changed")
        mode = results[supported.mutation]
        mode["pairs"] += 1
        before, after = source_bound_gate(supported), source_bound_gate(invalid)
        mode["supported_retained"] += before.action == "ANSWER"
        mode["invalidated_denied"] += after.action == "ABSTAIN"
        mode["paired_reversals"] += (
            before.action == "ANSWER" and after.action == "ABSTAIN"
        )
        baseline_supported_answers += proposal_only(supported.proposal).action == "ANSWER"
        baseline_invalidated_answers += proposal_only(invalid.proposal).action == "ANSWER"

    fixture_description = [{"pair_id": a.pair_id, "proposal": vars(a.proposal),
                            "supported": [(s.source_id, s.content, s.selected_spans)
                                          for s in a.sources],
                            "invalidated": [(s.source_id, s.content, s.selected_spans)
                                            for s in b.sources],
                            "supported_anchors": a.expected_hashes,
                            "invalidated_anchors": b.expected_hashes}
                           for a, b in pairs]
    fixture_sha256 = _sha(json.dumps(fixture_description, sort_keys=True,
                                     separators=(",", ":")))
    total = len(pairs)
    return {
        "schema": SCHEMA,
        "evidence_class": "SIMULATED",
        "scope": "deterministic synthetic literal-span contract only",
        "seed": SEED,
        "fixture_sha256": fixture_sha256,
        "training_eligible": False,
        "model_invocations": 0,
        "external_effects": 0,
        "denominators": {"pairs": total, "supported": total,
                         "invalidated": total},
        "proposal_only": {"supported_answers": baseline_supported_answers,
                          "invalidated_answers": baseline_invalidated_answers},
        "source_bound_gate": {
            "supported_answers": sum(m["supported_retained"] for m in results.values()),
            "invalidated_abstentions": sum(m["invalidated_denied"] for m in results.values()),
            "paired_reversals": sum(m["paired_reversals"] for m in results.values()),
            "by_mutation": results,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_experiment(), indent=2, sort_keys=True))
