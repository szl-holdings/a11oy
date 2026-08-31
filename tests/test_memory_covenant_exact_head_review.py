# SPDX-License-Identifier: Apache-2.0
"""Regression guards for the 2026-08-26 exact-head Memory review."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "migrations" / "20260820_memory_covenant_v2_postmerge_hardening.sql"


def _source() -> str:
    return MIGRATION.read_text(encoding="utf-8")


def test_stale_policies_are_dropped_before_force_rls_and_application_queries() -> None:
    source = _source()
    early_sweep = source.index("A stale RLS policy is executable SQL")
    force_rls = source.index("ALTER TABLE public.memory_records FORCE ROW LEVEL SECURITY")
    audit_preflight = source.index("FROM public.memory_query_audit AS audit")
    policy_create = source.index("CREATE POLICY memory_records_isolation")

    assert early_sweep < force_rls < audit_preflight
    assert early_sweep < policy_create


def test_context_binding_resolves_session_user_by_exact_catalog_name() -> None:
    source = _source()
    helper_start = source.index(
        "CREATE OR REPLACE FUNCTION public.a11oy_memory_context_matches"
    )
    helper_end = source.index(
        "ALTER FUNCTION public.memory_touch_updated_at() OWNER TO CURRENT_USER",
        helper_start,
    )
    helper = source[helper_start:helper_end]

    assert "pg_catalog.to_regrole(session_user)" not in helper
    assert "FROM pg_catalog.pg_roles AS role" in helper
    assert "role.rolname = session_user" in helper
    assert "SELECT role.oid" in helper


def test_policy_sweep_includes_every_covenant_relation() -> None:
    source = _source()
    early_start = source.index("A stale RLS policy is executable SQL")
    early_end = source.index("A stale function owner", early_start)
    sweep = source[early_start:early_end]
    for relation in (
        "memory_records",
        "memory_evidence_refs",
        "memory_outbox",
        "memory_receipts",
        "memory_query_audit",
        "memory_index_generations",
        "memory_idempotency",
        "memory_context_bindings",
    ):
        assert f"'{relation}'" in sweep
