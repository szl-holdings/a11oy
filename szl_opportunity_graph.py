# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""Public, read-only opportunity graph for real estate, counsel, and finance.

This service turns official organization/property records into source-linked
research opportunities. It never collects contact details, never marks a
record callable, and never performs outreach. Upstream failure is represented
as STALE or UNAVAILABLE; there is no generated-data fallback.

Taxonomy: services/business logic. GET routes are side-effect free and do not
mint receipts or signatures.
"""

import copy
import hashlib
import html as html_lib
import io
import json
import math
import os
import re
import threading
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable
from urllib.parse import quote, urlencode, urljoin, urlparse
from xml.etree import ElementTree as ET

import anyio
import httpx
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse


SCHEMA = "szl.opportunity-board/v1"
SOURCE_SCHEMA = "szl.source-envelope/v1"
PAGE_PATH = Path(__file__).with_name("opportunities.html")
POLICY_PATH = Path(__file__).parent / "verticals" / "opportunity-graph" / "source_admission.json"
USER_AGENT = os.environ.get(
    "A11OY_PUBLIC_DATA_USER_AGENT",
    "SZL-Holdings-A11oy/1.0 opportunity-research stephenlutar2@gmail.com",
)

EASTERN_STATES = {
    "CT": "Connecticut",
    "DC": "District of Columbia",
    "DE": "Delaware",
    "FL": "Florida",
    "GA": "Georgia",
    "KY": "Kentucky",
    "MA": "Massachusetts",
    "MD": "Maryland",
    "ME": "Maine",
    "NC": "North Carolina",
    "NH": "New Hampshire",
    "NJ": "New Jersey",
    "NY": "New York",
    "OH": "Ohio",
    "PA": "Pennsylvania",
    "RI": "Rhode Island",
    "SC": "South Carolina",
    "TN": "Tennessee",
    "VA": "Virginia",
    "VT": "Vermont",
    "WV": "West Virginia",
}

VERTICALS = {
    "realestate": {
        "label": "Commercial real estate",
        "canonical_pack": "terra",
        "primary_entity": "property_or_lease",
        "source_ids": ["gsa_lease_inventory"],
    },
    "counsel": {
        "label": "Counsel and legal",
        "canonical_pack": "counsel",
        "primary_entity": "organization_or_regulatory_event",
        "source_ids": ["federal_register_documents", "usaspending_awards"],
    },
    "finance": {
        "label": "Finance and private markets",
        "canonical_pack": "puriq-markets",
        "primary_entity": "organization_or_filing",
        "source_ids": ["sec_recent_filings", "usaspending_awards"],
    },
}

_POLICY_ERROR: str | None = None
try:
    _SOURCE_POLICY = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
except (OSError, json.JSONDecodeError) as exc:
    _SOURCE_POLICY = {}
    _POLICY_ERROR = f"{type(exc).__name__}: {str(exc)[:160]}"

_ADMITTED = {
    str(item.get("id")): item
    for item in _SOURCE_POLICY.get("admitted", [])
    if isinstance(item, dict) and item.get("id")
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _timeout_seconds() -> float:
    try:
        configured = float(os.environ.get("A11OY_OPPORTUNITY_HTTP_TIMEOUT_S", "12"))
    except (TypeError, ValueError):
        configured = 12.0
    if not math.isfinite(configured):
        configured = 12.0
    return max(2.0, min(20.0, configured))


def _trim(value: Any, maximum: int = 520) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:maximum]


def _stable_id(namespace: str, value: str) -> str:
    digest = hashlib.sha256(f"{namespace}:{value}".encode("utf-8")).hexdigest()[:20]
    return f"{namespace}:{digest}"


def _source_rule(source_id: str) -> dict[str, Any]:
    rule = _ADMITTED.get(source_id)
    if not isinstance(rule, dict):
        raise RuntimeError(f"source {source_id!r} is not present in the admitted-source manifest")
    return rule


def _assert_url_admitted(source_id: str, url: str) -> None:
    rule = _source_rule(source_id)
    parsed = urlparse(url)
    hosts = {str(host).lower() for host in rule.get("hosts", [])}
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in hosts:
        raise RuntimeError(f"source URL is outside the admitted HTTPS hosts for {source_id}")


def _admitted_record_url(source_id: str, value: Any) -> str | None:
    candidate = _trim(value, 800)
    if not candidate:
        return None
    try:
        _assert_url_admitted(source_id, candidate)
    except RuntimeError:
        return None
    return candidate


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        timeout=httpx.Timeout(_timeout_seconds()),
        follow_redirects=False,
    )


def _safe_error(exc: BaseException) -> str:
    return f"{type(exc).__name__}: {_trim(exc, 180)}"


class _RefreshFlight:
    def __init__(self) -> None:
        self.event = threading.Event()
        self.result: dict[str, Any] | None = None


_CACHE_LOCK = threading.Lock()
_CACHE: dict[str, dict[str, Any]] = {}
_INFLIGHT: dict[str, _RefreshFlight] = {}


def _source_envelope(
    source_id: str,
    payload: dict[str, Any],
    *,
    state: str,
    observed_at: str,
    latency_ms: int,
    cache_status: str,
    cache_age_s: float = 0.0,
    error: str | None = None,
) -> dict[str, Any]:
    rule = _source_rule(source_id)
    envelope = {
        "schema": SOURCE_SCHEMA,
        "source_id": source_id,
        "label": rule.get("label"),
        "owner": rule.get("owner"),
        "state": state,
        "observed_at": observed_at,
        "record_count": len(payload.get("opportunities", [])),
        "coverage": payload.get("coverage", "UNAVAILABLE"),
        "reason": payload.get("reason"),
        "citation": payload.get("citation", rule.get("terms_url")),
        "latency_ms": latency_ms,
        "cache_status": cache_status,
        "cache_age_s": round(max(0.0, cache_age_s), 1),
        "access": rule.get("access"),
        "permitted_use": rule.get("permitted_use"),
        "contact_data": bool(rule.get("contact_data", False)),
        "source_revision": payload.get("source_revision"),
        "upstream_observed_at": payload.get("upstream_observed_at"),
    }
    if error:
        envelope["error"] = error
    return envelope


def _cached_source(
    source_id: str,
    variant: str,
    ttl_s: int,
    fetcher: Callable[[], dict[str, Any]],
) -> dict[str, Any]:
    key = f"{source_id}:{variant}"
    now = time.time()
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
        if cached and now - cached["fetched_at"] < ttl_s:
            result = copy.deepcopy(cached["result"])
            age = now - cached["fetched_at"]
            result["source"]["cache_status"] = "HIT"
            result["source"]["cache_age_s"] = round(age, 1)
            return result
        flight = _INFLIGHT.get(key)
        if flight is None:
            flight = _RefreshFlight()
            _INFLIGHT[key] = flight
            is_owner = True
        else:
            is_owner = False

    if not is_owner:
        if flight.event.wait(_timeout_seconds() + 2.0) and flight.result is not None:
            return copy.deepcopy(flight.result)
        payload = {"opportunities": [], "coverage": "UNAVAILABLE"}
        return {
            "opportunities": [],
            "source": _source_envelope(
                source_id,
                payload,
                state="UNAVAILABLE",
                observed_at=_utc_now(),
                latency_ms=0,
                cache_status="MISS",
                error="refresh wait exceeded the bounded source budget",
            ),
        }

    started = time.monotonic()
    result: dict[str, Any]
    try:
        payload = fetcher()
        if not isinstance(payload, dict) or not isinstance(payload.get("opportunities"), list):
            raise ValueError("source adapter returned an invalid payload")
        observed_at = _utc_now()
        result = {
            "opportunities": payload["opportunities"],
            "source": _source_envelope(
                source_id,
                payload,
                state="LIVE",
                observed_at=observed_at,
                latency_ms=round((time.monotonic() - started) * 1000),
                cache_status="MISS",
            ),
        }
        with _CACHE_LOCK:
            _CACHE[key] = {"fetched_at": time.time(), "result": copy.deepcopy(result)}
    except BaseException as exc:
        if cached:
            result = copy.deepcopy(cached["result"])
            age = max(0.0, time.time() - cached["fetched_at"])
            result["source"]["state"] = "STALE"
            result["source"]["cache_status"] = "STALE_FALLBACK"
            result["source"]["cache_age_s"] = round(age, 1)
            result["source"]["latency_ms"] = round((time.monotonic() - started) * 1000)
            result["source"]["error"] = _safe_error(exc)
        else:
            payload = {"opportunities": [], "coverage": "UNAVAILABLE"}
            result = {
                "opportunities": [],
                "source": _source_envelope(
                    source_id,
                    payload,
                    state="UNAVAILABLE",
                    observed_at=_utc_now(),
                    latency_ms=round((time.monotonic() - started) * 1000),
                    cache_status="MISS",
                    error=_safe_error(exc),
                ),
            }
        if not isinstance(exc, Exception):
            raise
    finally:
        with _CACHE_LOCK:
            active = _INFLIGHT.pop(key, None)
            if active is not None:
                active.result = copy.deepcopy(result)
                active.event.set()
    return result


def _reported(label: str, value: Any, unit: str | None = None) -> dict[str, Any]:
    return {"label": label, "value": value, "unit": unit, "method": "REPORTED"}


def _derived(label: str, value: Any, method: str, unit: str | None = None) -> dict[str, Any]:
    return {"label": label, "value": value, "unit": unit, "method": f"DERIVED: {method}"}


def _opportunity(
    *,
    opportunity_id: str,
    vertical: str,
    entity_id: str,
    entity_type: str,
    entity_name: str,
    location: dict[str, Any],
    authoritative_ids: list[dict[str, str]],
    signal_kind: str,
    title: str,
    summary: str,
    observed_at: str | None,
    measurements: list[dict[str, Any]],
    priority: int,
    reasons: list[str],
    next_action: str,
    citations: list[dict[str, str]],
    vertical_facts: dict[str, Any],
) -> dict[str, Any]:
    return {
        "id": opportunity_id,
        "vertical": vertical,
        "entity": {
            "id": entity_id,
            "type": entity_type,
            "name": _trim(entity_name, 220),
            "location": location,
            "authoritative_ids": authoritative_ids,
        },
        "signal": {
            "kind": signal_kind,
            "title": _trim(title, 240),
            "summary": _trim(summary, 600),
            "observed_at": observed_at,
            "measurements": measurements,
        },
        "ranking": {
            "research_priority": max(0, min(100, int(priority))),
            "reasons": reasons,
            "method": "TRANSPARENT_RULES_NOT_DEAL_PROBABILITY",
        },
        "workflow": {
            "stage": "INBOX",
            "next_action": next_action,
            "deadline": None,
            "mutable_in_public_view": False,
        },
        "evidence": {
            "state": "OBSERVED",
            "grade": "SOURCE_BACKED",
            "citations": citations,
            "counter_evidence": [],
            "receipt_id": None,
            "verified_at": None,
            "recheck_at": None,
            "expires_at": None,
        },
        "permission": {
            "state": "PUBLIC_RESEARCH_ONLY",
            "call_ready": False,
            "reasons": [
                "A public record is research evidence, not consent to contact a person.",
                "No person-level contact data is collected or projected.",
                "A human must verify business identity, purpose, channel rules, and suppression status.",
            ],
        },
        "vertical_facts": vertical_facts,
    }


_XLSX_NS = {"x": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}


def _column_number(reference: str) -> int:
    letters = re.match(r"[A-Z]+", reference.upper())
    if not letters:
        return -1
    value = 0
    for character in letters.group(0):
        value = value * 26 + ord(character) - 64
    return value - 1


def _xlsx_table(content: bytes) -> list[dict[str, Any]]:
    with zipfile.ZipFile(io.BytesIO(content)) as workbook:
        shared_root = ET.fromstring(workbook.read("xl/sharedStrings.xml"))
        shared = [
            "".join(node.text or "" for node in item.findall(".//x:t", _XLSX_NS))
            for item in shared_root.findall("x:si", _XLSX_NS)
        ]
        sheet_root = ET.fromstring(workbook.read("xl/worksheets/sheet1.xml"))

    rows: list[list[Any]] = []
    for row in sheet_root.findall(".//x:sheetData/x:row", _XLSX_NS):
        values: dict[int, Any] = {}
        for cell in row.findall("x:c", _XLSX_NS):
            column = _column_number(cell.attrib.get("r", ""))
            if column < 0:
                continue
            cell_type = cell.attrib.get("t")
            value_node = cell.find("x:v", _XLSX_NS)
            raw = value_node.text if value_node is not None else None
            if cell_type == "s" and raw is not None:
                try:
                    value: Any = shared[int(raw)]
                except (ValueError, IndexError):
                    value = None
            elif cell_type == "inlineStr":
                value = "".join(node.text or "" for node in cell.findall(".//x:t", _XLSX_NS))
            else:
                value = raw
            values[column] = value
        if values:
            width = max(values) + 1
            rows.append([values.get(index) for index in range(width)])

    if not rows:
        return []
    headers = [_trim(item, 120) for item in rows[0]]
    records: list[dict[str, Any]] = []
    for row in rows[1:]:
        records.append({
            header: row[index] if index < len(row) else None
            for index, header in enumerate(headers)
            if header
        })
    return records


def _excel_date(value: Any) -> date | None:
    if value in (None, ""):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        text = _trim(value, 40)
        for pattern in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
            try:
                return datetime.strptime(text, pattern).date()
            except ValueError:
                continue
        return None
    if not math.isfinite(number):
        return None
    return (datetime(1899, 12, 30) + timedelta(days=number)).date()


def _number(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _http_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _gsa_priority(days_to_expiry: int, action: str) -> tuple[int, list[str]]:
    action_lower = action.lower()
    if "holdover" in action_lower:
        return 96, ["GSA reports the lease as holdover", "Federal lease record requires source verification"]
    if days_to_expiry < 0:
        return 92, ["Reported expiration date has passed", "Current lease status requires source verification"]
    if days_to_expiry <= 365:
        return 90, ["Reported expiration is within 12 months", "Time-sensitive property research window"]
    if days_to_expiry <= 730:
        return 82, ["Reported expiration is within 24 months", "Property research can begin before procurement activity"]
    if days_to_expiry <= 1095:
        return 72, ["Reported expiration is within 36 months"]
    return 56, ["Reported expiration is more than 36 months away"]


def _fetch_gsa_leases(state: str, limit: int) -> dict[str, Any]:
    source_id = "gsa_lease_inventory"
    inventory_page = "https://www.gsa.gov/real-estate/realty-and-lease-acquisition"
    _assert_url_admitted(source_id, inventory_page)
    with _client() as client:
        page_response = client.get(inventory_page, headers={"Accept": "text/html"})
        page_response.raise_for_status()
        match = re.search(
            r'href=["\']([^"\']*External[^"\']*\.xlsx)["\']',
            page_response.text,
            flags=re.IGNORECASE,
        )
        if not match:
            raise ValueError("current GSA lease workbook link was not found")
        workbook_url = urljoin(inventory_page, html_lib.unescape(match.group(1)))
        _assert_url_admitted(source_id, workbook_url)
        workbook_response = client.get(
            workbook_url,
            headers={"Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"},
        )
        workbook_response.raise_for_status()
        rows = _xlsx_table(workbook_response.content)

    today = datetime.now(timezone.utc).date()
    opportunities: list[dict[str, Any]] = []
    for row in rows:
        if _trim(row.get("State"), 2).upper() != state:
            continue
        lease_number = _trim(row.get("Lease Num"), 80)
        expiration = _excel_date(row.get("Lease Expiration"))
        if not lease_number or expiration is None:
            continue
        days_to_expiry = (expiration - today).days
        if days_to_expiry < -730 or days_to_expiry > 1825:
            continue
        address = _trim(row.get("Address"), 180)
        city = _trim(row.get("City"), 100)
        county = _trim(row.get("County"), 100)
        zip_code = _trim(row.get("ZipCode"), 20)
        action = _trim(row.get("Latest Action affecting Term"), 120)
        annual_rent = _number(row.get("Current Annual Rent"))
        square_feet = _number(row.get("Lease Agreement RSF"))
        priority, reasons = _gsa_priority(days_to_expiry, action)
        parts = [f"GSA reports lease {lease_number} expiring {expiration.isoformat()}."]
        if annual_rent is not None and annual_rent > 0:
            parts.append(f"Reported annual rent is ${annual_rent:,.0f}.")
        if square_feet is not None and square_feet > 0:
            parts.append(f"Reported rentable area is {square_feet:,.0f} square feet.")
        measurements = [
            _reported("Lease expiration", expiration.isoformat(), "date"),
            _derived("Days to reported expiration", days_to_expiry, "expiration date minus query date", "days"),
        ]
        if annual_rent is not None and annual_rent > 0:
            measurements.append(_reported("Current annual rent", round(annual_rent, 2), "USD/year"))
        if square_feet is not None and square_feet > 0:
            measurements.append(_reported("Lease agreement area", round(square_feet, 2), "RSF"))
        opportunities.append(_opportunity(
            opportunity_id=_stable_id("gsa-lease", lease_number),
            vertical="realestate",
            entity_id=lease_number,
            entity_type="federal_lease_property",
            entity_name=f"{address or 'Address redacted'}, {city or state}",
            location={"address": address or None, "city": city or None, "county": county or None,
                      "state": state, "postal_code": zip_code or None, "scope": "STATE"},
            authoritative_ids=[{"scheme": "GSA_LEASE_NUMBER", "value": lease_number}],
            signal_kind="LEASE_EXPIRATION",
            title=("Federal lease is reported in holdover" if "holdover" in action.lower()
                   else f"Federal lease expires {expiration.isoformat()}"),
            summary=" ".join(parts),
            observed_at=_http_date(workbook_response.headers.get("Last-Modified")),
            measurements=measurements,
            priority=priority,
            reasons=reasons,
            next_action="Open the GSA workbook, confirm the lease record, then research the property and procurement path.",
            citations=[{"source_id": source_id, "record_id": lease_number,
                        "label": "GSA external lease inventory", "url": workbook_url}],
            vertical_facts={"lease_number": lease_number, "latest_term_action": action or None,
                            "field_office": _trim(row.get("Field Office Name"), 140) or None},
        ))

    opportunities.sort(key=lambda item: (-item["ranking"]["research_priority"],
                                         item["signal"]["observed_at"] or ""))
    return {
        "opportunities": opportunities[:limit],
        "coverage": f"GSA leases in {state} with reported expiration from two years ago through five years ahead",
        "citation": workbook_url,
        "source_revision": Path(urlparse(workbook_url).path).name,
        "upstream_observed_at": _http_date(workbook_response.headers.get("Last-Modified")),
    }


def _amount_priority(amount: float | None, base: int = 42) -> tuple[int, list[str]]:
    if amount is None or amount <= 0:
        return base, ["Official event is present; amount is unavailable or not positive"]
    score = min(92, base + int(math.log10(max(amount, 1.0)) * 6))
    return score, [f"Reported award value is ${amount:,.0f}", "Priority is a research sort, not outcome probability"]


def _fetch_usaspending(state: str, vertical: str, limit: int) -> dict[str, Any]:
    source_id = "usaspending_awards"
    url = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
    _assert_url_admitted(source_id, url)
    end = datetime.now(timezone.utc).date()
    start = end - timedelta(days=365)
    if vertical == "finance":
        award_codes = ["07", "08"]
        fields = [
            "Award ID", "Recipient Name", "Awarding Agency", "Awarding Sub Agency",
            "Description", "Base Obligation Date", "Recipient UEI", "Primary Place of Performance",
            "Issued Date", "Loan Value", "Subsidy Cost", "Assistance Listings",
            "generated_internal_id",
        ]
        sort_field = "Loan Value"
    else:
        award_codes = ["A", "B", "C", "D"]
        fields = [
            "Award ID", "Recipient Name", "Start Date", "End Date", "Award Amount",
            "Awarding Agency", "Awarding Sub Agency", "Description", "Last Modified Date",
            "Base Obligation Date", "Recipient UEI", "Primary Place of Performance", "NAICS",
            "generated_internal_id",
        ]
        sort_field = "Award Amount"
    body = {
        "filters": {
            "time_period": [{"start_date": start.isoformat(), "end_date": end.isoformat()}],
            "award_type_codes": award_codes,
            "place_of_performance_scope": "domestic",
            "place_of_performance_locations": [{"country": "USA", "state": state}],
        },
        "fields": fields,
        "limit": limit,
        "page": 1,
        "sort": sort_field,
        "order": "desc",
        "subawards": False,
    }
    with _client() as client:
        response = client.post(url, json=body)
        response.raise_for_status()
        payload = response.json()

    opportunities: list[dict[str, Any]] = []
    for row in payload.get("results", []):
        if not isinstance(row, dict):
            continue
        award_id = _trim(row.get("Award ID"), 120)
        recipient = _trim(row.get("Recipient Name"), 220)
        if not award_id or not recipient:
            continue
        place = row.get("Primary Place of Performance") or {}
        if not isinstance(place, dict):
            place = {}
        generated_id = _trim(row.get("generated_internal_id"), 260)
        record_url = (
            f"https://www.usaspending.gov/award/{quote(generated_id, safe='_-')}/"
            if generated_id else "https://www.usaspending.gov/search"
        )
        description = _trim(row.get("Description"), 600)
        uei = _trim(row.get("Recipient UEI"), 40)
        if vertical == "finance":
            amount = _number(row.get("Loan Value"))
            event_date = _trim(row.get("Issued Date") or row.get("Base Obligation Date"), 40) or None
            signal_kind = "FEDERAL_LOAN_AWARD"
            title = f"Federal loan record for {recipient}"
            measurements = []
            if amount is not None:
                measurements.append(_reported("Loan value", round(amount, 2), "USD"))
            subsidy = _number(row.get("Subsidy Cost"))
            if subsidy is not None:
                measurements.append(_reported("Subsidy cost", round(subsidy, 2), "USD"))
            next_action = "Verify the award and organization, then document a permitted finance research hypothesis."
        else:
            amount = _number(row.get("Award Amount"))
            event_date = _trim(row.get("Last Modified Date") or row.get("Base Obligation Date"), 40) or None
            signal_kind = "FEDERAL_CONTRACT_AWARD"
            title = f"Federal contract record for {recipient}"
            measurements = []
            if amount is not None:
                measurements.append(_reported("Award amount", round(amount, 2), "USD"))
            next_action = "Verify the award and organization, document a legal-service hypothesis, and clear conflicts before pursuit."
        priority, reasons = _amount_priority(amount)
        authoritative_ids = [{"scheme": "USASPENDING_AWARD_ID", "value": award_id}]
        if uei:
            authoritative_ids.append({"scheme": "UEI", "value": uei})
        opportunities.append(_opportunity(
            opportunity_id=_stable_id(f"usaspending-{vertical}", award_id),
            vertical=vertical,
            entity_id=uei or award_id,
            entity_type="organization_unverified",
            entity_name=recipient,
            location={
                "address": None,
                "city": place.get("city_name"),
                "county": place.get("county_name"),
                "state": place.get("state_code") or state,
                "postal_code": place.get("zip5"),
                "scope": "STATE",
            },
            authoritative_ids=authoritative_ids,
            signal_kind=signal_kind,
            title=title,
            summary=description or "USAspending reports an award record; open the cited record for details.",
            observed_at=event_date,
            measurements=measurements,
            priority=priority,
            reasons=reasons,
            next_action=next_action,
            citations=[{"source_id": source_id, "record_id": award_id,
                        "label": "USAspending award record", "url": record_url}],
            vertical_facts={
                "award_id": award_id,
                "uei": uei or None,
                "awarding_agency": row.get("Awarding Agency"),
                "awarding_sub_agency": row.get("Awarding Sub Agency"),
                "naics": row.get("NAICS") if vertical == "counsel" else None,
                "assistance_listings": row.get("Assistance Listings") if vertical == "finance" else None,
            },
        ))

    return {
        "opportunities": opportunities,
        "coverage": f"Federal {'loan' if vertical == 'finance' else 'contract'} awards with place of performance in {state} during the last 365 days",
        "citation": "https://api.usaspending.gov/docs/endpoints",
        "source_revision": response.headers.get("ETag") or response.headers.get("Last-Modified"),
        "upstream_observed_at": _utc_now(),
    }


def _fetch_federal_register(limit: int) -> dict[str, Any]:
    source_id = "federal_register_documents"
    query = urlencode({"per_page": limit, "order": "newest"})
    url = f"https://www.federalregister.gov/api/v1/documents.json?{query}"
    _assert_url_admitted(source_id, url)
    with _client() as client:
        response = client.get(url)
        response.raise_for_status()
        payload = response.json()

    opportunities: list[dict[str, Any]] = []
    for row in payload.get("results", []):
        if not isinstance(row, dict):
            continue
        document_number = _trim(row.get("document_number"), 80)
        title = _trim(row.get("title"), 300)
        if not document_number or not title:
            continue
        agencies = [
            _trim(agency.get("name"), 180)
            for agency in row.get("agencies", [])
            if isinstance(agency, dict) and agency.get("name")
        ]
        agency_label = ", ".join(agencies[:3]) or "Federal agency"
        document_type = _trim(row.get("type"), 80)
        priority = 72 if document_type in {"Rule", "Proposed Rule"} else 58
        reasons = [f"Official document type: {document_type or 'unavailable'}",
                   "Federal event is national; state scope is not applicable"]
        record_url = _admitted_record_url(source_id, row.get("html_url"))
        if record_url is None:
            continue
        opportunities.append(_opportunity(
            opportunity_id=_stable_id("federal-register", document_number),
            vertical="counsel",
            entity_id=document_number,
            entity_type="regulatory_event",
            entity_name=agency_label,
            location={"address": None, "city": None, "county": None, "state": None,
                      "postal_code": None, "scope": "NATIONAL"},
            authoritative_ids=[{"scheme": "FEDERAL_REGISTER_DOCUMENT_NUMBER", "value": document_number}],
            signal_kind="FEDERAL_REGULATORY_EVENT",
            title=title,
            summary=_trim(row.get("abstract"), 600) or "Open the official document for the complete text and effective dates.",
            observed_at=_trim(row.get("publication_date"), 40) or None,
            measurements=[_reported("Document type", document_type or None),
                          _reported("Publication date", row.get("publication_date"), "date")],
            priority=priority,
            reasons=reasons,
            next_action="Open the official document, identify affected organizations, and route any conclusion for attorney review.",
            citations=[{"source_id": source_id, "record_id": document_number,
                        "label": "Federal Register document", "url": record_url}],
            vertical_facts={"document_number": document_number, "document_type": document_type or None,
                            "agencies": agencies, "state_filter": "NOT_APPLICABLE"},
        ))
    return {
        "opportunities": opportunities,
        "coverage": "Newest Federal Register documents; national coverage",
        "reason": "A selected state does not narrow federal regulatory records.",
        "citation": "https://www.federalregister.gov/developers/documentation/api/v1",
        "source_revision": response.headers.get("ETag") or response.headers.get("Last-Modified"),
        "upstream_observed_at": _utc_now(),
    }


def _atom_text(summary: str) -> str:
    decoded = html_lib.unescape(summary or "")
    decoded = re.sub(r"<br\s*/?>", " · ", decoded, flags=re.IGNORECASE)
    return _trim(re.sub(r"<[^>]+>", " ", decoded), 650)


def _sec_priority(summary: str) -> tuple[int, list[str]]:
    rules = [
        ("Item 1.01", 16, "Material agreement item reported"),
        ("Item 1.02", 16, "Material agreement termination item reported"),
        ("Item 2.03", 14, "Direct financial obligation item reported"),
        ("Item 2.01", 14, "Asset acquisition or disposition item reported"),
        ("Item 5.02", 10, "Director or officer change item reported"),
    ]
    score = 52
    reasons = ["Recent SEC current report"]
    for marker, points, reason in rules:
        if marker in summary:
            score += points
            reasons.append(reason)
    reasons.append("Priority is a research sort, not investment advice")
    return min(94, score), reasons


def _fetch_sec_filings(limit: int) -> dict[str, Any]:
    source_id = "sec_recent_filings"
    count = max(10, min(40, limit))
    query = urlencode({"action": "getcurrent", "type": "8-K", "owner": "include",
                       "count": count, "output": "atom"})
    url = f"https://www.sec.gov/cgi-bin/browse-edgar?{query}"
    _assert_url_admitted(source_id, url)
    response = None
    last_transport_error: httpx.TransportError | None = None
    with _client() as client:
        for attempt in range(2):
            try:
                response = client.get(
                    url,
                    headers={"Accept": "application/atom+xml", "User-Agent": USER_AGENT},
                    timeout=min(6.0, _timeout_seconds()),
                )
                response.raise_for_status()
                break
            except httpx.TransportError as exc:
                last_transport_error = exc
                if attempt == 0:
                    time.sleep(0.35)
        else:
            if last_transport_error is None:
                raise RuntimeError("SEC request failed without a transport error")
            raise last_transport_error
    if response is None:
        raise RuntimeError("SEC response was not available")
    root = ET.fromstring(response.content)

    atom = {"a": "http://www.w3.org/2005/Atom"}
    opportunities: list[dict[str, Any]] = []
    for entry in root.findall("a:entry", atom):
        raw_title = _trim(entry.findtext("a:title", default="", namespaces=atom), 320)
        match = re.match(r"8-K\s+-\s+(.+?)\s+\((\d{6,10})\)\s+\(Filer\)", raw_title)
        if not match:
            continue
        company, cik = match.groups()
        link_node = entry.find("a:link[@rel='alternate']", atom)
        record_url = _admitted_record_url(
            source_id,
            link_node.attrib.get("href", "") if link_node is not None else "",
        )
        if record_url is None:
            continue
        summary = _atom_text(entry.findtext("a:summary", default="", namespaces=atom))
        accession_urn = _trim(entry.findtext("a:id", default="", namespaces=atom), 200)
        accession = accession_urn.rsplit("=", 1)[-1] if "=" in accession_urn else accession_urn
        updated = _trim(entry.findtext("a:updated", default="", namespaces=atom), 60) or None
        priority, reasons = _sec_priority(summary)
        opportunities.append(_opportunity(
            opportunity_id=_stable_id("sec-8k", accession or f"{cik}:{updated}"),
            vertical="finance",
            entity_id=cik.zfill(10),
            entity_type="sec_filer",
            entity_name=company,
            location={"address": None, "city": None, "county": None, "state": None,
                      "postal_code": None, "scope": "NATIONAL"},
            authoritative_ids=[{"scheme": "SEC_CIK", "value": cik.zfill(10)},
                               {"scheme": "SEC_ACCESSION", "value": accession}],
            signal_kind="SEC_8K_FILING",
            title=f"8-K filed by {company}",
            summary=summary or "SEC EDGAR reports a current filing; open the cited filing for its contents.",
            observed_at=updated,
            measurements=[_reported("Form", "8-K"), _reported("Filed or updated", updated, "timestamp")],
            priority=priority,
            reasons=reasons,
            next_action="Open the filing, verify the reported event, and document a finance research hypothesis for human review.",
            citations=[{"source_id": source_id, "record_id": accession,
                        "label": "SEC EDGAR filing", "url": record_url}],
            vertical_facts={"cik": cik.zfill(10), "accession": accession,
                            "form": "8-K", "state_filter": "NOT_APPLICABLE"},
        ))
        if len(opportunities) >= limit:
            break
    feed_updated = _trim(root.findtext("a:updated", default="", namespaces=atom), 60) or None
    return {
        "opportunities": opportunities,
        "coverage": "Recent SEC 8-K filings; national coverage",
        "reason": "A selected state does not narrow this SEC recent-filings feed.",
        "citation": "https://www.sec.gov/search-filings/edgar-application-programming-interfaces",
        "source_revision": feed_updated,
        "upstream_observed_at": feed_updated,
    }


async def _run_source(function: Callable[..., dict[str, Any]], *args: Any) -> dict[str, Any]:
    call = lambda: function(*args)
    return await anyio.to_thread.run_sync(call)


def _board_state(sources: list[dict[str, Any]]) -> str:
    states = [source.get("state") for source in sources]
    if states and all(state == "UNAVAILABLE" for state in states):
        return "UNAVAILABLE"
    if any(state in {"UNAVAILABLE", "STALE"} for state in states):
        return "PARTIAL"
    return "LIVE"


def _proof_payload(opportunities: list[dict[str, Any]], sources: list[dict[str, Any]]) -> dict[str, Any]:
    canonical = json.dumps(
        {"opportunities": opportunities, "sources": sources},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    github_sha = os.environ.get("GITHUB_SHA")
    hf_sha = os.environ.get("HF_SPACE_COMMIT_SHA") or os.environ.get("SPACE_COMMIT_SHA")
    if github_sha and hf_sha:
        release_state = "OBSERVED" if github_sha == hf_sha else "DRIFT"
    else:
        release_state = "UNAVAILABLE"
    return {
        "structural_hash": f"sha256:{hashlib.sha256(canonical).hexdigest()}",
        "hash_is_signature": False,
        "release_state": release_state,
        "github_sha": github_sha,
        "hf_space_commit": hf_sha,
        "attestation_url": os.environ.get("HF_DEPLOYMENT_ATTESTATION_URL"),
        "build_info_path": "/api/build-info",
        "evidence_clock": _utc_now(),
        "replayable_packets": len(opportunities),
    }


async def build_board(vertical: str, state: str, limit: int) -> dict[str, Any]:
    vertical = vertical.lower().strip()
    state = state.upper().strip()
    if vertical == "legal":
        vertical = "counsel"
    if vertical not in VERTICALS:
        raise ValueError("vertical must be one of: realestate, counsel, finance")
    if state not in EASTERN_STATES:
        raise ValueError("state must be an admitted Eastern U.S. postal code")
    limit = max(1, min(50, int(limit)))

    if vertical == "realestate":
        calls = [
            _run_source(_cached_source, "gsa_lease_inventory", state, 21600,
                        lambda: _fetch_gsa_leases(state, max(limit * 2, 30))),
        ]
    elif vertical == "counsel":
        calls = [
            _run_source(_cached_source, "federal_register_documents", "national", 900,
                        lambda: _fetch_federal_register(max(limit, 20))),
            _run_source(_cached_source, "usaspending_awards", f"counsel:{state}", 900,
                        lambda: _fetch_usaspending(state, "counsel", max(limit, 20))),
        ]
    else:
        calls = [
            _run_source(_cached_source, "sec_recent_filings", "8-k", 300,
                        lambda: _fetch_sec_filings(max(limit, 20))),
            _run_source(_cached_source, "usaspending_awards", f"finance:{state}", 900,
                        lambda: _fetch_usaspending(state, "finance", max(limit, 20))),
        ]

    results = await _gather(calls)
    sources = [result["source"] for result in results]
    opportunities: list[dict[str, Any]] = []
    seen: set[str] = set()
    for result in results:
        for item in result["opportunities"]:
            if item["id"] in seen:
                continue
            seen.add(item["id"])
            opportunities.append(item)
    opportunities.sort(
        key=lambda item: (-item["ranking"]["research_priority"], item["id"])
    )
    opportunities = opportunities[:limit]
    data_state = _board_state(sources)
    source_counts = {state_name: sum(1 for source in sources if source.get("state") == state_name)
                     for state_name in ("LIVE", "STALE", "UNAVAILABLE")}
    board = {
        "schema": SCHEMA,
        "vertical": vertical,
        "workspace": VERTICALS[vertical],
        "scope": {"state": state, "state_name": EASTERN_STATES[state], "region": "EASTERN_US"},
        "generated_at": _utc_now(),
        "data_state": data_state,
        "summary": {
            "observed_opportunities": len(opportunities),
            "public_research_only": len(opportunities),
            "call_ready": 0,
            "source_counts": source_counts,
            "zero_means_completed_query": data_state != "UNAVAILABLE" and len(opportunities) == 0,
        },
        "opportunities": opportunities,
        "sources": sources,
        "policy": {
            "default_permission": "PUBLIC_RESEARCH_ONLY",
            "contact_fields": "PROHIBITED",
            "automatic_outreach": "PROHIBITED",
            "source_manifest_path": "/api/a11oy/v1/opportunities/sources",
        },
    }
    board["proof"] = _proof_payload(opportunities, sources)
    return board


async def _gather(awaitables: list[Any]) -> list[Any]:
    results: list[Any] = [None] * len(awaitables)

    async def run_one(index: int, awaitable: Any) -> None:
        results[index] = await awaitable

    async with anyio.create_task_group() as group:
        for index, awaitable in enumerate(awaitables):
            group.start_soon(run_one, index, awaitable)
    return results


def source_policy() -> dict[str, Any]:
    if _POLICY_ERROR:
        return {"state": "UNAVAILABLE", "error": _POLICY_ERROR, "manifest": None}
    return {"state": "OBSERVED", "error": None, "manifest": copy.deepcopy(_SOURCE_POLICY)}


def register(app: FastAPI, ns: str = "a11oy") -> dict[str, Any]:
    """Mount the public page and read-only APIs before broad catch-all routes."""
    base = f"/api/{ns}/v1/opportunities"
    before = len(app.router.routes)

    @app.get("/opportunities", include_in_schema=False)
    async def opportunities_page():
        return FileResponse(PAGE_PATH, media_type="text/html")

    @app.get(base + "/board", include_in_schema=False)
    async def opportunities_board(vertical: str = "realestate", state: str = "NY", limit: int = 30):
        try:
            board = await build_board(vertical, state, limit)
        except (TypeError, ValueError) as exc:
            return JSONResponse({"detail": str(exc)}, status_code=422)
        status_code = 503 if board["data_state"] == "UNAVAILABLE" else 200
        return JSONResponse(board, status_code=status_code, headers={"Cache-Control": "no-store"})

    @app.get(base + "/sources", include_in_schema=False)
    async def opportunities_sources():
        payload = source_policy()
        return JSONResponse(payload, status_code=200 if payload["state"] == "OBSERVED" else 503,
                            headers={"Cache-Control": "no-store"})

    @app.get(base + "/healthz", include_in_schema=False)
    async def opportunities_health():
        return JSONResponse({
            "ok": _POLICY_ERROR is None and PAGE_PATH.is_file(),
            "service": "opportunity-graph",
            "schema": SCHEMA,
            "verticals": list(VERTICALS),
            "states": EASTERN_STATES,
            "policy_state": "OBSERVED" if _POLICY_ERROR is None else "UNAVAILABLE",
            "page_state": "OBSERVED" if PAGE_PATH.is_file() else "UNAVAILABLE",
            "external_sources_probed_by_healthz": False,
        })

    try:
        new_routes = app.router.routes[before:]
        del app.router.routes[before:]
        app.router.routes[0:0] = new_routes
        moved = len(new_routes)
    except Exception:
        moved = -1
    return {
        "mounted": base,
        "page": "/opportunities",
        "verticals": list(VERTICALS),
        "states": len(EASTERN_STATES),
        "routes_moved_before_catch_all": moved,
        "policy_state": "OBSERVED" if _POLICY_ERROR is None else "UNAVAILABLE",
    }
