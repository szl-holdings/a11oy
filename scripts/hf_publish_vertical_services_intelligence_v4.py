#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publish and prove the vertical-services intelligence fabric v4.

This layer deliberately builds on the reviewed frontier-v3 publisher. It moves
the exact source pin to the merged Python 2.2 runtime and adds terminal evidence
for the six model-and-kernel intelligence rooms. It does not create a second
writer, accept caller-supplied provider endpoints, expose credential material,
or grant any model, formula, Hatun review, or frontend autonomous authority.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import time
import urllib.error
import urllib.request
from pathlib import Path
from types import ModuleType
from typing import Any

HERE = Path(__file__).resolve().parent
V3_IMPL = HERE / "hf_publish_vertical_services_frontier_v3.py"

SOURCE_REVISION = "c24ef61716f173e48d95dad61408d9fa065f0204"
EXPECTED_VERSION = "2.2.0"
USER_AGENT = "SZLHOLDINGS-Vertical-Intelligence-v4-Publisher/1.0"

CANONICAL_VERTICALS = (
    "sentra",
    "lyte",
    "killinchu",
    "finance",
    "terra",
    "counsel",
)

INTELLIGENCE_ROOMS = {
    "sentra": "threat-shield",
    "lyte": "service-lattice",
    "killinchu": "voyage-radar",
    "finance": "probability-orbit",
    "terra": "parcel-grid",
    "counsel": "authority-chain",
}

INTELLIGENCE_ALIASES = {
    "aegis": "sentra",
    "immune": "sentra",
    "business-observability": "lyte",
    "vessels": "killinchu",
    "puriq": "finance",
    "markets": "finance",
    "real-estate": "terra",
    "prism": "counsel",
}

MODEL_ASSETS = {
    "khipu-1.5b": "SZLHOLDINGS/SZL-Khipu-1.5B",
    "receipt-agent": "SZLHOLDINGS/szl-receiptagent-qwen35-0.8b-v2",
    "a11oy-mini": "SZLHOLDINGS/A11OY-MINI",
    "nemo-recipe": "SZLHOLDINGS/szl-nemo",
}

KERNEL_ASSETS = {
    "kernel-suite": "SZLHOLDINGS/szl-kernels",
    "lambda-gate": "SZLHOLDINGS/szl-lambda-gate",
    "invariants": "SZLHOLDINGS/szl-invariants",
    "blocked": "SZLHOLDINGS/szl-blocked",
    "receipt-attn": "SZLHOLDINGS/szl-receipt-attn",
    "block-kv": "SZLHOLDINGS/szl-block-kv",
}

INTELLIGENCE_SMOKE_PATHS = (
    "/api/intelligence",
    "/intelligence/sentra",
    "/intelligence/lyte",
    "/intelligence/killinchu",
    "/intelligence/finance",
    "/intelligence/terra",
    "/intelligence/counsel",
    "/api/verticals/sentra/intelligence",
    "/api/verticals/lyte/intelligence",
    "/api/verticals/killinchu/intelligence",
    "/api/verticals/finance/intelligence",
    "/api/verticals/terra/intelligence",
    "/api/verticals/counsel/intelligence",
)


def load_v3() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "szl_vertical_services_frontier_v3",
        V3_IMPL,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load frontier-v3 publisher: {V3_IMPL}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def request_text(base: ModuleType, path: str) -> tuple[int, str]:
    separator = "&" if "?" in path else "?"
    request = urllib.request.Request(
        f"{base.ORIGIN}{path}{separator}szl_intelligence_verify={time.time_ns()}",
        headers={
            "Accept": "text/html, application/json;q=0.8",
            "Cache-Control": "no-cache",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.status, response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")


def verify_intelligence(base: ModuleType) -> dict[str, Any]:
    failures: list[str] = []
    catalog_status, catalog = base.request_json("/api/intelligence")
    if not isinstance(catalog, dict):
        catalog = {}

    catalog_verticals = catalog.get("verticals", {})
    catalog_models = catalog.get("model_assets", {})
    catalog_kernels = catalog.get("kernel_assets", {})
    if catalog_status != 200:
        failures.append(f"catalog: HTTP {catalog_status}")
    if set(catalog_verticals) != set(CANONICAL_VERTICALS):
        failures.append("catalog: canonical vertical set mismatch")
    if set(catalog_models) != set(MODEL_ASSETS):
        failures.append("catalog: model asset set mismatch")
    if set(catalog_kernels) != set(KERNEL_ASSETS):
        failures.append("catalog: kernel asset set mismatch")
    if catalog.get("caller_supplied_endpoints_allowed") is not False:
        failures.append("catalog: caller-supplied endpoint boundary drifted")
    if catalog.get("effectors_enabled") is not False:
        failures.append("catalog: effector boundary drifted")
    for alias, repo_id in MODEL_ASSETS.items():
        if catalog_models.get(alias, {}).get("repo_id") != repo_id:
            failures.append(f"catalog/model/{alias}: repository mismatch")
    for alias, repo_id in KERNEL_ASSETS.items():
        if catalog_kernels.get(alias, {}).get("repo_id") != repo_id:
            failures.append(f"catalog/kernel/{alias}: repository mismatch")

    rooms: list[dict[str, Any]] = []
    room_hashes: set[str] = set()
    profiles: list[dict[str, Any]] = []
    for vertical, motif in INTELLIGENCE_ROOMS.items():
        room_status, text = request_text(base, f"/intelligence/{vertical}")
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        required_room_fragments = (
            f'data-vertical="{vertical}"',
            f'data-motif="{motif}"',
            "Skip to intelligence room",
            "Learn broadly. Copy nothing proprietary.",
            "@media(prefers-reduced-motion:reduce)",
            "@media(forced-colors:active)",
            "HUMAN BIND",
        )
        missing_room_fragments = [
            value for value in required_room_fragments if value not in text
        ]
        room = {
            "vertical": vertical,
            "http_status": room_status,
            "motif": motif,
            "sha256": digest,
            "missing_fragments": missing_room_fragments,
        }
        if room_status != 200 or missing_room_fragments:
            failures.append(f"room/{vertical}: public intelligence surface mismatch")
        rooms.append(room)
        room_hashes.add(digest)

        profile_status, profile = base.request_json(
            f"/api/verticals/{vertical}/intelligence"
        )
        if not isinstance(profile, dict):
            profile = {}
        model_rows = profile.get("models", [])
        kernel_rows = profile.get("kernels", [])
        pattern_rows = profile.get("reference_patterns", [])
        policy = profile.get("policy", {})
        profile_item = {
            "vertical": vertical,
            "http_status": profile_status,
            "tasks": len(profile.get("tasks", {})),
            "models": len(model_rows),
            "kernels": len(kernel_rows),
            "frontier_capabilities": len(profile.get("novel_capabilities", [])),
            "effectors_enabled": policy.get("effectors_enabled"),
            "human_approval_required": policy.get("human_approval_required"),
        }
        profile_valid = (
            profile_status == 200
            and profile.get("vertical") == vertical
            and len(profile.get("tasks", {})) == 4
            and len(model_rows) == 3
            and len(kernel_rows) >= 5
            and len(profile.get("novel_capabilities", [])) == 3
            and policy.get("caller_supplied_model_endpoints_allowed") is False
            and policy.get("public_or_licensed_data_only") is True
            and policy.get("effectors_enabled") is False
            and policy.get("human_approval_required") is True
            and all(
                isinstance(row, dict)
                and row.get("credential_value_exposed") is False
                and row.get("repo_id") in set(MODEL_ASSETS.values())
                for row in model_rows
            )
            and all(
                isinstance(row, dict)
                and row.get("repo_id") in set(KERNEL_ASSETS.values())
                for row in kernel_rows
            )
            and all(
                isinstance(row, dict)
                and row.get("proprietary_code_copied") is False
                and row.get("proprietary_data_copied") is False
                for row in pattern_rows
            )
        )
        if not profile_valid:
            failures.append(f"profile/{vertical}: model, kernel, or authority mismatch")
        profiles.append(profile_item)

    if len(room_hashes) != len(INTELLIGENCE_ROOMS):
        failures.append("rooms: six intelligence surfaces are not byte-distinct")

    aliases: list[dict[str, Any]] = []
    for alias, canonical in INTELLIGENCE_ALIASES.items():
        status, body = base.request_json(f"/api/verticals/{alias}/intelligence")
        observed = body.get("vertical") if isinstance(body, dict) else None
        item = {
            "alias": alias,
            "canonical": canonical,
            "observed": observed,
            "http_status": status,
        }
        if status != 200 or observed != canonical:
            failures.append(f"alias/{alias}: intelligence identity mismatch")
        aliases.append(item)

    session = "live-intelligence-verifier-0123456789abcdef"
    raw_context = "bounded verifier context that must not be returned"
    plan_status, plan = base.request_json(
        "/api/verticals/counsel/intelligence/plan",
        method="POST",
        payload={
            "task": "argument-map",
            "objective": "Verify fail-closed planning without provider invocation.",
            "context": raw_context,
            "axes": {
                "evidence": 0.40,
                "freshness": 0.95,
                "reversibility": 0.95,
            },
            "evidence_sha256": ["a" * 64, "b" * 64],
        },
        headers={"X-SZL-Session": session},
    )
    plan_text = json.dumps(plan, sort_keys=True) if isinstance(plan, dict) else str(plan)
    plan_valid = (
        plan_status == 200
        and isinstance(plan, dict)
        and plan.get("decision") == "ABSTAIN"
        and "LAMBDA_BELOW_INFERENCE_FLOOR" in plan.get("blockers", [])
        and plan.get("can_execute") is False
        and plan.get("effectors_enabled") is False
        and plan.get("human_approval_required") is True
        and plan.get("raw_context_returned") is False
        and plan.get("raw_context_stored") is False
        and raw_context not in plan_text
        and isinstance(plan.get("receipt", {}).get("basis_sha256"), str)
        and len(plan["receipt"]["basis_sha256"]) == 64
    )
    if not plan_valid:
        failures.append("plan: fail-closed provider-free planning contract mismatch")

    health_status, health = base.request_json("/healthz")
    if not isinstance(health, dict):
        health = {}
    health_valid = (
        health_status == 200
        and health.get("version") == EXPECTED_VERSION
        and health.get("vertical_intelligence_wired") is True
        and health.get("model_provider_invocation_fail_closed") is True
        and health.get("caller_supplied_model_endpoints_allowed") is False
        and health.get("hatun_can_authorize") is False
        and health.get("effectors_enabled") is False
        and health.get("build", {}).get("revision") == SOURCE_REVISION
    )
    if not health_valid:
        failures.append("health: intelligence or authority boundary mismatch")

    return {
        "schema": "szl.vertical-intelligence-live-proof/v4",
        "source_revision": SOURCE_REVISION,
        "expected_version": EXPECTED_VERSION,
        "catalog_http": catalog_status,
        "catalog_model_assets": sorted(catalog_models),
        "catalog_kernel_assets": sorted(catalog_kernels),
        "rooms": rooms,
        "unique_room_count": len(room_hashes),
        "profiles": profiles,
        "aliases": aliases,
        "provider_free_abstention": {
            "http_status": plan_status,
            "decision": plan.get("decision") if isinstance(plan, dict) else None,
            "can_execute": plan.get("can_execute") if isinstance(plan, dict) else None,
            "raw_context_returned": False,
            "raw_context_stored": False,
        },
        "caller_supplied_endpoints_allowed": False,
        "effectors_enabled": False,
        "failures": failures,
        "complete": not failures,
        "truth_label": "MEASURED",
    }


def configure_v4(v3: ModuleType) -> ModuleType:
    v3.SOURCE_REVISION = SOURCE_REVISION
    v3.EXPECTED_VERSION = EXPECTED_VERSION
    v3.USER_AGENT = USER_AGENT
    v3.SMOKE_PATHS = tuple(dict.fromkeys((*v3.SMOKE_PATHS, *INTELLIGENCE_SMOKE_PATHS)))

    prior_verify_frontier = v3.verify_frontier

    def verify_frontier_v4(base: ModuleType) -> dict[str, Any]:
        result = prior_verify_frontier(base)
        intelligence_result = verify_intelligence(base)
        result["schema"] = "szl.vertical-frontier-live-proof/v4"
        result["source_revision"] = SOURCE_REVISION
        result["expected_version"] = EXPECTED_VERSION
        result["intelligence_v4"] = intelligence_result
        result["failures"] = list(result.get("failures", [])) + list(
            intelligence_result.get("failures", [])
        )
        result["complete"] = bool(
            result.get("complete") is True
            and intelligence_result.get("complete") is True
        )
        return result

    v3.verify_frontier = verify_frontier_v4
    return v3


def main() -> int:
    v3 = configure_v4(load_v3())
    return int(v3.main())


if __name__ == "__main__":
    raise SystemExit(main())
