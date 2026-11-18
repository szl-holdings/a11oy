#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Canonical read-only delivery of ORO's existing evidence projection.

This module never imports oro.api: that standalone app constructs a separate
store and signer. Owner reads run in FastAPI's threadpool and are resolved at
request time, after the canonical app has registered its provenance owner.
"""

from collections.abc import Mapping
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import Response

from .brain_anatomy_contract import LOCKED_PROVEN
from .evidence_dag import project_dag
from .source_adapters import project_source_snapshots

SCHEMA = "szl.oro-evidence-observation/v1"
API_PATH = "/api/a11oy/v1/oro/evidence"
PAGE_PATH = "/oro/evidence"
WEB_ROOT = Path(__file__).resolve().parent / "evidence_web"
HEADERS = {
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}
PAGE_HEADERS = {
    **HEADERS,
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "connect-src 'self'; img-src 'self' data:; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
    ),
}
METHODS = ["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "TRACE", "CONNECT"]
EXECUTION_BLOCKERS = (
    "CANONICAL_ORO_STORAGE_ADAPTER_UNAVAILABLE",
    "CANONICAL_ORO_SIGNER_ADAPTER_UNAVAILABLE",
    "CANONICAL_ORO_ADMISSION_NOT_BOUND",
)


def _read_anatomy_snapshot() -> Mapping[str, Any]:
    from szl_anatomy_brainloop import evidence_snapshot

    return evidence_snapshot(ns="a11oy")


def _anatomy_summary(snapshot: object) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise ValueError("invalid anatomy snapshot")
    if (
        snapshot.get("schema") != "szl.anatomy.evidence/v6"
        or snapshot.get("evidence_class") != "MODELED"
        or snapshot.get("mode") != "READ_ONLY"
        or snapshot.get("content_access") != "SUMMARY_ONLY"
        or type(snapshot.get("storage_writes")) is not int
        or snapshot.get("storage_writes") != 0
        or any(snapshot.get(key) is not False for key in (
            "receipt_minted_on_get", "model_invoked", "gradient_training"
        ))
    ):
        raise ValueError("invalid anatomy read boundary")
    authority = snapshot.get("authority")
    if not isinstance(authority, Mapping) or any(
        authority.get(key) != "NONE"
        for key in ("training", "promotion", "execution", "provider_write")
    ):
        raise ValueError("invalid anatomy authority")
    audit, overlay = snapshot.get("audit"), snapshot.get("overlay")
    if not isinstance(audit, Mapping) or not isinstance(overlay, Mapping):
        raise ValueError("invalid anatomy counts")
    if type(audit.get("chain_ok")) is not bool:
        raise ValueError("invalid anatomy hash-chain observation")
    summary: dict[str, Any] = {"chain_ok": audit["chain_ok"]}
    for owner, keys in (
        (audit, ("receipts_checked", "broken_receipts", "proposed_demotions")),
        (overlay, ("nodes", "reinforced_edges")),
    ):
        for key in keys:
            value = owner.get(key)
            if type(value) is not int or not 0 <= value <= 2**53 - 1:
                raise ValueError("invalid anatomy count")
            summary[key] = value
    return summary


def _absent(reason: str = "OWNER_SNAPSHOT_UNAVAILABLE") -> dict[str, Any]:
    return {"state": "UNKNOWN", "count": None, "reason": reason}


def collect_observation(application: FastAPI) -> tuple[int, dict[str, Any]]:
    """Inspect existing owners; retrieval time is never evidence freshness."""
    projection = project_dag([])
    sources = {
        "canonical_khipu": _absent("OWNER_NOT_REGISTERED"),
        "second_brain": _absent(),
        "anatomy": _absent(),
        "hatun": _absent(),
    }
    khipu_observed = False
    owner = getattr(application.state, "szl_khipu_dag", None)
    if owner is not None:
        try:
            if not callable(getattr(owner, "evidence_window", None)):
                raise ValueError("bounded canonical Khipu window reader required")
            observed = project_source_snapshots(canonical_khipu_dag=owner)
            sources["canonical_khipu"] = observed["sources"]["canonical_khipu"]
            projection = {key: value for key, value in observed.items() if key != "sources"}
            khipu_observed = True
        except (ValueError, TypeError, PermissionError):
            sources["canonical_khipu"] = {
                "state": "UNAVAILABLE", "count": None, "reason": "OWNER_CONTRACT_INVALID",
            }
        except Exception:
            sources["canonical_khipu"] = {
                "state": "UNAVAILABLE", "count": None, "reason": "OWNER_READ_FAILED",
            }

    anatomy_observed = False
    try:
        summary = _anatomy_summary(_read_anatomy_snapshot())
        sources["anatomy"] = {
            "state": "MODELED",
            "count": None,
            "schema": "szl.anatomy.evidence/v6",
            "content_access": "SUMMARY_ONLY",
            "summary": summary,
            "evidence_handles": "UNAVAILABLE",
            "signature_verification": "UNKNOWN",
            "execution_authority": False,
        }
        anatomy_observed = True
    except (ValueError, TypeError, PermissionError):
        sources["anatomy"] = {
            "state": "UNAVAILABLE", "count": None, "reason": "OWNER_CONTRACT_INVALID",
        }
    except Exception:
        sources["anatomy"] = {
            "state": "UNAVAILABLE", "count": None, "reason": "OWNER_READ_FAILED",
        }

    revision = os.environ.get("SZL_GIT_SHA", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        revision = None
    body = {
        "schema": SCHEMA,
        "scope": "LOCAL_OWNER_INSPECTION",
        "observation_scope": "Existing local owner reads only; not total source coverage or execution readiness.",
        "status": (
            "OBSERVED" if khipu_observed and anatomy_observed
            else "PARTIAL" if khipu_observed else "UNAVAILABLE"
        ),
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "freshness": "NOT_ASSERTED",
        "source_revision": revision,
        "source_revision_state": "OBSERVED" if revision else "UNAVAILABLE",
        "source_binding": "RUNTIME_REPORTED_NOT_INDEPENDENTLY_ATTESTED",
        "sources": sources,
        "projection": projection,
        "execution_authority": False,
        "promotion_authority": False,
        "signing_authority": False,
        "receipt_minted_on_get": False,
        "capabilities": {
            "inspection": {"available": khipu_observed},
            "execution": {"available": False, "reasons": list(EXECUTION_BLOCKERS)},
        },
        "mathematical_scope": {
            "locked_proven": sorted(LOCKED_PROVEN, key=lambda item: int(item[1:])),
            "lambda_uniqueness": "CONJECTURE_1",
            "evidence_proof_status": "UNVERIFIED",
        },
    }
    return (200 if khipu_observed else 503), body


def _send(request: Request, body: bytes, media_type: str, *, status: int = 200,
          headers: Mapping[str, str] | None = None) -> Response:
    return Response(
        content=b"" if request.method == "HEAD" else body,
        status_code=status,
        media_type=media_type,
        headers={**HEADERS, "Content-Length": str(len(body)), **(headers or {})},
    )


def _json(request: Request, body: Mapping[str, Any], *, status: int = 200,
          headers: Mapping[str, str] | None = None) -> Response:
    encoded = json.dumps(body, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _send(request, encoded, "application/json", status=status, headers=headers)


def register(application: FastAPI, namespace: str = "a11oy") -> dict[str, Any]:
    """Own the narrow inspection namespaces before either application fallback."""
    if namespace != "a11oy":
        raise ValueError("ORO evidence is bound to the canonical a11oy owner")
    paths = {
        API_PATH, API_PATH + "/{path:path}",
        PAGE_PATH, PAGE_PATH + "/", PAGE_PATH + "/{path:path}",
        PAGE_PATH + "/assets/app.js", PAGE_PATH + "/assets/styles.css",
    }
    existing = [route for route in application.routes if getattr(route, "path", None) in paths]
    expected = {
        (API_PATH, frozenset({"GET", "HEAD"})),
        (API_PATH, frozenset(METHODS)),
        (API_PATH + "/{path:path}", frozenset(METHODS)),
        (PAGE_PATH, frozenset({"GET", "HEAD"})),
        (PAGE_PATH, frozenset(METHODS)),
        (PAGE_PATH + "/", frozenset({"GET", "HEAD"})),
        (PAGE_PATH + "/{path:path}", frozenset(METHODS)),
        (PAGE_PATH + "/assets/app.js", frozenset({"GET", "HEAD"})),
        (PAGE_PATH + "/assets/styles.css", frozenset({"GET", "HEAD"})),
    }
    if existing:
        if (
            len(existing) == len(expected)
            and {(route.path, frozenset(route.methods)) for route in existing} == expected
            and all(getattr(getattr(route, "endpoint", None), "__module__", None) == __name__
                    for route in existing)
        ):
            return {"ok": True, "state": "READ_ONLY", "already_registered": True}
        raise RuntimeError("ORO_EVIDENCE_ROUTE_COLLISION")

    @application.api_route(API_PATH, methods=["GET", "HEAD"])
    def evidence(request: Request) -> Response:
        status, body = collect_observation(request.app)
        return _json(request, body, status=status)

    def view(filename: str, media_type: str):
        def read(request: Request) -> Response:
            try:
                body = (WEB_ROOT / filename).read_bytes()
            except OSError:
                return _json(request, {
                    "schema": SCHEMA, "status": "UNAVAILABLE",
                    "reason": "VIEW_ASSET_UNAVAILABLE", "execution_authority": False,
                }, status=503)
            return _send(
                request, body, media_type,
                headers=PAGE_HEADERS if media_type == "text/html" else HEADERS,
            )
        return read

    for path, filename, media_type in (
        (PAGE_PATH, "index.html", "text/html"),
        (PAGE_PATH + "/", "index.html", "text/html"),
        (PAGE_PATH + "/assets/app.js", "app.js", "text/javascript"),
        (PAGE_PATH + "/assets/styles.css", "styles.css", "text/css"),
    ):
        application.add_api_route(path, view(filename, media_type), methods=["GET", "HEAD"])

    def refuse(request: Request, path: str = "") -> Response:
        readonly = request.method in {"GET", "HEAD"}
        return _json(request, {
            "schema": SCHEMA, "status": "UNAVAILABLE",
            "reason": "UNKNOWN_EVIDENCE_ROUTE" if readonly else "READ_ONLY_SURFACE",
            "execution_authority": False, "promotion_authority": False,
            "signing_authority": False,
        }, status=404 if readonly else 405,
            headers={} if readonly else {"Allow": "GET, HEAD"})

    # Starlette may continue after a method mismatch. These explicit guards
    # keep mutations and unknown subpaths away from the API proxy/SPA fallback.
    application.add_api_route(API_PATH, refuse, methods=METHODS, include_in_schema=False)
    application.add_api_route(API_PATH + "/{path:path}", refuse, methods=METHODS, include_in_schema=False)
    application.add_api_route(PAGE_PATH, refuse, methods=METHODS, include_in_schema=False)
    application.add_api_route(PAGE_PATH + "/{path:path}", refuse, methods=METHODS, include_in_schema=False)
    return {"ok": True, "state": "READ_ONLY", "routes": [API_PATH, PAGE_PATH]}
