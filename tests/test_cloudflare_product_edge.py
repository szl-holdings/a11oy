#!/usr/bin/env python3
"""Network-free checks for the exact-scope A11oy edge adapter."""
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repair_cloudflare_product_edge.py"
WORKER = ROOT / "cloudflare" / "a11oy-product-root-worker.mjs"
spec = importlib.util.spec_from_file_location("edge", SCRIPT)
assert spec and spec.loader
edge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(edge)


class ProductEdgeContract(unittest.TestCase):
    def test_routes_are_exact_scope(self) -> None:
        self.assertEqual(edge.ROUTES, ("a-11-oy.com/", "www.a-11-oy.com/*"))
        self.assertNotIn("a-11-oy.com/*", edge.ROUTES)

    def test_conflicting_exact_route_fails_closed(self) -> None:
        with mock.patch.object(edge, "request_json", return_value={"result": [{"id": "r1", "pattern": "a-11-oy.com/", "script": "foreign"}]}):
            with self.assertRaises(edge.EdgeError) as raised:
                edge.upsert_routes("zone", "token", dry_run=False)
        self.assertIn("ROUTE_CONFLICT", str(raised.exception))

    def test_missing_token_is_unavailable_and_not_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, mock.patch.dict(os.environ, {}, clear=True), mock.patch("sys.argv", [str(SCRIPT), "--report", str(Path(tmp) / "report.json")]):
            self.assertEqual(edge.main(), 2)
            text = (Path(tmp) / "report.json").read_text(encoding="utf-8")
            self.assertIn('"token_recorded": false', text)
            self.assertNotIn("Bearer", text)

    def test_public_probe_targets_literal_exact_root(self) -> None:
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('url = f"https://{ZONE_NAME}/"', text)
        self.assertNotIn("?szl_edge_probe=", text)

    def test_worker_proxies_only_to_canonical_runtime_and_rewrites_location(self) -> None:
        text = WORKER.read_text(encoding="utf-8")
        self.assertIn("szlholdings-a11oy.hf.space", text)
        self.assertIn("www.a-11-oy.com", text)
        self.assertIn("Response.redirect", text)
        self.assertIn("x-szl-edge", text)
        self.assertNotIn("eval(", text)


if __name__ == "__main__":
    unittest.main()
