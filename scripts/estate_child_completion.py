"""Native child completion barrier. Publication remains in canonical workflows.

SPDX-License-Identifier: Apache-2.0
An unsigned local journal binds each single dispatch attempt to its returned run.
No run-list guessing, automatic resend, provider mutation or production authority.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time

REPOSITORY = "szl-holdings/a11oy"
REPOSITORY_ID = 1225834126
WORKFLOWS = {"hf-sync.yml", "repair-cloudflare-product-edge.yml"}
VERTICAL_JOB = "Publish and live-verify six domain-native flagship Spaces"
VERTICAL_GATE = "Enforce complete explicitly requested vertical publication"
EDGE_JOB = "Deploy, cut over exact DNS proxy state, and prove the public edge"
EDGE_GATE = "Enforce proved live edge"
MAX_BYTES = 8 * 1024 * 1024


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def sha40(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def decode(raw: bytes) -> dict:
    require(len(raw) <= MAX_BYTES, "response exceeds bound")

    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def reject(_):
        raise ValueError("non-finite JSON constant")

    def finite(text):
        value = float(text)
        require(math.isfinite(value), "overflowed JSON number")
        return value

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=reject, parse_float=finite)
    require(type(value) is dict, "expected JSON object")
    return value


def cli(argv: list[str]) -> bytes:
    """Bound stdout/stderr without shell evaluation or printing token values."""
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        env = dict(os.environ)
        env.update(GH_HOST="github.com", GH_PROMPT_DISABLED="1")
        env.pop("GH_DEBUG", None)
        process = subprocess.Popen(argv, stdout=out, stderr=err, shell=False, env=env)
        deadline = time.monotonic() + 90
        try:
            while process.poll() is None:
                require(time.monotonic() < deadline, "GitHub CLI deadline exceeded")
                require(os.fstat(out.fileno()).st_size <= MAX_BYTES
                        and os.fstat(err.fileno()).st_size <= MAX_BYTES,
                        "GitHub CLI output exceeds bound")
                time.sleep(0.1)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
        require(process.returncode == 0, "GitHub CLI did not confirm operation")
        require(os.fstat(out.fileno()).st_size <= MAX_BYTES, "response exceeds bound")
        out.seek(0)
        return out.read(MAX_BYTES + 1)


def api(suffix: str) -> dict:
    # Only fixed repository GETs are reachable from this reader.
    require(re.fullmatch(r"[a-zA-Z0-9_./?=&-]+", suffix) is not None,
            "invalid repository read path")
    return decode(cli(["gh", "api", "--hostname", "github.com", "--method", "GET",
                       f"repos/{REPOSITORY}/{suffix}"]))


def journal(path: Path, record: dict, *, first: bool = False) -> None:
    with path.open("x" if first else "a", encoding="utf-8") as stream:
        stream.write(json.dumps({"observed_at": datetime.now(timezone.utc).isoformat(),
                                 **record}, sort_keys=True, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def dispatch_id(stdout: bytes) -> int:
    require(len(stdout) <= 65536, "dispatch response exceeds bound")
    lines = stdout.decode("utf-8").splitlines()
    prefix = f"https://github.com/{REPOSITORY}/actions/runs/"
    matches = [line.strip()[len(prefix):] for line in lines
               if re.fullmatch(re.escape(prefix) + r"[1-9][0-9]*", line.strip())]
    require(len(matches) == 1, "UNKNOWN_AFTER_ATTEMPT: no unique returned run URL")
    return int(matches[0])


def dispatch_child(command: list[str], workflow: str, source: str, vertical: bool,
                   output: Path) -> dict:
    require(workflow in WORKFLOWS and sha40(source) and type(vertical) is bool,
            "unadmitted child identity")
    prefix = ["gh", "workflow", "run", workflow, "--repo", REPOSITORY, "--ref", "main"]
    expected = list(prefix)
    if vertical:
        require(workflow == "hf-sync.yml", "vertical request belongs to hf-sync only")
        plan = {"complete": True, "approved": True, "expected_source_revision": source}
        expected += ["-f", "publish_vertical_flagships=true", "-f",
                     "vertical_plan_json=" + json.dumps(plan, sort_keys=True)]
    require(command == expected, "command differs from canonical source-bound plan")
    require(api("git/ref/heads/main").get("object", {}).get("sha") == source,
            "source moved before canonical dispatch")
    record = {"schema": "szl.estate-child-completion/v1", "workflow": workflow,
              "source_revision": source, "vertical_requested": vertical,
              "parent_run_id": os.environ.get("GITHUB_RUN_ID"),
              "state": "UNKNOWN_AFTER_ATTEMPT", "run_id": None,
              "production_authorization": False}
    # Exclusive first write refuses a repeated/uncertain request in this attempt.
    journal(output, record, first=True)
    try:
        raw = cli(command)
        record.update(run_id=dispatch_id(raw), state="DISPATCH_BOUND",
                      dispatch_response_sha256=hashlib.sha256(raw).hexdigest())
        journal(output, record)
        return record
    except Exception:
        # Never retry or select a 'latest' run after a possibly accepted write.
        journal(output, record)
        raise


def validate_run(run: dict, child: dict) -> str:
    require(type(run.get("id")) is int and run["id"] == child["run_id"], "child run mismatch")
    require(run.get("repository", {}).get("id") == REPOSITORY_ID
            and run.get("repository", {}).get("full_name") == REPOSITORY
            and run.get("head_repository", {}).get("id") == REPOSITORY_ID
            and run.get("event") == "workflow_dispatch"
            and run.get("head_branch") == "main"
            and run.get("head_sha") == child["source_revision"]
            and run.get("path") == ".github/workflows/" + child["workflow"]
            and type(run.get("run_attempt")) is int and run["run_attempt"] == 1,
            "child repository/source/workflow/attempt mismatch")
    status = run.get("status")
    require(status in {"queued", "requested", "waiting", "pending", "in_progress", "completed"},
            "unknown child status")
    if status == "completed":
        require(run.get("conclusion") == "success", "canonical child did not succeed")
    return status


def validate_jobs(jobs: list[dict], child: dict) -> None:
    require(bool(jobs), "missing child jobs")
    ids = [job.get("id") for job in jobs]
    require(all(type(value) is int for value in ids) and len(set(ids)) == len(ids),
            "invalid/duplicate child jobs")
    for job in jobs:
        require(job.get("run_id") == child["run_id"]
                and job.get("head_sha") == child["source_revision"]
                and type(job.get("run_attempt")) is int and job["run_attempt"] == 1
                and job.get("status") == "completed"
                and job.get("conclusion") in {"success", "skipped"},
                "child job pending/failed or origin mismatch")
    require(any(job["conclusion"] == "success" for job in jobs), "no executed child job")
    if child["workflow"] == "hf-sync.yml":
        for name in ("Prove exact live source, runtime, routes, and singleton state",
                     "Probe and ingest exact post-deploy readiness verdict"):
            matched = [job for job in jobs if job.get("name") == name]
            require(len(matched) == 1 and matched[0]["conclusion"] == "success",
                    "canonical product completion job missing/skipped")
    if child["workflow"] == "repair-cloudflare-product-edge.yml":
        # The contract-test job can pass while the requested writer is skipped.
        # Require the actual canonical repair and its exit-code enforcement.
        required = [job for job in jobs if job.get("name") == EDGE_JOB]
        require(len(required) == 1 and required[0]["conclusion"] == "success",
                "canonical edge repair job missing/skipped")
        steps = [step for step in required[0].get("steps", []) if step.get("name") == EDGE_GATE]
        require(len(steps) == 1 and steps[0].get("status") == "completed"
                and steps[0].get("conclusion") == "success",
                "canonical edge terminal gate was not executed successfully")
    if child["vertical_requested"]:
        required = [job for job in jobs if job.get("name") == VERTICAL_JOB]
        require(len(required) == 1 and required[0]["conclusion"] == "success",
                "explicit vertical job not successful")
        steps = [step for step in required[0].get("steps", []) if step.get("name") == VERTICAL_GATE]
        require(len(steps) == 1 and steps[0].get("status") == "completed"
                and steps[0].get("conclusion") == "success",
                "explicit vertical receipt gate was not executed successfully")


def child_jobs(child: dict) -> list[dict]:
    rows = []
    for page in range(1, 11):
        data = api(f"actions/runs/{child['run_id']}/attempts/1/jobs?per_page=100&page={page}")
        batch = data.get("jobs")
        require(type(batch) is list, "child jobs observation unavailable")
        rows.extend(batch)
        if len(batch) < 100:
            require(data.get("total_count") == len(rows), "incomplete child job pagination")
            return rows
    raise RuntimeError("child job pagination bound exceeded")


def wait_for_children(children: list[tuple[dict, Path]], *, seconds: int = 3600) -> None:
    """Join exact first-attempt children; recheck the whole set before returning.

    These bounded sequential reads are not an atomic GitHub lease. Re-reading
    runs after job enumeration and again after the slowest sibling catches an
    observed rerun or source change, without inventing fresh execution evidence.
    Neither an earlier green child nor successful edge tests can finish a repair.
    """
    require(bool(children) and type(seconds) is int and 1 <= seconds <= 3600,
            "invalid child wait bound")
    require(len(children) <= len(WORKFLOWS), "unexpected child count")
    run_ids = [child.get("run_id") for child, _ in children]
    workflows = [child.get("workflow") for child, _ in children]
    paths = [path.resolve() for _, path in children]
    require(all(type(value) is int and value > 0 for value in run_ids)
            and len(set(run_ids)) == len(run_ids)
            and all(workflow in WORKFLOWS for workflow in workflows)
            and len(set(workflows)) == len(workflows)
            and len(set(paths)) == len(paths), "duplicate or invalid child identity")
    source = children[0][0].get("source_revision")
    require(sha40(source) and all(child.get("source_revision") == source
                                 for child, _ in children), "child source set mismatch")
    deadline = time.monotonic() + seconds
    remaining = list(children)
    observations = {}

    def within_deadline() -> None:
        require(time.monotonic() < deadline, "child completion deadline; repair remains HOLD")

    try:
        while remaining:
            within_deadline()
            for child, path in list(remaining):
                within_deadline()
                run = api(f"actions/runs/{child['run_id']}")
                observations[child["run_id"]] = {"run": run}
                status = validate_run(run, child)
                if status != "completed":
                    continue
                jobs = child_jobs(child)
                observations[child["run_id"]]["jobs"] = jobs
                validate_jobs(jobs, child)
                # An attempt can change while the paginated job collection is read.
                readback = api(f"actions/runs/{child['run_id']}")
                observations[child["run_id"]]["run"] = readback
                require(validate_run(readback, child) == "completed",
                        "child changed during job observation")
                require(api("git/ref/heads/main").get("object", {}).get("sha") == source,
                        "source moved during child execution")
                observations[child["run_id"]] = {"run": readback, "jobs": jobs}
                remaining.remove((child, path))
            if remaining:
                time.sleep(min(20, max(0, deadline - time.monotonic())))

        # Do not retain a completed child's stale green state while another runs.
        # Delay every completion record until the entire requested set validates.
        for child, _ in children:
            within_deadline()
            readback = api(f"actions/runs/{child['run_id']}")
            observations[child["run_id"]]["run"] = readback
            require(validate_run(readback, child) == "completed",
                    "child changed before complete-set readback")
        require(api("git/ref/heads/main").get("object", {}).get("sha") == source,
                "source moved before complete-set readback")
        within_deadline()
        for child, path in children:
            journal(path, {**child, "state": "CHILD_COMPLETION_VERIFIED",
                           **observations[child["run_id"]]})
    except Exception:
        # Partial observations and timeouts never become a successful return.
        # Do not redispatch, cancel children, or overwrite the attempt journal.
        for child, path in children:
            journal(path, {**child, "state": "HOLD",
                           "run": observations.get(child["run_id"], {}).get("run")})
        raise


def verify_vertical(value: dict, source: str, run_id: int) -> None:
    """Validate the publisher's actual v4 envelope, not a liveness snapshot."""
    require(sha40(source) and type(run_id) is int and run_id > 0, "invalid expected source/run")
    require(value.get("schema") == "szl.hf-vertical-flagships/v4"
            and value.get("source_repository") == REPOSITORY
            and value.get("source_revision") == source
            and type(value.get("workflow_run_id")) is int and value["workflow_run_id"] == run_id
            and value.get("complete") is True, "vertical publication incomplete or unbound")
    for key in ("combined_exit_code", "generated_flagship_exit_code", "lyte_exit_code"):
        require(type(value.get(key)) is int and value[key] == 0, "publisher nonzero or unknown exit: " + key)
    lyte = value.get("lyte_runtime", {})
    require(lyte.get("schema") == "szl.hf-lyte-enterprise-publication/v3"
            and lyte.get("complete") is True
            and lyte.get("source_repository") == "szl-holdings/lyte-services"
            and sha40(lyte.get("source_revision"))
            and not lyte.get("error"), "canonical Lyte attestation incomplete")


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    require(os.environ.get("EXACT_MAIN_PUBLISH") == "true"
            and os.environ.get("VERTICAL_PLAN_PUBLISH") == "true"
            and os.environ.get("VERTICAL_PUBLISH_OUTCOME") == "success",
            "explicit vertical publication was denied/skipped/failed")
    path = Path(__file__).resolve().parents[1] / "hf-vertical-flagships-receipt.json"
    with path.open("rb") as stream:
        value = decode(stream.read(MAX_BYTES + 1))
    verify_vertical(value, os.environ.get("GITHUB_SHA", ""), int(os.environ.get("GITHUB_RUN_ID", "0")))
    print("EXPLICIT_VERTICAL_PUBLICATION_COMPLETE; production model qualification not inferred")


if __name__ == "__main__":
    main()
