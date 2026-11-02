# SPDX-License-Identifier: Apache-2.0
"""Regression tests for connector state claims without observed reachability."""

from __future__ import annotations

import os
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from szl_connectors.base import Connector, State, resolve_state
from szl_connectors import registry
from szl_connectors.ready import WritableReadyConnector
from szl_connectors.data_sources.maritime_air import AisStreamConnector
from szl_connectors.erp.erpnext import ErpNextConnector
from szl_connectors.erp.odoo import OdooConnector


_TOKEN_ENV = "A11OY_TEST_CONNECTOR_TOKEN"


class _KeylessDeferred(Connector):
    id = "test-keyless-deferred"
    auth_kind = "none"
    provider_base = "https://keyless.invalid"


class _KeylessReachable(_KeylessDeferred):
    id = "test-keyless-reachable"

    def _probe(self):
        return True, "test provider HTTP 200"


class _CredentialedDeferred(Connector):
    id = "test-credentialed-deferred"
    auth_kind = "api_key"
    env_vars = [_TOKEN_ENV]
    provider_base = "https://credentialed.invalid"


class _WritableDeferred(WritableReadyConnector):
    id = "test-writable-deferred"
    auth_kind = "api_key"
    env_vars = [_TOKEN_ENV]
    _primary_secret = _TOKEN_ENV
    provider_base = "https://writable.invalid"
    _read_path = "records"
    _write_path = "records"

    def _probe(self):
        return None, "probe deferred"


class _WritableReachable(_WritableDeferred):
    id = "test-writable-reachable"

    def _probe(self):
        return True, "provider HTTP 200"


class _WritableRejected(_WritableDeferred):
    id = "test-writable-rejected"

    def _probe(self):
        return False, "provider HTTP 401"


class ConnectorStateTruthTests(unittest.TestCase):
    def test_unprobed_keyless_connector_is_ready(self):
        state, detail, sample_reason = resolve_state(
            auth_kind="none",
            missing_env=[],
            has_fixture=False,
            free_tier=True,
            probe_ok=None,
        )
        self.assertEqual(state, State.READY)
        self.assertIn("reachability unknown", detail)
        self.assertNotIn("verified live on read", detail)
        self.assertIsNone(sample_reason)

    def test_credentials_without_probe_are_ready(self):
        state, detail, sample_reason = resolve_state(
            auth_kind="api_key",
            missing_env=[],
            has_fixture=False,
            free_tier=False,
            probe_ok=None,
        )
        self.assertEqual(state, State.READY)
        self.assertIn("credentials present", detail)
        self.assertIn("reachability unknown", detail)
        self.assertNotIn("verified live on read", detail)
        self.assertIsNone(sample_reason)

    def test_successful_probe_is_required_for_connected(self):
        for auth_kind in ("none", "api_key"):
            with self.subTest(auth_kind=auth_kind):
                state, detail, _ = resolve_state(
                    auth_kind=auth_kind,
                    missing_env=[],
                    has_fixture=False,
                    free_tier=auth_kind == "none",
                    probe_ok=True,
                    probe_detail="provider HTTP 200",
                )
                self.assertEqual(state, State.CONNECTED)
                self.assertEqual(detail, "provider HTTP 200")

    def test_failed_probe_paths_are_unchanged(self):
        keyless_state, _, _ = resolve_state(
            auth_kind="none",
            missing_env=[],
            has_fixture=False,
            free_tier=True,
            probe_ok=False,
        )
        credentialed_state, _, _ = resolve_state(
            auth_kind="api_key",
            missing_env=[],
            has_fixture=False,
            free_tier=False,
            probe_ok=False,
        )
        self.assertEqual(keyless_state, State.ERROR)
        self.assertEqual(credentialed_state, State.ERROR)

    def test_default_deferred_probe_cannot_claim_connected(self):
        with patch.dict(os.environ, {_TOKEN_ENV: "configured"}, clear=False):
            report = _CredentialedDeferred().health(probe=True)
        self.assertEqual(report.state, State.READY)
        self.assertIn("reachability unknown", report.detail)

    def test_observed_success_can_claim_connected(self):
        report = _KeylessReachable().health(probe=True)
        self.assertEqual(report.state, State.CONNECTED)
        self.assertEqual(report.detail, "test provider HTTP 200")


class ConnectorWriteTruthTests(unittest.TestCase):
    def test_generic_write_refuses_deferred_reachability(self):
        with patch.dict(os.environ, {_TOKEN_ENV: "configured"}, clear=False), \
             patch("szl_connectors.ready.http_json",
                   side_effect=AssertionError("write HTTP must not run")):
            result = _WritableDeferred().write({"values": {"name": "test"}})
        self.assertFalse(result.ok)
        self.assertEqual(result.state, State.READY)
        self.assertIn("provider reachability", result.detail)

    def test_generic_write_refuses_rejected_provider(self):
        with patch.dict(os.environ, {_TOKEN_ENV: "configured"}, clear=False), \
             patch("szl_connectors.ready.http_json",
                   side_effect=AssertionError("write HTTP must not run")):
            result = _WritableRejected().write({"values": {"name": "test"}})
        self.assertFalse(result.ok)
        self.assertEqual(result.state, State.ERROR)

    def test_generic_write_runs_after_observed_success(self):
        with patch.dict(os.environ, {_TOKEN_ENV: "configured"}, clear=False), \
             patch("szl_connectors.ready.http_json", return_value=(201, {})) as request:
            result = _WritableReachable().write({"values": {"name": "test"}})
        self.assertTrue(result.ok)
        self.assertEqual(result.state, State.CONNECTED)
        self.assertEqual(request.call_count, 1)
        self.assertEqual(request.call_args.kwargs["method"], "POST")

    def test_erpnext_credentials_alone_do_not_pass_write_gate(self):
        env = {
            "SZL_ERPNEXT_URL": "https://erpnext.invalid",
            "SZL_ERPNEXT_TOKEN": "configured",
        }
        connector = ErpNextConnector()
        with patch.dict(os.environ, env, clear=False), \
             patch.object(connector, "health",
                          return_value=SimpleNamespace(state=State.READY)), \
             patch("szl_connectors.erp.erpnext.http_json",
                   side_effect=AssertionError("write HTTP must not run")):
            result = connector.write({"values": {"first_name": "test"}})
        self.assertFalse(result.ok)
        self.assertEqual(result.state, State.READY)

    def test_odoo_credentials_alone_do_not_pass_write_gate(self):
        env = {
            "SZL_ODOO_URL": "https://odoo.invalid",
            "SZL_ODOO_DB": "db",
            "SZL_ODOO_USER": "user",
            "SZL_ODOO_PASSWORD": "configured",
        }
        connector = OdooConnector()
        with patch.dict(os.environ, env, clear=False), \
             patch.object(connector, "health",
                          return_value=SimpleNamespace(state=State.READY)), \
             patch("szl_connectors.erp.odoo._xmlrpc",
                   side_effect=AssertionError("write XML-RPC must not run")):
            result = connector.write({"values": {"name": "test"}})
        self.assertFalse(result.ok)
        self.assertEqual(result.state, State.READY)


class ConnectorReadTruthTests(unittest.TestCase):
    def test_aisstream_key_without_handshake_stays_ready(self):
        with patch.dict(
            os.environ, {"SZL_AISSTREAM_API_KEY": "configured"}, clear=False
        ):
            result = AisStreamConnector().read()
        self.assertEqual(result.state, State.READY)
        self.assertFalse(result.live)
        self.assertEqual(result.records, [])
        self.assertIn("WebSocket reachability is unverified", result.note)


class ConnectorManifestTruthTests(unittest.TestCase):
    def setUp(self):
        self._registry = dict(registry.REGISTRY)
        registry.REGISTRY.clear()
        registry.REGISTRY.update({
            _KeylessDeferred.id: _KeylessDeferred,
            _KeylessReachable.id: _KeylessReachable,
            _CredentialedDeferred.id: _CredentialedDeferred,
        })

    def tearDown(self):
        registry.REGISTRY.clear()
        registry.REGISTRY.update(self._registry)

    def test_cheap_manifest_counts_unobserved_connectors_as_ready(self):
        with patch.dict(os.environ, {_TOKEN_ENV: "configured"}, clear=False):
            result = registry.manifest(probe=False)
        self.assertEqual(result["scoreboard"]["connected"], 0)
        self.assertEqual(result["scoreboard"]["ready"], 3)
        self.assertEqual(result["count"], 3)

    def test_probed_manifest_counts_only_observed_success_as_connected(self):
        with patch.dict(os.environ, {_TOKEN_ENV: "configured"}, clear=False):
            result = registry.manifest(probe=True)
        self.assertEqual(result["scoreboard"]["connected"], 1)
        self.assertEqual(result["scoreboard"]["ready"], 2)
        by_id = {item["id"]: item for item in result["connectors"]}
        self.assertEqual(by_id[_KeylessReachable.id]["state"], "connected")
        self.assertEqual(by_id[_KeylessDeferred.id]["state"], "ready")
        self.assertEqual(by_id[_CredentialedDeferred.id]["state"], "ready")


if __name__ == "__main__":
    unittest.main()
