#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Deploy the exact SZL combined vertical runtime through the canonical HF writer.

The deployment reuses SZL's pinned Dockerfile-derived controller. It never
deletes a Space, never rotates an existing signing key, and never prints secret
values. After deployment it exercises every required bounded official-source
connector through the live runtime and records only source-safe receipts.
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

SOURCE_REPOSITORY = "szl-holdings/vertical-services"
SOURCE_REVISION = "dfc16a3c89e0b4bc070dc7e8ae2415e9bcb04eab"
EXPECTED_VERSION = "2.0.0"
HF_REPOSITORY = "SZLHOLDINGS/vertical-services"
ORIGIN = "https://szlholdings-vertical-services.hf.space"
SOURCE_VARIABLE = "SZL_SOURCE_REVISION"
SIGNING_SECRET = "SENTRA_SIGNING_KEY"
RECEIPT_PATH = Path("hf-vertical-services-receipt.json")

CONTROLLER_REPOSITORY = "szl-holdings/.github"
CONTROLLER_REVISION = "c889276e51e7d954c4bba8b216f86fc7577721fa"
CONTROLLER_PATH = ".github/scripts/hf_deploy_from_dockerfile.py"
CONTROLLER_BLOB_SHA1 = "9d5b90b8bbf04e6d46ef0f971fc65604e1323b1b"
USER_AGENT = "SZLHOLDINGS-Canonical-Vertical-Services-Publisher/2.0"

CANONICAL_VERTICALS = (
    "sentra",
    "lyte",
    "killinchu",
    "finance",
    "terra",
    "counsel",
)

LIVE_PROBES: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("sentra", "cisa-kev", {"limit": 3}),
    ("lyte", "github-actions", {"repository": "vertical-services", "limit": 10}),
    ("killinchu", "noaa-ais-2025", {}),
    ("finance", "sec-submissions", {"cik": "320193", "limit": 3}),
    ("terra", "nyc-pluto", {"borough": "MN", "limit": 1}),
    ("counsel", "federal-register", {"limit": 3}),
)

SMOKE_PATHS = (
    "/",
    "/healthz",
    "/readyz",
    "/api/build-info",
    "/api/catalog",
    "/api/verticals",
    "/sentra/healthz",
    "/lyte/healthz",
    "/killinchu/healthz",
    "/vessels/healthz",
    "/finance/healthz",
    "/terra/healthz",
    "/counsel/healthz",
    "/api/verticals/sentra/anatomy",
    "/api/verticals/lyte/formulas",
    "/api/verticals/killinchu/connectors",
    "/api/verticals/finance/readyz",
    "/api/verticals/terra/anatomy",
    "/api/verticals/counsel/formulas",
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
            + " ".join(command[:4])
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
        ["git", "-C", str(destination), "checkout", "--quiet", "--detach", "FETCH_HEAD"]
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
    header = f"blob {len(payload)}\0".encode("ascii")
    return hashlib.sha1(header + payload).hexdigest()


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
    api.create_repo(
        repo_id=HF_REPOSITORY,
        repo_type="space",
        space_sdk="docker",
        exist_ok=True,
        private=False,
    )
    api.auth_check(repo_id=HF_REPOSITORY, repo_type="space", write=True)

    configured = set(api.get_space_secrets(repo_id=HF_REPOSITORY))
    if SIGNING_SECRET in configured:
        secret_action = "preserved"
    else:
        api.add_space_secret(
            repo_id=HF_REPOSITORY,
            key=SIGNING_SECRET,
            value=secrets.token_hex(32),
            description=(
                "Persistent HMAC key for Sentra and Killinchu defense verdict "
                "receipts; generated once by the canonical a11oy writer."
            ),
        )
        secret_action = "created"

    api.add_space_variable(
        repo_id=HF_REPOSITORY,
        key=SOURCE_VARIABLE,
        value=SOURCE_REVISION,
        description="Exact GitHub revision for fail-closed runtime binding.",
    )
    return {
        "secret": SIGNING_SECRET,
        "secret_action": secret_action,
        "secret_value_recorded": False,
        "source_variable": SOURCE_VARIABLE,
        "source_variable_value": SOURCE_REVISION,
    }


def request_json(
    path: str,
    *,
    method: str = "GET",
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    attempts: int = 3,
) -> tuple[int, Any]:
    separator = "&" if "?" in path else "?"
    url = f"{ORIGIN}{path}{separator}szl_verify={time.time_ns()}"
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


def get_json(path: str) -> tuple[int, Any]:
    return request_json(path)


def probe_live_connectors() -> dict[str, Any]:
    session = secrets.token_urlsafe(32)
    headers = {"X-SZL-Session": session}
    report: dict[str, Any] = {
        "schema": "szl.live-connector-probe/v2",
        "base_url": ORIGIN,
        "observed_at": time.time(),
        "probes": [],
        "session_token_recorded": False,
        "truth_label": "MEASURED",
    }
    failures: list[str] = []

    for vertical, connector, parameters in LIVE_PROBES:
        path = f"/api/verticals/{vertical}/connectors/{connector}/fetch"
        status, body = request_json(
            path,
            method="POST",
            payload={"parameters": parameters, "force_refresh": True},
            headers=headers,
        )
        item: dict[str, Any] = {
            "vertical": vertical,
            "connector": connector,
            "path": path,
            "http_status": status,
        }
        if status != 200 or not isinstance(body, dict):
            item["state"] = "FAILED"
            item["body_excerpt"] = str(body)[:500]
            failures.append(f"{vertical}/{connector}: HTTP {status}")
        else:
            receipt = body.get("receipt", {})
            item.update(
                {
                    "state": receipt.get("state"),
                    "receipt_id": receipt.get("receipt_id"),
                    "payload_sha256": receipt.get("payload_sha256"),
                    "source_url": receipt.get("source_url"),
                    "signal": body.get("signal"),
                    "cache": body.get("cache"),
                }
            )
            if (
                item["state"] != "OBSERVED"
                or not isinstance(item["receipt_id"], str)
                or len(item["receipt_id"]) != 64
                or not isinstance(item["payload_sha256"], str)
                or len(item["payload_sha256"]) != 64
            ):
                failures.append(f"{vertical}/{connector}: invalid observation receipt")
        report["probes"].append(item)

    vertical_readiness: dict[str, Any] = {}
    for vertical in CANONICAL_VERTICALS:
        status, body = request_json(
            f"/api/verticals/{vertical}/readyz",
            headers=headers,
        )
        if status != 200 or not isinstance(body, dict):
            failures.append(f"{vertical}: readiness HTTP {status}")
            vertical_readiness[vertical] = {
                "http_status": status,
                "body_excerpt": str(body)[:500],
            }
            continue
        vertical_readiness[vertical] = {
            "http_status": status,
            "ready": body.get("ready"),
            "status": body.get("status"),
            "live_data": body.get("live_data"),
            "build": body.get("build"),
            "lambda_advisory": body.get("lambda_advisory"),
        }
        if body.get("ready") is not True:
            failures.append(f"{vertical}: readiness did not close")
        if not body.get("live_data", {}).get("observed_in_scope"):
            failures.append(f"{vertical}: required live observation not visible")

    root_status, root = request_json("/readyz", headers=headers)
    report["vertical_readiness"] = vertical_readiness
    report["root_readiness"] = {
        "http_status": root_status,
        "body": root,
    }
    if root_status != 200 or not isinstance(root, dict) or root.get("ready") is not True:
        failures.append(f"root readiness: HTTP {root_status}")

    report["status"] = "PASS" if not failures else "FAIL"
    report["failures"] = failures
    if failures:
        raise RuntimeError("live official-source connector probe did not close: " + "; ".join(failures))
    return report


def verify_contract() -> dict[str, Any]:
    health_status, health = get_json("/healthz")
    ready_status, ready = get_json("/readyz")
    build_status, build = get_json("/api/build-info")
    catalog_status, catalog = get_json("/api/catalog")
    vertical_catalog_status, vertical_catalog = get_json("/api/verticals")

    ready_verticals = ready.get("verticals", {}) if isinstance(ready, dict) else {}
    expected = set(CANONICAL_VERTICALS)
    requirements = (
        "source_bound",
        "observation_store_writable",
        "required_connector_contracts_ready",
        "persistent_signing_key",
        "formula_registry_bound",
    )
    vertical_contracts: dict[str, bool] = {}
    live_observations: dict[str, bool] = {}
    for vertical in CANONICAL_VERTICALS:
        item = ready_verticals.get(vertical, {})
        item_requirements = item.get("requirements", {})
        vertical_contracts[vertical] = bool(
            item.get("ready") is True
            and item.get("status") == "READY"
            and all(item_requirements.get(name) is True for name in requirements)
        )
        live_observations[vertical] = bool(
            item.get("live_data", {}).get("observed_in_scope") is True
        )

    catalog_engines = catalog.get("engines", {}) if isinstance(catalog, dict) else {}
    registered_verticals = (
        vertical_catalog.get("verticals", {})
        if isinstance(vertical_catalog, dict)
        else {}
    )
    aliases = vertical_catalog.get("aliases", {}) if isinstance(vertical_catalog, dict) else {}

    complete = (
        health_status == 200
        and health.get("ok") is True
        and health.get("version") == EXPECTED_VERSION
        and health.get("engines") == list(CANONICAL_VERTICALS)
        and health.get("sentra_signing_key_source") == "env"
        and health.get("official_source_connectors_wired") is True
        and health.get("compatibility_routes", {}).get("/vessels", {}).get("canonical")
        == "/killinchu"
        and ready_status == 200
        and ready.get("ready") is True
        and ready.get("version") == EXPECTED_VERSION
        and set(ready_verticals) == expected
        and all(vertical_contracts.values())
        and all(live_observations.values())
        and ready.get("build", {}).get("state") == "OBSERVED"
        and ready.get("build", {}).get("revision") == SOURCE_REVISION
        and ready.get("store", {}).get("writable") is True
        and build_status == 200
        and build.get("schema") == "szl.build-info/v1"
        and build.get("version") == EXPECTED_VERSION
        and build.get("source_repository") == SOURCE_REPOSITORY
        and build.get("hf_repository") == HF_REPOSITORY
        and build.get("build", {}).get("state") == "OBSERVED"
        and build.get("build", {}).get("revision") == SOURCE_REVISION
        and build.get("source_binding", {}).get("bindings_agree") is True
        and build.get("receipt_minted") is False
        and catalog_status == 200
        and set(catalog_engines) == expected
        and catalog.get("vessels_independent_vertical") is False
        and catalog.get("vessels_canonical_home") == "SZLHOLDINGS/killinchu"
        and catalog.get("official_source_connectors_wired") is True
        and catalog.get("live_observations_require_explicit_fetch") is True
        and catalog.get("effectors_enabled") is False
        and vertical_catalog_status == 200
        and vertical_catalog.get("schema") == "szl.vertical-catalog/v2"
        and set(registered_verticals) == expected
        and aliases.get("vessels") == "killinchu"
        and vertical_catalog.get("vessels_independent_vertical") is False
    )
    return {
        "complete": complete,
        "health_http": health_status,
        "health": health,
        "ready_http": ready_status,
        "ready": ready,
        "vertical_contracts": vertical_contracts,
        "live_observations": live_observations,
        "build_info_http": build_status,
        "build_info": build,
        "catalog_http": catalog_status,
        "catalog": catalog,
        "vertical_catalog_http": vertical_catalog_status,
        "vertical_catalog": vertical_catalog,
    }


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
            "deploy/Dockerfile",
            "--source-revision-file",
            "deploy/source_revision.txt",
            "--include-readme",
            "true",
            "--smoke-paths",
            smoke_json,
            "--manifest-out",
            str(manifest),
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
            "20",
        ]
    )


def main() -> int:
    token, token_source = token_from_env()
    os.environ["HF_TOKEN"] = token
    receipt: dict[str, Any] = {
        "schema": "szl.hf-vertical-services-publication/v2",
        "generated_at": utc_now(),
        "source_repository": SOURCE_REPOSITORY,
        "source_revision": SOURCE_REVISION,
        "expected_version": EXPECTED_VERSION,
        "canonical_verticals": list(CANONICAL_VERTICALS),
        "hf_repository": HF_REPOSITORY,
        "origin": ORIGIN,
        "controller_repository": CONTROLLER_REPOSITORY,
        "controller_revision": CONTROLLER_REVISION,
        "controller_blob_sha1": CONTROLLER_BLOB_SHA1,
        "token_source_name": token_source,
        "token_value_recorded": False,
        "delete_operations": 0,
        "vessels_space_retained": True,
        "complete": False,
    }
    try:
        api = HfApi(token=token)
        receipt["configuration"] = ensure_runtime_configuration(api)
        with tempfile.TemporaryDirectory(prefix="szl-vertical-services-") as td:
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
        receipt["live_connector_probe"] = probe_live_connectors()
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
