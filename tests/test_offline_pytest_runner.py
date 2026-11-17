# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the Linux offline runner in real isolated pytest processes."""
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT / ".github/scripts/offline_pytest.py"


def _run(tmp_path, source, *args):
    module = tmp_path / "test_contract.py"
    module.write_text(source, encoding="utf-8")
    config = tmp_path / "pytest.ini"
    config.write_text("[pytest]\n", encoding="utf-8")
    return subprocess.run(
        [sys.executable, str(RUNNER), "-c", str(config), str(module), "-q", *args],
        cwd=ROOT, capture_output=True, text=True, timeout=30, check=False,
    )


def test_real_dns_and_inet_sockets_are_denied_before_test_collection(tmp_path):
    result = _run(tmp_path, '''
import socket
import pytest

# These real calls happen while pytest imports the module, before any fixture
# or test function can install a late boundary.
for operation in (
    lambda: socket.getaddrinfo("example.invalid", 443),
    lambda: socket.socket(socket.AF_INET, socket.SOCK_STREAM),
):
    with pytest.raises(PermissionError, match="frontier contract denies outbound network"):
        operation()

def test_collected_after_denial():
    assert True
''')
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


def test_pytest_selection_and_failure_exit_status_are_preserved(tmp_path):
    result = _run(tmp_path, '''
def test_selected_failure():
    assert False, "deliberate runner negative control"

def test_unselected_pass():
    assert True
''', "-k", "selected_failure")
    assert result.returncode == 1, result.stdout + result.stderr
    assert "deliberate runner negative control" in result.stdout
    assert "1 failed, 1 deselected" in result.stdout
