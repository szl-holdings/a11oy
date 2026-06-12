#!/usr/bin/env python3
"""Self-test for evaluate() in check_a11oy_api_health.py.

Proves the checker actually catches the regressions it claims to catch:
SPA-HTML-instead-of-JSON (200 but text/html), non-200, unparseable body, a
non-object payload, and a missing contract key — and that it accepts a valid
governed envelope, a valid /healthz body, and the recommend/ledger contract
shapes (which intentionally do NOT carry the governed envelope). Stdlib
unittest, no network. Guards the validator so a future edit can't silently
neuter the health check.
"""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from check_a11oy_api_health import evaluate, ENVELOPE  # noqa: E402

GOVERNED = json.dumps(
    {
        "status": "REAL",
        "doctrine": "v11",
        "capability": "operator/ask",
        "citations": [],
        "fetchedAt": "2026-06-11T00:00:00+00:00",
        "summary": "grounded answer",
    }
).encode("utf-8")
SPA_HTML = b"<!doctype html><html><head><title>a11oy</title></head><body></body></html>"


class EvaluateTests(unittest.TestCase):
    def test_valid_governed_envelope_passes(self):
        ok, reason = evaluate(200, "application/json", GOVERNED, ENVELOPE)
        self.assertTrue(ok, reason)

    def test_valid_with_charset_suffix_passes(self):
        ok, reason = evaluate(200, "application/json; charset=utf-8", GOVERNED, ENVELOPE)
        self.assertTrue(ok, reason)

    def test_spa_html_200_fails(self):
        ok, reason = evaluate(200, "text/html; charset=utf-8", SPA_HTML, ENVELOPE)
        self.assertFalse(ok)
        self.assertIn("not application/json", reason)

    def test_non_200_fails(self):
        ok, reason = evaluate(503, "application/json", GOVERNED, ENVELOPE)
        self.assertFalse(ok)
        self.assertIn("503", reason)

    def test_internal_error_500_fails(self):
        ok, reason = evaluate(500, "application/json", b'{"detail":"boom"}', ENVELOPE)
        self.assertFalse(ok)
        self.assertIn("500", reason)

    def test_unparseable_json_fails(self):
        ok, reason = evaluate(200, "application/json", b"{not json", ENVELOPE)
        self.assertFalse(ok)
        self.assertIn("not valid JSON", reason)

    def test_non_object_json_fails(self):
        ok, reason = evaluate(200, "application/json", b"[1,2,3]", ENVELOPE)
        self.assertFalse(ok)
        self.assertIn("not an object", reason)

    def test_missing_doctrine_field_fails(self):
        body = json.dumps(
            {"status": "REAL", "citations": [], "fetchedAt": "2026-06-11T00:00:00+00:00"}
        ).encode("utf-8")  # no doctrine
        ok, reason = evaluate(200, "application/json", body, ENVELOPE)
        self.assertFalse(ok)
        self.assertIn("doctrine", reason)

    def test_missing_fetchedat_field_fails(self):
        body = json.dumps(
            {"status": "REAL", "citations": [], "doctrine": "v11"}
        ).encode("utf-8")  # no fetchedAt
        ok, reason = evaluate(200, "application/json", body, ENVELOPE)
        self.assertFalse(ok)
        self.assertIn("fetchedAt", reason)

    def test_healthz_minimal_status_passes(self):
        body = json.dumps({"status": "ok", "organ": "a11oy", "doctrine": "v11"}).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["status"])
        self.assertTrue(ok, reason)

    def test_healthz_missing_status_fails(self):
        body = json.dumps({"organ": "a11oy"}).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["status"])
        self.assertFalse(ok)
        self.assertIn("status", reason)

    def test_recommend_contract_passes_without_governed_envelope(self):
        # recommend has its own shape (no status/doctrine/fetchedAt).
        body = json.dumps(
            {"citations": [], "counts": {}, "honesty": "x", "recommendations": []}
        ).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["citations", "recommendations"])
        self.assertTrue(ok, reason)

    def test_recommend_missing_recommendations_fails(self):
        body = json.dumps({"citations": [], "counts": {}}).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["citations", "recommendations"])
        self.assertFalse(ok)
        self.assertIn("recommendations", reason)

    def test_ledger_contract_passes(self):
        body = json.dumps(
            {"count": 0, "head_seq": 0, "receipts": [], "root_hash": "0" * 64, "total": 0}
        ).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["receipts", "root_hash"])
        self.assertTrue(ok, reason)

    def test_ledger_missing_root_hash_fails(self):
        body = json.dumps({"count": 0, "receipts": []}).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["receipts", "root_hash"])
        self.assertFalse(ok)
        self.assertIn("root_hash", reason)

    # --- console DATA tab contracts (own shapes, no governed envelope) ---------
    def test_formulas_contract_passes(self):
        body = json.dumps({"count": 22, "formulas": []}).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["count", "formulas"])
        self.assertTrue(ok, reason)

    def test_formulas_missing_formulas_fails(self):
        body = json.dumps({"count": 22}).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["count", "formulas"])
        self.assertFalse(ok)
        self.assertIn("formulas", reason)

    def test_bounties_contract_passes(self):
        body = json.dumps({"count": 2, "bounties": [], "honest": True}).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["count", "bounties", "honest"])
        self.assertTrue(ok, reason)

    def test_bounties_missing_honest_flag_fails(self):
        # A tab that drops its honesty disclosure must turn the check red.
        body = json.dumps({"count": 2, "bounties": []}).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["count", "bounties", "honest"])
        self.assertFalse(ok)
        self.assertIn("honest", reason)

    def test_contracting_contract_passes(self):
        body = json.dumps(
            {"areas": [], "summary": "x", "honest": True, "founder_actions": []}
        ).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["areas", "summary", "honest"])
        self.assertTrue(ok, reason)

    def test_readiness_contract_passes(self):
        body = json.dumps(
            {"sections": [], "summary": "x", "honest": True, "organ": "a11oy"}
        ).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["sections", "summary", "honest"])
        self.assertTrue(ok, reason)

    def test_evidence_contract_passes(self):
        body = json.dumps(
            {"claims": [], "total_assertions": 13, "status_counts": {}, "passed": 13}
        ).encode("utf-8")
        ok, reason = evaluate(
            200, "application/json", body, ["claims", "total_assertions", "status_counts"]
        )
        self.assertTrue(ok, reason)

    def test_evidence_missing_status_counts_fails(self):
        body = json.dumps({"claims": [], "total_assertions": 13}).encode("utf-8")
        ok, reason = evaluate(
            200, "application/json", body, ["claims", "total_assertions", "status_counts"]
        )
        self.assertFalse(ok)
        self.assertIn("status_counts", reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
