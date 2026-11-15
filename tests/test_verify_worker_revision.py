# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline contract for the post-deploy Worker revision readback."""

from __future__ import annotations

import json
from email.message import Message
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from scripts import verify_worker_revision as readback

URL = "https://ntfy.a11oy.net/.well-known/szl-worker-revision"
SHA = "0123456789abcdef0123456789abcdef01234567"
OLD_SHA = "fedcba9876543210fedcba9876543210fedcba98"


def headers(**values: str) -> Message:
    message = Message()
    for name, value in values.items():
        message[name.replace("_", "-")] = value
    return message


class FakeResponse:
    def __init__(self, status: int, body: bytes, response_headers: Message | None = None):
        self.status = status
        self.headers = response_headers or headers(content_type="application/json")
        self._body = BytesIO(body)

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def payload(revision: str | None = SHA, worker: str = "szl-alert-relay", **extra) -> bytes:
    return json.dumps({"worker": worker, "source_revision": revision, **extra}).encode()


def http_error(status: int, response_headers: Message | None = None, body: bytes = b"") -> HTTPError:
    return HTTPError(URL, status, "refused", response_headers or headers(), BytesIO(body))


def install(monkeypatch: pytest.MonkeyPatch, answers: list) -> list:
    seen = []

    def open_request(request, timeout):
        seen.append(request)
        answer = answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        return answer

    def create_opener(handler):
        assert isinstance(handler, readback.NoRedirectHandler)
        return SimpleNamespace(open=open_request)

    monkeypatch.setattr(readback, "build_opener", create_opener)
    return seen


def run(monkeypatch, answers, *, require_ready=False, attempts=4, worker="szl-alert-relay"):
    seen = install(monkeypatch, list(answers))
    sleeps: list[float] = []
    result = readback.verify(
        URL,
        worker=worker,
        revision=SHA,
        require_ready=require_ready,
        attempts=attempts,
        interval=5,
        sleep=sleeps.append,
    )
    return result, seen, sleeps


def test_exact_live_revision_passes_on_first_answer(monkeypatch) -> None:
    result, seen, sleeps = run(monkeypatch, [FakeResponse(200, payload())])
    assert result.ok and result.category == "LIVE_REVISION_MATCH"
    assert len(seen) == 1 and sleeps == []
    request = seen[0]
    assert request.get_method() == "GET"
    assert request.get_header("User-agent") == readback.USER_AGENT
    assert request.full_url == URL


def test_previous_version_during_propagation_is_retried_then_passes(monkeypatch) -> None:
    html = FakeResponse(200, b"<html>ntfy web app</html>", headers(content_type="text/html"))
    answers = [html, FakeResponse(200, payload(OLD_SHA)), FakeResponse(200, payload())]
    result, seen, sleeps = run(monkeypatch, answers)
    assert result.ok
    assert len(seen) == 3 and sleeps == [5, 5]


def test_stale_revision_fails_after_bounded_attempts(monkeypatch) -> None:
    result, seen, sleeps = run(monkeypatch, [FakeResponse(200, payload(OLD_SHA)) for _ in range(4)])
    assert not result.ok and result.category == "REVISION_MISMATCH"
    assert OLD_SHA in result.detail and SHA in result.detail
    assert len(seen) == 4 and len(sleeps) == 3


def test_unset_revision_never_passes(monkeypatch) -> None:
    result, _, _ = run(monkeypatch, [FakeResponse(200, payload(None)) for _ in range(4)])
    assert result.category == "REVISION_MISMATCH"


def test_x402_paywall_is_named_and_not_retried(monkeypatch) -> None:
    result, seen, sleeps = run(monkeypatch, [http_error(402, headers(payment_required="e30="))])
    assert result.category == "EDGE_PAYWALL"
    assert "edge returned 402 (x402 paywall)" in result.detail
    assert len(seen) == 1 and sleeps == []


def test_managed_challenge_is_named_and_not_retried(monkeypatch) -> None:
    challenge = http_error(403, headers(cf_mitigated="challenge"), b"<html>Just a moment</html>")
    result, seen, _ = run(monkeypatch, [challenge])
    assert result.category == "EDGE_CHALLENGE"
    assert "managed challenge (Super Bot Fight Mode)" in result.detail
    assert len(seen) == 1


def test_plain_403_and_redirects_are_terminal_status_failures(monkeypatch) -> None:
    for status in (403, 301, 302, 401):
        result, seen, _ = run(monkeypatch, [http_error(status)])
        assert result.category == "HTTP_STATUS" and f"status={status}" in result.detail
        assert len(seen) == 1


def test_server_errors_and_transport_failures_are_retried(monkeypatch) -> None:
    answers = [http_error(503), URLError("reset"), TimeoutError(), FakeResponse(200, payload())]
    result, seen, _ = run(monkeypatch, answers)
    assert result.ok and len(seen) == 4


def test_wrong_worker_on_the_host_fails(monkeypatch) -> None:
    result, _, _ = run(monkeypatch, [FakeResponse(200, payload(worker="szl-email-sender")) for _ in range(4)])
    assert result.category == "WORKER_MISMATCH"


def test_ready_is_required_only_when_requested(monkeypatch) -> None:
    unready = payload(worker="szl-email-sender", ready=False)
    result, seen, _ = run(monkeypatch, [FakeResponse(200, unready)], require_ready=True, worker="szl-email-sender")
    assert result.category == "NOT_READY" and len(seen) == 1
    result, _, _ = run(monkeypatch, [FakeResponse(200, unready)], worker="szl-email-sender")
    assert result.ok
    ready = payload(worker="szl-email-sender", ready=True)
    result, _, _ = run(monkeypatch, [FakeResponse(200, ready)], require_ready=True, worker="szl-email-sender")
    assert result.ok


def test_oversized_and_non_object_bodies_fail(monkeypatch) -> None:
    huge = FakeResponse(200, b" " * (readback.MAX_RESPONSE_BYTES + 1))
    result, _, _ = run(monkeypatch, [huge])
    assert result.category == "RESPONSE_TOO_LARGE"
    result, _, _ = run(monkeypatch, [FakeResponse(200, b"[1,2]") for _ in range(4)])
    assert result.category == "INVALID_RESPONSE"


@pytest.mark.parametrize(
    "argv",
    [
        ["--url", "http://ntfy.a11oy.net/x", "--worker", "szl-alert-relay", "--expect-revision", SHA],
        ["--url", "https://user:pw@ntfy.a11oy.net/x", "--worker", "szl-alert-relay", "--expect-revision", SHA],
        ["--url", URL + "#frag", "--worker", "szl-alert-relay", "--expect-revision", SHA],
        ["--url", URL, "--worker", "Bad_Name", "--expect-revision", SHA],
        ["--url", URL, "--worker", "szl-alert-relay", "--expect-revision", SHA[:8]],
        ["--url", URL, "--worker", "szl-alert-relay", "--expect-revision", SHA.upper()],
        ["--url", URL, "--worker", "szl-alert-relay", "--expect-revision", SHA, "--attempts", "0"],
    ],
)
def test_invalid_arguments_are_refused_before_any_request(monkeypatch, capsys, argv) -> None:
    seen = install(monkeypatch, [])
    assert readback.main(argv) == 2
    assert seen == []
    assert "::error::" in capsys.readouterr().err


def test_main_reports_success_and_failure_with_annotations(monkeypatch, capsys) -> None:
    install(monkeypatch, [FakeResponse(200, payload())])
    argv = ["--url", URL, "--worker", "szl-alert-relay", "--expect-revision", SHA, "--attempts", "1"]
    assert readback.main(argv) == 0
    assert SHA in capsys.readouterr().out

    install(monkeypatch, [http_error(402)])
    assert readback.main(argv) == 1
    err = capsys.readouterr().err
    assert err.startswith("::error::szl-alert-relay on ntfy.a11oy.net did not prove the deployed revision")
    assert "edge returned 402 (x402 paywall)" in err
