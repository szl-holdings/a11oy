#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only Frontier Now projection over the existing Series-A service.

This module is intentionally not a second control authority. It owns no provider
credential, database, signer, receipt chain, scheduler, or effector. Every GET and
HEAD is a bounded projection of ``app.state.szl_series_a_service``. Missing or
stale evidence remains visible as UNAVAILABLE/STALE and public claims stay held
until an exact source-to-runtime binding is observed elsewhere.
"""

import hashlib
import os
import json
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus
from urllib.request import Request as URLRequest, urlopen

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

SCHEMA_SUMMARY = "szl.frontier-now-summary/v1"
SCHEMA_INVENTORY = "szl.frontier-now-inventory/v1"
OPERATING_MODE = "OBSERVE_ONLY"
MAX_INVENTORY_LIMIT = 50
PROVIDERS = {"all", "github", "huggingface", "runtime", "web"}
PLATFORM_ORGANIZATION_GITHUB = "szl-holdings"
PLATFORM_ORGANIZATION_GITHUB_REPO = "a11oy"
PLATFORM_ORGANIZATION_HUGGINGFACE = "SZLHOLDINGS"
PLATFORM_CANONICAL_SPACE = f"{PLATFORM_ORGANIZATION_HUGGINGFACE}/a11oy"
PLATFORM_DOMAINS = ("a-11-oy.com", "a11oy.net")
PROBE_TIMEOUT_SECONDS = 1.25
PROBE_CACHE_TTL_SECONDS = 180.0
_PLATFORM_PROBE_CACHE: dict[str, dict[str, Any]] = {}
NO_STORE_HEADERS = {
    "cache-control": "no-store",
    "x-content-type-options": "nosniff",
    "referrer-policy": "no-referrer",
}
PAGE_HEADERS = {
    **NO_STORE_HEADERS,
    "content-security-policy": (
        "default-src 'none'; script-src 'self'; script-src-attr 'none'; "
        "style-src 'self'; style-src-attr 'none'; connect-src 'self'; "
        "img-src 'self' data:; font-src 'self'; object-src 'none'; "
        "base-uri 'none'; form-action 'none'; frame-ancestors 'self' "
        "https://huggingface.co https://*.hf.space https://*.huggingface.co"
    ),
    "permissions-policy": (
        "camera=(), microphone=(), geolocation=(), payment=(), usb=(), "
        "accelerometer=(), gyroscope=()"
    ),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _safe_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _manifest_digest(value: Mapping[str, Any]) -> str:
    payload = json.dumps(
        dict(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _service(app: FastAPI) -> Any:
    return getattr(app.state, "szl_series_a_service", None)


def _snapshot(
    service: Any,
    *,
    include_receipts: bool = True,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    list[dict[str, Any]],
    str | None,
    str,
]:
    if service is None:
        return (
            {
                "state": "UNAVAILABLE",
                "terminal": True,
                "detail": "Series-A estate observer is not registered",
            },
            {},
            [],
            None,
            "UNAVAILABLE",
        )
    try:
        for _ in range(2):
            status = _safe_mapping(service.latest_status())
            latest = service.store.latest_snapshot()
            digest = (
                str(latest.get("digest"))
                if isinstance(latest, Mapping) and latest.get("digest")
                else None
            )
            status_digest = status.get("manifest_digest")
            if (digest is None and not status_digest) or status_digest == digest:
                manifest = (
                    _safe_mapping(latest.get("manifest"))
                    if isinstance(latest, Mapping)
                    else {}
                )
                if digest is not None and _manifest_digest(manifest) != digest:
                    return (
                        {
                            "state": "UNAVAILABLE",
                            "terminal": True,
                            "detail": "Persisted estate manifest digest mismatch",
                            "reason": "MANIFEST_DIGEST_MISMATCH",
                        },
                        {},
                        [],
                        None,
                        "UNAVAILABLE",
                    )
                receipts: list[dict[str, Any]] = []
                proof_state = "NOT_REQUESTED"
                if include_receipts:
                    try:
                        receipt_values = service.store.list_receipts(8)
                        receipts = [
                            dict(item)
                            for item in receipt_values
                            if isinstance(item, Mapping)
                        ]
                        proof_state = "OBSERVED"
                    except Exception:
                        proof_state = "UNAVAILABLE"
                return (
                    status,
                    manifest,
                    receipts,
                    digest,
                    proof_state,
                )
        return (
            {
                "state": "UNAVAILABLE",
                "terminal": True,
                "detail": "Estate snapshot changed during bounded projection",
                "reason": "SNAPSHOT_CHANGED_DURING_READ",
            },
            {},
            [],
            None,
            "UNAVAILABLE",
        )
    except Exception:
        return (
            {
                "state": "UNAVAILABLE",
                "terminal": True,
                "detail": "Series-A read projection failed closed",
                "reason": "SERIES_A_READ_FAILED",
            },
            {},
            [],
            None,
            "UNAVAILABLE",
        )


def _probe_cache_ttl_remaining(cache_at: float) -> bool:
    return (time.time() - cache_at) < PROBE_CACHE_TTL_SECONDS


def _cache_get(key: str) -> dict[str, Any] | None:
    cached = _PLATFORM_PROBE_CACHE.get(key)
    if not cached:
        return None
    captured = cached.get("captured_at")
    if captured is None or not isinstance(captured, (int, float)):
        _PLATFORM_PROBE_CACHE.pop(key, None)
        return None
    if not _probe_cache_ttl_remaining(captured):
        _PLATFORM_PROBE_CACHE.pop(key, None)
        return None
    return cached


def _cache_set(key: str, value: dict[str, Any]) -> dict[str, Any]:
    _PLATFORM_PROBE_CACHE[key] = {**value, "captured_at": time.time()}
    return _PLATFORM_PROBE_CACHE[key]


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _live_probes_enabled() -> bool:
    return _parse_bool(os.getenv("A11OY_FRONTIER_NOW_LIVE_PROBES", "0"))


def _http_get_json(url: str, *, timeout_seconds: float = PROBE_TIMEOUT_SECONDS) -> dict[str, Any]:
    request = URLRequest(
        url,
        headers={
            "accept": "application/json",
            "user-agent": "szl-a11oy-frontier-now/2.0",
        },
    )
    try:
        with urlopen(request, timeout=timeout_seconds, context=ssl.create_default_context()) as response:
            status = int(response.status)
            payload = response.read().decode("utf-8", errors="replace")
            detail = {}
            if payload:
                try:
                    detail = _safe_mapping(json.loads(payload))
                except Exception:
                    detail = {"body": payload[:240]}
            return {
                "state": "OBSERVED" if 200 <= status < 300 else "BLOCKED",
                "status": status,
                "url": url,
                "detail": detail,
            }
    except HTTPError as exc:
        return {
            "state": "UNAVAILABLE",
            "status": getattr(exc, "code", None),
            "url": url,
            "error": f"HTTP {getattr(exc, 'code', 'unknown')}",
        }
    except (URLError, OSError) as exc:
        return {"state": "UNAVAILABLE", "status": None, "url": url, "error": str(exc)}


def _platform_projection() -> dict[str, Any]:
    return {
        "source": {
            "github_organization": PLATFORM_ORGANIZATION_GITHUB,
            "github_repo": PLATFORM_ORGANIZATION_GITHUB_REPO,
            "github_default_branch": None,
            "github_default_branch_revision": None,
            "github_observation_state": "UNAVAILABLE",
        },
        "runtime": {
            "state": "UNAVAILABLE",
            "artifact_digest": None,
            "equivalence_state": "UNAVAILABLE",
            "equivalence_reason": "ESTATE_MANIFEST_DOES_NOT_BIND_SOURCE_TO_HF_OVERLAY_AND_RUNTIME_ARTIFACT",
        },
        "huggingface": {
            "organization": PLATFORM_ORGANIZATION_HUGGINGFACE,
            "canonical_space": PLATFORM_CANONICAL_SPACE,
            "revision": None,
            "state": "UNAVAILABLE",
            "observation_state": "UNAVAILABLE",
            "canonical_scope": "PUBLIC_ONLY",
        },
        "web": {
            "domains": [
                {"domain": domain, "state": "UNAVAILABLE", "status": None, "url": f"https://{domain}", "detail": {}}
                for domain in PLATFORM_DOMAINS
            ],
            "state": "UNAVAILABLE",
        },
    }


def _augment_with_live_probes(
    manifest: Mapping[str, Any],
    source_revision: str | None,
    probe_seed: str | None,
) -> dict[str, Any]:
    projection = _platform_projection()
    if not _live_probes_enabled():
        return projection
    if manifest:
        projection["source"]["github_organization"] = str(
            manifest.get("organization") or PLATFORM_ORGANIZATION_GITHUB
        )
        projection["source"]["github_repo"] = str(
            manifest.get("github_repo") or PLATFORM_ORGANIZATION_GITHUB_REPO
        )
        projection["huggingface"]["organization"] = str(
            manifest.get("huggingface_organization") or PLATFORM_ORGANIZATION_HUGGINGFACE
        )
    cache_key = (
        f"platform:{probe_seed or 'no-manifest'}"
        f":{projection['source']['github_organization']}"
        f":{projection['source']['github_repo']}"
        f":{projection['huggingface']['organization']}"
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        return {
            "source": _safe_mapping(cached.get("source")),
            "runtime": _safe_mapping(cached.get("runtime")),
            "huggingface": _safe_mapping(cached.get("huggingface")),
            "web": _safe_mapping(cached.get("web")),
        }

    github_org = projection["source"]["github_organization"]
    github_repo = projection["source"]["github_repo"]
    github_payload = _http_get_json(
        f"https://api.github.com/repos/{quote_plus(github_org)}/{quote_plus(github_repo)}"
    )
    branch = "main"
    if github_payload.get("state") == "OBSERVED":
        detail = _safe_mapping(github_payload.get("detail"))
        branch = str(detail.get("default_branch") or "main")
        projection["source"]["github_default_branch"] = branch
        branch_payload = _http_get_json(
            f"https://api.github.com/repos/{quote_plus(github_org)}/{quote_plus(github_repo)}/branches/{quote_plus(branch)}"
        )
        if branch_payload.get("state") == "OBSERVED":
            branch_detail = _safe_mapping(branch_payload.get("detail"))
            branch_commit = _safe_mapping(branch_detail.get("commit"))
            revision = str(branch_commit.get("sha") or "")
            if revision:
                projection["source"]["github_default_branch_revision"] = revision
                projection["source"]["github_observation_state"] = "OBSERVED"
        else:
            projection["source"]["github_observation_state"] = (
                branch_payload.get("state") or "UNAVAILABLE"
            )
    else:
        projection["source"]["github_observation_state"] = github_payload.get(
            "state", "UNAVAILABLE"
        )

    hf_org = projection["huggingface"]["organization"]
    hf_payload = _http_get_json(
        f"https://huggingface.co/api/spaces/{quote_plus(hf_org)}/a11oy"
    )
    if hf_payload.get("state") == "OBSERVED":
        detail = _safe_mapping(hf_payload.get("detail"))
        hf_revision = (
            detail.get("sha")
            or detail.get("revision")
            or detail.get("lastModified")
            or detail.get("id")
        )
        if hf_revision:
            projection["huggingface"]["revision"] = str(hf_revision)
            projection["huggingface"]["state"] = "OBSERVED"
            projection["huggingface"]["observation_state"] = "OBSERVED"
        else:
            projection["huggingface"]["state"] = "PARTIAL"
            projection["huggingface"]["observation_state"] = "PARTIAL"
    else:
        projection["huggingface"]["state"] = hf_payload.get("state", "UNAVAILABLE")
        projection["huggingface"]["observation_state"] = (
            hf_payload.get("state", "UNAVAILABLE")
        )

    projection["runtime"]["artifact_digest"] = source_revision
    projection["runtime"]["state"] = (
        "OBSERVED" if projection["runtime"]["artifact_digest"] else "UNAVAILABLE"
    )
    if (
        projection["source"]["github_observation_state"] == "OBSERVED"
        and projection["huggingface"]["state"] == "OBSERVED"
    ):
        projection["runtime"]["equivalence_state"] = "OBSERVED"
        projection["runtime"]["equivalence_reason"] = "SOURCE_RUNTIME_BINDING_ESTABLISHED"
    else:
        projection["runtime"]["equivalence_state"] = "UNAVAILABLE"
        projection["runtime"]["equivalence_reason"] = "ESTATE_MANIFEST_DOES_NOT_BIND_SOURCE_TO_HF_OVERLAY_AND_RUNTIME_ARTIFACT"

    domain_states = []
    for domain in PLATFORM_DOMAINS:
        value = _http_get_json(f"https://{domain}/healthz")
        if value.get("state") == "OBSERVED":
            state = "OBSERVED"
            status = int(value.get("status", 0))
        else:
            if value.get("status") is not None:
                status = int(value["status"])
                state = "PARTIAL" if 200 <= status < 500 else "UNAVAILABLE"
            else:
                status = None
                state = "UNAVAILABLE"
        domain_states.append(
            {
                "domain": domain,
                "state": state,
                "status": status,
                "url": f"https://{domain}",
                "detail": _safe_mapping(value.get("detail")),
            }
        )
    projection["web"]["domains"] = domain_states
    projection["web"]["state"] = (
        "OBSERVED"
        if any(item.get("state") == "OBSERVED" for item in domain_states)
        else "UNAVAILABLE"
    )
    cached_projection = _cache_set(cache_key, projection)
    return {
        "source": _safe_mapping(cached_projection.get("source")),
        "runtime": _safe_mapping(cached_projection.get("runtime")),
        "huggingface": _safe_mapping(cached_projection.get("huggingface")),
        "web": _safe_mapping(cached_projection.get("web")),
    }


def _platform_identity_state(projection: Mapping[str, Any], state: str) -> str:
    if state != "OBSERVED":
        return "UNAVAILABLE"
    return (
        "HELD" if projection.get("runtime", {}).get("equivalence_state") != "OBSERVED" else "READY"
    )

def _capability_state(raw: Any, observation_state: str) -> str:
    value = str(raw or "UNAVAILABLE")
    if observation_state == "STALE" and value in {"OBSERVED", "PARTIAL"}:
        return "STALE"
    return value


def _capabilities(
    manifest: Mapping[str, Any], observation_state: str, projection: Mapping[str, Any] | None = None
) -> list[dict[str, Any]]:
    if projection is None:
        projection = _platform_projection()

    github = _safe_mapping(manifest.get("github"))
    github_value = _safe_mapping(github.get("value"))
    github_detail = _safe_mapping(github.get("detail"))
    github_state = _capability_state(github.get("state"), observation_state)

    rows: list[dict[str, Any]] = [
        {
            "provider": "github",
            "capability": "repositories",
            "state": github_state,
            "count": (
                github_value.get("repository_count")
                if github_state == "OBSERVED"
                else None
            ),
            "scope": (
                "AUTHENTICATED_SCOPE_REDACTED"
                if github_detail.get("authenticated")
                else "PUBLIC_ONLY"
            ),
        },
        {
            "provider": "github",
            "capability": "open_pull_requests",
            "state": github_state,
            "count": (
                github_value.get("open_pull_request_count")
                if github_state == "OBSERVED"
                else None
            ),
            "scope": (
                "AUTHENTICATED_SCOPE_REDACTED"
                if github_detail.get("authenticated")
                else "PUBLIC_ONLY"
            ),
        },
    ]

    huggingface = _safe_mapping(manifest.get("huggingface"))
    huggingface_value = _safe_mapping(huggingface.get("value"))
    huggingface_detail = _safe_mapping(huggingface.get("detail"))
    categories = _safe_mapping(huggingface_value.get("categories"))
    for capability in (
        "models",
        "datasets",
        "spaces",
        "collections",
        "buckets",
        "kernels",
    ):
        value = _safe_mapping(categories.get(capability))
        state = _capability_state(value.get("state"), observation_state)
        rows.append(
            {
                "provider": "huggingface",
                "capability": capability,
                "state": state,
                "count": value.get("count") if state == "OBSERVED" else None,
                "scope": (
                    "AUTHENTICATED_SCOPE_REDACTED"
                    if huggingface_detail.get("authenticated")
                    else "PUBLIC_ONLY"
                ),
            }
        )

    rows.extend(
        [
            {
                "provider": "runtime",
                "capability": "source_to_hf_overlay_binding",
                "state": _capability_state(
                    projection.get("runtime", {}).get("equivalence_state"),
                    observation_state,
                ),
                "count": None,
                "scope": "PUBLIC_OR_PUBLIC_AUDIT",
            },
            {
                "provider": "runtime",
                "capability": "runtime_artifact_digest",
                "state": "OBSERVED"
                if projection.get("runtime", {}).get("state") == "OBSERVED"
                else "UNAVAILABLE",
                "count": None,
                "scope": "PUBLIC_OR_PUBLIC_AUDIT",
            },
            {
                "provider": "web",
                "capability": "domain_build_identity",
                "state": projection.get("web", {}).get("state", "UNAVAILABLE"),
                "count": None,
                "scope": "PUBLIC_ONLY",
            },
        ]
    )
    return rows


def _receipt_projection(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projected = []
    for item in items:
        envelope = _safe_mapping(item.get("envelope"))
        projected.append(
            {
                "kind": item.get("kind"),
                "receipt_hash": item.get("receipt_hash"),
                "created_at": item.get("created_at"),
                "signature_status": envelope.get("signature_status", "UNAVAILABLE"),
                "verification_state": "UNAVAILABLE",
            }
        )
    return projected


def build_summary(app: FastAPI) -> dict[str, Any]:
    status, manifest, receipts, digest, proof_state = _snapshot(_service(app))
    state = str(status.get("state") or "UNAVAILABLE")
    critical_failures = status.get("critical_failures")
    if not isinstance(critical_failures, list):
        critical_failures = []
    enforcement = "OBSERVE_ONLY" if state == "OBSERVED" and not critical_failures else "FAILED_CLOSED"
    source_revision = status.get("source_revision") or manifest.get("source_revision")
    platform_projection = _augment_with_live_probes(
        manifest, source_revision, digest
    )
    identity_state = _platform_identity_state(platform_projection, state)
    claim_state = "READY" if identity_state == "READY" else "FAILED_CLOSED"
    claim_reason = (
        "EXACT_SOURCE_RUNTIME_BINDING_ESTABLISHED"
        if claim_state == "READY"
        else "EXACT_SOURCE_RUNTIME_BINDING_UNAVAILABLE"
    )
    identity_public_reason = platform_projection.get("runtime", {}).get(
        "equivalence_reason",
        "ESTATE_MANIFEST_DOES_NOT_BIND_SOURCE_TO_HF_OVERLAY_AND_RUNTIME_ARTIFACT",
    )

    raw_counts = _safe_mapping(status.get("counts"))
    current_counts = (
        raw_counts
        if state == "OBSERVED" and not critical_failures
        else {key: None for key in raw_counts}
    )

    return {
        "schema": SCHEMA_SUMMARY,
        "generated_at": _now(),
        "operating_mode": OPERATING_MODE,
        "observation": {
            "state": state,
            "observed_at": status.get("observed_at"),
            "valid_until": status.get("valid_until"),
            "manifest_digest": digest,
            "critical_failures": critical_failures,
            "detail": status.get("detail"),
            "reason": status.get("reason"),
        },
        "enforcement": {
            "state": enforcement,
            "external_writes": "DISABLED",
            "automatic_retries": 0,
            "effectors": [],
            "reason": (
                "READ_PROJECTION_ONLY"
                if enforcement == "OBSERVE_ONLY"
                else "CURRENT_EVIDENCE_CANNOT_AUTHORIZE_ACTION"
            ),
        },
        "identity": {
            "runtime_reported_source_revision": source_revision,
            "github_default_branch_revision": platform_projection["source"].get(
                "github_default_branch_revision"
            ),
            "github_default_branch": platform_projection["source"].get(
                "github_default_branch"
            ),
            "github_organization": platform_projection["source"].get(
                "github_organization"
            ),
            "github_repo": platform_projection["source"].get("github_repo"),
            "huggingface_repository_revision": platform_projection["huggingface"].get(
                "revision"
            ),
            "huggingface_organization": platform_projection["huggingface"].get(
                "organization"
            ),
            "runtime_artifact_digest": platform_projection["runtime"].get(
                "artifact_digest"
            ),
            "equivalence_state": platform_projection["runtime"].get("equivalence_state"),
            "reason": identity_public_reason,
            "platform": platform_projection,
        },
        "counts": current_counts,
        "last_known_counts": {
            "state": state,
            "values": raw_counts,
        },
        "coverage": _capabilities(manifest, state, platform_projection),
        "claim_gate": {
            "state": claim_state,
            "public_claim_status": "READY" if claim_state == "READY" else "HELD",
            "reason": claim_reason,
        },
        "frontiers": [
            {
                "id": "estate-observation",
                "label": "Estate observation",
                "state": state,
                "source": "series-a-manifest",
            },
            {
                "id": "source-runtime-parity",
                "label": "Source to runtime parity",
                "state": "UNAVAILABLE",
                "source": "binding-not-observed",
            },
            {
                "id": "defensive-activation",
                "label": "Defensive activation",
                "state": "MODELED",
                "source": "no-effectors-bound",
            },
            {
                "id": "atelier-clean-room",
                "label": "ATELIER clean-room innovation",
                "state": "MODELED",
                "source": "release-gate-not-bound",
            },
        ],
        "proof_rail": _receipt_projection(receipts),
        "proof_rail_state": proof_state,
        "routes": {
            "series_a_manifest": "/api/a11oy/v1/series-a/manifest",
            "series_a_receipts": "/api/a11oy/v1/series-a/receipts",
            "series_a_events": "/api/a11oy/v1/series-a/events",
            "frontier_manifest": "/api/a11oy/v1/frontier/manifest",
        },
        "private_reasoning_collected": False,
        "claim": "CURRENT_OBSERVATION_NOT_ETERNAL_TRUTH",
    }


def build_inventory(app: FastAPI) -> dict[str, Any]:
    status, manifest, _, digest, _ = _snapshot(
        _service(app), include_receipts=False
    )
    state = str(status.get("state") or "UNAVAILABLE")
    source_revision = status.get("source_revision") or manifest.get("source_revision")
    platform_projection = _augment_with_live_probes(
        manifest, source_revision, digest
    )
    return {
        "manifest_digest": digest,
        "observation_state": state,
        "observed_at": status.get("observed_at"),
        "valid_until": status.get("valid_until"),
        "items": _capabilities(manifest, state, platform_projection),
    }


def _single_query_value(request: Request, name: str, default: str) -> str:
    values = request.query_params.getlist(name)
    if len(values) > 1:
        raise HTTPException(status_code=400, detail=f"{name} must be supplied at most once")
    return values[0] if values else default


def _bounded_integer(
    request: Request,
    name: str,
    default: int,
    *,
    minimum: int,
    maximum: int,
) -> int:
    raw = _single_query_value(request, name, str(default))
    try:
        value = int(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"{name} must be an integer") from exc
    if value < minimum or value > maximum:
        raise HTTPException(
            status_code=422,
            detail=f"{name} must be between {minimum} and {maximum}",
        )
    return value


def _asset_bytes(name: str) -> bytes:
    path = Path(__file__).resolve().parent / "frontier_now_web" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"asset missing: {name}")
    return path.read_bytes()


def _asset_digest(name: str) -> str:
    return hashlib.sha256(_asset_bytes(name)).hexdigest()


def _asset_cache_control(request: Request, content: bytes) -> str:
    if request.query_params.get("v") == hashlib.sha256(content).hexdigest():
        return "public,max-age=31536000,immutable"
    return "no-store"


def register(app: FastAPI, ns: str = "a11oy") -> dict[str, Any]:
    prefix = f"/api/{ns}/v1/frontier-now"
    intended_paths = {
        "/frontier-now",
        "/frontier-now/",
        "/now",
        "/now/",
        "/frontier-now/app.js",
        "/frontier-now/app.js/",
        "/frontier-now/styles.css",
        "/frontier-now/styles.css/",
        f"{prefix}/summary",
        f"{prefix}/summary/",
        f"{prefix}/inventory",
        f"{prefix}/inventory/",
    }
    existing = [
        route
        for route in app.router.routes
        if getattr(route, "path", None) in intended_paths
    ]
    if existing:
        complete = {getattr(route, "path", None) for route in existing} == intended_paths
        owned = all(
            getattr(getattr(route, "endpoint", None), "__module__", None)
            == __name__
            for route in existing
        )
        methods_complete = all(
            {"GET", "HEAD"}.issubset(getattr(route, "methods", set()))
            for route in existing
        )
        if complete and owned and methods_complete and len(existing) == len(intended_paths):
            return {
                "ok": True,
                "state": "ALREADY_REGISTERED",
                "routes": sorted(intended_paths),
            }
        raise RuntimeError("FRONTIER_NOW_ROUTE_COLLISION")

    async def page(request: Request) -> Response:
        html = (
            _asset_bytes("index.html")
            .decode("utf-8")
            .replace("__APP_ASSET_DIGEST__", _asset_digest("app.js"))
            .replace("__STYLE_ASSET_DIGEST__", _asset_digest("styles.css"))
        )
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="text/html",
                headers=PAGE_HEADERS,
            )
        return HTMLResponse(html, headers=PAGE_HEADERS)

    async def js(request: Request) -> Response:
        content = _asset_bytes("app.js")
        headers = {
            "cache-control": _asset_cache_control(request, content),
            "x-content-type-options": "nosniff",
            "referrer-policy": "no-referrer",
        }
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="application/javascript",
                headers=headers,
            )
        return Response(content, media_type="application/javascript", headers=headers)

    async def css(request: Request) -> Response:
        content = _asset_bytes("styles.css")
        headers = {
            "cache-control": _asset_cache_control(request, content),
            "x-content-type-options": "nosniff",
            "referrer-policy": "no-referrer",
        }
        if request.method == "HEAD":
            return Response(status_code=200, media_type="text/css", headers=headers)
        return Response(content, media_type="text/css", headers=headers)

    async def summary(request: Request) -> Response:
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="application/json",
                headers=NO_STORE_HEADERS,
            )
        return JSONResponse(build_summary(request.app), headers=NO_STORE_HEADERS)

    async def inventory(request: Request) -> Response:
        provider = _single_query_value(request, "provider", "all").lower()
        if provider not in PROVIDERS:
            raise HTTPException(
                status_code=422,
                detail="provider must be one of all, github, huggingface, runtime, web",
            )
        cursor = _bounded_integer(
            request, "cursor", 0, minimum=0, maximum=1_000_000
        )
        limit = _bounded_integer(
            request,
            "limit",
            20,
            minimum=1,
            maximum=MAX_INVENTORY_LIMIT,
        )
        projection = build_inventory(request.app)
        rows = projection["items"]
        if provider != "all":
            rows = [item for item in rows if item.get("provider") == provider]
        page_rows = rows[cursor : cursor + limit]
        next_cursor = cursor + len(page_rows) if cursor + len(page_rows) < len(rows) else None
        if request.method == "HEAD":
            return Response(
                status_code=200,
                media_type="application/json",
                headers=NO_STORE_HEADERS,
            )
        return JSONResponse(
            {
                "schema": SCHEMA_INVENTORY,
                "generated_at": _now(),
                "operating_mode": OPERATING_MODE,
                "manifest_digest": projection["manifest_digest"],
                "observation_state": projection["observation_state"],
                "observed_at": projection["observed_at"],
                "valid_until": projection["valid_until"],
                "provider": provider,
                "cursor": cursor,
                "limit": limit,
                "next_cursor": next_cursor,
                "total": len(rows),
                "items": page_rows,
                "asset_names_exposed": False,
                "claim": "CAPABILITY_COVERAGE_NOT_ASSET_READINESS",
            },
            headers=NO_STORE_HEADERS,
        )

    routes: list[tuple[str, Callable[..., Any], list[str]]] = [
        ("/frontier-now", page, ["GET", "HEAD"]),
        ("/frontier-now/", page, ["GET", "HEAD"]),
        ("/now", page, ["GET", "HEAD"]),
        ("/now/", page, ["GET", "HEAD"]),
        ("/frontier-now/app.js", js, ["GET", "HEAD"]),
        ("/frontier-now/app.js/", js, ["GET", "HEAD"]),
        ("/frontier-now/styles.css", css, ["GET", "HEAD"]),
        ("/frontier-now/styles.css/", css, ["GET", "HEAD"]),
        (f"{prefix}/summary", summary, ["GET", "HEAD"]),
        (f"{prefix}/summary/", summary, ["GET", "HEAD"]),
        (f"{prefix}/inventory", inventory, ["GET", "HEAD"]),
        (f"{prefix}/inventory/", inventory, ["GET", "HEAD"]),
    ]
    added: list[str] = []
    for path, endpoint, methods in routes:
        app.add_api_route(path, endpoint, methods=methods, include_in_schema=False)
        added.append(path)

    route_set = set(added)
    selected = [
        route
        for route in app.router.routes
        if getattr(route, "path", None) in route_set
    ]
    selected_ids = {id(route) for route in selected}
    app.router.routes[:] = selected + [
        route for route in app.router.routes if id(route) not in selected_ids
    ]

    return {
        "ok": True,
        "state": "REGISTERED",
        "namespace": ns,
        "routes": sorted(added),
        "operating_mode": OPERATING_MODE,
        "sign_on_read": False,
        "effectors": [],
        "private_reasoning_collected": False,
    }
