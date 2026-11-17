# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read bounded Cloudflare email Worker metadata; never deploy, send mail, or export values."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import tomllib
import urllib.error
import urllib.request

WORKER = "szl-email-sender"
API = "https://api.cloudflare.com/client/v4"
MAX_BODY = 1024 * 1024
NOT_FOUND = object()
REQUIRED = {"MAIL_FROM": "plain_text", "SEND_EMAIL": "send_email", "SOURCE_REVISION": "plain_text"}


class AuditError(Exception):
    pass


def require(condition, code):
    if not condition:
        raise AuditError(code)


def decode(raw):
    def pairs(items):
        value = {}
        for key, item in items:
            require(key not in value, "DUPLICATE_JSON_KEY")
            value[key] = item
        return value

    def nonfinite(_value):
        raise AuditError("NONFINITE_JSON")

    require(0 < len(raw) <= MAX_BODY, "RESPONSE_SIZE_INVALID")
    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise AuditError("RESPONSE_JSON_INVALID") from None
    require(type(value) is dict and value.get("success") is True, "API_RESPONSE_UNSUCCESSFUL")
    return value


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *_args, **_kwargs):
        raise AuditError("API_REDIRECT_REFUSED")


class MetadataClient:
    def __init__(self, token, opener=None):
        require(type(token) is str and bool(token.strip()) and not any(c in token for c in "\r\n\0"),
                "CLOUDFLARE_TOKEN_UNAVAILABLE")
        self.token = token
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.requests = 0

    def get(self, path, *, allow_missing_secret=False):
        permitted = path == "/accounts?page=1&per_page=5" or re.fullmatch(
            r"/accounts/[0-9a-f]{32}/workers/scripts/szl-email-sender/(settings|secrets/API_SECRET)", path)
        require(bool(permitted), "API_TARGET_REFUSED")
        require(not allow_missing_secret or path.endswith("/secrets/API_SECRET"), "NOT_FOUND_SCOPE_REFUSED")
        require(self.requests < 4, "REQUEST_BUDGET_EXCEEDED")
        self.requests += 1
        request = urllib.request.Request(API + path, method="GET", headers={
            "Authorization": "Bearer " + self.token, "Accept": "application/json",
            "Accept-Encoding": "identity", "User-Agent": "a11oy-email-config-audit/1",
        })
        try:
            with self.opener.open(request, timeout=15) as response:
                require(response.headers.get("Content-Encoding", "identity").lower() == "identity",
                        "RESPONSE_ENCODING_REFUSED")
                return decode(response.read(MAX_BODY + 1))
        except urllib.error.HTTPError as error:
            if error.code == 404 and allow_missing_secret:
                return NOT_FOUND
            raise AuditError("API_HTTP_READ_FAILED") from None
        except (OSError, ValueError):
            raise AuditError("API_READ_UNAVAILABLE") from None


def account_id(client, configured):
    if configured:
        require(re.fullmatch(r"[0-9a-fA-F]{32}", configured) is not None, "ACCOUNT_ID_INVALID")
        return configured.lower()
    payload = client.get("/accounts?page=1&per_page=5")
    rows = payload.get("result")
    require(type(rows) is list and len(rows) == 1 and type(rows[0]) is dict, "SINGLE_ACCOUNT_REQUIRED")
    info = payload.get("result_info")
    if info is not None:
        require(type(info) is dict, "ACCOUNT_PAGINATION_INVALID")
        for key, expected in (("per_page", 5), ("count", 1), ("page", 1), ("total_count", 1), ("total_pages", 1)):
            require(key not in info or (type(info[key]) is int and info[key] == expected), "SINGLE_ACCOUNT_REQUIRED")
    value = rows[0].get("id")
    require(type(value) is str and re.fullmatch(r"[0-9a-fA-F]{32}", value) is not None, "ACCOUNT_ID_INVALID")
    return value.lower()


def bindings(payload):
    result = payload.get("result")
    require(type(result) is dict and type(result.get("bindings")) is list, "BINDING_METADATA_UNAVAILABLE")
    require(len(result["bindings"]) <= 1024, "BINDING_COUNT_EXCEEDED")
    found = {}
    for row in result["bindings"]:
        require(type(row) is dict and type(row.get("name")) is str and 0 < len(row["name"]) <= 256,
                "BINDING_METADATA_INVALID")
        require(row["name"] not in found, "DUPLICATE_BINDING")
        found[row["name"]] = row
    return found


def summarize(before, after, secret, expected_revision, expected_sender):
    first = bindings(before)
    current = bindings(after)
    require(before == after, "WORKER_METADATA_CHANGED_DURING_AUDIT")
    checks = {name: current.get(name, {}).get("type") == kind for name, kind in REQUIRED.items()}
    sender_matches = checks["MAIL_FROM"] and current["MAIL_FROM"].get("text") == expected_sender
    revision = current.get("SOURCE_REVISION", {}).get("text")
    revision_valid = checks["SOURCE_REVISION"] and type(revision) is str and re.fullmatch(r"[0-9a-f]{40}", revision) is not None
    revision_matches = bool(revision_valid and revision == expected_revision)
    if secret is NOT_FOUND:
        require("API_SECRET" not in first, "SECRET_METADATA_CONTRADICTION")
        secret_state = "NOT_FOUND"
        secret_type_matches = False
    else:
        result = secret.get("result")
        require(type(result) is dict and result.get("name") == "API_SECRET", "SECRET_METADATA_INVALID")
        secret_type_matches = result.get("type") == "secret_text"
        secret_state = "PRESENT" if secret_type_matches else "UNEXPECTED_TYPE"
        require("API_SECRET" not in first or first["API_SECRET"].get("type") == result.get("type"),
                "SECRET_METADATA_CONTRADICTION")
    consistent = all(checks.values()) and sender_matches and revision_matches and secret_type_matches
    return {
        "status": "METADATA_PRESENT_RUNTIME_UNPROVED" if consistent else "CONFIGURATION_METADATA_BLOCKED",
        "worker": WORKER, "required_binding_type_matches": checks,
        "mail_from_matches_repository": bool(sender_matches),
        "source_revision": expected_revision if revision_matches else None,
        "expected_revision_matches": revision_matches, "api_secret_metadata": secret_state,
        "api_secret_value_exported": False, "api_secret_length_verified": False,
        "runtime_readiness_proved": False, "email_delivery_proved": False,
        "metadata_unchanged_between_reads": True, "provider_mutations": 0,
    }


def audit(client, configured_account, expected_revision, config_path):
    require(type(expected_revision) is str and re.fullmatch(r"[0-9a-f]{40}", expected_revision) is not None,
            "EXPECTED_REVISION_INVALID")
    with config_path.open("rb") as stream:
        raw = stream.read(65537)
    require(len(raw) <= 65536, "REPOSITORY_CONFIG_TOO_LARGE")
    config = tomllib.loads(raw.decode("utf-8"))
    sender = config.get("vars", {}).get("MAIL_FROM")
    require(config.get("name") == WORKER and type(sender) is str
            and re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@a-11-oy\.com", sender) is not None,
            "REPOSITORY_SENDER_CONTRACT_INVALID")
    account = account_id(client, configured_account)
    target = "/accounts/" + account + "/workers/scripts/" + WORKER
    before = client.get(target + "/settings")
    bindings(before)
    secret = client.get(target + "/secrets/API_SECRET", allow_missing_secret=True)
    after = client.get(target + "/settings")
    return summarize(before, after, secret, expected_revision, sender)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expect-revision", required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    client = None
    try:
        client = MetadataClient(os.environ.get("CLOUDFLARE_API_TOKEN", ""))
        report = audit(client, os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""), args.expect_revision,
                       Path(__file__).resolve().parents[1] / "ops/email-sender-worker/wrangler.toml")
    except AuditError as error:
        report = {"status": "AUDIT_UNAVAILABLE", "reason": str(error), "provider_mutations": 0}
    except Exception:
        report = {"status": "AUDIT_UNAVAILABLE", "reason": "BOUNDED_METADATA_AUDIT_FAILED", "provider_mutations": 0}
    report.update(observed_at=datetime.now(timezone.utc).isoformat(), http_get_attempts=client.requests if client else 0)
    encoded = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output:
        try:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
        except OSError:
            print(json.dumps({"status": "AUDIT_UNAVAILABLE", "reason": "EVIDENCE_WRITE_FAILED", "provider_mutations": 0}))
            return 2
    print(encoded, end="")
    return 0 if report["status"] == "METADATA_PRESENT_RUNTIME_UNPROVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
