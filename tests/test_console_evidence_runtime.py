# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Execute client evidence boundaries offline, including actual local ECDSA."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_shipped_console_evidence_runtime():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node is required to execute shipped browser JavaScript helpers")
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [node, "scripts/test_console_evidence.cjs"],
        cwd=root,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
