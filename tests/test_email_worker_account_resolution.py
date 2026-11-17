#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exercise the deployed account validator without credentials or provider calls."""

import json
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/email-sender-worker.yml"
ACCOUNT = "a" * 32


def _validator():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    step = workflow.split("      - name: Resolve Cloudflare deployment account\n", 1)[1]
    step = step.split("      - name: Deploy the exact commit with SOURCE_REVISION\n", 1)[0]
    return textwrap.dedent(step.split("<<'PY'\n", 1)[1].split("\n          PY\n", 1)[0])


def _run(tmp_path, raw):
    response = tmp_path / "accounts.json"
    response.write_bytes(raw)
    return subprocess.run(
        [sys.executable, "-B", "-c", _validator(), str(response)],
        capture_output=True, text=True, timeout=10,
    )


@pytest.mark.parametrize("metadata", [None, {"count": 1, "page": 1, "per_page": 5, "total_count": 1}])
def test_one_account_is_selected_from_a_successful_response(tmp_path, metadata):
    payload = {"success": True, "result": [{"id": ACCOUNT}]}
    if metadata is not None:
        payload["result_info"] = metadata
    result = _run(tmp_path, json.dumps(payload).encode())
    assert result.returncode == 0
    assert result.stdout.strip() == ACCOUNT
    assert result.stderr == ""


@pytest.mark.parametrize("payload", [
    None,
    [],
    {"success": False, "result": [{"id": ACCOUNT}]},
    {"success": "true", "result": [{"id": ACCOUNT}]},
    {"success": 1, "result": [{"id": ACCOUNT}]},
    {"success": True},
    {"success": True, "result": []},
    {"success": True, "result": {}},
    {"success": True, "result": [{"id": ACCOUNT}, {"id": "b" * 32}]},
    {"success": True, "result": [None]},
    {"success": True, "result": [{"id": "private-account-marker"}]},
    {"success": True, "result": [{"id": ACCOUNT + "\nother=value"}]},
    {"success": True, "result": [{"id": 123}]},
    {"success": True, "result": [{"id": ACCOUNT}], "result_info": []},
    {"success": True, "result": [{"id": ACCOUNT}], "result_info": {"total_count": 2}},
    {"success": True, "result": [{"id": ACCOUNT}], "result_info": {"total_count": True}},
    {"success": True, "result": [{"id": ACCOUNT}], "result_info": {"count": 0}},
    {"success": True, "result": [{"id": ACCOUNT}], "result_info": {"page": 2}},
    {"success": True, "result": [{"id": ACCOUNT}], "result_info": {"per_page": False}},
    {"success": True, "result": [{"id": ACCOUNT}], "result_info": {"per_page": 1}},
    {"success": True, "result": [{"id": ACCOUNT}], "result_info": {"per_page": 50}},
    {"success": True, "result": [{"id": ACCOUNT}], "result_info": {"total_pages": 2}},
])
def test_invalid_or_ambiguous_account_responses_stop_without_outputs(tmp_path, payload):
    result = _run(tmp_path, json.dumps(payload).encode())
    assert result.returncode != 0
    assert result.stdout == ""
    assert ACCOUNT not in result.stderr
    assert "private-account-marker" not in result.stderr
    assert "Traceback" not in result.stderr


@pytest.mark.parametrize(
    "raw", [b"private-response-marker", b"\xff", b"x" * (1024 * 1024 + 1)],
    ids=("malformed-json", "invalid-utf8", "oversized-response"),
)
def test_unreadable_and_oversized_responses_do_not_leak_contents(tmp_path, raw):
    result = _run(tmp_path, raw)
    assert result.returncode != 0
    assert result.stdout == ""
    assert "private-response-marker" not in result.stderr
    assert "Traceback" not in result.stderr


def test_account_resolution_keeps_the_existing_deployment_boundary():
    workflow = WORKFLOW.read_text(encoding="utf-8")
    deploy = workflow.split("\n  deploy:\n", 1)[1]
    assert "environment: cloudflare-production" in deploy
    assert "apiToken: ${{ secrets.CLOUDFLARE_API_TOKEN }}" in deploy
    assert "accountId: ${{ steps.cloudflare-account.outputs.account_id }}" in deploy
    assert 'echo "::add-mask::$account_id"' in deploy
    assert "https://api.cloudflare.com/client/v4/accounts?page=1&per_page=5" in deploy
    assert 'if [[ ! "$account_id" =~ ^[0-9a-fA-F]{32}$ ]]' in deploy
    assert "--connect-timeout 10 --max-time 30 --max-filesize 1048576" in deploy
    assert "--require-ready" in deploy
    assert "/zones" not in deploy
    assert "--send" not in deploy
    assert deploy.index("Resolve Cloudflare deployment account") < deploy.index("uses: cloudflare/wrangler-action@")
    assert workflow.count("'tests/test_email_worker_account_resolution.py'") == 2
    test_job = workflow.split("\n  test:\n", 1)[1].split("\n  deploy:\n", 1)[0]
    assert "tests/test_email_worker_account_resolution.py -q" in test_job
