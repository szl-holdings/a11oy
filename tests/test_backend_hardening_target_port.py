# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
'''Probe targets honor the port a node's URL env declares.

A Cloudflare-fronted public origin (https, 443) previously kept the static
tailnet probe port, so the fabric sweep reported the operator-declared
endpoint unreachable even while it answered. Ports travel with their URL:
https means 443, an explicit :port is that port, a bare host keeps the static
port, and the host and the port are resolved as one unit.
'''
import pytest

import szl_backend_hardening as bh

_NODE_ENV_VARS = (
    'A11OY_MODEL_BASE_URL', 'A11OY_BETTERWITHAGE_BASE_URL',
    'A11OY_OMEN_BASE_URL', 'A11OY_OMEN_URL', 'A11OY_ENERGY_OMEN_URL',
    'A11OY_CHASKI_BASE_URL', 'A11OY_ENERGY_CHASKI_URL', 'A11OY_CHASKI_URL',
    'SZL_GOV_LLM_URL', 'A11OY_GPU_NODE_RTX_BETTERWITHAGE_IP',
    'A11OY_GPU_NODE_OMEN_BETTERWITHAGE_IP', 'A11OY_GPU_NODE_CHASKI_IP',
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    for var in _NODE_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(bh, '_tailscale_peers', lambda: {})


def test_https_url_env_probes_443(monkeypatch):
    monkeypatch.setenv('A11OY_MODEL_BASE_URL', 'https://meter2.a-11-oy.com/v1')
    assert bh._resolve_node_target('rtx-betterwithage', '100.125.77.31', 11434) == (
        'meter2.a-11-oy.com', 443, 'env:A11OY_MODEL_BASE_URL')


def test_explicit_port_env_url_honored(monkeypatch):
    monkeypatch.setenv('A11OY_BETTERWITHAGE_BASE_URL', 'http://192.0.2.9:4000/v1')
    assert bh._resolve_node_target('rtx-betterwithage', '100.125.77.31', 11434)[:2] == (
        '192.0.2.9', 4000)


def test_bare_host_keeps_static_port(monkeypatch):
    monkeypatch.setenv('A11OY_MODEL_BASE_URL', '192.0.2.9')
    assert bh._resolve_node_target('rtx-betterwithage', '100.125.77.31', 11434)[:2] == (
        '192.0.2.9', 11434)


def test_router_urls_are_ignored(monkeypatch):
    monkeypatch.setenv('A11OY_MODEL_BASE_URL', 'https://router.huggingface.co/v1')
    assert bh._resolve_node_target('rtx-betterwithage', '0.0.0.0', 11434) == (
        '0.0.0.0', 11434, 'static-fallback')


def test_first_env_var_in_priority_order_wins(monkeypatch):
    monkeypatch.setenv('A11OY_OMEN_BASE_URL', 'https://tunnel.a-11-oy.com/v1')
    monkeypatch.setenv('A11OY_OMEN_URL', 'http://192.0.2.10:1234')
    assert bh._resolve_node_target('omen-betterwithage', '100.70.130.45', 11434) == (
        'tunnel.a-11-oy.com', 443, 'env:A11OY_OMEN_BASE_URL')


def test_env_pin_keeps_static_port(monkeypatch):
    monkeypatch.setenv('A11OY_GPU_NODE_RTX_BETTERWITHAGE_IP', '203.0.113.7')
    assert bh._resolve_node_target('rtx-betterwithage', '100.125.77.31', 1188) == (
        '203.0.113.7', 1188, 'env-pin')


def test_sweep_probes_declared_443_with_https_endpoint(monkeypatch):
    monkeypatch.setenv('A11OY_MODEL_BASE_URL', 'https://meter2.a-11-oy.com/v1')
    seen = []

    def fake_probe(host, port, timeout, retries=0):
        seen.append((host, port))
        return True, 'tcp reachable'

    monkeypatch.setattr(bh, 'tcp_connect_probe', fake_probe)
    cache = bh.TTLCache(ttl=30.0)
    payload = bh.probe_fabric_pool(timeout=0.5, cache=cache, force=True, retries=0)
    assert ('meter2.a-11-oy.com', 443) in seen
    by_name = {n['name']: n for n in payload['nodes']}
    assert by_name['rtx-betterwithage']['reachable'] is True
    # The PUBLIC payload scrubs sovereign endpoints to a label by design; the
    # real contract is that the sweep probed the declared https target at all.
    assert 'https://meter2' not in repr(payload)
    assert ('100.125.77.31:11434') not in repr(payload)
