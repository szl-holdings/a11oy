#!/usr/bin/env python3
"""Network-free checks for the www-only A11oy Cloudflare redirect."""
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
    def test_desired_route_is_www_only(self) -> None:
        self.assertEqual(edge.WWW_ROUTE, "www.a-11-oy.com/*")
        self.assertEqual(edge.LEGACY_APEX_ROUTE, "a-11-oy.com/")
        self.assertEqual(edge.FORBIDDEN_APEX_WILDCARD, "a-11-oy.com/*")
        self.assertNotEqual(edge.WWW_ROUTE, edge.LEGACY_APEX_ROUTE)

    def test_empty_route_table_creates_only_www(self) -> None:
        self.assertEqual(
            edge.route_plan([]),
            [
                {
                    "action": "create-www-route",
                    "pattern": "www.a-11-oy.com/*",
                    "script": edge.SCRIPT_NAME,
                }
            ],
        )

    def test_known_legacy_apex_is_deleted_before_www_update(self) -> None:
        plan = edge.route_plan(
            [
                {
                    "id": "legacy-apex",
                    "pattern": edge.LEGACY_APEX_ROUTE,
                    "script": edge.RETIRED_SCRIPT_NAME,
                },
                {
                    "id": "legacy-www",
                    "pattern": edge.WWW_ROUTE,
                    "script": edge.RETIRED_SCRIPT_NAME,
                },
            ]
        )
        self.assertEqual(
            [item["action"] for item in plan],
            ["delete-known-legacy-apex-route", "update-www-route"],
        )
        self.assertEqual(plan[0]["route_id"], "legacy-apex")
        self.assertEqual(plan[1]["route_id"], "legacy-www")
        self.assertEqual(plan[1]["script"], edge.SCRIPT_NAME)

    def test_foreign_exact_apex_route_fails_closed(self) -> None:
        with self.assertRaisesRegex(edge.EdgeError, "APEX_ROUTE_CONFLICT"):
            edge.route_plan(
                [
                    {
                        "id": "foreign-apex",
                        "pattern": edge.LEGACY_APEX_ROUTE,
                        "script": "foreign-worker",
                    }
                ]
            )

    def test_any_apex_wildcard_fails_closed(self) -> None:
        with self.assertRaisesRegex(edge.EdgeError, "APEX_WILDCARD_CONFLICT"):
            edge.route_plan(
                [
                    {
                        "id": "wildcard",
                        "pattern": edge.FORBIDDEN_APEX_WILDCARD,
                        "script": edge.RETIRED_SCRIPT_NAME,
                    }
                ]
            )

    def test_foreign_www_route_fails_closed(self) -> None:
        with self.assertRaisesRegex(edge.EdgeError, "WWW_ROUTE_CONFLICT"):
            edge.route_plan(
                [
                    {
                        "id": "foreign-www",
                        "pattern": edge.WWW_ROUTE,
                        "script": "foreign-worker",
                    }
                ]
            )

    def test_route_application_deletes_then_updates_exact_ids(self) -> None:
        plan = [
            {
                "action": "delete-known-legacy-apex-route",
                "pattern": edge.LEGACY_APEX_ROUTE,
                "route_id": "legacy-apex",
                "script": edge.RETIRED_SCRIPT_NAME,
            },
            {
                "action": "update-www-route",
                "pattern": edge.WWW_ROUTE,
                "route_id": "legacy-www",
                "from_script": edge.RETIRED_SCRIPT_NAME,
                "script": edge.SCRIPT_NAME,
            },
        ]
        with mock.patch.object(
            edge,
            "request_json",
            side_effect=[
                {"success": True, "result": {"id": "legacy-apex"}},
                {
                    "success": True,
                    "result": {"id": "legacy-www", "script": edge.SCRIPT_NAME},
                },
            ],
        ) as request:
            results = edge.apply_route_plan("zone", "secret", plan)
        self.assertEqual([row["state"] for row in results], ["deleted", "updated"])
        self.assertEqual(request.call_count, 2)
        self.assertEqual(
            request.call_args_list[0],
            mock.call(
                "DELETE",
                "/zones/zone/workers/routes/legacy-apex",
                bearer="secret",
            ),
        )
        self.assertEqual(
            request.call_args_list[1],
            mock.call(
                "PUT",
                "/zones/zone/workers/routes/legacy-www",
                bearer="secret",
                payload={"pattern": edge.WWW_ROUTE, "script": edge.SCRIPT_NAME},
            ),
        )

    def test_missing_token_is_unavailable_and_not_recorded(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch(
                "sys.argv",
                [str(SCRIPT), "--report", str(Path(tmp) / "report.json")],
            ),
        ):
            self.assertEqual(edge.main(), 2)
            text = (Path(tmp) / "report.json").read_text(encoding="utf-8")
            self.assertIn('"token_recorded": false', text)
            self.assertIn('"apex_proxy_authorized": false', text)
            self.assertNotIn("Bearer", text)

    def test_public_probe_uses_literal_www_path_and_exact_apex_target(self) -> None:
        with (
            mock.patch.object(
                edge,
                "_redirect_observation",
                return_value={
                    "status": 301,
                    "location": "https://a-11-oy.com/__szl_www_redirect_probe__?contract=v2",
                    "edge": edge.EDGE_MARKER,
                    "final_url": "https://www.a-11-oy.com/__szl_www_redirect_probe__?contract=v2",
                },
            ) as redirect,
            mock.patch.object(
                edge,
                "_apex_observation",
                return_value={
                    "status": 200,
                    "edge": None,
                    "final_url": "https://a-11-oy.com/",
                    "body_has_szl": True,
                },
            ),
        ):
            result = edge.public_probe(attempts=1)
        redirect.assert_called_once_with(
            "https://www.a-11-oy.com/__szl_www_redirect_probe__?contract=v2"
        )
        self.assertTrue(result["www_verified"])
        self.assertTrue(result["apex_verified"])

    def test_retired_apex_marker_fails_public_proof(self) -> None:
        with (
            mock.patch.object(
                edge,
                "_redirect_observation",
                return_value={
                    "status": 301,
                    "location": "https://a-11-oy.com/__szl_www_redirect_probe__?contract=v2",
                    "edge": edge.EDGE_MARKER,
                    "final_url": "https://www.a-11-oy.com/__szl_www_redirect_probe__?contract=v2",
                },
            ),
            mock.patch.object(
                edge,
                "_apex_observation",
                return_value={
                    "status": 200,
                    "edge": edge.RETIRED_EDGE_MARKER,
                    "final_url": "https://a-11-oy.com/",
                    "body_has_szl": True,
                },
            ),
            mock.patch.object(edge.time, "sleep"),
        ):
            with self.assertRaisesRegex(edge.EdgeError, "PUBLIC_PROBE_FAILED"):
                edge.public_probe(attempts=1)

    def test_worker_is_incapable_of_upstream_proxying(self) -> None:
        text = WORKER.read_text(encoding="utf-8")
        self.assertIn("www.a-11-oy.com", text)
        self.assertIn("a-11-oy.com", text)
        self.assertIn("status: 301", text)
        self.assertIn("status: 421", text)
        self.assertIn("canonicalLocation", text)
        self.assertIn("a11oy-www-redirect-v2", text)
        self.assertNotIn("hf.space", text)
        self.assertNotIn("await fetch(", text)
        self.assertNotIn("ORIGIN_HOST", text)
        self.assertNotIn("x-forwarded-host", text)
        self.assertNotIn("eval(", text)


if __name__ == "__main__":
    unittest.main()
