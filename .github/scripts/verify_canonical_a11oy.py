#!/usr/bin/env python3
"""Verify the sole canonical A11oy Space against one exact protected source SHA.

The reusable deployer owns publication, source-variable binding, immutable Hub
commit attestation, byte readback, and smoke routes. This verifier independently
rechecks the application-specific terminal contract and writes one JSON report.
It performs no Hugging Face or GitHub mutation.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

import requests
from huggingface_hub import HfApi

SHA40 = re.compile(r"^[0-9a-f]{40}$")
REPO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
REPORT_SCHEMA = "szl.a11oy-deployment-relock/v4"
REQUIRED_REMOTE_FILES = {"Dockerfile", "console/3d/holographic.html"}
ROUTES = {
    "livez": "/api/livez",
    "build_info": "/api/build-info",
    "brain_capabilities": "/api/a11oy/v1/brain/capabilities",
    "readiness": "/api/a11oy/v1/readiness/tab-matrix?view=summary",
    "holographic": "/static/3d/holographic.html",
}


class RelockError(RuntimeError):
    """The live canonical deployment does not satisfy the reviewed contract."""


def normalize_origin(value: str) -> str:
    parsed = urlsplit(str(value or "").strip())
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path not in ("", "/")
    ):
        raise RelockError("origin must be a credential-free HTTPS origin")
    port = f":{parsed.port}" if parsed.port else ""
    return f"https://{parsed.hostname.lower()}{port}"


def normalize(repo_id: str, origin: str, source_sha: str, variable: str) -> dict[str, str]:
    repo = str(repo_id or "").strip()
    source = str(source_sha or "").strip().lower()
    key = str(variable or "").strip()
    if REPO_ID.fullmatch(repo) is None:
        raise RelockError(f"invalid Space repository id: {repo!r}")
    if SHA40.fullmatch(source) is None:
        raise RelockError(f"source SHA must be an exact 40-character revision: {source!r}")
    if re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", key) is None:
        raise RelockError(f"invalid source-binding variable: {key!r}")
    return {"repo_id": repo, "origin": normalize_origin(origin), "source_sha": source, "variable": key}


def stage_of(info: Any) -> str:
    raw = getattr(getattr(info, "runtime", None), "stage", None)
    raw = getattr(raw, "value", raw)
    return str(raw or "UNKNOWN").split(".")[-1].upper()


def variable_value(value: Any) -> str | None:
    if isinstance(value, Mapping):
        observed = value.get("value")
    else:
        observed = getattr(value, "value", None)
    return str(observed) if observed is not None else None


def require_json(response: requests.Response) -> Mapping[str, Any]:
    if "application/json" not in str(response.headers.get("content-type") or "").lower():
        raise RelockError(f"{response.url} did not return JSON")
    try:
        payload = response.json()
    except ValueError as exc:
        raise RelockError(f"{response.url} returned invalid JSON") from exc
    if not isinstance(payload, Mapping):
        raise RelockError(f"{response.url} JSON is not an object")
    return payload


def validate_route(name: str, response: requests.Response, source_sha: str) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "url": response.url,
        "get_http_status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "bytes": len(response.content),
    }
    if name == "holographic":
        text = response.text
        if (
            "A11oy Holographic Operations" not in text
            or "The estate, observed—not assumed." not in text
        ):
            raise RelockError("holographic surface lacks the reviewed source markers")
        evidence["source_markers"] = True
        return evidence

    payload = require_json(response)
    evidence["json_keys"] = sorted(str(key) for key in payload)[:100]
    evidence["schema"] = payload.get("schema")
    evidence["status"] = payload.get("status") or payload.get("overall_status")
    if name == "livez":
        if payload.get("status") != "LIVE" or payload.get("receipt_minted") is not False:
            raise RelockError("liveness route is not LIVE/read-only")
    elif name == "build_info":
        build = payload.get("build")
        if (
            payload.get("status") != "OBSERVED"
            or payload.get("receipt_minted") is not False
            or not isinstance(build, Mapping)
            or str(build.get("state") or "").upper() != "OBSERVED"
            or str(build.get("revision") or "").lower() != source_sha
        ):
            raise RelockError("build identity is not bound to the exact protected source")
        evidence["source_bound"] = True
    elif name == "brain_capabilities":
        if (
            payload.get("schema") != "szl.brain-capabilities.v1"
            or not isinstance(payload.get("capabilities"), list)
            or not isinstance(payload.get("claim_policy"), Mapping)
        ):
            raise RelockError("Brain capabilities contract is incomplete")
    elif name == "readiness":
        if (
            payload.get("honest") is not True
            or payload.get("view") != "summary"
            or not isinstance(payload.get("matrix_available"), bool)
            or not isinstance(payload.get("probe_verdict_available"), bool)
        ):
            raise RelockError("readiness summary contract is incomplete or dishonest")
    return evidence


def probe_routes(
    session: requests.Session, origin: str, source_sha: str
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for name, path in ROUTES.items():
        url = origin + path
        head = session.head(url, allow_redirects=False, timeout=45)
        get = session.get(url, allow_redirects=False, timeout=60)
        if head.status_code != 200 or get.status_code != 200:
            raise RelockError(
                f"{path} is not operational: HEAD={head.status_code}; GET={get.status_code}"
            )
        evidence = validate_route(name, get, source_sha)
        evidence["head_http_status"] = head.status_code
        output[name] = evidence
    return output


def evaluate_once(
    api: HfApi,
    session: requests.Session,
    contract: Mapping[str, str],
) -> dict[str, Any]:
    info = api.space_info(contract["repo_id"])
    repository_sha = str(getattr(info, "sha", "") or "").lower()
    runtime_sha = str(getattr(getattr(info, "runtime", None), "sha", "") or "").lower()
    stage = stage_of(info)
    sdk = str(getattr(info, "sdk", "") or "").lower()
    private = getattr(info, "private", None)
    if SHA40.fullmatch(repository_sha) is None or SHA40.fullmatch(runtime_sha) is None:
        raise RelockError("canonical Space lacks immutable repository/runtime revisions")
    if repository_sha != runtime_sha:
        raise RelockError(
            f"runtime does not serve the current Space revision: repo={repository_sha}; runtime={runtime_sha}"
        )
    if stage != "RUNNING" or sdk != "docker" or private is not False:
        raise RelockError(
            f"canonical Space state invalid: stage={stage}; sdk={sdk}; private={private}"
        )

    remote_files = set(api.list_repo_files(contract["repo_id"], repo_type="space"))
    missing = sorted(REQUIRED_REMOTE_FILES - remote_files)
    if missing:
        raise RelockError(f"canonical Space is missing reviewed files: {missing}")

    variables = api.get_space_variables(contract["repo_id"])
    if not isinstance(variables, Mapping):
        raise RelockError("Space variable readback did not return a mapping")
    observed_source = variable_value(variables.get(contract["variable"]))
    if observed_source != contract["source_sha"]:
        raise RelockError(
            f"source-binding variable mismatch: expected={contract['source_sha']}; observed={observed_source}"
        )

    routes = probe_routes(session, contract["origin"], contract["source_sha"])
    clones = {f"SZLHOLDINGS/a11oy-clone-{index}": False for index in range(1, 5)}
    for clone_id in tuple(clones):
        clones[clone_id] = bool(api.repo_exists(clone_id, repo_type="space"))
    if any(clones.values()):
        raise RelockError(f"historical A11oy clone reappeared: {clones}")

    return {
        "schema": REPORT_SCHEMA,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "PASS",
        "ok": True,
        "public": True,
        "sdk": sdk,
        "runtime_stage": stage,
        "github_source_sha": contract["source_sha"],
        "source_revision_variable": {
            "key": contract["variable"],
            "observed": observed_source,
            "matched": True,
        },
        "hf_repository_sha": repository_sha,
        "hf_runtime_sha": runtime_sha,
        "managed_file_count": len(remote_files),
        "dockerfile_present": True,
        "holographic_source_present": True,
        "clone_presence": clones,
        "routes": routes,
        "boundaries": [
            "This verifier performs only Hugging Face metadata reads and same-host HEAD/GET probes.",
            "No receipt is minted by liveness or build identity routes.",
            "No Space, model, dataset, hardware, visibility, branch, training, weight, or promotion state is changed.",
        ],
    }


def evaluate(
    api: HfApi,
    session: requests.Session,
    contract: Mapping[str, str],
    attempts: int,
    retry_seconds: int,
) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            report = evaluate_once(api, session, contract)
            report["attempts"] = attempt
            return report
        except Exception as exc:  # noqa: BLE001
            last = exc
            if attempt < max(1, attempts):
                time.sleep(max(0, retry_seconds))
    assert last is not None
    raise last


def write_report(path: str, report: Mapping[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--origin", required=True)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--source-variable", default="SZL_GIT_SHA")
    parser.add_argument("--output", required=True)
    parser.add_argument("--attempts", type=int, default=12)
    parser.add_argument("--retry-seconds", type=int, default=10)
    args = parser.parse_args()
    contract = normalize(args.repo_id, args.origin, args.source_sha, args.source_variable)
    token = os.environ.get("HF_TOKEN")
    if not token:
        failure = {
            "schema": REPORT_SCHEMA,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "FAIL",
            "ok": False,
            "github_source_sha": contract["source_sha"],
            "fatal": "RelockError: HF_TOKEN is required for canonical Space metadata readback",
        }
        write_report(args.output, failure)
        print(json.dumps(failure, indent=2, sort_keys=True))
        return 2
    api = HfApi(token=token)
    session = requests.Session()
    session.headers.update(
        {
            "Accept": "application/json,text/html;q=0.9,*/*;q=0.8",
            "Cache-Control": "no-cache, no-store, max-age=0",
            "Pragma": "no-cache",
            "User-Agent": "szl-canonical-a11oy-relock/4",
        }
    )
    try:
        report = evaluate(api, session, contract, args.attempts, args.retry_seconds)
        code = 0
    except Exception as exc:  # noqa: BLE001
        report = {
            "schema": REPORT_SCHEMA,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "FAIL",
            "ok": False,
            "github_source_sha": contract["source_sha"],
            "fatal": f"{type(exc).__name__}: {exc}",
        }
        code = 1
    write_report(args.output, report)
    print(json.dumps(report, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
