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
import math
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
HOLOGRAPHIC_SOURCE_PATH = "static/3d/holographic.html"
HOLOGRAPHIC_SOURCE_MARKERS = (
    "A11oy Holographic Operations",
    "The estate, observed—not assumed.",
)
REQUIRED_REMOTE_FILES = {"Dockerfile", HOLOGRAPHIC_SOURCE_PATH}
CANONICAL_SIGNING_SECRET = "SZL_COSIGN_PRIVATE_PEM"
CANONICAL_SERIES_A_BUCKET = "SZLHOLDINGS/szl-evidence"
SERIES_A_VARIABLES = {
    "A11OY_REQUIRE_PERSISTENT_SIGNING": "1",
    "A11OY_REQUIRE_PERSISTENT_STORAGE": "1",
    "A11OY_SERIES_A_DB": "/data/a11oy/series-a/control-plane-v2.sqlite3",
    "A11OY_SERIES_A_REQUIRE_MOUNT": "/data",
    "A11OY_SERIES_A_STARTUP_REFRESH": "1",
    "A11OY_SERIES_A_REFRESH_INTERVAL_SECONDS": "240",
    "A11OY_SERIES_A_SQLITE_JOURNAL": "DELETE",
    "SZL_ENERGY_LEDGER_PATH": "/data/a11oy/energy/ledger.jsonl",
    "SZL_LAKE_DIR": "/data/a11oy/khipu",
}
ROUTES = {
    "livez": "/api/livez",
    "build_info": "/api/build-info",
    "brain_capabilities": "/api/a11oy/v1/brain/capabilities",
    "readiness": "/api/a11oy/v1/readiness/tab-matrix?view=summary",
    "series_a_status": "/api/a11oy/v1/series-a/status",
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


def immutable_runtime_revision(info: Any) -> tuple[str, str]:
    """Return the immutable runtime revision and the exact SDK evidence path.

    ``huggingface_hub`` has exposed this value both as ``runtime.sha`` and as
    ``runtime.raw["sha"]`` across released versions. Accept only those explicit
    metadata fields and only an exact SHA-1; never infer a runtime revision.
    """
    runtime = getattr(info, "runtime", None)
    direct = str(getattr(runtime, "sha", "") or "").strip().lower()
    if SHA40.fullmatch(direct):
        return direct, "space_info.runtime.sha"

    raw = getattr(runtime, "raw", None)
    raw_sha = raw.get("sha") if isinstance(raw, Mapping) else None
    candidate = str(raw_sha or "").strip().lower()
    if SHA40.fullmatch(candidate):
        return candidate, "space_info.runtime.raw.sha"
    return "", "UNKNOWN"


def variable_value(value: Any) -> str | None:
    if isinstance(value, Mapping):
        observed = value.get("value")
    else:
        observed = getattr(value, "value", None)
    return str(observed) if observed is not None else None


def volume_record(value: Any) -> dict[str, Any]:
    def field(name: str, default: Any = None) -> Any:
        if isinstance(value, Mapping):
            return value.get(name, default)
        return getattr(value, name, default)

    volume_type = field("type", "")
    volume_type = getattr(volume_type, "value", volume_type)
    return {
        "type": str(volume_type),
        "source": str(field("source", "")),
        "mount_path": str(field("mount_path", "")),
        "read_only": bool(field("read_only", False)),
        "path": field("path"),
        "revision": field("revision"),
    }


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


def validate_readiness_summary(
    payload: Mapping[str, Any],
    source_sha: str,
    *,
    expected_origin: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    if (
        payload.get("honest") is not True
        or payload.get("view") != "summary"
        or payload.get("available") is not True
        or payload.get("matrix_available") is not True
        or payload.get("probe_verdict_available") is not True
        or payload.get("verdict_source_revision") != source_sha
    ):
        raise RelockError("readiness summary is unavailable or source-unbound")
    if normalize_origin(payload.get("verdict_base")) != normalize_origin(
        expected_origin
    ):
        raise RelockError("readiness verdict was not probed at the canonical origin")

    checked_at = payload.get("verdict_checked_at")
    if (
        not isinstance(checked_at, str)
        or re.fullmatch(
            r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z",
            checked_at,
        )
        is None
    ):
        raise RelockError("readiness verdict lacks a strict UTC observation time")
    try:
        checked = datetime.fromisoformat(checked_at[:-1] + "+00:00")
    except ValueError as exc:
        raise RelockError(
            "readiness verdict observation time is invalid"
        ) from exc
    current = now or datetime.now(timezone.utc)
    age_seconds = (current - checked).total_seconds()
    if age_seconds < 0 or age_seconds > 86400:
        raise RelockError("readiness verdict is future-dated or stale")

    summary = payload.get("verdict_summary")
    if not isinstance(summary, Mapping):
        raise RelockError("readiness verdict summary is unavailable")
    fields = (
        "endpoints",
        "ok",
        "skippedStateChanging",
        "lies",
        "unreachable",
        "throttled",
    )
    counts = [summary.get(field) for field in fields]
    if not all(
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
        for value in counts
    ):
        raise RelockError("readiness verdict counts are incomplete or invalid")
    endpoints, _, skipped, *_ = counts
    if (
        endpoints <= 0
        or endpoints - skipped <= 0
        or sum(counts[1:]) != endpoints
    ):
        raise RelockError("readiness verdict outcomes are incomplete")
    if summary["lies"] != 0:
        raise RelockError("readiness verdict contains doctrine lies")
    p95_worst = summary.get("p95_worst")
    if (
        not isinstance(p95_worst, (int, float))
        or isinstance(p95_worst, bool)
        or not math.isfinite(p95_worst)
        or p95_worst < 0
    ):
        raise RelockError("readiness verdict latency is incomplete or invalid")
    return {
        "source_revision": source_sha,
        "checked_at": checked_at,
        "base": normalize_origin(expected_origin),
        "age_seconds": age_seconds,
        "summary": dict(summary),
    }


def validate_route(
    name: str,
    response: requests.Response,
    source_sha: str,
    source_variable: str,
    origin: str,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "url": response.url,
        "get_http_status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "bytes": len(response.content),
    }
    if name == "holographic":
        text = response.text
        if not all(marker in text for marker in HOLOGRAPHIC_SOURCE_MARKERS):
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
        runtime = payload.get("runtime")
        if (
            payload.get("status") != "OBSERVED"
            or payload.get("receipt_minted") is not False
            or not isinstance(build, Mapping)
            or str(build.get("state") or "").upper() != "OBSERVED"
            or str(build.get("revision") or "").lower() != source_sha
            or build.get("revision_source") != f"env:{source_variable}"
            or not isinstance(runtime, Mapping)
            or not str(runtime.get("python") or "").strip()
            or not str(runtime.get("platform") or "").strip()
        ):
            raise RelockError("build identity is not bound to the exact protected source")

        field_evidence = build.get("field_evidence")
        if not isinstance(field_evidence, Mapping):
            raise RelockError("build identity lacks per-field evidence classifications")
        if field_evidence.get("revision") != "OBSERVED":
            raise RelockError("build revision is not classified as observed metadata")

        version = build.get("version")
        version_source = build.get("version_source")
        if version is None:
            version_valid = (
                version_source == "UNKNOWN"
                and field_evidence.get("version") == "UNKNOWN"
            )
        else:
            version_valid = (
                isinstance(version, str)
                and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+\-]{0,63}", version))
                and isinstance(version_source, str)
                and version_source.startswith("env:")
                and field_evidence.get("version") == "OBSERVED"
            )
        if not version_valid:
            raise RelockError("build version value, source, and evidence classification conflict")

        working_tree = build.get("working_tree")
        working_tree_source = build.get("working_tree_source")
        if working_tree == "UNKNOWN":
            working_tree_valid = (
                working_tree_source == "UNKNOWN"
                and field_evidence.get("working_tree") == "UNKNOWN"
            )
        else:
            working_tree_valid = (
                working_tree in {"CLEAN", "DIRTY"}
                and working_tree_source == "git:status"
                and field_evidence.get("working_tree") == "OBSERVED"
            )
        if not working_tree_valid:
            raise RelockError(
                "working-tree value, source, and evidence classification conflict"
            )

        evidence["source_bound"] = True
        evidence["build_identity"] = {
            "revision": build["revision"],
            "revision_source": build["revision_source"],
            "version": version,
            "version_source": version_source,
            "working_tree": working_tree,
            "working_tree_source": working_tree_source,
            "field_evidence": dict(field_evidence),
            "receipt_minted": False,
        }
    elif name == "brain_capabilities":
        if (
            payload.get("schema") != "szl.brain-capabilities.v1"
            or not isinstance(payload.get("capabilities"), list)
            or not isinstance(payload.get("claim_policy"), Mapping)
        ):
            raise RelockError("Brain capabilities contract is incomplete")
    elif name == "readiness":
        evidence["verdict"] = validate_readiness_summary(
            payload,
            source_sha,
            expected_origin=origin,
        )
    elif name == "series_a_status":
        storage = payload.get("storage")
        if (
            payload.get("schema") != "szl.series-a-status/v1"
            or payload.get("terminal") is not True
            or str(payload.get("source_revision") or "").lower() != source_sha
            or payload.get("signing_key_source")
            != "persistent:env:SZL_COSIGN_PRIVATE_PEM"
            or payload.get("database")
            != SERIES_A_VARIABLES["A11OY_SERIES_A_DB"]
            or not isinstance(storage, Mapping)
            or storage.get("persistence_required") is not True
            or storage.get("required_mount") != "/data"
            or storage.get("mount_verified") is not True
            or storage.get("journal_mode") != "DELETE"
            or re.fullmatch(
                r"store_[0-9a-f]{32}",
                str(storage.get("instance_id") or ""),
            )
            is None
            or not isinstance(storage.get("created_at"), str)
            or not storage.get("created_at")
            or not isinstance(storage.get("receipt_count"), int)
            or isinstance(storage.get("receipt_count"), bool)
            or storage.get("receipt_count") <= 0
            or not isinstance(storage.get("last_receipt_sequence"), int)
            or isinstance(storage.get("last_receipt_sequence"), bool)
            or storage.get("last_receipt_sequence") < storage.get("receipt_count")
        ):
            raise RelockError(
                "Series-A signer or persistent storage contract is incomplete"
            )
        chain_head = storage.get("chain_head")
        receipt_count = storage["receipt_count"]
        if receipt_count == 0:
            if chain_head is not None:
                raise RelockError("empty Series-A receipt chain has a head")
        elif re.fullmatch(r"[0-9a-f]{64}", str(chain_head or "")) is None:
            raise RelockError("Series-A receipt chain head is invalid")
        evidence["source_bound"] = True
        evidence["signing_key_source"] = payload["signing_key_source"]
        evidence["storage"] = dict(storage)
    return evidence


def probe_routes(
    session: requests.Session,
    origin: str,
    source_sha: str,
    source_variable: str,
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
        evidence = validate_route(
            name,
            get,
            source_sha,
            source_variable,
            origin,
        )
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
    runtime_sha, runtime_sha_source = immutable_runtime_revision(info)
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
    variable_drift = {
        name: variable_value(variables.get(name))
        for name, expected in SERIES_A_VARIABLES.items()
        if variable_value(variables.get(name)) != expected
    }
    if variable_drift:
        raise RelockError(
            "Series-A runtime variable drift: " + ",".join(sorted(variable_drift))
        )

    secrets = api.get_space_secrets(contract["repo_id"])
    if (
        not isinstance(secrets, Mapping)
        or CANONICAL_SIGNING_SECRET not in secrets
    ):
        raise RelockError(
            f"canonical signing secret is absent: {CANONICAL_SIGNING_SECRET}"
        )

    runtime = getattr(info, "runtime", None)
    if runtime is None or getattr(runtime, "volumes", None) is None:
        raise RelockError(
            "canonical Space info lacks authoritative volume metadata"
        )
    volumes = [
        volume_record(item)
        for item in list(runtime.volumes)
    ]
    data_volumes = [
        item for item in volumes if item["mount_path"] == "/data"
    ]
    if (
        len(data_volumes) != 1
        or data_volumes[0]["type"] != "bucket"
        or data_volumes[0]["source"] != CANONICAL_SERIES_A_BUCKET
        or data_volumes[0]["read_only"]
    ):
        raise RelockError(
            "canonical read-write Series-A bucket is not attached at /data"
        )

    routes = probe_routes(
        session,
        contract["origin"],
        contract["source_sha"],
        contract["variable"],
    )
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
        "series_a_runtime": {
            "signing_secret_present": True,
            "variables": {
                name: expected
                for name, expected in sorted(SERIES_A_VARIABLES.items())
            },
            "volumes": volumes,
            "persistent_contract_matched": True,
        },
        "hf_repository_sha": repository_sha,
        "hf_runtime_sha": runtime_sha,
        "hf_runtime_sha_source": runtime_sha_source,
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
