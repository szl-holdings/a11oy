#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Observe one fixed Cloudflare ingress profile; never modify provider state.

The artifact is unsigned configuration evidence, not an access/security verdict.
Cloudflare schemas:
https://developers.cloudflare.com/api/resources/zero_trust/subresources/tunnels/
https://developers.cloudflare.com/api/resources/zero_trust/subresources/access/
https://developers.cloudflare.com/api/resources/zero_trust/subresources/organizations/
"""

import argparse
import datetime
import ipaddress
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

API = "https://api.cloudflare.com/client/v4"
ACCOUNT = "d2d4084c615189c795286ea5eaec2229"
TUNNEL = "acd44edd-1faf-46fc-ad40-c2977b3f98fb"
PREFIX = f"/accounts/{ACCOUNT}"
TUNNELS = f"{PREFIX}/cfd_tunnel"
CONFIG = f"{TUNNELS}/{TUNNEL}/configurations"
APPS = f"{PREFIX}/access/apps"
TOKENS = f"{PREFIX}/access/service_tokens"
ORGANIZATION = f"{PREFIX}/access/organizations"
PROFILES = ("massed", "windows-gateway")
ZONE_NAME = "a-11-oy.com"
GATEWAY_HOSTNAME = "gateway.a-11-oy.com"
WINDOWS_TUNNEL = "4d22013d-e93b-4889-9a17-b30012cf19e9"
GATEWAY_CNAME = f"{WINDOWS_TUNNEL}.cfargotunnel.com"
ZONES = "/zones"
ZONE_PAGE_SIZE = 50
GATEWAY_MAX_REQUESTS = 8
PAGE_SIZE = 100
MAX_PAGES = 3
MAX_POLICY_APPS = 6
MAX_REQUESTS = 30
MAX_BYTES = 2 * 1024 * 1024
TIMEOUT = 10
DEADLINE_SECONDS = 180
MAX_INGRESS = 200
SELECTOR_TYPES = frozenset({
    "everyone", "service_token", "any_valid_service_token", "email",
    "email_domain", "email_list", "ip", "ip_list", "geo", "group", "gsuite",
    "github-organization", "login_method", "device_posture", "certificate",
    "common_name", "auth_method", "okta", "azureAD", "saml", "auth_context",
    "external_evaluation", "access_linked_app_token", "service_token_tag",
    "linked_app_token", "rule_group",
})


class AuditError(Exception):
    def __init__(self, code, http_status=None, error_codes=()):
        super().__init__(code)
        self.code = code
        self.http_status = http_status
        self.error_codes = list(error_codes)

    def public(self):
        return {
            "status": self.code, "complete": False,
            "http_status": self.http_status, "error_codes": self.error_codes,
        }


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise AuditError("REDIRECT_REFUSED", code)


def identifier(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = str(uuid.UUID(value))
        return parsed if value.lower() == parsed else None
    except (ValueError, AttributeError):
        return None


def cloudflare_identifier(value):
    if isinstance(value, str) and re.fullmatch(r"[a-fA-F0-9]{32}", value):
        return value.lower()
    return None


def integer(value):
    return value if type(value) is int and 0 <= value <= 10_000_000 else None


def boolean(value):
    return value if type(value) is bool else None


def enum(value, allowed):
    return value if isinstance(value, str) and value in allowed else None


def timestamp(value):
    if not isinstance(value, str) or len(value) > 40:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.isoformat() if parsed.tzinfo is not None else None
    except ValueError:
        return None


def hostname(value, wildcard=False):
    if not isinstance(value, str) or not value or len(value) > 253:
        return None
    value = value.lower().rstrip(".")
    if wildcard and value.startswith("*."):
        rest = hostname(value[2:])
        return "*." + rest if rest and "." in rest else None
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        pass
    if value == "localhost":
        return value
    labels = value.split(".")
    if len(labels) < 2:
        return None
    valid = r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
    return value if all(re.fullmatch(valid, label) for label in labels) else None


def domain_host(value):
    if not isinstance(value, str) or "@" in value or len(value) > 2048:
        return None
    try:
        url = urllib.parse.urlsplit(value if "://" in value else "//" + value)
        return hostname(url.hostname, wildcard=True)
    except ValueError:
        return None


def origin(value):
    # Paths can carry credentials too; retain only the scheme, host, and port.
    result = {"endpoint": None, "path_present": False}
    if not isinstance(value, str) or len(value) > 4096:
        return result
    if re.fullmatch(r"http_status:[1-5][0-9]{2}", value):
        result["endpoint"] = value
        return result
    if value == "hello_world":
        result["endpoint"] = value
        return result
    try:
        parsed = urllib.parse.urlsplit(value)
        scheme = enum(parsed.scheme, {"http", "https", "ssh", "tcp", "udp", "rdp", "smb"})
        host = hostname(parsed.hostname)
        port = parsed.port
        if scheme and host and (port is None or 1 <= port <= 65535):
            address = f"[{host}]" if ":" in host else host
            result["endpoint"] = f"{scheme}://{address}" + (f":{port}" if port else "")
            result["path_present"] = bool(parsed.path and parsed.path != "/")
    except ValueError:
        pass
    return result


def access_options(value):
    value = value if isinstance(value, dict) else {}
    team = value.get("teamName")
    if not isinstance(team, str) or not re.fullmatch(r"[A-Za-z0-9-]{1,63}", team):
        team = None
    audiences = value.get("audTag", [])
    if not isinstance(audiences, list):
        audiences = []
    return {
        "required": boolean(value.get("required")),
        "team_name": team,
        "audiences": [
            x.lower() for x in audiences[:20]
            if isinstance(x, str) and re.fullmatch(r"[a-fA-F0-9]{64}", x)
        ],
    }


class Client:
    def __init__(self, token, opener=None, clock=time.monotonic, profile="massed"):
        if profile not in PROFILES:
            raise AuditError("SCOPE_REFUSED")
        self._profile = profile
        self._gateway_zone = None
        self._gateway_account = None
        self._token = token
        self._opener = opener or urllib.request.build_opener(
            urllib.request.ProxyHandler({}), NoRedirect()
        )
        self._clock = clock
        self._deadline = clock() + DEADLINE_SECONDS
        self.calls = 0
        self._policy_apps = set()

    @property
    def profile(self):
        return self._profile

    @property
    def gateway_dns_path(self):
        return f"/zones/{self._gateway_zone}/dns_records" if self._gateway_zone else None

    @property
    def gateway_tunnel_path(self):
        return (
            f"/accounts/{self._gateway_account}/cfd_tunnel/{WINDOWS_TUNNEL}"
            if self._gateway_account else None
        )

    def admit_gateway_zone(self, zone_id, account_id):
        zone = cloudflare_identifier(zone_id)
        account = cloudflare_identifier(account_id)
        if (self._profile != "windows-gateway" or not zone or not account
                or self._gateway_zone is not None):
            raise AuditError("SCOPE_REFUSED")
        self._gateway_zone = zone
        self._gateway_account = account

    def admit_policy_app(self, app_id):
        if (self._profile != "massed" or not identifier(app_id)
                or len(self._policy_apps) >= MAX_POLICY_APPS):
            raise AuditError("POLICY_SCOPE_LIMIT")
        self._policy_apps.add(app_id)

    def _allowed(self, path, page):
        if self._profile == "windows-gateway":
            if path == ZONES:
                return type(page) is int and 1 <= page <= MAX_PAGES
            if self._gateway_zone is None:
                return False
            if path == self.gateway_dns_path:
                return type(page) is int and 1 <= page <= MAX_PAGES
            return page is None and path in {
                self.gateway_tunnel_path,
                self.gateway_tunnel_path + "/configurations",
            }
        if path in {CONFIG, ORGANIZATION}:
            return page is None
        if path in {TUNNELS, APPS, TOKENS}:
            return type(page) is int and 1 <= page <= MAX_PAGES
        return (
            type(page) is int and 1 <= page <= MAX_PAGES
            and path in {f"{APPS}/{app}/policies" for app in self._policy_apps}
        )

    def _check_budget(self):
        limit = min(MAX_REQUESTS, GATEWAY_MAX_REQUESTS) if self._profile == "windows-gateway" else MAX_REQUESTS
        if self.calls >= limit:
            raise AuditError("REQUEST_LIMIT")
        if self._clock() >= self._deadline:
            raise AuditError("DEADLINE_EXCEEDED")

    def _body(self, response):
        chunks = []
        size = 0
        while True:
            if self._clock() >= self._deadline:
                raise AuditError("DEADLINE_EXCEEDED")
            chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
            if not chunk:
                return b"".join(chunks)
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_BYTES:
                raise AuditError("RESPONSE_TOO_LARGE")

    def get(self, path, page=None):
        if not self._allowed(path, page):
            raise AuditError("SCOPE_REFUSED")
        self._check_budget()
        query = {}
        if page is not None:
            query = {"page": page, "per_page": PAGE_SIZE}
        if self._profile == "windows-gateway" and path == ZONES:
            query.update(name=ZONE_NAME, status="active", match="all", per_page=ZONE_PAGE_SIZE)
        elif self._profile == "windows-gateway" and path == self.gateway_dns_path:
            query.update({"name.exact": GATEWAY_HOSTNAME, "match": "all"})
        elif path == TUNNELS:
            query["is_deleted"] = "false"
        url = API + path + ("?" + urllib.parse.urlencode(query) if query else "")
        request = urllib.request.Request(
            url, method="GET",
            headers={"Authorization": "Bearer " + self._token, "Accept": "application/json"},
        )
        self.calls += 1
        try:
            try:
                response = self._opener.open(request, timeout=TIMEOUT)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                status = response.getcode()
                if 300 <= status < 400:
                    raise AuditError("REDIRECT_REFUSED", status)
                raw = self._body(response)
            try:
                data = json.loads(raw)
            except (ValueError, UnicodeDecodeError):
                raise AuditError("INVALID_JSON", status) from None
            if not isinstance(data, dict):
                raise AuditError("INVALID_ENVELOPE", status)
            errors = data.get("errors")
            codes = [
                integer(item.get("code")) for item in errors[:10]
                if isinstance(item, dict) and integer(item.get("code")) is not None
            ] if isinstance(errors, list) else []
            if status in {401, 403}:
                raise AuditError("PERMISSION_DENIED", status, codes)
            if not 200 <= status < 300 or data.get("success") is not True:
                raise AuditError("API_ERROR", status, codes)
            return data
        except AuditError:
            raise
        except (OSError, urllib.error.URLError, TimeoutError):
            raise AuditError("NETWORK_ERROR") from None


def collection(client, path, projector, *, id_parser=identifier, page_size=PAGE_SIZE,
               strict_pagination=False):
    rows = []
    seen_ids = set()
    pagination = None
    report = {"items": [], "pages_read": 0, "complete": False}
    try:
        for page in range(1, MAX_PAGES + 1):
            envelope = client.get(path, page)
            items = envelope.get("result")
            info = envelope.get("result_info", {})
            if not isinstance(items, list) or any(not isinstance(x, dict) for x in items):
                raise AuditError("INVALID_RESULT")
            if len(items) > page_size or not isinstance(info, dict):
                raise AuditError("INVALID_PAGINATION")
            if strict_pagination:
                for key in ("page", "per_page", "count"):
                    if key in info and integer(info[key]) is None:
                        raise AuditError("INVALID_PAGINATION")
                if ("per_page" in info and info["per_page"] != page_size
                        or "count" in info and info["count"] != len(items)):
                    raise AuditError("INVALID_PAGINATION")
                signature = (info.get("total_pages"), info.get("total_count"), info.get("per_page"))
                if pagination is not None and signature != pagination:
                    raise AuditError("INCONSISTENT_PAGINATION")
                pagination = signature
            if "page" in info and info["page"] != page:
                raise AuditError("INVALID_PAGINATION")
            for key in ("total_pages", "total_count"):
                if key in info and integer(info[key]) is None:
                    raise AuditError("INVALID_PAGINATION")
            if strict_pagination and "total_pages" in info and "total_count" in info:
                count = info["total_count"]
                expected = (count + page_size - 1) // page_size
                allowed = {0, 1} if count == 0 else {expected}
                if info["total_pages"] not in allowed:
                    raise AuditError("INCONSISTENT_PAGINATION")
            for item in items:
                item_id = id_parser(item.get("id"))
                if not item_id:
                    raise AuditError("INVALID_RESOURCE_ID")
                if item_id in seen_ids:
                    raise AuditError("DUPLICATE_RESOURCE_ID")
                seen_ids.add(item_id)
                rows.append(item)
                report["items"].append(projector(item))
            report["pages_read"] = page
            total_pages = info.get("total_pages")
            if total_pages is None and "total_count" not in info:
                raise AuditError("PAGINATION_UNVERIFIED")
            finished = (
                page >= max(1, total_pages) if total_pages is not None
                else len(rows) >= info["total_count"]
            )
            if not items and not finished:
                raise AuditError("INCOMPLETE_PAGINATION")
            if finished:
                if "total_count" in info and len(rows) != info["total_count"]:
                    raise AuditError("INCOMPLETE_PAGINATION")
                report.update(status="OBSERVED", complete=True)
                return report, rows
        raise AuditError("PAGE_LIMIT")
    except AuditError as error:
        report.update(error.public())
        return report, rows


def single(client, path, projector):
    try:
        result = client.get(path).get("result")
        if not isinstance(result, dict):
            raise AuditError("INVALID_RESULT")
        return {"status": "OBSERVED", "complete": True, "item": projector(result)}, result
    except AuditError as error:
        return error.public(), None


def tunnel_metadata(item):
    return {
        "id": identifier(item.get("id")),
        "status": enum(item.get("status"), {"inactive", "degraded", "healthy", "down"}),
        "config_source": enum(item.get("config_src"), {"local", "cloudflare"}),
    }


def config_metadata(item):
    config = item.get("config")
    if not isinstance(config, dict):
        raise AuditError("INVALID_CONFIG")
    ingress = config.get("ingress")
    if not isinstance(ingress, list) or len(ingress) > MAX_INGRESS:
        raise AuditError("INGRESS_LIMIT_OR_INVALID")
    routes = []
    for rule in ingress:
        if not isinstance(rule, dict):
            raise AuditError("INVALID_INGRESS_RULE")
        options = rule.get("originRequest", {})
        if not isinstance(options, dict):
            raise AuditError("INVALID_ORIGIN_OPTIONS")
        routes.append({
            "hostname": hostname(rule.get("hostname"), wildcard=True),
            "path_specific": bool(rule.get("path")),
            "origin": origin(rule.get("service")),
            "access_override": access_options(options.get("access")),
            "no_tls_verify_override": boolean(options.get("noTLSVerify")),
        })
    defaults = config.get("originRequest", {})
    if not isinstance(defaults, dict):
        raise AuditError("INVALID_ORIGIN_OPTIONS")
    return {
        "tunnel_id": TUNNEL, "version": integer(item.get("version")),
        "source": enum(item.get("source"), {"local", "cloudflare"}),
        "default_access": access_options(defaults.get("access")),
        "default_no_tls_verify": boolean(defaults.get("noTLSVerify")),
        "ingress": routes,
    }


def application_metadata(item):
    hosts = set()
    primary = domain_host(item.get("domain"))
    if primary:
        hosts.add(primary)
    destinations = item.get("destinations")
    legacy = item.get("self_hosted_domains")
    if isinstance(destinations, list):
        for destination in destinations[:100]:
            if isinstance(destination, dict) and destination.get("type") == "public":
                host = domain_host(destination.get("uri"))
                if host:
                    hosts.add(host)
    elif isinstance(legacy, list):
        hosts.update(host for value in legacy[:100] if (host := domain_host(value)))
    audience = item.get("aud")
    return {
        "id": identifier(item.get("id")), "hostnames": sorted(hosts),
        "type": enum(item.get("type"), {
            "self_hosted", "ssh", "vnc", "rdp", "bookmark", "saas",
            "warp", "biso", "infrastructure", "app_launcher",
        }),
        "audience": audience.lower() if isinstance(audience, str)
        and re.fullmatch(r"[a-fA-F0-9]{64}", audience) else None,
        "path_specific": isinstance(item.get("domain"), str) and "/" in item["domain"],
    }


def token_metadata(item):
    return {
        "id": identifier(item.get("id")),
        "created_at": timestamp(item.get("created_at")),
        "expires_at": timestamp(item.get("expires_at")),
    }


def selectors(value):
    if not isinstance(value, list) or len(value) > 1000:
        raise AuditError("SELECTOR_LIMIT_OR_INVALID")
    types = set()
    tokens = set()
    for rule in value:
        if not isinstance(rule, dict):
            raise AuditError("INVALID_SELECTOR")
        for key, detail in rule.items():
            types.add(key if key in SELECTOR_TYPES else "unrecognized")
            if key == "service_token" and isinstance(detail, dict):
                token_id = identifier(detail.get("token_id"))
                if token_id:
                    tokens.add(token_id)
    return {"rule_count": len(value), "types": sorted(types), "service_token_ids": sorted(tokens)}


def policy_metadata(item):
    return {
        "id": identifier(item.get("id")),
        "decision": enum(item.get("decision"), {"allow", "deny", "bypass", "non_identity"}),
        "precedence": integer(item.get("precedence")),
        "selectors": {key: selectors(item.get(key, [])) for key in ("include", "exclude", "require")},
    }


def related(application, targets):
    metadata = application_metadata(application)
    names = [application.get("name"), application.get("domain")]
    if any(isinstance(value, str) and re.search(r"massed|modelhost|gate1", value, re.I) for value in names):
        return True
    for host in metadata["hostnames"]:
        for target in targets:
            if host == target or (host.startswith("*.") and target.endswith(host[1:])):
                return True
            if target.startswith("*.") and host.endswith(target[1:]):
                return True
    return False


def audit(client):
    report = {
        "schema": "szl.cloudflare-massed-ingress-audit/v1",
        "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "account_id": ACCOUNT, "target_tunnel_id": TUNNEL,
        "provider_mutations": False, "signature": "UNSIGNED",
        "security_verdict": "NOT_EVALUATED",
        "limits": {"requests": MAX_REQUESTS, "pages": MAX_PAGES, "policy_apps": MAX_POLICY_APPS,
                   "response_bytes": MAX_BYTES, "timeout_seconds": TIMEOUT,
                   "deadline_seconds": DEADLINE_SECONDS},
        "issues": [],
    }
    observed = report["observations"] = {}
    observed["tunnels"], tunnels = collection(client, TUNNELS, tunnel_metadata)
    observed["target_configuration"], _ = single(client, CONFIG, config_metadata)
    observed["organization"], _ = single(
        client, ORGANIZATION,
        lambda item: {"auth_domain": hostname(item.get("auth_domain"))},
    )
    observed["applications"], applications = collection(client, APPS, application_metadata)
    observed["service_tokens"], _ = collection(client, TOKENS, token_metadata)
    if not any(item.get("id") == TUNNEL for item in tunnels):
        report["issues"].append("TARGET_TUNNEL_NOT_OBSERVED_IN_LIST")
    target = observed["target_configuration"].get("item", {})
    hosts = {row["hostname"] for row in target.get("ingress", []) if row["hostname"]}
    relevant = [app for app in applications if related(app, hosts)]
    if len(relevant) > MAX_POLICY_APPS:
        report["issues"].append("RELEVANT_APPLICATION_LIMIT")
    policies = report["application_policies"] = []
    for app in relevant[:MAX_POLICY_APPS]:
        app_id = identifier(app.get("id"))
        if not app_id:
            report["issues"].append("RELEVANT_APPLICATION_ID_INVALID")
            continue
        client.admit_policy_app(app_id)
        summary, _ = collection(client, f"{APPS}/{app_id}/policies", policy_metadata)
        policies.append({"application_id": app_id, **summary})
    report["relevant_application_count"] = len(relevant)
    report["request_count"] = client.calls
    report["status"] = "OBSERVED" if (
        not report["issues"]
        and all(value["complete"] for value in observed.values())
        and all(value["complete"] for value in policies)
    ) else "INCOMPLETE"
    return report


def gateway_report():
    return {
        "schema": "szl.cloudflare-gateway-binding-audit/v1",
        "profile": "windows-gateway",
        "observed_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "zone_name": ZONE_NAME, "hostname": GATEWAY_HOSTNAME,
        "target_tunnel_id": WINDOWS_TUNNEL,
        "provider_mutations": False, "signature": "UNSIGNED",
        "security_verdict": "NOT_EVALUATED",
        "origin_probed": False, "windows_connector_identity": "NOT_ESTABLISHED",
        "limits": {
            "requests": GATEWAY_MAX_REQUESTS, "global_requests": MAX_REQUESTS,
            "pages": MAX_PAGES, "zone_page_size": ZONE_PAGE_SIZE,
            "dns_page_size": PAGE_SIZE, "response_bytes": MAX_BYTES,
            "timeout_seconds": TIMEOUT, "deadline_seconds": DEADLINE_SECONDS,
        },
        "observations": {}, "binding": {}, "issues": [],
    }


def gateway_literal_text(value, limit):
    # URL parsers remove some controls; fixed subjects must survive verbatim.
    return (
        isinstance(value, str) and 0 < len(value) <= limit
        and not any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value)
    )


def gateway_hostname(value, wildcard=False):
    # One final root dot is valid DNS syntax; repeated dots are not.
    if not gateway_literal_text(value, 253) or value.endswith(".."):
        return None
    return hostname(value, wildcard=wildcard)


def gateway_zone_metadata(item):
    account = item.get("account")
    account_id = cloudflare_identifier(account.get("id")) if isinstance(account, dict) else None
    if gateway_hostname(item.get("name")) != ZONE_NAME or item.get("status") != "active":
        raise AuditError("ZONE_SCOPE_MISMATCH")
    if not account_id:
        raise AuditError("ZONE_ACCOUNT_ID_INVALID")
    return {
        "id": cloudflare_identifier(item.get("id")), "name": ZONE_NAME,
        "status": "active", "account_id": account_id,
    }


def gateway_dns_metadata(item, zone_id):
    if gateway_hostname(item.get("name")) != GATEWAY_HOSTNAME:
        raise AuditError("DNS_NAME_SCOPE_MISMATCH")
    if "zone_id" in item and cloudflare_identifier(item["zone_id"]) != zone_id:
        raise AuditError("DNS_ZONE_IDENTITY_MISMATCH")
    kind = enum(item.get("type"), {
        "A", "AAAA", "CAA", "CERT", "CNAME", "DNSKEY", "DS", "HTTPS", "LOC",
        "MX", "NAPTR", "NS", "OPENPGPKEY", "PTR", "SMIMEA", "SRV", "SSHFP",
        "SVCB", "TLSA", "TXT", "URI",
    })
    if kind is None:
        raise AuditError("DNS_RECORD_TYPE_UNVERIFIED")
    content = None
    if kind == "CNAME":
        content = gateway_hostname(item.get("content"))
        if content is None:
            raise AuditError("DNS_RECORD_CONTENT_INVALID")
    elif kind in {"A", "AAAA"}:
        if not isinstance(item.get("content"), str):
            raise AuditError("DNS_RECORD_CONTENT_INVALID")
        try:
            address = ipaddress.ip_address(item.get("content"))
        except (ValueError, TypeError):
            raise AuditError("DNS_RECORD_CONTENT_INVALID") from None
        if address.version != (4 if kind == "A" else 6):
            raise AuditError("DNS_RECORD_CONTENT_INVALID")
        content = str(address)
    return {
        "id": cloudflare_identifier(item.get("id")), "name": GATEWAY_HOSTNAME,
        "type": kind, "content": content, "content_omitted": kind not in {"A", "AAAA", "CNAME"},
        "proxied": boolean(item.get("proxied")), "ttl": integer(item.get("ttl")),
    }


def gateway_tunnel_metadata(item):
    result = tunnel_metadata(item)
    result["account_id"] = cloudflare_identifier(item.get("account_tag"))
    return result


def gateway_config_metadata(item):
    result = config_metadata(item)
    # Expected request subjects must never stand in for returned identities.
    result["tunnel_id"] = identifier(item.get("tunnel_id"))
    result["account_id"] = cloudflare_identifier(item.get("account_id"))
    return result


def gateway_origin_matches(value):
    if not gateway_literal_text(value, 4096) or "?" in value or "#" in value:
        return False
    try:
        parsed = urllib.parse.urlsplit(value)
        return (
            parsed.scheme == "http"
            and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            and parsed.port == 4000
            and parsed.username is None and parsed.password is None
            and parsed.path in {"", "/"}
        )
    except ValueError:
        return False


def gateway_ingress_binding(configuration):
    for index, rule in enumerate(configuration["config"]["ingress"]):
        raw_host = rule.get("hostname")
        if raw_host is None or raw_host == "":
            kind = "catch_all"
        else:
            host = gateway_hostname(raw_host, wildcard=True)
            if host is None:
                return {"status": "INGRESS_HOSTNAME_UNVERIFIED", "rule_index": index}
            if host == GATEWAY_HOSTNAME:
                kind = "exact"
            elif host.startswith("*.") and GATEWAY_HOSTNAME.endswith(host[1:]):
                kind = "wildcard"
            else:
                continue
        observation = {
            "rule_index": index, "match_kind": kind,
            "origin": origin(rule.get("service")),
        }
        raw_path = rule.get("path")
        if raw_path is not None and raw_path != "":
            return {**observation, "status": "GATEWAY_PATH_RULE_UNRESOLVED"}
        if kind != "exact":
            return {**observation, "status": "GATEWAY_INGRESS_SHADOWED"}
        if not gateway_origin_matches(rule.get("service")):
            return {**observation, "status": "GATEWAY_ORIGIN_OUTSIDE_FIXED_SCOPE"}
        return {**observation, "status": "MATCHED_CONFIGURATION_ONLY"}
    return {"status": "GATEWAY_INGRESS_NOT_OBSERVED"}


def audit_gateway(client):
    if client.profile != "windows-gateway":
        raise AuditError("SCOPE_REFUSED")
    report = gateway_report()
    observed, binding, issues = report["observations"], report["binding"], report["issues"]
    observed["zone"], zones = collection(
        client, ZONES, gateway_zone_metadata, id_parser=cloudflare_identifier,
        page_size=ZONE_PAGE_SIZE, strict_pagination=True,
    )
    if not observed["zone"]["complete"]:
        issues.append("ZONE_DISCOVERY_INCOMPLETE")
    elif len(zones) != 1:
        issues.append("ACTIVE_ZONE_NOT_UNIQUE" if zones else "ACTIVE_ZONE_NOT_OBSERVED")
    if issues:
        report.update(status="INCOMPLETE", request_count=client.calls)
        return report

    zone = observed["zone"]["items"][0]
    client.admit_gateway_zone(zone["id"], zone["account_id"])
    report["resolved_zone_id"] = zone["id"]
    report["resolved_account_id"] = zone["account_id"]
    observed["dns"], _ = collection(
        client, client.gateway_dns_path,
        lambda item: gateway_dns_metadata(item, zone["id"]),
        id_parser=cloudflare_identifier, strict_pagination=True,
    )
    records = observed["dns"]["items"]
    if not observed["dns"]["complete"]:
        binding["dns"] = "DNS_READ_INCOMPLETE"
    elif not records:
        binding["dns"] = "GATEWAY_DNS_ABSENT"
    elif len(records) != 1:
        binding["dns"] = "GATEWAY_DNS_AMBIGUOUS"
    elif records[0]["type"] != "CNAME" or records[0]["content"] != GATEWAY_CNAME:
        binding["dns"] = "GATEWAY_DNS_TARGET_MISMATCH"
    elif records[0]["proxied"] is not True:
        binding["dns"] = "GATEWAY_DNS_PROXY_UNVERIFIED"
    else:
        binding["dns"] = "MATCHED_CONFIGURATION_ONLY"
    if binding["dns"] != "MATCHED_CONFIGURATION_ONLY":
        issues.append(binding["dns"])

    observed["tunnel"], _ = single(client, client.gateway_tunnel_path, gateway_tunnel_metadata)
    tunnel = observed["tunnel"].get("item", {})
    identity_matches = (
        observed["tunnel"]["complete"] and tunnel.get("id") == WINDOWS_TUNNEL
        and tunnel.get("account_id") == zone["account_id"]
    )
    binding["tunnel"] = "MATCHED_METADATA" if identity_matches else "TUNNEL_IDENTITY_UNVERIFIED"
    if not identity_matches:
        issues.append(binding["tunnel"])
        observed["configuration"] = {"status": "NOT_ATTEMPTED", "complete": False}
    else:
        if tunnel["status"] is None:
            issues.append("TUNNEL_STATUS_UNVERIFIED")
        observed["configuration"], raw_config = single(
            client, client.gateway_tunnel_path + "/configurations", gateway_config_metadata,
        )
        config = observed["configuration"].get("item", {})
        if (not observed["configuration"]["complete"]
                or config.get("account_id") != zone["account_id"]
                or config.get("tunnel_id") != WINDOWS_TUNNEL):
            binding["ingress"] = {"status": "CONFIGURATION_IDENTITY_UNVERIFIED"}
        elif "local" in {tunnel.get("config_source"), config.get("source")}:
            binding["ingress"] = {"status": "LOCAL_CONFIGURATION_NOT_PROVIDER_AUTHORITATIVE"}
        elif tunnel.get("config_source") != "cloudflare" or config.get("source") != "cloudflare":
            binding["ingress"] = {"status": "CONFIGURATION_SOURCE_UNVERIFIED"}
        else:
            binding["ingress"] = gateway_ingress_binding(raw_config)
        if binding["ingress"]["status"] != "MATCHED_CONFIGURATION_ONLY":
            issues.append(binding["ingress"]["status"])

    report["request_count"] = client.calls
    report["status"] = "OBSERVED" if (
        not issues and all(value["complete"] for value in observed.values())
    ) else "INCOMPLETE"
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--profile", choices=PROFILES, default="massed")
    args = parser.parse_args(argv)
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    report = {"schema": "szl.cloudflare-massed-ingress-audit/v1",
              "account_id": ACCOUNT, "target_tunnel_id": TUNNEL,
              "provider_mutations": False, "signature": "UNSIGNED",
              "security_verdict": "NOT_EVALUATED", "request_count": 0}
    if args.profile == "windows-gateway":
        report = gateway_report()
        report["request_count"] = 0
    if not token:
        report.update(status="BLOCKED", issues=["CREDENTIAL_UNAVAILABLE"])
    else:
        client = Client(token, profile=args.profile)
        try:
            report = audit_gateway(client) if args.profile == "windows-gateway" else audit(client)
        except AuditError as error:
            report.update(status="INCOMPLETE", issues=[error.code])
        except Exception:
            report.update(status="INCOMPLETE", issues=["INTERNAL_ERROR"])
        report["request_count"] = client.calls
    revision = os.environ.get("GITHUB_SHA", "")
    report["source_revision"] = revision if re.fullmatch(r"[a-f0-9]{40}", revision) else None
    run_id = os.environ.get("GITHUB_RUN_ID", "")
    report["run_id"] = run_id if re.fullmatch(r"[0-9]{1,20}", run_id) else None
    if args.profile == "windows-gateway":
        attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "")
        report["run_attempt"] = int(attempt) if re.fullmatch(r"[1-9][0-9]{0,9}", attempt) else None
    serialized = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if token:
        serialized = serialized.replace(token, "[REDACTED]")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(serialized, encoding="utf-8")
    print(f"Cloudflare configuration audit: {report['status']}; security verdict: NOT_EVALUATED.")
    return 0 if report["status"] == "OBSERVED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
