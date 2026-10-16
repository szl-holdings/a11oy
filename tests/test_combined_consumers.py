#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Isolated synthetic integration: temporary keys and mocked model transport only."""
import ast
import asyncio
import base64
import copy
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import sys

import pytest
from httpx import Client as FixtureHTTPClient
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent
if not (ROOT / "szl_execution_readiness.py").is_file():
    ROOT = ROOT.parent
sys.path.insert(0, str(ROOT))


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


gate = load("combined_gate_test", ROOT / "szl_execution_readiness.py")
publisher = load("combined_publisher_test", ROOT / ".github/scripts/publish_readiness_verdict.py")
reader = load("combined_reader_test", ROOT / "szl_readiness_artifact.py")
relock = load("combined_relock_test", ROOT / ".github/scripts/verify_canonical_a11oy.py")
native_fixture = ROOT / "tests/test_observer_adapters.py"
native_tests = load("combined_native_fixture", native_fixture)
world = native_tests.world
a = gate.acceptance


def sign(payload, kind, key, keyid):
    raw = a.canonical(payload)
    encoded_type = kind.encode()
    pae = b"DSSEv1 " + str(len(encoded_type)).encode() + b" " + encoded_type + b" " + str(len(raw)).encode() + b" " + raw
    return {"payloadType": kind, "payload": base64.b64encode(raw).decode(),
            "signatures": [{"keyid": keyid, "sig": base64.b64encode(key.sign(pae, ec.ECDSA(hashes.SHA256()))).decode()}]}


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


@pytest.fixture
def combined(world):
    captured = native_tests.execute_all(world)
    now = datetime.now(timezone.utc)
    authority = ec.generate_private_key(ec.SECP256R1())
    pem = authority.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    context = a.AdmissionContext("a" * 40, "b" * 40, "fixture-boot", world.plan["run_nonce"],
                                 pem, a.digest(pem.strip()), world.pem, world.key_id)
    binding = {"origin": a.ORIGIN, "source_revision": context.source_revision,
               "runtime_revision": context.runtime_revision, "runtime_boot_id": context.runtime_boot_id,
               "run_nonce": context.run_nonce}
    plan = {"schema": "szl.execution-acceptance-plan/v1", **binding,
            "issued_at": stamp(now - timedelta(minutes=2)), "expires_at": stamp(now + timedelta(minutes=2)),
            "operator_reference": "fixture-independent-operator", "max_requests": 5, "retries": 0,
            "cases": copy.deepcopy(world.plan["cases"])}
    for case in plan["cases"]:
        case["response_assertions"] = ({"/model_id": native_tests.MODEL} if case["id"] == "eval-run" else
            {"/ok": True} if case["id"] == "agentloop-run" else {"/status": "REAL"})
        if case["id"] == "agentloop-run":
            case["readback_assertions"] = {"/record/schema": native_tests.adapters.READBACK_SCHEMA}
    observations = []
    for case in plan["cases"]:
        capture = captured[case["id"]]
        receipt = {"schema": "szl.execution-observation/v1", **binding,
            "receipt_id": "fixture-observation:" + case["id"], "case_id": case["id"],
            "plan_sha256": a.digest(a.canonical(plan)), "operator_reference": plan["operator_reference"],
            "request_sha256": a.digest(a.canonical({k: case[k] for k in ("method", "path", "body")})),
            "response_sha256": a.digest(capture.response_bytes), "readback_sha256": a.digest(capture.readback_bytes),
            "response_status": 200, "started_at": stamp(now - timedelta(seconds=30)),
            "completed_at": stamp(now - timedelta(seconds=10))}
        observations.append({"receipt": sign(receipt, a.RECEIPT_TYPE, world.key, world.key_id),
            "response_b64": base64.b64encode(capture.response_bytes).decode(),
            "readback_b64": base64.b64encode(capture.readback_bytes).decode()})
    bundle = {"schema": "szl.execution-acceptance-bundle/v1",
              "plan": sign(plan, a.PLAN_TYPE, authority, context.authority_key_id), "observations": observations}
    matrix = {"endpoints": {"/api/livez": {"method": "GET", "schema": "generic_obj"},
               **{path: {"method": "POST"} for path in a.CONTRACTS.values()}}}
    rows = [{"path": "/api/livez", "method": "GET", "status": 200, "samples": 1,
             "lie": False, "unreachable": False, "throttled": False, "degraded": False,
             "schemaOk": True, "citationOk": True, "labelPolicyOk": True, "freshOk": None}]
    rows += [{"path": path, "method": "POST", "status": None, "samples": 0,
              "skipped": True, "runtimeState": "NOT_PROBED", "required": True,
              "lie": False, "unreachable": False, "throttled": False, "degraded": False,
              "schemaOk": None, "citationOk": None, "labelPolicyOk": None, "freshOk": None}
             for path in a.CONTRACTS.values()]
    passive = {"schema": "szl.readiness-verdict/v1", "harness": "a11oy-readiness probe", "doctrine": "v11",
        "base": a.ORIGIN, "checkedAt": stamp(now), "sourceRevision": context.source_revision,
        "sourceRevisionBefore": context.source_revision, "sourceRevisionAfter": context.source_revision,
        "sourceRevisionStatus": "OBSERVED", "results": rows,
        "summary": {"endpoints": 6, "ok": 1, "skippedStateChanging": 5, "requiredNotProbed": 5,
                    "lies": 0, "unreachable": 0, "throttled": 0, "degraded": 0, "blockingDegraded": 0, "p95_worst": 1}}
    return {"world": world, "authority": authority, "context": context, "plan": plan,
            "bundle": bundle, "matrix": matrix, "passive": passive, "now": now}


def compact(c):
    return publisher.compact_verdict(c["passive"], expected_origin=a.ORIGIN,
        expected_source_sha=c["context"].source_revision, now=c["now"], matrix=c["matrix"],
        execution_bundle=c["bundle"], execution_context=c["context"])


def inputs(c):
    return {k: c[k] for k in ("passive", "matrix", "bundle", "context")}


def resign_observation(c, case_id, label, mutate):
    row = next(row for row in c["bundle"]["observations"]
               if a.strict_json(a.decode(row["receipt"]["payload"]))["case_id"] == case_id)
    body = a.strict_json(a.decode(row[label + "_b64"]))
    mutate(body)
    raw = a.canonical(body)
    row[label + "_b64"] = base64.b64encode(raw).decode()
    receipt = a.strict_json(a.decode(row["receipt"]["payload"]))
    receipt[label + "_sha256"] = a.digest(raw)
    row["receipt"] = sign(receipt, a.RECEIPT_TYPE, c["world"].key, c["world"].key_id)


def test_three_consumers_verify_real_test_signatures_and_keep_passive_rows(combined):
    c = combined
    before = a.canonical(c["passive"])
    result = compact(c)
    assert result["summary"]["requiredNotProbed"] == 5
    assert result["summary"]["skippedStateChanging"] == 5
    assert result["executionCoverage"]["requiredExecutionCovered"] == 5
    job = {"started_at": stamp(c["now"] - timedelta(minutes=1)), "completed_at": stamp(c["now"])}
    assert reader.validate_verdict(c["passive"], c["matrix"], source=c["context"].source_revision,
        now=c["now"], job=job, execution_bundle=c["bundle"], execution_context=c["context"]) == result
    evidence = relock.validate_verdict_evidence(base=a.ORIGIN, checked_at=c["passive"]["checkedAt"],
        summary=result["summary"], source_sha=c["context"].source_revision, expected_origin=a.ORIGIN,
        now=c["now"], execution_inputs=inputs(c))
    assert evidence["executionCoverage"] == result["executionCoverage"]
    assert a.canonical(c["passive"]) == before


@pytest.mark.parametrize("field", ["source_revision", "runtime_revision", "runtime_boot_id", "run_nonce"])
def test_independent_identity_mismatch_denies(combined, field):
    c = combined
    c["context"] = replace(c["context"], **{field: {"source_revision": "d" * 40,
        "runtime_revision": "d" * 40, "runtime_boot_id": "other-boot", "run_nonce": "d" * 64}[field]})
    with pytest.raises(Exception):
        compact(c)


@pytest.mark.parametrize("kind", ["missing-context", "dictionary-context", "wrapper", "missing-row", "duplicate-row", "old-plan", "same-authority"])
def test_absent_forged_or_replayed_authority_denies(combined, kind):
    c = combined
    if kind == "missing-context": c["context"] = None
    elif kind == "dictionary-context": c["context"] = dict(c["context"].__dict__)
    elif kind == "wrapper": c["bundle"] = {"bundle": c["bundle"], "publication_eligible": True, "storage_acknowledgment": True}
    elif kind == "missing-row": c["bundle"]["observations"].pop()
    elif kind == "duplicate-row": c["bundle"]["observations"][0] = c["bundle"]["observations"][1]
    elif kind == "old-plan": c["now"] += timedelta(minutes=20)
    else: c["context"] = replace(c["context"], authority_public_key=c["context"].runtime_public_key,
                                  authority_key_id=c["context"].runtime_key_id)
    with pytest.raises(Exception):
        publisher.compact_verdict(c["passive"], expected_origin=a.ORIGIN, expected_source_sha="a" * 40,
            now=c["now"], matrix=c["matrix"], execution_bundle=c["bundle"], execution_context=c["context"])


@pytest.mark.parametrize("kind", ["zero-count", "post-as-get", "fake-sampled", "missing-required", "unknown-post", "passive-degraded"])
def test_passive_contract_cannot_be_relabelled_or_weakened(combined, kind):
    c = combined
    row = c["passive"]["results"][1]
    if kind == "zero-count":
        c["passive"]["summary"].update(requiredNotProbed=0, skippedStateChanging=0, ok=6)
        for row in c["passive"]["results"][1:]:
            row.update(skipped=False, samples=1, status=200, schemaOk=True, citationOk=True, labelPolicyOk=True)
    elif kind == "post-as-get": c["matrix"]["endpoints"][row["path"]]["method"] = row["method"] = "GET"
    elif kind == "fake-sampled": row.update(samples=1, status=200)
    elif kind == "missing-required": c["matrix"]["endpoints"][row["path"]]["required"] = False
    elif kind == "unknown-post": c["matrix"]["endpoints"]["/api/livez"]["method"] = c["passive"]["results"][0]["method"] = "POST"
    else: c["passive"]["results"][0]["degraded"] = True
    with pytest.raises(Exception): compact(c)


@pytest.mark.parametrize("case,label,mutation", [
    ("eval-run", "response", lambda value: value.update(execution_complete=False)),
    ("eval-run", "response", lambda value: value["receipt"].update(dsse={"signed": True})),
    ("eval-run", "readback", lambda value: value.update(payload_sha256="e" * 64)),
    ("agentloop-run", "response", lambda value: value["completion"].update(complete=False)),
    ("agentloop-run", "readback", lambda value: value.pop("eval_record")),
    ("operator-ask", "readback", lambda value: value["record"].update(lean_verified=True)),
])
def test_valid_outer_signature_cannot_substitute_for_native_proof(combined, case, label, mutation):
    c = combined
    resign_observation(c, case, label, mutation)
    # The offline binding validator alone may pass; fixed native semantics must deny.
    a.validate(c["bundle"], c["context"], now=c["now"])
    with pytest.raises(Exception): compact(c)


def test_reader_rechecks_current_context_and_never_exposes_raw_bundle(combined):
    c = combined
    value = compact(c)
    env = {"SPACE_ID": "SZLHOLDINGS/a11oy", "SZL_GIT_SHA": "a" * 40}
    subject = reader.Reader(environ=env)
    subject.execution_context_provider = lambda _digest: c["context"]  # Explicit synthetic trusted-owner fixture.
    subject.state = {"verdict": value, "source": "a" * 40, "reason": None,
                     "evidence": {}, "_execution_bundle": c["bundle"]}
    snapshot = subject.snapshot(now=c["now"])
    assert snapshot["verdict"] == value and "_execution_bundle" not in snapshot
    subject.execution_context_provider = lambda _digest: replace(c["context"], runtime_boot_id="restarted")
    assert subject.snapshot(now=c["now"])["verdict"] is None
    subject.execution_context_provider = None
    assert subject.snapshot(now=c["now"])["verdict"] is None


def test_served_route_requires_private_retained_evidence_and_revalidates_it(combined, monkeypatch):
    c = combined
    value = compact(c)
    for key, val in {"SPACE_ID": "SZLHOLDINGS/a11oy", "SZL_GIT_SHA": "a" * 40}.items():
        monkeypatch.setenv(key, val)
    subject = reader.Reader(environ=os.environ)
    subject.execution_context_provider = lambda _digest: c["context"]
    subject.state = {"verdict": value, "source": "a" * 40, "reason": None,
                     "evidence": {}, "_execution_bundle": c["bundle"]}
    monkeypatch.setattr(reader, "reader", subject)
    namespace = {"app": FastAPI(), "_RDRequest": Request, "_RDJSON": JSONResponse,
        "_rd_os": os, "_rd_json": json, "_rd_re": re, "_rd_math": math,
        "_rd_dt": datetime, "_rd_tz": timezone, "_rd_urlsplit": urlsplit,
        "_rd_artifact": reader, "_RD_HARNESS_DIR": str(ROOT), "_rd_load": lambda _paths: c["matrix"]}
    tree = ast.parse((ROOT / "serve.py").read_text())
    wanted = {"_rd_normalize_origin", "_rd_load_verdict", "_a11oy_readiness_tab_matrix"}
    functions = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in wanted]
    exec(compile(ast.Module(body=functions, type_ignores=[]), "staged-readiness-route", "exec"), namespace)
    request = Request({"type": "http", "query_string": b"view=summary", "headers": []})
    result = json.loads(asyncio.run(namespace["_a11oy_readiness_tab_matrix"](request)).body)
    assert result["probe_verdict_available"] is True
    assert result["verdict_summary"]["requiredNotProbed"] == 5
    subject.execution_context_provider = None
    result = json.loads(asyncio.run(namespace["_a11oy_readiness_tab_matrix"](request)).body)
    assert result["probe_verdict_available"] is False


@pytest.mark.parametrize("field,value", [("schema", "forged"), ("harness", None), ("doctrine", "v0"),
    ("base", "https://foreign.example"), ("checkedAt", "2020-01-01T00:00:00Z")])
def test_all_consumers_enforce_raw_passive_identity(combined, field, value):
    c = combined
    c["passive"][field] = value
    with pytest.raises(Exception):
        gate.validate_combined(c["passive"], c["matrix"], c["bundle"], c["context"], source="a" * 40, now=c["now"])
    with pytest.raises(Exception):
        relock.validate_verdict_evidence(base=c["passive"]["base"], checked_at=c["passive"]["checkedAt"],
            summary=c["passive"]["summary"], source_sha="a" * 40, expected_origin=a.ORIGIN,
            now=c["now"], execution_inputs=inputs(c))


def test_canonical_helper_cannot_accept_zero_claim_without_raw_execution(combined):
    c = combined
    summary = dict(c["passive"]["summary"], requiredNotProbed=0, skippedStateChanging=0, ok=6)
    with pytest.raises(Exception):
        relock.validate_verdict_evidence(base=a.ORIGIN, checked_at=c["passive"]["checkedAt"], summary=summary,
            source_sha="a" * 40, expected_origin=a.ORIGIN, now=c["now"])


def test_production_matrix_must_match_exact_source_bytes(combined, tmp_path):
    subset = tmp_path / "matrix.json"
    subset.write_bytes(a.canonical(combined["matrix"]))
    with pytest.raises(Exception, match="CANONICAL_MATRIX_BYTES_REQUIRED"):
        gate.canonical_matrix(subset)
    subset.write_bytes((ROOT / "tools/readiness-harness/tabs.json").read_bytes())
    assert gate.canonical_matrix(subset) == gate.canonical_matrix()


collector = load("combined_collector_test", ROOT / ".github/scripts/collect_execution_readiness.py")


def collection_payloads(c):
    return {
        collector.HF_INFO: {"id": "SZLHOLDINGS/a11oy", "sha": c["context"].runtime_revision,
            "runtime": {"sha": c["context"].runtime_revision, "stage": "RUNNING"}, "sdk": "docker", "private": False},
        a.ORIGIN + "/api/build-info": {"build": {"revision": c["context"].source_revision}},
        a.ORIGIN + "/api/a11oy/v1/series-a/status": {
            "schema": "szl.series-a-status/v1", "terminal": True, "state": "OBSERVED", "critical_failures": [],
            "source_revision": c["context"].source_revision, "runtime_boot_id": c["context"].runtime_boot_id,
            "signing_key_source": "persistent:env:SZL_COSIGN_PRIVATE_PEM",
            "database": "/tmp/a11oy-state/series-a/control-plane-v2.sqlite3",
            "storage": {"persistence_required": True, "required_mount": "/data", "mount_verified": True,
                "journal_mode": "DELETE", "instance_id": "store_" + "1" * 32,
                "created_at": stamp(c["now"] - timedelta(minutes=3)), "receipt_count": 6,
                "last_receipt_sequence": 6, "chain_head": "2" * 64}},
        a.ORIGIN + "/api/a11oy/v1/storage/status": {
            "schema": "szl.a11oy-storage-status/v2", "mode": "FENCED", "role": "WRITER", "writable": True,
            "unfenced": False, "alert": False, "pending_publish": [], "last_error": None, "epoch": 1,
            "lease": {"state": "ACTIVE", "sequence": 4, "heartbeat_age_s": 1},
            "stores": {name: {"kind": kind, "health": "OK", "blocked_code": None, "last_error_code": None,
                "snapshot_failures": 0, "integrity": "lmdb_read" if kind == "lmdb" else "integrity_check",
                "sha16": "3" * 16, "last_snapshot_age_s": 1, "unsnapshotted_change_age_s": None}
                for name, kind in relock.STATE_STORE_KINDS.items()}},
        a.ORIGIN + collector.EXPORT_PREFIX + c["context"].run_nonce: {
            "schema": "szl.execution-observation-export/v1", "bundle": c["bundle"],
            "storage_acknowledgment": {"snapshot_confirmed": True}, "archive_only": False, "publication_eligible": False,
            "execution_authorized": False, "passive_probe_modified": False}}


def test_get_only_collector_validates_signatures_and_full_before_after_bracket(combined):
    import httpx
    c = combined
    payloads = collection_payloads(c)
    seen = []
    def handler(request):
        seen.append(request)
        assert request.method == "GET"
        if collector.EXPORT_PREFIX in request.url.path:
            assert request.headers["authorization"] == "Bearer fixture-only-operator"
            assert request.headers["x-a11oy-tenant"] == "fixture-only-tenant"
        else:
            assert "authorization" not in request.headers and "x-a11oy-tenant" not in request.headers
        return httpx.Response(200, json=payloads[str(request.url)])
    with FixtureHTTPClient(transport=httpx.MockTransport(handler)) as client:
        bundle, report = collector.collect(client, c["context"], operator_token="fixture-only-operator",
                                            tenant="fixture-only-tenant", now=c["now"])
    assert bundle == c["bundle"] and len(seen) == 9
    assert report["bundle_sha256"] == a.digest(a.canonical(bundle))
    assert report["execution_authorized"] is False and report["provider_state_changed"] is False


@pytest.mark.parametrize("mutation", ["source", "hf", "boot", "epoch", "lease", "snapshot", "chain", "unfenced", "critical", "missingbundle", "fakesignature", "archive", "missingarchive", "absentcredentials"])
def test_collector_rejects_identity_storage_authority_and_signature_failures(combined, mutation):
    import httpx
    c = combined
    payloads = collection_payloads(c)
    calls = 0
    def handler(request):
        nonlocal calls
        calls += 1
        value = copy.deepcopy(payloads[str(request.url)])
        if calls > 5:
            if mutation == "source" and request.url.path == "/api/build-info": value["build"]["revision"] = "d" * 40
            if mutation == "hf" and str(request.url) == collector.HF_INFO: value["runtime"]["sha"] = "d" * 40
            if mutation == "boot" and request.url.path.endswith("series-a/status"): value["runtime_boot_id"] = "other"
            if request.url.path.endswith("storage/status"):
                if mutation == "epoch": value["epoch"] += 1
                if mutation == "lease": value["lease"]["sequence"] += 1
                if mutation == "snapshot": value["stores"]["series_a"]["sha16"] = "4" * 16
            if mutation == "chain" and request.url.path.endswith("series-a/status"): value["storage"]["chain_head"] = "4" * 64
        if mutation == "unfenced" and request.url.path.endswith("storage/status"): value["unfenced"] = True
        if mutation == "critical" and request.url.path.endswith("series-a/status"): value["critical_failures"] = ["fixture"]
        if collector.EXPORT_PREFIX in request.url.path:
            if mutation == "archive": value["archive_only"] = True
            if mutation == "missingarchive": value.pop("archive_only")
            if mutation == "missingbundle": value.pop("bundle")
            if mutation == "fakesignature": value["bundle"]["observations"][0]["receipt"]["signatures"][0]["sig"] = "AA=="
        return httpx.Response(200, json=value)
    with FixtureHTTPClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(Exception):
            collector.collect(client, c["context"], operator_token="" if mutation == "absentcredentials" else "fixture-only",
                              tenant="fixture-only", now=c["now"])
    if mutation == "absentcredentials": assert calls == 0
    else: assert calls >= 3


@pytest.mark.parametrize("kind", ["redirect", "html", "oversized", "invalid-length", "duplicates", "non-object", "exception"])
def test_collector_read_boundaries_and_sanitized_failures(combined, kind):
    import httpx
    seen = []
    def handler(request):
        seen.append(request)
        if kind == "redirect": return httpx.Response(302, headers={"location": "https://foreign.example/token-capture"})
        if kind == "html": return httpx.Response(200, text="<html>200</html>")
        if kind == "oversized": return httpx.Response(200, content=b" " * (collector.MAX_BYTES + 1), headers={"content-type": "application/json"})
        if kind == "invalid-length": return httpx.Response(200, content=b"{}", headers={"content-type": "application/json", "content-length": "invalid"})
        if kind == "duplicates": return httpx.Response(200, content=b'{"a":1,"a":2}', headers={"content-type": "application/json"})
        if kind == "non-object": return httpx.Response(200, json=[])
        raise RuntimeError("fixture-only-secret-must-not-appear")
    with FixtureHTTPClient(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        with pytest.raises(collector.CollectionBlocked) as raised:
            collector.fetch_json(client, a.ORIGIN + collector.EXPORT_PREFIX + combined["context"].run_nonce,
                                 authorization="fixture-only", tenant="fixture-only")
    assert len(seen) == 1
    assert "fixture-only-secret" not in str(raised.value)


def test_collector_blocks_foreign_routes_before_any_request():
    class NoNetwork:
        def stream(self, *args, **kwargs): raise AssertionError("network must not be reached")
    for url in ("https://foreign.example/", a.ORIGIN + "/api/anything", a.ORIGIN + collector.EXPORT_PREFIX + "../status"):
        with pytest.raises(collector.CollectionBlocked, match="FIXED_READ_ROUTE_REQUIRED"):
            collector.fetch_json(NoNetwork(), url, authorization="fixture-only", tenant="fixture-only")
    with pytest.raises(collector.CollectionBlocked, match="EXPORT_CREDENTIALS_REQUIRED"):
        collector.fetch_json(NoNetwork(), collector.HF_INFO, authorization="fixture-only", tenant="fixture-only")


def test_sole_workflow_passes_raw_separate_evidence_and_independent_context():
    import yaml
    text = (ROOT / ".github/workflows/hf-sync.yml").read_text()
    fragment = text[text.index("  readiness-verdict:"):text.index("  post-deployment-parity:")]
    assert fragment.count("collect_execution_readiness.py") == 1
    assert "--passive-verdict" in fragment and fragment.count("--execution-bundle") == 2
    assert fragment.count("vars.A11OY_EXECUTION_AUTHORITY_PINS_JSON") == 2
    assert fragment.count("vars.A11OY_EXECUTION_RUN_NONCE") == 2
    assert "actions/download-artifact@9000827ccba6bdab643e8b6fd33ac0654aef8333" in fragment
    assert 'name: canonical-a11oy-readiness-${{ github.run_id }}-${{ github.run_attempt }}' in fragment
    upload = fragment[fragment.index("      - name: Upload immutable full probe evidence"):fragment.index("      # The same fail-closed")]
    assert "execution-observations.json" in upload and "execution-authority-pins.json" not in upload
    # The upload action cannot see another step's environment. Bind its actual
    # paths to the collector's directory rather than an out-of-scope env name.
    steps = yaml.safe_load(text)["jobs"]["execution-readiness"]["steps"]
    collect_step = next(step for step in steps
                        if "collect_execution_readiness.py" in step.get("run", ""))
    upload_step = next(step for step in steps
                       if step.get("name") == "Upload immutable full probe evidence")
    folder = collect_step["env"]["EXECUTION_EVIDENCE_DIR"]
    assert folder == "${{ runner.temp }}/execution-evidence"
    assert upload_step["with"]["path"].splitlines() == [
        folder + "/readiness-verdict.json", folder + "/execution-observations.json"]
    assert "${{ env.VERDICT_PATH }}" not in upload
    assert "--validate-only" in fragment and "--matrix" not in fragment


def test_observer_allowlist_tracks_single_series_a_registration():
    allowlist = (ROOT / ".github/register-invocation-allowlist.txt").read_text()
    entries = [line for line in allowlist.splitlines() if line.split("#", 1)[0].strip() == "observer_runtime"]
    assert len(entries) == 1 and "routers.series_a_control_plane.register" in entries[0]
    assert "register_from_service" in entries[0]

    chain = [
        ("serve.py", None, "routers", "frontier_reads", "_fr_router.register"),
        ("routers/frontier_reads.py", "register", "routers", "series_a_control_plane", "_series_a_control_plane.register"),
        ("routers/series_a_control_plane.py", "register", "observer_runtime", "register_from_service", "register_from_service"),
    ]
    for path, function, module, imported, called in chain:
        tree = ast.parse((ROOT / path).read_text())
        if function:
            tree = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == function)
        bound = called.split(".", 1)[0]
        assert any(isinstance(node, ast.ImportFrom) and node.module == module and
                   any(alias.name == imported and (alias.asname or alias.name) == bound for alias in node.names)
                   for node in ast.walk(tree)), path
        calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call) and ast.unparse(node.func) == called]
        assert len(calls) == 1 and ast.unparse(calls[0].args[0]) == "app", path

    tree = ast.parse((ROOT / "observer_runtime.py").read_text())
    owner = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "register_from_service")
    calls = [node for node in ast.walk(owner) if isinstance(node, ast.Call) and ast.unparse(node.func) == "register"]
    assert len(calls) == 1 and [ast.unparse(arg) for arg in calls[0].args] == ["app", "subject"]


@pytest.mark.parametrize("mode", ["current", "cancelled", "different", "storage", "boot"])
def test_final_relock_rechecks_current_retained_owner(combined, monkeypatch, mode):
    import httpx
    c = combined
    payloads = collection_payloads(c)
    monkeypatch.setenv("A11OY_CODE_ADMIN_KEY", "fixture-only")
    monkeypatch.setenv("A11OY_CODE_TENANT", "fixture-only")
    seen = []
    def handler(request):
        seen.append(request)
        assert request.method == "GET"
        value = copy.deepcopy(payloads[str(request.url)])
        if mode == "cancelled" and collector.EXPORT_PREFIX in request.url.path:
            return httpx.Response(409, json={"status": "CANCELLED"})
        if mode == "different" and collector.EXPORT_PREFIX in request.url.path:
            value["bundle"]["observations"] = list(reversed(value["bundle"]["observations"]))
        if mode == "storage" and request.url.path.endswith("storage/status"):
            value["lease"]["state"] = "LOST"
        if mode == "boot" and request.url.path.endswith("series-a/status"):
            value["runtime_boot_id"] = "restarted"
        return httpx.Response(200, json=value)
    with FixtureHTTPClient(transport=httpx.MockTransport(handler)) as client:
        if mode == "current":
            result = relock.verify_current_execution_owner(inputs(c), client=client)
            assert result["bundle_sha256"] == a.digest(a.canonical(c["bundle"]))
        else:
            with pytest.raises(relock.RelockError, match="current retained execution owner"):
                relock.verify_current_execution_owner(inputs(c), client=client)
    assert seen and all(request.method == "GET" for request in seen)
    assert not any("challenge" in request.url.path for request in seen)


@pytest.mark.parametrize("mode", ["valid", "absent", "private-field", "same-authority", "exists"])
def test_public_pin_materializer_is_validated_exclusive_and_never_authorizes(combined, tmp_path, monkeypatch, mode):
    c = combined
    materializer = load("fixture_pin_materializer", ROOT / ".github/scripts/materialize_execution_authority_pins.py")
    context = c["context"]
    pins = {"schema": "szl.execution-authority-pins/v1", "approval_public_pem": context.authority_public_key.decode(),
            "approval_key_id": context.authority_key_id, "runtime_public_pem": context.runtime_public_key.decode(),
            "runtime_key_id": context.runtime_key_id}
    if mode == "private-field": pins["private_key"] = "fixture-forbidden"
    if mode == "same-authority":
        pins.update(approval_public_pem=pins["runtime_public_pem"], approval_key_id=pins["runtime_key_id"])
    monkeypatch.setenv("A11OY_EXECUTION_AUTHORITY_PINS_JSON", "" if mode == "absent" else json.dumps(pins))
    path = tmp_path / "public-pins.json"
    if mode == "exists": path.write_bytes(b"preserve-existing")
    code = materializer.main(["--source-sha", context.source_revision, "--runtime-sha", context.runtime_revision,
        "--boot-id", context.runtime_boot_id, "--run-nonce", context.run_nonce, "--output", str(path)])
    if mode == "valid":
        assert code == 0 and a.strict_json(path.read_bytes()) == pins
    elif mode == "exists":
        assert code == 2 and path.read_bytes() == b"preserve-existing"
    else:
        assert code == 2 and not path.exists()


def test_passive_browser_job_keeps_credentials_separate_from_execution_reads():
    text = (ROOT / ".github/workflows/hf-sync.yml").read_text()
    passive = text.split("  readiness-verdict:", 1)[1].split("  execution-readiness:", 1)[0]
    execution = text.split("  execution-readiness:", 1)[1].split("  relock:", 1)[0]
    assert "secrets." not in passive and "A11OY_CODE_ADMIN_KEY" not in passive
    assert "collect_execution_readiness.py" not in passive and "publish_readiness_verdict.py" not in passive
    assert "canonical-a11oy-passive-${{ github.run_id }}-${{ github.run_attempt }}" in passive
    assert "needs: readiness-verdict" in execution
    assert "Collect and verify admitted execution evidence" in execution
    assert "node " not in execution and "playwright" not in execution.lower()
    assert 'python -I -c' not in text
    assert "python -I -B .github/scripts/materialize_execution_authority_pins.py" in text
