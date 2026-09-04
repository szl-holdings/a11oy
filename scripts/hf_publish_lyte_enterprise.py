#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Publish the exact source-owned Lyte Enterprise runtime through A11oy.

This publisher is intentionally narrow. It deploys the tested default-branch
revision of ``szl-holdings/lyte-services`` to the already-existing
``SZLHOLDINGS/lyte`` Space through the pinned Dockerfile-derived controller.
It does not create or delete a Space, does not copy a token into another
repository, does not touch Sentra secrets, and never records credential values.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from huggingface_hub import HfApi

SOURCE_REPOSITORY = "szl-holdings/lyte-services"
SOURCE_REVISION = "f5e85a57cd616c0d2b216e2c5f1686485b8c43e8"
EXPECTED_VERSION = "3.0.0"
HF_REPOSITORY = "SZLHOLDINGS/lyte"
ORIGIN = "https://szlholdings-lyte.hf.space"
SOURCE_VARIABLE = "LYTE_SOURCE_REVISION"
RECEIPT_PATH = Path("hf-lyte-enterprise-receipt.json")

CONTROLLER_REPOSITORY = "szl-holdings/.github"
CONTROLLER_REVISION = "c889276e51e7d954c4bba8b216f86fc7577721fa"
CONTROLLER_PATH = ".github/scripts/hf_deploy_from_dockerfile.py"
CONTROLLER_BLOB_SHA1 = "9d5b90b8bbf04e6d46ef0f971fc65604e1323b1b"
USER_AGENT = "SZLHOLDINGS-Lyte-Enterprise-Publisher/3.0"

SMOKE_PATHS = (
    "/",
    "/healthz",
    "/readyz",
    "/api/build-info",
    "/.well-known/szl-source.json",
    "/metrics",
    "/api/lyte/v3/catalog",
    "/api/lyte/v3/capabilities",
    "/api/lyte/v3/anatomy",
    "/api/lyte/v3/formulas",
    "/api/lyte/v3/sources",
    "/api/lyte/v3/scenario",
    "/api/cells",
    "/api/jobs",
    "/api/roadmap",
)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def token_from_env() -> tuple[str, str]:
    for name in (
        "HF_ORG_TOKEN",
        "HF_WRITE_TOKEN",
        "HF_TOKEN",
        "HUGGINGFACE_TOKEN",
        "HUGGING_FACE_HUB_TOKEN",
    ):
        value = os.getenv(name, "").strip()
        if value:
            return value, name
    raise RuntimeError("no Hugging Face write token available to canonical writer")


def run_checked(command: list[str], *, cwd: Path | None = None) -> None:
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode:
        raise RuntimeError(
            f"command failed with exit {result.returncode}: "
            + " ".join(command[:5])
        )


def checkout_exact_source(destination: Path) -> None:
    run_checked(["git", "init", "--quiet", str(destination)])
    run_checked(
        [
            "git",
            "-C",
            str(destination),
            "remote",
            "add",
            "origin",
            f"https://github.com/{SOURCE_REPOSITORY}.git",
        ]
    )
    run_checked(
        [
            "git",
            "-C",
            str(destination),
            "fetch",
            "--quiet",
            "--depth=1",
            "origin",
            SOURCE_REVISION,
        ]
    )
    run_checked(
        [
            "git",
            "-C",
            str(destination),
            "checkout",
            "--quiet",
            "--detach",
            "FETCH_HEAD",
        ]
    )
    observed = subprocess.check_output(
        ["git", "-C", str(destination), "rev-parse", "HEAD"],
        text=True,
    ).strip()
    if observed != SOURCE_REVISION:
        raise RuntimeError(
            f"source checkout mismatch: expected {SOURCE_REVISION}, observed {observed}"
        )


def git_blob_sha1(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


def fetch_pinned_controller(destination: Path) -> None:
    url = (
        f"https://raw.githubusercontent.com/{CONTROLLER_REPOSITORY}/"
        f"{CONTROLLER_REVISION}/{CONTROLLER_PATH}"
    )
    request = urllib.request.Request(
        url,
        headers={"Cache-Control": "no-cache", "User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = response.read()
        if response.status != 200:
            raise RuntimeError(f"controller fetch failed: HTTP {response.status}")
    observed = git_blob_sha1(payload)
    if observed != CONTROLLER_BLOB_SHA1:
        raise RuntimeError(
            f"controller blob mismatch: expected {CONTROLLER_BLOB_SHA1}, "
            f"observed {observed}"
        )
    destination.write_bytes(payload)


def ensure_runtime_configuration(api: HfApi) -> dict[str, Any]:
    """Require the existing Space and bind only a non-secret source variable."""
    api.auth_check(repo_id=HF_REPOSITORY, repo_type="space", write=True)
    api.add_space_variable(
        repo_id=HF_REPOSITORY,
        key=SOURCE_VARIABLE,
        value=SOURCE_REVISION,
        description="Exact tested GitHub revision for Lyte fail-closed source binding.",
    )
    return {
        "space_preexisted": True,
        "space_created": False,
        "source_variable": SOURCE_VARIABLE,
        "source_variable_value": SOURCE_REVISION,
        "secret_values_read": False,
        "secret_values_written": False,
        "sentra_signing_key_touched": False,
    }


def request_json(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    attempts: int = 4,
) -> tuple[int, Any]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    request_headers = {
        "Accept": "application/json",
        "Cache-Control": "no-cache",
        "User-Agent": USER_AGENT,
        **(headers or {}),
    }
    if body is not None:
        request_headers["Content-Type"] = "application/json"
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        separator = "&" if "?" in path else "?"
        url = f"{ORIGIN}{path}{separator}szl_verify={time.time_ns()}"
        request = urllib.request.Request(
            url,
            data=body,
            method=method,
            headers=request_headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=75) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            if exc.code < 500:
                try:
                    parsed: Any = json.loads(response_body)
                except json.JSONDecodeError:
                    parsed = {"body_excerpt": response_body[:500]}
                return exc.code, parsed
            last_error = exc
        except Exception as exc:
            last_error = exc
        if attempt < attempts:
            time.sleep(2 ** (attempt - 1))
    raise RuntimeError(
        f"live request did not converge: {method} {path}: "
        f"{type(last_error).__name__ if last_error else 'UnknownError'}"
    )


def request_text(path: str, *, attempts: int = 4) -> tuple[int, str]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        separator = "&" if "?" in path else "?"
        request = urllib.request.Request(
            f"{ORIGIN}{path}{separator}szl_verify={time.time_ns()}",
            headers={
                "Accept": "text/html",
                "Cache-Control": "no-cache",
                "User-Agent": USER_AGENT,
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.status, response.read().decode(
                    "utf-8", errors="replace"
                )
        except Exception as exc:
            last_error = exc
        if attempt < attempts:
            time.sleep(2 ** (attempt - 1))
    raise RuntimeError(
        "live HTML request did not converge: "
        f"{type(last_error).__name__ if last_error else 'UnknownError'}"
    )


def deploy_with_controller(source: Path, controller: Path, manifest: Path) -> None:
    smoke_json = json.dumps(SMOKE_PATHS, separators=(",", ":"))
    base = [
        sys.executable,
        str(controller),
        "--repo-root",
        str(source),
        "--github-repo",
        SOURCE_REPOSITORY,
        "--hf-repo",
        HF_REPOSITORY,
    ]
    run_checked(
        base
        + [
            "--ref",
            SOURCE_REVISION,
            "--source-sha",
            SOURCE_REVISION,
            "--dockerfile-path",
            "Dockerfile",
            "--include-readme",
            "true",
            "--smoke-paths",
            smoke_json,
            "--manifest-out",
            str(manifest),
            "--prune",
            "--require-default-branch-tip",
        ]
    )
    run_checked(
        [
            sys.executable,
            str(controller),
            "--restart-space",
            "--manifest",
            str(manifest),
            "--hf-repo",
            HF_REPOSITORY,
        ]
    )
    run_checked(
        [
            sys.executable,
            str(controller),
            "--attest",
            "--manifest",
            str(manifest),
            "--hf-repo",
            HF_REPOSITORY,
            "--wait-running",
            "1200",
            "--smoke-retries",
            "24",
        ]
    )


def verify_contract() -> dict[str, Any]:
    health_status, health = request_json("/healthz")
    ready_status, ready = request_json("/readyz")
    build_status, build = request_json("/api/build-info")
    catalog_status, catalog = request_json("/api/lyte/v3/catalog")
    capability_status, capabilities = request_json("/api/lyte/v3/capabilities")
    scenario_status, scenario = request_json("/api/lyte/v3/scenario")
    root_status, root = request_text("/")

    session = secrets.token_urlsafe(32)
    session_headers = {"X-SZL-Session": session}
    scenario_inputs = scenario.get("inputs", {}) if isinstance(scenario, dict) else {}
    analysis_status, analysis = request_json(
        "/api/lyte/v3/analyze",
        method="POST",
        payload=scenario_inputs.get("analysis", {}),
        headers=session_headers,
    )
    journey_status, journey = request_json(
        "/api/lyte/v3/journeys/analyze",
        method="POST",
        payload=scenario_inputs.get("journey", {}),
        headers=session_headers,
    )
    analysis_receipt = (
        analysis.get("receipt", {}) if isinstance(analysis, dict) else {}
    )
    journey_receipt = journey.get("receipt", {}) if isinstance(journey, dict) else {}
    evidence_receipt = str(analysis_receipt.get("receipt_id") or "")

    memory_status, memory = request_json(
        "/api/lyte/v3/second-brain?limit=20",
        headers=session_headers,
    )
    ask_status, ask = request_json(
        "/api/lyte/v3/ask",
        method="POST",
        payload={"question": "Which service is consuming the most error budget?"},
        headers=session_headers,
    )
    hatun_status, hatun = request_json(
        "/api/lyte/v3/hatun/evaluate",
        method="POST",
        payload={
            "intent": "review the source-bound checkout degradation evidence",
            "requested_action": "incident.review",
            "axes": {
                "evidence": 0.96,
                "safety": 0.94,
                "policy": 0.95,
                "reversibility": 0.92,
            },
            "evidence_receipt_ids": [evidence_receipt],
        },
        headers=session_headers,
    )
    source_status, source_observation = request_json(
        "/api/lyte/v3/github/lyte-services?limit=5",
        headers=session_headers,
    )

    memory_records = memory.get("memory", []) if isinstance(memory, dict) else []
    root_contract = {
        "http_status": root_status,
        "product_marker": 'data-lyte="signal-lattice-v3"' in root,
        "signal_lattice": "SIGNAL LATTICE" in root,
        "ask_lyte": "ASK LYTE" in root,
        "reduced_motion": "@media(prefers-reduced-motion:reduce)" in root,
        "forced_colors": "@media(forced-colors:active)" in root,
        "viewport_fit": "viewport-fit=cover" in root,
    }
    receipt_contracts = {
        "analysis": bool(
            analysis_status == 200
            and len(str(analysis_receipt.get("receipt_id") or "")) == 64
            and analysis_receipt.get("raw_session_token_recorded") is False
            and analysis.get("effectors_enabled") is False
        ),
        "journey": bool(
            journey_status == 200
            and len(str(journey_receipt.get("receipt_id") or "")) == 64
            and journey_receipt.get("raw_session_token_recorded") is False
            and journey.get("effectors_enabled") is False
        ),
    }
    complete = bool(
        health_status == 200
        and isinstance(health, dict)
        and health.get("ok") is True
        and health.get("service") == "lyte-signal-lattice"
        and health.get("version") == EXPECTED_VERSION
        and health.get("engine_imported") is True
        and health.get("effectors_enabled") is False
        and ready_status == 200
        and isinstance(ready, dict)
        and ready.get("ready") is True
        and ready.get("version") == EXPECTED_VERSION
        and ready.get("build", {}).get("state") == "OBSERVED"
        and ready.get("build", {}).get("revision") == SOURCE_REVISION
        and ready.get("source_binding", {}).get("bindings_agree") is True
        and build_status == 200
        and isinstance(build, dict)
        and build.get("schema") == "szl.build-info/v1"
        and build.get("source_repository") == SOURCE_REPOSITORY
        and build.get("version") == EXPECTED_VERSION
        and build.get("build", {}).get("state") == "OBSERVED"
        and build.get("build", {}).get("revision") == SOURCE_REVISION
        and build.get("source_binding", {}).get("bindings_agree") is True
        and catalog_status == 200
        and isinstance(catalog, dict)
        and len(catalog.get("lenses", [])) == 6
        and catalog.get("effectors_enabled") is False
        and capability_status == 200
        and isinstance(capabilities, dict)
        and capabilities.get("service_observability") is True
        and capabilities.get("customer_journey_intelligence") is True
        and capabilities.get("ai_agent_operations") is True
        and capabilities.get("automatic_remediation") is False
        and capabilities.get("effectors_enabled") is False
        and scenario_status == 200
        and isinstance(scenario, dict)
        and scenario.get("truth_label") == "SAMPLE"
        and scenario.get("demo_mode") is True
        and scenario.get("effectors_enabled") is False
        and all(root_contract.values())
        and all(receipt_contracts.values())
        and memory_status == 200
        and isinstance(memory, dict)
        and len(memory_records) >= 2
        and memory.get("raw_session_token_recorded") is False
        and memory.get("effectors_enabled") is False
        and ask_status == 200
        and isinstance(ask, dict)
        and ask.get("truth_label") == "MEASURED"
        and bool(ask.get("evidence_receipt_ids"))
        and ask.get("causality_claimed") is False
        and ask.get("effectors_enabled") is False
        and hatun_status == 200
        and isinstance(hatun, dict)
        and hatun.get("decision") == "REVIEW"
        and hatun.get("can_authorize") is False
        and hatun.get("can_execute") is False
        and hatun.get("effectors_enabled") is False
        and hatun.get("session_token_recorded") is False
        and hatun.get("credential_material_recorded") is False
        and source_status == 200
        and isinstance(source_observation, dict)
        and source_observation.get("truth_label") == "REPORTED"
        and len(
            str(source_observation.get("receipt", {}).get("receipt_id") or "")
        )
        == 64
        and source_observation.get("session_token_recorded") is False
    )
    return {
        "complete": complete,
        "health_http": health_status,
        "health": health,
        "ready_http": ready_status,
        "ready": ready,
        "build_info_http": build_status,
        "build_info": build,
        "catalog_http": catalog_status,
        "catalog": catalog,
        "capabilities_http": capability_status,
        "capabilities": capabilities,
        "scenario_http": scenario_status,
        "scenario": {
            "schema": scenario.get("schema") if isinstance(scenario, dict) else None,
            "truth_label": scenario.get("truth_label") if isinstance(scenario, dict) else None,
            "demo_mode": scenario.get("demo_mode") if isinstance(scenario, dict) else None,
            "effectors_enabled": scenario.get("effectors_enabled") if isinstance(scenario, dict) else None,
        },
        "root": root_contract,
        "receipt_contracts": receipt_contracts,
        "second_brain_http": memory_status,
        "second_brain_count": len(memory_records),
        "ask_http": ask_status,
        "ask": ask,
        "hatun_http": hatun_status,
        "hatun": hatun,
        "github_source_http": source_status,
        "github_source": source_observation,
        "session_token_recorded": False,
        "secret_values_recorded": False,
        "delete_operations": 0,
    }


def main() -> int:
    token, token_source = token_from_env()
    os.environ["HF_TOKEN"] = token
    receipt: dict[str, Any] = {
        "schema": "szl.hf-lyte-enterprise-publication/v3",
        "generated_at": utc_now(),
        "source_repository": SOURCE_REPOSITORY,
        "source_revision": SOURCE_REVISION,
        "expected_version": EXPECTED_VERSION,
        "hf_repository": HF_REPOSITORY,
        "origin": ORIGIN,
        "controller_repository": CONTROLLER_REPOSITORY,
        "controller_revision": CONTROLLER_REVISION,
        "controller_blob_sha1": CONTROLLER_BLOB_SHA1,
        "token_source_name": token_source,
        "token_value_recorded": False,
        "secret_values_recorded": False,
        "sentra_signing_key_touched": False,
        "space_created": False,
        "delete_operations": 0,
        "complete": False,
    }
    try:
        api = HfApi(token=token)
        receipt["configuration"] = ensure_runtime_configuration(api)
        with tempfile.TemporaryDirectory(prefix="szl-lyte-enterprise-") as td:
            root = Path(td)
            source = root / "source"
            controller = root / "hf_deploy_from_dockerfile.py"
            manifest = root / "manifest.json"
            checkout_exact_source(source)
            fetch_pinned_controller(controller)
            deploy_with_controller(source, controller, manifest)
            receipt["deployment_manifest"] = json.loads(
                manifest.read_text(encoding="utf-8")
            )
        receipt["verification"] = verify_contract()
        receipt["complete"] = receipt["verification"]["complete"]
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        receipt["finished_at"] = utc_now()
        RECEIPT_PATH.write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
