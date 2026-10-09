#!/usr/bin/env python3
"""Network-free checks for the bounded A11oy Cloudflare product edge."""
from __future__ import annotations

import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "repair_cloudflare_product_edge.py"
WORKER = ROOT / "cloudflare" / "a11oy-product-root-worker.mjs"
WORKFLOW = ROOT / ".github" / "workflows" / "repair-cloudflare-product-edge-production.yml"
spec = importlib.util.spec_from_file_location("edge", SCRIPT)
assert spec and spec.loader
edge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(edge)


def dns_record(
    record_id: str,
    host: str,
    record_type: str,
    *,
    proxied: bool,
    proxiable: bool = True,
) -> dict[str, object]:
    return {
        "id": record_id,
        "name": host,
        "type": record_type,
        "content": "origin.invalid",
        "ttl": 1,
        "proxied": proxied,
        "proxiable": proxiable,
    }


class ProductEdgeContract(unittest.TestCase):
    def test_provider_repair_requires_dispatch_and_production_environment(self) -> None:
        workflow = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("  pull_request:\n", workflow)
        self.assertIn("  push:\n", workflow)
        self.assertIn("  workflow_dispatch:\n", workflow)
        repair = workflow.split("  repair:\n", 1)[1]
        self.assertRegex(
            repair,
            r"(?m)^    if: github\.event_name == 'workflow_dispatch'$",
        )
        self.assertRegex(repair, r"(?m)^    environment: production$")
        self.assertRegex(
            repair,
            r"(?m)^        if: always\(\) && inputs\.dry_run != true$",
        )

    def test_authority_is_exact_apex_and_www_wildcards(self) -> None:
        self.assertEqual(edge.APEX_ROUTE, "a-11-oy.com/*")
        self.assertEqual(edge.WWW_ROUTE, "www.a-11-oy.com/*")
        self.assertEqual(edge.DESIRED_ROUTES, (edge.APEX_ROUTE, edge.WWW_ROUTE))
        self.assertEqual(edge.WEB_HOSTS, ("a-11-oy.com", "www.a-11-oy.com"))
        self.assertEqual(edge.WEB_RECORD_TYPES, {"A", "AAAA", "CNAME"})
        self.assertNotIn("*.a-11-oy.com", edge.DESIRED_ROUTES)

    def test_empty_route_table_creates_apex_then_www_only_while_dns_only(self) -> None:
        plan = edge.route_plan([], dns_is_proxied=False)
        self.assertEqual(
            [(item["action"], item["pattern"]) for item in plan],
            [
                ("create-apex-route", edge.APEX_ROUTE),
                ("create-www-route", edge.WWW_ROUTE),
            ],
        )
        with self.assertRaisesRegex(edge.EdgeError, "LIVE_ROUTE_MUTATION_BLOCKED"):
            edge.route_plan([], dns_is_proxied=True)

    def test_current_routes_are_noop_when_dns_is_already_proxied(self) -> None:
        plan = edge.route_plan(
            [
                {
                    "id": "apex-current",
                    "pattern": edge.APEX_ROUTE,
                    "script": edge.SCRIPT_NAME,
                },
                {
                    "id": "www-current",
                    "pattern": edge.WWW_ROUTE,
                    "script": edge.SCRIPT_NAME,
                },
            ],
            dns_is_proxied=True,
        )
        self.assertEqual(
            [item["action"] for item in plan],
            ["verify-apex-route", "verify-www-route"],
        )
        with mock.patch.object(edge, "request_json") as request:
            results = edge.apply_route_plan("zone", "secret", plan, dry_run=False)
        request.assert_not_called()
        self.assertEqual(
            [item["state"] for item in results],
            ["already-current", "already-current"],
        )

    def test_proxied_cutover_creates_only_missing_exact_routes_on_new_script(self) -> None:
        script = edge.immutable_script_name(WORKER)
        self.assertTrue(script.startswith(edge.PROXIED_SCRIPT_PREFIX))
        self.assertEqual(script, edge.immutable_script_name(WORKER))
        plan = edge.route_plan(
            [],
            dns_is_proxied=True,
            script_name=script,
            allow_proxied_create=True,
        )
        self.assertEqual(
            [(item["action"], item["pattern"], item["script"]) for item in plan],
            [
                ("create-apex-route", edge.APEX_ROUTE, script),
                ("create-www-route", edge.WWW_ROUTE, script),
            ],
        )
        self.assertNotIn("a11oy.net", str(plan))

        existing_www = {
            "id": "current-www",
            "pattern": edge.WWW_ROUTE,
            "script": edge.SCRIPT_NAME,
        }
        partial = edge.route_plan(
            [existing_www],
            dns_is_proxied=True,
            script_name=script,
            allow_proxied_create=True,
        )
        self.assertEqual(
            [item["action"] for item in partial],
            ["create-apex-route", "verify-www-route"],
        )
        self.assertEqual(partial[1]["script"], edge.SCRIPT_NAME)

    def test_proxied_cutover_refuses_overlaps_and_foreign_owners(self) -> None:
        script = edge.immutable_script_name(WORKER)
        for rows, marker in (
            (
                [{"id": "extra", "pattern": "a-11-oy.com/api/*", "script": "foreign"}],
                "OVERLAPPING_LIVE_ROUTE",
            ),
            (
                [{"id": "foreign", "pattern": edge.WWW_ROUTE, "script": "foreign"}],
                "MIXED_LIVE_ROUTE_OWNERSHIP",
            ),
            (
                [{"id": "old", "pattern": edge.LEGACY_APEX_ROOT_ROUTE,
                  "script": edge.RETIRED_ROOT_SCRIPT}],
                "OVERLAPPING_LIVE_ROUTE",
            ),
        ):
            with self.subTest(marker=marker):
                with self.assertRaisesRegex(edge.EdgeError, marker):
                    edge.route_plan(
                        rows,
                        dns_is_proxied=True,
                        script_name=script,
                        allow_proxied_create=True,
                    )

    def test_incomplete_route_listing_fails_closed(self) -> None:
        with mock.patch.object(
            edge,
            "request_json",
            return_value={"success": True, "result": [],
                          "result_info": {"total_pages": 2}},
        ):
            with self.assertRaisesRegex(edge.EdgeError, "AMBIGUOUS_WORKER_ROUTE"):
                edge.fetch_routes("zone", "secret")

    def test_account_script_name_is_absent_or_exact_bytes_only(self) -> None:
        source = WORKER.read_bytes()
        script = edge.immutable_script_name(WORKER)
        with (
            mock.patch.object(
                edge, "request_json",
                return_value={"success": True, "result": []},
            ),
            mock.patch.object(edge.urllib.request, "urlopen") as read,
        ):
            self.assertEqual(
                edge.inspect_worker_script("account", "secret", script, source),
                "absent",
            )
            read.assert_not_called()

        with (
            mock.patch.object(
                edge, "request_json",
                return_value={"success": True, "result": [{"id": script}]},
            ),
            mock.patch.object(
                edge.urllib.request, "urlopen", return_value=io.BytesIO(source)
            ),
        ):
            self.assertEqual(
                edge.inspect_worker_script("account", "secret", script, source),
                "identical",
            )
        with (
            mock.patch.object(
                edge, "request_json",
                return_value={"success": True, "result": [{"id": script}]},
            ),
            mock.patch.object(
                edge.urllib.request, "urlopen", return_value=io.BytesIO(b"foreign")
            ),
        ):
            with self.assertRaisesRegex(edge.EdgeError, "WORKER_SCRIPT_NAME_COLLISION"):
                edge.inspect_worker_script("account", "secret", script, source)

    def test_incomplete_script_listing_blocks_upload(self) -> None:
        with mock.patch.object(
            edge,
            "request_json",
            return_value={"success": True, "result": [],
                          "result_info": {"total_pages": 2}},
        ):
            with self.assertRaisesRegex(edge.EdgeError, "AMBIGUOUS_WORKER_SCRIPT"):
                edge.inspect_worker_script("account", "secret", "script", b"source")

    def test_new_script_upload_is_conditional_create_only(self) -> None:
        response = io.BytesIO(b'{"success":true,"result":{"id":"new"}}')
        with mock.patch.object(
            edge.urllib.request, "urlopen", return_value=response
        ) as send:
            edge.upload_worker(
                "account", "secret", WORKER,
                script_name=edge.immutable_script_name(WORKER),
                create_only=True,
            )
        request = send.call_args.args[0]
        self.assertEqual(request.get_method(), "PUT")
        self.assertEqual(request.get_header("If-none-match"), "*")

    def test_route_drift_preflight_sends_no_post(self) -> None:
        script = edge.immutable_script_name(WORKER)
        plan = edge.route_plan(
            [], dns_is_proxied=True, script_name=script, allow_proxied_create=True
        )
        with (
            mock.patch.object(
                edge, "fetch_routes",
                return_value=[{"id": "raced", "pattern": edge.APEX_ROUTE,
                               "script": "foreign"}],
            ),
            mock.patch.object(edge, "request_json") as write,
        ):
            with self.assertRaises(edge.RouteMutationError) as raised:
                edge.apply_route_plan(
                    "zone", "secret", plan, dry_run=False,
                    expected_routes=[], guard_live_create=True,
                )
        self.assertFalse(raised.exception.request_sent)
        self.assertIn("ROUTE_STATE_DRIFT_BEFORE_WRITE", str(raised.exception))
        write.assert_not_called()

    def test_live_route_postcondition_requires_exact_script_owner(self) -> None:
        script = edge.immutable_script_name(WORKER)
        plan = edge.route_plan(
            [], dns_is_proxied=True, script_name=script, allow_proxied_create=True
        )
        matching = [
            {"id": str(index), "pattern": item["pattern"], "script": script}
            for index, item in enumerate(plan)
        ]
        with mock.patch.object(edge, "fetch_routes", return_value=matching):
            edge.verify_desired_routes("zone", "secret", plan)
        matching[1] = {**matching[1], "script": "foreign"}
        with mock.patch.object(edge, "fetch_routes", return_value=matching):
            with self.assertRaisesRegex(edge.EdgeError, "ROUTE_POSTCONDITION_FAILED"):
                edge.verify_desired_routes("zone", "secret", plan)

    def test_proxied_dry_run_plans_routes_without_provider_writes(self) -> None:
        records = [
            dns_record("apex", edge.ZONE_NAME, "CNAME", proxied=True),
            dns_record("www", f"www.{edge.ZONE_NAME}", "CNAME", proxied=True),
        ]
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "secret"}, clear=True),
            mock.patch(
                "sys.argv",
                [str(SCRIPT), "--report", str(Path(tmp) / "report.json"), "--dry-run"],
            ),
            mock.patch.object(
                edge,
                "request_json",
                side_effect=[
                    {"success": True, "result": {"status": "active"}},
                    {"success": True, "result": [{
                        "id": "zone-id", "account": {"id": "account-id"}
                    }]},
                ],
            ) as request,
            mock.patch.object(edge, "fetch_dns_records", return_value=records),
            mock.patch.object(edge, "fetch_routes", return_value=[]),
            mock.patch.object(edge, "inspect_worker_script", return_value="absent"),
            mock.patch.object(edge, "upload_worker") as upload,
            mock.patch("builtins.print"),
        ):
            self.assertEqual(edge.main(), 0)
            report = json.loads((Path(tmp) / "report.json").read_text())
        self.assertEqual(report["status"], "VALIDATED")
        self.assertFalse(report["dns_mutated"])
        self.assertEqual(report["worker_script_preflight"], "absent")
        self.assertEqual(
            [row["action"] for row in report["route_plan"]],
            ["create-apex-route", "create-www-route"],
        )
        self.assertTrue(all(call.args[0] == "GET" for call in request.call_args_list))
        upload.assert_not_called()

    def test_script_collision_blocks_without_provider_write(self) -> None:
        records = [
            dns_record("apex", edge.ZONE_NAME, "CNAME", proxied=True),
            dns_record("www", f"www.{edge.ZONE_NAME}", "CNAME", proxied=True),
        ]
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "secret"}, clear=True),
            mock.patch(
                "sys.argv", [str(SCRIPT), "--report", str(Path(tmp) / "report.json")]
            ),
            mock.patch.object(
                edge, "request_json",
                side_effect=[
                    {"success": True, "result": {"status": "active"}},
                    {"success": True, "result": [{
                        "id": "zone-id", "account": {"id": "account-id"}
                    }]},
                ],
            ) as request,
            mock.patch.object(edge, "fetch_dns_records", return_value=records),
            mock.patch.object(edge, "fetch_routes", return_value=[]),
            mock.patch.object(
                edge, "inspect_worker_script",
                side_effect=edge.EdgeError("WORKER_SCRIPT_NAME_COLLISION"),
            ),
            mock.patch.object(edge, "upload_worker") as upload,
            mock.patch("builtins.print"),
        ):
            self.assertEqual(edge.main(), 1)
            report = json.loads((Path(tmp) / "report.json").read_text())
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("WORKER_SCRIPT_NAME_COLLISION", report["error"])
        self.assertTrue(all(call.args[0] == "GET" for call in request.call_args_list))
        upload.assert_not_called()

    def test_route_race_after_upload_reports_unknown_without_post(self) -> None:
        records = [
            dns_record("apex", edge.ZONE_NAME, "CNAME", proxied=True),
            dns_record("www", f"www.{edge.ZONE_NAME}", "CNAME", proxied=True),
        ]
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "secret"}, clear=True),
            mock.patch(
                "sys.argv", [str(SCRIPT), "--report", str(Path(tmp) / "report.json")]
            ),
            mock.patch.object(
                edge, "request_json",
                side_effect=[
                    {"success": True, "result": {"status": "active"}},
                    {"success": True, "result": [{
                        "id": "zone-id", "account": {"id": "account-id"}
                    }]},
                ],
            ) as request,
            mock.patch.object(edge, "fetch_dns_records", return_value=records),
            mock.patch.object(
                edge, "fetch_routes",
                side_effect=[
                    [], [], [],
                    [{"id": "raced", "pattern": edge.APEX_ROUTE,
                      "script": "foreign"}],
                ],
            ),
            mock.patch.object(
                edge, "inspect_worker_script", side_effect=["absent", "identical"]
            ),
            mock.patch.object(edge, "upload_worker") as upload,
            mock.patch("builtins.print"),
        ):
            self.assertEqual(edge.main(), 1)
            report = json.loads((Path(tmp) / "report.json").read_text())
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertIn("ROUTE_STATE_DRIFT_BEFORE_WRITE", report["error"])
        self.assertFalse(report["dns_mutated"])
        self.assertTrue(all(call.args[0] == "GET" for call in request.call_args_list))
        upload.assert_called_once()

    def test_identical_script_retry_skips_upload_before_route_guard(self) -> None:
        records = [
            dns_record("apex", edge.ZONE_NAME, "CNAME", proxied=True),
            dns_record("www", f"www.{edge.ZONE_NAME}", "CNAME", proxied=True),
        ]
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "secret"}, clear=True),
            mock.patch(
                "sys.argv", [str(SCRIPT), "--report", str(Path(tmp) / "report.json")]
            ),
            mock.patch.object(
                edge, "request_json",
                side_effect=[
                    {"success": True, "result": {"status": "active"}},
                    {"success": True, "result": [{
                        "id": "zone-id", "account": {"id": "account-id"}
                    }]},
                ],
            ) as request,
            mock.patch.object(edge, "fetch_dns_records", return_value=records),
            mock.patch.object(
                edge, "fetch_routes",
                side_effect=[
                    [], [], [],
                    [{"id": "raced", "pattern": edge.APEX_ROUTE,
                      "script": "foreign"}],
                ],
            ),
            mock.patch.object(
                edge, "inspect_worker_script", return_value="identical"
            ) as inspect,
            mock.patch.object(edge, "upload_worker") as upload,
            mock.patch("builtins.print"),
        ):
            self.assertEqual(edge.main(), 1)
            report = json.loads((Path(tmp) / "report.json").read_text())
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(report["worker_upload_outcome"], "skipped-identical")
        self.assertEqual(inspect.call_count, 2)
        upload.assert_not_called()
        self.assertTrue(all(call.args[0] == "GET" for call in request.call_args_list))

    def test_ambiguous_upload_ack_reports_unknown_without_route_post(self) -> None:
        records = [
            dns_record("apex", edge.ZONE_NAME, "CNAME", proxied=True),
            dns_record("www", f"www.{edge.ZONE_NAME}", "CNAME", proxied=True),
        ]
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "secret"}, clear=True),
            mock.patch(
                "sys.argv", [str(SCRIPT), "--report", str(Path(tmp) / "report.json")]
            ),
            mock.patch.object(
                edge, "request_json",
                side_effect=[
                    {"success": True, "result": {"status": "active"}},
                    {"success": True, "result": [{
                        "id": "zone-id", "account": {"id": "account-id"}
                    }]},
                ],
            ) as request,
            mock.patch.object(edge, "fetch_dns_records", return_value=records),
            mock.patch.object(edge, "fetch_routes", return_value=[]),
            mock.patch.object(edge, "inspect_worker_script", return_value="absent"),
            mock.patch.object(
                edge, "upload_worker",
                side_effect=edge.EdgeError("WORKER_UPLOAD_ACK_LOST"),
            ) as upload,
            mock.patch("builtins.print"),
        ):
            self.assertEqual(edge.main(), 1)
            report = json.loads((Path(tmp) / "report.json").read_text())
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertEqual(report["worker_upload_outcome"], "UNKNOWN")
        self.assertFalse(report["dns_mutated"])
        upload.assert_called_once()
        self.assertTrue(all(call.args[0] == "GET" for call in request.call_args_list))

    def test_lost_route_ack_never_rolls_back_a_matching_unowned_route(self) -> None:
        script = edge.immutable_script_name(WORKER)
        records = [
            dns_record("apex", edge.ZONE_NAME, "CNAME", proxied=True),
            dns_record("www", f"www.{edge.ZONE_NAME}", "CNAME", proxied=True),
        ]
        apex = {"id": "apex-new", "pattern": edge.APEX_ROUTE, "script": script}
        same_script_www = {
            "id": "not-our-www", "pattern": edge.WWW_ROUTE, "script": script
        }
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "secret"}, clear=True),
            mock.patch(
                "sys.argv", [str(SCRIPT), "--report", str(Path(tmp) / "report.json")]
            ),
            mock.patch.object(
                edge, "request_json",
                side_effect=[
                    {"success": True, "result": {"status": "active"}},
                    {"success": True, "result": [{
                        "id": "zone-id", "account": {"id": "account-id"}
                    }]},
                    {"success": True, "result": apex},
                    edge.EdgeError("SECOND_POST_ACK_LOST"),
                    {"success": True, "result": {}},
                ],
            ) as request,
            mock.patch.object(edge, "fetch_dns_records", return_value=records),
            mock.patch.object(
                edge, "fetch_routes",
                side_effect=[
                    [], [], [], [], [apex],
                    [apex, same_script_www], [same_script_www],
                ],
            ),
            mock.patch.object(
                edge, "inspect_worker_script", side_effect=["absent", "identical"]
            ),
            mock.patch.object(edge, "upload_worker"),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(edge.main(), 1)
            report = json.loads((Path(tmp) / "report.json").read_text())
        self.assertEqual(report["status"], "UNKNOWN")
        self.assertTrue(report["route_write_request_sent"])
        self.assertEqual(report["route_attempted"]["pattern"], edge.WWW_ROUTE)
        self.assertEqual(report["route_rollback"][0]["state"], "restored-absent")
        deletes = [call for call in request.call_args_list if call.args[0] == "DELETE"]
        self.assertEqual(len(deletes), 1)
        self.assertTrue(deletes[0].args[1].endswith("/apex-new"))

    def test_failed_proxied_public_proof_rolls_back_only_new_routes(self) -> None:
        script = edge.immutable_script_name(WORKER)
        records = [
            dns_record("apex", edge.ZONE_NAME, "CNAME", proxied=True),
            dns_record("www", f"www.{edge.ZONE_NAME}", "CNAME", proxied=True),
        ]
        apex = {"id": "apex-route", "pattern": edge.APEX_ROUTE, "script": script}
        www = {"id": "www-route", "pattern": edge.WWW_ROUTE, "script": script}
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "secret"}, clear=True),
            mock.patch(
                "sys.argv", [str(SCRIPT), "--report", str(Path(tmp) / "report.json")]
            ),
            mock.patch.object(
                edge, "request_json",
                side_effect=[
                    {"success": True, "result": {"status": "active"}},
                    {"success": True, "result": [{
                        "id": "zone-id", "account": {"id": "account-id"}
                    }]},
                    {"success": True, "result": apex},
                    {"success": True, "result": www},
                    {"success": True, "result": {"id": "www-route"}},
                    {"success": True, "result": {"id": "apex-route"}},
                ],
            ) as request,
            mock.patch.object(edge, "fetch_dns_records", return_value=records),
            mock.patch.object(
                edge, "fetch_routes",
                side_effect=[[], [], [], [], [apex], [apex, www], [apex], [apex], []],
            ),
            mock.patch.object(
                edge, "inspect_worker_script", side_effect=["absent", "identical"]
            ),
            mock.patch.object(edge, "upload_worker") as upload,
            mock.patch.object(
                edge, "public_probe", side_effect=edge.EdgeError("PUBLIC_PROBE_FAILED")
            ),
            mock.patch("builtins.print"),
        ):
            self.assertEqual(edge.main(), 1)
            report = json.loads((Path(tmp) / "report.json").read_text())
        self.assertEqual(report["status"], "ROLLED_BACK")
        self.assertFalse(report["dns_mutated"])
        self.assertEqual(
            [row["state"] for row in report["route_rollback"]],
            ["restored-absent", "restored-absent"],
        )
        self.assertEqual(request.call_args_list[-2].args[0], "DELETE")
        self.assertEqual(request.call_args_list[-1].args[0], "DELETE")
        self.assertTrue(all("dns_records" not in call.args[1] for call in request.call_args_list))
        upload.assert_called_once()
        self.assertTrue(upload.call_args.kwargs["create_only"])

    def test_known_legacy_routes_are_reconciled_deterministically_when_dns_only(self) -> None:
        current = [
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
        plan = edge.route_plan(current, dns_is_proxied=False)
        self.assertEqual(
            [item["action"] for item in plan],
            [
                "delete-known-legacy-apex-root",
                "update-apex-route",
                "update-www-route",
            ],
        )
        self.assertTrue(
            all(item["script"] in edge.KNOWN_SCRIPT_NAMES for item in plan)
        )
        with self.assertRaisesRegex(edge.EdgeError, "LIVE_ROUTE_MUTATION_BLOCKED"):
            edge.route_plan(current, dns_is_proxied=True)

    def test_foreign_route_ownership_fails_closed(self) -> None:
        for pattern, marker in (
            (edge.LEGACY_APEX_ROOT_ROUTE, "LEGACY_APEX_ROUTE_CONFLICT"),
            (edge.APEX_ROUTE, "APEX_ROUTE_CONFLICT"),
            (edge.WWW_ROUTE, "WWW_ROUTE_CONFLICT"),
        ):
            with self.subTest(pattern=pattern):
                with self.assertRaisesRegex(edge.EdgeError, marker):
                    edge.route_plan(
                        [{"id": "foreign", "pattern": pattern, "script": "foreign"}],
                        dns_is_proxied=False,
                    )

    def test_duplicate_route_pattern_fails_closed(self) -> None:
        with self.assertRaisesRegex(edge.EdgeError, "DUPLICATE_ROUTE_PATTERN"):
            edge.route_plan(
                [
                    {
                        "id": "one",
                        "pattern": edge.APEX_ROUTE,
                        "script": edge.SCRIPT_NAME,
                    },
                    {
                        "id": "two",
                        "pattern": edge.APEX_ROUTE,
                        "script": edge.SCRIPT_NAME,
                    },
                ],
                dns_is_proxied=False,
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
                {
                    "success": True,
                    "result": {"id": "apex-created", "script": edge.SCRIPT_NAME},
                },
                {
                    "success": True,
                    "result": {"id": "www-route", "script": edge.SCRIPT_NAME},
                },
            ],
        ) as request:
            results = edge.apply_route_plan(
                "zone",
                "secret",
                plan,
                dry_run=False,
            )
        self.assertEqual(
            [row["state"] for row in results],
            ["deleted", "created", "updated"],
        )
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

    def test_dns_plan_selects_only_exact_existing_web_records(self) -> None:
        current = [
            dns_record("apex-a", edge.ZONE_NAME, "A", proxied=False),
            dns_record("apex-aaaa", edge.ZONE_NAME, "AAAA", proxied=False),
            dns_record("www-cname", f"www.{edge.ZONE_NAME}", "CNAME", proxied=False),
            {
                "id": "apex-txt",
                "name": edge.ZONE_NAME,
                "type": "TXT",
                "content": "ownership-proof",
                "proxied": False,
                "proxiable": False,
            },
            dns_record("other", f"api.{edge.ZONE_NAME}", "A", proxied=False),
        ]
        plan, initially_proxied = edge.dns_proxy_plan(current)
        self.assertFalse(initially_proxied)
        self.assertEqual(
            [(item["record_id"], item["action"]) for item in plan],
            [
                ("apex-a", "enable-proxy"),
                ("apex-aaaa", "enable-proxy"),
                ("www-cname", "enable-proxy"),
            ],
        )

    def test_dns_plan_allows_uniform_already_proxied_noop(self) -> None:
        plan, initially_proxied = edge.dns_proxy_plan(
            [
                dns_record("apex", edge.ZONE_NAME, "A", proxied=True),
                dns_record(
                    "www",
                    f"www.{edge.ZONE_NAME}",
                    "CNAME",
                    proxied=True,
                ),
            ]
        )
        self.assertTrue(initially_proxied)
        self.assertEqual(
            [item["action"] for item in plan],
            ["verify-proxied", "verify-proxied"],
        )

    def test_dns_plan_missing_nonproxiable_mixed_and_ambiguous_fail_closed(self) -> None:
        with self.assertRaisesRegex(edge.EdgeError, "MISSING_WEB_DNS_RECORD"):
            edge.dns_proxy_plan(
                [dns_record("apex", edge.ZONE_NAME, "A", proxied=False)]
            )

        with self.assertRaisesRegex(edge.EdgeError, "NON_PROXIABLE_WEB_DNS_RECORD"):
            edge.dns_proxy_plan(
                [
                    dns_record(
                        "apex",
                        edge.ZONE_NAME,
                        "A",
                        proxied=False,
                        proxiable=False,
                    ),
                    dns_record(
                        "www",
                        f"www.{edge.ZONE_NAME}",
                        "CNAME",
                        proxied=False,
                    ),
                ]
            )

        with self.assertRaisesRegex(edge.EdgeError, "MIXED_DNS_PROXY_STATE"):
            edge.dns_proxy_plan(
                [
                    dns_record("apex", edge.ZONE_NAME, "A", proxied=True),
                    dns_record(
                        "www",
                        f"www.{edge.ZONE_NAME}",
                        "CNAME",
                        proxied=False,
                    ),
                ]
            )

        with self.assertRaisesRegex(edge.EdgeError, "AMBIGUOUS_WEB_DNS_RECORDS"):
            edge.dns_proxy_plan(
                [
                    dns_record("apex-a", edge.ZONE_NAME, "A", proxied=False),
                    dns_record(
                        "apex-cname",
                        edge.ZONE_NAME,
                        "CNAME",
                        proxied=False,
                    ),
                    dns_record(
                        "www",
                        f"www.{edge.ZONE_NAME}",
                        "CNAME",
                        proxied=False,
                    ),
                ]
            )

    def test_dns_application_patches_only_the_proxy_flag(self) -> None:
        plan, _ = edge.dns_proxy_plan(
            [
                dns_record("apex", edge.ZONE_NAME, "A", proxied=False),
                dns_record(
                    "www",
                    f"www.{edge.ZONE_NAME}",
                    "CNAME",
                    proxied=False,
                ),
            ]
        )
        with mock.patch.object(
            edge,
            "request_json",
            side_effect=[
                {
                    "success": True,
                    "result": {
                        "id": "apex",
                        "name": edge.ZONE_NAME,
                        "type": "A",
                        "proxied": True,
                    },
                },
                {
                    "success": True,
                    "result": {
                        "id": "www",
                        "name": f"www.{edge.ZONE_NAME}",
                        "type": "CNAME",
                        "proxied": True,
                    },
                },
            ],
        ) as request:
            results = edge.apply_dns_proxy_plan(
                "zone",
                "secret",
                plan,
                dry_run=False,
            )
        self.assertEqual([item["state"] for item in results], ["enabled", "enabled"])
        self.assertEqual(
            request.call_args_list[0],
            mock.call(
                "PATCH",
                "/zones/zone/dns_records/apex",
                bearer="secret",
                payload={"proxied": True},
            ),
        )
        self.assertEqual(
            request.call_args_list[1],
            mock.call(
                "PATCH",
                "/zones/zone/dns_records/www",
                bearer="secret",
                payload={"proxied": True},
            ),
        )

    def test_partial_dns_activation_rolls_back_completed_records(self) -> None:
        plan, _ = edge.dns_proxy_plan(
            [
                dns_record("apex", edge.ZONE_NAME, "A", proxied=False),
                dns_record(
                    "www",
                    f"www.{edge.ZONE_NAME}",
                    "CNAME",
                    proxied=False,
                ),
            ]
        )
        with mock.patch.object(
            edge,
            "request_json",
            side_effect=[
                {
                    "success": True,
                    "result": {
                        "id": "apex",
                        "name": edge.ZONE_NAME,
                        "type": "A",
                        "proxied": True,
                    },
                },
                edge.EdgeError("provider rejected www"),
                {
                    "success": True,
                    "result": {
                        "id": "apex",
                        "name": edge.ZONE_NAME,
                        "type": "A",
                        "proxied": False,
                    },
                },
            ],
        ) as request:
            with self.assertRaises(edge.DnsMutationError) as raised:
                edge.apply_dns_proxy_plan(
                    "zone",
                    "secret",
                    plan,
                    dry_run=False,
                )
        self.assertEqual(
            [item["state"] for item in raised.exception.results],
            ["enabled"],
        )
        self.assertEqual(
            [item["state"] for item in raised.exception.rollback],
            ["restored-dns-only"],
        )
        self.assertEqual(
            request.call_args_list[-1],
            mock.call(
                "PATCH",
                "/zones/zone/dns_records/apex",
                bearer="secret",
                payload={"proxied": False},
            ),
        )

    def test_dns_identity_drift_after_enable_is_rolled_back(self) -> None:
        plan, _ = edge.dns_proxy_plan(
            [
                dns_record("apex", edge.ZONE_NAME, "A", proxied=False),
                dns_record(
                    "www",
                    f"www.{edge.ZONE_NAME}",
                    "CNAME",
                    proxied=False,
                ),
            ]
        )
        with mock.patch.object(
            edge,
            "request_json",
            side_effect=[
                {
                    "success": True,
                    "result": {
                        "id": "apex",
                        "name": "wrong.example",
                        "type": "A",
                        "proxied": True,
                    },
                },
                {
                    "success": True,
                    "result": {
                        "id": "apex",
                        "name": edge.ZONE_NAME,
                        "type": "A",
                        "proxied": False,
                    },
                },
            ],
        ):
            with self.assertRaises(edge.DnsMutationError) as raised:
                edge.apply_dns_proxy_plan(
                    "zone",
                    "secret",
                    plan,
                    dry_run=False,
                )
        self.assertIn("DNS_RECORD_IDENTITY_DRIFT", str(raised.exception))
        self.assertEqual(
            [item["state"] for item in raised.exception.rollback],
            ["restored-dns-only"],
        )

    def test_fetch_dns_records_queries_only_exact_hosts(self) -> None:
        with mock.patch.object(
            edge,
            "request_json",
            side_effect=[
                {
                    "success": True,
                    "result": [
                        dns_record("apex", edge.ZONE_NAME, "A", proxied=False)
                    ],
                    "result_info": {"total_pages": 1},
                },
                {
                    "success": True,
                    "result": [
                        dns_record(
                            "www",
                            f"www.{edge.ZONE_NAME}",
                            "CNAME",
                            proxied=False,
                        )
                    ],
                    "result_info": {"total_pages": 1},
                },
            ],
        ) as request:
            records = edge.fetch_dns_records("zone", "secret")
        self.assertEqual([row["id"] for row in records], ["apex", "www"])
        self.assertEqual(request.call_count, 2)
        for call, host in zip(request.call_args_list, edge.WEB_HOSTS, strict=True):
            self.assertEqual(call.args[0], "GET")
            self.assertIn(
                f"name={host.replace('.', '%2E')}",
                call.args[1].replace(".", "%2E"),
            )
            self.assertEqual(call.kwargs["bearer"], "secret")

    def test_failed_public_proof_restores_dns_and_records_rolled_back_status(self) -> None:
        dns_actions, _ = edge.dns_proxy_plan(
            [
                dns_record("apex", edge.ZONE_NAME, "A", proxied=False),
                dns_record(
                    "www",
                    f"www.{edge.ZONE_NAME}",
                    "CNAME",
                    proxied=False,
                ),
            ]
        )
        dns_results = [
            {**item, "state": "enabled"} for item in dns_actions
        ]
        rollback = [
            {**item, "state": "restored-dns-only"}
            for item in reversed(dns_results)
        ]
        with (
            tempfile.TemporaryDirectory() as tmp,
            mock.patch.dict(
                os.environ,
                {"CLOUDFLARE_API_TOKEN": "secret"},
                clear=True,
            ),
            mock.patch(
                "sys.argv",
                [str(SCRIPT), "--report", str(Path(tmp) / "report.json")],
            ),
            mock.patch.object(
                edge,
                "request_json",
                side_effect=[
                    {"success": True, "result": {"status": "active"}},
                    {
                        "success": True,
                        "result": [
                            {
                                "id": "zone-id",
                                "account": {"id": "account-id"},
                            }
                        ],
                    },
                    {"success": True, "result": []},
                ],
            ),
            mock.patch.object(
                edge,
                "fetch_dns_records",
                return_value=[
                    dns_record("apex", edge.ZONE_NAME, "A", proxied=False),
                    dns_record(
                        "www",
                        f"www.{edge.ZONE_NAME}",
                        "CNAME",
                        proxied=False,
                    ),
                ],
            ),
            mock.patch.object(edge, "inspect_worker_script", return_value="identical"),
            mock.patch.object(edge, "upload_worker"),
            mock.patch.object(
                edge,
                "apply_route_plan",
                return_value=[
                    {
                        "action": "create-apex-route",
                        "pattern": edge.APEX_ROUTE,
                        "script": edge.SCRIPT_NAME,
                        "state": "created",
                    },
                    {
                        "action": "create-www-route",
                        "pattern": edge.WWW_ROUTE,
                        "script": edge.SCRIPT_NAME,
                        "state": "created",
                    },
                ],
            ),
            mock.patch.object(
                edge,
                "apply_dns_proxy_plan",
                return_value=dns_results,
            ),
            mock.patch.object(
                edge,
                "public_probe",
                side_effect=edge.EdgeError("PUBLIC_PROBE_FAILED"),
            ),
            mock.patch.object(
                edge,
                "rollback_dns_proxy_plan",
                return_value=rollback,
            ) as rollback_call,
        ):
            self.assertEqual(edge.main(), 1)
            report = json.loads(
                (Path(tmp) / "report.json").read_text(encoding="utf-8")
            )
        rollback_call.assert_called_once()
        self.assertEqual(report["status"], "ROLLED_BACK")
        self.assertTrue(report["dns_mutated"])
        self.assertTrue(report["dns_rollback_succeeded"])
        self.assertNotIn("secret", json.dumps(report))

    def test_public_provider_receipt_hides_full_ids_and_dns_content(self) -> None:
        public = edge._public_provider_item(
            {
                "action": "enable-proxy",
                "record_id": "0123456789abcdef",
                "host": edge.ZONE_NAME,
                "type": "A",
                "prior_proxied": False,
                "content": "192.0.2.10",
                "state": "enabled",
            }
        )
        self.assertEqual(public["provider_id_suffix"], "abcdef")
        self.assertNotIn("record_id", public)
        self.assertNotIn("content", public)

    def test_dry_run_never_calls_provider_mutation(self) -> None:
        route_actions = edge.route_plan([], dns_is_proxied=False)
        dns_actions, _ = edge.dns_proxy_plan(
            [
                dns_record("apex", edge.ZONE_NAME, "A", proxied=False),
                dns_record(
                    "www",
                    f"www.{edge.ZONE_NAME}",
                    "CNAME",
                    proxied=False,
                ),
            ]
        )
        with mock.patch.object(edge, "request_json") as request:
            route_results = edge.apply_route_plan(
                "zone",
                "secret",
                route_actions,
                dry_run=True,
            )
            dns_results = edge.apply_dns_proxy_plan(
                "zone",
                "secret",
                dns_actions,
                dry_run=True,
            )
        request.assert_not_called()
        self.assertEqual(
            [row["state"] for row in route_results],
            ["would-apply", "would-apply"],
        )
        self.assertEqual(
            [row["state"] for row in dns_results],
            ["would-enable-proxy", "would-enable-proxy"],
        )

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
            report = json.loads(
                (Path(tmp) / "report.json").read_text(encoding="utf-8")
            )
        self.assertEqual(report["status"], "UNAVAILABLE")
        self.assertEqual(report["schema"], "szl.cloudflare-product-edge/v4")
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

    def test_public_probe_requires_root_honesty_www_and_live_aliases(self) -> None:
        observations = [
            {
                "status": 301,
                "location": (
                    "https://a-11-oy.com/__szl_edge_probe__/path?"
                    "contract=v3&preserve=yes"
                ),
                "edge": edge.EDGE_MARKER,
                "content_type": None,
                "final_url": (
                    "https://www.a-11-oy.com/__szl_edge_probe__/path?"
                    "contract=v3&preserve=yes"
                ),
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
                "body": json.dumps(
                    {"organ": "a11oy", "locked_formula_count": 8}
                ),
            },
            {
                "status": 200,
                "edge": edge.EDGE_MARKER,
                "alias": "/spectral->/static/3d/holographic.html",
                "content_type": "text/html",
                "body": "<title>A11oy holographic</title>",
            },
            {
                "status": 200,
                "edge": edge.EDGE_MARKER,
                "alias": "/controller->/api/a11oy/v1/honest",
                "content_type": "application/json",
                "body": json.dumps(
                    {"organ": "a11oy", "locked_formula_count": 8}
                ),
            },
        ]
        with mock.patch.object(edge, "_observation", side_effect=observations):
            result = edge.public_probe(attempts=1)
        self.assertTrue(result["root_verified"])
        self.assertTrue(result["honest_verified"])
        self.assertTrue(result["www_verified"])
        self.assertTrue(result["spectral_verified"])
        self.assertTrue(result["controller_verified"])
        self.assertNotIn("body", result["root"])
        self.assertNotIn("body", result["honest"])
        self.assertNotIn("body", result["spectral"])

    def test_public_probe_rejects_missing_edge_marker(self) -> None:
        observations = [
            {
                "status": 301,
                "location": (
                    "https://a-11-oy.com/__szl_edge_probe__/path?"
                    "contract=v3&preserve=yes"
                ),
                "edge": edge.EDGE_MARKER,
                "body": "",
            },
            {"status": 200, "edge": None, "body": "a11oy"},
            {
                "status": 200,
                "edge": edge.EDGE_MARKER,
                "body": json.dumps(
                    {"organ": "a11oy", "locked_formula_count": 8}
                ),
            },
            {"status": 404, "body": ""},
            {"status": 404, "body": ""},
        ]
        with (
            mock.patch.object(edge, "_observation", side_effect=observations),
            mock.patch.object(edge.time, "sleep"),
        ):
            with self.assertRaisesRegex(edge.EdgeError, "PUBLIC_PROBE_FAILED"):
                edge.public_probe(attempts=1)

    def test_worker_is_fixed_origin_and_never_redirects_apex_to_hf(self) -> None:
        text = WORKER.read_text(encoding="utf-8")
        self.assertIn(
            'const ORIGIN_HOST = "szlholdings-a11oy.hf.space"',
            text,
        )
        self.assertIn('const PRODUCT_HOST = "a-11-oy.com"', text)
        self.assertIn('const WWW_HOST = "www.a-11-oy.com"', text)
        self.assertIn("await fetchImpl(outgoing)", text)
        self.assertIn('request.method === "HEAD" ? null : response.body', text)
        self.assertIn("status: 301", text)
        self.assertIn("errorResponse(421", text)
        self.assertIn("status,", text)
        self.assertIn("origin_unavailable", text)
        self.assertNotIn("eval(", text)
        self.assertNotIn("new Function", text)
        self.assertNotIn("Response.redirect(upstream", text)


if __name__ == "__main__":
    unittest.main()
