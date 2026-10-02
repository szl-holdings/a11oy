#!/usr/bin/env python3
# Copyright 2026 SZL Holdings - SPDX-License-Identifier: Apache-2.0
"""Converge the canonical A11oy Space on fail-closed Series-A durability.

The script is intentionally narrow:

* it reuses an existing organization bucket and never creates storage;
* it preserves every existing Space volume and fails on mount conflicts;
* it requires the canonical signing-secret name without reading its value;
* it checks manually installed credential metadata without transferring values;
* it verifies installed signing authority by matching the live runtime public
  key against the pinned runtime key (``scripts/verify_installed_authority.py``);
* its report contains names, public fingerprints and topology, never secret
  material.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


CANONICAL_SPACE = "SZLHOLDINGS/a11oy"
CANONICAL_BUCKET = "SZLHOLDINGS/szl-evidence"
CANONICAL_SIGNING_SECRET = "SZL_COSIGN_PRIVATE_PEM"
GITHUB_PUBLIC_READ_SECRET = "A11OY_GITHUB_PUBLIC_READ_TOKEN"
GITHUB_READ_SCOPES = {"read:org", "read:user", "user:email"}
# Founder decision 2026-09-30: the GitHub public reader is optional. It is
# reported by name only and never required for admission.
REQUIRED_SECRET_NAMES = (CANONICAL_SIGNING_SECRET,)
OPTIONAL_SECRET_NAMES = (GITHUB_PUBLIC_READ_SECRET,)
DEFAULT_CANONICAL_ORIGIN = "https://szlholdings-a11oy.hf.space"
DATA_MOUNT = "/data"
SERIES_A_VARIABLES = {
    "A11OY_REQUIRE_PERSISTENT_SIGNING": "1",
    "A11OY_REQUIRE_PERSISTENT_STORAGE": "1",
    # Preserve the malformed v1 store at its original path for forensic
    # recovery. This versioned path is a non-destructive operational rotation.
    "A11OY_SERIES_A_DB": "/data/a11oy/series-a/control-plane-v2.sqlite3",
    "A11OY_SERIES_A_REQUIRE_MOUNT": DATA_MOUNT,
    "A11OY_SERIES_A_STARTUP_REFRESH": "1",
    "A11OY_SERIES_A_REFRESH_INTERVAL_SECONDS": "240",
    # SQLite WAL requires shared-memory semantics that are not portable across
    # network filesystems. The rollback journal is the conservative NFS choice.
    "A11OY_SERIES_A_SQLITE_JOURNAL": "DELETE",
    "SZL_ENERGY_LEDGER_PATH": "/data/a11oy/energy/ledger.jsonl",
    "SZL_LAKE_DIR": "/data/a11oy/khipu",
    "A11OY_ATELIER_LEDGER_PATH": "/data/a11oy/atelier/turn-receipts-v1.jsonl",
    "A11OY_ATELIER_REQUIRED_MOUNT": DATA_MOUNT,
}
GDW_VARIABLES = {
    "GDW_PRODUCTION_MODE": "1",
    "GDW_NAMESPACE": "a11oy",
    "GDW_SERVICE_OWNER_ID": "gdw-runtime",
    "GDW_DB_PATH": "/data/a11oy/gdw/gdw.sqlite3",
    "GDW_PROOF_DIR": "/data/a11oy/gdw/proofs",
    "GDW_RECEIPT_PROJECTION_DIR": "/data/a11oy/gdw/receipts",
    "GDW_REQUIRE_PERSISTENT_STORAGE": "1",
    "GDW_REQUIRED_MOUNT": DATA_MOUNT,
    "GDW_SQLITE_JOURNAL": "DELETE",
    "GDW_SQLITE_SYNCHRONOUS": "FULL",
    "GDW_PROOF_EXPORT_MODE": "outbox",
    "GDW_OUTBOX_ENABLED": "1",
    "GDW_OUTBOX_INTERVAL_SECONDS": "5",
    "GDW_OUTBOX_RETRY_MAX_SECONDS": "60",
    "GDW_OUTBOX_BATCH_SIZE": "100",
    "GDW_OUTBOX_LEASE_SECONDS": "300",
}
RUNTIME_VARIABLES = {
    **SERIES_A_VARIABLES,
    **GDW_VARIABLES,
}


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


def verify_public_github_reader(token: str, *, get: Callable | None = None) -> dict[str, Any]:
    """Check identity, read-only OAuth scopes, and the exact public read target.

    The existing organization automation token must expose its OAuth scopes.
    Fine-grained credentials without this scope evidence require a separate
    permission receipt and are not implicitly admitted by this helper.
    Response bodies, credential values, and exception text are never reported.
    """
    if not token or any(char.isspace() for char in token):
        raise RuntimeConfigError("a persistent GitHub public read token is required")
    if get is None:
        import requests

        get = requests.get
    headers = {"Authorization": "Bearer " + token,
               "Accept": "application/vnd.github+json",
               "User-Agent": "SZL-Canonical-Public-Inventory-Reader/1.0"}

    def probe(path: str) -> Any:
        try:
            response = get("https://api.github.com" + path, headers=headers,
                           timeout=20, allow_redirects=False)
        except Exception:
            raise RuntimeConfigError("GitHub read authority probe transport failed") from None
        if response.status_code != 200:
            raise RuntimeConfigError("GitHub read authority probe returned HTTP " + str(response.status_code))
        return response

    identity = probe("/user")
    if "X-OAuth-Scopes" not in identity.headers:
        raise RuntimeConfigError("GitHub read token scope evidence is unavailable")
    scopes = {value.strip() for value in identity.headers["X-OAuth-Scopes"].split(",") if value.strip()}
    if not scopes <= GITHUB_READ_SCOPES:
        raise RuntimeConfigError("GitHub reader has scopes outside the permitted read boundary")
    try:
        actor = identity.json()
        authenticated = isinstance(actor, dict) and type(actor.get("id")) is int and actor["id"] > 0
    except Exception:
        authenticated = False
    if not authenticated:
        raise RuntimeConfigError("GitHub reader authenticated identity is unavailable")
    public = probe("/orgs/szl-holdings/repos?type=public&per_page=1")
    try:
        rows = public.json()
        verified = (isinstance(rows, list) and bool(rows)
                    and all(isinstance(row, dict) and row.get("private") is False
                            and row.get("visibility") == "public"
                            and isinstance(row.get("owner"), dict)
                            and str(row["owner"].get("login", "")).lower() == "szl-holdings"
                            for row in rows))
    except Exception:
        verified = False
    if not verified:
        raise RuntimeConfigError("GitHub public organization read contract failed")
    return {"state": "VERIFIED_AUTHENTICATED_PUBLIC_READ", "organization": "szl-holdings",
            "inventory_scope": "public-only", "oauth_scopes": sorted(scopes),
            "credential_value_reported": False}


def manual_prerequisites(api: Any, *, repo_id: str, origin: str | None = None,
                         authority_get: Callable | None = None) -> dict[str, Any]:
    """Inspect names and storage, then verify installed signing authority.

    Authority is VERIFIED only when the live runtime public key matches both
    pins (``verify_installed_authority``); every other outcome stays
    SETUP_REQUIRED with a fixed diagnostic. Secret values are never read.
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
    required = set(REQUIRED_SECRET_NAMES)
    if (required | set(OPTIONAL_SECRET_NAMES)).intersection(public_names):
        raise RuntimeConfigError("SETUP_REQUIRED: a required secret collides with a public variable", diagnostic_code="PUBLIC_VARIABLE_COLLISION")
    try:
        volumes = read_space_volumes(api, repo_id=repo_id)
        if any(type(_value(item, "read_only")) is not bool for item in volumes):
            raise RuntimeConfigError("volume access metadata is unknown")
        _, missing_volume = plan_volumes(volumes)
    except Exception:
        raise RuntimeConfigError("SETUP_REQUIRED: canonical persistent volume metadata is unavailable or conflicting", diagnostic_code="PERSISTENT_STORAGE_UNAVAILABLE") from None
    try:
        authority = load_authority_verifier().verify_installed_authority(
            names, public_names, origin=origin or canonical_origin(), get=authority_get)
    except Exception:
        raise RuntimeConfigError("SETUP_REQUIRED: installed credential authority is UNKNOWN", diagnostic_code="INSTALLED_AUTHORITY_UNKNOWN") from None
    verified = (authority.get("credential_authority_state") == "VERIFIED"
                and not missing_volume and required <= names)
    diagnostic = authority.get("diagnostic_code")
    if not verified:
        if diagnostic == "INSTALLED_AUTHORITY_VERIFIED" or diagnostic not in INSTALLED_AUTHORITY_DIAGNOSTICS:
            diagnostic = "INSTALLED_AUTHORITY_UNKNOWN"
    return {
        "schema": "szl.hf-series-a-runtime-config/v1",
        "repo_id": repo_id,
        "state": "READY" if verified else "SETUP_REQUIRED",
        "diagnostic_code": "INSTALLED_AUTHORITY_VERIFIED" if verified else diagnostic,
        "missing_secret_names": sorted(required - names),
        "required_secret_names": sorted(required),
        "optional_secret_names": sorted(OPTIONAL_SECRET_NAMES),
        "optional_secret_names_present": sorted(set(OPTIONAL_SECRET_NAMES) & names),
        "persistent_volume_present": not missing_volume,
        "credential_authority_state": "VERIFIED" if verified else "UNKNOWN",
        "installed_authority": authority,
        "converged": verified,
        "secret_values_read": False,
        "secret_values_written": False,
    }


def _value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def _enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def volume_record(item: Any) -> dict[str, Any]:
    """Return a stable, secret-free volume representation."""

    return {
        "type": str(_enum_value(_value(item, "type", ""))),
        "source": str(_value(item, "source", "")),
        "mount_path": str(_value(item, "mount_path", "")),
        "read_only": bool(_value(item, "read_only", False)),
        "path": _value(item, "path"),
        "revision": _value(item, "revision"),
    }


def plan_volumes(
    current: Iterable[Any],
    *,
    bucket: str = CANONICAL_BUCKET,
    mount_path: str = DATA_MOUNT,
) -> tuple[list[dict[str, Any]], bool]:
    """Preserve current volumes and append the canonical bucket when absent."""

    records = [volume_record(item) for item in current]
    at_mount = [item for item in records if item["mount_path"] == mount_path]
    if at_mount:
        if len(at_mount) != 1:
            raise RuntimeConfigError(
                f"multiple volumes already claim required mount {mount_path}"
            )
        existing = at_mount[0]
        if (
            existing["type"] != "bucket"
            or existing["source"] != bucket
            or existing["read_only"]
        ):
            raise RuntimeConfigError(
                f"required mount {mount_path} conflicts with an existing volume"
            )
        return records, False

    records.append(
        {
            "type": "bucket",
            "source": bucket,
            "mount_path": mount_path,
            "read_only": False,
            "path": None,
            "revision": None,
        }
    )
    return records, True


def plan_variables(
    current: Mapping[str, Any],
    secret_names: Iterable[str],
    desired: Mapping[str, str] = RUNTIME_VARIABLES,
) -> dict[str, str]:
    """Return only drifted variables after checking secret-name collisions."""

    secrets = set(secret_names)
    collisions = sorted(set(desired) & secrets)
    if collisions:
        raise RuntimeConfigError(
            "runtime variable names collide with Space secrets: "
            + ",".join(collisions)
        )

    changes: dict[str, str] = {}
    for name, expected in desired.items():
        item = current.get(name)
        observed = _value(item, "value") if item is not None else None
        if str(observed) != expected:
            changes[name] = expected
    return changes


def _volume_objects(records: Iterable[Mapping[str, Any]]) -> list[Any]:
    from huggingface_hub import Volume

    return [
        Volume(
            type=str(item["type"]),
            source=str(item["source"]),
            mount_path=str(item["mount_path"]),
            read_only=bool(item["read_only"]),
            path=item.get("path"),
            revision=item.get("revision"),
        )
        for item in records
    ]


def read_space_volumes(api: Any, *, repo_id: str) -> list[Any]:
    """Read mounted volumes through the same metadata path as the HF CLI.

    ``hf spaces volumes ls`` reads ``space_info().runtime.volumes``.  The
    dedicated runtime endpoint can temporarily omit newly attached volumes
    even after the Space has rebuilt with the mount, so it is not the
    authoritative configuration readback for this operation.
    """

    info = api.space_info(repo_id=repo_id)
    runtime = getattr(info, "runtime", None)
    if runtime is None:
        raise RuntimeConfigError("Space info did not include runtime metadata")
    volumes = getattr(runtime, "volumes", None)
    if volumes is None:
        raise RuntimeConfigError("Space runtime did not include volume metadata")
    return list(volumes)


def await_readback(
    api: Any,
    *,
    repo_id: str,
    bucket: str,
    secret_names: Iterable[str],
    attempts: int = 60,
    delay_seconds: float = 5,
    sleep: Callable[[float], None] = time.sleep,
) -> tuple[list[Any], int]:
    """Poll boundedly until the Hub reflects both volume and variable writes."""

    if attempts < 1 or delay_seconds < 0:
        raise RuntimeConfigError("readback bounds must be non-negative")
    missing_volume = True
    remaining_variables: dict[str, str] = dict(RUNTIME_VARIABLES)
    observed_volumes: list[Any] = []
    for attempt in range(1, attempts + 1):
        observed_volumes = read_space_volumes(api, repo_id=repo_id)
        _, missing_volume = plan_volumes(observed_volumes, bucket=bucket)
        observed_variables = api.get_space_variables(repo_id=repo_id)
        remaining_variables = plan_variables(
            observed_variables,
            secret_names,
        )
        if not missing_volume and not remaining_variables:
            return observed_volumes, attempt
        if attempt < attempts:
            sleep(delay_seconds)

    detail = []
    if missing_volume:
        detail.append("persistent volume")
    if remaining_variables:
        detail.append(
            "variables=" + ",".join(sorted(remaining_variables))
        )
    raise RuntimeConfigError(
        f"runtime readback did not converge after {attempts} attempts: "
        + "; ".join(detail)
    )


def configure(
    *,
    repo_id: str,
    bucket: str,
    token: str,
    check_only: bool = False,
    origin: str | None = None,
    authority_get: Callable | None = None,
) -> dict[str, Any]:
    if not token:
        raise RuntimeConfigError("HF_TOKEN is required", diagnostic_code="HF_CONTROL_CREDENTIAL_MISSING")
    if repo_id != CANONICAL_SPACE or bucket != CANONICAL_BUCKET:
        raise RuntimeConfigError("SETUP_REQUIRED: canonical Space and bucket are required", diagnostic_code="CANONICAL_DESTINATION_REQUIRED")
    if type(check_only) is not bool:
        raise RuntimeConfigError("SETUP_REQUIRED: check_only must be a boolean", diagnostic_code="CHECK_MODE_MALFORMED")
    try:
        from huggingface_hub import HfApi

        api = HfApi(token=token)
    except Exception:
        raise RuntimeConfigError("SETUP_REQUIRED: Space metadata client is unavailable", diagnostic_code="SPACE_CLIENT_UNAVAILABLE") from None
    prerequisites = manual_prerequisites(api, repo_id=repo_id, origin=origin, authority_get=authority_get)
    if check_only:
        return prerequisites
    # Only independently verified installed authority (live runtime key equal
    # to both pins) admits configuration; every other state stays held.
    if (prerequisites["converged"] is not True or prerequisites["state"] != "READY"
            or prerequisites["credential_authority_state"] != "VERIFIED"):
        raise RuntimeConfigError("SETUP_REQUIRED: installed credential authority is not VERIFIED",
                                 diagnostic_code=prerequisites.get("diagnostic_code", "INSTALLED_AUTHORITY_UNKNOWN"))
    current_volumes = read_space_volumes(api, repo_id=repo_id)
    desired_volumes, volume_change = plan_volumes(
        current_volumes,
        bucket=bucket,
    )

    secrets = api.get_space_secrets(repo_id=repo_id)
    secret_names = set(secrets)
    if CANONICAL_SIGNING_SECRET not in secret_names:
        raise RuntimeConfigError(
            f"required signing secret is absent: {CANONICAL_SIGNING_SECRET}"
        )
    variables = api.get_space_variables(repo_id=repo_id)
    variable_changes = plan_variables(variables, secret_names)

    if volume_change:
        api.set_space_volumes(
            repo_id=repo_id,
            volumes=_volume_objects(desired_volumes),
        )
    for name, value in sorted(variable_changes.items()):
        api.add_space_variable(
            repo_id=repo_id,
            key=name,
            value=value,
            description=(
                "Protected deployment contract for persistent A11oy Series-A "
                "and GDW runtime storage."
            ),
        )

    observed_volumes, readback_attempts = await_readback(
        api,
        repo_id=repo_id,
        bucket=bucket,
        secret_names=secret_names,
    )

    return {
        "schema": "szl.hf-series-a-runtime-config/v1",
        "repo_id": repo_id,
        "bucket": bucket,
        "required_signing_secret": CANONICAL_SIGNING_SECRET,
        "signing_secret_present": True,
        "volumes": [volume_record(item) for item in observed_volumes],
        "volume_changed": volume_change,
        "readback_attempts": readback_attempts,
        "variables_managed": sorted(RUNTIME_VARIABLES),
        "variables_changed": sorted(variable_changes),
        "converged": True,
        "existing_space_secret_values_read": False,
        "credential_authority_state": "VERIFIED",
        "github_public_reader": prerequisites["installed_authority"]["github_public_reader"],
        "installed_authority": prerequisites["installed_authority"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", default=CANONICAL_SPACE)
    parser.add_argument("--bucket", default=CANONICAL_BUCKET)
    parser.add_argument("--output")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args(argv)
    try:
        report = configure(repo_id=args.repo_id, bucket=args.bucket,
                           token=os.environ.get("HF_TOKEN", ""), check_only=args.check_only)
    except RuntimeConfigError as error:
        report = {"schema": "szl.hf-series-a-runtime-config/v1", "repo_id": CANONICAL_SPACE,
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
