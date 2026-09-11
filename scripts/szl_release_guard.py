"""Release evidence primitives for integration into the existing A11oy writer.

Standard library only. No HF writes, workflow dispatch, remote shell, package
installation, or auto-approval is performed by this module. Process execution
is POSIX-only and is for reviewed commands in an isolated authorized runner.
Public receipts contain digests and fixed reason codes, never process output.
Local content-addressing is not a signature or remote immutable storage.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import os
import re
import selectors
import signal
import stat
import subprocess
import time
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Mapping, Sequence

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA64 = re.compile(r"^[0-9a-f]{64}$")
NAME = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
VIEWPORTS = ((320, 568), (375, 812), (430, 932), (768, 1024),
             (1024, 768), (1440, 900), (1920, 1080))
PHASES = (
    "qualify-source", "controller-preflight", "snapshot-previous",
    "recheck-source", "publish-files", "confirm-publication",
    "bind-source", "restart", "attest-runtime", "verify-existing",
    "verify-forecast-workbench", "verify-source-again",
)


class ContractError(ValueError):
    """A contract was absent, contradictory, malformed, or not satisfied."""


class PhaseFailure(RuntimeError):
    """A phase failed; public event evidence was retained before propagation."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(canonical(value)).hexdigest()


def strict_json(raw: bytes | str, *, limit: int = 2_000_000) -> Any:
    """Reject duplicate keys, NaN/Infinity and excessive input before parsing."""
    if isinstance(raw, str):
        raw = raw.encode("utf-8")
    if len(raw) > limit:
        raise ContractError("JSON_BYTES_EXCEEDED")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ContractError("DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def constant(_):
        raise ContractError("NONFINITE_JSON_NUMBER")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=constant)
        # Large exponents can become infinity without invoking parse_constant.
        canonical(value)
        return value
    except (UnicodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise ContractError("INVALID_STRICT_JSON") from exc


def sha(value: Any, length: int = 40) -> str:
    pattern = SHA40 if length == 40 else SHA64
    if not isinstance(value, str) or pattern.fullmatch(value) is None:
        raise ContractError("INVALID_SHA")
    return value


def immutable_json(directory: Path, value: Any) -> Path:
    """Write one content-addressed JSON file without overwriting another value.

    Use only an owner-controlled output directory. This prevents accidental
    clobbering; it is not a hostile-user filesystem sandbox or signing service.
    """
    if directory.is_symlink():
        raise ContractError("SYMLINK_EVIDENCE_DIRECTORY")
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    data = canonical(value) + b"\n"
    path = directory / (hashlib.sha256(data).hexdigest() + ".json")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(path, flags, 0o600)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != data:
            raise ContractError("EVIDENCE_COLLISION")
        return path
    try:
        with os.fdopen(fd, "wb") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
    except BaseException:
        # A crash may leave an incomplete exclusive file; never report it valid.
        raise
    return path


def classify_process(code: int | None, output: bytes, *, timed_out: bool,
                     output_limited: bool) -> str:
    """Classify evidence without treating exit 2 as an established root cause."""
    if output_limited:
        return "OUTPUT_LIMIT"
    if timed_out:
        return "TIMEOUT"
    if code == 0:
        return "EXIT_ZERO"
    text = output.decode("utf-8", "replace")
    if "unrecognized arguments:" in text:
        return "CLI_ARGUMENT_REJECTED"
    if re.search(r"(?i)(default.branch.tip|current default).{0,100}(mismatch|must|unless|not)", text):
        return "DEFAULT_TIP_GUARD_REPORTED"
    if re.search(r"(?i)(HTTP(?: Error)?|status(?:_code)?)[ :=]+502\b", text):
        return "UPSTREAM_502_REPORTED"
    if "HF deploy contract" in text:
        return "DEPLOY_CONTRACT_REJECTED"
    return "NONZERO_EXIT_UNCLASSIFIED"


def run_bounded(command: Sequence[str], *, cwd: Path, timeout: float = 120.0,
                max_output: int = 2_000_000,
                env: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Execute reviewed argv, drain both streams, and kill its POSIX group.

    No shell is invoked. Output remains in bounded memory and is never written
    to public logs. Store private diagnostics only through an independently
    approved secret-handling path; digests here bind exactly the captured
    prefix, and completeness is explicit. Spawn itself may be OS-blocked.
    """
    if os.name != "posix":
        raise ContractError("PROCESS_RUNNER_REQUIRES_POSIX")
    if (isinstance(command, (str, bytes)) or not command
            or any(not isinstance(arg, str) or "\0" in arg for arg in command)):
        raise ContractError("ARGV_REQUIRED")
    if (isinstance(timeout, bool) or not isinstance(timeout, (int, float))
            or not math.isfinite(timeout) or not 0 < timeout <= 3600):
        raise ContractError("INVALID_TIMEOUT")
    if type(max_output) is not int or not 128 <= max_output <= 8_000_000:
        raise ContractError("INVALID_OUTPUT_BUDGET")
    start = time.monotonic()
    started = utc_now()
    captured = {"stdout": bytearray(), "stderr": bytearray()}
    limited = timed_out = killed = False
    selector = selectors.DefaultSelector()
    proc = None

    def kill_group():
        nonlocal killed
        killed = True
        if proc is not None:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    try:
        proc = subprocess.Popen(list(command), cwd=cwd, env=None if env is None else dict(env),
                                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, shell=False, start_new_session=True)
        assert proc.stdout is not None and proc.stderr is not None
        for label, stream in (("stdout", proc.stdout), ("stderr", proc.stderr)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, label)
        deadline = start + float(timeout)
        killed_at = None
        while selector.get_map() or proc.poll() is None:
            now = time.monotonic()
            if now >= deadline and not killed:
                timed_out = True
                kill_group()
                killed_at = now
            if killed_at is not None and now - killed_at >= 2.0:
                break  # Escaped descendants must not hold pipes forever.
            for key, _ in selector.select(timeout=0.03):
                try:
                    block = os.read(key.fileobj.fileno(), 65536)
                except BlockingIOError:
                    continue
                if not block:
                    selector.unregister(key.fileobj)
                    continue
                room = max_output - sum(map(len, captured.values()))
                captured[key.data].extend(block[:max(0, room)])
                if len(block) > room and not killed:
                    limited = True
                    kill_group()
                    killed_at = time.monotonic()
        if proc.poll() is None:
            kill_group()
        proc.wait(timeout=3)
    except BaseException:
        if proc is not None:
            kill_group()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                pass
        raise
    finally:
        selector.close()
        if proc is not None:
            if proc.stdout is not None:
                proc.stdout.close()
            if proc.stderr is not None:
                proc.stderr.close()
    output = bytes(captured["stderr"] + b"\n" + captured["stdout"])
    code = proc.returncode
    complete = not limited and not timed_out
    return {
        "schema": "szl.process-observation/v1", "started_at": started,
        "finished_at": utc_now(), "elapsed_seconds": round(time.monotonic() - start, 6),
        "exit_code": code, "timed_out": timed_out, "output_limited": limited,
        "output_complete": complete, "process_group_kill_attempted": killed,
        "reason_code": classify_process(code, output, timed_out=timed_out,
                                         output_limited=limited),
        "passed": code == 0 and complete,
        "streams": {name: {"captured_bytes": len(value),
                            "captured_sha256": hashlib.sha256(value).hexdigest()}
                    for name, value in captured.items()},
        "raw_output_recorded": False, "argv_recorded": False,
    }


class ReleaseJournal:
    """Ordered local event chain; supplied operation callbacks own real actions.

    The journal is not an authorization source. This object must be invoked
    inside the existing canonical writer, not used to create a second writer.
    Callbacks return measured public metadata, never credentials/log bodies.
    """
    def __init__(self, directory: Path, *, source: str, publisher: str,
                 phases: Sequence[str] = PHASES):
        self.source, self.publisher = sha(source), sha(publisher)
        if not phases or len(set(phases)) != len(phases) or any(
                not isinstance(p, str) or NAME.fullmatch(p) is None for p in phases):
            raise ContractError("INVALID_PHASE_SET")
        self.phases = tuple(phases)
        self.directory = directory / uuid.uuid4().hex
        self.directory.mkdir(parents=True, mode=0o700)
        self.events: list[dict[str, Any]] = []
        self.completed: list[str] = []
        self.failed = False

    def _append(self, phase: str, state: str, payload: dict[str, Any]):
        event = {"schema": "szl.release-phase/v1", "sequence": len(self.events),
                 "phase": phase, "state": state, "observed_at": utc_now(),
                 "source_revision": self.source, "publisher_revision": self.publisher,
                 "previous_sha256": digest(self.events[-1]) if self.events else None,
                 "payload": payload}
        immutable_json(self.directory, event)
        self.events.append(event)

    def perform(self, phase: str, action: Callable[[], Mapping[str, Any]]) -> Mapping[str, Any]:
        if self.failed or len(self.completed) >= len(self.phases):
            raise ContractError("RELEASE_ALREADY_TERMINAL")
        if phase != self.phases[len(self.completed)]:
            raise ContractError("PHASE_ORDER_VIOLATION")
        self._append(phase, "RUNNING", {})
        try:
            result = action()
            if (not isinstance(result, Mapping) or result.get("executed") is not True
                    or result.get("passed") is not True):
                raise ContractError("PHASE_DID_NOT_EXECUTE_SUCCESSFULLY")
            # Do not expose arbitrary callback output: only fixed fields/digests.
            code = result.get("reason_code", "OBSERVED_PASS")
            if not isinstance(code, str) or re.fullmatch(r"[A-Z0-9_]{1,80}", code) is None:
                raise ContractError("INVALID_REASON_CODE")
            evidence_sha = sha(result.get("evidence_sha256"), 64)
            self._append(phase, "PASS", {"executed": True, "passed": True,
                                         "reason_code": code, "evidence_sha256": evidence_sha})
            self.completed.append(phase)
            return result
        except BaseException as exc:
            self.failed = True
            self._append(phase, "FAIL", {"passed": False,
                                        "error_type": type(exc).__name__})
            raise PhaseFailure(f"{phase}: failure retained; release not complete") from exc

    def summary(self) -> dict[str, Any]:
        return {"schema": "szl.release-journal-summary/v1", "source_revision": self.source,
                "publisher_revision": self.publisher, "required_phases": list(self.phases),
                "completed_phases": list(self.completed), "failed": self.failed,
                "complete": not self.failed and tuple(self.completed) == self.phases,
                "events_sha256": digest(self.events), "event_count": len(self.events),
                "signature_verified": False, "execution_authority": "NONE"}


def verify_event_chain(events: Sequence[Mapping[str, Any]]) -> bool:
    if not events:
        return False
    try:
        source, publisher = sha(events[0]["source_revision"]), sha(events[0]["publisher_revision"])
        for i, event in enumerate(events):
            if (event.get("sequence") != i or event.get("source_revision") != source
                    or event.get("publisher_revision") != publisher
                    or event.get("previous_sha256") != (digest(events[i - 1]) if i else None)):
                return False
        return True
    except (KeyError, TypeError, ValueError):
        return False


def inspect_publisher(text: str) -> dict[str, Any]:
    """Static inspection only: never execute a downloaded publisher."""
    if len(text.encode()) > 1_000_000:
        raise ContractError("SOURCE_BYTES_EXCEEDED")
    tree = ast.parse(text)
    constants = {}
    wanted = {"SOURCE_REPOSITORY", "SOURCE_REVISION", "EXPECTED_VERSION",
              "CONTROLLER_REVISION", "CONTROLLER_BLOB_SHA1", "HF_REPOSITORY"}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in wanted:
                    if target.id in constants:
                        raise ContractError("DUPLICATE_SOURCE_CONSTANT")
                    constants[target.id] = ast.literal_eval(node.value)
    main = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"), None)
    calls = []
    if main:
        for node in ast.walk(main):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                calls.append((node.lineno, node.func.id))
    calls.sort()
    positions = {name: line for line, name in calls}
    before = (positions.get("ensure_runtime_configuration", 10**9)
              < positions.get("deploy_with_controller", -1))
    raw = text.encode()
    return {"schema": "szl.publisher-static-inspection/v1", "constants": constants,
            "git_blob_sha1": hashlib.sha1(f"blob {len(raw)}\0".encode() + raw).hexdigest(),
            "source_sha256": hashlib.sha256(raw).hexdigest(),
            "config_call_lexically_before_deploy": before,
            "lexical_inspection_not_runtime_proof": True}


def inspect_archive(path: Path, expected_sha256: str, member: str) -> dict[str, Any]:
    """Read one bounded JSON member in memory; never extract an archive."""
    sha(expected_sha256, 64)
    if path.stat().st_size > 32_000_000:
        raise ContractError("ARCHIVE_BYTES_EXCEEDED")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ContractError("ARCHIVE_DIGEST_MISMATCH")
    with zipfile.ZipFile(path) as archive:
        infos = archive.infolist()
        if len(infos) > 1000:
            raise ContractError("ARCHIVE_MEMBER_LIMIT")
        names = [i.filename for i in infos]
        if len(names) != len(set(names)):
            raise ContractError("DUPLICATE_ARCHIVE_MEMBER")
        for info in infos:
            parts = PurePosixPath(info.filename).parts
            mode = info.external_attr >> 16
            if (info.filename.startswith("/") or ".." in parts or "\\" in info.filename
                    or ":" in info.filename or stat.S_ISLNK(mode)):
                raise ContractError("UNSAFE_ARCHIVE_PATH")
        if member not in names:
            raise ContractError("RECEIPT_MEMBER_ABSENT")
        info = archive.getinfo(member)
        if info.file_size > 2_000_000 or info.file_size / max(1, info.compress_size) > 1000:
            raise ContractError("ARCHIVE_EXPANSION_LIMIT")
        value = strict_json(archive.read(member))
        if not isinstance(value, dict):
            raise ContractError("RECEIPT_NOT_OBJECT")
        return {"archive_sha256": expected_sha256, "member": member,
                "receipt": value, "signature_verified": False}


def phase_step_gate(jobs: Sequence[Mapping[str, Any]], *, job_name: str,
                    required_steps: Sequence[str]) -> dict[str, Any]:
    """A green wrapper does not turn skipped publication into a deployment."""
    selected = [j for j in jobs if j.get("name") == job_name]
    reasons = []
    if len(selected) != 1:
        return {"passed": False, "reason_codes": ["MISSING_OR_AMBIGUOUS_JOB"]}
    job = selected[0]
    if job.get("status") != "completed" or job.get("conclusion") != "success":
        reasons.append("JOB_NOT_SUCCESSFUL")
    if not required_steps or len(set(required_steps)) != len(required_steps):
        reasons.append("INVALID_REQUIRED_STEP_SET")
    for name in required_steps:
        steps = [s for s in (job.get("steps") or []) if s.get("name") == name]
        if (len(steps) != 1 or steps[0].get("status") != "completed"
                or steps[0].get("conclusion") != "success"):
            reasons.append("MANDATORY_STEP_NOT_EXECUTED_SUCCESSFULLY:" + name)
    return {"passed": not reasons, "reason_codes": reasons}


def identity_gate(*, producer: str, observed_source: str, hf_published: str,
                  hf_running: str, hf_stage: str, image_manifest_match: bool) -> bool:
    """Compare source with source, HF with HF; never compare across namespaces."""
    try:
        return (sha(producer) == sha(observed_source)
                and sha(hf_published) == sha(hf_running) and hf_stage == "RUNNING"
                and image_manifest_match is True)
    except (ValueError, TypeError):
        return False


def browser_gate(rows: Sequence[Mapping[str, Any]], *, source: str) -> bool:
    """Require all seven public-runtime browser sizes and nonempty evidence."""
    try:
        sha(source)
        if len(rows) != len(VIEWPORTS):
            return False
        seen = set()
        for row in rows:
            vp = tuple(row["viewport"])
            if vp not in VIEWPORTS or vp in seen:
                return False
            seen.add(vp)
            if (row.get("executed") is not True or row.get("passed") is not True
                    or row.get("source_revision") != source
                    or row.get("scope") != "PUBLIC_RUNTIME"):
                return False
            sha(row.get("report_sha256"), 64)
        return seen == set(VIEWPORTS)
    except (KeyError, TypeError, ValueError):
        return False


SOURCE_JOBS = (
    "lint", "accessibility", "api-contract", "responsive-overflow", "connector-contract",
    "release-gates", "database-migrations", "python-compile", "container-build",
    "source-binding", "bundle-budget", "truth-and-governance", "security-scan",
    "unit", "secret-scan", "frontend-static-contract", "container-smoke",
)


def source_qualification(*, source: str, repository: str, default_tip: Mapping[str, Any],
                         workflow_run: Mapping[str, Any], jobs: Sequence[Mapping[str, Any]],
                         expected_workflow_id: int) -> dict[str, Any]:
    """Validate paginated native GitHub evidence already collected by the caller.

    Caller must retrieve the complete jobs of the run's explicit latest attempt.
    Existing source jobs are distinguished from live-deployment probes; the run's
    own conclusion is retained even if a separate live probe has failed. Required
    PR merge checks are NOT waived by this source-only classification.
    """
    reasons = []
    try:
        sha(source)
        if repository != "szl-holdings/lyte-services":
            reasons.append("UNEXPECTED_PRODUCER")
        if default_tip.get("object", {}).get("sha") != source:
            reasons.append("PRODUCER_DEFAULT_TIP_MISMATCH")
        if workflow_run.get("head_sha") != source:
            reasons.append("SOURCE_TEST_HEAD_MISMATCH")
        if workflow_run.get("repository", {}).get("full_name") != repository:
            reasons.append("SOURCE_TEST_REPOSITORY_MISMATCH")
        if (type(expected_workflow_id) is not int or expected_workflow_id <= 0
                or workflow_run.get("workflow_id") != expected_workflow_id):
            reasons.append("SOURCE_TEST_WORKFLOW_MISMATCH")
        if workflow_run.get("status") != "completed":
            reasons.append("SOURCE_TESTS_NOT_TERMINAL")
        attempt, run_id = workflow_run.get("run_attempt"), workflow_run.get("id")
        if type(attempt) is not int or attempt < 1 or type(run_id) is not int or run_id < 1:
            reasons.append("SOURCE_TEST_RUN_IDENTITY_MISSING")
        for name in SOURCE_JOBS:
            matching = [j for j in jobs if j.get("name") == name]
            if (len(matching) != 1 or matching[0].get("status") != "completed"
                    or matching[0].get("conclusion") != "success"
                    or matching[0].get("run_id") != run_id
                    or matching[0].get("run_attempt") != attempt
                    or matching[0].get("head_sha") != source):
                reasons.append("SOURCE_JOB_NOT_BOUND_AND_SUCCESSFUL:" + name)
    except (TypeError, ValueError, AttributeError):
        reasons.append("INVALID_NATIVE_SOURCE_EVIDENCE")
    return {"schema": "szl.source-qualification/v1", "passed": not reasons,
            "reason_codes": reasons, "source_revision": source,
            "native_run_conclusion": workflow_run.get("conclusion"),
            "scope": "REQUIRED_SOURCE_JOBS_ONLY_NOT_MERGE_OR_LIVE_AUTHORITY"}


def retain_manifest_metadata(path: Path, directory: Path) -> dict[str, Any]:
    """Call in finally while the controller's temporary workspace still exists.

    Publish only whitelisted structural metadata. Preserve raw controller
    manifests separately only where their visibility/redaction has been approved.
    Missing and malformed manifests produce evidence, never an empty success.
    """
    result: dict[str, Any] = {"schema": "szl.controller-manifest-observation/v1",
                              "raw_manifest_published": False}
    if path.is_symlink():
        result["state"] = "REFUSED_SYMLINK"
    elif not path.exists():
        result["state"] = "ABSENT"
    elif path.stat().st_size > 2_000_000:
        result["state"] = "REFUSED_OVERSIZE"
    else:
        raw = path.read_bytes()
        result["raw_manifest_sha256"] = hashlib.sha256(raw).hexdigest()
        try:
            manifest = strict_json(raw)
            if not isinstance(manifest, dict):
                raise ContractError("MANIFEST_NOT_OBJECT")
            for name in ("ref", "hf_commit_oid"):
                if name in manifest:
                    result[name] = sha(manifest[name])
            for name in ("files_deployed", "files_resolved", "copy_sources"):
                if name in manifest:
                    if type(manifest[name]) is not int or manifest[name] < 0:
                        raise ContractError("MANIFEST_COUNT_INVALID")
                    result[name] = manifest[name]
            files = manifest.get("files", {})
            if not isinstance(files, dict):
                raise ContractError("MANIFEST_FILES_INVALID")
            # Entire dictionary is bound, but generated_contents and arbitrary
            # source filenames/values do not enter the public projection.
            result["files_dictionary_sha256"] = digest(files)
            result["state"] = "PARSED_METADATA_ONLY"
        except (ValueError, TypeError, KeyError):
            result["state"] = "MALFORMED"
    file = immutable_json(directory, result)
    return {**result, "metadata_receipt_name": file.name}


SAMPLE_RECORDS = (
    "source-ci", "container", "controller-preflight", "publication", "image-bytes",
    "live-existing", "live-extended", "metrics", "public-browser", "product-source",
    "proof-publication", "rollback-plan",
)
PRODUCTION_RECORDS = (
    "oidc", "tenant-isolation", "database-migrations", "restart-durability", "backup-restore",
    "authorized-ingest", "retention", "load-slo", "operator-alerts", "production-browser",
)
PROVIDER_RECORDS = (
    "model-license", "model-revision", "evaluation-data-provenance", "held-out-quality",
    "quantile-calibration", "serving-slo", "cost-budget", "provider-rollback", "human-admission",
)


def readiness_levels(records: Mapping[str, Any], *, source: str, publisher: str) -> dict[str, Any]:
    """Projection gate, not an evidence signer or independent authenticator.

    Input records must first be bound to actual native reports/artifacts by the
    existing controller. This function deliberately performs no provider switch.
    Missing evidence never becomes success; optional provider HOLD cannot turn
    an independently working baseline sample into a model-quality claim.
    """
    sha(source); sha(publisher)

    def missing(names):
        failed = []
        for name in names:
            record = records.get(name)
            if not isinstance(record, Mapping):
                failed.append(name); continue
            try:
                sha(record.get("report_sha256"), 64)
                ok = (record.get("executed") is True and record.get("passed") is True
                      and record.get("source_revision") == source
                      and record.get("publisher_revision") == publisher
                      and record.get("state") == "OBSERVED_PASS")
                if not ok:
                    failed.append(name)
            except (ValueError, TypeError):
                failed.append(name)
        return failed

    sample = missing(SAMPLE_RECORDS)
    production = missing(PRODUCTION_RECORDS)
    provider = missing(PROVIDER_RECORDS)
    return {"schema": "szl.readiness-levels/v1", "source_revision": source,
            "publisher_revision": publisher,
            "sample": "LIVE_VERIFIED_SAMPLE" if not sample else "BLOCKED",
            "production": "PRODUCTION_QUALIFIED" if not sample and not production else "HOLD",
            "provider": "QUALIFICATION_RECORDED_NOT_ENABLED" if not sample and not production and not provider else "HOLD",
            "missing_or_failing": {"sample": sample, "production": production, "provider": provider},
            "model_enablement_performed": False, "signature_verified_by_this_gate": False,
            "execution_authority": "NONE"}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect-publisher")
    inspect.add_argument("file", type=Path)
    archive = commands.add_parser("inspect-archive")
    archive.add_argument("file", type=Path)
    archive.add_argument("--sha256", required=True)
    archive.add_argument("--member", required=True)
    args = parser.parse_args(argv)
    if args.command == "inspect-publisher":
        result = inspect_publisher(args.file.read_text(encoding="utf-8"))
    else:
        result = inspect_archive(args.file, args.sha256, args.member)
        # Avoid dumping arbitrary archive data into a terminal/public job log.
        receipt = result.pop("receipt")
        result["receipt_sha256"] = digest(receipt)
        result["top_level_keys"] = sorted(receipt)
        result["complete"] = receipt.get("complete") is True
    print(json.dumps(result, indent=2, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
