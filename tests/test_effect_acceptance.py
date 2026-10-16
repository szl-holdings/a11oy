"""Offline checks for the separate, simulated POST acceptance driver."""

import ast
import copy
from functools import lru_cache
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import pytest


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


@lru_cache(maxsize=1)
def _source_operator_ask():
    # Bind this simulated transport to the actual deterministic formula answer,
    # without importing serve, signing a receipt, opening stores or using a model.
    path = SCRIPT.parents[2] / "serve.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    functions = []
    for name in ("_sc_classify", "_sc_ask"):
        nodes = [node for node in ast.walk(tree)
                 if isinstance(node, ast.FunctionDef) and node.name == name]
        assert len(nodes) == 1
        functions.append(nodes[0])
    constants = [node for node in ast.walk(tree) if isinstance(node, ast.Assign)
                 and any(isinstance(target, ast.Name) and target.id == "_SC_PROVED_FORMULAS"
                         for target in node.targets)]
    assert len(constants) == 1
    namespace = {"_SC_PROVED_FORMULAS": ast.literal_eval(constants[0].value),
                 "_sc_receipt": lambda *args: {"evidenceClass": "SIMULATED"}}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(path), "exec"), namespace)
    return namespace["_sc_ask"]


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
                self.top = {"request_id": json["request_id"],
                            "decision": "allow", "receipt_hash": "fixture-only"}
            return Response(200, {"decision": "allow", "receipt_hash": "fixture-only"})
        if path == effect.ROUTES[1]:
            return Response(200, copy.deepcopy(_source_operator_ask()(json["question"])))
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
    assert fixture.posts == list(effect.ROUTES)
    assert [row["result"] for row in rows] == ["PASS"] * 3 + ["UNAVAILABLE", "PASS"]
    assert all(row["attempts"] == 1 for row in rows)
    assert rows[3]["semantic"] == {"authorizationRefused": True}
    assert rows[3]["effectState"] == "REFUSED_BEFORE_ROUTE"
    assert rows[1]["effectState"] == "RESPONSE_OBSERVED_NO_TRACKED_STATE_DELTA"
    assert all("fixture-token" not in str(row) for row in rows)


def test_http_200_without_policy_state_readback_is_unavailable():
    fixture = LocalRouteFixture(record_policy=False)
    rows = effect.rehearse(fixture, "fixture-token")
    assert rows[0]["statusCode"] == 200
    assert rows[0]["result"] == "UNAVAILABLE"
    assert rows[0]["reason"] == "effect_unknown_contract_mismatch"
    assert rows[0]["effectState"] == "UNKNOWN"
    assert fixture.posts == [effect.ROUTES[0]]
    assert all(row["attempts"] == 0 for row in rows[1:])


@pytest.mark.parametrize("mutation", ["old_citation", "count", "formulas", "grounded", "question", "topic"])
def test_formula_contract_mismatch_stops_before_remaining_posts(mutation):
    class ChangedFormula(LocalRouteFixture):
        def post(self, path, json, headers):
            response = super().post(path, json, headers)
            if path == effect.ROUTES[1]:
                body = response.body
                if mutation == "old_citation":
                    body["citations"][0]["endpoint"] = "szl_brain.CANONICAL"
                elif mutation == "count":
                    body["citations"][0]["data"]["count"] = 9
                elif mutation == "formulas":
                    body["citations"][0]["data"]["proved"][-1] = "F23"
                elif mutation == "grounded":
                    body["grounded"] = False
                elif mutation == "question":
                    body["question"] = "different question"
                else:
                    body["topic"] = "general"
            return response

    fixture = ChangedFormula()
    rows = effect.rehearse(fixture, "fixture-token")
    assert fixture.posts == list(effect.ROUTES[:2])
    assert rows[1]["result"] == "UNAVAILABLE" and rows[1]["effectState"] == "UNKNOWN"
    assert all(row["attempts"] == 0 and row["reason"] == "stopped_after_unknown_effect"
               for row in rows[2:])


def test_failed_baseline_never_counts_as_post_attempt():
    class FailedBaseline(LocalRouteFixture):
        def get(self, path):
            if path == effect.FEED:
                raise RuntimeError("fixture_baseline_unavailable")
            return super().get(path)

    fixture = FailedBaseline()
    rows = effect.rehearse(fixture, "fixture-token")
    assert fixture.posts == []
    assert all(row["attempts"] == 0 for row in rows)
    assert all(row["effectState"] == "NOT_ATTEMPTED" for row in rows)


def test_post_effect_readback_failure_stops_all_later_posts():
    class FailedAfterPost(LocalRouteFixture):
        def get(self, path):
            if self.posts:
                raise RuntimeError("fixture_after_unavailable")
            return super().get(path)

    fixture = FailedAfterPost()
    rows = effect.rehearse(fixture, "fixture-token")
    assert fixture.posts == [effect.ROUTES[0]]
    assert rows[0]["attempts"] == 1
    assert rows[0]["reason"] == "effect_unknown_after_post"
    assert rows[0]["effectState"] == "UNKNOWN"
    assert all(row["attempts"] == 0 and row["reason"] == "stopped_after_unknown_effect"
               for row in rows[1:])


def test_unparseable_post_response_stops_all_later_posts():
    class BrokenJson(LocalRouteFixture):
        def post(self, path, json, headers):
            response = super().post(path, json, headers)
            if path == effect.ROUTES[0]:
                response.json = lambda: (_ for _ in ()).throw(ValueError("fixture_json_failure"))
            return response

    fixture = BrokenJson()
    rows = effect.rehearse(fixture, "fixture-token")
    assert fixture.posts == [effect.ROUTES[0]]
    assert rows[0]["effectState"] == "UNKNOWN"
    assert rows[0]["attempts"] == 1
    assert all(row["attempts"] == 0 for row in rows[1:])


def test_redirect_is_not_followed_by_test_client():
    from fastapi import FastAPI
    from fastapi.responses import RedirectResponse

    app = FastAPI()
    reached = []

    @app.post("/start")
    def start():
        return RedirectResponse("/target", status_code=307)

    @app.post("/target")
    def target():
        reached.append(True)
        return {"ok": True}

    response = effect._isolated_client(app).post("/start", json={})
    assert response.status_code == 307
    assert reached == []


def _sample_report(sha, image):
    rows = effect.rehearse(LocalRouteFixture(), "fixture-token")
    return {"schema": "szl.a11oy-effect-acceptance/v1", "evidenceClass": "SIMULATED",
            "scope": "one_shot_declared_source_isolated_container",
            "sourceRevision": sha, "imageId": image,
            "sourceBinding": "DECLARED_IMAGE_REVISION_LABEL", "network": "docker_none",
            "checkedAt": effect._stamp(), "results": rows,
            "summary": {"total": 5, "pass": 4, "unavailable": 1},
            "productionReadiness": "UNAVAILABLE"}


def test_host_accepts_only_bounded_consistent_child_report():
    sha, image = "a" * 40, "sha256:" + "b" * 64
    report = _sample_report(sha, image)
    effect._validate_child_report(report, sha, image)
    for corrupt in (lambda x: x.update(productionReadiness="REAL"),
                    lambda x: x["results"].pop(),
                    lambda x: x["summary"].update(unavailable=0),
                    lambda x: x["results"][3].update(result="PASS", evidenceClass="SIMULATED"),
                    lambda x: x["results"][0].update(attempts=0),
                    lambda x: x["results"][0]["after"].update(policy_decisions=99),
                    lambda x: x["results"][1]["semantic"].update(citationEndpoint="szl_brain.CANONICAL")):
        forged = copy.deepcopy(report)
        corrupt(forged)
        with pytest.raises(ValueError):
            effect._validate_child_report(forged, sha, image)


def test_missing_exact_image_does_not_call_docker(monkeypatch):
    sha = "a" * 40
    monkeypatch.setattr(effect, "_git", lambda *args: sha if args == ("rev-parse", "HEAD") else "")
    monkeypatch.setattr(effect, "_run_bounded", lambda *args, **kwargs: 1 / 0)
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
        return 0, json.dumps([{"Id": image, "Config": {
            "Labels": {"org.opencontainers.image.revision": "c" * 40}}}])

    monkeypatch.setattr(effect, "_run_bounded", inspect_only)
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
            return 0, json.dumps(body)
        assert command[:2] == ["docker", "run"]
        return 0, effect.MARKER + json.dumps(_sample_report(sha, image)) + "\n"

    monkeypatch.setattr(effect, "_run_bounded", local_docker)
    monkeypatch.setattr(effect, "_cleanup_own_container", lambda *args: True)
    with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as directory:
        output = Path(directory) / "report.json"
        assert effect.launch(output, image) == 2
        report = json.loads(output.read_text())
    command = calls[1]
    assert report["summary"] == {"total": 5, "pass": 4, "unavailable": 1}
    assert report["containerCleanupVerified"] is True
    assert command[command.index("--network") + 1] == "none"
    assert "--read-only" in command and "--cap-drop" in command
    assert command[command.index("--entrypoint") + 1] == "python"
    assert "A11OY_NVD_CVSS_DELAY_SEC=0" in command
    assert "--cidfile" in command and "--name" in command and "--label" in command
    assert command[command.index("--mount") + 1].endswith("readonly")
    assert all("fixture-token" not in argument for argument in command)


def test_forged_child_marker_is_rejected_before_write(monkeypatch):
    sha, image = "a" * 40, "sha256:" + "b" * 64
    monkeypatch.setattr(effect, "_git", lambda *args: sha if args == ("rev-parse", "HEAD") else "")
    forged = _sample_report(sha, image)
    forged["results"][3]["result"] = "PASS"
    forged["results"][3]["evidenceClass"] = "SIMULATED"
    forged["secret"] = "must-never-reach-disk"

    def local_docker(command, **kwargs):
        if command[:3] == ["docker", "image", "inspect"]:
            return 0, json.dumps([{"Id": image, "Config": {
                "Labels": {"org.opencontainers.image.revision": sha}}}])
        return 0, effect.MARKER + json.dumps(forged) + "\n"

    monkeypatch.setattr(effect, "_run_bounded", local_docker)
    monkeypatch.setattr(effect, "_cleanup_own_container", lambda *args: True)
    with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as directory:
        output = Path(directory) / "report.json"
        assert effect.launch(output, image) == 2
        on_disk = output.read_text()
    assert "must-never-reach-disk" not in on_disk
    retained = json.loads(on_disk)
    assert retained["results"][0]["reason"] == "isolated_report_invalid"
    assert retained["containerRunInvoked"] is True
    assert retained["containerStarted"] == "UNKNOWN"
    assert all(row["attempts"] == "UNKNOWN" and row["effectState"] == "UNKNOWN"
               for row in retained["results"])


def test_failed_container_run_keeps_effect_occurrence_unknown(monkeypatch):
    sha, image = "a" * 40, "sha256:" + "b" * 64
    monkeypatch.setattr(effect, "_git", lambda *args: sha if args == ("rev-parse", "HEAD") else "")

    def local_docker(command, **kwargs):
        if command[:3] == ["docker", "image", "inspect"]:
            return 0, json.dumps([{"Id": image, "Config": {
                "Labels": {"org.opencontainers.image.revision": sha}}}])
        return 1, ""

    monkeypatch.setattr(effect, "_run_bounded", local_docker)
    monkeypatch.setattr(effect, "_cleanup_own_container", lambda *args: True)
    with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as directory:
        output = Path(directory) / "report.json"
        assert effect.launch(output, image) == 2
        report = json.loads(output.read_text())
    assert report["containerStarted"] == "UNKNOWN"
    assert report["containerCleanupVerified"] is True
    assert all(row["attempts"] == "UNKNOWN" for row in report["results"])


def test_unverified_cleanup_rejects_valid_child_marker(monkeypatch):
    sha, image = "a" * 40, "sha256:" + "b" * 64
    monkeypatch.setattr(effect, "_git", lambda *args: sha if args == ("rev-parse", "HEAD") else "")

    def local_docker(command, **kwargs):
        if command[:3] == ["docker", "image", "inspect"]:
            return 0, json.dumps([{"Id": image, "Config": {
                "Labels": {"org.opencontainers.image.revision": sha}}}])
        return 0, effect.MARKER + json.dumps(_sample_report(sha, image)) + "\n"

    monkeypatch.setattr(effect, "_run_bounded", local_docker)
    monkeypatch.setattr(effect, "_cleanup_own_container", lambda *args: False)
    with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as directory:
        output = Path(directory) / "report.json"
        assert effect.launch(output, image) == 2
        report = json.loads(output.read_text())
    assert report["containerCleanupVerified"] is False
    assert report["summary"]["pass"] == 0
    assert all(row["attempts"] == "UNKNOWN" for row in report["results"])


def test_recovery_identity_survives_failed_report_write_and_temp_cid_removal(monkeypatch):
    sha, image, cid = "a" * 40, "sha256:" + "b" * 64, "c" * 64
    monkeypatch.setattr(effect, "_git", lambda *args: sha if args == ("rev-parse", "HEAD") else "")
    docker_run = []

    def local_docker(command, **kwargs):
        if command[:3] == ["docker", "image", "inspect"]:
            return 0, json.dumps([{"Id": image, "Config": {
                "Labels": {"org.opencontainers.image.revision": sha}}}])
        assert command[:2] == ["docker", "run"]
        docker_run.append(command)
        prepared = Path(directory) / "report.json.recovery.jsonl"
        assert json.loads(prepared.read_text(encoding="utf-8").splitlines()[0])["phase"] == "prepared"
        Path(command[command.index("--cidfile") + 1]).write_text(cid, encoding="ascii")
        return 0, effect.MARKER + json.dumps(_sample_report(sha, image)) + "\n"

    monkeypatch.setattr(effect, "_run_bounded", local_docker)
    monkeypatch.setattr(effect, "_cleanup_own_container", lambda *args: False)
    monkeypatch.setattr(effect, "_write_report", lambda *args: (_ for _ in ()).throw(
        OSError("report write failed")))
    with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as directory:
        output = Path(directory) / "report.json"
        with pytest.raises(OSError, match="report write failed"):
            effect.launch(output, image)
        recovery = output.with_name(output.name + ".recovery.jsonl")
        events = [json.loads(line) for line in recovery.read_text(encoding="utf-8").splitlines()]
        command = docker_run[0]
        assert not Path(command[command.index("--cidfile") + 1]).exists()
        assert not output.exists()
        assert [event["phase"] for event in events] == ["prepared", "cidfile", "cleanup"]
        assert events[0]["containerName"] == command[command.index("--name") + 1]
        assert command[command.index("--label") + 1] == (
            "szl.effect.rehearsal.run=" + events[0]["nonce"])
        assert events[0]["sourceRevision"] == sha and events[0]["imageId"] == image
        assert events[1]["containerId"] == cid
        assert events[1]["idEvidence"] == "FORMAT_VALIDATED_DOCKER_CIDFILE"
        assert events[2]["containerCleanupVerified"] is False
        assert set(events[0]) == {"schema", "phase", "checkedAt", "sourceRevision", "imageId",
                                  "containerName", "nonce"}
        assert set(events[1]) == {"schema", "phase", "checkedAt", "containerId", "idEvidence"}
        assert set(events[2]) == {"schema", "phase", "checkedAt", "containerCleanupVerified"}
        assert all(len(json.dumps(event).encode("utf-8")) <= effect.MAX_RECOVERY_EVENT_BYTES
                   for event in events)


def test_existing_recovery_sidecar_prevents_another_docker_run(monkeypatch):
    with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as directory:
        output = Path(directory) / "report.json"
        recovery = output.with_name(output.name + ".recovery.jsonl")
        recovery.write_text("prior evidence\n", encoding="utf-8")
        monkeypatch.setattr(effect, "_run_bounded", lambda *args, **kwargs: pytest.fail(
            "Docker must not be invoked for an existing recovery receipt"))
        with pytest.raises(FileExistsError):
            effect.launch(output, "sha256:" + "b" * 64)
        assert recovery.read_text(encoding="utf-8") == "prior evidence\n"


def test_recovery_rejects_unbounded_or_untrusted_cidfile():
    with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as directory:
        cidfile = Path(directory) / "container.cid"
        cidfile.write_text("sensitive-marker" * 100, encoding="utf-8")
        assert effect._valid_cidfile_id(cidfile) is None
        with (Path(directory) / "recovery.jsonl").open("x", encoding="utf-8") as recovery:
            with pytest.raises(ValueError, match="recovery_cid_invalid"):
                effect._record_recovery(recovery, "cidfile", container_id="sensitive-marker")
            effect._record_recovery(recovery, "cidfile",
                                    container_id=effect._valid_cidfile_id(cidfile))
        assert "sensitive-marker" not in (Path(directory) / "recovery.jsonl").read_text()


def test_cleanup_only_targets_verified_nonce_container(monkeypatch):
    identifier = "c" * 64
    image = "sha256:" + "b" * 64
    nonce = "a" * 24
    name = "szl-effect-rehearsal-" + nonce
    commands = []
    listings = iter([(0, identifier[:12] + "\n"), (0, "")])

    def local_docker(command, **kwargs):
        commands.append(command)
        if command[:3] == ["docker", "container", "ls"]:
            return next(listings)
        if command[:3] == ["docker", "container", "inspect"]:
            return 0, json.dumps([{"Id": identifier, "Name": "/" + name,
                                   "Image": image,
                                   "Config": {"Labels": {"szl.effect.rehearsal.run": nonce}}}])
        assert command[:3] in (["docker", "container", "stop"],
                               ["docker", "container", "rm"])
        assert command[-1] == identifier
        return 0, ""

    monkeypatch.setattr(effect, "_run_bounded", local_docker)
    with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as directory:
        cidfile = Path(directory) / "container.cid"
        cidfile.write_text(identifier, encoding="utf-8")
        assert effect._cleanup_own_container(name, nonce, image, cidfile) is True
    assert len(commands) == 5


def test_malformed_inspect_is_receipted_without_starting_container(monkeypatch):
    sha, image = "a" * 40, "sha256:" + "b" * 64
    monkeypatch.setattr(effect, "_git", lambda *args: sha if args == ("rev-parse", "HEAD") else "")
    commands = []

    def malformed(command, **kwargs):
        commands.append(command)
        return 0, '["not-an-inspect-object"]'

    monkeypatch.setattr(effect, "_run_bounded", malformed)
    with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as directory:
        output = Path(directory) / "report.json"
        assert effect.launch(output, image) == 2
        report = json.loads(output.read_text())
    assert len(commands) == 1
    assert report["containerRunInvoked"] is False
    assert all(row["attempts"] == 0 for row in report["results"])


def test_existing_report_is_never_overwritten(monkeypatch):
    sha = "a" * 40
    monkeypatch.setattr(effect, "_git", lambda *args: sha if args == ("rev-parse", "HEAD") else "")
    with tempfile.TemporaryDirectory(dir=SCRIPT.parent) as directory:
        output = Path(directory) / "report.json"
        output.write_text("first evidence", encoding="utf-8")
        with pytest.raises(FileExistsError):
            effect.launch(output, None)
        assert output.read_text(encoding="utf-8") == "first evidence"


def test_docker_stdout_is_bounded():
    with pytest.raises(RuntimeError, match="subprocess_output_unavailable"):
        effect._run_bounded([sys.executable, "-c",
                             f"import sys; sys.stdout.write('x'*{effect.MAX_STDIO_BYTES + 1})"],
                            timeout=10)
