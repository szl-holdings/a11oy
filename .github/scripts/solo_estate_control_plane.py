#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Solo-safe security, issue, and Hugging Face estate control plane.

The controller inventories GitHub security surfaces, deterministically triages
open issues, audits every Hugging Face model/dataset/Space/collection, and
maintains one evidence-bound control issue. It never reads secret values back,
auto-dismisses security alerts, auto-closes issues, weakens repository policy,
or changes Hugging Face visibility/hardware.
"""
from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import hashlib
import io
import json
import math
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

API_VERSION = "2022-11-28"
USER_AGENT = "szl-solo-estate-control-plane/1.0"
SECURITY_ENDPOINTS = {
    "dependabot": "/repos/{repo}/dependabot/alerts?state=open&per_page=100",
    "code_scanning": "/repos/{repo}/code-scanning/alerts?state=open&per_page=100",
    "secret_scanning": "/repos/{repo}/secret-scanning/alerts?state=open&per_page=100",
    "repository_advisories": "/repos/{repo}/security-advisories?per_page=100",
}
SEVERITY_ORDER = {"critical": 4, "high": 3, "medium": 2, "moderate": 2, "low": 1, "warning": 1, "unknown": 0}


class ApiFailure(RuntimeError):
    """An API call failed without exposing response bodies or credentials."""

    def __init__(self, service: str, status: int | None, operation: str) -> None:
        self.service = service
        self.status = status
        self.operation = operation
        super().__init__(f"{service} {operation} failed with HTTP {status or 'UNKNOWN'}")


@dataclasses.dataclass(frozen=True)
class Finding:
    domain: str
    severity: str
    kind: str
    resource: str
    detail: str
    evidence_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value), encoding="utf-8")


def safe_text(value: Any, limit: int = 240) -> str:
    text = "" if value is None else str(value)
    text = re.sub(r"(?i)(authorization:\s*bearer\s+)\S+", r"\1<REDACTED>", text)
    text = re.sub(r"(?i)\bgithub_pat_[A-Za-z0-9_]+\b", "<REDACTED>", text)
    text = re.sub(r"(?i)\bgh[pousr]_[A-Za-z0-9]+\b", "<REDACTED>", text)
    text = re.sub(r"(?i)\bhf_[A-Za-z0-9]{16,}\b", "<REDACTED>", text)
    text = " ".join(text.split())
    return text[:limit]


def enum_value(value: Any) -> Any:
    return getattr(value, "value", value)


def object_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, Mapping):
        return dict(value)
    if hasattr(value, "to_dict"):
        try:
            result = value.to_dict()
            return dict(result) if isinstance(result, Mapping) else {}
        except Exception:
            return {}
    try:
        return dict(value)
    except Exception:
        return {}


def http_json(
    *,
    url: str,
    token: str | None,
    method: str = "GET",
    payload: Mapping[str, Any] | None = None,
    service: str,
) -> tuple[Any, Mapping[str, str]]:
    body = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {
        "Accept": "application/vnd.github+json" if service == "github" else "application/json",
        "User-Agent": USER_AGENT,
    }
    if service == "github":
        headers["X-GitHub-Api-Version"] = API_VERSION
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read()
            response_headers = dict(response.headers.items())
            return (json.loads(raw.decode("utf-8")) if raw else None, response_headers)
    except urllib.error.HTTPError as exc:
        # Never surface the provider response body: security APIs can contain
        # sensitive context and authorization errors can echo request metadata.
        try:
            exc.read()
        except Exception:
            pass
        raise ApiFailure(service, int(exc.code), f"{method} {urllib.parse.urlsplit(url).path}") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ApiFailure(service, None, f"{method} {urllib.parse.urlsplit(url).path}") from exc


def github_pages(path: str, token: str, *, max_pages: int = 50) -> list[Any]:
    results: list[Any] = []
    for page in range(1, max_pages + 1):
        separator = "&" if "?" in path else "?"
        url = f"https://api.github.com{path}{separator}page={page}"
        payload, _ = http_json(url=url, token=token, service="github")
        if payload is None:
            break
        if isinstance(payload, list):
            batch = payload
        elif isinstance(payload, Mapping) and isinstance(payload.get("items"), list):
            batch = list(payload["items"])
        else:
            raise ApiFailure("github", None, f"unexpected pagination shape for {path}")
        results.extend(batch)
        if len(batch) < 100:
            break
    return results


def github_write(
    token: str,
    path: str,
    *,
    method: str,
    payload: Mapping[str, Any],
) -> Any:
    result, _ = http_json(
        url=f"https://api.github.com{path}",
        token=token,
        method=method,
        payload=payload,
        service="github",
    )
    return result


def normalize_security_alert(kind: str, alert: Mapping[str, Any]) -> dict[str, Any]:
    if kind == "dependabot":
        advisory = object_dict(alert.get("security_advisory"))
        dependency = object_dict(alert.get("dependency"))
        package = object_dict(dependency.get("package"))
        severity = str(advisory.get("severity") or "unknown").lower()
        return {
            "kind": kind,
            "number": alert.get("number"),
            "severity": severity,
            "state": alert.get("state"),
            "package": safe_text(package.get("name")),
            "summary": safe_text(advisory.get("summary")),
            "url": alert.get("html_url"),
            "created_at": alert.get("created_at"),
        }
    if kind == "code_scanning":
        rule = object_dict(alert.get("rule"))
        tool = object_dict(alert.get("tool"))
        severity = str(rule.get("security_severity_level") or rule.get("severity") or "unknown").lower()
        return {
            "kind": kind,
            "number": alert.get("number"),
            "severity": severity,
            "state": alert.get("state"),
            "rule": safe_text(rule.get("id") or rule.get("name")),
            "tool": safe_text(tool.get("name")),
            "url": alert.get("html_url"),
            "created_at": alert.get("created_at"),
        }
    if kind == "secret_scanning":
        return {
            "kind": kind,
            "number": alert.get("number"),
            "severity": "critical",
            "state": alert.get("state"),
            "secret_type": safe_text(alert.get("secret_type_display_name") or alert.get("secret_type")),
            "url": alert.get("html_url"),
            "created_at": alert.get("created_at"),
        }
    return {
        "kind": kind,
        "ghsa_id": safe_text(alert.get("ghsa_id")),
        "severity": str(alert.get("severity") or "unknown").lower(),
        "state": alert.get("state"),
        "summary": safe_text(alert.get("summary")),
        "url": alert.get("html_url"),
        "created_at": alert.get("created_at"),
    }


def audit_security(repo: str, token: str, policy: Mapping[str, Any]) -> dict[str, Any]:
    inventory: dict[str, Any] = {}
    terminal: list[dict[str, Any]] = []
    terminal_severities = {
        str(value).lower() for value in policy["security"]["terminal_security_severities"]
    }
    for name, template in SECURITY_ENDPOINTS.items():
        path = template.format(repo=repo)
        try:
            raw = github_pages(path, token)
            alerts = [normalize_security_alert(name, item) for item in raw if isinstance(item, Mapping)]
            inventory[name] = {
                "status": "OBSERVED",
                "count": len(alerts),
                "alerts": alerts,
            }
            for alert in alerts:
                severity = str(alert.get("severity") or "unknown").lower()
                if name == "secret_scanning" or severity in terminal_severities:
                    terminal.append(alert)
        except ApiFailure as exc:
            inventory[name] = {
                "status": "BLOCKED_PERMISSION_OR_PROVIDER",
                "count": None,
                "alerts": [],
                "error": safe_text(exc),
                "http_status": exc.status,
            }
            terminal.append(
                {
                    "kind": name,
                    "severity": "unknown",
                    "state": "BLOCKED",
                    "summary": safe_text(exc),
                }
            )

    control_candidates = {
        "dependabot": [Path(".github/dependabot.yml"), Path(".github/dependabot.yaml")],
        "codeql": list(Path(".github/workflows").glob("*codeql*.yml"))
        + list(Path(".github/workflows").glob("*codeql*.yaml")),
        "secret_scan": list(Path(".github/workflows").glob("*gitleaks*.yml"))
        + list(Path(".github/workflows").glob("*gitleaks*.yaml"))
        + list(Path(".github/workflows").glob("*secret*scan*.yml")),
        "security_policy": [Path("SECURITY.md"), Path(".github/SECURITY.md")],
        "codeowners": [Path("CODEOWNERS"), Path(".github/CODEOWNERS")],
    }
    controls: dict[str, Any] = {}
    missing: list[str] = []
    for name, candidates in control_candidates.items():
        observed = sorted(str(path) for path in candidates if path.exists())
        controls[name] = {"status": "PRESENT" if observed else "MISSING", "paths": observed}
        if not observed:
            missing.append(name)
    for item in missing:
        terminal.append(
            {
                "kind": "repository_control",
                "severity": "high",
                "state": "MISSING",
                "summary": item,
            }
        )

    try:
        branch, _ = http_json(
            url=f"https://api.github.com/repos/{repo}/branches/main/protection",
            token=token,
            service="github",
        )
        controls["main_protection"] = {
            "status": "OBSERVED",
            "required_status_checks": bool(object_dict(branch).get("required_status_checks")),
            "enforce_admins": object_dict(object_dict(branch).get("enforce_admins")).get("enabled"),
            "required_pull_request_reviews": bool(object_dict(branch).get("required_pull_request_reviews")),
        }
    except ApiFailure as exc:
        controls["main_protection"] = {
            "status": "BLOCKED_PERMISSION_OR_PROVIDER",
            "error": safe_text(exc),
            "http_status": exc.status,
        }
        terminal.append(
            {
                "kind": "main_protection",
                "severity": "unknown",
                "state": "BLOCKED",
                "summary": safe_text(exc),
            }
        )

    return {
        "status": "BLOCKED" if terminal else "PASS",
        "inventory": inventory,
        "controls": controls,
        "terminal_findings": terminal,
        "alert_auto_dismissal_performed": False,
        "secret_values_recorded": False,
    }


def classify_issue(issue: Mapping[str, Any], policy: Mapping[str, Any]) -> dict[str, Any]:
    title = safe_text(issue.get("title"), 500)
    body = safe_text(issue.get("body"), 4000)
    haystack = f"{title}\n{body}".lower()
    classifiers = policy["issue_triage"]["classifiers"]

    def matches(group: str) -> bool:
        return any(str(term).lower() in haystack for term in classifiers[group])

    domains: list[str] = []
    if matches("security"):
        domains.append("security")
    if matches("huggingface"):
        domains.append("huggingface")
    if matches("deployment"):
        domains.append("deployment")
    if matches("p0"):
        priority = "p0"
    elif matches("p1") or domains:
        priority = "p1"
    else:
        priority = "p2"
    labels = ["solo-build", f"priority:{priority}"]
    labels.extend(f"domain:{domain}" for domain in domains)
    if domains:
        labels.append("needs:evidence")
    if matches("external"):
        labels.append("blocked:external-authority")
    if matches("major_upgrade"):
        labels.append("upgrade:major")
    return {
        "number": issue.get("number"),
        "title": title,
        "url": issue.get("html_url"),
        "created_at": issue.get("created_at"),
        "updated_at": issue.get("updated_at"),
        "priority": priority.upper(),
        "domains": domains,
        "recommended_labels": sorted(set(labels)),
        "existing_labels": sorted(
            safe_text(object_dict(label).get("name"))
            for label in issue.get("labels") or []
            if object_dict(label).get("name")
        ),
    }


def ensure_labels(repo: str, token: str, policy: Mapping[str, Any]) -> dict[str, Any]:
    observed = github_pages(f"/repos/{repo}/labels?per_page=100", token)
    existing = {
        str(item.get("name")): item for item in observed if isinstance(item, Mapping)
    }
    result: dict[str, Any] = {"created": [], "existing": sorted(existing)}
    for name, spec in policy["issue_triage"]["labels"].items():
        if name in existing:
            continue
        github_write(
            token,
            f"/repos/{repo}/labels",
            method="POST",
            payload={
                "name": name,
                "color": str(spec["color"]),
                "description": str(spec["description"]),
            },
        )
        result["created"].append(name)
    return result


def audit_and_triage_issues(
    repo: str,
    token: str,
    policy: Mapping[str, Any],
    *,
    apply_labels: bool,
) -> dict[str, Any]:
    query = urllib.parse.quote(f"repo:{repo} is:issue is:open")
    issues = github_pages(f"/search/issues?q={query}&per_page=100", token)
    triaged = [classify_issue(issue, policy) for issue in issues if isinstance(issue, Mapping)]
    label_result: dict[str, Any] = {"created": [], "applied": [], "errors": []}
    if apply_labels:
        try:
            label_result.update(ensure_labels(repo, token, policy))
        except ApiFailure as exc:
            label_result["errors"].append(safe_text(exc))
        for item in triaged:
            missing = sorted(set(item["recommended_labels"]) - set(item["existing_labels"]))
            if not missing:
                continue
            try:
                github_write(
                    token,
                    f"/repos/{repo}/issues/{item['number']}/labels",
                    method="POST",
                    payload={"labels": missing},
                )
                label_result["applied"].append(
                    {"number": item["number"], "labels": missing}
                )
            except ApiFailure as exc:
                label_result["errors"].append(
                    f"issue #{item['number']}: {safe_text(exc)}"
                )
    counts = {
        "open": len(triaged),
        "p0": sum(1 for item in triaged if item["priority"] == "P0"),
        "p1": sum(1 for item in triaged if item["priority"] == "P1"),
        "p2": sum(1 for item in triaged if item["priority"] == "P2"),
    }
    return {
        "status": "BLOCKED" if label_result["errors"] else "OBSERVED",
        "counts": counts,
        "issues": triaged,
        "label_mutations": label_result,
        "issues_closed": [],
        "issue_auto_close_performed": False,
    }


def sibling_names(info: Any) -> set[str]:
    names: set[str] = set()
    for sibling in getattr(info, "siblings", None) or []:
        name = getattr(sibling, "rfilename", None)
        if name:
            names.add(str(name))
    return names


def card_headings(text: str) -> list[str]:
    return [
        re.sub(r"[^a-z0-9]+", " ", match.group(1).lower()).strip()
        for match in re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*$", text)
    ]


def markdown_table_columns(line: str) -> int:
    stripped = line.strip()
    if not stripped.startswith("|") or not stripped.endswith("|"):
        return 0
    return max(0, len(stripped.split("|")) - 2)


def audit_card(
    *,
    text: str | None,
    resource_type: str,
    policy: Mapping[str, Any],
    is_kernel: bool,
) -> dict[str, Any]:
    requirements = policy["huggingface"]["required_sections"][
        "kernel" if is_kernel else resource_type
    ]
    if text is None:
        return {
            "present": False,
            "characters": 0,
            "frontmatter": False,
            "headings": [],
            "missing_sections": list(requirements),
            "mobile_risks": ["README.md is missing"],
            "status": "BLOCKED",
        }
    headings = card_headings(text)
    normalized_headings = " | ".join(headings)
    missing_sections = [
        section for section in requirements if section.lower() not in normalized_headings
    ]
    risks: list[str] = []
    max_line = int(policy["huggingface"]["maximum_mobile_line_characters"])
    longest = max((len(line) for line in text.splitlines()), default=0)
    if longest > max_line:
        risks.append(f"line exceeds {max_line} characters")
    if re.search(r"(?i)<(?:img|video|iframe)[^>]+width\s*=\s*['\"]?\d{3,}(?:px)?", text):
        risks.append("fixed-width media markup")
    if re.search(r"(?i)<table(?:\s|>)", text):
        risks.append("raw HTML table may overflow narrow screens")
    max_columns = int(policy["huggingface"]["maximum_markdown_table_columns"])
    if any(markdown_table_columns(line) > max_columns for line in text.splitlines()):
        risks.append(f"Markdown table exceeds {max_columns} columns")
    minimum = int(policy["huggingface"]["minimum_card_characters"])
    if len(text.strip()) < minimum:
        risks.append(f"card is shorter than {minimum} characters")
    frontmatter = text.lstrip().startswith("---\n") or text.lstrip().startswith("---\r\n")
    if not frontmatter:
        risks.append("YAML frontmatter is missing")
    status = "PASS" if not missing_sections and not risks else "POLISH_REQUIRED"
    return {
        "present": True,
        "characters": len(text),
        "frontmatter": frontmatter,
        "headings": headings,
        "missing_sections": missing_sections,
        "mobile_risks": risks,
        "status": status,
    }


def load_hf_readme(repo_id: str, repo_type: str, revision: str | None, token: str | None) -> str | None:
    from huggingface_hub import hf_hub_download

    try:
        path = hf_hub_download(
            repo_id=repo_id,
            repo_type=repo_type,
            filename="README.md",
            revision=revision or "main",
            token=token or None,
        )
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def inferred_kernel(identifier: str, tags: Iterable[Any], policy: Mapping[str, Any]) -> bool:
    haystack = " ".join([identifier, *(str(tag) for tag in tags)]).lower()
    return any(
        str(marker).lower() in haystack
        for marker in policy["huggingface"]["kernel_identifiers"]
    )


def license_value(card: Mapping[str, Any]) -> Any:
    value = card.get("license")
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, list):
        cleaned = [str(item).strip() for item in value if str(item).strip()]
        return cleaned or None
    return value


def safe_missing_card_template(repo_id: str, resource_type: str, sdk: str | None) -> str:
    title = repo_id.split("/", 1)[-1].replace("-", " ").replace("_", " ").title()
    frontmatter = ["---", f"title: {json.dumps(title)}", "tags:", "- szl-holdings", "- governed-ai"]
    if resource_type == "space" and sdk:
        frontmatter.append(f"sdk: {sdk}")
    frontmatter.append("---")
    return "\n".join(frontmatter) + f"""

# {title}

## Overview

This repository is part of the SZL Holdings Hugging Face estate. This baseline
card records discoverable metadata only; it does not claim model quality,
dataset fitness, production readiness, or deployment parity.

## Status

**DISCOVERED — EVIDENCE REQUIRED.** Capability and release status must be bound
to an immutable revision and current verification receipt before promotion.

## Usage

Use only after reviewing the repository files, exact revision, license metadata,
and task-specific limitations.

## Evidence

Authoritative evidence belongs in source-controlled, immutable receipts linked
to the exact resource revision.

## Limitations

No license, benchmark, safety, accuracy, availability, or production guarantee
is inferred by this generated baseline card.
"""


def audit_huggingface(
    org: str,
    token: str | None,
    policy: Mapping[str, Any],
    *,
    apply_safe_cards: bool,
) -> dict[str, Any]:
    try:
        from huggingface_hub import CommitOperationAdd, HfApi
    except Exception as exc:
        return {
            "status": "BLOCKED",
            "error": f"huggingface_hub import failed: {type(exc).__name__}",
            "counts": {},
            "resources": {},
            "findings": [],
            "safe_card_writes": [],
        }

    api = HfApi(token=token or None)
    findings: list[Finding] = []
    writes: list[dict[str, Any]] = []
    resources: dict[str, list[dict[str, Any]]] = {
        "models": [],
        "datasets": [],
        "spaces": [],
        "collections": [],
        "kernels": [],
    }

    try:
        models = list(api.list_models(author=org, full=True, limit=None))
        datasets = list(api.list_datasets(author=org, full=True, limit=None))
        spaces = list(api.list_spaces(author=org, full=True, limit=None))
        collections = list(api.list_collections(owner=org, limit=None))
    except Exception as exc:
        return {
            "status": "BLOCKED",
            "error": f"Hugging Face inventory failed: {type(exc).__name__}",
            "counts": {},
            "resources": resources,
            "findings": [],
            "safe_card_writes": [],
        }

    def audit_repo(info: Any, resource_type: str) -> dict[str, Any]:
        repo_id = str(getattr(info, "id", None) or getattr(info, "repo_id", None) or "")
        sha = str(getattr(info, "sha", None) or "") or None
        tags = [str(tag) for tag in (getattr(info, "tags", None) or [])]
        kernel = inferred_kernel(repo_id, tags, policy)
        card_data = object_dict(getattr(info, "cardData", None))
        readme = load_hf_readme(repo_id, resource_type, sha, token)
        sdk = str(enum_value(getattr(info, "sdk", None)) or "") or None
        runtime_stage: str | None = None
        runtime_error: str | None = None
        if resource_type == "space":
            try:
                runtime = api.get_space_runtime(repo_id)
                runtime_stage = str(enum_value(getattr(runtime, "stage", None)) or "UNKNOWN").split(".")[-1].upper()
            except Exception as exc:
                runtime_error = type(exc).__name__
        card = audit_card(
            text=readme,
            resource_type=resource_type,
            policy=policy,
            is_kernel=kernel,
        )
        license_declared = license_value(card_data)
        pipeline = str(getattr(info, "pipeline_tag", None) or card_data.get("task_categories") or "") or None
        row = {
            "id": repo_id,
            "type": resource_type,
            "sha": sha,
            "private": bool(getattr(info, "private", False)),
            "last_modified": str(getattr(info, "lastModified", None) or getattr(info, "last_modified", None) or "") or None,
            "tags": tags,
            "kernel": kernel,
            "license": license_declared,
            "pipeline_or_task": pipeline,
            "sdk": sdk,
            "runtime_stage": runtime_stage,
            "runtime_error": runtime_error,
            "card": card,
        }
        if not sha or not re.fullmatch(r"[0-9a-f]{40}", sha):
            findings.append(Finding("huggingface", "HIGH", "IMMUTABLE_SHA_UNOBSERVED", repo_id, "A full immutable repository SHA was not observed."))
        if not card["present"]:
            findings.append(Finding("huggingface", "HIGH", "CARD_MISSING", repo_id, "README.md is missing."))
            if apply_safe_cards:
                try:
                    content = safe_missing_card_template(repo_id, resource_type, sdk)
                    api.create_commit(
                        repo_id=repo_id,
                        repo_type=resource_type,
                        operations=[
                            CommitOperationAdd(
                                path_in_repo="README.md",
                                path_or_fileobj=io.BytesIO(content.encode("utf-8")),
                            )
                        ],
                        commit_message="docs: add evidence-bound baseline card",
                    )
                    writes.append(
                        {
                            "id": repo_id,
                            "type": resource_type,
                            "operation": "CREATE_MISSING_README_ONLY",
                            "content_sha256": sha256_text(content),
                        }
                    )
                except Exception as exc:
                    findings.append(Finding("huggingface", "HIGH", "SAFE_CARD_WRITE_FAILED", repo_id, f"Missing-card creation failed: {type(exc).__name__}"))
        elif card["status"] != "PASS":
            findings.append(
                Finding(
                    "huggingface",
                    "MEDIUM",
                    "CARD_POLISH_REQUIRED",
                    repo_id,
                    safe_text(
                        "; ".join(card["missing_sections"] + card["mobile_risks"]),
                        500,
                    ),
                )
            )
        if resource_type in {"model", "dataset"} and not license_declared:
            findings.append(Finding("huggingface", "HIGH", "LICENSE_UNDECLARED", repo_id, "License metadata is absent; the controller will not infer it."))
        if resource_type == "model" and not pipeline:
            findings.append(Finding("huggingface", "MEDIUM", "TASK_METADATA_MISSING", repo_id, "Pipeline/task metadata is absent."))
        if resource_type == "space":
            if not sdk:
                findings.append(Finding("huggingface", "HIGH", "SPACE_SDK_UNOBSERVED", repo_id, "Space SDK metadata is absent."))
            if runtime_error:
                findings.append(Finding("huggingface", "HIGH", "SPACE_RUNTIME_UNOBSERVED", repo_id, f"Runtime metadata failed: {runtime_error}."))
            elif runtime_stage not in set(policy["huggingface"]["runtime_healthy_stages"]):
                findings.append(Finding("huggingface", "HIGH", "SPACE_RUNTIME_NOT_HEALTHY", repo_id, f"Observed runtime stage: {runtime_stage or 'UNKNOWN'}."))
        return row

    for item in models:
        row = audit_repo(item, "model")
        resources["models"].append(row)
        if row["kernel"]:
            resources["kernels"].append(row)
    for item in datasets:
        row = audit_repo(item, "dataset")
        resources["datasets"].append(row)
        if row["kernel"]:
            resources["kernels"].append(row)
    for item in spaces:
        row = audit_repo(item, "space")
        resources["spaces"].append(row)
        if row["kernel"]:
            resources["kernels"].append(row)

    for collection in collections:
        slug = str(getattr(collection, "slug", None) or getattr(collection, "id", None) or "")
        title = str(getattr(collection, "title", None) or "") or None
        items = list(getattr(collection, "items", None) or [])
        row = {
            "id": slug,
            "title": title,
            "private": bool(getattr(collection, "private", False)),
            "last_modified": str(getattr(collection, "lastModified", None) or "") or None,
            "item_count": len(items),
            "kernel": inferred_kernel(slug, [title or ""], policy),
        }
        resources["collections"].append(row)
        if row["kernel"]:
            resources["kernels"].append({**row, "type": "collection"})
        if not title:
            findings.append(Finding("huggingface", "MEDIUM", "COLLECTION_TITLE_MISSING", slug, "Collection title is absent."))
        if not items:
            findings.append(Finding("huggingface", "HIGH", "COLLECTION_EMPTY", slug, "Collection contains no resources."))

    counts = {
        "models": len(resources["models"]),
        "datasets": len(resources["datasets"]),
        "spaces": len(resources["spaces"]),
        "collections": len(resources["collections"]),
        "kernels": len(resources["kernels"]),
        "findings": len(findings),
        "high_findings": sum(1 for finding in findings if finding.severity in {"HIGH", "CRITICAL"}),
        "safe_card_writes": len(writes),
    }
    return {
        "status": "BLOCKED" if counts["high_findings"] else ("POLISH_REQUIRED" if findings else "PASS"),
        "counts": counts,
        "resources": resources,
        "findings": [finding.to_dict() for finding in findings],
        "safe_card_writes": writes,
        "existing_cards_overwritten": False,
        "licenses_inferred": False,
        "visibility_changed": False,
        "hardware_changed": False,
        "resources_deleted": False,
        "secret_values_recorded": False,
    }


def markdown_table(rows: list[list[Any]], headers: list[str]) -> str:
    def cell(value: Any) -> str:
        return safe_text(value, 180).replace("|", "\\|")

    lines = [
        "| " + " | ".join(cell(value) for value in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in rows)
    return "\n".join(lines)


def build_control_issue_body(report: Mapping[str, Any], artifact_hint: str) -> str:
    security = report["github_security"]
    issues = report["issues"]
    hf = report["huggingface"]
    endpoint_rows: list[list[Any]] = []
    for name, item in security["inventory"].items():
        endpoint_rows.append([name, item.get("status"), item.get("count")])
    top_issues = sorted(
        issues["issues"],
        key=lambda item: ({"P0": 0, "P1": 1, "P2": 2}[item["priority"]], item["number"]),
    )[:25]
    top_findings = sorted(
        hf.get("findings", []),
        key=lambda item: (-SEVERITY_ORDER.get(str(item.get("severity", "unknown")).lower(), 0), str(item.get("resource", ""))),
    )[:30]
    body = [
        "<!-- szl-solo-estate-control-plane -->",
        "# Solo estate closure control plane",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Exact source revision: `{report['source_revision']}`",
        f"Overall state: **{report['status']}**",
        "",
        "This issue is the deterministic solo-operator dashboard for security alerts,",
        "open issue triage, and the SZL Holdings Hugging Face estate. It never dismisses",
        "alerts, closes work, weakens protected-main policy, or infers licenses.",
        "",
        "## GitHub security",
        "",
        markdown_table(endpoint_rows, ["Surface", "Readback", "Open"]),
        "",
        f"- Required controls missing: **{sum(1 for value in security['controls'].values() if value.get('status') == 'MISSING')}**",
        f"- Terminal security findings: **{len(security['terminal_findings'])}**",
        "",
        "## Open issue triage",
        "",
        f"- Open issues: **{issues['counts']['open']}**",
        f"- P0: **{issues['counts']['p0']}**",
        f"- P1: **{issues['counts']['p1']}**",
        f"- P2: **{issues['counts']['p2']}**",
        "",
    ]
    if top_issues:
        body.append(
            markdown_table(
                [
                    [f"#{item['number']}", item["priority"], ", ".join(item["domains"]) or "general", item["title"]]
                    for item in top_issues
                ],
                ["Issue", "Priority", "Domain", "Title"],
            )
        )
    else:
        body.append("No open issues were observed.")
    body.extend(
        [
            "",
            "## Hugging Face estate",
            "",
            f"- Models: **{hf.get('counts', {}).get('models', 'UNKNOWN')}**",
            f"- Datasets: **{hf.get('counts', {}).get('datasets', 'UNKNOWN')}**",
            f"- Spaces: **{hf.get('counts', {}).get('spaces', 'UNKNOWN')}**",
            f"- Collections: **{hf.get('counts', {}).get('collections', 'UNKNOWN')}**",
            f"- Kernel-classified resources: **{hf.get('counts', {}).get('kernels', 'UNKNOWN')}**",
            f"- High findings: **{hf.get('counts', {}).get('high_findings', 'UNKNOWN')}**",
            "",
        ]
    )
    if top_findings:
        body.append(
            markdown_table(
                [
                    [item.get("severity"), item.get("kind"), item.get("resource"), item.get("detail")]
                    for item in top_findings
                ],
                ["Severity", "Finding", "Resource", "Detail"],
            )
        )
    else:
        body.append("No Hugging Face findings were observed.")
    body.extend(
        [
            "",
            "## Evidence and closure law",
            "",
            f"- Workflow artifact: `{artifact_hint}`",
            "- Security alerts require current provider readback after remediation.",
            "- Issues require exact-head evidence before closure; no heuristic auto-close is used.",
            "- Missing licenses are blocked for owner/legal selection; the controller never guesses.",
            "- Existing Hugging Face cards are never overwritten automatically.",
            "- Space visibility, hardware, storage, models, datasets, and collections are never deleted or silently mutated.",
            "- Solo operation remains supported through exact-head automation, protected auto-merge/merge queue, and independent automated attestation rather than a mandatory second human.",
            "",
            "## Truth boundary",
            "",
            "`PROVED` means deterministic source validation. `MEASURED` means current API/runtime readback.",
            "Any denied permission or unavailable provider remains `BLOCKED`; it is never counted as green.",
        ]
    )
    return "\n".join(body).strip() + "\n"


def upsert_control_issue(repo: str, token: str, policy: Mapping[str, Any], body: str) -> dict[str, Any]:
    title = str(policy["issue_triage"]["control_issue_title"])
    query = urllib.parse.quote(f'repo:{repo} is:issue in:title "{title}"')
    matches = github_pages(f"/search/issues?q={query}&per_page=100", token)
    exact = next(
        (
            item
            for item in matches
            if isinstance(item, Mapping)
            and item.get("title") == title
            and not item.get("pull_request")
        ),
        None,
    )
    labels = ["solo-build", "priority:p0", "domain:security", "domain:huggingface", "domain:deployment", "needs:evidence"]
    if exact:
        number = int(exact["number"])
        updated = github_write(
            token,
            f"/repos/{repo}/issues/{number}",
            method="PATCH",
            payload={"body": body, "state": "open"},
        )
        github_write(
            token,
            f"/repos/{repo}/issues/{number}/labels",
            method="POST",
            payload={"labels": labels},
        )
        return {"operation": "UPDATED", "number": number, "url": updated.get("html_url")}
    created = github_write(
        token,
        f"/repos/{repo}/issues",
        method="POST",
        payload={"title": title, "body": body, "labels": labels},
    )
    return {"operation": "CREATED", "number": created.get("number"), "url": created.get("html_url")}


def current_revision() -> str | None:
    import subprocess

    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).strip()
        return value if re.fullmatch(r"[0-9a-f]{40}", value) else None
    except Exception:
        return None


def status_from_report(report: Mapping[str, Any]) -> str:
    if report["github_security"]["terminal_findings"]:
        return "BLOCKED_SECURITY"
    if report["issues"]["counts"]["p0"]:
        return "BLOCKED_P0_ISSUES"
    if report["huggingface"].get("status") == "BLOCKED":
        return "BLOCKED_HUGGINGFACE"
    if report["huggingface"].get("status") == "POLISH_REQUIRED":
        return "POLISH_REQUIRED"
    return "PASS"


def self_test(policy: Mapping[str, Any]) -> None:
    issue = {
        "number": 7,
        "title": "Critical Hugging Face production drift",
        "body": "External blocker and breaking change",
        "html_url": "https://example.invalid/7",
        "labels": [],
    }
    classified = classify_issue(issue, policy)
    assert classified["priority"] == "P0"
    assert "domain:huggingface" in classified["recommended_labels"]
    assert "domain:deployment" in classified["recommended_labels"]
    assert "blocked:external-authority" in classified["recommended_labels"]
    assert "upgrade:major" in classified["recommended_labels"]

    card = audit_card(
        text="---\ntags: [test]\n---\n# Demo\n## Overview\n## Status\n## Usage\n## Limitations\n" + "x" * 400,
        resource_type="model",
        policy=policy,
        is_kernel=False,
    )
    assert card["present"] is True
    assert card["missing_sections"] == []
    assert card["status"] == "PASS"

    missing = audit_card(
        text=None,
        resource_type="space",
        policy=policy,
        is_kernel=False,
    )
    assert missing["status"] == "BLOCKED"
    assert "README.md is missing" in missing["mobile_risks"]

    redacted = safe_text("authorization: bearer abc github_pat_abcdefghijklmnopqrstuv hf_abcdefghijklmnopqrstuv")
    assert "abc" not in redacted
    assert "github_pat_" not in redacted
    assert "hf_" not in redacted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", type=Path, default=Path(".github/solo-estate-policy.json"))
    parser.add_argument("--repo", default=os.environ.get("GITHUB_REPOSITORY", "szl-holdings/a11oy"))
    parser.add_argument("--hf-org", default="SZLHOLDINGS")
    parser.add_argument("--output-dir", type=Path, default=Path("reports/solo-estate"))
    parser.add_argument("--apply-labels", action="store_true")
    parser.add_argument("--apply-safe-hf-cards", action="store_true")
    parser.add_argument("--update-control-issue", action="store_true")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    if policy.get("schema") != "szl.solo-estate-policy/v1":
        raise SystemExit("Unsupported solo estate policy schema")
    if args.self_test:
        self_test(policy)
        print("SOLO ESTATE CONTROL PLANE SELF-TEST: PASS")
        return 0

    github_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    hf_token = os.environ.get("HF_TOKEN") or ""
    if not github_token:
        raise SystemExit("GH_TOKEN/GITHUB_TOKEN is required for the live audit")
    revision = current_revision()
    if not revision:
        raise SystemExit("Exact Git source revision could not be observed")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {
        "schema": "szl.solo-estate-report/v1",
        "generated_at": utc_now(),
        "source_revision": revision,
        "repository": args.repo,
        "huggingface_organization": args.hf_org,
        "policy_digest": sha256_text(canonical_json(policy)),
        "github_security": audit_security(args.repo, github_token, policy),
        "issues": audit_and_triage_issues(
            args.repo,
            github_token,
            policy,
            apply_labels=args.apply_labels,
        ),
        "huggingface": audit_huggingface(
            args.hf_org,
            hf_token or None,
            policy,
            apply_safe_cards=args.apply_safe_hf_cards,
        ),
        "mutations": {
            "issue_labels_applied": args.apply_labels,
            "safe_missing_hf_cards_requested": args.apply_safe_hf_cards,
            "security_alerts_dismissed": False,
            "issues_closed": False,
            "existing_hf_cards_overwritten": False,
            "hf_visibility_changed": False,
            "hf_hardware_changed": False,
            "hf_resources_deleted": False,
        },
        "secret_values_recorded": False,
        "administrator_bypass_used": False,
        "force_push_used": False,
    }
    report["status"] = status_from_report(report)

    artifact_hint = f"solo-estate-report-{os.environ.get('GITHUB_RUN_ID', 'local')}-{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    issue_body = build_control_issue_body(report, artifact_hint)
    if args.update_control_issue:
        try:
            # Ensure labels before creating the dashboard even when issue-wide
            # labeling is disabled.
            ensure_labels(args.repo, github_token, policy)
            report["control_issue"] = upsert_control_issue(
                args.repo,
                github_token,
                policy,
                issue_body,
            )
        except ApiFailure as exc:
            report["control_issue"] = {
                "operation": "BLOCKED",
                "error": safe_text(exc),
                "http_status": exc.status,
            }
            report["status"] = "BLOCKED_CONTROL_ISSUE"

    write_json(args.output_dir / "estate-report.json", report)
    write_json(args.output_dir / "issue-triage.json", report["issues"])
    write_json(args.output_dir / "hf-estate.json", report["huggingface"])
    (args.output_dir / "estate-summary.md").write_text(issue_body, encoding="utf-8")
    digest = hashlib.sha256((args.output_dir / "estate-report.json").read_bytes()).hexdigest()
    (args.output_dir / "estate-report.json.sha256").write_text(
        f"{digest}  estate-report.json\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "source_revision": revision,
                "security_terminal_findings": len(report["github_security"]["terminal_findings"]),
                "open_issues": report["issues"]["counts"]["open"],
                "p0_issues": report["issues"]["counts"]["p0"],
                "hf_counts": report["huggingface"].get("counts", {}),
                "receipt_sha256": digest,
            },
            sort_keys=True,
        )
    )
    return 0 if report["status"] in {"PASS", "POLISH_REQUIRED"} else 2


if __name__ == "__main__":
    raise SystemExit(main())
