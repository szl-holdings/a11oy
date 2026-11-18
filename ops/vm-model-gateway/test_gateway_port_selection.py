#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings
"""Strict fixture tests for one selected native gateway port (no credentials)."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from runtime_config import GATEWAY_PORT_ENV, LOOPBACK_HOST, TUNNEL_PORT_ENV, LocalTransport
import gateway


class GatewayPortSelectionTests(unittest.TestCase):
    def test_old_two_field_file_still_uses_4000_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transport-config.json"
            path.write_text(json.dumps({
                "schema": "szl.vm-model-transport/v1", "local_tunnel_port": 19484,
            }), encoding="utf-8")
            self.assertEqual(LocalTransport.from_file(path), LocalTransport(19484, 4000))

    def test_new_port_persists_and_matches_child_and_health(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transport-config.json"
            path.write_text(json.dumps({
                "schema": "szl.vm-model-transport/v1",
                "local_tunnel_port": 19484, "local_gateway_port": 4001,
            }), encoding="utf-8")
            for _ in range(2):
                transport = LocalTransport.from_file(path)
                self.assertEqual(transport.gateway_bind, "127.0.0.1:4001")
                self.assertEqual(transport.gateway_health_url, "http://127.0.0.1:4001/health")
                self.assertEqual(transport.upstream, "127.0.0.1:19484")
                self.assertEqual(transport.gateway_environment, {
                    TUNNEL_PORT_ENV: "19484", GATEWAY_PORT_ENV: "4001"
                })

    def test_bad_ports_unknown_or_duplicate_keys_fail_closed(self):
        fixtures = [
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":19484,"local_gateway_port":true}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":19484,"local_gateway_port":"4001"}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":19484,"local_gateway_port":19483}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":19484,"local_gateway_port":19484}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":19484,"local_gateway_port":8080}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":19484,"local_gateway_port":80}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":19484,"local_gateway_port":65536}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":19484,"local_gateway_port":4001,"host":"0.0.0.0"}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":19484,"local_gateway_port":4001,"remote_port":8080}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":19484,"local_gateway_port":4001,"local_gateway_port":4002}',
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "transport-config.json"
            for source in fixtures:
                with self.subTest(source=source):
                    path.write_text(source, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        LocalTransport.from_file(path)
            path.write_text("x" * 1025, encoding="utf-8")
            with self.assertRaises(ValueError):
                LocalTransport.from_file(path)

    def test_gateway_env_rejects_nonascii_malformed_and_reserved_ports(self):
        for value in ("", "04001", "4001.0", "4001 ", "80", "0", "99999",
                      "19483", "8080", None, True, 4001, "127.0.0.1:4001"):
            with self.subTest(port=value):
                with self.assertRaisesRegex(ValueError, "invalid_local_gateway_port"):
                    LocalTransport.from_environment({
                        TUNNEL_PORT_ENV: "19484", GATEWAY_PORT_ENV: value
                    })
        with self.assertRaisesRegex(ValueError, "invalid_local_tunnel_port"):
            LocalTransport(4000, 4001)

    def test_no_takeover_selected_ports_only(self):
        factory = mock.MagicMock()
        conn = factory.return_value.__enter__.return_value
        conn.connect_ex.side_effect = [1, 0]
        with self.assertRaisesRegex(SystemExit, "Existing listener preserved"):
            LocalTransport(19484, 4001).require_free_ports(factory)
        self.assertEqual(conn.connect_ex.call_args_list, [
            mock.call((LOOPBACK_HOST, 4001)),
            mock.call((LOOPBACK_HOST, 19484)),
        ])

    def test_gateway_selected_bind_and_unmodified_model_identity(self):
        with mock.patch.dict(os.environ, {
            TUNNEL_PORT_ENV: "19484", GATEWAY_PORT_ENV: "4001",
            "SZL_LITELLM_KEY": "fixture-only",
            "SZL_COSIGN_PRIVATE_PEM": "fixture-only",
            "SZL_VM_GATEWAY_RECEIPTS_DIR": "fixture-only",
        }), mock.patch.object(gateway, "Gateway") as adapter, \
                mock.patch.object(gateway, "BoundedServer") as server, \
                mock.patch.object(gateway.Handler, "gateway", create=True):
            gateway.main()
        adapter.assert_called_once_with("fixture-only", "fixture-only", upstream_port=19484)
        server.assert_called_once_with((LOOPBACK_HOST, 4001), gateway.Handler)

    def test_source_pin_chain_rejects_unreviewed_bytes(self):
        supervisor_path = HERE / "windows-supervisor.py"
        source = supervisor_path.read_text(encoding="utf-8")
        for name in ("runtime_config.py", "gateway.py"):
            self.assertIn(hashlib.sha256((HERE / name).read_bytes()).hexdigest(), source)
        self.assertIn('"bind":transport.gateway_bind', source)
        self.assertIn("urlopen(transport.gateway_health_url", source)
        self.assertIn('"gateway_bind":transport.gateway_bind', source)
        self.assertIn("FOUR_FILE_SHA256", source)
        bootstrap = (HERE / "windows-bootstrap.py").read_text(encoding="utf-8")
        self.assertIn(hashlib.sha256(supervisor_path.read_bytes()).hexdigest(), bootstrap)


if __name__ == "__main__":
    unittest.main()
