#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed static contract for the Memory Covenant v2 migrations."""

from __future__ import annotations

import argparse
import functools
import re
from pathlib import Path
from typing import Iterable, NamedTuple

BASE_MIGRATION = Path("migrations/20260811_memory_covenant_v2.sql")
HARDENING_MIGRATION = Path(
    "migrations/20260811_memory_covenant_v2_security_hardening.sql"
)
CORRECTIVE_MIGRATION = Path(
    "migrations/20260820_memory_covenant_v2_postmerge_hardening.sql"
)
MIGRATIONS = (BASE_MIGRATION, HARDENING_MIGRATION, CORRECTIVE_MIGRATION)
WORKFLOW = Path(".github/workflows/memory-covenant-v2.yml")
ACCEPTANCE = Path("tests/memory_covenant_acceptance.sql")
REQUIRED_FILES = MIGRATIONS + (WORKFLOW, ACCEPTANCE)

MEMORY_TABLES = (
    "memory_records",
    "memory_evidence_refs",
    "memory_outbox",
    "memory_receipts",
    "memory_query_audit",
    "memory_index_generations",
    "memory_idempotency",
)
CONTEXT_BINDING_TABLE = "memory_context_bindings"
ALL_COVENANT_TABLES = MEMORY_TABLES + (CONTEXT_BINDING_TABLE,)
FORCE_RLS_TABLES = frozenset(MEMORY_TABLES) - {"memory_outbox"}
APPEND_ONLY_TABLES = (
    "memory_receipts",
    "memory_query_audit",
    "memory_idempotency",
)
EXPECTED_INDEXES = (
    "memory_one_active_generation",
    "memory_records_searchable_idx",
    "memory_records_expiry_idx",
    "memory_outbox_ready_idx",
    "memory_receipts_namespace_idx",
    "memory_query_audit_time_idx",
)
EXPECTED_APP_GRANTS = {
    "memory_records": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "memory_evidence_refs": frozenset({"SELECT", "INSERT", "DELETE"}),
    "memory_outbox": frozenset({"SELECT", "INSERT"}),
    "memory_receipts": frozenset({"SELECT", "INSERT"}),
    "memory_query_audit": frozenset({"SELECT", "INSERT"}),
    "memory_index_generations": frozenset({"SELECT", "INSERT", "UPDATE"}),
    "memory_idempotency": frozenset({"SELECT", "INSERT"}),
}
ROLE_ATTRIBUTES = (
    "NOSUPERUSER",
    "NOCREATEDB",
    "NOCREATEROLE",
    "NOLOGIN",
    "NOREPLICATION",
    "INHERIT",
    "NOBYPASSRLS",
)
# Existing capability roles converge one attribute at a time, and only when the
# catalog shows a deviation. A provider-managed owner is not expected to be a
# superuser (for Neon this is MODELED, not read back), and PostgreSQL rejects
# any ALTER ROLE that names the superuser attribute unless the caller is one,
# even to clear it.
ROLE_CONVERGENCE_STEPS = (
    ("rolsuper", "NOSUPERUSER", False),
    ("rolcreatedb", "NOCREATEDB", False),
    ("rolcanlogin", "NOLOGIN", False),
    ("rolreplication", "NOREPLICATION", False),
    ("rolinherit", "INHERIT", True),
    ("rolbypassrls", "NOBYPASSRLS", False),
)
OUTBOUND_CONVERGENCE_MESSAGE = (
    "a capability role still belongs to a parent role this principal could not revoke"
)
INBOUND_CONVERGENCE_MESSAGE = (
    "capability-role delegation survived the sweep; another grantor holds it"
)
SET_SURVIVOR_MESSAGE = (
    "a swept capability-role delegate keeps SET or INHERIT through another grant"
)
SET_ONLY_MESSAGE = (
    "a capability-role membership grants SET without INHERIT; runtime logins must inherit"
)
GRANTOR_MESSAGE = (
    "a capability-role membership was granted by a role that no longer holds ADMIN on it"
)
OWNERSHIP_MESSAGE = "a capability role owns the database or a schema"
ATTRIBUTE_CONVERGENCE_MESSAGE = "a capability role attribute did not converge"
CONVERGENCE_MESSAGES = (
    OUTBOUND_CONVERGENCE_MESSAGE,
    INBOUND_CONVERGENCE_MESSAGE,
    SET_SURVIVOR_MESSAGE,
    SET_ONLY_MESSAGE,
    GRANTOR_MESSAGE,
    OWNERSHIP_MESSAGE,
    ATTRIBUTE_CONVERGENCE_MESSAGE,
)
ROW_SECURITY_PRECONDITION_MESSAGE = (
    "the migration principal must bypass row security to check existing rows"
)
SCHEMA_OWNER_PRECONDITION_MESSAGE = "the migration principal must own schema public"
PRINCIPAL_PRECONDITION_MESSAGES = (
    ROW_SECURITY_PRECONDITION_MESSAGE,
    SCHEMA_OWNER_PRECONDITION_MESSAGE,
)
LEASE_GUARD_MESSAGE = "session user does not inherit a11oy_memory_worker"
ACCEPTANCE_SET_ONLY_MESSAGE = (
    "Memory Covenant capability membership grants SET without INHERIT"
)
ACCEPTANCE_GRANTOR_MESSAGE = (
    "Memory Covenant capability membership has a grantor without ADMIN"
)
ACCEPTANCE_OWNERSHIP_MESSAGE = (
    "Memory Covenant capability role owns the database or a schema"
)
# psql runs the acceptance; this is the only psql meta-command it may use.
ACCEPTANCE_PSQL_PREAMBLE = r"\set ON_ERROR_STOP on"
# psql reads each line with fgets and keeps it only up to its first NUL, then
# joins the next line; inside a backslash command it treats CR as a space, so
# text after a CR becomes that command's arguments. YAML also breaks lines at
# CR, NEL, U+2028 and U+2029. The lexer and the workflow scan split lines at LF
# alone, so these files may hold no other control character and no Unicode
# line separator. TAB stays legal in SQL, where psql and PostgreSQL read it as
# whitespace.
FORBIDDEN_CHARACTER = re.compile(r"[\x00-\x08\x0b-\x1f\x7f-\x9f\u2028\u2029]")

# Security-critical statements are pinned whole. Substring tokens let an extra
# predicate (for example a name-pattern exemption) slip into a WHERE clause
# while every token still matches; a pinned statement changes only together
# with this validator, in the same reviewed diff.
#
# Pins are compared token by token after lexing the SQL the way psql and
# PostgreSQL do, so whitespace and comments do not matter. A copy inside a
# string literal, a dollar-quoted literal, a function body or a comment is not
# a statement and never counts. Whole statements count only as top-level
# statements. Inner blocks count only inside the body of a top-level
# DO $$ ... $$ statement, and the DO statements that hold them are pinned whole
# as well, so no dead code or exception handler can be wrapped around them.
PINNED_PRINCIPAL_PRECONDITION = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles AS principal
         WHERE principal.rolname = CURRENT_USER
           AND (principal.rolsuper OR principal.rolbypassrls)
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'the migration principal must bypass row security to check existing rows';
    END IF;
    IF NOT EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles AS principal
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.nspname = 'public'
         WHERE principal.rolname = CURRENT_USER
           AND (principal.rolsuper
                OR pg_catalog.pg_has_role(CURRENT_USER, namespace.nspowner, 'USAGE'))
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'the migration principal must own schema public';
    END IF;
END;
$$;
"""
PINNED_TRANSACTION_PREAMBLE = """
BEGIN;
SET LOCAL search_path = pg_catalog, pg_temp;
"""
PINNED_ROLE_CONVERGENCE = """
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = '{role}') THEN
        CREATE ROLE {role}
          NOSUPERUSER NOCREATEDB NOCREATEROLE NOLOGIN
          NOREPLICATION INHERIT NOBYPASSRLS;
    ELSE
        IF EXISTS (
            SELECT 1
              FROM pg_catalog.pg_roles AS role
             WHERE role.rolname = '{role}'
               AND role.rolsuper
        ) AND NOT EXISTS (
            SELECT 1
              FROM pg_catalog.pg_roles AS principal
             WHERE principal.rolname = CURRENT_USER
               AND principal.rolsuper
        ) THEN
            RAISE EXCEPTION USING ERRCODE = '42501',
              MESSAGE = '{role} holds an attribute this migration principal cannot clear';
        END IF;
        ALTER ROLE {role} NOCREATEROLE;
        SELECT role.rolsuper, role.rolcreatedb, role.rolcanlogin,
               role.rolreplication, role.rolinherit, role.rolbypassrls
          INTO observed
          FROM pg_catalog.pg_roles AS role
         WHERE role.rolname = '{role}';
        IF observed.rolsuper THEN ALTER ROLE {role} NOSUPERUSER; END IF;
        IF observed.rolcreatedb THEN ALTER ROLE {role} NOCREATEDB; END IF;
        IF observed.rolcanlogin THEN ALTER ROLE {role} NOLOGIN; END IF;
        IF observed.rolreplication THEN ALTER ROLE {role} NOREPLICATION; END IF;
        IF NOT observed.rolinherit THEN ALTER ROLE {role} INHERIT; END IF;
        IF observed.rolbypassrls THEN ALTER ROLE {role} NOBYPASSRLS; END IF;
    END IF;
"""
PINNED_OUTBOUND_SWEEP = """
    FOR membership IN
        SELECT DISTINCT parent.rolname AS parent_role,
                        child.rolname AS capability_role
          FROM pg_catalog.pg_auth_members AS edge
          JOIN pg_catalog.pg_roles AS parent ON parent.oid = edge.roleid
          JOIN pg_catalog.pg_roles AS child ON child.oid = edge.member
         WHERE child.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
    LOOP
        EXECUTE pg_catalog.format(
            'REVOKE %I FROM %I CASCADE',
            membership.parent_role,
            membership.capability_role
        );
    END LOOP;
"""
PINNED_INBOUND_SWEEP = """
    FOR membership IN
        SELECT DISTINCT parent.rolname AS capability_role,
                        member.rolname AS member_role
          FROM pg_catalog.pg_auth_members AS edge
          JOIN pg_catalog.pg_roles AS parent ON parent.oid = edge.roleid
          JOIN pg_catalog.pg_roles AS member ON member.oid = edge.member
         WHERE parent.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND edge.admin_option
           AND member.rolname <> CURRENT_USER
    LOOP
        EXECUTE pg_catalog.format(
            'REVOKE ADMIN OPTION FOR %I FROM %I CASCADE',
            membership.capability_role,
            membership.member_role
        );
        EXECUTE pg_catalog.format(
            'GRANT %I TO %I WITH INHERIT FALSE, SET FALSE, ADMIN FALSE',
            membership.capability_role,
            membership.member_role
        );
    END LOOP;
"""


def _do_statement(declaration: str, *blocks: str) -> str:
    """A DO statement whose whole body is the given declaration and blocks."""
    return (
        "DO $$\nDECLARE\n    "
        + declaration
        + "\nBEGIN\n"
        + "".join(blocks)
        + "END;\n$$;\n"
    )


def _role_convergence_statement(*roles: str) -> str:
    return _do_statement(
        "observed record;",
        *(PINNED_ROLE_CONVERGENCE.format(role=role) for role in roles),
    )


# The hardening converges each capability role in its own DO statement; the
# corrective converges both in one.
ROLE_CONVERGENCE_LAYOUT = {
    "hardening": (("a11oy_memory_app",), ("a11oy_memory_worker",)),
    "corrective": (("a11oy_memory_app", "a11oy_memory_worker"),),
}
PINNED_OUTBOUND_SWEEP_STATEMENT = _do_statement(
    "membership record;", PINNED_OUTBOUND_SWEEP
)
PINNED_INBOUND_SWEEP_STATEMENT = _do_statement(
    "membership record;", PINNED_INBOUND_SWEEP
)
PINNED_CONVERGENCE_ASSERTIONS = """
DO $$
BEGIN
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS edge
          JOIN pg_catalog.pg_roles AS capability ON capability.oid = edge.member
         WHERE capability.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'a capability role still belongs to a parent role this principal could not revoke';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS edge
          JOIN pg_catalog.pg_roles AS capability ON capability.oid = edge.roleid
          JOIN pg_catalog.pg_roles AS holder ON holder.oid = edge.member
         WHERE capability.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND edge.admin_option
           AND holder.rolname <> CURRENT_USER
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'capability-role delegation survived the sweep; another grantor holds it';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS swept
          JOIN pg_catalog.pg_auth_members AS other
            ON other.roleid = swept.roleid
           AND other.member = swept.member
          JOIN pg_catalog.pg_roles AS capability ON capability.oid = swept.roleid
         WHERE capability.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND NOT swept.admin_option
           AND NOT swept.inherit_option
           AND NOT swept.set_option
           AND (other.inherit_option OR other.set_option)
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'a swept capability-role delegate keeps SET or INHERIT through another grant';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS edge
          JOIN pg_catalog.pg_roles AS capability ON capability.oid = edge.roleid
          JOIN pg_catalog.pg_roles AS holder ON holder.oid = edge.member
         WHERE capability.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND edge.set_option
           AND NOT edge.inherit_option
           AND NOT edge.admin_option
           AND holder.rolname <> CURRENT_USER
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'a capability-role membership grants SET without INHERIT; runtime logins must inherit';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members AS edge
          JOIN pg_catalog.pg_roles AS capability ON capability.oid = edge.roleid
         WHERE capability.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND NOT EXISTS (
               SELECT 1
                 FROM pg_catalog.pg_roles AS grantor
                WHERE grantor.oid = edge.grantor
                  AND grantor.rolsuper
           )
           AND NOT EXISTS (
               SELECT 1
                 FROM pg_catalog.pg_auth_members AS authority
                WHERE authority.roleid = edge.roleid
                  AND authority.member = edge.grantor
                  AND authority.admin_option
           )
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'a capability-role membership was granted by a role that no longer holds ADMIN on it';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles AS capability
         WHERE capability.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND (EXISTS (
                    SELECT 1
                      FROM pg_catalog.pg_database AS owned_database
                     WHERE owned_database.datname = pg_catalog.current_database()
                       AND owned_database.datdba = capability.oid
                )
                OR EXISTS (
                    SELECT 1
                      FROM pg_catalog.pg_namespace AS owned_schema
                     WHERE owned_schema.nspowner = capability.oid
                ))
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'a capability role owns the database or a schema';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_roles AS capability
         WHERE capability.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND (capability.rolsuper OR capability.rolcreatedb
                OR capability.rolcreaterole OR capability.rolcanlogin
                OR capability.rolreplication OR NOT capability.rolinherit
                OR capability.rolbypassrls)
    ) THEN
        RAISE EXCEPTION USING ERRCODE = '42501',
          MESSAGE = 'a capability role attribute did not converge';
    END IF;
END;
$$;
"""
# MEMBER is true for any membership row in PostgreSQL 16 and later, including a
# swept delegate's and a SET-only one, so the guard tests USAGE.
PINNED_LEASE_GUARD = """
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles WHERE rolname='a11oy_memory_worker'
    ) OR NOT pg_catalog.pg_has_role(
        session_user,
        'a11oy_memory_worker',
        'USAGE'
    ) THEN
        RAISE EXCEPTION USING ERRCODE='42501', MESSAGE='session user does not inherit a11oy_memory_worker';
    END IF;
"""
PINNED_LEASE_FUNCTION = """
CREATE OR REPLACE FUNCTION public.memory_lease_outbox(
    p_worker_id text,
    p_limit integer DEFAULT 25,
    p_lease_seconds integer DEFAULT 30
)
RETURNS SETOF public.memory_outbox
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
    IF p_worker_id IS NULL OR p_worker_id = '' THEN
        RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='worker id is required';
    END IF;
    IF p_limit IS NULL OR p_limit < 1 OR p_limit > 500
       OR p_lease_seconds IS NULL OR p_lease_seconds < 1 OR p_lease_seconds > 3600 THEN
        RAISE EXCEPTION USING ERRCODE='22023', MESSAGE='worker lease bounds are invalid';
    END IF;
""" + PINNED_LEASE_GUARD + """
    RETURN QUERY
    WITH candidates AS (
        SELECT event_id
          FROM public.memory_outbox
         WHERE status IN ('PENDING','RETRY','LEASED')
           AND available_at <= pg_catalog.now()
           AND (lease_expires_at IS NULL OR lease_expires_at <= pg_catalog.now())
         ORDER BY available_at, event_id
         FOR UPDATE SKIP LOCKED
         LIMIT p_limit
    )
    UPDATE public.memory_outbox AS event
       SET status='LEASED',
           attempts=event.attempts + 1,
           lease_owner=p_worker_id,
           lease_expires_at=pg_catalog.now() + pg_catalog.make_interval(secs => p_lease_seconds),
           updated_at=pg_catalog.now()
      FROM candidates
     WHERE event.event_id = candidates.event_id
    RETURNING event.*;
END;
$$;
"""
# Dynamic SQL runs only inside pinned statements. Each top-level statement
# that executes a string as SQL is pinned whole, so neither its template nor
# the query that feeds it can change unless this validator changes with it.
COVENANT_RELATION_LIST = """(
               'memory_records',
               'memory_evidence_refs',
               'memory_outbox',
               'memory_receipts',
               'memory_query_audit',
               'memory_index_generations',
               'memory_idempotency',
               'memory_context_bindings'
           )"""
PINNED_BASE_POLICY_SWEEP = """
DO $$
DECLARE
    policy_row record;
BEGIN
    FOR policy_row IN
        SELECT c.relname AS table_name, p.polname AS policy_name
          FROM pg_catalog.pg_policy AS p
          JOIN pg_catalog.pg_class AS c ON c.oid = p.polrelid
          JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relname IN """ + COVENANT_RELATION_LIST + """
    LOOP
        EXECUTE format(
            'DROP POLICY %I ON public.%I',
            policy_row.policy_name,
            policy_row.table_name
        );
    END LOOP;
END;
$$;
"""
PINNED_EARLY_POLICY_SWEEP = """
DO $$
DECLARE
    policy_row record;
BEGIN
    FOR policy_row IN
        SELECT relation.relname AS table_name, policy.polname AS policy_name
          FROM pg_catalog.pg_policy AS policy
          JOIN pg_catalog.pg_class AS relation ON relation.oid = policy.polrelid
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relname IN """ + COVENANT_RELATION_LIST + """
    LOOP
        EXECUTE pg_catalog.format(
            'DROP POLICY %I ON public.%I',
            policy_row.policy_name,
            policy_row.table_name
        );
    END LOOP;
END;
$$;
"""
PINNED_RULE_SWEEP = """
DO $$
DECLARE
    rewrite_row record;
BEGIN
    FOR rewrite_row IN
        SELECT relation.relname AS table_name, rewrite.rulename AS rule_name
          FROM pg_catalog.pg_rewrite AS rewrite
          JOIN pg_catalog.pg_class AS relation
            ON relation.oid = rewrite.ev_class
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relname IN """ + COVENANT_RELATION_LIST + """
           AND rewrite.rulename <> '_RETURN'
    LOOP
        EXECUTE pg_catalog.format(
            'DROP RULE %I ON public.%I',
            rewrite_row.rule_name,
            rewrite_row.table_name
        );
    END LOOP;
END;
$$;
"""
PINNED_TRIGGER_SWEEP = """
DO $$
DECLARE
    trigger_row record;
BEGIN
    FOR trigger_row IN
        SELECT relation.relname AS table_name, trigger.tgname AS trigger_name
          FROM pg_catalog.pg_trigger AS trigger
          JOIN pg_catalog.pg_class AS relation
            ON relation.oid = trigger.tgrelid
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
         WHERE namespace.nspname = 'public'
           AND relation.relname IN """ + COVENANT_RELATION_LIST + """
           AND NOT trigger.tgisinternal
    LOOP
        EXECUTE pg_catalog.format(
            'DROP TRIGGER %I ON public.%I',
            trigger_row.trigger_name,
            trigger_row.table_name
        );
    END LOOP;
END;
$$;
"""
PINNED_RECEIPT_FOREIGN_KEY_SWEEP = """
DO $$
DECLARE
    relationship record;
BEGIN
    FOR relationship IN
        SELECT child.relname AS table_name, constraint_row.conname
          FROM pg_catalog.pg_constraint AS constraint_row
          JOIN pg_catalog.pg_class AS child ON child.oid = constraint_row.conrelid
          JOIN pg_catalog.pg_namespace AS child_namespace
            ON child_namespace.oid = child.relnamespace
         WHERE constraint_row.contype = 'f'
           AND constraint_row.confrelid = 'public.memory_receipts'::pg_catalog.regclass
           AND child_namespace.nspname = 'public'
           AND child.relname IN ('memory_query_audit', 'memory_idempotency')
    LOOP
        EXECUTE pg_catalog.format(
            'ALTER TABLE public.%I DROP CONSTRAINT %I',
            relationship.table_name,
            relationship.conname
        );
    END LOOP;
END;
$$;
"""
PINNED_LATE_POLICY_SWEEP = """
DO $$
DECLARE
    policy_row record;
BEGIN
    FOR policy_row IN
        SELECT c.relname AS table_name, p.polname AS policy_name
          FROM pg_catalog.pg_policy AS p
          JOIN pg_catalog.pg_class AS c ON c.oid = p.polrelid
          JOIN pg_catalog.pg_namespace AS n ON n.oid = c.relnamespace
         WHERE n.nspname = 'public'
           AND c.relname IN """ + COVENANT_RELATION_LIST + """
    LOOP
        EXECUTE pg_catalog.format(
            'DROP POLICY %I ON public.%I',
            policy_row.policy_name,
            policy_row.table_name
        );
    END LOOP;
END;
$$;
"""
PINNED_SCHEMA_CREATE_SWEEP = """
DO $$
DECLARE
    grantee_oid oid;
BEGIN
    FOR grantee_oid IN
        SELECT DISTINCT acl.grantee
          FROM pg_catalog.pg_namespace AS namespace
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              COALESCE(
                  namespace.nspacl,
                  pg_catalog.acldefault('n', namespace.nspowner)
              )
          ) AS acl
         WHERE namespace.nspname = 'public'
           AND acl.privilege_type = 'CREATE'
           AND acl.grantee <> namespace.nspowner
    LOOP
        IF grantee_oid = 0 THEN
            REVOKE CREATE ON SCHEMA public FROM PUBLIC CASCADE;
        ELSE
            EXECUTE pg_catalog.format(
                'REVOKE CREATE ON SCHEMA public FROM %I CASCADE',
                pg_catalog.pg_get_userbyid(grantee_oid)
            );
        END IF;
    END LOOP;
END;
$$;
"""
PINNED_TABLE_ACL_SWEEP = """
DO $$
DECLARE
    privilege_row record;
BEGIN
    FOR privilege_row IN
        SELECT DISTINCT relation.relname AS table_name, acl.grantee
          FROM pg_catalog.pg_class AS relation
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              COALESCE(
                  relation.relacl,
                  pg_catalog.acldefault('r', relation.relowner)
              )
          ) AS acl
         WHERE namespace.nspname = 'public'
           AND relation.relname IN """ + COVENANT_RELATION_LIST + """
           AND acl.grantee <> relation.relowner
    LOOP
        IF privilege_row.grantee = 0 THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM PUBLIC CASCADE',
                privilege_row.table_name
            );
        ELSE
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM %I CASCADE',
                privilege_row.table_name,
                pg_catalog.pg_get_userbyid(privilege_row.grantee)
            );
        END IF;
    END LOOP;

    FOR privilege_row IN
        SELECT DISTINCT relation.relname AS table_name,
                        attribute.attname AS column_name,
                        acl.grantee
          FROM pg_catalog.pg_class AS relation
          JOIN pg_catalog.pg_namespace AS namespace
            ON namespace.oid = relation.relnamespace
          JOIN pg_catalog.pg_attribute AS attribute
            ON attribute.attrelid = relation.oid
          CROSS JOIN LATERAL pg_catalog.aclexplode(attribute.attacl) AS acl
         WHERE namespace.nspname = 'public'
           AND relation.relname IN """ + COVENANT_RELATION_LIST + """
           AND attribute.attnum > 0
           AND NOT attribute.attisdropped
           AND attribute.attacl IS NOT NULL
           AND acl.grantee <> relation.relowner
    LOOP
        IF privilege_row.grantee = 0 THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES (%I) ON TABLE public.%I FROM PUBLIC CASCADE',
                privilege_row.column_name,
                privilege_row.table_name
            );
        ELSE
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES (%I) ON TABLE public.%I FROM %I CASCADE',
                privilege_row.column_name,
                privilege_row.table_name,
                pg_catalog.pg_get_userbyid(privilege_row.grantee)
            );
        END IF;
    END LOOP;
END;
$$;
"""
# The %s placeholder takes a regprocedure rendered as text, which PostgreSQL
# quotes; the pin keeps the query that produces it fixed.
PINNED_FUNCTION_ACL_SWEEP = """
DO $$
DECLARE
    privilege_row record;
BEGIN
    FOR privilege_row IN
        SELECT DISTINCT procedure.oid::pg_catalog.regprocedure::text AS identity,
                        acl.grantee
          FROM pg_catalog.pg_proc AS procedure
          CROSS JOIN LATERAL pg_catalog.aclexplode(
              COALESCE(
                  procedure.proacl,
                  pg_catalog.acldefault('f', procedure.proowner)
              )
          ) AS acl
         WHERE procedure.oid = ANY(ARRAY[
                   'public.memory_touch_updated_at()'::pg_catalog.regprocedure,
                   'public.memory_reject_mutation()'::pg_catalog.regprocedure,
                   'public.a11oy_memory_context_matches(text,text)'::pg_catalog.regprocedure,
                   'public.memory_lease_outbox(text,integer,integer)'::pg_catalog.regprocedure
               ])
           AND acl.grantee <> procedure.proowner
    LOOP
        IF privilege_row.grantee = 0 THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON FUNCTION %s FROM PUBLIC CASCADE',
                privilege_row.identity
            );
        ELSE
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON FUNCTION %s FROM %I CASCADE',
                privilege_row.identity,
                pg_catalog.pg_get_userbyid(privilege_row.grantee)
            );
        END IF;
    END LOOP;
END;
$$;
"""
DYNAMIC_SQL_PINS = {
    BASE_MIGRATION: (
        (PINNED_BASE_POLICY_SWEEP, "policy sweep"),
    ),
    HARDENING_MIGRATION: (
        (PINNED_SCHEMA_CREATE_SWEEP, "schema CREATE sweep"),
        (PINNED_TABLE_ACL_SWEEP, "table and column ACL sweep"),
        (PINNED_FUNCTION_ACL_SWEEP, "function ACL sweep"),
    ),
    CORRECTIVE_MIGRATION: (
        (PINNED_EARLY_POLICY_SWEEP, "early policy sweep"),
        (PINNED_RULE_SWEEP, "rewrite-rule sweep"),
        (PINNED_TRIGGER_SWEEP, "trigger sweep"),
        (PINNED_RECEIPT_FOREIGN_KEY_SWEEP, "receipt foreign-key sweep"),
        (PINNED_LATE_POLICY_SWEEP, "late policy sweep"),
        (PINNED_SCHEMA_CREATE_SWEEP, "schema CREATE sweep"),
        (PINNED_TABLE_ACL_SWEEP, "table and column ACL sweep"),
        (PINNED_FUNCTION_ACL_SWEEP, "function ACL sweep"),
    ),
}
PINNED_ACCEPTANCE_ATTRIBUTE_ASSERTION = """
    IF EXISTS (
        SELECT 1
          FROM pg_roles
         WHERE rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
           AND (
               rolsuper
               OR rolcreatedb
               OR rolcreaterole
               OR rolreplication
               OR NOT rolinherit
               OR rolbypassrls
               OR rolcanlogin
           )
    ) THEN
        RAISE EXCEPTION 'Memory Covenant roles retain a privileged role attribute';
    END IF;
"""
PINNED_ACCEPTANCE_ADMIN_EXEMPTION = """
    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS edge
         WHERE edge.roleid IN (
             'a11oy_memory_app'::regrole,
             'a11oy_memory_worker'::regrole
         )
           AND edge.admin_option
           AND edge.member <> (
               SELECT relation.relowner
                 FROM pg_catalog.pg_class AS relation
                WHERE relation.oid = 'public.memory_records'::pg_catalog.regclass
           )
    ) THEN
        RAISE EXCEPTION 'Memory Covenant capability membership retained ADMIN OPTION';
    END IF;
"""
PINNED_ACCEPTANCE_ROLE_ASSERTIONS = (
    "DO $$\nBEGIN\n"
    + PINNED_ACCEPTANCE_ATTRIBUTE_ASSERTION
    + """
    IF (
        SELECT count(*)
          FROM pg_roles
         WHERE rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')
    ) <> 2 THEN
        RAISE EXCEPTION 'Memory Covenant roles are missing';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS edge
         WHERE edge.member IN (
             'a11oy_memory_app'::regrole,
             'a11oy_memory_worker'::regrole
         )
    ) THEN
        RAISE EXCEPTION 'Memory Covenant capability role retained an inherited parent';
    END IF;
"""
    + PINNED_ACCEPTANCE_ADMIN_EXEMPTION
    + """
    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS swept
          JOIN pg_auth_members AS other
            ON other.roleid = swept.roleid
           AND other.member = swept.member
         WHERE swept.roleid IN (
             'a11oy_memory_app'::regrole,
             'a11oy_memory_worker'::regrole
         )
           AND NOT swept.admin_option
           AND NOT swept.inherit_option
           AND NOT swept.set_option
           AND (other.inherit_option OR other.set_option)
    ) THEN
        RAISE EXCEPTION 'A swept capability-role delegate keeps SET or INHERIT through another grant';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS edge
         WHERE edge.roleid IN (
             'a11oy_memory_app'::regrole,
             'a11oy_memory_worker'::regrole
         )
           AND edge.set_option
           AND NOT edge.inherit_option
           AND NOT edge.admin_option
           AND edge.member <> (
               SELECT relation.relowner
                 FROM pg_catalog.pg_class AS relation
                WHERE relation.oid = 'public.memory_records'::pg_catalog.regclass
           )
    ) THEN
        RAISE EXCEPTION 'Memory Covenant capability membership grants SET without INHERIT';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS edge
         WHERE edge.roleid IN (
             'a11oy_memory_app'::regrole,
             'a11oy_memory_worker'::regrole
         )
           AND NOT EXISTS (
               SELECT 1
                 FROM pg_roles AS grantor
                WHERE grantor.oid = edge.grantor
                  AND grantor.rolsuper
           )
           AND NOT EXISTS (
               SELECT 1
                 FROM pg_auth_members AS authority
                WHERE authority.roleid = edge.roleid
                  AND authority.member = edge.grantor
                  AND authority.admin_option
           )
    ) THEN
        RAISE EXCEPTION 'Memory Covenant capability membership has a grantor without ADMIN';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_database AS owned_database
         WHERE owned_database.datname = current_database()
           AND owned_database.datdba IN (
               'a11oy_memory_app'::regrole,
               'a11oy_memory_worker'::regrole
           )
    ) OR EXISTS (
        SELECT 1
          FROM pg_namespace AS owned_schema
         WHERE owned_schema.nspowner IN (
             'a11oy_memory_app'::regrole,
             'a11oy_memory_worker'::regrole
         )
    ) THEN
        RAISE EXCEPTION 'Memory Covenant capability role owns the database or a schema';
    END IF;
END;
$$;
"""
)
ROLE_ATTRIBUTE_COLUMN = re.compile(
    r"\brol(?:super|createdb|createrole|canlogin|replication|inherit|bypassrls)\b",
    re.IGNORECASE,
)
SEEDED_DELEGATE_VARIABLES = (
    "hostile_delegate",
    "owner_delegate",
    "foreign_delegate",
    "signature_delegate",
    "setonly_member",
    "worker_login",
    "raced_grantor",
    "raced_member",
)
# YAML spellings of an if: key: plain, quoted, tagged or anchored keys, keys in
# flow mappings, escaped double-quoted keys such as "\x69f", explicit "?" keys
# and "<<" merge keys.
WORKFLOW_IF_KEY = re.compile(
    r"^[ \t]*(?:-[ \t]+)*(?:[!&]\S*[ \t]+)*[\"']?if[\"']?[ \t]*:(?:[ \t]|$)",
    re.IGNORECASE | re.MULTILINE,
)
WORKFLOW_FLOW_IF_KEY = re.compile(
    r"[{,\[][ \t]*(?:[!&]\S*[ \t]+)*[\"']?if[\"']?[ \t]*:",
    re.IGNORECASE,
)
WORKFLOW_ESCAPED_KEY = re.compile(r"\"[^\"\n]*\\[^\"\n]*\"[ \t]*:(?:[ \t]|$)", re.MULTILINE)
WORKFLOW_COMPLEX_KEY = re.compile(r"^[ \t]*(?:-[ \t]+)*\?(?:[ \t]|$)", re.MULTILINE)
WORKFLOW_MERGE_KEY = re.compile(r"^[ \t]*(?:-[ \t]+)*<<[ \t]*:", re.MULTILINE)
# The workflow is read as a strict YAML subset, so every key GitHub reads is a
# key this scan sees: block mappings and sequences with plain keys; block
# scalars opened by "key: |", "|-", ">" or ">-"; and one-line plain or quoted
# values, "[a, b]" or "{}". Anchors, aliases, tags, quoted, explicit and merge
# keys, non-empty flow mappings and multi-line quoted values are unreadable here
# and refused. Keys outside the reviewed set are refused too: if:,
# continue-on-error, defaults or container would let a failing check pass.
WORKFLOW_KEY = r"[A-Za-z0-9_][A-Za-z0-9_.-]*"
WORKFLOW_ENTRY = re.compile(rf"^ *(?:- +)*(?P<key>{WORKFLOW_KEY}) *:(?P<rest>(?: .*)?)$")
WORKFLOW_ITEM = re.compile(r"^ *(?:- +)+(?P<rest>.*)$")
WORKFLOW_BLOCK_INDICATORS = frozenset({"|", "|-", ">", ">-"})
WORKFLOW_PLAIN_START = re.compile(r"[^\s\-?:,\[\]{}#&*!|>'\"%@`]")
WORKFLOW_FLOW_SEQUENCE = re.compile(
    r"\[ *(?:[A-Za-z0-9_./-]+(?: *, *[A-Za-z0-9_./-]+)*)? *\]"
)
WORKFLOW_ALLOWED_KEYS = frozenset(
    {
        "name", "on", "pull_request", "push", "workflow_dispatch", "branches",
        "paths", "permissions", "contents", "concurrency", "group",
        "cancel-in-progress", "jobs", "static-contract", "postgres-18-acceptance",
        "provider-owner-acceptance", "needs", "runs-on", "timeout-minutes",
        "services", "postgres", "image", "ports", "options", "env",
        "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_DB", "EXPECTED_SOURCE_SHA",
        "steps", "uses", "with", "egress-policy", "persist-credentials", "ref",
        "python-version", "shell", "run", "path", "if-no-files-found",
        "retention-days",
    }
)
WORKFLOW_FORBIDDEN_KEYS = {
    "if": "Memory Covenant workflow must not contain an if: key",
    "continue-on-error": "Memory Covenant workflow must not contain a continue-on-error key",
}


# --------------------------------------------------------------------------
# SQL lexer.
#
# The rules follow PostgreSQL's scanner and psql's statement splitter:
# standard strings with '' escapes; E'' strings with backslash escapes; B'',
# X'' and N'' strings; double-quoted identifiers; dollar quotes ($$ or $tag$);
# "--" comments only outside literals; nested /* */ comments; identifiers that
# may contain "$"; and psql backslash meta-commands and :variable references,
# which this contract rejects. Lexing assumes standard_conforming_strings=on,
# PostgreSQL's default, and a UTF-8 client encoding; the contract rejects any
# attempt to change either, and rejects E'' strings outright.
#
# psql's input layer, which reads lines before this splitter sees them, is not
# modelled. FORBIDDEN_CHARACTER refuses every byte at which it differs (NUL,
# CR and the other control characters), so the lexer's lines are psql's lines.
# --------------------------------------------------------------------------


class SqlLexError(ValueError):
    """The text cannot be split the way psql and PostgreSQL would split it."""


class Token(NamedTuple):
    kind: str
    text: str
    tag: str = ""
    body: str = ""


SKIPPED_TOKENS = frozenset({"space", "comment"})
SQL_WHITESPACE = frozenset(" \t\n\r\f\v")
IDENT_START = re.compile(r"[A-Za-z_\u0080-\U0010ffff]")
IDENT_REST = re.compile(r"[A-Za-z0-9_$\u0080-\U0010ffff]*")
DOLLAR_DELIMITER = re.compile(
    r"\$(?:[A-Za-z_\u0080-\U0010ffff][A-Za-z0-9_\u0080-\U0010ffff]*)?\$"
)
POSITIONAL_PARAMETER = re.compile(r"\$[0-9]+")
NUMBER = re.compile(
    r"0[xX][0-9A-Fa-f_]+|0[oO][0-7_]+|0[bB][01_]+"
    r"|(?:[0-9][0-9_]*(?:\.[0-9_]*)?|\.[0-9][0-9_]*)(?:[eE][+-]?[0-9]+)?"
)
OPERATOR_CHARS = frozenset("+-*/<>=~!@#%^&|`?")
# psql interpolates :name, :'name', :"name" and :{?name} outside literals.
PSQL_VARIABLE = re.compile(
    r":(?:[A-Za-z0-9_\u0080-\U0010ffff]+"
    r"|'[A-Za-z0-9_\u0080-\U0010ffff]+'"
    r"|\"[A-Za-z0-9_\u0080-\U0010ffff]+\""
    r"|\{\?[A-Za-z0-9_\u0080-\U0010ffff]+\})"
)


def _scan_quoted(text: str, start: int, quote: str, *, backslash: bool) -> int:
    index, length = start, len(text)
    while index < length:
        char = text[index]
        if backslash and char == "\\":
            index += 2
            continue
        if char == quote:
            if text.startswith(quote, index + 1):
                index += 2
                continue
            return index + 1
        index += 1
    raise SqlLexError(f"unterminated {quote} literal")


def _is_ascii_digit(char: str) -> bool:
    return "0" <= char <= "9"


@functools.lru_cache(maxsize=None)
def _lex(text: str) -> tuple[Token, ...]:
    tokens: list[Token] = []
    index, length = 0, len(text)
    while index < length:
        char = text[index]
        follower = text[index + 1] if index + 1 < length else ""
        if char in SQL_WHITESPACE:
            end = index + 1
            while end < length and text[end] in SQL_WHITESPACE:
                end += 1
            tokens.append(Token("space", text[index:end]))
        elif text.startswith("--", index):
            end = index + 2
            while end < length and text[end] not in "\r\n":
                end += 1
            tokens.append(Token("comment", text[index:end]))
        elif text.startswith("/*", index):
            depth, end = 1, index + 2
            while depth:
                if end >= length:
                    raise SqlLexError("unterminated block comment")
                if text.startswith("/*", end):
                    depth, end = depth + 1, end + 2
                elif text.startswith("*/", end):
                    depth, end = depth - 1, end + 2
                else:
                    end += 1
            tokens.append(Token("comment", text[index:end]))
        elif char in "eE" and follower == "'":
            end = _scan_quoted(text, index + 2, "'", backslash=True)
            tokens.append(Token("string", text[index:end]))
        elif char in "bBxXnN" and follower == "'":
            end = _scan_quoted(text, index + 2, "'", backslash=False)
            tokens.append(Token("string", text[index:end]))
        elif char in "uU" and follower == "&" and text[index + 2 : index + 3] in ("'", '"'):
            end = _scan_quoted(text, index + 3, text[index + 2], backslash=False)
            tokens.append(Token("unicode", text[index:end]))
        elif char == "'":
            end = _scan_quoted(text, index + 1, "'", backslash=False)
            tokens.append(Token("string", text[index:end]))
        elif char == '"':
            end = _scan_quoted(text, index + 1, '"', backslash=False)
            tokens.append(Token("identifier", text[index:end]))
        elif char == "$":
            delimiter = DOLLAR_DELIMITER.match(text, index)
            parameter = POSITIONAL_PARAMETER.match(text, index)
            if delimiter:
                marker = delimiter.group(0)
                close = text.find(marker, delimiter.end())
                if close < 0:
                    raise SqlLexError(f"unterminated dollar quote {marker}")
                end = close + len(marker)
                tokens.append(
                    Token(
                        "dollar",
                        text[index:end],
                        tag=marker[1:-1],
                        body=text[delimiter.end() : close],
                    )
                )
            elif parameter:
                end = parameter.end()
                tokens.append(Token("parameter", text[index:end]))
            else:
                end = index + 1
                tokens.append(Token("punct", char))
        elif IDENT_START.match(char):
            match = IDENT_REST.match(text, index + 1)
            end = match.end() if match else index + 1
            tokens.append(Token("word", text[index:end]))
        elif _is_ascii_digit(char) or (char == "." and _is_ascii_digit(follower)):
            match = NUMBER.match(text, index)
            end = match.end() if match and match.end() > index else index + 1
            tokens.append(Token("number", text[index:end]))
        elif char == "\\":
            end = index
            while end < length and text[end] not in "\r\n":
                end += 1
            tokens.append(Token("meta", text[index:end]))
        elif char == ":":
            if follower in (":", "="):
                end = index + 2
                tokens.append(Token("punct", text[index:end]))
            elif PSQL_VARIABLE.match(text, index):
                end = PSQL_VARIABLE.match(text, index).end()
                tokens.append(Token("variable", text[index:end]))
            else:
                end = index + 1
                tokens.append(Token("punct", char))
        elif char in OPERATOR_CHARS:
            end = index + 1
            while (
                end < length
                and text[end] in OPERATOR_CHARS
                and not text.startswith("--", end)
                and not text.startswith("/*", end)
            ):
                end += 1
            tokens.append(Token("operator", text[index:end]))
        else:
            end = index + 1
            tokens.append(Token("punct", char))
        index = end
    return tuple(tokens)


def _render(tokens: Iterable[Token], *, edges: bool = False) -> str:
    """Collapse whitespace and comments to one space; keep literals verbatim."""
    parts: list[str] = []
    gap = False
    for token in tokens:
        if token.kind in SKIPPED_TOKENS:
            gap = True
            continue
        if gap and (parts or edges):
            parts.append(" ")
        gap = False
        if token.kind == "dollar":
            marker = f"${token.tag}$"
            parts.append(marker + _render(_lex(token.body), edges=True) + marker)
        else:
            parts.append(token.text)
    if gap and edges and parts:
        parts.append(" ")
    return "".join(parts)


def _normalize(text: str) -> str:
    return _render(_lex(text))


def _signature(tokens: Iterable[Token]) -> tuple:
    signature: list[tuple] = []
    for token in tokens:
        if token.kind in SKIPPED_TOKENS:
            continue
        if token.kind == "dollar":
            signature.append(("dollar", token.tag, _signature(_lex(token.body))))
        else:
            signature.append((token.kind, token.text))
    return tuple(signature)


class Statement(NamedTuple):
    tokens: tuple[Token, ...]
    signature: tuple
    text: str

    @property
    def do_body(self) -> tuple[Token, ...] | None:
        """The lexed body of a plain DO $$ ... $$; statement, else None."""
        significant = [t for t in self.tokens if t.kind not in SKIPPED_TOKENS]
        if (
            len(significant) == 3
            and significant[0].kind == "word"
            and significant[0].text.upper() == "DO"
            and significant[1].kind == "dollar"
            and significant[1].tag == ""
            and significant[2].text == ";"
        ):
            return _lex(significant[1].body)
        return None


@functools.lru_cache(maxsize=None)
def _top_level_statements(text: str) -> tuple[Statement, ...]:
    """Split like psql: at ';' outside literals, comments and parentheses."""
    statements: list[Statement] = []
    current: list[Token] = []

    def flush() -> None:
        if any(token.kind not in SKIPPED_TOKENS for token in current):
            statements.append(
                Statement(tuple(current), _signature(current), _render(current))
            )
        current.clear()

    depth = 0
    for token in _lex(text):
        if token.kind == "meta":
            flush()
            current.append(token)
            flush()
            continue
        current.append(token)
        if token.kind == "punct":
            if token.text == "(":
                depth += 1
            elif token.text == ")":
                depth = max(depth - 1, 0)
            elif token.text == ";" and depth == 0:
                flush()
    flush()
    return tuple(statements)


@functools.lru_cache(maxsize=None)
def _pinned_statement(pinned_sql: str) -> Statement:
    statements = _top_level_statements(pinned_sql)
    if len(statements) != 1:
        raise ValueError("a pinned statement must be exactly one statement")
    return statements[0]


def _count_statement_pins(statements: Iterable[Statement], pinned_sql: str) -> int:
    signature = _pinned_statement(pinned_sql).signature
    return sum(1 for statement in statements if statement.signature == signature)


def _statement_index(statements: tuple[Statement, ...], pinned_sql: str) -> int:
    signature = _pinned_statement(pinned_sql).signature
    for index, statement in enumerate(statements):
        if statement.signature == signature:
            return index
    return -1


def _count_body_pins(statements: Iterable[Statement], fragment_sql: str) -> int:
    """Count a pinned block only inside the body of a top-level DO statement."""
    needle = _signature(_lex(fragment_sql))
    width = len(needle)
    total = 0
    for statement in statements:
        body = statement.do_body
        if body is None or not width:
            continue
        haystack = _signature(body)
        total += sum(
            1
            for start in range(len(haystack) - width + 1)
            if haystack[start : start + width] == needle
        )
    return total


def _remainder(statements: Iterable[Statement], pinned: Iterable[str]) -> str:
    """Every top-level statement except the pinned ones, as normalized text."""
    excluded = {_pinned_statement(sql).signature for sql in pinned}
    return " ".join(
        statement.text for statement in statements if statement.signature not in excluded
    )


def _require_statement_pin(
    statements: tuple[Statement, ...],
    pinned_sql: str,
    expected: int,
    label: str,
    errors: list[str],
) -> None:
    actual = _count_statement_pins(statements, pinned_sql)
    if actual != expected:
        errors.append(f"{label}: expected {expected} exact copy, found {actual}")


def _require_body_pin(
    statements: tuple[Statement, ...],
    fragment_sql: str,
    expected: int,
    label: str,
    errors: list[str],
) -> None:
    actual = _count_body_pins(statements, fragment_sql)
    if actual != expected:
        errors.append(
            f"{label}: expected {expected} exact copy inside a top-level DO body, found {actual}"
        )


def _check_nested_literals(label: str, tokens: Iterable[Token], errors: list[str]) -> bool:
    """Dollar-quoted bodies are code here: lex them and apply the same rules."""
    clean = True
    for token in tokens:
        if token.kind == "dollar":
            if token.tag:
                errors.append(
                    f"{label} uses a tagged dollar quote ${token.tag}$; only $$ is allowed"
                )
            try:
                body = _lex(token.body)
            except SqlLexError as exc:
                errors.append(f"{label} has a dollar-quoted body that cannot be lexed: {exc}")
                clean = False
                continue
            clean = _check_nested_literals(label, body, errors) and clean
        elif token.kind == "meta":
            errors.append(
                f"{label} contains a psql meta-command: {token.text.strip()[:40]}"
            )
        elif token.kind == "unicode":
            errors.append(f"{label} contains a Unicode-escape literal or identifier")
        elif token.kind == "string" and token.text[:1] in ("e", "E"):
            # A backslash escape can spell any text, so a check that reads the
            # literal's characters would not see its value.
            errors.append(f"{label} contains an E'' escape-string literal")
    return clean


def _validate_lexical(
    label: str,
    text: str,
    errors: list[str],
    *,
    psql_preamble: str | None = None,
) -> bool:
    """Reject SQL whose meaning a token-level contract cannot see. False if unlexable."""
    try:
        tokens = _lex(text)
    except SqlLexError as exc:
        errors.append(f"{label} cannot be lexed: {exc}")
        return False
    significant = [token for token in tokens if token.kind not in SKIPPED_TOKENS]
    nested: list[Token] = []
    for position, token in enumerate(significant):
        if token.kind == "meta":
            if not (
                psql_preamble is not None
                and position == 0
                and token.text.rstrip() == psql_preamble
            ):
                errors.append(
                    f"{label} contains a psql meta-command: {token.text.strip()[:40]}"
                )
        elif token.kind == "variable":
            errors.append(f"{label} contains a psql variable reference")
        elif token.kind == "word" and token.text.upper() == "ATOMIC":
            errors.append(f"{label} must not use BEGIN ATOMIC bodies")
        else:
            nested.append(token)
    if not _check_nested_literals(label, nested, errors):
        return False
    if re.search(
        r"standard_conforming_strings|backslash_quote|escape_string_warning",
        _render(tokens),
        re.IGNORECASE,
    ):
        errors.append(f"{label} must not change how string literals are lexed")
    # psql lexes each later line in the new client encoding, where a
    # multi-byte character can absorb the byte after it.
    if re.search(
        r"client_encoding|\bSET\s+(?:(?:SESSION|LOCAL)\s+)?NAMES\b",
        _render(tokens),
        re.IGNORECASE,
    ):
        errors.append(f"{label} must not change the client encoding")
    return True


def _read_utf8_file(root: Path, relative: Path, errors: list[str]) -> str:
    path = root / relative
    if not path.exists():
        errors.append(f"missing required migration: {relative.as_posix()}")
        return ""
    if path.is_symlink():
        errors.append(f"migration must not be a symlink: {relative.as_posix()}")
        return ""
    try:
        raw = path.read_bytes()
    except OSError as exc:
        errors.append(f"cannot read {relative.as_posix()}: {exc}")
        return ""
    if raw.startswith(b"\xef\xbb\xbf") or b"\xef\xbb\xbf" in raw:
        errors.append(f"UTF-8 BOM is forbidden: {relative.as_posix()}")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"invalid UTF-8 in {relative.as_posix()}: {exc}")
        return ""
    forbidden = FORBIDDEN_CHARACTER.search(text)
    if forbidden:
        line = text.count("\n", 0, forbidden.start()) + 1
        errors.append(
            f"control character U+{ord(forbidden.group()):04X} is forbidden: "
            f"{relative.as_posix()} line {line}"
        )
        return ""
    return text


def _require_count(
    pattern: str,
    text: str,
    expected: int,
    label: str,
    errors: list[str],
    *,
    flags: int = re.IGNORECASE,
) -> None:
    actual = len(re.findall(pattern, text, flags))
    if actual != expected:
        errors.append(f"{label}: expected {expected}, found {actual}")


def _require_token(token: str, text: str, label: str, errors: list[str]) -> None:
    if token.upper() not in text.upper():
        errors.append(f"missing {label}")


def _statements(normalized_sql: str) -> Iterable[str]:
    for statement in normalized_sql.split(";"):
        statement = statement.strip()
        if statement:
            yield statement


def _validate_transactions(migrations: dict[Path, str], errors: list[str]) -> None:
    for path, text in migrations.items():
        label = path.name
        normalized = _normalize(text)
        _require_count(r"\bBEGIN\s*;", normalized, 1, f"{label} BEGIN", errors)
        _require_count(r"\bCOMMIT\s*;", normalized, 1, f"{label} COMMIT", errors)
        if not normalized.upper().startswith("BEGIN;"):
            errors.append(f"{label} must start with BEGIN")
        if not normalized.upper().endswith("COMMIT;"):
            errors.append(f"{label} must end with COMMIT")
        if re.search(r"\bROLLBACK\b", normalized, re.IGNORECASE):
            errors.append(f"{label} must not contain ROLLBACK")
        _require_count(
            r"\bSET\s+LOCAL\s+search_path\s*=\s*pg_catalog\s*,\s*pg_temp\b",
            normalized,
            1,
            f"{label} safe migration search_path",
            errors,
        )


def _validate_tables_and_rls(base: str, hardening: str, corrective: str, errors: list[str]) -> None:
    base_sql = _normalize(base)
    hard_sql = _normalize(hardening)
    corrective_sql = _normalize(corrective)
    combined = f"{base_sql} {hard_sql} {corrective_sql}"

    for table in MEMORY_TABLES:
        _require_count(
            rf"\bCREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+public\.{table}\b",
            base_sql,
            1,
            f"schema-bound idempotent table {table}",
            errors,
        )
        _require_count(
            rf"\bALTER\s+TABLE\s+public\.{table}\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY\b",
            base_sql,
            1,
            f"RLS enablement for {table}",
            errors,
        )
        policy = f"{table}_isolation"
        for label, sql in (("base", base_sql), ("corrective", corrective_sql)):
            _require_count(
                rf"\bCREATE\s+POLICY\s+{policy}\s+ON\s+public\.{table}\b",
                sql,
                1,
                f"{label} isolation policy for {table}",
                errors,
            )
            match = re.search(
                rf"CREATE\s+POLICY\s+{policy}\s+ON\s+public\.{table}\s+(?P<body>.*?)\s*;",
                sql,
                re.IGNORECASE,
            )
            if match is None:
                errors.append(f"cannot inspect {label} isolation policy for {table}")
            else:
                body = match.group("body")
                if len(
                    re.findall(
                        r"public\.a11oy_memory_context_matches\s*\(\s*tenant_id\s*,\s*security_domain\s*\)",
                        body,
                        re.IGNORECASE,
                    )
                ) != 2:
                    errors.append(
                        f"{label} {table} policy must bind USING and WITH CHECK to tenant/domain context"
                    )
                if not re.search(r"\bUSING\s*\(", body, re.IGNORECASE):
                    errors.append(f"{label} {table} policy is missing USING")
                if not re.search(r"\bWITH\s+CHECK\s*\(", body, re.IGNORECASE):
                    errors.append(f"{label} {table} policy is missing WITH CHECK")

    for label, sql in (("base", base_sql), ("corrective", corrective_sql)):
        _require_count(
            rf"\bCREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+public\.{CONTEXT_BINDING_TABLE}\b",
            sql,
            1,
            f"{label} owner-only context binding table",
            errors,
        )
        _require_token(
            "PRIMARY KEY (principal_oid, tenant_id, security_domain)",
            sql,
            f"{label} context binding identity",
            errors,
        )
        for table in ALL_COVENANT_TABLES:
            _require_count(
                rf"\bALTER\s+TABLE\s+public\.{table}\s+OWNER\s+TO\s+CURRENT_USER\b",
                sql,
                1,
                f"{label} trusted owner convergence for {table}",
                errors,
            )
        _require_count(
            rf"\bALTER\s+TABLE\s+public\.{CONTEXT_BINDING_TABLE}\s+"
            r"ENABLE\s+ROW\s+LEVEL\s+SECURITY\b",
            sql,
            1,
            f"{label} context-binding defense-in-depth RLS",
            errors,
        )
        _require_count(
            rf"\bALTER\s+TABLE\s+public\.{CONTEXT_BINDING_TABLE}\s+"
            r"NO\s+FORCE\s+ROW\s+LEVEL\s+SECURITY\b",
            sql,
            1,
            f"{label} RLS-independent context-binding preflight",
            errors,
        )
        if re.search(
            rf"\bALTER\s+TABLE\s+public\.{CONTEXT_BINDING_TABLE}\s+"
            r"FORCE\s+ROW\s+LEVEL\s+SECURITY\b",
            sql,
            re.IGNORECASE,
        ):
            errors.append(
                f"{label} context-binding table must not retain FORCE RLS"
            )

    for label, sql in (("base", base_sql), ("corrective", corrective_sql)):
        _require_token(
            "FROM pg_catalog.pg_policy AS p",
            sql,
            f"{label} all-policy catalog sweep",
            errors,
        )
        _require_token(
            "DROP POLICY %I ON public.%I",
            sql,
            f"{label} stale-policy removal",
            errors,
        )
        for table in ALL_COVENANT_TABLES:
            if sql.count(f"'{table}'") < 1:
                errors.append(f"{label} stale-policy sweep omits {table}")
        policy_sweep = re.search(
            r"FROM\s+pg_catalog\.pg_policy\s+AS\s+p\b.*?"
            r"c\.relname\s+IN\s*\((?P<tables>.*?)\)\s+LOOP",
            sql,
            re.IGNORECASE,
        )
        if policy_sweep is None:
            errors.append(f"cannot inspect {label} covenant-policy sweep")
        else:
            observed_tables = frozenset(
                re.findall(r"'([^']+)'", policy_sweep.group("tables"))
            )
            if observed_tables != frozenset(ALL_COVENANT_TABLES):
                errors.append(
                    f"{label} policy sweep table set differs from covenant tables"
                )

    for table in MEMORY_TABLES:
        for label, sql in (("base", base_sql), ("corrective", corrective_sql)):
            _require_count(
                rf"\bALTER\s+TABLE\s+public\.{table}\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY\b",
                sql,
                1,
                f"{label} RLS enablement for {table}",
                errors,
            )

    for table in FORCE_RLS_TABLES:
        for label, sql in (("base", base_sql), ("corrective", corrective_sql)):
            _require_count(
                rf"\bALTER\s+TABLE\s+public\.{table}\s+FORCE\s+ROW\s+LEVEL\s+SECURITY\b",
                sql,
                1,
                f"{label} FORCE RLS for {table}",
                errors,
            )
        if re.search(
            rf"\bALTER\s+TABLE\s+(?:public\.)?{table}\s+NO\s+FORCE\s+ROW\s+LEVEL\s+SECURITY\b",
            combined,
            re.IGNORECASE,
        ):
            errors.append(f"tenant table must remain FORCE RLS: {table}")

    if re.search(
        r"\bALTER\s+TABLE\s+(?:public\.)?memory_outbox\s+FORCE\s+ROW\s+LEVEL\s+SECURITY\b",
        combined,
        re.IGNORECASE,
    ):
        errors.append("memory_outbox must not use FORCE RLS; bounded definer leasing needs owner access")
    for label, sql in (("hardening", hard_sql), ("corrective", corrective_sql)):
        _require_count(
            r"\bALTER\s+TABLE\s+public\.memory_outbox\s+NO\s+FORCE\s+ROW\s+LEVEL\s+SECURITY\b",
            sql,
            1,
            f"{label} explicit memory_outbox NO FORCE RLS boundary",
            errors,
        )

    if re.search(
        r"\bCREATE\s+TABLE\s+(?!IF\s+NOT\s+EXISTS\b)(?:public\.)?memory_",
        combined,
        re.IGNORECASE,
    ):
        errors.append("all memory tables must use CREATE TABLE IF NOT EXISTS")

    for index in EXPECTED_INDEXES:
        _require_count(
            rf"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS\s+{index}\b.*?\bON\s+public\.memory_",
            base_sql,
            1,
            f"schema-bound idempotent index {index}",
            errors,
        )


def _validate_context_binding(base: str, corrective: str, errors: list[str]) -> None:
    for label, text in (("base", base), ("corrective", corrective)):
        sql = _normalize(text)
        match = re.search(
            r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\.a11oy_memory_context_matches\s*"
            r"\(\s*row_tenant\s+text\s*,\s*row_domain\s+text\s*\)\s+"
            r"RETURNS\s+boolean\s+(?P<body>.*?)\s*\$\$\s*;",
            sql,
            re.IGNORECASE,
        )
        if match is None:
            errors.append(f"{label} missing inspectable bound RLS context function")
            continue
        body = match.group("body")
        required = {
            "SECURITY DEFINER": r"\bSECURITY\s+DEFINER\b",
            "safe fixed search_path": (
                r"\bSET\s+search_path\s*=\s*pg_catalog\s*,\s*pg_temp\b"
            ),
            "tenant custom GUC comparison": (
                r"row_tenant\s*=\s*current_setting\s*\(\s*'a11oy\.tenant_id'\s*,\s*true\s*\)"
            ),
            "domain custom GUC comparison": (
                r"row_domain\s*=\s*current_setting\s*\(\s*'a11oy\.security_domain'\s*,\s*true\s*\)"
            ),
            "owner-only context binding lookup": (
                r"FROM\s+public\.memory_context_bindings\s+AS\s+binding"
            ),
            "exact catalog session principal binding": (
                r"binding\.principal_oid\s*=\s*\(\s*SELECT\s+role\.oid\s+"
                r"FROM\s+pg_catalog\.pg_roles\s+AS\s+role\s+"
                r"WHERE\s+role\.rolname\s*=\s*session_user\s*\)"
            ),
            "bound tenant": r"binding\.tenant_id\s*=\s*row_tenant",
            "bound security domain": (
                r"binding\.security_domain\s*=\s*row_domain"
            ),
        }
        for requirement, pattern in required.items():
            if re.search(pattern, body, re.IGNORECASE) is None:
                errors.append(
                    f"{label} a11oy_memory_context_matches missing {requirement}"
                )
        if re.search(
            r"pg_catalog\.to_regrole\s*\(\s*session_user\s*\)",
            body,
            re.IGNORECASE,
        ):
            errors.append(
                f"{label} a11oy_memory_context_matches must not reparse session_user as regrole text"
            )
        _require_count(
            r"\bALTER\s+FUNCTION\s+public\.a11oy_memory_context_matches\s*"
            r"\(\s*text\s*,\s*text\s*\)\s+OWNER\s+TO\s+CURRENT_USER\b",
            sql,
            1,
            f"{label} trusted context-function owner convergence",
            errors,
        )

    base_sql = _normalize(base)
    _require_count(
        r"\bREVOKE\s+ALL\s+PRIVILEGES\s+ON\s+FUNCTION\s+"
        r"public\.a11oy_memory_context_matches\s*\(\s*text\s*,\s*text\s*\)\s+"
        r"FROM\s+PUBLIC\b",
        base_sql,
        1,
        "base PUBLIC context-function revoke",
        errors,
    )
    for source_label, source in (("base", base), ("corrective", corrective)):
        sql = _normalize(source)
        preflight = re.search(
            r"\bDO\s+\$\$\s+BEGIN\s+"
            r"IF\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+"
            r"public\.memory_context_bindings\s*\)\s+THEN\s+"
            r"RAISE\s+EXCEPTION\s+USING\s+ERRCODE\s*=\s*'23514'\s*,\s*"
            r"MESSAGE\s*=\s*'pre-existing memory_context_bindings rows lack "
            r"durable write provenance'\s*;\s*END\s+IF\s*;\s*END\s*;\s*\$\$\s*;",
            sql,
            re.IGNORECASE,
        )
        if preflight is None:
            errors.append(
                f"{source_label} missing unconditional durable-provenance preflight"
            )
        else:
            table_position = sql.find(
                "CREATE TABLE IF NOT EXISTS public.memory_context_bindings"
            )
            context_owner = re.search(
                r"ALTER\s+TABLE\s+public\.memory_context_bindings\s+"
                r"OWNER\s+TO\s+CURRENT_USER",
                sql,
                re.IGNORECASE,
            )
            context_enable = re.search(
                r"ALTER\s+TABLE\s+public\.memory_context_bindings\s+"
                r"ENABLE\s+ROW\s+LEVEL\s+SECURITY",
                sql,
                re.IGNORECASE,
            )
            context_no_force = re.search(
                r"ALTER\s+TABLE\s+public\.memory_context_bindings\s+"
                r"NO\s+FORCE\s+ROW\s+LEVEL\s+SECURITY",
                sql,
                re.IGNORECASE,
            )
            other_owner_position = sql.find(
                "ALTER TABLE public.memory_records OWNER TO CURRENT_USER"
            )
            if (
                context_owner is None
                or context_enable is None
                or context_no_force is None
                or not (
                    table_position
                    < context_owner.start()
                    < context_enable.start()
                    < context_no_force.start()
                    < preflight.start()
                    < other_owner_position
                )
            ):
                errors.append(
                    f"{source_label} durable-provenance preflight must inspect physical rows before other mutation"
                )
        if re.search(
            r"\bhelper_was_authenticated\b|\$bound_helper\$",
            sql,
            re.IGNORECASE,
        ):
            errors.append(
                f"{source_label} must not infer binding provenance from current catalog state"
            )


def _validate_receipt_relationships(base: str, corrective: str, errors: list[str]) -> None:
    base_sql = _normalize(base)
    corrective_sql = _normalize(corrective)
    required_base = {
        "tenant/domain receipt key": (
            r"CONSTRAINT\s+memory_receipts_tenant_domain_receipt_key\s+UNIQUE\s*\(\s*tenant_id\s*,\s*security_domain\s*,\s*receipt_id\s*\)"
        ),
        "audit tenant/domain receipt foreign key": (
            r"CONSTRAINT\s+memory_query_audit_tenant_domain_receipt_fkey\s+FOREIGN\s+KEY\s*\(\s*tenant_id\s*,\s*security_domain\s*,\s*receipt_id\s*\)\s+REFERENCES\s+public\.memory_receipts\s*\(\s*tenant_id\s*,\s*security_domain\s*,\s*receipt_id\s*\)"
        ),
        "idempotency tenant/domain receipt foreign key": (
            r"CONSTRAINT\s+memory_idempotency_tenant_domain_receipt_fkey\s+FOREIGN\s+KEY\s*\(\s*tenant_id\s*,\s*security_domain\s*,\s*receipt_id\s*\)\s+REFERENCES\s+public\.memory_receipts\s*\(\s*tenant_id\s*,\s*security_domain\s*,\s*receipt_id\s*\)"
        ),
    }
    for label, pattern in required_base.items():
        _require_count(pattern, base_sql, 1, f"base {label}", errors)
        _require_count(pattern, corrective_sql, 1, f"corrective {label}", errors)

    if re.search(
        r"receipt_id\s+text\s+NOT\s+NULL\s+REFERENCES\s+(?:public\.)?memory_receipts\s*\(\s*receipt_id\s*\)",
        base_sql,
        re.IGNORECASE,
    ):
        errors.append("receipt relationships must not be receipt_id-only")
    for table in ("memory_query_audit", "memory_idempotency"):
        _require_token(
            f"{table} contains a cross-domain receipt reference",
            corrective_sql,
            f"{table} cross-domain preflight",
            errors,
        )
    _require_token(
        "constraint_row.confrelid = 'public.memory_receipts'::pg_catalog.regclass",
        corrective_sql,
        "stale receipt foreign-key sweep",
        errors,
    )


def _validate_append_only(base: str, corrective: str, errors: list[str]) -> None:
    sources = (("base", _normalize(base)), ("corrective", _normalize(corrective)))
    for label, sql in sources:
        _require_count(
            r"\bCREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\.memory_reject_mutation\s*\(\s*\)",
            sql,
            1,
            f"{label} append-only rejection function",
            errors,
        )
        _require_token(
            "ERRCODE='55000'",
            sql,
            f"{label} append-only SQLSTATE 55000",
            errors,
        )
        _require_count(
            r"\bCREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\.memory_touch_updated_at\s*\(\s*\)",
            sql,
            1,
            f"{label} updated-at helper restoration",
            errors,
        )
        for function in ("memory_touch_updated_at", "memory_reject_mutation"):
            _require_count(
                rf"\bALTER\s+FUNCTION\s+public\.{function}\s*\(\s*\)\s+"
                rf"OWNER\s+TO\s+CURRENT_USER\b",
                sql,
                1,
                f"{label} trusted helper owner convergence for {function}",
                errors,
            )

        for table in APPEND_ONLY_TABLES:
            trigger = f"{table}_append_only"
            _require_count(
                rf"\bCREATE\s+TRIGGER\s+{trigger}\s+BEFORE\s+UPDATE\s+OR\s+DELETE\s+ON\s+public\.{table}\b.*?EXECUTE\s+FUNCTION\s+public\.memory_reject_mutation\s*\(\s*\)",
                sql,
                1,
                f"{label} append-only trigger for {table}",
                errors,
            )

    base_sql = sources[0][1]
    for table in APPEND_ONLY_TABLES:
        trigger = f"{table}_append_only"
        _require_count(
            rf"\bDROP\s+TRIGGER\s+IF\s+EXISTS\s+{trigger}\s+ON\s+public\.{table}\b",
            base_sql,
            1,
            f"base idempotent append-only trigger drop for {table}",
            errors,
        )

    corrective_sql = sources[1][1]
    for token, label in (
        ("FROM pg_catalog.pg_trigger AS trigger", "corrective all-trigger catalog sweep"),
        ("AND NOT trigger.tgisinternal", "corrective internal-trigger preservation"),
        ("DROP TRIGGER %I ON public.%I", "corrective stale-trigger removal"),
        ("FROM pg_catalog.pg_rewrite AS rewrite", "corrective rewrite-rule catalog sweep"),
        ("AND rewrite.rulename <> '_RETURN'", "corrective internal rewrite-rule preservation"),
        ("DROP RULE %I ON public.%I", "corrective stale rewrite-rule removal"),
    ):
        _require_token(token, corrective_sql, label, errors)
    trigger_sweep = re.search(
        r"FROM\s+pg_catalog\.pg_trigger\s+AS\s+trigger\b.*?"
        r"relation\.relname\s+IN\s*\((?P<tables>.*?)\)\s+"
        r"AND\s+NOT\s+trigger\.tgisinternal",
        corrective_sql,
        re.IGNORECASE,
    )
    if trigger_sweep is None:
        errors.append("cannot inspect corrective covenant-trigger sweep")
    else:
        observed_tables = frozenset(
            re.findall(r"'([^']+)'", trigger_sweep.group("tables"))
        )
        if observed_tables != frozenset(ALL_COVENANT_TABLES):
            errors.append(
                "corrective trigger sweep table set differs from covenant tables"
            )
    rewrite_sweep = re.search(
        r"FROM\s+pg_catalog\.pg_rewrite\s+AS\s+rewrite\b.*?"
        r"relation\.relname\s+IN\s*\((?P<tables>.*?)\)\s+"
        r"AND\s+rewrite\.rulename\s*<>\s*'_RETURN'",
        corrective_sql,
        re.IGNORECASE,
    )
    if rewrite_sweep is None:
        errors.append("cannot inspect corrective covenant rewrite-rule sweep")
    else:
        observed_tables = frozenset(
            re.findall(r"'([^']+)'", rewrite_sweep.group("tables"))
        )
        if observed_tables != frozenset(ALL_COVENANT_TABLES):
            errors.append(
                "corrective rewrite-rule sweep table set differs from covenant tables"
            )
    for table in ("memory_records", "memory_outbox"):
        trigger = f"{table}_touch_updated_at"
        _require_count(
            rf"\bCREATE\s+TRIGGER\s+{trigger}\s+BEFORE\s+UPDATE\s+ON\s+public\.{table}\b.*?EXECUTE\s+FUNCTION\s+public\.memory_touch_updated_at\s*\(\s*\)",
            corrective_sql,
            1,
            f"corrective updated-at trigger for {table}",
            errors,
        )


def _validate_principal_preamble(
    statements: tuple[Statement, ...], label: str, errors: list[str]
) -> None:
    # The principal must see every row before any preflight or foreign-key
    # validation runs under FORCE RLS, and must own schema public so the schema
    # sweep cannot degrade to warnings. Both checks open the transaction, as the
    # first statement after BEGIN and the safe search_path.
    expected = _top_level_statements(
        PINNED_TRANSACTION_PREAMBLE + PINNED_PRINCIPAL_PRECONDITION
    )
    opening = tuple(statement.signature for statement in statements[: len(expected)])
    if opening != tuple(statement.signature for statement in expected):
        errors.append(
            f"{label} must open with the pinned migration-principal precondition"
        )
    _require_statement_pin(
        statements,
        PINNED_PRINCIPAL_PRECONDITION,
        1,
        f"{label} pinned migration-principal precondition",
        errors,
    )


def _validate_remainder(remainder: str, label: str, errors: list[str]) -> None:
    # Outside the pinned statements, nothing may read, assign or reuse role
    # attributes, create a role, alter a capability role or grant one. One
    # assignment to the observed record, or a reordered ALTER ROLE ...
    # NOSUPERUSER, would otherwise pass every token check.
    if ROLE_ATTRIBUTE_COLUMN.search(remainder):
        errors.append(
            f"{label} role-attribute columns appear outside the pinned statements"
        )
    if re.search(r"\bobserved\s*(?:\.|:=|=)|\bINTO\s+observed\b", remainder, re.IGNORECASE):
        errors.append(
            f"{label} the observed attribute record is used outside the pinned statements"
        )
    if re.search(
        r"\bALTER\s+(?:ROLE|USER|GROUP)\s+\"?(?:a11oy_memory_app|a11oy_memory_worker)\b",
        remainder,
        re.IGNORECASE,
    ):
        errors.append(
            f"{label} capability roles are altered outside the pinned convergence"
        )
    if re.search(r"\bCREATE\s+(?:ROLE|USER|GROUP)\b", remainder, re.IGNORECASE):
        errors.append(f"{label} roles are created outside the pinned convergence")
    if re.search(
        r"\bGRANT\b(?:(?!\bON\b|\bTO\b|;).)*\b(?:a11oy_memory_app|a11oy_memory_worker)\b",
        remainder,
        re.IGNORECASE,
    ):
        errors.append(f"{label} capability roles are granted outside the pinned sweep")
    # A format string names no role, so a regular expression on role names
    # cannot see a dynamic membership change. Only the pinned sweeps make one.
    # format() also takes positional, flagged and width-bearing specifiers
    # such as %1$I, %-10s and %*2$I. _validate_dynamic_sql refuses every other
    # dynamic route; this pattern remains as a second, textual check.
    if re.search(
        r"\b(?:GRANT|REVOKE)\s+(?:(?:ADMIN|INHERIT|SET)\s+OPTION\s+FOR\s+)?"
        r"%(?:[0-9]+\$)?-?(?:[0-9]+|\*(?:[0-9]+\$)?)?[ILs]\s+(?:TO|FROM)\b",
        remainder,
        re.IGNORECASE,
    ):
        errors.append(f"{label} role memberships change outside the pinned sweeps")


MIGRATION_LABELS = {
    BASE_MIGRATION: "base",
    HARDENING_MIGRATION: "hardening",
    CORRECTIVE_MIGRATION: "corrective",
}


def _pinned_statements_for(path: Path) -> tuple[str, ...]:
    dynamic = tuple(sql for sql, _ in DYNAMIC_SQL_PINS[path])
    if path == BASE_MIGRATION:
        return (PINNED_PRINCIPAL_PRECONDITION,) + dynamic
    return (
        PINNED_PRINCIPAL_PRECONDITION,
        *(
            _role_convergence_statement(*roles)
            for roles in ROLE_CONVERGENCE_LAYOUT[MIGRATION_LABELS[path]]
        ),
        PINNED_OUTBOUND_SWEEP_STATEMENT,
        PINNED_INBOUND_SWEEP_STATEMENT,
        PINNED_CONVERGENCE_ASSERTIONS,
        PINNED_LEASE_FUNCTION,
    ) + dynamic


def _flatten(tokens: Iterable[Token], depth: int = 0) -> Iterable[tuple[Token, int]]:
    """Significant tokens, descending into dollar-quoted bodies, with their depth."""
    for token in tokens:
        if token.kind in SKIPPED_TOKENS:
            continue
        if token.kind == "dollar":
            yield from _flatten(_lex(token.body), depth + 1)
        else:
            yield token, depth


def _is_word(token: Token | None, *words: str) -> bool:
    return token is not None and token.kind == "word" and token.text.upper() in words


def _leading_words(statement: Statement, count: int) -> tuple[str, ...]:
    words: list[str] = []
    for token in statement.tokens:
        if token.kind in SKIPPED_TOKENS:
            continue
        if token.kind != "word" or len(words) == count:
            break
        words.append(token.text.upper())
    return tuple(words)


def _creates_trigger(statement: Statement) -> bool:
    words = _leading_words(statement, 5)
    rest = words[1:] if words[:1] == ("CREATE",) else ()
    if rest[:2] == ("OR", "REPLACE"):
        rest = rest[2:]
    if rest[:1] in (("CONSTRAINT",), ("EVENT",)):
        rest = rest[1:]
    return rest[:1] == ("TRIGGER",)


def _runs_dynamic_sql(statement: Statement, flat: list[tuple[Token, int]]) -> bool:
    trigger = _creates_trigger(statement)
    for index, (token, depth) in enumerate(flat):
        if not _is_word(token, "EXECUTE"):
            continue
        following = flat[index + 1][0] if index + 1 < len(flat) else None
        # The EXECUTE privilege in GRANT or REVOKE is followed by ON or a comma;
        # an expression that PL/pgSQL could run cannot start with either.
        if _is_word(following, "ON") or (
            following is not None and following.kind == "punct" and following.text == ","
        ):
            continue
        if trigger and depth == 0 and _is_word(following, "FUNCTION", "PROCEDURE"):
            continue
        return True
    return False


def _changes_membership(flat: list[tuple[Token, int]]) -> bool:
    """A GRANT or REVOKE with no ON in its own statement, or ALTER GROUP."""
    for index, (token, depth) in enumerate(flat):
        previous = flat[index - 1][0] if index else None
        following = flat[index + 1][0] if index + 1 < len(flat) else None
        if _is_word(token, "ALTER") and _is_word(following, "GROUP"):
            return True
        if not _is_word(token, "GRANT", "REVOKE"):
            continue
        if (
            _is_word(token, "GRANT")
            and _is_word(previous, "WITH", "REVOKE")
            and _is_word(following, "OPTION")
        ):
            continue
        # The statement ends at its semicolon or at the edge of the body that
        # holds it; an ON beyond either belongs to another statement.
        for later, later_depth in flat[index + 1 :]:
            if later_depth != depth or (later.kind == "punct" and later.text == ";"):
                return True
            if _is_word(later, "ON"):
                break
        else:
            return True
    return False


def _literal_changes_membership(token: Token) -> bool:
    """A string literal whose SQL would begin with GRANT, REVOKE or ALTER GROUP."""
    value = token.text[token.text.index("'") + 1 : -1].replace("''", "'")
    try:
        inner = [item for item in _lex(value) if item.kind not in SKIPPED_TOKENS]
    except SqlLexError:
        return (
            re.match(r"\s*(?:GRANT|REVOKE|ALTER\s+GROUP)\b", value, re.IGNORECASE)
            is not None
        )
    return bool(inner) and (
        _is_word(inner[0], "GRANT", "REVOKE")
        or (_is_word(inner[0], "ALTER") and len(inner) > 1 and _is_word(inner[1], "GROUP"))
    )


def _has_unlexed_body(statement: Statement) -> bool:
    """A DO or function body that the lexer would read as a string, not code."""
    words = _leading_words(statement, 4)
    if words[:1] == ("DO",):
        return statement.do_body is None
    rest = words[1:] if words[:1] == ("CREATE",) else ()
    if rest[:2] == ("OR", "REPLACE"):
        rest = rest[2:]
    if rest[:1] not in (("FUNCTION",), ("PROCEDURE",)):
        return False
    top = [token for token in statement.tokens if token.kind not in SKIPPED_TOKENS]
    dollars = [index for index, token in enumerate(top) if token.kind == "dollar"]
    languages = [
        top[index + 1] for index, token in enumerate(top[:-1]) if _is_word(token, "LANGUAGE")
    ]
    return not (
        len(dollars) == 1
        and dollars[0] > 0
        and _is_word(top[dollars[0] - 1], "AS")
        and len(languages) == 1
        and _is_word(languages[0], "PLPGSQL", "SQL")
    )


def _validate_dynamic_sql(migrations: dict[Path, str], errors: list[str]) -> None:
    # Outside the pinned statements nothing may run SQL built at run time,
    # change a role membership, or hide code where the lexer reads a string.
    # A membership change that the pinned sweeps did not make cannot be told
    # apart, in the catalog, from a runtime login the owner granted, so no
    # check that runs in a database can catch one; only this static rule can.
    for path, text in migrations.items():
        label = MIGRATION_LABELS[path]
        statements = _top_level_statements(text)
        for pinned_sql, name in DYNAMIC_SQL_PINS[path]:
            _require_statement_pin(statements, pinned_sql, 1, f"{label} pinned {name}", errors)
        pinned_signatures = {
            _pinned_statement(sql).signature for sql in _pinned_statements_for(path)
        }
        problems: set[str] = set()
        for statement in statements:
            if statement.signature in pinned_signatures:
                continue
            flat = list(_flatten(statement.tokens))
            if _runs_dynamic_sql(statement, flat):
                problems.add(f"{label} runs dynamic SQL outside the pinned statements")
            if _changes_membership(flat):
                problems.add(f"{label} role memberships change outside the pinned sweeps")
            if any(
                token.kind == "string" and _literal_changes_membership(token)
                for token, _ in flat
            ):
                problems.add(
                    f"{label} a string literal outside the pinned statements "
                    "begins with GRANT or REVOKE"
                )
            if _has_unlexed_body(statement):
                problems.add(
                    f"{label} DO and function bodies must be $$-quoted plpgsql or sql"
                )
            if any(_is_word(token, "COPY", "LOAD") for token, _ in flat):
                problems.add(f"{label} must not run COPY or LOAD")
        errors.extend(sorted(problems))


def _validate_base_principal(base: str, errors: list[str]) -> None:
    statements = _top_level_statements(base)
    _validate_principal_preamble(statements, "base", errors)
    sql = _normalize(base)
    for message in PRINCIPAL_PRECONDITION_MESSAGES:
        _require_count(
            r"\bRAISE\s+EXCEPTION\s+USING\s+ERRCODE\s*=\s*'42501'\s*,\s*"
            rf"MESSAGE\s*=\s*'{re.escape(message)}'",
            sql,
            1,
            f"base fail-closed convergence assertion ({message[:40]})",
            errors,
        )
    _validate_remainder(
        _remainder(statements, (PINNED_PRINCIPAL_PRECONDITION,)), "base", errors
    )


def _validate_roles_and_grants(sql_text: str, label: str, errors: list[str]) -> None:
    sql = _normalize(sql_text)
    statements = _top_level_statements(sql_text)
    attrs = r"\s+".join(ROLE_ATTRIBUTES)
    for role in ("a11oy_memory_app", "a11oy_memory_worker"):
        _require_count(
            rf"\bCREATE\s+ROLE\s+{role}\s+{attrs}\b",
            sql,
            1,
            f"{label} fully hardened CREATE ROLE for {role}",
            errors,
        )
        if re.search(rf"\bALTER\s+ROLE\s+{role}\s+NOSUPERUSER\s+\w", sql, re.IGNORECASE):
            errors.append(
                f"{label} combined ALTER ROLE for {role} names the superuser "
                "attribute and cannot run under a provider-managed owner"
            )
        _require_count(
            r"\bSELECT\s+role\.rolsuper\s*,\s*role\.rolcreatedb\s*,\s*"
            r"role\.rolcanlogin\s*,\s*role\.rolreplication\s*,\s*"
            r"role\.rolinherit\s*,\s*role\.rolbypassrls\s+INTO\s+observed\s+"
            r"FROM\s+pg_catalog\.pg_roles\s+AS\s+role\s+WHERE\s+"
            rf"role\.rolname\s*=\s*'{role}'\s*;",
            sql,
            1,
            f"{label} catalog read of current attributes for {role}",
            errors,
        )
        # Rewriting the role row first holds it until COMMIT; a concurrent
        # ALTER ROLE then waits and fails instead of landing after the read.
        _require_count(
            rf"\bALTER\s+ROLE\s+{role}\s+NOCREATEROLE\s*;\s*SELECT\s+role\.rolsuper\b",
            sql,
            1,
            f"{label} catalog row lock before reading attributes of {role}",
            errors,
        )
        _require_count(
            r"\bIF\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+pg_catalog\.pg_roles\s+AS\s+"
            rf"role\s+WHERE\s+role\.rolname\s*=\s*'{role}'\s+AND\s+role\.rolsuper\s*\)\s+"
            r"AND\s+NOT\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+pg_catalog\.pg_roles\s+AS\s+"
            r"principal\s+WHERE\s+principal\.rolname\s*=\s*CURRENT_USER\s+AND\s+"
            r"principal\.rolsuper\s*\)\s+THEN\s+RAISE\s+EXCEPTION\s+USING\s+"
            rf"ERRCODE\s*=\s*'42501'\s*,\s*MESSAGE\s*=\s*'{role} holds an attribute "
            r"this migration principal cannot clear'\s*;\s*END\s+IF\s*;\s*"
            rf"ALTER\s+ROLE\s+{role}\s+NOCREATEROLE\s*;",
            sql,
            1,
            f"{label} fail-closed superuser-attribute convergence for {role}",
            errors,
        )
        _require_body_pin(
            statements,
            PINNED_ROLE_CONVERGENCE.format(role=role),
            1,
            f"{label} pinned attribute convergence for {role}",
            errors,
        )
        for column, clause, negated in ROLE_CONVERGENCE_STEPS:
            guard = (
                rf"\bIF\s+NOT\s+observed\.{column}"
                if negated
                else rf"\bIF\s+observed\.{column}"
            )
            _require_count(
                guard + rf"\s+THEN\s+ALTER\s+ROLE\s+{role}\s+{clause}\s*;\s*END\s+IF\s*;",
                sql,
                1,
                f"{label} guarded {clause} convergence for {role}",
                errors,
            )

    # A word-character lookbehind keeps catalog columns such as rolcanlogin
    # from reading as granted attributes while NOLOGIN and friends stay legal.
    forbidden_positive_attributes = {
        "BYPASSRLS": r"(?<![A-Za-z0-9_])BYPASSRLS\b",
        "SUPERUSER": r"(?<![A-Za-z0-9_])SUPERUSER\b",
        "LOGIN": r"(?<![A-Za-z0-9_])LOGIN\b",
        "CREATEDB": r"(?<![A-Za-z0-9_])CREATEDB\b",
        "CREATEROLE": r"(?<![A-Za-z0-9_])CREATEROLE\b",
        "REPLICATION": r"(?<![A-Za-z0-9_])REPLICATION\b",
    }
    for attribute, pattern in forbidden_positive_attributes.items():
        if re.search(pattern, sql, re.IGNORECASE):
            errors.append(f"{label} memory roles must never receive {attribute}")
    if re.search(r"\bRAISE\s+NOTICE\b", sql, re.IGNORECASE):
        errors.append(f"{label} role hardening must fail closed, not raise notice")
    if re.search(
        r"EXCEPTION\s+WHEN\s+insufficient_privilege",
        sql,
        re.IGNORECASE,
    ):
        errors.append(f"{label} must not swallow insufficient role authority")

    membership_requirements = {
        "outbound role-membership catalog sweep": (
            "FROM pg_catalog.pg_auth_members AS edge"
        ),
        "capability membership selector": (
            "child.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')"
        ),
        "cascading capability membership revoke": (
            "REVOKE %I FROM %I CASCADE"
        ),
        "inbound capability membership selector": (
            "parent.rolname IN ('a11oy_memory_app', 'a11oy_memory_worker')"
        ),
        "inbound delegation-right selector": (
            "edge.admin_option"
        ),
        "cascading inbound delegation-right revoke": (
            "REVOKE ADMIN OPTION FOR %I FROM %I CASCADE"
        ),
        "delegated inbound inherit disable": (
            "GRANT %I TO %I WITH INHERIT FALSE, SET FALSE, ADMIN FALSE"
        ),
        "provider-owner ADMIN retention limited to the migration principal": (
            "AND edge.admin_option AND member.rolname <> CURRENT_USER LOOP"
        ),
        "outbound membership convergence assertion": (
            OUTBOUND_CONVERGENCE_MESSAGE
        ),
        "inbound delegation convergence assertion": (
            INBOUND_CONVERGENCE_MESSAGE
        ),
        "schema ACL catalog sweep": (
            "namespace.nspacl"
        ),
        "non-owner schema CREATE selector": (
            "acl.privilege_type = 'CREATE'"
        ),
        "cascading stale schema CREATE revoke": (
            "REVOKE CREATE ON SCHEMA public FROM %I CASCADE"
        ),
        "table ACL catalog sweep": (
            "relation.relacl"
        ),
        "column ACL catalog sweep": (
            "pg_catalog.aclexplode(attribute.attacl)"
        ),
        "cascading non-owner table ACL revoke": (
            "REVOKE ALL PRIVILEGES ON TABLE public.%I FROM %I CASCADE"
        ),
        "cascading non-owner column ACL revoke": (
            "REVOKE ALL PRIVILEGES (%I) ON TABLE public.%I FROM %I CASCADE"
        ),
    }
    for requirement, token in membership_requirements.items():
        _require_token(token, sql, f"{label} {requirement}", errors)
    # A principal that is not a superuser can revoke only grants it made; any
    # other grantor's membership survives with a WARNING. The sweeps must be
    # proven, fail closed, after they run.
    for message in CONVERGENCE_MESSAGES + (
        ROW_SECURITY_PRECONDITION_MESSAGE,
        SCHEMA_OWNER_PRECONDITION_MESSAGE,
    ):
        _require_count(
            r"\bRAISE\s+EXCEPTION\s+USING\s+ERRCODE\s*=\s*'42501'\s*,\s*"
            rf"MESSAGE\s*=\s*'{re.escape(message)}'",
            sql,
            1,
            f"{label} fail-closed convergence assertion ({message[:40]})",
            errors,
        )
    sweep_position = sql.upper().find("REVOKE ADMIN OPTION FOR %I FROM %I CASCADE")
    for message in CONVERGENCE_MESSAGES:
        assertion_position = sql.upper().find(message.upper())
        if sweep_position >= 0 and 0 <= assertion_position < sweep_position:
            errors.append(
                f"{label} membership convergence assertions must follow both sweeps"
            )

    _validate_principal_preamble(statements, label, errors)
    role_statements = tuple(
        _role_convergence_statement(*roles) for roles in ROLE_CONVERGENCE_LAYOUT[label]
    )
    for pinned in role_statements:
        _require_statement_pin(
            statements,
            pinned,
            1,
            f"{label} pinned attribute convergence statement",
            errors,
        )
    for fragment, name in (
        (PINNED_OUTBOUND_SWEEP, "outbound membership sweep"),
        (PINNED_INBOUND_SWEEP, "inbound delegation sweep"),
    ):
        _require_body_pin(statements, fragment, 1, f"{label} pinned {name}", errors)
    for pinned, name in (
        (PINNED_OUTBOUND_SWEEP_STATEMENT, "outbound membership sweep statement"),
        (PINNED_INBOUND_SWEEP_STATEMENT, "inbound delegation sweep statement"),
        (PINNED_CONVERGENCE_ASSERTIONS, "membership and attribute convergence assertions"),
    ):
        _require_statement_pin(statements, pinned, 1, f"{label} pinned {name}", errors)
    assertion_index = _statement_index(statements, PINNED_CONVERGENCE_ASSERTIONS)
    sweep_indexes = (
        _statement_index(statements, PINNED_OUTBOUND_SWEEP_STATEMENT),
        _statement_index(statements, PINNED_INBOUND_SWEEP_STATEMENT),
    )
    if assertion_index >= 0 and any(index > assertion_index for index in sweep_indexes):
        errors.append(
            f"{label} membership convergence assertions must follow both sweeps"
        )

    _validate_remainder(
        _remainder(
            statements,
            (
                PINNED_PRINCIPAL_PRECONDITION,
                *role_statements,
                PINNED_OUTBOUND_SWEEP_STATEMENT,
                PINNED_INBOUND_SWEEP_STATEMENT,
                PINNED_CONVERGENCE_ASSERTIONS,
            ),
        ),
        label,
        errors,
    )
    for table in ALL_COVENANT_TABLES:
        if sql.count(f"'{table}'") < 1:
            errors.append(f"{label} table ACL sweep omits {table}")

    _require_count(
        r"\bGRANT\s+USAGE\s+ON\s+SCHEMA\s+public\s+TO\s+a11oy_memory_app\s*,\s*a11oy_memory_worker\b",
        sql,
        1,
        f"{label} capability schema USAGE grant",
        errors,
    )

    observed: dict[str, frozenset[str]] = {}
    for statement in _statements(sql):
        match = re.fullmatch(
            r"GRANT\s+(?P<privileges>[A-Z, ]+)\s+ON\s+TABLE\s+public\.(?P<table>memory_[a-z0-9_]+)\s+TO\s+a11oy_memory_app",
            statement,
            re.IGNORECASE,
        )
        if match is None:
            continue
        table = match.group("table").lower()
        privileges = frozenset(
            token.strip().upper()
            for token in match.group("privileges").split(",")
            if token.strip()
        )
        if table in observed:
            errors.append(f"{label} duplicate application grant for {table}")
        observed[table] = privileges

    if observed != EXPECTED_APP_GRANTS:
        errors.append(
            f"{label} application table grants differ from the bounded contract: "
            f"expected {EXPECTED_APP_GRANTS}, observed {observed}"
        )

    if re.search(
        r"\bGRANT\b.*?\bON\s+TABLE\s+public\.memory_[a-z0-9_]+\s+TO\s+a11oy_memory_worker\b",
        sql,
        re.IGNORECASE,
    ):
        errors.append(f"{label} worker role must not receive direct memory-table privileges")

    _require_count(
        r"\bGRANT\s+EXECUTE\s+ON\s+FUNCTION\s+public\.a11oy_memory_context_matches\s*\(\s*text\s*,\s*text\s*\)\s+TO\s+a11oy_memory_app\b",
        sql,
        1,
        f"{label} application context-function EXECUTE grant",
        errors,
    )
    _require_count(
        r"\bGRANT\s+EXECUTE\s+ON\s+FUNCTION\s+public\.memory_lease_outbox\s*\(\s*text\s*,\s*integer\s*,\s*integer\s*\)\s+TO\s+a11oy_memory_worker\b",
        sql,
        1,
        f"{label} worker EXECUTE grant",
        errors,
    )
    _require_count(
        r"\bALTER\s+FUNCTION\s+public\.memory_lease_outbox\s*"
        r"\(\s*text\s*,\s*integer\s*,\s*integer\s*\)\s+"
        r"OWNER\s+TO\s+CURRENT_USER\b",
        sql,
        1,
        f"{label} trusted lease-function owner convergence",
        errors,
    )
    _require_token(
        "CROSS JOIN LATERAL pg_catalog.aclexplode",
        sql,
        f"{label} stale function ACL audit",
        errors,
    )
    _require_token(
        "acl.grantee <> procedure.proowner",
        sql,
        f"{label} non-owner function ACL filter",
        errors,
    )
    _require_token(
        "REVOKE ALL PRIVILEGES ON FUNCTION %s FROM %I CASCADE",
        sql,
        f"{label} stale function ACL revoke",
        errors,
    )
    for identity in (
        "public.memory_touch_updated_at()",
        "public.memory_reject_mutation()",
        "public.a11oy_memory_context_matches(text,text)",
        "public.memory_lease_outbox(text,integer,integer)",
    ):
        _require_token(
            f"'{identity}'::pg_catalog.regprocedure",
            sql,
            f"{label} function ACL target {identity}",
            errors,
        )
    if re.search(r"\bGRANT\b.*?\bTO\s+PUBLIC\b", sql, re.IGNORECASE):
        errors.append(f"{label} Memory Covenant must not grant privileges to PUBLIC")
    if re.search(r"\bGRANT\s+ALL\b", sql, re.IGNORECASE):
        errors.append(f"{label} Memory Covenant must not use GRANT ALL")


def _validate_worker_function(sql_text: str, label: str, errors: list[str]) -> None:
    sql = _normalize(sql_text)
    match = re.search(
        r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+public\.memory_lease_outbox\s*\(.*?\)\s+RETURNS\s+SETOF\s+public\.memory_outbox\s+(?P<body>.*?)\s*\$\$\s*;",
        sql,
        re.IGNORECASE,
    )
    if match is None:
        errors.append(f"{label} missing inspectable memory_lease_outbox function")
        return
    body = match.group("body")
    required = {
        "SECURITY DEFINER": r"\bSECURITY\s+DEFINER\b",
        "safe fixed search_path": r"\bSET\s+search_path\s*=\s*pg_catalog\s*,\s*pg_temp\b",
        "worker id validation": r"p_worker_id\s+IS\s+NULL\s+OR\s+p_worker_id\s*=\s*''",
        "NULL item limit rejection": r"p_limit\s+IS\s+NULL",
        "bounded item limit": r"p_limit\s*<\s*1\s+OR\s+p_limit\s*>\s*500(?!\d)",
        "NULL lease duration rejection": r"p_lease_seconds\s+IS\s+NULL",
        "bounded lease duration": r"p_lease_seconds\s*<\s*1\s+OR\s+p_lease_seconds\s*>\s*3600(?!\d)",
        # MEMBER is true for any membership row in PostgreSQL 16 and later, so
        # only USAGE (privileges inherited from the worker role) admits a lease.
        "worker inheritance check": (
            r"IF\s+NOT\s+EXISTS\s*\(\s*SELECT\s+1\s+FROM\s+pg_catalog\.pg_roles\s+"
            r"WHERE\s+rolname\s*=\s*'a11oy_memory_worker'\s*\)\s+OR\s+NOT\s+"
            r"pg_catalog\.pg_has_role\s*\(\s*session_user\s*,\s*'a11oy_memory_worker'\s*,\s*"
            r"'USAGE'\s*\)\s+THEN\s+RAISE\s+EXCEPTION\s+USING\s+ERRCODE\s*=\s*'42501'\s*,\s*"
            r"MESSAGE\s*=\s*'session user does not inherit a11oy_memory_worker'\s*;\s*"
            r"END\s+IF\s*;"
        ),
        "schema-bound outbox": r"\bFROM\s+public\.memory_outbox\b",
        "locked candidate selection": r"FOR\s+UPDATE\s+SKIP\s+LOCKED",
        "request limit": r"LIMIT\s+p_limit",
        "schema-bound update": r"\bUPDATE\s+public\.memory_outbox\b",
        "lease state": r"status\s*=\s*'LEASED'",
        "attempt increment": r"attempts\s*=\s*event\.attempts\s*\+\s*1",
        "lease owner": r"lease_owner\s*=\s*p_worker_id",
        "lease expiry": r"lease_expires_at\s*=\s*pg_catalog\.now\s*\(\s*\)\s*\+\s*pg_catalog\.make_interval",
    }
    for requirement, pattern in required.items():
        if re.search(pattern, body, re.IGNORECASE) is None:
            errors.append(f"{label} memory_lease_outbox missing {requirement}")
    if re.search(r"pg_has_role\s*\([^;]*?'member'", body, re.IGNORECASE):
        errors.append(
            f"{label} memory_lease_outbox must not admit a session user by MEMBER"
        )
    _require_statement_pin(
        _top_level_statements(sql_text),
        PINNED_LEASE_FUNCTION,
        1,
        f"{label} pinned bounded lease function",
        errors,
    )


def _validate_schema_binding(migrations: dict[Path, str], errors: list[str]) -> None:
    for path, text in migrations.items():
        sql = _normalize(text)
        unsafe = {
            "unqualified memory table DDL": (
                r"\b(?:ALTER\s+TABLE|CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS|REFERENCES|ON\s+TABLE)\s+memory_"
            ),
            "unqualified memory function DDL": (
                r"\b(?:CREATE\s+OR\s+REPLACE\s+FUNCTION|ON\s+FUNCTION|EXECUTE\s+FUNCTION)\s+memory_"
            ),
        }
        for label, pattern in unsafe.items():
            if re.search(pattern, sql, re.IGNORECASE):
                errors.append(f"{path.name} contains {label}")


def _validate_forbidden_sql(migrations: dict[Path, str], errors: list[str]) -> None:
    sql = _normalize("\n".join(migrations.values()))
    forbidden = {
        "DROP TABLE": r"\bDROP\s+TABLE\b",
        "DROP SCHEMA": r"\bDROP\s+SCHEMA\b",
        "TRUNCATE": r"\bTRUNCATE\b",
        "RLS disablement": r"\bALTER\s+TABLE\s+(?:public\.)?memory_[a-z0-9_]+\s+DISABLE\s+ROW\s+LEVEL\s+SECURITY\b",
        "row_security off": r"\bSET\s+row_security\s*=\s*off\b",
        "extension installation": r"\bCREATE\s+EXTENSION\b",
        # CURRENT_USER names the trusted principal in the precondition and in
        # every OWNER TO; nothing may switch it mid-migration.
        "role switch": (
            r"\b(?:SET|RESET)\s+(?:(?:LOCAL|SESSION)\s+)?(?:ROLE|SESSION\s+AUTHORIZATION)\b"
            r"|\bset_config\s*\(\s*'(?:role|session_authorization)'"
        ),
        # Ownership is a privilege path that pg_auth_members does not show, and
        # a statement after the assertion block would never meet that check.
        "ownership passed to a capability role": (
            r"\b(?:OWNER\s+TO|AUTHORIZATION)\s+\"?(?:a11oy_memory_app|a11oy_memory_worker)\b"
        ),
        "ownership reassignment": r"\bREASSIGN\s+OWNED\b",
    }
    for label, pattern in forbidden.items():
        if re.search(pattern, sql, re.IGNORECASE):
            errors.append(f"forbidden migration operation: {label}")


def _workflow_value(rest: str) -> str | None:
    """A structure line's value without its comment, or None if unreadable here."""
    value = rest.strip(" ")
    if not value or value.startswith("#"):
        return ""
    head = value.split(" #", 1)[0].rstrip(" ")
    if head in WORKFLOW_BLOCK_INDICATORS:
        return head
    if value[0] == "'":
        whole = re.match(r"'(?:[^']|'')*'", value)
    elif value[0] == '"':
        whole = re.match(r'"[^"\\]*"', value)
    elif value[0] == "[":
        whole = WORKFLOW_FLOW_SEQUENCE.match(value)
    elif value[0] == "{":
        whole = re.match(r"\{ *\}", value)
    elif WORKFLOW_PLAIN_START.match(value):
        return None if ": " in head or head.endswith(":") else head
    else:
        return None
    if whole is None:
        return None
    tail = value[whole.end() :].strip(" ")
    return whole.group(0) if not tail or tail.startswith("#") else None


def _validate_workflow_structure(text: str, errors: list[str]) -> None:
    if "\t" in text:
        errors.append("Memory Covenant workflow must not contain a tab character")
    problems: list[str] = []
    lines = text.split("\n")
    index = 0
    while index < len(lines):
        number, line = index + 1, lines[index]
        index += 1
        if not line.strip(" ") or line.lstrip(" ").startswith("#"):
            continue
        unreadable = (
            f"Memory Covenant workflow line {number} is outside the YAML subset "
            "this validator reads"
        )
        entry = WORKFLOW_ENTRY.match(line)
        if entry is None:
            item = WORKFLOW_ITEM.match(line)
            value = _workflow_value(item.group("rest")) if item else None
            if value is None or value in WORKFLOW_BLOCK_INDICATORS:
                problems.append(unreadable)
            continue
        key = entry.group("key")
        value = _workflow_value(entry.group("rest"))
        if value is None:
            problems.append(unreadable)
            continue
        if key.lower() in WORKFLOW_FORBIDDEN_KEYS:
            problems.append(WORKFLOW_FORBIDDEN_KEYS[key.lower()])
        elif key not in WORKFLOW_ALLOWED_KEYS:
            problems.append(
                f"Memory Covenant workflow key {key!r} on line {number} is outside "
                "the reviewed key set"
            )
        # A shell template such as "true {0}" would run something other than
        # the step's script and exit 0.
        if key == "shell" and value != "bash":
            problems.append("Memory Covenant workflow steps must run with shell: bash")
        if value not in WORKFLOW_BLOCK_INDICATORS:
            continue
        # A block scalar's text is every following line that is blank or at
        # least as indented as its first non-blank line, provided that line is
        # indented past the key, which is how YAML ends one.
        probe = index
        while probe < len(lines) and not lines[probe].strip(" "):
            probe += 1
        if probe == len(lines):
            continue
        indent = len(lines[probe]) - len(lines[probe].lstrip(" "))
        if indent <= entry.start("key"):
            continue
        while index < len(lines) and (
            not lines[index].strip(" ")
            or len(lines[index]) - len(lines[index].lstrip(" ")) >= indent
        ):
            index += 1
    errors.extend(dict.fromkeys(problems))


def _validate_workflow(text: str, errors: list[str]) -> None:
    _require_count(
        r"ref:\s*\$\{\{\s*github\.event\.pull_request\.head\.sha\s*\|\|\s*github\.sha\s*\}\}",
        text,
        3,
        "exact requested-head checkout binding",
        errors,
    )
    _require_count(
        r'test\s+"\$\(git\s+rev-parse\s+HEAD\)"\s*=\s*"\$EXPECTED_SOURCE_SHA"',
        text,
        3,
        "checked-out source identity assertion",
        errors,
    )
    required = {
        "recorded source commit": (
            "git rev-parse HEAD > evidence/memory-covenant-v2/source-sha.txt"
        ),
        "recorded source hashes": (
            "> evidence/memory-covenant-v2/source-sha256.txt"
        ),
        "stale capability parent seed": (
            "GRANT a11oy_memory_stale_parent"
        ),
        "inbound capability delegation seed": (
            "TO a11oy_memory_stale_grantee WITH ADMIN OPTION"
        ),
        "stale relation owner seed": (
            "ALTER TABLE public.memory_context_bindings"
        ),
        "stale function owner seed": (
            "ALTER FUNCTION public.a11oy_memory_context_matches(text, text)"
        ),
        "historical unbound helper seed": (
            "RETURNS boolean LANGUAGE sql STABLE SECURITY INVOKER"
        ),
        "substring-spoofed historical helper seed": (
            "-- public.memory_context_bindings"
        ),
        "substring-spoof reproduction": (
            "spoofed_binding_marker"
        ),
        "untrusted binding-row seed": (
            "'untrusted-domain'"
        ),
        "forced-RLS binding adversary": (
            "ALTER TABLE public.memory_context_bindings FORCE ROW LEVEL SECURITY"
        ),
        "GUC-filtered binding policy adversary": (
            "CREATE POLICY memory_context_bindings_stale_guc_filter"
        ),
        "RLS-hidden binding reproduction": (
            'test "$hidden_binding_count" = "0"'
        ),
        "non-superuser provenance preflight": (
            "printf '%s\\n' 'SET ROLE a11oy_memory_stale_owner;'"
        ),
        "untrusted binding-row rejection": (
            "pre-existing memory_context_bindings rows lack durable write provenance' \\\n"
            "            evidence/memory-covenant-v2/untrusted-binding-provenance.log"
        ),
        "stale owner refused by the row-security precondition": (
            "grep -F 'the migration principal must bypass row security to check existing rows' \\\n"
            "            evidence/memory-covenant-v2/untrusted-binding-preflight.log"
        ),
        "rejected-preflight RLS rollback assertion": (
            'test "$binding_rls_state" = "true:true"'
        ),
        "rejected-preflight policy rollback assertion": (
            'test "$binding_policy_count" = "1"'
        ),
        "rejected-preflight owner rollback assertion": (
            'test "$binding_owner" = "a11oy_memory_stale_owner"'
        ),
        "arbitrary table ACL seed": (
            "public.memory_context_bindings TO a11oy_memory_stale_grantee"
        ),
        "column ACL seed": (
            "GRANT UPDATE (classification) ON TABLE public.memory_records"
        ),
        "PUBLIC table ACL seed": (
            "GRANT SELECT ON TABLE public.memory_records TO PUBLIC"
        ),
        "PUBLIC helper ACL seed": (
            "public.a11oy_memory_context_matches(text, text)\n            TO PUBLIC"
        ),
        "stale append-only helper owner seed": (
            "ALTER FUNCTION public.memory_reject_mutation()"
        ),
        "stale append-only helper body seed": (
            "IF TG_OP = 'DELETE' THEN"
        ),
        "missing append-only trigger seed": (
            "DROP TRIGGER memory_receipts_append_only"
        ),
        "arbitrary user trigger seed": (
            "CREATE TRIGGER memory_records_stale_trigger"
        ),
        "arbitrary rewrite rule seed": (
            "CREATE RULE memory_records_stale_update AS"
        ),
        "disabled RLS seed": (
            "ALTER TABLE public.memory_records DISABLE ROW LEVEL SECURITY"
        ),
        "corrective-only acceptance evidence": (
            "evidence/memory-covenant-v2/corrective-only-acceptance.log"
        ),
        "revoked binding-grant provenance test": (
            "=== prove revoked binding grant lacks durable provenance ==="
        ),
        "revoked binding-grant rejection": (
            "revoked-binding-provenance-preflight.log"
        ),
        "runtime application membership seed": (
            "GRANT a11oy_memory_app TO a11oy_memory_stale_grantee"
        ),
        "untrusted binding column ACL seed": (
            "GRANT INSERT (principal_oid, tenant_id, security_domain)"
        ),
        "temporary binding column ACL revoke": (
            "REVOKE ALL PRIVILEGES (principal_oid, tenant_id, security_domain)"
        ),
        "temporary binding RLS policy seed": (
            "CREATE POLICY memory_context_bindings_temporary_insert"
        ),
        "temporary binding RLS policy revoke": (
            "DROP POLICY memory_context_bindings_temporary_insert"
        ),
        "revoked binding column ACL assertion": (
            "test \"$revoked_binding_acl_count\" = \"0\""
        ),
        "revoked binding RLS policy assertion": (
            "test \"$revoked_binding_policy_count\" = \"0\""
        ),
        "planted binding rollback assertion": (
            "test \"$planted_binding_count\" = \"1\""
        ),
        "runtime application membership cleanup": (
            "DELETE FROM public.memory_context_bindings WHERE tenant_id = 'revoked-grant-tenant'\""
        ),
        "inbound capability membership preservation assertion": (
            'test "$inbound_membership_count" = "2"'
        ),
        "outbound membership evidence": (
            "'outbound_memberships'"
        ),
        "relation ACL evidence": "'relation_acl'",
        "column ACL evidence": "'column_acl'",
        "function ACL evidence": "'function_acl'",
        "schema CREATE ACL evidence": "'schema_create_acl'",
        "context binding evidence": "'context_binding_count'",
        "context definer evidence": "'context_security_definer'",
        "context rollback residue assertion": (
            "grep -F '\"context_binding_rows\": 0'"
        ),
        "provider-owner marker": (
            "=== provider-owner (non-superuser) application ==="
        ),
        "non-superuser provider owner fixture": (
            "CREATE ROLE a11oy_memory_provider_owner LOGIN NOSUPERUSER CREATEDB CREATEROLE BYPASSRLS"
        ),
        "migrations applied by the provider owner": (
            "psql -X -U a11oy_memory_provider_owner -d memory_covenant_provider -v ON_ERROR_STOP=1"
        ),
        "provider owner keeps capability ADMIN": (
            'test "$provider_owner_admin_count" = "2"'
        ),
        "provider owner provisions a runtime login": (
            "GRANT a11oy_memory_app TO a11oy_memory_provider_runtime"
        ),
        "provider-owner acceptance evidence": (
            "provider-owner-acceptance.log"
        ),
        "randomly named hostile delegate": (
            'hostile_delegate="$(random_role)"'
        ),
        "run-unique hostile delegate keeps neither ADMIN, INHERIT nor SET": (
            'test "$hostile_delegate_swept_count" = "2"'
        ),
        "provider-owner refusal marker": (
            "=== provider-owner convergence and fail-closed refusals ==="
        ),
        "provider-owner clearable attribute seed": (
            "ALTER ROLE a11oy_memory_app LOGIN CREATEDB CREATEROLE NOINHERIT BYPASSRLS"
        ),
        "provider-owner attribute convergence assertion": (
            'test "$provider_attribute_deviation_count" = "0"'
        ),
        "provider-owner run-unique delegate is swept": (
            'test "$owner_delegate_swept_count" = "1"'
        ),
        "expected refusals must fail the migration": (
            'if apply_as "$principal" "$migration" "$database" > "$out" 2>&1; then'
        ),
        "superuser-attribute refusal": (
            "'a11oy_memory_worker holds an attribute this migration principal cannot clear'"
        ),
        "foreign-grantor delegation refusal": f"'{INBOUND_CONVERGENCE_MESSAGE}'",
        "outbound membership refusal": f"'{OUTBOUND_CONVERGENCE_MESSAGE}'",
        "swept-delegate SET or INHERIT refusal": f"'{SET_SURVIVOR_MESSAGE}'",
        "row-security bypass precondition refusal": f"'{ROW_SECURITY_PRECONDITION_MESSAGE}'",
        "schema-ownership precondition refusal": f"'{SCHEMA_OWNER_PRECONDITION_MESSAGE}'",
        "refusals roll back and the owner re-applies": (
            "--- every refusal rolled back; the owner re-applies cleanly ---"
        ),
        "lease-guard probe marker": (
            "=== prove the lease guard requires an inherited worker role ==="
        ),
        "swept delegate refused by the lease guard": (
            "evidence/memory-covenant-v2/swept-delegate-lease.log"
        ),
        "SET-only member refused by the lease guard": (
            "evidence/memory-covenant-v2/set-only-lease.log"
        ),
        "lease guard refusal message": f"'{LEASE_GUARD_MESSAGE}'",
        "inheriting worker login still leases": (
            'test "$inherited_lease" = "lease-guard-event:inherited-worker"'
        ),
        "SET-only member refused by the migration": f"'{SET_ONLY_MESSAGE}'",
        "SET-only member refused by the acceptance": f"'{ACCEPTANCE_SET_ONLY_MESSAGE}'",
        "database-ownership marker": (
            "=== prove capability-role database ownership fails closed ==="
        ),
        "capability role made the database owner": (
            "ALTER DATABASE memory_covenant OWNER TO a11oy_memory_app"
        ),
        "ownership refused by the migrations": f"'{OWNERSHIP_MESSAGE}'",
        "ownership refused by the acceptance": f"'{ACCEPTANCE_OWNERSHIP_MESSAGE}'",
        "every state refusal also runs against the corrective alone": (
            'for migration in "$hardening" "$corrective"; do\n'
            '              expect_refusal a11oy_memory_provider_owner "$migration" "$message"'
        ),
        "corrective alone converges clearable deviations": (
            'test "$corrective_attribute_deviation_count" = "0"'
        ),
        "SET-only member fixture": (
            "GRANT a11oy_memory_worker TO ${setonly_member} WITH INHERIT FALSE, SET TRUE"
        ),
        "raced grant made by a delegate that held ADMIN": (
            'psql -X -U "$raced_grantor" -d memory_covenant_provider -v ON_ERROR_STOP=1 \\\n'
            '            -c "GRANT a11oy_memory_worker TO ${raced_member}"'
        ),
        "raced grantor reduced to the swept shape": (
            "UPDATE pg_catalog.pg_auth_members SET admin_option = false, "
            "inherit_option = false, set_option = false WHERE roleid = "
            "'a11oy_memory_worker'::regrole AND member = '${raced_grantor}'::regrole"
        ),
        "raced end state present before the refusal": (
            'test "$raced_row_count" = "1"'
        ),
        "raced grant refused by the migrations": f"'{GRANTOR_MESSAGE}'",
        "raced grant refused by the acceptance": f"'{ACCEPTANCE_GRANTOR_MESSAGE}'",
        "schema owned by a capability role": (
            "CREATE SCHEMA ${capability_schema} AUTHORIZATION a11oy_memory_app"
        ),
        "provider database owned by a capability role": (
            "ALTER DATABASE memory_covenant_provider OWNER TO a11oy_memory_app"
        ),
        "base migration refuses principals too": (
            'for migration in "$base" "$hardening" "$corrective"; do'
        ),
        "database-owning principal without BYPASSRLS": (
            "CREATE DATABASE memory_covenant_unbypassed OWNER a11oy_memory_unbypassed_owner"
        ),
        "database-owning principal owns schema public": (
            'test "$unbypassed_owner_owns_public" = "t"'
        ),
        "database-owning principal refused for row security": (
            '"$ev/refusal-row-security-database-owner-${name}.log" \\\n'
            "              memory_covenant_unbypassed"
        ),
        "provider owner meets a legacy cross-domain receipt": (
            'expect_refusal a11oy_memory_provider_owner "$corrective" \\\n'
            "            'memory_query_audit contains a cross-domain receipt reference'"
        ),
    }
    for label, token in required.items():
        _require_token(token, text, f"workflow {label}", errors)
    _require_count(
        r"^[ \t]*expect_state_refusal[ \t]+(?:\\$|')",
        text,
        8,
        "workflow state refusals run against both migrations",
        errors,
        flags=re.MULTILINE,
    )
    _require_count(
        re.escape("\"$(od -An -N8 -tx1 /dev/urandom | tr -d ' \\n')\""),
        text,
        2,
        "workflow random delegate names in both database jobs",
        errors,
        flags=0,
    )
    _require_count(
        re.escape("printf '%s%s' \"${letters:$((RANDOM % 26)):1}\""),
        text,
        2,
        "workflow random first letter in both database jobs",
        errors,
        flags=0,
    )
    # Delegates are named at random and can log in, so a sweep that skips a
    # fixed fixture name or NOLOGIN roles still meets them. The names still
    # follow a pattern, and CI-only state is visible to the migrations, so a
    # filter keyed to either passes these jobs; only _validate_dynamic_sql and
    # the pins refuse such code.
    for variable in SEEDED_DELEGATE_VARIABLES:
        assignments = re.findall(rf"(?m)^[ \t]*{variable}=(.*)$", text)
        if not assignments:
            errors.append(f"workflow seeded delegate {variable} is missing")
        for value in assignments:
            if value.strip() != '"$(random_role)"':
                errors.append(
                    f"workflow seeded delegate {variable} must be named by random_role"
                )
        if not re.search(rf"\bCREATE\s+ROLE\s+\$\{{{variable}\}}\s+LOGIN\b", text):
            errors.append(f"workflow seeded delegate {variable} must be able to log in")
        if re.search(rf"\bCREATE\s+ROLE\s+\$\{{{variable}\}}\s+(?!LOGIN\b)", text):
            errors.append(f"workflow seeded delegate {variable} must be able to log in")
    if re.search(r"a11oy_[a-z_]*delegate_\$\{GITHUB_RUN_ID", text):
        errors.append("workflow delegate names must not carry a fixed prefix")
    # A job or step skipped by an if: condition reports as skipped, which can
    # satisfy a required check, so this workflow carries no if: key at all. A
    # step that continues on error leaves its job green when it fails. The
    # structure scan finds these keys in any YAML spelling; the patterns below
    # also run over block scalars.
    _validate_workflow_structure(text, errors)
    if_message = WORKFLOW_FORBIDDEN_KEYS["if"]
    if if_message not in errors and (
        WORKFLOW_IF_KEY.search(text)
        or WORKFLOW_FLOW_IF_KEY.search(text)
        or WORKFLOW_ESCAPED_KEY.search(text)
        or WORKFLOW_COMPLEX_KEY.search(text)
        or WORKFLOW_MERGE_KEY.search(text)
    ):
        errors.append(if_message)
    ordered_markers = (
        "=== forward corrective migration ===",
        "=== corrective-only acceptance ===",
        "=== prove the lease guard requires an inherited worker role ===",
        "=== prove revoked binding grant lacks durable provenance ===",
        "=== full second pass ===",
        "=== prove capability-role database ownership fails closed ===",
    )
    marker_positions = tuple(text.find(marker) for marker in ordered_markers)
    if any(position < 0 for position in marker_positions) or marker_positions != tuple(
        sorted(marker_positions)
    ):
        errors.append(
            "workflow must run corrective-only acceptance before historical migration reapplication"
        )
    if re.search(r"\bcontinue-on-error\s*:\s*true\b", text, re.IGNORECASE):
        errors.append("Memory Covenant workflow must not continue on error")


def _validate_acceptance(text: str, errors: list[str]) -> None:
    sql = _normalize(text)
    expected_triggers = {
        "memory_idempotency.memory_idempotency_append_only",
        "memory_outbox.memory_outbox_touch_updated_at",
        "memory_query_audit.memory_query_audit_append_only",
        "memory_receipts.memory_receipts_append_only",
        "memory_records.memory_records_touch_updated_at",
    }
    for trigger in expected_triggers:
        _require_token(
            f"'{trigger}'",
            sql,
            f"acceptance exact trigger identity {trigger}",
            errors,
        )
    for token, label in (
        (
            "FROM pg_catalog.pg_trigger AS trigger",
            "acceptance trigger catalog inspection",
        ),
        (
            "AND NOT trigger.tgisinternal",
            "acceptance internal-trigger exclusion",
        ),
        (
            "FROM pg_rewrite AS rewrite",
            "acceptance rewrite-rule catalog inspection",
        ),
        (
            "Memory Covenant relation retained a user rewrite rule",
            "acceptance rewrite-rule absence assertion",
        ),
        (
            "AND edge.admin_option",
            "acceptance inbound ADMIN OPTION inspection",
        ),
        (
            "Memory Covenant capability membership retained ADMIN OPTION",
            "acceptance inbound ADMIN OPTION absence assertion",
        ),
        (
            "Seeded inbound capability membership was not preserved",
            "acceptance inbound capability membership preservation assertion",
        ),
        (
            "AND edge.member = 'a11oy_memory_stale_grantee'::regrole "
            "AND NOT edge.admin_option AND NOT edge.inherit_option "
            "AND NOT edge.set_option",
            "acceptance swept delegate keeps neither INHERIT nor SET",
        ),
        (
            "A swept capability-role delegate keeps SET or INHERIT through another grant",
            "acceptance swept-delegate SET or INHERIT survivor assertion",
        ),
        (
            "A tenant/domain receipt reference does not resolve",
            "acceptance tenant/domain receipt row validity assertion",
        ),
        (
            "observed_triggers IS DISTINCT FROM expected_triggers",
            "acceptance exact trigger-set comparison",
        ),
        (
            "memory_context_bindings must remain NO FORCE RLS for owner-unfiltered provenance checks",
            "acceptance context-binding NO FORCE RLS assertion",
        ),
        (
            "memory_context_bindings retained a stale RLS policy",
            "acceptance context-binding policy cleanup assertion",
        ),
        (
            "UPDATE memory_query_audit",
            "acceptance append-only audit update probe",
        ),
        (
            "DELETE FROM memory_query_audit",
            "acceptance append-only audit delete probe",
        ),
        (
            "UPDATE memory_idempotency",
            "acceptance append-only idempotency update probe",
        ),
        (
            "DELETE FROM memory_idempotency",
            "acceptance append-only idempotency delete probe",
        ),
    ):
        _require_token(token, sql, label, errors)
    for token, label in (
        (ACCEPTANCE_SET_ONLY_MESSAGE, "acceptance SET-without-INHERIT membership assertion"),
        (ACCEPTANCE_GRANTOR_MESSAGE, "acceptance grantor-holds-ADMIN assertion"),
        (ACCEPTANCE_OWNERSHIP_MESSAGE, "acceptance capability-role ownership assertion"),
    ):
        _require_token(token, sql, label, errors)
    statements = _top_level_statements(text)
    _require_body_pin(
        statements,
        PINNED_ACCEPTANCE_ADMIN_EXEMPTION,
        1,
        "acceptance ADMIN OPTION exemption limited to the covenant owner",
        errors,
    )
    _require_body_pin(
        statements,
        PINNED_ACCEPTANCE_ATTRIBUTE_ASSERTION,
        1,
        "acceptance role-attribute assertion",
        errors,
    )
    _require_statement_pin(
        statements,
        PINNED_ACCEPTANCE_ROLE_ASSERTIONS,
        1,
        "acceptance pinned role and membership assertions",
        errors,
    )
    _require_count(
        r"WHEN\s+SQLSTATE\s+'55000'",
        sql,
        6,
        "acceptance append-only SQLSTATE probes",
        errors,
    )


def validate(root: Path | str = Path(".")) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    migrations = {
        relative: _read_utf8_file(root, relative, errors) for relative in MIGRATIONS
    }
    workflow = _read_utf8_file(root, WORKFLOW, errors)
    acceptance = _read_utf8_file(root, ACCEPTANCE, errors)
    if any(not text for text in migrations.values()) or not workflow or not acceptance:
        return errors
    # Every later check reads the lexer's view of the SQL. Text that psql and
    # PostgreSQL would read differently is refused before any check trusts it.
    lexable = [
        _validate_lexical(relative.name, text, errors)
        for relative, text in migrations.items()
    ]
    lexable.append(
        _validate_lexical(
            ACCEPTANCE.name,
            acceptance,
            errors,
            psql_preamble=ACCEPTANCE_PSQL_PREAMBLE,
        )
    )
    if not all(lexable):
        return errors

    base = migrations[BASE_MIGRATION]
    hardening = migrations[HARDENING_MIGRATION]
    corrective = migrations[CORRECTIVE_MIGRATION]
    _validate_transactions(migrations, errors)
    _validate_base_principal(base, errors)
    _validate_tables_and_rls(base, hardening, corrective, errors)
    _validate_context_binding(base, corrective, errors)
    _validate_receipt_relationships(base, corrective, errors)
    _validate_append_only(base, corrective, errors)
    for label, text in (("hardening", hardening), ("corrective", corrective)):
        _validate_roles_and_grants(text, label, errors)
        _validate_worker_function(text, label, errors)
    _validate_schema_binding(migrations, errors)
    _validate_forbidden_sql(migrations, errors)
    _validate_dynamic_sql(migrations, errors)
    _validate_workflow(workflow, errors)
    _validate_acceptance(acceptance, errors)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    args = parser.parse_args(argv)
    errors = validate(args.root)
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print("Memory Covenant v2 static contract: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
