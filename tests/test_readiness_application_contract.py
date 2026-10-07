#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline regression cases for passive endpoint and cached readiness evidence."""

import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
from types import ModuleType
import unittest
from unittest.mock import Mock, patch
import urllib.error


SPEC = importlib.util.spec_from_file_location(
    "readiness_under_test", Path(__file__).resolve().parents[1] / "szl_readiness.py")
readiness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(readiness)


class Response:
    def __init__(self, body, status=200, content_type="application/json"):
        self.body = io.BytesIO(body)
        self.status = status
        self.headers = {"Content-Type": content_type}

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def getcode(self):
        return self.status

    def read(self, size=-1):
        return self.body.read(size)


class ReadinessContractTests(unittest.TestCase):
    def setUp(self):
        self.clock = 1000.0
        self.addCleanup(patch.stopall)
        patch.object(readiness.time, "time", side_effect=lambda: self.clock).start()
        patch.object(readiness, "_CACHE", {}).start()
        patch.object(readiness, "_DISK_LOADED", True).start()
        patch.object(readiness, "_disk_save").start()
        self.network = patch.object(readiness.urllib.request, "urlopen").start()
        self.endpoint = readiness._killinchu_cfg()["deployment"]["endpoints"][-1]
        self.health = readiness._killinchu_cfg()["deployment"]["endpoints"][-2]
        self.evidence = {"layer": "killinchu evidence & research", "honest": "Source disclosure",
                         "count": 1, "claims": [{"id": "claim", "claim": "Research claim", "sources": []}]}

    def observe(self, value, endpoint=None, *, status=200, content_type="application/json", fresh=True):
        body = value if isinstance(value, bytes) else json.dumps(value).encode()
        self.network.side_effect = None
        self.network.return_value = Response(body, status, content_type)
        return readiness._endpoint_liveness(endpoint or self.endpoint, fresh=fresh)

    def test_expected_evidence_contract_passes_with_get(self):
        result = self.observe(self.evidence)
        self.assertTrue(result["reachable"])
        self.assertTrue(result["contract"]["ready"])
        self.assertEqual(result["mode"], "live")
        self.assertEqual(self.network.call_args.args[0].get_method(), "GET")

    def test_health_accepts_both_canonical_identity_shapes(self):
        for field in ("organ", "service"):
            with self.subTest(field=field):
                result = self.observe({"status": "ok", field: "killinchu"}, self.health)
                self.assertTrue(result["contract"]["ready"])

    def test_a11oy_health_and_evidence_contracts(self):
        health, api = readiness._a11oy_cfg()["deployment"]["endpoints"][-2:]
        self.assertTrue(self.observe({"status": "ok", "organ": "a11oy"}, health)["contract"]["ready"])
        body = {**self.evidence, "layer": "a11oy evidence & research"}
        self.assertTrue(self.observe(body, api)["contract"]["ready"])

    def background_sections(self):
        cfg = readiness._killinchu_cfg()
        cfg["deployment"]["endpoints"] = [self.health, self.endpoint]
        patch.object(readiness, "_cfg_for", return_value=cfg).start()
        patch.object(readiness, "_SNAPSHOT", {}).start()
        sections = {sid: Mock(return_value={"id": sid})
                    for sid in readiness._SECTION_ORDER}
        sections["deployment"] = readiness._sec_deployment
        patch.object(readiness, "_SECTIONS", sections).start()

        def reply(request, **_kwargs):
            body = ({"status": "ok", "organ": "killinchu"}
                    if request.full_url == self.health["url"] else self.evidence)
            return Response(json.dumps(body).encode())

        self.network.side_effect = reply
        return sections

    def test_background_rebuild_renews_contracts_before_cache_expiry(self):
        self.background_sections()
        readiness._build_snapshot("killinchu")
        self.assertEqual(self.network.call_count, 2)
        self.clock += readiness._WARM_INTERVAL
        readiness._build_snapshot("killinchu")
        self.assertEqual(self.network.call_count, 4)
        # The original observations have expired, but the second sweep actually
        # reobserved both contracts; no timestamp is fabricated on a GET.
        self.clock = 1000.0 + readiness._LIVENESS_TTL + 1
        snap = readiness._snapshot("killinchu")
        payload = readiness._snapshot_payload(snap)
        self.assertTrue(payload["summary"]["application_ready"])
        for row in payload["sections"][0]["endpoints"]:
            self.assertEqual(row["liveness"]["checked_at_unix"],
                             1000.0 + readiness._WARM_INTERVAL)

    def test_failed_background_refresh_cannot_reuse_a_cached_pass(self):
        self.background_sections()
        readiness._build_snapshot("killinchu")
        self.clock += readiness._WARM_INTERVAL
        self.network.side_effect = TimeoutError("unavailable")
        readiness._build_snapshot("killinchu")
        payload = readiness._snapshot_payload(readiness._snapshot("killinchu"))
        self.assertFalse(payload["summary"]["application_ready"])
        self.assertEqual(self.network.call_count, 4)
        for row in payload["sections"][0]["endpoints"]:
            lv = row["liveness"]
            self.assertEqual(lv["checked_at_unix"], 1000.0)
            self.assertEqual(lv["contract"]["reason"], "live_check_failed")

    def test_background_sweep_refreshes_each_source_section(self):
        sections = {sid: Mock(return_value={"id": sid})
                    for sid in readiness._SECTION_ORDER}
        cfg = readiness._killinchu_cfg()
        with patch.object(readiness, "_cfg_for", return_value=cfg), \
                patch.object(readiness, "_SECTIONS", sections):
            readiness._assemble_index("killinchu")
        for section in sections.values():
            section.assert_called_once_with(cfg, fresh=True)
        self.network.assert_not_called()

    def test_both_namespace_descriptors_are_bound(self):
        for ns in ("a11oy", "killinchu"):
            for endpoint in readiness._cfg_for(ns)["deployment"]["endpoints"]:
                if endpoint["role"] in ("api", "health"):
                    self.assertEqual(endpoint["organ"], ns)
                    self.assertIn(endpoint["contract"], ("health-v1", "evidence-v1"))

    def test_html_200_is_transport_only(self):
        result = self.observe(b"<html>SPA</html>", content_type="text/html")
        self.assertTrue(result["reachable"])
        self.assertEqual(result["http_status"], 200)
        self.assertFalse(result["contract"]["ready"])
        self.assertEqual(result["contract"]["reason"], "content_type_not_json")

    def test_http_404_overrides_previous_success(self):
        self.observe(self.evidence)
        self.network.side_effect = urllib.error.HTTPError(self.endpoint["url"], 404, "missing", {}, None)
        result = readiness._endpoint_liveness(self.endpoint, fresh=True)
        self.assertTrue(result["reachable"])
        self.assertEqual(result["http_status"], 404)
        self.assertEqual(result["mode"], "live")
        self.assertFalse(result["contract"]["ready"])
        self.assertEqual(result["contract"]["reason"], "http_status_404")

    def test_other_http_statuses_never_pass(self):
        for status in (204, 301, 403, 500):
            with self.subTest(status=status):
                result = self.observe(self.evidence, status=status)
                self.assertFalse(result["contract"]["ready"])

    def test_invalid_json_and_non_object_fail(self):
        for body, reason in ((b'{"count":', "malformed_json"), (b"[]", "json_not_object"),
                             (b"\xff", "malformed_json")):
            with self.subTest(body=body):
                result = self.observe(body)
                self.assertFalse(result["contract"]["ready"])
                self.assertEqual(result["contract"]["reason"], reason)

    def test_missing_and_wrong_evidence_contracts_fail(self):
        bad = [{}, {"detail": "Not Found"}, {"status": "ok", "organ": "killinchu"}]
        for key in self.evidence:
            value = dict(self.evidence)
            del value[key]
            bad.append(value)
        bad.extend([{**self.evidence, "count": True}, {**self.evidence, "count": 2},
                    {**self.evidence, "layer": "a11oy evidence & research"},
                    {**self.evidence, "claims": [{}]}, {**self.evidence, "honest": ""}])
        for value in bad:
            with self.subTest(value=value):
                self.assertFalse(self.observe(value)["contract"]["ready"])

    def test_duplicate_keys_cannot_override_an_unhealthy_status(self):
        for body in (b'{"status":"down","status":"ok","organ":"killinchu"}',
                     b'{"status":"ok","organ":"killinchu","meta":{"v":0,"v":1}}'):
            with self.subTest(body=body):
                result = self.observe(body, self.health)
                self.assertTrue(result["reachable"])
                self.assertFalse(result["contract"]["ready"])
                self.assertEqual(result["contract"]["reason"], "malformed_json")

    def test_non_finite_constants_are_malformed_even_in_extra_fields(self):
        for constant in (b"NaN", b"Infinity", b"-Infinity", b"1e400", b"-1e400"):
            with self.subTest(constant=constant):
                body = b'{"status":"ok","organ":"killinchu","value":' + constant + b'}'
                result = self.observe(body, self.health)
                self.assertFalse(result["contract"]["ready"])
                self.assertEqual(result["contract"]["reason"], "malformed_json")

    def test_missing_unhealthy_or_wrong_health_identity_fails(self):
        for value in ({"status": "ok"}, {"status": "down", "organ": "killinchu"},
                      {"status": "ok", "service": "a11oy"},
                      {"status": "ok", "organ": "killinchu", "service": "a11oy"}):
            with self.subTest(value=value):
                self.assertFalse(self.observe(value, self.health)["contract"]["ready"])

    def test_upstream_stale_is_not_ready(self):
        result = self.observe({**self.evidence, "stale": True})
        self.assertFalse(result["contract"]["ready"])
        self.assertEqual(result["contract"]["reason"], "upstream_stale")

    def test_bounded_body_fails_oversize(self):
        result = self.observe(b" " * (readiness._CONTRACT_MAX_BYTES + 2))
        self.assertEqual(result["contract"]["reason"], "body_too_large")

    def test_missing_declared_contract_fails_closed(self):
        endpoint = dict(self.endpoint)
        del endpoint["contract"]
        with patch.object(readiness, "_liveness", return_value={"reachable": True, "mode": "live"}):
            result = readiness._endpoint_liveness(endpoint)
        self.assertFalse(result["contract"]["ready"])
        self.assertEqual(result["contract"]["reason"], "contract_unconfigured")

    def test_cache_is_usable_only_inside_freshness_bound(self):
        first = self.observe(self.evidence)
        self.clock += 20
        self.network.reset_mock()
        cached = readiness._endpoint_liveness(self.endpoint)
        self.network.assert_not_called()
        self.assertEqual(cached["mode"], "cached")
        self.assertEqual(cached["checked_at"], first["checked_at"])
        self.assertTrue(cached["contract"]["ready"])
        self.assertEqual(cached["age_seconds"], 20)
        self.clock += readiness._LIVENESS_TTL
        self.network.side_effect = TimeoutError("unavailable")
        stale = readiness._endpoint_liveness(self.endpoint)
        self.assertEqual(stale["mode"], "cached")
        self.assertTrue(stale["stale"])
        self.assertTrue(stale["contract"]["valid"])
        self.assertFalse(stale["contract"]["ready"])
        self.assertEqual(stale["error"], "TimeoutError")

    def test_failed_forced_refresh_cannot_reuse_fresh_cache_as_ready(self):
        self.observe(self.evidence)
        self.network.side_effect = TimeoutError("unavailable")
        result = readiness._endpoint_liveness(self.endpoint, fresh=True)
        self.assertEqual(result["mode"], "cached")
        self.assertFalse(result["contract"]["ready"])
        self.assertEqual(result["contract"]["reason"], "live_check_failed")
        self.assertFalse(readiness._endpoint_liveness(self.endpoint)["contract"]["ready"])

    def test_no_cache_network_failure_is_unreachable(self):
        self.network.side_effect = TimeoutError("unavailable")
        result = readiness._endpoint_liveness(self.endpoint, fresh=True)
        self.assertFalse(result["reachable"])
        self.assertFalse(result["contract"]["ready"])
        self.assertEqual(result["mode"], "unreachable")

    def test_legacy_transport_cache_is_not_json_evidence(self):
        readiness._CACHE["live:" + self.endpoint["url"]] = {
            "v": {"reachable": True, "http_status": 200}, "_t": self.clock, "at": "prior"}
        self.network.side_effect = TimeoutError("unavailable")
        self.assertFalse(readiness._endpoint_liveness(self.endpoint)["contract"]["ready"])

    def test_transport_and_application_summary_remain_separate(self):
        good = self.observe({"status": "ok", "organ": "killinchu"}, self.health)
        missing = self.observe({"detail": "Not Found"}, status=404)
        transport = {"reachable": True, "http_status": 200, "mode": "live"}
        with patch.object(readiness, "_endpoints_live", return_value=[transport, transport, good, missing]):
            section = readiness._sec_deployment(readiness._killinchu_cfg())
        summary = readiness._summary([section])
        self.assertEqual(summary["endpoints_reachable"], 4)
        self.assertEqual(summary["json_endpoints_ready"], 1)
        self.assertEqual(summary["json_endpoints_total"], 2)
        self.assertFalse(summary["application_ready"])
        self.assertFalse(readiness._summary([])["application_ready"])

    def snapshot(self):
        lv = self.observe(self.evidence)
        health = self.observe({"status": "ok", "organ": "killinchu"}, self.health)
        rows = [{"role": "api", "liveness": lv}, {"role": "health", "liveness": health}]
        return {"_t": self.clock, "at": "snapshot-time",
                "payload": {"organ": "killinchu",
                            "sections": [{"id": "deployment", "endpoints": rows}]}}

    def contract_cache_key(self, organ="killinchu"):
        return "contract:v1:%s:%s:%s" % (self.endpoint["contract"], organ, self.endpoint["url"])

    def test_snapshot_reconciles_new_http_failure_without_mutation(self):
        snap = self.snapshot()
        original = copy.deepcopy(snap)
        self.clock += 1
        self.network.side_effect = urllib.error.HTTPError(self.endpoint["url"], 404, "missing", {}, None)
        self.assertFalse(readiness._endpoint_liveness(self.endpoint, fresh=True)["contract"]["ready"])
        payload = readiness._snapshot_payload(snap)
        self.assertFalse(payload["summary"]["application_ready"])
        self.assertEqual(payload["sections"][0]["endpoints"][0]["liveness"]["contract"]["reason"],
                         "http_status_404")
        self.assertEqual(snap, original)

    def test_snapshot_reconciles_timeout_without_renewing_evidence_clock(self):
        snap = self.snapshot()
        original = copy.deepcopy(snap)
        self.clock += 1
        self.network.side_effect = TimeoutError("unavailable")
        readiness._endpoint_liveness(self.endpoint, fresh=True)
        payload = readiness._snapshot_payload(snap)
        lv = payload["sections"][0]["endpoints"][0]["liveness"]
        self.assertFalse(payload["summary"]["application_ready"])
        self.assertEqual(lv["contract"]["reason"], "live_check_failed")
        self.assertEqual(lv["checked_at_unix"], original["_t"])
        self.assertEqual(lv["age_seconds"], 1)
        self.assertEqual(payload["snapshot_age_seconds"], 1)
        self.assertEqual(snap, original)

    def test_snapshot_does_not_replace_newer_evidence_with_an_older_failure(self):
        snap = self.snapshot()
        entry = copy.deepcopy(readiness._CACHE[self.contract_cache_key()])
        entry["_t"] -= 1
        entry["v"]["contract"].update(ready=False, reason="live_check_failed")
        readiness._CACHE[self.contract_cache_key()] = entry
        self.assertTrue(readiness._snapshot_payload(snap)["summary"]["application_ready"])

    def test_other_namespace_failure_cannot_override_snapshot(self):
        snap = self.snapshot()
        entry = copy.deepcopy(readiness._CACHE[self.contract_cache_key()])
        entry["v"]["contract"].update(ready=False, reason="live_check_failed")
        readiness._CACHE[self.contract_cache_key("a11oy")] = entry
        self.assertTrue(readiness._snapshot_payload(snap)["summary"]["application_ready"])

    def test_malformed_snapshot_clocks_fail_closed_and_serialize(self):
        for value in (None, True, "bad", float("nan"), float("inf"), -float("inf"), 10**400):
            with self.subTest(clock_type=type(value).__name__):
                snap = self.snapshot()
                snap["_t"] = value
                payload = readiness._snapshot_payload(snap)
                self.assertFalse(payload["summary"]["application_ready"])
                self.assertTrue(payload["stale"])
                self.assertIsNone(payload["snapshot_age_seconds"])
                json.dumps(payload, allow_nan=False)

    def test_malformed_endpoint_clocks_fail_closed_and_serialize(self):
        for value in (None, True, "bad", float("nan"), float("inf"), -float("inf"), 10**400):
            with self.subTest(clock_type=type(value).__name__):
                snap = self.snapshot()
                snap["payload"]["sections"][0]["endpoints"][0]["liveness"]["checked_at_unix"] = value
                before = json.dumps(snap, sort_keys=True)
                payload = readiness._snapshot_payload(snap)
                self.assertFalse(payload["summary"]["application_ready"])
                self.assertIsNone(payload["sections"][0]["endpoints"][0]["liveness"]["checked_at_unix"])
                json.dumps(payload, allow_nan=False)
                self.assertEqual(json.dumps(snap, sort_keys=True), before)

    def test_malformed_cache_clocks_require_new_observation(self):
        for value in (None, True, "bad", float("nan"), float("inf"), -float("inf"), 10**400):
            with self.subTest(clock_type=type(value).__name__):
                self.observe(self.evidence)
                readiness._CACHE[self.contract_cache_key()]["_t"] = value
                self.network.side_effect = TimeoutError("unavailable")
                self.network.reset_mock()
                result = readiness._endpoint_liveness(self.endpoint)
                self.assertFalse(result["contract"]["ready"])
                self.assertEqual(result["mode"], "unreachable")
                self.network.assert_called_once()
                json.dumps(result, allow_nan=False)

    def test_snapshot_rejects_malformed_latest_cache_clock(self):
        snap = self.snapshot()
        readiness._CACHE[self.contract_cache_key()]["_t"] = float("nan")
        payload = readiness._snapshot_payload(snap)
        self.assertFalse(payload["summary"]["application_ready"])
        self.assertEqual(payload["sections"][0]["endpoints"][0]["liveness"]["contract"]["reason"],
                         "invalid_cached_evidence_clock")
        json.dumps(payload, allow_nan=False)

    def test_snapshot_requires_both_health_and_evidence(self):
        for roles in ({"health"}, {"api"}, set()):
            with self.subTest(roles=roles):
                snap = self.snapshot()
                section = snap["payload"]["sections"][0]
                section["endpoints"] = [row for row in section["endpoints"] if row["role"] in roles]
                self.assertFalse(readiness._snapshot_payload(snap)["summary"]["application_ready"])

    def test_future_endpoint_and_latest_cache_clocks_fail_independently(self):
        snap = self.snapshot()
        snap["payload"]["sections"][0]["endpoints"][0]["liveness"]["checked_at_unix"] = self.clock + 1
        payload = readiness._snapshot_payload(snap)
        self.assertFalse(payload["stale"])
        self.assertFalse(payload["summary"]["application_ready"])
        self.assertTrue(payload["sections"][0]["endpoints"][0]["liveness"]["stale"])
        snap = self.snapshot()
        readiness._CACHE[self.contract_cache_key()]["_t"] = self.clock + 1
        payload = readiness._snapshot_payload(snap)
        self.assertFalse(payload["stale"])
        self.assertFalse(payload["summary"]["application_ready"])
        self.assertEqual(payload["sections"][0]["endpoints"][0]["liveness"]["contract"]["reason"],
                         "invalid_cached_evidence_clock")

    def test_snapshot_expires_inner_evidence_before_snapshot_ttl(self):
        snap = self.snapshot()
        original = copy.deepcopy(snap)
        self.assertTrue(readiness._snapshot_payload(snap)["summary"]["application_ready"])
        self.clock += readiness._LIVENESS_TTL
        payload = readiness._snapshot_payload(snap)
        self.assertFalse(payload["summary"]["application_ready"])
        self.assertFalse(payload["stale"])
        self.assertTrue(payload["sections"][0]["endpoints"][0]["liveness"]["stale"])
        self.assertEqual(snap, original)

    def test_old_snapshot_missing_contract_clock_fails(self):
        snap = self.snapshot()
        del snap["payload"]["sections"][0]["endpoints"][0]["liveness"]["checked_at_unix"]
        self.assertFalse(readiness._snapshot_payload(snap)["summary"]["application_ready"])

    def test_stale_or_future_snapshot_never_passes(self):
        for delta in (readiness._SNAPSHOT_STALE + 1, -10):
            with self.subTest(delta=delta):
                snap = self.snapshot()
                self.clock += delta
                payload = readiness._snapshot_payload(snap)
                self.assertTrue(payload["stale"])
                self.assertFalse(payload["summary"]["application_ready"])

    def test_index_and_refresh_expire_same_snapshot_without_live_probes(self):
        snap = self.snapshot()
        self.clock += readiness._LIVENESS_TTL
        handlers = {}

        class App:
            def get(self, path):
                def register(fn):
                    handlers[path] = fn
                    return fn
                return register

        responses = ModuleType("fastapi.responses")
        responses.JSONResponse = lambda body, **_kwargs: body
        with patch.dict(sys.modules, {"fastapi": ModuleType("fastapi"), "fastapi.responses": responses}), \
                patch.object(readiness, "_start_warmer"), \
                patch.object(readiness, "_kick_background_build"), \
                patch.object(readiness, "_snapshot", return_value=snap):
            readiness.register(App(), ns="killinchu")
            self.network.reset_mock()
            for path in ("/api/killinchu/v1/readiness", "/api/killinchu/v1/readiness/refresh"):
                with self.subTest(path=path):
                    result = handlers[path]()
                    self.assertFalse(result["summary"]["application_ready"])
                    self.assertEqual(result["summary"]["json_endpoints_ready"], 0)
                    self.assertEqual(result["served_from"], "background-snapshot")
            self.network.assert_not_called()


if __name__ == "__main__":
    unittest.main()
