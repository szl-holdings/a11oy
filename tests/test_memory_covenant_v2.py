#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Adversarial tests for the Memory Covenant v2 migration contract."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR_PATH = ROOT / "scripts/validate_memory_covenant_v2.py"
SPEC = importlib.util.spec_from_file_location("validate_memory_covenant_v2", VALIDATOR_PATH)
assert SPEC and SPEC.loader
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)


class MemoryCovenantV2ContractTests(unittest.TestCase):
    def make_fixture(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        for relative in (validator.BASE_MIGRATION, validator.HARDENING_MIGRATION):
            source = ROOT / relative
            target = root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(source.read_bytes())
        return temp, root

    @staticmethod
    def replace_once(path: Path, old: str, new: str) -> None:
        text = path.read_text(encoding="utf-8")
        count = text.count(old)
        if count != 1:
            raise AssertionError(f"expected one fixture match, found {count}: {old!r}")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def assert_contract_error(self, root: Path, fragment: str) -> None:
        errors = validator.validate(root)
        self.assertTrue(
            any(fragment in error for error in errors),
            f"missing error fragment {fragment!r}; observed: {errors}",
        )

    def test_committed_migrations_pass(self) -> None:
        self.assertEqual(validator.validate(ROOT), [])

    def test_missing_migration_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            (root / validator.HARDENING_MIGRATION).unlink()
            self.assert_contract_error(root, "missing required migration")

    def test_tenant_table_without_force_rls_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(
                path,
                "ALTER TABLE memory_records FORCE ROW LEVEL SECURITY;\n",
                "",
            )
            self.assert_contract_error(root, "FORCE RLS for memory_records")

    def test_outbox_force_rls_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(
                path,
                "ALTER TABLE memory_outbox ENABLE ROW LEVEL SECURITY;\n",
                "ALTER TABLE memory_outbox ENABLE ROW LEVEL SECURITY;\n"
                "ALTER TABLE memory_outbox FORCE ROW LEVEL SECURITY;\n",
            )
            self.assert_contract_error(root, "memory_outbox must not use FORCE RLS")

    def test_missing_tenant_policy_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(
                path,
                "CREATE POLICY memory_records_isolation ON memory_records\n",
                "CREATE POLICY memory_records_other ON memory_records\n",
            )
            self.assert_contract_error(root, "isolation policy for memory_records")

    def test_policy_reset_missing_table_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(
                path,
                "AND c.relname IN (\n"
                "               'memory_records',\n"
                "               'memory_evidence_refs',",
                "AND c.relname IN (\n"
                "               'memory_records',",
            )
            self.assert_contract_error(root, "policy reset must cover memory_evidence_refs")

    def test_policy_without_with_check_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(
                path,
                "CREATE POLICY memory_records_isolation ON memory_records\n"
                "USING (a11oy_memory_context_matches(tenant_id, security_domain))\n"
                "WITH CHECK (a11oy_memory_context_matches(tenant_id, security_domain));",
                "CREATE POLICY memory_records_isolation ON memory_records\n"
                "USING (a11oy_memory_context_matches(tenant_id, security_domain));",
            )
            self.assert_contract_error(root, "bind both USING and WITH CHECK")

    def test_append_only_trigger_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(
                path,
                "CREATE TRIGGER memory_receipts_append_only BEFORE UPDATE OR DELETE ON memory_receipts\n"
                "FOR EACH ROW EXECUTE FUNCTION memory_reject_mutation();\n",
                "",
            )
            self.assert_contract_error(root, "append-only trigger for memory_receipts")

    def test_append_only_sqlstate_change_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "ERRCODE='55000'", "ERRCODE='P0001'")
            self.assert_contract_error(root, "append-only SQLSTATE 55000")

    def test_bypass_rls_role_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            text = path.read_text(encoding="utf-8").replace("NOBYPASSRLS", "BYPASSRLS")
            path.write_text(text, encoding="utf-8")
            self.assert_contract_error(root, "must never receive BYPASSRLS")

    def test_existing_superuser_normalization_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "ALTER ROLE a11oy_memory_app\n"
                "            NOSUPERUSER NOCREATEDB NOCREATEROLE NOLOGIN INHERIT "
                "NOREPLICATION NOBYPASSRLS;",
                "ALTER ROLE a11oy_memory_app\n"
                "            NOCREATEDB NOCREATEROLE NOLOGIN INHERIT "
                "NOREPLICATION NOBYPASSRLS;",
            )
            self.assert_contract_error(root, "hardened ALTER ROLE for a11oy_memory_app")

    def test_login_role_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            text = path.read_text(encoding="utf-8").replace("NOLOGIN", "LOGIN")
            path.write_text(text, encoding="utf-8")
            self.assert_contract_error(root, "must remain NOLOGIN")

    def test_application_privilege_expansion_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "GRANT SELECT, INSERT ON memory_outbox TO a11oy_memory_app;",
                "GRANT SELECT, INSERT, UPDATE, DELETE ON memory_outbox TO a11oy_memory_app;",
            )
            self.assert_contract_error(root, "application table grants differ")

    def test_missing_application_acl_reset_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "REVOKE ALL PRIVILEGES ON TABLE memory_records\n"
                "    FROM PUBLIC, a11oy_memory_app;\n",
                "",
            )
            self.assert_contract_error(
                root, "missing bounded ACL reset for application table memory_records"
            )

    def test_missing_worker_acl_reset_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "REVOKE ALL PRIVILEGES ON TABLE memory_outbox\n"
                "    FROM a11oy_memory_worker;\n",
                "",
            )
            self.assert_contract_error(
                root, "missing bounded ACL reset for worker table memory_outbox"
            )

    def test_worker_direct_table_grant_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "COMMIT;",
                "GRANT SELECT ON memory_outbox TO a11oy_memory_worker;\n\nCOMMIT;",
            )
            self.assert_contract_error(root, "worker role must not receive direct")

    def test_public_grant_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "COMMIT;",
                "GRANT EXECUTE ON FUNCTION memory_lease_outbox(text, integer, integer) TO PUBLIC;\n\nCOMMIT;",
            )
            self.assert_contract_error(root, "must not grant privileges to PUBLIC")

    def test_missing_public_revoke_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "REVOKE ALL ON FUNCTION memory_lease_outbox(text, integer, integer)\n"
                "    FROM PUBLIC, a11oy_memory_app, a11oy_memory_worker;\n",
                "",
            )
            self.assert_contract_error(root, "PUBLIC and capability-role function revoke")

    def test_unbounded_worker_limit_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "p_limit > 500", "p_limit > 5000")
            self.assert_contract_error(root, "bounded item limit")

    def test_null_worker_limit_guard_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "IF p_limit IS NULL\n       OR p_lease_seconds IS NULL",
                "IF p_lease_seconds IS NULL",
            )
            self.assert_contract_error(root, "null item-limit rejection")

    def test_unbounded_lease_duration_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "p_lease_seconds > 3600", "p_lease_seconds > 86400")
            self.assert_contract_error(root, "bounded lease duration")

    def test_null_lease_duration_guard_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "OR p_lease_seconds IS NULL\n       OR p_limit < 1",
                "OR p_limit < 1",
            )
            self.assert_contract_error(root, "null lease-duration rejection")

    def test_cross_scope_receipt_reference_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(
                path,
                "ADD CONSTRAINT memory_query_audit_receipt_scope_fkey\n"
                "  FOREIGN KEY (tenant_id, security_domain, receipt_id)\n"
                "  REFERENCES memory_receipts (tenant_id, security_domain, receipt_id)",
                "ADD CONSTRAINT memory_query_audit_receipt_scope_fkey\n"
                "  FOREIGN KEY (receipt_id)\n"
                "  REFERENCES memory_receipts (receipt_id)",
            )
            self.assert_contract_error(
                root, "tenant/domain-bound receipt reference for memory_query_audit"
            )
            self.assert_contract_error(root, "receipt references must never use receipt_id alone")

    def test_legacy_receipt_reference_reset_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(
                path,
                "constraint_entry.confrelid = 'public.memory_receipts'::regclass",
                "constraint_entry.confrelid = 'public.memory_records'::regclass",
            )
            self.assert_contract_error(root, "receipt foreign-key reset is missing receipt target")

    def test_missing_fixed_search_path_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "SET search_path = public, pg_temp\n", "")
            self.assert_contract_error(root, "fixed search_path")

    def test_missing_skip_locked_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "FOR UPDATE SKIP LOCKED", "FOR UPDATE")
            self.assert_contract_error(root, "locked candidate selection")

    def test_destructive_table_drop_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "COMMIT;", "DROP TABLE memory_records;\n\nCOMMIT;")
            self.assert_contract_error(root, "forbidden migration operation: DROP TABLE")

    def test_rls_disablement_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "COMMIT;",
                "ALTER TABLE memory_records DISABLE ROW LEVEL SECURITY;\n\nCOMMIT;",
            )
            self.assert_contract_error(root, "forbidden migration operation: RLS disablement")

    def test_bom_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
            self.assert_contract_error(root, "UTF-8 BOM is forbidden")


if __name__ == "__main__":
    unittest.main()
