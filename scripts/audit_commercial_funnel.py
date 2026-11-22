#!/usr/bin/env python3
"""Bounded, read-only public buyer-journey witness; not a revenue certificate.

Never sends mail, makes a purchase, follows a redirect, or reads credentials.
A successful GET or mailto href is not evidence of delivery, a lead, or cash.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
import re
import urllib.error
import urllib.request

ORIGIN = "https://a-11-oy.com"
PATHS = ("/pricing", "/verify", "/contact", "/demo", "/api/build-info")
MAX_RESPONSE_BYTES = 192 * 1024
TIMEOUT_SECONDS = 8
SHA40 = re.compile(r"[a-f0-9]{40}\Z")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None


class PricingHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.mailto_ctas = 0
        self.forms = 0
        self.verify_links = 0
        self.pilot_ctas = 0

    def handle_starttag(self, tag, attrs):
        values = {name: value for name, value in attrs if name not in (None, "")}
        if tag == "form":
            self.forms += 1
        if tag != "a":
            return
        href = values.get("href", "") or ""
        if href.lower().startswith("mailto:"):
            self.mailto_ctas += 1
            if "pilot" in href.lower():
                self.pilot_ctas += 1
        if href.split("?", 1)[0] == "/verify":
            self.verify_links += 1


def probe(path: str, *, opener=None) -> tuple[dict, bytes | None]:
    """One public GET to one exact path, with a byte cap and no redirect."""
    if path not in PATHS:
        raise ValueError("endpoint is outside the approved public probe set")
    if opener is None:
        opener = urllib.request.build_opener(NoRedirect()).open
    request = urllib.request.Request(
        ORIGIN + path,
        method="GET",
        headers={
            "User-Agent": "szl-commercial-funnel-readonly/1",
            "Accept": "text/html,application/json",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with opener(request, timeout=TIMEOUT_SECONDS) as response:
            status = response.getcode()
            if status != 200 or response.geturl() != ORIGIN + path:
                return {"state": "NON_200_OR_REDIRECT", "http_status": status}, None
            body = response.read(MAX_RESPONSE_BYTES + 1)
            if len(body) > MAX_RESPONSE_BYTES:
                return {"state": "OVERSIZE", "http_status": status}, None
            content_type = response.headers.get("Content-Type", "").split(";", 1)[0].lower()
            if content_type not in {"text/html", "application/json"}:
                return {"state": "UNSUPPORTED_CONTENT_TYPE", "http_status": status}, None
            return {"state": "REACHABLE", "http_status": status, "content_type": content_type}, body
    except urllib.error.HTTPError as exc:
        # Do not log provider body, headers, request cookies, or IP addresses.
        return {"state": "HTTP_REFUSED", "http_status": int(exc.code)}, None
    except (OSError, ValueError, TimeoutError, UnicodeError):
        return {"state": "UNAVAILABLE", "http_status": None}, None


def observe(*, opener=None, source_revision: str = "UNKNOWN", clock=None) -> dict:
    if source_revision != "UNKNOWN" and SHA40.fullmatch(source_revision) is None:
        raise ValueError("source_revision must be UNKNOWN or exact lowercase SHA40")
    if clock is None:
        clock = lambda: datetime.now(timezone.utc)
    now = clock()
    if not isinstance(now, datetime) or now.utcoffset() != timezone.utc.utcoffset(now):
        raise ValueError("observation clock must return UTC datetime")
    routes = {}
    pricing_body = None
    for path in PATHS:
        result, body = probe(path, opener=opener)
        routes[path] = result
        if path == "/pricing" and result["state"] == "REACHABLE":
            if result["content_type"] == "text/html":
                pricing_body = body
    ctas = {"mailto_count": None, "forms_count": None,
            "verify_link_count": None, "pilot_mailto_count": None}
    if pricing_body is None:
        intake = "UNAVAILABLE"
    else:
        try:
            parser = PricingHTML()
            parser.feed(pricing_body.decode("utf-8", errors="strict"))
            parser.close()
            ctas = {"mailto_count": parser.mailto_ctas, "forms_count": parser.forms,
                    "verify_link_count": parser.verify_links,
                    "pilot_mailto_count": parser.pilot_ctas}
            if parser.forms:
                intake = "FORM_PRESENT_DELIVERY_UNVERIFIED"
            elif parser.mailto_ctas:
                intake = "MAILTO_ONLY_DELIVERY_UNVERIFIED"
            else:
                intake = "NO_VISIBLE_INTAKE"
        except (UnicodeError, ValueError):
            intake = "UNAVAILABLE"
    return {
        "schema": "szl.public-commercial-journey-observation/v1",
        "observed_at": now.isoformat(),
        "source_revision": source_revision,
        "source_identity_scope": "CALLER_DECLARED_NOT_ATTESTED",
        "scope": "PUBLIC_GET_ONLY_NO_BROWSER_NO_AUTHENTICATION",
        "routes": routes,
        "pricing_calls_to_action": ctas,
        "inquiry_routing_state": intake,
        "mailbox_delivery_verified": False,
        "form_delivery_verified": False,
        "lead_attribution_verified": False,
        "settled_payment_verified": False,
        "paid_customer_conversion_verified": False,
        "production_or_revenue_admission": "HOLD",
        "provider_writes": 0,
        "messages_sent": 0,
        "note": "Public response states are not browser or buyer experience; no inbox, analytics, payment or settlement was checked.",
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-revision", default="UNKNOWN")
    args = parser.parse_args(argv)
    result = observe(source_revision=args.source_revision)
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0 if result["routes"]["/pricing"]["state"] == "REACHABLE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
