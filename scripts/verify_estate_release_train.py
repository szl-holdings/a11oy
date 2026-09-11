#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify one SZL release vector across GitHub, Hugging Face, and public origins.

The verifier is intentionally read-only. Protected GitHub source is the release
input. Hugging Face runtimes and public domains are observations that must prove
which exact source revision they serve. A successful HTTP response without a
source witness is not alignment.

No provider mutation, branch mutation, credential serialization, or runtime
execution authority is present in this module.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import time
from typing import Any, Callable, Iterable, Mapping, Sequence
import urllib.error
import urllib.parse
import urllib.request

SCHEMA = "szl.estate-release-train.receipt/v1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
PROFILE_COUNTS = re.compile(
    r"(?P<spaces>[0-9]+) public Spaces, (?P<models>[0-9]+) models, "
    r"(?P<datasets>[0-9]+) datasets"
)
MAX_BODY = 2_000_000
USER_AGENT = "SZL-Estate-Release-Train/1.0"
RETRYABLE = frozenset({429, 500, 502, 503, 504})
SOURCE_KEYS = (
    "source_revision",
    "source_sha",
    "git_sha",
    "commit_sha",
    "revision",
)
INVENTORY_KINDS = ("models", "datasets", "spaces")
MAX_INVENTORY_PAGES = 20
MAX_INVENTORY_ITEMS = 2_000
MAX_INVENTORY_SECONDS = 90
REPO_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*/[A-Za-z0-9][A-Za-z0-9_.-]*$"
)
ORG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")


class AlignmentError(RuntimeError):
    """Raised for malformed configuration or unavailable required evidence."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _token(names: Iterable[str]) -> str | None:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return None


def _headers(*, github: bool = False, huggingface: bool = False) -> dict[str, str]:
    result = {
        "Accept": "application/json, text/html;q=0.8, text/plain;q=0.7",
        "Cache-Control": "no-cache, no-store",
        "User-Agent": USER_AGENT,
    }
    token = None
    if github:
        token = _token(("GITHUB_TOKEN", "GH_TOKEN"))
        result["Accept"] = "application/vnd.github+json"
        result["X-GitHub-Api-Version"] = "2022-11-28"
    elif huggingface:
        token = _token(
            (
                "HF_ORG_TOKEN",
                "HF_ORG_TOKEN1",
                "HF_WRITE_TOKEN",
                "HF_TOKEN",
                "HUGGINGFACE_TOKEN",
                "HUGGING_FACE_HUB_TOKEN",
            )
        )
    if token:
        result["Authorization"] = f"Bearer {token}"
    return result


def _retry_delay(error: BaseException, attempt: int) -> float:
    delay = float(min(2**attempt, 60))
    if isinstance(error, urllib.error.HTTPError) and error.headers:
        raw = error.headers.get("Retry-After")
        try:
            if raw is not None:
                delay = max(delay, min(float(raw), 60.0))
        except (TypeError, ValueError):
            pass
    return delay


def fetch(
    url: str,
    *,
    github: bool = False,
    huggingface: bool = False,
    attempts: int = 4,
) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise AlignmentError(f"refusing noncanonical URL: {url}")
    opener = urllib.request.build_opener(NoRedirect())
    started = time.monotonic()
    last_error: BaseException | None = None
    for attempt in range(attempts):
        request = urllib.request.Request(
            url,
            headers=_headers(github=github, huggingface=huggingface),
        )
        try:
            with opener.open(request, timeout=35) as response:
                raw = response.read(MAX_BODY + 1)
                if len(raw) > MAX_BODY:
                    raise AlignmentError(f"response exceeded {MAX_BODY} bytes: {url}")
                text = raw.decode("utf-8", "replace")
                content_type = response.headers.get("Content-Type", "")
                try:
                    decoded: Any = json.loads(text)
                except json.JSONDecodeError:
                    decoded = None
                return {
                    "url": url,
                    "status": response.status,
                    "content_type": content_type,
                    "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
                    "bytes": len(raw),
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "json": decoded,
                    "text": text if decoded is None else None,
                    "redirect": None,
                    "link": response.headers.get("Link"),
                }
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in {301, 302, 303, 307, 308}:
                return {
                    "url": url,
                    "status": exc.code,
                    "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
                    "bytes": 0,
                    "sha256": None,
                    "json": None,
                    "text": None,
                    "redirect": exc.headers.get("Location"),
                    "link": None,
                }
            if exc.code not in RETRYABLE or attempt + 1 == attempts:
                body = exc.read(4096)
                return {
                    "url": url,
                    "status": exc.code,
                    "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
                    "bytes": len(body),
                    "sha256": hashlib.sha256(body).hexdigest() if body else None,
                    "json": None,
                    "text": body.decode("utf-8", "replace")[:500],
                    "redirect": None,
                    "link": None,
                }
        except (urllib.error.URLError, ConnectionError, TimeoutError) as exc:
            last_error = exc
            if attempt + 1 == attempts:
                break
        if last_error is not None:
            time.sleep(_retry_delay(last_error, attempt))
    return {
        "url": url,
        "status": None,
        "elapsed_ms": round((time.monotonic() - started) * 1000, 1),
        "bytes": 0,
        "sha256": None,
        "json": None,
        "text": None,
        "redirect": None,
        "link": None,
        "error": f"{type(last_error).__name__}: {last_error}",
    }


def github_main(repository: str) -> dict[str, Any]:
    response = fetch(
        f"https://api.github.com/repos/{repository}/branches/main",
        github=True,
    )
    payload = response.get("json")
    sha = None
    protected = None
    if isinstance(payload, Mapping):
        commit = payload.get("commit")
        if isinstance(commit, Mapping):
            sha = str(commit.get("sha") or "").lower()
        protected = payload.get("protected")
    valid = bool(SHA40.fullmatch(sha or ""))
    return {
        "repository": repository,
        "status": response.get("status"),
        "sha": sha,
        "sha_valid": valid,
        "protected": protected,
        "observed": valid and response.get("status") == 200,
    }


def github_file(repository: str, path: str, revision: str) -> dict[str, Any]:
    quoted = urllib.parse.quote(path, safe="/")
    url = (
        f"https://raw.githubusercontent.com/{repository}/{revision}/{quoted}"
    )
    return fetch(url)


def hf_space(repo_id: str) -> dict[str, Any]:
    encoded = "/".join(urllib.parse.quote(part) for part in repo_id.split("/", 1))
    response = fetch(
        f"https://huggingface.co/api/spaces/{encoded}",
        huggingface=True,
    )
    payload = response.get("json")
    if not isinstance(payload, Mapping):
        return {
            "repo_id": repo_id,
            "status": response.get("status"),
            "observed": False,
        }
    runtime = payload.get("runtime")
    runtime = runtime if isinstance(runtime, Mapping) else {}
    return {
        "repo_id": repo_id,
        "status": response.get("status"),
        "observed": response.get("status") == 200,
        "sha": payload.get("sha"),
        "private": payload.get("private"),
        "sdk": payload.get("sdk"),
        "stage": runtime.get("stage"),
        "hardware": runtime.get("hardware"),
        "requested_hardware": runtime.get("requestedHardware"),
    }


def _inventory_error(code: str) -> AlignmentError:
    return AlignmentError(code)


def _validate_inventory_url(url: str, org: str, kind: str) -> None:
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    if (
        parsed.scheme != "https"
        or parsed.netloc != "huggingface.co"
        or parsed.path != f"/api/{kind}"
        or parsed.fragment
        or parsed.username
        or parsed.password
        or set(query) - {"author", "limit", "full", "cursor"}
        or query.get("author") != [org]
        or query.get("limit") != ["100"]
        or query.get("full") != ["true"]
        or (
            "cursor" in query
            and (len(query["cursor"]) != 1 or not query["cursor"][0])
        )
    ):
        raise _inventory_error("UNSAFE_OR_CHANGED_PAGINATION_SCOPE")


def _inventory_next_url(link: Any, org: str, kind: str) -> str | None:
    if link is None or link == "":
        return None
    if not isinstance(link, str) or len(link) > 16_384:
        raise _inventory_error("MALFORMED_LINK_HEADER")
    found: list[str] = []
    for field in link.split(","):
        match = re.fullmatch(r'\s*<([^<>]+)>\s*;\s*rel="([a-z ]+)"\s*', field)
        if not match:
            raise _inventory_error("MALFORMED_LINK_HEADER")
        target, relations = match.groups()
        if "next" in relations.split():
            _validate_inventory_url(target, org, kind)
            found.append(target)
    if len(found) > 1:
        raise _inventory_error("MULTIPLE_NEXT_LINKS")
    return found[0] if found else None


def hf_inventory(
    org: str,
    fetch_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Paginated Hub listing. A malformed 200 is UNAVAILABLE, never an observed zero.

    A reached page/item/time cap is PARTIAL, not completion. Duplicate IDs,
    foreign namespaces and non-list bodies fail closed. This listing is not
    authenticated whole-organization membership.
    """
    getter = fetch if fetch_fn is None else fetch_fn
    result: dict[str, Any] = {
        "organization": org,
        "counts": {},
        "items": {},
        "page_evidence": {},
        "errors": {},
        "enumeration_state": {},
        "observed": False,
        "membership_class": "PAGINATED_LISTING_NOT_AUTHENTICATED_ORG_CENSUS",
    }
    if not isinstance(org, str) or not ORG_RE.fullmatch(org):
        result["errors"]["_org"] = "INVALID_ORGANIZATION"
        result["observed"] = False
        return result
    started = time.monotonic()
    for kind in INVENTORY_KINDS:
        url = (
            f"https://huggingface.co/api/{kind}?"
            f"{urllib.parse.urlencode({'author': org, 'limit': 100, 'full': 'true'})}"
        )
        seen_urls: set[str] = set()
        members: dict[str, dict[str, Any]] = {}
        pages: list[dict[str, Any]] = []
        state = "UNAVAILABLE"
        try:
            while url is not None:
                if time.monotonic() - started > MAX_INVENTORY_SECONDS:
                    raise _inventory_error("INVENTORY_TIME_BUDGET")
                _validate_inventory_url(url, org, kind)
                if url in seen_urls:
                    raise _inventory_error("PAGINATION_CYCLE")
                if len(seen_urls) >= MAX_INVENTORY_PAGES:
                    raise _inventory_error("PAGE_BUDGET")
                seen_urls.add(url)
                try:
                    response = getter(url, huggingface=True)
                except TypeError:
                    response = getter(url)
                if response.get("status") != 200:
                    raise _inventory_error("HTTP_UNAVAILABLE")
                rows = response.get("json")
                if not isinstance(rows, list):
                    raise _inventory_error("INVALID_LIST_RESPONSE")
                if len(rows) > 100:
                    raise _inventory_error("PAGE_OVERFLOW")
                for row in rows:
                    if not isinstance(row, Mapping):
                        raise _inventory_error("MALFORMED_REPOSITORY_ROW")
                    name = row.get("id")
                    if (
                        not isinstance(name, str)
                        or not REPO_ID_RE.fullmatch(name)
                        or name.split("/", 1)[0] != org
                    ):
                        raise _inventory_error("FOREIGN_OR_MALFORMED_ID")
                    if name in members:
                        raise _inventory_error("DUPLICATE_ID")
                    members[name] = {
                        "id": name,
                        "sha": row.get("sha"),
                        "last_modified": row.get("lastModified"),
                        "private": row.get("private"),
                    }
                if len(members) > MAX_INVENTORY_ITEMS:
                    raise _inventory_error("ITEM_BUDGET")
                continuation = _inventory_next_url(response.get("link"), org, kind)
                if continuation and not rows:
                    raise _inventory_error("EMPTY_CONTINUATION_PAGE")
                pages.append(
                    {
                        "index": len(pages) + 1,
                        "count": len(rows),
                        "response_sha256": response.get("sha256"),
                        "has_next": continuation is not None,
                    }
                )
                url = continuation
            state = "COMPLETE"
            result["items"][kind] = [members[name] for name in sorted(members)]
            result["counts"][kind] = len(members)
        except AlignmentError as exc:
            message = str(exc)
            if message in {"PAGE_BUDGET", "ITEM_BUDGET", "INVENTORY_TIME_BUDGET"}:
                state = "PARTIAL"
            else:
                state = "UNAVAILABLE"
            result["counts"][kind] = None
            result["items"][kind] = []
            result["errors"][kind] = message
        result["page_evidence"][kind] = pages
        result["enumeration_state"][kind] = state
    result["observed"] = all(
        result["enumeration_state"].get(kind) == "COMPLETE"
        for kind in INVENTORY_KINDS
    )
    return result


def _candidate_revision(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    return candidate if SHA40.fullmatch(candidate) else None


def extract_source_revision(payload: Any) -> tuple[str | None, str | None]:
    """Collect recognized source-identity fields. Conflicts and invalid aliases fail closed.

    A producer Git commit, Hub repository commit, image digest and runtime
    environment declaration remain different objects. This helper only extracts
    SHA-40 Git-like source aliases; it does not compare them to image digests.
    """
    if not isinstance(payload, Mapping):
        return None, None
    observed: list[tuple[str, str]] = []
    invalid = False

    def consider(container: Mapping[str, Any], prefix: str) -> None:
        nonlocal invalid
        for key in SOURCE_KEYS:
            if key not in container:
                continue
            value = container.get(key)
            if value is None:
                continue
            candidate = _candidate_revision(value)
            if candidate is None:
                invalid = True
                return
            observed.append((candidate, f"{prefix}{key}"))

    consider(payload, "")
    if invalid:
        return None, "INVALID"
    for parent_key in ("build", "source", "git", "deployment", "release"):
        child = payload.get(parent_key)
        if not isinstance(child, Mapping):
            continue
        consider(child, f"{parent_key}.")
        if invalid:
            return None, "INVALID"
    if not observed:
        return None, None
    shas = {sha for sha, _ in observed}
    if len(shas) != 1:
        return None, "CONFLICT"
    return observed[0][0], observed[0][1]


def probe_source(origin: str, paths: Sequence[str]) -> dict[str, Any]:
    """Observe every declared identity endpoint. First-success ordering cannot hide conflict."""
    observations: list[dict[str, Any]] = []
    found: list[tuple[str, str, str]] = []
    identity_state = "UNAVAILABLE"
    for path in paths:
        response = fetch(origin.rstrip("/") + path)
        revision, field = extract_source_revision(response.get("json"))
        observations.append(
            {
                "path": path,
                "status": response.get("status"),
                "sha256": response.get("sha256"),
                "revision": revision,
                "revision_field": field,
                "redirect": response.get("redirect"),
            }
        )
        if field in {"INVALID", "CONFLICT"}:
            identity_state = field
            continue
        if response.get("status") == 200 and revision:
            found.append((revision, field or "unknown", path))
    if identity_state in {"INVALID", "CONFLICT"}:
        return {
            "observed": False,
            "revision": None,
            "revision_field": identity_state,
            "selected_path": None,
            "identity_state": identity_state,
            "observations": observations,
        }
    if not found:
        return {
            "observed": False,
            "revision": None,
            "revision_field": None,
            "selected_path": None,
            "identity_state": "UNAVAILABLE",
            "observations": observations,
        }
    shas = {item[0] for item in found}
    if len(shas) != 1:
        return {
            "observed": False,
            "revision": None,
            "revision_field": "ENDPOINT_DISAGREEMENT",
            "selected_path": None,
            "identity_state": "ENDPOINT_DISAGREEMENT",
            "observations": observations,
        }
    revision, field, path = found[0]
    return {
        "observed": True,
        "revision": revision,
        "revision_field": field,
        "selected_path": path,
        "identity_state": "OBSERVED",
        "observations": observations,
    }


class SemanticHTML(HTMLParser):
    """Collect stable public-experience markers instead of volatile page bytes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.in_title = False
        self.markers: dict[str, str] = {}
        self.scripts: set[str] = set()
        self.styles: set[str] = set()
        self.links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = {key: value or "" for key, value in attrs}
        if tag == "title":
            self.in_title = True
        for key, value in values.items():
            if key.startswith("data-szl-"):
                self.markers[key] = value
        if tag == "script" and values.get("src"):
            self.scripts.add(values["src"])
        if tag == "link" and values.get("href"):
            rel = values.get("rel", "")
            if "stylesheet" in rel:
                self.styles.add(values["href"])
        if tag == "a" and values.get("href"):
            href = values["href"]
            if href.startswith("/"):
                self.links.add(href.split("?", 1)[0])

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            self.title_parts.append(data.strip())

    def result(self) -> dict[str, Any]:
        stable = {
            "title": " ".join(part for part in self.title_parts if part),
            "markers": dict(sorted(self.markers.items())),
            "scripts": sorted(self.scripts),
            "styles": sorted(self.styles),
            "internal_links": sorted(self.links),
        }
        return {**stable, "semantic_sha256": canonical_sha256(stable)}


def semantic_html(origin: str) -> dict[str, Any]:
    response = fetch(origin.rstrip("/") + "/")
    text = response.get("text")
    if response.get("status") != 200 or not isinstance(text, str):
        return {
            "origin": origin,
            "status": response.get("status"),
            "observed": False,
            "semantic_sha256": None,
        }
    parser = SemanticHTML()
    parser.feed(text)
    return {
        "origin": origin,
        "status": response.get("status"),
        "observed": True,
        **parser.result(),
    }


def inspect_component(component: Mapping[str, Any], paths: Sequence[str]) -> dict[str, Any]:
    source = github_main(str(component["source_repository"]))
    space = hf_space(str(component["hf_repo_id"]))
    runtime = probe_source(str(component["origin"]), paths)
    expected = source.get("sha")
    observed = runtime.get("revision")
    root = fetch(str(component["origin"]).rstrip("/") + "/")
    aligned = bool(
        source.get("observed")
        and space.get("observed")
        and str(space.get("stage") or "").upper() == "RUNNING"
        and root.get("status") == 200
        and runtime.get("observed")
        and expected == observed
    )
    blockers: list[str] = []
    if not source.get("observed"):
        blockers.append("SOURCE_TIP_UNAVAILABLE")
    if not space.get("observed"):
        blockers.append("HF_REPOSITORY_UNAVAILABLE")
    elif str(space.get("stage") or "").upper() != "RUNNING":
        blockers.append(f"HF_STAGE_{str(space.get('stage') or 'UNKNOWN').upper()}")
    if root.get("status") != 200:
        blockers.append(f"ROOT_HTTP_{root.get('status')}")
    if not runtime.get("observed"):
        state = str(runtime.get("identity_state") or "UNAVAILABLE")
        if state in {"CONFLICT", "INVALID", "ENDPOINT_DISAGREEMENT"}:
            blockers.append(f"SOURCE_WITNESS_{state}")
        else:
            blockers.append("SOURCE_WITNESS_UNAVAILABLE")
    elif expected != observed:
        blockers.append("SOURCE_REVISION_MISMATCH")
    return {
        "key": component["key"],
        "required": bool(component.get("required")),
        "generated_by": component.get("generated_by"),
        "source": source,
        "space": space,
        "runtime": runtime,
        "root": {
            "status": root.get("status"),
            "sha256": root.get("sha256"),
            "bytes": root.get("bytes"),
        },
        "aligned": aligned,
        "blockers": blockers,
    }


def profile_inventory_contract(
    config: Mapping[str, Any],
    inventory: Mapping[str, Any],
    a11oy_sha: str | None,
) -> dict[str, Any]:
    profile = config["profile"]
    repository = str(profile["repository"])
    head = github_main(repository)
    profile_file = github_file(repository, str(profile["path"]), str(head.get("sha")))
    text = profile_file.get("text") or ""
    match = PROFILE_COUNTS.search(text)
    declared = None
    if match:
        declared = {key: int(value) for key, value in match.groupdict().items()}
    actual = inventory.get("counts") if isinstance(inventory, Mapping) else None
    enumeration = (
        inventory.get("enumeration_state") if isinstance(inventory, Mapping) else None
    )
    enumeration_complete = enumeration is None or (
        isinstance(enumeration, Mapping)
        and all(enumeration.get(kind) == "COMPLETE" for kind in INVENTORY_KINDS)
    )

    manifest = None
    if a11oy_sha:
        manifest_file = github_file(
            "szl-holdings/a11oy",
            "docs/huggingface-ecosystem-manifest.json",
            a11oy_sha,
        )
        if isinstance(manifest_file.get("json"), Mapping):
            manifest = manifest_file["json"].get("counts")

    aligned = bool(
        head.get("observed")
        and declared
        and actual
        and manifest
        and enumeration_complete
        and declared == actual == manifest
    )
    blockers: list[str] = []
    if not aligned:
        if enumeration is not None and not enumeration_complete:
            blockers.append("HF_INVENTORY_ENUMERATION_INCOMPLETE_OR_UNAVAILABLE")
        else:
            blockers.append("HF_INVENTORY_COUNT_MISMATCH_OR_UNAVAILABLE")
    return {
        "profile_repository": repository,
        "profile_sha": head.get("sha"),
        "declared_counts": declared,
        "manifest_counts": manifest,
        "observed_counts": actual,
        "enumeration_state": enumeration,
        "aligned": aligned,
        "blockers": blockers,
    }


def proof_contract(config: Mapping[str, Any]) -> dict[str, Any]:
    proof = config["proof"]
    repository = str(proof["repository"])
    source = github_main(repository)
    origin = str(proof["origin"])
    root = fetch(origin.rstrip("/") + "/")
    health = fetch(origin.rstrip("/") + "/health.json")
    health_revision, health_field = extract_source_revision(health.get("json"))

    pages = fetch(
        f"https://api.github.com/repos/{repository}/pages/builds/latest",
        github=True,
    )
    pages_json = pages.get("json")
    pages_sha = None
    pages_status = None
    if isinstance(pages_json, Mapping):
        commit = pages_json.get("commit")
        pages_sha = _candidate_revision(commit)
        pages_status = pages_json.get("status")

    exact_pages = pages_sha if pages_status == "built" else None
    aligned = bool(
        source.get("observed")
        and root.get("status") == 200
        and exact_pages == source.get("sha")
    )
    blockers: list[str] = []
    if root.get("status") != 200:
        blockers.append(f"PROOF_ROOT_HTTP_{root.get('status')}")
    if pages_status not in {None, "built"}:
        blockers.append(f"PROOF_PAGES_STATUS_{pages_status}")
    if not exact_pages:
        blockers.append("PROOF_PAGES_REVISION_UNAVAILABLE")
    elif exact_pages != source.get("sha"):
        blockers.append("PROOF_PAGES_REVISION_MISMATCH")
    if health_field in {"INVALID", "CONFLICT"}:
        blockers.append(f"PROOF_HEALTH_DOCUMENT_{health_field}")
    return {
        "source": source,
        "origin": origin,
        "root_status": root.get("status"),
        "health_status": health.get("status"),
        "health_revision": health_revision,
        "health_revision_field": health_field,
        "health_is_not_pages_deployment": True,
        "pages_status": pages.get("status"),
        "pages_build_status": pages_status,
        "pages_revision": pages_sha,
        "aligned": aligned,
        "blockers": blockers,
    }


def observe(config: Mapping[str, Any]) -> dict[str, Any]:
    paths = tuple(str(path) for path in config["build_info_paths"])
    components = [inspect_component(row, paths) for row in config["components"]]
    product = config["product"]
    product_source = github_main(str(product["repository"]))
    domain_source = probe_source(str(product["domain_origin"]), paths)
    space_source = probe_source(str(product["space_origin"]), paths)
    domain_semantic = semantic_html(str(product["domain_origin"]))
    space_semantic = semantic_html(str(product["space_origin"]))
    semantic_parity = bool(
        domain_semantic.get("observed")
        and space_semantic.get("observed")
        and domain_semantic.get("semantic_sha256")
        == space_semantic.get("semantic_sha256")
    )
    product_aligned = bool(
        product_source.get("observed")
        and domain_source.get("revision") == product_source.get("sha")
        and space_source.get("revision") == product_source.get("sha")
        and (
            semantic_parity
            if product.get("require_semantic_root_parity") is True
            else True
        )
    )
    product_blockers: list[str] = []
    if domain_source.get("revision") != product_source.get("sha"):
        product_blockers.append("PRODUCT_DOMAIN_SOURCE_MISMATCH")
    if space_source.get("revision") != product_source.get("sha"):
        product_blockers.append("CANONICAL_SPACE_SOURCE_MISMATCH")
    if product.get("require_semantic_root_parity") and not semantic_parity:
        product_blockers.append("PRODUCT_DOMAIN_SPACE_SEMANTIC_DRIFT")

    inventory = hf_inventory(str(config["huggingface_organization"]))
    profile = profile_inventory_contract(
        config,
        inventory,
        str(product_source.get("sha") or "") or None,
    )
    proof = proof_contract(config)

    required_components = [row for row in components if row["required"]]
    aligned = bool(
        product_aligned
        and proof.get("aligned")
        and profile.get("aligned")
        and all(row["aligned"] for row in required_components)
    )
    source_vector = {
        row["key"]: row["source"].get("sha") for row in components
    }
    source_vector["proof"] = proof.get("source", {}).get("sha")
    source_vector["profile"] = profile.get("profile_sha")
    release_id = canonical_sha256(source_vector)[:24]

    blockers = list(product_blockers)
    blockers.extend(proof.get("blockers", []))
    blockers.extend(profile.get("blockers", []))
    for row in required_components:
        blockers.extend(f"{row['key']}:{item}" for item in row["blockers"])

    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "observed_at": utc_now(),
        "state": "ALIGNED" if aligned else "DIVERGENT",
        "release_id": release_id,
        "source_vector": source_vector,
        "product": {
            "source": product_source,
            "domain_source": domain_source,
            "space_source": space_source,
            "domain_semantic": domain_semantic,
            "space_semantic": space_semantic,
            "semantic_parity": semantic_parity,
            "aligned": product_aligned,
            "blockers": product_blockers,
        },
        "proof": proof,
        "profile_inventory": profile,
        "huggingface_inventory": inventory,
        "components": components,
        "blockers": sorted(set(blockers)),
        "authority": config["authority"],
        "secret_values_recorded": False,
        "provider_writes_performed": False,
    }
    receipt["proof_chain_sha256"] = canonical_sha256(receipt)
    return receipt


def load_config(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise AlignmentError("configuration root must be an object")
    if value.get("schema") != "szl.estate-release-train.config/v1":
        raise AlignmentError("unexpected configuration schema")
    for key in (
        "organization",
        "huggingface_organization",
        "product",
        "proof",
        "profile",
        "components",
        "build_info_paths",
        "authority",
    ):
        if key not in value:
            raise AlignmentError(f"configuration is missing {key}")
    return value


def write_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def verify_until(
    config: Mapping[str, Any],
    *,
    wait_seconds: int,
    poll_seconds: int,
    output: Path,
) -> dict[str, Any]:
    deadline = time.monotonic() + max(wait_seconds, 0)
    history: list[dict[str, Any]] = []
    while True:
        receipt = observe(config)
        history.append(
            {
                "observed_at": receipt["observed_at"],
                "state": receipt["state"],
                "release_id": receipt["release_id"],
                "blockers": receipt["blockers"],
            }
        )
        receipt["poll_history"] = history
        receipt["proof_chain_sha256"] = canonical_sha256(
            {key: value for key, value in receipt.items() if key != "proof_chain_sha256"}
        )
        write_receipt(output, receipt)
        if receipt["state"] == "ALIGNED" or time.monotonic() >= deadline:
            return receipt
        time.sleep(max(poll_seconds, 1))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument(
        "--config",
        type=Path,
        default=Path("config/estate-release-train.v1.json"),
    )
    result.add_argument(
        "--output",
        type=Path,
        default=Path("reports/estate-release-train.json"),
    )
    result.add_argument("--wait-seconds", type=int, default=0)
    result.add_argument("--poll-seconds", type=int, default=20)
    result.add_argument(
        "--soft",
        action="store_true",
        help="Write the receipt and return zero even when drift remains.",
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    config = load_config(args.config)
    receipt = verify_until(
        config,
        wait_seconds=args.wait_seconds,
        poll_seconds=args.poll_seconds,
        output=args.output,
    )
    print(
        json.dumps(
            {
                "state": receipt["state"],
                "release_id": receipt["release_id"],
                "blockers": receipt["blockers"],
                "proof_chain_sha256": receipt["proof_chain_sha256"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    if receipt["state"] == "ALIGNED" or args.soft:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
