#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Emit a read-only, evidence-labeled inventory for Operation Verified Throughput."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

ORG = "szl-holdings"
REPO = "a11oy"
HF_ORG = "SZLHOLDINGS"
KERNEL_REF = "c7c0ba17c2eaec60ad38ea9172b4a0d9ca0b582f"
ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "audit"
USER_AGENT = "szl-operation-verified-throughput/1.0"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
EXACT_TAG = re.compile(r"^v\d+\.\d+\.\d+$")
USES_RE = re.compile(
    r"(?m)^\s*uses:\s*([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_./-]+)?)@([^\s#]+)"
)


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def command(args: list[str], cwd: Path = ROOT, check: bool = True) -> str:
    proc = subprocess.run(
        args,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and proc.returncode:
        raise RuntimeError(
            f"{args[0]} failed with exit {proc.returncode}: {proc.stderr.strip()}"
        )
    return proc.stdout.strip()


def github_token() -> str:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        return token
    return command(["gh", "auth", "token"])


class GitHub:
    def __init__(self, token: str) -> None:
        self.token = token
        self.errors: list[dict[str, Any]] = []

    def get(self, endpoint: str, *, paginate: bool = False, required: bool = False) -> Any:
        url = (
            endpoint
            if endpoint.startswith("https://")
            else "https://api.github.com" + endpoint
        )
        pages: list[Any] = []
        while url:
            req = urllib.request.Request(
                url,
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self.token}",
                    "User-Agent": USER_AGENT,
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            try:
                with urllib.request.urlopen(req, timeout=45) as response:
                    body = json.loads(response.read().decode("utf-8"))
                    next_url = parse_next_link(response.headers.get("Link", ""))
            except urllib.error.HTTPError as exc:
                error = {
                    "endpoint": redact_url(url),
                    "http_status": exc.code,
                    "label": "BLOCKED",
                    "reason": exc.reason,
                }
                self.errors.append(error)
                if required:
                    raise RuntimeError(json.dumps(error)) from exc
                return {"status": "BLOCKED", **error}
            pages.append(body)
            if not paginate:
                break
            url = next_url
        if not paginate:
            return pages[0]
        flattened: list[Any] = []
        for page in pages:
            if isinstance(page, list):
                flattened.extend(page)
            else:
                flattened.append(page)
        return flattened


def parse_next_link(value: str) -> str:
    for part in value.split(","):
        match = re.match(r'\s*<([^>]+)>;\s*rel="([^"]+)"', part)
        if match and match.group(2) == "next":
            return match.group(1)
    return ""


def redact_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def http_json(url: str) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"Accept": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return {
                "label": "MEASURED",
                "url": redact_url(url),
                "http_status": response.status,
                "payload": json.loads(response.read().decode("utf-8")),
            }
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        code = getattr(exc, "code", None)
        return {
            "label": "FAILED",
            "url": redact_url(url),
            "http_status": code,
            "reason": str(exc),
        }


def repository_summary(repo: dict[str, Any]) -> dict[str, Any]:
    fields = (
        "id",
        "name",
        "full_name",
        "private",
        "archived",
        "disabled",
        "default_branch",
        "visibility",
        "pushed_at",
        "updated_at",
    )
    summary = {field: repo.get(field) for field in fields}
    if repo.get("private"):
        private_name = str(summary.pop("name", ""))
        for sensitive_field in ("full_name", "id", "pushed_at", "updated_at"):
            summary.pop(sensitive_field, None)
        summary["name_sha256"] = hashlib.sha256(
            private_name.encode("utf-8")
        ).hexdigest()
        summary["name_redacted"] = True
    return summary


def summarize_branches(branches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": branch.get("name"),
            "protected": branch.get("protected"),
            "commit_sha": branch.get("commit", {}).get("sha"),
        }
        for branch in branches
    ]


def summarize_environments(response: Any) -> dict[str, Any]:
    if not isinstance(response, dict) or "environments" not in response:
        return response
    return {
        "total_count": response.get("total_count"),
        "environments": [
            {
                "name": environment.get("name"),
                "protection_rule_types": sorted(
                    {
                        rule.get("type")
                        for rule in environment.get("protection_rules", [])
                        if rule.get("type")
                    }
                ),
                "deployment_branch_policy": environment.get(
                    "deployment_branch_policy"
                ),
            }
            for environment in response.get("environments", [])
        ],
    }


def summarize_releases(releases: Any) -> Any:
    if not isinstance(releases, list):
        return releases
    return [
        {
            "tag_name": release.get("tag_name"),
            "target_commitish": release.get("target_commitish"),
            "draft": release.get("draft"),
            "prerelease": release.get("prerelease"),
            "published_at": release.get("published_at"),
            "assets": [
                {
                    "name": asset.get("name"),
                    "size": asset.get("size"),
                    "digest": asset.get("digest"),
                    "updated_at": asset.get("updated_at"),
                }
                for asset in release.get("assets", [])
            ],
        }
        for release in releases
    ]


def summarize_deployments(deployments: Any) -> Any:
    if not isinstance(deployments, list):
        return deployments
    return [
        {
            "sha": deployment.get("sha"),
            "ref": deployment.get("ref"),
            "task": deployment.get("task"),
            "environment": deployment.get("environment"),
            "created_at": deployment.get("created_at"),
            "updated_at": deployment.get("updated_at"),
        }
        for deployment in deployments
    ]


def summarize_pulls(pulls: Any) -> Any:
    if not isinstance(pulls, list):
        return pulls
    return [
        {
            "number": pull.get("number"),
            "title": pull.get("title"),
            "draft": pull.get("draft"),
            "state": pull.get("state"),
            "head": pull.get("head", {}).get("ref"),
            "base": pull.get("base", {}).get("ref"),
            "author": pull.get("user", {}).get("login"),
            "updated_at": pull.get("updated_at"),
        }
        for pull in pulls
    ]


def summarize_rulesets(rulesets: Any) -> Any:
    if not isinstance(rulesets, list):
        return rulesets
    return [
        {
            "name": ruleset.get("name"),
            "target": ruleset.get("target"),
            "enforcement": ruleset.get("enforcement"),
            "source_type": ruleset.get("source_type"),
            "conditions": ruleset.get("conditions"),
            "bypass_actor_types": sorted(
                {
                    actor.get("actor_type")
                    for actor in ruleset.get("bypass_actors", [])
                    if actor.get("actor_type")
                }
            ),
            "bypass_actor_count": len(ruleset.get("bypass_actors", [])),
            "rules": ruleset.get("rules", []),
        }
        for ruleset in rulesets
    ]


def summarize_protection(protection: Any) -> Any:
    if not isinstance(protection, dict) or protection.get("status") == "BLOCKED":
        return protection
    reviews = protection.get("required_pull_request_reviews") or {}
    checks = protection.get("required_status_checks") or {}
    restrictions = protection.get("restrictions") or {}
    return {
        "required_status_checks": {
            "strict": checks.get("strict"),
            "contexts": checks.get("contexts", []),
            "checks": checks.get("checks", []),
        },
        "enforce_admins": (protection.get("enforce_admins") or {}).get("enabled"),
        "required_pull_request_reviews": {
            "dismiss_stale_reviews": reviews.get("dismiss_stale_reviews"),
            "require_code_owner_reviews": reviews.get("require_code_owner_reviews"),
            "required_approving_review_count": reviews.get(
                "required_approving_review_count"
            ),
            "require_last_push_approval": reviews.get("require_last_push_approval"),
        },
        "required_conversation_resolution": (
            protection.get("required_conversation_resolution") or {}
        ).get("enabled"),
        "required_signatures": (protection.get("required_signatures") or {}).get(
            "enabled"
        ),
        "allow_force_pushes": (protection.get("allow_force_pushes") or {}).get(
            "enabled"
        ),
        "allow_deletions": (protection.get("allow_deletions") or {}).get("enabled"),
        "restriction_counts": {
            "users": len(restrictions.get("users", [])),
            "teams": len(restrictions.get("teams", [])),
            "apps": len(restrictions.get("apps", [])),
        },
    }


def ref_sha(gh: GitHub, action: str, ref: str) -> dict[str, Any]:
    owner, repository, *_ = action.split("/")
    if FULL_SHA.fullmatch(ref):
        return {"resolved_sha": ref, "resolution": "literal_full_sha"}
    encoded = urllib.parse.quote(ref, safe="")
    tag = gh.get(f"/repos/{owner}/{repository}/git/ref/tags/{encoded}")
    if isinstance(tag, dict) and "object" in tag:
        obj = tag["object"]
        if obj.get("type") == "tag":
            annotated = gh.get(f"/repos/{owner}/{repository}/git/tags/{obj['sha']}")
            if isinstance(annotated, dict) and annotated.get("object"):
                obj = annotated["object"]
        return {"resolved_sha": obj.get("sha"), "resolution": "tag_ref"}
    branch = gh.get(f"/repos/{owner}/{repository}/git/ref/heads/{encoded}")
    if isinstance(branch, dict) and branch.get("object"):
        return {
            "resolved_sha": branch["object"].get("sha"),
            "resolution": "branch_ref",
        }
    return {"resolved_sha": None, "resolution": "BLOCKED"}


def workflow_inventory(gh: GitHub) -> tuple[dict[str, Any], dict[str, Any]]:
    raw_entries: list[dict[str, Any]] = []
    identity_files: list[dict[str, Any]] = []
    workflow_dir = ROOT / ".github" / "workflows"
    for path in sorted((*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml"))):
        text = path.read_text(encoding="utf-8")
        permissions = sorted(
            set(
                re.findall(
                    r"(?m)^\s*(id-token|attestations|packages|contents|pull-requests):\s*([A-Za-z-]+)",
                    text,
                )
            )
        )
        identity_files.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "id_token_write": bool(
                    re.search(r"(?m)^\s*id-token:\s*write\s*$", text)
                ),
                "permissions_observed": [
                    {"permission": name, "level": level} for name, level in permissions
                ],
                "static_credential_names": sorted(
                    set(
                        re.findall(
                            r"(?:AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AZURE_CREDENTIALS|"
                            r"GOOGLE_APPLICATION_CREDENTIALS|GCP_SA_KEY|KUBECONFIG)",
                            text,
                        )
                    )
                ),
            }
        )
        for action, ref in USES_RE.findall(text):
            slsa = action.lower().startswith("slsa-framework/")
            raw_entries.append(
                {
                    "workflow": path.relative_to(ROOT).as_posix(),
                    "action": action,
                    "ref": ref,
                    "pin_policy": "exact_semver_tag" if slsa else "full_commit_sha",
                    "pin_compliant": bool(
                        EXACT_TAG.fullmatch(ref) if slsa else FULL_SHA.fullmatch(ref)
                    ),
                }
            )
    unique_refs = sorted({(item["action"], item["ref"]) for item in raw_entries})
    resolutions: dict[tuple[str, str], dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
        pending = {
            pool.submit(ref_sha, gh, action, ref): (action, ref)
            for action, ref in unique_refs
        }
        for future in concurrent.futures.as_completed(pending):
            key = pending[future]
            try:
                resolutions[key] = future.result()
            except Exception as exc:  # preserve the unresolved evidence
                resolutions[key] = {
                    "resolved_sha": None,
                    "resolution": "BLOCKED",
                    "reason": str(exc),
                }
    entries = [
        {**item, **resolutions[(item["action"], item["ref"])]}
        for item in raw_entries
    ]
    action_snapshot = {
        "generated_at": now(),
        "label": "MEASURED",
        "scope": "canonical a11oy tracked workflows",
        "source_commit": command(["git", "rev-parse", "HEAD"]),
        "entries": entries,
        "summary": {
            "references": len(entries),
            "compliant": sum(1 for entry in entries if entry["pin_compliant"]),
            "noncompliant": sum(1 for entry in entries if not entry["pin_compliant"]),
            "unresolved": sum(1 for entry in entries if not entry["resolved_sha"]),
        },
    }
    identity_snapshot = {
        "generated_at": now(),
        "label": "MEASURED",
        "scope": "canonical a11oy workflow identity declarations",
        "workflows": identity_files,
        "summary": {
            "workflows_with_oidc": sum(
                1 for item in identity_files if item["id_token_write"]
            ),
            "static_credential_name_references": sum(
                len(item["static_credential_names"]) for item in identity_files
            ),
        },
    }
    return action_snapshot, identity_snapshot


def secret_metadata(gh: GitHub, environments: list[dict[str, Any]]) -> dict[str, Any]:
    repo_secrets = gh.get(f"/repos/{ORG}/{REPO}/actions/secrets?per_page=100")
    org_secrets = gh.get(f"/orgs/{ORG}/actions/secrets?per_page=100")
    env_secrets: list[dict[str, Any]] = []
    for environment in environments:
        name = environment.get("name")
        if not name:
            continue
        encoded = urllib.parse.quote(name, safe="")
        response = gh.get(
            f"/repos/{ORG}/{REPO}/environments/{encoded}/secrets?per_page=100"
        )
        env_secrets.append({"environment": name, "metadata": response})
    def redacted(response: Any) -> Any:
        if not isinstance(response, dict) or "secrets" not in response:
            return response
        return {
            "total_count": response.get("total_count"),
            "secrets": [
                {
                    "name_sha256": hashlib.sha256(
                        str(secret.get("name", "")).encode("utf-8")
                    ).hexdigest(),
                    "updated_at": secret.get("updated_at"),
                    "visibility": secret.get("visibility"),
                }
                for secret in response.get("secrets", [])
            ],
        }

    return {
        "generated_at": now(),
        "label": "MEASURED",
        "redaction": "names and timestamps only; secret values are inaccessible and absent",
        "organization": redacted(org_secrets),
        "repository": redacted(repo_secrets),
        "environments": [
            {
                "environment": item["environment"],
                "metadata": redacted(item["metadata"]),
            }
            for item in env_secrets
        ],
    }


def local_lean_baseline() -> dict[str, Any]:
    proof_root = ROOT / "proofs" / "lutar-lean"
    lean_files = sorted(proof_root.rglob("*.lean"))
    theorem_count = 0
    for path in lean_files:
        theorem_count += len(
            re.findall(
                r"(?m)^\s*(?:theorem|lemma)\s+[A-Za-z0-9_'./-]+",
                path.read_text(encoding="utf-8"),
            )
        )
    return {
        "generated_at": now(),
        "label": "MEASURED",
        "scope": "tracked lutar-lean mirror in a11oy",
        "kernel_of_record": KERNEL_REF,
        "lean_toolchain": (proof_root / "lean-toolchain").read_text(
            encoding="utf-8"
        ).strip(),
        "lake_manifest_sha256": hashlib.sha256(
            (proof_root / "lake-manifest.json").read_bytes()
        ).hexdigest(),
        "lean_files": len(lean_files),
        "theorem_or_lemma_declarations": theorem_count,
        "clean_build": {
            "status": "BLOCKED",
            "reason": "inventory is read-only; build receipt is emitted by the formal verification command",
        },
    }


def local_serving_baseline() -> dict[str, Any]:
    candidates = [
        ROOT / "requirements.txt",
        ROOT / "requirements-vsp-otel.txt",
        ROOT / "Dockerfile",
        ROOT / "Containerfile",
    ]
    signals: list[dict[str, Any]] = []
    for path in candidates:
        if not path.exists():
            continue
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if re.search(r"\b(vllm|sglang|cuda|nvidia)\b", line, re.I):
                signals.append(
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "line": line_number,
                        "text": line.strip(),
                    }
                )
    return {
        "generated_at": now(),
        "label": "MEASURED",
        "source_signals": signals,
        "hardware": {
            "status": "BLOCKED",
            "reason": "no authorized identical-GPU staging node is connected to this run",
        },
        "benchmark_baseline": {
            "status": "BLOCKED",
            "reason": "no identical-hardware vLLM/SGLang run has been executed",
        },
    }


def local_observability_baseline() -> dict[str, Any]:
    paths: list[str] = []
    for candidate in (
        ROOT / "vsp_otel",
        ROOT / "infra" / "otel",
        ROOT / "docs" / "OBSERVABILITY_SECURITY.md",
        ROOT / "szl_observability.py",
    ):
        if candidate.exists():
            paths.append(candidate.relative_to(ROOT).as_posix())
    return {
        "generated_at": now(),
        "label": "MEASURED",
        "tracked_surfaces": paths,
        "live_collector": {
            "status": "BLOCKED",
            "reason": "no production collector credentials or endpoint were supplied",
        },
        "content_capture": {
            "status": "UNKNOWN",
            "reason": "production collector configuration is unavailable",
        },
    }


def claim_inventory() -> dict[str, Any]:
    sources = [ROOT / "README.md", ROOT / "docs" / "SERIES_A_DILIGENCE.md"]
    label_pattern = re.compile(
        r"\b(PROVED|MEASURED|MODELED|PLANNED|RETIRED|SAMPLE|ROADMAP|BLOCKED)\b"
    )
    number_pattern = re.compile(r"\b\d+(?:\.\d+)?(?:%|/\d+|x)?\b", re.I)
    rows: list[dict[str, Any]] = []
    for path in sources:
        for line_number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            labels = sorted(set(label_pattern.findall(line)))
            numbers = number_pattern.findall(line)
            if labels or numbers:
                rows.append(
                    {
                        "path": path.relative_to(ROOT).as_posix(),
                        "line": line_number,
                        "labels": labels,
                        "numbers": numbers,
                        "text_sha256": hashlib.sha256(line.encode("utf-8")).hexdigest(),
                    }
                )
    return {
        "generated_at": now(),
        "label": "MEASURED",
        "scope": "automated material-claim candidate scan of README and diligence packet",
        "candidate_lines": rows,
        "limitations": "human semantic review is still required; line text is hashed to avoid duplicating public copy",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    output = args.output.resolve()
    generated_at = now()
    gh = GitHub(github_token())

    organization = gh.get(f"/orgs/{ORG}", required=True)
    repositories_raw = gh.get(
        f"/orgs/{ORG}/repos?type=all&per_page=100", paginate=True, required=True
    )
    repositories = [repository_summary(item) for item in repositories_raw]
    branches = gh.get(
        f"/repos/{ORG}/{REPO}/branches?per_page=100", paginate=True, required=True
    )
    workflows = gh.get(
        f"/repos/{ORG}/{REPO}/actions/workflows?per_page=100", required=True
    )
    releases = gh.get(
        f"/repos/{ORG}/{REPO}/releases?per_page=100", paginate=True
    )
    deployments = gh.get(
        f"/repos/{ORG}/{REPO}/deployments?per_page=100", paginate=True
    )
    pulls = gh.get(
        f"/repos/{ORG}/{REPO}/pulls?state=open&per_page=100", paginate=True
    )
    environments_response = gh.get(f"/repos/{ORG}/{REPO}/environments?per_page=100")
    environments = (
        environments_response.get("environments", [])
        if isinstance(environments_response, dict)
        else []
    )
    owners = gh.get(f"/orgs/{ORG}/members?role=admin&per_page=100", paginate=True)
    org_rulesets = gh.get(
        f"/orgs/{ORG}/rulesets?includes_parents=true&per_page=100", paginate=True
    )
    repo_rulesets = gh.get(
        f"/repos/{ORG}/{REPO}/rulesets?includes_parents=true&per_page=100",
        paginate=True,
    )
    protection = gh.get(f"/repos/{ORG}/{REPO}/branches/main/protection")
    packages = gh.get(
        f"/orgs/{ORG}/packages?package_type=container&visibility=public&per_page=100",
        paginate=True,
    )

    github_estate = {
        "generated_at": generated_at,
        "label": "MEASURED",
        "scope": {
            "organization_repositories": "all visible repositories",
            "canonical_repository_detail": f"{ORG}/{REPO}",
        },
        "organization": {
            field: organization.get(field)
            for field in (
                "id",
                "login",
                "two_factor_requirement_enabled",
                "default_repository_permission",
                "members_can_create_repositories",
            )
        },
        "owners": [
            {"id": item.get("id"), "login": item.get("login")} for item in owners
        ],
        "repositories": repositories,
        "canonical_repository": {
            "branches": summarize_branches(branches),
            "environments": summarize_environments(environments_response),
            "workflows": workflows,
            "releases": summarize_releases(releases),
            "packages": packages,
            "deployments": summarize_deployments(deployments),
            "open_pull_requests": summarize_pulls(pulls),
        },
        "summary": {
            "repositories": len(repositories),
            "active_repositories": sum(
                1 for item in repositories if not item["archived"]
            ),
            "archived_repositories": sum(
                1 for item in repositories if item["archived"]
            ),
            "canonical_branches": len(branches),
            "canonical_open_pull_requests": len(pulls),
            "organization_owners": len(owners),
        },
        "api_errors": gh.errors,
    }
    write_json(output / "github-estate.json", github_estate)
    write_json(
        output / "repository-rulesets.json",
        {
            "generated_at": generated_at,
            "label": "MEASURED",
            "mutation": "none",
            "organization_rulesets": summarize_rulesets(org_rulesets),
            "canonical_repository_rulesets": summarize_rulesets(repo_rulesets),
            "canonical_main_protection": summarize_protection(protection),
        },
    )

    action_pins, identity = workflow_inventory(gh)
    write_json(output / "workflow-action-pins.json", action_pins)
    write_json(output / "identity-and-oidc-estate.json", identity)
    write_json(output / "secrets-inventory-redacted.json", secret_metadata(gh, environments))

    provenance_signals = [
        item
        for item in action_pins["entries"]
        if re.search(r"(attest|slsa|cosign|sbom)", item["action"], re.I)
    ]
    release_assets = []
    if isinstance(releases, list):
        for release in releases:
            for asset in release.get("assets", []):
                if re.search(r"(sbom|attest|provenance|intoto|sha256)", asset["name"], re.I):
                    release_assets.append(
                        {
                            "release": release.get("tag_name"),
                            "name": asset.get("name"),
                            "digest": asset.get("digest"),
                        }
                    )
    write_json(
        output / "provenance-baseline.json",
        {
            "generated_at": generated_at,
            "label": "MEASURED",
            "workflow_signals": provenance_signals,
            "release_assets": release_assets,
            "independent_live_verification": {
                "status": "BLOCKED",
                "reason": "no immutable staging artifact digest was produced by this run",
            },
        },
    )
    write_json(output / "lean-baseline.json", local_lean_baseline())
    write_json(output / "serving-baseline.json", local_serving_baseline())
    write_json(output / "observability-baseline.json", local_observability_baseline())

    deployments_live = {
        "generated_at": generated_at,
        "label": "MEASURED",
        "surfaces": {
            "a11oy_build_info": http_json("https://a-11-oy.com/api/build-info"),
            "a11oy_health": http_json("https://a-11-oy.com/api/a11oy/healthz"),
            "hf_a11oy_build_info": http_json(
                "https://szlholdings-a11oy.hf.space/api/build-info"
            ),
            "hf_killinchu_build_info": http_json(
                "https://szlholdings-killinchu.hf.space/api/build-info"
            ),
        },
    }
    write_json(output / "deployment-identities.json", deployments_live)
    write_json(output / "claim-inventory.json", claim_inventory())
    write_json(
        output / "cloud-estate.json",
        {
            "generated_at": generated_at,
            "label": "BLOCKED",
            "reason": "no cloud account, registry, or cluster credentials were supplied",
            "mutation": "none",
            "known_from_repository": {
                "environments": [
                    environment.get("name") for environment in environments
                ],
                "container_packages": packages,
            },
        },
    )

    risks = [
        {
            "id": "OVT-R1",
            "severity": "P0",
            "owner": "Founder / infrastructure owner",
            "label": "BLOCKED",
            "risk": "Cloud, registry, and cluster identities are not independently inventoried.",
        },
        {
            "id": "OVT-R2",
            "severity": "P0",
            "owner": "Platform engineering",
            "label": "BLOCKED",
            "risk": "No identical-hardware vLLM/SGLang benchmark receipt exists.",
        },
        {
            "id": "OVT-R3",
            "severity": "P0",
            "owner": "Platform engineering",
            "label": "BLOCKED",
            "risk": "No immutable staging artifact was independently verified in this run.",
        },
        {
            "id": "OVT-R4",
            "severity": "P1",
            "owner": "CTO / independent reviewer",
            "label": "PLANNED",
            "risk": "Formal authorization statements require independent English-statement review.",
        },
        {
            "id": "OVT-R5",
            "severity": "P1",
            "owner": "Platform engineering",
            "label": "MEASURED",
            "risk": "Deployment identity endpoints may be absent or incomplete; see deployment-identities.json.",
        },
    ]
    write_json(
        output / "risk-register.json",
        {"generated_at": generated_at, "label": "MEASURED", "risks": risks},
    )

    ledger = f"""<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Operation Verified Throughput estate ledger

Generated at `{generated_at}` by `scripts/operation_verified_throughput_inventory.py`.

| Surface | Label | Evidence |
|---|---|---|
| GitHub organization and canonical repository | MEASURED | `audit/github-estate.json` |
| Rulesets and `main` protection | MEASURED | `audit/repository-rulesets.json`; read-only capture |
| Workflow action references | MEASURED | `audit/workflow-action-pins.json` |
| Workflow identity declarations | MEASURED | `audit/identity-and-oidc-estate.json` |
| Secret metadata | MEASURED | `audit/secrets-inventory-redacted.json`; values absent |
| Tracked Lean mirror | MEASURED | `audit/lean-baseline.json`; clean build recorded separately |
| Serving hardware parity | BLOCKED | No authorized identical-GPU staging node is connected |
| Production collectors | BLOCKED | No production collector access is connected |
| Cloud, registry, and cluster estate | BLOCKED | No production cloud credentials are connected |
| Deployment identity endpoints | MEASURED | `audit/deployment-identities.json`; failures remain failures |
| Production mutation | RETIRED | This inventory performs no production mutation |

Gate 1 is **BLOCKED** until the cloud/cluster estate is inventoried, a production backup is
restored, and every P0 discrepancy is closed or accepted through the approval manifest.
"""
    (output / "ESTATE_LEDGER.md").write_text(ledger, encoding="utf-8")
    print(
        json.dumps(
            {
                "label": "MEASURED",
                "generated_at": generated_at,
                "output": str(output),
                "repositories": len(repositories),
                "canonical_branches": len(branches),
                "open_pull_requests": len(pulls),
                "action_references": action_pins["summary"],
                "api_errors": len(gh.errors),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
