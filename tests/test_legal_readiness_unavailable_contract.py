from __future__ import annotations

import ast
import importlib.util
import time
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
VERTICAL_FEEDS = ROOT / "a11oy_vertical_feeds.py"
DEVB_ENDPOINTS = ROOT / "a11oy_devb_endpoints.py"
GENERATOR = ROOT / "tools" / "readiness-harness" / "gen_tabs_matrix.py"

LEGAL_ENDPOINTS = (
    "/api/a11oy/v1/vert/legal/feed",
    "/api/a11oy/v1/devb/legal/matter?limit=1",
    "/api/a11oy/v1/devb/legal/matter?term=defense&limit=1",
    "/api/a11oy/v1/devb/legal/matter?term=insurance&limit=1",
    "/api/a11oy/v1/devb/legal/regulatory?limit=1",
    "/api/a11oy/v1/devb/legal/exposure?limit=1",
)


def _load_helper(path: Path, function_name: str):
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    function = next(
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == function_name
    )
    module = ast.Module(body=[function], type_ignores=[])
    namespace: dict[str, Any] = {
        "Any": Any,
        "time": time,
        "_READINESS_PUBLIC_FRESHNESS": frozenset({"live", "cached"}),
    }
    exec(compile(module, str(path), "exec"), namespace)
    return namespace[function_name]


def _load_generator():
    spec = importlib.util.spec_from_file_location("legal_readiness_matrix", GENERATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class LegalReadinessUnavailableContractTests(unittest.TestCase):
    def test_never_observed_sources_use_canonical_unavailable_without_data_invention(self) -> None:
        observed_at = 1_788_400_000.0
        payload = {
            "value": None,
            "freshness": {
                "status": "unavailable",
                "fetched_at": observed_at,
                "error": "upstream timeout",
            },
        }
        helpers = (
            _load_helper(VERTICAL_FEEDS, "_readiness_public_source"),
            _load_helper(DEVB_ENDPOINTS, "_readiness_public_source_local"),
        )
        for helper in helpers:
            with self.subTest(helper=helper.__name__):
                result = helper(payload)
                self.assertIsNone(result["value"])
                self.assertEqual(result["freshness"]["status"], "UNAVAILABLE")
                self.assertEqual(result["freshness"]["fetched_at"], observed_at)
                self.assertEqual(result["freshness"]["error"], "upstream timeout")
                self.assertEqual(payload["freshness"]["status"], "unavailable")

    def test_last_good_sources_remain_cached_with_original_clock(self) -> None:
        observed_at = time.time() - 45.0
        payload = {
            "value": {"items": [{"url": "https://example.invalid/evidence"}]},
            "freshness": {
                "status": "stale",
                "fetched_at": observed_at,
                "error": "refresh timeout",
            },
        }
        helpers = (
            _load_helper(VERTICAL_FEEDS, "_readiness_public_source"),
            _load_helper(DEVB_ENDPOINTS, "_readiness_public_source_local"),
        )
        for helper in helpers:
            with self.subTest(helper=helper.__name__):
                result = helper(payload)
                self.assertEqual(result["freshness"]["status"], "cached")
                self.assertEqual(result["freshness"]["fetched_at"], observed_at)
                self.assertEqual(result["value"], payload["value"])

    def test_every_legal_probe_explicitly_admits_only_named_degraded_evidence(self) -> None:
        matrix = _load_generator().build()
        for endpoint in LEGAL_ENDPOINTS:
            with self.subTest(endpoint=endpoint):
                contract = matrix["endpoints"][endpoint]
                self.assertTrue(contract["citationsRequired"])
                labels = contract["degradedRules"]["allowLabels"]
                self.assertIn("UNAVAILABLE", labels)
                self.assertNotIn("unavailable", labels)
                self.assertNotIn("stale", labels)
                self.assertNotIn("mock", labels)

    def test_devb_legal_responses_cite_public_sources_even_when_results_are_absent(self) -> None:
        source = DEVB_ENDPOINTS.read_text(encoding="utf-8")
        self.assertIn("_COURTLISTENER_CITATION", source)
        self.assertIn("_FEDERAL_REGISTER_CITATION", source)
        self.assertIn("_SEC_EDGAR_CITATION", source)
        self.assertIn('"sources_cited": [dict(_COURTLISTENER_CITATION)]', source)
        self.assertIn('"sources_cited": [dict(_FEDERAL_REGISTER_CITATION)]', source)
        self.assertIn('result["sources_cited"] = [', source)


if __name__ == "__main__":
    unittest.main(verbosity=2)
