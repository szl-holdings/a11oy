# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Stephen P. Lutar Jr. and SZL Holdings
"""Read-only product projection of Forge's executed HF tooling evaluations.

The archived results and the packages installed in THIS product process are two
separate observations. Neither a successful smoke test nor a matching version
confers model, training, deployment or billable-job authority. No remote service
is contacted, and upstream packages are never imported or installed by a request.
"""
from __future__ import annotations

import hashlib
import hmac
import importlib.metadata as metadata
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

SCHEMA = "szl.hf-tooling-product.v1"
FORGE_SOURCE = "74a8a07ced6c6b8697b31b7d0e482c4241d55880"
FORGE_REPOSITORY = "szl-holdings/szl-forge"
WORKFLOW_RUN = 34484379349
BUNDLE_SHA256 = "4efd64ffd9c3e1c5a6de5a7d18b206d5464d8906cbb0a51d51abeef80e74c12d"
BUNDLE_PATH = Path(__file__).parent / "data" / "hf-tooling-20260910.json"
PAGE_ROOT = Path(__file__).resolve().parents[1] / "pages"
MAX_BUNDLE_BYTES = 128 * 1024
CHAIN = ["GitHub", "Hugging Face", "a-11-oy.com", "a11oy.net"]
EXPECTED = {
    "hub-linux": ("hub", "Linux", 10154971656,
                  "e58473d6755dcd7eb7e75027440fcf6443681967729bfd46d67ab1997ea723fb"),
    "hub-windows": ("hub", "Windows", 10154985719,
                    "fe013be7be73640630176e1f3fdc8bae3aa06965a48a117dd20e41a4ca98fe1a"),
    "trl": ("trl", "Linux", 10155023898,
            "451f24319b1845c73bcbdcd2a9c6aedd1ee2dec581298eb29099cd49bf82ee3b"),
    "tau": ("tau", "Linux", 10154973349,
            "fe4dedc6e88e6581e786c98cdeba3b9053bdd27674251ba4e39954ab526eb30f"),
}
PACKAGES = {"huggingface-hub": "1.31.0", "transformers": "5.17.0",
            "accelerate": "1.15.0", "trl": "1.13.0", "tau-ai": "0.4.2"}
LABELS = {"hub-linux": "Hub · Linux", "hub-windows": "Hub · Windows",
          "trl": "Training stack", "tau": "Agent memory"}
AUTHORITY = {"productionDependencyPromotion": False, "productionRouteChange": False,
             "hubPublication": False, "automaticPromotion": False,
             "jobCreation": False, "toolExecution": False}
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
           "Referrer-Policy": "no-referrer"}
PAGE_HEADERS = {
    **HEADERS,
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; script-src-attr 'none'; "
        "style-src 'self'; style-src-attr 'none'; connect-src 'self'; "
        "img-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'self' https://huggingface.co "
        "https://*.hf.space https://*.huggingface.co"
    ),
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
}


class EvidenceError(ValueError):
    """Missing or modified archive evidence must fail closed."""


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def _require(condition: bool) -> None:
    if not condition:
        raise EvidenceError("archive_evidence_invalid")


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result)
        result[key] = value
    return result


def validate_bundle(raw: bytes) -> dict[str, Any]:
    """Validate source-committed byte pin AND nested exact-run receipt bindings.

    This is integrity relative to reviewed source, not signature verification.
    The ZIP digest is historical provenance; we do not redownload ZIPs on GET.
    """
    try:
        _require(type(raw) is bytes and 0 < len(raw) <= MAX_BUNDLE_BYTES)
        _require(hmac.compare_digest(hashlib.sha256(raw).hexdigest(), BUNDLE_SHA256))
        value = json.loads(raw, object_pairs_hook=_unique,
                           parse_constant=lambda _: (_ for _ in ()).throw(EvidenceError()))
        _require(value["schema"] == "szl.hf-tooling-archive.v1")
        _require(value["kind"] == "ARCHIVED_MEASUREMENT" and value["signatureState"] == "UNSIGNED")
        _require(value["sourceRepository"] == FORGE_REPOSITORY and value["sourceRevision"] == FORGE_SOURCE)
        _require(type(value["workflowRun"]) is int and value["workflowRun"] == WORKFLOW_RUN)
        _require(type(value["rows"]) is list and len(value["rows"]) == len(EXPECTED))
        seen: set[str] = set()
        for row in value["rows"]:
            identity = row["id"]
            _require(identity in EXPECTED and identity not in seen)
            seen.add(identity)
            lane, platform, artifact, receipt_hash = EXPECTED[identity]
            report = row["report"]
            _require(row["artifactId"] == artifact)
            _require(report["schema"] == "szl.forge.hf-tooling-runtime.v1")
            _require(report["sourceRepository"] == FORGE_REPOSITORY and report["sourceRevision"] == FORGE_SOURCE)
            _require(report["lane"] == lane and report["environment"]["platform"] == platform)
            _require(report["reportSha256"] == receipt_hash)
            _require(hashlib.sha256(canonical({k: v for k, v in report.items() if k != "reportSha256"})).hexdigest() == receipt_hash)
            _require(report["runtimeStatus"] == "SMOKE_PASS" and report["productionDisposition"] == "HOLD")
            _require(report["installationStatus"] == "EXACT_SOURCE_VERIFIED")
            _require(canonical(report["authority"]) == canonical(AUTHORITY))
            _require(report["dependencyClosureFullyHashLocked"] is False)
            _require(len(report["checks"]) == 4 and all(c["status"] == "PASS" for c in report["checks"].values()))
            _require(all(v == "UNAVAILABLE" for v in report["remainingEvaluation"].values()))
        _require(seen == set(EXPECTED))
        return value
    except (KeyError, TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise EvidenceError("archive_evidence_invalid") from exc


def load_bundle() -> dict[str, Any]:
    # Path is source-defined, never supplied by a request. Size is bounded before
    # parsing; no caching hides a removed or replaced evidence file.
    try:
        with BUNDLE_PATH.open("rb") as stream:
            raw = stream.read(MAX_BUNDLE_BYTES + 1)
        return validate_bundle(raw)
    except OSError as exc:
        raise EvidenceError("archive_evidence_unavailable") from exc


def installed_packages() -> list[dict[str, Any]]:
    """Inspect only distribution metadata; do not import upstream agent code."""
    rows = []
    for name, evaluated in PACKAGES.items():
        try:
            installed = metadata.version(name)
            state = "VERSION_MATCH_ONLY" if installed == evaluated else "VERSION_DIFFERS"
        except metadata.PackageNotFoundError:
            installed, state = None, "NOT_INSTALLED"
        except (OSError, ValueError, TypeError):
            installed, state = None, "UNAVAILABLE"
        rows.append({"package": name, "evaluatedVersion": evaluated,
                     "installedVersion": installed, "state": state,
                     "exactInstalledSourceVerified": False})
    return rows


def runtime_source() -> tuple[str | None, str]:
    """Read the canonical publisher identity; conflicting aliases stay unknown.

    hf-sync.yml publishes SZL_GIT_SHA. Older image builds can also carry
    A11OY_GIT_SHA. Do not silently choose one when both report different sources.
    """
    values = {os.environ.get(key, "").strip() for key in ("SZL_GIT_SHA", "A11OY_GIT_SHA")}
    values.discard("")
    if not values:
        return None, "UNAVAILABLE"
    if not all(re.fullmatch(r"[0-9a-f]{40}", value) for value in values):
        return None, "INVALID"
    if len(values) != 1:
        return None, "CONFLICT"
    return values.pop(), "REPORTED"


def project(bundle: dict[str, Any]) -> dict[str, Any]:
    lanes = []
    for row in bundle["rows"]:
        report = row["report"]
        lanes.append({"id": row["id"], "label": LABELS[row["id"]],
                      "state": report["runtimeStatus"], "observedAt": report["observedAt"],
                      "environment": report["environment"], "sources": report["sources"],
                      "checks": report["checks"], "remaining": list(report["remainingEvaluation"]),
                      "receiptSha256": report["reportSha256"], "archiveSha256": row["archiveSha256"],
                      "artifactId": row["artifactId"]})
    revision, source_state = runtime_source()
    return {"schema": SCHEMA, "available": True, "kind": "ARCHIVED_MEASUREMENT",
            "authorityChain": CHAIN, "archiveSha256": BUNDLE_SHA256,
            "sourceRepository": FORGE_REPOSITORY, "sourceRevision": FORGE_SOURCE,
            "workflowRun": WORKFLOW_RUN, "signatureState": "UNSIGNED", "lanes": lanes,
            "runtime": {"observedAt": datetime.now(timezone.utc).isoformat(),
                        "productSourceRevision": revision, "productSourceState": source_state,
                        "packages": installed_packages(), "sourceBinding": "RUNTIME_REPORTED_NOT_INDEPENDENTLY_ATTESTED"},
            "productionDisposition": "HOLD", "authority": AUTHORITY,
            "bounds": ["Archived smoke tests, not a live model-quality or uptime measurement.",
                       "A matching installed version does not attest the exact installed source.",
                       "Million-token configuration was tested; million-token training was not executed.",
                       "GPU throughput, distributed training and full provider/agent integration remain unmeasured.",
                       "Dependency closure is recorded, not fully hash-locked; receipts are unsigned."]}


def register(app: FastAPI, ns: str = "a11oy") -> dict[str, Any]:
    """Register before the existing API proxy/SPA fallback. GET/HEAD only."""
    if ns != "a11oy":
        raise ValueError("This projection is bound to the canonical A11oy product.")
    intended = {"/api/a11oy/v1/frontier-tooling",
                "/api/a11oy/v1/frontier-tooling/receipts/{lane_id}",
                "/frontier-tooling", "/frontier-tooling/",
                "/frontier-tooling/assets/view.js", "/frontier-tooling/assets/view.css"}
    existing = [route for route in app.routes if getattr(route, "path", None) in intended]
    if existing:
        complete = len(existing) == len(intended) and {route.path for route in existing} == intended
        owned = all(getattr(getattr(route, "endpoint", None), "__module__", None) == __name__
                    and getattr(route, "methods", set()) == {"GET", "HEAD"} for route in existing)
        if complete and owned:
            return {"ok": True, "state": "READ_ONLY", "alreadyRegistered": True, "effectors": []}
        raise RuntimeError("HF_TOOLING_ROUTE_COLLISION")

    def send(request: Request, body: bytes, media_type: str, *, status: int = 200,
             headers: dict[str, str] | None = None) -> Response:
        return Response(content=b"" if request.method == "HEAD" else body,
                        status_code=status, media_type=media_type,
                        headers={**HEADERS, "Content-Length": str(len(body)), **(headers or {})})

    @app.api_route("/api/a11oy/v1/frontier-tooling", methods=["GET", "HEAD"])
    def status(request: Request) -> Response:
        try:
            return send(request, canonical(project(load_bundle())), "application/json")
        except EvidenceError:
            return send(request, canonical({"schema": SCHEMA, "available": False,
                "state": "UNAVAILABLE", "productionDisposition": "HOLD", "lanes": [],
                "authority": AUTHORITY, "reasonCode": "archive_evidence_unavailable_or_invalid"}),
                "application/json", status=503)

    @app.api_route("/api/a11oy/v1/frontier-tooling/receipts/{lane_id}", methods=["GET", "HEAD"])
    def receipt(lane_id: str, request: Request) -> Response:
        if lane_id not in EXPECTED:
            raise HTTPException(404, "Unknown evaluation lane")
        try:
            report = next(row["report"] for row in load_bundle()["rows"] if row["id"] == lane_id)
            return send(request, canonical(report), "application/json")
        except EvidenceError:
            raise HTTPException(503, "Archive evidence unavailable") from None

    files = {"/frontier-tooling": ("hf-tooling.html", "text/html"),
             "/frontier-tooling/": ("hf-tooling.html", "text/html"),
             "/frontier-tooling/assets/view.js": ("hf-tooling.js", "text/javascript"),
             "/frontier-tooling/assets/view.css": ("hf-tooling.css", "text/css")}

    def file_handler(name: str, media_type: str):
        def read(request: Request) -> Response:
            try:
                body = (PAGE_ROOT / name).read_bytes()
            except OSError:
                raise HTTPException(503, "Tooling view unavailable") from None
            return send(request, body, media_type, headers=PAGE_HEADERS if media_type == "text/html" else HEADERS)
        return read

    for index, (path, (name, media_type)) in enumerate(files.items()):
        app.add_api_route(path, file_handler(name, media_type), methods=["GET", "HEAD"],
                          name=f"hf_tooling_file_{index}", include_in_schema=False)
    return {"ok": True, "state": "READ_ONLY", "effectors": [], "productionDisposition": "HOLD",
            "routes": ["/frontier-tooling", "/api/a11oy/v1/frontier-tooling"]}
