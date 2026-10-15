#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Independent readiness admission of signed, native execution observations.

The passive probe remains read-only and keeps all five NOT_PROBED rows. This
module never executes requests, selects identities from evidence, signs, writes
provider state, or treats an export wrapper's claims as authority.
"""
from __future__ import annotations

from datetime import datetime, timezone
import importlib.util
import math
from pathlib import Path
import re
import sys

# The deployed source directory is fixed by this module, not cwd or a request.
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    # Isolated CLI invocations (-I) still import only the reviewed source root.
    sys.path.insert(0, str(ROOT))


def _load(relative, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


acceptance = _load("tools/execution_acceptance.py", "_readiness_execution_acceptance")


class CombinedEvidenceError(ValueError):
    pass


def require(value, code):
    if value is not True:
        raise CombinedEvidenceError(code)


def canonical_matrix(path=None):
    """Bind production scope to exact source bytes; an override may only copy them."""
    canonical_path = ROOT / "tools/readiness-harness/tabs.json"
    raw = acceptance.read_file(str(canonical_path))
    if path is not None:
        require(acceptance.read_file(str(path)) == raw, "CANONICAL_MATRIX_BYTES_REQUIRED")
    return acceptance.strict_json(raw)


def context_from_independent_file(path, *, expected_source, expected_runtime_revision,
                                  expected_runtime_boot_id, expected_run_nonce):
    """Load deployment-selected public pins with separate expected identities.

    The path and four expectations are caller-owned inputs. They must never be
    read from the bundle, a receipt, its plan, or an artifact archive. Runtime
    consumers instead use the observer's retained-digest context lookup.
    """
    require(bool(path), "INDEPENDENT_AUTHORITY_FILE_REQUIRED")
    value = acceptance.strict_json(acceptance.read_file(path, 16384))
    acceptance.fields(value, "schema approval_public_pem approval_key_id runtime_public_pem runtime_key_id",
                      "INVALID_AUTHORITY_CONFIGURATION")
    require(value["schema"] == "szl.execution-authority-pins/v1", "AUTHORITY_SCHEMA_MISMATCH")
    context = acceptance.AdmissionContext(
        expected_source, expected_runtime_revision, expected_runtime_boot_id, expected_run_nonce,
        value["approval_public_pem"].encode(), value["approval_key_id"],
        value["runtime_public_pem"].encode(), value["runtime_key_id"])
    _context(context, expected_source)
    return context


def _context(context, source):
    # Dataclass identity may differ between explicitly loaded source modules.
    # Read only the fixed fields from an actual frozen admission-context class;
    # never coerce a submitted dictionary into trusted context.
    require(context is not None and type(context).__name__ == "AdmissionContext"
            and getattr(type(context), "__dataclass_params__", None) is not None
            and type(context).__dataclass_params__.frozen is True,
            "INDEPENDENT_EXECUTION_CONTEXT_REQUIRED")
    require(context.source_revision == source, "EXECUTION_SOURCE_MISMATCH")
    require(acceptance.SHA40.fullmatch(context.source_revision or "") is not None
            and acceptance.SHA40.fullmatch(context.runtime_revision or "") is not None,
            "EXACT_EXECUTION_REVISIONS_REQUIRED")
    acceptance.text(context.runtime_boot_id, "RUNTIME_BOOT_REQUIRED")
    require(acceptance.HEX64.fullmatch(context.run_nonce or "") is not None, "RUN_NONCE_REQUIRED")
    require(context.authority_key_id != context.runtime_key_id, "SEPARATE_APPROVAL_AUTHORITY_REQUIRED")
    acceptance.public_key(context.authority_public_key, context.authority_key_id)
    acceptance.public_key(context.runtime_public_key, context.runtime_key_id)


def validate_passive(payload, matrix, *, source, now=None):
    """Verify exact matrix coverage without relabeling unexecuted POSTs."""
    require(type(payload) is dict and type(matrix) is dict, "PASSIVE_MATRIX_REQUIRED")
    require(payload.get("schema") == "szl.readiness-verdict/v1"
            and payload.get("harness") == "a11oy-readiness probe"
            and payload.get("doctrine") == "v11" and payload.get("base") == acceptance.ORIGIN,
            "PASSIVE_IDENTITY_MISMATCH")
    checked = payload.get("checkedAt")
    require(type(checked) is str and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z", checked) is not None,
        "PASSIVE_TIME_INVALID")
    current = datetime.now(timezone.utc) if now is None else now
    require(0 <= (current - acceptance.moment(checked)).total_seconds() <= 3600,
            "PASSIVE_TIME_INVALID")
    specs, rows, summary = matrix.get("endpoints"), payload.get("results"), payload.get("summary")
    require(type(specs) is dict and 0 < len(specs) <= 1000 and type(rows) is list
            and len(rows) == len(specs) and type(summary) is dict, "PASSIVE_COVERAGE_INCOMPLETE")
    require(all(type(row) is dict and type(row.get("path")) is str for row in rows),
            "PASSIVE_ROW_INVALID")
    require(len({row["path"] for row in rows}) == len(rows)
            and {row["path"] for row in rows} == set(specs), "PASSIVE_MATRIX_MISMATCH")
    mutation_paths = set(acceptance.CONTRACTS.values())
    require(mutation_paths <= set(specs), "FIVE_MUTATION_CONTRACTS_REQUIRED")
    skipped, degraded = set(), 0
    for row in rows:
        path = row["path"]
        spec = specs[path]
        require(type(spec) is dict and row.get("method") == spec.get("method", "GET"),
                "PASSIVE_METHOD_MISMATCH")
        require(all(row.get(name) is False for name in ("lie", "unreachable", "throttled")),
                "PASSIVE_RESULT_FAILED")
        if path in mutation_paths:
            require(spec.get("method") == "POST" and spec.get("required", True) is True,
                    "MUTATION_CONTRACT_WEAKENED")
            require(row.get("skipped") is True and row.get("runtimeState") == "NOT_PROBED"
                    and row.get("required") is True and type(row.get("samples")) is int
                    and row["samples"] == 0 and row.get("status") is None
                    and row.get("degraded") is False
                    and all(row.get(name) is None for name in ("schemaOk", "citationOk", "labelPolicyOk", "freshOk")),
                    "PASSIVE_MUTATION_ROW_RELABELED")
            skipped.add(path)
            continue
        require(spec.get("method", "GET") in ("GET", "HEAD"), "UNRECOGNIZED_MUTATION_CONTRACT")
        require(row.get("skipped", False) is False and type(row.get("samples")) is int
                and row["samples"] > 0 and type(row.get("degraded")) is bool,
                "PASSIVE_RESULT_NOT_PROBED")
        require(all(row.get(name) is True for name in ("schemaOk", "citationOk", "labelPolicyOk"))
                and row.get("freshOk") is not False, "PASSIVE_RESULT_FAILED")
        require(spec.get("freshnessSLA") is None or row.get("freshOk") is True,
                "PASSIVE_FRESHNESS_UNAVAILABLE")
        require(type(row.get("status")) is int
                and row["status"] in spec.get("degradedRules", {}).get("allowStatuses", [200]),
                "PASSIVE_STATUS_FAILED")
        if row["degraded"]:
            require(spec.get("required", True) is False or spec.get("degradedBlocksReadiness", True) is False,
                    "PASSIVE_REQUIRED_SOURCE_UNAVAILABLE")
            degraded += 1
    require(skipped == mutation_paths, "FIVE_NOT_PROBED_ROWS_REQUIRED")
    counts = {"endpoints": len(rows), "ok": len(rows) - 5 - degraded,
              "skippedStateChanging": 5, "requiredNotProbed": 5, "degraded": degraded,
              "blockingDegraded": 0, "lies": 0, "unreachable": 0, "throttled": 0}
    require(all(type(summary.get(k)) is int and summary[k] == v for k, v in counts.items()),
            "PASSIVE_SUMMARY_MISMATCH")
    latency = summary.get("p95_worst")
    require(type(latency) in (int, float) and math.isfinite(latency) and latency >= 0,
            "PASSIVE_LATENCY_INVALID")
    require(payload.get("sourceRevision") == source
            and payload.get("sourceRevisionBefore") == source
            and payload.get("sourceRevisionAfter") == source
            and payload.get("sourceRevisionStatus") == "OBSERVED", "PASSIVE_SOURCE_BRACKET_INVALID")
    return sorted(skipped)


def validate_execution(bundle, context, *, source, now=None):
    """Recheck every cryptographic binding and fixed native semantic predicate."""
    now = datetime.now(timezone.utc) if now is None else now
    _context(context, source)
    # An outer export's publication_eligible or storage_acknowledgment cannot
    # substitute for a real raw bundle or current service-owned context.
    report = acceptance.validate(bundle, context, now=now)
    plan = acceptance.validate_plan(bundle["plan"], context, now=now)
    native = _load("observer_adapters.py", "_readiness_native_observation_adapters")
    native.validate_fixed_plan(plan)
    planned = {case["id"]: case for case in plan["cases"]}
    public = acceptance.public_key(context.runtime_public_key, context.runtime_key_id)
    for row in bundle["observations"]:
        receipt = acceptance.verify(row["receipt"], acceptance.RECEIPT_TYPE, public, context.runtime_key_id)
        native.validate_native_observation(
            planned[receipt["case_id"]], receipt["response_status"],
            acceptance.decode(row["response_b64"]), acceptance.decode(row["readback_b64"]),
            context.runtime_public_key, context.runtime_key_id)
    return {
        "schema": "szl.readiness-execution-coverage/v1",
        "bundle_sha256": acceptance.digest(acceptance.canonical(bundle)),
        "plan_sha256": report["plan_sha256"], "case_ids": sorted(acceptance.CONTRACTS),
        "receipt_ids": report["receipt_ids"], "source_revision": context.source_revision,
        "runtime_revision": context.runtime_revision, "runtime_boot_id": context.runtime_boot_id,
        "run_nonce": context.run_nonce, "authority_key_id": context.authority_key_id,
        "runtime_key_id": context.runtime_key_id, "requiredExecutionCovered": 5,
        "passiveRequiredNotProbed": 5,
    }


def validate_combined(payload, matrix, bundle, context, *, source, now=None):
    validate_passive(payload, matrix, source=source, now=now)
    return validate_execution(bundle, context, source=source, now=now)
