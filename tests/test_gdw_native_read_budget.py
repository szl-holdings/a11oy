#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline transport-observed read allowance; never a write reservation."""
import time

import httpx
import pytest

from scripts import gdw_acquisition_evidence as native


def evidence(headers, *, protected=True, source="a" * 40):
    calls = []
    def read(request):
        calls.append(request)
        assert request.method == "GET"
        assert str(request.url) == native.API + "/repos/" + native.REPOSITORY + "/branches/main"
        return httpx.Response(200, headers=headers,
            json={"name": "main", "protected": protected, "commit": {"sha": source}})
    environ = {"GITHUB_ACTIONS": "true", "GITHUB_REPOSITORY": native.REPOSITORY,
        "GITHUB_REF": "refs/heads/main", "GITHUB_SHA": "a" * 40,
        "GITHUB_WORKFLOW_REF": native.REPOSITORY + "/" + native.WORKFLOW + "@refs/heads/main",
        "GITHUB_RUN_ID": "123", "GITHUB_RUN_ATTEMPT": "1", "GITHUB_REPOSITORY_ID": "1225834126",
        "GITHUB_EVENT_NAME": "push", "GITHUB_JOB": "durable-acquisition", "GH_TOKEN": "synthetic-read-token"}
    value = native.NativeEvidence(environ, time.monotonic() + 60,
        client=httpx.Client(transport=httpx.MockTransport(read), follow_redirects=False))
    return value, calls


def headers(remaining=950):
    return {"x-ratelimit-resource": "core", "x-ratelimit-limit": "1000",
        "x-ratelimit-remaining": str(remaining), "x-ratelimit-reset": str(int(time.time()) + 3600)}


def test_fresh_protected_main_headers_not_cached_or_claimed_reserved():
    value, calls = evidence(headers())
    for _ in range(2):
        result = value.require_remaining_read_budget(900)
        assert result == {"minimum_reads": 900, "remaining_reads_observed": 950,
            "server_reservation_established": False, "provider_writes_performed": False}
    assert len(calls) == 2
    assert all(request.headers["Authorization"] == "Bearer synthetic-read-token" for request in calls)


@pytest.mark.parametrize("remaining,admitted", [(799, False), (800, True), (877, True)])
def test_canonical_floor_covers_modeled_continuation_without_inventing_reservation(remaining, admitted):
    from scripts import acquire_gdw_durable_storage as acquisition
    assert acquisition.MINIMUM_PUBLICATION_READ_BUDGET == 697 + 103 == 800
    value, calls = evidence(headers(remaining))
    if admitted:
        result = value.require_remaining_read_budget(acquisition.MINIMUM_PUBLICATION_READ_BUDGET)
        assert result["remaining_reads_observed"] == remaining
        assert result["server_reservation_established"] is False
    else:
        with pytest.raises(native.EvidenceBlocked, match="GITHUB_READ_BUDGET_INSUFFICIENT"):
            value.require_remaining_read_budget(acquisition.MINIMUM_PUBLICATION_READ_BUDGET)
    assert len(calls) == 1


@pytest.mark.parametrize("remaining", [0, 1, 899])
def test_insufficient_allowance_holds_without_any_non_get(remaining):
    value, calls = evidence(headers(remaining))
    with pytest.raises(native.EvidenceBlocked, match="GITHUB_READ_BUDGET_INSUFFICIENT"):
        value.require_remaining_read_budget(900)
    assert len(calls) == 1


@pytest.mark.parametrize("name,replacement", [
    ("x-ratelimit-resource", "graphql"), ("x-ratelimit-resource", None),
    ("x-ratelimit-remaining", None), ("x-ratelimit-remaining", "950.0"),
    ("x-ratelimit-remaining", "-1"), ("x-ratelimit-remaining", "1001"),
    ("x-ratelimit-remaining", "private-error"), ("x-ratelimit-limit", "0"),
    ("x-ratelimit-limit", "100001"), ("x-ratelimit-reset", "0"),
    ("x-ratelimit-reset", None), ("x-ratelimit-reset", "nan"),
])
def test_missing_or_malformed_headers_are_unknown_not_invented(name, replacement):
    supplied = headers()
    if replacement is None:
        del supplied[name]
    else:
        supplied[name] = replacement
    value, calls = evidence(supplied)
    with pytest.raises(native.EvidenceBlocked, match="GITHUB_READ_BUDGET_UNAVAILABLE") as caught:
        value.require_remaining_read_budget(900)
    assert "private-error" not in str(caught.value)
    assert len(calls) == 1


@pytest.mark.parametrize("minimum", [0, -1, True, False, 900.0, "900", 100001])
def test_invalid_budget_request_never_contacts_github(minimum):
    value, calls = evidence(headers())
    with pytest.raises(native.EvidenceBlocked, match="GITHUB_READ_BUDGET_UNAVAILABLE"):
        value.require_remaining_read_budget(minimum)
    assert calls == []


@pytest.mark.parametrize("protected,source", [(False, "a" * 40), (True, "b" * 40)])
def test_headers_cannot_substitute_for_exact_protected_source(protected, source):
    value, calls = evidence(headers(), protected=protected, source=source)
    with pytest.raises(native.EvidenceBlocked, match="PROTECTED_SOURCE_NO_LONGER_CURRENT"):
        value.require_remaining_read_budget(900)
    assert len(calls) == 1
