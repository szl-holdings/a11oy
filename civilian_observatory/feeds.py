#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Bounded, key-free public observations. No exploit tests or external mutations."""
import argparse
import hashlib
import ipaddress
import json
import math
import re
import socket
import sys
import time
from datetime import datetime, timezone, date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
EPSS_URL = "https://api.first.org/data/v1/epss"
WEATHER_URL = "https://api.weather.gov/alerts/active"
TARGETS = {"a-11-oy.com", "szlholdings.com"}
STATES = {"NY", "CA", "TX"}
CVE = re.compile(r"^CVE-[0-9]{4}-[0-9]{4,19}$")
UA = "SZL-Civilian-Observatory/0.2 (https://a-11-oy.com; public-read-only)"
HEADER_NAMES = [
    "content-security-policy", "strict-transport-security", "x-content-type-options",
    "referrer-policy", "permissions-policy", "x-frame-options",
]
MAX_BYTES = 6_000_000


def now():
    return datetime.now(timezone.utc).isoformat()


def approved_url(url, hosts):
    p = urlsplit(url)
    if p.scheme != "https" or p.hostname not in hosts or p.username or p.password or p.port not in (None, 443):
        raise ValueError("URL is outside the exact HTTPS observation scope")
    return url


def public_dns(host):
    addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    if not addresses or any(not ipaddress.ip_address(info[4][0]).is_global for info in addresses):
        raise ValueError("Target did not resolve exclusively to public addresses")


class ScopedRedirect(HTTPRedirectHandler):
    def __init__(self, hosts):
        self.hosts = hosts
        self.count = 0

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.count += 1
        if self.count > 3:
            raise ValueError("Redirect limit reached")
        approved_url(newurl, self.hosts)
        public_dns(urlsplit(newurl).hostname)
        # HEAD stays HEAD; no automatic body download on a redirected scan.
        return Request(newurl, headers=dict(req.header_items()), method=req.get_method())


def open_scoped(url, hosts, method="GET"):
    approved_url(url, hosts)
    public_dns(urlsplit(url).hostname)
    req = Request(url, headers={"User-Agent": UA, "Accept": "application/json,application/geo+json;q=0.9,*/*;q=0.1"}, method=method)
    return build_opener(ScopedRedirect(hosts)).open(req, timeout=18)


def fetch_json(url, hosts):
    deadline = time.monotonic() + 30
    with open_scoped(url, hosts) as response:
        if response.status != 200:
            raise ValueError(f"Unexpected HTTP status {response.status}")
        chunks, size = [], 0
        while True:
            if time.monotonic() > deadline:
                raise TimeoutError("Public response exceeded the read deadline")
            chunk = response.read1(min(65536, MAX_BYTES + 1 - size))
            if not chunk:
                break
            chunks.append(chunk)
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError("Public response exceeds the bounded size limit")
        raw = b"".join(chunks)
        obj = json.loads(raw)
        if not isinstance(obj, dict):
            raise ValueError("Expected a JSON object")
        return obj, hashlib.sha256(raw).hexdigest()


def source(name, url, digest=None, source_date=None, error=None):
    return {"name": name, "source_url": url, "fetched_at": now() if not error else None,
            "source_date": source_date, "sha256": digest,
            "status": "UNAVAILABLE" if error else "OBSERVED", "error": error}


def empty_feeds():
    """Cold-start state contains no fixture or claimed prior observation."""
    reason = "No public observation has completed in this runtime."
    return {
        "schema_version": "1.0", "generated_at": now(),
        "kev": {"source": source("CISA KEV", KEV_URL, error=reason),
                "catalog_version": None, "entries": []},
        "epss": {"source": source("FIRST EPSS", EPSS_URL, error=reason),
                 "entries": [], "requested": []},
    }


def safe_error(exc):
    if isinstance(exc, HTTPError):
        return f"Public source returned HTTP {exc.code}. No alternative credential or bypass was attempted."
    if isinstance(exc, URLError):
        return "Public source could not be reached using the verified HTTPS connection."
    if isinstance(exc, (ValueError, KeyError, TypeError, json.JSONDecodeError)):
        return "Source failed the bounded URL, schema, or value checks."
    return "The public observation did not complete within its allowed scope."


def valid_cves(values):
    if not isinstance(values, list) or not 1 <= len(values) <= 50:
        raise ValueError("Provide one to fifty CVE identifiers")
    if any(not isinstance(v, str) or not CVE.fullmatch(v) for v in values):
        raise ValueError("Invalid CVE identifier")
    return sorted(set(values))


def probability(value):
    if isinstance(value, bool):
        raise ValueError("Boolean values are not probability estimates")
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ValueError("Invalid probability")
    return value


def get_kev():
    try:
        obj, digest = fetch_json(KEV_URL, {"www.cisa.gov", "cisa.gov"})
        entries = obj["vulnerabilities"]
        if not isinstance(entries, list) or not entries:
            raise ValueError("Empty or missing KEV catalogue")
        cleaned = []
        seen = set()
        for e in entries:
            if not isinstance(e, dict) or not CVE.fullmatch(e.get("cveID", "")) or e["cveID"] in seen:
                raise ValueError("Invalid or duplicated KEV record")
            seen.add(e["cveID"])
            date.fromisoformat(e["dateAdded"])
            cleaned.append({k: str(e.get(k, ""))[:8000] for k in
                            ("cveID", "vendorProject", "product", "vulnerabilityName", "shortDescription",
                             "requiredAction", "dateAdded", "knownRansomwareCampaignUse")})
        if type(obj.get("count")) is not int or obj["count"] != len(cleaned):
            raise ValueError("Catalogue count does not match the returned data")
        record = source("CISA KEV", KEV_URL, digest, obj.get("dateReleased"))
        return {"source": record, "catalog_version": str(obj.get("catalogVersion", "")), "entries": cleaned}
    except Exception as exc:
        return {"source": source("CISA KEV", KEV_URL, error=safe_error(exc)), "catalog_version": None, "entries": []}


def get_epss(ids):
    ids = valid_cves(ids)
    url = EPSS_URL + "?" + urlencode({"cve": ",".join(ids)})
    try:
        obj, digest = fetch_json(url, {"api.first.org"})
        rows = obj["data"]
        if obj.get("status") != "OK" or not isinstance(rows, list):
            raise ValueError("Malformed EPSS response")
        cleaned = []
        seen = set()
        for r in rows:
            if r["cve"] not in ids or r["cve"] in seen:
                raise ValueError("Unexpected EPSS identifier")
            seen.add(r["cve"])
            date.fromisoformat(r["date"])
            cleaned.append({"cve": r["cve"], "epss": probability(r["epss"]),
                            "percentile": probability(r["percentile"]), "date": r["date"]})
        last_date = max((r["date"] for r in cleaned), default=None)
        s = source("FIRST EPSS", url, digest, last_date)
        if last_date and (datetime.now(timezone.utc).date() - date.fromisoformat(last_date)).days > 3:
            s.update(status="STALE", error="EPSS score date is more than three days old; this is the dated estimate, not a current score.")
        return {"source": s, "entries": cleaned, "requested": ids}
    except Exception as exc:
        return {"source": source("FIRST EPSS", url, error=safe_error(exc)), "entries": [], "requested": ids}


def get_feeds():
    kev = get_kev()
    latest = sorted(kev["entries"], key=lambda r: (r["dateAdded"], r["cveID"]), reverse=True)[:20]
    ids = [r["cveID"] for r in latest]
    epss = get_epss(ids) if ids else {
        "source": source("FIRST EPSS", EPSS_URL, error="No observed catalogue examples available to query."),
        "entries": [], "requested": [],
    }
    return {"schema_version": "1.0", "generated_at": now(), "kev": kev, "epss": epss}


def get_weather(area):
    if area not in STATES:
        raise ValueError("Area is outside the public weather scope")
    url = WEATHER_URL + "?" + urlencode({"area": area})
    try:
        obj, digest = fetch_json(url, {"api.weather.gov"})
        if obj.get("type") != "FeatureCollection" or not isinstance(obj.get("features"), list):
            raise ValueError("Malformed weather response")
        alerts = []
        for item in obj["features"]:
            p = item["properties"]
            if p.get("status") not in (None, "Actual"):
                continue
            public_url = item.get("id", "")
            if not isinstance(public_url, str) or not public_url.startswith("https://api.weather.gov/alerts/"):
                public_url = "https://www.weather.gov/alerts"
            alerts.append({"id": str(item.get("id", "")), "event": str(p.get("event", "Unspecified"))[:200],
                           "headline": str(p.get("headline") or "")[:1200], "area": str(p.get("areaDesc") or "")[:1200],
                           "severity": str(p.get("severity", "Unknown")), "certainty": str(p.get("certainty", "Unknown")),
                           "expires": p.get("expires"), "instruction": str(p.get("instruction") or "")[:3000],
                           "url": public_url})
        return {"area": area, "source": source("National Weather Service", url, digest, obj.get("updated")),
                "alerts": alerts[:100], "count": len(alerts[:100]), "reported_count": len(alerts)}
    except Exception as exc:
        return {"area": area, "source": source("National Weather Service", url, error=safe_error(exc)),
                "alerts": [], "count": None, "reported_count": None}


def get_headers(target):
    if target not in TARGETS:
        raise ValueError("Target is not in the owner-approved observation allowlist")
    url = f"https://{target}/"
    checked_at = now()
    limitations = [
        "One root-page HTTPS HEAD request, plus at most three same-host redirects; no ports, exploits, logins, or origin bypass.",
        "Only selected response headers are recorded. Missing headers are observations, not exploitability findings.",
        "The digest covers the selected header values and HTTP status, not the complete site or its software.",
        "Results describe the network-visible response, potentially including a CDN, cache, or proxy; no TLS-security certification.",
    ]
    try:
        # Redirects stay on the exact hostname, including no implicit www expansion.
        with open_scoped(url, {target}, method="HEAD") as response:
            status = response.status
            headers = [{"name": k, "value": response.headers.get(k)[:2000] if response.headers.get(k) else None} for k in HEADER_NAMES]
            digest = hashlib.sha256(json.dumps({"status": status, "headers": headers}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            return {"target": target, "checked_at": checked_at, "method": "HEAD", "http_status": status,
                    "headers": headers, "source": source("Scoped web headers", url, digest), "limitations": limitations}
    except Exception as exc:
        return {"target": target, "checked_at": checked_at, "method": "HEAD", "http_status": None,
                "headers": [{"name": h, "value": None} for h in HEADER_NAMES],
                "source": source("Scoped web headers", url, error=safe_error(exc)), "limitations": limitations}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["feeds", "epss", "weather", "headers"])
    parser.add_argument("--ids", default="")
    parser.add_argument("--area", default="NY")
    parser.add_argument("--target", default="")
    parser.add_argument("--output", help="Optional operator-selected local JSON output path.")
    args = parser.parse_args()
    try:
        if args.command == "feeds":
            result = get_feeds()
        elif args.command == "epss":
            result = get_epss(args.ids.split(","))
        elif args.command == "weather":
            result = get_weather(args.area)
        else:
            result = get_headers(args.target)
        serialized = json.dumps(result, ensure_ascii=False, allow_nan=False)
        if args.output:
            Path(args.output).write_text(serialized + "\n", encoding="utf-8")
        else:
            print(serialized)
    except ValueError as exc:
        print(json.dumps({"error": str(exc)}))
        sys.exit(2)
