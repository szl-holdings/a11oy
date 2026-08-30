# SPDX-License-Identifier: Apache-2.0
"""Offline contracts for the public Opportunity Graph."""

import asyncio
import io
import json
import zipfile
from datetime import date, timedelta

import httpx
from fastapi import FastAPI

import szl_opportunity_graph as graph


class FakeResponse:
    def __init__(self, *, payload=None, text="", content=b"", headers=None, status_code=200):
        self._payload = payload
        self.text = text
        self.content = content
        self.headers = headers or {}
        self.status_code = status_code

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeClient:
    def __init__(self, *, gets=None, post=None):
        self.gets = list(gets or [])
        self.post_response = post

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def get(self, _url, **_kwargs):
        response = self.gets.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response

    def post(self, _url, **_kwargs):
        return self.post_response


def _xlsx_bytes(headers, values):
    shared = list(headers)
    shared_lookup = {value: index for index, value in enumerate(shared)}
    for value in values:
        if isinstance(value, str) and value not in shared_lookup:
            shared_lookup[value] = len(shared)
            shared.append(value)

    def column(index):
        output = ""
        number = index + 1
        while number:
            number, remainder = divmod(number - 1, 26)
            output = chr(65 + remainder) + output
        return output

    header_cells = "".join(
        f'<c r="{column(index)}1" t="s"><v>{shared_lookup[value]}</v></c>'
        for index, value in enumerate(headers)
    )
    value_cells = []
    for index, value in enumerate(values):
        if value is None:
            continue
        cell = column(index)
        if isinstance(value, str):
            value_cells.append(f'<c r="{cell}2" t="s"><v>{shared_lookup[value]}</v></c>')
        else:
            value_cells.append(f'<c r="{cell}2"><v>{value}</v></c>')
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        + "".join(f"<si><t>{value}</t></si>" for value in shared)
        + "</sst>"
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData><row r="1">{header_cells}</row><row r="2">{"".join(value_cells)}</row></sheetData>'
        "</worksheet>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as workbook:
        workbook.writestr("xl/sharedStrings.xml", shared_xml)
        workbook.writestr("xl/worksheets/sheet1.xml", sheet_xml)
    return buffer.getvalue()


def _route(app, path):
    for route in app.router.routes:
        if getattr(route, "path", None) == path:
            return route
    raise AssertionError(f"route not found: {path}")


def _source_result(source_id, opportunities=None, state="LIVE"):
    return {
        "opportunities": opportunities or [],
        "source": {
            "schema": graph.SOURCE_SCHEMA,
            "source_id": source_id,
            "label": source_id,
            "state": state,
            "observed_at": "2026-08-29T12:00:00Z",
            "record_count": len(opportunities or []),
            "coverage": "test contract",
            "citation": "https://example.gov/source",
            "latency_ms": 1,
            "cache_status": "MISS",
            "cache_age_s": 0,
            "access": "PUBLIC_NO_KEY",
            "permitted_use": "ORGANIZATION_RESEARCH",
            "contact_data": False,
            "source_revision": "r1",
            "upstream_observed_at": "2026-08-29T12:00:00Z",
        },
    }


def test_source_policy_admits_only_official_read_only_sources():
    payload = graph.source_policy()
    assert payload["state"] == "OBSERVED"
    manifest = payload["manifest"]
    assert manifest["public_projection"]["contact_fields"] == "PROHIBITED"
    assert manifest["public_projection"]["automatic_outreach"] == "PROHIBITED"
    admitted = {item["id"]: item for item in manifest["admitted"]}
    assert set(admitted) == {
        "gsa_lease_inventory",
        "usaspending_awards",
        "sec_recent_filings",
        "federal_register_documents",
    }
    assert all(item["contact_data"] is False for item in admitted.values())
    blocked = {item["id"] for item in manifest["blocked"]}
    assert {"linkedin_profiles", "finra_brokercheck_marketing", "sam_gov_page_scraping"} <= blocked


def test_gsa_workbook_becomes_property_research_without_contact_data(monkeypatch):
    expiration = date.today() + timedelta(days=180)
    serial = (expiration - date(1899, 12, 30)).days
    headers = [
        "Lease Num", "City", "County", "Address", "State", "ZipCode",
        "Lease Expiration", "Latest Action affecting Term", "Lease Agreement RSF",
        "Current Annual Rent", "Field Office Name",
    ]
    workbook = _xlsx_bytes(
        headers,
        ["LNY00001", "ALBANY", "ALBANY", "1 TEST PLAZA", "NY", "12207",
         serial, "Renewal", 0, 4100000, "NORTH SERVICE CENTER"],
    )
    page = '<a href="/system/files/July-2026-External.xlsx">Current inventory</a>'
    fake = FakeClient(gets=[
        FakeResponse(text=page),
        FakeResponse(content=workbook, headers={"Last-Modified": "Sat, 29 Aug 2026 12:00:00 GMT"}),
    ])
    monkeypatch.setattr(graph, "_client", lambda: fake)
    payload = graph._fetch_gsa_leases("NY", 10)
    assert payload["source_revision"] == "July-2026-External.xlsx"
    assert len(payload["opportunities"]) == 1
    item = payload["opportunities"][0]
    assert item["entity"]["id"] == "LNY00001"
    assert item["permission"] == {
        "state": "PUBLIC_RESEARCH_ONLY",
        "call_ready": False,
        "reasons": item["permission"]["reasons"],
    }
    encoded = json.dumps(item).lower()
    assert "email" not in encoded
    assert "phone" not in encoded
    assert "lessor" not in encoded
    assert "0 square feet" not in item["signal"]["summary"]
    assert "Lease agreement area" not in {
        measurement["label"] for measurement in item["signal"]["measurements"]
    }
    assert item["evidence"]["citations"][0]["url"].endswith("July-2026-External.xlsx")


def test_usaspending_contract_normalizes_to_counsel_research(monkeypatch):
    response = FakeResponse(payload={"results": [{
        "Award ID": "ABC123",
        "Recipient Name": "EXAMPLE SERVICES LLC",
        "Award Amount": 2500000,
        "Awarding Agency": "General Services Administration",
        "Awarding Sub Agency": "Public Buildings Service",
        "Description": "FACILITY SERVICES",
        "Last Modified Date": "2026-08-20 10:20:00",
        "Recipient UEI": "UEI123",
        "Primary Place of Performance": {"city_name": "BUFFALO", "state_code": "NY", "zip5": "14202"},
        "NAICS": {"code": "541611", "description": "Management consulting"},
        "generated_internal_id": "CONT_AWD_ABC123",
    }]})
    monkeypatch.setattr(graph, "_client", lambda: FakeClient(post=response))
    payload = graph._fetch_usaspending("NY", "counsel", 10)
    item = payload["opportunities"][0]
    assert item["vertical"] == "counsel"
    assert item["entity"]["name"] == "EXAMPLE SERVICES LLC"
    assert item["permission"]["call_ready"] is False
    assert item["ranking"]["method"] == "TRANSPARENT_RULES_NOT_DEAL_PROBABILITY"
    assert item["evidence"]["citations"][0]["url"].startswith("https://www.usaspending.gov/award/")


def test_sec_feed_normalizes_reported_items_without_advice(monkeypatch):
    atom = b'''<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <updated>2026-08-29T12:00:00-04:00</updated>
      <entry>
        <title>8-K - Example Holdings, Inc. (0001234567) (Filer)</title>
        <link rel="alternate" href="https://www.sec.gov/Archives/example-index.htm"/>
        <summary type="html">&lt;b&gt;Filed:&lt;/b&gt; 2026-08-29&lt;br&gt;Item 1.01: Entry into a Material Definitive Agreement</summary>
        <updated>2026-08-29T11:00:00-04:00</updated>
        <id>urn:tag:sec.gov,2008:accession-number=0001234567-26-000001</id>
      </entry>
      <entry>
        <title>8-K - Untrusted Link Corp. (0007654321) (Filer)</title>
        <link rel="alternate" href="https://example.com/not-sec-evidence"/>
        <summary type="html">Item 1.01: Entry into a Material Definitive Agreement</summary>
        <updated>2026-08-29T10:00:00-04:00</updated>
        <id>urn:tag:sec.gov,2008:accession-number=0007654321-26-000001</id>
      </entry>
    </feed>'''
    monkeypatch.setattr(
        graph,
        "_client",
        lambda: FakeClient(gets=[httpx.ReadTimeout("transient"), FakeResponse(content=atom)]),
    )
    payload = graph._fetch_sec_filings(10)
    assert len(payload["opportunities"]) == 1
    item = payload["opportunities"][0]
    assert item["entity"]["id"] == "0001234567"
    assert "Material agreement item reported" in item["ranking"]["reasons"]
    assert "investment advice" in item["ranking"]["reasons"][-1].lower()
    assert item["permission"]["call_ready"] is False


def test_federal_register_is_national_and_requires_attorney_review(monkeypatch):
    response = FakeResponse(payload={"results": [
        {
            "document_number": "2026-12345",
            "title": "Reporting Requirements for Covered Organizations",
            "type": "Proposed Rule",
            "abstract": "The agency proposes reporting changes.",
            "publication_date": "2026-08-29",
            "html_url": "https://www.federalregister.gov/documents/2026/08/29/example",
            "agencies": [{"name": "Example Federal Agency"}],
        },
        {
            "document_number": "2026-99999",
            "title": "Untrusted citation host",
            "type": "Notice",
            "publication_date": "2026-08-29",
            "html_url": "https://example.com/not-federal-register-evidence",
            "agencies": [{"name": "Example Federal Agency"}],
        },
    ]})
    monkeypatch.setattr(graph, "_client", lambda: FakeClient(gets=[response]))
    opportunities = graph._fetch_federal_register(10)["opportunities"]
    assert len(opportunities) == 1
    item = opportunities[0]
    assert item["entity"]["location"]["scope"] == "NATIONAL"
    assert item["vertical_facts"]["state_filter"] == "NOT_APPLICABLE"
    assert "attorney review" in item["workflow"]["next_action"].lower()


def test_board_keeps_truth_axes_separate(monkeypatch):
    graph._CACHE.clear()
    item = graph._opportunity(
        opportunity_id="o:1", vertical="realestate", entity_id="e:1",
        entity_type="property", entity_name="1 Source Plaza",
        location={"state": "NY", "scope": "STATE"}, authoritative_ids=[],
        signal_kind="LEASE_EXPIRATION", title="Lease event", summary="Reported event",
        observed_at="2026-08-29", measurements=[], priority=80,
        reasons=["Reported event"], next_action="Verify the source.",
        citations=[{"source_id": "gsa_lease_inventory", "record_id": "1", "label": "GSA", "url": "https://www.gsa.gov/example"}],
        vertical_facts={},
    )
    monkeypatch.setattr(
        graph,
        "_cached_source",
        lambda source_id, *_args: _source_result(source_id, [item]),
    )
    board = asyncio.run(graph.build_board("realestate", "NY", 30))
    assert board["data_state"] == "LIVE"
    assert board["summary"]["observed_opportunities"] == 1
    assert board["summary"]["public_research_only"] == 1
    assert board["summary"]["call_ready"] == 0
    assert board["opportunities"][0]["evidence"]["state"] == "OBSERVED"
    assert board["proof"]["hash_is_signature"] is False


def test_all_sources_unavailable_returns_503_not_a_false_zero(monkeypatch):
    monkeypatch.setattr(
        graph,
        "_cached_source",
        lambda source_id, *_args: _source_result(source_id, state="UNAVAILABLE"),
    )
    app = FastAPI()
    graph.register(app)
    endpoint = _route(app, "/api/a11oy/v1/opportunities/board").endpoint
    response = asyncio.run(endpoint(vertical="finance", state="NY", limit=30))
    payload = json.loads(response.body)
    assert response.status_code == 503
    assert payload["data_state"] == "UNAVAILABLE"
    assert payload["summary"]["observed_opportunities"] == 0
    assert payload["summary"]["zero_means_completed_query"] is False


def test_routes_precede_broad_catch_all():
    app = FastAPI()

    @app.get("/{path:path}")
    async def catch_all(path: str):
        return {"path": path}

    status = graph.register(app)
    first_paths = [getattr(route, "path", None) for route in app.router.routes[:4]]
    assert "/opportunities" in first_paths
    assert "/api/a11oy/v1/opportunities/board" in first_paths
    assert status["routes_moved_before_catch_all"] == 4


def test_page_is_mobile_first_no_cdn_and_has_visible_state_control():
    page = graph.PAGE_PATH.read_text(encoding="utf-8")
    assert 'name="viewport"' in page
    assert 'id="state-select"' in page
    assert 'id="queue"' in page
    assert 'data-vertical="realestate"' in page
    assert 'data-vertical="counsel"' in page
    assert 'data-vertical="finance"' in page
    assert "PUBLIC_RESEARCH_ONLY" in page
    assert "escapeHtml" in page
    assert "prefers-reduced-motion" in page
    assert "<script src=" not in page
    assert "<link rel=\"stylesheet\"" not in page
