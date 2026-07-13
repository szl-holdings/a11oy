# SPDX-License-Identifier: Apache-2.0
"""Fail-closed executor for the preregistered MATLAB/Octave comparison.

Taxonomy home: services/numerics.  The frozen 1,328-case design is read from
``szl_numerics_dataset``.  A run starts only when both external engines, POSIX
resource limits, a fresh ``unshare --net`` namespace, explicit operator
license review, and a 100-decimal-place mpmath reference are available.
Missing evidence produces a blocker receipt and zero engine invocations.

This module never installs or bundles MATLAB, Octave, mpmath, licenses, model
weights, or datasets.  ``MATCH`` means bounded agreement for one frozen case;
it is not mathematical proof or general correctness.
"""

import argparse
import datetime as _datetime
import hashlib
import importlib
import json
import os
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable, Mapping

import szl_numerics_adapter as _adapter
import szl_numerics_dataset as _dataset


PREFLIGHT_SCHEMA = "szl.numerics.experiment-preflight/v1"
EXPERIMENT_SCHEMA = "szl.numerics.preregistered-experiment/v1"
REFERENCE_SCHEMA = "szl.numerics.mpmath-reference/v1"
ZERO_UPLIFT = {"proof_uplift": 0, "trust_uplift": 0}
_ROOT = Path(__file__).resolve().parent
_ISOLATION_HELPER = _ROOT / "numerics" / "isolation_probe.py"
_MAX_VERSION_OUTPUT_BYTES = 64 * 1024


class ExperimentUnavailable(RuntimeError):
    """A mandatory execution or evidence boundary is unavailable."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _utc_now() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _child_env(work: Path) -> dict[str, str]:
    """Return the fixed, secret-free environment for evidence-only children."""

    return {
        "HOME": str(work),
        "TMPDIR": str(work),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "PATH": "/usr/bin:/bin",
    }


def experiment_plan() -> dict[str, Any]:
    manifest = _dataset.preregistration()
    return {
        "protocol_id": manifest["protocol_id"],
        "protocol_version": manifest["protocol_version"],
        "preregistration_sha256": _adapter.digest_json(manifest),
        "frozen_before_execution": manifest["frozen_before_execution"],
        "matrix_families": [item["id"] for item in manifest["confirmatory_matrix_families"]],
        "exploratory_families": [item["id"] for item in manifest["exploratory_matrix_families"]],
        "dimensions": manifest["matrix_dimensions"],
        "condition_number_strata": manifest["condition_number_strata"],
        "seeds": manifest["deterministic_seeds"],
        "tolerance": manifest["tolerance"],
        "engines": manifest["engines"],
        "case_counts": manifest["expected_case_counts"],
        "planned_engine_runs": manifest["expected_case_counts"]["total"] * len(manifest["engines"]),
        "result_claim": "NO_ENGINE_RESULT_IN_PLAN",
    }


def _mpmath_status() -> dict[str, Any]:
    try:
        module = importlib.import_module("mpmath")
    except (ImportError, OSError):
        return {"state": "UNAVAILABLE", "version": None}
    version = str(getattr(module, "__version__", "")).strip()
    if not version:
        return {"state": "UNAVAILABLE", "version": None}
    return {"state": "AVAILABLE_UNPROBED", "version": version}


def _engine_path(status: Mapping[str, Any], engine: str) -> Path | None:
    details = status["engines"][engine]
    raw = details.get("executable_path") if engine == "octave" else details.get("service_executable_path")
    if not raw:
        return None
    path = Path(str(raw))
    return path if path.is_absolute() and path.is_file() else None


def preflight(
    *,
    status: Mapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    os_name: str | None = None,
    mpmath_status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    environment = os.environ if environ is None else environ
    runtime = dict(_adapter.engine_status() if status is None else status)
    host_os = os.name if os_name is None else os_name
    controls = runtime["controls"]
    reasons: list[str] = []
    if host_os != "posix":
        reasons.append("POSIX_RESOURCE_AND_NETWORK_ISOLATION_UNAVAILABLE")
    if not controls.get("network_launcher"):
        reasons.append("NETWORK_NAMESPACE_LAUNCHER_UNAVAILABLE")
    if controls.get("resource_limits") != "PRESENT":
        reasons.append("POSIX_RESOURCE_LIMITS_UNAVAILABLE")
    engines: dict[str, Any] = {}
    for engine in ("octave", "matlab"):
        path = _engine_path(runtime, engine)
        reviewed = environment.get(f"A11OY_{engine.upper()}_LICENSE_REVIEWED") == "1"
        state = runtime["engines"][engine].get("execution_state", "UNAVAILABLE")
        if state != "READY_TO_ATTEMPT" or path is None:
            reasons.append(f"{engine.upper()}_ENGINE_UNAVAILABLE")
        if not reviewed:
            reasons.append(f"{engine.upper()}_LICENSE_REVIEW_UNAVAILABLE")
        engines[engine] = {
            "execution_state": state,
            "executable_sha256": _sha256_file(path) if path is not None else None,
            "license_review": "OPERATOR_REVIEWED" if reviewed else "REVIEW_REQUIRED",
            "offline_license_state": (
                "CONFIGURED_UNVERIFIED"
                if engine == "matlab" and runtime["engines"][engine].get("offline_license_configuration") == "CONFIGURED_UNVERIFIED"
                else ("NOT_APPLICABLE" if engine == "octave" else "UNAVAILABLE")
            ),
        }
    reference = dict(_mpmath_status() if mpmath_status is None else mpmath_status)
    if reference.get("state") == "UNAVAILABLE":
        reasons.append("MPMATH_100DP_REFERENCE_UNAVAILABLE")
    core = {
        "schema": PREFLIGHT_SCHEMA,
        "state": "READY_TO_PROBE" if not reasons else "BLOCKED",
        "observed_at_utc": _utc_now(),
        "host": {
            "os_name": host_os,
            "system": platform.system(),
            "machine": platform.machine(),
            "python": platform.python_version(),
        },
        "plan": experiment_plan(),
        "engines": engines,
        "controls": {
            "network_isolation": controls.get("network_isolation", "SOURCE_UNAVAILABLE"),
            "network_launcher_sha256": _sha256_file(Path(controls["network_launcher"])) if controls.get("network_launcher") and Path(controls["network_launcher"]).is_file() else None,
            "resource_limits": controls.get("resource_limits", "SOURCE_UNAVAILABLE"),
            "memory_limit_bytes": controls.get("memory_limit_bytes"),
            "output_limit_bytes": controls.get("output_limit_bytes"),
            "timeout_limit_seconds": controls.get("timeout_limit_seconds"),
        },
        "reference": {**reference, "precision_decimal_digits": 100},
        "blockers": sorted(set(reasons)),
        "engine_invocations": 0,
        "result_rows": 0,
        "network_denial_evidence": "NOT_EVALUATED",
        "substrate_evidence": "UNKNOWN",
        "interpretation_guard": "A ready preflight is permission to probe, not an engine result or agreement claim.",
        **ZERO_UPLIFT,
    }
    return {**core, "receipt_sha256": _adapter.digest_json(core)}


def _isolation_probe(status: Mapping[str, Any]) -> dict[str, Any]:
    if os.name != "posix" or not _ISOLATION_HELPER.is_file():
        raise ExperimentUnavailable("NETWORK_NAMESPACE_EVIDENCE_UNAVAILABLE")
    launcher = status["controls"].get("network_launcher")
    if not launcher:
        raise ExperimentUnavailable("NETWORK_NAMESPACE_EVIDENCE_UNAVAILABLE")
    parent_namespace = os.readlink("/proc/self/ns/net")
    with tempfile.TemporaryDirectory(prefix="a11oy-numerics-netprobe-") as tmp:
        evidence_path = Path(tmp) / "network-evidence.json"
        command = [launcher, "--net", "--", sys.executable, "-I", str(_ISOLATION_HELPER), str(evidence_path)]
        try:
            completed = subprocess.run(
                command,
                cwd=tmp,
                env=_child_env(Path(tmp)),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                timeout=5,
                check=False,
                preexec_fn=_adapter._preexec_limits(5),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ExperimentUnavailable("NETWORK_NAMESPACE_PROBE_FAILED") from exc
        if completed.returncode != 0 or not evidence_path.is_file() or evidence_path.stat().st_size > 16 * 1024:
            raise ExperimentUnavailable("NETWORK_NAMESPACE_PROBE_FAILED")
        try:
            child = json.loads(evidence_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ExperimentUnavailable("NETWORK_NAMESPACE_EVIDENCE_INVALID") from exc
    if child.get("schema") != "szl.numerics.network-namespace-evidence/v1":
        raise ExperimentUnavailable("NETWORK_NAMESPACE_EVIDENCE_INVALID")
    if child.get("network_operations_performed") != 0 or child.get("network_namespace") == parent_namespace:
        raise ExperimentUnavailable("NETWORK_NAMESPACE_NOT_SEPARATE")
    if child.get("interfaces") != ["lo"] or child.get("loopback_operstate") not in ("down", "unknown"):
        raise ExperimentUnavailable("NETWORK_NAMESPACE_NOT_DENY_BY_DEFAULT")
    core = {
        **child,
        "state": "DENIED",
        "parent_network_namespace": parent_namespace,
        "launcher_sha256": _sha256_file(Path(launcher)),
        "helper_sha256": _sha256_file(_ISOLATION_HELPER),
    }
    return {**core, "evidence_sha256": _adapter.digest_json(core)}


def _probe_engine_version(engine: str, status: Mapping[str, Any]) -> dict[str, Any]:
    path = _engine_path(status, engine)
    launcher = status["controls"].get("network_launcher")
    if path is None or not launcher:
        raise ExperimentUnavailable(f"{engine.upper()}_VERSION_PROBE_UNAVAILABLE")
    if engine == "octave":
        command = [launcher, "--net", "--", str(path), "--version"]
    else:
        command = [launcher, "--net", "--", str(path), "--version"]
    try:
        with tempfile.TemporaryDirectory(prefix=f"a11oy-numerics-{engine}-version-") as tmp:
            completed = subprocess.run(
                command,
                cwd=tmp,
                env=_child_env(Path(tmp)),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                shell=False,
                timeout=8,
                check=False,
                preexec_fn=_adapter._preexec_limits(8),
            )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ExperimentUnavailable(f"{engine.upper()}_VERSION_PROBE_FAILED") from exc
    output = completed.stdout or b""
    if completed.returncode != 0 or not output or len(output) > _MAX_VERSION_OUTPUT_BYTES:
        raise ExperimentUnavailable(f"{engine.upper()}_VERSION_PROBE_FAILED")
    try:
        lines = [line.strip() for line in output.decode("utf-8").splitlines() if line.strip()]
    except UnicodeDecodeError as exc:
        raise ExperimentUnavailable(f"{engine.upper()}_VERSION_PROBE_INVALID") from exc
    if not lines or len(lines[0]) > 120:
        raise ExperimentUnavailable(f"{engine.upper()}_VERSION_PROBE_INVALID")
    return {
        "version": lines[0],
        "version_evidence_sha256": _sha256_bytes(output),
        "executable_sha256": _sha256_file(path),
    }


def _iter_cases() -> Iterable[dict[str, Any]]:
    offset = 0
    total = experiment_plan()["case_counts"]["total"]
    while offset < total:
        page = _dataset.list_cases(offset=offset, limit=min(100, total - offset))
        for descriptor in page["items"]:
            yield _dataset.get_case(descriptor["case_id"])
        offset += len(page["items"])
        if not page["items"]:
            raise ExperimentUnavailable("PREREGISTERED_CASE_ENUMERATION_INCOMPLETE")


def _reference(case: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    try:
        mp = importlib.import_module("mpmath")
    except ImportError as exc:
        raise ExperimentUnavailable("MPMATH_100DP_REFERENCE_UNAVAILABLE") from exc
    mp.mp.dps = 100
    matrix = mp.matrix([[mp.mpf(format(value, ".17g")) for value in row] for row in case["request"]["inputs"]["matrix"]])
    operation = case["operation"]
    if operation == "SYMMETRIC_EIGENVALUES":
        computed = mp.eigsy(matrix, eigvals_only=True)
        values_mp = [computed[index] for index in range(len(computed))]
    else:
        rhs = mp.matrix([mp.mpf(format(value, ".17g")) for value in case["request"]["inputs"]["rhs"]])
        computed = mp.lu_solve(matrix, rhs)
        values_mp = [computed[index] for index in range(len(computed))]
    decimal_values = [mp.nstr(value, 105, strip_zeros=False) for value in values_mp]
    evidence_core = {
        "schema": REFERENCE_SCHEMA,
        "case_id": case["case_id"],
        "fixture_sha256": case["fixture_sha256"],
        "implementation": "PYTHON_MPMATH_100DP",
        "mpmath_version": str(mp.__version__),
        "precision_decimal_digits": 100,
        "decimal_values": decimal_values,
    }
    evidence_sha256 = _adapter.digest_json(evidence_core)
    return (
        {
            "state": "MEASURED",
            "implementation": "PYTHON_MPMATH_100DP",
            "values": [float(value) for value in values_mp],
            "evidence_sha256": evidence_sha256,
        },
        {**evidence_core, "evidence_sha256": evidence_sha256},
    )


def _child_cpu_snapshot() -> tuple[int | None, int | None]:
    try:
        import resource

        usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    except (ImportError, OSError):
        return None, None
    return int(usage.ru_utime * 1_000_000_000), int(usage.ru_stime * 1_000_000_000)


def _observe_case(
    engine: str,
    case: Mapping[str, Any],
    version: Mapping[str, Any],
    isolation: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    request = case["request"]
    before_user, before_system = _child_cpu_snapshot()
    started = time.perf_counter_ns()
    result = _adapter.run_engine(engine, request)
    elapsed = time.perf_counter_ns() - started
    after_user, after_system = _child_cpu_snapshot()
    user_ns = after_user - before_user if before_user is not None and after_user is not None else None
    system_ns = after_system - before_system if before_system is not None and after_system is not None else None
    reference, reference_evidence = _reference(case)
    outcome = (
        {"state": "RESULT", "values": result["values"]}
        if result["state"] == "RESULT"
        else {"state": "UNAVAILABLE", "reason": str(result.get("reason") or "ENGINE_UNAVAILABLE")[:160]}
    )
    # Keep the append-ledger identifier inside the strict 96-character ID
    # boundary without sacrificing uniqueness or reproducibility.  The case
    # request digest is frozen by the preregistration.
    run_id = f"{engine}-{str(case['case_id'])[:40]}-{str(case['request_sha256'])[:16]}"
    payload = {
        "schema": _dataset.INGEST_SCHEMA,
        "run_id": run_id,
        "case_id": case["case_id"],
        "engine": engine,
        "outcome": outcome,
        "engine_evidence": {
            **version,
            "license_state": "OPERATOR_REVIEWED",
            "offline_license_state": "CONFIGURED" if engine == "matlab" else "NOT_APPLICABLE",
        },
        "containment": {"network_state": "DENIED", "evidence_sha256": isolation["evidence_sha256"]},
        "resources": {
            "wall_time_ns": elapsed,
            "child_user_cpu_ns": user_ns,
            "child_system_cpu_ns": system_ns,
            "peak_resident_bytes": None,
            "request_bytes": len(_adapter.canonical_json(request)),
            "response_bytes": len(_adapter.canonical_json(result)),
            "log_bytes": None,
        },
        "reference": reference,
        "observed_at_utc": _utc_now(),
    }
    return _dataset.ingest_result(payload), reference_evidence


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    encoded = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def run_preregistered(*, execute_all: bool = False) -> dict[str, Any]:
    check = preflight()
    core: dict[str, Any] = {
        "schema": EXPERIMENT_SCHEMA,
        "state": "BLOCKED" if check["state"] == "BLOCKED" else ("READY_NOT_EXECUTED" if not execute_all else "RUNNING"),
        "observed_at_utc": _utc_now(),
        "plan": check["plan"],
        "preflight_receipt_sha256": check["receipt_sha256"],
        "preflight": check,
        "engine_invocations": 0,
        "engine_invocation_semantics": "ADAPTER_CALLS; CHILD_PROCESS_STARTS_NOT_INDEPENDENTLY_COUNTED",
        "result_rows": 0,
        "pair_outcomes": {"MATCH": 0, "CONFLICT": 0, "UNAVAILABLE": 0},
        "reference_rows": 0,
        "substrate_evidence": "UNKNOWN",
        "interpretation_guard": "MATCH is case-scoped numerical agreement, not proof or a general engine-quality claim.",
        **ZERO_UPLIFT,
    }
    if check["state"] == "BLOCKED" or not execute_all:
        return {**core, "receipt_sha256": _adapter.digest_json(core)}

    runtime = _adapter.engine_status()
    try:
        isolation = _isolation_probe(runtime)
        versions = {engine: _probe_engine_version(engine, runtime) for engine in ("octave", "matlab")}
    except ExperimentUnavailable as exc:
        core.update({"state": "BLOCKED", "blocker": str(exc)})
        return {**core, "receipt_sha256": _adapter.digest_json(core)}

    reference_chain: list[dict[str, Any]] = []
    outcomes = {"MATCH": 0, "CONFLICT": 0, "UNAVAILABLE": 0}
    invocations = 0
    result_rows = 0
    for case in _iter_cases():
        pair: list[dict[str, Any]] = []
        for engine in ("octave", "matlab"):
            row, reference_evidence = _observe_case(engine, case, versions[engine], isolation)
            invocations += 1
            result_rows += 1
            pair.append(row)
            if not reference_chain or reference_chain[-1]["case_id"] != case["case_id"]:
                reference_chain.append(reference_evidence)
        final_state = pair[-1]["comparison_state"] if pair[-1]["comparison_state"] in ("MATCH", "CONFLICT") else "UNAVAILABLE"
        outcomes[final_state] += 1

    complete = (
        result_rows == core["plan"]["planned_engine_runs"]
        and sum(outcomes.values()) == core["plan"]["case_counts"]["total"]
        and outcomes["UNAVAILABLE"] == 0
    )
    core.update({
        "state": "COMPLETE" if complete else "INCOMPLETE",
        "engine_invocations": invocations,
        "result_rows": result_rows,
        "pair_outcomes": outcomes,
        "reference_rows": len(reference_chain),
        "reference_evidence": reference_chain,
        "reference_chain_sha256": _adapter.digest_json(reference_chain),
        "network_denial_evidence_sha256": isolation["evidence_sha256"],
        "engine_versions": versions,
        "substrate_evidence": "UNKNOWN",
    })
    return {**core, "receipt_sha256": _adapter.digest_json(core)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run or preflight the frozen MATLAB/Octave comparison")
    parser.add_argument("--execute-all", action="store_true", help="run all 1,328 cases on both engines after every gate passes")
    parser.add_argument("--output", type=Path, required=True, help="write one atomic JSON experiment receipt")
    args = parser.parse_args(argv)
    receipt = run_preregistered(execute_all=args.execute_all)
    _write_json(args.output, receipt)
    print(json.dumps({"state": receipt["state"], "receipt_sha256": receipt["receipt_sha256"]}, sort_keys=True))
    return 0 if receipt["state"] in ("READY_NOT_EXECUTED", "COMPLETE") else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "EXPERIMENT_SCHEMA",
    "PREFLIGHT_SCHEMA",
    "ExperimentUnavailable",
    "experiment_plan",
    "preflight",
    "run_preregistered",
]
