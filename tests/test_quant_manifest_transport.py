#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline transport tests: real Requests session, synthetic adapter responses."""
import json
import socket
import sys
import types
import warnings
from unittest.mock import Mock

import pytest
import requests
from requests.adapters import BaseAdapter

from scripts import quant_manifest_tool as tool


QUANT = {"sha": "a" * 40, "lastModified": "2026-10-08T00:00:00Z", "siblings": [
    {"rfilename": "fixture.gguf", "lfs": {"sha256": "c" * 64, "size": 123}},
    {"rfilename": "README.md"},
]}
PARENT = {"sha": "b" * 40, "lastModified": "2026-10-07T00:00:00Z", "siblings": []}


class OfflineAdapter(BaseAdapter):
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = []

    def send(self, request, **kwargs):
        self.calls.append((request.url, kwargs))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        status, body = outcome
        response = requests.Response()
        response.status_code = status
        response.url = request.url
        response.request = request
        response._content = body if isinstance(body, bytes) else json.dumps(body).encode()
        return response

    def close(self):
        pass


@pytest.fixture
def transport(monkeypatch):
    sessions = []

    def no_network(*args, **kwargs):
        raise AssertionError("offline transport test attempted a socket connection")

    monkeypatch.setattr(socket.socket, "connect", no_network)
    monkeypatch.setattr(socket, "create_connection", no_network)
    # No test reads ambient netrc credentials or proxy configuration.
    monkeypatch.setattr(requests.sessions, "get_netrc_auth", lambda *args, **kwargs: None)
    monkeypatch.setattr(requests.sessions, "get_environ_proxies", lambda *args, **kwargs: {})
    monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
    monkeypatch.delenv("CURL_CA_BUNDLE", raising=False)

    def configure(outcomes):
        session = requests.sessions.Session()
        adapter = OfflineAdapter(outcomes)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        sessions.append(session)
        monkeypatch.setattr(requests, "Session", lambda: session)
        return adapter

    yield configure
    for session in sessions:
        session.close()


def invoke(monkeypatch, output, *, write_pr=False):
    argv = ["quant_manifest_tool.py", "--repo", "fixture/quant", "--parent",
            "fixture/parent", "--out", str(output)]
    if write_pr:
        argv.append("--write-pr")
    monkeypatch.setattr(sys, "argv", argv)
    return tool.main()


def forbid_provider(monkeypatch):
    provider = types.ModuleType("huggingface_hub")
    provider.HfApi = Mock(side_effect=AssertionError("provider client must not be constructed"))
    provider.CommitOperationAdd = Mock(side_effect=AssertionError("publication must not be prepared"))
    monkeypatch.setitem(sys.modules, "huggingface_hub", provider)
    return provider


def test_default_transport_verifies_tls_and_preserves_manifest_provenance(monkeypatch, tmp_path, transport):
    adapter = transport([(200, QUANT), (200, PARENT)])
    output = tmp_path / "manifest.json"
    assert invoke(monkeypatch, output) == 0
    assert [url for url, _ in adapter.calls] == [
        "https://huggingface.co/api/models/fixture/quant",
        "https://huggingface.co/api/models/fixture/parent",
    ]
    assert all(options["verify"] is True and options["timeout"] == 45 for _, options in adapter.calls)
    manifest = json.loads(output.read_text())
    assert manifest["quant_repo"]["revision"] == QUANT["sha"]
    assert manifest["parent"]["revision"] == PARENT["sha"]
    assert manifest["quant_repo"]["gguf_files"] == [{
        "path": "fixture.gguf", "size_bytes": 123, "sha256": "c" * 64,
        "sha256_source": "hub-lfs",
    }]
    assert manifest["parity_receipt"]["status"] == "BLOCKED"


def test_standard_approved_ca_bundle_setting_remains_available(monkeypatch, tmp_path, transport):
    adapter = transport([(200, QUANT), (200, PARENT)])
    monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/synthetic-approved-ca.pem")
    assert invoke(monkeypatch, tmp_path / "manifest.json") == 0
    assert all(options["verify"] == "/synthetic-approved-ca.pem" for _, options in adapter.calls)


def test_cli_does_not_suppress_transport_warnings_globally(monkeypatch, tmp_path, transport):
    transport([(200, QUANT), (200, PARENT)])
    with warnings.catch_warnings():
        warnings.simplefilter("default")
        before = list(warnings.filters)
        assert invoke(monkeypatch, tmp_path / "manifest.json") == 0
        assert warnings.filters == before


@pytest.mark.parametrize("failed_read", [0, 1], ids=["quant", "parent"])
@pytest.mark.parametrize("failure", [requests.exceptions.SSLError, requests.exceptions.Timeout,
                                      requests.exceptions.ConnectionError])
def test_transport_failure_preserves_existing_output_and_never_reaches_publication(
    monkeypatch, tmp_path, transport, failed_read, failure,
):
    outcomes = [(200, QUANT)] if failed_read else []
    outcomes.append(failure("synthetic transport failure"))
    adapter = transport(outcomes)
    provider = forbid_provider(monkeypatch)
    output = tmp_path / "manifest.json"
    output.write_bytes(b"existing reviewed manifest\n")
    with pytest.raises(failure, match="synthetic transport failure"):
        invoke(monkeypatch, output, write_pr=True)
    assert len(adapter.calls) == failed_read + 1
    assert output.read_bytes() == b"existing reviewed manifest\n"
    provider.HfApi.assert_not_called()
    provider.CommitOperationAdd.assert_not_called()


@pytest.mark.parametrize("failed_read", [0, 1], ids=["quant", "parent"])
@pytest.mark.parametrize("outcome,exception", [
    ((503, {"error": "synthetic outage"}), SystemExit),
    ((200, b"synthetic malformed JSON"), requests.exceptions.JSONDecodeError),
])
def test_failed_metadata_response_cannot_create_a_manifest_or_provider_client(
    monkeypatch, tmp_path, transport, failed_read, outcome, exception,
):
    outcomes = [(200, QUANT)] if failed_read else []
    outcomes.append(outcome)
    transport(outcomes)
    provider = forbid_provider(monkeypatch)
    output = tmp_path / "manifest.json"
    with pytest.raises(exception):
        invoke(monkeypatch, output, write_pr=True)
    assert not output.exists()
    provider.HfApi.assert_not_called()
    provider.CommitOperationAdd.assert_not_called()
