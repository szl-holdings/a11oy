#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed static contract for the Memory Covenant v2 migrations."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Iterable

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
# catalog shows a deviation. A provider-managed owner (Neon, for example) is
# never a superuser, and PostgreSQL rejects any ALTER ROLE that names the
# superuser attribute unless the caller is one, even to clear it.
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
ATTRIBUTE_CONVERGENCE_MESSAGE = "a capability role attribute did not converge"
CONVERGENCE_MESSAGES = (
    OUTBOUND_CONVERGENCE_MESSAGE,
    INBOUND_CONVERGENCE_MESSAGE,
    SET_SURVIVOR_MESSAGE,
    ATTRIBUTE_CONVERGENCE_MESSAGE,
)
ROW_SECURITY_PRECONDITION_MESSAGE = (
    "the migration principal must bypass row security to check existing rows"
)
SCHEMA_OWNER_PRECONDITION_MESSAGE = "the migration principal must own schema public"

# Security-critical statements are pinned whole. Substring tokens let an extra
# predicate (for example a name-pattern exemption) slip into a WHERE clause
# while every token still matches; a pinned statement changes only together
# with this validator, in the same reviewed diff. Comments and whitespace are
# normalized before comparison.
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
ROLE_ATTRIBUTE_COLUMN = re.compile(
    r"\brol(?:super|createdb|createrole|canlogin|replication|inherit|bypassrls)\b",
    re.IGNORECASE,
)


def _without_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    return "\n".join(line.split("--", 1)[0] for line in text.splitlines())


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", _without_comments(text)).strip()


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
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"invalid UTF-8 in {relative.as_posix()}: {exc}")
        return ""


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


def _require_pinned(
    pinned_sql: str, normalized_sql: str, expected: int, label: str, errors: list[str]
) -> None:
    actual = normalized_sql.count(_normalize(pinned_sql))
    if actual != expected:
        errors.append(f"{label}: expected {expected} exact copy, found {actual}")


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


def _validate_roles_and_grants(sql_text: str, label: str, errors: list[str]) -> None:
    sql = _normalize(sql_text)
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
        _require_pinned(
            PINNED_ROLE_CONVERGENCE.format(role=role),
            sql,
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

    # The principal must see every row before any preflight or foreign-key
    # validation runs under FORCE RLS, and must own schema public so the schema
    # sweep cannot degrade to warnings. Both checks open the transaction.
    if not sql.startswith(
        _normalize(PINNED_TRANSACTION_PREAMBLE + PINNED_PRINCIPAL_PRECONDITION)
    ):
        errors.append(
            f"{label} must open with the pinned migration-principal precondition"
        )
    _require_pinned(
        PINNED_PRINCIPAL_PRECONDITION,
        sql,
        1,
        f"{label} pinned migration-principal precondition",
        errors,
    )
    for pinned, name in (
        (PINNED_OUTBOUND_SWEEP, "outbound membership sweep"),
        (PINNED_INBOUND_SWEEP, "inbound delegation sweep"),
        (PINNED_CONVERGENCE_ASSERTIONS, "membership and attribute convergence assertions"),
    ):
        _require_pinned(pinned, sql, 1, f"{label} pinned {name}", errors)
    if sql.find(_normalize(PINNED_CONVERGENCE_ASSERTIONS)) < sql.find(
        _normalize(PINNED_INBOUND_SWEEP)
    ):
        errors.append(
            f"{label} membership convergence assertions must follow both sweeps"
        )

    # Outside the pinned statements, nothing may read, assign or reuse role
    # attributes, and nothing may alter a capability role. One assignment to
    # the observed record, or a reordered ALTER ROLE ... NOSUPERUSER, would
    # otherwise pass every token check.
    remainder = sql
    for pinned in (
        PINNED_PRINCIPAL_PRECONDITION,
        PINNED_ROLE_CONVERGENCE.format(role="a11oy_memory_app"),
        PINNED_ROLE_CONVERGENCE.format(role="a11oy_memory_worker"),
        PINNED_CONVERGENCE_ASSERTIONS,
    ):
        remainder = remainder.replace(_normalize(pinned), " ")
    if ROLE_ATTRIBUTE_COLUMN.search(remainder):
        errors.append(
            f"{label} role-attribute columns appear outside the pinned statements"
        )
    if re.search(r"\bobserved\s*(?:\.|:=|=)|\bINTO\s+observed\b", remainder, re.IGNORECASE):
        errors.append(
            f"{label} the observed attribute record is used outside the pinned statements"
        )
    if re.search(
        r"\bALTER\s+(?:ROLE|USER)\s+\"?(?:a11oy_memory_app|a11oy_memory_worker)\b",
        remainder,
        re.IGNORECASE,
    ):
        errors.append(
            f"{label} capability roles are altered outside the pinned convergence"
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
        "worker membership check": r"pg_catalog\.pg_has_role\s*\(\s*session_user\s*,\s*'a11oy_memory_worker'\s*,\s*'member'\s*\)",
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
    }
    for label, pattern in forbidden.items():
        if re.search(pattern, sql, re.IGNORECASE):
            errors.append(f"forbidden migration operation: {label}")


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
        "run-unique hostile delegate": (
            'hostile_delegate="a11oy_hostile_delegate_${GITHUB_RUN_ID:-local}_${RANDOM}"'
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
            'if apply_as "$principal" "$migration" > "$out" 2>&1; then'
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
    }
    for label, token in required.items():
        _require_token(token, text, f"workflow {label}", errors)
    ordered_markers = (
        "=== forward corrective migration ===",
        "=== corrective-only acceptance ===",
        "=== prove revoked binding grant lacks durable provenance ===",
        "=== full second pass ===",
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
    _require_pinned(
        PINNED_ACCEPTANCE_ADMIN_EXEMPTION,
        sql,
        1,
        "acceptance ADMIN OPTION exemption limited to the covenant owner",
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

    base = migrations[BASE_MIGRATION]
    hardening = migrations[HARDENING_MIGRATION]
    corrective = migrations[CORRECTIVE_MIGRATION]
    _validate_transactions(migrations, errors)
    _validate_tables_and_rls(base, hardening, corrective, errors)
    _validate_context_binding(base, corrective, errors)
    _validate_receipt_relationships(base, corrective, errors)
    _validate_append_only(base, corrective, errors)
    for label, text in (("hardening", hardening), ("corrective", corrective)):
        _validate_roles_and_grants(text, label, errors)
        _validate_worker_function(text, label, errors)
    _validate_schema_binding(migrations, errors)
    _validate_forbidden_sql(migrations, errors)
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
