# SPDX-License-Identifier: Apache-2.0
"""Truthful compute-pool/v1 projection over the existing fabric probe.

This is a contract surface for the Python/Hugging Face application.  It does not
claim to be, or replace, the separate Replit TypeScript control plane.  The
legacy pool remains available; this projection adds an explicit monotone state
machine and will only emit ``ready=true`` for a currently reachable node backed
by a fresh, bounded, Cosign-key-verified inference receipt.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, FrozenSet, List, Optional, Tuple

import anyio
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec

import szl_backend_hardening
import szl_dsse


SCHEMA_VERSION = "szl.compute-pool/v1"
RECEIPT_SCHEMA = "szl.compute-pool.inference-receipt/v1"
RECEIPT_PAYLOAD_TYPE = "application/vnd.szl.compute-pool.inference-receipt+json"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_MAX_RECEIPTS = 128
_MAX_RECEIPT_BYTES = 256 * 1024
_POOL_KEY_ID = "a11oy-pool-attester-v1"
_RECEIPT_FUTURE_SKEW_S = 30
_TRUST_ROOTS_ENV = "A11OY_POOL_RECEIPT_TRUST_ROOTS"
_EXTRA_KEY_ID = re.compile(r"^a11oy-pool-attester-[a-z0-9-]{1,48}-v[0-9]+$")
_MAX_EXTRA_TRUST_ROOTS = 8
_MAX_BOUND_NODES = 16
_POOL_ISSUER = "a11oy-pool-attester"
_POOL_AUDIENCE = "a11oy-compute-pool"
_POOL_PREDICATE = "szl.compute-pool.inference-qualification/v1"
_POOL_MEASUREMENT_CONTRACT = "szl.compute-pool.measurement-contract/v1"


class PoolState(str, Enum):
    DECLARED = "DECLARED"
    CONFIGURED = "CONFIGURED"
    REACHABLE = "REACHABLE"
    DISCOVERED = "DISCOVERED"
    QUALIFIED = "QUALIFIED"
    SERVING = "SERVING"


class EvidenceClass(str, Enum):
    MEASURED = "MEASURED"
    REPORTED = "REPORTED"
    UNKNOWN = "UNKNOWN"
    UNAVAILABLE = "UNAVAILABLE"


class Evidence(BaseModel):
    value: Optional[Any]
    evidence_class: EvidenceClass
    observed_at: Optional[str] = None

    class Config:
        extra = "forbid"


class ReceiptSummary(BaseModel):
    evidence_class: EvidenceClass
    verified: bool
    fresh: bool
    bounded: bool
    observed_at: Optional[str] = None
    model_id: Optional[str] = None
    model_digest_sha256: Optional[str] = None
    receipt_sha256: Optional[str] = None
    reason: Optional[str] = None

    class Config:
        extra = "forbid"


class PoolNode(BaseModel):
    node_id: str
    kind: Optional[str]
    sovereign: bool
    endpoint_label: Optional[str]
    state: PoolState
    ready: bool
    evidence_class: EvidenceClass
    configuration: Evidence
    reachability: Evidence
    inference_receipt: ReceiptSummary

    class Config:
        extra = "forbid"


class PoolCounts(BaseModel):
    declared: int
    configured: int
    reachable: int
    discovered: int
    qualified: int
    serving: int
    ready: int


class ComputePoolResponse(BaseModel):
    schema_version: str
    generated_at: str
    source_surface: str
    control_plane_relation: str
    receipt_freshness_seconds: int
    counts: PoolCounts
    nodes: List[PoolNode]

    class Config:
        extra = "forbid"


_HOSTED_AUTH_ENV: Dict[str, tuple[str, ...]] = {
    "groq": ("GROQ_API_KEY",),
    "nvidia-nim": ("NVIDIA_API_KEY", "NGC_API_KEY"),
    "hf-router": ("HF_TOKEN", "HUGGINGFACEHUB_API_TOKEN"),
}


def _iso(value: object) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return None
        return parsed.astimezone(timezone.utc)
    except ValueError:
        return None


def _freshness_seconds() -> int:
    try:
        value = int(os.environ.get("A11OY_POOL_RECEIPT_MAX_AGE_S", "300"))
    except ValueError:
        value = 300
    return max(30, min(3600, value))


def _configured(node: Dict[str, Any]) -> Evidence:
    node_id = str(node.get("name") or "")
    if node_id in _HOSTED_AUTH_ENV:
        present = any(bool((os.environ.get(name) or "").strip()) for name in _HOSTED_AUTH_ENV[node_id])
        return Evidence(
            value=present,
            evidence_class=EvidenceClass.MEASURED if present else EvidenceClass.UNAVAILABLE,
        )
    # Local/self-hosted endpoints are registry configuration, not proof of service.
    configured = bool(node.get("endpoint")) or bool(node.get("static_reachable"))
    return Evidence(value=configured, evidence_class=EvidenceClass.REPORTED)


def _is_reparse(info: os.stat_result) -> bool:
    return bool(
        getattr(info, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _confined(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath((str(path.resolve(strict=True)), str(root))) == str(root)
    except (OSError, ValueError):
        return False


def _read_regular_file(path: Path, root: Path) -> Optional[bytes]:
    try:
        if not _confined(path, root):
            return None
        before = os.lstat(path)
        if stat.S_ISLNK(before.st_mode) or _is_reparse(before) or not stat.S_ISREG(before.st_mode):
            return None
        if before.st_size <= 0 or before.st_size > _MAX_RECEIPT_BYTES:
            return None
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(path, flags)
        try:
            opened = os.fstat(fd)
            if not stat.S_ISREG(opened.st_mode) or opened.st_size != before.st_size:
                return None
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                return None
            data = os.read(fd, _MAX_RECEIPT_BYTES + 1)
            after = os.fstat(fd)
            if len(data) != before.st_size or len(data) > _MAX_RECEIPT_BYTES:
                return None
            if (opened.st_dev, opened.st_ino, opened.st_mtime_ns, opened.st_size) != (
                after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size
            ):
                return None
            return data
        finally:
            os.close(fd)
    except (OSError, ValueError):
        return None


def _valid_receipt_payload(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    exact = {
        "schema_version", "node_id", "model_id", "model_digest_sha256",
        "observed_at", "request_sha256", "response_sha256", "duration_ms",
        "success", "serving", "bounds",
        "issuer", "audience", "predicate_type", "measurement_contract",
    }
    if set(payload) != exact:
        return False
    bounds = payload.get("bounds")
    if not isinstance(bounds, dict) or set(bounds) != {
        "timeout_ms", "max_input_tokens", "max_output_tokens"
    }:
        return False
    integers = [bounds.get("timeout_ms"), bounds.get("max_input_tokens"), bounds.get("max_output_tokens")]
    return bool(
        payload.get("schema_version") == RECEIPT_SCHEMA
        and payload.get("issuer") == _POOL_ISSUER
        and payload.get("audience") == _POOL_AUDIENCE
        and payload.get("predicate_type") == _POOL_PREDICATE
        and payload.get("measurement_contract") == _POOL_MEASUREMENT_CONTRACT
        and isinstance(payload.get("node_id"), str) and 0 < len(payload["node_id"].strip()) <= 128
        and isinstance(payload.get("model_id"), str) and 0 < len(payload["model_id"].strip()) <= 256
        and _HEX64.fullmatch(str(payload.get("model_digest_sha256") or ""))
        and _HEX64.fullmatch(str(payload.get("request_sha256") or ""))
        and _HEX64.fullmatch(str(payload.get("response_sha256") or ""))
        and _iso(payload.get("observed_at"))
        and isinstance(payload.get("duration_ms"), (int, float))
        and not isinstance(payload.get("duration_ms"), bool)
        and 0 <= float(payload["duration_ms"]) <= 3_600_000
        and isinstance(payload.get("success"), bool)
        and isinstance(payload.get("serving"), bool)
        and all(isinstance(v, int) and not isinstance(v, bool) and 0 < v <= 1_000_000 for v in integers)
    )


def _load_pinned_key(raw: str, expected: str) -> Optional[Any]:
    if not raw or not _HEX64.fullmatch(expected):
        return None
    try:
        if "BEGIN" not in raw:
            raw = base64.b64decode(raw, validate=True).decode("utf-8")
        public_key = serialization.load_pem_public_key(raw.encode("utf-8"))
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            return None
        der = public_key.public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        if hashlib.sha256(der).hexdigest() != expected:
            return None
        return public_key
    except (ValueError, TypeError, UnicodeDecodeError):
        return None


def _pool_verifier() -> Optional[Any]:
    """Load the dedicated pool-attester key and verify its explicit pin.

    The estate-wide receipt key is intentionally not accepted here: a pool
    qualification receipt can change routing eligibility and therefore has a
    narrower trust root.  Missing or malformed configuration fails closed.
    """
    return _load_pinned_key(
        (os.environ.get("A11OY_POOL_RECEIPT_PUBLIC_KEY_PEM") or "").strip(),
        (os.environ.get("A11OY_POOL_RECEIPT_PUBLIC_KEY_SHA256") or "").strip().lower(),
    )


_TrustRoots = Dict[str, Tuple[Any, Optional[FrozenSet[str]]]]


def _extra_trust_roots(raw: str) -> Optional[_TrustRoots]:
    try:
        entries = json.loads(raw)
    except (ValueError, RecursionError):
        return None
    if not isinstance(entries, list) or not 0 < len(entries) <= _MAX_EXTRA_TRUST_ROOTS:
        return None
    roots: _TrustRoots = {}
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {"keyid", "public_key_pem", "sha256", "node_ids"}:
            return None
        keyid, pem, pin, node_ids = entry["keyid"], entry["public_key_pem"], entry["sha256"], entry["node_ids"]
        if not isinstance(keyid, str) or not _EXTRA_KEY_ID.fullmatch(keyid) or keyid == _POOL_KEY_ID or keyid in roots:
            return None
        if not isinstance(pem, str) or not isinstance(pin, str):
            return None
        if not isinstance(node_ids, list) or not 0 < len(node_ids) <= _MAX_BOUND_NODES:
            return None
        if any(not isinstance(n, str) or not n or n != n.strip() or len(n) > 128 for n in node_ids):
            return None
        if len(set(node_ids)) != len(node_ids):
            return None
        public_key = _load_pinned_key(pem.strip(), pin.strip().lower())
        if public_key is None or not isinstance(public_key.curve, ec.SECP256R1):
            return None
        roots[keyid] = (public_key, frozenset(node_ids))
    return roots


def _pool_trust_roots() -> Optional[_TrustRoots]:
    """Resolve keyid -> (public key, node_ids it may attest, or None for any).

    With A11OY_POOL_RECEIPT_TRUST_ROOTS unset this is exactly the single
    legacy key, unbound.  Once the map is set, any defect in it or in a
    configured legacy key refuses every receipt, so a typo can never fall
    back to the unbound root.
    """
    legacy_configured = any(
        (os.environ.get(name) or "").strip()
        for name in ("A11OY_POOL_RECEIPT_PUBLIC_KEY_PEM", "A11OY_POOL_RECEIPT_PUBLIC_KEY_SHA256")
    )
    legacy = _pool_verifier()
    raw = (os.environ.get(_TRUST_ROOTS_ENV) or "").strip()
    if not raw:
        return {_POOL_KEY_ID: (legacy, None)} if legacy is not None else None
    if legacy_configured and legacy is None:
        return None
    roots = _extra_trust_roots(raw)
    if roots is None:
        return None
    if legacy is not None:
        roots[_POOL_KEY_ID] = (legacy, None)
    spki = {
        key.public_bytes(serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
        for key, _ in roots.values()
    }
    return roots if len(spki) == len(roots) else None


def _verify_pool_envelope(envelope: object, roots: _TrustRoots) -> Optional[Dict[str, Any]]:
    if not isinstance(envelope, dict) or envelope.get("payloadType") != RECEIPT_PAYLOAD_TYPE:
        return None
    payload_b64 = envelope.get("payload")
    signatures = envelope.get("signatures")
    if not isinstance(payload_b64, str) or not isinstance(signatures, list):
        return None
    try:
        body = base64.b64decode(payload_b64, validate=True)
    except (ValueError, TypeError):
        return None
    # The signature's own keyid picks the one key it is checked against, so a
    # node-bound key can never be presented under the unbound legacy keyid.
    verified = False
    bound: Optional[FrozenSet[str]] = None
    for signature in signatures:
        keyid = signature.get("keyid") if isinstance(signature, dict) else None
        if not isinstance(keyid, str) or keyid not in roots:
            continue
        public_key, node_ids = roots[keyid]
        try:
            encoded = signature.get("sig")
            if not isinstance(encoded, str):
                continue
            public_key.verify(
                base64.b64decode(encoded, validate=True),
                szl_dsse.pae(RECEIPT_PAYLOAD_TYPE, body),
                ec.ECDSA(hashes.SHA256()),
            )
            verified = True
            bound = node_ids
            break
        except (InvalidSignature, ValueError, TypeError):
            continue
    if not verified:
        return None
    try:
        payload = json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not _valid_receipt_payload(payload):
        return None
    if bound is not None and payload["node_id"] not in bound:
        return None
    return payload


def _verified_receipts(now: datetime) -> Dict[str, Dict[str, Any]]:
    roots = _pool_trust_roots()
    if roots is None:
        return {}
    configured = (os.environ.get("A11OY_COMPUTE_POOL_RECEIPT_DIR") or "").strip()
    if not configured:
        return {}
    root = Path(configured)
    try:
        root_stat = os.lstat(root)
        if stat.S_ISLNK(root_stat.st_mode) or _is_reparse(root_stat) or not stat.S_ISDIR(root_stat.st_mode):
            return {}
        resolved_root = root.resolve(strict=True)
        candidates = sorted(resolved_root.glob("*.dsse.json"), key=lambda item: item.name)[:_MAX_RECEIPTS]
    except OSError:
        return {}

    accepted: Dict[str, Dict[str, Any]] = {}
    # A future-dated receipt must never outrank a current one for the same
    # node; it is kept only as a last resort so the node still reports
    # DISCOVERED with the stale-or-future-dated reason.
    future_only: Dict[str, Dict[str, Any]] = {}
    for candidate in candidates:
        raw = _read_regular_file(candidate, resolved_root)
        if raw is None:
            continue
        try:
            envelope = json.loads(raw)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
        payload = _verify_pool_envelope(envelope, roots)
        if payload is None:
            continue
        record = dict(payload)
        record["receipt_sha256"] = hashlib.sha256(raw).hexdigest()
        node_id = record["node_id"]
        observed = _iso(record["observed_at"])
        if observed is None:
            continue
        future = (observed - now).total_seconds() > _RECEIPT_FUTURE_SKEW_S
        bucket = future_only if future else accepted
        prior = bucket.get(node_id)
        rank = (observed, record["receipt_sha256"])
        prior_rank = (
            _iso(prior["observed_at"]), prior["receipt_sha256"]
        ) if prior else None
        if prior is None or (prior_rank is not None and rank > prior_rank):
            bucket[node_id] = record
    for node_id, record in future_only.items():
        accepted.setdefault(node_id, record)
    return accepted


def _receipt_summary(receipt: Optional[Dict[str, Any]], now: datetime, max_age_s: int) -> ReceiptSummary:
    if not receipt:
        return ReceiptSummary(
            evidence_class=EvidenceClass.UNAVAILABLE,
            verified=False,
            fresh=False,
            bounded=False,
            reason="no cryptographically verified bounded inference receipt",
        )
    observed = _iso(receipt["observed_at"])
    age = (now - observed).total_seconds() if observed else float("inf")
    fresh = -_RECEIPT_FUTURE_SKEW_S <= age <= max_age_s
    return ReceiptSummary(
        evidence_class=EvidenceClass.MEASURED,
        verified=True,
        fresh=fresh,
        bounded=True,
        observed_at=receipt["observed_at"],
        model_id=receipt["model_id"],
        model_digest_sha256=receipt["model_digest_sha256"],
        receipt_sha256=receipt["receipt_sha256"],
        reason=None if fresh else "verified receipt is stale or future-dated",
    )


def build_compute_pool_contract(pool: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
    pool = pool if pool is not None else szl_backend_hardening.probe_fabric_pool()
    generated = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    max_age = _freshness_seconds()
    receipts = _verified_receipts(generated)
    nodes: List[PoolNode] = []
    seen_node_ids: set[str] = set()

    for raw in pool.get("nodes", []) if isinstance(pool, dict) else []:
        if not isinstance(raw, dict):
            continue
        node_id = str(raw.get("name") or "")
        if not node_id.strip() or len(node_id) > 128 or node_id in seen_node_ids:
            continue
        seen_node_ids.add(node_id)
        configuration = _configured(raw)
        observed_at = pool.get("cached_at") if isinstance(pool, dict) else None
        reachable_value = raw.get("reachable") if isinstance(raw.get("reachable"), bool) else None
        reachability = Evidence(
            value=reachable_value,
            evidence_class=EvidenceClass.MEASURED if reachable_value is not None else EvidenceClass.UNKNOWN,
            observed_at=observed_at if isinstance(observed_at, str) else None,
        )
        receipt = receipts.get(node_id)
        receipt_summary = _receipt_summary(receipt, generated, max_age)

        state = PoolState.DECLARED
        if configuration.value is True:
            state = PoolState.CONFIGURED
            if reachable_value is True:
                state = PoolState.REACHABLE
                if receipt_summary.verified:
                    state = PoolState.DISCOVERED
                    if receipt_summary.fresh and receipt and receipt.get("success") is True:
                        state = PoolState.QUALIFIED
                        if receipt.get("serving") is True:
                            state = PoolState.SERVING
        # QUALIFIED and SERVING are both fresh bounded inference states. SERVING
        # additionally proves that the receipt was captured on the serving path.
        ready = state in {PoolState.QUALIFIED, PoolState.SERVING}
        evidence_class = (
            EvidenceClass.MEASURED
            if state in {PoolState.REACHABLE, PoolState.DISCOVERED, PoolState.QUALIFIED, PoolState.SERVING}
            else configuration.evidence_class
        )
        nodes.append(PoolNode(
            node_id=node_id,
            kind=raw.get("kind"),
            sovereign=bool(raw.get("sovereign")),
            endpoint_label=raw.get("endpoint"),
            state=state,
            ready=ready,
            evidence_class=evidence_class,
            configuration=configuration,
            reachability=reachability,
            inference_receipt=receipt_summary,
        ))

    order = list(PoolState)
    counts = {state.value.lower(): sum(order.index(node.state) >= order.index(state) for node in nodes) for state in order}
    counts["ready"] = sum(node.ready for node in nodes)
    payload = ComputePoolResponse(
        schema_version=SCHEMA_VERSION,
        generated_at=generated.isoformat().replace("+00:00", "Z"),
        source_surface="szl_backend_hardening.probe_fabric_pool",
        control_plane_relation="PYTHON_HF_PROJECTION_NOT_REPLIT_CONTROL_PLANE",
        receipt_freshness_seconds=max_age,
        counts=PoolCounts(**counts),
        nodes=nodes,
    )
    return json.loads(payload.json())


def register(app: Any, ns: str = "a11oy") -> List[str]:
    route = f"/api/{ns}/v1/compute-pool/v1"
    existing = {getattr(item, "path", None) for item in app.router.routes}
    if route in existing:
        return []

    # The shared FastAPI sync-handler pool is also used by /healthz and other
    # routes. Bound compute-pool probes separately so a cache-expiry burst cannot
    # exhaust the shared pool and starve independent synchronous health reads.
    pool_probe_limiter = anyio.CapacityLimiter(2)

    @app.get(route, response_model=ComputePoolResponse)
    async def compute_pool_v1():
        payload = await anyio.to_thread.run_sync(
            build_compute_pool_contract, limiter=pool_probe_limiter
        )
        return JSONResponse(payload, headers={"Cache-Control": "no-store"})

    return [route]


__all__ = [
    "ComputePoolResponse", "EvidenceClass", "PoolState", "RECEIPT_PAYLOAD_TYPE",
    "RECEIPT_SCHEMA", "SCHEMA_VERSION", "build_compute_pool_contract", "register",
]
