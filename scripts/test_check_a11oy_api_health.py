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

    # --- HITL action ring (governed envelope + action-ring record) ------------
    HITL_REQUIRED = ENVELOPE + ["ok", "entry", "audit_depth"]

    def test_hitl_act_contract_passes(self):
        # operator/act carries the governed envelope PLUS the action-ring record.
        body = json.dumps(
            {
                "ok": True,
                "action": "acknowledge",
                "target": "demo",
                "entry": {"action": "acknowledge", "entry_hash": "a" * 64, "prev_hash": "0" * 64},
                "audit_depth": 1,
                "receipt": {"signed": False},
                "honesty": "hash-chained audit ring",
                "status": "REAL",
                "citations": [],
                "fetchedAt": "2026-06-15T00:00:00+00:00",
                "doctrine": "v11",
            }
        ).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, self.HITL_REQUIRED)
        self.assertTrue(ok, reason)

    def test_hitl_act_missing_entry_fails(self):
        # Drop the hash-chained ring record -> the HITL contract is broken.
        body = json.dumps(
            {
                "ok": True,
                "action": "acknowledge",
                "audit_depth": 1,
                "status": "REAL",
                "citations": [],
                "fetchedAt": "2026-06-15T00:00:00+00:00",
                "doctrine": "v11",
            }
        ).encode("utf-8")  # no entry
        ok, reason = evaluate(200, "application/json", body, self.HITL_REQUIRED)
        self.assertFalse(ok)
        self.assertIn("entry", reason)

    def test_hitl_act_missing_audit_depth_fails(self):
        body = json.dumps(
            {
                "ok": True,
                "action": "acknowledge",
                "entry": {"entry_hash": "a" * 64},
                "status": "REAL",
                "citations": [],
                "fetchedAt": "2026-06-15T00:00:00+00:00",
                "doctrine": "v11",
            }
        ).encode("utf-8")  # no audit_depth
        ok, reason = evaluate(200, "application/json", body, self.HITL_REQUIRED)
        self.assertFalse(ok)
        self.assertIn("audit_depth", reason)

    def test_hitl_act_envelope_stripped_fails(self):
        # The action-ring record is present but the governed envelope is dropped.
        body = json.dumps(
            {"ok": True, "action": "acknowledge", "entry": {"entry_hash": "a" * 64}, "audit_depth": 1}
        ).encode("utf-8")  # no status/citations/fetchedAt/doctrine
        ok, reason = evaluate(200, "application/json", body, self.HITL_REQUIRED)
        self.assertFalse(ok)
        self.assertIn("status", reason)

    # --- MCP tools manifest (own contract, no governed envelope) --------------
    def test_mcp_tools_contract_passes(self):
        # Count is NOT pinned (it grows as formula tools + sibling surfaces merge).
        body = json.dumps(
            {
                "count": 11,
                "tools": [{"name": "a11oy_gate", "flagship": "a11oy"}],
                "flagship": "a11oy",
                "flagships": ["a11oy", "killinchu"],
                "doctrine": "v11",
            }
        ).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["count", "tools", "flagship"])
        self.assertTrue(ok, reason)

    def test_mcp_tools_spa_html_200_fails(self):
        # The whole point: an SPA-HTML 200 on the MCP manifest must go red.
        ok, reason = evaluate(200, "text/html; charset=utf-8", SPA_HTML, ["count", "tools", "flagship"])
        self.assertFalse(ok)
        self.assertIn("not application/json", reason)

    def test_mcp_tools_missing_tools_fails(self):
        body = json.dumps({"count": 11, "flagship": "a11oy"}).encode("utf-8")  # no tools
        ok, reason = evaluate(200, "application/json", body, ["count", "tools", "flagship"])
        self.assertFalse(ok)
        self.assertIn("tools", reason)

    # --- MCP tool calls (list / run / proof-status) — own {tool,status,...} ----
    def test_mcp_list_formulas_contract_passes(self):
        body = json.dumps(
            {"tool": "list_formulas", "status": "ok", "count": 22, "formulas": [], "doctrine": "v11"}
        ).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["tool", "status", "formulas"])
        self.assertTrue(ok, reason)

    def test_mcp_list_formulas_missing_formulas_fails(self):
        body = json.dumps({"tool": "list_formulas", "status": "ok", "count": 22}).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["tool", "status", "formulas"])
        self.assertFalse(ok)
        self.assertIn("formulas", reason)

    def test_mcp_run_formula_contract_passes(self):
        body = json.dumps(
            {"tool": "run_formula", "status": "ok", "result": {"ok": True, "result": 0.92}, "doctrine": "v11"}
        ).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["tool", "status", "result"])
        self.assertTrue(ok, reason)

    def test_mcp_run_formula_missing_result_fails(self):
        body = json.dumps({"tool": "run_formula", "status": "ok"}).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["tool", "status", "result"])
        self.assertFalse(ok)
        self.assertIn("result", reason)

    def test_mcp_proof_status_contract_passes(self):
        body = json.dumps(
            {"tool": "formula_proof_status", "status": "ok", "name": "lambda_aggregate",
             "proof_status": "PROVEN(A1-A4); uniqueness CONJECTURE"}
        ).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["tool", "status", "proof_status"])
        self.assertTrue(ok, reason)

    def test_mcp_proof_status_missing_proof_status_fails(self):
        body = json.dumps({"tool": "formula_proof_status", "status": "ok", "name": "x"}).encode("utf-8")
        ok, reason = evaluate(200, "application/json", body, ["tool", "status", "proof_status"])
        self.assertFalse(ok)
        self.assertIn("proof_status", reason)

    def test_mcp_call_503_fails(self):
        # If the formula registry stops importing in-process the call 503s -> red.
        ok, reason = evaluate(503, "application/json", b'{"tool":"list_formulas","error":"registry not available"}',
                              ["tool", "status", "formulas"])
        self.assertFalse(ok)
        self.assertIn("503", reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
