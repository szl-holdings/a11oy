#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Public SZL ecosystem atlas for a-11-oy.com.

The atlas reads the versioned public inventory published by
``SZLHOLDINGS/szl-estate-live`` instead of repeatedly walking the Hugging Face
listing APIs.  That keeps the browser same-origin, removes the live 429 failure
mode, and makes every count explicitly LIVE, CACHED, SNAPSHOT, or UNAVAILABLE.

This module never copies model weights or datasets into the application.  It
publishes immutable Hub links, repository revisions, and bounded producer
metadata so the web surface remains a control plane rather than an artifact
store.
"""
from __future__ import annotations

import asyncio
import json
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any

INVENTORY_URL = (
    "https://huggingface.co/spaces/SZLHOLDINGS/szl-estate-live/"
    "resolve/main/public-inventory.json"
)
SNAPSHOT_OBSERVED_AT = "2026-07-16T15:27:32Z"
SNAPSHOT_COUNTS = {
    "models": 15,
    "datasets": 24,
    "spaces": 26,
    "collections": 22,
    "buckets": 1,
    "public_resources_total": 88,
}

# Kernels are Hub model repositories with a governed-kernel contract, not
# runnable foundation models.  Owners were validated in the 2026-07-16 source
# alignment audit; archived owners remain labelled instead of being hidden.
KERNEL_OWNERS: dict[str, dict[str, Any]] = {
    "SZLHOLDINGS/governed-inference-meter": {"owner": "szl-holdings/szl-energy-attest"},
    "SZLHOLDINGS/szl-blocked": {"owner": "szl-holdings/szl-formula-ledger"},
    "SZLHOLDINGS/szl-formulas": {"owner": "szl-holdings/szl-formula-ledger"},
    "SZLHOLDINGS/szl-governed-norm": {
        "owner": "szl-holdings/szl-governed-norm",
        "owner_state": "ARCHIVED_PRODUCER_NEEDS_ADOPTION",
    },
    "SZLHOLDINGS/szl-govsign": {"owner": "szl-holdings/szl-receipt"},
    "SZLHOLDINGS/szl-invariants": {"owner": "szl-holdings/lutar-lean"},
    "SZLHOLDINGS/szl-kernels": {"owner": "szl-holdings/szl-kernels-live"},
    "SZLHOLDINGS/szl-lambda-gate": {"owner": "szl-holdings/szl-lambda-gate"},
    "SZLHOLDINGS/szl-ouroboros": {"owner": "szl-holdings/ouroboros"},
    "SZLHOLDINGS/szl-provctl": {"owner": "szl-holdings/governed-receipt-spec"},
}

CURATED_SURFACES: dict[str, list[dict[str, str]]] = {
    "brain": [
        {
            "id": "SZLHOLDINGS/SZL-Khipu-1.5B-BrainNavigator",
            "kind": "model",
            "href": "https://huggingface.co/SZLHOLDINGS/SZL-Khipu-1.5B-BrainNavigator",
            "owner": "szl-holdings/szl-forge",
        },
        {
            "id": "SZLHOLDINGS/szl-second-brain-inrepo",
            "kind": "dataset",
            "href": "https://huggingface.co/datasets/SZLHOLDINGS/szl-second-brain-inrepo",
            "owner": "szl-holdings/a11oy",
        },
        {
            "id": "A11oy Brain pulse",
            "kind": "runtime",
            "href": "/api/a11oy/v1/brain/pulse",
            "owner": "szl-holdings/a11oy",
        },
    ],
    "anatomy": [
        {
            "id": "SZLHOLDINGS/anatomy",
            "kind": "space",
            "href": "https://huggingface.co/spaces/SZLHOLDINGS/anatomy",
            "owner": "szl-holdings/anatomy",
        },
        {
            "id": "Living anatomy",
            "kind": "runtime",
            "href": "/living-anatomy",
            "owner": "szl-holdings/a11oy",
        },
    ],
    "holographic": [
        {
            "id": f"SZLHOLDINGS/{name}",
            "kind": "space",
            "href": f"https://huggingface.co/spaces/SZLHOLDINGS/{name}",
            "owner": "HF_NATIVE_ADOPTION_PENDING",
        }
        for name in (
            "holographic",
            "cosmos",
            "cathedral",
            "governed-norm-holo",
            "lambda-gate-holo",
            "energy-attest-holo",
            "receipt-chain-live",
            "szl-kernels-live",
        )
    ],
    "killinchu": [
        {
            "id": "SZLHOLDINGS/killinchu",
            "kind": "space",
            "href": "https://huggingface.co/spaces/SZLHOLDINGS/killinchu",
            "owner": "szl-holdings/killinchu",
        },
        {
            "id": "SZLHOLDINGS/killinchu-osint-corpus",
            "kind": "dataset",
            "href": "https://huggingface.co/datasets/SZLHOLDINGS/killinchu-osint-corpus",
            "owner": "szl-holdings/killinchu",
        },
        {
            "id": "Killinchu command surface",
            "kind": "runtime",
            "href": "/elite",
            "owner": "szl-holdings/killinchu",
        },
    ],
}

_CACHE_TTL_SECONDS = 300.0
_CACHE: dict[str, Any] = {"at": 0.0, "payload": None}
_LOCK = threading.Lock()
_REFRESH_LOCK = threading.Lock()
_PAGES_DIR = Path(__file__).resolve().parent / "pages"


def _hub_href(kind: str, item_id: str) -> str:
    if kind == "datasets":
        return f"https://huggingface.co/datasets/{item_id}"
    if kind == "spaces":
        return f"https://huggingface.co/spaces/{item_id}"
    if kind == "collections":
        return f"https://huggingface.co/collections/{item_id}"
    if kind == "buckets":
        return f"https://huggingface.co/buckets/{item_id}"
    return f"https://huggingface.co/{item_id}"


def _resource_id(kind: str, item: dict[str, Any]) -> str:
    if kind == "collections":
        return str(item.get("slug") or item.get("id") or "")
    return str(item.get("id") or "")


def _project_resource(kind: str, item: dict[str, Any]) -> dict[str, Any]:
    item_id = _resource_id(kind, item)
    runtime = item.get("runtime") if isinstance(item.get("runtime"), dict) else {}
    source = item.get("source_observation")
    source_state = source.get("state") if isinstance(source, dict) else source
    out: dict[str, Any] = {
        "id": item_id,
        "kind": kind[:-1] if kind.endswith("s") else kind,
        "href": _hub_href(kind, item_id),
        "revision": item.get("repository_sha") or item.get("head"),
        "last_modified": item.get("last_modified") or item.get("last_updated"),
        "license": item.get("license"),
        "runtime_stage": runtime.get("stage"),
        "source_state": source_state,
    }
    if item_id in KERNEL_OWNERS:
        out.update(KERNEL_OWNERS[item_id])
    return {key: value for key, value in out.items() if value is not None}


def project_inventory(raw: dict[str, Any], state: str = "LIVE") -> dict[str, Any]:
    resources = raw.get("resources") if isinstance(raw.get("resources"), dict) else {}
    projected: dict[str, list[dict[str, Any]]] = {}
    for kind in ("models", "datasets", "spaces", "collections", "buckets"):
        rows = resources.get(kind) if isinstance(resources.get(kind), list) else []
        projected[kind] = [_project_resource(kind, row) for row in rows if isinstance(row, dict)]

    model_by_id = {row.get("id"): row for row in projected["models"]}
    kernels = []
    for item_id, ownership in KERNEL_OWNERS.items():
        row = dict(model_by_id.get(item_id) or {
            "id": item_id,
            "kind": "kernel",
            "href": _hub_href("models", item_id),
        })
        row["kind"] = "kernel"
        row.update(ownership)
        kernels.append(row)

    counts = dict(SNAPSHOT_COUNTS)
    raw_counts = raw.get("counts")
    if isinstance(raw_counts, dict):
        for key in counts:
            value = raw_counts.get(key)
            if isinstance(value, int):
                counts[key] = value
    counts["kernels"] = len(kernels)

    observed_at = str(raw.get("observed_at") or SNAPSHOT_OBSERVED_AT)
    return {
        "schema": "szl.ecosystem-atlas/v1",
        "state": state,
        "observed_at": observed_at,
        "inventory_source": INVENTORY_URL,
        "counts": counts,
        "resources": {**projected, "kernels": kernels},
        "curated": CURATED_SURFACES,
        "limits": {
            "runtime_stage": "provider-reported reachability, not quality or freshness",
            "source_mapping": "validated ownership where present; pending adoption remains labelled",
            "models": "links immutable artifacts; no weights are copied into this application",
        },
    }


def _fetch_inventory() -> dict[str, Any]:
    request = urllib.request.Request(
        INVENTORY_URL,
        headers={"User-Agent": "a11oy-ecosystem-atlas/1.0", "Accept": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=12) as response:
        body = response.read(4 * 1024 * 1024)
    parsed = json.loads(body.decode("utf-8"))
    if not isinstance(parsed, dict) or not isinstance(parsed.get("resources"), dict):
        raise ValueError("inventory payload is missing resources")
    return parsed


def atlas_payload() -> dict[str, Any]:
    now = time.time()
    with _LOCK:
        cached = _CACHE.get("payload")
        cached_at = float(_CACHE.get("at") or 0.0)
        if isinstance(cached, dict) and now - cached_at < _CACHE_TTL_SECONDS:
            return project_inventory(cached, state="CACHED")
    # Coalesce cold/expired refreshes. The API executes this function in a worker
    # thread, so a slow provider never blocks the ASGI event loop and only one
    # outbound refresh is in flight for a process at a time.
    with _REFRESH_LOCK:
        now = time.time()
        with _LOCK:
            cached = _CACHE.get("payload")
            cached_at = float(_CACHE.get("at") or 0.0)
            if isinstance(cached, dict) and now - cached_at < _CACHE_TTL_SECONDS:
                return project_inventory(cached, state="CACHED")
        try:
            live = _fetch_inventory()
            with _LOCK:
                _CACHE["payload"] = live
                _CACHE["at"] = now
            return project_inventory(live, state="LIVE")
        except Exception as exc:
            with _LOCK:
                cached = _CACHE.get("payload")
            if isinstance(cached, dict):
                payload = project_inventory(cached, state="STALE_CACHE")
                payload["degraded_reason"] = type(exc).__name__
                return payload
            return {
                "schema": "szl.ecosystem-atlas/v1",
                "state": "SNAPSHOT",
                "observed_at": SNAPSHOT_OBSERVED_AT,
                "inventory_source": INVENTORY_URL,
                "counts": {**SNAPSHOT_COUNTS, "kernels": len(KERNEL_OWNERS)},
                "resources": {key: [] for key in (
                    "models", "datasets", "spaces", "collections", "buckets", "kernels"
                )},
                "curated": CURATED_SURFACES,
                "degraded_reason": type(exc).__name__,
                "limits": {
                    "snapshot": "counts only; rows stay empty rather than fabricating stale listings",
                },
            }


def register(app: Any, ns: str = "a11oy") -> str:
    """Mount the atlas API and real deep-link pages ahead of SPA fallbacks."""
    from fastapi.responses import FileResponse, JSONResponse
    from starlette.routing import Route

    atlas_page = _PAGES_DIR / "ecosystem.html"
    anatomy_page = _PAGES_DIR / "anatomy-v5.html"

    async def _api(request: Any = None) -> JSONResponse:
        return JSONResponse(await asyncio.to_thread(atlas_payload))

    async def _atlas_page(request: Any = None) -> Any:
        if atlas_page.is_file():
            return FileResponse(atlas_page, media_type="text/html")
        return JSONResponse({"error": "ecosystem page unavailable"}, status_code=503)

    async def _anatomy_page(request: Any = None) -> Any:
        if anatomy_page.is_file():
            return FileResponse(anatomy_page, media_type="text/html")
        return JSONResponse({"error": "anatomy v5 page unavailable"}, status_code=503)

    page_paths = (
        "/ecosystem",
        "/models",
        "/kernels",
        "/ecosystem/brain",
        "/ecosystem/anatomy",
        "/ecosystem/holographic",
    )
    routes = [Route(f"/api/{ns}/v1/ecosystem/atlas", _api, methods=["GET"])]
    routes.extend(Route(path, _atlas_page, methods=["GET", "HEAD"]) for path in page_paths)
    routes.append(Route("/anatomy-v5", _anatomy_page, methods=["GET", "HEAD"]))
    app.router.routes[0:0] = routes
    return f"ok: atlas API + {len(page_paths)} deep-link pages + Anatomy v5"


if __name__ == "__main__":
    print(json.dumps(atlas_payload(), indent=2))
