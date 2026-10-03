"""Bind the relay deploy to the active Cloudflare account for both owned zones.

Only the validated account ID is written to GITHUB_ENV. Diagnostics contain
fixed failure categories, a public owned-zone name, and (for HTTP failures)
the status code. API bodies, account IDs, and the token never enter the log.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping
from enum import Enum
from http.client import HTTPException
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ZONES = ("a-11-oy.com", "a11oy.net")
ACCOUNT_ID = re.compile(r"[0-9a-fA-F]{32}\Z")
MAX_RESPONSE_BYTES = 1_000_000


class FailureCategory(str, Enum):
    HTTP_STATUS = "HTTP_STATUS"
    TRANSPORT_ERROR = "TRANSPORT_ERROR"
    RESPONSE_TOO_LARGE = "RESPONSE_TOO_LARGE"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    UNSUCCESSFUL_RESPONSE = "UNSUCCESSFUL_RESPONSE"
    NO_ACTIVE_ZONE = "NO_ACTIVE_ZONE"
    MULTIPLE_ZONES = "MULTIPLE_ZONES"
    MISMATCHED_ZONE = "MISMATCHED_ZONE"
    INACTIVE_ZONE = "INACTIVE_ZONE"
    INVALID_ACCOUNT_ID = "INVALID_ACCOUNT_ID"
    INCOMPLETE_EVIDENCE = "INCOMPLETE_EVIDENCE"
    ACCOUNT_MISMATCH = "ACCOUNT_MISMATCH"


class AccountResolutionError(ValueError):
    """A preflight failure with only allowlisted diagnostic fields."""

    def __init__(
        self,
        category: FailureCategory,
        zone: str | None = None,
        status: int | None = None,
    ) -> None:
        self.category = category
        self.zone = zone if zone in ZONES else None
        self.status = status if type(status) is int and 100 <= status <= 599 else None
        super().__init__(category.value)

    def diagnostic(self) -> str:
        fields = ["::error::Cloudflare relay account preflight failed:"]
        if self.zone is not None:
            fields.append(f"zone={self.zone}")
        fields.append(f"category={self.category.value}")
        if self.status is not None:
            fields.append(f"status={self.status}")
        return " ".join(fields) + "."


def account_from_zone(payload: object, expected_name: str) -> str:
    if not isinstance(payload, dict):
        raise AccountResolutionError(FailureCategory.INVALID_RESPONSE, expected_name)
    if payload.get("success") is not True:
        raise AccountResolutionError(
            FailureCategory.UNSUCCESSFUL_RESPONSE, expected_name
        )
    zones = payload.get("result")
    if not isinstance(zones, list):
        raise AccountResolutionError(FailureCategory.INVALID_RESPONSE, expected_name)
    if not zones:
        raise AccountResolutionError(FailureCategory.NO_ACTIVE_ZONE, expected_name)
    if len(zones) != 1:
        raise AccountResolutionError(FailureCategory.MULTIPLE_ZONES, expected_name)
    zone = zones[0]
    if not isinstance(zone, dict):
        raise AccountResolutionError(FailureCategory.INVALID_RESPONSE, expected_name)
    if zone.get("name") != expected_name:
        raise AccountResolutionError(FailureCategory.MISMATCHED_ZONE, expected_name)
    if zone.get("status") != "active":
        raise AccountResolutionError(FailureCategory.INACTIVE_ZONE, expected_name)
    account = zone.get("account")
    account_id = account.get("id") if isinstance(account, dict) else None
    if not isinstance(account_id, str) or ACCOUNT_ID.fullmatch(account_id) is None:
        raise AccountResolutionError(FailureCategory.INVALID_ACCOUNT_ID, expected_name)
    return account_id.lower()


def shared_account(payloads: Mapping[str, object]) -> str:
    if set(payloads) != set(ZONES):
        raise AccountResolutionError(FailureCategory.INCOMPLETE_EVIDENCE)
    accounts = {account_from_zone(payloads[name], name) for name in ZONES}
    if len(accounts) != 1:
        raise AccountResolutionError(FailureCategory.ACCOUNT_MISMATCH)
    return accounts.pop()


def fetch_zone(token: str, name: str) -> object:
    query = urlencode({"name": name, "status": "active", "per_page": 50})
    try:
        request = Request(
            f"https://api.cloudflare.com/client/v4/zones?{query}",
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        )
        with urlopen(request, timeout=15) as response:
            content = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        raise AccountResolutionError(
            FailureCategory.HTTP_STATUS, name, error.code
        ) from None
    except (HTTPException, OSError, ValueError):
        raise AccountResolutionError(FailureCategory.TRANSPORT_ERROR, name) from None
    if len(content) > MAX_RESPONSE_BYTES:
        raise AccountResolutionError(FailureCategory.RESPONSE_TOO_LARGE, name)
    try:
        return json.loads(content)
    except (UnicodeError, ValueError):
        raise AccountResolutionError(FailureCategory.INVALID_RESPONSE, name) from None


def main() -> int:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "")
    github_env = os.environ.get("GITHUB_ENV", "")
    if not token or not github_env:
        print("::error::Cloudflare deploy inputs are unavailable.", file=sys.stderr)
        return 1
    try:
        account_id = shared_account({name: fetch_zone(token, name) for name in ZONES})
        with Path(github_env).open("a", encoding="utf-8") as output:
            output.write(f"CLOUDFLARE_ACCOUNT_ID={account_id}\n")
    except AccountResolutionError as error:
        print(error.diagnostic(), file=sys.stderr)
        return 1
    except (OSError, ValueError):
        print(
            "::error::Cloudflare relay account preflight failed: category=ENV_WRITE_ERROR.",
            file=sys.stderr,
        )
        return 1
    print("Cloudflare account identity bound from two active zones.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
