#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "docs" / "huggingface-space-source-map-v1.json"
HF_ORG = "SZLHOLDINGS"
GITHUB_ORG = "szl-holdings"
HF_SPACES_API = "https://huggingface.co/api/spaces"
GITHUB_API = "https://api.github.com"
GITHUB_URL_RE = re.compile(
    r"https?://github\.com/(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)",
    re.IGNORECASE,
)
SOURCE_FIELD_KEYS = {
    "source_repo",
    "source_repository",
    "source_url",
    "github",
    "github_repo",
    "github_repository",
    "repository",
    "repo_url",
}
WORKFLOW_NAME_TOKENS = ("hf", "hugging", "space", "deploy", "publish")
SHA40 = re.compile(r"^[0-9a-f]{40}$")


class SourceMapError(RuntimeError):
    pass


def _headers(*, github: bool = False) -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json" if github else "application/json",
        "User-Agent": "SZL-HF-Space-source-map/1.0",
    }
    if github:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
            headers["X-GitHub-Api-Version"] = "2022-11-28"
    return headers


def _request(url: str, *, github: bool = False, timeout: int = 45) -> bytes:
    request = urllib.request.Request(url, headers=_headers(github=github))
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


def _request_json(url: str, *, github: bool = False) -> Any:
    return json.loads(_request(url, github=github))


def _safe_request_json(url: str, *, github: bool = False) -> tuple[int, Any]:
    try:
        return 200, _request_json(url, github=github)
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", "replace")
        try:
            payload: Any = json.loads(body)
        except json.JSONDecodeError:
            payload = {"message": body}
        return error.code, payload


def _safe_request_text(url: str) -> tuple[int, str]:
    try:
        return 200, _request(url).decode("utf-8", "replace")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def fetch_spaces(author: str = HF_ORG) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"author": author, "limit": 100, "full": "true"})
    payload = _request_json(f"{HF_SPACES_API}?{query}")
    if not isinstance(payload, list):
        raise SourceMapError("Hugging Face Spaces API did not return a list")
    prefix = author.lower() + "/"
    records = [
        item
        for item in payload
        if isinstance(item, dict)
        and isinstance(item.get("id"), str)
        and item["id"].lower().startswith(prefix)
    ]
    records.sort(key=lambda item: item["id"].lower())
    if not records:
        raise SourceMapError(f"no public Spaces were returned for {author}")
    return records


def fetch_space_readme(repo_id: str) -> tuple[int, str, str]:
    quoted = "/".join(urllib.parse.quote(part, safe="") for part in repo_id.split("/", 1))
    candidates = (
        f"https://huggingface.co/spaces/{quoted}/raw/main/README.md",
        f"https://huggingface.co/spaces/{quoted}/resolve/main/README.md",
    )
    last_status = 404
    for url in candidates:
        status, text = _safe_request_text(url)
        last_status = status
        if status == 200:
            return status, text, url
    return last_status, "", candidates[0]


def parse_front_matter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    values: dict[str, str] = {}
    for line in text[4:end].splitlines():
        match = re.match(r"^([A-Za-z0-9_-]+)\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        value = match.group(2).strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[match.group(1).lower()] = value.strip()
    return values


def normalize_repo_name(value: str) -> str:
    text = value.strip().lower()
    if text.endswith(".git"):
        text = text[:-4]
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _clean_repo_token(value: str) -> str:
    return value.rstrip(".,);]}>\"'").removesuffix(".git")


def extract_explicit_github_repositories(
    readme: str,
    front_matter: dict[str, str],
    github_org: str = GITHUB_ORG,
) -> list[str]:
    candidates: set[str] = set()
    searchable = [readme]
    searchable.extend(
        value for key, value in front_matter.items() if key in SOURCE_FIELD_KEYS
    )
    for text in searchable:
        for match in GITHUB_URL_RE.finditer(text):
            owner = match.group("owner")
            repo = _clean_repo_token(match.group("repo"))
            if owner.lower() == github_org.lower() and repo:
                candidates.add(f"{github_org}/{repo}")
    return sorted(candidates, key=str.lower)


def inferred_repo_candidates(space_id: str) -> list[str]:
    name = space_id.split("/", 1)[1]
    raw = name.strip()
    candidates = [raw, raw.replace("_", "-"), raw.replace(".", "-")]
    lowered = normalize_repo_name(raw)
    for prefix in ("szl-", "szl_", "a11oy-", "a11oy_"):
        if raw.lower().startswith(prefix):
            candidates.append(raw[len(prefix) :])
    candidates.append(lowered)
    unique: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.strip("-/")
        key = candidate.lower()
        if candidate and key not in seen:
            seen.add(key)
            unique.append(f"{GITHUB_ORG}/{candidate}")
    return unique


def _repo_api_url(full_name: str) -> str:
    owner, repo = full_name.split("/", 1)
    return f"{GITHUB_API}/repos/{urllib.parse.quote(owner)}/{urllib.parse.quote(repo)}"


def resolve_github_repo(full_name: str) -> dict[str, Any] | None:
    status, payload = _safe_request_json(_repo_api_url(full_name), github=True)
    if status == 404:
        return None
    if status != 200 or not isinstance(payload, dict):
        raise SourceMapError(f"GitHub repository lookup failed for {full_name}: HTTP {status}")
    return {
        "full_name": payload.get("full_name") or full_name,
        "html_url": payload.get("html_url"),
        "default_branch": payload.get("default_branch"),
        "archived": bool(payload.get("archived")),
        "disabled": bool(payload.get("disabled")),
        "visibility": payload.get("visibility"),
        "pushed_at": payload.get("pushed_at"),
    }


def list_workflow_candidates(full_name: str) -> dict[str, Any]:
    url = _repo_api_url(full_name) + "/contents/.github/workflows"
    status, payload = _safe_request_json(url, github=True)
    if status == 404:
        return {"state": "UNAVAILABLE", "paths": []}
    if status != 200 or not isinstance(payload, list):
        return {"state": "ERROR", "http_status": status, "paths": []}
    paths = sorted(
        str(item.get("path"))
        for item in payload
        if isinstance(item, dict)
        and item.get("type") == "file"
        and isinstance(item.get("path"), str)
        and any(token in str(item.get("name", "")).lower() for token in WORKFLOW_NAME_TOKENS)
    )
    return {
        "state": "OBSERVED",
        "paths": paths,
        "candidate_count": len(paths),
        "single_writer_candidate": len(paths) == 1,
    }


def _runtime(record: dict[str, Any]) -> dict[str, Any]:
    value = record.get("runtime")
    return value if isinstance(value, dict) else {}


def _runtime_sha(record: dict[str, Any]) -> str | None:
    runtime = _runtime(record)
    raw = runtime.get("raw") if isinstance(runtime.get("raw"), dict) else {}
    for value in (runtime.get("sha"), raw.get("sha")):
        if isinstance(value, str) and SHA40.fullmatch(value.lower()):
            return value.lower()
    return None


def _runtime_stage(record: dict[str, Any]) -> str:
    value = _runtime(record).get("stage")
    return value.upper() if isinstance(value, str) and value else "UNAVAILABLE"


def _space_sdk(record: dict[str, Any]) -> str | None:
    card = record.get("cardData") if isinstance(record.get("cardData"), dict) else {}
    value = record.get("sdk") or card.get("sdk")
    return value.lower() if isinstance(value, str) and value else None


def select_source_mapping(
    space_id: str,
    explicit: Iterable[str],
    resolver: Callable[[str], dict[str, Any] | None],
) -> dict[str, Any]:
    explicit_list = list(dict.fromkeys(explicit))
    verified_explicit: list[dict[str, Any]] = []
    missing_explicit: list[str] = []
    for candidate in explicit_list:
        resolved = resolver(candidate)
        if resolved:
            verified_explicit.append(resolved)
        else:
            missing_explicit.append(candidate)

    if len(verified_explicit) == 1 and not missing_explicit:
        return {
            "state": "EXACT",
            "evidence": "README_OR_CARD_EXPLICIT_URL",
            "canonical": verified_explicit[0],
            "candidates": verified_explicit,
            "missing_candidates": [],
        }
    if verified_explicit or missing_explicit:
        return {
            "state": "DIVERGENT" if len(verified_explicit) != 1 or missing_explicit else "EXACT",
            "evidence": "MULTIPLE_OR_UNRESOLVED_EXPLICIT_URLS",
            "canonical": None,
            "candidates": verified_explicit,
            "missing_candidates": missing_explicit,
        }

    inferred_resolved: list[dict[str, Any]] = []
    for candidate in inferred_repo_candidates(space_id):
        resolved = resolver(candidate)
        if resolved:
            inferred_resolved.append(resolved)
    deduped = {
        str(item["full_name"]).lower(): item for item in inferred_resolved
    }
    inferred_resolved = [deduped[key] for key in sorted(deduped)]
    if len(inferred_resolved) == 1:
        return {
            "state": "INFERRED",
            "evidence": "NORMALIZED_NAME_MATCH",
            "canonical": inferred_resolved[0],
            "candidates": inferred_resolved,
            "missing_candidates": [],
        }
    if len(inferred_resolved) > 1:
        return {
            "state": "DIVERGENT",
            "evidence": "MULTIPLE_NORMALIZED_NAME_MATCHES",
            "canonical": None,
            "candidates": inferred_resolved,
            "missing_candidates": [],
        }
    return {
        "state": "UNAVAILABLE",
        "evidence": "NO_EXPLICIT_OR_NORMALIZED_SOURCE_REPOSITORY",
        "canonical": None,
        "candidates": [],
        "missing_candidates": [],
    }


def build_source_map(
    records: list[dict[str, Any]],
    readme_fetcher: Callable[[str], tuple[int, str, str]] = fetch_space_readme,
    resolver: Callable[[str], dict[str, Any] | None] = resolve_github_repo,
    workflow_lister: Callable[[str], dict[str, Any]] = list_workflow_candidates,
) -> dict[str, Any]:
    repo_cache: dict[str, dict[str, Any] | None] = {}
    workflow_cache: dict[str, dict[str, Any]] = {}

    def cached_resolver(full_name: str) -> dict[str, Any] | None:
        key = full_name.lower()
        if key not in repo_cache:
            repo_cache[key] = resolver(full_name)
        return repo_cache[key]

    spaces: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()
    sdk_counts: Counter[str] = Counter()
    workflow_state_counts: Counter[str] = Counter()

    for record in records:
        space_id = str(record["id"])
        status, readme, readme_url = readme_fetcher(space_id)
        front = parse_front_matter(readme) if status == 200 else {}
        explicit = extract_explicit_github_repositories(readme, front)
        mapping = select_source_mapping(space_id, explicit, cached_resolver)
        canonical = mapping.get("canonical")
        workflows: dict[str, Any]
        if isinstance(canonical, dict) and isinstance(canonical.get("full_name"), str):
            repo_key = canonical["full_name"].lower()
            if repo_key not in workflow_cache:
                workflow_cache[repo_key] = workflow_lister(canonical["full_name"])
            workflows = workflow_cache[repo_key]
        else:
            workflows = {"state": "BLOCKED_SOURCE_MAPPING", "paths": []}

        state_counts[mapping["state"]] += 1
        sdk_counts[_space_sdk(record) or "UNAVAILABLE"] += 1
        workflow_state_counts[str(workflows.get("state"))] += 1
        spaces.append(
            {
                "space_id": space_id,
                "hf_repository_sha": record.get("sha") if isinstance(record.get("sha"), str) else None,
                "hf_runtime_sha": _runtime_sha(record),
                "hf_runtime_stage": _runtime_stage(record),
                "sdk": _space_sdk(record),
                "readme": {
                    "http_status": status,
                    "url": readme_url,
                    "sha256": hashlib.sha256(readme.encode("utf-8")).hexdigest() if status == 200 else None,
                    "front_matter_keys": sorted(front),
                },
                "explicit_github_repositories": explicit,
                "source_mapping": mapping,
                "workflow_candidates": workflows,
            }
        )

    spaces.sort(key=lambda item: item["space_id"].lower())
    return {
        "schema": "szl.hf-space-source-map/v1",
        "organization": HF_ORG,
        "github_organization": GITHUB_ORG,
        "remote_mutation": False,
        "summary": {
            "spaces_observed": len(spaces),
            "mapping_states": dict(sorted(state_counts.items())),
            "sdk_counts": dict(sorted(sdk_counts.items())),
            "workflow_states": dict(sorted(workflow_state_counts.items())),
            "exact_or_inferred_sources": sum(
                state_counts[state] for state in ("EXACT", "INFERRED")
            ),
            "blocked_source_mappings": sum(
                state_counts[state] for state in ("DIVERGENT", "UNAVAILABLE")
            ),
        },
        "spaces": spaces,
    }


def _render(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        payload = build_source_map(fetch_spaces())
    except (SourceMapError, OSError, ValueError, json.JSONDecodeError) as error:
        print(json.dumps({"status": "FAIL", "error": str(error)}, indent=2, sort_keys=True))
        return 1
    rendered = _render(payload)
    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
            print(
                json.dumps(
                    {
                        "status": "DRIFT",
                        "output": str(args.output),
                        "summary": payload["summary"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 1
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "PASS",
                "output": str(args.output),
                "summary": payload["summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
