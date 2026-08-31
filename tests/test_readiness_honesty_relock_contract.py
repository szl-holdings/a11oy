from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

from routers.frontier_reads import normalize_phase_b_payload


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
        # router/stats is a live receipt-backed counter surface: it must NOT
        # admit "modeled" (that would hide a return to synthetic display traffic).
        self.assertNotIn(
  "modeled",
  endpoints["/api/a11oy/v1/router/stats"]["degradedRules"]["allowLabels"],
        )

    def test_router_schema_matches_the_live_counter_payload(self) -> None:
        # serve.py:_a11oy_router_stats_payload reads exact process-lifetime
        # routing-decision counters from szl_llm_registry.router_stats_snapshot
        # (incremented only with trusted routing-receipt writes). The contract
        # must require that live implementation, not the retired wall-clock
        # MODELED display from szl_brain.TIERS.
        schema = MATRIX.SCHEMAS["router_stats"]
        self.assertEqual(schema["properties"]["state"], {"const": "LIVE"})
        self.assertEqual(schema["properties"]["mode"], {"const": "live"})
        self.assertEqual(
  schema["properties"]["throughput_state"],
  {"const": "OBSERVED"},
        )
        self.assertEqual(
  schema["properties"]["counter_scope"],
  {"const": "process_lifetime"},
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
