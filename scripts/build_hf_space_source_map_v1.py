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
HF_PAGE_SIZE = 100
MAX_HF_PAGES = 20
MAX_HF_SPACES = 2000
MAX_HF_PAGE_BYTES = 4 * 1024 * 1024
MAX_SOURCE_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_LINK_HEADER_BYTES = 16384
REPO_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*")
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
SHA40 = re.compile(r"^(?!0{40}$)[0-9a-f]{40}$")
SOURCE_PROSE_PREFIXES = (
    re.compile(
        r"^(?:[-*+]\s+)?(?:\*\*|__)?"
        r"(?:canonical source|source repository|github source of record)"
        r"(?:\*\*|__)?\s*:(?:\*\*|__)?\s*(.*)$",
        re.IGNORECASE,
    ),
    re.compile(
        r"^(?:[-*+]\s+)?(?:\*\*|__)?"
        r"(?:the canonical source is|this space is published from)"
        r"(?:\*\*|__)?(?:\s+(.*)|$)",
        re.IGNORECASE,
    ),
)
SOURCE_EXPRESSION_RE = re.compile(
    r"\[[^\]\n]+\]\([^()\s]+\)|`[^`\n]+`|<https?://[^<>\s]+>|"
    r"https?://[^\s)<>]+|[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_.-]+",
    re.IGNORECASE,
)


class SourceMapError(RuntimeError):
    pass


class SourceDeclarationError(SourceMapError):
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
        content = response.read(MAX_SOURCE_RESPONSE_BYTES + 1)
        if len(content) > MAX_SOURCE_RESPONSE_BYTES:
            raise SourceMapError("source evidence response exceeds the byte limit")
        return content


def _request_json(url: str, *, github: bool = False) -> Any:
    return json.loads(_request(url, github=github))


def _safe_request_json(url: str, *, github: bool = False) -> tuple[int, Any]:
    try:
        return 200, _request_json(url, github=github)
    except urllib.error.HTTPError as error:
        body = error.read(MAX_SOURCE_RESPONSE_BYTES).decode("utf-8", "replace")
        try:
            payload: Any = json.loads(body)
        except json.JSONDecodeError:
            payload = {"message": body}
        return error.code, payload


def _safe_request_bytes(url: str) -> tuple[int, bytes]:
    try:
        return 200, _request(url)
    except urllib.error.HTTPError as error:
        return error.code, error.read(MAX_SOURCE_RESPONSE_BYTES)


class _RejectPaginationRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SourceMapError("Hugging Face Spaces pagination attempted a redirect")


def _request_hf_space_page(url: str) -> tuple[Any, str | None]:
    request = urllib.request.Request(url, headers=_headers())
    opener = urllib.request.build_opener(_RejectPaginationRedirect())
    with opener.open(request, timeout=45) as response:
        if response.status != 200:
            raise SourceMapError(f"Hugging Face Spaces API returned HTTP {response.status}")
        raw = response.read(MAX_HF_PAGE_BYTES + 1)
        if len(raw) > MAX_HF_PAGE_BYTES:
            raise SourceMapError("Hugging Face Spaces page exceeds the byte limit")
        links = response.headers.get_all("Link", [])
        return json.loads(raw.decode("utf-8", errors="strict")), ",".join(links) if links else None


def _validated_hf_page_url(url: str, author: str) -> str:
    if not isinstance(url, str) or not url.isascii() or len(url) > MAX_LINK_HEADER_BYTES or any(
        character.isspace() or ord(character) < 32 or ord(character) == 127
        for character in url
    ):
        raise SourceMapError("Hugging Face Spaces pagination URL is malformed")
    if re.search(r"%(?![0-9a-fA-F]{2})", url):
        raise SourceMapError("Hugging Face Spaces pagination URL has invalid percent encoding")
    parts = urllib.parse.urlsplit(url)
    if (
        parts.scheme != "https"
        or parts.netloc != "huggingface.co"
        or parts.path != "/api/spaces"
        or parts.fragment
    ):
        raise SourceMapError("Hugging Face Spaces pagination changed origin or path")
    try:
        pairs = urllib.parse.parse_qsl(
            parts.query, keep_blank_values=True, strict_parsing=True,
            encoding="utf-8", errors="strict", max_num_fields=4,
        )
    except ValueError as error:
        raise SourceMapError("Hugging Face Spaces pagination query is malformed") from error
    query = dict(pairs)
    required = {"author": author, "limit": str(HF_PAGE_SIZE), "full": "true"}
    if (
        len(pairs) != len(query)
        or set(query) - {"author", "limit", "full", "cursor"}
        or any(query.get(key) != value for key, value in required.items())
        or ("cursor" in query and (
            not query["cursor"]
            or any(ord(character) < 32 or ord(character) == 127 for character in query["cursor"])
        ))
    ):
        raise SourceMapError("Hugging Face Spaces pagination changed the query scope")
    return f"{HF_SPACES_API}?{urllib.parse.urlencode(sorted(query.items()))}"


def _next_hf_page(link_header: str | None, author: str) -> str | None:
    if link_header is None:
        return None
    if (
        not isinstance(link_header, str)
        or not link_header.isascii()
        or not link_header.strip()
        or len(link_header) > MAX_LINK_HEADER_BYTES
        or any(character in "\r\n\x00" for character in link_header)
    ):
        raise SourceMapError("Hugging Face Spaces Link header is malformed or oversized")
    next_url: str | None = None
    for part in link_header.split(","):
        match = re.fullmatch(
            r'\s*<([^<>\s]+)>\s*;\s*rel=(?:"([a-z ]+)"|([a-z]+))\s*', part
        )
        if not match:
            raise SourceMapError("Hugging Face Spaces Link header is malformed")
        url = _validated_hf_page_url(match.group(1), author)
        relations = (match.group(2) or match.group(3)).split()
        if not relations or any(
            relation not in {"next", "prev", "first", "last"}
            for relation in relations
        ):
            raise SourceMapError("Hugging Face Spaces Link header has an unsupported relation")
        if "next" in relations:
            if next_url is not None or relations.count("next") != 1:
                raise SourceMapError("Hugging Face Spaces Link header repeats the next relation")
            next_url = url
    return next_url


def fetch_spaces(author: str = HF_ORG) -> list[dict[str, Any]]:
    if not isinstance(author, str) or not REPO_NAME_RE.fullmatch(author):
        raise SourceMapError("Hugging Face Spaces author is invalid")
    query = urllib.parse.urlencode({"author": author, "limit": HF_PAGE_SIZE, "full": "true"})
    url: str | None = _validated_hf_page_url(f"{HF_SPACES_API}?{query}", author)
    records: list[dict[str, Any]] = []
    seen_pages: set[str] = set()
    seen_ids: set[str] = set()
    while url is not None:
        if url in seen_pages:
            raise SourceMapError("Hugging Face Spaces pagination repeated a page")
        if len(seen_pages) >= MAX_HF_PAGES:
            raise SourceMapError("Hugging Face Spaces pagination exceeds the page limit")
        seen_pages.add(url)
        payload, link_header = _request_hf_space_page(url)
        if not isinstance(payload, list) or len(payload) > HF_PAGE_SIZE:
            raise SourceMapError("Hugging Face Spaces API returned an invalid or oversized page")
        for item in payload:
            space_id = item.get("id") if isinstance(item, dict) else None
            if not isinstance(space_id, str) or space_id.count("/") != 1:
                raise SourceMapError("Hugging Face Spaces API returned an invalid repository ID")
            owner, name = space_id.split("/")
            if owner.lower() != author.lower() or not REPO_NAME_RE.fullmatch(name):
                raise SourceMapError("Hugging Face Spaces API returned an out-of-scope repository")
            if str(item.get("author", author)).lower() != author.lower():
                raise SourceMapError(f"{space_id} has conflicting author metadata")
            if item.get("private") is not False:
                raise SourceMapError(f"{space_id} has no confirmed public visibility")
            require_sha40(item.get("sha"), label=f"{space_id} Hugging Face repository revision")
            if space_id.lower() in seen_ids:
                raise SourceMapError(f"Hugging Face Spaces pagination repeated repository {space_id}")
            seen_ids.add(space_id.lower())
            records.append(item)
            if len(records) > MAX_HF_SPACES:
                raise SourceMapError("Hugging Face Spaces pagination exceeds the repository limit")
        url = _next_hf_page(link_header, author)
        if not payload and url is not None:
            raise SourceMapError("Hugging Face Spaces pagination returned an empty nonterminal page")
    if not records:
        raise SourceMapError(f"no public Spaces were returned for {author}")
    return sorted(records, key=lambda item: item["id"].lower())


def require_sha40(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not SHA40.fullmatch(value.lower()):
        raise SourceMapError(
            f"{label} must be an exact 40-character hexadecimal commit SHA"
        )
    return value.lower()


def fetch_space_readme(repo_id: str, revision: str) -> tuple[int, bytes, str]:
    revision = require_sha40(revision, label=f"{repo_id} Hugging Face revision")
    quoted = "/".join(urllib.parse.quote(part, safe="") for part in repo_id.split("/", 1))
    candidates = (
        f"https://huggingface.co/spaces/{quoted}/raw/{revision}/README.md",
        f"https://huggingface.co/spaces/{quoted}/resolve/{revision}/README.md",
    )
    last_status = 404
    for url in candidates:
        status, content = _safe_request_bytes(url)
        last_status = status
        if status == 200:
            return status, content, url
    return last_status, b"", candidates[0]


def _front_matter_parts(text: str) -> tuple[list[str], list[str]]:
    lines = text.removeprefix("\ufeff").splitlines()
    if not lines or lines[0] != "---":
        return [], lines
    for index, line in enumerate(lines[1:], 1):
        if line == "---":
            return lines[1:index], lines[index + 1 :]
    raise SourceDeclarationError("README front matter has no closing delimiter")


def _source_scalar(value: str) -> str:
    value = value.strip()
    if value.startswith('"'):
        try:
            scalar, end = json.JSONDecoder().raw_decode(value)
        except ValueError as error:
            raise SourceDeclarationError("source metadata has an invalid quoted scalar") from error
        if not isinstance(scalar, str) or (
            value[end:].strip() and not value[end:].lstrip().startswith("#")
        ):
            raise SourceDeclarationError("source metadata must contain one string scalar")
        return scalar
    if value.startswith("'"):
        match = re.fullmatch(r"'((?:[^']|'')*)'\s*(?:#.*)?", value)
        if not match:
            raise SourceDeclarationError("source metadata has an invalid quoted scalar")
        return match.group(1).replace("''", "'")
    value = re.split(r"\s+#", value, maxsplit=1)[0].strip()
    if not value or value[0] in "#|>!&*[{":
        raise SourceDeclarationError("source metadata must contain a plain or quoted repository scalar")
    return value


def parse_front_matter(text: str) -> dict[str, str]:
    lines, _ = _front_matter_parts(text)
    values: dict[str, str] = {}
    parent = ""
    child_indent: int | None = None
    for line in lines:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([ \t]*)([A-Za-z0-9_-]+|<<)\s*:\s*(.*?)\s*$", line)
        if not match:
            if (
                parent and parent != "szl" and parent not in SOURCE_FIELD_KEYS
                and re.match(r"^-\s", line)
            ):
                continue
            if parent == "szl" or line == line.lstrip():
                raise SourceDeclarationError("source metadata has unsupported YAML key syntax")
            continue
        whitespace, key, value = match.groups()
        key = key.lower()
        if not whitespace:
            parent = key
            child_indent = None
            path = key
        elif not parent:
            raise SourceDeclarationError("source metadata has no unindented root mapping")
        elif parent == "szl":
            if "\t" in whitespace:
                raise SourceDeclarationError("szl source metadata uses ambiguous indentation")
            if child_indent is None:
                child_indent = len(whitespace)
            if len(whitespace) != child_indent:
                raise SourceDeclarationError("szl source metadata must be a single-level mapping")
            path = f"szl.{key}"
        else:
            continue
        if key == "<<":
            raise SourceDeclarationError("source metadata cannot inherit YAML merge keys")
        if path == "szl":
            if path in values or (value and not value.startswith("#")):
                raise SourceDeclarationError("szl source metadata must be one block mapping")
            values[path] = ""
        elif key in SOURCE_FIELD_KEYS:
            if path in values:
                raise SourceDeclarationError(f"source metadata repeats {path}")
            values[path] = _source_scalar(value)
        else:
            values[path] = value.strip("\"'").strip()
    return values


def normalize_repo_name(value: str) -> str:
    text = value.strip().lower()
    if text.endswith(".git"):
        text = text[:-4]
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")


def _clean_repo_token(value: str) -> str:
    return value.rstrip(".,);]}>\"'").removesuffix(".git")


def extract_github_repository_references(
    readme: str, github_org: str = GITHUB_ORG,
) -> list[str]:
    candidates: set[str] = set()
    for match in GITHUB_URL_RE.finditer(readme):
        owner = match.group("owner")
        repo = _clean_repo_token(match.group("repo"))
        if owner.lower() == github_org.lower() and repo:
            candidates.add(f"{github_org}/{repo}".lower())
    return sorted(candidates)


def _declared_repository(value: str, github_org: str) -> str:
    value = value.strip()
    markdown = re.fullmatch(r"\[[^\]\n]+\]\(([^()\s]+)\)", value)
    if markdown:
        value = markdown.group(1)
    elif len(value) > 1 and (value[0], value[-1]) in {("`", "`"), ("<", ">")}:
        value = value[1:-1]
    if value.startswith(("https://", "http://")):
        try:
            url = urllib.parse.urlsplit(value)
        except ValueError as error:
            raise SourceDeclarationError("declared source repository URL is malformed") from error
        if url.netloc.lower() != "github.com" or any(character.isspace() for character in value):
            raise SourceDeclarationError("declared source is not a GitHub repository URL")
        parts = url.path.strip("/").split("/")
        if len(parts) < 2:
            raise SourceDeclarationError("declared source URL has no repository")
        owner, repo = parts[:2]
    else:
        parts = value.split("/")
        if len(parts) != 2:
            raise SourceDeclarationError("declared source is not an owner/repository identifier")
        owner, repo = parts
    repo = repo.removesuffix(".git")
    if owner.lower() != github_org.lower():
        raise SourceDeclarationError(f"declared source is outside {github_org}")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", repo) or repo in {".", ".."}:
        raise SourceDeclarationError("declared source repository name is invalid")
    return f"{github_org}/{repo}".lower()


def _prose_source_declarations(readme: str) -> list[tuple[str, str]]:
    _, body = _front_matter_parts(readme)
    # Code examples, quotations and comments are references, not owner assertions.
    prose = re.sub(r"<!--.*?(?:-->|\Z)", "", "\n".join(body), flags=re.DOTALL)
    prose = re.sub(
        r"<(pre|code|script|style|blockquote)\b[^>]*>.*?(?:</\1\s*>|\Z)",
        "", prose, flags=re.DOTALL | re.IGNORECASE,
    )
    body = prose.splitlines()
    visible: list[str] = []
    fence: tuple[str, int] | None = None
    for line in body:
        stripped = line.lstrip()
        fence_match = re.match(r"^ {0,3}(`{3,}|~{3,})", line)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = (marker[0], len(marker))
            elif (
                marker[0] == fence[0]
                and len(marker) >= fence[1]
                and not line[fence_match.end():].strip()
            ):
                fence = None
            visible.append("")
        elif fence is not None or stripped.startswith(">") or line.startswith(("    ", "\t")):
            visible.append("")
        else:
            visible.append(line.strip())
    declarations: list[tuple[str, str]] = []
    for index, line in enumerate(visible):
        match = next(
            (matched for pattern in SOURCE_PROSE_PREFIXES if (matched := pattern.match(line))),
            None,
        )
        if match is None:
            continue
        paragraph = [match.group(1) or ""]
        for continuation in visible[index + 1 :]:
            if not continuation or re.match(r"^(?:#|[-*+]\s|\d+\.\s)", continuation):
                break
            paragraph.append(continuation)
        declarations.append((f"body_declaration:{len(declarations) + 1}", " ".join(paragraph).strip()))
    return declarations


def extract_source_declarations(
    readme: str, front_matter: dict[str, str], github_org: str = GITHUB_ORG,
) -> tuple[list[dict[str, str]], list[str], list[str]]:
    declarations = [
        (f"front_matter:{key}", value)
        for key, value in front_matter.items()
        if key in SOURCE_FIELD_KEYS or key.removeprefix("szl.") in SOURCE_FIELD_KEYS
    ]
    declarations.extend(_prose_source_declarations(readme))
    observed: list[dict[str, str]] = []
    repositories: set[str] = set()
    errors: list[str] = []
    for location, raw_value in declarations:
        observed.append({"location": location, "value": raw_value})
        try:
            if location.startswith("front_matter:"):
                repositories.add(_declared_repository(raw_value, github_org))
                continue
            value = re.sub(
                r"^public(?: Apache-2\.0)? repository\s+", "", raw_value,
                flags=re.IGNORECASE,
            )
            value = re.split(r"(?<=[.!?])\s+", value, maxsplit=1)[0]
            expression = SOURCE_EXPRESSION_RE.match(value)
            if expression is None:
                raise SourceDeclarationError("source declaration does not begin with a repository")
            repositories.add(_declared_repository(expression.group().rstrip(".,;"), github_org))
            tail = value[expression.end():].strip()
            if (
                re.match(r"^(?:[,;&/]|and\b|or\b)", tail, re.IGNORECASE)
                or GITHUB_URL_RE.search(tail)
            ):
                raise SourceDeclarationError("source declaration contains more than one possible owner")
        except SourceDeclarationError as error:
            errors.append(f"{location}: {error}")
    return observed, sorted(repositories), sorted(errors)


def extract_explicit_github_repositories(
    readme: str, front_matter: dict[str, str], github_org: str = GITHUB_ORG,
) -> list[str]:
    _, repositories, errors = extract_source_declarations(readme, front_matter, github_org)
    if errors:
        raise SourceDeclarationError("; ".join(errors))
    return repositories


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
    }


def bind_github_repo_revision(repository: dict[str, Any]) -> dict[str, Any]:
    bound = dict(repository)
    existing = bound.get("default_branch_sha")
    if isinstance(existing, str) and SHA40.fullmatch(existing.lower()):
        bound["default_branch_sha"] = existing.lower()
        return bound

    full_name = bound.get("full_name")
    default_branch = bound.get("default_branch")
    if not isinstance(full_name, str) or not full_name:
        raise SourceMapError("GitHub repository metadata has no canonical full name")
    if not isinstance(default_branch, str) or not default_branch:
        bound["default_branch_sha"] = None
        return bound

    commit_url = (
        _repo_api_url(full_name)
        + "/commits/"
        + urllib.parse.quote(default_branch, safe="")
    )
    commit_status, commit = _safe_request_json(commit_url, github=True)
    if commit_status in {404, 409}:
        bound["default_branch_sha"] = None
        return bound
    if commit_status != 200 or not isinstance(commit, dict):
        raise SourceMapError(
            f"GitHub default-branch lookup failed for {full_name}: "
            f"HTTP {commit_status}"
        )
    bound["default_branch_sha"] = require_sha40(
        commit.get("sha"), label=f"{full_name} GitHub default-branch revision"
    )
    return bound


def list_workflow_candidates(full_name: str, revision: str) -> dict[str, Any]:
    revision = require_sha40(revision, label=f"{full_name} GitHub revision")
    url = (
        _repo_api_url(full_name)
        + "/contents/.github/workflows?"
        + urllib.parse.urlencode({"ref": revision})
    )
    status, payload = _safe_request_json(url, github=True)
    if status == 404:
        return {"state": "UNAVAILABLE", "github_ref": revision, "paths": []}
    if status != 200 or not isinstance(payload, list):
        return {
            "state": "ERROR",
            "github_ref": revision,
            "http_status": status,
            "paths": [],
        }
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
        "github_ref": revision,
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
    *,
    declaration_errors: Iterable[str] = (),
) -> dict[str, Any]:
    explicit_list = sorted({candidate.lower() for candidate in explicit})
    verified_explicit: list[dict[str, Any]] = []
    missing_explicit: list[str] = []
    for candidate in explicit_list:
        resolved = resolver(candidate)
        if resolved and str(resolved.get("full_name", "")).lower() == candidate:
            verified_explicit.append(resolved)
        else:
            missing_explicit.append(candidate)

    if list(declaration_errors):
        return {
            "state": "DIVERGENT",
            "evidence": "INVALID_SOURCE_DECLARATION",
            "canonical": None,
            "candidates": verified_explicit,
            "missing_candidates": missing_explicit,
        }
    if len(verified_explicit) == 1 and not missing_explicit:
        return {
            "state": "EXACT",
            "evidence": "README_OR_CARD_SOURCE_DECLARATION",
            "canonical": verified_explicit[0],
            "candidates": verified_explicit,
            "missing_candidates": [],
        }
    if verified_explicit or missing_explicit:
        return {
            "state": "DIVERGENT",
            "evidence": "MULTIPLE_OR_UNRESOLVED_SOURCE_DECLARATIONS",
            "canonical": None,
            "candidates": verified_explicit,
            "missing_candidates": missing_explicit,
        }

    inferred_resolved: list[dict[str, Any]] = []
    for candidate in inferred_repo_candidates(space_id):
        resolved = resolver(candidate)
        if resolved and str(resolved.get("full_name", "")).lower() == candidate.lower():
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
    readme_fetcher: Callable[[str, str], tuple[int, bytes, str]] = fetch_space_readme,
    resolver: Callable[[str], dict[str, Any] | None] = resolve_github_repo,
    workflow_lister: Callable[[str, str], dict[str, Any]] = list_workflow_candidates,
    repository_binder: Callable[[dict[str, Any]], dict[str, Any]] = bind_github_repo_revision,
) -> dict[str, Any]:
    repo_cache: dict[str, dict[str, Any] | None] = {}
    bound_repo_cache: dict[str, dict[str, Any]] = {}
    workflow_cache: dict[str, dict[str, Any]] = {}

    def cached_resolver(full_name: str) -> dict[str, Any] | None:
        key = full_name.lower()
        if key not in repo_cache:
            repo_cache[key] = resolver(full_name)
        return repo_cache[key]

    def cached_repository_binder(repository: dict[str, Any]) -> dict[str, Any]:
        full_name = repository.get("full_name")
        if not isinstance(full_name, str) or not full_name:
            raise SourceMapError("GitHub repository candidate has no canonical full name")
        key = full_name.lower()
        if key not in bound_repo_cache:
            bound = repository_binder(repository)
            bound_name = bound.get("full_name") if isinstance(bound, dict) else None
            if not isinstance(bound_name, str) or bound_name.lower() != key:
                raise SourceMapError(
                    f"GitHub repository revision binding changed identity for {full_name}"
                )
            bound_revision = bound.get("default_branch_sha")
            if not isinstance(bound_revision, str) or not SHA40.fullmatch(
                bound_revision
            ):
                raise SourceMapError(
                    f"GitHub repository candidate {full_name} has no immutable "
                    "default-branch revision"
                )
            bound_repo_cache[key] = bound
        return bound_repo_cache[key]

    def divergent_candidate_identity(repository: dict[str, Any]) -> dict[str, str]:
        full_name = repository.get("full_name")
        html_url = repository.get("html_url")
        if not isinstance(full_name, str) or not full_name:
            raise SourceMapError("GitHub repository candidate has no canonical full name")
        if not isinstance(html_url, str) or not html_url:
            raise SourceMapError(f"GitHub repository candidate {full_name} has no URL")
        return {"full_name": full_name, "html_url": html_url}

    spaces: list[dict[str, Any]] = []
    state_counts: Counter[str] = Counter()
    sdk_counts: Counter[str] = Counter()
    workflow_state_counts: Counter[str] = Counter()

    for record in records:
        space_id = str(record["id"])
        hf_repository_sha = require_sha40(
            record.get("sha"), label=f"{space_id} Hugging Face repository revision"
        )
        status, readme_bytes, readme_url = readme_fetcher(
            space_id, hf_repository_sha
        )
        if status == 200:
            try:
                readme = readme_bytes.decode("utf-8", errors="strict")
            except UnicodeDecodeError as error:
                raise SourceMapError(
                    f"{space_id} README at {hf_repository_sha} is not strict UTF-8"
                ) from error
        else:
            readme = ""
        front: dict[str, str] = {}
        declarations: list[dict[str, str]] = []
        explicit: list[str] = []
        declaration_errors: list[str] = []
        try:
            front = parse_front_matter(readme)
            declarations, explicit, declaration_errors = extract_source_declarations(readme, front)
        except SourceDeclarationError as error:
            declaration_errors = [str(error)]
        mapping = select_source_mapping(
            space_id, explicit, cached_resolver, declaration_errors=declaration_errors,
        )
        candidates = mapping.get("candidates")
        if not isinstance(candidates, list) or not all(
            isinstance(candidate, dict) for candidate in candidates
        ):
            raise SourceMapError(
                f"{space_id} source mapping returned invalid repository candidates"
            )
        canonical = mapping.get("canonical")
        workflows: dict[str, Any]
        if isinstance(canonical, dict) and isinstance(canonical.get("full_name"), str):
            mapping["candidates"] = [
                cached_repository_binder(candidate) for candidate in candidates
            ]
            canonical_name = canonical["full_name"].lower()
            matching_candidates = [
                candidate
                for candidate in mapping["candidates"]
                if isinstance(candidate.get("full_name"), str)
                and candidate["full_name"].lower() == canonical_name
            ]
            if len(matching_candidates) != 1:
                raise SourceMapError(
                    f"{space_id} canonical source is not one bound candidate"
                )
            canonical = matching_candidates[0]
            mapping["canonical"] = canonical
            repo_key = canonical["full_name"].lower()
            github_ref = canonical.get("default_branch_sha")
            if isinstance(github_ref, str) and SHA40.fullmatch(github_ref):
                cache_key = f"{repo_key}@{github_ref}"
                if cache_key not in workflow_cache:
                    workflow_cache[cache_key] = workflow_lister(
                        canonical["full_name"], github_ref
                    )
                workflows = workflow_cache[cache_key]
            else:
                workflows = {
                    "state": "UNAVAILABLE_REVISION",
                    "github_ref": None,
                    "paths": [],
                }
        else:
            mapping["candidates"] = [
                divergent_candidate_identity(candidate) for candidate in candidates
            ]
            workflows = {"state": "BLOCKED_SOURCE_MAPPING", "paths": []}

        state_counts[mapping["state"]] += 1
        sdk_counts[_space_sdk(record) or "UNAVAILABLE"] += 1
        workflow_state_counts[str(workflows.get("state"))] += 1
        spaces.append(
            {
                "space_id": space_id,
                "hf_repository_sha": hf_repository_sha,
                "hf_runtime_sha": _runtime_sha(record),
                "hf_runtime_stage": _runtime_stage(record),
                "sdk": _space_sdk(record),
                "readme": {
                    "http_status": status,
                    "url": readme_url,
                    "revision": hf_repository_sha,
                    "sha256": hashlib.sha256(readme_bytes).hexdigest()
                    if status == 200
                    else None,
                    "front_matter_keys": sorted(front),
                },
                "github_repository_references": extract_github_repository_references(readme),
                "explicit_github_repositories": explicit,
                "source_declarations": declarations,
                "source_declaration_errors": declaration_errors,
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
