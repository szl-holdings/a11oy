#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Convergent vertical publication, workflow shape, and drift tracking.

The vertical Spaces drifted for weeks because their publisher only ran on an
operator dispatch. These tests bind the automatic publisher to what the
renderer actually reads, prove a converged estate is a no-op, and prove the
drift tracker opens, updates and closes one issue.
"""
from __future__ import annotations

import datetime as dt
import fnmatch
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PUBLISH_WORKFLOW = ROOT / ".github/workflows/hf-publish-vertical-flagships.yml"
DRIFT_WORKFLOW = ROOT / ".github/workflows/hf-vertical-drift.yml"
SYNC_WORKFLOW = ROOT / ".github/workflows/hf-sync.yml"
HEAD = "a" * 40
SERVED = "b" * 40


def _fake_hub() -> ModuleType:
    fake = ModuleType("huggingface_hub")
    fake.HfApi = type("HfApi", (), {})
    return fake


@pytest.fixture
def conv(monkeypatch):
    monkeypatch.setitem(sys.modules, "huggingface_hub", _fake_hub())
    spec = importlib.util.spec_from_file_location("hf_vertical_convergence_test",
                                                  ROOT / "scripts/hf_vertical_convergence.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def renderer(conv):
    return conv.load_renderer()


def _on(workflow: dict) -> dict:
    return workflow.get("on", workflow.get(True))


def _load_workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


# ----------------------------------------------------------- input coverage

AUDIT_SCRIPT = textwrap.dedent(r'''
    import importlib.util, json, os, re, sys, types
    root = os.path.abspath(sys.argv[1])
    reads = set()
    pyc = re.compile(r"^(.*)/__pycache__/([^/.]+)\.[^/]+\.pyc(\.\d+)?$")
    def hook(event, args):
        if event != "open" or not args or not isinstance(args[0], (str, bytes, os.PathLike)):
            return
        path = os.path.abspath(os.fsdecode(args[0]))
        if not path.startswith(root + os.sep):
            return
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        match = pyc.match(rel)
        reads.add(f"{match.group(1)}/{match.group(2)}.py" if match else rel)
    fake = types.ModuleType("huggingface_hub")
    fake.HfApi = type("HfApi", (), {})
    sys.modules["huggingface_hub"] = fake
    sys.addaudithook(hook)
    spec = importlib.util.spec_from_file_location("renderer", os.path.join(root, "scripts/hf_publish_vertical_flagships_v4_impl.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = {"load": sorted(reads)}
    for slug in ("terra", "counsel", "sentra", "finance"):
        reads.clear()
        item = next(row for row in module.FLAGSHIPS if row["slug"] == slug)
        module.html(item); module.readme(item)
        if slug == "terra": module.load_terra_forge_bundle()
        if slug == "finance": module.render_finance_payloads("1" * 40, 1)
        if slug == "sentra": module.render_sentra_payload("1" * 40, 1)
        result[slug] = sorted(reads)
    print(json.dumps(result))
''')


def test_render_inputs_are_exactly_the_files_the_renderer_reads(conv):
    completed = subprocess.run([sys.executable, "-I", "-B", "-c", AUDIT_SCRIPT, str(ROOT)],
                               capture_output=True, text=True, check=True)
    observed = json.loads(completed.stdout.strip().splitlines()[-1])
    shared = set(observed["load"])
    assert shared == set(conv.SHARED_RENDER_INPUTS)
    for slug in conv.GENERATED_TARGETS:
        assert shared | set(observed[slug]) == set(conv.TARGET_RENDER_INPUTS[slug]), slug
    assert set(observed["terra"]) == set(conv.TERRA_FORGE_INPUTS)


def test_every_declared_input_exists(conv):
    for path in conv.workflow_push_paths():
        assert (ROOT / path).is_file(), path


def test_push_filter_is_exactly_the_declared_publisher_inputs(conv):
    on = _on(_load_workflow(PUBLISH_WORKFLOW))
    assert on["push"]["branches"] == ["main"]
    assert tuple(on["push"]["paths"]) == conv.workflow_push_paths()
    # Every publisher module the entrypoint loads by path is an input.
    entrypoint = (ROOT / "scripts/hf_publish_vertical_flagships_v4.py").read_text(encoding="utf-8")
    for name in re.findall(r'HERE / "([a-z_0-9]+\.py)"', entrypoint):
        if name.startswith("hf_publish_vertical_services"):
            continue  # estate-only combined runtime: manual dispatch, not automated
        assert f"scripts/{name}" in on["push"]["paths"], name


# ------------------------------------------------------------ workflow shape


def _job_text(workflow_text: str, job: str) -> str:
    start = workflow_text.index(f"\n  {job}:\n")
    following = re.search(r"\n  [a-z][a-z0-9-]*:\n", workflow_text[start + 1:])
    return workflow_text[start:start + 1 + following.start()] if following else workflow_text[start:]


def _assert_references_resolve(path: Path) -> None:
    workflow = _load_workflow(path)
    text = path.read_text(encoding="utf-8")
    jobs = workflow["jobs"]
    for name, job in jobs.items():
        block = _job_text(text, name)
        needs = job.get("needs", [])
        needs = [needs] if isinstance(needs, str) else list(needs)
        for needed, output in re.findall(r"needs\.([a-z0-9-]+)\.outputs\.([a-z_]+)", block):
            assert needed in needs, (name, needed)
            assert output in jobs[needed].get("outputs", {}), (name, needed, output)
        for needed in re.findall(r"needs\.([a-z0-9-]+)\.result", block):
            assert needed in needs, (name, needed)
        ids = []
        for step in job.get("steps", []):
            condition = str(step.get("if", "")) + json.dumps(step.get("with", {})) + str(step.get("run", ""))
            for referenced in re.findall(r"steps\.([a-z_]+)\.", condition):
                assert referenced in ids, (name, referenced, "referenced before definition")
            if "id" in step:
                ids.append(step["id"])
        for output in job.get("outputs", {}).values():
            for referenced in re.findall(r"steps\.([a-z_]+)\.", output):
                assert referenced in ids, (name, referenced)


def test_publisher_triggers_are_push_schedule_deploy_completion_and_dispatch():
    workflow = _load_workflow(PUBLISH_WORKFLOW)
    on = _on(workflow)
    assert set(on) == {"push", "schedule", "workflow_run", "workflow_dispatch"}
    assert on["schedule"] == [{"cron": "41 * * * *"}]
    sync_name = _load_workflow(SYNC_WORKFLOW)["name"]
    assert on["workflow_run"] == {"workflows": [sync_name], "types": ["completed"], "branches": ["main"]}
    scope = on["workflow_dispatch"]["inputs"]["scope"]
    assert scope["options"] == ["finance", "lyte", "terra", "sentra", "counsel", "estate"]
    assert workflow["permissions"] == {"contents": "read"}


WRITER_GROUP = {"group": "hf-vertical-estate", "cancel-in-progress": False}
HF_SECRETS = ("HF_ORG_TOKEN", "HF_WRITE_TOKEN", "HF_TOKEN", "HUGGINGFACE_TOKEN",
              "HUGGING_FACE_HUB_TOKEN")


def _writer_jobs(workflow: dict) -> dict:
    """Every job with a step that runs the vertical publisher."""
    return {name: job for name, job in workflow["jobs"].items()
            if any("hf_publish_vertical_flagships_v4.py" in str(step.get("run", ""))
                   for step in job.get("steps", []))}


def test_publisher_job_graph_and_conditions_are_consistent():
    _assert_references_resolve(PUBLISH_WORKFLOW)
    _assert_references_resolve(DRIFT_WORKFLOW)
    workflow = _load_workflow(PUBLISH_WORKFLOW)
    jobs = workflow["jobs"]
    assert set(jobs) == {"plan", "publish-targets", "publish"}
    assert set(jobs["plan"]["outputs"]) == {"mode", "publish", "estate"}
    assert jobs["plan"]["permissions"] == {"contents": "read", "actions": "read"}
    targets = jobs["publish-targets"]
    assert targets["needs"] == "plan" and "strategy" not in targets
    assert "needs.plan.outputs.publish == 'true'" in targets["if"]
    assert targets["env"]["SZL_PUBLICATION_MODE"] == "${{ needs.plan.outputs.mode }}"
    estate = jobs["publish"]
    assert "needs.plan.outputs.estate == 'true'" in estate["if"]
    assert estate["env"]["SZL_FLAGSHIP_SCOPE"] == "estate"
    # Planning is read-only and holds no group; a non-main dispatch fails there
    # instead of being skipped.
    assert "concurrency" not in workflow and "concurrency" not in jobs["plan"]
    assert "github.ref" not in jobs["plan"]["if"]
    assert jobs["plan"]["steps"][1]["run"].strip().endswith('test "$GITHUB_REF" = refs/heads/main')


def test_every_vertical_writer_shares_one_non_cancelling_lock():
    """One lock per Space across all writers: every vertical writer (both jobs
    here and hf-sync's vertical job) holds the same group, so two writers can
    never interleave uploads on one Space."""
    for path in (PUBLISH_WORKFLOW, SYNC_WORKFLOW):
        writers = _writer_jobs(_load_workflow(path))
        assert writers, path
        for name, job in writers.items():
            assert job.get("concurrency") == WRITER_GROUP, (path.name, name)
    assert set(_writer_jobs(_load_workflow(PUBLISH_WORKFLOW))) == {"publish-targets", "publish"}
    assert "hf-vertical-target-" not in PUBLISH_WORKFLOW.read_text(encoding="utf-8")


def test_hugging_face_credentials_reach_only_the_publisher_steps():
    workflow = _load_workflow(PUBLISH_WORKFLOW)
    for name, job in workflow["jobs"].items():
        assert not set(HF_SECRETS) & set(job.get("env", {})), name
        for step in job.get("steps", []):
            env = step.get("env", {})
            if "hf_publish_vertical_flagships_v4.py" in str(step.get("run", "")):
                assert set(HF_SECRETS) <= set(env), (name, step.get("name"))
            else:
                assert not set(HF_SECRETS) & set(env), (name, step.get("name"))
    # Inside the multi-target step, the read-only commands run without them.
    step = next(s for s in workflow["jobs"]["publish-targets"]["steps"] if s.get("id") == "publish")
    script = step["run"]
    assert "env -u HF_ORG_TOKEN -u HF_WRITE_TOKEN -u HF_TOKEN -u HUGGINGFACE_TOKEN -u HUGGING_FACE_HUB_TOKEN" in script
    for command in ("hf_vertical_convergence.py targets", "hf_vertical_convergence.py check",
                    "hf_vertical_convergence.py wait-sentra"):
        line = next(line for line in script.splitlines() if command in line)
        assert "readonly_run python" in line, line


def test_publish_steps_keep_exact_main_live_verification_and_honest_supersession():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    targets = _job_text(text, "publish-targets")
    assert 'test "$GITHUB_REF" = refs/heads/main' in targets
    assert 'if [ "$(git rev-parse HEAD)" = "$(git rev-parse FETCH_HEAD)" ]; then' in targets
    # A moved main is neutral only for automatic convergence; a dispatch fails.
    assert 'elif [ "$SZL_PUBLICATION_MODE" = CONVERGENCE ]; then' in targets
    assert "a dispatched publication requires the exact current main" in targets
    assert 'SZL_FLAGSHIP_SCOPE="$target" python scripts/hf_publish_vertical_flagships_v4.py' in targets
    assert 'if [ "$code" -eq 75 ] && [ "$forced" = false ]; then' in targets
    assert 'if [ "$code" -ne 0 ]; then' in targets
    assert 'if [ "$admission" = SUPERSEDED ] && [ "$forced" = false ]; then' in targets
    assert 'if [ "$admission" != ADMISSIBLE ]; then' in targets
    # The plan is re-made under the lock, and each target re-checked.
    assert "hf_vertical_convergence.py plan --output hf-vertical-convergence-locked-plan.json" in targets
    assert "--defer-to-dispatched-writers" not in targets
    assert 'hf_vertical_convergence.py check --target "$target"' in targets
    assert "wait-sentra --timeout 2400" in targets
    assert "--defer-to-dispatched-writers" in _job_text(text, "plan")
    estate = _job_text(text, "publish")
    assert 'test "$(git rev-parse HEAD)" = "$(git rev-parse FETCH_HEAD)"' in estate
    for job in (targets, estate, _job_text(text, "plan")):
        assert "persist-credentials: false" in job
        assert "ref: ${{ github.sha }}" in job


def test_sentra_is_published_last_under_the_lock(conv):
    assert conv.TARGETS[-1] == "sentra"
    assert set(conv.TARGETS) == {"terra", "counsel", "finance", "lyte", "sentra"}


def test_contract_suite_runs_on_every_publisher_input_change(conv):
    """The input-table test must run on the PRs that change those inputs."""
    on = _on(_load_workflow(ROOT / ".github/workflows/hf-vertical-services-v2-contract.yml"))
    for event in ("pull_request", "push"):
        paths = set(on[event]["paths"])
        for path in conv.workflow_push_paths():
            assert any(fnmatch.fnmatchcase(path, pattern) for pattern in paths), (event, path)
        for suite in ("tests/test_hf_vertical_convergence.py", "tests/test_vertical_publication_scope.py",
                      "tests/test_hf_publish_vertical_flagships_v3.py"):
            assert suite in paths, (event, suite)
    text = (ROOT / ".github/workflows/hf-vertical-services-v2-contract.yml").read_text(encoding="utf-8")
    for suite in ("tests/test_hf_vertical_convergence.py", "tests/test_vertical_publication_scope.py",
                  "tests/test_hf_publish_vertical_flagships_v3.py"):
        assert suite in text.split("python -m pytest", 1)[1], suite


@pytest.mark.parametrize("path", [PUBLISH_WORKFLOW, DRIFT_WORKFLOW])
def test_workflows_add_no_exact_identity_gates(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if "uses:" in line:
            continue
        assert re.search(r"\b[0-9a-f]{40}\b", line) is None, line
        assert re.search(r"\b\d{10,12}\b", line) is None, line  # run or artifact ids
    text = path.read_text(encoding="utf-8")
    assert "run_attempt ==" not in text


def test_drift_workflow_is_scheduled_read_only_and_tracks_one_issue():
    workflow = _load_workflow(DRIFT_WORKFLOW)
    on = _on(workflow)
    assert set(on) == {"schedule", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read", "issues": "write"}
    text = DRIFT_WORKFLOW.read_text(encoding="utf-8")
    assert "secrets." not in text  # no Hugging Face credential: it cannot write a Space
    assert "hf_vertical_convergence.py report" in text and "--sync-issue" in text
    job = workflow["jobs"]["drift"]
    assert job["env"]["DRIFT_ALERT_HOURS"] == "6"


def test_convergence_tool_never_writes_to_hugging_face():
    source = (ROOT / "scripts/hf_vertical_convergence.py").read_text(encoding="utf-8")
    for forbidden in ("create_commit", "upload_file", "upload_folder", "restart_space",
                      "add_space_variable", "delete_file", "HfApi(", "HF_TOKEN"):
        assert forbidden not in source, forbidden


# ------------------------------------------------------------------ renderer


def test_offline_fingerprint_matches_the_generated_writer_upload(conv, renderer, monkeypatch, tmp_path):
    """The planner's terra/counsel rendering equals what base main() uploads."""
    for slug in ("terra", "counsel"):
        monkeypatch.setenv("GITHUB_SHA", HEAD)
        monkeypatch.setenv("GITHUB_RUN_ID", "77")
        captured: dict[str, bytes] = {}
        api = SimpleNamespace(repo_exists=lambda **k: True, auth_check=lambda **k: None,
                              upload_file=lambda **k: captured.update({k["path_in_repo"]: k["path_or_fileobj"]}),
                              restart_space=lambda *a: None)
        monkeypatch.setattr(renderer, "FLAGSHIPS", tuple(row for row in conv.load_renderer().FLAGSHIPS
                                                         if row["slug"] == slug))
        monkeypatch.setattr(renderer._BASE, "token_from_env", lambda: ("fixture-writer", "SIMULATED"))
        monkeypatch.setattr(renderer._BASE, "HfApi", lambda **k: api)
        monkeypatch.setattr(renderer._BASE, "observe_flagship", lambda row: None)
        monkeypatch.setattr(renderer._BASE, "observation_passes", lambda *a, **k: True)
        monkeypatch.chdir(tmp_path)
        assert renderer.main() == 0
        expected = conv.expected_generated(renderer, slug)
        assert {path: conv.git_blob_id(captured[path]) for path in conv.PUBLISHED_FILES} == expected["files"]
        served = json.loads(captured["config.json"])
        assert served["source_revision"] == HEAD and served["workflow_run_id"] == 77
        assert conv.expected_config_bytes(expected["config"], served) == captured["config.json"]


def test_fingerprint_is_independent_of_source_identity(conv, renderer):
    for slug in conv.GENERATED_TARGETS:
        first = conv.expected_generated(renderer, slug)
        second = conv.expected_generated(renderer, slug)
        assert first == second
        assert not set(conv.IDENTITY_FIELDS) & set(first["config"])


def _served(conv, renderer, slug, *, revision=SERVED, run_id=11, mutate=None):
    expected = conv.expected_generated(renderer, slug)
    tree = dict(expected["files"])
    identity = {"source_revision": revision, "workflow_run_id": run_id}
    config = json.loads(conv.expected_config_bytes(expected["config"], identity))
    if slug == "finance":
        tree[conv.FINANCE_MANIFEST] = conv.expected_finance_manifest_blob(renderer, identity)
    if mutate:
        mutate(tree, config)
    raw = (json.dumps(config, indent=2, sort_keys=True) + "\n").encode()
    return expected, tree, config, raw


def _observe(conv, monkeypatch, tree, config, raw, *, live=None, last_modified="2026-10-13T00:00:00Z",
             stage="RUNNING"):
    monkeypatch.setattr(conv, "hub_tree", lambda slug: dict(tree))
    monkeypatch.setattr(conv, "hub_config", lambda slug: (dict(config), raw))
    monkeypatch.setattr(conv, "space_info", lambda slug: {"sha": "f" * 40, "stage": stage,
                                                          "last_modified": last_modified})
    if callable(live):
        monkeypatch.setattr(conv, "live_build_info", live)
    else:
        monkeypatch.setattr(conv, "live_build_info", lambda slug: live or {
            "source_revision": config["source_revision"],
            "artifact_set_sha256": config["artifact_set_sha256"]})
    monkeypatch.setattr(conv, "first_input_change_after", lambda revision, inputs: dt.datetime(
        2026, 10, 3, 6, 7, 50, tzinfo=dt.timezone.utc))


@pytest.mark.parametrize("slug", ["terra", "counsel", "sentra"])
def test_converged_target_is_a_no_op_despite_unrelated_main_commits(conv, renderer, monkeypatch, slug):
    _, tree, config, raw = _served(conv, renderer, slug)
    _observe(conv, monkeypatch, tree, config, raw)
    row = conv.assess_generated(slug, renderer, head=HEAD)
    assert row["state"] == "CONVERGED" and row["publish"] is False
    assert row["served_revision"] == SERVED != HEAD
    assert row["runtime"]["state"] == "CURRENT"


@pytest.mark.parametrize("path", ["app.py", "index.html", "README.md", "Dockerfile"])
def test_any_changed_published_byte_is_drift_and_publishes(conv, renderer, monkeypatch, path):
    _, tree, config, raw = _served(conv, renderer, "terra",
                                   mutate=lambda tree, config: tree.__setitem__(path, "0" * 40))
    _observe(conv, monkeypatch, tree, config, raw)
    row = conv.assess_generated("terra", renderer, head=HEAD)
    assert row["state"] == "DRIFT" and row["publish"] is True
    assert row["differing_files"] == [path]
    assert row["drift_since"] == "2026-10-03T06:07:50Z"


def test_config_content_change_is_drift_but_identity_change_is_not(conv, renderer, monkeypatch):
    _, tree, config, raw = _served(conv, renderer, "counsel",
                                   mutate=lambda tree, config: config.update(upstream="https://example.invalid/feed"))
    _observe(conv, monkeypatch, tree, config, raw)
    row = conv.assess_generated("counsel", renderer, head=HEAD)
    assert row["state"] == "DRIFT" and row["differing_files"] == ["config.json"]


def test_unexplained_drift_is_flagged_and_dated_from_the_served_revision(conv, renderer, monkeypatch):
    _, tree, config, raw = _served(conv, renderer, "counsel",
                                   mutate=lambda tree, config: tree.__setitem__("app.py", "0" * 40))
    _observe(conv, monkeypatch, tree, config, raw)
    monkeypatch.setattr(conv, "first_input_change_after", lambda revision, inputs: None)
    monkeypatch.setattr(conv, "commit_time", lambda revision: dt.datetime(2026, 10, 1, tzinfo=dt.timezone.utc))
    row = conv.assess_generated("counsel", renderer, head=HEAD)
    assert row["state"] == "DRIFT" and row["unexplained_drift"] is True
    assert row["drift_since"] == "2026-10-01T00:00:00Z"


def test_runtime_lagging_a_current_hub_tree_is_reported_not_republished(conv, renderer, monkeypatch):
    _, tree, config, raw = _served(conv, renderer, "sentra")
    _observe(conv, monkeypatch, tree, config, raw,
             live={"source_revision": "c" * 40, "artifact_set_sha256": "d" * 64})
    row = conv.assess_generated("sentra", renderer, head=HEAD)
    assert row["state"] == "RUNTIME_DRIFT" and row["publish"] is False


def test_unobservable_space_is_never_reported_converged(conv, renderer, monkeypatch):
    def down(slug):
        raise conv.Unavailable("HTTP 429")
    monkeypatch.setattr(conv, "hub_tree", down)
    row = conv.assess_generated("terra", renderer, head=HEAD)
    assert row["state"] == "UNOBSERVABLE" and row["publish"] is False


def _down(conv):
    def build_info(slug):
        raise conv.Unavailable("HTTP 503: build-info")
    return build_info


@pytest.mark.parametrize("stage", ["RUNTIME_ERROR", "RUNNING", None])
def test_current_hub_tree_with_a_down_runtime_is_never_converged(conv, renderer, monkeypatch, stage):
    """A crashed or unreachable Space is not converged: it alerts, keeps the
    tracker open, and is not republished into the same failure."""
    _, tree, config, raw = _served(conv, renderer, "terra")
    _observe(conv, monkeypatch, tree, config, raw, live=_down(conv), stage=stage)
    row = conv.assess_generated("terra", renderer, head=HEAD)
    assert row["state"] == "RUNTIME_UNAVAILABLE" and row["publish"] is False
    assert row["runtime"]["state"] == "UNOBSERVABLE"
    result = conv.report([row], head=HEAD, threshold_hours=6, now=NOW)
    assert result["converged"] is False and result["alerting"] == ["terra"]
    issues = _Issues([_tracker(conv)])
    assert conv.sync_issue(result, "szl-holdings/a11oy", read=issues.read,
                           write=issues.write)["action"] == "updated"
    assert all(payload.get("state") != "closed" for _, _, payload in issues.writes)


@pytest.mark.parametrize("stage", ["BUILD_ERROR", "RUNTIME_ERROR", "PAUSED", "STOPPED"])
def test_space_stage_other_than_running_is_runtime_unavailable(conv, renderer, monkeypatch, stage):
    _, tree, config, raw = _served(conv, renderer, "counsel")
    _observe(conv, monkeypatch, tree, config, raw, stage=stage)
    row = conv.assess_generated("counsel", renderer, head=HEAD)
    assert row["state"] == "RUNTIME_UNAVAILABLE" and stage in row["reason"]
    assert row["drift_since"] is None  # undatable: alerts at once


def test_a_build_in_progress_is_dated_from_the_last_commit(conv, renderer, monkeypatch):
    _, tree, config, raw = _served(conv, renderer, "terra")
    _observe(conv, monkeypatch, tree, config, raw, live=_down(conv), stage="BUILDING",
             last_modified="2026-10-13T11:00:00Z")
    row = conv.assess_generated("terra", renderer, head=HEAD)
    assert row["state"] == "RUNTIME_UNAVAILABLE" and row["drift_since"] == "2026-10-13T11:00:00Z"
    assert conv.report([row], head=HEAD, threshold_hours=6, now=NOW)["alerting"] == []


def test_a_sleeping_space_is_not_converged_and_does_not_alert(conv, renderer, monkeypatch):
    _, tree, config, raw = _served(conv, renderer, "terra")
    _observe(conv, monkeypatch, tree, config, raw, live=_down(conv), stage="SLEEPING")
    row = conv.assess_generated("terra", renderer, head=HEAD)
    assert row["state"] == "RUNTIME_SLEEPING"
    result = conv.report([row], head=HEAD, threshold_hours=6, now=NOW)
    assert result["converged"] is False and result["alerting"] == [] and result["unobservable"] == ["terra"]


@pytest.mark.parametrize("identity", [
    {"source_revision": None, "workflow_run_id": 11},
    {"source_revision": "0" * 40, "workflow_run_id": 11},
    {"source_revision": "not-a-revision", "workflow_run_id": 11},
    {"source_revision": SERVED, "workflow_run_id": 0},
    {"source_revision": SERVED, "workflow_run_id": True},
    {"source_revision": SERVED, "workflow_run_id": "11"},
])
def test_invalid_served_identity_is_drift_not_its_own_expectation(conv, renderer, monkeypatch, identity):
    _, tree, config, raw = _served(conv, renderer, "counsel",
                                   mutate=lambda tree, config: config.update(identity))
    _observe(conv, monkeypatch, tree, config, raw,
             live={"source_revision": identity["source_revision"],
                   "artifact_set_sha256": config["artifact_set_sha256"]})
    row = conv.assess_generated("counsel", renderer, head=HEAD)
    assert row["state"] == "DRIFT" and row["publish"] is True
    assert row["differing_files"] == ["config.json"] and row["served_identity_valid"] is False
    assert "identity" in row["reason"]


def test_stale_finance_projection_manifest_is_drift(conv, renderer, monkeypatch):
    """The manifest is uploaded last; a failed manifest upload must be retried."""
    for broken in ("0" * 40, None):
        def mutate(tree, config, broken=broken):
            if broken is None:
                tree.pop(conv.FINANCE_MANIFEST)
            else:
                tree[conv.FINANCE_MANIFEST] = broken
        _, tree, config, raw = _served(conv, renderer, "finance", mutate=mutate)
        _observe(conv, monkeypatch, tree, config, raw)
        row = conv.assess_generated("finance", renderer, head=HEAD)
        assert row["state"] == "DRIFT" and row["publish"] is True
        assert row["differing_files"] == [conv.FINANCE_MANIFEST]


def test_finance_manifest_binds_the_served_identity(conv, renderer):
    first = conv.expected_finance_manifest_blob(renderer, {"source_revision": SERVED, "workflow_run_id": 11})
    other_run = conv.expected_finance_manifest_blob(renderer, {"source_revision": SERVED, "workflow_run_id": 12})
    other_revision = conv.expected_finance_manifest_blob(renderer, {"source_revision": HEAD, "workflow_run_id": 11})
    assert len({first, other_run, other_revision}) == 3


def test_finance_binds_the_canonical_a11oy_revision(conv, renderer, monkeypatch):
    monkeypatch.setattr(conv, "finance_binds_canonical_revision", lambda renderer: True)
    _, tree, config, raw = _served(conv, renderer, "finance", revision=SERVED)
    _observe(conv, monkeypatch, tree, config, raw)
    converged = conv.assess_generated("finance", renderer, head=HEAD, a11oy_revision=lambda: SERVED)
    assert converged["state"] == "CONVERGED"
    # The canonical Space moved to main: Finance must republish to bind it.
    moved = conv.assess_generated("finance", renderer, head=HEAD, a11oy_revision=lambda: HEAD)
    assert moved["state"] == "DRIFT" and moved["publish"] is True
    # The canonical Space serves neither: publishing main cannot converge it.
    blocked = conv.assess_generated("finance", renderer, head=HEAD, a11oy_revision=lambda: "c" * 40)
    assert blocked["state"] == "BLOCKED" and blocked["publish"] is False
    assert "canonical A11oy Space serves" in blocked["reason"]


def test_finance_file_drift_publishes_only_while_a11oy_serves_main(conv, renderer, monkeypatch):
    monkeypatch.setattr(conv, "finance_binds_canonical_revision", lambda renderer: True)
    _, tree, config, raw = _served(conv, renderer, "finance",
                                   mutate=lambda tree, config: tree.__setitem__("app.py", "0" * 40))
    _observe(conv, monkeypatch, tree, config, raw)
    assert conv.assess_generated("finance", renderer, head=HEAD, a11oy_revision=lambda: HEAD)["publish"] is True
    assert conv.assess_generated("finance", renderer, head=HEAD,
                                 a11oy_revision=lambda: SERVED)["state"] == "BLOCKED"


def test_finance_coupling_is_detected_from_the_emitted_projection(conv, renderer):
    # Today's projection refuses any other canonical revision.
    assert conv.finance_binds_canonical_revision(renderer) is (
        "CANONICAL_REVISION_MISMATCH" in renderer.APP)
    assert conv.finance_binds_canonical_revision(SimpleNamespace(APP="contract-versioned")) is False


def test_contract_versioned_finance_is_planned_like_any_generated_target(conv, renderer, monkeypatch):
    monkeypatch.setattr(conv, "finance_binds_canonical_revision", lambda renderer: False)
    never = lambda: pytest.fail("an uncoupled projection never reads the canonical revision")
    _, tree, config, raw = _served(conv, renderer, "finance")
    _observe(conv, monkeypatch, tree, config, raw)
    assert conv.assess_generated("finance", renderer, head=HEAD, a11oy_revision=never)["state"] == "CONVERGED"
    _, tree, config, raw = _served(conv, renderer, "finance",
                                   mutate=lambda tree, config: tree.__setitem__("app.py", "0" * 40))
    _observe(conv, monkeypatch, tree, config, raw)
    row = conv.assess_generated("finance", renderer, head=HEAD, a11oy_revision=never)
    assert row["state"] == "DRIFT" and row["publish"] is True and row["canonical_revision_bound"] is False


# ---------------------------------------------------------------------- lyte


def _lyte(conv, monkeypatch, served, tip, *, durability="DURABLE_VOLUME", stage="RUNNING", live=True):
    def build_info(slug):
        if not live:
            raise conv.Unavailable("HTTP 503: lyte build-info")
        return {"source_revision": served, "runtime_source_revision": served,
                "persistence": {"backend": "sqlite", "state": "READY", "durability": durability}}
    monkeypatch.setattr(conv, "live_build_info", build_info)
    monkeypatch.setattr(conv, "space_info", lambda slug: {"sha": "f" * 40, "stage": stage,
                                                          "last_modified": "2026-10-13T00:00:00Z"})
    monkeypatch.setattr(conv, "_lyte_drift_since", lambda served, tip: dt.datetime(
        2026, 10, 10, tzinfo=dt.timezone.utc))
    return lambda: {"sha": tip}


def test_lyte_converges_on_the_lyte_services_tip(conv, monkeypatch):
    tip = _lyte(conv, monkeypatch, SERVED, SERVED)
    row = conv.assess_lyte(resolve=lambda: pytest.fail("qualification not needed"), source_tip=tip)
    assert row["state"] == "CONVERGED" and row["publish"] is False


def test_lyte_drift_publishes_only_a_qualified_tip(conv, monkeypatch):
    tip = _lyte(conv, monkeypatch, SERVED, HEAD)
    row = conv.assess_lyte(resolve=lambda: (HEAD, {}), source_tip=tip)
    assert row["state"] == "DRIFT" and row["publish"] is True
    assert row["drift_since"] == "2026-10-10T00:00:00Z"

    def refuse():
        raise RuntimeError("Lyte source gates did not pass: tests")
    blocked = conv.assess_lyte(resolve=refuse, source_tip=tip)
    assert blocked["state"] == "BLOCKED" and blocked["publish"] is False
    assert "not qualified" in blocked["reason"]


@pytest.mark.parametrize("durability", ["FILE_OR_PROCESS_SCOPED", None])
def test_lyte_is_explicitly_unplanned_while_persistence_is_not_durable(conv, monkeypatch, durability):
    """The release restarts the Space; a restart drops process-scoped ingest.

    The exclusion is an explicit state with its reason and the qualified
    revision it was evaluated against, never an omission, and it alerts at
    once: no automatic run will converge it."""
    tip = _lyte(conv, monkeypatch, SERVED, HEAD, durability=durability)
    row = conv.assess_lyte(resolve=lambda: (HEAD, {}), source_tip=tip)
    assert row["state"] == "UNPLANNED" and row["publish"] is False
    assert row["automatic_writer"] == "EXCLUDED" and row["unplanned_reason"] == "NON_DURABLE_PERSISTENCE"
    assert "automatic writer excludes Lyte" in row["reason"] and "scope lyte" in row["operator_action"]
    assert row["expected_revision"] == HEAD and row["source_tip"] == HEAD
    assert conv.report([row], head=HEAD, threshold_hours=6, now=NOW)["alerting"] == ["lyte"]
    # A drift that began minutes ago alerts too: waiting changes nothing.
    monkeypatch.setattr(conv, "_lyte_drift_since", lambda served, tip: NOW - dt.timedelta(minutes=5))
    fresh = conv.assess_lyte(resolve=lambda: (HEAD, {}), source_tip=tip)
    result = conv.report([fresh], head=HEAD, threshold_hours=6, now=NOW)
    assert result["alerting"] == ["lyte"] and result["targets"][0]["drift_age_hours"] < 1
    title, body = conv.render_issue(result, run_url=None)
    assert "lyte needs an operator publish" in title and "UNPLANNED" in body


def test_lyte_is_evaluated_against_the_current_lyte_services_main(conv, monkeypatch):
    """No pinned revision: every assessment reads the head and qualifies it."""
    for current in (HEAD, "c" * 40):
        tip = _lyte(conv, monkeypatch, SERVED, current)
        qualified = []
        row = conv.assess_lyte(resolve=lambda current=current: qualified.append(current) or (current, {}),
                               source_tip=tip)
        assert qualified == [current]
        assert row["source_tip"] == row["expected_revision"] == current
        assert row["state"] == "DRIFT" and row["publish"] is True


@pytest.mark.parametrize("stage", ["RUNTIME_ERROR", "BUILD_ERROR", None])
def test_a_down_lyte_alerts_and_is_never_reported_converged(conv, monkeypatch, stage):
    tip = _lyte(conv, monkeypatch, SERVED, SERVED, stage=stage, live=False)
    row = conv.assess_lyte(resolve=lambda: pytest.fail("a down Lyte is not republished"), source_tip=tip)
    assert row["state"] == "RUNTIME_UNAVAILABLE" and row["publish"] is False
    result = conv.report([row], head=HEAD, threshold_hours=6, now=NOW)
    assert result["converged"] is False and result["alerting"] == ["lyte"]


def test_lyte_serving_the_tip_in_an_error_stage_is_not_converged(conv, monkeypatch):
    tip = _lyte(conv, monkeypatch, SERVED, SERVED, stage="RUNTIME_ERROR")
    row = conv.assess_lyte(resolve=lambda: pytest.fail("not republished"), source_tip=tip)
    assert row["state"] == "RUNTIME_UNAVAILABLE"


# ---------------------------------------------------------------------- plan


def test_plan_targeted_dispatch_is_a_forced_single_target(conv):
    result = conv.plan(event="workflow_dispatch", scope="terra", head=HEAD, main_tip=HEAD,
                       assess_fn=lambda *a, **k: pytest.fail("a targeted repair is not convergence-gated"))
    assert result["mode"] == "TARGETED_REPAIR"
    assert result["matrix"] == [{"target": "terra", "forced": True}]


def test_plan_estate_dispatch_uses_the_estate_job(conv):
    result = conv.plan(event="workflow_dispatch", scope="estate", head=HEAD, main_tip=HEAD,
                       assess_fn=lambda *a, **k: pytest.fail("estate is not convergence-gated"))
    assert result["mode"] == "ESTATE_DISPATCH" and result["matrix"] == []


def test_plan_publishes_only_drifted_targets(conv):
    def assess(targets, *, head):
        assert targets == conv.TARGETS and head == HEAD
        return [{"target": t, "publish": t in ("terra", "lyte"), "state": "X"} for t in targets]
    result = conv.plan(event="push", scope="", head=HEAD, main_tip=HEAD, assess_fn=assess)
    assert result["matrix"] == [{"target": "terra", "forced": False}, {"target": "lyte", "forced": False}]


def test_plan_converged_estate_is_a_no_op(conv):
    result = conv.plan(event="schedule", scope="", head=HEAD, main_tip=HEAD,
                       assess_fn=lambda targets, head: [{"target": t, "publish": False} for t in targets])
    assert result["matrix"] == []


def test_plan_superseded_head_publishes_nothing(conv):
    result = conv.plan(event="push", scope="", head=HEAD, main_tip=SERVED,
                       assess_fn=lambda *a, **k: pytest.fail("a superseded head is never assessed"))
    assert result["superseded_by"] == SERVED and result["matrix"] == []
    assert {row["state"] for row in result["targets"]} == {"SUPERSEDED"}
    assert all(row["assessed"] is False and SERVED in row["reason"] for row in result["targets"])


def test_plan_after_canonical_deploy_assesses_the_full_estate(conv):
    """A finance-only re-plan left Lyte and the others out of that receipt."""
    seen = []

    def assess(targets, *, head):
        seen.append(targets)
        return [{"target": t, "publish": False, "state": "CONVERGED"} for t in targets]
    conv.plan(event="workflow_run", scope="", head=HEAD, main_tip=HEAD, assess_fn=assess)
    assert seen == [conv.TARGETS]


def _declared_vertical_estate() -> set[str]:
    """The estate as the publishers and the dispatch input declare it."""
    spec = importlib.util.spec_from_file_location(
        "vertical_entrypoint_estate", ROOT / "scripts/hf_publish_vertical_flagships_v4.py")
    entrypoint = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entrypoint)
    declared = set(entrypoint.PUBLIC_FLAGSHIP_SLUGS)
    assert declared == set(entrypoint.GENERATED_FLAGSHIP_SLUGS) | set(entrypoint.SOURCE_OWNED_FLAGSHIP_SLUGS)
    options = _on(_load_workflow(PUBLISH_WORKFLOW))["workflow_dispatch"]["inputs"]["scope"]["options"]
    assert set(options) - {"estate"} == declared
    return declared


AUTOMATIC_EVENTS = ("push", "schedule", "workflow_run")


@pytest.mark.parametrize("event", AUTOMATIC_EVENTS)
def test_automatic_plan_target_set_is_the_full_declared_vertical_estate(conv, monkeypatch, renderer, event):
    """Every automatic plan receipt carries every declared target, Lyte included,
    with a state and, unless converged, a reason. This runs the real assess()
    with only the network reads replaced."""
    declared = _declared_vertical_estate()
    assert set(conv.TARGETS) == declared and len(conv.TARGETS) == len(declared)
    assert set(conv.GENERATED_TARGETS) | {"lyte"} == declared
    monkeypatch.setattr(conv, "load_renderer", lambda: renderer)
    monkeypatch.setattr(conv, "assess_generated", lambda slug, renderer, head: conv._row(
        slug, state="CONVERGED"))
    tip = _lyte(conv, monkeypatch, SERVED, HEAD, durability="FILE_OR_PROCESS_SCOPED")
    monkeypatch.setattr(conv, "github_json", lambda path: tip())
    monkeypatch.setattr(conv, "lyte_expected_revision", lambda: (HEAD, {}))
    result = conv.plan(event=event, scope="", head=HEAD, main_tip=HEAD, dispatched_writers=lambda: [])
    assert result["declared_targets"] == list(conv.TARGETS)
    assert [row["target"] for row in result["targets"]] == list(conv.TARGETS)
    lyte = next(row for row in result["targets"] if row["target"] == "lyte")
    assert lyte["state"] == "UNPLANNED" and lyte["reason"] and lyte["expected_revision"] == HEAD
    assert result["matrix"] == []


def test_every_plan_receipt_records_every_declared_target(conv):
    declared = list(conv.TARGETS)
    full = lambda targets, head: [{"target": t, "publish": False, "state": "CONVERGED"} for t in targets]
    plans = [
        conv.plan(event="schedule", scope="", head=HEAD, main_tip=SERVED, assess_fn=full),
        conv.plan(event="schedule", scope="", head=HEAD, main_tip=HEAD, assess_fn=full,
                  dispatched_writers=lambda: [{"workflow": "hf-sync.yml", "run_id": 5, "status": "queued"}]),
        conv.plan(event="workflow_dispatch", scope="lyte", head=HEAD, main_tip=HEAD),
        conv.plan(event="workflow_dispatch", scope="estate", head=HEAD, main_tip=HEAD),
        *(conv.plan(event=event, scope="", head=HEAD, main_tip=HEAD, assess_fn=full)
          for event in AUTOMATIC_EVENTS),
    ]
    for result in plans:
        assert [row["target"] for row in result["targets"]] == declared, result["mode"]
        assert all(row["state"] for row in result["targets"])
        unassessed = [row for row in result["targets"] if row.get("assessed") is False]
        assert all(row["reason"] for row in unassessed)
    deferred = plans[1]["targets"]
    assert {row["state"] for row in deferred} == {"DEFERRED"} and "hf-sync.yml 5" in deferred[0]["reason"]
    repair = {row["target"]: row["state"] for row in plans[2]["targets"]}
    assert repair == {"terra": "OUT_OF_SCOPE", "counsel": "OUT_OF_SCOPE", "finance": "OUT_OF_SCOPE",
                      "lyte": "FORCED", "sentra": "OUT_OF_SCOPE"}
    assert {row["state"] for row in plans[3]["targets"]} == {"FORCED"}


@pytest.mark.parametrize("rows", [
    lambda targets: [{"target": t, "publish": False} for t in targets if t != "lyte"],
    lambda targets: [{"target": t, "publish": False} for t in (*targets, "lyte")],
    lambda targets: [{"target": t, "publish": False} for t in reversed(targets)],
])
def test_a_plan_that_does_not_cover_the_estate_fails(conv, rows):
    with pytest.raises(RuntimeError, match="declared vertical estate"):
        conv.plan(event="schedule", scope="", head=HEAD, main_tip=HEAD,
                  assess_fn=lambda targets, head: rows(targets))


def test_automatic_plan_defers_to_an_active_dispatched_writer(conv):
    """In the shared writer group a newly queued job cancels the pending one, so
    an automatic run never queues behind a dispatched repair or hf-sync run."""
    active = [{"workflow": "hf-sync.yml", "run_id": 5, "status": "queued"}]
    result = conv.plan(event="schedule", scope="", head=HEAD, main_tip=HEAD,
                       assess_fn=lambda *a, **k: pytest.fail("a deferred plan publishes nothing"),
                       dispatched_writers=lambda: active)
    assert result["deferred_to"] == active and result["matrix"] == []
    # Dispatches never defer, and the in-lock re-plan does not check.
    forced = conv.plan(event="workflow_dispatch", scope="lyte", head=HEAD, main_tip=HEAD,
                       dispatched_writers=lambda: pytest.fail("a dispatch is the writer"))
    assert forced["matrix"] == [{"target": "lyte", "forced": True}]
    idle = conv.plan(event="push", scope="", head=HEAD, main_tip=HEAD, dispatched_writers=lambda: [],
                     assess_fn=lambda targets, head: [{"target": t, "publish": t == "terra"}
                                                      for t in targets])
    assert idle["matrix"] == [{"target": "terra", "forced": False}]


def test_active_dispatched_writers_lists_unfinished_runs_except_its_own(conv):
    reads = []

    def read(path):
        reads.append(path)
        if "hf-sync.yml" in path:
            return {"workflow_runs": [{"id": 1, "status": "completed"}, {"id": 2, "status": "in_progress"}]}
        return {"workflow_runs": [{"id": 77, "status": "in_progress"}, {"id": 3, "status": "waiting"}]}

    active = conv.active_dispatched_writers(own_run_id="77", read=read)
    assert active == [{"workflow": "hf-publish-vertical-flagships.yml", "run_id": 3, "status": "waiting"},
                      {"workflow": "hf-sync.yml", "run_id": 2, "status": "in_progress"}]
    assert all("event=workflow_dispatch" in path for path in reads)
    with pytest.raises(conv.Unavailable):
        conv.active_dispatched_writers(read=lambda path: {"message": "rate limited"})


def test_plan_target_lines_are_validated(conv):
    plan = {"matrix": [{"target": "terra", "forced": False}, {"target": "sentra", "forced": True}]}
    assert conv.plan_target_lines(plan) == ["terra false", "sentra true"]
    for bad in ({"target": "a11oy", "forced": False}, {"target": "terra", "forced": "yes"}):
        with pytest.raises(ValueError):
            conv.plan_target_lines({"matrix": [bad]})


# -------------------------------------------------------------------- sentra


def test_sentra_wait_polls_pending_checks_until_admissible(conv, monkeypatch):
    class Base(Exception):
        pass

    class Superseded(Base):
        pass

    class Pending(Base):
        pass

    outcomes = iter([Pending("unresolved"), Pending("unresolved"), HEAD])

    def admission():
        value = next(outcomes)
        if isinstance(value, Exception):
            raise value
        return value

    fake = SimpleNamespace(SentraPublicationError=Base, SentraSourceSuperseded=Superseded,
                           SentraChecksPending=Pending, _sentra_source_admission=admission)
    monkeypatch.setattr(conv, "_load", lambda name, path: fake)
    sleeps = []
    clock = iter(range(0, 1000, 10))
    outcome = conv.wait_for_sentra_admission(600, sleep=sleeps.append, clock=lambda: next(clock))
    assert outcome == {"state": "ADMISSIBLE", "revision": HEAD}
    assert len(sleeps) == 2

    fake._sentra_source_admission = lambda: (_ for _ in ()).throw(Superseded("moved"))
    assert conv.wait_for_sentra_admission(600, sleep=sleeps.append)["state"] == "SUPERSEDED"
    fake._sentra_source_admission = lambda: (_ for _ in ()).throw(Base("failed check"))
    assert conv.wait_for_sentra_admission(600, sleep=sleeps.append)["state"] == "BLOCKED"
    fake._sentra_source_admission = lambda: (_ for _ in ()).throw(Pending("unresolved"))
    timeline = iter([0, 0, 700])
    blocked = conv.wait_for_sentra_admission(600, sleep=lambda s: None, clock=lambda: next(timeline))
    assert blocked["state"] == "BLOCKED" and "after waiting" in blocked["reason"]


def _sentra_fake(conv, monkeypatch, outcomes):
    class Base(Exception):
        def __init__(self, message, http_status=None):
            super().__init__(message)
            self.http_status = http_status

    class Superseded(Base):
        pass

    class Pending(Base):
        pass

    sequence = iter(outcomes(Base))

    def admission():
        value = next(sequence)
        if isinstance(value, BaseException):
            raise value
        return value

    fake = SimpleNamespace(SentraPublicationError=Base, SentraSourceSuperseded=Superseded,
                           SentraChecksPending=Pending, _sentra_source_admission=admission)
    monkeypatch.setattr(conv, "_load", lambda name, path: fake)


@pytest.mark.parametrize("transient", [
    lambda Base: Base("GitHub source admission returned an HTTP error", 502),
    lambda Base: Base("GitHub source admission returned an HTTP error", 429),
    lambda Base: Base("GitHub source admission returned an HTTP error", 403),
    lambda Base: OSError("urlopen error timed out"),
    lambda Base: json.JSONDecodeError("Expecting value", "", 0),
])
def test_sentra_wait_retries_transient_github_reads(conv, monkeypatch, transient):
    _sentra_fake(conv, monkeypatch, lambda Base: [transient(Base), transient(Base), HEAD])
    sleeps = []
    clock = iter(range(0, 1000, 10))
    outcome = conv.wait_for_sentra_admission(600, sleep=sleeps.append, clock=lambda: next(clock))
    assert outcome == {"state": "ADMISSIBLE", "revision": HEAD} and len(sleeps) == 2


def test_sentra_wait_blocks_on_policy_errors_and_on_persistent_transients(conv, monkeypatch):
    _sentra_fake(conv, monkeypatch, lambda Base: [Base("Sentra source signature is unverified")])
    assert conv.wait_for_sentra_admission(600, sleep=lambda s: pytest.fail("no retry"))["state"] == "BLOCKED"
    _sentra_fake(conv, monkeypatch, lambda Base: [Base("not found", 404)])
    assert conv.wait_for_sentra_admission(600, sleep=lambda s: pytest.fail("no retry"))["state"] == "BLOCKED"
    _sentra_fake(conv, monkeypatch, lambda Base: [Base("server error", 503)] * 3)
    timeline = iter([0, 0, 700])
    outcome = conv.wait_for_sentra_admission(600, sleep=lambda s: None, clock=lambda: next(timeline))
    assert outcome["state"] == "BLOCKED" and "HTTP 503" in outcome["reason"]


# -------------------------------------------------------------------- report

NOW = dt.datetime(2026, 10, 13, 12, tzinfo=dt.timezone.utc)


def _rows(**states):
    rows = []
    for target, (state, since) in states.items():
        rows.append({"target": target, "state": state, "drift_since": since, "reason": state,
                     "served_revision": SERVED})
    return rows


def test_report_alerts_only_past_the_threshold(conv):
    result = conv.report(_rows(terra=("DRIFT", "2026-10-13T09:00:00Z"),
                               counsel=("DRIFT", "2026-10-12T00:00:00Z"),
                               lyte=("CONVERGED", None)),
                         head=HEAD, threshold_hours=6, now=NOW)
    assert result["alerting"] == ["counsel"]
    assert result["converged"] is False
    ages = {row["target"]: row["drift_age_hours"] for row in result["targets"]}
    assert ages == {"terra": 3.0, "counsel": 36.0, "lyte": None}


def test_report_undatable_drift_alerts_and_unobservable_does_not(conv):
    result = conv.report(_rows(finance=("BLOCKED", None), sentra=("UNOBSERVABLE", None)),
                         head=HEAD, threshold_hours=6, now=NOW)
    assert result["alerting"] == ["finance"]
    assert result["unobservable"] == ["sentra"]


class _Issues:
    def __init__(self, existing=None):
        self.existing = existing or []
        self.writes = []

    def read(self, path):
        assert "creator=github-actions%5Bbot%5D" in path and "state=open" in path
        return self.existing

    def write(self, method, path, payload):
        self.writes.append((method, path, payload))
        return {"number": 99}


def _tracker(conv, number=7):
    return {"number": number, "body": conv.TRACKER_MARKER + "\nold"}


def test_issue_opened_once_when_drift_persists(conv):
    issues = _Issues([{"number": 3, "body": "unrelated"}, {"number": 4, "body": conv.TRACKER_MARKER,
                                                           "pull_request": {}}])
    result = conv.report(_rows(terra=("DRIFT", "2026-10-01T00:00:00Z")), head=HEAD, threshold_hours=6, now=NOW)
    assert conv.sync_issue(result, "szl-holdings/a11oy", read=issues.read, write=issues.write) == {
        "action": "opened", "number": 99}
    method, path, payload = issues.writes[0]
    assert (method, path) == ("POST", "/repos/szl-holdings/a11oy/issues")
    assert conv.TRACKER_MARKER in payload["body"] and "terra" in payload["title"]


def test_issue_updated_not_duplicated(conv):
    issues = _Issues([_tracker(conv)])
    result = conv.report(_rows(terra=("DRIFT", "2026-10-01T00:00:00Z")), head=HEAD, threshold_hours=6, now=NOW)
    assert conv.sync_issue(result, "szl-holdings/a11oy", read=issues.read, write=issues.write)["action"] == "updated"
    assert [(m, p) for m, p, _ in issues.writes] == [("PATCH", "/repos/szl-holdings/a11oy/issues/7")]


def test_issue_closed_when_every_target_converges(conv):
    issues = _Issues([_tracker(conv)])
    result = conv.report(_rows(terra=("CONVERGED", None), lyte=("CONVERGED", None)),
                         head=HEAD, threshold_hours=6, now=NOW)
    assert conv.sync_issue(result, "szl-holdings/a11oy", read=issues.read, write=issues.write)["action"] == "closed"
    assert [(m, p) for m, p, _ in issues.writes] == [
        ("POST", "/repos/szl-holdings/a11oy/issues/7/comments"),
        ("PATCH", "/repos/szl-holdings/a11oy/issues/7")]
    assert issues.writes[1][2]["state"] == "closed"


def test_issue_stays_open_while_drift_remains_below_threshold(conv):
    issues = _Issues([_tracker(conv)])
    result = conv.report(_rows(terra=("DRIFT", "2026-10-13T11:00:00Z")), head=HEAD, threshold_hours=6, now=NOW)
    assert conv.sync_issue(result, "szl-holdings/a11oy", read=issues.read, write=issues.write)["action"] == "updated"
    assert all(payload.get("state") != "closed" for _, _, payload in issues.writes)


def test_no_issue_when_nothing_alerts_and_none_is_open(conv):
    issues = _Issues()
    result = conv.report(_rows(terra=("DRIFT", "2026-10-13T11:00:00Z")), head=HEAD, threshold_hours=6, now=NOW)
    assert conv.sync_issue(result, "szl-holdings/a11oy", read=issues.read, write=issues.write) == {"action": "none"}
    assert issues.writes == []


def test_git_blob_id_matches_git(conv, tmp_path):
    content = b"vertical publication\n"
    path = tmp_path / "blob"
    path.write_bytes(content)
    observed = subprocess.run(["git", "hash-object", str(path)], capture_output=True, text=True,
                              check=True).stdout.strip()
    assert conv.git_blob_id(content) == observed == hashlib.sha1(b"blob 21\0" + content).hexdigest()
