"""Authenticated Governed Delta Workspace API and benchmark surfaces."""

import asyncio
import hashlib
import json
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import List, Literal, Optional
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field, ValidationError

from gdw_attention import AttentionFeatures, choose_attention_mode
from gdw_auth import (
    AuthConfigurationError,
    AuthenticationError,
    Principal,
    authenticate_bearer,
    load_credential_registry,
)
from gdw_proofs import build_proof_payload, sha256_json
from gdw_runtime import drain_once, runtime_health
from gdw_telemetry import GDWTelemetry
from gdw_workspace import (
    GDWConfigurationError,
    GDWLifecycleError,
    GDWQuotaExceeded,
    GDWWorkspace,
)
from szl_sgh_scheduler import build_plan


_TELEMETRY = GDWTelemetry()
_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")
_EXPERTS = {"planner", "retriever", "auditor", "verifier", "operator"}
_AUTH_LOCK = threading.RLock()
_STEP_WRITE_LOCKS = tuple(threading.Lock() for _ in range(1024))
_POLICY_READINESS_LOCK = threading.Lock()
_POLICY_READINESS_CACHE = {
    "origin": None,
    "checked_at": 0.0,
    "ready": False,
}
_AUTH_REGISTRY = None
_AUTH_FINGERPRINT = None


def _step_write_locks(
    namespace: str,
    owner_id: str,
    session_id: str,
    request_id: str,
) -> tuple[threading.Lock, ...]:
    indexes = set()
    for scope, value in (("session", session_id), ("request", request_id)):
        key = "\x00".join((scope, namespace, owner_id, value)).encode("utf-8")
        digest = hashlib.sha256(key).digest()
        indexes.add(int.from_bytes(digest[:4], "big") % len(_STEP_WRITE_LOCKS))
    return tuple(_STEP_WRITE_LOCKS[index] for index in sorted(indexes))


async def _acquire_step_write_locks(
    locks: tuple[threading.Lock, ...],
) -> None:
    acquired = []
    try:
        for lock in locks:
            while not lock.acquire(blocking=False):
                await asyncio.sleep(0.01)
            acquired.append(lock)
    except BaseException:
        for lock in reversed(acquired):
            lock.release()
        raise


class GDWStepRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    request: str = Field(min_length=1, max_length=4096)
    allowed_experts: List[str] = Field(default_factory=list)
    risk_budget: float = Field(default=0.35, ge=0.0, le=1.0)
    mode_hint: Literal[
        "auto", "kda_local", "laguna_hybrid", "mla_global"
    ] = "auto"
    dry_run: bool = False
    novelty: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    disagreement: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    context_tokens: int = Field(default=0, ge=0, le=1000000)
    active_tool_count: int = Field(default=0, ge=0, le=64)
    memory_pressure: Optional[float] = Field(default=None, ge=0.0, le=1.0)

    class Config:
        extra = "forbid"


def _dump_model(model):
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json")
    return model.dict()


def _model_schema(model):
    if hasattr(model, "model_json_schema"):
        return model.model_json_schema()
    return model.schema()


def _validate_step_payload(value) -> GDWStepRequest:
    try:
        if hasattr(GDWStepRequest, "model_validate"):
            return GDWStepRequest.model_validate(value)
        return GDWStepRequest.parse_obj(value)
    except ValidationError as exc:
        raise HTTPException(
            status_code=422,
            detail="invalid GDW step request",
        ) from exc


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha(value) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _credential_registry():
    global _AUTH_FINGERPRINT, _AUTH_REGISTRY
    registry_json = os.environ.get("GDW_CREDENTIALS_JSON")
    principal_registry_json = os.environ.get("GDW_PRINCIPALS_JSON")
    legacy_enabled = os.environ.get(
        "GDW_ALLOW_LEGACY_AUTH", ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    legacy_scopes = tuple(
        value.strip()
        for value in os.environ.get("GDW_LEGACY_SCOPES", "").split(",")
        if value.strip()
    )
    principal_namespace = os.environ.get("GDW_NAMESPACE") or "a11oy"
    legacy_token = os.environ.get("GDW_AUTH_TOKEN") if legacy_enabled else None
    legacy_owner_id = os.environ.get("GDW_OWNER_ID") if legacy_enabled else None
    legacy_namespace = os.environ.get("GDW_NAMESPACE") if legacy_enabled else None
    if not legacy_enabled:
        legacy_scopes = ()
    fingerprint = _sha(
        {
            "registry": registry_json,
            "principal_registry": principal_registry_json,
            "principal_namespace": principal_namespace,
            "legacy_enabled": legacy_enabled,
            "legacy_token": legacy_token,
            "legacy_owner": legacy_owner_id,
            "legacy_namespace": legacy_namespace,
            "legacy_scopes": legacy_scopes,
        }
    )
    with _AUTH_LOCK:
        if _AUTH_REGISTRY is not None and _AUTH_FINGERPRINT == fingerprint:
            return _AUTH_REGISTRY
        registry = load_credential_registry(
            registry_json,
            principal_registry_json=principal_registry_json,
            principal_registry_namespace=principal_namespace,
            legacy_enabled=legacy_enabled,
            legacy_token=legacy_token,
            legacy_owner_id=legacy_owner_id,
            legacy_namespace=legacy_namespace,
            legacy_scopes=legacy_scopes,
        )
        _AUTH_REGISTRY = registry
        _AUTH_FINGERPRINT = fingerprint
        return registry


def _authorise(
    authorization: Optional[str],
    *,
    namespace: str,
    required_scopes=(),
) -> Principal:
    try:
        return authenticate_bearer(
            authorization,
            _credential_registry(),
            namespace=namespace,
            required_scopes=required_scopes,
        )
    except AuthConfigurationError as exc:
        raise HTTPException(
            status_code=503,
            detail="GDW credential registry is unavailable",
        ) from exc
    except AuthenticationError as exc:
        status = 403 if exc.code in {
            "credential_revoked",
            "foreign_namespace",
            "missing_scopes",
        } else 401
        raise HTTPException(status_code=status, detail=exc.code) from exc


def _workspace(principal: Principal) -> GDWWorkspace:
    return GDWWorkspace(
        namespace=principal.namespace,
        owner_id=principal.owner_id,
    )


def _governance_ready() -> bool:
    try:
        import szl_codename_gate
        import szl_colang_policy

        policy = szl_colang_policy.get_policy()
        return bool(
            policy.loaded
            and policy.enforcement_ready
            and callable(getattr(szl_codename_gate, "scan_text", None))
        )
    except Exception:
        return False


def _policy_bundle_sha256() -> Optional[str]:
    try:
        import szl_colang_policy

        policy = szl_colang_policy.get_policy()
        if not policy.enforcement_ready:
            return None
        return policy.bundle_sha256
    except Exception:
        return None


def _write_readiness(
    namespace: str,
) -> tuple[bool, list[str], int, dict, bool]:
    runtime = runtime_health()
    production = os.environ.get(
        "GDW_PRODUCTION_MODE", ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    blockers = []
    if production:
        storage = runtime.get("storage") or {}
        drain = runtime.get("drain") or {}
        if runtime.get("evidence_label") != "VERIFIED":
            blockers.append("RUNTIME_EVIDENCE_UNVERIFIED")
        if runtime.get("startup_state") != "READY":
            blockers.append("RUNTIME_NOT_READY")
        if storage.get("sqlite_integrity") != "ok":
            blockers.append("SQLITE_INTEGRITY_UNVERIFIED")
        if storage.get("schema_version") != GDWWorkspace.schema_version():
            blockers.append("SCHEMA_VERSION_UNVERIFIED")
        if not re.fullmatch(
            r"[0-9a-f]{32}",
            str(storage.get("database_generation_id") or ""),
        ):
            blockers.append("DATABASE_GENERATION_UNVERIFIED")
        if storage.get("proof_export_mode") != "outbox":
            blockers.append("OUTBOX_MODE_UNVERIFIED")
        if storage.get("journal_mode_observed") != storage.get(
            "journal_mode_requested"
        ):
            blockers.append("JOURNAL_MODE_MISMATCH")
        if storage.get("persistence_required") is not True:
            blockers.append("PERSISTENCE_NOT_REQUIRED")
        if storage.get("mount_verified") is not True:
            blockers.append("PERSISTENT_MOUNT_UNVERIFIED")
        expected_synchronous = {"FULL": 2, "NORMAL": 1}.get(
            storage.get("synchronous_requested")
        )
        if storage.get("synchronous_observed") != expected_synchronous:
            blockers.append("SYNCHRONOUS_MODE_MISMATCH")
        if not drain.get("enabled") or not drain.get("running"):
            blockers.append("OUTBOX_SUPERVISOR_NOT_RUNNING")
        if drain.get("last_outcome") != "SUCCEEDED":
            blockers.append("OUTBOX_SUPERVISOR_NOT_HEALTHY")
        last_report = drain.get("last_report")
        if isinstance(last_report, dict) and (
            last_report.get("failed")
            or last_report.get("pending_effects")
            or last_report.get("dead_letter_effects")
            or last_report.get("legacy_pending_proofs")
            or last_report.get("invalid_effect_bindings")
            or last_report.get("invalid_exported_artifacts")
            or last_report.get("sqlite_integrity") != "ok"
        ):
            blockers.append("OUTBOX_SUPERVISOR_NOT_QUIESCENT")
        if drain.get("success_run_generation_id") != drain.get(
            "run_generation_id"
        ):
            blockers.append("OUTBOX_SUPERVISOR_SUCCESS_STALE")
        if drain.get("success_database_generation_id") != storage.get(
            "database_generation_id"
        ):
            blockers.append("OUTBOX_SUPERVISOR_DATABASE_STALE")
        try:
            success_at = datetime.fromisoformat(
                str(drain.get("last_success_at") or "").replace("Z", "+00:00")
            )
            age = (datetime.now(timezone.utc) - success_at).total_seconds()
            max_age = int(drain.get("max_staleness_seconds") or 0)
            if max_age < 1 or age < 0 or age > max_age:
                raise ValueError
        except (TypeError, ValueError):
            blockers.append("OUTBOX_SUPERVISOR_HEARTBEAT_STALE")
    try:
        credentials = _credential_registry()
        credential_count = credentials.credential_count
    except AuthConfigurationError:
        credential_count = 0
        blockers.append("CREDENTIAL_REGISTRY_UNAVAILABLE")
    governance_ready = _governance_ready()
    if not governance_ready:
        blockers.append("GOVERNANCE_SOURCE_UNREADY")
    try:
        _policy_gateway_origin()
    except RuntimeError:
        blockers.append("CANONICAL_POLICY_GATEWAY_UNCONFIGURED")
    else:
        if not _canonical_policy_ready():
            blockers.append("CANONICAL_POLICY_GATEWAY_UNAVAILABLE")
    return (
        not blockers,
        sorted(set(blockers)),
        credential_count,
        runtime,
        governance_ready,
    )


def _require_write_ready(namespace: str) -> None:
    ready, blockers, _, _, _ = _write_readiness(namespace)
    if not ready:
        raise HTTPException(
            status_code=503,
            detail={
                "reason": "GDW_WRITE_SURFACE_UNAVAILABLE",
                "write_blockers": blockers,
            },
        )


def _require_transient_recovery_runtime(
    namespace: str,
    expected_source_revision: Optional[str],
) -> str:
    expected = str(expected_source_revision or "").strip().lower()
    observed_source = os.environ.get("SZL_GIT_SHA", "").strip().lower()
    if (
        re.fullmatch(r"[0-9a-f]{40}", expected) is None
        or observed_source != expected
    ):
        raise HTTPException(
            status_code=409,
            detail="GDW recovery source revision mismatch",
        )
    runtime = runtime_health()
    storage = runtime.get("storage") or {}
    drain = runtime.get("drain") or {}
    database_generation_id = str(
        storage.get("database_generation_id") or ""
    )
    runtime_ready = (
        runtime.get("startup_state") == "READY"
        and runtime.get("evidence_label") == "VERIFIED"
        and storage.get("persistence_required") is True
        and storage.get("mount_verified") is True
        and storage.get("journal_mode_requested") == "DELETE"
        and storage.get("journal_mode_observed") == "DELETE"
        and storage.get("synchronous_requested") == "FULL"
        and storage.get("synchronous_observed") == 2
        and storage.get("sqlite_integrity") == "ok"
        and storage.get("proof_export_mode") == "outbox"
        and storage.get("schema_version") == GDWWorkspace.schema_version()
        and re.fullmatch(
            r"[0-9a-f]{32}",
            database_generation_id,
        )
        is not None
        and drain.get("enabled") is True
        and drain.get("running") is True
        and _governance_ready()
    )
    try:
        policy_ready = _canonical_policy_ready()
    except Exception:
        policy_ready = False
    if not runtime_ready or not policy_ready:
        raise HTTPException(
            status_code=503,
            detail="GDW recovery runtime contract is unavailable",
        )
    return database_generation_id


def _public_runtime_health(runtime: dict) -> dict:
    storage = runtime.get("storage")
    public_storage = None
    if isinstance(storage, dict):
        public_storage = {
            key: storage.get(key)
            for key in (
                "persistence_required",
                "mount_verified",
                "journal_mode_requested",
                "synchronous_requested",
                "proof_export_mode",
                "journal_mode_observed",
                "synchronous_observed",
                "sqlite_integrity",
                "schema_version",
                "database_generation_id",
            )
            if key in storage
        }
    drain = runtime.get("drain")
    public_drain = None
    if isinstance(drain, dict):
        public_drain = {
            key: drain.get(key)
            for key in (
                "enabled",
                "running",
                "last_outcome",
                "last_attempt_at",
                "last_success_at",
                "last_error",
            )
            if key in drain
        }
        last_report = drain.get("last_report")
        if isinstance(last_report, dict):
            public_report = {
                key: last_report.get(key)
                for key in (
                    "attempted",
                    "exported",
                    "failed",
                    "pending_effects",
                    "claimed_effects",
                    "dead_letter_effects",
                    "legacy_pending_proofs",
                    "sqlite_integrity",
                    "invalid_effect_bindings",
                    "invalid_exported_artifacts",
                )
                if key in last_report
            }
            errors = last_report.get("errors")
            if isinstance(errors, list):
                public_report["errors"] = [
                    value
                    for value in errors
                    if isinstance(value, str)
                    and len(value) <= 96
                    and re.fullmatch(r"[a-z_]+:[A-Za-z_]+", value)
                ]
            public_drain["last_report"] = public_report
    return {
        "startup_state": runtime.get("startup_state"),
        "evidence_label": runtime.get("evidence_label"),
        "storage": public_storage,
        "drain": public_drain,
        "prepared_at": runtime.get("prepared_at"),
        "error": runtime.get("error"),
    }


def _validate_identifiers(payload: GDWStepRequest, request_id: Optional[str]) -> str:
    if not request_id or not _ID_PATTERN.fullmatch(request_id):
        raise HTTPException(
            status_code=422,
            detail="X-Request-Id must be 1-128 canonical identifier characters",
        )
    if not _ID_PATTERN.fullmatch(payload.session_id):
        raise HTTPException(status_code=422, detail="invalid session_id")
    if len(payload.allowed_experts) > 16:
        raise HTTPException(status_code=422, detail="too many allowed_experts")
    return request_id


def _decision(payload: GDWStepRequest) -> str:
    experts = set(payload.allowed_experts)
    if not experts or not experts.issubset(_EXPERTS):
        return "QUARANTINE"
    if payload.risk_budget >= 0.90:
        return "REJECT"
    if payload.risk_budget >= 0.75:
        return "QUARANTINE"
    return "ACCEPT"


_LOOPBACK_POLICY_GATEWAY_ORIGIN = "http://127.0.0.1:7860"


def _policy_gateway_origin() -> str:
    origin = os.environ.get("GDW_POLICY_ORIGIN", "").strip().rstrip("/")
    if (
        origin != _LOOPBACK_POLICY_GATEWAY_ORIGIN
        and not origin.startswith("https://")
    ):
        raise RuntimeError(
            "GDW_POLICY_ORIGIN must be HTTPS or the exact local gateway"
        )
    return origin


def _policy_readiness_timeout() -> float:
    try:
        configured = float(
            os.environ.get("GDW_POLICY_READINESS_TIMEOUT_SECONDS", "3")
        )
    except ValueError:
        configured = 3.0
    return min(10.0, max(0.25, configured))


def _policy_readiness_ttl() -> float:
    try:
        configured = float(
            os.environ.get("GDW_POLICY_READINESS_TTL_SECONDS", "15")
        )
    except ValueError:
        configured = 15.0
    return min(300.0, max(1.0, configured))


def _policy_gateway_json(path: str) -> dict:
    request = UrlRequest(
        _policy_gateway_origin() + path,
        headers={"Accept": "application/json"},
        method="GET",
    )
    with urlopen(request, timeout=_policy_readiness_timeout()) as response:
        if response.status != 200:
            raise RuntimeError("canonical policy readiness returned non-200")
        result = json.loads(response.read().decode("utf-8"))
    if not isinstance(result, dict):
        raise RuntimeError("canonical policy readiness returned non-object JSON")
    return result


def _canonical_policy_ready() -> bool:
    origin = _policy_gateway_origin()
    now = time.monotonic()
    with _POLICY_READINESS_LOCK:
        if (
            _POLICY_READINESS_CACHE["origin"] == origin
            and now - float(_POLICY_READINESS_CACHE["checked_at"])
            <= _policy_readiness_ttl()
        ):
            return bool(_POLICY_READINESS_CACHE["ready"])
        ready = False
        try:
            health = _policy_gateway_json("/api/a11oy/v1/healthz")
            signing = _policy_gateway_json("/api/a11oy/v1/signing-status")
            backend = health.get("backend_health")
            backend_ready = (
                str(health.get("status") or "").lower() in {"ok", "ready"}
                and (
                    not isinstance(backend, dict)
                    or backend.get("alive") is True
                )
            )
            dsse_keyid = str(signing.get("dsse_keyid") or "")
            signer_ready = (
                signing.get("key_persistent") is True
                and re.fullmatch(r"[0-9a-f]{16}", dsse_keyid) is not None
            )
            ready = backend_ready and signer_ready
        except Exception:
            ready = False
        _POLICY_READINESS_CACHE.update(
            {
                "origin": origin,
                "checked_at": time.monotonic(),
                "ready": ready,
            }
        )
        return ready


def _canonical_policy_evaluate(action: dict) -> dict:
    request = UrlRequest(
        _policy_gateway_origin() + "/api/a11oy/v1/policy/evaluate",
        data=json.dumps(
            {"action": action},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        if response.status != 200:
            raise RuntimeError("canonical policy gateway returned non-200")
        result = json.loads(response.read().decode("utf-8"))
    receipt_hash = str(result.get("receipt_hash") or "")
    if (
        result.get("gate") != "ThresholdPolicySeverity"
        or len(receipt_hash) != 64
        or any(ch not in "0123456789abcdef" for ch in receipt_hash)
        or result.get("receipt_signed") is not True
        or result.get("receipts_in_eq_out") is not True
        or result.get("receipt_error")
    ):
        raise RuntimeError("canonical policy response is not verifiable")
    return result


def _transient_recovery_governance(
    *,
    principal: Principal,
    recovery_id: str,
    source_revision: str,
    database_generation_id: str,
    limit: int,
) -> dict:
    """Obtain an explicit signed canonical-policy allow for one recovery call."""

    binding = {
        "schema": "szl.gdw.transient-effect-recovery-authorization/v1",
        "action_type": "gdw.transient-effect-recovery",
        "namespace": principal.namespace,
        "owner_id": principal.owner_id,
        "credential_key_id": principal.key_id,
        "recovery_id": recovery_id,
        "source_revision": source_revision,
        "database_generation_id": database_generation_id,
        "limit": limit,
        "failure_class": "hf-hard-link-enotsup/v1",
    }
    binding_sha256 = _sha(binding)
    action = {
        "actionId": f"gdw-recovery:{binding_sha256}",
        "severity": "high",
        "decisionClass": "ordinary",
        "confidence": 1.0,
        "witnesses": [
            {
                "id": (
                    f"principal:{principal.namespace}:"
                    f"{principal.owner_id}:{principal.key_id}"
                ),
                "role": "operator",
                "attested": True,
            },
            {
                "id": f"workload:szl-holdings/a11oy@{source_revision}",
                "role": "workload",
                "attested": True,
            },
        ],
    }
    result = _canonical_policy_evaluate(action)
    if result.get("decision") != "allow":
        raise PermissionError("canonical policy denied transient recovery")
    return {
        "schema": "szl.gdw.transient-effect-recovery-governance/v1",
        "decision": "ALLOW",
        "binding": binding,
        "binding_sha256": binding_sha256,
        "policy_gateway": {
            "decision": "ALLOW",
            "gate": result["gate"],
            "receipt_hash": result["receipt_hash"],
            "receipt_signed": True,
            "receipts_in_eq_out": True,
            "action_id": action["actionId"],
            "witnesses": action["witnesses"],
        },
    }


def _risk_severity(risk_budget: float) -> str:
    if risk_budget < 0.25:
        return "low"
    if risk_budget < 0.50:
        return "medium"
    if risk_budget < 0.75:
        return "high"
    if risk_budget < 0.90:
        return "critical"
    return "capital"


async def _governance_gate(
    payload_data: dict,
    request_id: str,
    request_digest: str,
    principal: Principal,
    database_generation_id: str,
    state_before_hash: str,
) -> dict:
    action = {
        "tool": "execute",
        "effecting": True,
        "events": ["gate.evaluate"],
        "action_type": "gdw.step",
        "target": payload_data["session_id"],
        "request_id": request_id,
        "request_digest": request_digest,
        "principal": principal.owner_id,
        "namespace": principal.namespace,
        "credential_key_id": principal.key_id,
        "text": payload_data["request"],
        "high_impact": float(payload_data["risk_budget"]) >= 0.75,
        "irreversible": False,
    }
    try:
        import szl_colang_policy

        policy = szl_colang_policy.get_policy()
        if not policy.enforcement_ready:
            raise RuntimeError("exact file-backed Colang policy is not ready")
        colang = policy.evaluate(action)
        if not colang.get("enforcement_ready"):
            raise RuntimeError("Colang policy evaluation failed exact-source checks")
    except Exception as exc:
        return {
            "allowed": False,
            "decision": "DENY",
            "reason_codes": ["DOCTRINE_GATE_UNAVAILABLE"],
            "detail": type(exc).__name__,
            "writer_is_judge": False,
            "enforcement_mode": "LOCAL_PRECONDITIONS_PLUS_CANONICAL_POLICY_GATEWAY",
            "principal": {
                "owner_id": principal.owner_id,
                "namespace": principal.namespace,
                "key_id": principal.key_id,
            },
        }

    try:
        import szl_codename_gate

        serialized = json.dumps(
            payload_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True
        )
        codename_hits = sorted(
            {str(value) for value in szl_codename_gate.scan_text(serialized)}
        )
    except Exception as exc:
        return {
            "allowed": False,
            "decision": "DENY",
            "reason_codes": ["CODENAME_GATE_UNAVAILABLE"],
            "detail": type(exc).__name__,
            "writer_is_judge": False,
            "enforcement_mode": "LOCAL_PRECONDITIONS_PLUS_CANONICAL_POLICY_GATEWAY",
            "principal": {
                "owner_id": principal.owner_id,
                "namespace": principal.namespace,
                "key_id": principal.key_id,
            },
            "colang": {
                "decision": colang.get("decision"),
                "fired_flows": colang.get("fired_flows", []),
                "flows_evaluated": colang.get("flows_evaluated", []),
                "policy_files": colang.get("policy_files", []),
                "bundle_sha256": colang.get("bundle_sha256"),
            },
        }

    reasons = []
    if not colang.get("allow"):
        reasons.append("DOCTRINE_POLICY_DENY")
    if codename_hits:
        reasons.append("CODENAME_POLICY_DENY")
    policy_gateway = None
    if not reasons:
        source_revision = os.environ.get("SZL_GIT_SHA", "").strip()
        if (
            len(source_revision) != 40
            or any(ch not in "0123456789abcdef" for ch in source_revision)
        ):
            reasons.append("RUNTIME_IDENTITY_UNAVAILABLE")
        else:
            binding = {
                "schema": "szl.gdw.authorization-binding/v1",
                "action_type": "gdw.step",
                "database_generation_id": database_generation_id,
                "namespace": principal.namespace,
                "owner_id": principal.owner_id,
                "credential_key_id": principal.key_id,
                "request_id": request_id,
                "request_digest": request_digest,
                "session_id": payload_data["session_id"],
                "state_before_hash": state_before_hash,
            }
            binding_sha256 = _sha(binding)
            gateway_action = {
                "actionId": f"gdw:{binding_sha256}",
                "severity": _risk_severity(float(payload_data["risk_budget"])),
                "decisionClass": "ordinary",
                "confidence": 1.0,
                "witnesses": [
                    {
                        "id": (
                            f"principal:{principal.namespace}:"
                            f"{principal.owner_id}:{principal.key_id}"
                        ),
                        "role": "operator",
                        "attested": True,
                    },
                    {
                        "id": (
                            "workload:szl-holdings/a11oy@"
                            f"{source_revision}"
                        ),
                        "role": "workload",
                        "attested": True,
                    },
                ],
            }
            try:
                result = await asyncio.to_thread(
                    _canonical_policy_evaluate,
                    gateway_action,
                )
                policy_gateway = {
                    "decision": str(result.get("decision") or "").upper(),
                    "gate": result["gate"],
                    "receipt_hash": result["receipt_hash"],
                    "receipt_signed": True,
                    "receipts_in_eq_out": True,
                    "binding_sha256": binding_sha256,
                    "action_id": gateway_action["actionId"],
                    "source_revision": source_revision,
                    "witnesses": gateway_action["witnesses"],
                }
                if result.get("decision") != "allow":
                    reasons.append("CANONICAL_POLICY_DENY")
            except Exception as exc:
                reasons.append("CANONICAL_POLICY_GATEWAY_UNAVAILABLE")
                policy_gateway = {
                    "decision": "UNAVAILABLE",
                    "detail": type(exc).__name__,
                }
    return {
        "allowed": not reasons,
        "decision": "ALLOW" if not reasons else "DENY",
        "reason_codes": reasons or [
            "FILE_BACKED_GOVERNANCE_PASS",
            "CANONICAL_POLICY_GATEWAY_PASS",
        ],
        "writer_is_judge": False,
        "enforcement_mode": "LOCAL_PRECONDITIONS_PLUS_CANONICAL_POLICY_GATEWAY",
        "principal": {
            "owner_id": principal.owner_id,
            "namespace": principal.namespace,
            "key_id": principal.key_id,
        },
        "colang": {
            "decision": colang.get("decision"),
            "fired_flows": colang.get("fired_flows", []),
            "flows_evaluated": colang.get("flows_evaluated", []),
            "policy_files": colang.get("policy_files", []),
            "bundle_sha256": colang.get("bundle_sha256"),
        },
        "codename_gate": {
            "clean": not codename_hits,
            "hits": codename_hits,
        },
        "policy_gateway": policy_gateway,
    }


def _atomic_receipt(
    *,
    proposal_id: str,
    request_id: str,
    request_digest: str,
    session_id: str,
    step: int,
    before_hash: str,
    after_hash: str,
    scheduler_mode: str,
    governance: dict,
    principal: Principal,
    database_generation_id: str,
    timestamp: str,
) -> dict:
    receipt = {
        "schema": "szl.gdw.transaction-receipt/v1",
        "status": "UNSIGNED_ATOMIC",
        "proposal_id": proposal_id,
        "request_id": request_id,
        "request_digest": request_digest,
        "session_id": session_id,
        "owner_id": principal.owner_id,
        "namespace": principal.namespace,
        "database_generation_id": database_generation_id,
        "credential_key_id": principal.key_id,
        "step": step,
        "state_before_hash": before_hash,
        "state_after_hash": after_hash,
        "scheduler_mode": scheduler_mode,
        "governance_evidence_sha256": sha256_json(governance),
        "governance": governance,
        "created_at": timestamp,
    }
    receipt["receipt_hash"] = sha256_json(receipt)
    return receipt


def register(app, ns: str = "a11oy"):
    prefix = f"/api/{ns}/v1/gdw"

    @app.get(prefix + "/healthz")
    @app.get("/v1/gdw/healthz")
    def gdw_healthz():
        (
            write_ready,
            blockers,
            credential_count,
            runtime,
            governance_ready,
        ) = _write_readiness(ns)
        public_runtime = _public_runtime_health(runtime)
        return {
            "service": "gdw-frontier",
            "status": "REAL" if write_ready else "UNAVAILABLE",
            "write_ready": write_ready,
            "credential_count": credential_count,
            "governance_ready": governance_ready,
            "write_blockers": blockers,
            "persistence": public_runtime,
            "benchmark_claim": "UNMEASURED",
        }

    @app.get(prefix + "/bench/meta")
    @app.get("/v1/gdw/bench/meta")
    def gdw_bench_meta(
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        _authorise(
            authorization,
            namespace=ns,
            required_scopes=("bench:read",),
        )
        return {
            "service": "gdw-frontier",
            "implementation_status": "REAL",
            "benchmark_status": "UNMEASURED",
            "recommended_burst": 10000,
            "metrics_path": prefix + "/metrics",
            "notes": [
                "A 10k-request run is harness evidence, not a production guarantee.",
                "Use p95, p99, error rate, receipt integrity, and SQLite integrity.",
            ],
        }

    @app.get(prefix + "/metrics", response_class=PlainTextResponse)
    @app.get("/v1/gdw/metrics", response_class=PlainTextResponse)
    def gdw_metrics(
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        _authorise(
            authorization,
            namespace=ns,
            required_scopes=("metrics:read",),
        )
        return PlainTextResponse(
            _TELEMETRY.render(),
            media_type="text/plain; version=0.0.4; charset=utf-8",
        )

    @app.get(prefix + "/integrity")
    @app.get("/v1/gdw/integrity")
    def gdw_integrity(
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        principal = _authorise(
            authorization,
            namespace=ns,
            required_scopes=("integrity:read",),
        )
        return _workspace(principal).integrity()

    @app.post(prefix + "/drain")
    @app.post("/v1/gdw/drain")
    def gdw_drain(
        limit: int = 100,
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        principal = _authorise(
            authorization,
            namespace=ns,
            required_scopes=("integrity:global",),
        )
        _require_write_ready(ns)
        report = drain_once(limit=limit)
        integrity = _workspace(principal).integrity(global_scope=True)
        return {
            "schema": "szl.gdw.drain-report/v1",
            **report,
            "integrity_ok": integrity["ok"],
            "database_generation_id": integrity["database_generation_id"],
        }

    @app.post(prefix + "/recovery/transient-effects")
    @app.post("/v1/gdw/recovery/transient-effects")
    def gdw_recover_transient_effects(
        limit: int = Query(default=100, ge=1, le=1_000),
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
        expected_source_revision: Optional[str] = Header(
            default=None,
            alias="X-Expected-Source-Revision",
        ),
        idempotency_key: Optional[str] = Header(
            default=None,
            alias="Idempotency-Key",
        ),
    ):
        principal = _authorise(
            authorization,
            namespace=ns,
            required_scopes=("effects:recover", "integrity:global"),
        )
        runtime_generation = _require_transient_recovery_runtime(
            ns,
            expected_source_revision,
        )
        if not idempotency_key or not _ID_PATTERN.fullmatch(idempotency_key):
            raise HTTPException(
                status_code=422,
                detail=(
                    "Idempotency-Key must be 1-128 canonical identifier "
                    "characters"
                ),
            )
        workspace = _workspace(principal)
        if workspace.database_generation_id != runtime_generation:
            raise HTTPException(
                status_code=503,
                detail="GDW recovery database generation changed",
            )
        try:
            governance = _transient_recovery_governance(
                principal=principal,
                recovery_id=idempotency_key,
                source_revision=str(expected_source_revision),
                database_generation_id=runtime_generation,
                limit=limit,
            )
        except PermissionError as exc:
            raise HTTPException(
                status_code=403,
                detail="GDW recovery denied by canonical policy",
            ) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="GDW recovery canonical policy unavailable",
            ) from exc
        try:
            report = workspace.recover_retry_scheduled_effects(
                recovery_id=idempotency_key,
                credential_key_id=principal.key_id,
                expected_source_revision=str(expected_source_revision),
                expected_database_generation_id=runtime_generation,
                governance=governance,
                limit=limit,
            )
        except GDWConfigurationError as exc:
            if str(exc) == "recovery_id was already used with different content":
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency-Key was already used with different content",
                ) from exc
            raise HTTPException(
                status_code=503,
                detail="GDW recovery refused by integrity gate",
            ) from exc
        if report.get("database_generation_id") != runtime_generation:
            raise HTTPException(
                status_code=503,
                detail="GDW recovery database generation changed",
            )
        return report

    @app.get(prefix + "/integrity/global")
    @app.get("/v1/gdw/integrity/global")
    def gdw_global_integrity(
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        principal = _authorise(
            authorization,
            namespace=ns,
            required_scopes=("integrity:global",),
        )
        return _workspace(principal).integrity(global_scope=True)

    @app.get(prefix + "/sessions/{session_id}")
    @app.get("/v1/gdw/sessions/{session_id}")
    def gdw_session(
        session_id: str,
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
    ):
        principal = _authorise(
            authorization,
            namespace=ns,
            required_scopes=("session:read",),
        )
        if not _ID_PATTERN.fullmatch(session_id):
            raise HTTPException(status_code=422, detail="invalid session_id")
        state = _workspace(principal).read_session(session_id)
        if state is None:
            raise HTTPException(status_code=404, detail="session not found")
        return state

    request_body_contract = {
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": _model_schema(GDWStepRequest),
                }
            },
        }
    }

    @app.post(prefix + "/step", openapi_extra=request_body_contract)
    @app.post("/v1/gdw/step", openapi_extra=request_body_contract)
    async def gdw_step(
        request: Request,
        authorization: Optional[str] = Header(default=None, alias="Authorization"),
        x_request_id: Optional[str] = Header(default=None, alias="X-Request-Id"),
    ):
        started = time.perf_counter()
        principal = _authorise(
            authorization,
            namespace=ns,
            required_scopes=("step:write",),
        )
        await asyncio.to_thread(_require_write_ready, ns)
        try:
            raw_payload = await request.json()
        except Exception as exc:
            raise HTTPException(
                status_code=422,
                detail="invalid GDW step request",
            ) from exc
        payload = _validate_step_payload(raw_payload)
        request_id = _validate_identifiers(payload, x_request_id)
        payload_data = _dump_model(payload)
        request_digest = _sha(payload_data)
        selected_mode = "unresolved"
        decision = "ERROR"
        receipt_hash = ""

        workspace = _workspace(principal)
        step_write_locks = _step_write_locks(
            principal.namespace,
            principal.owner_id,
            payload.session_id,
            request_id,
        )
        await _acquire_step_write_locks(step_write_locks)
        try:
            authorised_generation_id = workspace.database_generation_id
            with workspace.transaction() as connection:
                cached = workspace.cached_request(connection, request_id)
                if cached is not None:
                    cached_digest, cached_response = cached
                    if cached_digest != request_digest:
                        raise HTTPException(
                            status_code=409,
                            detail="X-Request-Id was already used with different content",
                        )
                    current_bundle = _policy_bundle_sha256()
                    cached_bundle = (
                        cached_response.get("audit", {})
                        .get("governance", {})
                        .get("colang", {})
                        .get("bundle_sha256")
                    )
                    if not current_bundle or cached_bundle != current_bundle:
                        raise HTTPException(
                            status_code=409,
                            detail="policy snapshot changed; replay refused",
                        )
                    cached_response["replayed"] = True
                    selected_mode = cached_response["scheduler_mode"]
                    decision = cached_response["decision"]
                    receipt_hash = cached_response.get("receipt_hash") or ""
                    _TELEMETRY.observe(
                        (time.perf_counter() - started) * 1000.0,
                        decision,
                        selected_mode,
                        False,
                    )
                    return cached_response
                authorised_previous = workspace.session_state(
                    connection,
                    payload.session_id,
                )
                if authorised_previous is None:
                    authorised_state_hash = _sha(
                        {
                            "namespace": principal.namespace,
                            "owner_id": principal.owner_id,
                            "session_id": payload.session_id,
                            "step": 0,
                            "state": "GENESIS",
                        }
                    )
                else:
                    authorised_state_hash = authorised_previous["state_hash"]
            precondition_decision = _decision(payload)
            governance = await _governance_gate(
                payload_data,
                request_id,
                request_digest,
                principal,
                authorised_generation_id,
                authorised_state_hash,
            )
            with workspace.transaction() as connection:
                cached = workspace.cached_request(connection, request_id)
                if cached is not None:
                    cached_digest, cached_response = cached
                    if cached_digest != request_digest:
                        raise HTTPException(
                            status_code=409,
                            detail="X-Request-Id was already used with different content",
                        )
                    current_bundle = _policy_bundle_sha256()
                    cached_bundle = (
                        cached_response.get("audit", {})
                        .get("governance", {})
                        .get("colang", {})
                        .get("bundle_sha256")
                    )
                    if not current_bundle or cached_bundle != current_bundle:
                        raise HTTPException(
                            status_code=409,
                            detail="policy snapshot changed; replay refused",
                        )
                    cached_response["replayed"] = True
                    selected_mode = cached_response["scheduler_mode"]
                    decision = cached_response["decision"]
                    receipt_hash = cached_response.get("receipt_hash") or ""
                    _TELEMETRY.observe(
                        (time.perf_counter() - started) * 1000.0,
                        decision,
                        selected_mode,
                        False,
                    )
                    return cached_response
                previous = workspace.session_state(connection, payload.session_id)
                if previous is None:
                    before_step = 0
                    before_hash = _sha(
                        {
                            "namespace": principal.namespace,
                            "owner_id": principal.owner_id,
                            "session_id": payload.session_id,
                            "step": 0,
                            "state": "GENESIS",
                        }
                    )
                else:
                    before_step = previous["step"]
                    before_hash = previous["state_hash"]
                if (
                    workspace.database_generation_id
                    != authorised_generation_id
                    or before_hash != authorised_state_hash
                ):
                    raise HTTPException(
                        status_code=409,
                        detail="state changed after governance authorization",
                    )

                features = AttentionFeatures(
                    novelty=payload.novelty
                    if payload.novelty is not None
                    else min(1.0, len(payload.request) / 1024.0),
                    disagreement=payload.disagreement
                    if payload.disagreement is not None
                    else min(1.0, max(0, len(set(payload.allowed_experts)) - 1) / 5.0),
                    risk=payload.risk_budget,
                    context_tokens=payload.context_tokens
                    or max(1, len(payload.request) // 4),
                    active_tool_count=payload.active_tool_count,
                    memory_pressure=payload.memory_pressure or 0.0,
                )
                routing = choose_attention_mode(features, payload.mode_hint)
                selected_mode = routing["mode"]
                decision = precondition_decision
                if decision == "ACCEPT" and not governance["allowed"]:
                    decision = "REJECT"
                mutates = decision == "ACCEPT" and not payload.dry_run
                step = before_step + 1 if mutates else before_step
                database_generation_id = workspace.database_generation_id
                proposal_id = sha256_json(
                    {
                        "schema": "szl.gdw.proposal-identity/v1",
                        "database_generation_id": database_generation_id,
                        "namespace": principal.namespace,
                        "owner_id": principal.owner_id,
                        "request_id": request_id,
                        "request_digest": request_digest,
                        "state_before_hash": before_hash,
                        "governance_evidence_sha256": sha256_json(governance),
                    }
                )
                timestamp = _now()

                if mutates:
                    state = {
                        "namespace": principal.namespace,
                        "owner_id": principal.owner_id,
                        "session_id": payload.session_id,
                        "database_generation_id": database_generation_id,
                        "step": step,
                        "previous_state_hash": before_hash,
                        "request_digest": request_digest,
                        "scheduler_mode": selected_mode,
                        "allowed_experts": sorted(set(payload.allowed_experts)),
                    }
                    after_hash = _sha(state)
                    workspace.save_state(
                        connection,
                        payload.session_id,
                        step,
                        state,
                        after_hash,
                        timestamp,
                    )
                    receipt = _atomic_receipt(
                        proposal_id=proposal_id,
                        request_id=request_id,
                        request_digest=request_digest,
                        session_id=payload.session_id,
                        step=step,
                        before_hash=before_hash,
                        after_hash=after_hash,
                        scheduler_mode=selected_mode,
                        governance=governance,
                        principal=principal,
                        database_generation_id=database_generation_id,
                        timestamp=timestamp,
                    )
                    receipt_hash = receipt["receipt_hash"]
                else:
                    state = previous["state"] if previous else {"state": "GENESIS"}
                    after_hash = before_hash
                    receipt = None

                proof_payload = build_proof_payload(
                    proposal_id=proposal_id,
                    request_id=request_id,
                    request_digest=request_digest,
                    namespace=principal.namespace,
                    owner_id=principal.owner_id,
                    database_generation_id=database_generation_id,
                    step=step,
                    before_hash=before_hash,
                    after_hash=after_hash,
                    decision=decision,
                    scheduler_mode=selected_mode,
                    receipt_hash=receipt_hash,
                    dry_run=payload.dry_run,
                    governance=governance,
                )
                proof_mode = os.environ.get(
                    "GDW_PROOF_EXPORT_MODE", "outbox"
                ).strip().lower()
                if proof_mode != "outbox":
                    raise ValueError(
                        "GDW_PROOF_EXPORT_MODE must be 'outbox'; "
                        "synchronous external effects are not transaction-safe"
                    )
                proof_artifact = {
                    "status": "OUTBOX_PENDING",
                    "kind": "proof_export",
                    "idempotency_key": workspace.scoped_effect_key(
                        principal.namespace,
                        principal.owner_id,
                        request_id,
                        "proof_export",
                        proof_payload["payload_sha256"],
                    ),
                    "payload_sha256": proof_payload["payload_sha256"],
                    "formal_status": "NOT_RUN",
                }
                plan = build_plan(
                    tasks=("governance", "attention_route", "state_transition", "verify"),
                    meta={"proposal_id": proposal_id},
                )
                response = {
                    "service": "gdw-frontier",
                    "implementation_status": "REAL",
                    "benchmark_status": "UNMEASURED",
                    "proposal_id": proposal_id,
                    "request_id": request_id,
                    "request_digest": request_digest,
                    "database_generation_id": database_generation_id,
                    "session_id": payload.session_id,
                    "principal": {
                        "owner_id": principal.owner_id,
                        "namespace": principal.namespace,
                        "key_id": principal.key_id,
                    },
                    "decision": decision,
                    "step": step,
                    "state_hash": after_hash,
                    "state_before_hash": before_hash,
                    "receipt_hash": receipt_hash or None,
                    "receipt_status": receipt.get("status") if receipt else None,
                    "scheduler_mode": selected_mode,
                    "routing": routing,
                    "kernel_execution": "NOT_EXECUTED_BY_CONTROL_API",
                    "dry_run": payload.dry_run,
                    "replayed": False,
                    "audit": {
                        "governance": governance,
                        "precondition_decision": precondition_decision,
                        "allowed_experts": sorted(set(payload.allowed_experts)),
                        "plan_version": plan["plan_version"],
                        "receipt_substrate": "gdw.sqlite.atomic/v1"
                        if receipt is not None
                        else None,
                        "proof_export_mode": proof_mode,
                    },
                    "proof": proof_artifact,
                }
                response_hash = _sha(response)
                workspace.save_request(
                    connection,
                    request_id,
                    request_digest,
                    payload.session_id,
                    response,
                    response_hash,
                    timestamp,
                )
                if receipt is not None:
                    receipt_payload_sha256 = sha256_json(receipt)
                    workspace.save_receipt(
                        connection,
                        receipt_hash,
                        request_id,
                        payload.session_id,
                        step,
                        receipt,
                        timestamp,
                    )
                    workspace.save_effect_outbox(
                        connection,
                        request_id,
                        "receipt_projection",
                        receipt,
                        receipt_payload_sha256,
                        workspace.scoped_effect_key(
                            principal.namespace,
                            principal.owner_id,
                            request_id,
                            "receipt_projection",
                            receipt_payload_sha256,
                        ),
                        timestamp,
                    )
                workspace.save_effect_outbox(
                    connection,
                    request_id,
                    "proof_export",
                    proof_payload,
                    proof_payload["payload_sha256"],
                    workspace.scoped_effect_key(
                        principal.namespace,
                        principal.owner_id,
                        request_id,
                        "proof_export",
                        proof_payload["payload_sha256"],
                    ),
                    timestamp,
                )

            _TELEMETRY.observe(
                (time.perf_counter() - started) * 1000.0,
                decision,
                selected_mode,
                bool(receipt_hash),
            )
            return response
        except HTTPException:
            raise
        except GDWQuotaExceeded as exc:
            # Name the saturated ceiling and advertise a backoff. The code is
            # a policy identifier (for example OWNER_SESSIONS_QUOTA), never
            # credential or payload material, and naming it is what lets a
            # caller distinguish "retry shortly" from a contract violation.
            code = str(getattr(exc, "code", "") or "UNSPECIFIED_QUOTA")
            raise HTTPException(
                status_code=429,
                detail=f"GDW quota exceeded: {code}",
                headers={"Retry-After": "5"},
            ) from exc
        except GDWLifecycleError as exc:
            raise HTTPException(
                status_code=409,
                detail="GDW object is outside its active lifecycle",
            ) from exc
        except GDWConfigurationError as exc:
            raise HTTPException(
                status_code=503,
                detail="GDW durable workspace is unavailable",
            ) from exc
        except Exception as exc:
            _TELEMETRY.observe(
                (time.perf_counter() - started) * 1000.0,
                "ERROR",
                selected_mode,
                False,
                error=True,
            )
            raise HTTPException(
                status_code=500,
                detail=f"GDW transition failed closed: {type(exc).__name__}",
            ) from exc
        finally:
            for lock in reversed(step_write_locks):
                lock.release()

    return {
        "ok": True,
        "state": "REAL",
        "routes": [
            prefix + "/healthz",
            prefix + "/bench/meta",
            prefix + "/metrics",
            prefix + "/integrity",
            prefix + "/integrity/global",
            prefix + "/drain",
            prefix + "/recovery/transient-effects",
            prefix + "/sessions/{session_id}",
            prefix + "/step",
        ],
    }
