#!/usr/bin/env python3
"""Materialize the A11oy Holographic v7 Brain frontier snapshot.

The command surface consumes only source handles, revisions, counts, and digests.
Candidate content stays inside the Second Brain controller boundary. All remote
origins, repositories, and paths are fixed; generated output is deterministic and
carries no materialization timestamp, secret, private graph row, model weight, or
execution authority. Review observations retain the original run timestamp and expire.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from typing import Any

# Direct script execution must resolve the same tracked modules as offline tests.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from routers.governed_graph_operations import analyse_graph
from scripts.observe_ouroboros_frontier import (
    ObservationError,
    observe_receipt,
    unavailable_observation,
    validate_run_status,
)

SECOND_BRAIN_REPOSITORY = "szl-holdings/szl-second-brain"
ANATOMY_REPOSITORY = "szl-holdings/anatomy"
FORMULA_REPOSITORY = "szl-holdings/szl-formulas"
OUROBOROS_REPOSITORY = "szl-holdings/szl-ouroboros"
FORUM_REPOSITORY = "szl-holdings/szl-science-forum-corpus"
FORUM_PATH = "dataset/sources.public.jsonl"
MAX_FORUM_PILOTS = 2
MAX_RESEARCH_RECORDS = 96
METADATA_REVISION_KIND = "metadata-capture-sha256"
RESEARCH_REPOSITORIES = {"public-metadata/arxiv", "public-metadata/crossref"}
ARXIV_IDENTIFIER = re.compile(r"^\d{4}\.\d{4,5}v[1-9]\d{0,2}$")
DOI_IDENTIFIER = re.compile(r"^10\.\d{4,9}/[a-z0-9._;()/:-]{1,180}$")
STATE_PATH = "data/frontier-state.v1.json"
CANDIDATES_PATH = "data/frontier-candidates.public.jsonl"
API_ORIGIN = "https://api.github.com"
RAW_ORIGIN = "https://raw.githubusercontent.com"
USER_AGENT = "a11oy-holographic-brain-frontier-v7/1.0"
MAX_JSON_BYTES = 4 * 1024 * 1024
MAX_HANDLES = 72
OUROBOROS_WORKFLOW = ".github/workflows/codex-continuous-frontier.yml"
MAX_REVIEW_ARCHIVE_BYTES = 4 * 1024 * 1024
MAX_ARTIFACT_REDIRECTS = 3
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
FRONTIER_ID = re.compile(r"^frontier:[0-9a-f]{32}$")
ALLOWED_SOURCE_REPOSITORIES = {
    "szl-holdings/szl-formulas",
    "szl-holdings/szl-ouroboros",
    "szl-holdings/anatomy",
    "szl-holdings/a11oy",
    "szl-holdings/szl-forge",
    "szl-holdings/szl-nemo",
    "szl-holdings/szl-kernels",
    FORUM_REPOSITORY,
} | RESEARCH_REPOSITORIES
KIND_ORDER = {
    "formula-authority": 0,
    "quant-domain": 1,
    "attributed-formula": 2,
    "executable-formula": 3,
    "python-contract": 4,
    "estate-authority": 5,
    "estate-surface": 6,
    "source-document": 7,
    "forum-insight": 8,
    "research-metadata": 9,
}
SAFE_DOMAIN = re.compile(r"[a-z0-9][a-z0-9_-]{0,79}")
SAFE_PATH_SEGMENT = re.compile(r"[A-Za-z0-9_.-]+")
UNSAFE_TITLE = re.compile(r"[\x00-\x1f\x7f-\x9f\ud800-\udfff]")
SECRET_LIKE_METADATA = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----|"
    r"\b(?:sk-|gh[pousr]_|hf_)[A-Za-z0-9_-]{24,}\b|\bAKIA[0-9A-Z]{16}\b"
)
ALLOWED_ADMISSIONS = {
    "DISCOVERED_REVIEW_REQUIRED",
    "EXECUTABLE_CONSTRAINT_REVIEW_REQUIRED",
    "OPEN_NOT_EXECUTION_AUTHORITY",
    "REFERENCE_AND_CONSTRAINT_INPUT_ONLY",
    "REFERENCE_ONLY_EXECUTION_AUTHORITY_NONE",
    "REFERENCE_ONLY_NO_PROVIDER_MUTATION",
    "REFERENCE_ONLY_UNLESS_EXECUTABLE_MATCH_IS_EXPLICIT",
    "SOURCE_RECEIPT_REQUIRED_FOR_CURRENT_CLAIM",
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


def research_text(value: Any) -> bool:
    """Accept only the producer's bounded, sanitized scalar projection."""
    return (isinstance(value, str) and 0 < len(value) <= 240
            and not UNSAFE_TITLE.search(value)
            and not SECRET_LIKE_METADATA.search(value)
            and " ".join(re.sub(r"<[^>]{0,512}>", " ", value).split()) == value)


def research_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def research_candidate_text(value: str, *, limit: int = 1600) -> str:
    """Match Second Brain make_candidate's bounded public projection."""
    value = value.replace("\x00", " ").replace("\r", "\n")
    value = "\n".join(line.rstrip() for line in value.splitlines())
    return re.sub(r"\n{3,}", "\n\n", value).strip()[:limit]


def validate_research_metadata(row: dict[str, Any]) -> None:
    """Verify metadata captures as metadata, never as Git or admission receipts.

    The source file is bound to an exact Second Brain Git revision. These nested
    captures bind normalized public metadata, not independently attested API bytes;
    no paper text, remote URL, or metadata-provided instruction is fetched or run.
    """
    provenance = row.get("provenance")
    provenance_keys = {"provider", "identifier", "capture_sha256", "response_sha256",
                       "response_bytes", "request_url", "observed_at",
                       "source_authentication", "metadata"}
    if not isinstance(provenance, dict) or set(provenance) != provenance_keys:
        raise MaterializationError("research metadata provenance is invalid")
    metadata = provenance["metadata"]
    metadata_keys = {"provider", "identifier", "canonical_url", "title", "authors",
                     "published", "updated", "categories", "licence_urls",
                     "metadata_licence", "full_text_licence"}
    if not isinstance(metadata, dict) or set(metadata) != metadata_keys:
        raise MaterializationError("research metadata projection is invalid")
    provider, identifier = metadata["provider"], metadata["identifier"]
    if (not isinstance(provider, str) or provider not in {"arxiv", "crossref"} or not isinstance(identifier, str)
            or not (ARXIV_IDENTIFIER if provider == "arxiv" else DOI_IDENTIFIER).fullmatch(identifier)
            or provenance["provider"] != provider or provenance["identifier"] != identifier
            or row.get("source_repository") != f"public-metadata/{provider}"
            or row.get("source_path") != identifier
            or row.get("source_kind") != "research-metadata"
            or row.get("source_revision_kind") != METADATA_REVISION_KIND
            or row.get("admission") != "DISCOVERED_REVIEW_REQUIRED"
            or "quant_domain" in row):
        raise MaterializationError("research metadata source binding is invalid")
    prefix = "https://arxiv.org/abs/" if provider == "arxiv" else "https://doi.org/"
    if (metadata["canonical_url"] != prefix + identifier
            or not research_text(metadata["title"])
            or row.get("title") != research_candidate_text(metadata["title"], limit=180)
            or metadata["full_text_licence"] != "NOT_INFERRED"):
        raise MaterializationError("research metadata title, URL, or rights binding is invalid")
    for field, bound in (("authors", 32), ("categories", 12), ("licence_urls", 8)):
        values = metadata[field]
        if not isinstance(values, list) or len(values) > bound or not all(research_text(value) for value in values):
            raise MaterializationError("research metadata scalar bound is invalid")
    if provider == "arxiv":
        requests = {"https://export.arxiv.org/api/query?" + urllib.parse.urlencode(
            {"id_list": item, "max_results": 1}) for item in (identifier, identifier.split("v")[0])}
        if (metadata["metadata_licence"] != "CC0-1.0"
                or not research_timestamp(metadata["published"])
                or not research_timestamp(metadata["updated"])):
            raise MaterializationError("research arXiv date or licence binding is invalid")
    else:
        requests = {"https://api.crossref.org/works/" + urllib.parse.quote(identifier, safe="")}
        if metadata["metadata_licence"] != "NOT_DECLARED_BY_RESPONSE" or metadata["updated"] is not None:
            raise MaterializationError("research Crossref revision or licence was inferred")
        published = metadata["published"]
        if published is not None:
            if not isinstance(published, str) or not re.fullmatch(r"\d{4}(?:-\d{2})?(?:-\d{2})?", published):
                raise MaterializationError("research publication date is invalid")
            fields = [int(field) for field in published.split("-")]
            try:
                date(*(fields + [1] * (3 - len(fields))))
            except ValueError as exc:
                raise MaterializationError("research publication date is invalid") from exc
    if (not isinstance(provenance["request_url"], str) or provenance["request_url"] not in requests
            or not research_timestamp(provenance["observed_at"])
            or not isinstance(provenance["response_sha256"], str)
            or not HEX_64.fullmatch(provenance["response_sha256"])
            or type(provenance["response_bytes"]) is not int
            or not 0 < provenance["response_bytes"] <= 256 * 1024
            or provenance["source_authentication"] != "PUBLIC_HTTPS_METADATA_NOT_INDEPENDENT_ATTESTATION"):
        raise MaterializationError("research metadata response receipt is invalid")
    measured = sha256_bytes(canonical_bytes(metadata))
    if row.get("source_revision") != measured or provenance["capture_sha256"] != measured:
        raise MaterializationError("research metadata capture digest mismatch")
    content = "\n".join((metadata["title"], "Authors: " + ", ".join(metadata["authors"]),
                         "Identifier: " + identifier, "Publication date: " + str(metadata["published"]),
                         "Categories: " + ", ".join(metadata["categories"]),
                         "Metadata licence: " + metadata["metadata_licence"],
                         "Full text licence: NOT_INFERRED", "Source: " + metadata["canonical_url"]))
    if row.get("content") != research_candidate_text(content):
        raise MaterializationError("research metadata content projection mismatch")


def validate_metadata(row: dict[str, Any]) -> None:
    """Accept the same bounded, scalar metadata that the browser can display."""
    if (row.get("source_kind") == "research-metadata"
            or (isinstance(row.get("source_repository"), str)
                and row["source_repository"] in RESEARCH_REPOSITORIES)):
        validate_research_metadata(row)
        return
    if "source_revision_kind" in row:
        raise MaterializationError("Git source cannot claim a metadata revision kind")
    title = row.get("title")
    if (not isinstance(title, str) or not title.strip() or len(title) > 180
            or UNSAFE_TITLE.search(title)):
        raise MaterializationError("frontier candidate title is invalid")
    path = row.get("source_path")
    if (not isinstance(path, str) or len(path) > 512
            or any(part in {".", ".."} or not SAFE_PATH_SEGMENT.fullmatch(part)
                   for part in path.split("/"))):
        raise MaterializationError("frontier candidate path is invalid")
    kind = row.get("source_kind")
    if not isinstance(kind, str) or kind not in KIND_ORDER:
        raise MaterializationError("frontier candidate kind is invalid")
    admission = row.get("admission")
    if admission not in ALLOWED_ADMISSIONS:
        raise MaterializationError("frontier candidate admission is invalid")
    # Second Brain binds two operator-reviewed summaries to this one fixed source.
    if kind == "forum-insight" or row.get("source_repository") == FORUM_REPOSITORY:
        if (kind != "forum-insight"
                or row.get("source_repository") != FORUM_REPOSITORY
                or path != FORUM_PATH
                or admission != "DISCOVERED_REVIEW_REQUIRED"
                or "quant_domain" in row):
            raise MaterializationError("frontier forum pilot binding is invalid")
    domain = row.get("quant_domain")
    if "quant_domain" in row or kind == "quant-domain":
        if not isinstance(domain, str) or not SAFE_DOMAIN.fullmatch(domain):
            raise MaterializationError("frontier candidate quant domain is invalid")


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


class _NoArtifactRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _artifact_storage_location(value: Any) -> str:
    """Admit only the fixed API's HTTPS artifact-storage redirect, without auth."""
    if not isinstance(value, str) or len(value) > 16384:
        raise MaterializationError("artifact redirect is invalid")
    try:
        parts = urllib.parse.urlsplit(value)
        valid = (
            parts.scheme == "https"
            and parts.username is None
            and parts.password is None
            and parts.port in {None, 443}
            and not parts.fragment
            and re.fullmatch(r"[a-z0-9-]+\.blob\.core\.windows\.net", parts.hostname or "")
        )
    except ValueError as exc:
        raise MaterializationError("artifact redirect is invalid") from exc
    if not valid:
        raise MaterializationError("artifact redirect origin is not admitted")
    return value


def download_ouroboros_artifact(artifact_id: int, token: str | None) -> bytes:
    """Read one artifact; never forward the GitHub bearer to redirected storage."""
    if type(artifact_id) is not int or artifact_id <= 0:
        raise MaterializationError("artifact identity is invalid")
    url = f"{API_ORIGIN}/repos/{OUROBOROS_REPOSITORY}/actions/artifacts/{artifact_id}/zip"
    opener = urllib.request.build_opener(_NoArtifactRedirect())
    for hop in range(MAX_ARTIFACT_REDIRECTS + 1):
        headers = {"User-Agent": USER_AGENT, "Accept": "application/vnd.github+json"}
        if hop == 0:
            headers["X-GitHub-Api-Version"] = "2022-11-28"
            if token:
                headers["Authorization"] = f"Bearer {token}"
        request = urllib.request.Request(url, headers=headers)
        try:
            with opener.open(request, timeout=45) as response:
                payload = response.read(MAX_REVIEW_ARCHIVE_BYTES + 1)
        except urllib.error.HTTPError as exc:
            location = exc.headers.get("Location") if exc.headers is not None else None
            redirect = exc.code in {301, 302, 303, 307, 308}
            exc.close()
            if not redirect or hop == MAX_ARTIFACT_REDIRECTS:
                raise MaterializationError("artifact download is unavailable") from None
            url = _artifact_storage_location(location)
            continue
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            raise MaterializationError("artifact download is unavailable") from exc
        if len(payload) > MAX_REVIEW_ARCHIVE_BYTES:
            raise MaterializationError("artifact archive exceeds the byte bound")
        return payload
    raise MaterializationError("artifact redirect bound exceeded")


def fetch_ouroboros_observation(
    expected: dict[str, Any], token: str | None, *, now: datetime | None = None,
) -> dict[str, Any]:
    """Observe only the latest fixed workflow; an older success is never a fallback."""
    run = None

    def unavailable(state: str, reason: str) -> dict[str, Any]:
        return unavailable_observation(expected, state=state, reason=reason, run=run)

    try:
        runs = github_json(
            f"{API_ORIGIN}/repos/{OUROBOROS_REPOSITORY}/actions/workflows/"
            "codex-continuous-frontier.yml/runs?branch=main&per_page=1",
            token,
        )
    except MaterializationError:
        return unavailable("UNAVAILABLE", "RUN_METADATA_UNAVAILABLE")
    if (not isinstance(runs, dict) or type(runs.get("total_count")) is not int
            or runs["total_count"] < 0 or not isinstance(runs.get("workflow_runs"), list)
            or len(runs["workflow_runs"]) > 1):
        return unavailable("REJECTED", "RUN_LIST_REJECTED")
    if not runs["workflow_runs"]:
        return unavailable("UNAVAILABLE", "REVIEW_RUN_UNAVAILABLE")
    run = runs["workflow_runs"][0]
    try:
        terminal = validate_run_status(expected, run, now=now)
    except ObservationError:
        return unavailable("REJECTED", "RUN_METADATA_REJECTED")
    if terminal is not None:
        return terminal

    run_id, attempt = run["id"], run["run_attempt"]
    name = f"ouroboros-frontier-{run_id}-{attempt}"
    try:
        listing = github_json(
            f"{API_ORIGIN}/repos/{OUROBOROS_REPOSITORY}/actions/runs/{run_id}/artifacts?per_page=100",
            token,
        )
    except MaterializationError:
        return unavailable("UNAVAILABLE", "ARTIFACT_METADATA_UNAVAILABLE")
    if (not isinstance(listing, dict) or type(listing.get("total_count")) is not int
            or not 0 <= listing["total_count"] <= 100
            or not isinstance(listing.get("artifacts"), list)
            or len(listing["artifacts"]) != listing["total_count"]
            or not all(isinstance(item, dict) for item in listing["artifacts"])):
        return unavailable("REJECTED", "ARTIFACT_LIST_REJECTED")
    matches = [item for item in listing["artifacts"] if item.get("name") == name]
    if not matches:
        return unavailable("UNAVAILABLE", "REVIEW_ARTIFACT_UNAVAILABLE")
    if len(matches) != 1:
        return unavailable("REJECTED", "REVIEW_ARTIFACT_AMBIGUOUS")
    artifact = matches[0]
    if artifact.get("expired") is True:
        return unavailable("UNAVAILABLE", "REVIEW_ARTIFACT_EXPIRED")
    try:
        archive = download_ouroboros_artifact(artifact.get("id"), token)
    except MaterializationError:
        return unavailable("UNAVAILABLE", "ARTIFACT_DOWNLOAD_UNAVAILABLE")
    try:
        return observe_receipt(archive, expected=expected, run=run, artifact=artifact, now=now)
    except ObservationError:
        return unavailable("REJECTED", "REVIEW_RECEIPT_REJECTED")


def build_advisory_dag(expected: dict[str, Any]) -> dict[str, Any]:
    """Analyze the existing review composition; this does not schedule its nodes."""
    candidate_input = "brain-candidates:sha256:" + expected["candidate_set_sha256"]
    controller_input = "ouroboros-controller:git:" + expected["controller_revision"]
    return analyse_graph({
        "schema": "szl.governed-graph/v1",
        "graph_id": "brain-frontier-review-" + expected["candidate_set_sha256"][:20],
        "goal": (
            "Inspect the source-bound Second Brain and existing Ouroboros advisory review composition. "
            "This MODELED topology grants no execution authority and makes no claim that its nodes ran."
        ),
        "external_inputs": [candidate_input, controller_input],
        "nodes": [
            {"id": "OBSERVE", "label": "Bind fixed public source packet", "role": "scope",
             "consumes": [candidate_input, controller_input], "produces": ["source.packet"],
             "authority": "READ_ONLY"},
            {"id": "ORIENT", "label": "Prepare review input from source handles", "role": "reducer",
             "depends_on": ["OBSERVE"], "consumes": ["source.packet"],
             "produces": ["review.input"], "authority": "READ_ONLY"},
            {"id": "PROPOSE", "label": "One bounded advisory reviewer attempt", "role": "loop",
             "depends_on": ["ORIENT"], "consumes": ["review.input"],
             "produces": ["untrusted.review"], "authority": "PROPOSE", "max_iterations": 1,
             "exit_conditions": ["review_returned", "review_failed", "budget_exhausted"]},
            {"id": "VERIFY", "label": "Validate source-bound review receipt", "role": "verifier",
             "depends_on": ["OBSERVE", "PROPOSE"], "consumes": ["source.packet", "untrusted.review"],
             "produces": ["advisory.observation"], "authority": "READ_ONLY",
             "fresh_context": True, "verifier_for": ["PROPOSE"]},
            {"id": "HOLD", "label": "Hold recommendations for human admission", "role": "governance",
             "depends_on": ["VERIFY"], "consumes": ["advisory.observation"],
             "produces": ["public.aggregate"], "authority": "READ_ONLY"},
        ],
        "anchors": [{
            "id": "exact-source-and-advisory-boundary", "type": "source",
            "nodes": ["OBSERVE", "VERIFY", "HOLD"], "required": True,
            "description": (
                "Require exact input, controller and receipt binding. Recorded review is untrusted; "
                "a matching digest does not establish truth, signature or production readiness."
            ),
        }],
        "budget": {"max_nodes": 5, "max_parallel": 1, "max_depth": 5, "max_total_iterations": 1},
    })


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
        validate_metadata(row)
        node_id = str(row.get("id") or "")
        if not FRONTIER_ID.fullmatch(node_id) or node_id in seen:
            raise MaterializationError("frontier candidate id is invalid or duplicated")
        seen.add(node_id)
        repository = str(row.get("source_repository") or "")
        if repository not in ALLOWED_SOURCE_REPOSITORIES:
            raise MaterializationError("frontier source repository is outside the allowlist")
        revision = str(row.get("source_revision") or "")
        revision_pattern = HEX_64 if row.get("source_kind") == "research-metadata" else HEX_40
        if not revision_pattern.fullmatch(revision):
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
    if type(state.get("candidate_count")) is not int or len(rows) != state["candidate_count"]:
        raise MaterializationError("frontier candidate count mismatch")
    if kinds["forum-insight"] > MAX_FORUM_PILOTS:
        raise MaterializationError("frontier forum pilot count drifted")
    if kinds["research-metadata"] > MAX_RESEARCH_RECORDS:
        raise MaterializationError("frontier research metadata count exceeded its bound")
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
    domain_ids = {row["quant_domain"] for row in rows if row["source_kind"] == "quant-domain"}
    if len(domain_ids) != 9 or set(domains) != domain_ids:
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
        FORMULA_REPOSITORY,
        "szl-holdings/anatomy",
        OUROBOROS_REPOSITORY,
        "szl-holdings/a11oy",
        "szl-holdings/szl-forge",
        "szl-holdings/szl-nemo",
        "szl-holdings/szl-kernels",
    )
    for repository in reserve_repositories:
        if any(row.get("source_repository") == repository for row in selected):
            continue
        candidate = next(
            (
                row
                for row in ordered
                if str(row["id"]) not in selected_ids
                and row.get("source_repository") == repository
            ),
            None,
        )
        if candidate is None:
            raise MaterializationError(
                f"reserved repository has no candidate: {repository}"
            )
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
            "title": row["title"],
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
        if row["source_kind"] == "research-metadata":
            handle["revisionKind"] = METADATA_REVISION_KIND
        handles.append(handle)
    return handles


def build_snapshot(
    second_brain_revision: str,
    state_raw: bytes,
    candidates_raw: bytes,
    dependency_revisions: dict[str, str],
    *,
    observe_ouroboros: bool = False,
    token: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    if not isinstance(second_brain_revision, str) or not HEX_40.fullmatch(second_brain_revision):
        raise MaterializationError("second brain revision is not exact")
    state, rows = validate_frontier(state_raw, candidates_raw)
    if set(dependency_revisions) != {ANATOMY_REPOSITORY, FORMULA_REPOSITORY, OUROBOROS_REPOSITORY}:
        raise MaterializationError("dependency repository set is incomplete or unexpected")
    for repository, revision in dependency_revisions.items():
        if not isinstance(revision, str) or not HEX_40.fullmatch(revision):
            raise MaterializationError(f"dependency revision is not exact: {repository}")
    expected_review = {
        "controller_revision": dependency_revisions[OUROBOROS_REPOSITORY],
        "second_brain_revision": second_brain_revision,
        "state_file_sha256": sha256_bytes(state_raw),
        "candidate_file_sha256": sha256_bytes(candidates_raw),
        "candidate_set_sha256": state["candidate_set_sha256"],
        "candidate_count": state["candidate_count"],
        "candidate_ids": [row["id"] for row in rows],
    }
    handles = select_handles(rows)
    observation = (
        fetch_ouroboros_observation(expected_review, token, now=now)
        if observe_ouroboros
        else unavailable_observation(expected_review, state="UNAVAILABLE", reason="REVIEW_NOT_OBSERVED")
    )
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
                "review_workflow": OUROBOROS_WORKFLOW,
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
        "ouroboros_observation": observation,
        "advisory_dag": build_advisory_dag(expected_review),
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
        observe_ouroboros=True,
        token=token,
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
                "ouroboros_observation_state": snapshot["ouroboros_observation"]["state"],
                "ouroboros_observation_reason": snapshot["ouroboros_observation"]["reason"],
                "advisory_dag_execution": snapshot["advisory_dag"]["execution"]["mode"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
