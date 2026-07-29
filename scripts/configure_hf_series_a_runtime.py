#!/usr/bin/env python3
# Copyright 2026 SZL Holdings - SPDX-License-Identifier: Apache-2.0
"""Converge the canonical A11oy Space on fail-closed Series-A durability.

The script is intentionally narrow:

* it reuses an existing organization bucket and never creates storage;
* it preserves every existing Space volume and fails on mount conflicts;
* it requires the canonical signing-secret name without reading its value;
* it writes only non-secret runtime variables; and
* its report contains names and topology, never secret material.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


CANONICAL_SPACE = "SZLHOLDINGS/a11oy"
CANONICAL_BUCKET = "SZLHOLDINGS/szl-evidence"
CANONICAL_SIGNING_SECRET = "SZL_COSIGN_PRIVATE_PEM"
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


class RuntimeConfigError(RuntimeError):
    """Fail-closed runtime configuration error."""


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
) -> dict[str, Any]:
    from huggingface_hub import HfApi

    if not token:
        raise RuntimeConfigError("HF_TOKEN is required")
    api = HfApi(token=token)
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
        "secret_values_read": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", default=CANONICAL_SPACE)
    parser.add_argument("--bucket", default=CANONICAL_BUCKET)
    parser.add_argument("--output")
    args = parser.parse_args()

    report = configure(
        repo_id=args.repo_id,
        bucket=args.bucket,
        token=os.environ.get("HF_TOKEN", ""),
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
