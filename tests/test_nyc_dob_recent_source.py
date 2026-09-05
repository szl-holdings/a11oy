# SPDX-License-Identifier: Apache-2.0
"""DOB query/date regressions. No network, provider writes, or application boot."""
from __future__ import annotations

import ast
import datetime as dt
import re
import unittest
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit


class FixedDatetime(dt.datetime):
    @classmethod
    def now(cls, tz=None):
        return cls(2026, 9, 4, tzinfo=dt.timezone.utc)


class TestDOBRecentSource(unittest.TestCase):
    source_path = "a11oy_vertical_feeds.py"
    function_name = "feed_nyc_dob"

    def setUp(self):
        source = Path(self.source_path).read_text(encoding="utf-8")
        nodes = [n for n in ast.parse(source).body
                 if isinstance(n, ast.FunctionDef) and n.name == self.function_name]
        self.assertEqual(len(nodes), 1)
        self.calls = []
        self.rows = []
        self.sentinel = object()
        self.ns = {
            "Any": Any, "datetime": FixedDatetime, "timezone": dt.timezone, "re": re,
            "_bounded_limit": self.bound_limit,
            "_variant_cache_key": lambda source, **kw: (source, tuple(sorted(kw.items()))),
            "_cached_fetch": self.fetch,
        }
        exec(compile(ast.Module(body=nodes, type_ignores=[]), "<DOB source>", "exec"), self.ns)
        self.feed = self.ns[self.function_name]

    @staticmethod
    def bound_limit(value, default, maximum):
        try:
            value = int(value)
        except (TypeError, ValueError, OverflowError):
            value = default
        return max(1, min(maximum, value))

    def fetch(self, key, url, ttl, parser):
        self.calls.append((key, url, ttl, parser))
        return {"value": parser(self.rows), "freshness": self.sentinel}

    @staticmethod
    def row(date, identity="123"):
        return {"issue_date": date, "isn_dob_bis_viol": identity,
                "violation_type": "SOURCE VALUE", "house_number": "10",
                "street": "EXAMPLE STREET", "boro": "1"}

    def test_query_has_fixed_origin_order_upper_bound_and_bounded_overfetch(self):
        self.feed(30)
        key, url, ttl, _ = self.calls[-1]
        parts = urlsplit(url)
        query = parse_qs(parts.query)
        self.assertEqual((parts.scheme, parts.netloc, parts.path),
                         ("https", "data.cityofnewyork.us", "/resource/3h2n-5cm9.json"))
        self.assertEqual(query["$order"], ["issue_date DESC, isn_dob_bis_viol DESC"])
        self.assertEqual(query["$where"], ["issue_date between '00010101' and '20260904'"])
        self.assertEqual(query["$limit"], ["90"])
        self.assertEqual(ttl, 1800)
        self.assertEqual(dict(key[1])["order"], query["$order"][0])
        self.assertEqual(dict(key[1])["as_of"], "20260904")
        self.assertIn("issue_date", query["$select"][0].split(","))

    def test_latest_valid_rows_not_first_historical_rows(self):
        self.rows = [self.row("19880101", "1"), self.row("20260903", "8"),
                     self.row("20260904", "2")]
        result = self.feed(1)
        self.assertEqual([r["issued"] for r in result["value"]["items"]], ["20260904"])
        self.assertIs(result["freshness"], self.sentinel)

    def test_malformed_impossible_and_future_dates_are_counted_not_invented(self):
        bad = ["Y9990120", "Y30819", "T90517", "33218262", "20260230",
               "20260905", "2026-09-04", "", None, 20260904, "２０２６０９０４"]
        self.rows = [self.row(d) for d in bad] + [self.row("20260903")]
        value = self.feed(20)["value"]
        self.assertEqual(value["selection"]["invalid_dates_rejected"], len(bad))
        self.assertEqual([r["issued"] for r in value["items"]], ["20260903"])
        self.assertFalse(value["selection"]["requested_count_met"])

    def test_leap_year_date_retained_and_nonleap_date_rejected(self):
        self.rows = [self.row("20240229"), self.row("20250229")]
        value = self.feed(5)["value"]
        self.assertEqual([r["issued"] for r in value["items"]], ["20240229"])
        self.assertEqual(value["selection"]["invalid_dates_rejected"], 1)

    def test_invalid_rows_rejected_without_mutating_input(self):
        original = self.row("20260903")
        self.rows = [None, ["not", "a", "row"], original]
        value = self.feed(5)["value"]
        self.assertEqual(value["selection"]["invalid_rows_rejected"], 2)
        self.assertEqual(original, self.row("20260903"))
        self.assertTrue(value["selection"]["source_dates_are_not_case_status"])

    def test_wrong_provider_shape_fails_instead_of_becoming_empty_live_data(self):
        self.rows = {"error": "upstream error"}
        with self.assertRaisesRegex(ValueError, "JSON array"):
            self.feed(5)

    def test_limit_is_bounded_and_result_is_not_padded(self):
        self.rows = [self.row("20260903")]
        self.feed(100000)
        self.assertEqual(parse_qs(urlsplit(self.calls[-1][1]).query)["$limit"], ["1000"])
        value = self.feed(5)["value"]
        self.assertEqual(len(value["items"]), 1)
        self.assertFalse(value["selection"]["requested_count_met"])

    def test_no_valid_data_stays_empty_with_explicit_rejection_count(self):
        self.rows = [self.row("20260230")]
        value = self.feed(5)["value"]
        self.assertEqual(value["items"], [])
        self.assertEqual(value["selection"]["invalid_dates_rejected"], 1)
        self.assertFalse(value["selection"]["requested_count_met"])

    def test_stable_tie_break_and_source_field_preservation(self):
        self.rows = [self.row("20260903", "001"), self.row("20260903", "003"),
                     self.row("20260903", "002")]
        value = self.feed(3)["value"]
        self.assertEqual([r["id"] for r in value["items"]], ["003", "002", "001"])
        self.assertEqual(value["items"][0]["type"], "SOURCE VALUE")
        self.assertEqual(value["items"][0]["street"], "10 EXAMPLE STREET")

    def test_next_day_uses_a_distinct_cache_variant(self):
        self.feed(3)
        first = self.calls[-1][0]
        class NextDay(FixedDatetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 9, 5, tzinfo=dt.timezone.utc)
        self.ns["datetime"] = NextDay
        self.feed(3)
        self.assertNotEqual(first, self.calls[-1][0])


class TestDOBDeepSource(TestDOBRecentSource):
    """The detailed Market Pulse feed must satisfy the same date contract."""
    source_path = "a11oy_deva_feeds.py"
    function_name = "feed_dob_violations"

    def test_detailed_source_fields_are_preserved_and_description_is_bounded(self):
        row = self.row("20260903")
        row.update(violation_category="SOURCE CATEGORY", block="00123", lot="0001",
                   description="x" * 200)
        self.rows = [row]
        value = self.feed()["value"]
        item = value["items"][0]
        self.assertEqual(item["category"], "SOURCE CATEGORY")
        self.assertEqual(item["block"], "00123")
        self.assertEqual(item["lot"], "0001")
        self.assertEqual(item["desc"], "x" * 120)
        self.assertEqual(value["selection"]["upstream_limit"], 180)
        self.assertEqual(self.calls[-1][0][0], "dob_viol")
        selected = parse_qs(urlsplit(self.calls[-1][1]).query)["$select"][0].split(",")
        self.assertTrue({"violation_category", "block", "lot", "description"}.issubset(selected))


if __name__ == "__main__":
    unittest.main()
