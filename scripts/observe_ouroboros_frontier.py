#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only projection of the fixed scheduled review's recorded evidence.

This provenance adapter does not fetch, extract, execute, sign, or admit actions.
Archive and receipt hashes bind bytes; they do not prove model correctness or a
durable ledger acknowledgement. Raw review text and candidate IDs stay local.
The producer contract is szl-ouroboros's codex-continuous-frontier workflow.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
import re
import stat
import zipfile
import zlib
from datetime import datetime, timedelta, timezone
from typing import Any

CONTROLLER_REPOSITORY = "szl-holdings/szl-ouroboros"
SECOND_BRAIN_REPOSITORY = "szl-holdings/szl-second-brain"
WORKFLOW = ".github/workflows/codex-continuous-frontier.yml"
SCHEMA = "szl.ouroboros.frontier-observation/v1"
MAX_AGE_SECONDS = 21_600
MAX_FUTURE_SECONDS = 300
MAX_ARCHIVE_BYTES = 2 * 1024 * 1024
MAX_MEMBER_BYTES = 512 * 1024
MAX_SAFE_INTEGER = 2**53 - 1
NONE_AUTHORITY = dict.fromkeys(
    ("training", "promotion", "execution", "merge", "provider_mutation"), "NONE"
)
STATES = {"UNAVAILABLE", "PENDING", "FAILED", "STALE", "REJECTED"}
SOURCE_PATH = "inputs/source-receipt.json"
SELECTION_PATH = "outputs/reviewer-selection.json"
REVIEW_PATH = "outputs/codex-review.json"
EXECUTION_PATH = "outputs/open-reviewer-execution.json"
LOOP_PATH = "outputs/ouroboros-frontier-loop-receipt.json"
FILE_PATHS = {SOURCE_PATH, SELECTION_PATH, REVIEW_PATH, EXECUTION_PATH, LOOP_PATH}
HEX40 = re.compile(r"[0-9a-f]{40}\Z")
HEX64 = re.compile(r"[0-9a-f]{64}\Z")
CANDIDATE_ID = re.compile(r"frontier:[0-9a-f]{32}\Z")
COMPACT_LIMITS = {
    "maximum_recommendations": 1, "summary_characters": 120,
    "title_characters": 80, "rationale_characters": 240,
    "risk_characters": 120, "maximum_evidence_ids": 2,
    "maximum_validation_steps": 2, "validation_step_characters": 120,
    "maximum_canonical_utf8_bytes": 1800,
}
LOOP_LABELS = {
    "modelMs": "MEASURED", "peakAttemptMs": "MEASURED",
    "overheadMs": "DERIVED", "serializationTaxMs": "DERIVED",
    "deadHopMs": "DERIVED", "steps": "MEASURED", "maxBudget": "DECLARED",
    "exit": "REPORTED", "receiptsInEqOut": "DOCTRINE", "wallMs": "MEASURED",
}
FORBIDDEN_TEXT = tuple(re.compile(pattern, re.I) for pattern in (
    r"\bbypass(?:ing|ed)?\b",
    r"\bdisable\s+(?:branch protection|signature|approval|authorization|safety)\b",
    r"\bauto(?:matic(?:ally)?|nomous(?:ly)?)?[- ]?merge\b",
    r"\bsilent(?:ly)?\s+(?:train|fine[- ]?tune|promote|deploy)\b",
    r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----",
    r"\bsk-[A-Za-z0-9_-]{24,}\b", r"\bgh[pousr]_[A-Za-z0-9]{30,}\b",
    r"\bhf_[A-Za-z0-9]{30,}\b",
))


class ObservationError(ValueError):
    """Rejected evidence; the message is a fixed, content-free reason code."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise ObservationError(reason)


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def _digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _integer(value: Any, *, minimum: int = 0, maximum: int = MAX_SAFE_INTEGER) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _hex(value: Any, pattern: re.Pattern[str] = HEX64) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def _keys(value: Any, keys: set[str], reason: str) -> dict:
    _require(isinstance(value, dict) and set(value) == keys, reason)
    return value


def _same(left: Any, right: Any) -> bool:
    # bool and integer are distinct evidence values, despite Python equality.
    return _canonical(left) == _canonical(right)


def _check_expected(expected: dict) -> dict:
    _require(isinstance(expected, dict), "EXPECTED_PACKET_INVALID")
    for key in ("controller_revision", "second_brain_revision"):
        _require(_hex(expected.get(key), HEX40), "EXPECTED_REVISION_INVALID")
    for key in ("state_file_sha256", "candidate_file_sha256", "candidate_set_sha256"):
        _require(_hex(expected.get(key)), "EXPECTED_DIGEST_INVALID")
    count, ids = expected.get("candidate_count"), expected.get("candidate_ids")
    _require(_integer(count, minimum=1, maximum=100_000), "EXPECTED_COUNT_INVALID")
    _require(isinstance(ids, (list, tuple, set, frozenset)) and len(ids) == count,
             "EXPECTED_CANDIDATES_INVALID")
    _require(all(_hex(item, CANDIDATE_ID) for item in ids), "EXPECTED_CANDIDATES_INVALID")
    _require(len(set(ids)) == count, "EXPECTED_CANDIDATES_INVALID")
    return expected


def _timestamp(value: Any) -> datetime:
    _require(isinstance(value, str) and len(value) <= 40, "RUN_TIMESTAMP_INVALID")
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ObservationError("RUN_TIMESTAMP_INVALID") from exc
    _require(result.tzinfo is not None and result.utcoffset() == timedelta(0),
             "RUN_TIMESTAMP_INVALID")
    return result.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _clock(now: datetime | None) -> datetime:
    value = datetime.now(timezone.utc) if now is None else now
    _require(isinstance(value, datetime) and value.tzinfo is not None,
             "OBSERVATION_CLOCK_INVALID")
    return value.astimezone(timezone.utc)


def _run_identity(run: dict, now: datetime) -> tuple[dict, datetime]:
    _require(isinstance(run, dict), "RUN_METADATA_INVALID")
    for key in ("repository", "head_repository"):
        repository = run.get(key)
        _require(isinstance(repository, dict)
                 and repository.get("full_name") == CONTROLLER_REPOSITORY
                 and _integer(repository.get("id"), minimum=1), "RUN_REPOSITORY_INVALID")
    _require(run["repository"]["id"] == run["head_repository"]["id"],
             "RUN_REPOSITORY_INVALID")
    _require(run.get("head_branch") == "main" and run.get("path") == WORKFLOW,
             "RUN_WORKFLOW_INVALID")
    _require(run.get("event") in ("schedule", "workflow_dispatch", "push"),
             "RUN_EVENT_INVALID")
    _require(_integer(run.get("id"), minimum=1)
             and _integer(run.get("run_attempt"), minimum=1)
             and _hex(run.get("head_sha"), HEX40), "RUN_IDENTITY_INVALID")
    status, conclusion = run.get("status"), run.get("conclusion")
    if status == "completed":
        _require(conclusion in ("success", "failure", "cancelled", "timed_out",
                                "action_required", "neutral", "skipped", "stale",
                                "startup_failure"), "RUN_CONCLUSION_INVALID")
    else:
        _require(status in ("queued", "in_progress", "waiting", "requested", "pending")
                 and conclusion is None, "RUN_STATUS_INVALID")
    observed = _timestamp(run.get("updated_at"))
    _require(observed <= now + timedelta(seconds=MAX_FUTURE_SECONDS),
             "RUN_TIMESTAMP_IN_FUTURE")
    projected = {
        "id": run["id"], "attempt": run["run_attempt"], "head_sha": run["head_sha"],
        "status": status, "conclusion": conclusion,
        "url": f"https://github.com/{CONTROLLER_REPOSITORY}/actions/runs/{run['id']}",
        "updated_at": _iso(observed),
    }
    return projected, observed


def _summary(expected: dict, state: str, reason: str, *, run: dict | None = None,
             observed: datetime | None = None) -> dict:
    value = {
        "schema": SCHEMA, "state": state, "reason": reason,
        "source": {
            "controller_repository": CONTROLLER_REPOSITORY,
            "controller_revision": expected["controller_revision"], "workflow": WORKFLOW,
            "second_brain_repository": SECOND_BRAIN_REPOSITORY,
            "second_brain_revision": expected["second_brain_revision"],
            "state_file_sha256": expected["state_file_sha256"],
            "candidate_file_sha256": expected["candidate_file_sha256"],
            "candidate_set_sha256": expected["candidate_set_sha256"],
            "candidate_count": expected["candidate_count"],
        },
        "run": run, "artifact": None,
        "observation": dict.fromkeys(("bounded", "terminated", "receipt_closed", "steps",
                                      "max_budget", "wall_ms", "exit", "review_state",
                                      "review_sha256", "recommendation_count")),
        "freshness": {
            "observed_at": _iso(observed) if observed is not None else None,
            "expires_at": _iso(observed + timedelta(seconds=MAX_AGE_SECONDS))
                          if observed is not None else None,
            "max_age_seconds": MAX_AGE_SECONDS,
        },
        "authority": dict(NONE_AUTHORITY),
        "claims": {
            "signature_verified": False, "review_is_accepted_truth": False,
            "production_verified": False, "private_graph_loaded": False,
            "measurement_scope": "RECORDED_REVIEW_ATTEMPT",
        },
    }
    value["observation_sha256"] = _digest(value)
    return value


def unavailable_observation(expected: dict, *, state: str, reason: str,
                            run: dict | None = None) -> dict:
    """Return no measurements; never echo arbitrary metadata or exception text."""
    _check_expected(expected)
    _require(isinstance(state, str) and state in STATES, "NONOBSERVED_STATE_INVALID")
    _require(isinstance(reason, str) and re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", reason),
             "REASON_CODE_INVALID")
    projected = observed = None
    if run is not None:
        try:
            projected, observed = _run_identity(run, _clock(None))
        except ObservationError:
            pass
    return _summary(expected, state, reason, run=projected, observed=observed)


def validate_run_status(expected: dict, run: dict, now: datetime | None = None) -> dict | None:
    """Preflight the latest run. None means its archive may be inspected next."""
    _check_expected(expected)
    clock = _clock(now)
    projected, observed = _run_identity(run, clock)
    if run["head_sha"] != expected["controller_revision"]:
        state, reason = "STALE", "CONTROLLER_REVISION_CHANGED"
    elif clock >= observed + timedelta(seconds=MAX_AGE_SECONDS):
        state, reason = "STALE", "REVIEW_OBSERVATION_EXPIRED"
    elif run["status"] != "completed":
        state, reason = "PENDING", "LATEST_REVIEW_PENDING"
    elif run["conclusion"] != "success":
        state, reason = "FAILED", "LATEST_REVIEW_FAILED"
    else:
        return None
    return _summary(expected, state, reason, run=projected, observed=observed)


def _artifact_metadata(archive: bytes, run: dict, artifact: dict) -> str:
    _require(isinstance(artifact, dict), "ARTIFACT_METADATA_INVALID")
    _require(_integer(artifact.get("id"), minimum=1)
             and artifact.get("name") == f"ouroboros-frontier-{run['id']}-{run['run_attempt']}"
             and artifact.get("expired") is False, "ARTIFACT_IDENTITY_INVALID")
    _require(_integer(artifact.get("size_in_bytes"), minimum=1, maximum=MAX_ARCHIVE_BYTES),
             "ARTIFACT_SIZE_INVALID")
    workflow_run = artifact.get("workflow_run")
    _require(isinstance(workflow_run, dict), "ARTIFACT_RUN_INVALID")
    for key, value in {
        "id": run["id"], "repository_id": run["repository"]["id"],
        "head_repository_id": run["head_repository"]["id"], "head_branch": "main",
        "head_sha": run["head_sha"],
    }.items():
        _require(_same(workflow_run.get(key), value), "ARTIFACT_RUN_INVALID")
    digest = artifact.get("digest")
    _require(isinstance(digest, str) and digest.startswith("sha256:")
             and _hex(digest[7:]), "ARTIFACT_DIGEST_UNAVAILABLE")
    _require(isinstance(archive, bytes) and 0 < len(archive) <= MAX_ARCHIVE_BYTES,
             "ARCHIVE_SIZE_INVALID")
    actual = hashlib.sha256(archive).hexdigest()
    _require(actual == digest[7:], "ARTIFACT_DIGEST_MISMATCH")
    return actual


def _strict_json(raw: bytes) -> dict:
    def pairs(items: list[tuple[str, Any]]) -> dict:
        result = {}
        for key, value in items:
            _require(key not in result, "JSON_DUPLICATE_KEY")
            result[key] = value
        return result

    def constant(_: str) -> None:
        raise ObservationError("JSON_NUMBER_INVALID")

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                           parse_constant=constant)
        stack = [(value, 0)]
        nodes = 0
        while stack:
            item, depth = stack.pop()
            nodes += 1
            _require(depth <= 32 and nodes <= 30_000, "JSON_COMPLEXITY_LIMIT")
            if isinstance(item, dict):
                stack.extend((child, depth + 1) for child in item.values())
                stack.extend((key, depth + 1) for key in item)
            elif isinstance(item, list):
                stack.extend((child, depth + 1) for child in item)
            elif isinstance(item, float):
                _require(math.isfinite(item), "JSON_NUMBER_INVALID")
            elif isinstance(item, str):
                item.encode("utf-8")
        _require(isinstance(value, dict), "JSON_OBJECT_REQUIRED")
        return value
    except (UnicodeError, ValueError, RecursionError, OverflowError) as exc:
        if isinstance(exc, ObservationError):
            raise
        raise ObservationError("JSON_INVALID") from exc


def _read_archive(archive: bytes) -> dict[str, dict]:
    result: dict[str, dict] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            members = bundle.infolist()
            _require(1 <= len(members) <= len(FILE_PATHS) + 2, "ARCHIVE_ENTRY_LIMIT")
            seen: set[str] = set()
            total = 0
            for member in members:
                name = member.filename
                _require(name not in seen, "ARCHIVE_DUPLICATE_PATH")
                seen.add(name)
                _require(member.orig_filename == name
                         and (name in FILE_PATHS or name in ("inputs/", "outputs/")),
                         "ARCHIVE_PATH_INVALID")
                mode = stat.S_IFMT(member.external_attr >> 16)
                _require(mode in (0, stat.S_IFDIR if member.is_dir() else stat.S_IFREG),
                         "ARCHIVE_FILE_TYPE_INVALID")
                _require(not member.flag_bits & 1
                         and member.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED),
                         "ARCHIVE_ENCODING_INVALID")
                _require(0 <= member.file_size <= MAX_MEMBER_BYTES
                         and 0 <= member.compress_size <= MAX_ARCHIVE_BYTES,
                         "ARCHIVE_MEMBER_LIMIT")
                total += member.file_size
                _require(total <= MAX_ARCHIVE_BYTES, "ARCHIVE_INFLATED_LIMIT")
                if member.is_dir():
                    _require(member.file_size == 0, "ARCHIVE_DIRECTORY_INVALID")
                    continue
                with bundle.open(member) as stream:
                    raw = stream.read(MAX_MEMBER_BYTES + 1)
                _require(len(raw) == member.file_size and len(raw) <= MAX_MEMBER_BYTES,
                         "ARCHIVE_MEMBER_LIMIT")
                result[name] = _strict_json(raw)
    except (zipfile.BadZipFile, zipfile.LargeZipFile, OSError, EOFError,
            RuntimeError, zlib.error) as exc:
        raise ObservationError("ARCHIVE_INVALID") from exc
    _require({SOURCE_PATH, SELECTION_PATH, LOOP_PATH, REVIEW_PATH} <= set(result),
             "ARCHIVE_REQUIRED_FILE_MISSING")
    return result


def _receipt(value: dict) -> None:
    claimed = value.get("receipt_sha256")
    _require(_hex(claimed), "RECEIPT_DIGEST_INVALID")
    _require(_digest({key: item for key, item in value.items() if key != "receipt_sha256"})
             == claimed, "RECEIPT_DIGEST_MISMATCH")


def _source_current(source: dict, expected: dict) -> bool:
    _keys(source, {"schema", "source_repository", "source_ref", "source_revision",
                   "state_path", "state_sha256", "candidates_path", "candidates_sha256",
                   "candidate_count", "candidate_set_sha256", "source_count",
                   "candidate_state", "content_scope", "authority", "receipt_sha256"},
          "SOURCE_SCHEMA_INVALID")
    _receipt(source)
    _require(source["schema"] == "szl.ouroboros.codex-frontier-source/v1"
             and source["source_repository"] == SECOND_BRAIN_REPOSITORY
             and source["source_ref"] == "main"
             and source["state_path"] == "data/frontier-state.v1.json"
             and source["candidates_path"] == "data/frontier-candidates.public.jsonl"
             and source["candidate_state"] == "DISCOVERED_REVIEW_REQUIRED"
             and source["content_scope"] == "PUBLIC_SOURCE_REVIEW_MATERIAL",
             "SOURCE_IDENTITY_INVALID")
    _require(_same(source["authority"], NONE_AUTHORITY), "SOURCE_AUTHORITY_INVALID")
    _require(_hex(source["source_revision"], HEX40)
             and all(_hex(source[key]) for key in (
                 "state_sha256", "candidates_sha256", "candidate_set_sha256"))
             and _integer(source["candidate_count"], minimum=1, maximum=100_000)
             and _integer(source["source_count"], minimum=1,
                          maximum=source["candidate_count"]), "SOURCE_BINDING_INVALID")
    return all(source[left] == expected[right] for left, right in (
        ("source_revision", "second_brain_revision"),
        ("state_sha256", "state_file_sha256"),
        ("candidates_sha256", "candidate_file_sha256"),
        ("candidate_set_sha256", "candidate_set_sha256"),
        ("candidate_count", "candidate_count"),
    ))


def _selection(value: dict, run: dict) -> str:
    _keys(value, {"schema", "workflow_event", "controller_revision", "requested_reviewer",
                  "selected_reviewer", "codex_authority_enabled"}, "SELECTION_SCHEMA_INVALID")
    _require(value["schema"] == "szl.ouroboros.reviewer-selection/v1"
             and value["workflow_event"] == run["event"]
             and value["controller_revision"] == run["head_sha"], "SELECTION_RUN_MISMATCH")
    selected, requested = value["selected_reviewer"], value["requested_reviewer"]
    _require(selected in ("codex", "local-gguf") and requested in ("auto", "local-gguf")
             and value["codex_authority_enabled"] is (selected == "codex")
             and (requested == "auto" or selected == "local-gguf"),
             "REVIEWER_SELECTION_INVALID")
    return "codex" if selected == "codex" else "open_reviewer"


def _text(value: Any, limit: int) -> str:
    _require(isinstance(value, str), "REVIEW_TEXT_INVALID")
    text = value.strip()
    _require(0 < len(text) <= limit and not any(p.search(text) for p in FORBIDDEN_TEXT),
             "REVIEW_TEXT_INVALID")
    return text


def _review(value: dict, expected: dict) -> dict:
    value = copy.deepcopy(value)
    _keys(value, {"schema", "state", "candidate_set_sha256", "summary", "recommendations",
                  "authority"}, "REVIEW_SCHEMA_INVALID")
    _require(value["schema"] == "szl.codex.frontier-review/v1"
             and value["state"] in ("REVIEW_PROPOSED", "NO_ACTION_RECOMMENDED", "BLOCKED")
             and value["candidate_set_sha256"] == expected["candidate_set_sha256"],
             "REVIEW_BINDING_INVALID")
    _require(_same(value["authority"], NONE_AUTHORITY), "REVIEW_AUTHORITY_INVALID")
    value["summary"] = _text(value["summary"], 2000)
    recommendations = value["recommendations"]
    _require(isinstance(recommendations, list) and len(recommendations) <= 12,
             "REVIEW_RECOMMENDATIONS_INVALID")
    offered, seen = set(expected["candidate_ids"]), set()
    for item in recommendations:
        _keys(item, {"id", "priority", "target_repository", "title", "rationale",
                     "evidence_candidate_ids", "recommended_change_type", "validation", "risk"},
              "RECOMMENDATION_SCHEMA_INVALID")
        ident = item["id"]
        _require(isinstance(ident, str) and re.fullmatch(r"R[0-9]{2}", ident) is not None
                 and ident not in seen, "RECOMMENDATION_ID_INVALID")
        seen.add(ident)
        _require(item["priority"] in ("P0", "P1", "P2", "P3")
                 and item["target_repository"] in tuple("szl-holdings/" + name for name in (
                     "szl-second-brain", "anatomy", "a11oy", "szl-formulas", "szl-forge",
                     "szl-nemo", "szl-ouroboros"))
                 and item["recommended_change_type"] in (
                     "TEST", "DOCUMENTATION", "OBSERVABILITY", "INTEGRATION",
                     "PERFORMANCE_EXPERIMENT", "SECURITY_HARDENING", "RESEARCH_EXPERIMENT",
                     "NO_CHANGE"), "RECOMMENDATION_ENUM_INVALID")
        evidence = item["evidence_candidate_ids"]
        _require(isinstance(evidence, list) and 1 <= len(evidence) <= 8
                 and all(isinstance(entry, str) and entry in offered for entry in evidence)
                 and len(set(evidence)) == len(evidence), "REVIEW_EVIDENCE_INVALID")
        validation = item["validation"]
        _require(isinstance(validation, list) and 1 <= len(validation) <= 8,
                 "REVIEW_VALIDATION_INVALID")
        item["validation"] = [_text(step, 300) for step in validation]
        for key, limit in (("title", 180), ("rationale", 1200), ("risk", 600)):
            item[key] = _text(item[key], limit)
    _require(value["state"] != "NO_ACTION_RECOMMENDED" or not recommendations,
             "REVIEW_STATE_INVALID")
    _require(value["state"] != "REVIEW_PROPOSED" or bool(recommendations),
             "REVIEW_STATE_INVALID")
    return value


def _execution(value: dict, review: dict, expected: dict, review_sha: str,
               active_model: str) -> None:
    _keys(value, {"schema", "state", "source_revision", "candidate_set_sha256",
                  "selected_candidate_ids", "selected_candidate_count", "review_scope",
                  "compact_output_limits", "canonical_review_utf8_bytes", "prompt_sha256",
                  "raw_output_sha256", "review_sha256", "admission", "provider", "authority",
                  "claims", "receipt_sha256"}, "EXECUTION_SCHEMA_INVALID")
    _receipt(value)
    _require(value["schema"] == "szl.ouroboros.open-frontier-review-execution/v1"
             and value["state"] == "OPEN_WEIGHT_REVIEW_OUTPUT_ADMITTED"
             and value["source_revision"] == expected["second_brain_revision"]
             and value["candidate_set_sha256"] == expected["candidate_set_sha256"]
             and value["review_sha256"] == review_sha
             and _hex(value["prompt_sha256"]) and _hex(value["raw_output_sha256"]),
             "EXECUTION_BINDING_INVALID")
    ids = value["selected_candidate_ids"]
    offered = set(expected["candidate_ids"])
    _require(isinstance(ids, list) and 1 <= len(ids) <= 24
             and all(isinstance(item, str) and item in offered for item in ids)
             and len(set(ids)) == len(ids)
             and _integer(value["selected_candidate_count"], minimum=1)
             and value["selected_candidate_count"] == len(ids), "EXECUTION_EVIDENCE_INVALID")
    _require(_same(value["review_scope"], {
        "kind": "SELECTED_PUBLIC_CANDIDATE_EXCERPTS_ONLY",
        "source_candidate_count": expected["candidate_count"], "full_portfolio_review_claimed": False,
    }) and _same(value["compact_output_limits"], COMPACT_LIMITS), "EXECUTION_SCOPE_INVALID")
    _require(_same(value["admission"], {
        "state": "MODEL_OUTPUT_ADMITTED", "model_output_admitted": True, "failure_code": None,
        "validator": "scripts.finalize_codex_frontier_review.validate_review",
        "additional_validator": "scripts.run_open_frontier_review.validate_compact_review",
        "validation_error_echoed": False,
    }), "EXECUTION_ADMISSION_INVALID")
    provider = value["provider"]
    provider_keys = {
        "provider", "model", "model_repository", "model_revision", "model_filename",
        "model_sha256", "model_size", "key_required", "native_schema_grammar",
        "json_object_grammar", "bounded_generation_grammar", "generation_grammar_sha256",
        "independent_post_generation_validation", "finish_reason", "threads",
        "context_tokens", "max_tokens", "seed", "temperature", "latency_ms",
    }
    _require(isinstance(provider, dict)
             and set(provider) in (provider_keys, provider_keys | {"usage"}),
             "EXECUTION_PROVIDER_INVALID")
    _require(provider["provider"] == "llama-cpp-python"
             and provider["model_repository"] == "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF"
             and _hex(provider["model_revision"], HEX40)
             and provider["model_filename"] == "SZL-Khipu-1.5B-Q4_K_M.gguf"
             and provider["model"] == active_model == (
                 f"{provider['model_repository']}@{provider['model_revision']}:"
                 f"{provider['model_filename']}")
             and _hex(provider["model_sha256"]) and _hex(provider["generation_grammar_sha256"])
             and _integer(provider["model_size"], minimum=1)
             and provider["key_required"] is False
             and provider["native_schema_grammar"] is False
             and provider["json_object_grammar"] is True
             and provider["bounded_generation_grammar"] == "szl.ouroboros.compact-ascii-json/v1"
             and provider["independent_post_generation_validation"] is True,
             "EXECUTION_PROVIDER_BINDING_INVALID")
    for key in ("threads", "context_tokens", "max_tokens"):
        _require(_integer(provider[key], minimum=1), "EXECUTION_PROVIDER_BUDGET_INVALID")
    _require(_integer(provider["seed"])
             and type(provider["temperature"]) in (int, float) and provider["temperature"] == 0
             and type(provider["latency_ms"]) in (int, float)
             and 0 <= provider["latency_ms"] <= 3_600_000
             and provider["finish_reason"] in (None, "stop", "length"),
             "EXECUTION_PROVIDER_BUDGET_INVALID")
    if "usage" in provider:
        usage = provider["usage"]
        _require(isinstance(usage, dict)
                 and set(usage) <= {"prompt_tokens", "completion_tokens", "total_tokens"}
                 and all(_integer(count) for count in usage.values()),
                 "EXECUTION_PROVIDER_USAGE_INVALID")
    claims = value["claims"]
    _require(isinstance(claims, dict)
             and type(claims.get("bounded_generation_grammar_used")) is bool
             and _same(claims, {
                 "model_output_is_untrusted": True, "independent_validation_required": True,
                 "native_schema_grammar_used": False,
                 "bounded_generation_grammar_used": True,
                 "private_graph_loaded": False, "weights_modified": False,
                 "recommendations_executed": False, "lambda": "CONJECTURE_1",
             })
             and _same(value["authority"], NONE_AUTHORITY), "EXECUTION_AUTHORITY_INVALID")
    encoded = _canonical(review)
    _require(_integer(value["canonical_review_utf8_bytes"], minimum=1)
             and value["canonical_review_utf8_bytes"] == len(encoded)
             and len(encoded) <= COMPACT_LIMITS["maximum_canonical_utf8_bytes"]
             and len(review["summary"]) <= COMPACT_LIMITS["summary_characters"]
             and len(review["recommendations"]) <= COMPACT_LIMITS["maximum_recommendations"],
             "EXECUTION_COMPACT_LIMIT_INVALID")
    for item in review["recommendations"]:
        _require(set(item["evidence_candidate_ids"]) <= set(ids)
                 and len(item["evidence_candidate_ids"]) <= COMPACT_LIMITS["maximum_evidence_ids"]
                 and len(item["validation"]) <= COMPACT_LIMITS["maximum_validation_steps"]
                 and all(len(step) <= COMPACT_LIMITS["validation_step_characters"]
                         for step in item["validation"])
                 and all(len(item[key]) <= COMPACT_LIMITS[f"{key}_characters"]
                         for key in ("title", "rationale", "risk")), "EXECUTION_COMPACT_LIMIT_INVALID")


def _loop_measurements(loop: dict, active: str) -> dict:
    _keys(loop, {"steps", "maxBudget", "withinBudget", "boundedDoctrine", "exit", "trace",
                 "doctrine", "receiptsInEqOut", "receiptsInEqOutBasis", "modelMs", "overheadMs",
                 "peakAttemptMs", "serializationTaxMs", "deadHopMs", "wallMs", "servedHopIndex",
                 "wallLessThanModel", "labels", "timingBasis"}, "LOOP_SCHEMA_INVALID")
    _require(_integer(loop["steps"], minimum=1, maximum=1)
             and _integer(loop["maxBudget"], minimum=1, maximum=1)
             and loop["withinBudget"] is True and loop["receiptsInEqOut"] is True
             and loop["exit"] == "converged"
             and _integer(loop["servedHopIndex"], maximum=0)
             and _same(loop["trace"], [{"n": 1, "label": f"{active}-frontier-review"}]),
             "LOOP_CLOSURE_INVALID")
    _require(loop["boundedDoctrine"] == "steps ≤ maxBudget (bounded, terminating)"
             and loop["doctrine"] == "bounded, terminating, receipt-closed"
             and loop["receiptsInEqOutBasis"] == (
                 "DOCTRINE invariant (one receipt trail in, one out) — NOT a mathematical proof")
             and _same(loop["labels"], LOOP_LABELS)
             and isinstance(loop["timingBasis"], str) and 0 < len(loop["timingBasis"]) <= 2000,
             "LOOP_LABEL_INVALID")
    for key in ("wallMs", "modelMs", "peakAttemptMs", "overheadMs", "serializationTaxMs", "deadHopMs"):
        number = loop[key]
        _require(type(number) in (int, float) and 0 <= number <= 3_600_000
                 and math.isfinite(number), "LOOP_TIMING_INVALID")
    wall, model = loop["wallMs"], loop["modelMs"]
    _require(loop["wallLessThanModel"] is False and wall + 1e-9 >= model
             and math.isclose(loop["peakAttemptMs"], model, rel_tol=1e-12, abs_tol=1e-9)
             and math.isclose(loop["overheadMs"], max(wall - model, 0), rel_tol=1e-12, abs_tol=1e-9)
             and loop["serializationTaxMs"] == 0 and loop["deadHopMs"] == 0,
             "LOOP_ACCOUNTING_INVALID")
    # The current workflow records integer millisecond differences. Preserve
    # their exact value and JSON.stringify compatibility; never round a window.
    if float(wall).is_integer():
        wall = int(wall)
    else:
        _require(wall >= 0.0001, "LOOP_TIMING_PRECISION_UNSUPPORTED")
    return {"bounded": True, "terminated": True, "receipt_closed": True,
            "steps": loop["steps"], "max_budget": loop["maxBudget"],
            "wall_ms": wall, "exit": loop["exit"]}


def observe_receipt(archive: bytes, *, expected: dict, run: dict, artifact: dict,
                    now: datetime | None = None) -> dict:
    """Validate one selected run's evidence and publish only an aggregate view."""
    preflight = validate_run_status(expected, run, now)
    if preflight is not None:
        return preflight
    projected, observed = _run_identity(run, _clock(now))
    archive_sha = _artifact_metadata(archive, run, artifact)
    files = _read_archive(archive)
    source, loop = files[SOURCE_PATH], files[LOOP_PATH]
    _keys(loop, {"schema", "state", "source", "preparation", "codex", "open_reviewer",
                 "ouroboros", "authority", "claims", "receipt_sha256"}, "RECEIPT_SCHEMA_INVALID")
    _receipt(loop)
    _require(loop["schema"] == "szl.ouroboros.codex-frontier-loop/v1"
             and _same(loop["source"], source), "EMBEDDED_SOURCE_MISMATCH")
    active = _selection(files[SELECTION_PATH], run)
    if not _source_current(source, expected):
        return _summary(expected, "STALE", "SECOND_BRAIN_PACKET_CHANGED",
                        run=projected, observed=observed)
    _require(_same(loop["authority"], NONE_AUTHORITY) and _same(loop["claims"], {
        "candidate_material_is_training_data": False, "review_is_accepted_truth": False,
        "recommendations_executed": False, "weights_modified": False,
        "private_graph_loaded": False, "lambda": "CONJECTURE_1",
    }), "LOOP_AUTHORITY_INVALID")
    _require(_same(loop["preparation"], {"outcome": "success", "validated": True}),
             "SOURCE_PREPARATION_INVALID")
    for key in ("codex", "open_reviewer"):
        fields = {"attempted", "outcome", "model", "review_sha256", "review"}
        _keys(loop[key], fields | ({"configured"} if key == "codex" else set()),
              "REVIEWER_SCHEMA_INVALID")
    _require(loop["codex"]["configured"] is (active == "codex"), "REVIEWER_SELECTION_MISMATCH")
    inactive = loop["open_reviewer" if active == "codex" else "codex"]
    _require(inactive["attempted"] is False and inactive["outcome"] == "not_attempted"
             and all(inactive[key] is None for key in ("model", "review", "review_sha256")),
             "MULTIPLE_REVIEWERS_REJECTED")
    reviewer = loop[active]
    _require(reviewer["attempted"] is True and reviewer["outcome"] == "success"
             and isinstance(reviewer["model"], str) and 0 < len(reviewer["model"]) <= 400,
             "ACTIVE_REVIEWER_INVALID")
    review = _review(files[REVIEW_PATH], expected)
    review_sha = _digest(review)
    _require(_same(review, reviewer["review"]) and reviewer["review_sha256"] == review_sha
             and loop["state"] == review["state"], "REVIEW_DIGEST_MISMATCH")
    _require(loop["state"] in ("REVIEW_PROPOSED", "NO_ACTION_RECOMMENDED"),
             "SUCCESSFUL_RUN_REVIEW_STATE_INVALID")
    if active == "open_reviewer":
        _require(EXECUTION_PATH in files, "EXECUTION_RECEIPT_MISSING")
        _execution(files[EXECUTION_PATH], review, expected, review_sha, reviewer["model"])
    else:
        _require(EXECUTION_PATH not in files, "INACTIVE_REVIEWER_EVIDENCE_REJECTED")
    measurements = _loop_measurements(loop["ouroboros"], active)
    result = _summary(expected, "OBSERVED", "CURRENT_REVIEW_RECEIPT_VALIDATED",
                      run=projected, observed=observed)
    result["artifact"] = {"id": artifact["id"], "name": artifact["name"],
                          "archive_sha256": archive_sha, "receipt_sha256": loop["receipt_sha256"]}
    result["observation"] = {**measurements, "review_state": review["state"],
                             "review_sha256": review_sha,
                             "recommendation_count": len(review["recommendations"])}
    result["observation_sha256"] = _digest({key: item for key, item in result.items()
                                            if key != "observation_sha256"})
    return result
