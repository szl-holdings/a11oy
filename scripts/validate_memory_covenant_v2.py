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

MEMORY_TABLES = (
    "memory_records",
    "memory_evidence_refs",
    "memory_outbox",
    "memory_receipts",
    "memory_query_audit",
    "memory_index_generations",
    "memory_idempotency",
)
FORCE_RLS_TABLES = frozenset(MEMORY_TABLES) - {"memory_outbox"}
APPEND_ONLY_TABLES = (
    "memory_receipts",
    "memory_query_audit",
    "memory_idempotency",
)
EXPECTED_INDEXES = (
    "memory_receipts_scope_id_uidx",
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


def _validate_transactions(
    base: str, hardening: str, errors: list[str]
) -> None:
    for label, text in (("base migration", base), ("hardening migration", hardening)):
        normalized = _normalize(text)
        _require_count(r"\bBEGIN\s*;", normalized, 1, f"{label} BEGIN", errors)
        _require_count(r"\bCOMMIT\s*;", normalized, 1, f"{label} COMMIT", errors)
        if not normalized.upper().startswith("BEGIN;"):
            errors.append(f"{label} must start with BEGIN")
        if not normalized.upper().endswith("COMMIT;"):
            errors.append(f"{label} must end with COMMIT")
        if re.search(r"\bROLLBACK\b", normalized, re.IGNORECASE):
            errors.append(f"{label} must not contain ROLLBACK")


def _validate_tables_and_rls(base: str, hardening: str, errors: list[str]) -> None:
    base_sql = _normalize(base)
    hard_sql = _normalize(hardening)
    combined = f"{base_sql} {hard_sql}"

    for table in MEMORY_TABLES:
        _require_count(
            rf"\bCREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+{table}\b",
            base_sql,
            1,
            f"idempotent table {table}",
            errors,
        )
        _require_count(
            rf"\bALTER\s+TABLE\s+{table}\s+ENABLE\s+ROW\s+LEVEL\s+SECURITY\b",
            base_sql,
            1,
            f"RLS enablement for {table}",
            errors,
        )
        policy = f"{table}_isolation"
        _require_count(
            rf"\bDROP\s+POLICY\s+IF\s+EXISTS\s+{policy}\s+ON\s+{table}\b",
            base_sql,
            1,
            f"idempotent policy drop for {table}",
            errors,
        )
        _require_count(
            rf"\bCREATE\s+POLICY\s+{policy}\s+ON\s+{table}\b",
            base_sql,
            1,
            f"isolation policy for {table}",
            errors,
        )
        match = re.search(
            rf"CREATE\s+POLICY\s+{policy}\s+ON\s+{table}\s+(?P<body>.*?)\s*;",
            base_sql,
            re.IGNORECASE,
        )
        if match is None:
            errors.append(f"cannot inspect isolation policy for {table}")
        else:
            body = match.group("body")
            if len(
                re.findall(
                    r"a11oy_memory_context_matches\s*\(\s*tenant_id\s*,\s*security_domain\s*\)",
                    body,
                    re.IGNORECASE,
                )
            ) != 2:
                errors.append(
                    f"{table} policy must bind both USING and WITH CHECK to tenant/domain context"
                )
            if not re.search(r"\bUSING\s*\(", body, re.IGNORECASE):
                errors.append(f"{table} policy is missing USING")
            if not re.search(r"\bWITH\s+CHECK\s*\(", body, re.IGNORECASE):
                errors.append(f"{table} policy is missing WITH CHECK")

    reset_match = re.search(
        r"DO\s+\$\$\s+DECLARE\s+stale_policy\s+record\s*;\s+BEGIN"
        r"(?P<body>.*?)END\s*;\s*\$\$\s*;",
        base_sql,
        re.IGNORECASE,
    )
    if reset_match is None:
        errors.append("missing fail-closed reset of pre-existing Memory Covenant policies")
    else:
        reset_body = reset_match.group("body")
        required_reset_tokens = {
            "policy catalog": r"\bFROM\s+pg_policy\b",
            "policy table catalog": r"\bJOIN\s+pg_class\b",
            "policy namespace catalog": r"\bJOIN\s+pg_namespace\b",
            "public schema scope": r"n\.nspname\s*=\s*'public'",
            "schema-qualified policy drop": (
                r"'DROP\s+POLICY\s+%I\s+ON\s+%I\.%I'"
            ),
        }
        for label, pattern in required_reset_tokens.items():
            if re.search(pattern, reset_body, re.IGNORECASE) is None:
                errors.append(f"policy reset is missing {label}")
        for table in MEMORY_TABLES:
            if re.search(rf"'{table}'", reset_body, re.IGNORECASE) is None:
                errors.append(f"policy reset must cover {table}")
        first_policy_create = re.search(r"\bCREATE\s+POLICY\b", base_sql, re.IGNORECASE)
        if first_policy_create and reset_match.start() > first_policy_create.start():
            errors.append("policy reset must run before isolation policies are created")

    for table in FORCE_RLS_TABLES:
        _require_count(
            rf"\bALTER\s+TABLE\s+{table}\s+FORCE\s+ROW\s+LEVEL\s+SECURITY\b",
            base_sql,
            1,
            f"FORCE RLS for {table}",
            errors,
        )
        if re.search(
            rf"\bALTER\s+TABLE\s+{table}\s+NO\s+FORCE\s+ROW\s+LEVEL\s+SECURITY\b",
            combined,
            re.IGNORECASE,
        ):
            errors.append(f"tenant table must remain FORCE RLS: {table}")

    if re.search(
        r"\bALTER\s+TABLE\s+memory_outbox\s+FORCE\s+ROW\s+LEVEL\s+SECURITY\b",
        combined,
        re.IGNORECASE,
    ):
        errors.append("memory_outbox must not use FORCE RLS; bounded definer leasing needs owner access")
    _require_count(
        r"\bALTER\s+TABLE\s+memory_outbox\s+NO\s+FORCE\s+ROW\s+LEVEL\s+SECURITY\b",
        hard_sql,
        1,
        "explicit memory_outbox NO FORCE RLS boundary",
        errors,
    )

    if re.search(
        r"\bCREATE\s+TABLE\s+(?!IF\s+NOT\s+EXISTS\b)memory_",
        combined,
        re.IGNORECASE,
    ):
        errors.append("all memory tables must use CREATE TABLE IF NOT EXISTS")

    for index in EXPECTED_INDEXES:
        _require_count(
            rf"\bCREATE\s+(?:UNIQUE\s+)?INDEX\s+IF\s+NOT\s+EXISTS\s+{index}\b",
            base_sql,
            1,
            f"idempotent index {index}",
            errors,
        )


def _validate_receipt_scope(base: str, errors: list[str]) -> None:
    sql = _normalize(base)
    _require_count(
        r"\bCREATE\s+UNIQUE\s+INDEX\s+IF\s+NOT\s+EXISTS\s+"
        r"memory_receipts_scope_id_uidx\s+ON\s+memory_receipts\s*"
        r"\(\s*tenant_id\s*,\s*security_domain\s*,\s*receipt_id\s*\)",
        sql,
        1,
        "tenant/domain receipt reference key",
        errors,
    )

    cleanup_match = re.search(
        r"DO\s+\$\$\s+DECLARE\s+receipt_reference\s+record\s*;\s+BEGIN"
        r"(?P<body>.*?)END\s*;\s*\$\$\s*;",
        sql,
        re.IGNORECASE,
    )
    if cleanup_match is None:
        errors.append("missing legacy receipt foreign-key reset")
    else:
        cleanup_body = cleanup_match.group("body")
        required_cleanup_tokens = {
            "foreign-key catalog filter": r"constraint_entry\.contype\s*=\s*'f'",
            "receipt target filter": (
                r"constraint_entry\.confrelid\s*=\s*"
                r"'public\.memory_receipts'::regclass"
            ),
            "query-audit scope": r"'memory_query_audit'",
            "idempotency scope": r"'memory_idempotency'",
            "schema-qualified constraint drop": (
                r"'ALTER\s+TABLE\s+%I\.%I\s+DROP\s+CONSTRAINT\s+%I'"
            ),
        }
        for label, pattern in required_cleanup_tokens.items():
            if re.search(pattern, cleanup_body, re.IGNORECASE) is None:
                errors.append(f"receipt foreign-key reset is missing {label}")

    for table in ("memory_query_audit", "memory_idempotency"):
        constraint = f"{table}_receipt_scope_fkey"
        _require_count(
            rf"\bALTER\s+TABLE\s+{table}\s+ADD\s+CONSTRAINT\s+{constraint}\s+"
            rf"FOREIGN\s+KEY\s*\(\s*tenant_id\s*,\s*security_domain\s*,\s*receipt_id\s*\)\s+"
            rf"REFERENCES\s+memory_receipts\s*"
            rf"\(\s*tenant_id\s*,\s*security_domain\s*,\s*receipt_id\s*\)\s+"
            rf"ON\s+DELETE\s+RESTRICT",
            sql,
            1,
            f"tenant/domain-bound receipt reference for {table}",
            errors,
        )

    if re.search(
        r"\bREFERENCES\s+memory_receipts\s*\(\s*receipt_id\s*\)",
        sql,
        re.IGNORECASE,
    ):
        errors.append("receipt references must never use receipt_id alone")


def _validate_append_only(base: str, errors: list[str]) -> None:
    sql = _normalize(base)
    _require_count(
        r"\bCREATE\s+OR\s+REPLACE\s+FUNCTION\s+memory_reject_mutation\s*\(\s*\)",
        sql,
        1,
        "append-only rejection function",
        errors,
    )
    _require_token("ERRCODE='55000'", sql, "append-only SQLSTATE 55000", errors)

    for table in APPEND_ONLY_TABLES:
        trigger = f"{table}_append_only"
        _require_count(
            rf"\bDROP\s+TRIGGER\s+IF\s+EXISTS\s+{trigger}\s+ON\s+{table}\b",
            sql,
            1,
            f"idempotent append-only trigger drop for {table}",
            errors,
        )
        _require_count(
            rf"\bCREATE\s+TRIGGER\s+{trigger}\s+BEFORE\s+UPDATE\s+OR\s+DELETE\s+ON\s+{table}\b.*?EXECUTE\s+FUNCTION\s+memory_reject_mutation\s*\(\s*\)",
            sql,
            1,
            f"append-only trigger for {table}",
            errors,
        )


def _validate_roles_and_grants(hardening: str, errors: list[str]) -> None:
    sql = _normalize(hardening)
    bounded_attributes = (
        r"NOSUPERUSER\s+NOCREATEDB\s+NOCREATEROLE\s+NOLOGIN\s+INHERIT\s+"
        r"NOREPLICATION\s+NOBYPASSRLS"
    )
    for role in ("a11oy_memory_app", "a11oy_memory_worker"):
        _require_count(
            rf"\bCREATE\s+ROLE\s+{role}\s+{bounded_attributes}\b",
            sql,
            1,
            f"hardened CREATE ROLE for {role}",
            errors,
        )
        _require_count(
            rf"\bALTER\s+ROLE\s+{role}\s+{bounded_attributes}\b",
            sql,
            1,
            f"hardened ALTER ROLE for {role}",
            errors,
        )

    if re.search(r"(?<!NO)BYPASSRLS\b", sql, re.IGNORECASE):
        errors.append("memory roles must never receive BYPASSRLS")
    if re.search(r"(?<!NO)SUPERUSER\b", sql, re.IGNORECASE):
        errors.append("memory roles must never receive SUPERUSER")
    if re.search(r"(?<!NO)CREATEDB\b", sql, re.IGNORECASE):
        errors.append("memory roles must never receive CREATEDB")
    if re.search(r"(?<!NO)CREATEROLE\b", sql, re.IGNORECASE):
        errors.append("memory roles must never receive CREATEROLE")
    if re.search(r"(?<!NO)REPLICATION\b", sql, re.IGNORECASE):
        errors.append("memory roles must never receive REPLICATION")
    if re.search(r"(?<!NO)LOGIN\b", sql, re.IGNORECASE):
        errors.append("memory capability roles must remain NOLOGIN")
    if re.search(r"\bWHEN\s+insufficient_privilege\b", sql, re.IGNORECASE):
        errors.append("capability-role hardening must fail closed on insufficient privilege")

    for role in ("a11oy_memory_app", "a11oy_memory_worker"):
        _require_count(
            rf"\bREVOKE\s+ALL\s+PRIVILEGES\s+ON\s+SCHEMA\s+public\s+FROM\s+{role}\b",
            sql,
            1,
            f"schema ACL reset for {role}",
            errors,
        )
        _require_count(
            rf"\bGRANT\s+USAGE\s+ON\s+SCHEMA\s+public\s+TO\s+{role}\b",
            sql,
            1,
            f"bounded schema USAGE grant for {role}",
            errors,
        )

    first_bounded_grant = re.search(
        r"\bGRANT\s+(?:USAGE|SELECT|INSERT|UPDATE|DELETE)", sql, re.IGNORECASE
    )
    worker_grant = re.search(
        r"\bGRANT\s+EXECUTE\s+ON\s+FUNCTION\s+memory_lease_outbox",
        sql,
        re.IGNORECASE,
    )
    for table in MEMORY_TABLES:
        app_revoke = re.search(
            rf"\bREVOKE\s+ALL\s+PRIVILEGES\s+ON\s+TABLE\s+{table}\s+"
            rf"FROM\s+PUBLIC\s*,\s*a11oy_memory_app\b",
            sql,
            re.IGNORECASE,
        )
        if app_revoke is None:
            errors.append(f"missing bounded ACL reset for application table {table}")
        elif first_bounded_grant and app_revoke.start() > first_bounded_grant.start():
            errors.append(f"application ACL reset must precede grants for {table}")

        worker_revoke = re.search(
            rf"\bREVOKE\s+ALL\s+PRIVILEGES\s+ON\s+TABLE\s+{table}\s+"
            rf"FROM\s+a11oy_memory_worker\b",
            sql,
            re.IGNORECASE,
        )
        if worker_revoke is None:
            errors.append(f"missing bounded ACL reset for worker table {table}")
        elif worker_grant and worker_revoke.start() > worker_grant.start():
            errors.append(f"worker ACL reset must precede grants for {table}")

    _require_count(
        r"\bREVOKE\s+ALL\s+ON\s+FUNCTION\s+memory_lease_outbox\s*"
        r"\(\s*text\s*,\s*integer\s*,\s*integer\s*\)\s+FROM\s+PUBLIC\s*,\s*"
        r"a11oy_memory_app\s*,\s*a11oy_memory_worker\b",
        sql,
        1,
        "PUBLIC and capability-role function revoke",
        errors,
    )

    observed: dict[str, frozenset[str]] = {}
    for statement in _statements(sql):
        match = re.fullmatch(
            r"GRANT\s+(?P<privileges>[A-Z, ]+)\s+ON\s+(?:TABLE\s+)?(?P<table>memory_[a-z0-9_]+)\s+TO\s+a11oy_memory_app",
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
            errors.append(f"duplicate application grant for {table}")
        observed[table] = privileges

    if observed != EXPECTED_APP_GRANTS:
        errors.append(
            "application table grants differ from the bounded contract: "
            f"expected {EXPECTED_APP_GRANTS}, observed {observed}"
        )

    if re.search(
        r"\bGRANT\b.*?\bON\s+(?:TABLE\s+)?memory_[a-z0-9_]+\s+TO\s+a11oy_memory_worker\b",
        sql,
        re.IGNORECASE,
    ):
        errors.append("worker role must not receive direct memory-table privileges")

    _require_count(
        r"\bGRANT\s+EXECUTE\s+ON\s+FUNCTION\s+memory_lease_outbox\s*\(\s*text\s*,\s*integer\s*,\s*integer\s*\)\s+TO\s+a11oy_memory_worker\b",
        sql,
        1,
        "worker EXECUTE grant",
        errors,
    )
    if re.search(r"\bGRANT\b.*?\bTO\s+PUBLIC\b", sql, re.IGNORECASE):
        errors.append("Memory Covenant must not grant privileges to PUBLIC")
    if re.search(r"\bGRANT\s+ALL\b", sql, re.IGNORECASE):
        errors.append("Memory Covenant must not use GRANT ALL")


def _validate_worker_function(hardening: str, errors: list[str]) -> None:
    sql = _normalize(hardening)
    match = re.search(
        r"CREATE\s+OR\s+REPLACE\s+FUNCTION\s+memory_lease_outbox\s*\(.*?\)\s+RETURNS\s+SETOF\s+memory_outbox\s+(?P<body>.*?)\s*\$\$\s*;",
        sql,
        re.IGNORECASE,
    )
    if match is None:
        errors.append("missing inspectable memory_lease_outbox function")
        return
    body = match.group("body")
    required = {
        "SECURITY DEFINER": r"\bSECURITY\s+DEFINER\b",
        "fixed search_path": r"\bSET\s+search_path\s*=\s*public\s*,\s*pg_temp\b",
        "worker id validation": r"p_worker_id\s+IS\s+NULL\s+OR\s+p_worker_id\s*=\s*''",
        "null item-limit rejection": r"p_limit\s+IS\s+NULL",
        "null lease-duration rejection": r"p_lease_seconds\s+IS\s+NULL",
        "bounded item limit": r"p_limit\s*<\s*1\s+OR\s+p_limit\s*>\s*500(?!\d)",
        "bounded lease duration": r"p_lease_seconds\s*<\s*1\s+OR\s+p_lease_seconds\s*>\s*3600(?!\d)",
        "worker membership check": r"pg_has_role\s*\(\s*session_user\s*,\s*'a11oy_memory_worker'\s*,\s*'member'\s*\)",
        "locked candidate selection": r"FOR\s+UPDATE\s+SKIP\s+LOCKED",
        "request limit": r"LIMIT\s+p_limit",
        "lease state": r"status\s*=\s*'LEASED'",
        "attempt increment": r"attempts\s*=\s*event\.attempts\s*\+\s*1",
        "lease owner": r"lease_owner\s*=\s*p_worker_id",
        "lease expiry": r"lease_expires_at\s*=\s*now\s*\(\s*\)\s*\+\s*make_interval",
    }
    for label, pattern in required.items():
        if re.search(pattern, body, re.IGNORECASE) is None:
            errors.append(f"memory_lease_outbox missing {label}")


def _validate_forbidden_sql(base: str, hardening: str, errors: list[str]) -> None:
    sql = _normalize(f"{base}\n{hardening}")
    forbidden = {
        "DROP TABLE": r"\bDROP\s+TABLE\b",
        "DROP SCHEMA": r"\bDROP\s+SCHEMA\b",
        "TRUNCATE": r"\bTRUNCATE\b",
        "RLS disablement": r"\bALTER\s+TABLE\s+memory_[a-z0-9_]+\s+DISABLE\s+ROW\s+LEVEL\s+SECURITY\b",
        "row_security off": r"\bSET\s+row_security\s*=\s*off\b",
        "extension installation": r"\bCREATE\s+EXTENSION\b",
    }
    for label, pattern in forbidden.items():
        if re.search(pattern, sql, re.IGNORECASE):
            errors.append(f"forbidden migration operation: {label}")


def validate(root: Path | str = Path(".")) -> list[str]:
    root = Path(root)
    errors: list[str] = []
    base = _read_utf8_file(root, BASE_MIGRATION, errors)
    hardening = _read_utf8_file(root, HARDENING_MIGRATION, errors)
    if not base or not hardening:
        return errors

    _validate_transactions(base, hardening, errors)
    _validate_tables_and_rls(base, hardening, errors)
    _validate_receipt_scope(base, errors)
    _validate_append_only(base, errors)
    _validate_roles_and_grants(hardening, errors)
    _validate_worker_function(hardening, errors)
    _validate_forbidden_sql(base, hardening, errors)
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
