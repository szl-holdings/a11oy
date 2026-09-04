#!/usr/bin/env python3
"""Materialize the A11oy Holographic v7 Brain frontier snapshot.

The command surface consumes only source handles, revisions, counts, and digests.
Candidate content stays inside the Second Brain controller boundary. All remote
origins, repositories, and paths are fixed; generated output is deterministic and
carries no timestamp, secret, private graph row, model weight, or execution authority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import tempfile
import urllib.error
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

SECOND_BRAIN_REPOSITORY = "szl-holdings/szl-second-brain"
ANATOMY_REPOSITORY = "szl-holdings/anatomy"
FORMULA_REPOSITORY = "szl-holdings/szl-formulas"
OUROBOROS_REPOSITORY = "szl-holdings/szl-ouroboros"
STATE_PATH = "data/frontier-state.v1.json"
CANDIDATES_PATH = "data/frontier-candidates.public.jsonl"
API_ORIGIN = "https://api.github.com"
RAW_ORIGIN = "https://raw.githubusercontent.com"
USER_AGENT = "a11oy-holographic-brain-frontier-v7/1.0"
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_HANDLES = 72
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
FRONTIER_ID = re.compile(r"^frontier:[0-9a-f]{32}$")
ALLOWED_SOURCE_REPOSITORIES = {
    "szl-holdings/szl-formulas",
    "szl-holdings/ouroboros",
    "szl-holdings/anatomy",
    "szl-holdings/a11oy",
    "szl-holdings/szl-forge",
    "szl-holdings/szl-nemo",
}
KIND_ORDER = {
    "formula-authority": 0,
    "quant-domain": 1,
    "attributed-formula": 2,
    "executable-formula": 3,
    "python-contract": 4,
    "estate-authority": 5,
    "estate-surface": 6,
    "source-document": 7,
}


class MaterializationError(RuntimeError):
    """A fixed source failed its exactness or authority contract."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def token_from_environment() -> str | None:
    for key in ("GH_READ_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return None


def request_bytes(url: str, *, limit: int, token: str | None = None) -> bytes:
    headers = {
        "Accept": "application/vnd.github+json, application/json, text/plain;q=0.9, */*;q=0.8",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            payload = response.read(limit + 1)
    except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
        raise MaterializationError(
            f"fixed-source fetch failed: {type(exc).__name__}"
        ) from exc
    if len(payload) > limit:
        raise MaterializationError(f"fixed-source response exceeded {limit} bytes")
    return payload


def github_json(url: str, token: str | None) -> Any:
    try:
        raw = request_bytes(url, limit=512 * 1024, token=token)
    except MaterializationError:
        if not token:
            raise
        raw = request_bytes(url, limit=512 * 1024, token=None)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise MaterializationError("GitHub source response was not JSON") from exc


def resolve_revision(repository: str, token: str | None) -> str:
    payload = github_json(f"{API_ORIGIN}/repos/{repository}/commits/main", token)
    revision = (
        str(payload.get("sha") or "").lower()
        if isinstance(payload, dict)
        else ""
    )
    if not HEX_40.fullmatch(revision):
        raise MaterializationError(f"{repository} main is not an exact revision")
    return revision


def fetch_second_brain(
    token: str | None,
) -> tuple[str, bytes, bytes]:
    revision = resolve_revision(SECOND_BRAIN_REPOSITORY, token)
    base = f"{RAW_ORIGIN}/{SECOND_BRAIN_REPOSITORY}/{revision}"
    state_raw = request_bytes(
        f"{base}/{STATE_PATH}", limit=MAX_JSON_BYTES
    )
    candidates_raw = request_bytes(
        f"{base}/{CANDIDATES_PATH}", limit=MAX_JSON_BYTES
    )
    return revision, state_raw, candidates_raw


def validate_frontier(
    state_raw: bytes,
    candidates_raw: bytes,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    state = json.loads(state_raw)
    if not isinstance(state, dict):
        raise MaterializationError("frontier state is not an object")
    expected = {
        "schema": "szl.second-brain.frontier-state/v1",
        "state": "REVIEW_REQUIRED",
        "public_content_access": "HANDLES_ONLY",
        "controller_content_access": "AUTHORIZED_CONTROLLER_ONLY",
        "training_authority": "NONE",
        "promotion_authority": "NONE",
        "execution_authority": "NONE",
        "merge_authority": "NONE",
        "lambda": "CONJECTURE_1",
    }
    for key, wanted in expected.items():
        if state.get(key) != wanted:
            raise MaterializationError(f"frontier authority mismatch: {key}")
    if int(state.get("private_graph_nodes_loaded") or 0) != 0:
        raise MaterializationError("private graph entered the public frontier")
    if int(state.get("raw_graph_nodes_admitted_to_gradients") or 0) != 0:
        raise MaterializationError("raw graph nodes entered gradients")

    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    canonical_lines: list[bytes] = []
    kinds: Counter[str] = Counter()
    domains: Counter[str] = Counter()
    source_repositories: set[str] = set()
    for line_number, line in enumerate(candidates_raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise MaterializationError(
                f"invalid candidate JSON at line {line_number}"
            ) from exc
        if not isinstance(row, dict):
            raise MaterializationError("frontier candidate is not an object")
        if row.get("schema") != "szl.second-brain.frontier-candidate/v1":
            raise MaterializationError("frontier candidate schema mismatch")
        node_id = str(row.get("id") or "")
        if not FRONTIER_ID.fullmatch(node_id) or node_id in seen:
            raise MaterializationError("frontier candidate id is invalid or duplicated")
        seen.add(node_id)
        repository = str(row.get("source_repository") or "")
        if repository not in ALLOWED_SOURCE_REPOSITORIES:
            raise MaterializationError("frontier source repository is outside the allowlist")
        revision = str(row.get("source_revision") or "")
        if not HEX_40.fullmatch(revision):
            raise MaterializationError("frontier source revision is not exact")
        if row.get("candidate_state") != "DISCOVERED_REVIEW_REQUIRED":
            raise MaterializationError("frontier candidate was promoted")
        if row.get("content_access") != "CONTROLLER_ONLY":
            raise MaterializationError("frontier candidate content boundary drifted")
        content = str(row.get("content") or "")
        measured = sha256_bytes(content.encode("utf-8"))
        if measured != row.get("content_sha256") or not HEX_64.fullmatch(measured):
            raise MaterializationError("frontier candidate content digest mismatch")
        kinds[str(row.get("source_kind") or "unknown")] += 1
        if row.get("quant_domain"):
            domains[str(row["quant_domain"])] += 1
        source_repositories.add(repository)
        rows.append(row)
        canonical_lines.append(canonical_bytes(row) + b"\n")

    measured_set = sha256_bytes(b"".join(canonical_lines))
    if measured_set != state.get("candidate_set_sha256"):
        raise MaterializationError("frontier candidate-set digest mismatch")
    if len(rows) != int(state.get("candidate_count") or -1):
        raise MaterializationError("frontier candidate count mismatch")
    if kinds["formula-authority"] != 1:
        raise MaterializationError("formula authority is missing")
    if kinds["attributed-formula"] != 30:
        raise MaterializationError("attributed formula count drifted")
    if kinds["executable-formula"] != 21:
        raise MaterializationError("executable formula count drifted")
    if kinds["quant-domain"] != 9:
        raise MaterializationError("quant domain count drifted")
    if len(domains) != 9:
        raise MaterializationError("quant domain identity count drifted")
    return state, rows


def select_handles(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep all formula tissue, then reserve one handle per connected system."""

    ordered = sorted(
        rows,
        key=lambda row: (
            KIND_ORDER.get(str(row.get("source_kind") or ""), 99),
            str(row.get("quant_domain") or ""),
            str(row["id"]),
        ),
    )
    formula_kinds = {
        "formula-authority",
        "quant-domain",
        "attributed-formula",
        "executable-formula",
    }
    selected = [
        row
        for row in ordered
        if str(row.get("source_kind") or "") in formula_kinds
    ]
    if len(selected) != 61:
        raise MaterializationError("complete formula tissue must contain 61 handles")

    selected_ids = {str(row["id"]) for row in selected}
    reserve_repositories = (
        "szl-holdings/anatomy",
        "szl-holdings/ouroboros",
        "szl-holdings/a11oy",
        "szl-holdings/szl-forge",
        "szl-holdings/szl-nemo",
    )
    for repository in reserve_repositories:
        candidate = next(
            (
                row
                for row in ordered
                if str(row["id"]) not in selected_ids
                and row.get("source_repository") == repository
            ),
            None,
        )
        if candidate is not None:
            selected.append(candidate)
            selected_ids.add(str(candidate["id"]))

    for row in ordered:
        if len(selected) >= MAX_HANDLES:
            break
        if str(row["id"]) in selected_ids:
            continue
        selected.append(row)
        selected_ids.add(str(row["id"]))
    if len(selected) < MAX_HANDLES:
        raise MaterializationError(
            f"frontier exposes {len(selected)} handles; {MAX_HANDLES} are required"
        )

    handles: list[dict[str, Any]] = []
    for row in selected[:MAX_HANDLES]:
        handle: dict[str, Any] = {
            "nodeId": row["id"],
            "title": str(row.get("title") or "")[:180],
            "sha256": row["content_sha256"],
            "repository": row["source_repository"],
            "revision": row["source_revision"],
            "path": row["source_path"],
            "kind": row["source_kind"],
            "admission": row["admission"],
            "candidateState": "DISCOVERED_REVIEW_REQUIRED",
            "contentAccess": "HANDLES_ONLY",
            "authority": "NONE",
        }
        if row.get("quant_domain"):
            handle["quantDomain"] = row["quant_domain"]
        handles.append(handle)
    return handles


def build_snapshot(
    second_brain_revision: str,
    state_raw: bytes,
    candidates_raw: bytes,
    dependency_revisions: dict[str, str],
) -> dict[str, Any]:
    state, rows = validate_frontier(state_raw, candidates_raw)
    for repository, revision in dependency_revisions.items():
        if not HEX_40.fullmatch(revision):
            raise MaterializationError(f"dependency revision is not exact: {repository}")
    handles = select_handles(rows)
    snapshot: dict[str, Any] = {
        "schema": "szl.a11oy.brain-frontier-holographic-v7/v1",
        "state": "SOURCE_BOUND_REVIEW_MEMORY",
        "surface": "A11OY_HOLOGRAPHIC_V7_BRAIN_FRONTIER",
        "sources": {
            "second_brain": {
                "repository": SECOND_BRAIN_REPOSITORY,
                "revision": second_brain_revision,
                "candidate_set_sha256": state["candidate_set_sha256"],
                "candidate_count": state["candidate_count"],
                "state_sha256": sha256_bytes(state_raw),
                "candidate_file_sha256": sha256_bytes(candidates_raw),
            },
            "anatomy": {
                "repository": ANATOMY_REPOSITORY,
                "revision": dependency_revisions[ANATOMY_REPOSITORY],
                "live_origin": "https://betterwithage-anatomy.hf.space",
                "holographic_v7_path": "/api/anatomy/v1/holographic-v7",
            },
            "formulas": {
                "repository": FORMULA_REPOSITORY,
                "revision": dependency_revisions[FORMULA_REPOSITORY],
            },
            "ouroboros": {
                "repository": OUROBOROS_REPOSITORY,
                "revision": dependency_revisions[OUROBOROS_REPOSITORY],
                "review_workflow": ".github/workflows/codex-frontier-review.yml",
            },
        },
        "formula_atlas": {
            "attributed_formula_count": 30,
            "executable_formula_count": 21,
            "quant_domain_count": 9,
            "locked_proven_formula_count": 8,
            "f_number_to_executable_mapping": "UNKNOWN_NOT_INFERRED",
            "lambda": "CONJECTURE_1",
        },
        "selected_handle_count": len(handles),
        "handles": handles,
        "authority": {
            "public_content_access": "HANDLES_ONLY",
            "controller_content_access": "NOT_EXPOSED_BY_A11OY_HOLOGRAPHIC",
            "training": "NONE",
            "promotion": "NONE",
            "execution": "NONE",
            "merge": "NONE",
            "provider_mutation": "NONE",
            "private_graph_present": False,
            "raw_graph_nodes_admitted_to_gradients": 0,
            "human_review_required": True,
        },
        "loop": [
            "OBSERVE",
            "ORIENT",
            "PROPOSE",
            "VERIFY",
            "HOLD",
        ],
    }
    snapshot["snapshot_sha256"] = sha256_bytes(canonical_bytes(snapshot))
    return snapshot


def atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent,
        prefix=f".{path.name}.",
        delete=False,
    ) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
        temporary = Path(handle.name)
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("console/assets/brain-frontier-v7.json"),
    )
    args = parser.parse_args()
    token = token_from_environment()
    second_brain_revision, state_raw, candidates_raw = fetch_second_brain(token)
    dependencies = {
        ANATOMY_REPOSITORY: resolve_revision(ANATOMY_REPOSITORY, token),
        FORMULA_REPOSITORY: resolve_revision(FORMULA_REPOSITORY, token),
        OUROBOROS_REPOSITORY: resolve_revision(OUROBOROS_REPOSITORY, token),
    }
    snapshot = build_snapshot(
        second_brain_revision,
        state_raw,
        candidates_raw,
        dependencies,
    )
    atomic_write(
        args.output,
        (json.dumps(snapshot, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
            "utf-8"
        ),
    )
    print(
        json.dumps(
            {
                "state": snapshot["state"],
                "second_brain_revision": second_brain_revision,
                "candidate_set_sha256": snapshot["sources"]["second_brain"][
                    "candidate_set_sha256"
                ],
                "selected_handle_count": snapshot["selected_handle_count"],
                "snapshot_sha256": snapshot["snapshot_sha256"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
