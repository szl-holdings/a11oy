#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read-only, fixed-origin witness for the SZL public command estate.

The witness consumes only the repository-owned manifest. It accepts no caller-
supplied target URL, performs GET requests only, follows redirects only within
the original host, reads no credentials from public products, and records only
bounded metadata plus response hashes. A product is either source-bound and
reachable or explicitly unverified.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

SCHEMA = "szl.public-estate-witness/v1"
MANIFEST_SCHEMA = "szl.public-estate/v1"
USER_AGENT = "SZLHOLDINGS-PublicEstateWitness/1.0"
MAX_RESPONSE_BYTES = 1_048_576
SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
ALLOWED_REVISION_POLICIES = {"exact-default-branch", "declared-commit"}
ALLOWED_SOURCE_REPOSITORY_POLICIES = {
    "runtime-declared",
    "manifest-fixed-runtime-revision",
}
ALLOWED_HF_REVISION_POLICIES = {"runtime-declared", "provider-observed"}
ALLOWED_CAPABILITY_STATES = {
    "folded",
    "portfolio-label",
    "migration-required",
}


class ContractError(RuntimeError):
    """Raised when the repository-owned estate contract is malformed."""


class SameHostRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Reject redirects that leave the fixed host declared by the manifest."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Mapping[str, str],
        newurl: str,
    ) -> urllib.request.Request | None:
        original = urllib.parse.urlsplit(req.full_url)
        redirected = urllib.parse.urlsplit(newurl)
        if (
            redirected.scheme != "https"
            or redirected.hostname != original.hostname
            or redirected.port not in (None, 443)
        ):
            raise urllib.error.HTTPError(
                req.full_url,
                code,
                "cross-host or non-HTTPS redirect rejected",
                headers,
                fp,
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


@dataclass(frozen=True)
class HttpObservation:
    url: str
    status: int
    content_type: str
    body_sha256: str
    body: bytes

    def receipt(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "status": self.status,
            "content_type": self.content_type,
            "body_sha256": self.body_sha256,
            "body_bytes": len(self.body),
        }


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def require_string(value: Any, label: str) -> str:
    require(isinstance(value, str) and bool(value.strip()), f"{label} must be a string")
    return value.strip()


def require_string_list(value: Any, label: str) -> list[str]:
    require(isinstance(value, list) and bool(value), f"{label} must be a non-empty list")
    result = [require_string(item, f"{label}[]") for item in value]
    require(len(result) == len(set(result)), f"{label} contains duplicates")
    return result


def validate_base_url(value: Any, allowed_hosts: set[str], label: str) -> str:
    base_url = require_string(value, label).rstrip("/")
    parsed = urllib.parse.urlsplit(base_url)
    require(parsed.scheme == "https", f"{label} must use HTTPS")
    require(parsed.hostname in allowed_hosts, f"{label} host is not allowlisted")
    require(parsed.port in (None, 443), f"{label} uses a non-standard port")
    require(parsed.path in ("", "/"), f"{label} must not contain a path")
    require(not parsed.query and not parsed.fragment, f"{label} must not contain query or fragment")
    return base_url


def validate_surface(
    surface: Any,
    *,
    allowed_hosts: set[str],
    expected_class: str,
) -> dict[str, Any]:
    require(isinstance(surface, dict), f"{expected_class} entry must be an object")
    value = dict(surface)
    surface_id = require_string(value.get("id"), f"{expected_class}.id")
    require(value.get("public") is True, f"{surface_id} must be explicitly public")
    require_string(value.get("title"), f"{surface_id}.title")
    require_string(value.get("class"), f"{surface_id}.class")
    hf_repository = require_string(value.get("hf_repository"), f"{surface_id}.hf_repository")
    require(hf_repository.startswith("SZLHOLDINGS/"), f"{surface_id} must be in SZLHOLDINGS")
    value["base_url"] = validate_base_url(
        value.get("base_url"),
        allowed_hosts,
        f"{surface_id}.base_url",
    )
    value["deployment_source_repository"] = require_string(
        value.get("deployment_source_repository"),
        f"{surface_id}.deployment_source_repository",
    )
    policy = require_string(value.get("revision_policy"), f"{surface_id}.revision_policy")
    require(policy in ALLOWED_REVISION_POLICIES, f"{surface_id} has unknown revision policy")
    if policy == "exact-default-branch":
        require_string(value.get("default_branch"), f"{surface_id}.default_branch")

    source_policy = str(
        value.get("source_repository_policy", "runtime-declared")
    ).strip()
    require(
        source_policy in ALLOWED_SOURCE_REPOSITORY_POLICIES,
        f"{surface_id} has unknown source-repository policy",
    )
    if source_policy == "manifest-fixed-runtime-revision":
        require(
            policy == "exact-default-branch",
            f"{surface_id} manifest-fixed source policy requires exact-default-branch",
        )
    value["source_repository_policy"] = source_policy

    hf_policy = str(value.get("hf_revision_policy", "runtime-declared")).strip()
    require(
        hf_policy in ALLOWED_HF_REVISION_POLICIES,
        f"{surface_id} has unknown Hugging Face revision policy",
    )
    value["hf_revision_policy"] = hf_policy

    required_paths = require_string_list(
        value.get("required_paths"),
        f"{surface_id}.required_paths",
    )
    for path in required_paths:
        parsed = urllib.parse.urlsplit(path)
        require(path.startswith("/"), f"{surface_id} path must begin with /")
        require(not parsed.scheme and not parsed.netloc, f"{surface_id} path cannot contain an origin")
        require(not parsed.query and not parsed.fragment, f"{surface_id} path cannot contain query or fragment")
    build_info_path = require_string(value.get("build_info_path"), f"{surface_id}.build_info_path")
    require(build_info_path in required_paths, f"{surface_id} build-info path must be required")
    value["required_paths"] = required_paths
    return value


def load_and_validate_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ContractError(f"cannot read manifest: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"manifest is not valid JSON: {exc}") from exc

    require(isinstance(manifest, dict), "manifest must be an object")
    require(manifest.get("schema") == MANIFEST_SCHEMA, "unexpected manifest schema")
    require_string(manifest.get("estate"), "estate")
    require_string(manifest.get("source_repository"), "source_repository")
    require(manifest.get("truth_policy") == "exact-source-or-unverified", "truth policy drift")

    allowed_hosts = set(require_string_list(manifest.get("allowed_hosts"), "allowed_hosts"))
    require("api.github.com" in allowed_hosts, "GitHub API host must be allowlisted")
    require("huggingface.co" in allowed_hosts, "Hugging Face API host must be allowlisted")

    raw_platforms = manifest.get("platforms")
    raw_products = manifest.get("public_products")
    require(isinstance(raw_platforms, list), "platforms must be a list")
    require(isinstance(raw_products, list), "public_products must be a list")
    platforms = [
        validate_surface(item, allowed_hosts=allowed_hosts, expected_class="platform")
        for item in raw_platforms
    ]
    products = [
        validate_surface(item, allowed_hosts=allowed_hosts, expected_class="public_product")
        for item in raw_products
    ]
    require(len(platforms) == manifest.get("platform_count"), "platform count drift")
    require(
        len(products) == manifest.get("public_vertical_product_count"),
        "public product count drift",
    )
    require(len(platforms) == 1, "exactly one public platform is expected")
    require(len(products) == 5, "exactly five public vertical products are expected")

    surfaces = platforms + products
    surface_ids = [item["id"] for item in surfaces]
    hf_repositories = [item["hf_repository"] for item in surfaces]
    base_urls = [item["base_url"] for item in surfaces]
    require(len(surface_ids) == len(set(surface_ids)), "public surface IDs must be unique")
    require(len(hf_repositories) == len(set(hf_repositories)), "public HF repositories must be unique")
    require(len(base_urls) == len(set(base_urls)), "public origins must be unique")
    require({item["id"] for item in products} == {"killinchu", "lyte", "finance", "terra", "counsel"}, "public product identity drift")

    planes = manifest.get("capability_planes")
    require(isinstance(planes, list), "capability_planes must be a list")
    plane_by_id: dict[str, dict[str, Any]] = {}
    for raw in planes:
        require(isinstance(raw, dict), "capability-plane entry must be an object")
        plane = dict(raw)
        plane_id = require_string(plane.get("id"), "capability_plane.id")
        require(plane_id not in plane_by_id, f"duplicate capability plane: {plane_id}")
        state = require_string(plane.get("status"), f"{plane_id}.status")
        require(state in ALLOWED_CAPABILITY_STATES, f"{plane_id} has unknown state")
        require(
            plane.get("independent_public_space_allowed") is False,
            f"{plane_id} cannot be an independent public product",
        )
        plane_by_id[plane_id] = plane
    require(set(plane_by_id) == {"sentra", "vessels", "aegis", "immune"}, "capability-plane inventory drift")
    require(not set(plane_by_id).intersection(surface_ids), "capability plane leaked into public surfaces")
    require(plane_by_id["sentra"].get("runtime") == "killinchu", "Sentra must resolve to Killinchu")
    require(plane_by_id["vessels"].get("runtime") == "killinchu", "Vessels must resolve to Killinchu")
    require(plane_by_id["aegis"].get("status") == "portfolio-label", "Aegis must remain a label")
    require(plane_by_id["immune"].get("status") == "migration-required", "IMMUNE must remain migration-gated")
    require(plane_by_id["immune"].get("runtime") is None, "IMMUNE cannot silently alias to a runtime")

    retirement = manifest.get("retirement_candidates")
    require(isinstance(retirement, list), "retirement_candidates must be a list")
    for candidate in retirement:
        require(isinstance(candidate, dict), "retirement candidate must be an object")
        require(candidate.get("state") == "evidence-gated", "retirement must remain evidence-gated")
        require_string_list(candidate.get("retire_only_after"), "retire_only_after")

    result = dict(manifest)
    result["allowed_hosts"] = sorted(allowed_hosts)
    result["platforms"] = platforms
    result["public_products"] = products
    result["manifest_sha256"] = sha256_hex(canonical_json(manifest))
    return result


def build_opener() -> urllib.request.OpenerDirector:
    context = ssl.create_default_context()
    return urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context),
        SameHostRedirectHandler(),
    )


def request_bytes(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    timeout: float,
    token: str | None = None,
) -> HttpObservation:
    headers = {
        "Accept": "application/json, text/html;q=0.9, */*;q=0.1",
        "User-Agent": USER_AGENT,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers, method="GET")
    with opener.open(request, timeout=timeout) as response:
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            raise ContractError(f"response exceeded {MAX_RESPONSE_BYTES} bytes: {url}")
        return HttpObservation(
            url=response.geturl(),
            status=int(response.status),
            content_type=response.headers.get("content-type", "").split(";", 1)[0].strip().lower(),
            body_sha256=sha256_hex(body),
            body=body,
        )


def request_json(
    opener: urllib.request.OpenerDirector,
    url: str,
    *,
    timeout: float,
    token: str | None = None,
) -> tuple[HttpObservation, dict[str, Any]]:
    observation = request_bytes(opener, url, timeout=timeout, token=token)
    try:
        payload = json.loads(observation.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError(f"expected JSON from {url}: {exc}") from exc
    require(isinstance(payload, dict), f"expected an object from {url}")
    return observation, payload


def join_fixed(base_url: str, path: str) -> str:
    parsed = urllib.parse.urlsplit(path)
    if parsed.scheme or parsed.netloc or not path.startswith("/"):
        raise ContractError("manifest path escaped its fixed origin")
    return f"{base_url}{path}"


def selected_build_fields(payload: Mapping[str, Any]) -> dict[str, Any]:
    candidates: list[Mapping[str, Any]] = [payload]
    for key in ("build", "source", "deployment", "data"):
        nested = payload.get(key)
        if isinstance(nested, dict):
            candidates.append(nested)

    aliases = {
        "source_repository": ("source_repository", "repository", "repo"),
        "source_revision": ("source_revision", "git_sha", "commit_sha", "sha"),
        "workflow_run_id": ("workflow_run_id", "run_id"),
        "hf_repository": ("hf_repository", "space_repository"),
        "hf_revision": ("hf_revision", "space_revision"),
        "artifact_set_sha256": ("artifact_set_sha256", "artifact_sha256"),
        "public_experience": ("public_experience", "experience_version"),
        "product_source": ("product_source",),
    }
    selected: dict[str, Any] = {}
    for canonical, names in aliases.items():
        for candidate in candidates:
            value = next((candidate[name] for name in names if name in candidate), None)
            if value not in (None, ""):
                selected[canonical] = value
                break

    # Killinchu's strict public route intentionally exposes build.revision rather
    # than duplicating a repository claim inside the process. Normalize only this
    # unambiguous nested runtime field; never treat an arbitrary deployment
    # revision as source identity.
    build = payload.get("build")
    if "source_revision" not in selected and isinstance(build, dict):
        revision = build.get("revision")
        if revision not in (None, ""):
            selected["source_revision"] = revision
    return selected


def apply_source_repository_policy(
    fields: Mapping[str, Any],
    payload: Mapping[str, Any],
    surface: Mapping[str, Any],
) -> dict[str, Any]:
    """Resolve a repository claim only under an explicit manifest policy.

    ``manifest-fixed-runtime-revision`` is deliberately narrow: the fixed route
    must identify the expected service, report an OBSERVED 40-hex revision, and
    disclose that the revision came from the deployer's ``SZL_GIT_SHA``. The
    manifest then supplies the immutable repository name. Missing or ambiguous
    evidence fails closed.
    """

    result = dict(fields)
    if result.get("source_repository"):
        return result
    if surface.get("source_repository_policy") != "manifest-fixed-runtime-revision":
        return result

    build = payload.get("build")
    require(isinstance(build, dict), "manifest-fixed source policy requires build object")
    require(
        str(payload.get("service", "")) == str(surface.get("id", "")),
        "manifest-fixed source policy service mismatch",
    )
    revision = str(result.get("source_revision", "")).lower()
    require(bool(SHA40.fullmatch(revision)), "manifest-fixed source revision is invalid")
    require(build.get("state") == "OBSERVED", "manifest-fixed source revision is not observed")
    require(
        build.get("revision_source") == "env:SZL_GIT_SHA",
        "manifest-fixed source revision has an untrusted origin",
    )
    result["source_repository"] = str(surface["deployment_source_repository"])
    result["source_repository_evidence"] = "MANIFEST_FIXED_RUNTIME_REVISION"
    return result


def github_token() -> str | None:
    for name in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.getenv(name, "").strip()
        if value:
            return value
    return None


def github_api_url(repository: str, suffix: str) -> str:
    owner, separator, name = repository.partition("/")
    require(bool(separator and owner and name), f"invalid GitHub repository: {repository}")
    return f"https://api.github.com/repos/{owner}/{name}{suffix}"


def github_default_tip(
    opener: urllib.request.OpenerDirector,
    repository: str,
    branch: str,
    *,
    timeout: float,
    token: str | None,
) -> tuple[str, dict[str, Any]]:
    encoded_branch = urllib.parse.quote(branch, safe="")
    observation, payload = request_json(
        opener,
        github_api_url(repository, f"/branches/{encoded_branch}"),
        timeout=timeout,
        token=token,
    )
    commit = payload.get("commit")
    require(isinstance(commit, dict), f"GitHub branch response missing commit: {repository}")
    sha = str(commit.get("sha", "")).lower()
    require(bool(SHA40.fullmatch(sha)), f"GitHub returned invalid branch SHA: {repository}")
    return sha, observation.receipt()


def github_commit_exists(
    opener: urllib.request.OpenerDirector,
    repository: str,
    revision: str,
    *,
    timeout: float,
    token: str | None,
) -> dict[str, Any]:
    observation, payload = request_json(
        opener,
        github_api_url(repository, f"/commits/{revision}"),
        timeout=timeout,
        token=token,
    )
    observed_sha = str(payload.get("sha", "")).lower()
    require(observed_sha == revision, f"GitHub commit proof mismatch for {repository}@{revision}")
    return observation.receipt()


def hf_space_revision(
    opener: urllib.request.OpenerDirector,
    hf_repository: str,
    *,
    timeout: float,
) -> tuple[str, dict[str, Any]]:
    encoded = urllib.parse.quote(hf_repository, safe="/")
    observation, payload = request_json(
        opener,
        f"https://huggingface.co/api/spaces/{encoded}",
        timeout=timeout,
    )
    revision = str(payload.get("sha", "")).lower()
    require(bool(SHA40.fullmatch(revision)), f"Hugging Face returned invalid Space SHA: {hf_repository}")
    return revision, observation.receipt()


def observe_surface(
    opener: urllib.request.OpenerDirector,
    surface: Mapping[str, Any],
    *,
    timeout: float,
    token: str | None,
) -> dict[str, Any]:
    surface_id = str(surface["id"])
    route_receipts: list[dict[str, Any]] = []
    build_payload: dict[str, Any] | None = None
    failures: list[str] = []

    for path in surface["required_paths"]:
        url = join_fixed(str(surface["base_url"]), str(path))
        try:
            observation = request_bytes(opener, url, timeout=timeout)
            route_receipts.append({"path": path, **observation.receipt()})
            if observation.status != 200:
                failures.append(f"{path}: HTTP {observation.status}")
            if path == surface["build_info_path"]:
                try:
                    decoded = json.loads(observation.body.decode("utf-8"))
                    if not isinstance(decoded, dict):
                        raise ValueError("build-info is not an object")
                    build_payload = decoded
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
                    failures.append(f"{path}: invalid build-info JSON ({exc})")
        except urllib.error.HTTPError as exc:
            failures.append(f"{path}: HTTP {exc.code}")
            route_receipts.append(
                {
                    "path": path,
                    "url": url,
                    "status": int(exc.code),
                    "error": type(exc).__name__,
                }
            )
        except Exception as exc:
            failures.append(f"{path}: {type(exc).__name__}")
            route_receipts.append(
                {
                    "path": path,
                    "url": url,
                    "status": None,
                    "error": type(exc).__name__,
                }
            )

    fields = apply_source_repository_policy(
        selected_build_fields(build_payload or {}),
        build_payload or {},
        surface,
    )
    expected_repository = str(surface["deployment_source_repository"])
    observed_repository = str(fields.get("source_repository", ""))
    observed_revision = str(fields.get("source_revision", "")).lower()
    if observed_repository != expected_repository:
        failures.append(
            f"source_repository: expected {expected_repository}, observed {observed_repository or 'MISSING'}"
        )
    if not SHA40.fullmatch(observed_revision):
        failures.append("source_revision: missing or invalid")

    source_proof: dict[str, Any] | None = None
    if SHA40.fullmatch(observed_revision):
        try:
            if surface["revision_policy"] == "exact-default-branch":
                expected_revision, proof = github_default_tip(
                    opener,
                    expected_repository,
                    str(surface["default_branch"]),
                    timeout=timeout,
                    token=token,
                )
                source_proof = {
                    "policy": "exact-default-branch",
                    "expected_revision": expected_revision,
                    "github": proof,
                }
                if observed_revision != expected_revision:
                    failures.append(
                        f"source_revision: expected default tip {expected_revision}, observed {observed_revision}"
                    )
            else:
                proof = github_commit_exists(
                    opener,
                    expected_repository,
                    observed_revision,
                    timeout=timeout,
                    token=token,
                )
                source_proof = {
                    "policy": "declared-commit",
                    "expected_revision": observed_revision,
                    "github": proof,
                }
        except Exception as exc:
            failures.append(f"source proof: {type(exc).__name__}: {exc}")

    hf_proof: dict[str, Any] | None = None
    try:
        current_hf_revision, proof = hf_space_revision(
            opener,
            str(surface["hf_repository"]),
            timeout=timeout,
        )
        hf_revision_policy = str(surface["hf_revision_policy"])
        declared_hf_revision = str(fields.get("hf_revision", "")).lower()
        hf_proof = {
            "policy": hf_revision_policy,
            "current_revision": current_hf_revision,
            "declared_revision": declared_hf_revision or None,
            "metadata": proof,
        }
        if hf_revision_policy == "provider-observed":
            # Provider metadata is evidence of the current Space repository tip,
            # not a claim that the running process can introspect that tip. Keep
            # the two facts separate in the receipt.
            fields["hf_revision_observed_by_witness"] = current_hf_revision
            fields["hf_revision_evidence"] = "HUGGING_FACE_PROVIDER_API"
        elif not SHA40.fullmatch(declared_hf_revision):
            failures.append("hf_revision: missing or invalid")
        elif declared_hf_revision != current_hf_revision:
            failures.append(
                f"hf_revision: metadata is {current_hf_revision}, build declares {declared_hf_revision}"
            )
    except Exception as exc:
        failures.append(f"Hugging Face proof: {type(exc).__name__}: {exc}")

    artifact_hash = str(fields.get("artifact_set_sha256", "")).lower()
    if artifact_hash and not SHA64.fullmatch(artifact_hash):
        failures.append("artifact_set_sha256: invalid")

    return {
        "id": surface_id,
        "title": surface["title"],
        "class": surface["class"],
        "hf_repository": surface["hf_repository"],
        "base_url": surface["base_url"],
        "revision_policy": surface["revision_policy"],
        "routes": route_receipts,
        "build": fields,
        "source_proof": source_proof,
        "hf_proof": hf_proof,
        "verified": not failures,
        "failures": failures,
    }


def build_receipt(
    manifest: Mapping[str, Any],
    *,
    mode: str,
    observations: Iterable[Mapping[str, Any]],
    attempt: int,
) -> dict[str, Any]:
    rows = [dict(item) for item in observations]
    complete = mode == "live" and bool(rows) and all(row.get("verified") is True for row in rows)
    receipt: dict[str, Any] = {
        "schema": SCHEMA,
        "generated_at": utc_now(),
        "mode": mode,
        "estate": manifest["estate"],
        "manifest_schema": manifest["schema"],
        "manifest_sha256": manifest["manifest_sha256"],
        "truth_policy": manifest["truth_policy"],
        "attempt": attempt,
        "platform_count": len(manifest["platforms"]),
        "public_vertical_product_count": len(manifest["public_products"]),
        "public_surface_count": len(rows),
        "verified_surface_count": sum(row.get("verified") is True for row in rows),
        "complete": complete,
        "surfaces": rows,
        "capability_planes": manifest["capability_planes"],
        "retirement_candidates": manifest["retirement_candidates"],
        "network_contract": {
            "method": "GET_ONLY",
            "origins": "MANIFEST_FIXED",
            "caller_supplied_urls": False,
            "cross_host_redirects": False,
            "credentials_sent_to_public_products": False,
            "response_bodies_recorded": False,
            "max_response_bytes": MAX_RESPONSE_BYTES,
        },
    }
    unsigned = dict(receipt)
    receipt["receipt_sha256"] = sha256_hex(canonical_json(unsigned))
    return receipt


def write_receipt(path: Path, receipt: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def run_live(
    manifest: Mapping[str, Any],
    *,
    timeout: float,
    retry_seconds: int,
    retry_interval: int,
) -> dict[str, Any]:
    opener = build_opener()
    token = github_token()
    deadline = time.monotonic() + max(0, retry_seconds)
    attempt = 0
    receipt: dict[str, Any]
    surfaces = list(manifest["platforms"]) + list(manifest["public_products"])

    while True:
        attempt += 1
        observations = [
            observe_surface(opener, surface, timeout=timeout, token=token)
            for surface in surfaces
        ]
        receipt = build_receipt(
            manifest,
            mode="live",
            observations=observations,
            attempt=attempt,
        )
        if receipt["complete"] is True or time.monotonic() >= deadline:
            return receipt
        remaining = deadline - time.monotonic()
        time.sleep(min(max(1, retry_interval), max(0.0, remaining)))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("governance/public-estate.v1.json"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("public-estate-live-witness.json"),
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--retry-seconds", type=int, default=0)
    parser.add_argument("--retry-interval", type=int, default=30)
    parser.add_argument("--offline-contract-only", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(list(sys.argv[1:] if argv is None else argv))
    try:
        manifest = load_and_validate_manifest(args.manifest)
        if args.offline_contract_only:
            receipt = build_receipt(
                manifest,
                mode="offline-contract",
                observations=[],
                attempt=1,
            )
        else:
            receipt = run_live(
                manifest,
                timeout=max(1.0, args.timeout),
                retry_seconds=max(0, args.retry_seconds),
                retry_interval=max(1, args.retry_interval),
            )
        write_receipt(args.output, receipt)
        print(json.dumps(receipt, indent=2, sort_keys=True, ensure_ascii=False))
        if args.offline_contract_only:
            return 0
        return 0 if receipt["complete"] is True else 1
    except ContractError as exc:
        failure = {
            "schema": SCHEMA,
            "generated_at": utc_now(),
            "complete": False,
            "error": f"ContractError: {exc}",
        }
        write_receipt(args.output, failure)
        print(json.dumps(failure, indent=2, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
