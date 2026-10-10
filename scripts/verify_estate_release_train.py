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

try:
    from scripts.hf_public_inventory import KINDS, PREDICATE, InventoryError, public_get, reserved_readme
except ModuleNotFoundError:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from hf_public_inventory import KINDS, PREDICATE, InventoryError, public_get, reserved_readme

SCHEMA = "szl.estate-release-train.receipt/v1"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
PROFILE_COUNTS = re.compile(
    r"(?P<spaces>[0-9]+) public Spaces, (?P<models>[0-9]+) models, "
    r"(?P<datasets>[0-9]+) datasets"
)
CURRENT_PROFILE_PUBLIC_COUNTS = re.compile(
    r"\bpublic\s+(?P<spaces>[0-9]+) Spaces,\s*(?P<models>[0-9]+) models, "
    r"(?P<datasets>[0-9]+) datasets\b",
    re.IGNORECASE,
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
INVENTORY_KINDS = KINDS
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
    retain_text: bool = False,
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
                    "text": text if decoded is None or retain_text else None,
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
    return fetch(url, retain_text=True)


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
    getter = public_get if fetch_fn is None else fetch_fn
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
                    if row.get('private') is not False:
                        raise _inventory_error('VISIBILITY_NOT_EXPLICITLY_PUBLIC')
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
                        "response_sha256": response.get("response_sha256", response.get("sha256")),
                        "has_next": continuation is not None,
                    }
                )
                url = continuation
            if kind == 'spaces':
                if time.monotonic() - started > MAX_INVENTORY_SECONDS:
                    raise _inventory_error('INVENTORY_TIME_BUDGET')
                name = f'{org}/README'
                if name in members:
                    result['reserved_readme_evidence'] = {'state': 'AUTHOR_LIST', 'id': name}
                else:
                    row, evidence = reserved_readme(org, getter)
                    result['reserved_readme_evidence'] = evidence
                    if time.monotonic() - started > MAX_INVENTORY_SECONDS:
                        raise _inventory_error('INVENTORY_TIME_BUDGET')
                    if row is not None:
                        if len(members) >= MAX_INVENTORY_ITEMS:
                            raise _inventory_error('ITEM_BUDGET')
                        members[name] = {'id': name, 'sha': row.get('sha'),
                                         'last_modified': row.get('lastModified'), 'private': False}
            state = "COMPLETE"
            result["items"][kind] = [members[name] for name in sorted(members)]
            result["counts"][kind] = len(members)
        except Exception as exc:
            message = str(exc) if isinstance(exc, (AlignmentError, InventoryError)) else type(exc).__name__
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


def _is_provider_injected_script(
    src: str, attrs: Sequence[tuple[str, str | None]] = ()
) -> bool:
    """Identify only the known Cloudflare beacon and exact observed WebMCP tag.

    The apex is served through Cloudflare, while the canonical Hugging Face Space
    is not. Cloudflare may therefore append its own external analytics beacon to
    otherwise byte-equivalent product HTML. That provider-owned script is not an
    SZL product asset and must not create product/Space semantic drift.
    Cloudflare also injects its WebMCP bridge when the zone's webmcp_enabled
    setting is on; see its zone-setting contract:
    https://developers.cloudflare.com/api/resources/zones/subresources/settings/
    Only the exact canonical-apex module tag observed on 2026-10-10 is
    recognized: data-packs="c2pa,mcp-server-client". Its URL and metadata
    remain bounded: altered attributes, duplicate attributes, URLs, or tool
    packs stay in the product semantic contract and continue to fail parity.
    """
    parsed = urllib.parse.urlsplit(src)
    if (
        parsed.scheme == "https"
        and parsed.netloc == "static.cloudflareinsights.com"
        and parsed.path.startswith("/beacon.min.js/")
        and not parsed.query
        and not parsed.fragment
    ):
        return True
    return bool(
        parsed.scheme == "https"
        and parsed.netloc == "a-11-oy.com"
        and parsed.path == "/.webmcp/bridge.js"
        and not parsed.query
        and not parsed.fragment
        and src == "https://a-11-oy.com/.webmcp/bridge.js"
        and len(attrs) == 3
        and dict(attrs)
        == {
            "src": src,
            "type": "module",
            "data-packs": "c2pa,mcp-server-client",
        }
    )


class SemanticHTML(HTMLParser):
    """Collect stable public-experience markers instead of volatile page bytes."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title_parts: list[str] = []
        self.in_title = False
        self.markers: dict[str, str] = {}
        self.scripts: set[str] = set()
        self.provider_scripts: set[str] = set()
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
            src = values["src"]
            if _is_provider_injected_script(src, attrs):
                self.provider_scripts.add(src)
            else:
                self.scripts.add(src)
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
        return {
            **stable,
            "provider_scripts": sorted(self.provider_scripts),
            "semantic_sha256": canonical_sha256(stable),
        }


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


def _inventory_counts(value: Any) -> dict[str, int] | None:
    if not isinstance(value, Mapping) or set(value) != set(INVENTORY_KINDS):
        return None
    if any(type(value[kind]) is not int or value[kind] < 0 for kind in INVENTORY_KINDS):
        return None
    return {kind: value[kind] for kind in INVENTORY_KINDS}


def _profile_record(response: Mapping[str, Any]) -> Mapping[str, Any] | None:
    """Reject duplicate JSON keys instead of choosing one ambiguous declaration."""
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate profile inventory key")
            result[key] = value
        return result

    if response.get("status") != 200:
        return None
    text = response.get("text")
    if isinstance(text, str):
        try:
            value = json.loads(text, object_pairs_hook=unique_object)
        except (ValueError, TypeError):
            return None
    else:
        value = response.get("json")
    return value if isinstance(value, Mapping) else None


def _public_manifest(response: Mapping[str, Any]) -> Mapping[str, Any] | None:
    value = _profile_record(response)
    scope = value.get("inventoryScope") if value else None
    if not (
        value and value.get("schemaVersion") == 2
        and value.get("org") == "SZLHOLDINGS"
        and isinstance(scope, Mapping)
        and scope.get("visibility") == "public-only"
        and scope.get("authenticated") is False
        and scope.get("privateAssetsIncluded") is False
        and _inventory_counts(value.get("counts")) is not None
    ):
        return None
    return value


def declared_profile_counts(text: str) -> dict[str, int] | None:
    """Read current public declarations without promoting historical snapshots.

    Profile declarations are compared with the independently observed anonymous
    membership below; they do not replace authenticated official inventory.
    """
    current: list[str] = []
    legacy: list[re.Match[str]] = []
    historical_section = False
    for paragraph in re.split(r"\n\s*\n", text):
        plain = re.sub(r"[*_`]", "", paragraph).strip()
        heading = re.match(r"^#{1,6}\s+([^\n]+)", plain)
        if heading:
            historical_section = "historical" in heading.group(1).lower()
        if historical_section or re.search(r"\bhistorical\b", plain, re.IGNORECASE):
            continue
        if re.match(r"^Current inventory\b", plain, re.IGNORECASE):
            current.append(plain)
        else:
            legacy.extend(PROFILE_COUNTS.finditer(plain))
    if current:
        if len(current) != 1:
            return None
        matches = list(CURRENT_PROFILE_PUBLIC_COUNTS.finditer(current[0]))
        matches.extend(PROFILE_COUNTS.finditer(current[0]))
    else:
        matches = legacy
    if len(matches) != 1:
        return None
    return {key: int(value) for key, value in matches[0].groupdict().items()}


def profile_inventory_contract(
    config: Mapping[str, Any],
    inventory: Mapping[str, Any],
    a11oy_sha: str | None,
) -> dict[str, Any]:
    profile = config["profile"]
    repository = str(profile["repository"])
    head = github_main(repository)
    record_path = str(profile.get("inventory_path", "profile/public-inventory.json"))
    record_file = (
        github_file(repository, record_path, str(head["sha"]))
        if head.get("observed") else {}
    )
    record = _profile_record(record_file)
    actual = _inventory_counts(inventory.get("counts"))
    declared = None
    blockers: list[str] = []
    expected_scope = config.get("public_inventory_scope")
    record_valid = bool(
        record
        and record.get("schema") == "szl.public-profile-inventory/v1"
        and isinstance(expected_scope, Mapping)
        and expected_scope == PREDICATE
        and expected_scope.get("authentication") == "none"
        and expected_scope.get("visibility") == "public-only"
        and record.get("scope") == expected_scope
        and record.get("scope_sha256") == canonical_sha256(expected_scope)
        and _inventory_counts(record.get("counts")) is not None
        and record.get("source_repository") == "szl-holdings/a11oy"
        and record.get("source_path") == "docs/huggingface-ecosystem-manifest.json"
        and isinstance(record.get("source_revision"), str)
        and SHA40.fullmatch(record["source_revision"])
        and isinstance(record.get("source_git_blob"), str)
        and SHA40.fullmatch(record["source_git_blob"])
        and isinstance(record.get("source_sha256"), str)
        and re.fullmatch(r"[0-9a-f]{64}", record["source_sha256"])
        and record.get("production_authorization") is False
        and record.get("runtime_readiness_inferred") is False
        and record.get("model_quality_inferred") is False
    )
    if record_valid:
        try:
            observed_at = dt.datetime.fromisoformat(str(record.get("observed_at", "")).replace("Z", "+00:00"))
            record_valid = observed_at.tzinfo is not None
        except ValueError:
            record_valid = False
    if not record_valid:
        blockers.append("HF_PROFILE_INVENTORY_RECORD_UNAVAILABLE_OR_INVALID")
    else:
        declared = _inventory_counts(record["counts"])
    enumeration = (
        inventory.get("enumeration_state") if isinstance(inventory, Mapping) else None
    )
    enumeration_complete = (
        isinstance(enumeration, Mapping)
        and all(enumeration.get(kind) == "COMPLETE" for kind in INVENTORY_KINDS)
    )

    manifest = None
    manifest_file: dict[str, Any] = {}
    if a11oy_sha:
        manifest_file = github_file(
            "szl-holdings/a11oy",
            "docs/huggingface-ecosystem-manifest.json",
            a11oy_sha,
        )
        manifest_json = _public_manifest(manifest_file)
        if manifest_json:
            manifest = _inventory_counts(manifest_json.get("counts"))

    source_bound = False
    if record_valid:
        pinned = github_file(record["source_repository"], record["source_path"], record["source_revision"])
        quoted = urllib.parse.quote(record["source_path"], safe="/")
        blob = fetch(
            f"https://api.github.com/repos/{record['source_repository']}/contents/"
            f"{quoted}?ref={record['source_revision']}", github=True,
        )
        metadata = blob.get("json")
        pinned_json = _public_manifest(pinned)
        source_bound = bool(
            pinned.get("status") == 200
            and pinned.get("sha256") == record["source_sha256"]
            and isinstance(pinned_json, Mapping)
            and _inventory_counts(pinned_json.get("counts")) == declared
            and blob.get("status") == 200
            and isinstance(metadata, Mapping)
            and metadata.get("type") == "file"
            and metadata.get("path") == record["source_path"]
            and metadata.get("sha") == record["source_git_blob"]
            and manifest_file.get("status") == 200
            and manifest_file.get("sha256") == record["source_sha256"]
        )
        if not source_bound:
            blockers.append("HF_PROFILE_INVENTORY_SOURCE_BINDING_MISMATCH_OR_UNAVAILABLE")

    aligned = bool(
        head.get("observed")
        and record_valid
        and source_bound
        and declared
        and actual
        and manifest
        and inventory.get("observed") is True
        and enumeration_complete
        and declared == actual == manifest
    )
    if not aligned:
        if not enumeration_complete:
            blockers.append("HF_INVENTORY_ENUMERATION_INCOMPLETE_OR_UNAVAILABLE")
        else:
            blockers.append("HF_INVENTORY_COUNT_MISMATCH_OR_UNAVAILABLE")
    return {
        "profile_repository": repository,
        "profile_sha": head.get("sha"),
        "inventory_record_path": record_path,
        "inventory_record_sha256": record_file.get("sha256"),
        "inventory_record_source_revision": record.get("source_revision") if record else None,
        "inventory_record_source_git_blob": record.get("source_git_blob") if record else None,
        "inventory_record_source_sha256": record.get("source_sha256") if record else None,
        "inventory_record_observed_at": record.get("observed_at") if record else None,
        "inventory_record_valid": record_valid,
        "inventory_record_source_bound": source_bound,
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

    base = f"https://api.github.com/repos/{repository}"
    pages = fetch(f"{base}/pages", github=True)
    metadata = pages.get("json")
    mode = metadata.get("build_type") if pages.get("status") == 200 and isinstance(metadata, Mapping) else None
    pages_sha = None
    pages_status = None
    revision_source = None
    deployment_id = None
    deployment_http = None
    status_http = None
    deployment_url = None
    deployment_log_url = None
    deployment_valid = False
    if mode == "legacy":
        build = fetch(f"{base}/pages/builds/latest", github=True)
        deployment_http = build.get("status")
        build_json = build.get("json")
        if deployment_http == 200 and isinstance(build_json, Mapping):
            pages_sha = _candidate_revision(build_json.get("commit"))
            pages_status = build_json.get("status")
            revision_source = "legacy-pages-build"
            deployment_valid = pages_status == "built"
    elif mode == "workflow":
        # Actions deployments do not update the old branch-build endpoint.
        # Only the newest github-pages deployment and its newest status count.
        # A failed/newer deployment never falls back to an older green record.
        deployments = fetch(f"{base}/deployments?environment=github-pages&per_page=1", github=True)
        deployment_http = deployments.get("status")
        rows = deployments.get("json")
        row = rows[0] if deployment_http == 200 and isinstance(rows, list) and len(rows) == 1 else None
        if isinstance(row, Mapping):
            pages_sha = _candidate_revision(row.get("sha"))
            candidate_id = row.get("id")
            if (type(candidate_id) is int and candidate_id > 0 and pages_sha
                    and row.get("environment") == "github-pages" and row.get("ref") in ("main", "refs/heads/main")):
                deployment_id = candidate_id
                statuses = fetch(f"{base}/deployments/{deployment_id}/statuses?per_page=1", github=True)
                status_http = statuses.get("status")
                status_rows = statuses.get("json")
                status = status_rows[0] if status_http == 200 and isinstance(status_rows, list) and len(status_rows) == 1 else None
                if isinstance(status, Mapping):
                    pages_status = status.get("state")
                    deployment_url = status.get("environment_url")
                    deployment_log_url = status.get("log_url")
                    # Pages may report its configured custom domain as http.
                    # The independent public root probe still requires the
                    # configured origin, normally https, to return HTTP 200.
                    allowed_sites = {origin.rstrip("/")}
                    if origin.startswith("https://"):
                        allowed_sites.add("http://" + origin[len("https://"):].rstrip("/"))
                    metadata_url = metadata.get("html_url")
                    deployment_valid = (
                        pages_status == "success"
                        and isinstance(deployment_url, str) and deployment_url.rstrip("/") in allowed_sites
                        and isinstance(metadata_url, str) and metadata_url.rstrip("/") in allowed_sites
                    )
                revision_source = "github-pages-deployment"

    exact_pages = pages_sha if deployment_valid else None
    aligned = bool(
        source.get("observed")
        and root.get("status") == 200
        and exact_pages == source.get("sha")
    )
    blockers: list[str] = []
    if root.get("status") != 200:
        blockers.append(f"PROOF_ROOT_HTTP_{root.get('status')}")
    if pages_status not in (None, "built", "success"):
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
        "pages_build_type": mode,
        "pages_build_status": pages_status,
        "pages_revision": pages_sha,
        "pages_revision_source": revision_source,
        "pages_deployment_id": deployment_id,
        "pages_deployment_http_status": deployment_http,
        "pages_deployment_status_http_status": status_http,
        "pages_deployment_environment_url": deployment_url,
        "pages_deployment_log_url": deployment_log_url,
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
