#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only product navigation and evidence projection. Taxonomy: services/.

This entry point consolidates existing product/proof surfaces. It neither
authorizes actions nor owns a signer, credential, publisher or scheduler.
"""

import hashlib
import json
import os
import re
import stat
from datetime import datetime, timezone
from pathlib import Path

from fastapi.responses import JSONResponse, Response
from routers import command_centre_view
from szl_provider_http import http_json

ROOT = Path(__file__).resolve().parent / "command_centre_web"
STUDY = Path(__file__).resolve().parent / "data" / "atelier-model-intake-2026-09-29.json"
PUBLIC_ESTATE = Path(__file__).resolve().parents[1] / "static/shared/public-estate-contract.v1.json"
PROOF_INVENTORY = "https://a11oy.net/estate/hf-current.json"
HEADERS = {"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "no-referrer"}
PAGE_HEADERS = {**HEADERS, "Cache-Control": "no-store, no-transform", "Content-Security-Policy": "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; font-src 'self'; object-src 'none'; base-uri 'none'; form-action 'self'; frame-ancestors 'self'", "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=(), usb=()"}

SURFACES = (
    ("operate", "Operator console", "/console?view=command", "Existing governed controls and runtime posture"),
    ("operate", "Command observations", "/command-v2", "Existing source inspector and expiring read-only observations; explicit actions keep their own guards"),
    ("operate", "Models and kernels", "/estate", "Existing source-aware estate classification"),
    ("operate", "Frontier", "/frontier-now", "Existing read-only runtime and evidence projection"),
    ("operate", "Fleet", "/fleet-c2", "Existing fleet posture; no new dispatch authority"),
    ("operate", "Governance", "/governance", "Policy gates, restraints and honest status"),
    ("operate", "Receipts", "/verify", "Existing receipt verifier; a signature is not inference proof"),
    ("operate", "Atelier model walk", "/atelier", "Retained model discovery surface"),
    ("operate", "Atelier research", "/atelier/frontier", "Independent capability synthesis and MODELED evaluations"),
    ("operate", "SZL public CPU lab", "https://huggingface.co/spaces/SZLHOLDINGS/szl-model-inference-lab", "Separate best-effort public Khipu demonstration; unsigned execution, no sensitive prompts"),
    ("verify", "Python source", "https://github.com/szl-holdings/a11oy", "Canonical product source: szl-holdings/a11oy"),
    ("verify", "Publication runs", "https://github.com/szl-holdings/a11oy/actions/workflows/hf-sync.yml", "Sole canonical Space publisher; inspect exact source and receipts"),
    ("verify", "Canonical runtime", "https://huggingface.co/spaces/SZLHOLDINGS/a11oy", "Python product runtime, not the separate artifact discovery Space"),
    ("verify", "Proof room", "https://a11oy.net", "Independent proof surface; retained evidence has its own timestamp"),
    ("artifacts", "SZL models", "https://huggingface.co/SZLHOLDINGS?type=model", "Provider metadata is not qualification or training proof"),
    ("artifacts", "SZL datasets", "https://huggingface.co/SZLHOLDINGS?type=dataset", "Published evidence and datasets; do not infer private inventory"),
    ("artifacts", "SZL Spaces", "https://huggingface.co/SZLHOLDINGS?type=space", "Existing applications retain their source and publication owners"),
    ("artifacts", "Kernel evidence", "https://a11oy.net/estate/", "Kernel inventory and source bindings on the proof surface"),
)


def _bounded_source(path, limit=65536):
    """Read only a regular, bounded bundled input; never follow a file symlink."""
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError("bundled source is not a regular file")
    with path.open("rb") as stream:
        body = stream.read(limit + 1)
    if len(body) > limit:
        raise ValueError("bundled source exceeds bound")
    return body


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate public binding field")
        value[key] = item
    return value


def _invalid_constant(_value):
    raise ValueError("non-finite public binding")


def public_estate():
    """Narrow local consumer, not an inventory scanner or keep-list authority.

    Project only fixed public origins and Ayllu's existing inventory-only row.
    Unrelated source rows are never serialized into the page or its manifest.
    Full estate/keep-list consistency remains the release validator's job.
    """
    unavailable = {"state": "UNAVAILABLE", "code": "PUBLIC_BINDING_UNAVAILABLE",
                   "source": "static/shared/public-estate-contract.v1.json",
                   "sha256": None, "canonical": None, "ayllu": None}
    try:
        raw = _bounded_source(PUBLIC_ESTATE)
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object,
                           parse_constant=_invalid_constant)
        if not isinstance(value, dict) or value.get("schema") != "szl.public-estate/v1" or value.get("version") != "1.0.2":
            raise ValueError("unsupported public binding")
        canonical = value.get("canonical")
        if canonical != {
            "product": "https://a-11-oy.com", "proof": "https://a11oy.net",
            "source": "https://github.com/szl-holdings/a11oy",
            "githubOrganization": "https://github.com/szl-holdings",
            "huggingFaceOrganization": "https://huggingface.co/SZLHOLDINGS",
        }:
            raise ValueError("public origins drifted")
        authority = value.get("authority")
        if not isinstance(authority, dict) or set(authority) != {
            "externalWrites", "publicEffectors", "automaticRemediation",
            "productionAuthorization", "humanApprovalRequired",
        } or authority.get("externalWrites") != "DISABLED_BY_DEFAULT" or authority.get("publicEffectors") != [] or authority.get("automaticRemediation") is not False or authority.get("productionAuthorization") is not False or authority.get("humanApprovalRequired") is not True:
            raise ValueError("public authority drifted")
        fabric = value.get("fabric")
        if not isinstance(fabric, dict) or fabric.get("id") != "a11oy" or fabric.get("githubRepository") != "szl-holdings/a11oy" or fabric.get("huggingFaceRepository") != "SZLHOLDINGS/a11oy":
            raise ValueError("product ownership drifted")
        inventory = value.get("inventoryOnlyHuggingFaceRepositories")
        if not isinstance(inventory, list) or not 1 <= len(inventory) <= 128:
            raise ValueError("invalid public classifications")
        seen = set()
        ayllu = None
        for row in inventory:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not re.fullmatch(r"SZLHOLDINGS/[A-Za-z0-9_.-]+", row["id"]):
                raise ValueError("invalid inventory identity")
            if row["id"] in seen:
                raise ValueError("duplicate inventory identity")
            seen.add(row["id"])
            if row.get("classification") != "INVENTORY_ONLY" or row.get("governedKeep") is not False or row.get("disposition") != ("ORG_CARD" if row["id"] == "SZLHOLDINGS/README" else "FOLD") or row.get("policySource") != "docs/series-a/hf-space-keep-list.yaml":
                raise ValueError("inventory disposition drifted")
            if row["id"] == "SZLHOLDINGS/ayllu":
                ayllu = {key: row[key] for key in ("id", "classification", "governedKeep", "disposition", "policySource")}
        if ayllu is None:
            raise ValueError("Ayllu public classification unavailable")
        topology = [fabric["huggingFaceRepository"]]
        for group in ("publicDomainBodies", "supportingSystems"):
            rows = value.get(group)
            if not isinstance(rows, list) or len(rows) > 128:
                raise ValueError("invalid public topology")
            for row in rows:
                if not isinstance(row, dict) or not isinstance(row.get("huggingFaceRepositories"), list):
                    raise ValueError("invalid public topology row")
                topology.extend(row["huggingFaceRepositories"])
        laboratories = value.get("laboratorySurfaces")
        if not isinstance(laboratories, list) or len(laboratories) > 128:
            raise ValueError("invalid public laboratory list")
        topology.extend(laboratories)
        if any(not isinstance(item, str) for item in topology) or "SZLHOLDINGS/ayllu" in topology:
            raise ValueError("inventory-only Ayllu cannot be promoted")
        ayllu["href"] = "https://huggingface.co/spaces/" + ayllu["id"]
        return {"state": "SOURCE_CONTRACT", "source": unavailable["source"],
                "sha256": hashlib.sha256(raw).hexdigest(), "version": value["version"],
                "canonical": dict(canonical), "ayllu": ayllu}
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        return unavailable


def presentation_sources():
    """Exact serving owners; the retained index.html is deliberately excluded."""
    sources = {
        "routers/command_centre.py": Path(__file__),
        "routers/command_centre_view.py": Path(command_centre_view.__file__),
    }
    for suffix in ("app.js", "style.css", "szl/szl-design-system.css", "szl/szl-console.css"):
        sources["routers/command_centre_web/" + suffix] = ROOT / suffix
    return {name: hashlib.sha256(_bounded_source(path, 1048576)).hexdigest()
            for name, path in sources.items()}


def manifest():
    revision = os.getenv("SZL_GIT_SHA", "")
    return {
        "schema": "szl.command-centre/v1", "read_only": True,
        "external_mutation_performed": False, "inference_verified": False,
        "runtime_scope": "LOCAL_PREVIEW_STARTUP_DISABLED" if os.getenv("A11OY_COMMAND_CENTRE_PREVIEW") == "1" else "DEPLOYED_PROCESS_REQUIRES_PROOF",
        "source_revision": revision if re.fullmatch(r"[0-9a-f]{40}", revision) else None,
        "public_estate": public_estate(),
        "presentation": {
            "mode": "PYTHON_SERVER_RENDERED",
            "renderer": "routers/command_centre_view.py",
            "retained_browser_interactions": "routers/command_centre_web/app.js",
            "legacy_non_serving_reference": "routers/command_centre_web/index.html",
            "sources": presentation_sources(),
        },
        "authorities": {"source": "szl-holdings/a11oy", "artifacts": "SZLHOLDINGS", "product": "https://a-11-oy.com", "proof": "https://a11oy.net", "publisher": "hf-sync.yml"},
        "release_order": ["protected_github_source", "canonical_hf_publication", "product_and_proof_verification"],
        "surfaces": [{"lane": lane, "title": title, "href": href, "boundary": boundary} for lane, title, href, boundary in SURFACES],
        "boundaries": ["Navigation does not authorize an action", "Grok is third-party inference, not SZL-owned weights", "Public CPU lab is a separate unsigned best-effort demonstration, not Grok or local Ollama", "Python chat is bounded single-turn; platform encrypted Turn Capsule is a separate source boundary", "Runtime metadata and HTTP 200 do not establish model inference"],
    }


def page_bytes():
    """Deterministic source-owner entry for route and browser byte witnesses."""
    return command_centre_view.render_page(manifest())


def proof_inventory():
    unavailable = {"state": "UNAVAILABLE", "read_only": True, "source": PROOF_INVENTORY, "counts": None, "inference_verified": False}
    try:
        document, error = http_json(PROOF_INVENTORY, timeout=12, max_response_bytes=1048576, max_redirects=0, allow_private=False)
    except Exception:
        return {**unavailable, "code": "PROOF_INVENTORY_UNAVAILABLE"}
    if error or not isinstance(document, dict):
        return {**unavailable, "code": "PROOF_INVENTORY_UNAVAILABLE"}
    counts = document.get("counts")
    keys = ("models", "datasets_public", "kernels", "spaces_public")
    if not isinstance(counts, dict) or any(type(counts.get(key)) is not int or not 0 <= counts[key] <= 100000 for key in keys):
        return {**unavailable, "code": "PROOF_INVENTORY_INVALID"}
    observed = document.get("observed_at")
    try:
        stamp = datetime.fromisoformat(observed.replace("Z", "+00:00"))
        if stamp.tzinfo is None:
            raise ValueError("timezone required")
        age = (datetime.now(timezone.utc) - stamp).total_seconds()
        if age < -300:
            raise ValueError("future observation")
    except (AttributeError, TypeError, ValueError):
        return {**unavailable, "code": "PROOF_INVENTORY_INVALID_TIME"}
    return {
        "state": "OBSERVED_SNAPSHOT" if age <= 86400 else "STALE_SNAPSHOT",
        "read_only": True, "source": PROOF_INVENTORY, "observed_at": observed,
        "counts": {key: counts[key] for key in keys}, "inference_verified": False,
        "boundary": "Public retained inventory, not model qualification or complete private estate. Spaces may include the organization profile card.",
    }


def register(app):
    prior = list(app.router.routes)

    def asset(path, media_type, headers=HEADERS):
        # The product's middleware cannot safely relay FileResponse pathsend.
        # Emit bounded body bytes, as the existing front door does.
        try:
            with path.open("rb") as stream:
                body = stream.read(1048577)
            if len(body) > 1048576:
                raise ValueError("asset exceeds bound")
        except (OSError, ValueError):
            return JSONResponse({"state": "UNAVAILABLE", "code": "ASSET_UNAVAILABLE"}, status_code=503, headers=HEADERS)
        return Response(body, media_type=media_type, headers=headers)

    def page():
        try:
            body = page_bytes()
            if len(body) > 1048576:
                raise ValueError("rendered page exceeds bound")
        except (OSError, ValueError, TypeError, KeyError, RecursionError):
            return JSONResponse({"state": "UNAVAILABLE", "code": "PAGE_SOURCE_UNAVAILABLE"}, status_code=503, headers=HEADERS)
        return Response(body, media_type="text/html", headers=PAGE_HEADERS)

    def script():
        return asset(ROOT / "app.js", "text/javascript")

    def styles():
        return asset(ROOT / "style.css", "text/css")

    def brand():
        return asset(ROOT / "szl" / "szl-design-system.css", "text/css")

    def console_styles():
        return asset(ROOT / "szl" / "szl-console.css", "text/css")

    async def source_manifest():
        try:
            body = manifest()
        except (OSError, ValueError, TypeError, KeyError, RecursionError):
            return JSONResponse({"state": "UNAVAILABLE", "code": "PAGE_SOURCE_UNAVAILABLE"}, status_code=503, headers=HEADERS)
        return JSONResponse(body, headers=HEADERS)

    def inventory():
        return JSONResponse(proof_inventory(), headers=HEADERS)

    def study():
        if not STUDY.is_file():
            return JSONResponse({"state": "UNAVAILABLE", "code": "STUDY_NOT_BUNDLED", "inference_verified": False}, status_code=503, headers=HEADERS)
        return asset(STUDY, "application/json")

    for path in ("/command-centre", "/a11oy/atelier"):
        app.add_api_route(path, page, methods=["GET", "HEAD"], include_in_schema=False)
    for path, handler in (("/command-centre/app.js", script), ("/command-centre/style.css", styles), ("/command-centre/szl/szl-design-system.css", brand), ("/command-centre/szl/szl-console.css", console_styles), ("/api/a11oy/v1/command-centre/manifest", source_manifest), ("/api/a11oy/v1/command-centre/inventory", inventory), ("/api/a11oy/v1/command-centre/study", study)):
        app.add_api_route(path, handler, methods=["GET", "HEAD"], include_in_schema=False)
    added = [route for route in app.router.routes if route not in prior]
    app.router.routes[:] = added + prior
    return {"module": "routers.command_centre", "routes": len(added), "read_only": True}
