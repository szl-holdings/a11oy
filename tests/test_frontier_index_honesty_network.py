# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 SZL Holdings
"""Prove the contract check denies real network I/O without replacing backends."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT / ".github/scripts/frontier_index_honesty_check.py"


def _checker():
    spec = importlib.util.spec_from_file_location("frontier_honesty_test", CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Audit hooks last for the process. Exercise real stdlib calls in fresh children
# so the pytest runner retains its own unrelated transport policy.
_PRELUDE = r"""
import importlib.util, json, socket, sys, urllib.request
spec = importlib.util.spec_from_file_location('frontier_honesty_child', sys.argv[1])
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
"""


def _child(code):
    result = subprocess.run(
        [sys.executable, "-I", "-c", _PRELUDE + code, str(CHECKER)],
        cwd=ROOT, capture_output=True, text=True, timeout=15, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("operation", [
    "socket.getaddrinfo('example.invalid', 443)",
    "socket.gethostbyname('example.invalid')",
    "socket.gethostbyaddr('192.0.2.1')",
    "socket.getnameinfo(('192.0.2.1', 443), 0)",
    "socket.socket(socket.AF_INET, socket.SOCK_STREAM)",
    "socket.socket(socket.AF_INET6, socket.SOCK_STREAM)",
    "socket.socket(socket.AF_INET, socket.SOCK_DGRAM)",
    "urllib.request.urlopen('https://example.invalid/', timeout=1)",
])
def test_real_dns_and_internet_clients_are_denied(operation):
    result = _child("""
guard._install_no_network_guard()
guard._install_no_network_guard()
try:
    """ + operation + """
except OSError as exc:
    assert 'frontier contract denies outbound network' in str(exc), repr(exc)
else:
    raise AssertionError('Internet operation was not denied')
assert guard._BLOCKED_NETWORK_ATTEMPTS
print(json.dumps({'blocked': True}))
""")
    assert result == {"blocked": True}


@pytest.mark.parametrize("operation,socket_kind", [
    ("sock.connect(('192.0.2.1', 443))", "SOCK_STREAM"),
    ("sock.connect_ex(('192.0.2.1', 443))", "SOCK_STREAM"),
    ("sock.sendto(b'probe', ('192.0.2.1', 443))", "SOCK_DGRAM"),
    ("sock.sendmsg([b'probe'], [], 0, ('192.0.2.1', 443))", "SOCK_DGRAM"),
])
def test_preexisting_socket_cannot_escape_the_boundary(operation, socket_kind):
    result = _child("\nsock = socket.socket(socket.AF_INET, socket." + socket_kind + ")\n" + """
guard._install_no_network_guard()
try:
    """ + operation + """
except PermissionError as exc:
    assert 'frontier contract denies outbound network' in str(exc)
else:
    raise AssertionError('preexisting socket escaped the boundary')
finally:
    sock.close()
print(json.dumps({'blocked': True}))
""")
    assert result == {"blocked": True}


def test_threads_are_denied_but_real_local_asgi_and_socketpairs_work():
    result = _child("""
import concurrent.futures
from fastapi import FastAPI
from starlette.testclient import TestClient
guard._install_no_network_guard()
with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
    future = pool.submit(socket.getaddrinfo, 'example.invalid', 443)
    try:
        future.result(timeout=2)
    except PermissionError:
        pass
    else:
        raise AssertionError('worker thread escaped the boundary')
left, right = socket.socketpair()
try:
    left.sendall(b'local')
    assert right.recv(5) == b'local'
finally:
    left.close()
    right.close()
app = FastAPI()
@app.get('/probe')
def route():
    return {'label': 'MODELED', 'citations': ['arXiv:2401.00001']}
with TestClient(app) as client:
    assert guard.probe_backend(app, client, '/probe') == route()
print(json.dumps({'thread_denied': True, 'real_asgi': True, 'socketpair': True}))
""")
    assert result == {"thread_denied": True, "real_asgi": True, "socketpair": True}


@pytest.mark.parametrize("claimed,emitted", [("LIVE", "SAMPLE"), ("SAMPLE", "LIVE")])
def test_network_policy_never_excuses_independently_observed_label_drift(claimed, emitted):
    guard = _checker()
    catalog = {
        "ok": True, "label": "MODELED", "surfaces": [{
            "id": "anatomy", "backend": "a11oy-native", "label": claimed,
            "endpoint": "/api/a11oy/v1/ecosystem/anatomy", "citations": [],
        }],
    }
    actual = {"label": emitted}
    violations = guard.find_violations(catalog, lambda _path: actual)
    assert len(violations) == 1
    assert "LABEL DRIFT" in violations[0]


def test_all_existing_and_new_negative_controls_still_pass():
    assert _checker()._selftest() == 0
