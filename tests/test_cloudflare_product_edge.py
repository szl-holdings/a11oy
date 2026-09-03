#!/usr/bin/env python3
"""Network-free checks for the bounded A11oy Cloudflare product edge."""
from __future__ import annotations

import importlib.util
import json
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
    def test_authority_is_exact_apex_and_www_wildcards(self) -> None:
        self.assertEqual(edge.APEX_ROUTE, "a-11-oy.com/*")
        self.assertEqual(edge.WWW_ROUTE, "www.a-11-oy.com/*")
        self.assertEqual(edge.DESIRED_ROUTES, (edge.APEX_ROUTE, edge.WWW_ROUTE))
        self.assertNotIn("*.a-11-oy.com", edge.DESIRED_ROUTES)

    def test_empty_route_table_creates_apex_then_www(self) -> None:
        plan = edge.route_plan([])
        self.assertEqual(
            [(item["action"], item["pattern"]) for item in plan],
            [
                ("create-apex-route", edge.APEX_ROUTE),
                ("create-www-route", edge.WWW_ROUTE),
            ],
        )

    def test_known_legacy_routes_are_reconciled_deterministically(self) -> None:
        plan = edge.route_plan(
            [
                {
                    "id": "legacy-root",
                    "pattern": edge.LEGACY_APEX_ROOT_ROUTE,
                    "script": edge.RETIRED_ROOT_SCRIPT,
                },
                {
                    "id": "apex-wildcard",
                    "pattern": edge.APEX_ROUTE,
                    "script": edge.RETIRED_ROOT_SCRIPT,
                },
                {
                    "id": "www-wildcard",
                    "pattern": edge.WWW_ROUTE,
                    "script": edge.RETIRED_WWW_SCRIPT,
                },
            ]
        )
        self.assertEqual(
            [item["action"] for item in plan],
            [
                "delete-known-legacy-apex-root",
                "update-apex-route",
                "update-www-route",
            ],
        )
        self.assertTrue(all(item["script"] in edge.KNOWN_SCRIPT_NAMES for item in plan))

    def test_foreign_route_ownership_fails_closed(self) -> None:
        for pattern, marker in (
            (edge.LEGACY_APEX_ROOT_ROUTE, "LEGACY_APEX_ROUTE_CONFLICT"),
            (edge.APEX_ROUTE, "APEX_ROUTE_CONFLICT"),
            (edge.WWW_ROUTE, "WWW_ROUTE_CONFLICT"),
        ):
            with self.subTest(pattern=pattern):
                with self.assertRaisesRegex(edge.EdgeError, marker):
                    edge.route_plan(
                        [{"id": "foreign", "pattern": pattern, "script": "foreign"}]
                    )

    def test_duplicate_route_pattern_fails_closed(self) -> None:
        with self.assertRaisesRegex(edge.EdgeError, "DUPLICATE_ROUTE_PATTERN"):
            edge.route_plan(
                [
                    {"id": "one", "pattern": edge.APEX_ROUTE, "script": edge.SCRIPT_NAME},
                    {"id": "two", "pattern": edge.APEX_ROUTE, "script": edge.SCRIPT_NAME},
                ]
            )

    def test_route_application_uses_exact_patterns_and_ids(self) -> None:
        plan = [
            {
                "action": "delete-known-legacy-apex-root",
                "pattern": edge.LEGACY_APEX_ROOT_ROUTE,
                "route_id": "legacy-root",
                "script": edge.RETIRED_ROOT_SCRIPT,
            },
            {
                "action": "create-apex-route",
                "pattern": edge.APEX_ROUTE,
                "script": edge.SCRIPT_NAME,
            },
            {
                "action": "update-www-route",
                "pattern": edge.WWW_ROUTE,
                "route_id": "www-route",
                "from_script": edge.RETIRED_WWW_SCRIPT,
                "script": edge.SCRIPT_NAME,
            },
        ]
        with mock.patch.object(
            edge,
            "request_json",
            side_effect=[
                {"success": True, "result": {"id": "legacy-root"}},
                {"success": True, "result": {"id": "apex-created", "script": edge.SCRIPT_NAME}},
                {"success": True, "result": {"id": "www-route", "script": edge.SCRIPT_NAME}},
            ],
        ) as request:
            results = edge.apply_route_plan(
                "zone",
                "secret",
                plan,
                dry_run=False,
            )
        self.assertEqual([row["state"] for row in results], ["deleted", "created", "updated"])
        self.assertEqual(request.call_count, 3)
        self.assertEqual(
            request.call_args_list[1],
            mock.call(
                "POST",
                "/zones/zone/workers/routes",
                bearer="secret",
                payload={"pattern": edge.APEX_ROUTE, "script": edge.SCRIPT_NAME},
            ),
        )
        self.assertEqual(
            request.call_args_list[2],
            mock.call(
                "PUT",
                "/zones/zone/workers/routes/www-route",
                bearer="secret",
                payload={"pattern": edge.WWW_ROUTE, "script": edge.SCRIPT_NAME},
            ),
        )

    def test_dry_run_never_calls_provider_mutation(self) -> None:
        plan = edge.route_plan([])
        with mock.patch.object(edge, "request_json") as request:
            results = edge.apply_route_plan("zone", "secret", plan, dry_run=True)
        request.assert_not_called()
        self.assertEqual([row["state"] for row in results], ["would-apply", "would-apply"])

    def test_missing_token_is_unavailable_and_never_recorded(self) -> None:
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {}, clear=True),
            mock.patch(
                "sys.argv",
                [str(SCRIPT), "--report", str(Path(tmp) / "report.json")],
            ),
        ):
            self.assertEqual(edge.main(), 2)
            report = json.loads((Path(tmp) / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "UNAVAILABLE")
        self.assertFalse(report["token_recorded"])
        self.assertFalse(report["dns_mutated"])
        self.assertNotIn("Bearer", json.dumps(report))

    def test_error_text_is_bounded_single_line_and_redacts_token(self) -> None:
        secret = "cf_sensitive_value"
        rendered = edge._safe_error(
            RuntimeError(f"first\nsecond {secret} " + ("x" * 5000)),
            secret,
        )
        self.assertNotIn(secret, rendered)
        self.assertIn("<redacted>", rendered)
        self.assertNotIn("\n", rendered)
        self.assertLessEqual(len(rendered), 4000)

    def test_public_probe_requires_root_honesty_and_www_contracts(self) -> None:
        observations = [
            {
                "status": 301,
                "location": "https://a-11-oy.com/__szl_edge_probe__/path?contract=v3&preserve=yes",
                "edge": edge.EDGE_MARKER,
                "content_type": None,
                "final_url": "https://www.a-11-oy.com/__szl_edge_probe__/path?contract=v3&preserve=yes",
                "body": "",
            },
            {
                "status": 200,
                "location": None,
                "edge": edge.EDGE_MARKER,
                "content_type": "text/html",
                "final_url": "https://a-11-oy.com/",
                "body": "<title>a11oy · SZL</title>",
            },
            {
                "status": 200,
                "location": None,
                "edge": edge.EDGE_MARKER,
                "content_type": "application/json",
                "final_url": "https://a-11-oy.com/api/a11oy/v1/honest",
                "body": json.dumps({"organ": "a11oy", "locked_formula_count": 8}),
            },
        ]
        with mock.patch.object(edge, "_observation", side_effect=observations):
            result = edge.public_probe(attempts=1)
        self.assertTrue(result["root_verified"])
        self.assertTrue(result["honest_verified"])
        self.assertTrue(result["www_verified"])
        self.assertNotIn("body", result["root"])
        self.assertNotIn("body", result["honest"])

    def test_public_probe_rejects_missing_edge_marker(self) -> None:
        observations = [
            {
                "status": 301,
                "location": "https://a-11-oy.com/__szl_edge_probe__/path?contract=v3&preserve=yes",
                "edge": edge.EDGE_MARKER,
                "body": "",
            },
            {"status": 200, "edge": None, "body": "a11oy"},
            {
                "status": 200,
                "edge": edge.EDGE_MARKER,
                "body": json.dumps({"organ": "a11oy", "locked_formula_count": 8}),
            },
        ]
        with (
            mock.patch.object(edge, "_observation", side_effect=observations),
            mock.patch.object(edge.time, "sleep"),
        ):
            with self.assertRaisesRegex(edge.EdgeError, "PUBLIC_PROBE_FAILED"):
                edge.public_probe(attempts=1)

    def test_worker_is_fixed_origin_and_never_redirects_apex_to_hf(self) -> None:
        text = WORKER.read_text(encoding="utf-8")
        self.assertIn('const ORIGIN_HOST = "szlholdings-a11oy.hf.space"', text)
        self.assertIn('const PRODUCT_HOST = "a-11-oy.com"', text)
        self.assertIn('const WWW_HOST = "www.a-11-oy.com"', text)
        self.assertIn("await fetchImpl(outgoing)", text)
        self.assertIn("status: 301", text)
        self.assertIn("errorResponse(421", text)
        self.assertIn("status,", text)
        self.assertIn("origin_unavailable", text)
        self.assertNotIn("eval(", text)
        self.assertNotIn("new Function", text)
        self.assertNotIn("Response.redirect(upstream", text)


if __name__ == "__main__":
    unittest.main()
