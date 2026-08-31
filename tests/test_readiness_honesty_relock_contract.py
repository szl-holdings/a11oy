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
        self.assertEqual(
  endpoints["/api/a11oy/v1/router/stats"]["degradedRules"]["allowLabels"],
  ["live", "cached"],
        )

    def test_router_schema_binds_live_counter_identity_and_clocks(self) -> None:
        schema = MATRIX.SCHEMAS["router_stats"]
        endpoint = MATRIX.ENDPOINTS["/api/a11oy/v1/router/stats"]
        self.assertEqual(endpoint["freshnessSLA"], 5 * MATRIX.MIN)
        self.assertEqual(schema["properties"]["state"], {"const": "LIVE"})
        self.assertEqual(schema["properties"]["mode"], {"const": "live"})
        self.assertEqual(
  schema["properties"]["throughput_state"],
  {"const": "OBSERVED"},
        )
        self.assertEqual(schema["properties"]["counter_state"], {"const": "OBSERVED"})
        self.assertEqual(
  schema["properties"]["source"],
  {"const": "szl_llm_registry.router_stats_snapshot"},
        )
        self.assertIn("routingDecisionsSinceStart", schema["required"])
        self.assertIn("counter_scope", schema["required"])
        self.assertIn("counter_started_at", schema["required"])
        self.assertEqual(
  schema["requiredPathTypes"]["counter_started_at"],
  "process_epoch_timestamp",
        )
        self.assertEqual(schema["requiredPathTypes"]["observed_at"], "timestamp")
        self.assertEqual(
  schema["semanticContract"]["catalog"],
  MATRIX.ROUTER_STATS_CATALOG,
        )
        self.assertEqual(
  schema["properties"]["honesty"]["const"],
  MATRIX.ROUTER_STATS_HONESTY,
        )

    def test_protected_router_catalog_exactly_matches_runtime_registry(self) -> None:
        alloy_ids = {model["model_id"] for model in ALLOY_ROSTER}
        runtime_identity = [
  {"tier": f"T{model['tier']}", "model": model["model_id"]}
  for model in MODEL_REGISTRY
  if model["model_id"] not in alloy_ids
        ] + [
  {"tier": "T90", "model": model["model_id"]}
  for model in ALLOY_ROSTER
        ]
        self.assertEqual(MATRIX.ROUTER_STATS_CATALOG, runtime_identity)


if __name__ == "__main__":
    unittest.main()
