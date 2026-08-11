from __future__ import annotations

"""Monotonic capability grants, exact-target authorization, and budget accounting."""

import fnmatch
from datetime import datetime
from pathlib import PurePosixPath

from .canonical import parse_utc
from .errors import AuthorizationError, ValidationError
from .models import ActionRequest, AutonomyEnvelope, BudgetLimits, BudgetUsage, CapabilityGrant


def normalize_target(value: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValidationError("target must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValidationError("target must be normalized and cannot traverse")
    return path.as_posix()


def target_matches(pattern: str, target: str) -> bool:
    target = normalize_target(target)
    if pattern.endswith("/**"):
        prefix = normalize_target(pattern[:-3])
        return target == prefix or target.startswith(prefix + "/")
    if any(token in pattern for token in "*?["):
        normalized = pattern.replace("\\", "/")
        if normalized.startswith("/") or "../" in normalized or normalized == "..":
            return False
        return fnmatch.fnmatchcase(target, normalized)
    return normalize_target(pattern) == target


def pattern_is_subset(child: str, parent: str) -> bool:
    """Conservative target-pattern attenuation check."""
    if child == parent:
        return True
    if parent.endswith("/**"):
        prefix = normalize_target(parent[:-3])
        if child.endswith("/**"):
            child_prefix = normalize_target(child[:-3])
            return child_prefix == prefix or child_prefix.startswith(prefix + "/")
        if any(token in child for token in "*?["):
            return False
        normalized_child = normalize_target(child)
        return normalized_child == prefix or normalized_child.startswith(prefix + "/")
    return False


def validate_attenuation(parent: CapabilityGrant, child: CapabilityGrant) -> None:
    if child.parent_grant_id != parent.grant_id:
        raise AuthorizationError("child grant is not bound to the parent grant")
    if not set(child.capabilities).issubset(parent.capabilities):
        raise AuthorizationError("child capability set expands parent authority")
    if not set(child.tools).issubset(parent.tools):
        raise AuthorizationError("child tool set expands parent authority")
    for child_pattern in child.target_patterns:
        if not any(pattern_is_subset(child_pattern, parent_pattern) for parent_pattern in parent.target_patterns):
            raise AuthorizationError(f"child target pattern is not provably within parent: {child_pattern}")
    if not child.budgets.is_subset_of(parent.budgets):
        raise AuthorizationError("child budgets exceed parent budgets")
    if parse_utc(child.issued_at) < parse_utc(parent.issued_at):
        raise AuthorizationError("child grant predates parent grant")
    if parse_utc(child.expires_at) > parse_utc(parent.expires_at):
        raise AuthorizationError("child grant outlives parent grant")
    if parent.revoked_at is not None:
        raise AuthorizationError("cannot attenuate a revoked grant")


def authorize_action(
    grant: CapabilityGrant,
    envelope: AutonomyEnvelope,
    action: ActionRequest,
    usage: BudgetUsage,
    *,
    now: str | datetime,
) -> None:
    if grant.grant_id != action.grant_id:
        raise AuthorizationError("action grant_id does not match supplied grant")
    if grant.principal != envelope.principal:
        raise AuthorizationError("grant principal does not match envelope principal")
    if action.case_id != envelope.case_id:
        raise AuthorizationError("action case_id does not match envelope")
    if not grant.active_at(now):
        raise AuthorizationError("capability grant is inactive, expired, or revoked")
    if not envelope.active_at(now):
        raise AuthorizationError("autonomy envelope is inactive, expired, or revoked")
    if action.kind.capability not in grant.capabilities or action.kind.capability not in envelope.capabilities:
        raise AuthorizationError(f"missing capability: {action.kind.capability}")
    rollback = envelope.rollback_plan
    if rollback.required and rollback.strategy != "NONE":
        rollback_capability = rollback.authority_capability
        if rollback_capability not in envelope.capabilities or rollback_capability not in grant.capabilities:
            raise AuthorizationError(f"missing rollback capability: {rollback_capability}")
    if action.tool not in grant.tools or action.tool not in envelope.tools:
        raise AuthorizationError("tool is not authorized by grant and envelope")
    target = normalize_target(action.target)
    if target not in {normalize_target(item) for item in envelope.exact_targets}:
        raise AuthorizationError("action target is not an exact envelope target")
    if not any(target_matches(pattern, target) for pattern in grant.target_patterns):
        raise AuthorizationError("action target is outside the capability grant")
    if action.idempotency_key != envelope.idempotency_key:
        raise AuthorizationError("action idempotency key does not match envelope")
    if not usage.within(grant.budgets) or not usage.within(envelope.budgets):
        raise AuthorizationError("budget usage exceeds grant or envelope")


class BudgetAccount:
    """Deterministic in-memory budget counter bound to immutable limits."""

    def __init__(self, limits: BudgetLimits) -> None:
        self.limits = limits
        self.usage = BudgetUsage()

    def consume(self, *, cost_usd: float = 0.0, duration_seconds: int = 0, tool_calls: int = 0, mutations: int = 0, branches: int = 0, recursion: int = 0) -> BudgetUsage:
        candidate = BudgetUsage(
            cost_usd=self.usage.cost_usd + cost_usd,
            duration_seconds=self.usage.duration_seconds + duration_seconds,
            tool_calls=self.usage.tool_calls + tool_calls,
            mutations=self.usage.mutations + mutations,
            branches=self.usage.branches + branches,
            recursion=self.usage.recursion + recursion,
        )
        if not candidate.within(self.limits):
            raise AuthorizationError("budget consumption would exceed the Autonomy Envelope")
        self.usage = candidate
        return candidate

    def snapshot(self) -> dict[str, object]:
        return {"limits": self.limits.to_dict(), "usage": self.usage.to_dict(), "within": self.usage.within(self.limits)}
