#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Produce a secret-safe GitHub private-alert posture receipt.

Only aggregate counts and permission/availability states are persisted. Raw alert
objects are held in memory long enough to count them and are never logged,
serialized, uploaded, or copied into issues. No alert is dismissed or resolved.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping

API_ROOT = "https://api.github.com"
SCHEMA = "szl.private-security-posture/v1"
ISSUE_TITLE = "[security] Private alert posture requires attention"
ISSUE_MARKER = "<!-- SZL-PRIVATE-SECURITY-POSTURE-V1 -->"
SEVERITIES = ("critical", "high", "medium", "low", "warning", "note", "unknown")
TOKEN_PATTERN = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|"
    r"hf_[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._~+/-]{20,})"
)
FORBIDDEN_PUBLIC_KEYS = frozenset(
    {
        "url",
        "html_url",
        "api_url",
        "path",
        "location",
        "locations",
        "secret_type",
        "secret",
        "token",
        "value",
        "description",
        "rule",
        "security_advisory",
        "dependency",
        "package",
        "manifest_path",
        "most_recent_instance",
        "instances_url",
    }
)
SECURITY_WORKFLOW = re.compile(
    r"(?:codeql|gitleaks|trivy|grype|dependency[- ]review|sbom|provenance|"
    r"container|secret[- ]scanning|security)",
    re.IGNORECASE,
)
SHA40 = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


class PostureError(RuntimeError):
    """Fail-closed posture error without raw API response content."""

    def __init__(self, code: str, *, status: int | None = None) -> None:
        super().__init__(code)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class FamilySpec:
    name: str
    endpoint: str
    severity_kind: str


FAMILIES = (
    FamilySpec("dependabot", "dependabot/alerts", "dependabot"),
    FamilySpec("code_scanning", "code-scanning/alerts", "code_scanning"),
    FamilySpec("secret_scanning", "secret-scanning/alerts", "none"),
)


SECURITY_TOKEN_ENV_NAMES = (
    "SZL_SECURITY_TOKEN",
    "SZL_SECURITY_TOKEN_1",
    "SZL_SECURITY_TOKEN_2",
    "SZL_SECURITY_TOKEN_3",
    "SZL_SECURITY_TOKEN_4",
    "SZL_SECURITY_TOKEN_5",
    "SZL_SECURITY_TOKEN_6",
    "GITHUB_TOKEN",
)


def security_token_candidates(
    environ: Mapping[str, str] | None = None,
) -> list[str]:
    """Return distinct nonempty credentials in declared priority order.

    Credentials and source names remain process-local and are never added to
    receipts, logs, issues, or artifacts. Digest-based deduplication prevents
    retrying aliases that resolve to the same underlying token.
    """
    source = os.environ if environ is None else environ
    tokens: list[str] = []
    fingerprints: set[bytes] = set()
    for name in SECURITY_TOKEN_ENV_NAMES:
        token = str(source.get(name) or "").strip()
        if not token:
            continue
        fingerprint = hashlib.sha256(token.encode("utf-8")).digest()
        if fingerprint in fingerprints:
            continue
        fingerprints.add(fingerprint)
        tokens.append(token)
    return tokens


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode(
        "utf-8"
    )


def digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def normalize_severity(value: Any) -> str:
    severity = str(value or "unknown").strip().lower()
    aliases = {"error": "high", "recommendation": "low"}
    severity = aliases.get(severity, severity)
    return severity if severity in SEVERITIES else "unknown"


def alert_severity(row: Mapping[str, Any], kind: str) -> str:
    if kind == "dependabot":
        advisory = row.get("security_advisory")
        value = advisory.get("severity") if isinstance(advisory, Mapping) else None
        return normalize_severity(value)
    if kind == "code_scanning":
        rule = row.get("rule")
        if not isinstance(rule, Mapping):
            return "unknown"
        return normalize_severity(rule.get("security_severity_level") or rule.get("severity"))
    return "unknown"


def public_receipt_errors(value: Any, *, path: str = "$") -> list[str]:
    """Return public-boundary violations without echoing their values."""
    errors: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            text = str(key)
            if text.lower() in FORBIDDEN_PUBLIC_KEYS:
                errors.append(f"forbidden key at {path}.{text}")
            errors.extend(public_receipt_errors(item, path=f"{path}.{text}"))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            errors.extend(public_receipt_errors(item, path=f"{path}[{index}]"))
    elif isinstance(value, str) and TOKEN_PATTERN.search(value):
        errors.append(f"credential-shaped value at {path}")
    return errors


class GitHubClient:
    def __init__(self, token: str) -> None:
        token = token.strip()
        if not token:
            raise PostureError("TOKEN_UNAVAILABLE")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "szl-private-security-posture/1",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def request(
        self,
        method: str,
        path: str,
        payload: Mapping[str, Any] | None = None,
        *,
        expected: Iterable[int] = (200,),
    ) -> tuple[Any, Mapping[str, str], int]:
        url = path if path.startswith("https://") else API_ROOT + path
        data = canonical_json(payload) if payload is not None else None
        headers = dict(self.headers)
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                body = response.read()
                value = json.loads(body) if body else None
                status = response.status
                response_headers = dict(response.headers.items())
        except urllib.error.HTTPError as exc:
            # Never read or persist the body; a private-alert payload may be in it.
            raise PostureError(f"HTTP_{exc.code}", status=exc.code) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise PostureError(type(exc).__name__.upper()) from exc
        if status not in set(expected):
            raise PostureError(f"UNEXPECTED_HTTP_{status}", status=status)
        return value, response_headers, status

    def paged_arrays(self, path: str, *, max_pages: int = 100) -> Iterable[list[dict[str, Any]]]:
        page = 1
        while page <= max_pages:
            separator = "&" if "?" in path else "?"
            value, _headers, _status = self.request(
                "GET", f"{path}{separator}per_page=100&page={page}"
            )
            if not isinstance(value, list):
                raise PostureError("NON_ARRAY_RESPONSE")
            rows = [item for item in value if isinstance(item, dict)]
            yield rows
            if len(value) < 100:
                return
            page += 1
        raise PostureError("PAGINATION_BOUND_EXCEEDED")


def collect_family(client: Any, repository: str, spec: FamilySpec) -> dict[str, Any]:
    severity = {name: 0 for name in SEVERITIES}
    count = 0
    pages = 0
    endpoint = f"/repos/{repository}/{spec.endpoint}?state=open"
    try:
        for batch in client.paged_arrays(endpoint):
            pages += 1
            for row in batch:
                count += 1
                severity[alert_severity(row, spec.severity_kind)] += 1
    except PostureError as exc:
        return {
            "status": "UNAVAILABLE",
            "reason": exc.code,
            "http_status": exc.status,
            "open_count": None,
            "severity": None,
            "pages_observed": pages,
        }
    return {
        "status": "OBSERVED",
        "reason": None,
        "http_status": 200,
        "open_count": count,
        "severity": severity,
        "pages_observed": pages,
    }


def collect_repository_features(client: GitHubClient, repository: str) -> dict[str, Any]:
    try:
        value, _headers, _status = client.request("GET", f"/repos/{repository}")
        if not isinstance(value, Mapping):
            raise PostureError("NON_OBJECT_RESPONSE")
        security = value.get("security_and_analysis")
        if not isinstance(security, Mapping):
            return {"status": "UNAVAILABLE", "reason": "FIELD_UNAVAILABLE", "features": {}}
        features: dict[str, str] = {}
        for name, row in sorted(security.items()):
            if isinstance(row, Mapping):
                status = str(row.get("status") or "unknown").lower()
                features[str(name)] = status
        return {"status": "OBSERVED", "reason": None, "features": features}
    except PostureError as exc:
        return {"status": "UNAVAILABLE", "reason": exc.code, "features": {}}


def collect_governance(client: GitHubClient, repository: str, default_branch: str) -> dict[str, Any]:
    branch: dict[str, Any]
    try:
        protection, _headers, _status = client.request(
            "GET", f"/repos/{repository}/branches/{urllib.parse.quote(default_branch)}/protection"
        )
        required = protection.get("required_status_checks") if isinstance(protection, Mapping) else None
        contexts = required.get("contexts") if isinstance(required, Mapping) else []
        reviews = protection.get("required_pull_request_reviews") if isinstance(protection, Mapping) else None
        branch = {
            "status": "OBSERVED",
            "required_check_count": len(contexts) if isinstance(contexts, list) else 0,
            "required_reviews": (
                int(reviews.get("required_approving_review_count") or 0)
                if isinstance(reviews, Mapping)
                else 0
            ),
        }
    except PostureError as exc:
        branch = {"status": "UNAVAILABLE", "reason": exc.code}

    try:
        rulesets, _headers, _status = client.request(
            "GET", f"/repos/{repository}/rulesets?includes_parents=true"
        )
        if not isinstance(rulesets, list):
            raise PostureError("NON_ARRAY_RESPONSE")
        identities = []
        for row in rulesets:
            if not isinstance(row, Mapping):
                continue
            identities.append(
                {
                    "id": int(row.get("id")) if str(row.get("id") or "").isdigit() else None,
                    "name": str(row.get("name") or ""),
                    "enforcement": str(row.get("enforcement") or "unknown"),
                    "target": str(row.get("target") or "unknown"),
                    "source_type": str(row.get("source_type") or "unknown"),
                }
            )
        normalized = sorted(identities, key=lambda item: (item["name"], item["id"] or 0))
        ruleset = {
            "status": "OBSERVED",
            "count": len(normalized),
            "identity_digest": digest(normalized),
        }
    except PostureError as exc:
        ruleset = {"status": "UNAVAILABLE", "reason": exc.code, "count": None}

    return {"default_branch": default_branch, "branch_protection": branch, "rulesets": ruleset}


def collect_workflow_evidence(client: GitHubClient, repository: str) -> dict[str, Any]:
    try:
        value, _headers, _status = client.request(
            "GET", f"/repos/{repository}/actions/runs?status=success&per_page=100"
        )
        runs = value.get("workflow_runs") if isinstance(value, Mapping) else None
        if not isinstance(runs, list):
            raise PostureError("NON_ARRAY_RESPONSE")
    except PostureError as exc:
        return {"status": "UNAVAILABLE", "reason": exc.code, "latest_success": []}

    latest: dict[str, dict[str, Any]] = {}
    for row in runs:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or "")
        if not name or not SECURITY_WORKFLOW.search(name) or name in latest:
            continue
        head_sha = str(row.get("head_sha") or "").lower()
        latest[name] = {
            "name": name,
            "run_id": int(row.get("id")) if str(row.get("id") or "").isdigit() else None,
            "conclusion": str(row.get("conclusion") or "unknown"),
            "head_sha": head_sha if SHA40.fullmatch(head_sha) else None,
            "created_at": str(row.get("created_at") or ""),
        }
    return {
        "status": "OBSERVED",
        "reason": None,
        "latest_success": [latest[name] for name in sorted(latest)],
    }



def collect_family_with_fallback(
    clients: Iterable[Any], repository: str, spec: FamilySpec
) -> dict[str, Any]:
    """Use the first credential that can observe this alert family."""
    fallback: dict[str, Any] = {
        "status": "UNAVAILABLE",
        "reason": "TOKEN_UNAVAILABLE",
        "http_status": None,
        "open_count": None,
        "severity": None,
        "pages_observed": 0,
    }
    for client in clients:
        result = collect_family(client, repository, spec)
        fallback = result
        if result.get("status") == "OBSERVED":
            return result
    return fallback


def collect_status_with_fallback(
    clients: Iterable[Any], collector: Any, *args: Any
) -> dict[str, Any]:
    """Retry a status collector without exposing credential identity."""
    fallback: dict[str, Any] = {
        "status": "UNAVAILABLE",
        "reason": "TOKEN_UNAVAILABLE",
    }
    for client in clients:
        result = collector(client, *args)
        fallback = result
        if result.get("status") == "OBSERVED":
            return result
    return fallback


def collect_governance_with_fallback(
    clients: Iterable[Any], repository: str, default_branch: str
) -> dict[str, Any]:
    """Merge independently observable governance families across credentials."""
    branch: dict[str, Any] = {
        "status": "UNAVAILABLE",
        "reason": "TOKEN_UNAVAILABLE",
    }
    rulesets: dict[str, Any] = {
        "status": "UNAVAILABLE",
        "reason": "TOKEN_UNAVAILABLE",
        "count": None,
    }
    for client in clients:
        result = collect_governance(client, repository, default_branch)
        candidate_branch = result.get("branch_protection")
        if (
            branch.get("status") != "OBSERVED"
            and isinstance(candidate_branch, Mapping)
        ):
            branch = dict(candidate_branch)
        candidate_rulesets = result.get("rulesets")
        if (
            rulesets.get("status") != "OBSERVED"
            and isinstance(candidate_rulesets, Mapping)
        ):
            rulesets = dict(candidate_rulesets)
        if (
            branch.get("status") == "OBSERVED"
            and rulesets.get("status") == "OBSERVED"
        ):
            break
    return {
        "default_branch": default_branch,
        "branch_protection": branch,
        "rulesets": rulesets,
    }


def build_receipt(
    *,
    repository: str,
    revision: str,
    default_branch: str,
    families: Mapping[str, Any],
    features: Mapping[str, Any],
    governance: Mapping[str, Any],
    workflows: Mapping[str, Any],
    observed_at: str | None = None,
) -> dict[str, Any]:
    unavailable = sorted(
        name for name, value in families.items() if value.get("status") != "OBSERVED"
    )
    open_total = sum(
        int(value.get("open_count") or 0)
        for value in families.values()
        if value.get("status") == "OBSERVED"
    )
    high_critical = sum(
        int((value.get("severity") or {}).get(level) or 0)
        for value in families.values()
        if value.get("status") == "OBSERVED"
        for level in ("critical", "high")
    )
    stable = {
        "schema": SCHEMA,
        "source_repository": repository,
        "source_revision": revision,
        "default_branch": default_branch,
        "families": families,
        "security_and_analysis": features,
        "governance": governance,
        "workflow_evidence": workflows,
        "attention": {
            "required": bool(unavailable or open_total),
            "unavailable_families": unavailable,
            "open_total": open_total,
            "high_critical_total": high_critical,
        },
        "privacy": {
            "raw_alerts_persisted": False,
            "alert_urls_persisted": False,
            "paths_persisted": False,
            "secret_types_persisted": False,
            "automatic_dismissal": False,
        },
    }
    receipt = dict(stable)
    receipt["observed_at"] = observed_at or utc_now()
    receipt["summary_digest"] = digest(stable)
    errors = public_receipt_errors(receipt)
    if errors:
        raise PostureError("PUBLIC_BOUNDARY_VIOLATION")
    return receipt


def render_issue(receipt: Mapping[str, Any]) -> str:
    families = receipt["families"]
    lines = [
        ISSUE_MARKER,
        "# Private security posture requires attention",
        "",
        f"- Source revision: `{receipt['source_revision']}`",
        f"- Observed: `{receipt['observed_at']}`",
        f"- Redacted summary digest: `{receipt['summary_digest']}`",
        "",
        "| Family | Visibility | Open count | Critical | High |",
        "|---|---:|---:|---:|---:|",
    ]
    for name in sorted(families):
        row = families[name]
        severity = row.get("severity") or {}
        count = row.get("open_count")
        lines.append(
            f"| `{name}` | {row.get('status')} | "
            f"{count if count is not None else 'UNAVAILABLE'} | "
            f"{severity.get('critical', '—')} | {severity.get('high', '—')} |"
        )
    attention = receipt["attention"]
    if attention["unavailable_families"]:
        lines.extend(
            [
                "",
                "Unobservable families: "
                + ", ".join(f"`{name}`" for name in attention["unavailable_families"]),
            ]
        )
    lines.extend(
        [
            "",
            "This public issue intentionally contains aggregate counts only. Raw alert data, "
            "secret types, locations, paths, advisory details, and alert URLs remain inside "
            "GitHub Security. No alert is automatically dismissed.",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def find_posture_issue(client: GitHubClient, repository: str) -> dict[str, Any] | None:
    for page in client.paged_arrays(f"/repos/{repository}/issues?state=all"):
        for row in page:
            if row.get("pull_request"):
                continue
            if ISSUE_MARKER in str(row.get("body") or ""):
                return row
    return None


def synchronize_issue(client: GitHubClient, repository: str, receipt: Mapping[str, Any]) -> str:
    issue = find_posture_issue(client, repository)
    required = bool(receipt["attention"]["required"])
    if issue is None and not required:
        return "NOT_REQUIRED"
    body = render_issue(receipt)
    if issue is None:
        client.request(
            "POST",
            f"/repos/{repository}/issues",
            {"title": ISSUE_TITLE, "body": body, "labels": ["security", "automated"]},
            expected=(201,),
        )
        return "CREATED"
    number = int(issue["number"])
    state = str(issue.get("state") or "open")
    desired = "open" if required else "closed"
    client.request(
        "PATCH",
        f"/repos/{repository}/issues/{number}",
        {"title": ISSUE_TITLE, "body": body, "state": desired},
        expected=(200,),
    )
    if state == desired:
        return "UPDATED"
    return "REOPENED" if desired == "open" else "CLOSED"


def write_report(path: str, receipt: Mapping[str, Any]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", default=os.environ.get("GITHUB_REPOSITORY", ""))
    parser.add_argument("--revision", default=os.environ.get("GITHUB_SHA", ""))
    parser.add_argument("--default-branch", default="main")
    parser.add_argument("--report", required=True)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    repository = str(args.repository).strip()
    revision = str(args.revision).strip().lower()
    if REPOSITORY.fullmatch(repository) is None:
        raise SystemExit("invalid repository")
    if SHA40.fullmatch(revision) is None:
        raise SystemExit("revision must be an exact 40-character Git SHA")

    tokens = security_token_candidates()
    if not tokens:
        raise SystemExit("security posture credential unavailable")
    clients = [GitHubClient(token) for token in tokens]
    family_results = {
        spec.name: collect_family_with_fallback(clients, repository, spec)
        for spec in FAMILIES
    }
    receipt = build_receipt(
        repository=repository,
        revision=revision,
        default_branch=args.default_branch,
        families=family_results,
        features=collect_status_with_fallback(
            clients, collect_repository_features, repository
        ),
        governance=collect_governance_with_fallback(
            clients, repository, args.default_branch
        ),
        workflows=collect_status_with_fallback(
            clients, collect_workflow_evidence, repository
        ),
    )
    if args.apply:
        issue_token = os.environ.get("SZL_SECURITY_TOKEN_5") or tokens[-1]
        receipt["incident_action"] = synchronize_issue(
            GitHubClient(issue_token), repository, receipt
        )
    else:
        receipt["incident_action"] = "DRY_RUN"
    errors = public_receipt_errors(receipt)
    if errors:
        raise SystemExit("public receipt boundary failed")
    write_report(args.report, receipt)
    print(
        json.dumps(
            {
                "schema": receipt["schema"],
                "source_revision": receipt["source_revision"],
                "summary_digest": receipt["summary_digest"],
                "attention": receipt["attention"],
                "incident_action": receipt["incident_action"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
