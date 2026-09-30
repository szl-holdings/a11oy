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
import json
import os
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response

SCHEMA_SUMMARY = "szl.frontier-now-summary/v1"
SCHEMA_INVENTORY = "szl.frontier-now-inventory/v1"
OPERATING_MODE = "OBSERVE_ONLY"
MAX_INVENTORY_LIMIT = 50
PROVIDERS = {"all", "github", "huggingface", "runtime", "web"}
GITHUB_DEFAULT_BRANCH_URL = "https://api.github.com/repos/szl-holdings/a11oy/commits/main"
GITHUB_OBSERVE_TIMEOUT_S = 2.0
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


def _capability_state(raw: Any, observation_state: str) -> str:
    value = str(raw or "UNAVAILABLE")
    if observation_state == "STALE" and value in {"OBSERVED", "PARTIAL"}:
        return "STALE"
    return value


def _capabilities(
    manifest: Mapping[str, Any], observation_state: str
) -> list[dict[str, Any]]:
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
                "state": "UNAVAILABLE",
                "count": None,
                "scope": "NOT_OBSERVED_BY_ESTATE_MANIFEST",
            },
            {
                "provider": "web",
                "capability": "domain_build_identity",
                "state": "UNAVAILABLE",
                "count": None,
                "scope": "NOT_OBSERVED_BY_ESTATE_MANIFEST",
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


def _observe_github_default_branch() -> str | None:
    """Public GitHub tip only. No token. Timeout fails closed to None."""
    if os.environ.get("A11OY_OBSERVE_GITHUB_MAIN", "1").strip().lower() in {
        "0",
        "false",
        "off",
        "no",
    }:
        return None
    request = urllib.request.Request(
        GITHUB_DEFAULT_BRANCH_URL,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "a11oy-frontier-now/1.0 (governed-read; no-secret)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=GITHUB_OBSERVE_TIMEOUT_S) as response:
            if int(getattr(response, "status", 0) or 0) != 200:
                return None
            payload = json.loads(response.read(65536).decode("utf-8"))
    except Exception:
        return None
    sha = payload.get("sha") if isinstance(payload, dict) else None
    if not isinstance(sha, str) or len(sha) < 7:
        return None
    return sha


def _normalize_revision(value: Any) -> str:
    return str(value or "").strip().lower()


def _source_parity(runtime: Any, github: Any) -> tuple[str, str, str]:
    github_sha = _normalize_revision(github)
    runtime_sha = _normalize_revision(runtime)
    if not github_sha:
        return (
            "UNAVAILABLE",
            "UNAVAILABLE",
            "ESTATE_MANIFEST_DOES_NOT_BIND_SOURCE_TO_HF_OVERLAY_AND_RUNTIME_ARTIFACT",
        )
    if not runtime_sha:
        return (
            "UNAVAILABLE",
            "UNAVAILABLE",
            "RUNTIME_SOURCE_REVISION_UNAVAILABLE",
        )
    width = min(len(github_sha), len(runtime_sha))
    matched = github_sha == runtime_sha or (
        width >= 7 and github_sha[:width] == runtime_sha[:width]
    )
    if matched:
        return (
            "UNAVAILABLE",
            "MATCH",
            "GITHUB_MAIN_MATCHES_RUNTIME_HF_OVERLAY_AND_ARTIFACT_DIGEST_UNAVAILABLE",
        )
    return (
        "DRIFT",
        "DRIFT",
        "GITHUB_DEFAULT_BRANCH_DRIFTS_FROM_RUNTIME_REPORTED_REVISION",
    )


def build_summary(app: FastAPI) -> dict[str, Any]:
    status, manifest, receipts, digest, proof_state = _snapshot(_service(app))
    state = str(status.get("state") or "UNAVAILABLE")
    critical_failures = status.get("critical_failures")
    if not isinstance(critical_failures, list):
        critical_failures = []
    enforcement = "OBSERVE_ONLY" if state == "OBSERVED" and not critical_failures else "FAILED_CLOSED"
    source_revision = status.get("source_revision") or manifest.get("source_revision")

    raw_counts = _safe_mapping(status.get("counts"))
    current_counts = (
        raw_counts
        if state == "OBSERVED" and not critical_failures
        else {key: None for key in raw_counts}
    )
    github_revision = _observe_github_default_branch()
    equivalence_state, parity_state, identity_reason = _source_parity(
        source_revision, github_revision
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
            "github_default_branch_revision": github_revision,
            "huggingface_repository_revision": None,
            "runtime_artifact_digest": None,
            "equivalence_state": equivalence_state,
            "reason": identity_reason,
        },
        "counts": current_counts,
        "last_known_counts": {
            "state": state,
            "values": raw_counts,
        },
        "coverage": _capabilities(manifest, state),
        "claim_gate": {
            "state": "FAILED_CLOSED",
            "public_claim_status": "HELD",
            "reason": "EXACT_SOURCE_RUNTIME_BINDING_UNAVAILABLE",
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
                "state": parity_state,
                "source": (
                    "public-github-main"
                    if github_revision
                    else "binding-not-observed"
                ),
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
    return {
        "manifest_digest": digest,
        "observation_state": state,
        "observed_at": status.get("observed_at"),
        "valid_until": status.get("valid_until"),
        "items": _capabilities(manifest, state),
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
