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


def test_publisher_job_graph_and_conditions_are_consistent():
    _assert_references_resolve(PUBLISH_WORKFLOW)
    _assert_references_resolve(DRIFT_WORKFLOW)
    workflow = _load_workflow(PUBLISH_WORKFLOW)
    jobs = workflow["jobs"]
    assert set(jobs) == {"plan", "publish-target", "publish"}
    assert set(jobs["plan"]["outputs"]) == {"matrix", "publish", "estate"}
    target = jobs["publish-target"]
    assert target["needs"] == "plan"
    assert target["strategy"]["matrix"] == "${{ fromJSON(needs.plan.outputs.matrix) }}"
    assert target["strategy"]["fail-fast"] is False
    assert target["concurrency"] == {"group": "hf-vertical-target-${{ matrix.target }}",
                                     "cancel-in-progress": False}
    assert "needs.plan.outputs.publish == 'true'" in target["if"]
    estate = jobs["publish"]
    assert estate["concurrency"] == {"group": "hf-vertical-estate", "cancel-in-progress": False}
    assert "needs.plan.outputs.estate == 'true'" in estate["if"]
    assert estate["env"]["SZL_FLAGSHIP_SCOPE"] == "estate"
    assert target["env"]["SZL_FLAGSHIP_SCOPE"] == "${{ matrix.target }}"
    # Planning is read-only; only writer jobs hold (per-Space or estate) groups.
    assert "concurrency" not in workflow and "concurrency" not in jobs["plan"]


def test_publish_steps_keep_exact_main_live_verification_and_neutral_supersession():
    text = PUBLISH_WORKFLOW.read_text(encoding="utf-8")
    target = _job_text(text, "publish-target")
    assert 'test "$GITHUB_REF" = refs/heads/main' in target
    assert 'if [ "$(git rev-parse HEAD)" = "$(git rev-parse FETCH_HEAD)" ]; then' in target
    assert "python scripts/hf_publish_vertical_flagships_v4.py" in target
    assert 'if [ "$code" -eq 75 ]; then' in target and 'exit "$code"' in target
    assert "hf_vertical_convergence.py check --target" in target
    assert "!matrix.forced" in target
    assert "wait-sentra" in target and "steps.sentra.outputs.state == 'ADMISSIBLE'" in target
    assert "steps.sentra.outputs.state == 'BLOCKED'" in target
    estate = _job_text(text, "publish")
    assert 'test "$(git rev-parse HEAD)" = "$(git rev-parse FETCH_HEAD)"' in estate
    for job in (target, estate, _job_text(text, "plan")):
        assert "persist-credentials: false" in job
        assert "ref: ${{ github.sha }}" in job


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
    config = json.loads(conv.expected_config_bytes(expected["config"],
                                                   {"source_revision": revision, "workflow_run_id": run_id}))
    if mutate:
        mutate(tree, config)
    raw = (json.dumps(config, indent=2, sort_keys=True) + "\n").encode()
    return expected, tree, config, raw


def _observe(conv, monkeypatch, tree, config, raw, *, live=None, last_modified="2026-10-13T00:00:00Z"):
    monkeypatch.setattr(conv, "hub_tree", lambda slug: dict(tree))
    monkeypatch.setattr(conv, "hub_config", lambda slug: (dict(config), raw))
    monkeypatch.setattr(conv, "space_info", lambda slug: {"sha": "f" * 40, "stage": "RUNNING",
                                                          "last_modified": last_modified})
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


def _lyte(conv, monkeypatch, served, tip):
    monkeypatch.setattr(conv, "live_build_info", lambda slug: {
        "source_revision": served, "runtime_source_revision": served})
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


def test_plan_after_canonical_deploy_assesses_finance_only(conv):
    seen = []
    conv.plan(event="workflow_run", scope="", head=HEAD, main_tip=HEAD,
              assess_fn=lambda targets, head: seen.append(targets) or [])
    assert seen == [("finance",)]


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
