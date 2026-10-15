#!/usr/bin/env python3
"""Verify the sole canonical A11oy Space against one exact protected source SHA.

The reusable deployer owns publication, source-variable binding, immutable Hub
commit attestation, byte readback, and smoke routes. This verifier independently
rechecks the application-specific terminal contract and writes one JSON report.
It performs no Hugging Face or GitHub mutation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import importlib.util
import sys
from functools import lru_cache
import math
import os
import re
import time
from collections import Counter
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlsplit

import requests
from huggingface_hub import HfApi

SHA40 = re.compile(r"^[0-9a-f]{40}$")
REPO_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")
REPORT_SCHEMA = "szl.a11oy-deployment-relock/v4"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
HOLOGRAPHIC_SOURCE_PATH = "static/3d/holographic.html"
HOLOGRAPHIC_SOURCE_MARKERS = (
    "A11oy Holographic Operations",
    "The estate, observed—not assumed.",
)
BRAIN_SOURCE_PATHS = {
    "brain_frontier_css": "console/assets/brain-frontier-v7.css",
    "brain_frontier_js": "console/assets/brain-frontier-v7.js",
    "brain_frontier_snapshot": "console/assets/brain-frontier-v7.json",
}
REQUIRED_REMOTE_FILES = {
    "Dockerfile",
    HOLOGRAPHIC_SOURCE_PATH,
    *BRAIN_SOURCE_PATHS.values(),
}
HOLOGRAPHIC_ROUTES = {"holographic", "holographic_slash"}
ASSET_CONTENT_TYPES = {
    "brain_frontier_css": ("text/css",),
    "brain_frontier_js": (
        "application/javascript",
        "text/javascript",
    ),
    "brain_frontier_snapshot": ("application/json",),
}
BRAIN_SCHEMA = "szl.a11oy.brain-frontier-holographic-v7/v1"
BRAIN_STATE = "SOURCE_BOUND_REVIEW_MEMORY"
BRAIN_SURFACE = "A11OY_HOLOGRAPHIC_V7_BRAIN_FRONTIER"
BRAIN_HANDLE_COUNT = 72
BRAIN_SOURCE_REPOSITORIES = {
    "szl-holdings/a11oy",
    "szl-holdings/anatomy",
    "szl-holdings/szl-forge",
    "szl-holdings/szl-formulas",
    "szl-holdings/szl-kernels",
    "szl-holdings/szl-nemo",
    "szl-holdings/szl-ouroboros",
}
BRAIN_ALLOWED_KINDS = {
    "attributed-formula",
    "estate-authority",
    "estate-surface",
    "executable-formula",
    "formula-authority",
    "python-contract",
    "quant-domain",
    "source-document",
}
BRAIN_REQUIRED_KIND_COUNTS = {
    "attributed-formula": 30,
    "executable-formula": 21,
    "formula-authority": 1,
    "quant-domain": 9,
}
BRAIN_ALLOWED_ADMISSIONS = {
    "DISCOVERED_REVIEW_REQUIRED",
    "EXECUTABLE_CONSTRAINT_REVIEW_REQUIRED",
    "OPEN_NOT_EXECUTION_AUTHORITY",
    "REFERENCE_AND_CONSTRAINT_INPUT_ONLY",
    "REFERENCE_ONLY_EXECUTION_AUTHORITY_NONE",
    "REFERENCE_ONLY_NO_PROVIDER_MUTATION",
    "REFERENCE_ONLY_UNLESS_EXECUTABLE_MATCH_IS_EXPLICIT",
    "SOURCE_RECEIPT_REQUIRED_FOR_CURRENT_CLAIM",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
FRONTIER_NODE_ID = re.compile(r"^frontier:[0-9a-f]{32}$")
CANONICAL_SIGNING_SECRET = "SZL_COSIGN_PRIVATE_PEM"
CANONICAL_SERIES_A_BUCKET = "SZLHOLDINGS/szl-evidence"
CANONICAL_STATE_ROOT = "/tmp/a11oy-state"
STATE_STORE_STATUS_ROUTE = "/api/a11oy/v1/storage/status"
STATE_STORE_KINDS = {
    "gdw": "sqlite",
    "series_a": "sqlite",
    "khipu": "sqlite",
    "khipu_council": "sqlite",
    "unay": "sqlite",
    "khipu_lmdb": "lmdb",
    "khipu_repl": "lmdb",
}
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
    "A11OY_ATELIER_LEDGER_PATH": "/data/a11oy/atelier/turn-receipts-v1.jsonl",
    "A11OY_ATELIER_REQUIRED_MOUNT": "/data",
    "SZL_GOVERN_INFER_LOG": "/data/.szl_govern_infer.jsonl",
}
ROUTES = {
    "livez": "/api/livez",
    "build_info": "/api/build-info",
    "brain_capabilities": "/api/a11oy/v1/brain/capabilities",
    "readiness": "/api/a11oy/v1/readiness/tab-matrix?view=summary",
    "series_a_status": "/api/a11oy/v1/series-a/status",
    "holographic": "/holographic",
    "holographic_slash": "/holographic/",
    "brain_frontier_css": "/assets/brain-frontier-v7.css",
    "brain_frontier_js": "/assets/brain-frontier-v7.js",
    "brain_frontier_snapshot": "/assets/brain-frontier-v7.json",
}


class RelockError(RuntimeError):
    """The live canonical deployment does not satisfy the reviewed contract."""


@lru_cache(maxsize=1)
def execution_validator():
    spec = importlib.util.spec_from_file_location("_relock_execution_readiness", REPOSITORY_ROOT / "szl_execution_readiness.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


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


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def source_bytes(path: str) -> bytes:
    candidate = (REPOSITORY_ROOT / path).resolve()
    try:
        candidate.relative_to(REPOSITORY_ROOT.resolve())
    except ValueError as exc:
        raise RelockError(f"reviewed source path escaped the repository: {path}") from exc
    try:
        return candidate.read_bytes()
    except OSError as exc:
        raise RelockError(f"reviewed source file is unavailable: {path}") from exc


def parse_json_object(raw: bytes, *, label: str) -> Mapping[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RelockError(f"{label} is not strict UTF-8 JSON") from exc
    if not isinstance(payload, Mapping):
        raise RelockError(f"{label} JSON is not an object")
    return payload


def validate_no_private_content_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key).casefold() in {"content", "text"}:
                raise RelockError("Brain snapshot exposes a forbidden content field")
            validate_no_private_content_keys(item)
    elif isinstance(value, list):
        for item in value:
            validate_no_private_content_keys(item)


def validate_brain_snapshot(raw: bytes) -> dict[str, Any]:
    payload = parse_json_object(raw, label="Brain frontier snapshot")
    validate_no_private_content_keys(payload)

    handles = payload.get("handles")
    if (
        payload.get("schema") != BRAIN_SCHEMA
        or payload.get("state") != BRAIN_STATE
        or payload.get("surface") != BRAIN_SURFACE
        or payload.get("selected_handle_count") != BRAIN_HANDLE_COUNT
        or not isinstance(handles, list)
        or len(handles) != BRAIN_HANDLE_COUNT
    ):
        raise RelockError("Brain snapshot identity or 72-handle contract drifted")

    claimed_digest = str(payload.get("snapshot_sha256") or "").lower()
    unsigned_snapshot = dict(payload)
    unsigned_snapshot.pop("snapshot_sha256", None)
    measured_digest = hashlib.sha256(canonical_bytes(unsigned_snapshot)).hexdigest()
    if HEX64.fullmatch(claimed_digest) is None or claimed_digest != measured_digest:
        raise RelockError("Brain snapshot self-digest is absent or invalid")

    expected_formula_atlas = {
        "attributed_formula_count": 30,
        "executable_formula_count": 21,
        "f_number_to_executable_mapping": "UNKNOWN_NOT_INFERRED",
        "lambda": "CONJECTURE_1",
        "locked_proven_formula_count": 8,
        "quant_domain_count": 9,
    }
    if payload.get("formula_atlas") != expected_formula_atlas:
        raise RelockError("Brain formula-atlas contract drifted")
    if payload.get("loop") != ["OBSERVE", "ORIENT", "PROPOSE", "VERIFY", "HOLD"]:
        raise RelockError("Brain review loop drifted")

    expected_authority = {
        "controller_content_access": "NOT_EXPOSED_BY_A11OY_HOLOGRAPHIC",
        "execution": "NONE",
        "human_review_required": True,
        "merge": "NONE",
        "private_graph_present": False,
        "promotion": "NONE",
        "provider_mutation": "NONE",
        "public_content_access": "HANDLES_ONLY",
        "raw_graph_nodes_admitted_to_gradients": 0,
        "training": "NONE",
    }
    if payload.get("authority") != expected_authority:
        raise RelockError("Brain snapshot authority boundary drifted")

    sources = payload.get("sources")
    expected_source_repositories = {
        "anatomy": "szl-holdings/anatomy",
        "formulas": "szl-holdings/szl-formulas",
        "ouroboros": "szl-holdings/szl-ouroboros",
        "second_brain": "szl-holdings/szl-second-brain",
    }
    if not isinstance(sources, Mapping) or set(sources) != set(expected_source_repositories):
        raise RelockError("Brain snapshot source authority set drifted")
    for name, expected_repository in expected_source_repositories.items():
        record = sources.get(name)
        if (
            not isinstance(record, Mapping)
            or record.get("repository") != expected_repository
            or SHA40.fullmatch(str(record.get("revision") or "").lower()) is None
        ):
            raise RelockError(f"Brain snapshot source is not immutable: {name}")
    second_brain = sources["second_brain"]
    for field in (
        "candidate_file_sha256",
        "candidate_set_sha256",
        "state_sha256",
    ):
        if HEX64.fullmatch(str(second_brain.get(field) or "").lower()) is None:
            raise RelockError(f"Brain Second Brain source lacks {field}")
    candidate_count = second_brain.get("candidate_count")
    if (
        not isinstance(candidate_count, int)
        or isinstance(candidate_count, bool)
        or candidate_count < BRAIN_HANDLE_COUNT
    ):
        raise RelockError("Brain candidate count cannot support the selected handles")

    node_ids: set[str] = set()
    observed_repositories: set[str] = set()
    kind_counts: Counter[str] = Counter()
    allowed_handle_keys = {
        "admission",
        "authority",
        "candidateState",
        "contentAccess",
        "kind",
        "nodeId",
        "path",
        "quantDomain",
        "repository",
        "revision",
        "sha256",
        "title",
    }
    for index, handle in enumerate(handles):
        if not isinstance(handle, Mapping) or not set(handle).issubset(allowed_handle_keys):
            raise RelockError(f"Brain handle {index} has an invalid shape")
        node_id = str(handle.get("nodeId") or "")
        repository = str(handle.get("repository") or "")
        revision = str(handle.get("revision") or "").lower()
        digest = str(handle.get("sha256") or "").lower()
        kind = str(handle.get("kind") or "")
        path = str(handle.get("path") or "")
        if (
            FRONTIER_NODE_ID.fullmatch(node_id) is None
            or node_id in node_ids
            or repository not in BRAIN_SOURCE_REPOSITORIES
            or SHA40.fullmatch(revision) is None
            or HEX64.fullmatch(digest) is None
            or kind not in BRAIN_ALLOWED_KINDS
            or not path
            or path.startswith("/")
            or "\\" in path
            or ".." in path.split("/")
            or not str(handle.get("title") or "").strip()
            or handle.get("admission") not in BRAIN_ALLOWED_ADMISSIONS
            or handle.get("candidateState") != "DISCOVERED_REVIEW_REQUIRED"
            or handle.get("contentAccess") != "HANDLES_ONLY"
            or handle.get("authority") != "NONE"
        ):
            raise RelockError(f"Brain handle {index} violates the handles-only contract")
        node_ids.add(node_id)
        observed_repositories.add(repository)
        kind_counts[kind] += 1

    if observed_repositories != BRAIN_SOURCE_REPOSITORIES:
        raise RelockError("Brain handle repository distribution is incomplete")
    for kind, expected in BRAIN_REQUIRED_KIND_COUNTS.items():
        if kind_counts[kind] != expected:
            raise RelockError(f"Brain handle kind distribution drifted: {kind}")

    return {
        "schema": BRAIN_SCHEMA,
        "state": BRAIN_STATE,
        "selected_handle_count": BRAIN_HANDLE_COUNT,
        "snapshot_sha256": claimed_digest,
        "source_repositories": sorted(observed_repositories),
        "kind_distribution": dict(sorted(kind_counts.items())),
        "handles_only": True,
        "authority": "NONE",
    }


class FrontierMountParser(HTMLParser):
    """Read active stylesheet/script mounts, excluding comments and inert markup."""

    TEXT_CONTEXTS = {"textarea", "title", "xmp", "iframe", "noembed", "noframes", "style", "plaintext"}
    INERT_CONTEXTS = TEXT_CONTEXTS | {"template", "noscript", "svg", "math"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.mounts: list[tuple[str, tuple[tuple[str, str | None], ...]]] = []
        self.inert_contexts: list[str] = []
        self.base_present = False
        self.pending_script = None

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # Browsers ignore '/>' on non-void HTML elements. Inherited HTMLParser
        # behavior would incorrectly close a <textarea/> or <template/> wrapper.
        self.handle_starttag(tag, attrs)
        if tag in {"svg", "math"}:
            self.handle_endtag(tag)
        if tag in {"script", "style"}:
            self.set_cdata_mode(tag)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        # HTMLParser reports tags inside RCDATA/raw-text elements that browsers
        # treat as text. Only the matching close can end such a context.
        if self.inert_contexts and self.inert_contexts[-1] in self.TEXT_CONTEXTS:
            return
        if tag in self.INERT_CONTEXTS:
            self.inert_contexts.append(tag)
        if self.inert_contexts:
            return
        if tag == "base":
            self.base_present = True
        if tag not in {"link", "script"}:
            return
        if any(
            key == "data-szl-brain-frontier-v7"
            or (key in {"src", "href"} and "brain-frontier-v7" in (value or ""))
            for key, value in attrs
        ):
            # Preserve duplicate attributes: browsers can disagree about which wins.
            mount = (tag, tuple(sorted(attrs, key=lambda pair: pair[0])))
            if tag == "script":
                self.pending_script = mount
            else:
                self.mounts.append(mount)

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self.pending_script is not None:
            self.mounts.append(self.pending_script)
            self.pending_script = None
        if (
            self.inert_contexts
            and self.inert_contexts[-1] != "plaintext"
            and tag == self.inert_contexts[-1]
        ):
            self.inert_contexts.pop()


def validate_exact_source_asset(
    name: str,
    response: requests.Response,
) -> dict[str, Any]:
    source_path = (
        HOLOGRAPHIC_SOURCE_PATH if name in HOLOGRAPHIC_ROUTES else BRAIN_SOURCE_PATHS[name]
    )
    expected = source_bytes(source_path)
    if name in HOLOGRAPHIC_ROUTES:
        try:
            text = response.content.decode("utf-8")
            source_text = expected.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RelockError("holographic surface is not strict UTF-8") from exc
        if not all(marker in text for marker in HOLOGRAPHIC_SOURCE_MARKERS):
            raise RelockError("holographic surface lacks the reviewed source markers")
        source_mounts = FrontierMountParser()
        source_mounts.feed(source_text)
        live_mounts = FrontierMountParser()
        live_mounts.feed(text)
        if (
            [tag for tag, _ in source_mounts.mounts] != ["link", "script"]
            or live_mounts.mounts != source_mounts.mounts
            or source_mounts.base_present
            or live_mounts.base_present
        ):
            raise RelockError("holographic surface lacks the exact active reviewed asset mounts")
        allowed_content_types = ("text/html",)
    else:
        allowed_content_types = ASSET_CONTENT_TYPES[name]

    observed_content_type = str(response.headers.get("content-type") or "")
    media_type = observed_content_type.split(";", 1)[0].strip().lower()
    if media_type not in allowed_content_types:
        raise RelockError(f"{ROUTES[name]} returned an invalid content type")
    if name not in HOLOGRAPHIC_ROUTES and response.content != expected:
        raise RelockError(f"{ROUTES[name]} does not match reviewed source bytes")

    evidence: dict[str, Any] = {
        "source_path": source_path,
        "source_bytes_matched": response.content == expected,
        "sha256": hashlib.sha256(response.content).hexdigest(),
        "source_sha256": hashlib.sha256(expected).hexdigest(),
    }
    if name in HOLOGRAPHIC_ROUTES:
        # The production HTML middleware injects a shared operator widget. Verify
        # the reviewed surface and mounts without mislabeling transformed HTML
        # as a byte-identical source artifact. The linked assets remain exact.
        evidence["source_markers"] = True
        evidence["reviewed_asset_mounts"] = True
    elif name == "brain_frontier_snapshot":
        evidence["snapshot"] = validate_brain_snapshot(response.content)
    return evidence


def load_run_verdict(path: str) -> Mapping[str, Any]:
    """Read this run's validated compact readiness verdict (the job output).

    The deploy path no longer writes the verdict into the Space, because a
    Space-variable write restarts the revision it just started. The verdict
    produced by this run's readiness-verdict job is handed to relock instead,
    and is re-validated here against the exact source and canonical origin.
    """
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        raise RelockError("run-local readiness verdict is unreadable") from exc
    if not raw.strip() or len(raw) > 4096:
        raise RelockError("run-local readiness verdict is absent or oversized")
    return parse_json_object(raw, label="run-local readiness verdict")


def validate_readiness_summary(
    payload: Mapping[str, Any],
    source_sha: str,
    *,
    expected_origin: str,
    now: datetime | None = None,
    run_verdict: Mapping[str, Any] | None = None,
    execution_inputs=None,
) -> dict[str, Any]:
    if (
        payload.get("honest") is not True
        or payload.get("view") != "summary"
        or payload.get("matrix_available") is not True
    ):
        raise RelockError("readiness summary is unavailable or source-unbound")
    served = (
        payload.get("available") is True
        and payload.get("probe_verdict_available") is True
        and payload.get("verdict_source_revision") == source_sha
    )
    if served:
        evidence = validate_verdict_evidence(
            base=payload.get("verdict_base"),
            checked_at=payload.get("verdict_checked_at"),
            summary=payload.get("verdict_summary"),
            execution_inputs=execution_inputs,
            source_sha=source_sha,
            expected_origin=expected_origin,
            now=now,
        )
        if evidence.get("executionCoverage") != payload.get("execution_coverage"):
            raise RelockError("served execution coverage differs from independently verified observations")
        evidence["channel"] = "served"
        return evidence
    if run_verdict is None:
        raise RelockError("readiness summary is unavailable or source-unbound")
    # The live route must honestly report that it serves no verdict; a served
    # verdict for any other source is never papered over by the run verdict.
    if (
        payload.get("available") is not False
        or payload.get("probe_verdict_available") is not False
        or payload.get("verdict_source_revision") is not None
        or payload.get("verdict_summary") is not None
    ):
        raise RelockError("readiness summary serves a verdict for another source")
    if (
        not isinstance(run_verdict, Mapping)
        or run_verdict.get("schema") != "szl.readiness-verdict/v1"
        or run_verdict.get("harness") != "a11oy-readiness probe"
        or run_verdict.get("doctrine") != "v11"
        or run_verdict.get("sourceRevision") != source_sha
    ):
        raise RelockError("run-local readiness verdict is not bound to this source")
    evidence = validate_verdict_evidence(
        base=run_verdict.get("base"),
        checked_at=run_verdict.get("checkedAt"),
        summary=run_verdict.get("summary"),
        execution_inputs=execution_inputs,
        source_sha=source_sha,
        expected_origin=expected_origin,
        now=now,
    )
    if evidence.get("executionCoverage") != run_verdict.get("executionCoverage"):
        raise RelockError("run-local execution coverage differs from independently verified observations")
    evidence["channel"] = "run-local"
    return evidence


def validate_verdict_evidence(
    *,
    base: Any,
    checked_at: Any,
    summary: Any,
    source_sha: str,
    expected_origin: str,
    now: datetime | None = None,
    execution_inputs=None,
) -> dict[str, Any]:
    try:
        observed_base = normalize_origin(base)
    except (RelockError, ValueError):
        observed_base = None
    if observed_base != normalize_origin(expected_origin):
        raise RelockError("readiness verdict was not probed at the canonical origin")

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

    if not isinstance(summary, Mapping):
        raise RelockError("readiness verdict summary is unavailable")
    fields = (
        "endpoints",
        "ok",
        "skippedStateChanging",
        "lies",
        "unreachable",
        "throttled",
        "degraded",
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
    required_not_probed = summary.get("requiredNotProbed", skipped)
    if (
        not isinstance(required_not_probed, int)
        or isinstance(required_not_probed, bool)
        or not 0 <= required_not_probed <= skipped
    ):
        raise RelockError("readiness verdict required-not-probed count is invalid")
    verified_execution = None
    gate = execution_validator()
    canonical_matrix = gate.acceptance.strict_json(gate.acceptance.read_file(
        str(REPOSITORY_ROOT / "tools/readiness-harness/tabs.json")))
    matrix_requires_execution = any(type(spec) is dict and spec.get("method", "GET") not in ("GET", "HEAD")
        for spec in canonical_matrix.get("endpoints", {}).values())
    if required_not_probed != 0 or matrix_requires_execution:
        try:
            if type(execution_inputs) is not dict or set(execution_inputs) != {"passive", "matrix", "bundle", "context"}:
                raise ValueError("raw independent execution inputs required")
            passive = execution_inputs["passive"]
            if passive.get("summary") != summary or passive.get("checkedAt") != checked_at or passive.get("base") != base:
                raise ValueError("compact verdict differs from full passive artifact")
            verified_execution = execution_validator().validate_combined(
                passive, execution_inputs["matrix"], execution_inputs["bundle"], execution_inputs["context"],
                source=source_sha, now=current)
        except Exception as exc:
            raise RelockError("readiness verdict contains unprobed required endpoints without independently verified execution evidence") from exc
    blocking_degraded = summary.get("blockingDegraded", summary["degraded"])
    if (
        not isinstance(blocking_degraded, int)
        or isinstance(blocking_degraded, bool)
        or blocking_degraded < 0
        or blocking_degraded > summary["degraded"]
    ):
        raise RelockError("readiness verdict blocking degradation is invalid")
    if summary["lies"] != 0:
        raise RelockError("readiness verdict contains doctrine lies")
    if summary["unreachable"] != 0:
        raise RelockError("readiness verdict contains unreachable required endpoints")
    if summary["throttled"] != 0:
        raise RelockError("readiness verdict contains throttled required endpoints")
    if blocking_degraded != 0:
        raise RelockError("readiness verdict contains unavailable required sources")
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
        "summary": {**dict(summary), "requiredNotProbed": required_not_probed},
        **({"executionCoverage": verified_execution} if verified_execution is not None else {}),
    }


def validate_state_store_status(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Require observed ADR-0001 fencing and snapshots, not just a local path."""
    def positive_integer(value: Any) -> bool:
        return isinstance(value, int) and not isinstance(value, bool) and value > 0

    def fresh_age(value: Any, limit: float) -> bool:
        return (
            isinstance(value, (int, float))
            and not isinstance(value, bool)
            and math.isfinite(value)
            and 0 <= value <= limit
        )

    lease = payload.get("lease")
    stores = payload.get("stores")
    if (
        payload.get("schema") != "szl.a11oy-storage-status/v2"
        or payload.get("mode") != "FENCED"
        or payload.get("role") != "WRITER"
        or payload.get("writable") is not True
        or payload.get("unfenced") is not False
        or payload.get("alert") is not False
        or payload.get("pending_publish") != []
        or payload.get("last_error") is not None
        or not positive_integer(payload.get("epoch"))
        or not isinstance(lease, Mapping)
        or lease.get("state") != "ACTIVE"
        or not positive_integer(lease.get("sequence"))
        or not fresh_age(lease.get("heartbeat_age_s"), 120)
        or not isinstance(stores, Mapping)
        or set(stores) != set(STATE_STORE_KINDS)
    ):
        raise RelockError("v2 storage lacks a healthy fenced writer and active lease")
    for label, kind in STATE_STORE_KINDS.items():
        store = stores[label]
        integrity = {"lmdb_read"} if kind == "lmdb" else {"quick_check", "integrity_check"}
        if (
            not isinstance(store, Mapping)
            or store.get("kind") != kind
            or store.get("health") != "OK"
            or store.get("blocked_code") is not None
            or store.get("last_error_code") is not None
            or type(store.get("snapshot_failures")) is not int
            or store.get("snapshot_failures") != 0
            or store.get("integrity") not in integrity
            or re.fullmatch(r"[0-9a-f]{16}", str(store.get("sha16") or "")) is None
            or not fresh_age(store.get("last_snapshot_age_s"), 900)
            or (
                store.get("unsnapshotted_change_age_s") is not None
                and not fresh_age(store["unsnapshotted_change_age_s"], 900)
            )
        ):
            raise RelockError(f"v2 storage snapshot contract is incomplete: {label}")
    return dict(payload)


def validate_route(
    name: str,
    response: requests.Response,
    source_sha: str,
    source_variable: str,
    origin: str,
    run_verdict: Mapping[str, Any] | None = None,
    series_a_database: str = SERIES_A_VARIABLES["A11OY_SERIES_A_DB"],
    execution_inputs=None,
) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "url": response.url,
        "get_http_status": response.status_code,
        "content_type": response.headers.get("content-type"),
        "bytes": len(response.content),
    }
    if name in HOLOGRAPHIC_ROUTES or name in BRAIN_SOURCE_PATHS:
        evidence.update(validate_exact_source_asset(name, response))
        return evidence

    payload = require_json(response)
    evidence["json_keys"] = sorted(str(key) for key in payload)[:100]
    evidence["schema"] = payload.get("schema")
    evidence["status"] = payload.get("status") or payload.get("overall_status")
    if name == "livez":
        if (
            payload.get("status") != "PROCESS_ALIVE"
            or payload.get("receipt_minted") is not False
            or payload.get("production_ready") is not False
        ):
            raise RelockError("liveness route is not process-only/read-only")
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
            run_verdict=run_verdict, execution_inputs=execution_inputs,
        )
    elif name == "storage_status":
        evidence["storage_state"] = validate_state_store_status(payload)
    elif name == "series_a_status":
        storage = payload.get("storage")
        critical_failures = payload.get("critical_failures")
        if (
            payload.get("schema") != "szl.series-a-status/v1"
            or payload.get("terminal") is not True
            or payload.get("state") != "OBSERVED"
            or not isinstance(critical_failures, list)
            or critical_failures
            or str(payload.get("source_revision") or "").lower() != source_sha
            or payload.get("signing_key_source")
            != "persistent:env:SZL_COSIGN_PRIVATE_PEM"
            or payload.get("database")
            != series_a_database
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
                "Series-A estate state, signer, or persistent storage contract is incomplete"
            )
        chain_head = storage.get("chain_head")
        receipt_count = storage["receipt_count"]
        if receipt_count == 0:
            if chain_head is not None:
                raise RelockError("empty Series-A receipt chain has a head")
        elif re.fullmatch(r"[0-9a-f]{64}", str(chain_head or "")) is None:
            raise RelockError("Series-A receipt chain head is invalid")
        evidence["source_bound"] = True
        evidence["estate_state"] = payload["state"]
        evidence["critical_failures"] = list(critical_failures)
        evidence["signing_key_source"] = payload["signing_key_source"]
        evidence["runtime_boot_id"] = payload.get("runtime_boot_id")
        evidence["storage"] = dict(storage)
    return evidence


def probe_routes(
    session: requests.Session,
    origin: str,
    source_sha: str,
    source_variable: str,
    run_verdict: Mapping[str, Any] | None = None,
    state_store_v2: bool = False,
    execution_inputs=None,
) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    routes = dict(ROUTES)
    if state_store_v2:
        routes["storage_status"] = STATE_STORE_STATUS_ROUTE
    series_a_database = (
        CANONICAL_STATE_ROOT + "/series-a/control-plane-v2.sqlite3"
        if state_store_v2 else SERIES_A_VARIABLES["A11OY_SERIES_A_DB"]
    )
    for name, path in routes.items():
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
            run_verdict,
            series_a_database, execution_inputs=execution_inputs,
        )
        evidence["head_http_status"] = head.status_code
        output[name] = evidence
    return output


def verify_current_execution_owner(execution_inputs, *, client=None):
    """Final read-only owner lookup; revoked/cancelled completed runs cannot relock."""
    if type(execution_inputs) is not dict:
        raise RelockError("raw execution inputs are required for current owner verification")
    spec = importlib.util.spec_from_file_location("_relock_completed_export_collector",
        REPOSITORY_ROOT / ".github/scripts/collect_execution_readiness.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    def read(active_client):
        bundle, report = module.collect(active_client, execution_inputs["context"],
            operator_token=os.environ.get("A11OY_CODE_ADMIN_KEY", ""),
            tenant=os.environ.get("A11OY_CODE_TENANT", ""))
        gate = execution_validator()
        if gate.acceptance.canonical(bundle) != gate.acceptance.canonical(execution_inputs["bundle"]):
            raise RelockError("current retained execution export differs from immutable run evidence")
        return report
    try:
        if client is not None:  # Explicit transport injection for isolated tests only.
            return read(client)
        import httpx
        with httpx.Client(timeout=httpx.Timeout(20, connect=10), follow_redirects=False, trust_env=True) as active:
            return read(active)
    except Exception:
        raise RelockError("current retained execution owner evidence is unavailable") from None


def evaluate_once(
    api: HfApi,
    session: requests.Session,
    contract: Mapping[str, str],
    run_verdict: Mapping[str, Any] | None = None,
    execution_inputs=None,
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

    state_store_mode = variable_value(variables.get("A11OY_STATE_STORE"))
    state_store_v2 = state_store_mode == "v2"
    if state_store_mode not in (None, "", "off", "v2"):
        raise RelockError("unsupported A11OY_STATE_STORE configuration")
    if state_store_v2 and variable_value(variables.get("A11OY_STATE_ROOT")) not in (
        None, "", CANONICAL_STATE_ROOT,
    ):
        raise RelockError("v2 storage root differs from the canonical local root")

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
        run_verdict,
        state_store_v2, execution_inputs=execution_inputs,
    )
    if execution_inputs is not None:
        context = execution_inputs["context"]
        if (not state_store_v2 or runtime_sha != context.runtime_revision
                or routes["series_a_status"].get("runtime_boot_id") != context.runtime_boot_id):
            raise RelockError("execution context does not match current HF revision, process boot, and fenced storage")
        # Bracket the complete readback. Same source alone cannot identify a
        # restarted process; verify HF serving revision and Series-A boot again.
        after_info = api.space_info(contract["repo_id"])
        after_revision, _ = immutable_runtime_revision(after_info)
        if after_revision != runtime_sha or str(getattr(after_info, "sha", "")).lower() != repository_sha:
            raise RelockError("runtime revision changed during execution evidence readback")
        after_status = session.get(contract["origin"] + ROUTES["series_a_status"], allow_redirects=False, timeout=60)
        if after_status.status_code != 200:
            raise RelockError("runtime boot recheck unavailable")
        after_payload = require_json(after_status)
        if after_payload.get("runtime_boot_id") != context.runtime_boot_id or after_payload.get("source_revision") != contract["source_sha"]:
            raise RelockError("runtime boot or source changed during execution evidence readback")
    clones = {f"SZLHOLDINGS/a11oy-clone-{index}": False for index in range(1, 5)}
    for clone_id in tuple(clones):
        clones[clone_id] = bool(api.repo_exists(clone_id, repo_type="space"))
    if any(clones.values()):
        raise RelockError(f"historical A11oy clone reappeared: {clones}")
    current_execution_owner = (verify_current_execution_owner(execution_inputs)
                               if execution_inputs is not None else None)

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
            "state_store_mode": "v2" if state_store_v2 else "legacy",
        },
        "hf_repository_sha": repository_sha,
        "hf_runtime_sha": runtime_sha,
        "hf_runtime_sha_source": runtime_sha_source,
        "managed_file_count": len(remote_files),
        "dockerfile_present": True,
        "holographic_source_present": True,
        "clone_presence": clones,
        "current_execution_owner": current_execution_owner,
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
    run_verdict: Mapping[str, Any] | None = None,
    execution_inputs=None,
) -> dict[str, Any]:
    last: Exception | None = None
    for attempt in range(1, max(1, attempts) + 1):
        try:
            report = evaluate_once(api, session, contract, run_verdict, execution_inputs=execution_inputs)
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
    parser.add_argument(
        "--readiness-verdict-file",
        help=(
            "This run's validated compact readiness verdict. Accepted only when "
            "the live route honestly serves no verdict; it is re-validated "
            "against the exact source and canonical origin."
        ),
    )
    parser.add_argument("--execution-bundle")
    parser.add_argument("--passive-verdict")
    parser.add_argument("--authority-pins")
    parser.add_argument("--expected-runtime-sha")
    parser.add_argument("--expected-boot-id")
    parser.add_argument("--expected-run-nonce")
    parser.add_argument("--matrix", default=str(REPOSITORY_ROOT / "tools/readiness-harness/tabs.json"))
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
        run_verdict = (
            load_run_verdict(args.readiness_verdict_file)
            if args.readiness_verdict_file
            else None
        )
        execution_inputs = None
        if not args.execution_bundle:
            raise RelockError("five canonical POST contracts require the raw admitted execution bundle")
        if args.execution_bundle:
            gate = execution_validator()
            context = gate.context_from_independent_file(
                args.authority_pins, expected_source=args.source_sha,
                expected_runtime_revision=args.expected_runtime_sha,
                expected_runtime_boot_id=args.expected_boot_id, expected_run_nonce=args.expected_run_nonce)
            execution_inputs = {"context": context,
                "bundle": gate.acceptance.strict_json(gate.acceptance.read_file(args.execution_bundle)),
                "passive": gate.acceptance.strict_json(gate.acceptance.read_file(args.passive_verdict)),
                "matrix": gate.canonical_matrix(args.matrix)}
        elif any((args.passive_verdict, args.authority_pins, args.expected_runtime_sha, args.expected_boot_id, args.expected_run_nonce)):
            raise RelockError("execution context requires raw passive and execution evidence")
        report = evaluate(
            api, session, contract, args.attempts, args.retry_seconds, run_verdict, execution_inputs=execution_inputs
        )
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
