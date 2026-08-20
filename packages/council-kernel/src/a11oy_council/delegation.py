"""Capability attenuation, delegation-chain verification, and revocation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime, timezone
import hmac
from threading import RLock
from typing import Any, Iterable, Mapping

from .kernel import (
    CapabilityGrant,
    HashChainLedger,
    LedgerIntegrityError,
    canonical_json,
    sha256_text,
)


_REVOCATION_PAYLOAD_FIELDS = {
    "grant_id",
    "grant_digest",
    "reason",
    "revoked_at",
}


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must be timezone-aware")
    return value.astimezone(timezone.utc)


def grant_canonical_dict(grant: CapabilityGrant) -> dict[str, Any]:
    return {
        "grant_id": grant.grant_id,
        "subject": grant.subject,
        "capabilities": sorted(grant.capabilities),
        "actions": sorted(grant.actions),
        "exact_targets": sorted(grant.exact_targets),
        "budget_microunits": grant.budget_microunits,
        "expires_at": _utc(grant.expires_at).isoformat().replace("+00:00", "Z"),
        "revoked": grant.revoked,
    }


def grant_digest(grant: CapabilityGrant) -> str:
    return sha256_text(canonical_json(grant_canonical_dict(grant)))


def _validated_revocation_payload(payload: Mapping[str, Any]) -> tuple[str, str]:
    if set(payload) != _REVOCATION_PAYLOAD_FIELDS:
        raise LedgerIntegrityError("invalid capability.revoked payload fields")

    grant_id = payload["grant_id"]
    digest = payload["grant_digest"]
    reason = payload["reason"]
    revoked_at = payload["revoked_at"]
    if not isinstance(grant_id, str) or not grant_id.strip():
        raise LedgerIntegrityError("invalid capability.revoked grant_id")
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(character not in "0123456789abcdef" for character in digest)
    ):
        raise LedgerIntegrityError("invalid capability.revoked grant_digest")
    if not isinstance(reason, str) or not reason.strip():
        raise LedgerIntegrityError("invalid capability.revoked reason")
    if not isinstance(revoked_at, str):
        raise LedgerIntegrityError("invalid capability.revoked revoked_at")
    try:
        parsed = datetime.fromisoformat(
            revoked_at[:-1] + "+00:00" if revoked_at.endswith("Z") else revoked_at
        )
        _utc(parsed)
    except ValueError as exc:
        raise LedgerIntegrityError("invalid capability.revoked revoked_at") from exc
    return grant_id, digest


@dataclass(frozen=True, slots=True)
class DelegationRecord:
    parent_grant_id: str
    parent_digest: str
    child_grant_id: str
    child_digest: str
    delegated_at: datetime
    attenuation_digest: str

    def canonical_dict(self, *, include_digest: bool = True) -> dict[str, Any]:
        value: dict[str, Any] = {
            "parent_grant_id": self.parent_grant_id,
            "parent_digest": self.parent_digest,
            "child_grant_id": self.child_grant_id,
            "child_digest": self.child_digest,
            "delegated_at": _utc(self.delegated_at).isoformat().replace("+00:00", "Z"),
        }
        if include_digest:
            value["attenuation_digest"] = self.attenuation_digest
        return value


@dataclass(frozen=True, slots=True)
class DelegatedGrant:
    grant: CapabilityGrant
    record: DelegationRecord


def attenuate_grant(
    parent: CapabilityGrant,
    *,
    child_grant_id: str,
    child_subject: str,
    capabilities: Iterable[str],
    actions: Iterable[str],
    exact_targets: Iterable[str],
    budget_microunits: int,
    expires_at: datetime,
    delegated_at: datetime,
) -> DelegatedGrant:
    capability_values = tuple(sorted(set(capabilities)))
    action_values = tuple(sorted(set(actions)))
    target_values = tuple(sorted(set(exact_targets)))
    delegated_time = _utc(delegated_at)
    child_expiry = _utc(expires_at)
    parent_expiry = _utc(parent.expires_at)

    if parent.revoked:
        raise ValueError("a revoked grant cannot be delegated")
    if delegated_time >= parent_expiry:
        raise ValueError("an expired grant cannot be delegated")
    if child_expiry > parent_expiry:
        raise ValueError("child expiry cannot exceed parent expiry")
    if child_expiry <= delegated_time:
        raise ValueError("child grant must expire after delegation")
    if budget_microunits < 0 or budget_microunits > parent.budget_microunits:
        raise ValueError("child budget must be within the parent budget")
    if not capability_values or not set(capability_values).issubset(parent.capabilities):
        raise ValueError("child capabilities must be a non-empty parent subset")
    if not action_values or not set(action_values).issubset(parent.actions):
        raise ValueError("child actions must be a non-empty parent subset")
    if not target_values or not set(target_values).issubset(parent.exact_targets):
        raise ValueError("child targets must be a non-empty exact parent subset")

    child = CapabilityGrant(
        grant_id=child_grant_id,
        subject=child_subject,
        capabilities=capability_values,
        actions=action_values,
        exact_targets=target_values,
        budget_microunits=budget_microunits,
        expires_at=child_expiry,
        revoked=False,
    )
    record_without_digest = {
        "parent_grant_id": parent.grant_id,
        "parent_digest": grant_digest(parent),
        "child_grant_id": child.grant_id,
        "child_digest": grant_digest(child),
        "delegated_at": delegated_time.isoformat().replace("+00:00", "Z"),
    }
    record = DelegationRecord(
        parent_grant_id=parent.grant_id,
        parent_digest=record_without_digest["parent_digest"],
        child_grant_id=child.grant_id,
        child_digest=record_without_digest["child_digest"],
        delegated_at=delegated_time,
        attenuation_digest=sha256_text(canonical_json(record_without_digest)),
    )
    return DelegatedGrant(grant=child, record=record)


def verify_delegation(
    parent: CapabilityGrant,
    delegated: DelegatedGrant,
) -> bool:
    child = delegated.grant
    record = delegated.record
    if record.parent_grant_id != parent.grant_id:
        return False
    if record.child_grant_id != child.grant_id:
        return False
    if not hmac.compare_digest(record.parent_digest, grant_digest(parent)):
        return False
    if not hmac.compare_digest(record.child_digest, grant_digest(child)):
        return False
    expected_digest = sha256_text(canonical_json(record.canonical_dict(include_digest=False)))
    if not hmac.compare_digest(record.attenuation_digest, expected_digest):
        return False
    if not set(child.capabilities).issubset(parent.capabilities):
        return False
    if not set(child.actions).issubset(parent.actions):
        return False
    if not set(child.exact_targets).issubset(parent.exact_targets):
        return False
    if child.budget_microunits > parent.budget_microunits:
        return False
    if _utc(child.expires_at) > _utc(parent.expires_at):
        return False
    return True


class RevocationRegistry:
    """Append-only grant revocations with parent-chain propagation."""

    def __init__(self, ledger: HashChainLedger | None = None) -> None:
        self.ledger = ledger if ledger is not None else HashChainLedger()
        self._revoked: dict[str, str] = {}
        self._lock = RLock()
        self._restore_revocations()

    def _restore_revocations(self) -> None:
        if not self.ledger.verify():
            raise LedgerIntegrityError("revocation ledger hash chain verification failed")
        for entry in self.ledger.entries:
            if entry.kind != "capability.revoked":
                continue
            grant_id, digest = _validated_revocation_payload(entry.payload)
            existing = self._revoked.get(grant_id)
            if existing is not None and not hmac.compare_digest(existing, digest):
                raise LedgerIntegrityError(
                    "grant_id revocation is bound to conflicting digests"
                )
            self._revoked[grant_id] = digest

    @property
    def revoked(self) -> Mapping[str, str]:
        with self._lock:
            return dict(self._revoked)

    def revoke(
        self,
        grant: CapabilityGrant,
        *,
        reason: str,
        revoked_at: datetime,
    ) -> None:
        if not reason.strip():
            raise ValueError("revocation reason must be non-empty")
        timestamp = _utc(revoked_at).isoformat().replace("+00:00", "Z")
        digest = grant_digest(grant)
        with self._lock:
            existing = self._revoked.get(grant.grant_id)
            if existing is not None and existing != digest:
                raise ValueError("grant_id revocation is already bound to another digest")
            if existing is None:
                self._revoked[grant.grant_id] = digest
                self.ledger.append(
                    "capability.revoked",
                    {
                        "grant_id": grant.grant_id,
                        "grant_digest": digest,
                        "reason": reason,
                        "revoked_at": timestamp,
                    },
                )

    def is_revoked(self, grant: CapabilityGrant) -> bool:
        with self._lock:
            digest = self._revoked.get(grant.grant_id)
        return digest is not None and hmac.compare_digest(digest, grant_digest(grant))

    def apply(self, grant: CapabilityGrant) -> CapabilityGrant:
        return replace(grant, revoked=grant.revoked or self.is_revoked(grant))


def verify_delegation_chain(
    root: CapabilityGrant,
    chain: Iterable[DelegatedGrant],
    revocations: RevocationRegistry | None = None,
) -> bool:
    parent = root
    if revocations is not None and revocations.is_revoked(parent):
        return False
    for delegated in chain:
        if not verify_delegation(parent, delegated):
            return False
        if revocations is not None and revocations.is_revoked(delegated.grant):
            return False
        parent = delegated.grant
    return True
