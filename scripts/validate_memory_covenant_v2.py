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
        _require_count(
            rf"\bALTER\s+ROLE\s+{role}\s+{attrs}\b",
            sql,
            1,
            f"{label} fully hardened ALTER ROLE for {role}",
            errors,
        )

    forbidden_positive_attributes = {
        "BYPASSRLS": r"(?<!NO)BYPASSRLS\b",
        "SUPERUSER": r"(?<!NO)SUPERUSER\b",
        "LOGIN": r"(?<!NO)LOGIN\b",
        "CREATEDB": r"(?<!NO)CREATEDB\b",
        "CREATEROLE": r"(?<!NO)CREATEROLE\b",
        "REPLICATION": r"(?<!NO)REPLICATION\b",
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
        2,
        "exact requested-head checkout binding",
        errors,
    )
    _require_count(
        r'test\s+"\$\(git\s+rev-parse\s+HEAD\)"\s*=\s*"\$EXPECTED_SOURCE_SHA"',
        text,
        2,
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
            "pre-existing memory_context_bindings rows lack durable write provenance"
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
            "REVOKE a11oy_memory_app FROM a11oy_memory_stale_grantee"
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
