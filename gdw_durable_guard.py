#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Services: pure admission for the exact paused legacy startup guard.

Schema validation is not evidence acquisition. Canonical acquisition observes
the provider and runs the pinned-image source probe before recording this
metadata. Configuration rereads the bound Space state before any effect.
"""

import hashlib
import json
import re
from datetime import datetime, timezone

SCHEMA = "szl.gdw-legacy-export-guard/v1"
SPACE_REVISION = "cc9214315db74cd2fe9f546ae777186093e1a9eb"
IMAGE = "python:3.14-slim@sha256:caaf356f40667c496d405780745b9ac25771c189a51dfcc42430d531ea09f8a2"
MODE = "private-dataset-v1"
EXPORT_GUARD = "durable-private-dataset-v1"
PROBE_SCOPE = "SOURCE_IMPORTS_AND_ENTRYPOINT_AFTER_INTERPRETER_INITIALIZATION"
SOURCE_FILES = {
    "Dockerfile": "a5801759653604580ff38e964855a340e62c04a9500deb185dad72f8f0fe3a68",
    "requirements-runtime.txt": "92476938854727bd503dc0f2ea076b4245ed821971665ca283286b45f6d73562",
    "gdw_runtime.py": "14a139cd5129ad9513681c306afbd123005e7a10d457c89b224b9a1a1d31ff1c",
    "gdw_workspace.py": "e557b54f8ca1256027677c423ddd369d984e61adbc87cda7813d9a58d6585f8e",
    "gdw_proofs.py": "022776048affd25ff34a8f9393cd7ea8a7c8ca2e5ca01621929c0011ae7817e3",
    "szl_dsse.py": "e095670051088929365f3eb4c76716122148d8f6b898db52f0e27867c221608c",
    "szl_content_address.py": "211b69d47fbbddf496fcfdedb0311e6fe6b67b67428100dd27ce7ce1f7247b10",
}
CASES = ("default", "production_disabled", "persistence_disabled", "outbox_disabled",
         "durable_flag", "wal_requested", "normal_sync", "combined_bypass_flags")
MANAGED_VARIABLES = {
    "GDW_PROOF_EXPORT_MODE": EXPORT_GUARD,
    "GDW_DURABLE_STORAGE": MODE,
    "GDW_REQUIRED_MOUNT": "",
    "A11OY_SERIES_A_REQUIRE_MOUNT": "",
    "GDW_SQLITE_JOURNAL": "DELETE",
    "GDW_SQLITE_SYNCHRONOUS": "FULL",
    "A11OY_SERIES_A_SQLITE_JOURNAL": "DELETE",
    "GDW_REQUIRE_PERSISTENT_STORAGE": "1",
    "A11OY_REQUIRE_PERSISTENT_STORAGE": "1",
    "GDW_PRODUCTION_MODE": "1",
    "A11OY_REQUIRE_PERSISTENT_SIGNING": "1",
    "GDW_PROOF_DIR": "/data/a11oy/gdw/proofs",
    "GDW_RECEIPT_PROJECTION_DIR": "/data/a11oy/gdw/receipts",
}
REQUIRED_SECRETS = {"HF_TOKEN", "GDW_CREDENTIALS_JSON", "SZL_COSIGN_PRIVATE_PEM"}


class GuardBlocked(RuntimeError):
    pass


def canonical(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
                          allow_nan=False).encode("ascii") + b"\n"
    except Exception:
        raise GuardBlocked("LEGACY_GUARD_INVALID") from None


def _shape(value, fields):
    if type(value) is not dict or set(value) != fields:
        raise GuardBlocked("LEGACY_GUARD_INVALID")
    return value


def _fixed(value, expected):
    if type(value) is not type(expected) or value != expected:
        raise GuardBlocked("LEGACY_GUARD_UNQUALIFIED")


def _digest(value):
    if type(value) is not str or re.fullmatch(r"[0-9a-f]{64}", value) is None or value == "0" * 64:
        raise GuardBlocked("LEGACY_GUARD_IDENTITY_INVALID")


def validate_legacy_guard(value):
    _shape(value, {"schema", "state", "space_revision", "image", "command", "working_directory",
                   "source_files_sha256", "observation", "native_probe"})
    _fixed(value["schema"], SCHEMA)
    _fixed(value["state"], "QUALIFIED_LEGACY_STARTUP_GUARD")
    _fixed(value["space_revision"], SPACE_REVISION)
    _fixed(value["image"], IMAGE)
    _fixed(value["command"], ["python", "gdw_runtime.py"])
    _fixed(value["working_directory"], "/app")
    _fixed(value["source_files_sha256"], SOURCE_FILES)
    observation = _shape(value["observation"], {"stage", "observed_at", "public_variables_sha256",
                                                "secret_names_sha256", "startup_overrides_absent"})
    _fixed(observation["stage"], "PAUSED")
    _fixed(observation["startup_overrides_absent"], True)
    for key in ("public_variables_sha256", "secret_names_sha256"):
        _digest(observation[key])
    try:
        observed = datetime.strptime(observation["observed_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        if observed.strftime("%Y-%m-%dT%H:%M:%SZ") != observation["observed_at"]:
            raise ValueError()
    except (TypeError, ValueError):
        raise GuardBlocked("LEGACY_GUARD_OBSERVATION_INVALID") from None
    probe = _shape(value["native_probe"], {"state", "scope", "python_version", "case_count", "case_results_sha256",
        "report_sha256", "source_closure_sha256", "forbidden_effect_count", "unguarded_control"})
    _fixed(probe["state"], "PREWRITE_REJECTION_VERIFIED")
    _fixed(probe["scope"], PROBE_SCOPE)
    if type(probe["python_version"]) is not str or re.fullmatch(r"3\.14\.\d{1,3}", probe["python_version"]) is None:
        raise GuardBlocked("PINNED_RUNTIME_INTERPRETER_PROOF_REQUIRED")
    _fixed(probe["case_count"], len(CASES))
    _fixed(probe["forbidden_effect_count"], 0)
    _fixed(probe["unguarded_control"], "PREPARATION_WRITE_OBSERVED")
    _fixed(probe["source_closure_sha256"], hashlib.sha256(canonical(SOURCE_FILES)).hexdigest())
    for key in ("case_results_sha256", "report_sha256"):
        _digest(probe[key])
    return json.loads(canonical(value))


def validate_environment(variables, secret_names):
    if (type(variables) is not dict or type(secret_names) is not list or len(variables) > 256
            or len(secret_names) > 256):
        raise GuardBlocked("LEGACY_ENVIRONMENT_UNQUALIFIED")
    for name in list(variables) + secret_names:
        if (type(name) is not str or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", name) is None
                or name.startswith(("PYTHON", "LD_"))
                or name in {"_PYTHON_SYSCONFIGDATA_NAME", "PATH", "HOME", "USER", "SHELL", "ENV", "BASH_ENV"}):
            raise GuardBlocked("LEGACY_STARTUP_OVERRIDE_REJECTED")
    if len(secret_names) != len(set(secret_names)):
        raise GuardBlocked("LEGACY_ENVIRONMENT_UNQUALIFIED")
    if (not REQUIRED_SECRETS <= set(secret_names) or set(secret_names).intersection(MANAGED_VARIABLES)
            or (REQUIRED_SECRETS | {"GDW_PRINCIPALS_JSON"}).intersection(variables)
            or "GDW_PRINCIPALS_JSON" in secret_names):
        raise GuardBlocked("LEGACY_CREDENTIAL_METADATA_UNQUALIFIED")
    if any(type(item) is not str or len(item.encode("utf-8")) > 8192 for item in variables.values()):
        raise GuardBlocked("LEGACY_ENVIRONMENT_UNQUALIFIED")
    if len(canonical(variables)) > 64 * 1024:
        raise GuardBlocked("LEGACY_ENVIRONMENT_UNQUALIFIED")


def validate_legacy_guard_observation(guard, observed, *, baseline_variables=None, expected_variables=None):
    """Before guard: exact paused baseline. After guard: only fixed changes.

    The initial full variable map stays private to this invocation. A partial
    uncertain invocation cannot create a fresh baseline or silently retry.
    """
    guard = validate_legacy_guard(guard)
    _shape(observed, {"space_revision", "stage", "variables", "secret_names", "variables_sha256"})
    variables, names = observed["variables"], observed["secret_names"]
    validate_environment(variables, names)
    _fixed(observed["space_revision"], SPACE_REVISION)
    _fixed(observed["variables_sha256"], hashlib.sha256(canonical(variables)).hexdigest())
    _fixed(hashlib.sha256(canonical(sorted(names))).hexdigest(), guard["observation"]["secret_names_sha256"])
    if baseline_variables is None and expected_variables is None:
        _fixed(observed["stage"], "PAUSED")
        _fixed(observed["variables_sha256"], guard["observation"]["public_variables_sha256"])
    else:
        if type(baseline_variables) is not dict or type(expected_variables) is not dict:
            raise GuardBlocked("LEGACY_GUARD_BASELINE_REQUIRED")
        _fixed(hashlib.sha256(canonical(baseline_variables)).hexdigest(), guard["observation"]["public_variables_sha256"])
        if set(baseline_variables) - set(expected_variables):
            raise GuardBlocked("LEGACY_GUARD_VARIABLE_DELETION_REJECTED")
        for name, value in expected_variables.items():
            if baseline_variables.get(name) != value:
                if name not in MANAGED_VARIABLES or type(value) is not str or value != MANAGED_VARIABLES[name]:
                    raise GuardBlocked("LEGACY_GUARD_VARIABLE_SCOPE_REJECTED")
        _fixed(expected_variables.get("GDW_PROOF_EXPORT_MODE"), EXPORT_GUARD)
        if observed["stage"] not in {"PAUSED", "RUNTIME_ERROR", "BUILDING"}:
            raise GuardBlocked("LEGACY_GUARD_PROCESS_NOT_STOPPED")
        _fixed(variables, expected_variables)
    return json.loads(canonical(observed))
