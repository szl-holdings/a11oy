#!/usr/bin/env python3
"""Check manual GDW credential prerequisites without mutating credentials.

Admission additionally requires independently verified installed signing
authority (``scripts/verify_installed_authority.py``): the live runtime public
key must match the pinned runtime key. Secret values are never read.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Mapping


CANONICAL_SPACE = "SZLHOLDINGS/a11oy"
DATA_MOUNT = "/data"
PRINCIPAL_ID = "gdw-operator"
PRINCIPAL_REGISTRY_SECRET = "GDW_PRINCIPALS_JSON"
CREDENTIAL_REGISTRY_SECRET = "GDW_CREDENTIALS_JSON"
CREDENTIAL_KEY_ID = "gdw-operator-v1"
STATIC_VARIABLES = {
    "GDW_PRODUCTION_MODE": "1",
    "GDW_NAMESPACE": "a11oy",
    "GDW_SERVICE_OWNER_ID": "gdw-runtime",
    "GDW_DB_PATH": "/data/a11oy/gdw/gdw.sqlite3",
    "GDW_PROOF_DIR": "/data/a11oy/gdw/proofs",
    "GDW_RECEIPT_PROJECTION_DIR": "/data/a11oy/gdw/receipts",
    "GDW_REQUIRE_PERSISTENT_STORAGE": "1",
    "GDW_REQUIRED_MOUNT": DATA_MOUNT,
    "GDW_SQLITE_SYNCHRONOUS": "FULL",
    "GDW_PROOF_EXPORT_MODE": "outbox",
    # The mounted Hugging Face bucket is a network filesystem. DELETE avoids
    # WAL shared-memory assumptions while preserving transactional SQLite.
    "GDW_SQLITE_JOURNAL": "DELETE",
    # Admission ceilings, not integrity gates. Every deployment of main opens
    # exactly one governed promotion session plus one governed promotion
    # request, and those objects stay ACTIVE for GDW_RETENTION_SECONDS (7 days)
    # before the retention compactor tombstones them and releases the slot.
    # The previous owner ceiling of 100 active sessions was far below this
    # estate's real 7-day deployment volume, so the ceiling stayed saturated
    # and POST /gdw/step intermittently answered 429 OWNER_SESSIONS_QUOTA,
    # failing the sync while the runtime itself was healthy. Sizing the
    # ceilings above the true 7-day working set removes that false failure.
    # The substantive resource guard is GDW_OWNER_MAX_STORED_BYTES, which is
    # deliberately unchanged, so unbounded growth is still refused.
    "GDW_OWNER_MAX_ACTIVE_REQUESTS": "50000",
    "GDW_OWNER_MAX_ACTIVE_SESSIONS": "5000",
    "GDW_OWNER_MAX_PENDING_EFFECTS": "2000",
    "GDW_OWNER_MAX_STORED_BYTES": "268435456",
    "GDW_GLOBAL_MAX_ACTIVE_REQUESTS": "500000",
    "GDW_GLOBAL_MAX_ACTIVE_SESSIONS": "50000",
    "GDW_GLOBAL_MAX_PENDING_EFFECTS": "100000",
    "GDW_GLOBAL_MAX_STORED_BYTES": "2147483648",
    "GDW_OWNER_MAX_ARTIFACTS": "10000",
    "GDW_GLOBAL_MAX_ARTIFACTS": "100000",
    "GDW_RETENTION_SECONDS": "604800",
    "GDW_TOMBSTONE_SECONDS": "2592000",
    "GDW_EFFECT_MAX_ATTEMPTS": "20",
    "GDW_EFFECT_BACKOFF_SECONDS": "5",
    "GDW_OUTBOX_ENABLED": "1",
    "GDW_OUTBOX_INTERVAL_SECONDS": "5",
    "GDW_OUTBOX_RETRY_MAX_SECONDS": "60",
    "GDW_OUTBOX_BATCH_SIZE": "100",
    "GDW_OUTBOX_LEASE_SECONDS": "300",
    # The policy gateway is co-resident in the canonical container. Exact
    # loopback avoids an external same-Space hairpin after singleton locking.
    "GDW_POLICY_ORIGIN": "http://127.0.0.1:7860",
}


DEFAULT_CANONICAL_ORIGIN = "https://szlholdings-a11oy.hf.space"
INSTALLED_AUTHORITY_DIAGNOSTICS = (
    "INSTALLED_AUTHORITY_VERIFIED", "AUTHORITY_ORIGIN_NOT_CANONICAL", "AUTHORITY_ORIGIN_UNAVAILABLE",
    "SIGNING_KEY_NOT_INSTALLED", "SIGNING_KEY_MISMATCH", "PINNED_KEY_INCONSISTENT",
    "SIGNING_SECRET_MISSING", "GDW_CREDENTIALS_MISSING",
)


def load_authority_verifier() -> Any:
    """Load the sibling verifier by path (scripts/ is not a package)."""
    cached = sys.modules.get("verify_installed_authority")
    if cached is not None:
        return cached
    path = Path(__file__).resolve().with_name("verify_installed_authority.py")
    spec = importlib.util.spec_from_file_location("verify_installed_authority", path)
    if spec is None or spec.loader is None:
        raise ImportError("installed-authority verifier is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_installed_authority"] = module
    try:
        spec.loader.exec_module(module)
    except Exception:
        sys.modules.pop("verify_installed_authority", None)
        raise
    return module


def canonical_origin() -> str:
    return os.environ.get("CANONICAL_ORIGIN") or DEFAULT_CANONICAL_ORIGIN


class RuntimeConfigError(RuntimeError):
    """Fail closed with a fixed public diagnostic and no provider error text."""

    def __init__(self, message: str, *, diagnostic_code: str = "PREREQUISITES_UNAVAILABLE") -> None:
        super().__init__(message)
        allowed = {
            "PREREQUISITES_UNAVAILABLE", "CANONICAL_DESTINATION_REQUIRED",
            "CREDENTIAL_METADATA_UNAVAILABLE", "CREDENTIAL_METADATA_MALFORMED",
            "CREDENTIAL_NAMES_MALFORMED", "PUBLIC_VARIABLE_COLLISION",
            "LEGACY_PRINCIPAL_CONFLICT", "PERSISTENT_STORAGE_UNAVAILABLE",
            "SPACE_CLIENT_UNAVAILABLE", "INSTALLED_AUTHORITY_UNKNOWN",
            "HF_CONTROL_CREDENTIAL_MISSING", "CHECK_MODE_MALFORMED",
            *INSTALLED_AUTHORITY_DIAGNOSTICS,
        }
        self.diagnostic_code = diagnostic_code if diagnostic_code in allowed else "PREREQUISITES_UNAVAILABLE"


def _value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def desired_variables() -> dict[str, str]:
    return dict(STATIC_VARIABLES)


def plan_variables(
    current: Mapping[str, Any],
    secret_names: set[str],
    desired: Mapping[str, str],
) -> dict[str, str]:
    collisions = sorted(set(desired) & secret_names)
    if collisions:
        raise RuntimeConfigError(
            "GDW variable names collide with Space secrets: "
            + ",".join(collisions)
        )
    return {
        name: value
        for name, value in desired.items()
        if str(_value(current.get(name), "value", "")) != value
    }


def manual_prerequisites(api: Any, *, repo_id: str, origin: str | None = None,
                         authority_get: Callable | None = None) -> dict[str, Any]:
    """Inspect metadata without deriving, replacing or retiring any credential.

    READY only when ``GDW_CREDENTIALS_JSON`` is present by name and the
    installed signing authority verifies against the pinned runtime key.
    """
    if repo_id != CANONICAL_SPACE:
        raise RuntimeConfigError("SETUP_REQUIRED: only the canonical A11oy Space is admitted", diagnostic_code="CANONICAL_DESTINATION_REQUIRED")
    try:
        secrets = api.get_space_secrets(repo_id=repo_id)
        variables = api.get_space_variables(repo_id=repo_id)
    except Exception:
        raise RuntimeConfigError("SETUP_REQUIRED: Space credential metadata is unavailable", diagnostic_code="CREDENTIAL_METADATA_UNAVAILABLE") from None
    if not isinstance(secrets, (Mapping, list, tuple, set)) or not isinstance(variables, Mapping):
        raise RuntimeConfigError("SETUP_REQUIRED: Space credential metadata is malformed", diagnostic_code="CREDENTIAL_METADATA_MALFORMED")
    try:
        secret_names = list(secrets)
        variable_names = list(variables)
        if not all(type(name) is str for name in secret_names + variable_names):
            raise ValueError("invalid metadata names")
        names = set(secret_names)
        public_names = set(variable_names)
    except Exception:
        raise RuntimeConfigError("SETUP_REQUIRED: Space credential names are malformed", diagnostic_code="CREDENTIAL_NAMES_MALFORMED") from None
    if {CREDENTIAL_REGISTRY_SECRET, PRINCIPAL_REGISTRY_SECRET}.intersection(public_names):
        raise RuntimeConfigError("SETUP_REQUIRED: a credential registry collides with a public variable", diagnostic_code="PUBLIC_VARIABLE_COLLISION")
    if PRINCIPAL_REGISTRY_SECRET in names:
        raise RuntimeConfigError("SETUP_REQUIRED: legacy GDW principals require owner resolution", diagnostic_code="LEGACY_PRINCIPAL_CONFLICT")
    try:
        volume = require_data_mount(api, repo_id=repo_id)
    except Exception:
        raise RuntimeConfigError("SETUP_REQUIRED: persistent GDW volume metadata is unavailable or conflicting", diagnostic_code="PERSISTENT_STORAGE_UNAVAILABLE") from None
    try:
        authority = load_authority_verifier().verify_installed_authority(
            names, public_names, origin=origin or canonical_origin(), get=authority_get)
    except Exception:
        raise RuntimeConfigError("SETUP_REQUIRED: installed credential authority is UNKNOWN", diagnostic_code="INSTALLED_AUTHORITY_UNKNOWN") from None
    verified = (authority.get("credential_authority_state") == "VERIFIED"
                and CREDENTIAL_REGISTRY_SECRET in names)
    diagnostic = authority.get("diagnostic_code")
    if not verified and (diagnostic == "INSTALLED_AUTHORITY_VERIFIED"
                         or diagnostic not in INSTALLED_AUTHORITY_DIAGNOSTICS):
        diagnostic = "INSTALLED_AUTHORITY_UNKNOWN"
    return {
        "schema": "szl.hf-gdw-runtime-config/v1", "repo_id": repo_id,
        "state": "READY" if verified else "SETUP_REQUIRED",
        "diagnostic_code": "INSTALLED_AUTHORITY_VERIFIED" if verified else diagnostic,
        "required_secret_names": [CREDENTIAL_REGISTRY_SECRET],
        "missing_secret_names": [] if CREDENTIAL_REGISTRY_SECRET in names else [CREDENTIAL_REGISTRY_SECRET],
        "data_volume": volume,
        "credential_authority_state": "VERIFIED" if verified else "UNKNOWN",
        "gdw_authority": authority["gdw"],
        "installed_authority": authority,
        "converged": verified, "secret_values_read": False, "secret_values_written": False,
    }


def require_data_mount(api: Any, *, repo_id: str) -> dict[str, Any]:
    info = api.space_info(repo_id=repo_id)
    runtime = getattr(info, "runtime", None)
    volumes = getattr(runtime, "volumes", None) if runtime is not None else None
    if volumes is None:
        raise RuntimeConfigError("Space runtime did not include volume metadata")
    at_data = [
        item
        for item in volumes
        if str(_value(item, "mount_path", "")) == DATA_MOUNT
    ]
    if len(at_data) != 1 or type(_value(at_data[0], "read_only")) is not bool or _value(at_data[0], "read_only"):
        raise RuntimeConfigError("GDW requires one read-write /data volume")
    # Only these fields were validated; opaque topology cannot enter a report.
    return {"mount_path": DATA_MOUNT, "read_only": False}


def await_readback(
    api: Any,
    *,
    repo_id: str,
    secret_names: set[str],
    desired: Mapping[str, str],
    attempts: int = 60,
    delay_seconds: float = 5,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    if attempts < 1 or delay_seconds < 0:
        raise RuntimeConfigError("readback bounds must be non-negative")
    for attempt in range(1, attempts + 1):
        remaining = plan_variables(
            api.get_space_variables(repo_id=repo_id),
            secret_names,
            desired,
        )
        if not remaining:
            return attempt
        if attempt < attempts:
            sleep(delay_seconds)
    raise RuntimeConfigError(
        "GDW runtime readback did not converge: "
        + ",".join(sorted(remaining))
    )


def configure(*, repo_id: str, hf_token: str, check_only: bool = False,
              origin: str | None = None, authority_get: Callable | None = None) -> dict[str, Any]:
    if not hf_token:
        raise RuntimeConfigError("HF_TOKEN is required", diagnostic_code="HF_CONTROL_CREDENTIAL_MISSING")
    if repo_id != CANONICAL_SPACE:
        raise RuntimeConfigError("SETUP_REQUIRED: only the canonical A11oy Space is admitted", diagnostic_code="CANONICAL_DESTINATION_REQUIRED")
    if type(check_only) is not bool:
        raise RuntimeConfigError("SETUP_REQUIRED: check_only must be a boolean", diagnostic_code="CHECK_MODE_MALFORMED")
    try:
        from huggingface_hub import HfApi

        api = HfApi(token=hf_token)
    except Exception:
        raise RuntimeConfigError("SETUP_REQUIRED: Space metadata client is unavailable", diagnostic_code="SPACE_CLIENT_UNAVAILABLE") from None
    prerequisites = manual_prerequisites(api, repo_id=repo_id, origin=origin, authority_get=authority_get)
    if check_only:
        return prerequisites
    if (prerequisites["converged"] is not True or prerequisites["state"] != "READY"
            or prerequisites["credential_authority_state"] != "VERIFIED"):
        raise RuntimeConfigError("SETUP_REQUIRED: installed credential authority is not VERIFIED",
                                 diagnostic_code=prerequisites.get("diagnostic_code", "INSTALLED_AUTHORITY_UNKNOWN"))
    desired = desired_variables()
    volume = require_data_mount(api, repo_id=repo_id)
    current_secret_names = set(api.get_space_secrets(repo_id=repo_id))
    current_variables = api.get_space_variables(repo_id=repo_id)
    changes = plan_variables(
        current_variables,
        current_secret_names,
        desired,
    )
    secret_names = current_secret_names
    for name, value in sorted(changes.items()):
        api.add_space_variable(
            repo_id=repo_id,
            key=name,
            value=value,
            description=(
                "Protected GDW successor runtime contract. "
                "Bearer material is stored only in GitHub Actions."
            ),
        )
    attempts = await_readback(
        api,
        repo_id=repo_id,
        secret_names=secret_names,
        desired=desired,
    )
    return {
        "schema": "szl.hf-gdw-runtime-config/v1",
        "repo_id": repo_id,
        "principal_id": PRINCIPAL_ID,
        "credential_key_id": CREDENTIAL_KEY_ID,
        "data_volume": volume,
        "variables_managed": sorted(desired),
        "variables_changed": sorted(changes),
        "secret_names_required": [CREDENTIAL_REGISTRY_SECRET],
        "secret_values_read": False,
        "secret_values_mutated": False,
        "credential_registry_converged": False,
        "readback_attempts": attempts,
        "converged": True,
        "credential_authority_state": "VERIFIED",
        "installed_authority": prerequisites["installed_authority"],
        "credential_values_recorded": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", default=CANONICAL_SPACE)
    parser.add_argument("--output")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = configure(repo_id=args.repo_id, hf_token=os.environ.get("HF_TOKEN", ""),
                           check_only=args.check_only)
    except RuntimeConfigError as error:
        report = {"schema": "szl.hf-gdw-runtime-config/v1", "repo_id": CANONICAL_SPACE,
                  "state": "SETUP_REQUIRED", "credential_authority_state": "UNKNOWN",
                  "converged": False, "secret_values_read": False, "secret_values_written": False,
                  "diagnostic_code": error.diagnostic_code}

    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 1 if report.get("state") == "SETUP_REQUIRED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
