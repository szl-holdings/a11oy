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

The explicit managed entrypoint delegates one first-cutover attempt for both
stores to the GDW coordinator. It is an alternative to that CLI, never a second
sequential application. Managed predeploy reports leave signing authority
unproven until startup and native live proof.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import json
import os
import re
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
    # Legacy mount contract only. A rollback journal does not establish
    # bucket-mount fsync durability; qualified recovery owns the cutover.
    "A11OY_SERIES_A_SQLITE_JOURNAL": "DELETE",
    "SZL_ENERGY_LEDGER_PATH": "/data/a11oy/energy/ledger.jsonl",
    "SZL_LAKE_DIR": "/data/a11oy/khipu",
    "A11OY_ATELIER_LEDGER_PATH": "/data/a11oy/atelier/turn-receipts-v1.jsonl",
    "A11OY_ATELIER_REQUIRED_MOUNT": DATA_MOUNT,
    "SZL_GOVERN_INFER_LOG": "/data/.szl_govern_infer.jsonl",
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
# ADR-0001 bounds continuous-write snapshot exposure at five minutes. Keep
# cadence in the existing canonical convergence owner, below the 900s alert;
# configuring this inert setting does not activate state-store v2.
STATE_STORE_VARIABLES = {"A11OY_STATE_PERIODIC_SECONDS": "300"}
# Match Settings.from_environ in a11oy_state_store without importing runtime
# storage code into the deployment helper. Bounds reject; they do not clamp.
STATE_STORE_CADENCE_SETTINGS = {
    "A11OY_STATE_DEBOUNCE_SECONDS": (30, 1, 3600),
    "A11OY_STATE_PERIODIC_SECONDS": (300, 5, 86400),
    "A11OY_STATE_ALERT_SECONDS": (900, 60, 86400),
}
RUNTIME_VARIABLES = {
    **SERIES_A_VARIABLES,
    **GDW_VARIABLES,
    **STATE_STORE_VARIABLES,
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
            "RUNTIME_CONFIG_DRIFT", "RUNTIME_CONFIG_UNAVAILABLE",
            "STATE_STORE_CADENCE_INVALID",
            "MANAGED_STORAGE_UNAVAILABLE", "MANAGED_OUTCOME_UNCERTAIN",
            "SOURCE_OWNERSHIP_UNAVAILABLE", "SOURCE_NOT_CURRENT_MAIN",
            "STATE_STORE_RELEASE_REQUIRED", "STATE_STORE_RELEASE_UNVERIFIED",
            "STATE_STORE_RELEASE_CHANGED", "STATE_STORE_OBSERVATION_EXPIRED",
            "RUNTIME_CONFIG_REQUEST_REFUSED", "RUNTIME_CONFIG_OUTCOME_UNCERTAIN",
            *INSTALLED_AUTHORITY_DIAGNOSTICS,
        }
        self.diagnostic_code = diagnostic_code if diagnostic_code in allowed else "PREREQUISITES_UNAVAILABLE"


def require_current_main(expected_source_sha: str | None,
                         main_reader: Callable[[], str] | None = None) -> None:
    """Re-read protected main next to each default-path provider mutation."""
    try:
        path = Path(__file__).resolve().with_name("hf_exact_main_ownership.py")
        spec = importlib.util.spec_from_file_location("_series_a_main_ownership", path)
        if spec is None or spec.loader is None:
            raise RuntimeError("main ownership reader unavailable")
        ownership = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(ownership)
        expected = ownership.validate_sha(expected_source_sha, label="expected source SHA")
        observed = (main_reader() if main_reader is not None else
                    ownership.fetch_main_sha("szl-holdings/a11oy", os.environ.get("GITHUB_TOKEN", "")))
        observed = ownership.validate_sha(observed, label="observed main SHA")
    except Exception:
        raise RuntimeConfigError("SETUP_REQUIRED: protected main ownership is unavailable",
                                 diagnostic_code="SOURCE_OWNERSHIP_UNAVAILABLE") from None
    if observed != expected:
        raise RuntimeConfigError("SETUP_REQUIRED: source is no longer protected main",
                                 diagnostic_code="SOURCE_NOT_CURRENT_MAIN")


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


def validate_state_store_cadence(
    current: Mapping[str, Any], desired: Mapping[str, str],
) -> None:
    """Validate the planned schedule without changing preserved settings.

    Managed periodic drift is repairable, including malformed old values.
    Readback still requires its exact managed value before reporting convergence.
    Debounce and alert are preserved, so malformed values must stop all writes.
    """
    effective: dict[str, float] = {}
    for name, (default, minimum, maximum) in STATE_STORE_CADENCE_SETTINGS.items():
        raw = desired[name] if name in desired else (
            _value(current[name], "value") if name in current else ""
        )
        try:
            if type(raw) is not str:
                raise ValueError("malformed setting metadata")
            raw = raw.strip()
            parsed = float(raw) if raw else float(default)
        except (TypeError, ValueError):
            raise RuntimeConfigError(
                "SETUP_REQUIRED: state-store cadence setting is invalid",
                diagnostic_code="STATE_STORE_CADENCE_INVALID",
            ) from None
        # As in the runtime parser, this also rejects NaN and infinities.
        if not minimum <= parsed <= maximum:
            raise RuntimeConfigError(
                "SETUP_REQUIRED: state-store cadence setting is out of range",
                diagnostic_code="STATE_STORE_CADENCE_INVALID",
            )
        effective[name] = parsed
    # Quiet-time debounce and periodic overdue are alternative snapshot triggers.
    # A longer valid debounce does not extend the periodic exposure bound.
    if effective["A11OY_STATE_PERIODIC_SECONDS"] >= effective["A11OY_STATE_ALERT_SECONDS"]:
        raise RuntimeConfigError(
            "SETUP_REQUIRED: periodic snapshot interval must be below alert interval",
            diagnostic_code="STATE_STORE_CADENCE_INVALID",
        )


def plan_variables(
    current: Mapping[str, Any],
    secret_names: Iterable[str],
    desired: Mapping[str, str] = RUNTIME_VARIABLES,
) -> dict[str, str]:
    """Return only drifted variables after checking secret-name collisions."""

    # The export-mode guard is installed before any other managed variable.
    # A legacy invocation must not remove that first cutover barrier while the
    # remaining managed configuration is deliberately incomplete.
    export_mode = _value(current.get("GDW_PROOF_EXPORT_MODE"), "value", "")
    if (_value(current.get("GDW_DURABLE_STORAGE"), "value", "")
            or (export_mode and export_mode != "outbox")):
        raise RuntimeConfigError("qualified durable storage cannot be replaced by the legacy mount contract")

    secrets = set(secret_names)
    collisions = sorted((set(desired) | set(STATE_STORE_CADENCE_SETTINGS)) & secrets)
    if collisions:
        raise RuntimeConfigError(
            "runtime variable names collide with Space secrets: "
            + ",".join(collisions)
        )

    validate_state_store_cadence(current, desired)
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
        + "; ".join(detail),
        diagnostic_code="RUNTIME_CONFIG_DRIFT",
    )


# Configuration writes can restart a process without changing its code revision.
# This is a fresh refusal gate, not an atomic lock or an audited handover.
STORAGE_STATUS_URL = DEFAULT_CANONICAL_ORIGIN + "/api/a11oy/v1/storage/status"
STATE_OBSERVATION_SECONDS = 30.0
CONFIG_SUBMISSION_SECONDS = 5.0
MAX_STORAGE_STATUS_BYTES = 256 * 1024


def load_state_store() -> Any:
    """Load only existing parser dependencies under isolated Python; never activate."""
    name = "_series_a_release_state_store"
    root = Path(__file__).resolve().parents[1]
    if name not in sys.modules:
        path = root / "a11oy_state_store.py"
        spec = importlib.util.spec_from_file_location(name, path)
        if spec is None or spec.loader is None:
            raise RuntimeError("state parser unavailable")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        previous_path = list(sys.path)
        try:
            # The canonical workflow uses -I. Its existing state parser imports
            # these repository siblings; scope path resolution to this import.
            sys.path.insert(0, str(root))
            spec.loader.exec_module(module)
            for dependency in ("gdw_sqlite_repair", "gdw_durable_storage"):
                imported = sys.modules.get(dependency)
                if Path(getattr(imported, "__file__", "")).resolve() != (root / (dependency + ".py")).resolve():
                    raise RuntimeError("state dependency source mismatch")
        except Exception:
            sys.modules.pop(name, None)
            raise
        finally:
            sys.path[:] = previous_path
    module = sys.modules[name]
    if Path(module.__file__).resolve() != (root / "a11oy_state_store.py").resolve():
        raise RuntimeError("state parser source mismatch")
    return module

def read_storage_status() -> Mapping[str, Any]:
    """One bounded, unauthenticated GET to the canonical runtime."""
    import httpx

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate field")
            result[key] = value
        return result

    def nonfinite(_value):
        raise ValueError("nonfinite value")

    with httpx.Client(transport=httpx.HTTPTransport(retries=0),
                      follow_redirects=False, timeout=5) as client:
        with client.stream("GET", STORAGE_STATUS_URL,
                           headers={"Accept": "application/json", "Accept-Encoding": "identity"}) as response:
            if response.status_code != 200 or response.headers.get("content-encoding", "").lower() not in ("", "identity"):
                raise ValueError("storage status unavailable")
            raw = bytearray()
            for part in response.iter_raw():
                if len(raw) + len(part) > MAX_STORAGE_STATUS_BYTES:
                    raise ValueError("storage status too large")
                raw.extend(part)
    result = json.loads(raw, object_pairs_hook=unique, parse_constant=nonfinite)
    if type(result) is not dict:
        raise ValueError("storage status is not an object")
    return result


class ReleasedStateGuard:
    """Pin one observed release and recheck the CURRENT tip before each write.

    Public status alone can be served by an older boot. The private HEAD is the
    current fence. Existing audited handover and object verification remain
    separate prerequisites; this guard neither performs nor certifies them.
    """

    def __init__(self, api, *, status_get=None, observe=None, clock=time.monotonic):
        self.api = api
        self.status_get = status_get or read_storage_status
        self.observe = observe
        self.clock = clock
        self.pinned = None
        self.summary = {"state": "NOT_OBSERVED"}
        self.temporary = None
        self.backend = None

    def close(self):
        if self.temporary is not None:
            self.temporary.cleanup()

    def _observe(self, ss):
        if self.observe is not None:
            return self.observe()
        if self.backend is None:
            import tempfile
            self.temporary = tempfile.TemporaryDirectory(prefix="a11oy-config-release-")
            self.backend = ss.HFDatasetHeadBackend(self.api, ss.DEFAULT_DATASET, Path(self.temporary.name))
        return self.backend.observe()

    def admit(self):
        import hashlib
        import math

        def require(condition, code="STATE_STORE_RELEASE_UNVERIFIED"):
            if not condition:
                raise RuntimeConfigError("SETUP_REQUIRED: storage release is not verified",
                                         diagnostic_code=code)
        started = self.clock()
        try:
            require(type(started) in (int, float) and math.isfinite(started))
            ss = load_state_store()
            variables = self.api.get_space_variables(repo_id=CANONICAL_SPACE)
            require(isinstance(variables, Mapping))
            configured = _value(variables.get(ss.ENABLE_ENV), "value", "")
            require(type(configured) is str)
            configured = configured.strip().lower()
            secrets = self.api.get_space_secrets(repo_id=CANONICAL_SPACE)
            require(isinstance(secrets, (Mapping, list, tuple, set))
                    and ss.ENABLE_ENV not in secrets)
            status = self.status_get()
            require(type(status) is dict and status.get("schema") == ss.STATUS_SCHEMA)
            if status.get("mode") == ss.MODE_DISABLED:
                # A new configuration can precede the old process's restart.
                # A secret activation flag is deliberately not read or guessed.
                require(configured in {"", "0", "false", "off", "disabled"}
                        and status.get("role") == ss.MODE_DISABLED
                        and status.get("writable") is True)
                pinned = ("DISABLED",)
                summary = {"state": "DISABLED"}
            else:
                require(configured == ss.ENABLED_VALUE
                        and status.get("mode") == ss.MODE_FENCED
                        and status.get("role") == ss.ROLE_RELEASED
                        and status.get("writable") is False
                        and (status.get("lease") or {}).get("state") == ss.STATE_RELEASED,
                        "STATE_STORE_RELEASE_REQUIRED")
                require(status.get("active_errors") == {} and status.get("pending_publish") == []
                        and status.get("last_error") is None and status.get("alert") is False)
                observed = self._observe(ss)
                head = ss.parse_head(observed.body)
                require(type(observed.revision) is str and re.fullmatch(r"[0-9a-f]{40}", observed.revision)
                        and head["state"] == ss.STATE_RELEASED and head["transition"] == "RELEASE"
                        and head["bucket"] == CANONICAL_BUCKET
                        and type(status.get("epoch")) is int and status["epoch"] == head["epoch"]
                        and type(status["lease"].get("sequence")) is int
                        and status["lease"]["sequence"] == head["sequence"]
                        and status.get("claim") == head["claim"]["kind"])
                stores = status.get("stores")
                labels = {spec.label for spec in ss.STORES}
                require(type(stores) is dict and set(stores) == labels
                        and set(head["snapshots"]) == labels)
                for spec in ss.STORES:
                    row, entry = stores[spec.label], head["snapshots"][spec.label]
                    require(type(row) is dict and row.get("health") == "OK"
                            and row.get("kind") == spec.kind
                            and type(row.get("snapshot_failures")) is int and row["snapshot_failures"] == 0
                            and row.get("blocked_code") is None and row.get("last_error_code") is None
                            and row.get("sha16") == entry["sha256"][:16]
                            and entry["kind"] == spec.kind
                            and row.get("integrity") == entry["integrity"])
                pinned = (observed.revision, hashlib.sha256(observed.body).hexdigest(),
                          head["epoch"], head["writer_id"], head["boot_id"])
                # Do not mistake reading an old immutable release for ownership
                # of the current tip after a successor has claimed it.
                final = self._observe(ss)
                require(final.revision == observed.revision and final.body == observed.body,
                        "STATE_STORE_RELEASE_CHANGED")
                summary = {"state": "RELEASED", "epoch": head["epoch"], "sequence": head["sequence"],
                           "claim": head["claim"]["kind"], "manifest_sha256": pinned[1]}
            require(self.pinned is None or pinned == self.pinned, "STATE_STORE_RELEASE_CHANGED")
            completed = self.clock()
            require(type(completed) in (int, float) and math.isfinite(completed)
                    and 0 <= completed - started < STATE_OBSERVATION_SECONDS,
                    "STATE_STORE_OBSERVATION_EXPIRED")
            self.pinned, self.summary = pinned, summary
            return min(started + STATE_OBSERVATION_SECONDS, completed + CONFIG_SUBMISSION_SECONDS)
        except RuntimeConfigError:
            raise
        except Exception:
            raise RuntimeConfigError("SETUP_REQUIRED: storage release observation is unavailable",
                                     diagnostic_code="STATE_STORE_RELEASE_UNVERIFIED") from None


class RuntimeMutationClient:
    """Invocation-local transport for the two existing configuration operations.

    SDK-equivalent POST variables / PUT volumes payloads, no redirects or
    retries. Only the current prepared request may pass its dispatch deadline.
    No SDK global client factory or other invocation's transport is changed.
    """

    def __init__(self, token, *, transport=None, clock=time.monotonic):
        import httpx
        self.token = token
        self.clock = clock
        self.pending = None
        self.attempted = []
        self.acknowledged = []
        self.client = httpx.Client(
            transport=transport or httpx.HTTPTransport(retries=0),
            follow_redirects=False, timeout=20, event_hooks={"request": [self._guard]})

    def close(self):
        self.client.close()

    def _guard(self, request):
        prepared = self.pending
        if (prepared is None or prepared["submitted"]
                or request.method != prepared["method"] or str(request.url) != prepared["url"]
                or json.loads(request.content) != prepared["payload"]):
            raise RuntimeConfigError("configuration request is outside the admitted operation",
                                     diagnostic_code="RUNTIME_CONFIG_REQUEST_REFUSED")
        import math
        now = self.clock()
        if (type(now) not in (int, float) or not math.isfinite(now)
                or not now < prepared["deadline"]):
            raise RuntimeConfigError("storage release observation expired before submission",
                                     diagnostic_code="STATE_STORE_OBSERVATION_EXPIRED")
        prepared["submitted"] = True
        self.attempted.append(prepared["label"])

    def submit(self, method, suffix, payload, *, deadline, label):
        if (method, suffix) not in {("POST", "variables"), ("PUT", "volumes")}:
            raise RuntimeConfigError("configuration request is outside the admitted operation",
                                     diagnostic_code="RUNTIME_CONFIG_REQUEST_REFUSED")
        import math
        now = self.clock()
        if (type(deadline) not in (int, float) or not math.isfinite(deadline)
                or type(now) not in (int, float) or not math.isfinite(now)
                or not 0 < deadline - now <= CONFIG_SUBMISSION_SECONDS):
            raise RuntimeConfigError("storage release observation expired before submission",
                                     diagnostic_code="STATE_STORE_OBSERVATION_EXPIRED")
        url = "https://huggingface.co/api/spaces/" + CANONICAL_SPACE + "/" + suffix
        self.pending = {"method": method, "url": url, "payload": payload,
                        "deadline": deadline, "label": label, "submitted": False}
        try:
            import httpx
            remaining = max(0.001, deadline - self.clock())
            with self.client.stream(method, url, json=payload,
                                    headers={"Authorization": "Bearer " + self.token},
                                    timeout=httpx.Timeout(remaining)) as response:
                if not 200 <= response.status_code < 300:
                    raise RuntimeError("configuration response was not successful")
            self.acknowledged.append(label)
        except RuntimeConfigError:
            raise
        except Exception:
            raise RuntimeConfigError("configuration submission outcome is uncertain; no retry was made",
                                     diagnostic_code="RUNTIME_CONFIG_OUTCOME_UNCERTAIN") from None
        finally:
            self.pending = None

    def outcome(self):
        return {"attempted": list(self.attempted), "acknowledged": list(self.acknowledged),
                "possible_partial_configuration": bool(self.attempted),
                "automatic_retry": False}

def configure(
    *,
    repo_id: str,
    bucket: str,
    token: str,
    check_only: bool = False,
    origin: str | None = None,
    authority_get: Callable | None = None,
    expected_source_sha: str | None = None,
    main_reader: Callable[[], str] | None = None,
) -> dict[str, Any]:
    if not token:
        raise RuntimeConfigError("HF_TOKEN is required", diagnostic_code="HF_CONTROL_CREDENTIAL_MISSING")
    if repo_id != CANONICAL_SPACE or bucket != CANONICAL_BUCKET:
        raise RuntimeConfigError("SETUP_REQUIRED: canonical Space and bucket are required", diagnostic_code="CANONICAL_DESTINATION_REQUIRED")
    if type(check_only) is not bool:
        raise RuntimeConfigError("SETUP_REQUIRED: check_only must be a boolean", diagnostic_code="CHECK_MODE_MALFORMED")
    if not check_only:
        # Refuse an unbound writer before creating a provider client. Each
        # actual mutation below still performs a fresh protected-main read.
        require_current_main(expected_source_sha, main_reader)
    try:
        from huggingface_hub import HfApi

        api = HfApi(endpoint='https://huggingface.co', token=token)
    except Exception:
        raise RuntimeConfigError("SETUP_REQUIRED: Space metadata client is unavailable", diagnostic_code="SPACE_CLIENT_UNAVAILABLE") from None
    prerequisites = manual_prerequisites(api, repo_id=repo_id, origin=origin, authority_get=authority_get)
    if check_only:
        if (prerequisites["converged"] is True and prerequisites["state"] == "READY"
                and prerequisites["credential_authority_state"] == "VERIFIED"):
            # Installed authority alone does not prove configuration parity.
            # A verification pass reads the full contract once and never writes.
            try:
                secret_names = api.get_space_secrets(repo_id=repo_id)
                _, attempts = await_readback(
                    api, repo_id=repo_id, bucket=bucket, secret_names=secret_names,
                    attempts=1, delay_seconds=0,
                )
            except RuntimeConfigError:
                raise
            except Exception:
                raise RuntimeConfigError(
                    "SETUP_REQUIRED: runtime configuration readback is unavailable",
                    diagnostic_code="RUNTIME_CONFIG_UNAVAILABLE",
                ) from None
            prerequisites = dict(prerequisites, variables_managed=sorted(RUNTIME_VARIABLES),
                                 readback_attempts=attempts)
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

    guard = None
    writer = None
    try:
        if volume_change or variable_changes:
            guard = ReleasedStateGuard(api)
            writer = RuntimeMutationClient(token)
        if volume_change:
            volumes = _volume_objects(desired_volumes)
            payload = {"volumes": [volume.to_dict() for volume in volumes]}
            require_current_main(expected_source_sha, main_reader)
            deadline = guard.admit()
            require_current_main(expected_source_sha, main_reader)
            writer.submit("PUT", "volumes", payload, deadline=deadline, label="volumes")
        for name, value in sorted(variable_changes.items()):
            payload = {"key": name, "value": value,
                       "description": "Protected deployment contract for persistent A11oy Series-A "
                                      "and GDW runtime storage."}
            require_current_main(expected_source_sha, main_reader)
            deadline = guard.admit()
            require_current_main(expected_source_sha, main_reader)
            writer.submit("POST", "variables", payload, deadline=deadline, label=name)
        observed_volumes, readback_attempts = await_readback(
            api, repo_id=repo_id, bucket=bucket, secret_names=secret_names)
    except RuntimeConfigError as error:
        if writer is not None:
            error.mutation_outcome = writer.outcome()
        raise
    except Exception:
        error = RuntimeConfigError("runtime configuration readback is unavailable",
                                   diagnostic_code="RUNTIME_CONFIG_UNAVAILABLE")
        if writer is not None:
            error.mutation_outcome = writer.outcome()
        raise error from None
    finally:
        # Cleanup must not replace the recorded mutation outcome with an
        # arbitrary provider/filesystem exception.
        for resource in (writer, guard):
            if resource is not None:
                with contextlib.suppress(Exception):
                    resource.close()

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
        "state_store_admission": guard.summary if guard is not None else {"state": "NO_CHANGES"},
        "runtime_boot_verified": False,
        "storage_preservation_verified": False,
        "mutation_deadline_scope": "REQUEST_DISPATCH_NOT_PROVIDER_EXECUTION",
        "converged": True,
        "existing_space_secret_values_read": False,
        "credential_authority_state": "VERIFIED",
        "github_public_reader": prerequisites["installed_authority"]["github_public_reader"],
        "installed_authority": prerequisites["installed_authority"],
    }


def configure_managed(receipt_path: Path, *, source_revision: str, deadline: float,
                      check_only: bool, repo_id: str, bucket: str) -> dict[str, Any]:
    """Alternative entrypoint for the single, shared first-cutover attempt."""
    try:
        if repo_id != CANONICAL_SPACE or bucket != CANONICAL_BUCKET:
            raise RuntimeConfigError("canonical managed storage is required")
        path = Path(__file__).resolve().with_name("configure_hf_gdw_runtime.py")
        spec = importlib.util.spec_from_file_location("_series_a_managed_config", path)
        if spec is None or spec.loader is None:
            raise RuntimeConfigError("managed storage qualification is unavailable")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.configure_managed(receipt_path, source_revision=source_revision,
            deadline=deadline, check_only=check_only, repo_id=repo_id)
    except RuntimeConfigError:
        raise
    except BaseException as error:
        code = getattr(error, "diagnostic_code", "MANAGED_STORAGE_UNAVAILABLE")
        raise RuntimeConfigError("managed storage qualification is unavailable",
            diagnostic_code=code if code in {"MANAGED_STORAGE_UNAVAILABLE", "MANAGED_OUTCOME_UNCERTAIN"}
            else "MANAGED_STORAGE_UNAVAILABLE") from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", default=CANONICAL_SPACE)
    parser.add_argument("--bucket", default=CANONICAL_BUCKET)
    parser.add_argument("--output")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--managed-acquisition", type=Path)
    parser.add_argument("--source-sha")
    parser.add_argument("--expected-source-sha")
    parser.add_argument("--managed-deadline-seconds", type=float, default=120)
    args = parser.parse_args(argv)
    try:
        if args.managed_acquisition is not None or args.source_sha is not None:
            if args.managed_acquisition is None or args.source_sha is None:
                raise RuntimeConfigError("managed storage qualification is unavailable",
                                         diagnostic_code="MANAGED_STORAGE_UNAVAILABLE")
            report = configure_managed(args.managed_acquisition, source_revision=args.source_sha,
                deadline=time.monotonic() + args.managed_deadline_seconds,
                check_only=args.check_only, repo_id=args.repo_id, bucket=args.bucket)
        else:
            report = configure(repo_id=args.repo_id, bucket=args.bucket,
                               token=os.environ.get("HF_TOKEN", ""), check_only=args.check_only,
                               expected_source_sha=args.expected_source_sha)
    except RuntimeConfigError as error:
        report = {"schema": "szl.hf-series-a-runtime-config/v1", "repo_id": CANONICAL_SPACE,
                  "state": "SETUP_REQUIRED", "credential_authority_state": "UNKNOWN",
                  "converged": False, "secret_values_read": False, "secret_values_written": False,
                  "diagnostic_code": error.diagnostic_code}
        if hasattr(error, "mutation_outcome"):
            report["mutation_outcome"] = error.mutation_outcome

    encoded = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 1 if report.get("state") in {"SETUP_REQUIRED", "ADMISSION_VERIFIED_CONFIGURATION_PENDING"} else 0


if __name__ == "__main__":
    raise SystemExit(main())
