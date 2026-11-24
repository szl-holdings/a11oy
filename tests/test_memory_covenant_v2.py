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
        for relative in validator.REQUIRED_FILES:
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
            (root / validator.CORRECTIVE_MIGRATION).unlink()
            self.assert_contract_error(root, "missing required migration")

    def test_tenant_table_without_force_rls_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "ALTER TABLE public.memory_records FORCE ROW LEVEL SECURITY;\n", "")
            self.assert_contract_error(root, "FORCE RLS for memory_records")

    def test_outbox_force_rls_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(
                path,
                "ALTER TABLE public.memory_outbox ENABLE ROW LEVEL SECURITY;\n",
                "ALTER TABLE public.memory_outbox ENABLE ROW LEVEL SECURITY;\n"
                "ALTER TABLE public.memory_outbox FORCE ROW LEVEL SECURITY;\n",
            )
            self.assert_contract_error(root, "memory_outbox must not use FORCE RLS")

    def test_missing_tenant_policy_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "CREATE POLICY memory_records_isolation ON public.memory_records\n", "CREATE POLICY memory_records_other ON public.memory_records\n")
            self.assert_contract_error(root, "isolation policy for memory_records")

    def test_policy_without_with_check_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(
                path,
                "CREATE POLICY memory_records_isolation ON public.memory_records\n"
                "USING (public.a11oy_memory_context_matches(tenant_id, security_domain))\n"
                "WITH CHECK (public.a11oy_memory_context_matches(tenant_id, security_domain));",
                "CREATE POLICY memory_records_isolation ON public.memory_records\n"
                "USING (public.a11oy_memory_context_matches(tenant_id, security_domain));",
            )
            self.assert_contract_error(root, "policy must bind USING and WITH CHECK")

    def test_append_only_trigger_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(
                path,
                "CREATE TRIGGER memory_receipts_append_only BEFORE UPDATE OR DELETE ON public.memory_receipts\n"
                "FOR EACH ROW EXECUTE FUNCTION public.memory_reject_mutation();\n",
                "",
            )
            self.assert_contract_error(root, "append-only trigger for memory_receipts")

    def test_append_only_sqlstate_change_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "ERRCODE='55000'", "ERRCODE='P0001'")
            self.assert_contract_error(root, "append-only SQLSTATE 55000")

    def test_corrective_append_only_helper_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(path, "CREATE OR REPLACE FUNCTION public.memory_reject_mutation()", "CREATE OR REPLACE FUNCTION public.memory_accept_mutation()")
            self.assert_contract_error(root, "corrective append-only rejection function")

    def test_corrective_all_trigger_sweep_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(path, "FROM pg_catalog.pg_trigger AS trigger", "FROM pg_catalog.unchecked_trigger AS trigger")
            self.assert_contract_error(root, "corrective all-trigger catalog sweep")

    def test_corrective_trigger_sweep_table_omission_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "               'memory_idempotency',\n               'memory_context_bindings'\n           )\n           AND NOT trigger.tgisinternal",
                "               'memory_idempotency'\n           )\n           AND NOT trigger.tgisinternal",
            )
            self.assert_contract_error(root, "corrective trigger sweep table set differs")

    def test_corrective_force_rls_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(path, "ALTER TABLE public.memory_records FORCE ROW LEVEL SECURITY;\n", "")
            self.assert_contract_error(root, "corrective FORCE RLS for memory_records")

    def test_acceptance_idempotency_append_only_probe_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.ACCEPTANCE
            self.replace_once(path, "        DELETE FROM memory_idempotency\n", "        SELECT * FROM memory_idempotency\n")
            self.assert_contract_error(root, "acceptance append-only idempotency delete probe")

    def test_acceptance_exact_trigger_set_comparison_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.ACCEPTANCE
            self.replace_once(path, "observed_triggers IS DISTINCT FROM expected_triggers", "observed_triggers IS NULL")
            self.assert_contract_error(root, "acceptance exact trigger-set comparison")

    def test_acceptance_rewrite_rule_assertion_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.ACCEPTANCE
            self.replace_once(
                path,
                "Memory Covenant relation retained a user rewrite rule",
                "Memory Covenant rewrite rule state unchecked",
            )
            self.assert_contract_error(root, "rewrite-rule absence assertion")

    def test_acceptance_admin_option_assertion_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.ACCEPTANCE
            self.replace_once(
                path,
                "Memory Covenant capability membership retained ADMIN OPTION",
                "Memory Covenant membership delegation state unchecked",
            )
            self.assert_contract_error(root, "ADMIN OPTION absence assertion")

    def test_acceptance_inbound_membership_assertion_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.ACCEPTANCE
            self.replace_once(
                path,
                "Seeded inbound capability membership was not preserved",
                "Seeded inbound capability membership state unchecked",
            )
            self.assert_contract_error(root, "membership preservation assertion")

    def test_bypass_rls_role_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            text = path.read_text(encoding="utf-8").replace("NOBYPASSRLS", "BYPASSRLS")
            path.write_text(text, encoding="utf-8")
            self.assert_contract_error(root, "must never receive BYPASSRLS")

    def test_login_role_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            text = path.read_text(encoding="utf-8").replace("NOLOGIN", "LOGIN")
            path.write_text(text, encoding="utf-8")
            self.assert_contract_error(root, "must never receive LOGIN")

    def test_application_privilege_expansion_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "GRANT SELECT, INSERT ON TABLE public.memory_outbox TO a11oy_memory_app;", "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.memory_outbox TO a11oy_memory_app;")
            self.assert_contract_error(root, "application table grants differ")

    def test_worker_direct_table_grant_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "COMMIT;", "GRANT SELECT ON TABLE public.memory_outbox TO a11oy_memory_worker;\n\nCOMMIT;")
            self.assert_contract_error(root, "worker role must not receive direct")

    def test_public_grant_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "COMMIT;", "GRANT EXECUTE ON FUNCTION public.memory_lease_outbox(text, integer, integer) TO PUBLIC;\n\nCOMMIT;")
            self.assert_contract_error(root, "must not grant privileges to PUBLIC")

    def test_missing_public_context_function_revoke_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "REVOKE ALL PRIVILEGES ON FUNCTION public.a11oy_memory_context_matches(text, text)\n  FROM PUBLIC;\n", "")
            self.assert_contract_error(root, "PUBLIC context-function revoke")

    def test_unbounded_worker_limit_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "p_limit > 500", "p_limit > 5000")
            self.assert_contract_error(root, "bounded item limit")

    def test_null_worker_limit_bypass_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "p_limit IS NULL OR ", "")
            self.assert_contract_error(root, "NULL item limit rejection")

    def test_unbounded_lease_duration_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "p_lease_seconds > 3600", "p_lease_seconds > 86400")
            self.assert_contract_error(root, "bounded lease duration")

    def test_missing_fixed_search_path_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "SET search_path = pg_catalog, pg_temp\n", "")
            self.assert_contract_error(root, "safe fixed search_path")

    def test_missing_skip_locked_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "FOR UPDATE SKIP LOCKED", "FOR UPDATE")
            self.assert_contract_error(root, "locked candidate selection")

    def test_worker_superuser_normalization_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "CREATE ROLE a11oy_memory_worker\n          NOSUPERUSER NOCREATEDB NOCREATEROLE NOLOGIN\n", "CREATE ROLE a11oy_memory_worker\n          SUPERUSER NOCREATEDB NOCREATEROLE NOLOGIN\n")
            self.assert_contract_error(root, "must never receive SUPERUSER")

    def test_notice_only_role_failure_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "COMMIT;", "DO $$ BEGIN NULL; EXCEPTION WHEN insufficient_privilege THEN RAISE NOTICE 'ignored'; END; $$;\n\nCOMMIT;")
            self.assert_contract_error(root, "must fail closed, not raise notice")

    def test_stale_policy_sweep_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "SELECT c.relname AS table_name, p.polname AS policy_name\n"
                "          FROM pg_catalog.pg_policy AS p",
                "SELECT c.relname AS table_name, p.polname AS policy_name\n"
                "          FROM pg_catalog.pg_policy_without_sweep AS p",
            )
            self.assert_contract_error(root, "cannot inspect corrective covenant-policy sweep")

    def test_stale_rewrite_rule_sweep_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "FROM pg_catalog.pg_rewrite AS rewrite",
                "FROM pg_catalog.pg_rewrite_without_sweep AS rewrite",
            )
            self.assert_contract_error(root, "rewrite-rule catalog sweep")

    def test_inbound_admin_option_revoke_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "REVOKE ADMIN OPTION FOR %I FROM %I CASCADE",
                "REVOKE %I FROM %I CASCADE",
            )
            self.assert_contract_error(root, "delegation-right revoke")

    def test_delegated_inbound_inherit_disable_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "GRANT %I TO %I WITH INHERIT FALSE, SET FALSE, ADMIN FALSE",
                "GRANT %I TO %I WITH INHERIT TRUE, ADMIN TRUE",
            )
            self.assert_contract_error(root, "delegated inbound inherit disable")

    def test_tenant_bound_receipt_relationship_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "CONSTRAINT memory_query_audit_tenant_domain_receipt_fkey\n", "CONSTRAINT memory_query_audit_receipt_only_fkey\n")
            self.assert_contract_error(root, "audit tenant/domain receipt foreign key")

    def test_cross_domain_receipt_preflight_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(path, "memory_idempotency contains a cross-domain receipt reference", "memory_idempotency relationship unchecked")
            self.assert_contract_error(root, "cross-domain preflight")

    def test_subtractive_acl_reset_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "relation.relacl,", "relation.unchecked_acl,")
            self.assert_contract_error(root, "table ACL catalog sweep")

    def test_stale_function_acl_audit_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "'public.memory_touch_updated_at()'::pg_catalog.regprocedure,", "'public.unchecked_touch_updated_at()'::pg_catalog.regprocedure,")
            self.assert_contract_error(root, "function ACL target")

    def test_inherited_capability_membership_sweep_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "child.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')",
                "child.rolname IN ('a11oy_memory_unchecked')",
            )
            self.assert_contract_error(root, "capability membership selector")

    def test_stale_schema_create_sweep_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "REVOKE CREATE ON SCHEMA public FROM %I CASCADE", "REVOKE USAGE ON SCHEMA public FROM %I CASCADE")
            self.assert_contract_error(root, "stale schema CREATE revoke")

    def test_column_acl_sweep_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.attacl) AS acl", "CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.unchecked_acl) AS acl")
            self.assert_contract_error(root, "column ACL catalog sweep")

    def test_context_binding_table_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(path, "CREATE TABLE IF NOT EXISTS public.memory_context_bindings (", "CREATE TABLE IF NOT EXISTS public.memory_unbound_contexts (")
            self.assert_contract_error(root, "owner-only context binding table")

    def test_base_durable_provenance_preflight_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "    IF EXISTS (SELECT 1 FROM public.memory_context_bindings) THEN", "    IF false THEN")
            self.assert_contract_error(root, "unconditional durable-provenance preflight")

    def test_corrective_durable_provenance_preflight_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(path, "    IF EXISTS (SELECT 1 FROM public.memory_context_bindings) THEN", "    IF false THEN")
            self.assert_contract_error(root, "unconditional durable-provenance preflight")

    def test_base_context_binding_no_force_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "ALTER TABLE public.memory_context_bindings NO FORCE ROW LEVEL SECURITY;\n", "")
            self.assert_contract_error(root, "RLS-independent context-binding preflight")

    def test_corrective_context_binding_no_force_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(path, "ALTER TABLE public.memory_context_bindings NO FORCE ROW LEVEL SECURITY;\n", "")
            self.assert_contract_error(root, "RLS-independent context-binding preflight")

    def test_corrective_context_binding_no_force_must_precede_preflight(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            text = path.read_text(encoding="utf-8")
            statement = "ALTER TABLE public.memory_context_bindings NO FORCE ROW LEVEL SECURITY;\n"
            text = text.replace(statement, "", 1)
            marker = "END;\n$$;\n\nALTER TABLE public.memory_records OWNER TO CURRENT_USER;\n"
            self.assertEqual(text.count(marker), 1)
            path.write_text(text.replace(marker, "END;\n$$;\n\n" + statement + "ALTER TABLE public.memory_records OWNER TO CURRENT_USER;\n", 1), encoding="utf-8")
            self.assert_contract_error(root, "inspect physical rows before other mutation")

    def test_base_durable_provenance_preflight_cannot_be_conditional(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "    IF EXISTS (SELECT 1 FROM public.memory_context_bindings) THEN", "    IF EXISTS (SELECT 1 FROM public.memory_context_bindings)\n       AND current_user = 'trusted-looking-owner' THEN")
            self.assert_contract_error(root, "unconditional durable-provenance preflight")

    def test_corrective_durable_provenance_preflight_cannot_be_conditional(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(path, "    IF EXISTS (SELECT 1 FROM public.memory_context_bindings) THEN", "    IF EXISTS (SELECT 1 FROM public.memory_context_bindings)\n       AND current_user = 'trusted-looking-owner' THEN")
            self.assert_contract_error(root, "unconditional durable-provenance preflight")

    def test_base_durable_provenance_error_identity_is_pinned(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "rows lack durable write provenance", "rows accepted after catalog inspection")
            self.assert_contract_error(root, "unconditional durable-provenance preflight")

    def test_corrective_durable_provenance_error_identity_is_pinned(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(path, "rows lack durable write provenance", "rows accepted after catalog inspection")
            self.assert_contract_error(root, "unconditional durable-provenance preflight")

    def test_base_catalog_state_cannot_substitute_for_write_provenance(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "DO $$\nBEGIN\n    IF EXISTS (SELECT 1 FROM public.memory_context_bindings) THEN", "DO $$\nDECLARE\n    helper_was_authenticated boolean := true;\nBEGIN\n    IF EXISTS (SELECT 1 FROM public.memory_context_bindings)\n       AND NOT helper_was_authenticated THEN")
            self.assert_contract_error(root, "current catalog state")

    def test_corrective_catalog_state_cannot_substitute_for_write_provenance(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(path, "DO $$\nBEGIN\n    IF EXISTS (SELECT 1 FROM public.memory_context_bindings) THEN", "DO $$\nDECLARE\n    helper_was_authenticated boolean := true;\nBEGIN\n    IF EXISTS (SELECT 1 FROM public.memory_context_bindings)\n       AND NOT helper_was_authenticated THEN")
            self.assert_contract_error(root, "current catalog state")

    def test_stale_context_table_owner_convergence_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(path, "ALTER TABLE public.memory_context_bindings OWNER TO CURRENT_USER;\n", "")
            self.assert_contract_error(root, "trusted owner convergence")

    def test_context_function_without_session_binding_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(
                path,
                "          WHERE binding.principal_oid = (\n"
                "                    SELECT role.oid\n"
                "                      FROM pg_catalog.pg_roles AS role\n"
                "                     WHERE role.rolname = session_user\n"
                "                )",
                "          WHERE binding.principal_oid = (\n"
                "                    SELECT role.oid\n"
                "                      FROM pg_catalog.pg_roles AS role\n"
                "                     WHERE role.rolname = current_user\n"
                "                )",
            )
            self.assert_contract_error(root, "exact catalog session principal binding")

    def test_context_function_regrole_reparse_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(
                path,
                "          WHERE binding.principal_oid = (\n"
                "                    SELECT role.oid\n"
                "                      FROM pg_catalog.pg_roles AS role\n"
                "                     WHERE role.rolname = session_user\n"
                "                )",
                "          WHERE binding.principal_oid = pg_catalog.to_regrole(session_user)",
            )
            self.assert_contract_error(root, "must not reparse session_user as regrole text")

    def test_context_function_without_security_definer_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "RETURNS boolean LANGUAGE sql STABLE SECURITY DEFINER\n", "RETURNS boolean LANGUAGE sql STABLE\n")
            self.assert_contract_error(root, "SECURITY DEFINER")

    def test_workflow_merge_ref_checkout_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            text = path.read_text(encoding="utf-8").replace("          ref: ${{ github.event.pull_request.head.sha || github.sha }}\n", "")
            path.write_text(text, encoding="utf-8")
            self.assert_contract_error(root, "requested-head checkout binding")

    def test_workflow_without_dirty_membership_seed_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(path, "GRANT a11oy_memory_stale_parent\n", "GRANT a11oy_memory_unchecked_parent\n")
            self.assert_contract_error(root, "stale capability parent seed")

    def test_workflow_without_substring_spoof_seed_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(path, "            -- public.memory_context_bindings\n", "")
            self.assert_contract_error(root, "substring-spoofed historical helper seed")

    def test_workflow_without_revoked_binding_grant_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(path, "          REVOKE ALL PRIVILEGES (principal_oid, tenant_id, security_domain)\n", "          -- revoked-grant adversary removed\n")
            self.assert_contract_error(root, "temporary binding column ACL revoke")

    def test_workflow_without_revoked_binding_acl_assertion_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(path, '          test "$revoked_binding_acl_count" = "0"\n', "")
            self.assert_contract_error(root, "revoked binding column ACL assertion")

    def test_workflow_without_temporary_binding_policy_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(path, "          CREATE POLICY memory_context_bindings_temporary_insert\n", "          CREATE POLICY memory_context_bindings_unchecked_insert\n")
            self.assert_contract_error(root, "temporary binding RLS policy seed")

    def test_workflow_without_revoked_binding_policy_assertion_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(path, '          test "$revoked_binding_policy_count" = "0"\n', "")
            self.assert_contract_error(root, "revoked binding RLS policy assertion")

    def test_workflow_without_planted_binding_rollback_assertion_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(path, '          test "$planted_binding_count" = "1"\n', "")
            self.assert_contract_error(root, "planted binding rollback assertion")

    def test_workflow_without_forced_rls_binding_adversary_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(path, "          ALTER TABLE public.memory_context_bindings FORCE ROW LEVEL SECURITY;\n", "")
            self.assert_contract_error(root, "forced-RLS binding adversary")

    def test_workflow_without_rls_hidden_binding_assertion_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(path, '          test "$hidden_binding_count" = "0"\n', "")
            self.assert_contract_error(root, "RLS-hidden binding reproduction")

    def test_workflow_without_non_superuser_preflight_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(path, "            printf '%s\\n' 'SET ROLE a11oy_memory_stale_owner;'\n", "            printf '%s\\n' 'SELECT current_user;'\n")
            self.assert_contract_error(root, "non-superuser provenance preflight")

    def test_workflow_without_rejected_preflight_atomicity_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(path, '          test "$binding_rls_state" = "true:true"\n', "")
            self.assert_contract_error(root, "rejected-preflight RLS rollback assertion")

    def test_acceptance_without_context_no_force_assertion_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.ACCEPTANCE
            self.replace_once(path, "memory_context_bindings must remain NO FORCE RLS for owner-unfiltered provenance checks", "memory_context_bindings RLS state unchecked")
            self.assert_contract_error(root, "acceptance context-binding NO FORCE RLS assertion")

    def test_acceptance_without_context_policy_cleanup_assertion_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.ACCEPTANCE
            self.replace_once(path, "memory_context_bindings retained a stale RLS policy", "memory_context_bindings policy state unchecked")
            self.assert_contract_error(root, "acceptance context-binding policy cleanup assertion")

    def test_workflow_without_corrective_only_acceptance_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            text = path.read_text(encoding="utf-8")
            start = text.index("          echo '=== corrective-only acceptance ==='")
            end = text.index("          echo '=== full second pass ==='", start)
            path.write_text(text[:start] + text[end:], encoding="utf-8")
            self.assert_contract_error(root, "corrective-only acceptance")

    def test_stale_context_function_owner_convergence_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "ALTER FUNCTION public.a11oy_memory_context_matches(text, text)\n  OWNER TO CURRENT_USER;\n", "")
            self.assert_contract_error(root, "context-function owner convergence")

    def test_unqualified_schema_target_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "CREATE TABLE IF NOT EXISTS public.memory_records (", "CREATE TABLE IF NOT EXISTS memory_records (")
            self.assert_contract_error(root, "unqualified memory table DDL")

    def test_corrective_migration_unsafe_search_path_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(path, "SET LOCAL search_path = pg_catalog, pg_temp;", "SET LOCAL search_path = public, pg_temp;")
            self.assert_contract_error(root, "safe migration search_path")

    def test_destructive_table_drop_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "COMMIT;", "DROP TABLE public.memory_records;\n\nCOMMIT;")
            self.assert_contract_error(root, "forbidden migration operation: DROP TABLE")

    def test_rls_disablement_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "COMMIT;", "ALTER TABLE public.memory_records DISABLE ROW LEVEL SECURITY;\n\nCOMMIT;")
            self.assert_contract_error(root, "forbidden migration operation: RLS disablement")

    def test_bom_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
            self.assert_contract_error(root, "UTF-8 BOM is forbidden")

    # Provider-owner compatibility: a provider-managed owner is not expected to
    # hold the superuser attribute (for Neon and similar providers this is
    # MODELED, not read back), so every role change must be one a project
    # owner can make, and every sweep must be proven rather than trusted.

    def test_combined_superuser_alter_reintroduction_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "ALTER ROLE a11oy_memory_app NOSUPERUSER;",
                "ALTER ROLE a11oy_memory_app NOSUPERUSER NOCREATEDB NOCREATEROLE "
                "NOLOGIN NOREPLICATION INHERIT NOBYPASSRLS;",
            )
            self.assert_contract_error(root, "cannot run under a provider-managed owner")

    def test_unguarded_attribute_convergence_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "IF observed.rolcreatedb THEN ALTER ROLE a11oy_memory_worker NOCREATEDB; END IF;",
                "ALTER ROLE a11oy_memory_worker NOCREATEDB;",
            )
            self.assert_contract_error(
                root, "guarded NOCREATEDB convergence for a11oy_memory_worker"
            )

    def test_superuser_attribute_branch_without_fail_closed_raise_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "RAISE EXCEPTION USING ERRCODE = '42501',\n"
                "              MESSAGE = 'a11oy_memory_app holds an attribute this "
                "migration principal cannot clear';",
                "NULL;",
            )
            self.assert_contract_error(
                root, "fail-closed superuser-attribute convergence for a11oy_memory_app"
            )

    def test_provider_owner_admin_exemption_widening_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "           AND member.rolname <> CURRENT_USER\n    LOOP",
                "           AND member.rolname <> CURRENT_USER OR TRUE\n    LOOP",
            )
            self.assert_contract_error(
                root, "ADMIN retention limited to the migration principal"
            )

    def test_inbound_convergence_assertion_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "capability-role delegation survived the sweep; another grantor holds it",
                "capability-role delegation state unchecked",
            )
            self.assert_contract_error(root, "inbound delegation convergence assertion")

    def test_notice_only_convergence_assertion_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "RAISE EXCEPTION USING ERRCODE = '42501',\n"
                "          MESSAGE = 'a capability role still belongs to a parent role "
                "this principal could not revoke';",
                "RAISE WARNING 'a capability role still belongs to a parent role "
                "this principal could not revoke';",
            )
            self.assert_contract_error(root, "fail-closed convergence assertion")

    def test_convergence_assertions_before_sweeps_fail(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            text = path.read_text(encoding="utf-8")
            start = text.index("-- A principal that is not a superuser can revoke only")
            end = text.index("$$;\n", start) + len("$$;\n")
            block = text[start:end]
            text = text[:start] + text[end:]
            anchor = text.index("-- Capability roles must not inherit or SET ROLE")
            path.write_text(text[:anchor] + block + "\n" + text[anchor:], encoding="utf-8")
            self.assert_contract_error(root, "must follow both sweeps")

    def test_acceptance_admin_exemption_widening_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.ACCEPTANCE
            self.replace_once(
                path,
                "           AND edge.admin_option\n"
                "           AND edge.member <> (\n"
                "               SELECT relation.relowner\n"
                "                 FROM pg_catalog.pg_class AS relation\n"
                "                WHERE relation.oid = 'public.memory_records'::pg_catalog.regclass",
                "           AND edge.admin_option\n"
                "           AND edge.member <> (\n"
                "               SELECT relation.relowner\n"
                "                 FROM pg_catalog.pg_class AS relation\n"
                "                WHERE relation.relname LIKE 'memory_%'",
            )
            self.assert_contract_error(root, "exemption limited to the covenant owner")

    def test_provider_owner_fixture_must_stay_non_superuser(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(
                path,
                "CREATE ROLE a11oy_memory_provider_owner LOGIN NOSUPERUSER",
                "CREATE ROLE a11oy_memory_provider_owner LOGIN SUPERUSER",
            )
            self.assert_contract_error(root, "non-superuser provider owner fixture")

    # Review findings on the provider-owner change. Each test is one concrete
    # edit that previously passed every static gate.

    def test_attribute_read_without_row_lock_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(path, "        ALTER ROLE a11oy_memory_app NOCREATEROLE;\n", "")
            self.assert_contract_error(
                root, "catalog row lock before reading attributes of a11oy_memory_app"
            )

    def test_observed_record_assignment_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "         WHERE role.rolname = 'a11oy_memory_app';\n"
                "        -- Name only the attributes that deviate.\n",
                "         WHERE role.rolname = 'a11oy_memory_app';\n"
                "        observed.rolbypassrls := observed.rolbypassrls AND observed.rolsuper;\n"
                "        -- Name only the attributes that deviate.\n",
            )
            self.assert_contract_error(
                root, "pinned attribute convergence for a11oy_memory_app"
            )

    def test_sweep_name_pattern_exemption_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "         WHERE parent.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')\n"
                "           AND edge.admin_option\n",
                "         WHERE parent.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')\n"
                "           AND member.rolname NOT LIKE 'a11oy\\_memory\\_ops%'\n"
                "           AND edge.admin_option\n",
            )
            self.assert_contract_error(root, "pinned inbound delegation sweep")

    def test_assertion_name_pattern_exemption_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "           AND edge.admin_option\n"
                "           AND holder.rolname <> CURRENT_USER\n",
                "           AND edge.admin_option\n"
                "           AND holder.rolname <> CURRENT_USER\n"
                "           AND holder.rolname NOT LIKE 'a11oy\\_memory\\_ops%'\n",
            )
            self.assert_contract_error(
                root, "pinned membership and attribute convergence assertions"
            )

    def test_acceptance_name_pattern_exemption_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.ACCEPTANCE
            self.replace_once(
                path,
                "           AND edge.admin_option\n           AND edge.member <> (\n",
                "           AND pg_get_userbyid(edge.member) NOT LIKE 'a11oy\\_memory\\_ops%'\n"
                "           AND edge.admin_option\n           AND edge.member <> (\n",
            )
            self.assert_contract_error(root, "exemption limited to the covenant owner")

    def test_reordered_superuser_alter_outside_convergence_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "-- Capability roles must not inherit or SET ROLE into any historical parent.\n",
                "ALTER ROLE a11oy_memory_worker WITH NOLOGIN NOSUPERUSER;\n\n"
                "-- Capability roles must not inherit or SET ROLE into any historical parent.\n",
            )
            self.assert_contract_error(
                root, "capability roles are altered outside the pinned convergence"
            )

    def test_alter_user_form_outside_convergence_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "-- Capability roles must not inherit or SET ROLE into any historical parent.\n",
                "ALTER USER a11oy_memory_app NOSUPERUSER;\n\n"
                "-- Capability roles must not inherit or SET ROLE into any historical parent.\n",
            )
            self.assert_contract_error(
                root, "capability roles are altered outside the pinned convergence"
            )

    def test_swept_delegate_set_option_retention_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "'GRANT %I TO %I WITH INHERIT FALSE, SET FALSE, ADMIN FALSE',",
                "'GRANT %I TO %I WITH INHERIT FALSE, ADMIN FALSE',",
            )
            self.assert_contract_error(root, "pinned inbound delegation sweep")

    def test_set_survivor_assertion_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "a swept capability-role delegate keeps SET or INHERIT through another grant",
                "a swept capability-role delegate state unchecked",
            )
            self.assert_contract_error(
                root, "fail-closed convergence assertion (a swept capability-role"
            )

    def test_attribute_convergence_assertion_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "                OR capability.rolbypassrls)\n",
                "                OR FALSE)\n",
            )
            self.assert_contract_error(
                root, "pinned membership and attribute convergence assertions"
            )

    def test_row_security_precondition_weakening_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "           AND (principal.rolsuper OR principal.rolbypassrls)\n",
                "           AND (principal.rolsuper OR TRUE)\n",
            )
            self.assert_contract_error(root, "pinned migration-principal precondition")

    def test_principal_precondition_must_open_the_transaction(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "SET LOCAL search_path = pg_catalog, pg_temp;\n",
                "SET LOCAL search_path = pg_catalog, pg_temp;\nSELECT 1;\n",
            )
            self.assert_contract_error(
                root, "must open with the pinned migration-principal precondition"
            )

    def test_acceptance_receipt_row_validity_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.ACCEPTANCE
            self.replace_once(
                path,
                "A tenant/domain receipt reference does not resolve",
                "tenant/domain receipt rows unchecked",
            )
            self.assert_contract_error(
                root, "acceptance tenant/domain receipt row validity assertion"
            )

    def test_acceptance_set_survivor_removal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.ACCEPTANCE
            self.replace_once(
                path,
                "A swept capability-role delegate keeps SET or INHERIT through another grant",
                "swept delegate state unchecked",
            )
            self.assert_contract_error(
                root, "acceptance swept-delegate SET or INHERIT survivor assertion"
            )

    def test_workflow_without_provider_refusals_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(
                path,
                "=== provider-owner convergence and fail-closed refusals ===",
                "=== provider-owner smoke ===",
            )
            self.assert_contract_error(root, "provider-owner refusal marker")

    def test_workflow_refusal_that_tolerates_success_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(
                path,
                'if apply_as "$principal" "$migration" "$database" > "$out" 2>&1; then',
                "if false; then",
            )
            self.assert_contract_error(root, "expected refusals must fail the migration")

    def test_workflow_fixed_name_hostile_delegate_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(
                path,
                'hostile_delegate="$(random_role)"',
                'hostile_delegate="a11oy_hostile_delegate_fixed"',
            )
            self.assert_contract_error(
                root, "seeded delegate hostile_delegate must be named by random_role"
            )

    # Second review of the provider-owner change. The validator now lexes SQL
    # the way psql and PostgreSQL do; each test below is an edit that passed
    # every static gate when comments were stripped by regular expression.

    def test_lexer_follows_postgresql_quoting_and_comments(self) -> None:
        def kinds(sql: str) -> list[str]:
            return [
                token.kind
                for token in validator._lex(sql)
                if token.kind not in validator.SKIPPED_TOKENS
            ]

        self.assertEqual(kinds("SELECT 'a -- b''c' ;"), ["word", "string", "punct"])
        self.assertEqual(kinds("SELECT E'a\\' -- b' ;"), ["word", "string", "punct"])
        self.assertEqual(kinds('SELECT "x -- y" ;'), ["word", "identifier", "punct"])
        self.assertEqual(kinds("/* a /* b */ c */ SELECT 1"), ["word", "number"])
        self.assertEqual(kinds("SELECT a$$, $$x -- y$$"), ["word", "word", "punct", "dollar"])
        self.assertEqual(kinds("SELECT 1::int"), ["word", "number", "punct", "word"])
        with self.assertRaises(validator.SqlLexError):
            validator._lex("/* /* */ SELECT 1")
        with self.assertRaises(validator.SqlLexError):
            validator._lex("SELECT 'unterminated")

    def test_dashdash_inside_literal_cannot_hide_capability_alter(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "-- Revoke first so reapplication converges from stale additive ACLs.",
                "SELECT 'roles / --';\n"
                "ALTER ROLE a11oy_memory_app BYPASSRLS;\n"
                "SELECT ' / normalized';\n\n"
                "-- Revoke first so reapplication converges from stale additive ACLs.",
            )
            self.assert_contract_error(root, "corrective memory roles must never receive BYPASSRLS")
            self.assert_contract_error(
                root, "corrective capability roles are altered outside the pinned convergence"
            )

    def test_nested_block_comment_cannot_stand_in_for_the_precondition(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            text = path.read_text(encoding="utf-8")
            start = text.index(
                "DO $$\nBEGIN\n    IF NOT EXISTS (\n        SELECT 1\n"
                "          FROM pg_catalog.pg_roles AS principal"
            )
            end = text.index("$$;\n", start) + len("$$;\n")
            # Block comments nest, so everything up to "-- */" is one comment
            # and PostgreSQL never runs the precondition.
            path.write_text(
                text[:start] + "/* /* */\n" + text[start:end] + "/* */\n-- */\n" + text[end:],
                encoding="utf-8",
            )
            self.assert_contract_error(
                root, "hardening must open with the pinned migration-principal precondition"
            )
            self.assert_contract_error(
                root, "hardening pinned migration-principal precondition: expected 1 exact copy, found 0"
            )

    def test_pinned_sweep_copied_into_dollar_literal_does_not_count(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "         WHERE parent.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')\n"
                "           AND edge.admin_option\n",
                "         WHERE parent.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')\n"
                "           AND member.rolname NOT LIKE 'z%'\n"
                "           AND edge.admin_option\n",
            )
            self.replace_once(
                path,
                "COMMIT;",
                "SELECT $$" + validator.PINNED_INBOUND_SWEEP + "$$ AS reviewed;\n\nCOMMIT;",
            )
            self.assert_contract_error(
                root,
                "corrective pinned inbound delegation sweep: expected 1 exact copy "
                "inside a top-level DO body, found 0",
            )

    def test_pinned_assertions_copied_into_dollar_literal_do_not_count(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            text = path.read_text(encoding="utf-8")
            start = text.index(
                "DO $$\nBEGIN\n    IF EXISTS (\n        SELECT 1\n"
                "          FROM pg_catalog.pg_auth_members AS edge\n"
                "          JOIN pg_catalog.pg_roles AS capability ON capability.oid = edge.member"
            )
            end = text.index("$$;\n", start) + len("$$;\n")
            body = text[start + len("DO $$") : end - len("$$;\n")]
            path.write_text(
                text[:start] + "SELECT $$" + body + "$$ AS reviewed;\n" + text[end:],
                encoding="utf-8",
            )
            self.assert_contract_error(
                root,
                "hardening pinned membership and attribute convergence assertions: "
                "expected 1 exact copy, found 0",
            )

    def test_tagged_dollar_quote_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            text = path.read_text(encoding="utf-8")
            start = text.index(
                "DO $$\nBEGIN\n    IF EXISTS (\n        SELECT 1\n"
                "          FROM pg_catalog.pg_auth_members AS edge\n"
                "          JOIN pg_catalog.pg_roles AS capability ON capability.oid = edge.member"
            )
            end = text.index("$$;\n", start) + len("$$;\n")
            path.write_text(
                text[:start]
                + "SELECT $assertions$\n"
                + text[start:end]
                + "$assertions$ AS reviewed;\n"
                + text[end:],
                encoding="utf-8",
            )
            self.assert_contract_error(root, "uses a tagged dollar quote $assertions$")
            self.assert_contract_error(
                root,
                "corrective pinned membership and attribute convergence assertions: "
                "expected 1 exact copy, found 0",
            )

    def test_tagged_dollar_quote_in_acceptance_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.ACCEPTANCE
            self.replace_once(path, "ROLLBACK;", "SELECT $note$ reviewed $note$;\nROLLBACK;")
            self.assert_contract_error(root, "uses a tagged dollar quote $note$")

    def test_pinned_convergence_copied_into_function_body_does_not_count(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "        IF observed.rolbypassrls THEN ALTER ROLE a11oy_memory_app NOBYPASSRLS; END IF;\n",
                "",
            )
            self.replace_once(
                path,
                "COMMIT;",
                "CREATE OR REPLACE FUNCTION public.memory_reviewed_copy()\n"
                "RETURNS void LANGUAGE plpgsql\n"
                "SET search_path = pg_catalog, pg_temp\n"
                "AS $$\nDECLARE\n    observed record;\nBEGIN\n"
                + validator.PINNED_ROLE_CONVERGENCE.format(role="a11oy_memory_app")
                + "END;\n$$;\n\nCOMMIT;",
            )
            self.assert_contract_error(
                root,
                "hardening pinned attribute convergence for a11oy_memory_app: expected 1 "
                "exact copy inside a top-level DO body, found 0",
            )

    def test_dead_code_around_pinned_sweep_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "BEGIN\n    FOR membership IN\n        SELECT DISTINCT parent.rolname AS parent_role,",
                "BEGIN\n    IF false THEN\n    FOR membership IN\n"
                "        SELECT DISTINCT parent.rolname AS parent_role,",
            )
            self.replace_once(
                path,
                "            membership.capability_role\n        );\n    END LOOP;\nEND;\n$$;\n\n"
                "-- Preserve inbound memberships.",
                "            membership.capability_role\n        );\n    END LOOP;\n    END IF;\n"
                "END;\n$$;\n\n-- Preserve inbound memberships.",
            )
            self.assert_contract_error(
                root,
                "hardening pinned outbound membership sweep statement: expected 1 exact copy, found 0",
            )

    def test_exception_handler_around_pinned_sweep_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "            membership.member_role\n        );\n    END LOOP;\nEND;\n$$;\n",
                "            membership.member_role\n        );\n    END LOOP;\n"
                "EXCEPTION WHEN OTHERS THEN\n    NULL;\nEND;\n$$;\n",
            )
            self.assert_contract_error(
                root,
                "corrective pinned inbound delegation sweep statement: expected 1 exact copy, found 0",
            )

    def test_identifier_dollar_suffix_is_not_a_dollar_quote(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            # PostgreSQL reads a$$ and b$$ as identifiers, so the ALTER between
            # them runs; a lexer that saw a dollar quote there would hide it.
            self.replace_once(
                path,
                "COMMIT;",
                "SELECT 1 AS a$$;\nALTER ROLE a11oy_memory_app NOINHERIT;\nSELECT 1 AS b$$;\n\nCOMMIT;",
            )
            self.assert_contract_error(
                root, "corrective capability roles are altered outside the pinned convergence"
            )

    def test_psql_meta_command_in_migration_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "COMMIT;", "SELECT 'SELECT 1' \\gexec\n\nCOMMIT;")
            self.assert_contract_error(root, "contains a psql meta-command")

    def test_psql_meta_command_beyond_acceptance_preamble_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.ACCEPTANCE
            self.replace_once(path, "ROLLBACK;", "ROLLBACK;\n\\! true\n")
            self.assert_contract_error(root, "contains a psql meta-command")

    def test_psql_variable_reference_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(path, "COMMIT;", "SELECT :'covenant_role';\n\nCOMMIT;")
            self.assert_contract_error(root, "contains a psql variable reference")

    def test_unicode_escape_identifier_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "COMMIT;",
                'ALTER ROLE U&"a11oy\\005fmemory\\005fapp" NOINHERIT;\n\nCOMMIT;',
            )
            self.assert_contract_error(root, "contains a Unicode-escape literal or identifier")

    def test_string_lexing_change_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "COMMIT;",
                "SET LOCAL standard_conforming_strings = off;\n\nCOMMIT;",
            )
            self.assert_contract_error(root, "must not change how string literals are lexed")

    def test_base_without_principal_precondition_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            text = path.read_text(encoding="utf-8")
            start = text.index(
                "DO $$\nBEGIN\n    IF NOT EXISTS (\n        SELECT 1\n"
                "          FROM pg_catalog.pg_roles AS principal"
            )
            end = text.index("$$;\n", start) + len("$$;\n")
            path.write_text(text[:start] + text[end:], encoding="utf-8")
            self.assert_contract_error(
                root, "base must open with the pinned migration-principal precondition"
            )
            self.assert_contract_error(root, "base pinned migration-principal precondition")

    def test_base_principal_precondition_weakening_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(
                path,
                "           AND (principal.rolsuper OR principal.rolbypassrls)\n",
                "           AND (principal.rolsuper OR TRUE)\n",
            )
            self.assert_contract_error(root, "base pinned migration-principal precondition")

    def test_lease_guard_member_regression_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(
                path,
                "        'a11oy_memory_worker',\n        'USAGE'\n",
                "        'a11oy_memory_worker',\n        'member'\n",
            )
            self.assert_contract_error(root, "hardening memory_lease_outbox missing worker inheritance check")
            self.assert_contract_error(root, "must not admit a session user by MEMBER")
            self.assert_contract_error(root, "hardening pinned bounded lease function")

    def test_lease_guard_widening_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path,
                "        'USAGE'\n    ) THEN\n",
                "        'USAGE'\n    ) AND session_user <> 'a11oy_worker_ops' THEN\n",
            )
            self.assert_contract_error(root, "corrective memory_lease_outbox missing worker inheritance check")
            self.assert_contract_error(root, "corrective pinned bounded lease function")

    def test_new_convergence_assertions_cannot_be_weakened(self) -> None:
        weakenings = (
            (
                validator.CORRECTIVE_MIGRATION,
                "                  AND authority.admin_option\n",
                "                  AND authority.admin_option IS NOT NULL\n",
            ),
            (
                validator.HARDENING_MIGRATION,
                "           AND edge.set_option\n"
                "           AND NOT edge.inherit_option\n"
                "           AND NOT edge.admin_option\n",
                "           AND FALSE\n",
            ),
            (
                validator.CORRECTIVE_MIGRATION,
                "                     WHERE owned_schema.nspowner = capability.oid\n",
                "                     WHERE owned_schema.nspowner = capability.oid\n"
                "                       AND owned_schema.nspname = 'public'\n",
            ),
        )
        for relative, old, new in weakenings:
            with self.subTest(old=old):
                temp, root = self.make_fixture()
                with temp:
                    self.replace_once(root / relative, old, new)
                    self.assert_contract_error(
                        root, "pinned membership and attribute convergence assertions"
                    )

    def test_new_convergence_messages_are_required(self) -> None:
        for message in (
            validator.SET_ONLY_MESSAGE,
            validator.GRANTOR_MESSAGE,
            validator.OWNERSHIP_MESSAGE,
        ):
            with self.subTest(message=message):
                temp, root = self.make_fixture()
                with temp:
                    self.replace_once(
                        root / validator.HARDENING_MIGRATION, message, "state unchecked"
                    )
                    self.assert_contract_error(
                        root, f"hardening fail-closed convergence assertion ({message[:40]})"
                    )

    def test_acceptance_attribute_assertion_weakening_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.ACCEPTANCE
            self.replace_once(path, "               OR rolbypassrls\n", "")
            self.assert_contract_error(root, "acceptance role-attribute assertion")
            self.assert_contract_error(root, "acceptance pinned role and membership assertions")

    def test_acceptance_new_membership_assertions_are_required(self) -> None:
        for message, label in (
            (validator.ACCEPTANCE_SET_ONLY_MESSAGE, "acceptance SET-without-INHERIT membership assertion"),
            (validator.ACCEPTANCE_GRANTOR_MESSAGE, "acceptance grantor-holds-ADMIN assertion"),
            (validator.ACCEPTANCE_OWNERSHIP_MESSAGE, "acceptance capability-role ownership assertion"),
        ):
            with self.subTest(message=message):
                temp, root = self.make_fixture()
                with temp:
                    self.replace_once(root / validator.ACCEPTANCE, message, "state unchecked")
                    self.assert_contract_error(root, label)
                    self.assert_contract_error(
                        root, "acceptance pinned role and membership assertions"
                    )

    def test_capability_grant_outside_sweep_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.CORRECTIVE_MIGRATION
            self.replace_once(
                path, "COMMIT;", "GRANT a11oy_memory_worker TO a11oy_memory_stale_owner;\n\nCOMMIT;"
            )
            self.assert_contract_error(
                root, "corrective capability roles are granted outside the pinned sweep"
            )

    def test_role_creation_outside_convergence_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.HARDENING_MIGRATION
            self.replace_once(path, "COMMIT;", "CREATE ROLE a11oy_memory_shadow NOLOGIN;\n\nCOMMIT;")
            self.assert_contract_error(root, "hardening roles are created outside the pinned convergence")

    def test_role_switch_in_migration_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.BASE_MIGRATION
            self.replace_once(path, "COMMIT;", "SET LOCAL ROLE a11oy_memory_app;\n\nCOMMIT;")
            self.assert_contract_error(root, "forbidden migration operation: role switch")

    def test_workflow_if_condition_fails(self) -> None:
        insertions = (
            (
                "  provider-owner-acceptance:\n"
                "    name: PostgreSQL 18 provider-owner (non-superuser) application\n",
                "    if: ${{ github.event_name == 'workflow_dispatch' }}\n",
            ),
            (
                "      - name: Prove provider-owner convergence and fail-closed refusals\n",
                "        if: ${{ false }}\n",
            ),
            ("      - name: Upload provider-owner evidence\n", "        if: always()\n"),
            ("      - name: Upload provider-owner evidence\n", '        "if": always()\n'),
            ("      - name: Upload provider-owner evidence\n", '        "\\x69f": always()\n'),
            ("      - name: Upload provider-owner evidence\n", "        with: {if: false}\n"),
        )
        for anchor, line in insertions:
            with self.subTest(line=line):
                temp, root = self.make_fixture()
                with temp:
                    self.replace_once(root / validator.WORKFLOW, anchor, anchor + line)
                    self.assert_contract_error(root, "must not contain an if: key")

    def test_workflow_nologin_delegate_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(
                path,
                '-c "CREATE ROLE ${owner_delegate} LOGIN"',
                '-c "CREATE ROLE ${owner_delegate} NOLOGIN"',
            )
            self.assert_contract_error(root, "seeded delegate owner_delegate must be able to log in")

    def test_workflow_prefixed_delegate_name_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(
                path,
                'foreign_delegate="$(random_role)"',
                'foreign_delegate="a11oy_foreign_delegate_${GITHUB_RUN_ID:-local}_${RANDOM}"',
            )
            self.assert_contract_error(
                root, "seeded delegate foreign_delegate must be named by random_role"
            )
            self.assert_contract_error(root, "delegate names must not carry a fixed prefix")

    def test_workflow_state_refusal_against_hardening_only_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(
                path,
                'for migration in "$hardening" "$corrective"; do\n'
                '              expect_refusal a11oy_memory_provider_owner "$migration" "$message"',
                'for migration in "$hardening"; do\n'
                '              expect_refusal a11oy_memory_provider_owner "$migration" "$message"',
            )
            self.assert_contract_error(
                root, "every state refusal also runs against the corrective alone"
            )

    def test_workflow_without_raced_grant_fixture_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(path, 'test "$raced_row_count" = "1"', ":")
            self.assert_contract_error(root, "raced end state present before the refusal")

    def test_workflow_without_base_refusals_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(
                path,
                'for migration in "$base" "$hardening" "$corrective"; do',
                'for migration in "$hardening" "$corrective"; do',
            )
            self.assert_contract_error(root, "base migration refuses principals too")

    def test_workflow_without_database_owning_unbypassed_principal_fails(self) -> None:
        temp, root = self.make_fixture()
        with temp:
            path = root / validator.WORKFLOW
            self.replace_once(
                path,
                "CREATE DATABASE memory_covenant_unbypassed OWNER a11oy_memory_unbypassed_owner",
                "CREATE DATABASE memory_covenant_unbypassed",
            )
            self.assert_contract_error(root, "database-owning principal without BYPASSRLS")


if __name__ == "__main__":
    unittest.main()
