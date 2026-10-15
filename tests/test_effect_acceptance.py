"""Offline checks for the separate, simulated POST acceptance driver."""

import importlib.util
import json
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "tools/readiness-harness/effect_acceptance.py"
SPEC = importlib.util.spec_from_file_location("effect_acceptance", SCRIPT)
effect = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(effect)


class Response:
    def __init__(self, status, body):
        self.status_code = status
        self.body = body

    def json(self):
        return self.body


class LocalRouteFixture:
    """A deterministic transport, not evidence that the deployed app ran."""

    def __init__(self, record_policy=True):
        self.policy = 0
        self.forum = 0
        self.top = None
        self.posts = []
        self.record_policy = record_policy

    def get(self, path):
        if path == effect.FEED:
            return Response(200, {"total_buffered": self.policy,
                                  "verdicts": [self.top] if self.top else []})
        if path == effect.FORUM:
            return Response(200, {"total_events": self.forum})
        raise AssertionError(path)

    def post(self, path, json, headers):
        self.posts.append(path)
        if path == effect.ROUTES[0]:
            if self.record_policy:
                self.policy += 1
                self.top = {"request_id": json["request_id"]}
            return Response(200, {"decision": "allow", "receipt_hash": "fixture-only"})
        if path == effect.ROUTES[1]:
            return Response(200, {"question": json["question"], "topic": "formulas",
                                  "grounded": True,
                                  "citations": [{"endpoint": "szl_brain.CANONICAL",
                                                 "data": {"count": 8, "proved":
                                                          ["F1", "F4", "F7", "F11", "F12",
                                                           "F18", "F19", "F22"]}}]})
        if path == effect.ROUTES[4]:
            return Response(200, {"status": "REAL", "framework": "NIST",
                                  "covered": 8, "total": 8})
        if path == effect.ROUTES[2]:
            assert headers == {"Authorization": "Bearer fixture-token"}
            self.forum += 1
            return Response(200, {"execution_mode": "modeled", "honesty_label": "MODELED",
                                  "aggregate": {"n_evaluated": 0, "execution_complete": False,
                                                "model_qualified": False},
                                  "receipt": {"signing": {"mode": "UNSIGNED-LOCAL"}},
                                  "forum_ingest": {"ingested": True}})
        if path == effect.ROUTES[3]:
            assert headers == {}
            return Response(401, {"status": "BLOCKED"})
        raise AssertionError(path)


def test_bounded_one_shot_rehearsal_keeps_unsafe_effect_unavailable():
    fixture = LocalRouteFixture()
    rows = effect.rehearse(fixture, "fixture-token")
    assert fixture.posts == [effect.ROUTES[i] for i in (0, 1, 4, 2, 3)]
    assert [row["result"] for row in rows] == ["PASS"] * 4 + ["UNAVAILABLE"]
    assert all(row["attempts"] == 1 for row in rows)
    assert rows[-1]["semantic"] == {"authorizationRefused": True}
    assert all("fixture-token" not in str(row) for row in rows)


def test_http_200_without_policy_state_readback_is_unavailable():
    rows = effect.rehearse(LocalRouteFixture(record_policy=False), "fixture-token")
    assert rows[0]["statusCode"] == 200
    assert rows[0]["result"] == "UNAVAILABLE"
    assert rows[0]["semantic"]["feedRequestMatched"] is False


def test_missing_exact_image_does_not_call_docker(monkeypatch):
    sha = "a" * 40
    monkeypatch.setattr(effect, "_git", lambda *args: sha if args == ("rev-parse", "HEAD") else "")
    monkeypatch.setattr(effect.subprocess, "run", lambda *args, **kwargs: 1 / 0)
    with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as directory:
        output = Path(directory) / "report.json"
        assert effect.launch(output, None) == 2
        report = json.loads(output.read_text())
    assert report["sourceRevision"] == sha
    assert report["summary"] == {"total": 5, "pass": 0, "unavailable": 5}
    assert report["productionReadiness"] == "UNAVAILABLE"


def test_image_revision_mismatch_never_starts_container(monkeypatch):
    sha = "a" * 40
    image = "sha256:" + "b" * 64
    monkeypatch.setattr(effect, "_git", lambda *args: sha if args == ("rev-parse", "HEAD") else "")
    calls = []

    def inspect_only(command, **kwargs):
        calls.append(command)
        assert command[:3] == ["docker", "image", "inspect"]
        return type("Result", (), {"returncode": 0,
                                    "stdout": json.dumps([{"Id": image, "Config": {
                                        "Labels": {"org.opencontainers.image.revision": "c" * 40}}}])})()

    monkeypatch.setattr(effect.subprocess, "run", inspect_only)
    with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as directory:
        output = Path(directory) / "report.json"
        assert effect.launch(output, image) == 2
        report = json.loads(output.read_text())
    assert len(calls) == 1
    assert report["summary"]["pass"] == 0
    assert report["summary"]["unavailable"] == 5


def test_matching_local_image_run_is_networkless_and_still_unavailable(monkeypatch):
    sha = "a" * 40
    image = "sha256:" + "b" * 64
    monkeypatch.setattr(effect, "_git", lambda *args: sha if args == ("rev-parse", "HEAD") else "")
    calls = []

    def local_docker(command, **kwargs):
        calls.append(command)
        if command[:3] == ["docker", "image", "inspect"]:
            body = [{"Id": image, "Config": {
                "Labels": {"org.opencontainers.image.revision": sha}}}]
            return type("Result", (), {"returncode": 0, "stdout": json.dumps(body)})()
        assert command[:2] == ["docker", "run"]
        report = effect._blocked_report(sha, "agentloop_effect_not_executed")
        report["imageId"] = image
        return type("Result", (), {"returncode": 0,
                                    "stdout": effect.MARKER + json.dumps(report) + "\n"})()

    monkeypatch.setattr(effect.subprocess, "run", local_docker)
    with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as directory:
        output = Path(directory) / "report.json"
        assert effect.launch(output, image) == 2
    command = calls[1]
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command and "--cap-drop" in command
    assert command[command.index("--mount") + 1].endswith("readonly")
    assert all("fixture-token" not in argument for argument in command)
