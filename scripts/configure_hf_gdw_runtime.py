#!/usr/bin/env python3
"""Check manual GDW credential prerequisites without mutating credentials.

Legacy admission additionally requires independently verified installed signing
authority (``scripts/verify_installed_authority.py``). Managed first cutover
requires immutable recovery admission and a verified old-source startup guard;
its predeploy report leaves signing authority unproven until actual startup and
native live proof. Existing Space secret values are never read.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import selectors
import signal
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Mapping


CANONICAL_SPACE = "SZLHOLDINGS/a11oy"
DATA_MOUNT = "/data"
PRINCIPAL_ID = "gdw-operator"
PRINCIPAL_REGISTRY_SECRET = "GDW_PRINCIPALS_JSON"
CREDENTIAL_REGISTRY_SECRET = "GDW_CREDENTIALS_JSON"
CREDENTIAL_KEY_ID = "gdw-operator-v1"
MANAGED_MODE = "private-dataset-v1"
MANAGED_EXPORT_GUARD = "durable-private-dataset-v1"
MANAGED_SDK_VERSION = "1.31.0"
MANAGED_PROTOCOL_LIMIT = 128 * 1024
MANAGED_RESPONSE_LIMIT = 512 * 1024
MANAGED_MAX_SECONDS = 120
MANAGED_SECRET_NAMES = {"HF_TOKEN", "GDW_CREDENTIALS_JSON", "SZL_COSIGN_PRIVATE_PEM"}
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
    # Legacy mount contract only. DELETE avoids WAL shared memory but does not
    # prove bucket-mount fsync durability; qualified recovery owns the cutover.
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
            "MANAGED_STORAGE_UNAVAILABLE", "MANAGED_OUTCOME_UNCERTAIN",
            *INSTALLED_AUTHORITY_DIAGNOSTICS,
        }
        self.diagnostic_code = diagnostic_code if diagnostic_code in allowed else "PREREQUISITES_UNAVAILABLE"


def _managed_error(code: str = "MANAGED_STORAGE_UNAVAILABLE") -> RuntimeConfigError:
    return RuntimeConfigError("managed storage qualification is unavailable", diagnostic_code=code)


def _managed_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii") + b"\n"


def _managed_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise _managed_error()
        result[key] = value
    return result


def _managed_api(*, write_values: dict[str, str] | None = None) -> Any:
    """Exact SDK and fixed routes, with an optional fixed variable-write scope.

    The parent owns a total wall-clock deadline. The SDK additionally receives
    no redirect, retry, ambient proxy, or implicit cached credential authority.
    The managed worker verifies immutable admission and the paused legacy guard
    before constructing the scoped writer. This argument narrows its effects;
    it is not itself an admission mechanism.
    """
    import httpx
    import huggingface_hub

    if huggingface_hub.__version__ != MANAGED_SDK_VERSION:
        raise _managed_error()
    token = os.environ.get("HF_TOKEN", "")
    if not token or any(character.isspace() for character in token):
        raise _managed_error()
    base = "https://huggingface.co/api/spaces/" + CANONICAL_SPACE
    allowed = {base, base + "/variables", base + "/secrets"}
    if write_values is not None:
        guard = _managed_guard_module()
        if type(write_values) is not dict or write_values != guard.MANAGED_VARIABLES:
            raise _managed_error()
        write_values = dict(write_values)

    class Client(httpx.Client):
        def request(self, method, url, *args, **kwargs):
            payload = kwargs.get("json")
            variable_write = (
                method == "POST" and str(url) == base + "/variables" and write_values is not None
                and type(payload) is dict and set(payload) == {"key", "value"}
                and type(payload["key"]) is str and payload["key"] in write_values
                and type(payload["value"]) is str and payload["value"] == write_values[payload["key"]])
            if not ((method == "GET" and str(url) in allowed) or variable_write):
                raise _managed_error()
            with super().stream(method, url, *args, **kwargs) as response:
                if response.status_code != 200:
                    raise _managed_error()
                content = bytearray()
                for chunk in response.iter_bytes(chunk_size=8192):
                    if len(content) + len(chunk) > MANAGED_RESPONSE_LIMIT:
                        raise _managed_error()
                    content.extend(chunk)
                return httpx.Response(200, content=bytes(content), request=response.request)

    huggingface_hub.set_client_factory(
        lambda: Client(timeout=20, follow_redirects=False, trust_env=False))
    return huggingface_hub.HfApi(endpoint="https://huggingface.co", token=token)


def managed_space_observation(api: Any) -> dict[str, Any]:
    """Bounded control-plane metadata, never secret values or live authority."""
    info = api.space_info(repo_id=CANONICAL_SPACE)
    revision = _value(info, "sha")
    runtime = _value(info, "runtime")
    stage = _value(runtime, "stage")
    stage = _value(stage, "value", stage)
    if (type(revision) is not str or re.fullmatch(r"[0-9a-f]{40}", revision) is None
            or revision == "0" * 40 or stage not in {"PAUSED", "RUNTIME_ERROR", "BUILDING", "RUNNING"}):
        raise _managed_error()
    secrets = api.get_space_secrets(repo_id=CANONICAL_SPACE)
    variables = api.get_space_variables(repo_id=CANONICAL_SPACE)
    if not isinstance(secrets, Mapping) or not isinstance(variables, Mapping):
        raise _managed_error()
    names = list(secrets)
    if (len(names) > 256 or len(variables) > 256
            or any(type(name) is not str or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,127}", name) is None
                   for name in names + list(variables))):
        raise _managed_error()
    # Public variables with credential names are an unsafe configuration;
    # do not inspect their values, even for a hash or diagnostic.
    if (MANAGED_SECRET_NAMES | {PRINCIPAL_REGISTRY_SECRET}).intersection(variables):
        raise _managed_error()
    values = {}
    for name, item in variables.items():
        value = _value(item, "value")
        if type(value) is not str or len(value.encode("utf-8")) > 8192:
            raise _managed_error()
        values[name] = value
    if len(_managed_json(values)) > MANAGED_PROTOCOL_LIMIT // 2:
        raise _managed_error()
    return {"space_revision": revision, "stage": str(stage), "variables": values,
            "secret_names": sorted(names),
            "variables_sha256": hashlib.sha256(_managed_json(values)).hexdigest()}


def _validate_managed_request(request: Any) -> None:
    if request == {"operation": "observe"}:
        return
    if (type(request) is not dict or set(request) != {"operation", "locator", "source_revision", "check_only", "deadline"}
            or request["operation"] != "configure" or type(request["check_only"]) is not bool
            or type(request["locator"]) is not dict or type(request["source_revision"]) is not str
            or re.fullmatch(r"[0-9a-f]{40}", request["source_revision"]) is None
            or request["source_revision"] == "0" * 40
            or type(request["deadline"]) not in (int, float)
            or not 0 < request["deadline"] - time.monotonic() <= MANAGED_MAX_SECONDS):
        raise _managed_error()


def managed_worker_call(request: dict[str, Any], *, deadline: float) -> dict[str, Any]:
    """Fixed child entrypoint with bounded protocol, deadline and group cleanup.

    The configuration worker independently reads immutable provider admission
    before constructing the fixed variable-write client. A locator is not an
    effect grant, and every uncertain worker outcome stops without retry.
    """
    _validate_managed_request(request)
    remaining = deadline - time.monotonic()
    if (not 0 < remaining <= MANAGED_MAX_SECONDS
            or (request["operation"] == "configure" and request["deadline"] != deadline)):
        raise _managed_error()
    encoded_request = _managed_json(request)
    if len(encoded_request) > MANAGED_PROTOCOL_LIMIT:
        raise _managed_error()
    process = None
    output = bytearray()
    try:
        with tempfile.TemporaryDirectory(prefix="gdw-managed-control-") as temporary:
            input_path = Path(temporary) / "request.json"
            input_path.write_bytes(encoded_request)
            input_path.chmod(0o600)
            with input_path.open("rb") as input_stream:
                environment = {"PATH": os.defpath, "HF_TOKEN": os.environ.get("HF_TOKEN", "")}
                if request["operation"] == "configure":
                    environment["GH_TOKEN"] = os.environ.get("GH_TOKEN", "")
                process = subprocess.Popen(
                    [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--managed-worker"],
                    stdin=input_stream, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    cwd=temporary, start_new_session=True,
                    env=environment)
                with selectors.DefaultSelector() as selector:
                    selector.register(process.stdout, selectors.EVENT_READ)
                    while selector.get_map():
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise _managed_error("MANAGED_OUTCOME_UNCERTAIN")
                        for key, _ in selector.select(min(remaining, 0.1)):
                            chunk = os.read(key.fileobj.fileno(), min(8192, MANAGED_PROTOCOL_LIMIT + 1 - len(output)))
                            if not chunk:
                                selector.unregister(key.fileobj)
                            else:
                                output.extend(chunk)
                                if len(output) > MANAGED_PROTOCOL_LIMIT:
                                    raise _managed_error("MANAGED_OUTCOME_UNCERTAIN")
                process.wait(timeout=max(0.001, deadline - time.monotonic()))
                if time.monotonic() >= deadline:
                    raise _managed_error("MANAGED_OUTCOME_UNCERTAIN")
            value = json.loads(output, object_pairs_hook=_managed_object)
            if (process.returncode != 0 and type(value) is dict and set(value) == {"ok", "code"}
                    and value["ok"] is False and value["code"] in {
                        "MANAGED_STORAGE_UNAVAILABLE", "MANAGED_OUTCOME_UNCERTAIN"}):
                raise _managed_error(value["code"])
            if process.returncode != 0:
                raise _managed_error("MANAGED_OUTCOME_UNCERTAIN")
            if type(value) is not dict or set(value) != {"ok", "value"} or value["ok"] is not True:
                raise _managed_error()
            if type(value["value"]) is not dict:
                raise _managed_error()
            result = value["value"]
        if time.monotonic() >= deadline:
            raise _managed_error("MANAGED_OUTCOME_UNCERTAIN")
        return result
    except RuntimeConfigError:
        raise
    except Exception:
        raise _managed_error("MANAGED_OUTCOME_UNCERTAIN") from None
    finally:
        if process is not None:
            try:
                # A parent may have exited while a descendant retains stdout.
                # Kill the group even when poll() already sees that exit.
                os.killpg(process.pid, signal.SIGKILL)
                if process.poll() is None:
                    process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
            if process.stdout is not None:
                process.stdout.close()


def _managed_worker() -> int:
    try:
        raw = sys.stdin.buffer.read(MANAGED_PROTOCOL_LIMIT + 1)
        if not 1 <= len(raw) <= MANAGED_PROTOCOL_LIMIT:
            raise _managed_error()
        request = json.loads(raw, object_pairs_hook=_managed_object)
        _validate_managed_request(request)
        value = (managed_space_observation(_managed_api()) if request["operation"] == "observe"
                 else _managed_configuration_worker(request))
        encoded = _managed_json({"ok": True, "value": value})
        if len(encoded) > MANAGED_PROTOCOL_LIMIT:
            raise _managed_error()
        sys.stdout.buffer.write(encoded)
        return 0
    except BaseException as error:
        code = ("MANAGED_OUTCOME_UNCERTAIN" if isinstance(error, RuntimeConfigError)
                and error.diagnostic_code == "MANAGED_OUTCOME_UNCERTAIN" else "MANAGED_STORAGE_UNAVAILABLE")
        sys.stdout.buffer.write(_managed_json({"ok": False, "code": code}))
        return 1


class ManagedProofContext:
    """Immutable admission identity and native dataset witness verification.

    The canonical loader supplies the provider-read admission and private
    worker backend. A live mode flag or locally supplied report never creates
    this context. Each runtime witness is checked against its immutable
    acknowledged HEAD and matching history object, avoiding a latest-HEAD race
    with a concurrent legitimate drain commit.
    """
    def __init__(self, admission: Mapping[str, Any], admission_sha256: str,
                 backend: Any, *, deadline: float, staging: Any = None):
        self._identity = {
            "source_revision": admission["source"]["revision"],
            "admission_sha256": admission_sha256,
            "qualification_sha256": admission["qualification"]["report_sha256"],
            "generations": {label: admission["snapshots"][label]["generation"]
                            for label in ("gdw", "series_a")},
        }
        self._identity = json.loads(_managed_json(self._identity))
        self._backend = backend
        self._deadline = deadline
        self._staging = staging
        self._closed = False
        self._latest = None

    @property
    def identity(self) -> dict[str, Any]:
        return json.loads(_managed_json(self._identity))

    @property
    def latest_witness(self) -> dict[str, Any] | None:
        return None if self._latest is None else json.loads(_managed_json(self._latest))

    def validate(self, witness: Any, *, label: str, generation: str) -> dict[str, Any]:
        fields = {"schema", "mode", "source_revision", "admission_sha256", "qualification_sha256",
                  "dataset_revision", "operation_id", "writer_epoch", "generations",
                  "actual_host_full_state_ack_ms", "startup_state", "throughput_claim"}
        try:
            if (self._closed or time.monotonic() >= self._deadline
                    or type(witness) is not dict or set(witness) != fields
                    or label not in ("gdw", "series_a")
                    or generation != self._identity["generations"][label]):
                raise _managed_error()
            expected = {"schema": "szl.gdw-managed-runtime/v1", "mode": MANAGED_MODE,
                        "startup_state": "RESTORED_AND_ACKNOWLEDGED", "throughput_claim": "NOT_CLAIMED",
                        **self.identity}
            for name, value in expected.items():
                if type(witness[name]) is not type(value) or witness[name] != value:
                    raise _managed_error()
            for name, length in (("dataset_revision", 40), ("operation_id", 32)):
                value = witness[name]
                if (type(value) is not str or re.fullmatch(r"[0-9a-f]{" + str(length) + "}", value) is None
                        or value == "0" * length):
                    raise _managed_error()
            if (type(witness["writer_epoch"]) is not int or witness["writer_epoch"] < 1
                    or type(witness["actual_host_full_state_ack_ms"]) is not int
                    or not 1 <= witness["actual_host_full_state_ack_ms"] <= 60_000):
                raise _managed_error()
            head, history = self._backend.read_at(
                witness["dataset_revision"], witness["operation_id"], self._deadline)
            if (history != head.body or head.revision != witness["dataset_revision"]
                    or head.value["operation_id"] != witness["operation_id"]
                    or head.value["kind"] not in {"CLAIM", "COMMIT"}
                    or head.value["epoch"] != witness["writer_epoch"]
                    or head.value["qualification_sha256"] != self._identity["admission_sha256"]
                    or head.value["source_revision"] != self._identity["source_revision"]
                    or any(head.value["snapshots"][store]["generation"] != self._identity["generations"][store]
                           for store in ("gdw", "series_a"))
                    or time.monotonic() >= self._deadline):
                raise _managed_error()
            self._latest = json.loads(_managed_json(witness))
            return self.latest_witness
        except RuntimeConfigError:
            raise
        except Exception:
            raise _managed_error() from None

    def close(self) -> None:
        self._closed = True
        if self._staging is not None:
            try:
                self._staging.cleanup()
            except OSError:
                raise _managed_error() from None


def _load_managed_module(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise _managed_error()
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return module


def _read_acquisition_locator(path: Path) -> dict[str, Any]:
    descriptor = os.open(path, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
    try:
        metadata = os.fstat(descriptor)
        if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                or metadata.st_uid != os.geteuid() or not 1 <= metadata.st_size <= 16 * 1024):
            raise _managed_error()
        encoded = os.read(descriptor, 16 * 1024 + 1)
        if len(encoded) != metadata.st_size:
            raise _managed_error()
    finally:
        os.close(descriptor)
    parser = _load_managed_module("_gdw_acquisition_locator",
        Path(__file__).resolve().with_name("acquire_gdw_durable_storage.py"))
    return parser.parse_acquisition_locator(encoded)


def _verified_managed_admission(locator: Mapping[str, Any], *, source_revision: str,
                                directory: Path, deadline: float) -> tuple[dict, Any, Any]:
    """Read provider authority; a locator selects but never authorizes state."""
    if (type(locator) is not dict or set(locator) != {
            "schema", "state", "space", "dataset", "bucket", "source_revision", "source_manifest_sha256",
            "admission_sha256", "qualification_sha256", "dataset_revision", "operation_id",
            "resource_group_sha256", "generations", "legacy_guard_sha256"}):
        raise _managed_error()
    import huggingface_hub
    if huggingface_hub.__version__ != MANAGED_SDK_VERSION:
        raise _managed_error()
    source_root = Path(__file__).resolve().parent.parent
    if str(source_root) not in sys.path:
        sys.path.insert(0, str(source_root))
    import gdw_durable_storage as storage
    import gdw_durable_startup as startup
    for module, name in ((storage, "gdw_durable_storage.py"), (startup, "gdw_durable_startup.py")):
        if Path(module.__file__).resolve() != source_root / name:
            raise _managed_error()
    head, encoded, resource_group = storage.load_admitted_head(directory, deadline)
    admission = startup.parse_admission(encoded)
    expected = {
        "space": CANONICAL_SPACE, "dataset": "SZLHOLDINGS/szl-evidence", "bucket": "SZLHOLDINGS/szl-evidence",
        "source_revision": source_revision,
        "source_manifest_sha256": admission["runtime"]["source_manifest_sha256"],
        "admission_sha256": hashlib.sha256(encoded).hexdigest(),
        "qualification_sha256": admission["qualification"]["report_sha256"],
        "resource_group_sha256": resource_group,
        "generations": {label: admission["snapshots"][label]["generation"] for label in ("gdw", "series_a")},
        "legacy_guard_sha256": hashlib.sha256(_managed_json(admission["legacy_guard"])).hexdigest(),
    }
    if (locator.get("schema") != "szl.gdw-durable-acquisition/v1"
            or locator.get("state") != "BOOTSTRAP_ACKNOWLEDGED"
            or admission["source"]["revision"] != source_revision
            or admission["provider"]["resource_group_observation_sha256"] != resource_group):
        raise _managed_error()
    for name, value in expected.items():
        if type(locator.get(name)) is not type(value) or locator[name] != value:
            raise _managed_error()
    if (head.value["qualification_sha256"] != expected["admission_sha256"]
            or head.value["source_revision"] != source_revision
            or any(head.value["snapshots"][label]["generation"] != expected["generations"][label]
                   for label in ("gdw", "series_a"))):
        raise _managed_error()
    backend = storage.WorkerFenceBackend(directory, resource_group)
    initial, history = backend.read_at(locator["dataset_revision"], locator["operation_id"], deadline)
    if (initial.revision != locator["dataset_revision"] or initial.value["operation_id"] != locator["operation_id"]
            or initial.value["kind"] != "BOOTSTRAP" or history != initial.body
            or backend.read_admission(initial, deadline) != encoded):
        raise _managed_error()
    startup.validate_bootstrap_binding(admission, initial.value)
    if time.monotonic() >= deadline:
        raise _managed_error()
    return admission, head, backend


def load_managed_proof_context(receipt_path: Path, *, source_revision: str,
                               deadline: float) -> ManagedProofContext:
    staging = None
    try:
        if (type(source_revision) is not str or re.fullmatch(r"[0-9a-f]{40}", source_revision) is None
                or source_revision == "0" * 40 or time.monotonic() >= deadline):
            raise _managed_error()
        locator = _read_acquisition_locator(Path(receipt_path))
        staging = tempfile.TemporaryDirectory(prefix="gdw-managed-proof-")
        admission, head, backend = _verified_managed_admission(
            locator, source_revision=source_revision, directory=Path(staging.name), deadline=deadline)
        return ManagedProofContext(admission, head.value["qualification_sha256"], backend,
                                   deadline=deadline, staging=staging)
    except BaseException:
        if staging is not None:
            try:
                staging.cleanup()
            except OSError:
                pass
        raise _managed_error() from None


def _managed_guard_module() -> Any:
    return _load_managed_module("_gdw_managed_guard", Path(__file__).resolve().parent.parent / "gdw_durable_guard.py")


def _managed_configuration_report(admission, locator, *, changed, verified):
    return {
        "schema": "szl.hf-managed-storage-config/v1",
        "state": "CONFIGURATION_VERIFIED" if verified else "ADMISSION_VERIFIED_CONFIGURATION_PENDING",
        "repo_id": CANONICAL_SPACE,
        "managed_identity": {
            "source_revision": locator["source_revision"], "admission_sha256": locator["admission_sha256"],
            "qualification_sha256": locator["qualification_sha256"], "generations": dict(locator["generations"])},
        "source_manifest_sha256": locator["source_manifest_sha256"],
        "bootstrap_dataset_revision": locator["dataset_revision"],
        "bootstrap_operation_id": locator["operation_id"],
        "legacy_space_revision": admission["legacy_guard"]["space_revision"],
        "legacy_guard_sha256": locator["legacy_guard_sha256"],
        "credential_authority_state": "SIGNING_AUTHORITY_UNPROVEN_UNTIL_STARTUP",
        "operational_state": "GUARDED_OLD_RUNTIME_BLOCKED" if verified else "LEGACY_PAUSED",
        "persistent_export_guard": MANAGED_EXPORT_GUARD if verified else None,
        "variables_changed": list(changed), "converged": verified,
        "legacy_resume_allowed": False, "runtime_proven": False,
        "secret_values_read": False, "secret_values_written": False, "volumes_mutated": False,
    }


def _managed_require_main(source_revision: str, deadline: float) -> None:
    """Existing canonical GitHub reader; exact main is required, not ancestry."""
    try:
        if time.monotonic() >= deadline:
            raise _managed_error()
        token = os.environ.get("GH_TOKEN", "")
        if not token or any(character.isspace() for character in token):
            raise _managed_error()
        ownership = _load_managed_module("_gdw_managed_main_ownership",
            Path(__file__).resolve().with_name("hf_exact_main_ownership.py"))
        if (ownership.fetch_main_sha("szl-holdings/a11oy", token) != source_revision
                or time.monotonic() >= deadline):
            raise _managed_error()
    except BaseException:
        raise _managed_error() from None


def _configure_admitted_managed_storage(api, admission, locator, head, backend, *, deadline, check_only):
    """One guarded attempt; no retry or compensation of a variable write."""
    guard = _managed_guard_module()
    guard.validate_legacy_guard(admission["legacy_guard"])
    initial, history = backend.read_at(locator["dataset_revision"], locator["operation_id"], deadline)
    if head.value["kind"] != "BOOTSTRAP" or head.body != initial.body or history != initial.body:
        raise _managed_error()
    before = managed_space_observation(api)
    guard.validate_legacy_guard_observation(admission["legacy_guard"], before)
    _managed_require_main(locator["source_revision"], deadline)
    baseline = dict(before["variables"])
    if check_only:
        return _managed_configuration_report(admission, locator, changed=[], verified=False)
    expected = dict(baseline)
    changed = []
    # The old source rejects this first value before writable probes or store
    # construction. It is never cleared remotely, including on a partial error.
    ordered = ["GDW_PROOF_EXPORT_MODE"] + sorted(set(guard.MANAGED_VARIABLES) - {"GDW_PROOF_EXPORT_MODE"})
    attempted = False
    try:
        for name in ordered:
            if time.monotonic() >= deadline or backend.observe(deadline).body != initial.body:
                raise _managed_error()
            _managed_require_main(locator["source_revision"], deadline)
            value = guard.MANAGED_VARIABLES[name]
            if expected.get(name) != value:
                attempted = True
                api.add_space_variable(repo_id=CANONICAL_SPACE, key=name, value=value)
                expected[name] = value
                changed.append(name)
            # Each subsequent effect requires fresh exact source/stage/environment
            # readback. Uncertain readback cannot be used as permission to proceed.
            after = managed_space_observation(api)
            guard.validate_legacy_guard_observation(admission["legacy_guard"], after,
                baseline_variables=baseline, expected_variables=expected)
        if time.monotonic() >= deadline or backend.observe(deadline).body != initial.body:
            raise _managed_error()
        _managed_require_main(locator["source_revision"], deadline)
    except BaseException:
        raise _managed_error("MANAGED_OUTCOME_UNCERTAIN" if attempted else "MANAGED_STORAGE_UNAVAILABLE") from None
    return _managed_configuration_report(admission, locator, changed=changed, verified=True)


def _managed_configuration_worker(request):
    _validate_managed_request(request)
    if request["operation"] != "configure":
        raise _managed_error()
    _managed_require_main(request["source_revision"], request["deadline"])
    parser = _load_managed_module("_gdw_acquisition_locator",
        Path(__file__).resolve().with_name("acquire_gdw_durable_storage.py"))
    locator = parser.parse_acquisition_locator(_managed_json(request["locator"]))
    with tempfile.TemporaryDirectory(prefix="gdw-managed-admission-") as temporary:
        admission, head, backend = _verified_managed_admission(
            locator, source_revision=request["source_revision"], directory=Path(temporary), deadline=request["deadline"])
        # Fixed secret names and old-state evidence are checked with a read-only
        # client before the optional writer client even exists.
        guard = _managed_guard_module()
        observation = managed_space_observation(_managed_api())
        guard.validate_legacy_guard_observation(admission["legacy_guard"], observation)
        api = _managed_api(write_values=None if request["check_only"] else guard.MANAGED_VARIABLES)
        return _configure_admitted_managed_storage(api, admission, locator, head, backend,
            deadline=request["deadline"], check_only=request["check_only"])


def configure_managed(receipt_path: Path, *, source_revision: str, deadline: float,
                      check_only: bool = False, repo_id: str = CANONICAL_SPACE) -> dict[str, Any]:
    """One explicit first-cutover attempt for both stores; no legacy resume.

    The two existing CLIs are alternative callers of this same coordinator.
    Running both sequentially, or retrying a partial configuration, is refused
    because the original admitted PAUSED environment no longer matches.
    """
    try:
        if repo_id != CANONICAL_SPACE or type(check_only) is not bool:
            raise _managed_error()
        request = {"operation": "configure", "locator": {}, "source_revision": source_revision,
                   "check_only": check_only, "deadline": deadline}
        _validate_managed_request(request)
        request["locator"] = _read_acquisition_locator(Path(receipt_path))
        return managed_worker_call(request, deadline=deadline)
    except RuntimeConfigError:
        raise
    except BaseException:
        raise _managed_error() from None


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
    # The export-mode guard is installed before any other managed variable.
    # A legacy invocation must not remove that first cutover barrier while the
    # remaining managed configuration is deliberately incomplete.
    export_mode = _value(current.get("GDW_PROOF_EXPORT_MODE"), "value", "")
    if (_value(current.get("GDW_DURABLE_STORAGE"), "value", "")
            or (export_mode and export_mode != "outbox")):
        raise RuntimeConfigError("qualified durable storage cannot be replaced by the legacy mount contract")
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



def _legacy_guard_rules() -> Any:
    return _load_managed_module("_gdw_legacy_guard_probe_rules",
        Path(__file__).resolve().parent.parent / "gdw_durable_guard.py")


def _legacy_guard_sources(source_directory: Path, rules: Any) -> dict[str, bytes]:
    """Read only the fixed, bounded closure; refuse drift before execution."""
    directory = Path(source_directory)
    if not stat.S_ISDIR(directory.lstat().st_mode):
        raise _managed_error()
    sources = {}
    for name, expected in rules.SOURCE_FILES.items():
        descriptor = os.open(directory / name, os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW)
        try:
            metadata = os.fstat(descriptor)
            if (not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1
                    or not 1 <= metadata.st_size <= 2 * 1024 * 1024):
                raise _managed_error()
            with os.fdopen(descriptor, "rb", closefd=False) as stream:
                data = stream.read(2 * 1024 * 1024 + 1)
            if len(data) != metadata.st_size or hashlib.sha256(data).hexdigest() != expected:
                raise _managed_error()
            sources[name] = data
        finally:
            os.close(descriptor)
    return sources


def _legacy_guard_case_variables(variables: dict, case: str, directory: Path, rules: Any) -> dict:
    changes = {
        "default": {},
        "production_disabled": {"GDW_PRODUCTION_MODE": "0"},
        "persistence_disabled": {"GDW_REQUIRE_PERSISTENT_STORAGE": "0"},
        "outbox_disabled": {"GDW_OUTBOX_ENABLED": "0"},
        "durable_flag": {"GDW_DURABLE_STORAGE": rules.MODE},
        "wal_requested": {"GDW_SQLITE_JOURNAL": "WAL"},
        "normal_sync": {"GDW_SQLITE_SYNCHRONOUS": "NORMAL"},
        "combined_bypass_flags": {"GDW_PRODUCTION_MODE": "0", "GDW_REQUIRE_PERSISTENT_STORAGE": "0",
                                  "GDW_OUTBOX_ENABLED": "0", "GDW_DURABLE_STORAGE": rules.MODE,
                                  "GDW_SQLITE_JOURNAL": "WAL", "GDW_SQLITE_SYNCHRONOUS": "NORMAL"},
    }
    if case == "unguarded_control":
        return {**variables, "GDW_PROOF_EXPORT_MODE": "outbox", "GDW_REQUIRED_MOUNT": "",
                "GDW_REQUIRE_PERSISTENT_STORAGE": "0", "GDW_SQLITE_JOURNAL": "DELETE",
                "GDW_SQLITE_SYNCHRONOUS": "FULL", "GDW_DB_PATH": str(directory / "disposable" / "gdw.sqlite3"),
                "GDW_PROOF_DIR": str(directory / "disposable" / "proofs"),
                "GDW_RECEIPT_PROJECTION_DIR": str(directory / "disposable" / "receipts")}
    if case not in rules.CASES or set(changes) != set(rules.CASES):
        raise _managed_error()
    return {**variables, "GDW_PROOF_EXPORT_MODE": rules.EXPORT_GUARD, **changes[case]}


def _legacy_guard_worker() -> int:
    """Probe exact deployed imports and main, after interpreter initialization.

    This is a source-bound effect observation, not an OS sandbox or a claim
    about interpreter/site initialization. The parent strips all ambient
    credentials before starting this worker; no secret values are supplied.
    """
    try:
        import _thread
        import runpy
        import threading

        request = json.loads(sys.stdin.buffer.read(MANAGED_PROTOCOL_LIMIT + 1), object_pairs_hook=_managed_object)
        if (type(request) is not dict or set(request) != {"case", "variables", "secret_names"}):
            raise _managed_error()
        rules = _legacy_guard_rules()
        rules.validate_environment(request["variables"], request["secret_names"])
        directory = Path.cwd()
        _legacy_guard_sources(directory, rules)
        case = request["case"]
        variables = _legacy_guard_case_variables(request["variables"], case, directory, rules)
        # Public variables are applied only after isolated Python initialization.
        os.environ.clear()
        os.environ.update(variables)
        sys.path.insert(0, str(directory))
        if any(name in sys.modules for name in ("gdw_runtime", "gdw_workspace", "gdw_proofs",
                                               "szl_dsse", "szl_content_address")):
            raise _managed_error()
        baseline_threads = set(threading.enumerate())
        effects = []

        class ForbiddenEffect(BaseException):
            pass

        def forbidden(event):
            preparation = False
            frame = sys._getframe()
            while frame is not None:
                if (frame.f_code.co_name == "_verify_writable_directory"
                        and frame.f_code.co_filename == str(directory / "gdw_runtime.py")):
                    preparation = True
                frame = frame.f_back
            effects.append((event, preparation))
            raise ForbiddenEffect()

        def audit(event, args):
            if event == "open":
                mode, flags = args[1], args[2]
                if ((isinstance(mode, str) and any(char in mode for char in "wax+"))
                        or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))):
                    forbidden("file_write")
            elif event in {"os.mkdir", "os.remove", "os.rmdir", "os.rename", "os.link", "os.symlink",
                           "os.chmod", "os.chown", "os.truncate", "os.utime", "os.setxattr", "os.removexattr",
                           "shutil.copyfile", "shutil.copymode", "shutil.copystat"}:
                forbidden(event)
            elif event.startswith(("sqlite3.connect", "socket.", "subprocess.", "_thread.start")) or event in {
                    "os.system", "os.fork", "os.forkpty", "os.posix_spawn", "os.exec", "os.startfile", "pty.spawn"}:
                forbidden(event)

        def blocked_thread(*_args, **_kwargs):
            forbidden("thread_start")

        # CPython 3.12 lacks a thread-start audit event; intercept both public
        # and threading-cached primitives, including 3.14's joinable primitive.
        for module, names in ((_thread, ("start_new_thread", "start_new", "start_joinable_thread")),
                              (threading, ("_start_new_thread", "_start_joinable_thread"))):
            for name in names:
                if hasattr(module, name):
                    setattr(module, name, blocked_thread)
        threading.Thread.start = blocked_thread
        sys.addaudithook(audit)
        state = None
        try:
            runpy.run_path(str(directory / "gdw_runtime.py"), run_name="__main__")
        except ForbiddenEffect:
            if case == "unguarded_control" and effects == [("os.mkdir", True)]:
                state = "PREPARATION_WRITE_OBSERVED"
        except Exception as error:
            if (case != "unguarded_control" and not effects
                    and type(error).__name__ == "GDWRuntimeError"
                    and type(error).__module__ == "__main__"
                    and str(error) == "GDW_PROOF_EXPORT_MODE must be 'outbox'; synchronous export is not transaction-safe"):
                state = "PREWRITE_REJECTION_VERIFIED"
        if state is None or set(threading.enumerate()) != baseline_threads:
            raise _managed_error()
        value = {"name": case, "state": state, "forbidden_effect_count": len(effects),
                 "python_version": ".".join(str(part) for part in sys.version_info[:3])}
        sys.stdout.buffer.write(_managed_json({"ok": True, "value": value}))
        return 0
    except BaseException:
        sys.stdout.write('{"ok":false,"code":"LEGACY_GUARD_PROBE_FAILED"}\n')
        return 1


def _legacy_guard_child(request: dict, *, directory: Path, deadline: float) -> dict:
    """Fixed worker, credential-free environment, bounded pipe and process group."""
    process = None
    output = bytearray()
    remaining = deadline - time.monotonic()
    if not 0 < remaining <= MANAGED_MAX_SECONDS:
        raise _managed_error()
    try:
        # Use a private prewritten input so stdin cannot block the parent while
        # the child is being admitted. The worker receives no ambient secrets.
        with tempfile.TemporaryFile() as input_stream:
            input_stream.write(_managed_json(request))
            input_stream.seek(0)
            process = subprocess.Popen(
                [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--legacy-guard-worker"],
                stdin=input_stream, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                cwd=directory, env={"PATH": os.defpath, "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
                start_new_session=True)
            with selectors.DefaultSelector() as selector:
                selector.register(process.stdout, selectors.EVENT_READ)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise _managed_error()
                    for key, _mask in selector.select(min(remaining, 0.1)):
                        chunk = os.read(key.fileobj.fileno(), min(8192, 16 * 1024 + 1 - len(output)))
                        if not chunk:
                            selector.unregister(process.stdout)
                        else:
                            output.extend(chunk)
                            if len(output) > 16 * 1024:
                                raise _managed_error()
            process.wait(timeout=max(0.001, deadline - time.monotonic()))
            if process.returncode != 0 or time.monotonic() >= deadline:
                raise _managed_error()
        result = json.loads(output, object_pairs_hook=_managed_object)
        if (type(result) is not dict or set(result) != {"ok", "value"} or result["ok"] is not True
                or type(result["value"]) is not dict):
            raise _managed_error()
        return result["value"]
    except RuntimeConfigError:
        raise
    except BaseException:
        raise _managed_error() from None
    finally:
        if process is not None:
            try:
                os.killpg(process.pid, signal.SIGKILL)
                if process.poll() is None:
                    process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
            if process.stdout is not None:
                process.stdout.close()


def legacy_guard_probe(source_directory: Path, *, variables: dict, secret_names: list,
                       deadline: float) -> dict:
    """Observe the exact legacy guard; never upgrades a local Python version."""
    try:
        rules = _legacy_guard_rules()
        rules.validate_environment(variables, secret_names)
        if not 0 < deadline - time.monotonic() <= MANAGED_MAX_SECONDS:
            raise _managed_error()
        sources = _legacy_guard_sources(Path(source_directory), rules)
        results = []
        python_version = None
        with tempfile.TemporaryDirectory(prefix="gdw-legacy-guard-") as temporary:
            directory = Path(temporary)
            for name, data in sources.items():
                path = directory / name
                path.write_bytes(data)
                path.chmod(0o400)
            for case in (*rules.CASES, "unguarded_control"):
                result = _legacy_guard_child({"case": case, "variables": variables, "secret_names": secret_names},
                                             directory=directory, deadline=deadline)
                expected_state = "PREPARATION_WRITE_OBSERVED" if case == "unguarded_control" else "PREWRITE_REJECTION_VERIFIED"
                expected_count = 1 if case == "unguarded_control" else 0
                if (set(result) != {"name", "state", "forbidden_effect_count", "python_version"}
                        or result["name"] != case or result["state"] != expected_state
                        or type(result["forbidden_effect_count"]) is not int
                        or result["forbidden_effect_count"] != expected_count
                        or type(result["python_version"]) is not str
                        or re.fullmatch(r"3\.\d{1,3}\.\d{1,3}", result["python_version"]) is None):
                    raise _managed_error()
                if python_version is not None and python_version != result["python_version"]:
                    raise _managed_error()
                python_version = result.pop("python_version")
                if case != "unguarded_control":
                    results.append(result)
            _legacy_guard_sources(directory, rules)
        if time.monotonic() >= deadline:
            raise _managed_error()
        return {"schema": "szl.gdw-legacy-guard-probe/v1", "state": "PREWRITE_REJECTION_VERIFIED",
                "python_version": python_version, "scope": rules.PROBE_SCOPE,
                "source_files_sha256": dict(rules.SOURCE_FILES),
                "source_closure_sha256": hashlib.sha256(rules.canonical(rules.SOURCE_FILES)).hexdigest(),
                "cases": results, "unguarded_control": "PREPARATION_WRITE_OBSERVED",
                "total_forbidden_effect_count": 0}
    except BaseException:
        raise _managed_error() from None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-id", default=CANONICAL_SPACE)
    parser.add_argument("--output")
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--managed-acquisition", type=Path)
    parser.add_argument("--source-sha")
    parser.add_argument("--managed-deadline-seconds", type=float, default=MANAGED_MAX_SECONDS)
    args = parser.parse_args(argv)
    try:
        if args.managed_acquisition is not None or args.source_sha is not None:
            if args.managed_acquisition is None or args.source_sha is None:
                raise _managed_error()
            report = configure_managed(args.managed_acquisition, source_revision=args.source_sha,
                deadline=time.monotonic() + args.managed_deadline_seconds,
                check_only=args.check_only, repo_id=args.repo_id)
        else:
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
    return 1 if report.get("state") in {"SETUP_REQUIRED", "ADMISSION_VERIFIED_CONFIGURATION_PENDING"} else 0


if __name__ == "__main__":
    raise SystemExit(_managed_worker() if sys.argv[1:] == ["--managed-worker"] else
                     _legacy_guard_worker() if sys.argv[1:] == ["--legacy-guard-worker"] else main())
