from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

from routers.frontier_reads import normalize_phase_b_payload
from szl_alloy_models import ALLOY_ROSTER
from szl_llm_registry import MODEL_REGISTRY


ROOT = Path(__file__).resolve().parents[1]
GENERATOR_PATH = ROOT / "tools" / "readiness-harness" / "gen_tabs_matrix.py"
SPEC = importlib.util.spec_from_file_location("readiness_matrix_generator", GENERATOR_PATH)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("unable to load readiness matrix generator")
MATRIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MATRIX)


class ReadinessHonestyRelockTests(unittest.TestCase):
    def test_compound_live_kev_label_is_canonicalized_without_losing_detail(self) -> None:
        detail = (
  "live KEV IDs/dates/vendors + LIVE EPSS (24/24 rows); "
  "LIVE CVSS (13/24 rows; remainder derived-sample)"
        )
        result = normalize_phase_b_payload(
  "/api/a11oy/v1/sec/kevgate",
  {"data_kind": detail, "items": []},
  observed_at="2026-08-29T17:02:13Z",
        )
        self.assertEqual(result["data_kind"], "live")
        self.assertEqual(result["data_kind_detail"], detail)
        self.assertEqual(result["observed_at"], "2026-08-29T17:02:13Z")

    def test_compound_kev_label_with_fabricated_marker_stays_fail_closed(self) -> None:
        detail = "live KEV rows with fabricated enrichment"
        result = normalize_phase_b_payload(
  "/api/a11oy/v1/sec/kevgate",
  {"data_kind": detail, "items": []},
  observed_at="2026-08-29T17:02:13Z",
        )
        self.assertEqual(result["data_kind"], detail)
        self.assertNotIn("data_kind_detail", result)

    def test_non_live_readiness_classes_are_explicitly_admitted(self) -> None:
        endpoints = MATRIX.ENDPOINTS
        self.assertIn(
  "sample",
  endpoints["/api/a11oy/v1/ledger"]["degradedRules"]["allowLabels"],
        )
        self.assertIn(
  "sample",
  endpoints["/api/a11oy/v1/receipt/export"]["degradedRules"]["allowLabels"],
        )
        self.assertIn(
  "degraded",
  endpoints["/api/a11oy/v1/rag/status"]["degradedRules"]["allowLabels"],
        )

    def test_router_stats_admits_only_live_counter_evidence(self) -> None:
        # #1526 (landed via #1538) removed the wall-clock-derived MODELED
        # tier display from /v1/router/stats; the endpoint now serves exact
        # process-lifetime routing-decision counters from szl_llm_registry
        # (locked by tests/test_functest_router_receipts.py and
        # tests/test_router_stats_counter.py, incl. the UNAVAILABLE-not-
        # MODELED failure path). Readmitting "modeled" here would hide a
        # return to synthetic display traffic, so the gate fails closed on it.
        labels = MATRIX.ENDPOINTS[
  "/api/a11oy/v1/router/stats"]["degradedRules"]["allowLabels"]
        self.assertEqual(labels, ["live", "cached"])
        self.assertNotIn("modeled", labels)

    def test_router_schema_matches_the_truthful_live_counter_payload(self) -> None:
        # Same relock intent as the former MODELED-payload check, updated for
        # the receipt-backed counter endpoint that replaced the wall-clock
        # display: the schema must admit exactly the observed LIVE payload.
        schema = MATRIX.SCHEMAS["router_stats"]
        self.assertEqual(schema["properties"]["state"], {"const": "LIVE"})
        self.assertEqual(schema["properties"]["mode"], {"const": "live"})
        self.assertEqual(
  schema["properties"]["throughput_state"],
  {"const": "OBSERVED"},
        )
        self.assertEqual(
  schema["properties"]["source"],
  {"const": "szl_llm_registry.router_stats_snapshot"},
        )
        self.assertIn("routingDecisionsSinceStart", schema["required"])
        self.assertIn("counter_scope", schema["required"])
        self.assertIn("counter_started_at", schema["required"])


if __name__ == "__main__":
    unittest.main()
