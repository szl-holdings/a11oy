from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from a11oy_council import CapabilityGrant, HashChainLedger, LedgerIntegrityError
from a11oy_council.delegation import (
    RevocationRegistry,
    attenuate_grant,
    grant_digest,
    verify_delegation,
    verify_delegation_chain,
)


NOW = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)


def root_grant() -> CapabilityGrant:
    return CapabilityGrant(
        grant_id="root",
        subject="owner",
        capabilities=("source.read", "source.write"),
        actions=("inspect", "apply_patch"),
        exact_targets=("repo://szl-holdings/a11oy", "repo://szl-holdings/platform"),
        budget_microunits=10_000,
        expires_at=NOW + timedelta(days=2),
    )


def child(parent: CapabilityGrant | None = None):
    return attenuate_grant(
        parent or root_grant(),
        child_grant_id="child",
        child_subject="council-alpha",
        capabilities=("source.write",),
        actions=("apply_patch",),
        exact_targets=("repo://szl-holdings/a11oy",),
        budget_microunits=2_000,
        expires_at=NOW + timedelta(days=1),
        delegated_at=NOW,
    )


class DelegationTests(unittest.TestCase):
    def test_valid_attenuation_verifies(self) -> None:
        parent = root_grant()
        delegated = child(parent)
        self.assertTrue(verify_delegation(parent, delegated))
        self.assertEqual(delegated.record.parent_digest, grant_digest(parent))
        self.assertEqual(delegated.grant.exact_targets, ("repo://szl-holdings/a11oy",))

    def test_capabilities_cannot_expand(self) -> None:
        with self.assertRaises(ValueError):
            attenuate_grant(
                root_grant(),
                child_grant_id="child",
                child_subject="council-alpha",
                capabilities=("source.write", "secrets.read"),
                actions=("apply_patch",),
                exact_targets=("repo://szl-holdings/a11oy",),
                budget_microunits=1,
                expires_at=NOW + timedelta(days=1),
                delegated_at=NOW,
            )

    def test_actions_and_targets_cannot_expand(self) -> None:
        with self.assertRaises(ValueError):
            attenuate_grant(
                root_grant(),
                child_grant_id="child",
                child_subject="council-alpha",
                capabilities=("source.write",),
                actions=("delete_repository",),
                exact_targets=("repo://szl-holdings/other",),
                budget_microunits=1,
                expires_at=NOW + timedelta(days=1),
                delegated_at=NOW,
            )

    def test_budget_and_expiry_cannot_expand(self) -> None:
        with self.assertRaises(ValueError):
            attenuate_grant(
                root_grant(),
                child_grant_id="child",
                child_subject="council-alpha",
                capabilities=("source.write",),
                actions=("apply_patch",),
                exact_targets=("repo://szl-holdings/a11oy",),
                budget_microunits=10_001,
                expires_at=NOW + timedelta(days=3),
                delegated_at=NOW,
            )

    def test_revoked_parent_cannot_delegate(self) -> None:
        with self.assertRaises(ValueError):
            child(replace(root_grant(), revoked=True))

    def test_two_level_chain_verifies(self) -> None:
        root = root_grant()
        first = child(root)
        second = attenuate_grant(
            first.grant,
            child_grant_id="grandchild",
            child_subject="worker-1",
            capabilities=("source.write",),
            actions=("apply_patch",),
            exact_targets=("repo://szl-holdings/a11oy",),
            budget_microunits=500,
            expires_at=NOW + timedelta(hours=12),
            delegated_at=NOW + timedelta(minutes=1),
        )
        self.assertTrue(verify_delegation_chain(root, (first, second)))

    def test_root_revocation_invalidates_chain(self) -> None:
        root = root_grant()
        delegated = child(root)
        registry = RevocationRegistry()
        registry.revoke(root, reason="owner revoked authority", revoked_at=NOW)
        self.assertFalse(verify_delegation_chain(root, (delegated,), registry))
        self.assertTrue(registry.ledger.verify())

    def test_child_revocation_invalidates_chain_and_apply_is_honest(self) -> None:
        root = root_grant()
        delegated = child(root)
        registry = RevocationRegistry()
        registry.revoke(
            delegated.grant,
            reason="task window closed",
            revoked_at=NOW + timedelta(minutes=1),
        )
        self.assertFalse(verify_delegation_chain(root, (delegated,), registry))
        self.assertTrue(registry.apply(delegated.grant).revoked)
        self.assertFalse(registry.apply(root).revoked)

    def test_revocation_id_cannot_bind_new_content(self) -> None:
        registry = RevocationRegistry()
        root = root_grant()
        registry.revoke(root, reason="closed", revoked_at=NOW)
        registry.revoke(root, reason="duplicate is idempotent", revoked_at=NOW)
        altered = replace(root, budget_microunits=9_999)
        with self.assertRaises(ValueError):
            registry.revoke(altered, reason="collision", revoked_at=NOW)
        self.assertEqual(len(registry.ledger.entries), 1)

    def test_revoked_grant_id_cannot_be_rebound_during_authority_check(self) -> None:
        registry = RevocationRegistry()
        root = root_grant()
        registry.revoke(root, reason="closed", revoked_at=NOW)
        altered = replace(root, budget_microunits=9_999)

        with self.assertRaisesRegex(LedgerIntegrityError, "conflicting grant digest"):
            registry.is_revoked(altered)
        with self.assertRaisesRegex(LedgerIntegrityError, "conflicting grant digest"):
            registry.apply(altered)

        altered_and_pre_revoked = replace(
            root,
            budget_microunits=9_999,
            revoked=True,
        )
        with self.assertRaisesRegex(LedgerIntegrityError, "conflicting grant digest"):
            registry.is_revoked(altered_and_pre_revoked)
        with self.assertRaisesRegex(LedgerIntegrityError, "conflicting grant digest"):
            registry.apply(altered_and_pre_revoked)

        materialized = registry.apply(root)
        self.assertTrue(materialized.revoked)
        self.assertTrue(registry.is_revoked(materialized))

    def test_revocation_is_restored_from_reopened_durable_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "council.jsonl"
            root = root_grant()
            delegated = child(root)
            registry = RevocationRegistry(HashChainLedger(path))
            registry.revoke(root, reason="owner revoked authority", revoked_at=NOW)

            reopened = RevocationRegistry(HashChainLedger(path))
            self.assertTrue(reopened.is_revoked(root))
            self.assertTrue(reopened.apply(root).revoked)
            self.assertFalse(verify_delegation_chain(root, (delegated,), reopened))
            self.assertEqual(reopened.revoked, {root.grant_id: grant_digest(root)})

            altered = replace(root, budget_microunits=9_999)
            with self.assertRaisesRegex(LedgerIntegrityError, "conflicting grant digest"):
                reopened.is_revoked(altered)

    def test_invalid_persisted_revocation_payload_fails_closed(self) -> None:
        ledger = HashChainLedger()
        ledger.append(
            "capability.revoked",
            {
                "grant_id": "root",
                "grant_digest": grant_digest(root_grant()),
                "revoked_at": NOW.isoformat().replace("+00:00", "Z"),
            },
        )
        with self.assertRaisesRegex(LedgerIntegrityError, "payload fields"):
            RevocationRegistry(ledger)

    def test_conflicting_persisted_revocation_digests_fail_closed(self) -> None:
        ledger = HashChainLedger()
        for digest in (grant_digest(root_grant()), "f" * 64):
            ledger.append(
                "capability.revoked",
                {
                    "grant_id": "root",
                    "grant_digest": digest,
                    "reason": "owner revoked authority",
                    "revoked_at": NOW.isoformat().replace("+00:00", "Z"),
                },
            )
        with self.assertRaisesRegex(LedgerIntegrityError, "conflicting digests"):
            RevocationRegistry(ledger)


if __name__ == "__main__":
    unittest.main()
