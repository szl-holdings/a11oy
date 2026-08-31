"""a11oy.policy_engine — TypedPolicyEngine.

Laws (settled across ten audit rounds — do not relitigate):
  * Default DENY: an action type matched by no rule is denied.
  * First-match-wins for the decision itself.
  * Evidence obligations accumulate across ALL matched rules.
  * Most-restrictive side-effect class wins across the request and all matches.
  * IRREVERSIBLE never auto-executes: an ALLOW that evaluates to IRREVERSIBLE
    is overridden to REQUIRE_APPROVAL. Article 12(3)(d) requires a natural
    person in the verification loop; a policy cannot wave that away.
"""
from __future__ import annotations

import datetime
import fnmatch
from dataclasses import dataclass, field

SIDE_EFFECT_CLASSES = ("READ_ONLY", "WORKSPACE_WRITE", "NETWORK_EGRESS", "IRREVERSIBLE")
_RESTRICTIVENESS = {c: i for i, c in enumerate(SIDE_EFFECT_CLASSES)}
DECISIONS = ("ALLOW", "DENY", "REQUIRE_APPROVAL")


def most_restrictive(*classes: str) -> str:
    known = [c for c in classes if c in _RESTRICTIVENESS]
    if not known:
        # An unrecognized side-effect class is treated as worst case.
        return "IRREVERSIBLE"
    return max(known, key=lambda c: _RESTRICTIVENESS[c])


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    action_patterns: tuple[str, ...]
    decision: str
    evidence_obligations: tuple[str, ...] = ()
    side_effect_class: str = "READ_ONLY"
    description: str = ""

    def __post_init__(self):
        if self.decision not in DECISIONS:
            raise ValueError(f"{self.rule_id}: unknown decision {self.decision!r}")
        if self.side_effect_class not in SIDE_EFFECT_CLASSES:
            raise ValueError(f"{self.rule_id}: unknown side_effect_class {self.side_effect_class!r}")


@dataclass
class PolicyDecision:
    action_type: str
    outcome: str
    deciding_rule: str | None
    matched_rules: list[str]
    obligations: list[str]
    side_effect_class: str
    evaluated_before_execution: bool
    rationale: str
    evaluated_at: str

    def to_dict(self) -> dict:
        return dict(self.__dict__)


# The wedge: governed agent change management. This is the only shipped
# ruleset — scope discipline, not a platform menu.
DEFAULT_RULES: tuple[PolicyRule, ...] = (
    PolicyRule(
        "ro-audit", ("estate.audit.*", "audit.*", "*.read", "verify.*"), "ALLOW",
        ("audit_inputs_recorded",), "READ_ONLY",
        "Read-only audits and verification run without approval.",
    ),
    PolicyRule(
        "ws-bounded-patch", ("agent.patch.*", "code.patch.*"), "ALLOW",
        ("tests_pass", "diff_bounded", "security_scan_clean"), "WORKSPACE_WRITE",
        "Coding agents may produce bounded patches inside the workspace.",
    ),
    PolicyRule(
        "net-egress", ("net.*", "fetch.*", "egress.*"), "REQUIRE_APPROVAL",
        ("egress_allowlist_hit",), "NETWORK_EGRESS",
        "Network egress requires approval and an allowlist hit.",
    ),
    PolicyRule(
        "prod-change", ("deploy.*", "merge.*", "release.*"), "REQUIRE_APPROVAL",
        ("human_approval_record", "ci_green", "rollback_plan"), "IRREVERSIBLE",
        "Production change management: signal → patch → approval → deploy → receipt.",
    ),
    PolicyRule(
        "deny-secrets", ("secrets.*", "credentials.*", "keys.*"), "DENY",
        ("denial_recorded",), "IRREVERSIBLE",
        "Credential material is never an agent action target.",
    ),
)


class TypedPolicyEngine:
    def __init__(self, rules=DEFAULT_RULES):
        self.rules = list(rules)

    def _matches(self, action_type: str) -> list[PolicyRule]:
        return [
            r for r in self.rules
            if any(fnmatch.fnmatchcase(action_type, p) for p in r.action_patterns)
        ]

    def evaluate(self, action_type: str, requested_side_effect: str = "READ_ONLY") -> PolicyDecision:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        matched = self._matches(action_type)

        obligations: list[str] = []
        for r in matched:
            for ob in r.evidence_obligations:
                if ob not in obligations:
                    obligations.append(ob)

        side_effect = most_restrictive(requested_side_effect, *[r.side_effect_class for r in matched])

        if not matched:
            return PolicyDecision(
                action_type=action_type, outcome="DENY", deciding_rule=None,
                matched_rules=[], obligations=["denial_recorded"],
                side_effect_class=side_effect, evaluated_before_execution=True,
                rationale="default DENY: no policy rule matched this action type",
                evaluated_at=now,
            )

        first = matched[0]
        outcome = first.decision
        rationale = f"first-match-wins: rule {first.rule_id}"
        if side_effect == "IRREVERSIBLE" and outcome == "ALLOW":
            outcome = "REQUIRE_APPROVAL"
            rationale += "; overridden: IRREVERSIBLE side effects never auto-execute"

        return PolicyDecision(
            action_type=action_type, outcome=outcome, deciding_rule=first.rule_id,
            matched_rules=[r.rule_id for r in matched], obligations=obligations,
            side_effect_class=side_effect, evaluated_before_execution=True,
            rationale=rationale, evaluated_at=now,
        )


def execution_gate(decision: PolicyDecision, approval: dict | None) -> tuple[str, str]:
    """Decide whether an evaluated action may execute.

    Returns (EXECUTE|REFUSE, reason). Approval must name a natural person:
    is_service_account=true is rejected structurally (Article 12(3)(d)).
    """
    if decision.outcome == "DENY":
        return "REFUSE", f"policy DENY ({decision.rationale})"
    if decision.outcome == "ALLOW":
        return "EXECUTE", "policy ALLOW"
    # REQUIRE_APPROVAL
    if not approval:
        return "REFUSE", "REQUIRE_APPROVAL with no approval record"
    principal = approval.get("principal", {})
    if principal.get("is_service_account") is True:
        return "REFUSE", "approval principal is a service account — Article 12(3)(d) requires a natural person"
    if not principal.get("id"):
        return "REFUSE", "approval principal has no identity"
    return "EXECUTE", f"approved by {principal['id']}"
