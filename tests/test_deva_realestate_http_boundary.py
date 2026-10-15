# SPDX-License-Identifier: Apache-2.0
"""Exercise registered HTTP routes, with only external feed functions replaced."""
from __future__ import annotations

import json
import time
from copy import deepcopy
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import a11oy_deva_feeds as deva


@pytest.mark.parametrize(
    ("route", "field", "required_feed"),
    [
        ("pulse", "rates", "feed_treasury"),
        ("ownership", "sec_fts", "feed_sec_realestate"),
        ("deal", "rates", "feed_treasury"),
    ],
)
@pytest.mark.parametrize("source_state", ["cold", "stale", "live"])
def test_registered_realestate_http_truth_boundary(
    monkeypatch: pytest.MonkeyPatch,
    route: str,
    field: str,
    required_feed: str,
    source_state: str,
) -> None:
    source_clock = datetime.now(timezone.utc).isoformat()
    raw = {
        "value": None if source_state == "cold" else {
            "items": [{"rate": 4.25}], "filings": [{"form": "10-K"}],
        },
        "freshness": {
            "status": "unavailable" if source_state == "cold" else source_state,
        },
    }
    if source_state != "cold":
        raw["freshness"].update(fetched_at=source_clock, age_s=45.0)
    if source_state != "live":
        raw["freshness"]["error"] = "ReadTimeout: synthetic source failure"
    original = deepcopy(raw)
    calls: list[str] = []

    def fake_feed(name: str):
        def read(*_args, **_kwargs):
            calls.append(name)
            return raw
        return read

    # Keep real route registration, async/thread dispatch, JSON serialization,
    # normalization and deterministic forecast. No real external feed is invoked.
    for name in (
        "feed_hpd_violations", "feed_dob_violations", "feed_treasury",
        "feed_sec_realestate", "feed_sec_submissions",
    ):
        monkeypatch.setattr(deva, name, fake_feed(name))

    app = FastAPI()
    deva.register(app)
    before = datetime.now(timezone.utc)
    with TestClient(app) as client:
        response = client.get(
            f"/api/a11oy/v1/deva/re/{route}",
            params={"violations": 0, "class_c": 0} if route == "deal" else None,
        )
    after = datetime.now(timezone.utc)

    assert response.status_code == (503 if route == "ownership" and source_state == "cold" else 200)
    payload = response.json()
    assert payload["tab"] == route
    assert required_feed in calls
    envelope = payload[field]
    freshness = envelope["freshness"]
    assert envelope["value"] == original["value"]
    assert raw == original, "public formatting must not mutate the feed/cache envelope"

    if source_state == "cold":
        assert freshness["status"] == "UNAVAILABLE"
        observed = datetime.fromisoformat(freshness["fetched_at"].replace("Z", "+00:00"))
        assert observed.tzinfo is not None
        assert before <= observed <= after
    else:
        assert freshness["status"] == ("cached" if source_state == "stale" else "live")
        assert freshness["fetched_at"] == source_clock
    if source_state != "live":
        assert freshness["error"] == original["freshness"]["error"]

    if route == "ownership":
        assert set(payload["reits"]) == {
            "Vornado", "Boston Properties", "SL Green", "Realty Income",
        }
        for child in payload["reits"].values():
            assert child["value"] == envelope["value"]
            assert child["freshness"]["status"] == freshness["status"]
            if source_state == "cold":
                child_observed = datetime.fromisoformat(
                    child["freshness"]["fetched_at"].replace("Z", "+00:00")
                )
                assert before <= child_observed <= after
                assert child["freshness"]["error"] == freshness["error"]
            else:
                assert child == envelope

    if route == "deal":
        # The source-envelope repair does not change the existing modeled fallback.
        forecast = payload["forecast"]
        assert "SIMULATED" in forecast["label"]
        assert forecast["drivers"]["rate_pct"] == (4.0 if source_state == "cold" else 4.25)


@pytest.mark.parametrize("unavailable_cik", [
    "0000899689", "0001037540", "0001040971", "0000726728",
])
def test_ownership_cold_child_fails_closed_without_masking_live_peers(
    monkeypatch: pytest.MonkeyPatch,
    unavailable_cik: str,
) -> None:
    observed_at = datetime.now(timezone.utc).isoformat()
    live = {
        "value": {"items": [{"accession": "observed"}], "filings": [{"form": "10-K"}]},
        "freshness": {"status": "live", "fetched_at": observed_at, "age_s": 0.0},
    }
    unavailable = {
        "value": None,
        "freshness": {"status": "unavailable", "error": "ReadTimeout: SEC source did not answer"},
    }
    original_unavailable = deepcopy(unavailable)

    monkeypatch.setattr(deva, "feed_sec_realestate", lambda *_args: live)
    monkeypatch.setattr(
        deva, "feed_sec_submissions",
        lambda cik: unavailable if cik == unavailable_cik else live,
    )
    app = FastAPI()
    deva.register(app)
    before = datetime.now(timezone.utc)
    with TestClient(app) as client:
        response = client.get("/api/a11oy/v1/deva/re/ownership")
    after = datetime.now(timezone.utc)

    assert response.status_code == 503
    payload = response.json()
    assert payload["tab"] == "ownership"
    assert payload["sec_fts"] == live
    assert set(payload["reits"]) == {
        "Vornado", "Boston Properties", "SL Green", "Realty Income",
    }
    names_by_cik = {
        "0000899689": "Vornado", "0001037540": "Boston Properties",
        "0001040971": "SL Green", "0000726728": "Realty Income",
    }
    unavailable_name = names_by_cik[unavailable_cik]
    for name, child in payload["reits"].items():
        if name != unavailable_name:
            assert child == live
    failed = payload["reits"][unavailable_name]
    assert failed["value"] is None
    assert failed["freshness"]["status"] == "UNAVAILABLE"
    assert failed["freshness"]["error"] == original_unavailable["freshness"]["error"]
    observed = datetime.fromisoformat(failed["freshness"]["fetched_at"].replace("Z", "+00:00"))
    assert observed.tzinfo is not None
    assert before <= observed <= after
    assert unavailable == original_unavailable


@pytest.mark.parametrize("failure", [
    "sec_cold", "child_unavailable_with_value", "child_unavailable_with_clock",
    "child_invalid_status", "child_missing_clock",
    "child_stale_without_raw_clock",
    "child_invalid_filings", "child_stale_clock", "child_future_clock",
])
def test_ownership_rejects_required_source_contract_failures(
    monkeypatch: pytest.MonkeyPatch,
    failure: str,
) -> None:
    observed_at = datetime.now(timezone.utc).isoformat()
    sec = {
        "value": {"items": [{"accession": "observed"}]},
        "freshness": {"status": "live", "fetched_at": observed_at},
    }
    cik_to_name = {
        "0000899689": "Vornado", "0001037540": "Boston Properties",
        "0001040971": "SL Green", "0000726728": "Realty Income",
    }
    submissions = {
        cik: {
            "value": {"filings": [{"form": "10-K"}]},
            "freshness": {"status": "live", "fetched_at": observed_at},
        }
        for cik in cik_to_name
    }
    if failure == "sec_cold":
        sec = {
            "value": None,
            "freshness": {"status": "unavailable", "error": "SEC search timeout"},
        }
    else:
        child = submissions["0001040971"]
        if failure == "child_unavailable_with_value":
            child["freshness"] = {"status": "UNAVAILABLE", "error": "SEC submissions timeout"}
        elif failure == "child_unavailable_with_clock":
            child["freshness"] = {
                "status": "unavailable", "fetched_at": observed_at,
                "error": "SEC submissions timeout",
            }
        elif failure == "child_invalid_status":
            child["freshness"]["status"] = ["live"]
        elif failure == "child_missing_clock":
            del child["freshness"]["fetched_at"]
        elif failure == "child_stale_without_raw_clock":
            child["freshness"] = {
                "status": "stale", "age_s": 45.0, "error": "SEC refresh failed",
            }
        elif failure == "child_invalid_filings":
            child["value"]["filings"] = "not an observed filing array"
        elif failure == "child_stale_clock":
            child["freshness"]["fetched_at"] = (
                datetime.now(timezone.utc) - timedelta(hours=2)
            ).isoformat()
        elif failure == "child_future_clock":
            child["freshness"]["fetched_at"] = (
                datetime.now(timezone.utc) + timedelta(minutes=6)
            ).isoformat()
    original_sec = deepcopy(sec)
    original_submissions = deepcopy(submissions)
    monkeypatch.setattr(deva, "feed_sec_realestate", lambda *_args: sec)
    monkeypatch.setattr(deva, "feed_sec_submissions", lambda cik: submissions[cik])

    app = FastAPI()
    deva.register(app)
    with TestClient(app) as client:
        response = client.get("/api/a11oy/v1/deva/re/ownership")

    assert response.status_code == 503
    payload = response.json()
    assert payload["tab"] == "ownership"
    assert set(payload["reits"]) == set(cik_to_name.values())
    if failure == "sec_cold":
        assert payload["sec_fts"]["value"] is None
        assert payload["sec_fts"]["freshness"]["status"] == "UNAVAILABLE"
        assert all(child["freshness"]["status"] == "live" for child in payload["reits"].values())
    else:
        assert payload["sec_fts"] == original_sec
        assert all(
            payload["reits"][name]["freshness"]["status"] == "live"
            for cik, name in cik_to_name.items() if cik != "0001040971"
        )
        assert payload["reits"]["SL Green"]["value"] == original_submissions["0001040971"]["value"]
        if failure in {"child_unavailable_with_value", "child_unavailable_with_clock", "child_invalid_status"}:
            assert payload["reits"]["SL Green"]["freshness"]["status"] == "UNAVAILABLE"
            assert payload["reits"]["SL Green"]["freshness"]["error"] == (
                original_submissions["0001040971"]["freshness"].get("error")
                or "source returned unsupported freshness status"
            )
            if "fetched_at" in original_submissions["0001040971"]["freshness"]:
                assert payload["reits"]["SL Green"]["freshness"]["fetched_at"] == (
                    original_submissions["0001040971"]["freshness"]["fetched_at"]
                )
    assert sec == original_sec
    assert submissions == original_submissions


@pytest.fixture
def hpd_source(monkeypatch):
    source = {"payload": [], "status": 200, "calls": []}

    class SourceClient:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def get(self, url):
            source["calls"].append(url)
            return httpx.Response(
                source["status"], request=httpx.Request("GET", url),
                content=json.dumps(source["payload"]).encode("utf-8"),
                headers={"Content-Type": "application/json"},
            )

    monkeypatch.setattr(deva, "_HAS_VF", False)
    monkeypatch.setattr(deva, "_CACHE", {})
    monkeypatch.setattr(deva, "_INFLIGHT", {})
    monkeypatch.setattr(deva, "_client", lambda *_args, **_kwargs: SourceClient())
    return source


def _row(**values):
    return {
        "violationid": "12345", "inspectiondate": "2026-10-01T00:00:00.000",
        "latitude": "40.7128", "longitude": "-74.0060", "class": "C",
        **values,
    }


@pytest.mark.parametrize("payload", [
    {"error": True, "message": "source query could not be evaluated"},
    {"items": []}, "upstream proxy HTML", None, 17, True,
])
def test_non_array_hpd_payload_is_unavailable_not_live_empty(hpd_source, payload):
    hpd_source["payload"] = payload
    result = deva.feed_hpd_violations(1)
    assert result["value"] is None
    assert result["freshness"]["status"] == "unavailable"
    assert "HPD source must return a JSON array" in result["freshness"]["error"]
    assert not deva._CACHE


@pytest.mark.parametrize("bad_row", [None, "bad row", 1, ["row"]])
def test_non_object_hpd_rows_fail_closed(hpd_source, bad_row):
    hpd_source["payload"] = [_row(), bad_row]
    result = deva.feed_hpd_violations(2)
    assert result["value"] is None
    assert result["freshness"]["status"] == "unavailable"
    assert "HPD source rows must be JSON objects" in result["freshness"]["error"]
    assert not deva._CACHE


def test_observed_empty_hpd_array_is_distinct_from_a_failed_source(hpd_source):
    result = deva.feed_hpd_violations(1)
    assert result["value"] == {"items": []}
    assert result["freshness"]["status"] == "live"
    assert datetime.fromisoformat(result["freshness"]["fetched_at"]).tzinfo is not None


def test_malformed_refresh_keeps_last_good_rows_and_original_clock(hpd_source):
    hpd_source["payload"] = [_row()]
    original = deepcopy(deva.feed_hpd_violations(1))
    for record in deva._CACHE.values():
        record["fetched_at"] = time.time() - 1000
    hpd_source["payload"] = {"error": "malformed upstream success response"}
    raw = deva.feed_hpd_violations(1)
    public = deva._readiness_public_source(raw)
    assert raw["freshness"]["status"] == "stale"
    assert public["freshness"]["status"] == "cached"
    assert public["value"] == original["value"]
    assert public["freshness"]["fetched_at"] == original["freshness"]["fetched_at"]
    assert "HPD source must return a JSON array" in public["freshness"]["error"]
    assert len(hpd_source["calls"]) == 2


@pytest.mark.parametrize(("latitude", "longitude"), [
    ("NaN", "-74"), ("Infinity", "-74"), ("40", "-Infinity"),
    (float("nan"), -74), (40, float("inf")),
    ("90.1", "-74"), ("40", "-180.1"),
    (True, "-74"), ("40", False), ("not a location", "-74"),
])
def test_unmappable_coordinates_do_not_break_registered_pulse_json(
    monkeypatch, hpd_source, latitude, longitude,
):
    hpd_source["payload"] = [_row(latitude=latitude, longitude=longitude)]
    peer = {
        "value": {"items": []},
        "freshness": {"status": "live", "fetched_at": datetime.now(timezone.utc).isoformat()},
    }
    monkeypatch.setattr(deva, "feed_dob_violations", lambda *_args: peer)
    monkeypatch.setattr(deva, "feed_treasury", lambda *_args: peer)
    app = FastAPI()
    deva.register(app)
    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/a11oy/v1/deva/re/pulse")
    assert response.status_code == 200
    payload = response.json()
    json.dumps(payload, allow_nan=False)
    envelope = payload["hpd"]
    assert envelope["freshness"]["status"] == "live"
    item = envelope["value"]["items"][0]
    assert item["id"] == "12345"
    assert item["lat"] is None and item["lng"] is None
    assert payload["dob"] == peer
    assert payload["rates"] == peer


@pytest.mark.parametrize(("latitude", "longitude"), [
    ("40.7128", "-74.0060"), ("0", "0"), (0, 0), ("90", "180"), ("-90", "-180"),
])
def test_valid_coordinates_are_preserved(hpd_source, latitude, longitude):
    hpd_source["payload"] = [_row(latitude=latitude, longitude=longitude)]
    result = deva.feed_hpd_violations(1)
    item = result["value"]["items"][0]
    assert item["lat"] == float(latitude)
    assert item["lng"] == float(longitude)
    assert result["freshness"]["status"] == "live"


@pytest.mark.parametrize(("coordinates", "expected"), [
    ({}, (None, None)),
    ({"latitude": None, "longitude": None}, (None, None)),
    ({"latitude": "", "longitude": ""}, (None, None)),
    ({"latitude": None, "longitude": "-74"}, (None, -74.0)),
    ({"latitude": "40", "longitude": ""}, (40.0, None)),
])
def test_missing_coordinates_remain_missing_without_discarding_source_row(
    hpd_source, coordinates, expected,
):
    row = _row()
    row.pop("latitude")
    row.pop("longitude")
    row.update(coordinates)
    hpd_source["payload"] = [row]
    result = deva.feed_hpd_violations(1)
    item = result["value"]["items"][0]
    assert item["id"] == "12345"
    assert (item["lat"], item["lng"]) == expected
    assert result["freshness"]["status"] == "live"


@pytest.mark.parametrize("warm_cache", [False, True])
def test_http_502_remains_an_upstream_failure(hpd_source, warm_cache):
    original = None
    if warm_cache:
        hpd_source["payload"] = [_row()]
        original = deepcopy(deva.feed_hpd_violations(1))
        for record in deva._CACHE.values():
            record["fetched_at"] = time.time() - 1000
    hpd_source["status"] = 502
    hpd_source["payload"] = {"error": "Bad Gateway"}
    raw = deva.feed_hpd_violations(1)
    public = deva._readiness_public_source(raw)
    assert "502 Bad Gateway" in public["freshness"]["error"]
    assert public["freshness"]["status"] == ("cached" if warm_cache else "UNAVAILABLE")
    if original is None:
        assert public["value"] is None
    else:
        assert public["value"] == original["value"]
        assert public["freshness"]["fetched_at"] == original["freshness"]["fetched_at"]
