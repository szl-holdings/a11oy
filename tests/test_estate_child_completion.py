"""Offline regression fixtures; none of these tests publishes or qualifies a runtime."""
from __future__ import annotations
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import estate_child_completion as gate  # noqa: E402

SOURCE = "a" * 40
RUN = 1234


def child(vertical=True, workflow="hf-sync.yml"):
    return {"run_id": RUN, "workflow": workflow, "source_revision": SOURCE,
            "vertical_requested": vertical, "production_authorization": False}


def run():
    return {"id": RUN, "repository": {"id": gate.REPOSITORY_ID, "full_name": gate.REPOSITORY},
            "head_repository": {"id": gate.REPOSITORY_ID}, "head_branch": "main",
            "head_sha": SOURCE, "run_attempt": 1, "event": "workflow_dispatch",
            "path": ".github/workflows/hf-sync.yml", "status": "completed", "conclusion": "success"}


def jobs():
    names = [gate.VERTICAL_JOB, "Prove exact live source, runtime, routes, and singleton state",
             "Probe and ingest exact post-deploy readiness verdict"]
    return [{"id": i+1, "name": name, "run_id": RUN, "head_sha": SOURCE,
             "run_attempt": 1, "status": "completed", "conclusion": "success",
             "steps": [{"name": gate.VERTICAL_GATE, "status": "completed", "conclusion": "success"}]}
            for i, name in enumerate(names)]


def receipt():
    return {"schema": "szl.hf-vertical-flagships/v4", "source_repository": gate.REPOSITORY,
            "source_revision": SOURCE, "workflow_run_id": RUN, "complete": True,
            "combined_exit_code": 0, "generated_flagship_exit_code": 0, "lyte_exit_code": 0,
            "lyte_runtime": {"schema": "szl.hf-lyte-enterprise-publication/v3", "complete": True,
                             "source_repository": "szl-holdings/lyte-services", "source_revision": "b" * 40}}


class CompletionTests(unittest.TestCase):
    def test_exact_terminal_child(self):
        self.assertEqual(gate.validate_run(run(), child()), "completed")
        gate.validate_jobs(jobs(), child())

    def test_source_workflow_attempt_event_identity(self):
        for key, value in (("head_sha", "b" * 40), ("head_branch", "other"), ("id", True),
                           ("event", "push"), ("run_attempt", 2), ("run_attempt", True),
                           ("path", ".github/workflows/other.yml")):
            with self.subTest(key=key, value=value), self.assertRaises(RuntimeError):
                gate.validate_run({**run(), key: value}, child())

    def test_wrong_repository(self):
        for key in ("repository", "head_repository"):
            value = run(); value[key] = {"id": 1, "full_name": gate.REPOSITORY}
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                gate.validate_run(value, child())

    def test_nonterminal_not_complete(self):
        for state in ("queued", "requested", "waiting", "pending", "in_progress"):
            with self.subTest(state=state):
                self.assertEqual(gate.validate_run({**run(), "status": state, "conclusion": None}, child()), state)

    def test_unknown_terminal_and_outcomes(self):
        with self.assertRaises(RuntimeError):
            gate.validate_run({**run(), "status": "mystery"}, child())
        for outcome in (None, "failure", "cancelled", "timed_out", "skipped", "neutral"):
            with self.subTest(outcome=outcome), self.assertRaises(RuntimeError):
                gate.validate_run({**run(), "conclusion": outcome}, child())

    def test_green_workflow_failed_vertical_is_rejected(self):
        value = jobs(); value[0]["conclusion"] = "failure"
        gate.validate_run(run(), child())
        with self.assertRaises(RuntimeError):
            gate.validate_jobs(value, child())

    def test_missing_duplicate_skipped_vertical(self):
        for value in (jobs()[1:], jobs()+[jobs()[0]], [{**j, "conclusion": "skipped"} for j in jobs()]):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                gate.validate_jobs(value, child())

    def test_job_source_attempt_and_pending(self):
        for key, bad in (("head_sha", "b" * 40), ("run_id", 55), ("run_attempt", 2),
                         ("status", "in_progress"), ("id", None)):
            value = jobs(); value[0][key] = bad
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                gate.validate_jobs(value, child())

    def test_receipt_step_missing_failed_or_skipped(self):
        for steps in ([], [{"name": gate.VERTICAL_GATE, "status": "completed", "conclusion": "skipped"}],
                      [{"name": gate.VERTICAL_GATE, "status": "completed", "conclusion": "failure"}]):
            value = jobs(); value[0]["steps"] = steps
            with self.subTest(steps=steps), self.assertRaises(RuntimeError):
                gate.validate_jobs(value, child())

    def test_product_only_may_skip_vertical_not_product(self):
        value = jobs(); value[0]["conclusion"] = "skipped"
        gate.validate_jobs(value, child(False))
        value[1]["conclusion"] = "skipped"
        with self.assertRaises(RuntimeError):
            gate.validate_jobs(value, child(False))

    def test_empty_all_skipped_and_pagination_duplicates(self):
        for value in ([], [{**j, "conclusion": "skipped"} for j in jobs()], jobs()+[jobs()[0]]):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                gate.validate_jobs(value, child(False, "repair-cloudflare-product-edge.yml"))

    def test_unique_returned_url_only(self):
        url = f"https://github.com/{gate.REPOSITORY}/actions/runs/{RUN}"
        self.assertEqual(gate.dispatch_id(("Accepted\n"+url+"\n").encode()), RUN)
        for raw in (b"accepted", (url+"\n"+url).encode(), (url+"?x=y").encode(),
                    b"https://github.com/other/repo/actions/runs/1234", b"x" * 65537):
            with self.subTest(length=len(raw)), self.assertRaises(RuntimeError):
                gate.dispatch_id(raw)

    def test_canonical_dispatch_is_single_and_journaled(self):
        command = ["gh", "workflow", "run", "hf-sync.yml", "--repo", gate.REPOSITORY, "--ref", "main"]
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/"journal.jsonl"
            def action(argv):
                self.assertEqual(json.loads(path.read_text().splitlines()[0])["state"], "UNKNOWN_AFTER_ATTEMPT")
                return f"https://github.com/{gate.REPOSITORY}/actions/runs/{RUN}\n".encode()
            with patch.object(gate, "api", return_value={"object": {"sha": SOURCE}}), patch.object(gate, "cli", side_effect=action) as execute:
                result = gate.dispatch_child(command, "hf-sync.yml", SOURCE, False, path)
                self.assertEqual(result["state"], "DISPATCH_BOUND")
                with self.assertRaises(FileExistsError):
                    gate.dispatch_child(command, "hf-sync.yml", SOURCE, False, path)
                self.assertEqual(execute.call_count, 1)

    def test_unknown_dispatch_never_retries(self):
        command = ["gh", "workflow", "run", "hf-sync.yml", "--repo", gate.REPOSITORY, "--ref", "main"]
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"journal.jsonl"
            with patch.object(gate, "api", return_value={"object": {"sha": SOURCE}}), patch.object(gate, "cli", return_value=b"Accepted") as execute:
                with self.assertRaises(RuntimeError):
                    gate.dispatch_child(command, "hf-sync.yml", SOURCE, False, path)
            self.assertEqual(execute.call_count, 1)
            self.assertEqual(json.loads(path.read_text().splitlines()[-1])["state"], "UNKNOWN_AFTER_ATTEMPT")

    def test_source_movement_or_mutated_command_before_write(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(gate, "cli") as execute:
            path = Path(temp)/"journal.jsonl"
            command=["gh", "workflow", "run", "hf-sync.yml", "--repo", gate.REPOSITORY, "--ref", "main"]
            with self.assertRaises(RuntimeError):
                gate.dispatch_child(command+["--ref", "other"], "hf-sync.yml", SOURCE, False, path)
            with patch.object(gate, "api", return_value={"object": {"sha": "b"*40}}), self.assertRaises(RuntimeError):
                gate.dispatch_child(command, "hf-sync.yml", SOURCE, False, path)
            self.assertFalse(path.exists());execute.assert_not_called()

    def test_pagination_complete(self):
        with patch.object(gate, "api", return_value={"jobs": jobs(), "total_count": 3}):
            self.assertEqual(len(gate.child_jobs(child())), 3)
        with patch.object(gate, "api", return_value={"jobs": jobs(), "total_count": 4}), self.assertRaises(RuntimeError):
            gate.child_jobs(child())

    def test_wait_accepts_only_after_full_validation(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"journal.jsonl"
            with patch.object(gate, "api", side_effect=[run(), run(), {"object": {"sha": SOURCE}}, run(), {"object": {"sha": SOURCE}}]), patch.object(gate, "child_jobs", return_value=jobs()):
                gate.wait_for_children([(child(),path)])
            self.assertEqual(json.loads(path.read_text())["state"], "CHILD_COMPLETION_VERIFIED")

    def test_wait_rejects_failed_job_despite_green_run(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"journal.jsonl";bad=jobs();bad[0]["conclusion"]="failure"
            with patch.object(gate, "api", return_value=run()), patch.object(gate, "child_jobs", return_value=bad), self.assertRaises(RuntimeError):
                gate.wait_for_children([(child(),path)])
            self.assertEqual(json.loads(path.read_text())["state"], "HOLD")

    def test_wait_times_out_without_cancelling_or_redispatching(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(gate.time, "monotonic", side_effect=[0,2]), patch.object(gate, "cli") as execute:
            with self.assertRaises(RuntimeError):
                gate.wait_for_children([(child(),Path(temp)/"j")],seconds=1)
            execute.assert_not_called()

    def test_receipt_valid(self):
        gate.verify_vertical(receipt(),SOURCE,RUN)

    def test_real_failure_shape_never_passes(self):
        value=receipt();value.update(complete=False,lyte_exit_code=1)
        value["lyte_runtime"].update(complete=False,error="attestation child exit 1")
        with self.assertRaises(RuntimeError):
            gate.verify_vertical(value,SOURCE,RUN)

    def test_each_exit_and_receipt_identity(self):
        for key,bad in (("schema","other"),("source_revision","b"*40),("workflow_run_id",True),
                        ("complete",1),("combined_exit_code",True),("generated_flagship_exit_code",1),("lyte_exit_code",None)):
            with self.subTest(key=key),self.assertRaises(RuntimeError):
                gate.verify_vertical({**receipt(),key:bad},SOURCE,RUN)

    def test_missing_or_incomplete_lyte(self):
        for value in ({}, {**receipt()["lyte_runtime"],"complete":False},
                      {**receipt()["lyte_runtime"],"source_revision":"unknown"}):
            with self.subTest(value=value),self.assertRaises(RuntimeError):
                gate.verify_vertical({**receipt(),"lyte_runtime":value},SOURCE,RUN)

    def test_strict_json(self):
        for raw in (b'[]',b'{"a":1,"a":2}',b'{"a":NaN}',b'{"a":1e999}',b'x'*(gate.MAX_BYTES+1)):
            with self.subTest(length=len(raw)),self.assertRaises((RuntimeError,ValueError)):
                gate.decode(raw)

    def test_cli_gate_cannot_turn_skipped_writer_into_complete(self):
        with patch.dict(os.environ, {"EXACT_MAIN_PUBLISH":"false", "VERTICAL_PLAN_PUBLISH":"true", "VERTICAL_PUBLISH_OUTCOME":"skipped"}), patch.object(sys,"argv",["gate"]),self.assertRaises(RuntimeError):
            gate.main()

    def test_actual_workflow_wiring(self):
        hf=(ROOT/".github/workflows/hf-sync.yml").read_text()
        vertical=hf.split("  publish-vertical-flagships:\n",1)[1].split("\n  readiness-verdict:",1)[0]
        self.assertNotIn("continue-on-error: true",vertical)
        self.assertIn("id: vertical_publish",vertical)
        self.assertIn("name: "+gate.VERTICAL_GATE,vertical)
        self.assertIn("run: python scripts/estate_child_completion.py",vertical)
        self.assertIn("inputs.publish_vertical_flagships }}",vertical)
        parent=(ROOT/".github/workflows/estate-release-train.yml").read_text()
        self.assertIn("wait_for_children(children)",parent)
        self.assertLess(parent.index("wait_for_children(children)"),parent.index("- name: Reobserve after an explicit repair dispatch"))
        self.assertIn("reports/estate-child-*.jsonl",parent)
        self.assertIn("python tests/test_estate_child_completion.py",parent)
        self.assertNotIn("subprocess.run(command, check=True)",parent)
        self.assertIn("inputs.publish_vertical_flagships == true",parent)


def edge_jobs(run_id=RUN):
    """Names come from the existing canonical edge workflow, not the validator."""
    names = ["Prove bounded routes, reversible DNS cutover, and Worker behavior",
             "Deploy, cut over exact DNS proxy state, and prove the public edge"]
    return [{"id": i + 11, "name": name, "run_id": run_id, "head_sha": SOURCE,
             "run_attempt": 1, "status": "completed", "conclusion": "success",
             "steps": [{"name": "Enforce proved live edge", "status": "completed",
                        "conclusion": "success"}] if i else []}
            for i, name in enumerate(names)]


class CompletionReadbackTests(unittest.TestCase):
    def test_actual_edge_writer_and_gate_are_accepted(self):
        gate.validate_jobs(edge_jobs(), child(False, "repair-cloudflare-product-edge.yml"))

    def test_edge_contract_success_cannot_replace_missing_or_skipped_writer(self):
        edge = child(False, "repair-cloudflare-product-edge.yml")
        skipped = edge_jobs(); skipped[1]["conclusion"] = "skipped"
        for rows in (edge_jobs()[:1], skipped):
            with self.subTest(rows=rows), self.assertRaises(RuntimeError):
                gate.validate_jobs(rows, edge)

    def test_edge_enforcement_step_must_actually_execute_once(self):
        for steps in ([], [{"name": "Enforce proved live edge", "status": "completed",
                           "conclusion": "skipped"}],
                      [{"name": "Enforce proved live edge", "status": "completed",
                        "conclusion": "failure"}],
                      [{"name": "Enforce proved live edge", "status": "completed",
                        "conclusion": "success"}] * 2):
            rows = edge_jobs(); rows[1]["steps"] = steps
            with self.subTest(steps=steps), self.assertRaises(RuntimeError):
                gate.validate_jobs(rows, child(False, "repair-cloudflare-product-edge.yml"))

    def test_rerun_during_job_collection_cannot_be_first_attempt_completion(self):
        count = 0
        def observe(suffix):
            nonlocal count
            if suffix == "git/ref/heads/main":
                return {"object": {"sha": SOURCE}}
            count += 1
            return run() if count == 1 else {**run(), "run_attempt": 2}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "j"
            with patch.object(gate, "api", side_effect=observe), patch.object(gate, "child_jobs", return_value=jobs()):
                with self.assertRaises(RuntimeError):
                    gate.wait_for_children([(child(), path)])
            self.assertNotIn("CHILD_COMPLETION_VERIFIED", path.read_text())
            self.assertEqual(json.loads(path.read_text().splitlines()[-1])["state"], "HOLD")

    def test_completed_child_is_rechecked_after_the_slowest_sibling(self):
        second = {**child(False, "repair-cloudflare-product-edge.yml"), "run_id": 5678}
        edge_run = {**run(), "id": 5678, "path": ".github/workflows/repair-cloudflare-product-edge.yml"}
        edge_seen = False
        def observe(suffix):
            nonlocal edge_seen
            if suffix == "git/ref/heads/main":
                return {"object": {"sha": SOURCE}}
            if suffix == "actions/runs/5678":
                edge_seen = True
                return edge_run
            return {**run(), "run_attempt": 2} if edge_seen else run()
        with tempfile.TemporaryDirectory() as temp:
            pairs = [(child(), Path(temp) / "hf"), (second, Path(temp) / "edge")]
            with patch.object(gate, "api", side_effect=observe), patch.object(
                gate, "child_jobs", side_effect=lambda item: jobs() if item["run_id"] == RUN else edge_jobs(5678)
            ):
                with self.assertRaises(RuntimeError):
                    gate.wait_for_children(pairs)
            for _, path in pairs:
                self.assertNotIn("CHILD_COMPLETION_VERIFIED", path.read_text())

    def test_failed_sibling_does_not_leave_an_earlier_completion_claim(self):
        second = {**child(False, "repair-cloudflare-product-edge.yml"), "run_id": 5678}
        edge_run = {**run(), "id": 5678, "path": ".github/workflows/repair-cloudflare-product-edge.yml"}
        failed = edge_jobs(5678); failed[1]["conclusion"] = "failure"
        def observe(suffix):
            if suffix == "git/ref/heads/main":
                return {"object": {"sha": SOURCE}}
            return edge_run if suffix == "actions/runs/5678" else run()
        with tempfile.TemporaryDirectory() as temp:
            pairs = [(child(), Path(temp) / "hf"), (second, Path(temp) / "edge")]
            with patch.object(gate, "api", side_effect=observe), patch.object(
                gate, "child_jobs", side_effect=lambda item: jobs() if item["run_id"] == RUN else failed
            ), self.assertRaises(RuntimeError):
                gate.wait_for_children(pairs)
            for _, path in pairs:
                self.assertNotIn("CHILD_COMPLETION_VERIFIED", path.read_text())
                self.assertEqual(json.loads(path.read_text().splitlines()[-1])["state"], "HOLD")

    def test_final_source_movement_keeps_the_join_incomplete(self):
        reads = 0
        def observe(suffix):
            nonlocal reads
            if suffix != "git/ref/heads/main":
                return run()
            reads += 1
            return {"object": {"sha": SOURCE if reads == 1 else "c" * 40}}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "j"
            with patch.object(gate, "api", side_effect=observe), patch.object(gate, "child_jobs", return_value=jobs()):
                with self.assertRaises(RuntimeError):
                    gate.wait_for_children([(child(), path)])
            self.assertNotIn("CHILD_COMPLETION_VERIFIED", path.read_text())

    def test_nonterminal_final_readback_is_not_completion(self):
        count = 0
        def observe(suffix):
            nonlocal count
            if suffix == "git/ref/heads/main":
                return {"object": {"sha": SOURCE}}
            count += 1
            return run() if count < 3 else {**run(), "status": "in_progress", "conclusion": None}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "j"
            with patch.object(gate, "api", side_effect=observe), patch.object(gate, "child_jobs", return_value=jobs()):
                with self.assertRaises(RuntimeError):
                    gate.wait_for_children([(child(), path)])
            self.assertNotIn("CHILD_COMPLETION_VERIFIED", path.read_text())

    def test_final_transport_failure_is_not_stale_completion(self):
        count = 0
        def observe(suffix):
            nonlocal count
            if suffix == "git/ref/heads/main":
                return {"object": {"sha": SOURCE}}
            count += 1
            if count >= 3:
                raise OSError("synthetic unavailable readback")
            return run()
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "j"
            with patch.object(gate, "api", side_effect=observe), patch.object(gate, "child_jobs", return_value=jobs()):
                with self.assertRaises(OSError):
                    gate.wait_for_children([(child(), path)])
            self.assertEqual(json.loads(path.read_text().splitlines()[-1])["state"], "HOLD")

    def test_timeout_records_hold_without_cancelling_or_redispatching(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "j"
            with patch.object(gate.time, "monotonic", side_effect=[0, 2]), patch.object(gate, "cli") as execute:
                with self.assertRaises(RuntimeError):
                    gate.wait_for_children([(child(), path)], seconds=1)
            execute.assert_not_called()
            self.assertEqual(json.loads(path.read_text().splitlines()[-1])["state"], "HOLD")

    def test_duplicate_child_identity_is_rejected_before_reads(self):
        with tempfile.TemporaryDirectory() as temp:
            for pairs in ([(child(), Path(temp) / "a"), (child(), Path(temp) / "b")],
                          [(child(), Path(temp) / "a"),
                           ({**child(False, "repair-cloudflare-product-edge.yml"), "run_id": 5678}, Path(temp) / "a")]):
                with self.subTest(pairs=pairs), patch.object(gate, "api") as observe, self.assertRaises(RuntimeError):
                    gate.wait_for_children(pairs)
                observe.assert_not_called()

    def test_two_children_complete_only_after_both_final_readbacks(self):
        second = {**child(False, "repair-cloudflare-product-edge.yml"), "run_id": 5678}
        counts = {RUN: 0, 5678: 0}
        edge_run = {**run(), "id": 5678, "path": ".github/workflows/repair-cloudflare-product-edge.yml"}
        with tempfile.TemporaryDirectory() as temp:
            pairs = [(child(), Path(temp) / "hf"), (second, Path(temp) / "edge")]
            def observe(suffix):
                # Completion journals must not exist before all observations pass.
                self.assertFalse(any(path.exists() for _, path in pairs))
                if suffix == "git/ref/heads/main":
                    return {"object": {"sha": SOURCE}}
                identity = int(suffix.rsplit("/", 1)[-1]); counts[identity] += 1
                return run() if identity == RUN else edge_run
            with patch.object(gate, "api", side_effect=observe), patch.object(
                gate, "child_jobs", side_effect=lambda item: jobs() if item["run_id"] == RUN else edge_jobs(5678)
            ):
                gate.wait_for_children(pairs)
            self.assertEqual(counts, {RUN: 3, 5678: 3})
            for item, path in pairs:
                value = json.loads(path.read_text())
                self.assertEqual(value["state"], "CHILD_COMPLETION_VERIFIED")
                self.assertEqual(value["run"]["id"], item["run_id"])
                self.assertIs(value["production_authorization"], False)

    def test_invalid_wait_bounds_are_rejected_before_reads(self):
        for bound in (True, False, 0, 3601, 1.5, float("nan")):
            with self.subTest(bound=bound), tempfile.TemporaryDirectory() as temp, patch.object(gate, "api") as observe:
                with self.assertRaises(RuntimeError):
                    gate.wait_for_children([(child(), Path(temp) / "j")], seconds=bound)
                observe.assert_not_called()


if __name__ == "__main__":
    unittest.main()
