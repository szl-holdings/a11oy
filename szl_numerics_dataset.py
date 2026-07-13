# SPDX-License-Identifier: Apache-2.0
"""Deterministic, evidence-typed numerical evaluator dataset service.

Taxonomy home: services/numerics.  This module freezes and serves the
preregistered matrix-case design, accepts only authenticated bounded run
receipts, computes binary64 diagnostics, and appends an integrity-linked row to
an NDJSON ledger.  It does not invoke MATLAB or Octave, does not infer engine or
network availability, and never increases proof or trust state.
"""

import datetime as _datetime
import hashlib
import hmac
import json
import math
import os
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import szl_numerics_adapter as _adapter
import szl_puriq_formulas as _puriq
from starlette.requests import Request


PREREGISTRATION_SCHEMA = "szl.numerics.dataset-preregistration/v1"
INGEST_SCHEMA = "szl.numerics.dataset-ingest/v1"
CASE_SCHEMA = "szl.numerics.dataset-case/v1"
ROW_SCHEMA = "szl.numerics.dataset-row/v1"
STATUS_SCHEMA = "szl.numerics.dataset-status/v1"
CURRICULUM_SCHEMA = "szl.numerics.formula-curriculum/v1"
MAX_LEDGER_ROWS = 10_000
MAX_LEDGER_BYTES = 64 * 1024 * 1024
MAX_ROW_BYTES = 64 * 1024
MAX_PAGE_SIZE = 100
ZERO_UPLIFT = {"proof_uplift": 0, "trust_uplift": 0}
_ROOT = Path(__file__).resolve().parent
_MANIFEST_PATH = _ROOT / "numerics" / "dataset_preregistration.json"
_FORMULA_SOURCE_PATH = _ROOT / "szl_puriq_formulas.py"
_LICENSE_PATH = _ROOT / "LICENSE"
_LOCKED_FORMULA_IDS = frozenset({"F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"})
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$")
_CASE_RE = re.compile(r"^case-[a-z0-9-]{8,120}$")
_LEDGER_LOCK = threading.Lock()
_MASK64 = (1 << 64) - 1


class DatasetContractError(ValueError):
    """A case selector or ingested row violates the frozen contract."""


class DatasetUnavailable(RuntimeError):
    """A mandatory dataset service precondition is unavailable."""


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _formula_source_family(meta: Mapping[str, Any]) -> str:
    organ = str(meta.get("organ") or "source-unavailable").strip().lower()
    organ = re.sub(r"[^a-z0-9]+", "-", organ).strip("-") or "source-unavailable"
    return f"puriq-formula-meta/{organ}"


def _source_family_split(source_family: str) -> str:
    """Assign a whole source family to one split to prevent family leakage."""

    bucket = int(hashlib.sha256(source_family.encode("utf-8")).hexdigest()[:8], 16) % 10
    if bucket < 7:
        return "train"
    if bucket < 9:
        return "validation"
    return "test"


@lru_cache(maxsize=1)
def formula_curriculum() -> dict[str, Any]:
    """Build the full formula-ID/status curriculum without manufacturing proof evidence.

    This is a metadata bridge into the Brain curriculum, not a theorem dataset.
    The local canonical registry and repository license are content-addressed.  A
    proof/refutation receipt remains null unless an exact per-formula receipt is
    present; the repository currently provides no such mapping.
    """

    if not _FORMULA_SOURCE_PATH.is_file() or not _LICENSE_PATH.is_file():
        raise DatasetUnavailable("FORMULA_CURRICULUM_SOURCE_OR_LICENSE_UNAVAILABLE")
    source_sha256 = _file_sha256(_FORMULA_SOURCE_PATH)
    license_sha256 = _file_sha256(_LICENSE_PATH)
    eligible: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    expected_ids = {f"F{index}" for index in range(1, 24)}

    def quarantine(formula_id: str, reasons: Sequence[str], meta: Mapping[str, Any] | None = None) -> None:
        quarantined.append({
            "formula_id": formula_id,
            "reasons": sorted(set(reasons)),
            "source_record_sha256": _adapter.digest_json(dict(meta)) if meta is not None else None,
            "proof_receipt_sha256": None,
            "refutation_receipt_sha256": None,
            "proof_uplift": 0,
            "trust_uplift": 0,
        })

    for formula_id in sorted(expected_ids, key=lambda token: int(token[1:])):
        meta = _puriq.FORMULA_META.get(formula_id)
        if not isinstance(meta, Mapping):
            quarantine(formula_id, ["CANONICAL_RECORD_UNAVAILABLE"])
            continue
        reasons: list[str] = []
        if meta.get("id") != formula_id:
            reasons.append("FORMULA_ID_CONFLICT")
        status = meta.get("proof_status")
        if status not in {"PROVED", "UNATTEMPTED", "CONJECTURE_1"}:
            reasons.append("UNSUPPORTED_PROOF_STATUS")
        if (formula_id in _LOCKED_FORMULA_IDS) != (status == "PROVED"):
            reasons.append("LOCKED_PROOF_CLAIM_CONFLICT")
        if formula_id == "F23" and status != "CONJECTURE_1":
            reasons.append("LAMBDA_CONJECTURE_STATUS_CONFLICT")
        required_text = ("name", "organ", "primitive", "identity_doc")
        if any(not isinstance(meta.get(field), str) or not str(meta[field]).strip() for field in required_text):
            reasons.append("PROVENANCE_METADATA_INCOMPLETE")
        if reasons:
            quarantine(formula_id, reasons, meta)
            continue

        source_family = _formula_source_family(meta)
        proof_note = meta.get("proof_note")
        if status == "PROVED" and proof_note:
            claim_scope = "LOCKED_THEOREM_ONLY_FORMULA_IDENTITY_SCOPE_MAY_DIFFER"
        elif status == "PROVED":
            claim_scope = "LOCKED_THEOREM_REPORTED_BY_CANONICAL_REGISTRY"
        elif status == "CONJECTURE_1":
            claim_scope = "CONJECTURE_1_OPEN_NOT_A_THEOREM"
        else:
            claim_scope = "OPEN_PROOF_OBLIGATION_UNATTEMPTED"
        eligible.append({
            "formula_id": formula_id,
            "name": meta["name"],
            "organ": meta["organ"],
            "primitive": meta["primitive"],
            "identity_doc": meta["identity_doc"],
            "proof_status": status,
            "lean_name": meta.get("lean_name"),
            "lean_status": meta.get("lean_status"),
            "locked": formula_id in _LOCKED_FORMULA_IDS,
            "claim_scope": claim_scope,
            "source_family": source_family,
            "split": _source_family_split(source_family),
            "source_record_sha256": _adapter.digest_json(dict(meta)),
            "proof_receipt_sha256": None,
            "refutation_receipt_sha256": None,
            "receipt_state": "PER_FORMULA_RECEIPT_SOURCE_UNAVAILABLE",
            "license_state": "REPOSITORY_APACHE_2_0",
            "dataset_role": "STATUS_AND_PROVENANCE_METADATA_ONLY",
            "proof_uplift": 0,
            "trust_uplift": 0,
        })

    extras = sorted(set(_puriq.FORMULA_META) - expected_ids)
    for formula_id in extras:
        meta = _puriq.FORMULA_META[formula_id]
        quarantine(str(formula_id), ["FORMULA_ID_OUTSIDE_F1_F23_CONTRACT"], meta if isinstance(meta, Mapping) else None)

    split_families: dict[str, list[str]] = {"train": [], "validation": [], "test": []}
    for item in eligible:
        if item["source_family"] not in split_families[item["split"]]:
            split_families[item["split"]].append(item["source_family"])
    for families in split_families.values():
        families.sort()
    return {
        "schema": CURRICULUM_SCHEMA,
        "state": "READY" if eligible and not quarantined else ("PARTIAL" if eligible else "UNAVAILABLE"),
        "dataset_role": "BRAIN_CURRICULUM_FORMULA_STATUS_AND_PROVENANCE_METADATA",
        "canonical_source": {
            "path": "szl_puriq_formulas.py",
            "sha256": source_sha256,
            "license": "Apache-2.0",
            "license_file_sha256": license_sha256,
        },
        "formula_contract": {
            "expected_ids": [f"F{index}" for index in range(1, 24)],
            "locked_proven_ids": sorted(_LOCKED_FORMULA_IDS, key=lambda token: int(token[1:])),
            "lambda_formula_id": "F23",
            "lambda_status": "CONJECTURE_1",
        },
        "counts": {
            "expected": 23,
            "eligible": len(eligible),
            "quarantined": len(quarantined),
            "source_families": len({item["source_family"] for item in eligible}),
        },
        "source_family_split": {
            "method": "SHA256_FAMILY_BUCKET_70_20_10_NO_FAMILY_LEAKAGE",
            "families": split_families,
        },
        "eligible": eligible,
        "quarantined": quarantined,
        "receipt_boundary": (
            "Null receipt hashes mean no exact per-formula proof/refutation receipt mapping was found; "
            "canonical registry status is not upgraded into receipt evidence."
        ),
        "interpretation_guard": (
            "This curriculum carries formula identifiers, statuses, and provenance metadata only. "
            "It does not prove formulas, refute conjectures, or improve numerical-result trust."
        ),
        **ZERO_UPLIFT,
    }


def _strict(value: Any, required: set[str], name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise DatasetContractError(f"{name} must be an object")
    missing = sorted(required - set(value))
    extras = sorted(set(value) - required)
    if missing:
        raise DatasetContractError(f"{name} is missing fields: {', '.join(missing)}")
    if extras:
        raise DatasetContractError(f"{name} has unsupported fields: {', '.join(extras)}")
    return value


def _finite(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DatasetContractError(f"{name} must be a finite JSON number")
    result = float(value)
    if not math.isfinite(result) or abs(result) > _adapter.MAX_ABS_VALUE:
        raise DatasetContractError(f"{name} must be finite and bounded")
    return result


def _nullable_uint(value: Any, name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise DatasetContractError(f"{name} must be a non-negative integer or null")
    return value


def _sha_or_none(value: Any, name: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise DatasetContractError(f"{name} must be a lowercase SHA-256 digest or null")
    return value


def _utc_timestamp(value: Any) -> str:
    if not isinstance(value, str) or len(value) > 40:
        raise DatasetContractError("observed_at_utc must be an ISO-8601 timestamp")
    try:
        parsed = _datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DatasetContractError("observed_at_utc must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DatasetContractError("observed_at_utc must include a UTC offset")
    return parsed.astimezone(_datetime.timezone.utc).isoformat().replace("+00:00", "Z")


@lru_cache(maxsize=1)
def preregistration() -> dict[str, Any]:
    try:
        value = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DatasetUnavailable("PREREGISTRATION_SOURCE_UNAVAILABLE") from exc
    required = {
        "schema", "protocol_id", "protocol_version", "state", "frozen_before_execution",
        "results_present", "matrix_dimensions", "deterministic_seeds",
        "condition_number_strata", "confirmatory_matrix_families",
        "exploratory_matrix_families", "fixture_generation", "tolerance",
        "machine_epsilon_binary64", "execution_order_seed", "engines",
        "expected_case_counts", "evidence_boundary",
    }
    _strict(value, required, "preregistration")
    if value["schema"] != PREREGISTRATION_SCHEMA:
        raise DatasetUnavailable("PREREGISTRATION_SCHEMA_MISMATCH")
    if value["matrix_dimensions"] != [2, 4, 8, 16, 32, 64]:
        raise DatasetUnavailable("PREREGISTRATION_DIMENSIONS_MISMATCH")
    if value["deterministic_seeds"] != [1729, 57721, 271828, 314159, 1618033]:
        raise DatasetUnavailable("PREREGISTRATION_SEEDS_MISMATCH")
    if value["expected_case_counts"] != {"confirmatory": 1320, "exploratory": 8, "total": 1328}:
        raise DatasetUnavailable("PREREGISTRATION_CASE_COUNT_MISMATCH")
    if value["engines"] != ["octave", "matlab"]:
        raise DatasetUnavailable("PREREGISTRATION_ENGINE_SET_MISMATCH")
    return value


class _SplitMix64:
    def __init__(self, seed: int) -> None:
        self.state = seed & _MASK64

    def next_u64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & _MASK64
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _MASK64
        return (z ^ (z >> 31)) & _MASK64

    def uniform(self) -> float:
        return (self.next_u64() >> 11) / float(1 << 53)


def _derived_seed(seed: int, family: str, label: str) -> int:
    payload = f"szl-numerics-v1:{seed}:{family}:{label}".encode("ascii")
    return int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")


def _identity(n: int) -> list[list[float]]:
    return [[1.0 if row == column else 0.0 for column in range(n)] for row in range(n)]


def _orthogonal(n: int, seed: int) -> list[list[float]]:
    generator = _SplitMix64(seed)
    result = _identity(n)
    for left in range(n):
        for right in range(left + 1, n):
            theta = 2.0 * math.pi * generator.uniform()
            cosine, sine = math.cos(theta), math.sin(theta)
            for row in range(n):
                old_left, old_right = result[row][left], result[row][right]
                result[row][left] = cosine * old_left - sine * old_right
                result[row][right] = sine * old_left + cosine * old_right
    return result


def _spectrum(n: int, kappa: float, *, signed: bool = False) -> list[float]:
    if n == 1:
        values = [1.0]
    else:
        exponent = math.log10(kappa)
        values = [10.0 ** (-exponent * index / (n - 1)) for index in range(n)]
    if signed:
        values = [value if index % 2 == 0 else -value for index, value in enumerate(values)]
    return values


def _q_diag_qt(q: Sequence[Sequence[float]], diagonal: Sequence[float]) -> list[list[float]]:
    n = len(diagonal)
    return [
        [sum(q[row][k] * diagonal[k] * q[column][k] for k in range(n)) for column in range(n)]
        for row in range(n)
    ]


def _ql_diag_qr(ql: Sequence[Sequence[float]], diagonal: Sequence[float], qr: Sequence[Sequence[float]]) -> list[list[float]]:
    n = len(diagonal)
    return [
        [sum(ql[row][k] * diagonal[k] * qr[column][k] for k in range(n)) for column in range(n)]
        for row in range(n)
    ]


def _stable_matrix(matrix: Sequence[Sequence[float]]) -> list[list[float]]:
    return [[float(format(value, ".17g")) for value in row] for row in matrix]


def _matvec(matrix: Sequence[Sequence[float]], vector: Sequence[float]) -> list[float]:
    return [sum(value * vector[column] for column, value in enumerate(row)) for row in matrix]


def _known_solution(n: int) -> list[float]:
    return [((-1.0) ** index) * (index + 1) / n for index in range(n)]


def _slug(token: str) -> str:
    return token.lower().replace("_", "-")


def _case_id(family: str, dimension: int, stratum: str, seed: int, operation: str) -> str:
    return f"case-{_slug(family)}-n{dimension:02d}-{_slug(stratum)}-s{seed}-{_slug(operation)}"


def _case_descriptors() -> Iterable[dict[str, Any]]:
    manifest = preregistration()
    strata = manifest["condition_number_strata"]
    for family in manifest["confirmatory_matrix_families"]:
        for dimension in manifest["matrix_dimensions"]:
            for stratum in strata:
                for seed in manifest["deterministic_seeds"]:
                    for operation in family["operations"]:
                        case_id = _case_id(family["id"], dimension, stratum["id"], seed, operation)
                        yield {
                            "case_id": case_id,
                            "design": "CONFIRMATORY",
                            "matrix_family": family["id"],
                            "symmetric": family["symmetric"],
                            "dimension": dimension,
                            "condition_stratum": stratum["id"],
                            "condition_number_target": stratum["target"],
                            "seed": seed,
                            "operation": operation,
                            "execution_order_sha256": hashlib.sha256(
                                f"{manifest['execution_order_seed']}:{case_id}".encode("utf-8")
                            ).hexdigest(),
                        }
    for family in manifest["exploratory_matrix_families"]:
        for dimension in family["dimensions"]:
            for seed in family["seeds"]:
                for operation in family["operations"]:
                    case_id = _case_id(family["id"], dimension, family["condition_stratum"], seed, operation)
                    yield {
                        "case_id": case_id,
                        "design": "EXPLORATORY",
                        "matrix_family": family["id"],
                        "symmetric": family["symmetric"],
                        "dimension": dimension,
                        "condition_stratum": family["condition_stratum"],
                        "condition_number_target": None,
                        "seed": seed,
                        "operation": operation,
                        "excluded_from_confirmatory_denominators": True,
                        "execution_order_sha256": hashlib.sha256(
                            f"{manifest['execution_order_seed']}:{case_id}".encode("utf-8")
                        ).hexdigest(),
                    }


@lru_cache(maxsize=1)
def _case_index() -> dict[str, dict[str, Any]]:
    values = {item["case_id"]: item for item in _case_descriptors()}
    manifest = preregistration()
    if len(values) != manifest["expected_case_counts"]["total"]:
        raise DatasetUnavailable("GENERATED_CASE_COUNT_MISMATCH")
    return values


def _matrix_for(descriptor: Mapping[str, Any]) -> list[list[float]]:
    n = descriptor["dimension"]
    family = descriptor["matrix_family"]
    seed = descriptor["seed"]
    kappa = descriptor["condition_number_target"]
    if family == "HILBERT_SENTINEL":
        return _stable_matrix([[1.0 / (row + column + 1) for column in range(n)] for row in range(n)])
    diagonal = _spectrum(n, kappa, signed=family == "SYMMETRIC_INDEFINITE_GIVENS")
    if family == "DIAGONAL_GEOMETRIC":
        matrix = [[diagonal[row] if row == column else 0.0 for column in range(n)] for row in range(n)]
    elif family in ("SPD_GIVENS", "SYMMETRIC_INDEFINITE_GIVENS"):
        q = _orthogonal(n, _derived_seed(seed, family, "Q"))
        matrix = _q_diag_qt(q, diagonal)
    elif family == "GENERAL_SVD_GIVENS":
        ql = _orthogonal(n, _derived_seed(seed, family, "Q_LEFT"))
        qr = _orthogonal(n, _derived_seed(seed, family, "Q_RIGHT"))
        matrix = _ql_diag_qr(ql, diagonal, qr)
    else:
        raise DatasetUnavailable("UNKNOWN_PREREGISTERED_MATRIX_FAMILY")
    return _stable_matrix(matrix)


def get_case(case_id: str) -> dict[str, Any]:
    if not isinstance(case_id, str) or not _CASE_RE.fullmatch(case_id):
        raise DatasetContractError("case_id is invalid")
    descriptor = _case_index().get(case_id)
    if descriptor is None:
        raise DatasetContractError("case_id is not preregistered")
    matrix = _matrix_for(descriptor)
    operation = descriptor["operation"]
    inputs: dict[str, Any] = {"matrix": matrix}
    construction_reference: dict[str, Any] = {"state": "NOT_APPLICABLE"}
    if operation != "SYMMETRIC_EIGENVALUES":
        expected = _known_solution(descriptor["dimension"])
        inputs["rhs"] = _matvec(matrix, expected)
        construction_reference = {
            "state": "FROZEN_CONSTRUCTION_REFERENCE",
            "role": "fixture construction only; not the independent primary reference",
            "values": expected,
        }
        if operation == "VALIDATE_REFERENCE_VECTOR":
            inputs["expected"] = expected
    request = {
        "schema": _adapter.REQUEST_SCHEMA,
        "request_id": case_id,
        "operation": operation,
        "inputs": inputs,
        "tolerance": preregistration()["tolerance"],
    }
    request = _adapter.parse_request(request)
    core = {
        "schema": CASE_SCHEMA,
        **descriptor,
        "request": request,
        "request_sha256": _adapter.digest_json(request),
        "construction_reference": construction_reference,
        "primary_reference": {"state": "SOURCE_UNAVAILABLE"},
        "condition_number_reference": {"state": "NOT_EVALUATED"},
        "substrate_evidence": "UNKNOWN",
        **ZERO_UPLIFT,
    }
    return {**core, "fixture_sha256": _adapter.digest_json(core)}


def list_cases(*, offset: int = 0, limit: int = 25, family: str | None = None, operation: str | None = None) -> dict[str, Any]:
    if offset < 0 or not 1 <= limit <= MAX_PAGE_SIZE:
        raise DatasetContractError(f"offset must be non-negative and limit must be 1..{MAX_PAGE_SIZE}")
    values = list(_case_index().values())
    if family:
        values = [item for item in values if item["matrix_family"] == family]
    if operation:
        values = [item for item in values if item["operation"] == operation]
    values.sort(key=lambda item: item["execution_order_sha256"])
    return {
        "schema": "szl.numerics.dataset-case-list/v1",
        "total": len(values),
        "offset": offset,
        "limit": limit,
        "items": values[offset: offset + limit],
        "items_are": "PREREGISTERED_INPUT_DESCRIPTORS_NOT_ENGINE_RESULTS",
        **ZERO_UPLIFT,
    }


def _ledger_path() -> Path:
    configured = os.environ.get("A11OY_NUMERICS_DATASET_LEDGER", "").strip()
    return Path(configured).expanduser() if configured else _ROOT / ".a11oy-state" / "numerics-dataset.ndjson"


def _read_rows() -> list[dict[str, Any]]:
    path = _ledger_path()
    if not path.is_file():
        return []
    if path.stat().st_size > MAX_LEDGER_BYTES:
        raise DatasetUnavailable("LEDGER_SIZE_LIMIT_EXCEEDED")
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(path.read_bytes().splitlines(), start=1):
        if not raw:
            continue
        if len(raw) > MAX_ROW_BYTES:
            raise DatasetUnavailable(f"LEDGER_ROW_SIZE_LIMIT_EXCEEDED:{line_number}")
        try:
            value = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise DatasetUnavailable(f"LEDGER_ROW_INVALID:{line_number}") from exc
        if not isinstance(value, dict) or value.get("schema") != ROW_SCHEMA:
            raise DatasetUnavailable(f"LEDGER_ROW_SCHEMA_INVALID:{line_number}")
        rows.append(value)
    if len(rows) > MAX_LEDGER_ROWS:
        raise DatasetUnavailable("LEDGER_ROW_LIMIT_EXCEEDED")
    return rows


def list_results(*, offset: int = 0, limit: int = 25, case_id: str | None = None) -> dict[str, Any]:
    if offset < 0 or not 1 <= limit <= MAX_PAGE_SIZE:
        raise DatasetContractError(f"offset must be non-negative and limit must be 1..{MAX_PAGE_SIZE}")
    rows = _read_rows()
    if case_id:
        rows = [row for row in rows if row.get("case_id") == case_id]
    rows.reverse()
    return {
        "schema": "szl.numerics.dataset-result-list/v1",
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "items": rows[offset: offset + limit],
        "ledger_semantics": "APPEND_ONLY_NEWEST_FIRST",
        **ZERO_UPLIFT,
    }


def _vector_norm(vector: Sequence[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _matrix_norm2_diagnostic(matrix: Sequence[Sequence[float]]) -> float:
    """Deterministic binary64 power iteration; explicitly not a high-precision reference."""

    n = len(matrix)
    vector = [1.0 / math.sqrt(n)] * n
    for _ in range(96):
        av = _matvec(matrix, vector)
        ata_v = [sum(matrix[row][column] * av[row] for row in range(n)) for column in range(n)]
        size = _vector_norm(ata_v)
        if size == 0.0:
            return 0.0
        next_vector = [value / size for value in ata_v]
        delta = _vector_norm([left - right for left, right in zip(next_vector, vector)])
        vector = next_vector
        if delta <= 1.0e-15:
            break
    return _vector_norm(_matvec(matrix, vector))


def _relative_error(actual: Sequence[float], expected: Sequence[float]) -> float:
    numerator = _vector_norm([left - right for left, right in zip(actual, expected)])
    denominator = _vector_norm(expected)
    if denominator == 0.0:
        return 0.0 if numerator == 0.0 else math.inf
    return numerator / denominator


def _within(left: float, right: float, tolerance: Mapping[str, float]) -> bool:
    return abs(left - right) <= tolerance["absolute"] + tolerance["relative"] * max(abs(left), abs(right))


def _diagnostics(case: Mapping[str, Any], values: Sequence[float], reference: Mapping[str, Any]) -> dict[str, Any]:
    request = case["request"]
    matrix = request["inputs"]["matrix"]
    operation = request["operation"]
    n = len(matrix)
    threshold = 100.0 * n * preregistration()["machine_epsilon_binary64"]
    base: dict[str, Any] = {
        "diagnostic_precision": "PYTHON_BINARY64",
        "matrix_norm2_method": "DETERMINISTIC_POWER_ITERATION_NOT_PRIMARY_REFERENCE",
        "absolute_residual_norm2": None,
        "relative_residual": None,
        "normwise_backward_error": None,
        "forward_error": None,
        "maximum_elementwise_reference_error": None,
        "reference_state": "NOT_EVALUATED",
        "trace_invariant": None,
        "frobenius_invariant": None,
        "quality_gate_threshold": threshold,
        "quality_gate": "NOT_EVALUATED",
    }
    if operation in ("MATRIX_SOLVE", "VALIDATE_REFERENCE_VECTOR"):
        rhs = request["inputs"]["rhs"]
        residual_vector = [right - left for right, left in zip(rhs, _matvec(matrix, values))]
        residual = _vector_norm(residual_vector)
        denominator = _matrix_norm2_diagnostic(matrix) * _vector_norm(values) + _vector_norm(rhs)
        backward = 0.0 if residual == 0.0 and denominator == 0.0 else (math.inf if denominator == 0.0 else residual / denominator)
        base.update({
            "absolute_residual_norm2": residual,
            "relative_residual": backward,
            "normwise_backward_error": backward,
            "quality_gate": "PASS" if math.isfinite(backward) and backward <= threshold else "FAIL",
        })
    else:
        trace_matrix = sum(matrix[index][index] for index in range(n))
        trace_values = sum(values)
        norm_f_squared = sum(value * value for row in matrix for value in row)
        value_sq_sum = sum(value * value for value in values)
        trace_invariant = abs(trace_values - trace_matrix) / max(1.0, abs(trace_matrix))
        frobenius_invariant = abs(value_sq_sum - norm_f_squared) / max(1.0, norm_f_squared)
        base.update({
            "trace_invariant": trace_invariant,
            "frobenius_invariant": frobenius_invariant,
            "quality_gate": "PASS" if trace_invariant <= threshold and frobenius_invariant <= threshold else "FAIL",
        })
    if reference["state"] == "MEASURED":
        expected = reference["values"]
        base.update({
            "forward_error": _relative_error(values, expected),
            "maximum_elementwise_reference_error": max(abs(left - right) for left, right in zip(values, expected)),
            "reference_state": "REFERENCE_MATCH" if all(
                _within(left, right, request["tolerance"]) for left, right in zip(values, expected)
            ) else "REFERENCE_CONFLICT",
            "reference_implementation": reference["implementation"],
            "reference_evidence_sha256": reference["evidence_sha256"],
        })
    return base


def _parse_ingest(payload: Mapping[str, Any]) -> dict[str, Any]:
    required = {"schema", "run_id", "case_id", "engine", "outcome", "engine_evidence", "containment", "resources", "reference", "observed_at_utc"}
    obj = _strict(payload, required, "ingest")
    if obj["schema"] != INGEST_SCHEMA:
        raise DatasetContractError(f"schema must be {INGEST_SCHEMA}")
    if not isinstance(obj["run_id"], str) or not _ID_RE.fullmatch(obj["run_id"]):
        raise DatasetContractError("run_id is invalid")
    case = get_case(obj["case_id"])
    if obj["engine"] not in _adapter.ENGINES:
        raise DatasetContractError("engine must be octave or matlab")
    outcome = obj["outcome"]
    if not isinstance(outcome, Mapping) or outcome.get("state") not in ("RESULT", "UNAVAILABLE"):
        raise DatasetContractError("outcome.state must be RESULT or UNAVAILABLE")
    if outcome["state"] == "RESULT":
        outcome = _strict(outcome, {"state", "values"}, "outcome")
        raw_values = outcome["values"]
        if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes, bytearray)):
            raise DatasetContractError("outcome.values must be an array")
        if len(raw_values) != case["dimension"]:
            raise DatasetContractError(f"outcome.values must contain exactly {case['dimension']} numbers")
        outcome = {"state": "RESULT", "values": [_finite(value, f"outcome.values[{index}]") for index, value in enumerate(raw_values)]}
    else:
        outcome = _strict(outcome, {"state", "reason"}, "outcome")
        if not isinstance(outcome["reason"], str) or not 1 <= len(outcome["reason"]) <= 160:
            raise DatasetContractError("outcome.reason must contain 1..160 characters")
        outcome = dict(outcome)
    engine_evidence = _strict(
        obj["engine_evidence"],
        {"version", "version_evidence_sha256", "executable_sha256", "license_state", "offline_license_state"},
        "engine_evidence",
    )
    version = engine_evidence["version"]
    if version is not None and (not isinstance(version, str) or not 1 <= len(version) <= 120):
        raise DatasetContractError("engine_evidence.version must be null or 1..120 characters")
    engine_evidence = {
        "version": version,
        "version_evidence_sha256": _sha_or_none(engine_evidence["version_evidence_sha256"], "engine_evidence.version_evidence_sha256"),
        "executable_sha256": _sha_or_none(engine_evidence["executable_sha256"], "engine_evidence.executable_sha256"),
        "license_state": engine_evidence["license_state"],
        "offline_license_state": engine_evidence["offline_license_state"],
    }
    if engine_evidence["license_state"] not in ("OPERATOR_REVIEWED", "REVIEW_REQUIRED", "UNKNOWN"):
        raise DatasetContractError("engine_evidence.license_state is invalid")
    if engine_evidence["offline_license_state"] not in ("CONFIGURED", "UNAVAILABLE", "NOT_APPLICABLE", "UNKNOWN"):
        raise DatasetContractError("engine_evidence.offline_license_state is invalid")
    containment = _strict(obj["containment"], {"network_state", "evidence_sha256"}, "containment")
    if containment["network_state"] not in ("DENIED", "UNAVAILABLE", "UNKNOWN"):
        raise DatasetContractError("containment.network_state is invalid")
    containment = {"network_state": containment["network_state"], "evidence_sha256": _sha_or_none(containment["evidence_sha256"], "containment.evidence_sha256")}
    resources = _strict(
        obj["resources"],
        {"wall_time_ns", "child_user_cpu_ns", "child_system_cpu_ns", "peak_resident_bytes", "request_bytes", "response_bytes", "log_bytes"},
        "resources",
    )
    resources = {name: _nullable_uint(value, f"resources.{name}") for name, value in resources.items()}
    reference = obj["reference"]
    if not isinstance(reference, Mapping) or reference.get("state") not in ("SOURCE_UNAVAILABLE", "MEASURED"):
        raise DatasetContractError("reference.state must be SOURCE_UNAVAILABLE or MEASURED")
    if reference["state"] == "SOURCE_UNAVAILABLE":
        reference = dict(_strict(reference, {"state"}, "reference"))
    else:
        reference = _strict(reference, {"state", "implementation", "values", "evidence_sha256"}, "reference")
        if reference["implementation"] != "PYTHON_MPMATH_100DP":
            raise DatasetContractError("only the preregistered PYTHON_MPMATH_100DP primary reference is accepted")
        values = reference["values"]
        if not isinstance(values, Sequence) or isinstance(values, (str, bytes, bytearray)) or len(values) != case["dimension"]:
            raise DatasetContractError(f"reference.values must contain exactly {case['dimension']} numbers")
        reference = {
            "state": "MEASURED",
            "implementation": "PYTHON_MPMATH_100DP",
            "values": [_finite(value, f"reference.values[{index}]") for index, value in enumerate(values)],
            "evidence_sha256": _sha_or_none(reference["evidence_sha256"], "reference.evidence_sha256"),
        }
        if reference["evidence_sha256"] is None:
            raise DatasetContractError("measured primary reference requires evidence_sha256")
    return {
        "run_id": obj["run_id"],
        "case": case,
        "engine": obj["engine"],
        "outcome": outcome,
        "engine_evidence": engine_evidence,
        "containment": containment,
        "resources": resources,
        "reference": reference,
        "observed_at_utc": _utc_timestamp(obj["observed_at_utc"]),
    }


def _evidence_gate(parsed: Mapping[str, Any]) -> tuple[str, str | None]:
    if parsed["outcome"]["state"] == "UNAVAILABLE":
        return "UNAVAILABLE", parsed["outcome"]["reason"]
    evidence = parsed["engine_evidence"]
    containment = parsed["containment"]
    resources = parsed["resources"]
    if containment["network_state"] != "DENIED" or containment["evidence_sha256"] is None:
        return "REFUSED", "NETWORK_DENIAL_EVIDENCE_UNAVAILABLE"
    if evidence["version"] is None or evidence["version_evidence_sha256"] is None or evidence["executable_sha256"] is None:
        return "REFUSED", "ENGINE_VERSION_EVIDENCE_UNAVAILABLE"
    if evidence["license_state"] != "OPERATOR_REVIEWED":
        return "REFUSED", "ENGINE_LICENSE_REVIEW_UNAVAILABLE"
    if parsed["engine"] == "matlab" and evidence["offline_license_state"] != "CONFIGURED":
        return "REFUSED", "MATLAB_OFFLINE_LICENSE_STATE_UNAVAILABLE"
    if parsed["engine"] == "octave" and evidence["offline_license_state"] != "NOT_APPLICABLE":
        return "REFUSED", "OCTAVE_OFFLINE_LICENSE_STATE_MUST_BE_NOT_APPLICABLE"
    if resources["wall_time_ns"] is None:
        return "REFUSED", "WALL_TIME_MEASUREMENT_UNAVAILABLE"
    return "RESULT", None


def _latest_other(rows: Sequence[Mapping[str, Any]], case_id: str, engine: str) -> Mapping[str, Any] | None:
    for row in reversed(rows):
        if row.get("case_id") == case_id and row.get("engine") != engine and row.get("row_state") == "RESULT":
            return row
    return None


def ingest_result(payload: Mapping[str, Any]) -> dict[str, Any]:
    parsed = _parse_ingest(payload)
    with _LEDGER_LOCK:
        rows = _read_rows()
        if len(rows) >= MAX_LEDGER_ROWS:
            raise DatasetUnavailable("LEDGER_ROW_LIMIT_EXCEEDED")
        if any(row.get("run_id") == parsed["run_id"] for row in rows):
            raise DatasetContractError("run_id already exists in the append-only ledger")
        row_state, reason = _evidence_gate(parsed)
        values = parsed["outcome"].get("values") if row_state == "RESULT" else None
        diagnostics = _diagnostics(parsed["case"], values, parsed["reference"]) if values is not None else None
        comparison_state = "UNAVAILABLE" if row_state == "UNAVAILABLE" else ("REFUSED" if row_state == "REFUSED" else "NOT_EVALUATED")
        compared_to = None
        if row_state == "RESULT":
            other = _latest_other(rows, parsed["case"]["case_id"], parsed["engine"])
            if other is not None:
                compared_to = other["run_id"]
                tolerance = parsed["case"]["request"]["tolerance"]
                pair_matches = all(_within(left, right, tolerance) for left, right in zip(values, other["values"]))
                own_gate = diagnostics["quality_gate"] == "PASS"
                other_gate = (other.get("diagnostics") or {}).get("quality_gate") == "PASS"
                comparison_state = "MATCH" if pair_matches and own_gate and other_gate else "CONFLICT"
        core = {
            "schema": ROW_SCHEMA,
            "sequence": len(rows) + 1,
            "run_id": parsed["run_id"],
            "case_id": parsed["case"]["case_id"],
            "fixture_sha256": parsed["case"]["fixture_sha256"],
            "request_sha256": parsed["case"]["request_sha256"],
            "engine": parsed["engine"],
            "row_state": row_state,
            "comparison_state": comparison_state,
            "compared_to_run_id": compared_to,
            "reason": reason,
            "values": values,
            "values_sha256": _adapter.digest_json(values) if values is not None else None,
            "diagnostics": diagnostics,
            "engine_evidence": parsed["engine_evidence"],
            "containment": parsed["containment"],
            "resources": parsed["resources"],
            "reference": {key: value for key, value in parsed["reference"].items() if key != "values"},
            "observed_at_utc": parsed["observed_at_utc"],
            "evidence_label": "MEASURED" if row_state == "RESULT" else "UNKNOWN",
            "evidence_origin": "AUTHENTICATED_APPEND_ONLY_INGESTION_NOT_LOCAL_ENGINE_EXECUTION",
            "substrate_evidence": "UNKNOWN",
            "signature_state": "UNSIGNED_INTEGRITY_CHAIN",
            "previous_row_sha256": rows[-1]["row_sha256"] if rows else None,
            **ZERO_UPLIFT,
        }
        row = {**core, "row_sha256": _adapter.digest_json(core)}
        encoded = _adapter.canonical_json(row) + b"\n"
        if len(encoded) > MAX_ROW_BYTES:
            raise DatasetContractError("result row exceeds the 64 KiB append ceiling")
        path = _ledger_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        return row


def _ingest_configured() -> bool:
    digest = os.environ.get("A11OY_NUMERICS_DATASET_INGEST_TOKEN_SHA256", "").strip().lower()
    return bool(_SHA256_RE.fullmatch(digest))


def _authorized(token: str | None) -> bool:
    expected = os.environ.get("A11OY_NUMERICS_DATASET_INGEST_TOKEN_SHA256", "").strip().lower()
    if not _SHA256_RE.fullmatch(expected) or not token:
        return False
    return hmac.compare_digest(hashlib.sha256(token.encode("utf-8")).hexdigest(), expected)


def dataset_status() -> dict[str, Any]:
    manifest = preregistration()
    curriculum = formula_curriculum()
    rows = _read_rows()
    classifications: dict[str, int] = {}
    for row in rows:
        token = row.get("comparison_state", "UNKNOWN")
        classifications[token] = classifications.get(token, 0) + 1
    runtime = _adapter.engine_status()
    return {
        "schema": STATUS_SCHEMA,
        "service_state": "READY" if manifest["frozen_before_execution"] else "UNAVAILABLE",
        "preregistration": {
            "protocol_id": manifest["protocol_id"],
            "state": manifest["state"],
            "manifest_sha256": _adapter.digest_json(manifest),
            "inputs_frozen": manifest["frozen_before_execution"],
            "case_count": len(_case_index()),
            "confirmatory_case_count": manifest["expected_case_counts"]["confirmatory"],
            "exploratory_case_count": manifest["expected_case_counts"]["exploratory"],
        },
        "result_ledger": {
            "row_count": len(rows),
            "classification_counts": classifications,
            "append_only": True,
            "ingest_gate": "CONFIGURED" if _ingest_configured() else "UNAVAILABLE",
            "path_disclosed": False,
        },
        "local_runtime": {
            "octave": runtime["engines"]["octave"]["execution_state"],
            "matlab": runtime["engines"]["matlab"]["execution_state"],
            "network_isolation": runtime["controls"]["network_isolation"],
            "network_denial_evidence": "NOT_EVALUATED",
            "substrate_evidence": "UNKNOWN",
        },
        "reference_state": "MEASURED_PER_ROW_ONLY_WHEN_PINNED_EVIDENCE_IS_INGESTED",
        "formula_curriculum": {
            "state": curriculum["state"],
            **curriculum["counts"],
            "proof_uplift": 0,
            "trust_uplift": 0,
        },
        "interpretation_guard": "MATCH is bounded cross-engine agreement for one frozen case; it is not proof or general correctness.",
        **ZERO_UPLIFT,
    }


def _page_int(raw: str | None, default: int, name: str) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise DatasetContractError(f"{name} must be an integer") from exc
    return value


def register(app: Any, ns: str = "a11oy") -> str:
    """Register read APIs and the authenticated append-only result endpoint."""

    from fastapi.responses import JSONResponse

    prefix = f"/api/{ns}/v1/numerics/dataset"

    @app.get(f"{prefix}/status")
    async def numerics_dataset_status() -> JSONResponse:
        try:
            return JSONResponse(dataset_status())
        except DatasetUnavailable as exc:
            return JSONResponse({"schema": STATUS_SCHEMA, "service_state": "UNAVAILABLE", "reason": str(exc), **ZERO_UPLIFT}, status_code=503)

    @app.get(f"{prefix}/cases")
    async def numerics_dataset_cases(request: Request) -> JSONResponse:
        try:
            result = list_cases(
                offset=_page_int(request.query_params.get("offset"), 0, "offset"),
                limit=_page_int(request.query_params.get("limit"), 25, "limit"),
                family=request.query_params.get("family"),
                operation=request.query_params.get("operation"),
            )
        except (DatasetContractError, DatasetUnavailable) as exc:
            return JSONResponse({"state": "REJECTED", "error": str(exc), **ZERO_UPLIFT}, status_code=422)
        return JSONResponse(result)

    @app.get(f"{prefix}/cases/{{case_id}}")
    async def numerics_dataset_case(case_id: str) -> JSONResponse:
        try:
            return JSONResponse(get_case(case_id))
        except DatasetContractError as exc:
            return JSONResponse({"state": "REJECTED", "error": str(exc), **ZERO_UPLIFT}, status_code=404)

    @app.get(f"{prefix}/results")
    async def numerics_dataset_results(request: Request) -> JSONResponse:
        try:
            result = list_results(
                offset=_page_int(request.query_params.get("offset"), 0, "offset"),
                limit=_page_int(request.query_params.get("limit"), 25, "limit"),
                case_id=request.query_params.get("case_id"),
            )
        except (DatasetContractError, DatasetUnavailable) as exc:
            return JSONResponse({"state": "UNAVAILABLE", "error": str(exc), **ZERO_UPLIFT}, status_code=503)
        return JSONResponse(result)

    @app.get(f"{prefix}/curriculum/formulas")
    async def numerics_formula_curriculum() -> JSONResponse:
        try:
            return JSONResponse(formula_curriculum())
        except DatasetUnavailable as exc:
            return JSONResponse({
                "schema": CURRICULUM_SCHEMA,
                "state": "UNAVAILABLE",
                "reason": str(exc),
                **ZERO_UPLIFT,
            }, status_code=503)

    @app.post(f"{prefix}/results")
    async def numerics_dataset_ingest(request: Request) -> JSONResponse:
        if not _ingest_configured():
            return JSONResponse({"state": "UNAVAILABLE", "reason": "INGEST_TOKEN_NOT_CONFIGURED", **ZERO_UPLIFT}, status_code=503)
        if not _authorized(request.headers.get("x-a11oy-numerics-ingest-key")):
            return JSONResponse({"state": "REFUSED", "reason": "INGEST_AUTHENTICATION_FAILED", **ZERO_UPLIFT}, status_code=401)
        try:
            payload = await _adapter._bounded_json_body(request)
            row = ingest_result(payload)
        except DatasetContractError as exc:
            return JSONResponse({"state": "REJECTED", "error": str(exc), **ZERO_UPLIFT}, status_code=422)
        except DatasetUnavailable as exc:
            return JSONResponse({"state": "UNAVAILABLE", "error": str(exc), **ZERO_UPLIFT}, status_code=503)
        return JSONResponse(row, status_code=201)

    return (
        "Numerics dataset registered: "
        f"{prefix}/status · cases · case detail · append-only results; proof uplift=0"
    )


__all__ = [
    "CASE_SCHEMA",
    "CURRICULUM_SCHEMA",
    "DatasetContractError",
    "DatasetUnavailable",
    "INGEST_SCHEMA",
    "ROW_SCHEMA",
    "dataset_status",
    "formula_curriculum",
    "get_case",
    "ingest_result",
    "list_cases",
    "list_results",
    "preregistration",
    "register",
]
