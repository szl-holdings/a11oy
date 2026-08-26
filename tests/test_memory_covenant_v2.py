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
            self.replace_once(path, "FROM pg_catalog.pg_policy AS p", "FROM pg_catalog.pg_policy_without_sweep AS p")
            self.assert_contract_error(root, "all-policy catalog sweep")

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
            self.replace_once(path, "FROM pg_catalog.pg_auth_members AS edge", "FROM pg_catalog.unchecked_auth_members AS edge")
            self.assert_contract_error(root, "role-membership catalog sweep")

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


if __name__ == "__main__":
    unittest.main()
