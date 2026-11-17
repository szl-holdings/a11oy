#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Fixture checks for one explicitly selected private tunnel port."""

import json
import os
import pathlib
import sys
import tempfile
import unittest
from unittest import mock

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from runtime_config import GATEWAY_PORT, LOOPBACK_HOST, LocalTransport, TUNNEL_PORT_ENV
import gateway


class LocalTransportTests(unittest.TestCase):
    def test_missing_file_retains_default(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "transport-config.json"
            self.assertEqual(LocalTransport.from_file(path), LocalTransport())

    def test_file_persists_the_selected_port(self):
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "transport-config.json"
            path.write_text(json.dumps({
                "schema": "szl.vm-model-transport/v1", "local_tunnel_port": 19484,
            }), encoding="utf-8")
            self.assertEqual(LocalTransport.from_file(path), LocalTransport(19484))
            self.assertEqual(LocalTransport.from_file(path), LocalTransport(19484))

    def test_invalid_file_fails_closed(self):
        payloads = [
            "{}", "[]", "{",
            '{"schema":"other","local_tunnel_port":19484}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":"19484"}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":true}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":4000}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":19484,"host":"example.com"}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":19484,"remote_port":8081}',
            '{"schema":"szl.vm-model-transport/v1","local_tunnel_port":19484,"local_tunnel_port":19485}',
            " " * 1025,
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = pathlib.Path(directory) / "transport-config.json"
            for payload in payloads:
                with self.subTest(payload=payload):
                    path.write_text(payload, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        LocalTransport.from_file(path)

    def test_default_retains_existing_transport(self):
        transport = LocalTransport.from_environment({})
        self.assertEqual(transport.tunnel_port, 19483)
        self.assertEqual(transport.ssh_forward, "127.0.0.1:19483:127.0.0.1:8080")

    def test_selected_port_matches_forward_probe_and_child(self):
        for port in (1024, 19484, 65535):
            with self.subTest(port=port):
                transport = LocalTransport.from_environment({TUNNEL_PORT_ENV: str(port)})
                self.assertEqual(transport.ssh_forward, f"127.0.0.1:{port}:127.0.0.1:8080")
                self.assertEqual(transport.health_url, f"http://127.0.0.1:{port}/health")
                child = LocalTransport.from_environment(transport.gateway_environment)
                self.assertEqual(child, transport)

    def test_invalid_environment_values_refuse(self):
        for value in ("", "0", "80", "1023", "65536", "99999", "4000", "019483",
                      "+19484", "-19484", "19484.0", " 19484", "19484\n",
                      "localhost:19484", "127.0.0.1:19484", "\uff11\uff19\uff14\uff18\uff14",
                      None, True, 19484):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "invalid_local_tunnel_port"):
                    LocalTransport.from_environment({TUNNEL_PORT_ENV: value})

    def test_invalid_direct_values_refuse(self):
        for value in (True, None, "19484", 19484.0, 0, 1023, 4000, 65536):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "invalid_local_tunnel_port"):
                    LocalTransport(value)

    def test_occupied_gateway_or_selected_tunnel_is_preserved(self):
        for results in ([0], [1, 0]):
            with self.subTest(results=results):
                factory = mock.MagicMock()
                connection = factory.return_value.__enter__.return_value
                connection.connect_ex.side_effect = results
                with self.assertRaisesRegex(SystemExit, "Existing listener preserved"):
                    LocalTransport(19484).require_free_ports(factory)
                expected = [mock.call((LOOPBACK_HOST, GATEWAY_PORT))]
                if len(results) == 2:
                    expected.append(mock.call((LOOPBACK_HOST, 19484)))
                self.assertEqual(connection.connect_ex.call_args_list, expected)

    def test_only_selected_ports_are_probed(self):
        factory = mock.MagicMock()
        connection = factory.return_value.__enter__.return_value
        connection.connect_ex.return_value = 1
        LocalTransport(19484).require_free_ports(factory)
        self.assertEqual(connection.connect_ex.call_args_list, [
            mock.call(("127.0.0.1", 4000)), mock.call(("127.0.0.1", 19484))])

    def test_gateway_main_propagates_selected_upstream(self):
        fixture = {
            TUNNEL_PORT_ENV: "19484",
            "SZL_LITELLM_KEY": "fixture-only",
            "SZL_COSIGN_PRIVATE_PEM": "fixture-only",
            "SZL_VM_GATEWAY_RECEIPTS_DIR": "fixture-only",
        }
        with mock.patch.dict(os.environ, fixture), \
                mock.patch.object(gateway, "Gateway") as adapter, \
                mock.patch.object(gateway, "BoundedServer") as server, \
                mock.patch.object(gateway.Handler, "gateway", create=True):
            gateway.main()
        adapter.assert_called_once_with("fixture-only", "fixture-only", upstream_port=19484)
        server.assert_called_once_with(("127.0.0.1", 4000), gateway.Handler)

    def test_invalid_configuration_precedes_gateway_initialization(self):
        with mock.patch.dict(os.environ, {TUNNEL_PORT_ENV: "4000"}), \
                mock.patch.object(gateway, "Gateway") as adapter, \
                mock.patch.object(gateway, "BoundedServer") as server:
            with self.assertRaisesRegex(ValueError, "invalid_local_tunnel_port"):
                gateway.main()
        adapter.assert_not_called()
        server.assert_not_called()


if __name__ == "__main__":
    unittest.main()
