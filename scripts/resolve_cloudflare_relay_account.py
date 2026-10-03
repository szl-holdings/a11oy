"""Bind the relay deploy to the active Cloudflare account for both owned zones.

Only the validated account ID is written to GITHUB_ENV. API errors, zone
metadata, and the token never enter the workflow log.
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ZONES = ("a-11-oy.com", "a11oy.net")
ACCOUNT_ID = re.compile(r"[0-9a-fA-F]{32}\Z")
MAX_RESPONSE_BYTES = 1_000_000


class AccountResolutionError(ValueError):
    """Cloudflare did not establish one shared active account."""


def account_from_zone(payload: object, expected_name: str) -> str:
    if not isinstance(payload, dict) or payload.get("success") is not True:
        raise AccountResolutionError("Cloudflare zone read was unsuccessful")
    zones = payload.get("result")
    if not isinstance(zones, list) or len(zones) != 1:
        raise AccountResolutionError("Cloudflare zone result was not unique")
    zone = zones[0]
    if (
        not isinstance(zone, dict)
        or zone.get("name") != expected_name
        or zone.get("status") != "active"
    ):
        raise AccountResolutionError(
            "Cloudflare zone identity was not active and exact"
        )
    account = zone.get("account")
    account_id = account.get("id") if isinstance(account, dict) else None
    if not isinstance(account_id, str) or ACCOUNT_ID.fullmatch(account_id) is None:
        raise AccountResolutionError("Cloudflare account ID was malformed")
    return account_id.lower()


def shared_account(payloads: Mapping[str, object]) -> str:
    if set(payloads) != set(ZONES):
        raise AccountResolutionError("Required Cloudflare zone evidence was incomplete")
    accounts = {account_from_zone(payloads[name], name) for name in ZONES}
    if len(accounts) != 1:
        raise AccountResolutionError(
            "Owned Cloudflare zones belong to different accounts"
        )
    return accounts.pop()


def fetch_zone(token: str, name: str) -> object:
    query = urlencode({"name": name, "status": "active", "per_page": 50})
    request = Request(
        f"https://api.cloudflare.com/client/v4/zones?{query}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    with urlopen(request, timeout=15) as response:
        content = response.read(MAX_RESPONSE_BYTES + 1)
    if len(content) > MAX_RESPONSE_BYTES:
        raise AccountResolutionError("Cloudflare zone response exceeded the bound")
    return json.loads(content)


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
    except (AccountResolutionError, OSError, ValueError):
        print(
            "::error::Could not bind the relay to one active Cloudflare account.",
            file=sys.stderr,
        )
        return 1
    print("Cloudflare account identity bound from two active zones.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
