"""Execute the real CLI and workflow run blocks with a recording, offline gh.

The tests never contact GitHub/HF, dispatch production, or need credentials.
They prove source-bound plan admission and the child-completion integration,
not live publication/readiness. Every test uses its own checkout and journals.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import unittest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "scripts" / "estate_repair_dispatch.py"
SPEC = importlib.util.spec_from_file_location("estate_plan_authority", MODULE)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load the exact repository dispatcher")
dispatch = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dispatch)
ESTATE = ROOT / ".github/workflows/estate-release-train.yml"
HF_SYNC = ROOT / ".github/workflows/hf-sync.yml"
SHA = "a" * 40
OTHER = "b" * 40
PLAN = {"complete": True, "approved": True, "expected_source_revision": SHA}
CALLER = "Dispatch only the established canonical writers"
GATE = "Require the approved plan for the actual vertical source"


def step(path: Path, name: str) -> str:
    """Read this workflow's literal named step, without evaluating expressions."""
    marker = "      - name: " + name + "\n"
    text = path.read_text(encoding="utf-8")
    if text.count(marker) != 1:
        raise ValueError("expected one exact named workflow step")
    return text.split(marker, 1)[1].split("\n      - name: ", 1)[0]


def run_block(path: Path, name: str) -> str:
    body = step(path, name).split("        run: |\n", 1)[1]
    return textwrap.dedent(body).rstrip() + "\n"


class SourcePlanTests(unittest.TestCase):
    def decision(self, plan: object) -> dict:
        return dispatch.plan_repair_dispatch(
            repair=True, vertical_requested=True, current_sha=SHA,
            expected_sha=SHA, plan=plan,
        )

    def test_missing_plan_denies_vertical(self) -> None:
        self.assertIs(self.decision(None)["vertical_flagships"], False)

    def test_stale_plan_denies_vertical(self) -> None:
        self.assertIs(self.decision({**PLAN, "expected_source_revision": OTHER})["vertical_flagships"], False)

    def test_plan_revision_is_required_and_hex(self) -> None:
        for revision in (None, "", "g" * 40, SHA + "\n", 1, "A" * 40):
            with self.subTest(revision=revision):
                self.assertIs(self.decision({**PLAN, "expected_source_revision": revision})["vertical_flagships"], False)
        self.assertIs(self.decision({"complete": True, "approved": True})["vertical_flagships"], False)

    def test_approval_and_completeness_are_boolean(self) -> None:
        for field in ("approved", "complete"):
            for value in (False, 1, "true", None):
                with self.subTest(field=field, value=value):
                    self.assertIs(self.decision({**PLAN, field: value})["vertical_flagships"], False)

    def test_missing_or_invalid_observed_source_denies_all_writers(self) -> None:
        for revision in (None, "", "g" * 40, SHA + "\n"):
            result = dispatch.plan_repair_dispatch(
                repair=True, vertical_requested=True, expected_sha=revision,
                current_sha=revision, plan=PLAN,
            )
            self.assertIs(result["dispatch"], False)
            self.assertIsNone(dispatch.hf_sync_command(result, repo="szl-holdings/a11oy"))

    def test_malformed_duplicate_and_nonfinite_json_denied(self) -> None:
        for value in ("", "{", "[]", "null", '{"approved":false,"approved":true}',
                      '{"approved":NaN}', '{"approved":Infinity}', "[" * 2000,
                      " " * (dispatch.MAX_PLAN_BYTES + 1)):
            with self.subTest(sample=value[:40]):
                self.assertIsNone(dispatch.parse_plan(value))

    def test_unreadable_malformed_and_oversized_plan_files_denied(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.assertIsNone(dispatch.load_plan(root / "absent.json"))
            self.assertIsNone(dispatch.load_plan(root))
            plan = root / "plan.json"
            for data in (b"{", b"\xff", b" " * (dispatch.MAX_PLAN_BYTES + 1)):
                plan.write_bytes(data)
                self.assertIsNone(dispatch.load_plan(plan))

    def test_admitted_command_only_carries_public_source_contract(self) -> None:
        result = self.decision({**PLAN, "note": "do-not-forward-this"})
        command = dispatch.hf_sync_command(result, repo="szl-holdings/a11oy")
        self.assertIn("publish_vertical_flagships=true", command)
        serialized = next(arg.split("=", 1)[1] for arg in command if arg.startswith("vertical_plan_json="))
        self.assertEqual(json.loads(serialized), PLAN)
        self.assertNotIn("do-not-forward-this", json.dumps(result))
        self.assertIs(result["production_authorization"], False)

    def test_vertical_command_cannot_omit_admitted_plan(self) -> None:
        with self.assertRaises(ValueError):
            dispatch.hf_sync_command({"dispatch": True, "vertical_flagships": True}, repo="szl-holdings/a11oy")

    def test_cli_file_input_and_github_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            plan = Path(directory) / "plan.json"
            output = Path(directory) / "out"
            plan.write_text(json.dumps(PLAN), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(MODULE), "--repair", "true", "--vertical-requested", "true",
                 "--expected-sha", SHA, "--current-sha", SHA, "--plan", str(plan),
                 "--require-vertical", "--github-output", str(output)],
                capture_output=True, text=True, timeout=10, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIs(json.loads(result.stdout)["vertical_flagships"], True)
            self.assertIn("vertical_flagships=true\n", output.read_text())

    def test_cli_missing_file_is_not_authority(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(MODULE), "--repair", "true", "--vertical-requested", "true",
                 "--expected-sha", SHA, "--current-sha", SHA,
                 "--plan", str(Path(directory) / "absent.json"), "--require-vertical"],
                capture_output=True, text=True, timeout=10, check=False,
            )
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)["vertical_state"], "NOT_REQUESTED")


# A protocol fixture, not a stand-in for the native dispatcher/barrier. Unknown
# commands fail; every command is logged; no network or credentials are available.
FAKE_GH = r'''
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
with Path(os.environ["GH_LOG"]).open("a") as stream:
    stream.write(json.dumps(args) + "\n")
repo = "szl-holdings/a11oy"
repo_id = 1225834126
source = os.environ["FAKE_CURRENT_SHA"]
workflows = {1001: "hf-sync.yml", 1002: "repair-cloudflare-product-edge.yml"}
vertical_job = "Publish and live-verify six domain-native flagship Spaces"
vertical_gate = "Enforce complete explicitly requested vertical publication"

if args == ["api", f"repos/{repo}/git/ref/heads/main", "--jq", ".object.sha"]:
    print(source)
elif args == ["workflow", "view", workflows[1002], "--repo", repo]:
    print("fixture: existing canonical workflow")
elif args[:2] == ["workflow", "run"]:
    if len(args) < 7 or args[2] not in workflows.values():
        sys.exit(64)
    if args[3:7] != ["--repo", repo, "--ref", "main"]:
        sys.exit(64)
    if args[2] == os.environ.get("FAKE_FAIL_WORKFLOW"):
        sys.exit(7)
    if os.environ.get("FAKE_DISPATCH_NO_URL") != "true":
        run_id = next(key for key, value in workflows.items() if value == args[2])
        print(f"https://github.com/{repo}/actions/runs/{run_id}")
elif args[:5] == ["api", "--hostname", "github.com", "--method", "GET"] and len(args) == 6:
    endpoint = args[5]
    if endpoint == f"repos/{repo}/git/ref/heads/main":
        print(json.dumps({"object": {"sha": source}}))
    else:
        match = next((run_id for run_id in workflows
                      if endpoint in {f"repos/{repo}/actions/runs/{run_id}",
                                      f"repos/{repo}/actions/runs/{run_id}/attempts/1/jobs?per_page=100&page=1"}), None)
        if match is None:
            sys.exit(64)
        identity = {"run_id": match, "head_sha": os.environ.get("FAKE_CHILD_SOURCE", source),
                    "run_attempt": 1, "status": "completed"}
        if endpoint.endswith(f"/runs/{match}"):
            result = {**identity, "id": match, "repository": {"id": repo_id, "full_name": repo},
                      "head_repository": {"id": repo_id, "full_name": repo},
                      "event": "workflow_dispatch", "head_branch": "main",
                      "path": ".github/workflows/" + workflows[match],
                      "conclusion": os.environ.get("FAKE_RUN_CONCLUSION", "success")}
        else:
            names = (["Prove exact live source, runtime, routes, and singleton state",
                      "Probe and ingest exact post-deploy readiness verdict", vertical_job]
                     if match == 1001 else [
                         "Prove bounded routes, reversible DNS cutover, and Worker behavior",
                         "Deploy, cut over exact DNS proxy state, and prove the public edge"])
            jobs = [{**identity, "id": match * 10 + index, "name": name,
                     "conclusion": "success", "steps": []}
                    for index, name in enumerate(names)]
            if match == 1001:
                jobs[-1]["conclusion"] = (
                    os.environ.get("FAKE_JOB_CONCLUSION", "success")
                    if os.environ["VERTICAL_REQUESTED"] == "true" else "skipped")
                jobs[-1]["steps"] = [{"name": vertical_gate, "status": "completed",
                                      "conclusion": os.environ.get("FAKE_GATE_CONCLUSION", "success")}]
            else:
                jobs[-1]["conclusion"] = os.environ.get("FAKE_EDGE_JOB_CONCLUSION", "success")
                jobs[-1]["steps"] = [{"name": "Enforce proved live edge", "status": "completed",
                                      "conclusion": os.environ.get("FAKE_EDGE_GATE_CONCLUSION", "success")}]
            result = {"total_count": len(jobs), "jobs": jobs}
        print(json.dumps(result))
else:
    sys.exit(64)
'''


class ExecutedWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        binary = self.directory / "bin"
        binary.mkdir()
        (binary / "python").symlink_to(sys.executable)
        gh = binary / "gh"
        # The stdlib-only recorder does not need ambient site-startup hooks.
        gh.write_text(f"#!{sys.executable} -S\n" + FAKE_GH, encoding="utf-8")
        gh.chmod(0o700)
        # Run the actual source in an isolated miniature checkout so exclusive
        # journals never pollute the repository or collide across test methods.
        scripts = self.directory / "scripts"
        scripts.mkdir()
        for name in ("estate_repair_dispatch.py", "estate_child_completion.py"):
            shutil.copy2(ROOT / "scripts" / name, scripts / name)
        (self.directory / "reports").mkdir()
        self.env = {
            "PATH": str(binary) + os.pathsep + os.defpath,
            "HOME": str(self.directory), "RUNNER_TEMP": str(self.directory),
            "GITHUB_OUTPUT": str(self.directory / "out"), "GITHUB_SHA": SHA,
            "GITHUB_REPOSITORY": "szl-holdings/a11oy", "GITHUB_RUN_ID": "900",
            "EXPECTED_SHA": SHA, "VERTICAL_REQUESTED": "true", "VERTICAL_PLAN_JSON": "",
            "FAKE_CURRENT_SHA": SHA, "GH_LOG": str(self.directory / "gh.jsonl"),
        }
        if sys.flags.optimize:
            self.env["PYTHONOPTIMIZE"] = str(sys.flags.optimize)

    def execute(self, path: Path, name: str) -> subprocess.CompletedProcess:
        bash = shutil.which("bash")
        if bash is None:
            self.fail("these Ubuntu workflow integration tests require bash")
        command = [bash, "-c", run_block(path, name)]
        # The literal block starts child Python/gh processes. Reap our isolated
        # process group on timeout instead of leaving a fixture waiter running.
        process = subprocess.Popen(command, cwd=self.directory, env=self.env,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                   text=True, start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=15)
        except subprocess.TimeoutExpired:
            if os.name == "posix":
                os.killpg(process.pid, signal.SIGKILL)
            else:
                process.kill()
            process.communicate()
            raise
        return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)

    def calls(self) -> list[list[str]]:
        path = Path(self.env["GH_LOG"])
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def writers(self) -> list[list[str]]:
        return [args for args in self.calls() if args[:2] == ["workflow", "run"]]

    def records(self, child: str) -> list[dict]:
        path = self.directory / "reports" / f"estate-child-{child}.jsonl"
        return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []

    def test_caller_wires_input_as_data_and_preserves_manual_repair_gate(self) -> None:
        block = step(ESTATE, CALLER)
        self.assertIn("VERTICAL_PLAN_JSON: ${{ inputs.vertical_plan_json }}", block)
        self.assertIn("--plan-from-env", run_block(ESTATE, CALLER))
        self.assertNotIn("${{ inputs.", run_block(ESTATE, CALLER))
        for predicate in ("github.event_name == 'workflow_dispatch'", "inputs.repair == true",
                          "steps.initial.outputs.state != 'ALIGNED'",
                          "inputs.publish_vertical_flagships == true"):
            self.assertIn(predicate, block)

    def test_missing_plan_executes_product_only(self) -> None:
        self.env["VERTICAL_REQUESTED"] = "false"
        result = self.execute(ESTATE, CALLER)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([args[2] for args in self.writers()], ["hf-sync.yml", "repair-cloudflare-product-edge.yml"])
        self.assertNotIn("publish_vertical_flagships=true", self.writers()[0])
        for child in ("hf", "edge"):
            self.assertEqual(self.records(child)[-1]["state"], "CHILD_COMPLETION_VERIFIED")

    def test_explicit_vertical_without_plan_fails_before_any_writer(self) -> None:
        result = self.execute(ESTATE, CALLER)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.writers(), [])
        self.assertEqual(self.records("hf"), [])

    def test_approved_plan_reaches_actual_downstream_cli(self) -> None:
        self.env["VERTICAL_PLAN_JSON"] = json.dumps(PLAN)
        result = self.execute(ESTATE, CALLER)
        self.assertEqual(result.returncode, 0, result.stderr)
        args = self.writers()[0]
        self.assertIn("publish_vertical_flagships=true", args)
        for child, run_id in (("hf", 1001), ("edge", 1002)):
            records = self.records(child)
            self.assertEqual([record["state"] for record in records],
                             ["UNKNOWN_AFTER_ATTEMPT", "DISPATCH_BOUND", "CHILD_COMPLETION_VERIFIED"])
            self.assertEqual(records[-1]["run_id"], run_id)
            self.assertEqual(records[-1]["source_revision"], SHA)
        forwarded = next(arg.split("=", 1)[1] for arg in args if arg.startswith("vertical_plan_json="))
        self.env["VERTICAL_PLAN_JSON"] = forwarded
        result = self.execute(HF_SYNC, GATE)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("vertical_flagships=true", Path(self.env["GITHUB_OUTPUT"]).read_text())

    def test_invalid_plans_never_forward_vertical(self) -> None:
        for text in ("{", "[]", json.dumps({**PLAN, "approved": False}),
                     json.dumps({**PLAN, "expected_source_revision": OTHER})):
            with self.subTest(plan=text):
                self.env["VERTICAL_PLAN_JSON"] = text
                result = self.execute(ESTATE, CALLER)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(self.writers(), [])
                self.assertEqual(self.records("hf"), [])

    def test_source_movement_prevents_both_writers(self) -> None:
        self.env["VERTICAL_PLAN_JSON"] = json.dumps(PLAN)
        self.env["FAKE_CURRENT_SHA"] = OTHER
        result = self.execute(ESTATE, CALLER)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.writers(), [])

    def test_invalid_equal_sources_cannot_dispatch_edge_independently(self) -> None:
        self.env["EXPECTED_SHA"] = self.env["FAKE_CURRENT_SHA"] = "not-a-sha"
        result = self.execute(ESTATE, CALLER)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.writers(), [])

    def test_plan_text_is_not_shell_code_or_raw_receipt_content(self) -> None:
        marker = self.directory / "must-not-exist"
        self.env["VERTICAL_PLAN_JSON"] = json.dumps({**PLAN, "note": f'$(touch "{marker}")'})
        result = self.execute(ESTATE, CALLER)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())
        self.assertNotIn("touch", (self.directory / "estate-repair-dispatch.json").read_text())
        self.assertNotIn("touch", json.dumps(self.records("hf")))

    def test_queued_main_movement_is_denied_by_actual_writer_gate(self) -> None:
        self.env["VERTICAL_PLAN_JSON"] = json.dumps(PLAN)
        self.env["GITHUB_SHA"] = OTHER
        result = self.execute(HF_SYNC, GATE)
        self.assertEqual(result.returncode, 2, result.stderr)
        receipt = json.loads((self.directory / "hf-vertical-plan.json").read_text())
        self.assertEqual(receipt["vertical_state"], "NOT_REQUESTED")
        self.assertEqual(self.writers(), [])

    def test_direct_writer_dispatch_without_plan_fails_closed(self) -> None:
        for text in ("", "{", "null"):
            with self.subTest(plan=text):
                self.env["VERTICAL_PLAN_JSON"] = text
                result = self.execute(HF_SYNC, GATE)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(self.writers(), [])

    def test_failed_hf_dispatch_does_not_retry_or_dispatch_edge(self) -> None:
        self.env["VERTICAL_PLAN_JSON"] = json.dumps(PLAN)
        self.env["FAKE_FAIL_WORKFLOW"] = "hf-sync.yml"
        result = self.execute(ESTATE, CALLER)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([args[2] for args in self.writers()], ["hf-sync.yml"])
        self.assertEqual(self.records("hf")[-1]["state"], "UNKNOWN_AFTER_ATTEMPT")

    def test_missing_dispatch_url_stops_without_resend(self) -> None:
        self.env["VERTICAL_PLAN_JSON"] = json.dumps(PLAN)
        self.env["FAKE_DISPATCH_NO_URL"] = "true"
        result = self.execute(ESTATE, CALLER)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([args[2] for args in self.writers()], ["hf-sync.yml"])
        self.assertEqual(self.records("hf")[-1]["state"], "UNKNOWN_AFTER_ATTEMPT")

    def test_green_run_cannot_hide_failed_vertical_job(self) -> None:
        self.env["VERTICAL_PLAN_JSON"] = json.dumps(PLAN)
        self.env["FAKE_JOB_CONCLUSION"] = "failure"
        result = self.execute(ESTATE, CALLER)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.records("hf")[-1]["state"], "HOLD")
        self.assertEqual(self.records("hf")[-1]["run"]["conclusion"], "success")
        self.assertNotIn("CHILD_COMPLETION_VERIFIED", json.dumps(self.records("hf")))

    def test_green_job_cannot_hide_skipped_receipt_gate(self) -> None:
        self.env["VERTICAL_PLAN_JSON"] = json.dumps(PLAN)
        self.env["FAKE_GATE_CONCLUSION"] = "skipped"
        result = self.execute(ESTATE, CALLER)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.records("hf")[-1]["state"], "HOLD")

    def test_wrong_child_source_stays_hold(self) -> None:
        self.env["VERTICAL_PLAN_JSON"] = json.dumps(PLAN)
        self.env["FAKE_CHILD_SOURCE"] = OTHER
        result = self.execute(ESTATE, CALLER)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.records("hf")[-1]["state"], "HOLD")

    def test_repeated_run_block_does_not_dispatch_twice(self) -> None:
        self.env["VERTICAL_PLAN_JSON"] = json.dumps(PLAN)
        first = self.execute(ESTATE, CALLER)
        self.assertEqual(first.returncode, 0, first.stderr)
        before = self.writers()
        second = self.execute(ESTATE, CALLER)
        self.assertNotEqual(second.returncode, 0)
        self.assertEqual(self.writers(), before)

    def test_writer_publication_requires_plan_and_exact_main_outputs(self) -> None:
        gate = step(HF_SYNC, GATE)
        self.assertIn("VERTICAL_PLAN_JSON: ${{ inputs.vertical_plan_json }}", gate)
        self.assertIn("--require-vertical", gate)
        for name in ("Install pinned vertical publisher", "Publish and verify the v4 vertical estate"):
            block = step(HF_SYNC, name)
            self.assertIn("steps.exact_main_owner.outputs.publish == 'true'", block)
            self.assertIn("steps.vertical_plan.outputs.vertical_flagships == 'true'", block)
        for path in (ESTATE, HF_SYNC):
            self.assertIn('        default: ""', path.read_text())
            self.assertIn('        default: false', path.read_text())

    def test_skipped_edge_writer_cannot_finish_product_repair(self) -> None:
        self.env["VERTICAL_REQUESTED"] = "false"
        self.env["FAKE_EDGE_JOB_CONCLUSION"] = "skipped"
        result = self.execute(ESTATE, CALLER)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.writers()), 2)
        for name in ("hf", "edge"):
            self.assertEqual(self.records(name)[-1]["state"], "HOLD")
            self.assertNotIn("CHILD_COMPLETION_VERIFIED", json.dumps(self.records(name)))

    def test_skipped_edge_enforcement_cannot_finish_product_repair(self) -> None:
        self.env["VERTICAL_REQUESTED"] = "false"
        self.env["FAKE_EDGE_GATE_CONCLUSION"] = "skipped"
        result = self.execute(ESTATE, CALLER)
        self.assertNotEqual(result.returncode, 0)
        for name in ("hf", "edge"):
            self.assertNotIn("CHILD_COMPLETION_VERIFIED", json.dumps(self.records(name)))

    def test_failed_edge_dispatch_does_not_certify_the_started_hf_child(self) -> None:
        self.env["VERTICAL_PLAN_JSON"] = json.dumps(PLAN)
        self.env["FAKE_FAIL_WORKFLOW"] = "repair-cloudflare-product-edge.yml"
        result = self.execute(ESTATE, CALLER)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual([args[2] for args in self.writers()], ["hf-sync.yml", "repair-cloudflare-product-edge.yml"])
        self.assertEqual(self.records("edge")[-1]["state"], "UNKNOWN_AFTER_ATTEMPT")
        for name in ("hf", "edge"):
            self.assertNotIn("CHILD_COMPLETION_VERIFIED", json.dumps(self.records(name)))


if __name__ == "__main__":
    unittest.main()
