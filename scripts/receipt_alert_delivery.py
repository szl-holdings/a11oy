#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Deliver receipt alerts through a durable GitHub authority plus optional ntfy.

GitHub Issues is the required delivery path because the workflow already has a
repository-scoped, auditable identity. ntfy is an optional secondary path and is
never allowed to make receipt-alert delivery disappear when its endpoint,
credential, or service is unavailable.

The script records no token or full ntfy topic URL. It fails closed when the
GitHub authority cannot create/update an issue. A configured ntfy failure is
reported as DEGRADED and reconciled into a separate provider incident while the
primary GitHub delivery remains successful.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API = "https://api.github.com"
SCHEMA = "szl.receipt-alert-delivery/v1"
ALERT_TITLE = "[alert] Receipt verification failures"
ALERT_MARKER = "<!-- SZL-RECEIPT-ALERT-V1 -->"
CANARY_TITLE = "[canary] Receipt alert delivery"
CANARY_MARKER = "<!-- SZL-RECEIPT-ALERT-CANARY-V1 -->"
PROVIDER_TITLE = "[provider] ntfy receipt-alert delivery degraded"
PROVIDER_MARKER = "<!-- SZL-NTFY-PROVIDER-INCIDENT-V1 -->"
TOKEN_RE = re.compile(
    r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,}|hf_[A-Za-z0-9]{20,}|Bearer\s+[A-Za-z0-9._~+/=-]{12,})",
    re.IGNORECASE,
)
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
SEVERITIES = {"info", "warning", "error", "critical"}
PRIORITY = {"info": "3", "warning": "4", "error": "5", "critical": "5"}
TAGS = {
    "info": "information_source,receipt",
    "warning": "warning,receipt",
    "error": "rotating_light,receipt",
    "critical": "rotating_light,skull,receipt",
}


class DeliveryError(RuntimeError):
    """Fail-closed delivery error with secret-free text."""


@dataclass
class GitHubDelivery:
    status: str
    action: str
    issue_url: str | None
    issue_number: int | None
    delivery_digest: str


@dataclass
class NtfyDelivery:
    status: str
    configured: bool
    host: str | None
    http_status: int | None
    error: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return TOKEN_RE.sub("[REDACTED]", value)
    if isinstance(value, list):
        return [redact(item) for item in value]
    if isinstance(value, dict):
        return {str(key): redact(item) for key, item in value.items()}
    return value


def delivery_digest(*, severity: str, message: str, source_url: str | None) -> str:
    framed = json.dumps(
        {
            "severity": severity,
            "message": message.strip(),
            "source_url": (source_url or "").strip(),
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(framed).hexdigest()


def validate_repository(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", value):
        raise DeliveryError("GITHUB_REPOSITORY is not an owner/repository identity")
    return value


def validate_severity(value: str) -> str:
    normalized = value.strip().casefold()
    if normalized not in SEVERITIES:
        raise DeliveryError(f"unsupported alert severity: {value!r}")
    return normalized


def validate_message(value: str) -> str:
    normalized = " ".join(value.split()).strip()
    if not normalized:
        raise DeliveryError("alert message is empty")
    if len(normalized) > 4000:
        raise DeliveryError("alert message exceeds the 4000-character contract")
    return normalized


def validate_source_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise DeliveryError("source URL must be credential-free HTTPS")
    return value


def ntfy_identity(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    parsed = urllib.parse.urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise DeliveryError("ntfy topic URL must be credential-free HTTPS")
    if parsed.query or parsed.fragment:
        raise DeliveryError("ntfy topic URL must not contain query or fragment data")
    path = parsed.path.strip("/")
    if not path:
        raise DeliveryError("ntfy topic URL must include a topic path")
    return value.rstrip("/"), parsed.hostname


class GitHubClient:
    def __init__(self, token: str, repository: str) -> None:
        if not token.strip():
            raise DeliveryError("GitHub issue delivery requires GITHUB_TOKEN or GH_TOKEN")
        self.token = token.strip()
        self.repository = validate_repository(repository)
        self.headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Authorization": f"Bearer {self.token}",
            "User-Agent": "a11oy-receipt-alert/1.0",
        }

    def request(
        self,
        method: str,
        path: str,
        payload: Any | None = None,
        *,
        expected: tuple[int, ...] = (200,),
    ) -> Any:
        body = None
        headers = dict(self.headers)
        if payload is not None:
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            API + path,
            data=body,
            method=method,
            headers=headers,
        )
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                raw = response.read()
                value = json.loads(raw) if raw else None
                status = response.status
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:2000]
            raise DeliveryError(
                f"GitHub issue delivery HTTP {exc.code}: {redact(detail)}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise DeliveryError(f"GitHub issue delivery failed: {redact(str(exc))}") from exc
        if status not in expected:
            raise DeliveryError(f"unexpected GitHub status {status} for {method} {path}")
        return value

    def exact_issues(self, title: str, marker: str, *, state: str = "open") -> list[dict[str, Any]]:
        query = f'repo:{self.repository} is:issue is:{state} in:title "{title}"'
        encoded = urllib.parse.quote(query)
        result = self.request("GET", f"/search/issues?q={encoded}&per_page=100")
        rows = result.get("items", []) if isinstance(result, dict) else []
        exact: list[dict[str, Any]] = []
        for row in rows:
            if row.get("title") != title or marker not in str(row.get("body") or ""):
                continue
            exact.append(row)
        return exact

    def create_issue(self, title: str, body: str, labels: list[str] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"title": title, "body": body}
        if labels:
            payload["labels"] = labels
        result = self.request(
            "POST",
            f"/repos/{self.repository}/issues",
            payload,
            expected=(201,),
        )
        if not isinstance(result, dict):
            raise DeliveryError("GitHub issue creation returned a non-object")
        return result

    def comments(self, number: int) -> list[dict[str, Any]]:
        result = self.request(
            "GET", f"/repos/{self.repository}/issues/{number}/comments?per_page=100"
        )
        return result if isinstance(result, list) else []

    def comment(self, number: int, body: str) -> None:
        self.request(
            "POST",
            f"/repos/{self.repository}/issues/{number}/comments",
            {"body": body},
            expected=(201,),
        )

    def close(self, number: int, *, reason: str = "completed") -> None:
        self.request(
            "PATCH",
            f"/repos/{self.repository}/issues/{number}",
            {"state": "closed", "state_reason": reason},
            expected=(200,),
        )

    def reopen(self, number: int) -> None:
        self.request(
            "PATCH",
            f"/repos/{self.repository}/issues/{number}",
            {"state": "open"},
            expected=(200,),
        )


def alert_body(
    *,
    marker: str,
    severity: str,
    message: str,
    source_url: str | None,
    digest: str,
    observed_at: str,
) -> str:
    source = source_url or "UNAVAILABLE"
    return "\n".join(
        (
            marker,
            "## Receipt alert delivery",
            "",
            f"- Severity: `{severity.upper()}`",
            f"- Observed: `{observed_at}`",
            f"- Delivery digest: `{digest}`",
            f"- Source: {source}",
            "",
            message,
            "",
            "This issue is the durable primary alert channel. A configured external relay is secondary and cannot suppress this evidence.",
        )
    )


def deliver_github_alert(
    client: GitHubClient,
    *,
    severity: str,
    message: str,
    source_url: str | None,
    canary: bool,
    observed_at: str,
) -> GitHubDelivery:
    digest = delivery_digest(severity=severity, message=message, source_url=source_url)
    if canary:
        body = alert_body(
            marker=CANARY_MARKER,
            severity=severity,
            message=message,
            source_url=source_url,
            digest=digest,
            observed_at=observed_at,
        )
        created = client.create_issue(CANARY_TITLE, body)
        number = int(created["number"])
        url = str(created.get("html_url") or "")
        client.comment(number, f"{CANARY_MARKER}\nCanary delivery acknowledged; closing the synthetic issue. Digest `{digest}`.")
        client.close(number)
        return GitHubDelivery(
            status="DELIVERED",
            action="CREATED_AND_CLOSED_CANARY",
            issue_url=url,
            issue_number=number,
            delivery_digest=digest,
        )

    body = alert_body(
        marker=ALERT_MARKER,
        severity=severity,
        message=message,
        source_url=source_url,
        digest=digest,
        observed_at=observed_at,
    )
    exact = client.exact_issues(ALERT_TITLE, ALERT_MARKER, state="open")
    if exact:
        canonical = max(exact, key=lambda row: int(row.get("number") or 0))
        number = int(canonical["number"])
        comments = client.comments(number)
        if any(f"`{digest}`" in str(row.get("body") or "") for row in comments):
            action = "DEDUPLICATED"
        else:
            client.comment(number, body)
            action = "COMMENTED"
        return GitHubDelivery(
            status="DELIVERED",
            action=action,
            issue_url=str(canonical.get("html_url") or ""),
            issue_number=number,
            delivery_digest=digest,
        )

    created = client.create_issue(ALERT_TITLE, body)
    return GitHubDelivery(
        status="DELIVERED",
        action="CREATED",
        issue_url=str(created.get("html_url") or ""),
        issue_number=int(created["number"]),
        delivery_digest=digest,
    )


def deliver_ntfy(
    *,
    topic_url: str | None,
    token: str | None,
    severity: str,
    message: str,
    source_url: str | None,
) -> NtfyDelivery:
    validated_url, host = ntfy_identity(topic_url)
    if not validated_url:
        return NtfyDelivery(
            status="UNCONFIGURED",
            configured=False,
            host=None,
            http_status=None,
        )
    text = message if not source_url else f"{message}\nSource: {source_url}"
    headers = {
        "User-Agent": "a11oy-receipt-alert/1.0",
        "Content-Type": "text/plain; charset=utf-8",
        "Title": "A11oy receipt alert",
        "Priority": PRIORITY[severity],
        "Tags": TAGS[severity],
    }
    if token:
        headers["Authorization"] = f"Bearer {token.strip()}"
    request = urllib.request.Request(
        validated_url,
        data=text.encode("utf-8"),
        method="POST",
        headers=headers,
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read(4096)
            status = response.status
    except urllib.error.HTTPError as exc:
        exc.read(4096)
        return NtfyDelivery(
            status="FAILED",
            configured=True,
            host=host,
            http_status=exc.code,
            error=f"ntfy returned HTTP {exc.code}",
        )
    except (urllib.error.URLError, TimeoutError) as exc:
        return NtfyDelivery(
            status="FAILED",
            configured=True,
            host=host,
            http_status=None,
            error=redact(str(exc)),
        )
    if not 200 <= status < 300:
        return NtfyDelivery(
            status="FAILED",
            configured=True,
            host=host,
            http_status=status,
            error=f"ntfy returned HTTP {status}",
        )
    return NtfyDelivery(
        status="DELIVERED",
        configured=True,
        host=host,
        http_status=status,
    )


def reconcile_provider_incident(
    client: GitHubClient,
    *,
    ntfy: NtfyDelivery,
    observed_at: str,
) -> dict[str, Any]:
    open_rows = client.exact_issues(PROVIDER_TITLE, PROVIDER_MARKER, state="open")
    if ntfy.status == "FAILED":
        body = "\n".join(
            (
                PROVIDER_MARKER,
                "## Optional ntfy relay is degraded",
                "",
                f"- Observed: `{observed_at}`",
                f"- Host: `{ntfy.host or 'UNAVAILABLE'}`",
                f"- HTTP status: `{ntfy.http_status if ntfy.http_status is not None else 'UNAVAILABLE'}`",
                f"- Error: `{redact(ntfy.error or 'UNKNOWN')}`",
                "",
                "The required GitHub issue delivery path remains authoritative and operational. No topic URL or token value is recorded here.",
            )
        )
        if open_rows:
            canonical = max(open_rows, key=lambda row: int(row.get("number") or 0))
            client.comment(int(canonical["number"]), body)
            return {"action": "COMMENTED", "issue_url": canonical.get("html_url")}
        created = client.create_issue(PROVIDER_TITLE, body)
        return {"action": "CREATED", "issue_url": created.get("html_url")}

    if ntfy.status == "DELIVERED" and open_rows:
        canonical = max(open_rows, key=lambda row: int(row.get("number") or 0))
        number = int(canonical["number"])
        client.comment(
            number,
            f"{PROVIDER_MARKER}\nntfy delivery recovered at `{observed_at}` with HTTP `{ntfy.http_status}`. Closing the provider-specific incident.",
        )
        client.close(number)
        return {"action": "CLOSED_RECOVERED", "issue_url": canonical.get("html_url")}

    return {"action": "NONE", "issue_url": None}


def write_report(path: Path, payload: dict[str, Any]) -> None:
    safe = redact(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--message", default="Receipt alert delivery canary")
    parser.add_argument("--severity", default="info")
    parser.add_argument("--source-url")
    parser.add_argument("--canary", action="store_true")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args(argv)

    observed_at = utc_now()
    payload: dict[str, Any] = {
        "schema": SCHEMA,
        "observed_at": observed_at,
        "mode": "CANARY" if args.canary else "ALERT",
        "status": "FAIL",
        "token_value_recorded": False,
    }
    try:
        severity = validate_severity(args.severity)
        message = validate_message(args.message)
        source_url = validate_source_url(args.source_url)
        repository = os.environ.get("GITHUB_REPOSITORY", "szl-holdings/a11oy")
        github_token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN") or ""
        client = GitHubClient(github_token, repository)

        github_delivery = deliver_github_alert(
            client,
            severity=severity,
            message=message,
            source_url=source_url,
            canary=args.canary,
            observed_at=observed_at,
        )
        ntfy_delivery = deliver_ntfy(
            topic_url=os.environ.get("NTFY_TOPIC_URL"),
            token=os.environ.get("NTFY_TOKEN"),
            severity=severity,
            message=message,
            source_url=source_url,
        )
        provider = reconcile_provider_incident(
            client,
            ntfy=ntfy_delivery,
            observed_at=observed_at,
        )
        payload.update(
            {
                "status": (
                    "DELIVERED"
                    if ntfy_delivery.status in {"DELIVERED", "UNCONFIGURED"}
                    else "DELIVERED_WITH_SECONDARY_DEGRADATION"
                ),
                "severity": severity,
                "github": asdict(github_delivery),
                "ntfy": asdict(ntfy_delivery),
                "provider_incident": provider,
            }
        )
    except Exception as exc:
        payload["error"] = redact(str(exc))
        write_report(args.report, payload)
        print(json.dumps(payload, indent=2, sort_keys=True), file=sys.stderr)
        return 1

    write_report(args.report, payload)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
