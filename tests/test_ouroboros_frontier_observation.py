#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline adversarial tests; all review/run fixtures in this file are synthetic.

The fixture shapes follow the fixed producer's prepare/finalize/open-reviewer
receipts. No fixture is represented as a hosted reviewer observation.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import stat
import warnings
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from scripts import observe_ouroboros_frontier as observer


NOW = datetime(2026, 10, 8, 22, 0, 0, tzinfo=timezone.utc)
AUTHORITY = dict.fromkeys(("training", "promotion", "execution", "merge", "provider_mutation"), "NONE")
SENTINEL = "Synthetic review text must never reach a public observation."
MODEL = ("SZLHOLDINGS/SZL-Khipu-1.5B-GGUF@" + "d" * 40 + ":SZL-Khipu-1.5B-Q4_K_M.gguf")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def seal(value):
    value["receipt_sha256"] = digest({key: item for key, item in value.items() if key != "receipt_sha256"})
    return value


def packet(local=False):
    expected = {
        "controller_revision": "a" * 40, "second_brain_revision": "b" * 40,
        "state_file_sha256": "1" * 64, "candidate_file_sha256": "2" * 64,
        "candidate_set_sha256": "3" * 64, "candidate_count": 2,
        "candidate_ids": ["frontier:" + "4" * 32, "frontier:" + "5" * 32],
    }
    run = {
        "repository": {"id": 77, "full_name": "szl-holdings/szl-ouroboros"},
        "head_repository": {"id": 77, "full_name": "szl-holdings/szl-ouroboros"},
        "head_branch": "main", "path": ".github/workflows/codex-continuous-frontier.yml",
        "head_sha": expected["controller_revision"], "id": 1234, "run_attempt": 2,
        "event": "schedule", "status": "completed", "conclusion": "success",
        "updated_at": "2026-10-08T21:00:00Z", "html_url": "https://untrusted.invalid/ignored",
    }
    source = seal({
        "schema": "szl.ouroboros.codex-frontier-source/v1",
        "source_repository": "szl-holdings/szl-second-brain", "source_ref": "main",
        "source_revision": expected["second_brain_revision"],
        "state_path": "data/frontier-state.v1.json", "state_sha256": expected["state_file_sha256"],
        "candidates_path": "data/frontier-candidates.public.jsonl",
        "candidates_sha256": expected["candidate_file_sha256"],
        "candidate_count": 2, "candidate_set_sha256": expected["candidate_set_sha256"],
        "source_count": 1, "candidate_state": "DISCOVERED_REVIEW_REQUIRED",
        "content_scope": "PUBLIC_SOURCE_REVIEW_MATERIAL", "authority": dict(AUTHORITY),
    })
    review = {
        "schema": "szl.codex.frontier-review/v1", "state": "REVIEW_PROPOSED",
        "candidate_set_sha256": expected["candidate_set_sha256"], "summary": SENTINEL,
        "recommendations": [{
            "id": "R01", "priority": "P2", "target_repository": "szl-holdings/a11oy",
            "title": "Check a read-only receipt", "rationale": "Synthetic evidence for a parser test.",
            "evidence_candidate_ids": [expected["candidate_ids"][0]],
            "recommended_change_type": "TEST", "validation": ["Exercise a rejected input."],
            "risk": "Test data only.",
        }],
        "authority": dict(AUTHORITY),
    }
    inactive = {"attempted": False, "outcome": "not_attempted", "model": None,
                "review_sha256": None, "review": None}
    active = {"attempted": True, "outcome": "success", "model": MODEL if local else "fixture-codex",
              "review_sha256": digest(review), "review": copy.deepcopy(review)}
    label = "open_reviewer" if local else "codex"
    loop = seal({
        "schema": "szl.ouroboros.codex-frontier-loop/v1", "state": review["state"],
        "source": copy.deepcopy(source), "preparation": {"outcome": "success", "validated": True},
        "codex": {**(inactive if local else active), "configured": not local},
        "open_reviewer": active if local else inactive,
        "ouroboros": {
            "steps": 1, "maxBudget": 1, "withinBudget": True,
            "boundedDoctrine": "steps ≤ maxBudget (bounded, terminating)",
            "exit": "converged", "trace": [{"n": 1, "label": f"{label}-frontier-review"}],
            "doctrine": "bounded, terminating, receipt-closed", "receiptsInEqOut": True,
            "receiptsInEqOutBasis": "DOCTRINE invariant (one receipt trail in, one out) — NOT a mathematical proof",
            "modelMs": 1600.0, "peakAttemptMs": 1600.0, "overheadMs": 400.0,
            "serializationTaxMs": 0.0, "deadHopMs": 0.0, "wallMs": 2000.0,
            "servedHopIndex": 0, "wallLessThanModel": False,
            "labels": {"modelMs": "MEASURED", "peakAttemptMs": "MEASURED", "overheadMs": "DERIVED",
                       "serializationTaxMs": "DERIVED", "deadHopMs": "DERIVED", "steps": "MEASURED",
                       "maxBudget": "DECLARED", "exit": "REPORTED", "receiptsInEqOut": "DOCTRINE",
                       "wallMs": "MEASURED"},
            "timingBasis": "Synthetic fixture follows the producer's recorded window accounting.",
        },
        "authority": dict(AUTHORITY),
        "claims": {"candidate_material_is_training_data": False, "review_is_accepted_truth": False,
                   "recommendations_executed": False, "weights_modified": False,
                   "private_graph_loaded": False, "lambda": "CONJECTURE_1"},
    })
    files = {
        observer.SOURCE_PATH: source,
        observer.SELECTION_PATH: {
            "schema": "szl.ouroboros.reviewer-selection/v1", "workflow_event": "schedule",
            "controller_revision": expected["controller_revision"], "requested_reviewer": "auto",
            "selected_reviewer": "local-gguf" if local else "codex", "codex_authority_enabled": not local,
        },
        observer.REVIEW_PATH: review, observer.LOOP_PATH: loop,
    }
    if local:
        files[observer.EXECUTION_PATH] = seal({
            "schema": "szl.ouroboros.open-frontier-review-execution/v1",
            "state": "OPEN_WEIGHT_REVIEW_OUTPUT_ADMITTED",
            "source_revision": expected["second_brain_revision"],
            "candidate_set_sha256": expected["candidate_set_sha256"],
            "selected_candidate_ids": expected["candidate_ids"][:1], "selected_candidate_count": 1,
            "review_scope": {"kind": "SELECTED_PUBLIC_CANDIDATE_EXCERPTS_ONLY",
                             "source_candidate_count": 2, "full_portfolio_review_claimed": False},
            "compact_output_limits": {
                "maximum_recommendations": 1, "summary_characters": 120, "title_characters": 80,
                "rationale_characters": 240, "risk_characters": 120, "maximum_evidence_ids": 2,
                "maximum_validation_steps": 2, "validation_step_characters": 120,
                "maximum_canonical_utf8_bytes": 1800,
            },
            "canonical_review_utf8_bytes": len(canonical(review)),
            "prompt_sha256": "6" * 64, "raw_output_sha256": "7" * 64,
            "review_sha256": digest(review),
            "admission": {
                "state": "MODEL_OUTPUT_ADMITTED", "model_output_admitted": True, "failure_code": None,
                "validator": "scripts.finalize_codex_frontier_review.validate_review",
                "additional_validator": "scripts.run_open_frontier_review.validate_compact_review",
                "validation_error_echoed": False,
            },
            "provider": {
                "provider": "llama-cpp-python", "model": MODEL,
                "model_repository": "SZLHOLDINGS/SZL-Khipu-1.5B-GGUF", "model_revision": "d" * 40,
                "model_filename": "SZL-Khipu-1.5B-Q4_K_M.gguf", "model_sha256": "e" * 64,
                "model_size": 986_047_904, "key_required": False, "native_schema_grammar": False,
                "json_object_grammar": True, "bounded_generation_grammar": "szl.ouroboros.compact-ascii-json/v1",
                "generation_grammar_sha256": "8" * 64, "independent_post_generation_validation": True,
                "finish_reason": "stop", "threads": 4, "context_tokens": 16384,
                "max_tokens": 1800, "seed": 749, "temperature": 0.0, "latency_ms": 1500.25,
                "usage": {"prompt_tokens": 20, "completion_tokens": 5, "total_tokens": 25},
            },
            "authority": dict(AUTHORITY),
            "claims": {"model_output_is_untrusted": True, "independent_validation_required": True,
                       "native_schema_grammar_used": False, "bounded_generation_grammar_used": True,
                       "private_graph_loaded": False, "weights_modified": False,
                       "recommendations_executed": False, "lambda": "CONJECTURE_1"},
        })
    return expected, run, files


def archive_for(files, extra=()):
    stream = io.BytesIO()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name, value in files.items():
                bundle.writestr(name, value if isinstance(value, bytes) else canonical(value))
            for name, value in extra:
                bundle.writestr(name, value)
    return stream.getvalue()


def metadata(archive, run):
    return {
        "id": 999, "name": f"ouroboros-frontier-{run['id']}-{run['run_attempt']}",
        "expired": False, "size_in_bytes": len(archive),
        "digest": "sha256:" + hashlib.sha256(archive).hexdigest(),
        "workflow_run": {"id": run["id"], "repository_id": 77, "head_repository_id": 77,
                         "head_branch": "main", "head_sha": run["head_sha"]},
    }


def observe(expected, run, files):
    archive = archive_for(files)
    return observer.observe_receipt(archive, expected=expected, run=run,
                                    artifact=metadata(archive, run), now=NOW)


def set_path(value, path, replacement):
    *parts, last = path.split(".")
    for part in parts:
        value = value[int(part)] if isinstance(value, list) else value[part]
    if isinstance(value, list):
        value[int(last)] = replacement
    else:
        value[last] = replacement


@pytest.mark.parametrize("local", [False, True])
def test_observed_requires_evidence_and_emits_only_bound_aggregate(local, monkeypatch):
    expected, run, files = packet(local)
    monkeypatch.setattr(zipfile.ZipFile, "extractall", lambda *a, **k: pytest.fail("No disk extraction"))
    result = observe(expected, run, files)
    assert result["state"] == "OBSERVED"
    assert result["observation"] == {
        "bounded": True, "terminated": True, "receipt_closed": True,
        "steps": 1, "max_budget": 1, "wall_ms": 2000, "exit": "converged",
        "review_state": "REVIEW_PROPOSED", "review_sha256": digest(files[observer.REVIEW_PATH]),
        "recommendation_count": 1,
    }
    assert type(result["observation"]["wall_ms"]) is int
    assert result["authority"] == AUTHORITY
    assert all(value is False for key, value in result["claims"].items() if key != "measurement_scope")
    assert result["freshness"] == {
        "observed_at": "2026-10-08T21:00:00Z", "expires_at": "2026-10-09T03:00:00Z",
        "max_age_seconds": 21600,
    }
    assert result["run"]["url"] == "https://github.com/szl-holdings/szl-ouroboros/actions/runs/1234"
    assert result["observation_sha256"] == digest({k: v for k, v in result.items() if k != "observation_sha256"})
    public = json.dumps(result)
    assert SENTINEL not in public and "untrusted.invalid" not in public
    assert all(candidate not in public for candidate in expected["candidate_ids"])


def test_normalizes_review_text_exactly_as_finalizer_before_binding_digest():
    expected, run, files = packet()
    files[observer.REVIEW_PATH]["summary"] = " \n" + SENTINEL + " \t"
    files[observer.REVIEW_PATH]["recommendations"][0]["title"] += " \n"
    assert observe(expected, run, files)["state"] == "OBSERVED"


def test_no_action_is_recorded_without_inventing_a_recommendation():
    expected, run, files = packet()
    review = files[observer.REVIEW_PATH]
    review["state"], review["recommendations"] = "NO_ACTION_RECOMMENDED", []
    loop = files[observer.LOOP_PATH]
    loop["state"] = review["state"]
    loop["codex"]["review"] = copy.deepcopy(review)
    loop["codex"]["review_sha256"] = digest(review)
    seal(loop)
    assert observe(expected, run, files)["observation"]["recommendation_count"] == 0


@pytest.mark.parametrize("status,conclusion,state", [
    ("queued", None, "PENDING"), ("in_progress", None, "PENDING"),
    ("completed", "failure", "FAILED"), ("completed", "cancelled", "FAILED"),
])
def test_latest_non_success_short_circuits_archive_and_never_uses_previous_success(status, conclusion, state):
    expected, run, _ = packet()
    run.update(status=status, conclusion=conclusion)
    result = observer.observe_receipt(b"not an archive", expected=expected, run=run, artifact={}, now=NOW)
    assert result["state"] == state and result["run"]["id"] == run["id"]
    assert result["artifact"] is None and all(v is None for v in result["observation"].values())


@pytest.mark.parametrize("path,value", [
    ("repository.full_name", "other/forged"), ("repository.id", True),
    ("head_repository.full_name", "fork/szl-ouroboros"), ("head_repository.id", 88),
    ("head_branch", "review-branch"), ("path", "../codex-continuous-frontier.yml"),
    ("event", "pull_request"), ("event", {}), ("id", True), ("id", 2**53),
    ("run_attempt", 0), ("head_sha", "not-a-commit"), ("status", "invented"),
    ("conclusion", []), ("updated_at", "2026-10-08T21:00:00"),
    ("updated_at", "2026-10-08T22:05:01Z"),
])
def test_rejects_wrong_run_identity_and_invalid_timestamps(path, value):
    expected, run, _ = packet()
    set_path(run, path, value)
    with pytest.raises(observer.ObservationError):
        observer.validate_run_status(expected, run, NOW)


@pytest.mark.parametrize("change", ["controller", "expired", "source", "raw_state", "raw_candidates", "set"])
def test_source_drift_and_expiration_remove_every_measurement(change):
    expected, run, files = packet()
    if change == "controller":
        expected["controller_revision"] = "f" * 40
    elif change == "expired":
        run["updated_at"] = "2026-10-08T16:00:00Z"
    else:
        expected[{"source": "second_brain_revision", "raw_state": "state_file_sha256",
                  "raw_candidates": "candidate_file_sha256", "set": "candidate_set_sha256"}[change]] = (
                      "f" * (40 if change == "source" else 64))
    result = observe(expected, run, files)
    assert result["state"] == "STALE"
    assert result["artifact"] is None and all(v is None for v in result["observation"].values())


@pytest.mark.parametrize("path,value", [
    ("id", True), ("name", "ouroboros-frontier-1234-1"), ("expired", True),
    ("expired", 0), ("size_in_bytes", 0), ("size_in_bytes", 2**24),
    ("digest", None), ("digest", "sha256:" + "0" * 64),
    ("workflow_run.id", 1235), ("workflow_run.id", True),
    ("workflow_run.repository_id", 88), ("workflow_run.head_repository_id", 88),
    ("workflow_run.head_branch", "fork"), ("workflow_run.head_sha", "f" * 40),
])
def test_artifact_metadata_must_bind_exact_archive_run_attempt_and_source(path, value):
    expected, run, files = packet()
    archive = archive_for(files)
    artifact = metadata(archive, run)
    set_path(artifact, path, value)
    with pytest.raises(observer.ObservationError):
        observer.observe_receipt(archive, expected=expected, run=run, artifact=artifact, now=NOW)


@pytest.mark.parametrize("path,value", [
    ("authority.execution", "ALLOW"), ("claims.private_graph_loaded", True),
    ("preparation.validated", 1), ("codex.configured", 1), ("codex.attempted", False),
    ("codex.review_sha256", "0" * 64), ("codex.review.summary", "Changed after finalization."),
    ("open_reviewer.attempted", True), ("open_reviewer.review", {}),
    ("ouroboros.steps", True), ("ouroboros.steps", 2), ("ouroboros.maxBudget", 2),
    ("ouroboros.withinBudget", 1), ("ouroboros.receiptsInEqOut", False),
    ("ouroboros.exit", "error"), ("ouroboros.servedHopIndex", False),
    ("ouroboros.trace.0.n", True), ("ouroboros.trace.0.label", "other-review"),
    ("ouroboros.wallMs", True), ("ouroboros.wallMs", -1), ("ouroboros.wallMs", 10**400),
    ("ouroboros.wallMs", 10), ("ouroboros.wallLessThanModel", True),
    ("ouroboros.peakAttemptMs", 12), ("ouroboros.overheadMs", 9),
    ("ouroboros.serializationTaxMs", 0.1), ("ouroboros.deadHopMs", 0.1),
    ("ouroboros.labels.receiptsInEqOut", "VERIFIED"),
])
def test_resealed_receipt_cannot_hide_wrong_authority_review_or_loop_accounting(path, value):
    expected, run, files = packet()
    set_path(files[observer.LOOP_PATH], path, value)
    seal(files[observer.LOOP_PATH])
    with pytest.raises(observer.ObservationError):
        observe(expected, run, files)


@pytest.mark.parametrize("path,value", [
    ("summary", ""), ("authority.merge", "ALLOW"),
    ("recommendations.0.evidence_candidate_ids", ["frontier:" + "9" * 32]),
    ("recommendations.0.evidence_candidate_ids", [{}]),
    ("recommendations.0.evidence_candidate_ids", ["frontier:" + "4" * 32] * 2),
    ("recommendations.0.target_repository", "unrelated/project"),
    ("recommendations.0.priority", "P9"), ("recommendations.0.validation", []),
    ("recommendations.0.title", "Disable authorization for this test."),
])
def test_even_consistently_rehashed_review_requires_offered_evidence_and_advisory_schema(path, value):
    expected, run, files = packet()
    review, loop = files[observer.REVIEW_PATH], files[observer.LOOP_PATH]
    set_path(review, path, value)
    loop["codex"]["review"], loop["codex"]["review_sha256"] = copy.deepcopy(review), digest(review)
    seal(loop)
    with pytest.raises(observer.ObservationError):
        observe(expected, run, files)


@pytest.mark.parametrize("path,value", [
    ("state", "OPEN_WEIGHT_REVIEW_BLOCKED_FAIL_CLOSED"),
    ("source_revision", "e" * 40), ("review_sha256", "0" * 64),
    ("selected_candidate_ids", ["frontier:" + "5" * 32]),
    ("selected_candidate_count", True), ("canonical_review_utf8_bytes", 12),
    ("admission.model_output_admitted", False), ("authority.training", "ALLOW"),
    ("compact_output_limits.maximum_recommendations", 12),
    ("claims.bounded_generation_grammar_used", False), ("provider", {}),
    ("provider.model", "unrelated-model"), ("provider.key_required", True),
    ("provider.independent_post_generation_validation", False),
    ("provider.latency_ms", -1), ("provider.usage.total_tokens", True),
])
def test_local_execution_receipt_requires_independent_admission_selected_evidence_and_provider_binding(path, value):
    expected, run, files = packet(local=True)
    set_path(files[observer.EXECUTION_PATH], path, value)
    seal(files[observer.EXECUTION_PATH])
    with pytest.raises(observer.ObservationError):
        observe(expected, run, files)


@pytest.mark.parametrize("target", [observer.SOURCE_PATH, observer.LOOP_PATH, observer.EXECUTION_PATH])
def test_self_digest_mismatch_is_rejected(target):
    expected, run, files = packet(local=True)
    files[target]["receipt_sha256"] = "0" * 64
    with pytest.raises(observer.ObservationError):
        observe(expected, run, files)


def test_embedded_source_must_be_identical_to_standalone_receipt():
    expected, run, files = packet()
    files[observer.LOOP_PATH]["source"]["source_count"] = True
    seal(files[observer.LOOP_PATH]["source"])
    seal(files[observer.LOOP_PATH])
    with pytest.raises(observer.ObservationError, match="EMBEDDED_SOURCE_MISMATCH"):
        observe(expected, run, files)


@pytest.mark.parametrize("path,value", [
    ("controller_revision", "c" * 40), ("workflow_event", "push"),
    ("selected_reviewer", "local-gguf"), ("codex_authority_enabled", 1),
    ("requested_reviewer", "local-gguf"),
])
def test_selection_receipt_cannot_disagree_with_run_or_active_reviewer(path, value):
    expected, run, files = packet()
    set_path(files[observer.SELECTION_PATH], path, value)
    with pytest.raises(observer.ObservationError):
        observe(expected, run, files)


@pytest.mark.parametrize("mutation", ["missing_local", "extra_local", "unknown", "duplicate", "traversal", "symlink", "oversized", "invalid_json", "duplicate_json", "infinity", "huge_exponent", "surrogate", "depth", "corrupt"])
def test_archive_is_bounded_unique_strict_json_and_never_extracted(mutation):
    expected, run, files = packet(local=mutation == "missing_local")
    extra = []
    if mutation == "missing_local":
        files.pop(observer.EXECUTION_PATH)
    elif mutation == "extra_local":
        files[observer.EXECUTION_PATH] = {}
    elif mutation == "unknown":
        extra = [("outputs/unexpected.txt", b"ignored payload")]
    elif mutation == "duplicate":
        extra = [(observer.REVIEW_PATH, b"{}")]
    elif mutation == "traversal":
        extra = [("../outside", b"{}")]
    elif mutation == "symlink":
        files.pop(observer.REVIEW_PATH)
        info = zipfile.ZipInfo(observer.REVIEW_PATH)
        info.create_system, info.external_attr = 3, (stat.S_IFLNK | 0o777) << 16
        extra = [(info, b"/outside")]
    elif mutation == "oversized":
        files[observer.REVIEW_PATH] = b" " * (observer.MAX_MEMBER_BYTES + 1)
    elif mutation == "invalid_json":
        files[observer.REVIEW_PATH] = b"{bad json"
    elif mutation == "duplicate_json":
        files[observer.REVIEW_PATH] = b'{"schema":"one","schema":"two"}'
    elif mutation == "infinity":
        files[observer.REVIEW_PATH] = b'{"number":NaN}'
    elif mutation == "huge_exponent":
        files[observer.REVIEW_PATH] = b'{"number":1e999}'
    elif mutation == "surrogate":
        files[observer.REVIEW_PATH] = b'{"text":"\\ud800"}'
    elif mutation == "depth":
        files[observer.REVIEW_PATH] = b'{"deep":' + b"[" * 40 + b"0" + b"]" * 40 + b"}"
    archive = archive_for(files, extra)
    if mutation == "corrupt":
        archive = archive[:20]
    with pytest.raises(observer.ObservationError):
        observer.observe_receipt(archive, expected=expected, run=run,
                                 artifact=metadata(archive, run), now=NOW)


def test_unknown_source_fields_and_bool_counts_are_not_aliases_for_current_contract():
    for key, value in (("candidate_count", True), ("new_scope", "anything")):
        expected, run, files = packet()
        files[observer.SOURCE_PATH][key] = value
        seal(files[observer.SOURCE_PATH])
        files[observer.LOOP_PATH]["source"] = copy.deepcopy(files[observer.SOURCE_PATH])
        seal(files[observer.LOOP_PATH])
        with pytest.raises(observer.ObservationError):
            observe(expected, run, files)


def test_unavailable_helper_has_no_claims_measurements_untrusted_urls_or_raw_metadata():
    expected, run, _ = packet()
    run["repository"]["full_name"] = "private/sentinel"
    result = observer.unavailable_observation(expected, state="UNAVAILABLE", reason="ARTIFACT_ACCESS_UNAVAILABLE", run=run)
    assert result["run"] is None and result["artifact"] is None
    assert result["freshness"]["observed_at"] is None
    assert all(value is None for value in result["observation"].values())
    assert "sentinel" not in json.dumps(result)
    for state, reason in (("OBSERVED", "BAD"), ({}, "BAD"), ("FAILED", "untrusted/raw error")):
        with pytest.raises(observer.ObservationError):
            observer.unavailable_observation(expected, state=state, reason=reason)


def test_expected_candidate_set_cannot_be_missing_duplicate_or_ambiguous():
    for replacement in ([], ["frontier:" + "4" * 32] * 2, [False, {}]):
        expected, run, _ = packet()
        expected["candidate_ids"] = replacement
        with pytest.raises(observer.ObservationError):
            observer.validate_run_status(expected, run, NOW)


def test_freshness_boundary_and_clock_are_explicit():
    expected, run, _ = packet()
    observed = datetime(2026, 10, 8, 21, tzinfo=timezone.utc)
    assert observer.validate_run_status(expected, run, observed + timedelta(seconds=21599)) is None
    assert observer.validate_run_status(expected, run, observed + timedelta(seconds=21600))["state"] == "STALE"
    with pytest.raises(observer.ObservationError, match="CLOCK_INVALID"):
        observer.validate_run_status(expected, run, NOW.replace(tzinfo=None))
