# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline contract tests for the single-GET, value-free email diagnostic."""

from http.client import IncompleteRead
import importlib.util
import io
import json
from pathlib import Path
import socket
from urllib.error import HTTPError, URLError

import pytest
import yaml

SCRIPT = Path(__file__).resolve().parents[1] / "diagnose_readiness.py"
SPEC = importlib.util.spec_from_file_location("email_readiness_diagnostic", SCRIPT)
assert SPEC and SPEC.loader
diagnostic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostic)
ROOT = SCRIPT.parents[2]
URL = "https://szl-email-sender.fixture-account.workers.dev"
REVISION = "a" * 40
CANARY = "PRIVATE_PROVIDER_AND_ARGUMENT_CANARY"


@pytest.fixture(autouse=True)
def deny_real_network(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("offline tests must not open a real socket")
    monkeypatch.setattr(socket.socket, "connect", forbidden)
    monkeypatch.setattr(socket, "create_connection", forbidden)


def payload():
    return {
        "worker": "szl-email-sender",
        "source_revision": REVISION,
        "ready": True,
        "readiness_checks": {name: True for name in diagnostic.CHECK_NAMES},
    }


class Response:
    def __init__(self, body, *, status=200, headers=None, url=None):
        self.body = body
        self.status = status
        self.headers = headers if headers is not None else {"Content-Type": "application/json; charset=utf-8"}
        self.url = url if url is not None else URL + diagnostic.REVISION_PATH
        self.read_sizes = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def geturl(self):
        return self.url

    def read(self, size):
        self.read_sizes.append(size)
        return self.body[:size]


class Opener:
    def __init__(self, response=None, error=None):
        self.response = response
        self.error = error
        self.calls = []

    def open(self, request, *, timeout):
        self.calls.append((request, timeout))
        if self.error is not None:
            raise self.error
        return self.response


def observe_body(body, **response_kwargs):
    response = Response(body, **response_kwargs)
    opener = Opener(response)
    report = diagnostic.observe(URL, REVISION, opener=opener)
    assert len(opener.calls) == 1
    assert CANARY not in json.dumps(report)
    return report, response, opener


def observe_payload(value):
    return observe_body(json.dumps(value).encode())[0]


def test_one_get_is_canonical_unauthenticated_and_bounded():
    report, response, opener = observe_body(json.dumps(payload()).encode())
    request, timeout = opener.calls[0]
    assert request.get_method() == "GET" and request.data is None
    assert request.full_url == URL + "/.well-known/szl-worker-revision"
    assert timeout == 15
    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["accept-encoding"] == "identity"
    assert headers["accept"] == "application/json"
    assert not ({"authorization", "proxy-authorization", "cookie"} & set(headers))
    assert response.read_sizes == [64 * 1024] and response.closed
    assert report["state"] == "READY" and report["ready"] is True
    assert report["http_get_attempts"] == 1
    assert report["source_revision_matched"] is True
    assert report["failed_checks"] == []
    assert report["provider_writes"] == report["mail_sends"] == 0
    assert report["caller_authentication_proved"] is False
    assert report["email_delivery_proved"] is False
    assert URL not in json.dumps(report)


@pytest.mark.parametrize("name", diagnostic.CHECK_NAMES)
def test_each_failed_predicate_is_reported_without_guessing(name):
    value = payload()
    value["readiness_checks"][name] = False
    value["ready"] = False
    report = observe_payload(value)
    assert report["state"] == "NOT_READY"
    assert report["reason"] == "PREREQUISITES_NOT_MET"
    assert report["readiness_checks"] == value["readiness_checks"]
    assert report["failed_checks"] == [name]


@pytest.mark.parametrize("field,value", [
    ("worker", CANARY), ("source_revision", "b" * 40),
    ("ready", 0), ("ready", 1), ("ready", "true"), ("ready", None),
    ("readiness_checks", []), ("readiness_checks", None),
])
def test_schema_and_source_mismatch_export_no_provider_values(field, value):
    body = payload()
    body[field] = value
    report = observe_payload(body)
    assert report["state"] == "UNAVAILABLE"
    assert report["readiness_checks"] is None and report["ready"] is None


@pytest.mark.parametrize("value", [0, 1, "true", None, {}, []])
def test_flag_must_be_exact_boolean(value):
    body = payload()
    body["readiness_checks"]["sender_valid"] = value
    assert observe_payload(body)["reason"] == "INVALID_SCHEMA"


@pytest.mark.parametrize("change", ["missing_flag", "extra_flag", "missing_top_key", "extra_top_key", "root_list"])
def test_exact_schema_rejects_omissions_and_unknown_fields(change):
    body = payload()
    if change == "missing_flag":
        del body["readiness_checks"]["sender_valid"]
    elif change == "extra_flag":
        body["readiness_checks"][CANARY] = True
    elif change == "missing_top_key":
        del body["worker"]
    elif change == "extra_top_key":
        body[CANARY] = CANARY
    else:
        body = [body]
    assert observe_payload(body)["reason"] == "INVALID_SCHEMA"


@pytest.mark.parametrize("ready,flag", [(False, True), (True, False)])
def test_ready_must_equal_all_four_flags(ready, flag):
    body = payload()
    body["ready"] = ready
    body["readiness_checks"]["secret_requirement_met"] = flag
    assert observe_payload(body)["reason"] == "READINESS_INCOHERENT"


@pytest.mark.parametrize("body", [
    b'{"ready": false, "ready": true}',
    b'{"nested": {"name": 1, "name": 2}}',
    b'{"value": NaN}', b'{"value": Infinity}', b'{"value": -Infinity}',
    b'{"value": 1e999}', b"\xff", b"not-json",
])
def test_invalid_json_is_rejected_without_body_disclosure(body):
    assert observe_body(body)[0]["reason"] == "INVALID_JSON"


@pytest.mark.parametrize("size", [64 * 1024, 64 * 1024 + 20])
def test_full_read_buffer_is_refused_without_an_overflow_read(size):
    report, response, _ = observe_body(b" " * size)
    assert report["reason"] == "RESPONSE_TOO_LARGE"
    assert response.read_sizes == [64 * 1024]


@pytest.mark.parametrize("status", [201, 301, 400, 404, 500])
def test_unexpected_status_does_not_read_error_body(status):
    report, response, _ = observe_body(CANARY.encode(), status=status)
    assert report["reason"] == "HTTP_STATUS_UNEXPECTED"
    assert response.read_sizes == []


@pytest.mark.parametrize("headers,reason", [
    ({"Content-Type": "application/json", "Content-Encoding": "gzip"}, "CONTENT_ENCODING_UNSUPPORTED"),
    ({"Content-Type": CANARY}, "CONTENT_TYPE_UNEXPECTED"),
    ({}, "CONTENT_TYPE_UNEXPECTED"),
])
def test_unsupported_response_headers_do_not_export_values_or_read_body(headers, reason):
    report, response, _ = observe_body(CANARY.encode(), headers=headers)
    assert report["reason"] == reason and response.read_sizes == []


def test_changed_response_url_is_refused_without_body_read():
    report, response, _ = observe_body(CANARY.encode(), url="https://other.invalid/" + CANARY)
    assert report["reason"] == "RESPONSE_URL_MISMATCH"
    assert response.read_sizes == []


def test_proxy_and_redirect_handlers_are_explicitly_disabled(monkeypatch):
    captured = []
    marker = object()
    monkeypatch.setattr(diagnostic, "build_opener", lambda *handlers: (captured.extend(handlers) or marker))
    assert diagnostic.public_opener() is marker
    proxies = [handler for handler in captured if isinstance(handler, diagnostic.ProxyHandler)]
    redirects = [handler for handler in captured if isinstance(handler, diagnostic.NoRedirectHandler)]
    assert len(proxies) == len(redirects) == 1
    assert proxies[0].proxies == {}
    assert redirects[0].redirect_request(None, None, 302, CANARY, {}, "https://other.invalid") is None


def test_redirect_is_one_failed_request_without_reading_the_error_body():
    class ForbiddenRead(io.BytesIO):
        def read(self, *args):
            pytest.fail("HTTP error bodies must never be read")
    body = ForbiddenRead(CANARY.encode())
    error = HTTPError(URL, 302, CANARY, {"Location": "https://other.invalid/" + CANARY}, body)
    opener = Opener(error=error)
    report = diagnostic.observe(URL, REVISION, opener=opener)
    assert report["reason"] == "REDIRECT_REFUSED"
    assert len(opener.calls) == 1 and body.closed
    assert CANARY not in json.dumps(report)


@pytest.mark.parametrize("error", [URLError(CANARY), TimeoutError(CANARY), IncompleteRead(CANARY.encode())])
def test_transport_failure_is_not_retried_or_reflected(error):
    opener = Opener(error=error)
    report = diagnostic.observe(URL, REVISION, opener=opener)
    assert report["reason"] == "TRANSPORT_UNAVAILABLE"
    assert len(opener.calls) == report["http_get_attempts"] == 1
    assert CANARY not in json.dumps(report)


@pytest.mark.parametrize("url", [
    "http://szl-email-sender.fixture-account.workers.dev",
    "https://other.fixture-account.workers.dev",
    "https://szl-email-sender.fixture-account.workers.dev.evil.invalid",
    URL + "/", URL + "/send", URL + "?secret=" + CANARY, URL + "#" + CANARY,
    URL + ":443", "https://user:password@szl-email-sender.fixture-account.workers.dev",
    "https://szl-email-sender.-invalid.workers.dev", URL + "\n",
])
def test_invalid_deployment_url_never_opens_a_connection(url):
    opener = Opener()
    report = diagnostic.observe(url, REVISION, opener=opener)
    assert report["reason"] == "INVALID_DEPLOYMENT_URL"
    assert report["http_get_attempts"] == 0 and opener.calls == []
    assert CANARY not in json.dumps(report)


@pytest.mark.parametrize("revision", ["a" * 39, "A" * 40, CANARY, "", None])
def test_invalid_revision_never_opens_a_connection_or_echoes_input(revision):
    opener = Opener()
    report = diagnostic.observe(URL, revision, opener=opener)
    assert report["reason"] == "INVALID_EXPECTED_REVISION"
    assert report["expected_source_revision"] is None
    assert report["http_get_attempts"] == 0 and opener.calls == []
    assert CANARY not in json.dumps(report)


def args(output=None):
    values = ["--deployment-url", URL, "--expect-revision", REVISION]
    return values + (["--output", str(output)] if output is not None else [])


def test_valid_not_ready_exits_zero_and_writes_only_the_sanitized_record(tmp_path, monkeypatch, capsys):
    body = payload()
    body["ready"] = False
    body["readiness_checks"]["secret_requirement_met"] = False
    opener = Opener(Response(json.dumps(body).encode()))
    monkeypatch.setattr(diagnostic, "public_opener", lambda: opener)
    path = tmp_path / "readiness.json"
    assert diagnostic.main(args(path)) == 0
    output = capsys.readouterr()
    assert output.err == ""
    assert path.read_text(encoding="utf-8") == output.out
    report = json.loads(output.out)
    assert report["state"] == "NOT_READY"
    assert report["failed_checks"] == ["secret_requirement_met"]
    assert len(opener.calls) == 1


def test_existing_record_is_not_overwritten_and_prevents_observation(tmp_path, monkeypatch, capsys):
    path = tmp_path / "readiness.json"
    path.write_text(CANARY)
    monkeypatch.setattr(diagnostic, "observe", lambda *a, **k: pytest.fail("existing output must stop before GET"))
    assert diagnostic.main(args(path)) == 2
    output = capsys.readouterr()
    assert json.loads(output.out)["reason"] == "RECORD_UNAVAILABLE"
    assert CANARY not in output.out + output.err
    assert path.read_text() == CANARY


def test_unavailable_observation_writes_fixed_record_and_exits_two(tmp_path, monkeypatch, capsys):
    opener = Opener(error=TimeoutError(CANARY))
    monkeypatch.setattr(diagnostic, "public_opener", lambda: opener)
    path = tmp_path / "readiness.json"
    assert diagnostic.main(args(path)) == 2
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report["state"] == "UNAVAILABLE"
    assert report["reason"] == "TRANSPORT_UNAVAILABLE"
    assert path.read_text(encoding="utf-8") == output.out
    assert CANARY not in output.out + output.err


def test_invalid_cli_arguments_do_not_echo_values(capsys):
    assert diagnostic.main(["--unexpected", CANARY]) == 2
    output = capsys.readouterr()
    assert json.loads(output.out)["reason"] == "INVALID_ARGUMENTS"
    assert CANARY not in output.out + output.err


@pytest.mark.parametrize("failure", ["write", "close"])
def test_record_failure_removes_owned_output_without_exporting_exception_text(tmp_path, monkeypatch, capsys, failure):
    path = tmp_path / "readiness.json"
    real_open = Path.open
    class FailingRecord:
        def __init__(self, inner):
            self.inner = inner
        def write(self, text):
            if failure == "write":
                self.inner.write('{"partial":')
                self.inner.flush()
                raise OSError(CANARY)
            return self.inner.write(text)
        def close(self):
            self.inner.close()
            if failure == "close":
                raise OSError(CANARY)
    monkeypatch.setattr(diagnostic.Path, "open", lambda self, *a, **k: FailingRecord(real_open(self, *a, **k)))
    monkeypatch.setattr(diagnostic, "observe", lambda *a: diagnostic.result("OBSERVED_READY", revision=REVISION, attempts=1, checks=payload()["readiness_checks"]))
    assert diagnostic.main(args(path)) == 2
    output = capsys.readouterr()
    report = json.loads(output.out)
    assert report["reason"] == "RECORD_WRITE_FAILED"
    assert report["http_get_attempts"] == 1
    assert CANARY not in output.out + output.err
    assert not path.exists()


def test_workflow_preserves_authoritative_gate_and_owns_the_report_path():
    path = ROOT / ".github/workflows/email-sender-worker.yml"
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["deploy"]["steps"]
    gate = next(step for step in steps if step.get("name") == "Read back the live revision and readiness")
    report = next(step for step in steps if step.get("id") == "readiness_diagnostic")
    artifact = next(step for step in steps if step.get("name") == "Preserve the value-free readiness report")
    assert "--require-ready" in gate["run"] and "continue-on-error" not in gate
    assert steps.index(gate) < steps.index(report) < steps.index(artifact)
    assert report["if"] == "always() && steps.deploy.outcome == 'success'"
    assert report["env"] == {"DEPLOYMENT_URL": "$" + "{{ steps.deploy.outputs.deployment-url }}"}
    assert "mktemp -d" in report["run"] and "--expect-revision" in report["run"]
    assert ('"$' + '{GITHUB_SHA}"') in report["run"]
    assert "diagnose_readiness.py" in report["run"] and "exit" in report["run"]
    assert artifact["if"] == "always() && steps.readiness_diagnostic.outputs.record_path != ''"
    assert artifact["with"]["path"] == "$" + "{{ steps.readiness_diagnostic.outputs.record_path }}"
    assert artifact["with"]["retention-days"] == 7
    assert artifact["with"]["if-no-files-found"] == "error"
    test_command = next(step["run"] for step in workflow["jobs"]["test"]["steps"] if step.get("name") == "Test readback and deployment toolchain contracts")
    assert "ops/email-sender-worker/test/test_diagnose_readiness.py" in test_command
