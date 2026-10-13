#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Board observations cannot invoke state-changing request contracts."""
from unittest.mock import Mock

import pytest

from tools.verify_board import STATE_CHANGING_ENDPOINTS, observe_endpoint


@pytest.mark.parametrize("endpoint", sorted(STATE_CHANGING_ENDPOINTS))
def test_effect_contracts_remain_unprobed(endpoint):
    client = Mock()
    row = observe_endpoint(client, endpoint + "?example=1")
    assert row["live"] is False
    assert row["code"] is None
    assert "NOT_PROBED" in row["fields"]
    assert client.mock_calls == []


@pytest.mark.parametrize("status", [200, 405, 503])
def test_get_never_falls_back_to_post_and_503_is_not_live(status):
    client = Mock()
    client.get.return_value.status_code = status
    client.get.return_value.json.return_value = {"state": "UNAVAILABLE"}
    row = observe_endpoint(client, "/api/a11oy/v1/genome")
    assert row["live"] is (status == 200)
    client.get.assert_called_once_with("/api/a11oy/v1/genome")
    client.post.assert_not_called()
