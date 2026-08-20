#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read-only GitHub security, issue, and Hugging Face estate inventory.

Every provider interaction in this module is a read. The only writes are local
evidence files beneath ``--output-dir``. Provider denial, incomplete identity
binding, pagination exhaustion, and runtime readback failures stay BLOCKED.
"""

import argparse
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


API_VERSION = "2022-11-28"
USER_AGENT = "szl-solo-estate-readonly-inventory/1.0"
FULL_SHA = re.compile(r"[0-9a-f]{40}")
REPOSITORY = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")
SECURITY_ENDPOINTS = {
    "dependabot": "/repos/{repo}/dependabot/alerts?state=open&per_page=100",
    "code_scanning": "/repos/{repo}/code-scanning/alerts?state=open&per_page=100",
    "secret_scanning": "/repos/{repo}/secret-scanning/alerts?state=open&per_page=100",
    "repository_advisories": "/repos/{repo}/security-advisories?per_page=100",
}
SEVERITY_ORDER = {
    "critical": 4,
    "high": 3,
    "medium": 2,
    "moderate": 2,
    "low": 1,
    "warning": 1,
    "unknown": 0,
}


class ApiFailure(RuntimeError):
    """A provider read failed without retaining a response body or credential."""

    def __init__(self, service: str, status: int | None, operation: str) -> None:
        self.service = service
        self.status = status
        self.operation = operation
        super().__init__(
            f"{service} read {operation} failed with HTTP {status or 'UNKNOWN'}"
        )


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
    text = re.sub(
        r"(?i)(authorization\s*:\s*bearer\s+)\S+",
        r"\1<REDACTED>",
        text,
    )
    text = re.sub(r"(?i)\bgithub_pat_[A-Za-z0-9_=-]+\b", "<REDACTED>", text)
    text = re.sub(r"(?i)\bgh[pousr]_[A-Za-z0-9_=-]+\b", "<REDACTED>", text)
    text = re.sub(r"(?i)\bhf_[A-Za-z0-9_=-]{16,}\b", "<REDACTED>", text)
    return " ".join(text.split())[:limit]


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


def http_json(*, url: str, token: str, service: str) -> Any:
    """Perform one authenticated GET and discard all provider error bodies."""

    headers = {
        "Accept": (
            "application/vnd.github+json"
            if service == "github"
            else "application/json"
        ),
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT,
    }
    if service == "github":
        headers["X-GitHub-Api-Version"] = API_VERSION
    request = urllib.request.Request(url, method="GET", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            raw = response.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        try:
            exc.read()
        except Exception:
            pass
        raise ApiFailure(
            service,
            int(exc.code),
            urllib.parse.urlsplit(url).path,
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ApiFailure(
            service,
            None,
            urllib.parse.urlsplit(url).path,
        ) from exc


def github_pages(path: str, token: str, *, max_pages: int = 50) -> list[Any]:
    results: list[Any] = []
    for page in range(1, max_pages + 1):
        separator = "&" if "?" in path else "?"
        payload = http_json(
            url=f"https://api.github.com{path}{separator}page={page}",
            token=token,
            service="github",
        )
        if payload is None:
            return results
        if isinstance(payload, list):
            batch = payload
        elif isinstance(payload, Mapping) and isinstance(payload.get("items"), list):
            batch = list(payload["items"])
        else:
            raise ApiFailure("github", None, f"unexpected pagination shape: {path}")
        results.extend(batch)
        if len(batch) < 100:
            return results
    raise ApiFailure("github", None, f"pagination limit reached: {path}")


def current_revision() -> str | None:
    try:
        value = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=10,
        ).strip()
        return value if FULL_SHA.fullmatch(value) else None
    except Exception:
        return None


def audit_source_binding(
    repo: str,
    branch: str,
    token: str,
    local_revision: str | None,
) -> dict[str, Any]:
    if not token:
        return {
            "status": "BLOCKED_CREDENTIAL",
            "branch": branch,
            "local_revision": local_revision,
            "protected_revision": None,
            "exact_match": False,
        }
    if not local_revision or not FULL_SHA.fullmatch(local_revision):
        return {
            "status": "BLOCKED_LOCAL_REVISION",
            "branch": branch,
            "local_revision": local_revision,
            "protected_revision": None,
            "exact_match": False,
        }
    try:
        payload = http_json(
            url=(
                "https://api.github.com/repos/"
                f"{repo}/git/ref/heads/{urllib.parse.quote(branch, safe='')}"
            ),
            token=token,
            service="github",
        )
        protected_revision = safe_text(
            object_dict(object_dict(payload).get("object")).get("sha"),
            40,
        )
        exact = bool(FULL_SHA.fullmatch(protected_revision)) and (
            protected_revision == local_revision
        )
        return {
            "status": "PASS" if exact else "BLOCKED_SOURCE_DRIFT",
            "branch": branch,
            "local_revision": local_revision,
            "protected_revision": protected_revision or None,
            "exact_match": exact,
        }
    except ApiFailure as exc:
        return {
            "status": "BLOCKED_PERMISSION_OR_PROVIDER",
            "branch": branch,
            "local_revision": local_revision,
            "protected_revision": None,
            "exact_match": False,
            "error": safe_text(exc),
            "http_status": exc.status,
        }


def normalize_security_alert(kind: str, alert: Mapping[str, Any]) -> dict[str, Any]:
    if kind == "dependabot":
        advisory = object_dict(alert.get("security_advisory"))
        dependency = object_dict(alert.get("dependency"))
        package = object_dict(dependency.get("package"))
        return {
            "kind": kind,
            "number": alert.get("number"),
            "severity": str(advisory.get("severity") or "unknown").lower(),
            "state": safe_text(alert.get("state")),
            "package": safe_text(package.get("name")),
            "summary": safe_text(advisory.get("summary")),
            "url": safe_text(alert.get("html_url"), 500) or None,
            "created_at": safe_text(alert.get("created_at"), 50) or None,
        }
    if kind == "code_scanning":
        rule = object_dict(alert.get("rule"))
        tool = object_dict(alert.get("tool"))
        return {
            "kind": kind,
            "number": alert.get("number"),
            "severity": str(
                rule.get("security_severity_level")
                or rule.get("severity")
                or "unknown"
            ).lower(),
            "state": safe_text(alert.get("state")),
            "rule": safe_text(rule.get("id") or rule.get("name")),
            "tool": safe_text(tool.get("name")),
            "url": safe_text(alert.get("html_url"), 500) or None,
            "created_at": safe_text(alert.get("created_at"), 50) or None,
        }
    if kind == "secret_scanning":
        return {
            "kind": kind,
            "number": alert.get("number"),
            "severity": "critical",
            "state": safe_text(alert.get("state")),
            "secret_type": safe_text(
                alert.get("secret_type_display_name") or alert.get("secret_type")
            ),
            "url": safe_text(alert.get("html_url"), 500) or None,
            "created_at": safe_text(alert.get("created_at"), 50) or None,
        }
    return {
        "kind": kind,
        "ghsa_id": safe_text(alert.get("ghsa_id")),
        "severity": str(alert.get("severity") or "unknown").lower(),
        "state": safe_text(alert.get("state")),
        "summary": safe_text(alert.get("summary")),
        "url": safe_text(alert.get("html_url"), 500) or None,
        "created_at": safe_text(alert.get("created_at"), 50) or None,
    }


def audit_security(
    repo: str,
    branch: str,
    token: str,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    inventory: dict[str, Any] = {}
    terminal: list[dict[str, Any]] = []
    terminal_severities = {
        str(value).lower()
        for value in policy["security"]["terminal_security_severities"]
    }
    if not token:
        for name in SECURITY_ENDPOINTS:
            blocked = {
                "status": "BLOCKED_CREDENTIAL",
                "count": None,
                "alerts": [],
            }
            inventory[name] = blocked
            terminal.append(
                {
                    "kind": name,
                    "severity": "unknown",
                    "state": "BLOCKED",
                    "summary": "GitHub credential unavailable for security readback.",
                }
            )
    else:
        for name, template in SECURITY_ENDPOINTS.items():
            try:
                raw = github_pages(template.format(repo=repo), token)
                alerts = [
                    normalize_security_alert(name, item)
                    for item in raw
                    if isinstance(item, Mapping)
                ]
                inventory[name] = {
                    "status": "OBSERVED",
                    "count": len(alerts),
                    "alerts": alerts,
                }
                for alert in alerts:
                    severity = str(alert.get("severity") or "unknown").lower()
                    state = str(alert.get("state") or "").lower()
                    if state == "closed":
                        continue
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

    controls: dict[str, Any] = {}
    for name, candidate_values in policy["security"][
        "required_repository_controls"
    ].items():
        candidates = [Path(str(value)) for value in candidate_values]
        observed = sorted(str(path) for path in candidates if path.is_file())
        controls[name] = {
            "status": "PRESENT" if observed else "MISSING",
            "paths": observed,
        }
        if not observed:
            terminal.append(
                {
                    "kind": "repository_control",
                    "severity": "high",
                    "state": "MISSING",
                    "summary": name,
                }
            )

    if not token:
        controls["protected_branch"] = {"status": "BLOCKED_CREDENTIAL"}
    else:
        try:
            protection = object_dict(
                http_json(
                    url=(
                        f"https://api.github.com/repos/{repo}/branches/"
                        f"{urllib.parse.quote(branch, safe='')}/protection"
                    ),
                    token=token,
                    service="github",
                )
            )
            checks = bool(protection.get("required_status_checks"))
            reviews = bool(protection.get("required_pull_request_reviews"))
            admins = bool(
                object_dict(protection.get("enforce_admins")).get("enabled")
            )
            controls["protected_branch"] = {
                "status": "OBSERVED",
                "required_status_checks": checks,
                "required_pull_request_reviews": reviews,
                "enforce_admins": admins,
            }
            for control, enabled in {
                "required_status_checks": checks,
                "required_pull_request_reviews": reviews,
                "enforce_admins": admins,
            }.items():
                if not enabled:
                    terminal.append(
                        {
                            "kind": "protected_branch_control",
                            "severity": "high",
                            "state": "MISSING",
                            "summary": control,
                        }
                    )
        except ApiFailure as exc:
            controls["protected_branch"] = {
                "status": "BLOCKED_PERMISSION_OR_PROVIDER",
                "error": safe_text(exc),
                "http_status": exc.status,
            }
            terminal.append(
                {
                    "kind": "protected_branch",
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
        "provider_mutations_performed": [],
        "secret_values_recorded": False,
    }


def classify_issue(
    issue: Mapping[str, Any], policy: Mapping[str, Any]
) -> dict[str, Any]:
    title = safe_text(issue.get("title"), 500)
    body = safe_text(issue.get("body"), 4000)
    haystack = f"{title}\n{body}".lower()
    classifiers = policy["issue_inventory"]["classifiers"]

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
        priority = "P0"
    elif matches("p1") or domains:
        priority = "P1"
    else:
        priority = "P2"
    signals: list[str] = []
    if matches("external"):
        signals.append("EXTERNAL_AUTHORITY")
    if matches("major_upgrade"):
        signals.append("MAJOR_UPGRADE")
    return {
        "number": issue.get("number"),
        "title": title,
        "url": safe_text(issue.get("html_url"), 500) or None,
        "created_at": safe_text(issue.get("created_at"), 50) or None,
        "updated_at": safe_text(issue.get("updated_at"), 50) or None,
        "priority": priority,
        "domains": domains,
        "signals": signals,
        "observed_labels": sorted(
            safe_text(object_dict(label).get("name"))
            for label in issue.get("labels") or []
            if object_dict(label).get("name")
        ),
    }


def audit_issues(
    repo: str,
    token: str,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    if not token:
        return {
            "status": "BLOCKED_CREDENTIAL",
            "counts": {"open": None, "p0": None, "p1": None, "p2": None},
            "issues": [],
            "provider_mutations_performed": [],
        }
    query = urllib.parse.quote(f"repo:{repo} is:issue is:open")
    try:
        raw = github_pages(
            f"/search/issues?q={query}&per_page=100",
            token,
            max_pages=10,
        )
    except ApiFailure as exc:
        return {
            "status": "BLOCKED_PERMISSION_OR_PROVIDER",
            "counts": {"open": None, "p0": None, "p1": None, "p2": None},
            "issues": [],
            "error": safe_text(exc),
            "http_status": exc.status,
            "provider_mutations_performed": [],
        }
    issues = [
        classify_issue(item, policy) for item in raw if isinstance(item, Mapping)
    ]
    return {
        "status": "OBSERVED",
        "counts": {
            "open": len(issues),
            "p0": sum(item["priority"] == "P0" for item in issues),
            "p1": sum(item["priority"] == "P1" for item in issues),
            "p2": sum(item["priority"] == "P2" for item in issues),
        },
        "issues": issues,
        "provider_mutations_performed": [],
    }


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
    read_error: str | None = None,
) -> dict[str, Any]:
    requirements = policy["huggingface"]["required_sections"][
        "kernel" if is_kernel else resource_type
    ]
    if read_error:
        return {
            "present": None,
            "characters": None,
            "frontmatter": None,
            "headings": [],
            "missing_sections": [],
            "mobile_risks": [],
            "status": "BLOCKED_READBACK",
            "read_error": safe_text(read_error),
        }
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
        section
        for section in requirements
        if section.lower() not in normalized_headings
    ]
    risks: list[str] = []
    max_line = int(policy["huggingface"]["maximum_mobile_line_characters"])
    longest = max((len(line) for line in text.splitlines()), default=0)
    if longest > max_line:
        risks.append(f"line exceeds {max_line} characters")
    if re.search(
        r"(?i)<(?:img|video|iframe)[^>]+width\s*=\s*['\"]?\d{3,}(?:px)?",
        text,
    ):
        risks.append("fixed-width media markup")
    if re.search(r"(?i)<table(?:\s|>)", text):
        risks.append("raw HTML table may overflow narrow screens")
    max_columns = int(policy["huggingface"]["maximum_markdown_table_columns"])
    if any(
        markdown_table_columns(line) > max_columns for line in text.splitlines()
    ):
        risks.append(f"Markdown table exceeds {max_columns} columns")
    minimum = int(policy["huggingface"]["minimum_card_characters"])
    if len(text.strip()) < minimum:
        risks.append(f"card is shorter than {minimum} characters")
    frontmatter = text.lstrip().startswith("---\n") or text.lstrip().startswith(
        "---\r\n"
    )
    if not frontmatter:
        risks.append("YAML frontmatter is missing")
    return {
        "present": True,
        "characters": len(text),
        "frontmatter": frontmatter,
        "headings": headings,
        "missing_sections": missing_sections,
        "mobile_risks": risks,
        "status": "PASS" if not missing_sections and not risks else "POLISH_REQUIRED",
    }


def load_hf_readme(
    repo_id: str,
    repo_type: str,
    revision: str,
    token: str,
) -> tuple[str | None, str | None]:
    from huggingface_hub import hf_hub_download

    try:
        path = hf_hub_download(
            repo_id=repo_id,
            repo_type=repo_type,
            filename="README.md",
            revision=revision,
            token=token,
        )
        return Path(path).read_text(encoding="utf-8", errors="replace"), None
    except Exception as exc:
        error_type = type(exc).__name__
        if error_type in {"EntryNotFoundError", "RemoteEntryNotFoundError"}:
            return None, None
        return None, error_type


def inferred_kernel(
    identifier: str,
    tags: Iterable[Any],
    policy: Mapping[str, Any],
) -> bool:
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
        cleaned = [safe_text(item) for item in value if safe_text(item)]
        return cleaned or None
    return safe_text(value) or None if value is not None else None


def identity_authorizes_org(identity: Mapping[str, Any], org: str) -> bool:
    target = org.casefold()
    if safe_text(identity.get("name")).casefold() == target:
        return True
    for item in identity.get("orgs") or []:
        record = object_dict(item)
        if safe_text(record.get("name") or record.get("displayName")).casefold() == target:
            return True
    return False


def audit_huggingface(
    org: str,
    token: str,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    empty_resources: dict[str, list[dict[str, Any]]] = {
        "models": [],
        "datasets": [],
        "spaces": [],
        "collections": [],
        "kernels": [],
    }
    if not token:
        return {
            "status": "BLOCKED_CREDENTIAL",
            "identity": {"status": "BLOCKED_CREDENTIAL"},
            "counts": {},
            "resources": empty_resources,
            "findings": [],
            "provider_mutations_performed": [],
            "secret_values_recorded": False,
        }
    try:
        from huggingface_hub import HfApi
    except Exception as exc:
        return {
            "status": "BLOCKED_CLIENT",
            "identity": {"status": "NOT_OBSERVED"},
            "error": f"huggingface_hub import failed: {type(exc).__name__}",
            "counts": {},
            "resources": empty_resources,
            "findings": [],
            "provider_mutations_performed": [],
            "secret_values_recorded": False,
        }

    api = HfApi(token=token)
    try:
        identity = object_dict(api.whoami())
    except Exception as exc:
        return {
            "status": "BLOCKED_IDENTITY_READBACK",
            "identity": {
                "status": "BLOCKED_PERMISSION_OR_PROVIDER",
                "error_type": type(exc).__name__,
            },
            "counts": {},
            "resources": empty_resources,
            "findings": [],
            "provider_mutations_performed": [],
            "secret_values_recorded": False,
        }
    identity_name = safe_text(identity.get("name"))
    authorized = identity_authorizes_org(identity, org)
    if policy["huggingface"].get(
        "organization_membership_readback_required", True
    ) and not authorized:
        return {
            "status": "BLOCKED_ORG_AUTHORITY",
            "identity": {
                "status": "OBSERVED_NOT_AUTHORIZED",
                "name": identity_name or None,
                "organization": org,
            },
            "counts": {},
            "resources": empty_resources,
            "findings": [],
            "provider_mutations_performed": [],
            "secret_values_recorded": False,
        }

    resources: dict[str, list[dict[str, Any]]] = {
        "models": [],
        "datasets": [],
        "spaces": [],
        "collections": [],
        "kernels": [],
    }
    findings: list[Finding] = []
    try:
        models = list(api.list_models(author=org, full=True, limit=None))
        datasets = list(api.list_datasets(author=org, full=True, limit=None))
        spaces = list(api.list_spaces(author=org, full=True, limit=None))
        collections = list(api.list_collections(owner=org, limit=None))
    except Exception as exc:
        return {
            "status": "BLOCKED_INVENTORY_READBACK",
            "identity": {
                "status": "AUTHORIZED",
                "name": identity_name or None,
                "organization": org,
            },
            "error": f"Hugging Face inventory failed: {type(exc).__name__}",
            "counts": {},
            "resources": resources,
            "findings": [],
            "provider_mutations_performed": [],
            "secret_values_recorded": False,
        }

    def audit_repo(info: Any, resource_type: str) -> dict[str, Any]:
        repo_id = safe_text(
            getattr(info, "id", None) or getattr(info, "repo_id", None),
            500,
        )
        sha = safe_text(getattr(info, "sha", None), 40) or None
        tags = [safe_text(tag) for tag in (getattr(info, "tags", None) or [])]
        kernel = inferred_kernel(repo_id, tags, policy)
        card_data = object_dict(getattr(info, "cardData", None))
        readme: str | None = None
        read_error: str | None = None
        if sha and FULL_SHA.fullmatch(sha):
            readme, read_error = load_hf_readme(
                repo_id,
                resource_type,
                sha,
                token,
            )
        else:
            read_error = "IMMUTABLE_REVISION_UNAVAILABLE"
        sdk = safe_text(
            enum_value(getattr(info, "sdk", None)) or card_data.get("sdk")
        ) or None
        runtime_stage: str | None = None
        runtime_error: str | None = None
        if resource_type == "space":
            try:
                runtime = api.get_space_runtime(repo_id)
                runtime_stage = safe_text(
                    enum_value(getattr(runtime, "stage", None)) or "UNKNOWN"
                ).split(".")[-1].upper()
            except Exception as exc:
                runtime_error = type(exc).__name__
        card = audit_card(
            text=readme,
            resource_type=resource_type,
            policy=policy,
            is_kernel=kernel,
            read_error=read_error,
        )
        license_declared = license_value(card_data)
        pipeline = safe_text(
            getattr(info, "pipeline_tag", None)
            or card_data.get("task_categories")
        ) or None
        row = {
            "id": repo_id,
            "type": resource_type,
            "sha": sha,
            "private": bool(getattr(info, "private", False)),
            "last_modified": safe_text(
                getattr(info, "lastModified", None)
                or getattr(info, "last_modified", None),
                80,
            )
            or None,
            "tags": tags,
            "kernel": kernel,
            "license": license_declared,
            "pipeline_or_task": pipeline,
            "sdk": sdk,
            "runtime_stage": runtime_stage,
            "runtime_error": runtime_error,
            "card": card,
        }
        if not repo_id:
            findings.append(
                Finding(
                    "huggingface",
                    "HIGH",
                    "RESOURCE_ID_UNOBSERVED",
                    "UNKNOWN",
                    "The inventory item did not expose a repository identifier.",
                )
            )
        if not sha or not FULL_SHA.fullmatch(sha):
            findings.append(
                Finding(
                    "huggingface",
                    "HIGH",
                    "IMMUTABLE_SHA_UNOBSERVED",
                    repo_id or "UNKNOWN",
                    "A full immutable repository SHA was not observed.",
                )
            )
        if read_error and read_error != "IMMUTABLE_REVISION_UNAVAILABLE":
            findings.append(
                Finding(
                    "huggingface",
                    "HIGH",
                    "CARD_READBACK_UNAVAILABLE",
                    repo_id or "UNKNOWN",
                    f"README.md readback failed: {safe_text(read_error)}.",
                )
            )
        elif card["present"] is False:
            findings.append(
                Finding(
                    "huggingface",
                    "HIGH",
                    "CARD_MISSING",
                    repo_id or "UNKNOWN",
                    "README.md is missing.",
                )
            )
        elif card["status"] == "POLISH_REQUIRED":
            findings.append(
                Finding(
                    "huggingface",
                    "MEDIUM",
                    "CARD_POLISH_REQUIRED",
                    repo_id or "UNKNOWN",
                    safe_text(
                        "; ".join(
                            card["missing_sections"] + card["mobile_risks"]
                        ),
                        500,
                    ),
                )
            )
        if resource_type in {"model", "dataset"} and not license_declared:
            findings.append(
                Finding(
                    "huggingface",
                    "HIGH",
                    "LICENSE_UNDECLARED",
                    repo_id or "UNKNOWN",
                    "License metadata is absent; no license is inferred.",
                )
            )
        if resource_type == "model" and not pipeline:
            findings.append(
                Finding(
                    "huggingface",
                    "MEDIUM",
                    "TASK_METADATA_MISSING",
                    repo_id or "UNKNOWN",
                    "Pipeline or task metadata is absent.",
                )
            )
        if resource_type == "space":
            if not sdk:
                findings.append(
                    Finding(
                        "huggingface",
                        "HIGH",
                        "SPACE_SDK_UNOBSERVED",
                        repo_id or "UNKNOWN",
                        "Space SDK metadata is absent.",
                    )
                )
            if runtime_error:
                findings.append(
                    Finding(
                        "huggingface",
                        "HIGH",
                        "SPACE_RUNTIME_UNOBSERVED",
                        repo_id or "UNKNOWN",
                        f"Runtime metadata failed: {runtime_error}.",
                    )
                )
            elif runtime_stage not in set(
                policy["huggingface"]["runtime_healthy_stages"]
            ):
                findings.append(
                    Finding(
                        "huggingface",
                        "HIGH",
                        "SPACE_RUNTIME_NOT_HEALTHY",
                        repo_id or "UNKNOWN",
                        f"Observed runtime stage: {runtime_stage or 'UNKNOWN'}.",
                    )
                )
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
        slug = safe_text(
            getattr(collection, "slug", None) or getattr(collection, "id", None),
            500,
        )
        title = safe_text(getattr(collection, "title", None), 500) or None
        items = list(getattr(collection, "items", None) or [])
        row = {
            "id": slug,
            "title": title,
            "private": bool(getattr(collection, "private", False)),
            "last_modified": safe_text(
                getattr(collection, "lastModified", None), 80
            )
            or None,
            "item_count": len(items),
            "kernel": inferred_kernel(slug, [title or ""], policy),
        }
        resources["collections"].append(row)
        if row["kernel"]:
            resources["kernels"].append({**row, "type": "collection"})
        if not title:
            findings.append(
                Finding(
                    "huggingface",
                    "MEDIUM",
                    "COLLECTION_TITLE_MISSING",
                    slug or "UNKNOWN",
                    "Collection title is absent.",
                )
            )
        if not items:
            findings.append(
                Finding(
                    "huggingface",
                    "HIGH",
                    "COLLECTION_EMPTY",
                    slug or "UNKNOWN",
                    "Collection contains no resources.",
                )
            )

    counts = {
        "models": len(resources["models"]),
        "datasets": len(resources["datasets"]),
        "spaces": len(resources["spaces"]),
        "collections": len(resources["collections"]),
        "kernels": len(resources["kernels"]),
        "findings": len(findings),
        "high_findings": sum(
            finding.severity in {"HIGH", "CRITICAL"} for finding in findings
        ),
    }
    return {
        "status": (
            "BLOCKED"
            if counts["high_findings"]
            else ("POLISH_REQUIRED" if findings else "PASS")
        ),
        "identity": {
            "status": "AUTHORIZED",
            "name": identity_name or None,
            "organization": org,
        },
        "counts": counts,
        "resources": resources,
        "findings": [finding.to_dict() for finding in findings],
        "provider_mutations_performed": [],
        "secret_values_recorded": False,
    }


def markdown_table(rows: list[list[Any]], headers: list[str]) -> str:
    def cell(value: Any) -> str:
        return safe_text(value, 180).replace("|", "\\|")

    lines = [
        "| " + " | ".join(cell(value) for value in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    lines.extend(
        "| " + " | ".join(cell(value) for value in row) + " |" for row in rows
    )
    return "\n".join(lines)


def build_summary(report: Mapping[str, Any], artifact_name: str) -> str:
    security = report["github_security"]
    issues = report["issues"]
    hf = report["huggingface"]
    endpoint_rows = [
        [name, item.get("status"), item.get("count")]
        for name, item in security["inventory"].items()
    ]
    issue_rows: list[list[Any]] = []
    if isinstance(issues.get("issues"), list):
        top_issues = sorted(
            issues["issues"],
            key=lambda item: (
                {"P0": 0, "P1": 1, "P2": 2}.get(item["priority"], 3),
                item.get("number") or 0,
            ),
        )[:25]
        issue_rows = [
            [
                f"#{item['number']}",
                item["priority"],
                ", ".join(item["domains"]) or "general",
                item["title"],
            ]
            for item in top_issues
        ]
    top_findings = sorted(
        hf.get("findings", []),
        key=lambda item: (
            -SEVERITY_ORDER.get(str(item.get("severity", "unknown")).lower(), 0),
            str(item.get("resource", "")),
        ),
    )[:30]
    lines = [
        "# Solo estate read-only inventory",
        "",
        f"Generated: `{report['generated_at']}`",
        f"Exact local source revision: `{report['source_revision']}`",
        f"Protected source binding: **{report['source_binding']['status']}**",
        f"Overall state: **{report['status']}**",
        "",
        "This is a provider readback artifact. It does not mutate issues, reviews,",
        "security alerts, Hugging Face repositories, cards, visibility, or hardware.",
        "",
        "## GitHub security",
        "",
        markdown_table(endpoint_rows, ["Surface", "Readback", "Open"]),
        "",
        f"- Terminal findings: **{len(security['terminal_findings'])}**",
        "",
        "## Open issue inventory",
        "",
        f"- Readback: **{issues['status']}**",
        f"- Open: **{issues.get('counts', {}).get('open', 'UNKNOWN')}**",
        f"- P0: **{issues.get('counts', {}).get('p0', 'UNKNOWN')}**",
        f"- P1: **{issues.get('counts', {}).get('p1', 'UNKNOWN')}**",
        f"- P2: **{issues.get('counts', {}).get('p2', 'UNKNOWN')}**",
        "",
    ]
    lines.append(
        markdown_table(issue_rows, ["Issue", "Priority", "Domain", "Title"])
        if issue_rows
        else "No issue rows were observed."
    )
    lines.extend(
        [
            "",
            "## Hugging Face estate",
            "",
            f"- Readback: **{hf['status']}**",
            f"- Models: **{hf.get('counts', {}).get('models', 'UNKNOWN')}**",
            f"- Datasets: **{hf.get('counts', {}).get('datasets', 'UNKNOWN')}**",
            f"- Spaces: **{hf.get('counts', {}).get('spaces', 'UNKNOWN')}**",
            f"- Collections: **{hf.get('counts', {}).get('collections', 'UNKNOWN')}**",
            f"- Kernel-classified resources: **{hf.get('counts', {}).get('kernels', 'UNKNOWN')}**",
            f"- High findings: **{hf.get('counts', {}).get('high_findings', 'UNKNOWN')}**",
            "",
        ]
    )
    lines.append(
        markdown_table(
            [
                [
                    item.get("severity"),
                    item.get("kind"),
                    item.get("resource"),
                    item.get("detail"),
                ]
                for item in top_findings
            ],
            ["Severity", "Finding", "Resource", "Detail"],
        )
        if top_findings
        else "No Hugging Face findings were observed."
    )
    lines.extend(
        [
            "",
            "## Evidence boundary",
            "",
            f"- Workflow artifact: `{artifact_name}`",
            "- Provider permission denial and unavailable readback remain BLOCKED.",
            "- Missing licenses remain unclassified; no license is inferred.",
            "- No provider mutation method is available to this controller.",
            "- MEASURED applies only to this named, current provider readback.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def status_from_report(report: Mapping[str, Any]) -> str:
    if report["source_binding"]["status"] != "PASS":
        return "BLOCKED_SOURCE_BINDING"
    if report["github_security"]["status"] != "PASS":
        return "BLOCKED_SECURITY"
    if report["issues"]["status"] != "OBSERVED":
        return "BLOCKED_ISSUE_INVENTORY"
    if report["huggingface"]["status"].startswith("BLOCKED"):
        return "BLOCKED_HUGGINGFACE"
    if report["issues"]["counts"]["p0"]:
        return "BLOCKED_P0_ISSUES"
    if report["huggingface"]["status"] == "POLISH_REQUIRED":
        return "POLISH_REQUIRED"
    return "PASS"


def validate_policy(policy: Mapping[str, Any]) -> None:
    if policy.get("schema") != "szl.solo-estate-readonly-policy/v1":
        raise ValueError("Unsupported solo estate read-only policy schema")
    repo = str(policy.get("repository") or "")
    if not REPOSITORY.fullmatch(repo):
        raise ValueError("Policy repository must be an owner/name pair")
    contract = object_dict(policy.get("read_only_contract"))
    if contract.get("provider_mutations_allowed") is not False:
        raise ValueError("Provider mutation authority must be false")
    if contract.get("github_api_methods") != ["GET"]:
        raise ValueError("Only the GitHub GET method may be configured")
    if contract.get("huggingface_mutation_methods_allowed") != []:
        raise ValueError("Hugging Face mutation methods must be empty")
    required_false = [
        "issue_label_mutation_allowed",
        "control_issue_mutation_allowed",
        "review_request_mutation_allowed",
        "missing_card_creation_allowed",
        "alert_dismissal_allowed",
        "resource_visibility_change_allowed",
        "resource_hardware_change_allowed",
        "resource_deletion_allowed",
        "secret_value_readback_allowed",
    ]
    if any(contract.get(name) is not False for name in required_false):
        raise ValueError("Every provider mutation and secret-readback flag must be false")
    if contract.get("exact_protected_head_binding_required") is not True:
        raise ValueError("Exact protected-head binding must remain required")
    if contract.get("permission_denied_is_green") is not False:
        raise ValueError("Permission denial cannot be green")
    if contract.get("provider_failure_is_green") is not False:
        raise ValueError("Provider failure cannot be green")


def self_test(policy: Mapping[str, Any]) -> None:
    validate_policy(policy)
    classified = classify_issue(
        {
            "number": 7,
            "title": "Critical Hugging Face production drift",
            "body": "External blocker and breaking change",
            "html_url": "https://example.invalid/7",
            "labels": [],
        },
        policy,
    )
    assert classified["priority"] == "P0"
    assert classified["domains"] == ["huggingface", "deployment"]
    assert classified["signals"] == ["EXTERNAL_AUTHORITY", "MAJOR_UPGRADE"]
    card = audit_card(
        text=(
            "---\ntags: [test]\n---\n# Demo\n## Overview\n## Status\n"
            "## Usage\n## Limitations\n" + "evidence line\n" * 30
        ),
        resource_type="model",
        policy=policy,
        is_kernel=False,
    )
    assert card["status"] == "PASS"
    blocked = audit_card(
        text=None,
        resource_type="space",
        policy=policy,
        is_kernel=False,
        read_error="ProviderTimeout",
    )
    assert blocked["status"] == "BLOCKED_READBACK"
    redacted = safe_text(
        "authorization: bearer abc123 "
        + "github"
        + "_pat_"
        + "a" * 24
        + " "
        + "hf"
        + "_"
        + "b" * 24
    )
    assert "abc123" not in redacted
    assert "github_pat_" not in redacted
    assert "hf_" not in redacted


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--policy",
        type=Path,
        default=Path(".github/solo-estate-readonly-policy.json"),
    )
    parser.add_argument("--repo")
    parser.add_argument("--hf-org")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/solo-estate-readonly"),
    )
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    policy = json.loads(args.policy.read_text(encoding="utf-8"))
    validate_policy(policy)
    if args.self_test:
        self_test(policy)
        print("SOLO ESTATE READ-ONLY INVENTORY SELF-TEST: PASS")
        return 0

    repo = args.repo or str(policy["repository"])
    org = args.hf_org or str(policy["huggingface_organization"])
    if repo != policy["repository"] or not REPOSITORY.fullmatch(repo):
        raise SystemExit("Runtime repository must match the policy repository")
    if org != policy["huggingface_organization"]:
        raise SystemExit("Runtime Hugging Face organization must match policy")

    github_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
    hf_token = os.environ.get("HF_TOKEN") or ""
    revision = current_revision()
    branch = str(policy["protected_branch"])
    report: dict[str, Any] = {
        "schema": "szl.solo-estate-readonly-report/v1",
        "generated_at": utc_now(),
        "source_revision": revision,
        "repository": repo,
        "protected_branch": branch,
        "huggingface_organization": org,
        "policy_digest": sha256_text(canonical_json(policy)),
        "source_binding": audit_source_binding(
            repo,
            branch,
            github_token,
            revision,
        ),
        "github_security": audit_security(
            repo,
            branch,
            github_token,
            policy,
        ),
        "issues": audit_issues(repo, github_token, policy),
        "huggingface": audit_huggingface(org, hf_token, policy),
        "provider_mutations_performed": [],
        "secret_values_recorded": False,
        "truth_boundary": {
            "source_contract": "PROVED",
            "live_provider_inventory": "MEASURED",
            "production_state": "NOT_CLAIMED",
        },
    }
    report["status"] = status_from_report(report)
    artifact_name = (
        "solo-estate-readonly-report-"
        f"{os.environ.get('GITHUB_RUN_ID', 'local')}-"
        f"{os.environ.get('GITHUB_RUN_ATTEMPT', '1')}"
    )
    summary = build_summary(report, artifact_name)

    write_json(args.output_dir / "estate-report.json", report)
    write_json(args.output_dir / "issue-inventory.json", report["issues"])
    write_json(args.output_dir / "hf-estate.json", report["huggingface"])
    (args.output_dir / "estate-summary.md").write_text(summary, encoding="utf-8")
    digest = hashlib.sha256(
        (args.output_dir / "estate-report.json").read_bytes()
    ).hexdigest()
    (args.output_dir / "estate-report.json.sha256").write_text(
        f"{digest}  estate-report.json\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": report["status"],
                "source_revision": revision,
                "security_terminal_findings": len(
                    report["github_security"]["terminal_findings"]
                ),
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
