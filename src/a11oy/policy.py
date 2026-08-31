"""TypedPolicyEngine: the a11oy v1 policy core.

Decision semantics (CANON Laws 2 and 6):

  - Default DENY: if no rule matches, the decision is DENY.
  - First-match-wins: the first rule (in declaration order) that matches the
    action determines ALLOW vs DENY.
  - Evidence obligations accumulate across ALL matched rules, not just the
    first. The winning rule decides; every matched rule obliges.
  - Most-restrictive side-effect class wins: the effective class is the most
    restrictive of the action's declared class and every class named by a
    matched rule.
  - IRREVERSIBLE always requires human approval, regardless of any rule.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from .schemas import SideEffectClass, most_restrictive


class Effect(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


@dataclass(frozen=True)
class Rule:
    """One policy rule.

    action_types: exact action_type strings or glob patterns ("deploy.*").
    side_effect_classes: None matches any class; otherwise the rule matches
    only actions whose declared class is in this tuple, and those classes are
    folded into the most-restrictive computation.
    """

    rule_id: str
    effect: Effect
    action_types: tuple[str, ...]
    side_effect_classes: Optional[tuple[SideEffectClass, ...]] = None
    evidence_obligations: tuple[str, ...] = ()
    requires_human_approval: bool = False

    def matches(self, action_type: str, side_effect_class: SideEffectClass) -> bool:
        type_ok = any(
            fnmatch.fnmatchcase(action_type, pattern) for pattern in self.action_types
        )
        class_ok = (
            self.side_effect_classes is None
            or side_effect_class in self.side_effect_classes
        )
        return type_ok and class_ok


@dataclass(frozen=True)
class Decision:
    """The engine's output. Recorded verbatim on the receipt."""

    decision: Effect
    reason: str
    first_match_rule: Optional[str]
    matched_rules: tuple[str, ...]
    evidence_obligations: tuple[str, ...]
    effective_side_effect_class: SideEffectClass
    requires_human_approval: bool

    @property
    def allowed(self) -> bool:
        return self.decision is Effect.ALLOW


class TypedPolicyEngine:
    """Evaluates actions against an ordered rule list. Default DENY."""

    def __init__(self, rules: Sequence[Rule]):
        self._rules = list(rules)
        ids = [r.rule_id for r in self._rules]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate rule_id in policy")

    @property
    def rules(self) -> list[Rule]:
        return list(self._rules)

    def evaluate(
        self, *, action_type: str, side_effect_class: SideEffectClass
    ) -> Decision:
        matched = [
            r
            for r in self._rules
            if r.matches(action_type, side_effect_class)
        ]

        # Evidence obligations accumulate across ALL matched rules.
        obligations: list[str] = []
        for rule in matched:
            for obligation in rule.evidence_obligations:
                if obligation not in obligations:
                    obligations.append(obligation)

        # Most-restrictive side-effect class wins.
        implicated: list[SideEffectClass] = [side_effect_class]
        for rule in matched:
            if rule.side_effect_classes:
                implicated.extend(rule.side_effect_classes)
        effective_class = most_restrictive(implicated)

        if not matched:
            return Decision(
                decision=Effect.DENY,
                reason="default DENY: no rule matched this action",
                first_match_rule=None,
                matched_rules=(),
                evidence_obligations=(),
                effective_side_effect_class=effective_class,
                requires_human_approval=False,
            )

        winner = matched[0]
        approval_by_rule = any(r.requires_human_approval for r in matched)
        requires_approval = (
            winner.effect is Effect.ALLOW
            and (
                approval_by_rule
                or effective_class is SideEffectClass.IRREVERSIBLE
            )
        )
        if winner.effect is Effect.ALLOW:
            reason = f"allowed by first matching rule {winner.rule_id}"
            if effective_class is SideEffectClass.IRREVERSIBLE:
                reason += "; IRREVERSIBLE class: human approval mandatory"
        else:
            reason = f"denied by first matching rule {winner.rule_id}"
        return Decision(
            decision=winner.effect,
            reason=reason,
            first_match_rule=winner.rule_id,
            matched_rules=tuple(r.rule_id for r in matched),
            evidence_obligations=tuple(obligations),
            effective_side_effect_class=effective_class,
            requires_human_approval=requires_approval,
        )
