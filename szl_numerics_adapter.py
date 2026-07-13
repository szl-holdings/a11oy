# SPDX-License-Identifier: Apache-2.0
"""Fail-closed external numerical-engine frontier.

The host accepts only three fixed numeric operations.  It never accepts source
code, expressions, function names, file paths, packages, or shell arguments.
GNU Octave is an optional external process.  MATLAB is an optional external
service executable with an offline-license status boundary; the proprietary
Python Engine is detected for status only and is never imported.  Neither
engine, its libraries, nor its license material is shipped by a11oy.

External execution is allowed only on POSIX when ``unshare --net`` and resource
limits are available.  The child runs with a private network namespace, a small
environment, a temporary working directory, and hard time/address-space/file-
size limits.  Missing controls produce ``UNAVAILABLE`` rather than a soft
fallback.  Results and receipts are deterministic hashes, always unsigned, and
never increase proof or trust state.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from starlette.requests import Request


REQUEST_SCHEMA = "szl.numerics.request/v1"
ENGINE_RESPONSE_SCHEMA = "szl.numerics.engine-response/v1"
RESULT_SCHEMA = "szl.numerics.result/v1"
COMPARE_SCHEMA = "szl.numerics.compare/v1"
RECEIPT_SCHEMA = "szl.numerics.receipt/v1"
OPERATIONS = ("MATRIX_SOLVE", "SYMMETRIC_EIGENVALUES", "VALIDATE_REFERENCE_VECTOR")
ENGINES = ("octave", "matlab")
MAX_BODY_BYTES = 128 * 1024
MAX_DIMENSION = 64
MAX_SCALARS = MAX_DIMENSION * MAX_DIMENSION + 2 * MAX_DIMENSION
MAX_ABS_VALUE = 1.0e12
MAX_TIMEOUT_SECONDS = 8
DEFAULT_TIMEOUT_SECONDS = 5
MAX_MEMORY_BYTES = 512 * 1024 * 1024
MAX_OUTPUT_BYTES = 256 * 1024
MAX_ABS_TOLERANCE = 1.0
MAX_REL_TOLERANCE = 1.0
ZERO_UPLIFT = {"proof_uplift": 0, "trust_uplift": 0}
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$")


class ContractError(ValueError):
    """The request or engine response violates the fixed contract."""


class EngineUnavailable(RuntimeError):
    """The external engine or a mandatory isolation control is unavailable."""


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def digest_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _mapping(value: Any, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ContractError(f"{name} must be an object")
    return value


def _strict_keys(value: Mapping[str, Any], allowed: set[str], name: str) -> None:
    extras = sorted(set(value) - allowed)
    missing = sorted(allowed - set(value))
    if extras:
        raise ContractError(f"{name} has unsupported fields: {', '.join(extras)}")
    if missing:
        raise ContractError(f"{name} is missing fields: {', '.join(missing)}")


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ContractError(f"{name} must be a finite JSON number")
    result = float(value)
    if not math.isfinite(result) or abs(result) > MAX_ABS_VALUE:
        raise ContractError(f"{name} must be finite with absolute value <= {MAX_ABS_VALUE:g}")
    return result


def _vector(value: Any, name: str, length: int | None = None) -> list[float]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ContractError(f"{name} must be an array")
    if not value or len(value) > MAX_DIMENSION:
        raise ContractError(f"{name} must contain 1..{MAX_DIMENSION} numbers")
    if length is not None and len(value) != length:
        raise ContractError(f"{name} must contain exactly {length} numbers")
    return [_number(item, f"{name}[{index}]") for index, item in enumerate(value)]


def _matrix(value: Any, name: str) -> list[list[float]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ContractError(f"{name} must be an array of rows")
    if not value or len(value) > MAX_DIMENSION:
        raise ContractError(f"{name} must contain 1..{MAX_DIMENSION} rows")
    size = len(value)
    rows = [_vector(row, f"{name}[{index}]", size) for index, row in enumerate(value)]
    return rows


def _tolerance(value: Any) -> dict[str, float]:
    obj = _mapping(value, "tolerance")
    _strict_keys(obj, {"absolute", "relative"}, "tolerance")
    absolute = _number(obj["absolute"], "tolerance.absolute")
    relative = _number(obj["relative"], "tolerance.relative")
    if not 0.0 <= absolute <= MAX_ABS_TOLERANCE:
        raise ContractError("tolerance.absolute must be between 0 and 1")
    if not 0.0 <= relative <= MAX_REL_TOLERANCE:
        raise ContractError("tolerance.relative must be between 0 and 1")
    return {"absolute": absolute, "relative": relative}


def parse_request(payload: Mapping[str, Any]) -> dict[str, Any]:
    obj = _mapping(payload, "request")
    _strict_keys(obj, {"schema", "request_id", "operation", "inputs", "tolerance"}, "request")
    if obj["schema"] != REQUEST_SCHEMA:
        raise ContractError(f"schema must be {REQUEST_SCHEMA}")
    request_id = obj["request_id"]
    if not isinstance(request_id, str) or not _REQUEST_ID_RE.fullmatch(request_id):
        raise ContractError("request_id must match [A-Za-z0-9][A-Za-z0-9._:-]{0,63}")
    operation = obj["operation"]
    if operation not in OPERATIONS:
        raise ContractError(f"operation must be one of: {', '.join(OPERATIONS)}")
    raw_inputs = _mapping(obj["inputs"], "inputs")
    if operation == "SYMMETRIC_EIGENVALUES":
        _strict_keys(raw_inputs, {"matrix"}, "inputs")
    elif operation == "MATRIX_SOLVE":
        _strict_keys(raw_inputs, {"matrix", "rhs"}, "inputs")
    else:
        _strict_keys(raw_inputs, {"matrix", "rhs", "expected"}, "inputs")

    matrix = _matrix(raw_inputs["matrix"], "inputs.matrix")
    size = len(matrix)
    inputs: dict[str, Any] = {"matrix": matrix}
    if operation == "SYMMETRIC_EIGENVALUES":
        for row in range(size):
            for column in range(row + 1, size):
                if abs(matrix[row][column] - matrix[column][row]) > 1.0e-12:
                    raise ContractError("SYMMETRIC_EIGENVALUES requires a symmetric matrix")
    else:
        inputs["rhs"] = _vector(raw_inputs["rhs"], "inputs.rhs", size)
    if operation == "VALIDATE_REFERENCE_VECTOR":
        inputs["expected"] = _vector(raw_inputs["expected"], "inputs.expected", size)
    if sum(len(row) for row in matrix) + sum(
        len(value) for value in inputs.values() if isinstance(value, list) and value and not isinstance(value[0], list)
    ) > MAX_SCALARS:
        raise ContractError("request exceeds the scalar ceiling")
    return {
        "schema": REQUEST_SCHEMA,
        "request_id": request_id,
        "operation": operation,
        "inputs": inputs,
        "tolerance": _tolerance(obj["tolerance"]),
    }


def _configured_executable(name: str, env_key: str) -> str | None:
    configured = os.environ.get(env_key, "").strip()
    if configured:
        path = Path(configured)
        return str(path.resolve()) if path.is_absolute() and path.is_file() else None
    discovered = shutil.which(name)
    return str(Path(discovered).resolve()) if discovered else None


def _controls() -> dict[str, Any]:
    try:
        import resource  # noqa: F401
        resource_limits = os.name == "posix"
    except ImportError:
        resource_limits = False
    unshare = shutil.which("unshare") if os.name == "posix" else None
    return {
        "network_isolation": "PRESENT_UNVERIFIED" if unshare else "SOURCE_UNAVAILABLE",
        "network_launcher": str(Path(unshare).resolve()) if unshare else None,
        "resource_limits": "PRESENT" if resource_limits else "SOURCE_UNAVAILABLE",
        "memory_limit_bytes": MAX_MEMORY_BYTES,
        "output_limit_bytes": MAX_OUTPUT_BYTES,
        "timeout_limit_seconds": MAX_TIMEOUT_SECONDS,
        "package_installs": "DISABLED",
        "arbitrary_code": "DISABLED",
    }


def engine_status() -> dict[str, Any]:
    controls = _controls()
    controls_ready = bool(controls["network_launcher"] and controls["resource_limits"] == "PRESENT")
    octave = _configured_executable("octave-cli", "A11OY_OCTAVE_EXECUTABLE")
    matlab_service = _configured_executable("", "A11OY_MATLAB_SERVICE_EXECUTABLE")
    # Looking up the top-level package is status-only and does not import it.
    # Looking up ``matlab.engine`` could import its parent as a side effect.
    matlab_engine = importlib.util.find_spec("matlab") is not None
    matlab_offline_license = os.environ.get("A11OY_MATLAB_OFFLINE_LICENSE_CONFIGURED") == "1"
    return {
        "schema": "szl.numerics.status/v1",
        "mode": "EXTERNAL_ENGINES_ONLY",
        "substrate_evidence": "UNKNOWN",
        "engines": {
            "octave": {
                "execution_state": "READY_TO_ATTEMPT" if octave and controls_ready else "UNAVAILABLE",
                "executable": "PRESENT_UNVERIFIED" if octave else "SOURCE_UNAVAILABLE",
                "executable_path": octave,
                "license_boundary": "EXTERNAL_GPL_PROCESS_NOT_BUNDLED",
            },
            "matlab": {
                "execution_state": "READY_TO_ATTEMPT" if matlab_service and matlab_offline_license and controls_ready else "UNAVAILABLE",
                "service_executable": "PRESENT_UNVERIFIED" if matlab_service else "SOURCE_UNAVAILABLE",
                "service_executable_path": matlab_service,
                "python_engine_package": "PRESENT_STATUS_ONLY_NOT_IMPORTED" if matlab_engine else "SOURCE_UNAVAILABLE",
                "offline_license_configuration": "CONFIGURED_UNVERIFIED" if matlab_offline_license else "SOURCE_UNAVAILABLE",
                "license_boundary": "EXTERNAL_PROPRIETARY_SERVICE_NOT_BUNDLED",
            },
        },
        "controls": controls,
        "operations": list(OPERATIONS),
        "limits": {
            "max_body_bytes": MAX_BODY_BYTES,
            "max_dimension": MAX_DIMENSION,
            "max_scalars": MAX_SCALARS,
            "max_abs_value": MAX_ABS_VALUE,
        },
        **ZERO_UPLIFT,
    }


def _preexec_limits(timeout_seconds: int) -> Callable[[], None]:
    def apply() -> None:
        import resource

        resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_BYTES, MAX_MEMORY_BYTES))
        resource.setrlimit(resource.RLIMIT_CPU, (timeout_seconds, timeout_seconds))
        resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_OUTPUT_BYTES, MAX_OUTPUT_BYTES))
        resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))

    return apply


def _read_bounded(path: Path) -> bytes:
    size = path.stat().st_size
    if size > MAX_OUTPUT_BYTES:
        raise EngineUnavailable("ENGINE_OUTPUT_LIMIT_EXCEEDED")
    return path.read_bytes()


def _engine_command(engine: str, input_path: Path, output_path: Path) -> list[str]:
    status = engine_status()
    details = status["engines"][engine]
    if details["execution_state"] != "READY_TO_ATTEMPT":
        raise EngineUnavailable("ENGINE_OR_ISOLATION_CONTROL_UNAVAILABLE")
    if engine == "octave":
        script = Path(__file__).resolve().parent / "numerics" / "octave_adapter.m"
        if not script.is_file():
            raise EngineUnavailable("FIXED_OCTAVE_ADAPTER_SOURCE_UNAVAILABLE")
        command = [details["executable_path"], "--quiet", "--no-gui", "--no-history", str(script), str(input_path), str(output_path)]
    else:
        command = [details["service_executable_path"], "--json-input", str(input_path), "--json-output", str(output_path)]
    return [status["controls"]["network_launcher"], "--net", "--", *command]


def _execute_external(engine: str, request: Mapping[str, Any], timeout_seconds: int) -> Mapping[str, Any]:
    if engine not in ENGINES:
        raise ContractError(f"engine must be one of: {', '.join(ENGINES)}")
    if not 1 <= timeout_seconds <= MAX_TIMEOUT_SECONDS:
        raise ContractError(f"timeout_seconds must be between 1 and {MAX_TIMEOUT_SECONDS}")
    if os.name != "posix":
        raise EngineUnavailable("POSIX_RESOURCE_AND_NETWORK_ISOLATION_UNAVAILABLE")
    with tempfile.TemporaryDirectory(prefix="a11oy-numerics-") as tmp:
        work = Path(tmp)
        input_path = work / "request.json"
        output_path = work / "response.json"
        log_path = work / "engine.log"
        input_path.write_bytes(canonical_json(request))
        command = _engine_command(engine, input_path, output_path)
        env = {
            "HOME": str(work),
            "TMPDIR": str(work),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "OCTAVE_HISTFILE": os.devnull,
            "PATH": "/usr/bin:/bin",
        }
        try:
            with log_path.open("wb") as log:
                completed = subprocess.run(
                    command,
                    cwd=work,
                    env=env,
                    stdin=subprocess.DEVNULL,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    shell=False,
                    timeout=timeout_seconds,
                    check=False,
                    preexec_fn=_preexec_limits(timeout_seconds),
                )
        except subprocess.TimeoutExpired as exc:
            raise EngineUnavailable("ENGINE_TIMEOUT") from exc
        except OSError as exc:
            raise EngineUnavailable("ENGINE_START_FAILED") from exc
        _read_bounded(log_path)
        if completed.returncode != 0:
            raise EngineUnavailable(f"ENGINE_EXIT_{completed.returncode}")
        if not output_path.is_file():
            raise EngineUnavailable("ENGINE_RESPONSE_UNAVAILABLE")
        try:
            response = json.loads(_read_bounded(output_path).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EngineUnavailable("ENGINE_RESPONSE_INVALID_JSON") from exc
        return _mapping(response, "engine response")


def _parse_engine_response(value: Mapping[str, Any], request: Mapping[str, Any]) -> list[float]:
    obj = _mapping(value, "engine response")
    _strict_keys(obj, {"schema", "state", "operation", "values", "substrate_evidence"}, "engine response")
    if obj["schema"] != ENGINE_RESPONSE_SCHEMA or obj["state"] != "RESULT":
        raise EngineUnavailable("ENGINE_RESPONSE_NOT_RESULT")
    if obj["operation"] != request["operation"]:
        raise EngineUnavailable("ENGINE_OPERATION_MISMATCH")
    if obj["substrate_evidence"] not in ("MEASURED", "UNKNOWN"):
        raise EngineUnavailable("ENGINE_SUBSTRATE_LABEL_INVALID")
    values = _vector(obj["values"], "engine response.values", len(request["inputs"]["matrix"]))
    return values


def _within(left: float, right: float, tolerance: Mapping[str, float]) -> bool:
    return abs(left - right) <= tolerance["absolute"] + tolerance["relative"] * max(abs(left), abs(right))


def _receipt(kind: str, engine: str | None, request_digest: str, result: Mapping[str, Any]) -> dict[str, Any]:
    body = {
        "schema": RECEIPT_SCHEMA,
        "kind": kind,
        "engine": engine,
        "request_sha256": request_digest,
        "result_sha256": digest_json(result),
        "signature_state": "UNSIGNED_DETERMINISTIC_DIGEST_ONLY",
        **ZERO_UPLIFT,
    }
    return {**body, "receipt_sha256": digest_json(body)}


Executor = Callable[[Mapping[str, Any]], Mapping[str, Any]]


def run_engine(
    engine: str,
    payload: Mapping[str, Any],
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    executor: Executor | None = None,
) -> dict[str, Any]:
    if engine not in ENGINES:
        raise ContractError(f"engine must be one of: {', '.join(ENGINES)}")
    request = parse_request(payload)
    request_digest = digest_json(request)
    try:
        raw = executor(request) if executor is not None else _execute_external(engine, request, timeout_seconds)
        values = _parse_engine_response(raw, request)
        reference = None
        if request["operation"] == "VALIDATE_REFERENCE_VECTOR":
            reference = "MATCH" if all(
                _within(value, expected, request["tolerance"])
                for value, expected in zip(values, request["inputs"]["expected"])
            ) else "CONFLICT"
        core = {
            "schema": RESULT_SCHEMA,
            "state": "RESULT",
            "engine": engine,
            "request_id": request["request_id"],
            "request_sha256": request_digest,
            "operation": request["operation"],
            "values": values,
            "reference_validation": reference,
            "substrate_evidence": "UNKNOWN",
            "signature_state": "UNSIGNED",
            **ZERO_UPLIFT,
        }
    except EngineUnavailable as exc:
        core = {
            "schema": RESULT_SCHEMA,
            "state": "UNAVAILABLE",
            "engine": engine,
            "request_id": request["request_id"],
            "request_sha256": request_digest,
            "operation": request["operation"],
            "reason": str(exc),
            "substrate_evidence": "UNKNOWN",
            "signature_state": "UNSIGNED",
            **ZERO_UPLIFT,
        }
    return {**core, "receipt": _receipt("ENGINE_RUN", engine, request_digest, core)}


def compare_engines(
    payload: Mapping[str, Any],
    *,
    executors: Mapping[str, Executor] | None = None,
) -> dict[str, Any]:
    request = parse_request(payload)
    request_digest = digest_json(request)
    configured = executors or {}
    results = {
        engine: run_engine(engine, request, executor=configured.get(engine))
        for engine in ENGINES
    }
    if any(result["state"] != "RESULT" for result in results.values()):
        state = "UNAVAILABLE"
        metrics = None
    else:
        octave_values = results["octave"]["values"]
        matlab_values = results["matlab"]["values"]
        differences = [abs(left - right) for left, right in zip(octave_values, matlab_values)]
        state = "MATCH" if all(
            _within(left, right, request["tolerance"])
            for left, right in zip(octave_values, matlab_values)
        ) else "CONFLICT"
        metrics = {
            "max_absolute_difference": max(differences, default=0.0),
            "declared_tolerance": request["tolerance"],
        }
    core = {
        "schema": COMPARE_SCHEMA,
        "comparison_state": state,
        "request_id": request["request_id"],
        "request_sha256": request_digest,
        "operation": request["operation"],
        "engine_states": {engine: result["state"] for engine, result in results.items()},
        "engine_result_sha256": {engine: result["receipt"]["result_sha256"] for engine, result in results.items()},
        "metrics": metrics,
        "substrate_evidence": "UNKNOWN",
        "signature_state": "UNSIGNED",
        **ZERO_UPLIFT,
    }
    return {**core, "receipt": _receipt("CROSS_ENGINE_COMPARE", None, request_digest, core)}


async def _bounded_json_body(request: Any) -> dict[str, Any]:
    declared = request.headers.get("content-length")
    if declared is not None:
        try:
            size = int(declared)
        except ValueError as exc:
            raise ContractError("content-length must be a non-negative integer") from exc
        if size < 0:
            raise ContractError("content-length must be a non-negative integer")
        if size > MAX_BODY_BYTES:
            raise ContractError("request body exceeds 128 KiB")
    data = bytearray()
    async for chunk in request.stream():
        if len(data) + len(chunk) > MAX_BODY_BYTES:
            raise ContractError("request body exceeds 128 KiB")
        data.extend(chunk)
    try:
        value = json.loads(bytes(data).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ContractError("request body must be one JSON object") from exc
    if not isinstance(value, dict):
        raise ContractError("request body must be one JSON object")
    return value


def register(app: Any, ns: str = "a11oy") -> dict[str, Any]:
    """Register the fixed status/run/compare routes on a FastAPI application."""

    from fastapi.responses import JSONResponse

    prefix = f"/api/{ns}/v1/numerics"

    @app.get(f"{prefix}/status")
    async def numerics_status() -> JSONResponse:
        return JSONResponse(engine_status())

    @app.post(f"{prefix}/run/{{engine}}")
    async def numerics_run(engine: str, request: Request) -> JSONResponse:
        try:
            result = run_engine(engine, await _bounded_json_body(request))
        except ContractError as exc:
            return JSONResponse({"state": "REJECTED", "error": str(exc), "substrate_evidence": "UNKNOWN", **ZERO_UPLIFT}, status_code=422)
        return JSONResponse(result, status_code=200 if result["state"] == "RESULT" else 503)

    @app.post(f"{prefix}/compare")
    async def numerics_compare(request: Request) -> JSONResponse:
        try:
            result = compare_engines(await _bounded_json_body(request))
        except ContractError as exc:
            return JSONResponse({"comparison_state": "REJECTED", "error": str(exc), "substrate_evidence": "UNKNOWN", **ZERO_UPLIFT}, status_code=422)
        return JSONResponse(result, status_code=200 if result["comparison_state"] in ("MATCH", "CONFLICT") else 503)

    return {
        "registered": True,
        "routes": [f"{prefix}/status", f"{prefix}/run/{{engine}}", f"{prefix}/compare"],
        "engines_bundled": 0,
        **ZERO_UPLIFT,
    }


__all__ = [
    "COMPARE_SCHEMA",
    "ContractError",
    "ENGINE_RESPONSE_SCHEMA",
    "ENGINES",
    "OPERATIONS",
    "REQUEST_SCHEMA",
    "compare_engines",
    "digest_json",
    "engine_status",
    "parse_request",
    "register",
    "run_engine",
]
