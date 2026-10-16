#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Transport and crash controls, with synthetic responses and no live writes."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))
import operator_acceptance_run as run

SOURCE = "a" * 40


class FakeClient:
    def __init__(self, output, *, failure=None):
        self.output = output
        self.failure = failure
        self.calls = []
        self.feed = []

    def request(self, method, path, payload=None):
        self.calls.append((method, path, copy.deepcopy(payload)))
        if method == "GET" and path == run.BUILD:
            reads = sum(m == "GET" and p == run.BUILD for m, p, _ in self.calls)
            changed = (self.failure == "source_drift" and self.feed) or (self.failure == "source_drift_before_second" and reads >= 4)
            if self.failure == "final_read_failure" and reads >= 8:
                raise run.ObservationError("READBACK_HTTP_UNAVAILABLE")
            revision = "b" * 40 if changed else SOURCE
            return 200, {"status": "OBSERVED", "service": "a11oy", "receipt_minted": False,
                         "build": {"state": "OBSERVED", "revision": revision,
                                   "revision_source": "env:SZL_GIT_SHA",
                                   "field_evidence": {"revision": "OBSERVED"}}}
        if method == "GET" and path == run.FEED:
            if self.failure == "readback_failure" and self.feed:
                raise run.ObservationError("READBACK_HTTP_UNAVAILABLE")
            return 200, {"total_buffered": 10 if self.failure == "invalid_baseline" else len(self.feed), "count": len(self.feed),
                         "verdicts": copy.deepcopy(self.feed)}
        assert method == "POST"
        # The fsynced intent must precede dispatch, not be reconstructed later.
        journal = [json.loads(line) for line in (self.output / "journal.jsonl").read_text().splitlines()]
        assert journal[-1]["event"] == "post_intent"
        if self.failure == "timeout":
            raise run.ObservationError("HTTP_OUTCOME_UNAVAILABLE")
        if path.endswith("/policy/decide"):
            item = {"request_id": payload["request_id"], "agent": payload["agent"],
                    "decision": "allow", "receipt_hash": "c" * 16, "lambda_value": 0.97,
                    "signals": []}
            self.feed.append(item)
            return 200, {"decision": "allow", "actionId": payload["request_id"],
                         "receipt_hash": "c" * 16, "lambda_value": 0.97,
                         "signals": [], "gates_fired": [], "status": "REAL", "doctrine": "v11"}
        if path.endswith("/operator/ask"):
            if self.failure == "wrong_answer":
                return 200, {"topic": "general", "answer": "no evidence"}
            endpoint = ("szl_brain.CANONICAL" if self.failure == "bad_citation"
                        else run.verifier.FORMULA_CITATION_ENDPOINT)
            receipt = {"schema": "szl.a11oy.operator/v1", "kind": "ask", "organ": "a11oy",
                       "ts_utc": run.stamp(), "doctrine": "v11",
                       "lambda_status": "Conjecture 1 (NOT a theorem)",
                       "body": {"question": payload["question"], "topic": "formulas", "grounded": True}}
            receipt["receipt_sha256"] = hashlib.sha256(json.dumps(receipt, sort_keys=True,
                                                                 separators=(",", ":")).encode()).hexdigest()
            return 200, {"topic": "formulas", "question": payload["question"],
                         "answer": ", ".join(run.verifier.LOCKED), "grounded": True,
                         "receipt": {"receipt": receipt, "signed": False, "signing_available": False,
                                     "dsse": {"signed": False}},
                         "citations": [{"endpoint": endpoint,
                                        "data": {"count": 8, "proved": run.verifier.LOCKED, "doctrine": "v11"}}]}
        if path.endswith("/policy/compliance"):
            return 200, {"status": "REAL", "framework": "NIST", "covered": 8, "total": 8}
        pytest.fail("A model route must never execute")


def capture(tmp_path, **options):
    output = tmp_path / "capture"
    client = FakeClient(output, **options)
    receipt = run.collect(output, SOURCE, execute=True, client=client)
    return output, client, receipt, json.loads((output / "observation.json").read_text())


def test_default_preflight_issues_no_posts_and_keeps_five_blocked(tmp_path):
    output = tmp_path / "capture"
    client = FakeClient(output)
    receipt = run.collect(output, SOURCE, client=client)
    assert all(method == "GET" for method, _, _ in client.calls)
    assert receipt["reported_semantic_contracts"] == 0
    assert receipt["publication_eligible"] is False
    assert len(json.loads((output / "observation.json").read_text())["cases"]) == 5


def test_bounded_capture_preserves_all_five_and_never_executes_model_routes(tmp_path):
    output, client, receipt, bundle = capture(tmp_path)
    posts = [(path, body) for method, path, body in client.calls if method == "POST"]
    assert [path for path, _ in posts] == list(run.verifier.CONTRACTS.values())[:3]
    assert posts[0][1]["axes"] == [0.97]
    assert receipt["reported_semantic_contracts"] == 3
    assert receipt["status"] == "BLOCKED" and receipt["signing"] == "UNSIGNED"
    assert all(row["state"] == "NOT_ATTEMPTED" for row in bundle["cases"][3:])
    for name, expected in receipt["files"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == expected
    previous = "0" * 64
    for raw in (output / "journal.jsonl").read_bytes().splitlines():
        event = json.loads(raw)
        assert event["previous_sha256"] == previous
        previous = hashlib.sha256(raw).hexdigest()


@pytest.mark.parametrize("failure", ["timeout", "readback_failure", "source_drift"])
def test_unknown_first_effect_stops_later_posts_without_retry(tmp_path, failure):
    _, client, receipt, bundle = capture(tmp_path, failure=failure)
    assert sum(method == "POST" for method, _, _ in client.calls) == 1
    assert bundle["cases"][0]["state"] == "UNKNOWN"
    assert all(row["state"] == "NOT_ATTEMPTED" for row in bundle["cases"][1:])
    assert receipt["reported_semantic_contracts"] == 0


def test_changed_source_before_second_post_is_retained_and_rejected(tmp_path):
    output, client, receipt, bundle = capture(tmp_path, failure="source_drift_before_second")
    assert sum(method == "POST" for method, _, _ in client.calls) == 1
    assert bundle["build_after"]["build"]["revision"] == "b" * 40
    assert bundle["cases"][1]["state"] == "NOT_ATTEMPTED"
    assert json.loads((output / "verification.json").read_text())["status"] == "BLOCKED"
    assert receipt["reported_semantic_contracts"] == 0


def test_missing_final_identity_cannot_reuse_old_success(tmp_path):
    output, client, receipt, bundle = capture(tmp_path, failure="final_read_failure")
    assert sum(method == "POST" for method, _, _ in client.calls) == 3
    assert bundle["build_after"] is None
    assert json.loads((output / "verification.json").read_text())["status"] == "BLOCKED"
    assert receipt["reported_semantic_contracts"] == 0


def test_incomplete_policy_baseline_stops_before_effect(tmp_path):
    _, client, _, bundle = capture(tmp_path, failure="invalid_baseline")
    assert not any(method == "POST" for method, _, _ in client.calls)
    assert all(case["state"] == "NOT_ATTEMPTED" for case in bundle["cases"])


def test_semantically_wrong_success_stops_before_next_post(tmp_path):
    _, client, receipt, bundle = capture(tmp_path, failure="wrong_answer")
    assert sum(method == "POST" for method, _, _ in client.calls) == 2
    assert bundle["cases"][0]["state"] == "OBSERVED"
    assert bundle["cases"][1]["state"] == "UNKNOWN"
    assert bundle["cases"][2]["state"] == "NOT_ATTEMPTED"
    assert receipt["publication_eligible"] is False


def test_retired_formula_citation_stops_after_second_post_without_retry(tmp_path):
    _, client, receipt, bundle = capture(tmp_path, failure="bad_citation")
    posts = [(path, body) for method, path, body in client.calls if method == "POST"]
    assert len(posts) == 2
    assert posts[1][0].endswith("/operator/ask")
    assert sum(path.endswith("/operator/ask") for path, _ in posts) == 1
    assert bundle["cases"][0]["state"] == "OBSERVED"
    assert bundle["cases"][1]["state"] == "UNKNOWN"
    assert bundle["cases"][1]["reason"] == "EFFECT_CONTRACT_MISMATCH"
    assert bundle["cases"][2]["state"] == "NOT_ATTEMPTED"
    assert all(row["state"] == "NOT_ATTEMPTED" for row in bundle["cases"][2:])
    assert receipt["publication_eligible"] is False
    assert receipt["execution_authorized"] is False
    assert receipt["signing"] == "UNSIGNED"


def test_existing_run_directory_is_never_resumed_or_overwritten(tmp_path):
    output, _, _, _ = capture(tmp_path)
    before = (output / "observation.json").read_bytes()
    client = FakeClient(output)
    with pytest.raises(FileExistsError):
        run.collect(output, SOURCE, execute=True, client=client)
    assert not client.calls and (output / "observation.json").read_bytes() == before


def test_journal_failure_prevents_post(tmp_path, monkeypatch):
    original = run.Journal.append

    def fail_before_dispatch(self, event, **values):
        if event == "post_intent":
            raise OSError("synthetic fsync failure")
        return original(self, event, **values)

    monkeypatch.setattr(run.Journal, "append", fail_before_dispatch)
    output = tmp_path / "capture"
    client = FakeClient(output)
    run.collect(output, SOURCE, execute=True, client=client)
    assert not any(method == "POST" for method, _, _ in client.calls)


@pytest.mark.parametrize("mode", ["normal", "redirect", "timeout", "oversize"])
def test_curl_transport_does_not_follow_redirects_retry_or_inherit_config(monkeypatch, mode):
    client = object.__new__(run.CurlClient)
    client.executable = "fixture-curl"
    calls = []

    def fake(command, **kwargs):
        calls.append(command)
        assert command[1] == "--disable"
        assert command[command.index("--max-time") + 1] == "30"
        assert command[command.index("--retry") + 1] == "0"
        assert command[command.index("--noproxy") + 1] == "*"
        assert "--location" not in command and "--insecure" not in command
        assert "--http1.1" in command
        assert not any("Authorization" in part for part in command)
        if mode == "timeout":
            raise subprocess.TimeoutExpired(command, 40)
        target = Path(command[command.index("--output") + 1])
        target.write_bytes(b"x" * (run.MAX_RESPONSE + 1) if mode == "oversize" else b'{"ok":true}')
        return subprocess.CompletedProcess(command, 0, b"302" if mode == "redirect" else b"200")

    monkeypatch.setattr(run.subprocess, "run", fake)
    if mode in ("timeout", "oversize"):
        with pytest.raises(run.ObservationError):
            client.request("POST", list(run.POST_PATHS)[0], {"fixed": True})
    else:
        status, _ = client.request("POST", list(run.POST_PATHS)[0], {"fixed": True})
        assert status == (302 if mode == "redirect" else 200)
    assert len(calls) == 1


def test_transport_denies_model_routes_before_subprocess(monkeypatch):
    client = object.__new__(run.CurlClient)
    client.executable = "fixture-curl"
    monkeypatch.setattr(run.subprocess, "run", lambda *a, **k: pytest.fail("unexpected curl invocation"))
    for path in list(run.verifier.CONTRACTS.values())[3:]:
        with pytest.raises(run.ObservationError, match="REQUEST_NOT_ADMITTED"):
            client.request("POST", path, {"execution_mode": "live"})


def test_invalid_expected_source_or_checkout_output_never_calls_network(tmp_path):
    client = FakeClient(tmp_path)
    with pytest.raises(run.ObservationError, match="EXACT_SOURCE_REQUIRED"):
        run.collect(tmp_path / "capture", "main", client=client)
    with pytest.raises(run.ObservationError, match="OUTPUT_MUST_BE_OUTSIDE_CHECKOUT"):
        run.collect(run.ROOT / "unsafe-output", SOURCE, client=client)
    assert not client.calls
