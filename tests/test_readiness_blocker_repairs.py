# SPDX-License-Identifier: Apache-2.0
"""Regression coverage for the bounded live-feed readiness endpoint."""

from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path
import threading
import time
from types import SimpleNamespace

import a11oy_live_feeds
import pytest
import serve


def _kev(cve_id):
    return {
        "cveID": cve_id,
        "vendorProject": "Example Vendor",
        "product": "Example Product",
        "vulnerabilityName": "Example Vulnerability",
        "cwes": ["CWE-79"],
        "knownRansomwareCampaignUse": "Unknown",
        "dateAdded": "2026-08-26",
    }


def _live_kev_payload(cve_id):
    return {
        "source": "CISA Known Exploited Vulnerabilities Catalog",
        "source_url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        "mode": "live",
        "fetched_at": "2026-08-26T16:00:00Z",
        "data": {"vulnerabilities": [_kev(cve_id)]},
    }


def test_kevgate_mixed_live_feed_remains_sample_labeled(
    monkeypatch,
):
    payload = {
        "source": "CISA Known Exploited Vulnerabilities Catalog",
        "source_url": (
            "https://www.cisa.gov/sites/default/files/feeds/"
            "known_exploited_vulnerabilities.json"
        ),
        "mode": "live",
        "fetched_at": "2026-08-26T15:00:00Z",
        "data": {
            "catalogVersion": "2026.08.26",
            "count": 2,
            "vulnerabilities": [_kev("CVE-2026-0001"), _kev("CVE-2026-0002")],
        },
    }
    monkeypatch.setattr(serve._kl_live, "get_feed", lambda _feed: payload)
    monkeypatch.setattr(
        serve,
        "_kl_epss_map",
        lambda _cves: {"CVE-2026-0001": (0.9, 0.99)},
    )
    monkeypatch.setattr(
        serve,
        "_KL_CVSS",
        {
            "CVE-2026-0001": {
                "cvss": 9.8,
                "severity": "CRITICAL",
                "vector": "CVSS:3.1",
                "src": "nvd",
                "ts": time.time(),
            }
        },
    )

    rows, meta = serve._kl_live_rows()

    assert meta["mode"] == "live"
    assert meta["data_kind"] == "sample"
    assert meta["source"] == payload["source"]
    assert meta["epss_source_rows"] == 1
    assert meta["cvss_source_rows"] == 1
    assert "epss_live_rows" not in meta
    assert "cvss_live_rows" not in meta
    assert "FIRST.org EPSS evidence (cache up to 6h, 1/2 rows)" in meta[
        "enrichment_provenance"
    ]
    assert "NVD-backed CVSS cache (1/2 rows" in meta["enrichment_provenance"]
    assert "derived-sample" in meta["enrichment_provenance"]
    assert {row["epss_src"] for row in rows} == {"first.org", "derived"}
    assert {row["cvss_src"] for row in rows} == {"nvd", "derived"}
    assert {row["data_kind"] for row in rows} == {"cached", "sample"}
    assert all("catalog=live" in row["evidence_detail"] for row in rows)

    mixed_route = json.loads(asyncio.run(serve._sec_kevgate(limit=2)).body)
    assert mixed_route["data_kind"] == "sample"
    assert {item["data_kind"] for item in mixed_route["items"]} == {
        "cached",
        "sample",
    }
    assert {item["cvss_src"] for item in mixed_route["items"]} == {
        "nvd",
        "derived",
    }

    serve._KL_CVSS["CVE-2026-0002"] = {
        "cvss": 8.8,
        "severity": "HIGH",
        "vector": "CVSS:3.1",
        "src": "nvd",
        "ts": time.time(),
    }
    monkeypatch.setattr(
        serve,
        "_kl_epss_map",
        lambda _cves: {
            "CVE-2026-0001": (0.9, 0.99),
            "CVE-2026-0002": (0.8, 0.95),
        },
    )
    fully_sourced = json.loads(asyncio.run(serve._sec_kevgate(limit=2)).body)
    assert fully_sourced["data_kind"] == "cached"
    assert {item["data_kind"] for item in fully_sourced["items"]} == {"cached"}


def test_kevgate_cached_payload_does_not_claim_live_or_hide_samples(monkeypatch):
    payload = {
        "source": "CISA cached test evidence",
        "source_url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        "mode": "cached",
        "fetched_at": "2026-08-25T15:00:00Z",
        "cache_note": "upstream unreachable; serving last good value",
        "data": {"vulnerabilities": [_kev("CVE-2026-0003")]},
    }
    monkeypatch.setattr(serve._kl_live, "get_feed", lambda _feed: payload)
    monkeypatch.setattr(serve, "_kl_epss_map", lambda _cves: {})
    monkeypatch.setattr(serve, "_KL_CVSS", {})

    rows, meta = serve._kl_live_rows()

    assert meta["mode"] == "cached"
    assert meta["data_kind"] == "sample"
    assert meta["source"] == payload["source"]
    assert meta["cache_note"] == payload["cache_note"]
    assert meta["enrichment_provenance"].startswith("cached KEV IDs/dates/vendors")
    assert rows[0]["data_kind"] == "sample"
    assert rows[0]["evidence_detail"] == (
        "catalog=cached; epss=derived-sample; cvss=derived-sample"
    )


def test_kevgate_cached_bundled_payload_never_promotes_to_cached(monkeypatch):
    monkeypatch.setattr(serve._kl_live, "_CACHE", {})
    monkeypatch.setattr(
        serve._kl_live,
        "_load_snapshot",
        lambda _feed: {"vulnerabilities": [_kev("CVE-2026-0005")]},
    )
    payload = serve._kl_live.get_cached_feed("kev", OSError("upstream down"))
    assert payload["mode"] == "cached"
    assert payload["fetched_at"] == "bundled-snapshot"
    assert "bundled in-image snapshot" in payload["cache_note"]
    monkeypatch.setattr(serve._kl_live, "get_feed", lambda _feed: payload)
    monkeypatch.setattr(
        serve,
        "_kl_epss_map",
        lambda _cves: {"CVE-2026-0005": (0.91, 0.99)},
    )
    monkeypatch.setattr(
        serve,
        "_KL_CVSS",
        {
            "CVE-2026-0005": {
                "cvss": 9.8,
                "severity": "CRITICAL",
                "vector": "CVSS:3.1",
                "src": "nvd",
                "ts": time.time(),
            }
        },
    )

    rows, meta = serve._kl_live_rows()

    assert meta["mode"] == "cached"
    assert meta["fetched_at"] == "bundled-snapshot"
    assert meta["data_kind"] == "sample"
    assert meta["enrichment_provenance"].startswith(
        "bundled-snapshot KEV IDs/dates/vendors"
    )
    assert rows[0]["epss_src"] == "first.org"
    assert rows[0]["cvss_src"] == "nvd"
    assert rows[0]["data_kind"] == "sample"
    assert rows[0]["evidence_detail"] == (
        "catalog=bundled-snapshot; epss=first.org-cache; cvss=nvd-cache"
    )

    route = json.loads(asyncio.run(serve._sec_kevgate(limit=1)).body)
    assert route["data_kind"] == "sample"
    assert route["items"][0]["data_kind"] == "sample"
    assert route["items"][0]["evidence_detail"].startswith(
        "catalog=bundled-snapshot;"
    )


def test_kevgate_last_good_cached_feed_can_remain_source_backed(monkeypatch):
    payload = {
        "source": "CISA cached test evidence",
        "source_url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        "mode": "cached",
        "fetched_at": "2026-08-26T15:00:00Z",
        "cache_note": "upstream unreachable; serving last good value",
        "data": {"vulnerabilities": [_kev("CVE-2026-0006")]},
    }
    monkeypatch.setattr(serve._kl_live, "get_feed", lambda _feed: payload)
    monkeypatch.setattr(
        serve,
        "_kl_epss_map",
        lambda _cves: {"CVE-2026-0006": (0.91, 0.99)},
    )
    monkeypatch.setattr(
        serve,
        "_KL_CVSS",
        {
            "CVE-2026-0006": {
                "cvss": 9.8,
                "severity": "CRITICAL",
                "vector": "CVSS:3.1",
                "src": "nvd",
                "ts": time.time(),
            }
        },
    )

    rows, meta = serve._kl_live_rows()

    assert meta["mode"] == "cached"
    assert meta["data_kind"] == "cached"
    assert rows[0]["data_kind"] == "cached"
    assert "catalog=cached" in rows[0]["evidence_detail"]

    route = json.loads(asyncio.run(serve._sec_kevgate(limit=1)).body)
    assert route["mode"] == "cached"
    assert route["data_kind"] == "cached"
    assert route["items"][0]["data_kind"] == "cached"


def test_kevgate_nvd_cache_requires_fresh_timestamp_and_source(monkeypatch):
    cve = "CVE-2026-0007"
    payload = {
        "source": "CISA Known Exploited Vulnerabilities Catalog",
        "source_url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        "mode": "live",
        "fetched_at": "2026-08-26T16:00:00Z",
        "data": {"vulnerabilities": [_kev(cve)]},
    }
    monkeypatch.setattr(serve._kl_live, "get_feed", lambda _feed: payload)
    monkeypatch.setattr(
        serve,
        "_kl_epss_map",
        lambda _cves: {cve: (0.91, 0.99)},
    )
    now = time.time()
    record = {
        "cvss": 9.8,
        "severity": "CRITICAL",
        "vector": "CVSS:3.1",
        "src": "nvd",
    }
    invalid_records = {
        "expired": {**record, "ts": now - serve._KL_CVSS_TTL - 1},
        "future": {**record, "ts": now + 60},
        "missing": dict(record),
        "invalid": {**record, "ts": "not-a-timestamp"},
        "non-finite": {**record, "ts": float("inf")},
        "overflow": {**record, "ts": 10**10000},
        "wrong-source": {**record, "src": "unknown", "ts": now},
    }

    for case, invalid_record in invalid_records.items():
        monkeypatch.setattr(serve, "_KL_CVSS", {cve: invalid_record})
        rows, meta = serve._kl_live_rows()

        assert rows[0]["cvss_src"] == "derived", case
        assert rows[0]["cvss_cache_state"] == "stale", case
        assert rows[0]["data_kind"] == "sample", case
        assert "stale-nvd-cache-ignored" in rows[0]["evidence_detail"], case
        assert meta["data_kind"] == "sample", case

        route = json.loads(asyncio.run(serve._sec_kevgate(limit=1)).body)
        assert route["data_kind"] == "sample", case
        assert route["items"][0]["data_kind"] == "sample", case
        assert route["items"][0]["cvss_src"] == "derived", case
        assert route["items"][0]["cvss_cache_state"] == "stale", case
        assert "stale-nvd-cache-ignored" in route["items"][0]["evidence_detail"], case

    monkeypatch.setattr(
        serve,
        "_KL_CVSS",
        {cve: {**record, "ts": time.time()}},
    )
    fresh_rows, fresh_meta = serve._kl_live_rows()
    assert fresh_rows[0]["cvss_src"] == "nvd"
    assert fresh_rows[0]["cvss_cache_state"] == "fresh"
    assert fresh_rows[0]["data_kind"] == "cached"
    assert fresh_meta["data_kind"] == "cached"

    fresh_route = json.loads(asyncio.run(serve._sec_kevgate(limit=1)).body)
    assert fresh_route["data_kind"] == "cached"
    assert fresh_route["items"][0]["data_kind"] == "cached"
    assert fresh_route["items"][0]["cvss_src"] == "nvd"
    assert fresh_route["items"][0]["cvss_cache_state"] == "fresh"


def test_kevgate_nvd_cache_rejects_malformed_scores_and_never_500(monkeypatch):
    cve = "CVE-2026-0009"
    monkeypatch.setattr(serve._kl_live, "get_feed", lambda _feed: _live_kev_payload(cve))
    monkeypatch.setattr(serve, "_kl_epss_map", lambda _cves: {cve: (0.91, 0.99)})
    base_record = {
        "severity": "CRITICAL",
        "vector": "CVSS:3.1",
        "src": "nvd",
        "ts": time.time(),
    }
    invalid_scores = {
        "missing": None,
        "text": "not-a-number",
        "numeric-text": "9.8",
        "boolean": True,
        "nan": float("nan"),
        "positive-infinity": float("inf"),
        "negative-infinity": float("-inf"),
        "negative": -0.1,
        "above-maximum": 10.1,
        "far-above-maximum": 99,
        "overflow": 10**10000,
    }

    for case, score in invalid_scores.items():
        monkeypatch.setattr(
            serve,
            "_KL_CVSS",
            {cve: {**base_record, "cvss": score}},
        )
        rows, meta = serve._kl_live_rows()

        assert rows[0]["cvss_src"] == "derived", case
        assert rows[0]["cvss_cache_state"] == "malformed", case
        assert type(rows[0]["cvss"]) in (int, float), case
        assert math.isfinite(rows[0]["cvss"]), case
        assert 0.0 <= rows[0]["cvss"] <= 10.0, case
        assert rows[0]["data_kind"] == "sample", case
        assert "malformed-nvd-cache-ignored" in rows[0]["evidence_detail"], case
        assert meta["data_kind"] == "sample", case

        response = asyncio.run(serve._sec_kevgate(limit=1))
        assert response.status_code == 200, case
        route = json.loads(response.body)
        assert route["data_kind"] == "sample", case
        assert route["items"][0]["cvss_src"] == "derived", case
        assert route["items"][0]["cvss_cache_state"] == "malformed", case
        assert math.isfinite(route["items"][0]["cvss"]), case
        assert "malformed-nvd-cache-ignored" in route["items"][0]["evidence_detail"], case

    for boundary in (0.0, 10.0):
        monkeypatch.setattr(
            serve,
            "_KL_CVSS",
            {cve: {**base_record, "cvss": boundary}},
        )
        rows, meta = serve._kl_live_rows()
        assert rows[0]["cvss"] == boundary
        assert rows[0]["cvss_src"] == "nvd"
        assert rows[0]["cvss_cache_state"] == "fresh"
        assert rows[0]["data_kind"] == "cached"
        assert meta["data_kind"] == "cached"
        route = json.loads(asyncio.run(serve._sec_kevgate(limit=1)).body)
        assert route["items"][0]["cvss"] == boundary
        assert route["items"][0]["data_kind"] == "cached"


def test_kevgate_normalizes_malformed_nvd_metadata(monkeypatch):
    cve = "CVE-2026-0010"
    monkeypatch.setattr(serve._kl_live, "get_feed", lambda _feed: _live_kev_payload(cve))
    monkeypatch.setattr(serve, "_kl_epss_map", lambda _cves: {cve: (0.91, 0.99)})
    monkeypatch.setattr(
        serve,
        "_KL_CVSS",
        {
            cve: {
                "cvss": 9.8,
                "severity": float("nan"),
                "vector": float("inf"),
                "src": "nvd",
                "ts": time.time(),
            }
        },
    )

    rows, meta = serve._kl_live_rows()
    assert rows[0]["cvss_src"] == "nvd"
    assert rows[0]["severity"] == "CRITICAL"
    assert "cvss_vector" not in rows[0]
    assert meta["data_kind"] == "cached"
    response = asyncio.run(serve._sec_kevgate(limit=1))
    assert response.status_code == 200
    route = json.loads(response.body)
    assert route["items"][0]["severity"] == "CRITICAL"


def test_nvd_cache_load_and_persist_drop_future_records(monkeypatch, tmp_path):
    cache_path = tmp_path / "nvd-cache.json"
    now = time.time()
    fresh = {
        "cvss": 10.0,
        "severity": "CRITICAL",
        "vector": "CVSS:3.1",
        "src": "nvd",
        "ts": now,
    }
    future = {**fresh, "ts": now + 3600}
    monkeypatch.setattr(serve, "_KL_CVSS_PATH", cache_path)
    monkeypatch.setattr(
        serve,
        "_KL_CVSS",
        {"CVE-FRESH": fresh, "CVE-FUTURE": future},
    )

    serve._kl_cvss_persist()
    persisted = json.loads(cache_path.read_text(encoding="utf-8"))
    assert set(persisted) == {"CVE-FRESH"}
    assert persisted["CVE-FRESH"]["cvss"] == 10.0

    cache_path.write_text(json.dumps({"CVE-FUTURE": future}), encoding="utf-8")
    serve._KL_CVSS = {}
    serve._kl_cvss_load()
    assert serve._KL_CVSS == {}


def test_nvd_fetch_rejects_invalid_scores_and_accepts_boundaries(monkeypatch):
    import urllib.request

    class Response:
        def __init__(self, score):
            self.body = json.dumps(
                {
                    "vulnerabilities": [
                        {
                            "cve": {
                                "id": "CVE-2026-0011",
                                "metrics": {
                                    "cvssMetricV31": [
                                        {
                                            "cvssData": {
                                                "baseScore": score,
                                                "vectorString": "CVSS:3.1",
                                            }
                                        }
                                    ]
                                }
                            }
                        }
                    ]
                }
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return self.body

    for score in (
        "not-a-number",
        "9.8",
        True,
        float("nan"),
        float("inf"),
        -0.1,
        10.1,
        99,
    ):
        monkeypatch.setattr(
            urllib.request,
            "urlopen",
            lambda *_args, _score=score, **_kwargs: Response(_score),
        )
        assert serve._kl_cvss_fetch_one("CVE-2026-0011") is None

    for score in (0.0, 10.0):
        monkeypatch.setattr(
            urllib.request,
            "urlopen",
            lambda *_args, _score=score, **_kwargs: Response(_score),
        )
        record = serve._kl_cvss_fetch_one("CVE-2026-0011")
        assert record["cvss"] == score
        assert record["src"] == "nvd"
        assert serve._kl_cvss_record_is_fresh(record)


def test_kevgate_rejects_invalid_epss_pairs_and_accepts_boundaries(monkeypatch):
    cve = "CVE-2026-0012"
    monkeypatch.setattr(serve._kl_live, "get_feed", lambda _feed: _live_kev_payload(cve))
    monkeypatch.setattr(
        serve,
        "_KL_CVSS",
        {
            cve: {
                "cvss": 9.8,
                "severity": "CRITICAL",
                "vector": "CVSS:3.1",
                "src": "nvd",
                "ts": time.time(),
            }
        },
    )
    invalid_pairs = {
        "wrong-shape": (0.5,),
        "text": ("not-a-number", 0.5),
        "boolean": (True, 0.5),
        "epss-nan": (float("nan"), 0.5),
        "epss-infinity": (float("inf"), 0.5),
        "epss-negative": (-0.1, 0.5),
        "epss-above-maximum": (1.1, 0.5),
        "percentile-nan": (0.5, float("nan")),
        "percentile-infinity": (0.5, float("inf")),
        "percentile-negative": (0.5, -0.1),
        "percentile-above-maximum": (0.5, 1.1),
    }

    for case, pair in invalid_pairs.items():
        monkeypatch.setattr(
            serve,
            "_kl_epss_map",
            lambda _cves, _pair=pair: {cve: _pair},
        )
        rows, meta = serve._kl_live_rows()
        assert rows[0]["epss_src"] == "derived", case
        assert type(rows[0]["epss"]) in (int, float), case
        assert math.isfinite(rows[0]["epss"]), case
        assert "epss_pctl" not in rows[0], case
        assert rows[0]["data_kind"] == "sample", case
        assert meta["data_kind"] == "sample", case
        response = asyncio.run(serve._sec_kev_live())
        assert response.status_code == 200, case
        payload = json.loads(response.body)
        assert payload["vulnerabilities"][0]["epss_src"] == "derived", case

    for boundary in ((0.0, 0.0), (1.0, 1.0)):
        monkeypatch.setattr(
            serve,
            "_kl_epss_map",
            lambda _cves, _pair=boundary: {cve: _pair},
        )
        rows, meta = serve._kl_live_rows()
        assert rows[0]["epss"] == boundary[0]
        assert rows[0]["epss_pctl"] == boundary[1]
        assert rows[0]["epss_src"] == "first.org"
        assert rows[0]["data_kind"] == "cached"
        assert meta["data_kind"] == "cached"
        payload = json.loads(asyncio.run(serve._sec_kev_live()).body)
        assert payload["vulnerabilities"][0]["epss"] == boundary[0]


def test_epss_fetch_and_fresh_cache_validate_probability_range(monkeypatch):
    import urllib.request

    class Response:
        def __init__(self):
            self.body = json.dumps(
                {
                    "data": [
                        {"cve": "CVE-ZERO", "epss": "0", "percentile": "0"},
                        {"cve": "CVE-ONE", "epss": "1", "percentile": "1"},
                        {"cve": "CVE-NAN", "epss": "NaN", "percentile": "0.5"},
                        {"cve": "CVE-INF", "epss": "Infinity", "percentile": "0.5"},
                        {"cve": "CVE-HIGH", "epss": "1.1", "percentile": "0.5"},
                        {"cve": "CVE-PCTL", "epss": "0.5", "percentile": "-0.1"},
                    ]
                }
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, size=-1):
            if not self.body:
                return b""
            if size is None or size < 0:
                size = len(self.body)
            chunk, self.body = self.body[:size], self.body[size:]
            return chunk

    monkeypatch.setattr(serve, "_KL_EPSS_CACHE", {"ts": 0.0, "map": {}})
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_args, **_kwargs: Response())
    result = serve._kl_epss_map(
        ["CVE-ZERO", "CVE-ONE", "CVE-NAN", "CVE-INF", "CVE-HIGH", "CVE-PCTL"]
    )
    assert result == {"CVE-ZERO": (0.0, 0.0), "CVE-ONE": (1.0, 1.0)}

    cached_at = time.time()
    monkeypatch.setattr(
        serve,
        "_KL_EPSS_CACHE",
        {
            "ts": cached_at,
            "map": {
                "CVE-ZERO": (0.0, 1.0),
                "CVE-NAN": (float("nan"), 0.5),
            },
        },
    )

    def fail_refresh(*_args, **_kwargs):
        raise OSError("FIRST.org unavailable")

    monkeypatch.setattr(urllib.request, "urlopen", fail_refresh)
    cached = serve._kl_epss_map(["CVE-ZERO", "CVE-NAN"])
    assert cached == {"CVE-ZERO": (0.0, 1.0)}
    assert serve._KL_EPSS_CACHE["ts"] == cached_at

    for invalid_timestamp in (str(time.time()), True, time.time() + 60, 10**10000):
        serve._KL_EPSS_CACHE = {
            "ts": invalid_timestamp,
            "map": {"CVE-NAN": (0.5, 0.5)},
        }
        assert serve._kl_epss_map(["CVE-NAN"]) == {}


def test_epss_request_path_spends_one_batch_and_leaves_gaps_derived(monkeypatch):
    import urllib.parse
    import urllib.request

    cached_cve = "CVE-2026-0000"
    missing_cves = [f"CVE-2026-{index:04d}" for index in range(1, 251)]
    payload = _live_kev_payload(cached_cve)
    payload["data"]["vulnerabilities"] = [
        _kev(cached_cve),
        *[_kev(cve) for cve in missing_cves],
    ]
    payload["data"]["count"] = len(payload["data"]["vulnerabilities"])
    monkeypatch.setattr(serve._kl_live, "get_feed", lambda _feed: payload)
    observed_at = time.time()
    monkeypatch.setattr(
        serve,
        "_KL_EPSS_CACHE",
        {"ts": observed_at, "map": {cached_cve: (0.9, 0.99)}},
    )
    monkeypatch.setattr(serve, "_KL_CVSS", {})
    monkeypatch.setattr(serve, "_KL_EPSS_FAIR_STATE", {"epoch": 0, "entries": {}})
    calls = []

    class Response:
        def __init__(self, requested):
            self.requested = requested
            self.body = json.dumps(
                {
                    "data": [
                        {"cve": cve, "epss": "0.8", "percentile": "0.95"}
                        for cve in self.requested
                    ]
                }
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, size=-1):
            if not self.body:
                return b""
            if size is None or size < 0:
                size = len(self.body)
            chunk, self.body = self.body[:size], self.body[size:]
            return chunk

    def bounded_fetch(request, *, timeout):
        query = urllib.parse.parse_qs(
            urllib.parse.urlparse(request.full_url).query
        )
        requested = query["cve"][0].split(",")
        calls.append((requested, timeout))
        return Response(requested)

    monkeypatch.delenv("A11OY_EPSS_REQUEST_TIMEOUT_SEC", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", bounded_fetch)

    rows, meta = serve._kl_live_rows()

    assert len(calls) == 1
    requested, timeout = calls[0]
    assert requested == missing_cves[: serve._KL_EPSS_BATCH_SIZE]
    assert timeout == serve._KL_EPSS_REQUEST_TIMEOUT_DEFAULT
    assert serve._KL_EPSS_REQUEST_TIMEOUT_MIN <= timeout
    assert timeout <= serve._KL_EPSS_REQUEST_TIMEOUT_MAX
    assert sum(row["epss_src"] == "first.org" for row in rows) == 101
    assert sum(row["epss_src"] == "derived" for row in rows) == 150
    assert meta["epss_source_rows"] == 101
    assert meta["data_kind"] == "sample"
    assert serve._KL_EPSS_CACHE["ts"] == observed_at
    assert set(serve._KL_EPSS_CACHE["map"]) == {
        cached_cve,
        *missing_cves[: serve._KL_EPSS_BATCH_SIZE],
    }


def test_epss_timeout_config_is_finite_bounded_and_fails_safe(monkeypatch):
    import urllib.request

    for invalid in ("", "nan", "inf", "-inf", "0", "0.24", "12.01", "oops"):
        monkeypatch.setenv("A11OY_EPSS_REQUEST_TIMEOUT_SEC", invalid)
        assert (
            serve._kl_epss_request_timeout()
            == serve._KL_EPSS_REQUEST_TIMEOUT_DEFAULT
        )
    for configured, expected in (("0.25", 0.25), ("3.5", 3.5), ("12", 12.0)):
        monkeypatch.setenv("A11OY_EPSS_REQUEST_TIMEOUT_SEC", configured)
        assert serve._kl_epss_request_timeout() == expected

    cached_cve = "CVE-2026-0300"
    missing_cve = "CVE-2026-0301"
    observed_at = time.time()
    monkeypatch.setattr(
        serve,
        "_KL_EPSS_CACHE",
        {"ts": observed_at, "map": {cached_cve: (0.4, 0.5)}},
    )
    attempted_timeouts = []

    def fail_fetch(_request, *, timeout):
        attempted_timeouts.append(timeout)
        raise TimeoutError("FIRST.org timed out")

    monkeypatch.setenv("A11OY_EPSS_REQUEST_TIMEOUT_SEC", "NaN")
    monkeypatch.setattr(urllib.request, "urlopen", fail_fetch)

    assert serve._kl_epss_map([cached_cve, missing_cve]) == {
        cached_cve: (0.4, 0.5)
    }
    assert attempted_timeouts == [serve._KL_EPSS_REQUEST_TIMEOUT_DEFAULT]
    assert serve._KL_EPSS_CACHE["ts"] == observed_at
    assert missing_cve not in serve._KL_EPSS_CACHE["map"]


def test_epss_busy_refresh_returns_only_sanitized_fresh_cache(monkeypatch):
    import urllib.request

    cached_cve = "CVE-2026-0400"
    invalid_cve = "CVE-2026-0401"
    missing_cve = "CVE-2026-0402"
    observed_at = time.time()
    monkeypatch.setattr(
        serve,
        "_KL_EPSS_CACHE",
        {
            "ts": observed_at,
            "map": {
                cached_cve: (0.7, 0.8),
                invalid_cve: (float("nan"), 0.9),
            },
        },
    )
    network_calls = []
    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: network_calls.append(True),
    )

    assert serve._KL_EPSS_REFRESH_LOCK.acquire(blocking=False)
    try:
        assert serve._kl_epss_map([cached_cve, invalid_cve, missing_cve]) == {
            cached_cve: (0.7, 0.8)
        }
        serve._KL_EPSS_CACHE["ts"] = time.time() - serve._KL_EPSS_TTL - 1
        assert serve._kl_epss_map([cached_cve]) == {}
    finally:
        serve._KL_EPSS_REFRESH_LOCK.release()

    assert network_calls == []
    assert serve._KL_EPSS_CACHE["map"][cached_cve] == (0.7, 0.8)


def test_epss_empty_responses_rotate_one_bounded_batch_without_starvation(
    monkeypatch,
):
    import urllib.parse
    import urllib.request

    cves = [f"CVE-2026-{index:04d}" for index in range(250)]
    requested_batches = []
    monkeypatch.setattr(serve, "_KL_EPSS_CACHE", {"ts": 0.0, "map": {}})
    monkeypatch.setattr(serve, "_KL_EPSS_FAIR_STATE", {"epoch": 0, "entries": {}})
    monkeypatch.setattr(serve, "_KL_EPSS_CACHE_LOCK", threading.Lock())
    monkeypatch.setattr(serve, "_KL_EPSS_REFRESH_LOCK", threading.Lock())

    class EmptyResponse:
        def __init__(self):
            self.body = b'{"data":[]}'

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, size=-1):
            if not self.body:
                return b""
            if size is None or size < 0:
                size = len(self.body)
            chunk, self.body = self.body[:size], self.body[size:]
            return chunk

    def empty_fetch(request, *, timeout):
        assert serve._KL_EPSS_REQUEST_TIMEOUT_MIN <= timeout
        query = urllib.parse.parse_qs(
            urllib.parse.urlparse(request.full_url).query
        )
        requested_batches.append(query["cve"][0].split(","))
        return EmptyResponse()

    monkeypatch.setattr(urllib.request, "urlopen", empty_fetch)

    assert serve._kl_epss_map(cves) == {}
    assert serve._kl_epss_map(cves) == {}
    assert serve._kl_epss_map(cves) == {}

    assert requested_batches == [
        cves[:100],
        cves[100:200],
        [*cves[200:], *cves[:50]],
    ]
    assert all(len(batch) == serve._KL_EPSS_BATCH_SIZE for batch in requested_batches)


def test_epss_changing_sets_cannot_positionally_starve_persistent_identity(
    monkeypatch,
):
    import urllib.parse
    import urllib.request

    persistent = "CVE-PERSISTENT"
    requested_batches = []
    monkeypatch.setattr(serve, "_KL_EPSS_CACHE", {"ts": 0.0, "map": {}})
    monkeypatch.setattr(serve, "_KL_EPSS_FAIR_STATE", {"epoch": 0, "entries": {}})
    monkeypatch.setattr(serve, "_KL_EPSS_CACHE_LOCK", threading.Lock())
    monkeypatch.setattr(serve, "_KL_EPSS_REFRESH_LOCK", threading.Lock())

    class EmptyResponse:
        def __init__(self):
            self.body = b'{"data":[]}'

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, size=-1):
            if not self.body:
                return b""
            if size is None or size < 0:
                size = len(self.body)
            chunk, self.body = self.body[:size], self.body[size:]
            return chunk

    def empty_fetch(request, **_kwargs):
        query = urllib.parse.parse_qs(
            urllib.parse.urlparse(request.full_url).query
        )
        requested_batches.append(query["cve"][0].split(","))
        return EmptyResponse()

    monkeypatch.setattr(urllib.request, "urlopen", empty_fetch)
    legacy_cursor = 0
    for turn in range(25):
        excluded = (legacy_cursor % 101 + 100) % 101
        changing = [f"CVE-CHURN-{turn:02d}-{index:03d}" for index in range(100)]
        changing.insert(excluded, persistent)
        assert serve._kl_epss_map(changing) == {}
        legacy_cursor = (legacy_cursor % 101 + 100) % 101

    attempts = [
        turn for turn, batch in enumerate(requested_batches) if persistent in batch
    ]
    assert attempts
    assert attempts[0] <= 1
    assert all(len(batch) == serve._KL_EPSS_BATCH_SIZE for batch in requested_batches)


def test_epss_fair_state_resets_malformed_top_level(monkeypatch):
    now = time.time()
    monkeypatch.setattr(serve, "_KL_EPSS_FAIR_STATE", ["malformed"])
    monkeypatch.setattr(serve, "_KL_EPSS_CACHE_LOCK", threading.Lock())

    assert serve._kl_epss_select_batch(["CVE-RESET"], now) == ["CVE-RESET"]
    assert serve._KL_EPSS_FAIR_STATE == {
        "epoch": 1,
        "entries": {
            "CVE-RESET": {"due_epoch": 2, "last_seen_at": now},
        },
    }


def test_epss_fair_state_prunes_invalid_age_and_enforces_hard_cap(monkeypatch):
    now = time.time()
    monkeypatch.setattr(serve, "_KL_EPSS_FAIR_STATE_TTL", 60)
    monkeypatch.setattr(serve, "_KL_EPSS_FAIR_STATE_MAX_ENTRIES", 3)
    monkeypatch.setattr(serve, "_KL_EPSS_CACHE_LOCK", threading.Lock())
    monkeypatch.setattr(
        serve,
        "_KL_EPSS_FAIR_STATE",
        {
            "epoch": 7,
            "entries": {
                "CVE-RECENT": {"due_epoch": 2, "last_seen_at": now - 5},
                "CVE-STALE": {"due_epoch": 1, "last_seen_at": now - 61},
                "CVE-FUTURE": {"due_epoch": 1, "last_seen_at": now + 1},
                "CVE-BAD-DUE": {"due_epoch": True, "last_seen_at": now},
                "CVE-BAD-TIME": {"due_epoch": 1, "last_seen_at": "now"},
                "CVE-BOOL-TIME": {"due_epoch": 1, "last_seen_at": True},
                "CVE-NAN-TIME": {"due_epoch": 1, "last_seen_at": float("nan")},
                "CVE-INF-TIME": {"due_epoch": 1, "last_seen_at": float("inf")},
                "CVE-HUGE-TIME": {"due_epoch": 1, "last_seen_at": 10**10000},
                "CVE-OLDER": {"due_epoch": 3, "last_seen_at": now - 10},
                "CVE-OLDEST": {"due_epoch": 4, "last_seen_at": now - 20},
            },
        },
    )

    batch = serve._kl_epss_select_batch(["CVE-PERSISTENT", "CVE-RECENT"], now)

    assert batch == ["CVE-RECENT", "CVE-PERSISTENT"]
    assert serve._KL_EPSS_FAIR_STATE["epoch"] == 8
    entries = serve._KL_EPSS_FAIR_STATE["entries"]
    assert len(entries) == serve._KL_EPSS_FAIR_STATE_MAX_ENTRIES
    assert set(entries) == {"CVE-PERSISTENT", "CVE-RECENT", "CVE-OLDER"}
    assert not {
        "CVE-STALE",
        "CVE-FUTURE",
        "CVE-BAD-DUE",
        "CVE-BAD-TIME",
        "CVE-BOOL-TIME",
        "CVE-NAN-TIME",
        "CVE-INF-TIME",
        "CVE-HUGE-TIME",
    } & set(entries)


def test_epss_partial_reply_preserves_clock_and_rotates_past_attempted_rows(
    monkeypatch,
):
    import urllib.parse
    import urllib.request

    cached_cve = "CVE-2026-CACHED"
    cves = [f"CVE-2026-PARTIAL-{index:04d}" for index in range(150)]
    observed_at = time.time() - 30
    requested_batches = []
    monkeypatch.setattr(
        serve,
        "_KL_EPSS_CACHE",
        {"ts": observed_at, "map": {cached_cve: (0.2, 0.3)}},
    )
    monkeypatch.setattr(serve, "_KL_EPSS_FAIR_STATE", {"epoch": 0, "entries": {}})
    monkeypatch.setattr(serve, "_KL_EPSS_CACHE_LOCK", threading.Lock())
    monkeypatch.setattr(serve, "_KL_EPSS_REFRESH_LOCK", threading.Lock())

    class PartialResponse:
        def __init__(self, requested):
            self.body = json.dumps(
                {
                    "data": [
                        {
                            "cve": requested[0],
                            "epss": "0.71",
                            "percentile": "0.91",
                        },
                        {
                            "cve": requested[-1],
                            "epss": "0.72",
                            "percentile": "0.92",
                        },
                    ]
                }
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, size=-1):
            if not self.body:
                return b""
            if size is None or size < 0:
                size = len(self.body)
            chunk, self.body = self.body[:size], self.body[size:]
            return chunk

    def partial_fetch(request, *, timeout):
        assert timeout == serve._KL_EPSS_REQUEST_TIMEOUT_DEFAULT
        query = urllib.parse.parse_qs(
            urllib.parse.urlparse(request.full_url).query
        )
        requested = query["cve"][0].split(",")
        requested_batches.append(requested)
        return PartialResponse(requested)

    monkeypatch.delenv("A11OY_EPSS_REQUEST_TIMEOUT_SEC", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", partial_fetch)

    first = serve._kl_epss_map([cached_cve, *cves])
    second = serve._kl_epss_map([cached_cve, *cves])

    assert requested_batches[0] == cves[:100]
    assert requested_batches[1][0] == cves[100]
    assert len(requested_batches[1]) == serve._KL_EPSS_BATCH_SIZE
    assert first[cached_cve] == (0.2, 0.3)
    assert first[cves[0]] == (0.71, 0.91)
    assert first[cves[99]] == (0.72, 0.92)
    assert cves[1] not in first
    assert serve._KL_EPSS_CACHE["ts"] == observed_at
    assert second[cached_cve] == (0.2, 0.3)
    assert cves[100] in second


def test_epss_concurrent_callers_singleflight_and_atomic_merge(monkeypatch):
    import urllib.request

    cached_cve = "CVE-2026-CONCURRENT-CACHED"
    invalid_cve = "CVE-2026-CONCURRENT-INVALID"
    requested_cve = "CVE-2026-CONCURRENT-REQUESTED"
    added_during_flight = "CVE-2026-CONCURRENT-ADDED"
    observed_at = time.time() - 10
    monkeypatch.setattr(
        serve,
        "_KL_EPSS_CACHE",
        {
            "ts": observed_at,
            "map": {
                cached_cve: (0.4, 0.5),
                invalid_cve: (float("nan"), 0.9),
            },
        },
    )
    monkeypatch.setattr(serve, "_KL_EPSS_FAIR_STATE", {"epoch": 0, "entries": {}})
    monkeypatch.setattr(serve, "_KL_EPSS_CACHE_LOCK", threading.Lock())
    monkeypatch.setattr(serve, "_KL_EPSS_REFRESH_LOCK", threading.Lock())
    monkeypatch.setenv("A11OY_EPSS_REQUEST_TIMEOUT_SEC", "1")
    read_started = threading.Event()
    release_read = threading.Event()
    network_calls = []

    class BlockedResponse:
        def __init__(self):
            self.body = json.dumps(
                {
                    "data": [
                        {
                            "cve": requested_cve,
                            "epss": "0.8",
                            "percentile": "0.95",
                        }
                    ]
                }
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, size=-1):
            read_started.set()
            assert release_read.wait(2)
            if not self.body:
                return b""
            if size is None or size < 0:
                size = len(self.body)
            chunk, self.body = self.body[:size], self.body[size:]
            return chunk

    def blocked_fetch(*_args, **_kwargs):
        network_calls.append(True)
        return BlockedResponse()

    monkeypatch.setattr(urllib.request, "urlopen", blocked_fetch)
    leader_results = []
    leader = threading.Thread(
        target=lambda: leader_results.append(
            serve._kl_epss_map([cached_cve, invalid_cve, requested_cve])
        )
    )
    leader.start()
    assert read_started.wait(1)

    contender_results = []
    contenders = [
        threading.Thread(
            target=lambda: contender_results.append(
                serve._kl_epss_map([cached_cve, invalid_cve, requested_cve])
            )
        )
        for _index in range(8)
    ]
    contender_started = time.monotonic()
    for contender in contenders:
        contender.start()
    for contender in contenders:
        contender.join(0.5)
    assert all(not contender.is_alive() for contender in contenders)
    assert time.monotonic() - contender_started < 0.75
    assert contender_results == [{cached_cve: (0.4, 0.5)}] * len(contenders)
    assert network_calls == [True]

    with serve._KL_EPSS_CACHE_LOCK:
        serve._KL_EPSS_CACHE["map"][added_during_flight] = (0.6, 0.7)
    release_read.set()
    leader.join(1)

    assert not leader.is_alive()
    assert network_calls == [True]
    assert leader_results == [
        {
            cached_cve: (0.4, 0.5),
            added_during_flight: (0.6, 0.7),
            requested_cve: (0.8, 0.95),
        }
    ]
    assert serve._KL_EPSS_CACHE["map"] == leader_results[0]
    assert serve._KL_EPSS_CACHE["ts"] == observed_at


def test_epss_stalled_read_has_hard_caller_budget_and_no_thread_buildup(
    monkeypatch,
):
    import urllib.request

    cve = "CVE-2026-STALLED-READ"
    monkeypatch.setattr(serve, "_KL_EPSS_CACHE", {"ts": 0.0, "map": {}})
    monkeypatch.setattr(serve, "_KL_EPSS_FAIR_STATE", {"epoch": 0, "entries": {}})
    monkeypatch.setattr(serve, "_KL_EPSS_CACHE_LOCK", threading.Lock())
    monkeypatch.setattr(serve, "_KL_EPSS_REFRESH_LOCK", threading.Lock())
    monkeypatch.setenv("A11OY_EPSS_REQUEST_TIMEOUT_SEC", "0.25")
    read_started = threading.Event()
    release_read = threading.Event()
    network_calls = []

    class StalledResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def settimeout(self, _timeout):
            return None

        def read(self, _size=-1):
            read_started.set()
            assert release_read.wait(2)
            return b'{"data":[]}'

    def stalled_fetch(*_args, **_kwargs):
        network_calls.append(True)
        return StalledResponse()

    monkeypatch.setattr(urllib.request, "urlopen", stalled_fetch)
    started_at = time.monotonic()
    assert serve._kl_epss_map([cve]) == {}
    elapsed = time.monotonic() - started_at

    assert read_started.is_set()
    assert 0.20 <= elapsed < 0.75
    assert network_calls == [True]
    live_workers = [
        thread
        for thread in threading.enumerate()
        if thread.name == "a11oy-epss-singleflight" and thread.is_alive()
    ]
    assert len(live_workers) == 1
    assert serve._kl_epss_map([cve]) == {}
    assert network_calls == [True]

    release_read.set()
    deadline = time.monotonic() + 1
    while time.monotonic() < deadline:
        remaining_workers = [
            thread
            for thread in threading.enumerate()
            if thread.name == "a11oy-epss-singleflight" and thread.is_alive()
        ]
        if not serve._KL_EPSS_REFRESH_LOCK.locked() and not remaining_workers:
            break
        time.sleep(0.01)
    assert not serve._KL_EPSS_REFRESH_LOCK.locked()
    assert not [
        thread
        for thread in threading.enumerate()
        if thread.name == "a11oy-epss-singleflight" and thread.is_alive()
    ]


def test_epss_worker_paused_before_merge_cannot_promote_after_deadline(
    monkeypatch,
):
    import urllib.request

    cve = "CVE-2026-LATE-MERGE"
    monkeypatch.setattr(serve, "_KL_EPSS_CACHE", {"ts": 0.0, "map": {}})
    monkeypatch.setattr(serve, "_KL_EPSS_FAIR_STATE", {"epoch": 0, "entries": {}})
    monkeypatch.setattr(serve, "_KL_EPSS_CACHE_LOCK", threading.Lock())
    monkeypatch.setattr(serve, "_KL_EPSS_REFRESH_LOCK", threading.Lock())
    monkeypatch.setenv("A11OY_EPSS_REQUEST_TIMEOUT_SEC", "0.25")
    merge_started = threading.Event()
    release_merge = threading.Event()

    class ImmediateResponse:
        def __init__(self):
            self.body = json.dumps(
                {
                    "data": [
                        {"cve": cve, "epss": "0.8", "percentile": "0.95"}
                    ]
                }
            ).encode()

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, size=-1):
            if not self.body:
                return b""
            if size is None or size < 0:
                size = len(self.body)
            chunk, self.body = self.body[:size], self.body[size:]
            return chunk

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: ImmediateResponse(),
    )
    merge_batch = serve._kl_epss_merge_batch

    def paused_merge(result, request_started_at, deadline):
        merge_started.set()
        assert release_merge.wait(2)
        merge_batch(result, request_started_at, deadline)

    monkeypatch.setattr(serve, "_kl_epss_merge_batch", paused_merge)
    started_at = time.monotonic()
    assert serve._kl_epss_map([cve]) == {}
    elapsed = time.monotonic() - started_at

    assert merge_started.is_set()
    assert 0.20 <= elapsed < 0.75
    assert serve._KL_EPSS_CACHE == {"ts": 0.0, "map": {}}
    release_merge.set()
    deadline = time.monotonic() + 1
    while serve._KL_EPSS_REFRESH_LOCK.locked() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not serve._KL_EPSS_REFRESH_LOCK.locked()
    assert serve._KL_EPSS_CACHE == {"ts": 0.0, "map": {}}


def test_epss_oversized_response_fails_closed_at_byte_limit(monkeypatch):
    import urllib.request

    cve = "CVE-2026-OVERSIZED"
    observed_at = time.time() - 5
    cached_cve = "CVE-2026-OVERSIZED-CACHED"
    monkeypatch.setattr(
        serve,
        "_KL_EPSS_CACHE",
        {"ts": observed_at, "map": {cached_cve: (0.3, 0.4)}},
    )
    monkeypatch.setattr(serve, "_KL_EPSS_FAIR_STATE", {"epoch": 0, "entries": {}})
    monkeypatch.setattr(serve, "_KL_EPSS_CACHE_LOCK", threading.Lock())
    monkeypatch.setattr(serve, "_KL_EPSS_REFRESH_LOCK", threading.Lock())
    bytes_read = []

    class OversizedResponse:
        def __init__(self):
            self.remaining = serve._KL_EPSS_RESPONSE_MAX_BYTES + 1

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self, size=-1):
            size = self.remaining if size is None or size < 0 else size
            count = min(size, self.remaining)
            self.remaining -= count
            bytes_read.append(count)
            return b"x" * count

    monkeypatch.setattr(
        urllib.request,
        "urlopen",
        lambda *_args, **_kwargs: OversizedResponse(),
    )

    assert serve._kl_epss_map([cached_cve, cve]) == {cached_cve: (0.3, 0.4)}
    assert sum(bytes_read) == serve._KL_EPSS_RESPONSE_MAX_BYTES + 1
    assert serve._KL_EPSS_CACHE == {
        "ts": observed_at,
        "map": {cached_cve: (0.3, 0.4)},
    }


def test_nvd_warm_loop_refreshes_huge_timestamp_without_terminating(monkeypatch):
    cve = "CVE-2026-0013"
    payload = _live_kev_payload(cve)
    payload["data"]["vulnerabilities"] = [
        {"cveID": []},
        {"cveID": {}},
        _kev(cve),
        _kev(cve),
    ]
    monkeypatch.setattr(serve._kl_live, "get_feed", lambda _feed: payload)
    monkeypatch.setattr(
        serve,
        "_KL_CVSS",
        {
            cve: {
                "cvss": 9.8,
                "severity": "CRITICAL",
                "vector": "CVSS:3.1",
                "src": "nvd",
                "ts": 10**10000,
            }
        },
    )
    fetched = []

    def fetch_one(requested_cve):
        fetched.append(requested_cve)
        return {
            "cvss": 9.8,
            "severity": "CRITICAL",
            "vector": "CVSS:3.1",
            "src": "nvd",
            "ts": time.time(),
        }

    class StopWarmLoop(Exception):
        pass

    sleeps = []

    def fake_sleep(seconds):
        sleeps.append(seconds)
        if seconds >= 300:
            raise StopWarmLoop

    monkeypatch.setattr(serve, "_kl_cvss_fetch_one", fetch_one)
    monkeypatch.setattr(serve, "_kl_cvss_persist", lambda: None)
    monkeypatch.setenv("A11OY_NVD_CVSS_DELAY_SEC", "nan")
    monkeypatch.setenv("A11OY_NVD_CVSS_INITIAL_DELAY_SEC", "inf")
    monkeypatch.setattr(time, "sleep", fake_sleep)

    with pytest.raises(StopWarmLoop):
        serve._kl_cvss_warm_loop()

    assert fetched == [cve]
    assert sleeps == [60.0, 7.0, 300.0]
    assert serve._kl_cvss_record_is_fresh(serve._KL_CVSS[cve])


def test_kevgate_expired_epss_cache_is_not_reused_after_refresh_failure(
    monkeypatch,
):
    import urllib.request

    cve = "CVE-2026-0008"
    payload = {
        "source": "CISA Known Exploited Vulnerabilities Catalog",
        "source_url": "https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
        "mode": "live",
        "fetched_at": "2026-08-26T16:00:00Z",
        "data": {"vulnerabilities": [_kev(cve)]},
    }
    monkeypatch.setattr(serve._kl_live, "get_feed", lambda _feed: payload)
    monkeypatch.setattr(
        serve,
        "_KL_EPSS_CACHE",
        {
            "ts": time.time() - serve._KL_EPSS_TTL - 1,
            "map": {cve: (0.91, 0.99)},
        },
    )

    def fail_refresh(*_args, **_kwargs):
        raise OSError("FIRST.org unavailable")

    monkeypatch.setattr(urllib.request, "urlopen", fail_refresh)
    monkeypatch.setattr(
        serve,
        "_KL_CVSS",
        {
            cve: {
                "cvss": 9.8,
                "severity": "CRITICAL",
                "vector": "CVSS:3.1",
                "src": "nvd",
                "ts": time.time(),
            }
        },
    )

    rows, meta = serve._kl_live_rows()
    assert rows[0]["epss_src"] == "derived"
    assert rows[0]["cvss_src"] == "nvd"
    assert rows[0]["data_kind"] == "sample"
    assert meta["data_kind"] == "sample"
    assert "EPSS = derived-sample" in meta["enrichment_provenance"]

    serve._KL_EPSS_CACHE["ts"] = time.time()
    fresh_rows, fresh_meta = serve._kl_live_rows()
    assert fresh_rows[0]["epss_src"] == "first.org"
    assert fresh_rows[0]["data_kind"] == "cached"
    assert fresh_meta["data_kind"] == "cached"


def test_kevgate_bundled_and_unavailable_fallbacks_remain_explicit(monkeypatch):
    monkeypatch.setattr(
        serve._kl_live,
        "get_feed",
        lambda _feed: {"mode": "unavailable", "data": None},
    )
    monkeypatch.setattr(
        serve,
        "_kl_snap",
        SimpleNamespace(
            KEV=[{"cveID": "CVE-2026-0004"}],
            KEV_SOURCE="https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
            KEV_CATALOG_VERSION="bundled-test",
        ),
    )

    rows, cached = serve._kl_live_rows()

    assert len(rows) == 1
    assert cached["mode"] == "cached"
    assert cached["data_kind"] == "sample"
    assert "sample enrichment" in cached["enrichment_provenance"]
    assert rows[0]["data_kind"] == "sample"

    monkeypatch.setattr(serve, "_kl_snap", None)
    rows, unavailable = serve._kl_live_rows()

    assert rows == []
    assert unavailable["mode"] == "unavailable"
    assert unavailable["data_kind"] == "unavailable"
    assert unavailable["fetched_at"] is None


def test_kevgate_console_surfaces_mode_and_item_provenance():
    console = (Path(__file__).parents[1] / "pages" / "console.html").read_text(
        encoding="utf-8"
    )
    block = console.split("/* ===== kevgate", 1)[1].split(
        "/* ===== feedpulse", 1
    )[0]

    assert "LIVE CISA KEV" not in block
    assert "loading live CISA KEV" not in block
    assert "id=\"kg-prov\"" in block
    assert "d.enrichment_provenance" in block
    assert "x.data_kind" in block
    assert "x.evidence_detail" in block


def test_feed_pulse_is_concurrent_bounded_and_honest_about_timeout(monkeypatch):
    active = 0
    active_lock = threading.Lock()
    all_workers_done = threading.Event()

    def fake_get_feed(feed, timeout_s=None):
        nonlocal active
        assert timeout_s == 0.15
        with active_lock:
            active += 1
        try:
            if feed == "celestrak":
                time.sleep(0.05)
                raise TimeoutError("cooperative test deadline")
            time.sleep(0.02)
            source, source_url = serve._kl_live._SOURCE[feed]
            return {
                "source": source,
                "source_url": source_url,
                "mode": "live",
                "fetched_at": serve._kl_live._now_iso(),
                "ttl_s": 60,
                "data": {"feed": feed},
            }
        finally:
            with active_lock:
                active -= 1
                if active == 0:
                    all_workers_done.set()

    monkeypatch.setattr(serve._kl_live, "get_feed", fake_get_feed)
    monkeypatch.setattr(serve, "_KL_FEED_PULSE_TIMEOUT_S", 0.15)

    started = time.monotonic()
    response = asyncio.run(serve._feeds_pulse())
    elapsed = time.monotonic() - started
    payload = json.loads(response.body)

    assert elapsed < 0.75
    # The endpoint deadline can win the race against a cooperative worker by a
    # few scheduler ticks.  Require that such a worker exits promptly without
    # making the request wait for the abandoned thread.
    assert all_workers_done.wait(0.25)
    assert active == 0
    assert payload["feed_count"] == 7
    assert payload["live_count"] == 6
    assert payload["live_count"] + payload["cached_count"] + payload["down_count"] == 7
    assert payload["down_count"] == 1
    assert [item["feed"] for item in payload["items"]] == [
        "kev", "osv", "rekor", "iss", "celestrak", "prometheus", "fhir"
    ]
    timed_out = payload["items"][4]
    assert timed_out["mode"] == "unavailable"
    assert timed_out["source_url"].startswith("https://")
    assert timed_out["fetched_at"] is None
    assert timed_out["payload_bytes"] == 0
    assert timed_out["error"] == "probe timeout after 0.15s"


def test_live_feed_budget_is_propagated_and_decreases_between_requests(monkeypatch):
    observed_timeouts = []

    def fake_http_get(_url, timeout=20, **_kwargs):
        observed_timeouts.append(timeout)
        time.sleep(0.01)
        return {"vulns": []}

    monkeypatch.setattr(a11oy_live_feeds, "_CACHE", {})
    monkeypatch.setattr(a11oy_live_feeds, "_http_get", fake_http_get)

    payload = a11oy_live_feeds.get_feed("osv", timeout_s=0.20)

    assert payload["mode"] == "live"
    assert len(observed_timeouts) == 5
    assert 0 < observed_timeouts[-1] < observed_timeouts[0] <= 0.20 + 1e-6


def test_feed_pulse_counts_internally_caught_timeout_without_cache_as_down(monkeypatch):
    def timeout_fetch(_feed, deadline=None):
        raise TimeoutError("cooperative test deadline")

    monkeypatch.setattr(a11oy_live_feeds, "_CACHE", {})
    monkeypatch.setattr(a11oy_live_feeds, "_fetch", timeout_fetch)
    monkeypatch.setattr(a11oy_live_feeds, "_load_snapshot", lambda _feed: None)
    unavailable = a11oy_live_feeds.get_feed("celestrak", timeout_s=0.15)

    assert unavailable["mode"] == "unavailable"
    assert unavailable["data"] is None
    assert "TimeoutError" in unavailable["error"]
    assert "cooperative test deadline" in unavailable["error"]

    def fake_get_feed(feed, timeout_s=None):
        assert timeout_s == 0.15
        if feed == "celestrak":
            return unavailable
        source, source_url = serve._kl_live._SOURCE[feed]
        return {
            "source": source,
            "source_url": source_url,
            "mode": "live",
            "fetched_at": serve._kl_live._now_iso(),
            "ttl_s": 60,
            "data": {"feed": feed},
        }

    monkeypatch.setattr(serve._kl_live, "get_feed", fake_get_feed)
    monkeypatch.setattr(serve, "_KL_FEED_PULSE_TIMEOUT_S", 0.15)

    response = asyncio.run(serve._feeds_pulse())
    payload = json.loads(response.body)

    assert payload["live_count"] == 6
    assert payload["cached_count"] == 0
    assert payload["down_count"] == 1
    timed_out = payload["items"][4]
    assert timed_out["mode"] == "unavailable"
    assert timed_out["payload_bytes"] == 0
    assert "cooperative test deadline" in timed_out["error"]


def test_feed_pulse_propagates_internal_timeout_cache_evidence(monkeypatch):
    def timeout_fetch(_feed, deadline=None):
        raise TimeoutError("cooperative test deadline")

    monkeypatch.setattr(a11oy_live_feeds, "_CACHE", {})
    monkeypatch.setattr(a11oy_live_feeds, "_fetch", timeout_fetch)
    monkeypatch.setattr(
        a11oy_live_feeds,
        "_load_snapshot",
        lambda feed: {"snapshot": feed},
    )
    cached = a11oy_live_feeds.get_feed("celestrak", timeout_s=0.15)

    assert cached["mode"] == "cached"
    assert "TimeoutError" in cached["cache_note"]

    def fake_get_feed(feed, timeout_s=None):
        assert timeout_s == 0.15
        if feed == "celestrak":
            return cached
        source, source_url = serve._kl_live._SOURCE[feed]
        return {
            "source": source,
            "source_url": source_url,
            "mode": "live",
            "fetched_at": serve._kl_live._now_iso(),
            "ttl_s": 60,
            "data": {"feed": feed},
        }

    monkeypatch.setattr(serve._kl_live, "get_feed", fake_get_feed)
    monkeypatch.setattr(serve, "_KL_FEED_PULSE_TIMEOUT_S", 0.15)

    response = asyncio.run(serve._feeds_pulse())
    payload = json.loads(response.body)

    assert payload["live_count"] == 6
    assert payload["cached_count"] == 1
    assert payload["down_count"] == 0
    timed_out = payload["items"][4]
    assert timed_out["mode"] == "cached"
    assert timed_out["payload_bytes"] > 0
    assert "TimeoutError" in timed_out["cache_note"]


def test_feed_pulse_preserves_cache_when_worker_propagates_timeout(monkeypatch):
    stale = {
        "data": {"snapshot": "real-stale-celestrak"},
        "ts": time.time() - a11oy_live_feeds._TTL["celestrak"] - 1,
        "mode": "live",
        "iso": "2026-07-25T00:00:00+00:00",
    }

    def fake_get_feed(feed, timeout_s=None):
        assert timeout_s == 0.05
        if feed == "celestrak":
            raise TimeoutError("transport deadline exhausted")
        source, source_url = serve._kl_live._SOURCE[feed]
        return {
            "source": source,
            "source_url": source_url,
            "mode": "live",
            "fetched_at": serve._kl_live._now_iso(),
            "ttl_s": 60,
            "data": {"feed": feed},
        }

    monkeypatch.setattr(a11oy_live_feeds, "_CACHE", {"celestrak": stale})
    monkeypatch.setattr(serve._kl_live, "get_feed", fake_get_feed)
    monkeypatch.setattr(serve, "_KL_FEED_PULSE_TIMEOUT_S", 0.05)

    payload = json.loads(asyncio.run(serve._feeds_pulse()).body)

    assert payload["live_count"] == 6
    assert payload["cached_count"] == 1
    assert payload["down_count"] == 0
    timed_out = payload["items"][4]
    assert timed_out["mode"] == "cached"
    assert timed_out["fetched_at"] == stale["iso"]
    assert timed_out["payload_bytes"] > 0
    assert timed_out["error"] is None
    assert "TimeoutError" in timed_out["cache_note"]


def test_feed_pulse_joins_trickling_worker_and_preserves_cached_evidence(monkeypatch):
    active_streams = 0
    max_active_streams = 0
    stream_calls = 0

    class TricklingResponse:
        headers = {}

        def __enter__(self):
            nonlocal active_streams, max_active_streams
            active_streams += 1
            max_active_streams = max(max_active_streams, active_streams)
            return self

        def __exit__(self, _exc_type, _exc, _traceback):
            nonlocal active_streams
            active_streams -= 1

        def raise_for_status(self):
            return None

        def iter_bytes(self):
            while True:
                # Each byte arrives before a per-read timeout would fire. The
                # absolute body deadline must still terminate the stream.
                time.sleep(0.01)
                yield b" "

    def fake_stream(method, url, **kwargs):
        nonlocal stream_calls
        assert method == "GET"
        assert url == "https://example.test/trickle"
        assert kwargs["follow_redirects"] is True
        stream_calls += 1
        return TricklingResponse()

    original_http_get = a11oy_live_feeds._http_get

    def fake_fetch(feed, deadline=None):
        if feed == "celestrak":
            return original_http_get(
                "https://example.test/trickle",
                timeout=a11oy_live_feeds._remaining_timeout(deadline, 1),
                deadline=deadline,
            )
        if feed == "iss":
            # Unlabeled ISS numbers fail closed (UNAVAILABLE). This test is
            # about the celestrak trickle worker, so supply honest lat/lon.
            return {
                "latitude": 41.2,
                "longitude": -73.4,
                "altitude": 420.1,
                "velocity": 27580.0,
            }
        return {"feed": feed}

    stale = {
        "data": {"snapshot": "real-stale-celestrak"},
        "ts": time.time() - a11oy_live_feeds._TTL["celestrak"] - 1,
        "mode": "live",
        "iso": "2026-07-25T00:00:00+00:00",
    }
    monkeypatch.setattr(a11oy_live_feeds.httpx, "stream", fake_stream)
    monkeypatch.setattr(a11oy_live_feeds, "_fetch", fake_fetch)
    monkeypatch.setattr(a11oy_live_feeds, "_CACHE", {"celestrak": stale})
    monkeypatch.setattr(serve, "_KL_FEED_PULSE_TIMEOUT_S", 0.05)

    started = time.monotonic()
    payloads = [
        json.loads(asyncio.run(serve._feeds_pulse()).body)
        for _ in range(4)
    ]
    elapsed = time.monotonic() - started

    assert elapsed < 1.0
    assert stream_calls == 4
    assert max_active_streams == 1
    assert active_streams == 0
    for payload in payloads:
        assert payload["live_count"] == 6
        assert payload["cached_count"] == 1
        assert payload["down_count"] == 0
        timed_out = payload["items"][4]
        assert timed_out["mode"] == "cached"
        assert timed_out["fetched_at"] == stale["iso"]
        assert timed_out["payload_bytes"] > 0
        assert timed_out["error"] is None
        assert "TimeoutError" in timed_out["cache_note"]
