# SPDX-License-Identifier: Apache-2.0
"""Exercise registered HTTP routes, with only external feed functions replaced."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

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
    source_clock = "2026-09-13T02:40:00+00:00"
    raw = {
        "value": None if source_state == "cold" else {"items": [{"rate": 4.25}]},
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
    observed_at = "2026-10-07T19:00:00+00:00"
    live = {
        "value": {"items": [{"accession": "observed"}]},
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
