#!/usr/bin/env python3
"""Converge GDW variables and the explicit-scope credential registry."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Mapping


CANONICAL_SPACE = "SZLHOLDINGS/a11oy"
DATA_MOUNT = "/data"
PRINCIPAL_ID = "gdw-operator"
PRINCIPAL_REGISTRY_SECRET = "GDW_PRINCIPALS_JSON"
CREDENTIAL_REGISTRY_SECRET = "GDW_CREDENTIALS_JSON"
CREDENTIAL_KEY_ID = "gdw-operator-v1"
OPERATOR_SCOPES = [
    "bench:read",
    "effects:recover",
    "integrity:global",
    "integrity:read",
    "metrics:read",
    "session:read",
    "step:write",
]
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
    "GDW_OWNER_MAX_ACTIVE_REQUESTS": "1000",
    "GDW_OWNER_MAX_ACTIVE_SESSIONS": "100",
    "GDW_OWNER_MAX_PENDING_EFFECTS": "2000",
    "GDW_OWNER_MAX_STORED_BYTES": "268435456",
    "GDW_GLOBAL_MAX_ACTIVE_REQUESTS": "100000",
    "GDW_GLOBAL_MAX_ACTIVE_SESSIONS": "10000",
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


class RuntimeConfigError(RuntimeError):
    """Fail-closed runtime configuration error."""


def _value(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, Mapping):
        return item.get(name, default)
    return getattr(item, name, default)


def desired_variables(operator_token: str) -> dict[str, str]:
    if len(operator_token.encode("utf-8")) < 32:
        raise RuntimeConfigError("GDW_OPERATOR_TOKEN must contain at least 32 bytes")
    return dict(STATIC_VARIABLES)


def credential_registry_value(operator_token: str) -> str:
    if len(operator_token.encode("utf-8")) < 32:
        raise RuntimeConfigError("GDW_OPERATOR_TOKEN must contain at least 32 bytes")
    credential_registry = {
        "version": 1,
        "credentials": [
            {
                "owner_id": PRINCIPAL_ID,
                "namespace": STATIC_VARIABLES["GDW_NAMESPACE"],
                "key_id": CREDENTIAL_KEY_ID,
                "token_sha256": hashlib.sha256(
                    operator_token.encode("utf-8")
                ).hexdigest(),
                "scopes": OPERATOR_SCOPES,
                "revoked": False,
            }
        ],
    }
    return json.dumps(
        credential_registry,
        sort_keys=True,
        separators=(",", ":"),
    )


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


def converge_credential_registry(
    api: Any,
    *,
    repo_id: str,
    current_variables: Mapping[str, Any],
    secret_names: set[str],
    operator_token: str,
) -> tuple[set[str], bool]:
    if CREDENTIAL_REGISTRY_SECRET in current_variables:
        raise RuntimeConfigError(
            "GDW credential registry collides with an existing Space variable"
        )
    if PRINCIPAL_REGISTRY_SECRET in current_variables:
        raise RuntimeConfigError(
            "GDW principal registry collides with an existing Space variable"
        )
    # Legacy roles cannot express the recovery capability as an explicit opt-in.
    # Retire the old registry first so the runtime always fails closed instead
    # of accepting two competing sources of authorization truth.
    if PRINCIPAL_REGISTRY_SECRET in secret_names:
        api.delete_space_secret(
            repo_id=repo_id,
            key=PRINCIPAL_REGISTRY_SECRET,
        )
        secret_names = set(api.get_space_secrets(repo_id=repo_id))
        if PRINCIPAL_REGISTRY_SECRET in secret_names:
            raise RuntimeConfigError(
                "legacy GDW principal registry secret did not retire"
            )
    api.add_space_secret(
        repo_id=repo_id,
        key=CREDENTIAL_REGISTRY_SECRET,
        value=credential_registry_value(operator_token),
        description=(
            "Digest-only explicit-scope GDW credential registry converged "
            "from the masked GitHub Actions operator credential."
        ),
    )
    converged_secret_names = set(api.get_space_secrets(repo_id=repo_id))
    if (
        CREDENTIAL_REGISTRY_SECRET not in converged_secret_names
        or PRINCIPAL_REGISTRY_SECRET in converged_secret_names
    ):
        raise RuntimeConfigError(
            "GDW credential registry secret did not converge exclusively"
        )
    return converged_secret_names, True


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
    if len(at_data) != 1 or bool(_value(at_data[0], "read_only", False)):
        raise RuntimeConfigError("GDW requires one read-write /data volume")
    return {
        "type": str(getattr(_value(at_data[0], "type", ""), "value", _value(at_data[0], "type", ""))),
        "source": str(_value(at_data[0], "source", "")),
        "mount_path": DATA_MOUNT,
        "read_only": False,
    }


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


def configure(*, repo_id: str, hf_token: str, operator_token: str) -> dict[str, Any]:
    from huggingface_hub import HfApi

    if not hf_token:
        raise RuntimeConfigError("HF_TOKEN is required")
    desired = desired_variables(operator_token)
    api = HfApi(token=hf_token)
    volume = require_data_mount(api, repo_id=repo_id)
    current_secret_names = set(api.get_space_secrets(repo_id=repo_id))
    current_variables = api.get_space_variables(repo_id=repo_id)
    changes = plan_variables(
        current_variables,
        current_secret_names,
        desired,
    )
    secret_names, credential_registry_changed = converge_credential_registry(
        api,
        repo_id=repo_id,
        current_variables=current_variables,
        secret_names=current_secret_names,
        operator_token=operator_token,
    )
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
        "secret_values_mutated": credential_registry_changed,
        "credential_registry_converged": True,
        "readback_attempts": attempts,
        "converged": True,
        "operator_token_present": True,
        "credential_values_recorded": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", default=CANONICAL_SPACE)
    parser.add_argument("--output")
    args = parser.parse_args()
    report = configure(
        repo_id=args.repo_id,
        hf_token=os.environ.get("HF_TOKEN", ""),
        operator_token=os.environ.get("GDW_OPERATOR_TOKEN", ""),
    )
    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
