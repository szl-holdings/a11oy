#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline contract for the execution-authority boundary.

An independently approved plan is checked before observation effects in
``ObserverRuntime.run``. ``execution_acceptance.validate_plan`` and the
operator binding run before ``adapters.preflight``. ``_acknowledge`` calls
``StateStore.snapshot_confirmed`` on the series-a label before
``adapters.capture``. That method is the active v2 writer acknowledgement.
Its docstring states that the acknowledgement does not admit a handler or
make an external effect atomic with the storage commit.

``routers.series_a_control_plane.Store.reserve_execution_observation``
consumes a nonce in local SQLite and says that commit is not the
acknowledgement authority. The caller must acknowledge the same row through
the active v2 store before dispatch.

The collector ``collect_execution_readiness.collect`` is GET-only. Its
success value and its blocked CLI path both keep ``execution_authorized``
false. This contract does not change that flag.

The final release decision in ``.github/workflows/hf-sync.yml`` is the job
``terminal-source-authorization``. It runs only
``scripts/hf_exact_main_ownership.py``, which classifies whether the
workflow SHA is still exact protected main. That script does not read an
approved plan, a v2 snapshot, or the merged szl-receipt
``examples/accountable-execution`` verifier. A COMMITTED reference receipt
is not an A11oy execution grant.

Missing integration: no step supplies the independently approved plan and
the v2 acknowledgement to ``terminal-source-authorization`` before that
job decides. The decision it does make is source ownership, not execution
acceptance.

Organization-card identity is a binding to ``szl-holdings/.github`` and
``huggingface/org-card.manifest.json``. It does not require the card
revision to equal the A11oy runtime SHA. ``probe_source`` records every
declared build-info path and fails only when no path observes one revision
or the observing paths disagree. A 404 on ``/api/source`` or a null
``/.well-known/szl-source.json`` revision is not, by itself, a defect.
The live canary identity URLs do not request either route.
"""
from __future__ import annotations

import base64
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from starlette.requests import Request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import a11oy_code_runloop as code_runloop
import a11oy_state_store as state_store
import szl_dsse

try:
    import fcntl  # noqa: F401  Linux hosts provide the real module.
except ModuleNotFoundError:
    import types
    fcntl = types.ModuleType("fcntl")
    fcntl.LOCK_EX = 2
    fcntl.LOCK_NB = 4
    fcntl.LOCK_UN = 8
    fcntl.flock = lambda *_args, **_kwargs: None
    sys.modules["fcntl"] = fcntl

from routers.series_a_control_plane import Store


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


acceptance = _load("authority_boundary_acceptance", ROOT / "tools/execution_acceptance.py")
collector = _load(
    "authority_boundary_collector",
    ROOT / ".github/scripts/collect_execution_readiness.py",
)
canary = _load(
    "authority_boundary_canary",
    ROOT / "scripts/audit_hf_frontend_live_canary_v1.py",
)
train = _load(
    "authority_boundary_train",
    ROOT / "scripts/verify_estate_release_train.py",
)

NOW = datetime(2026, 10, 16, 23, 40, tzinfo=timezone.utc)
SOURCE = "a" * 40
RUNTIME = "b" * 40
OTHER = "c" * 40
BOOT = "synthetic-boot"
NONCE = "d" * 64


def _stamp(value: datetime) -> str:
    return value.isoformat().replace("+00:00", "Z")


def _keypair():
    key = ec.generate_private_key(ec.SECP256R1())
    pem = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    return key, pem, szl_dsse.keyid_for_public_pem(pem.decode())


def _sign(payload, payload_type, key, key_id):
    body = szl_dsse.canonical_json(payload)
    pae = szl_dsse.pae(payload_type, body)
    return {
        "payloadType": payload_type,
        "payload": base64.b64encode(body).decode(),
        "signatures": [{
            "keyid": key_id,
            "sig": base64.b64encode(key.sign(pae, ec.ECDSA(hashes.SHA256()))).decode(),
        }],
    }


def _plan(context):
    bindings = {
        "origin": acceptance.ORIGIN,
        "source_revision": context.source_revision,
        "runtime_revision": context.runtime_revision,
        "runtime_boot_id": context.runtime_boot_id,
        "run_nonce": context.run_nonce,
    }
    bodies = {case_id: {"fixture": "SYNTHETIC_NOT_EXECUTED"} for case_id in acceptance.CONTRACTS}
    bodies["eval-run"] = {
        "model_id": "synthetic-model",
        "suite": "synthetic-suite",
        "execution_mode": "live",
        "execution_limits": {
            "max_model_requests": 8,
            "max_output_tokens": 1024,
            "max_elapsed_seconds": 120,
        },
    }
    bodies["agentloop-run"] = {
        "model_id": "synthetic-model",
        "eval_suite": "synthetic-suite",
        "task": "Synthetic no-request fixture",
        "mode": "chat",
        "sandbox": False,
        "max_retries": 0,
        "consult_brain": False,
        "allocate_energy": False,
        "execution_limits": {
            "max_model_requests": 9,
            "max_output_tokens": 1152,
            "max_elapsed_seconds": 120,
        },
    }
    return {
        "schema": "szl.execution-acceptance-plan/v1",
        **bindings,
        "issued_at": _stamp(NOW - timedelta(minutes=2)),
        "expires_at": _stamp(NOW + timedelta(minutes=2)),
        "operator_reference": "synthetic-operator",
        "max_requests": 5,
        "retries": 0,
        "cases": [
            {
                "id": case_id,
                "method": "POST",
                "path": path,
                "body": bodies[case_id],
                "expected_status": 200,
                "response_assertions": {"/synthetic": True},
                "readback_assertions": {"/fixture": "NOT_A_LIVE_RECEIPT"},
            }
            for case_id, path in acceptance.CONTRACTS.items()
        ],
    }


def _context():
    _authority, authority_pem, authority_id = _keypair()
    _runtime, runtime_pem, runtime_id = _keypair()
    context = acceptance.AdmissionContext(
        SOURCE, RUNTIME, BOOT, NONCE,
        authority_pem, authority_id, runtime_pem, runtime_id,
    )
    return context, _authority, authority_id


def _request(headers: dict[str, str]) -> Request:
    raw = [
        (key.lower().encode("latin-1"), value.encode("latin-1"))
        for key, value in headers.items()
    ]
    return Request({"type": "http", "headers": raw})


class _Bytes:
    def __init__(self, payload: dict):
        self.payload = json.dumps(payload).encode()

    def __iter__(self):
        yield self.payload


class _Response:
    def __init__(self, url: str, payload: dict):
        self.status_code = 200
        self.url = url
        self.headers = {"content-type": "application/json", "content-encoding": "identity"}
        self._payload = payload

    def iter_bytes(self):
        yield json.dumps(self._payload).encode()


class _Client:
    def __init__(self, routes: dict[str, dict]):
        self.routes = routes
        self.calls = []

    @contextmanager
    def stream(self, method, url, headers=None, follow_redirects=False):
        assert method == "GET"
        assert follow_redirects is False
        self.calls.append(url)
        yield _Response(url, self.routes[url])


def _routes(*, hf_sha=RUNTIME, source=SOURCE, boot=BOOT):
    return {
        collector.HF_INFO: {
            "id": "SZLHOLDINGS/a11oy",
            "sha": hf_sha,
            "sdk": "docker",
            "private": False,
            "runtime": {"sha": hf_sha, "stage": "RUNNING"},
        },
        collector.ORIGIN + "/api/build-info": {"build": {"revision": source}},
        collector.ORIGIN + "/api/a11oy/v1/series-a/status": {
            "schema": "szl.series-a-status/v1",
            "source_revision": source,
            "runtime_boot_id": boot,
            "signing_key_source": "persistent:env:SZL_COSIGN_PRIVATE_PEM",
        },
    }


def test_plan_is_enforced_before_effects_and_release_is_source_ownership():
    observer = (ROOT / "observer_runtime.py").read_text(encoding="utf-8")
    run = observer.split("async def run(", 1)[1].split("\n    def ", 1)[0]
    assert run.index("acceptance.validate_plan") < run.index("adapters.preflight")
    assert run.index("self._acknowledge") < run.index("adapters.capture")
    assert '"execution_authorized": False' in run
    acknowledgement = state_store.StateStore.snapshot_confirmed.__doc__
    assert "does not admit a handler" in acknowledgement
    reservation = Store.reserve_execution_observation.__doc__
    assert "active v2 store" in reservation
    assert "not that authority" in reservation

    workflow = (ROOT / ".github/workflows/hf-sync.yml").read_text(encoding="utf-8")
    terminal = workflow.split("  terminal-source-authorization:", 1)[1]
    assert "hf_exact_main_ownership.py" in terminal
    assert "snapshot_confirmed" not in terminal
    assert "accountable-execution" not in workflow
    assert "execution_authorized" not in terminal
    ownership = (ROOT / "scripts/hf_exact_main_ownership.py").read_text(encoding="utf-8")
    assert "execution_authorized" not in ownership
    assert "GET requests only" in ownership


def test_unauthorized_and_expired_plans_grant_nothing():
    context, authority, authority_id = _context()
    plan = _plan(context)
    forged = _sign(plan, acceptance.PLAN_TYPE, authority, authority_id)
    forged["signatures"][0]["sig"] = base64.b64encode(b"forged").decode()
    with pytest.raises(acceptance.EvidenceError, match="SIGNATURE_INVALID"):
        acceptance.validate_plan(forged, context, now=NOW)
    expired = dict(plan, expires_at=_stamp(NOW - timedelta(seconds=1)))
    with pytest.raises(acceptance.EvidenceError, match="PLAN_EXPIRED_OR_INVALID"):
        acceptance.validate_plan(
            _sign(expired, acceptance.PLAN_TYPE, authority, authority_id),
            context,
            now=NOW,
        )
    client = _Client({})

    def explode(*_args, **_kwargs):
        raise AssertionError("unauthorized collection must not read")

    client.stream = explode
    with pytest.raises(collector.CollectionBlocked, match="EXISTING_EXPORT_CREDENTIALS_REQUIRED"):
        collector.collect(client, context, operator_token="", tenant="synthetic-tenant", now=NOW)


def test_wrong_tenant_is_refused_before_any_execution_grant(monkeypatch):
    monkeypatch.setenv(code_runloop.TENANT_ENV, "admitted-tenant")
    refused = code_runloop._tenant_refusal(_request({"x-a11oy-tenant": "other-tenant"}))
    assert refused is not None
    assert refused.status_code == 403
    assert b"execution_authorized" not in refused.body
    admitted = code_runloop._tenant_refusal(_request({"x-a11oy-tenant": "admitted-tenant"}))
    assert admitted is None
    monkeypatch.delenv(code_runloop.TENANT_ENV)
    unconfigured = code_runloop._tenant_refusal(_request({"x-a11oy-tenant": "admitted-tenant"}))
    assert unconfigured is not None
    assert unconfigured.status_code == 503


def test_swapped_keys_are_rejected():
    context, authority, authority_id = _context()
    plan = _sign(_plan(context), acceptance.PLAN_TYPE, authority, authority_id)
    with pytest.raises(acceptance.EvidenceError, match="SEPARATE_AUTHORITY_REQUIRED"):
        acceptance.validate_plan(plan, replace(context, runtime_key_id=context.authority_key_id), now=NOW)
    _other, other_pem, _other_id = _keypair()
    with pytest.raises(acceptance.EvidenceError, match="PUBLIC_KEY_PIN_MISMATCH"):
        acceptance.validate_plan(plan, replace(context, authority_public_key=other_pem), now=NOW)
    swapped = replace(
        context,
        authority_public_key=context.runtime_public_key,
        authority_key_id=context.runtime_key_id,
        runtime_public_key=context.authority_public_key,
        runtime_key_id=context.authority_key_id,
    )
    with pytest.raises(acceptance.EvidenceError, match="SIGNER_MISMATCH"):
        acceptance.validate_plan(plan, swapped, now=NOW)


@pytest.mark.parametrize(
    ("field", "value", "routes"),
    [
        ("source_revision", OTHER, {"source": OTHER}),
        ("runtime_revision", OTHER, {"hf_sha": OTHER}),
        ("runtime_boot_id", "other-boot", {"boot": "other-boot"}),
    ],
)
def test_mismatched_source_hf_or_boot_identity_fails_closed(field, value, routes):
    context, authority, authority_id = _context()
    changed = dict(_plan(context), **{field: value})
    with pytest.raises(acceptance.EvidenceError, match="PLAN_BINDING_MISMATCH"):
        acceptance.validate_plan(
            _sign(changed, acceptance.PLAN_TYPE, authority, authority_id),
            context,
            now=NOW,
        )
    client = _Client(_routes(**routes))
    codes = {
        "source_revision": "SOURCE_IDENTITY_MISMATCH",
        "runtime_revision": "HF_IDENTITY_MISMATCH",
        "runtime_boot_id": "PROCESS_IDENTITY_MISMATCH",
    }
    with pytest.raises(collector.CollectionBlocked, match=codes[field]):
        collector.bracket(client, context)


def test_nonce_replay_stays_consumed_and_a_new_nonce_can_reserve(tmp_path, monkeypatch):
    monkeypatch.delenv("GDW_DURABLE_STORAGE", raising=False)
    monkeypatch.delenv("A11OY_STATE_STORE", raising=False)
    monkeypatch.delenv("A11OY_REQUIRE_PERSISTENT_STORAGE", raising=False)
    store = Store(str(tmp_path / "series-a.sqlite3"))
    fields = dict(
        source_revision=SOURCE,
        runtime_boot_id=BOOT,
        run_nonce=NONCE,
        plan_sha256="e" * 64,
        case_id="policy-decide",
        request_sha256="f" * 64,
        receipt_id="observation-boundary-1",
        started_at=_stamp(NOW),
    )
    first = store.reserve_execution_observation(**fields)
    assert first["state"] == "RESERVED"
    assert "execution_authorized" not in first
    with pytest.raises(ValueError, match="OBSERVATION_ATTEMPT_ALREADY_CONSUMED"):
        store.reserve_execution_observation(**fields)
    with pytest.raises(ValueError, match="OBSERVATION_NONCE_ALREADY_BOUND"):
        store.reserve_execution_observation(**dict(fields, plan_sha256="9" * 64, receipt_id="observation-boundary-2"))
    recovered = store.reserve_execution_observation(**dict(
        fields,
        run_nonce="1" * 64,
        receipt_id="observation-boundary-recovered",
    ))
    assert recovered["state"] == "RESERVED"
    assert recovered["run_nonce"] == "1" * 64
    completed = store.complete_execution_observation(
        recovered["receipt_id"],
        {"fixture": "NOT_A_LIVE_RECEIPT"},
    )
    assert completed["state"] == "COMPLETED"
    assert "execution_authorized" not in completed


def test_collector_success_shape_stays_unauthorized():
    source = (ROOT / ".github/scripts/collect_execution_readiness.py").read_text(encoding="utf-8")
    assert source.count('"execution_authorized": False') >= 3
    assert "execution_authorized\": True" not in source
    assert "execution_authorized\": true" not in source


def test_organization_card_binds_its_own_source_revision():
    expected = SOURCE
    card = OTHER
    identity = {
        "organization_deployment": {
            "schema": "szl.hf-static-deployment/v1",
            "source": {
                "repository": "szl-holdings/.github",
                "manifest": "huggingface/org-card.manifest.json",
                "revision": card,
            },
            "target": {
                "repo_id": "SZLHOLDINGS/README",
                "repo_type": "space",
                "live_base_url": "https://szlholdings-readme.static.hf.space",
            },
        },
        "a11oy_space_build": {
            "status": "OBSERVED",
            "build": {"revision": expected, "revision_source": "env:SZL_GIT_SHA"},
        },
        "a11oy_domain_build": {
            "status": "OBSERVED",
            "build": {"revision": expected, "revision_source": "env:SZL_GIT_SHA"},
        },
        "a11oy_space_metadata": {
            "sha": expected,
            "runtime": {"sha": expected, "stage": "RUNNING"},
        },
        "organization_space_metadata": {
            "id": "SZLHOLDINGS/README",
            "sha": card,
            "sdk": "static",
            "runtime": {"sha": card, "stage": "RUNNING"},
        },
    }
    assert canary.evaluate_identity(identity, expected) == []
    assert canary._organization_deployment_revision(identity["organization_deployment"]) == card
    broken = json.loads(json.dumps(identity))
    broken["organization_deployment"]["source"]["repository"] = "szl-holdings/a11oy"
    failures = canary.evaluate_identity(broken, expected)
    assert [item["code"] for item in failures] == ["ORG_DEPLOYMENT_IDENTITY_FAILED"]
    assert "/api/source" not in canary.IDENTITY_URLS.values()
    assert all("szl-source.json" not in url for url in canary.IDENTITY_URLS.values())


def test_absent_source_routes_are_not_defects_unless_observations_disagree(monkeypatch):
    sha = SOURCE

    def fetch(url, **_kwargs):
        if url.endswith("/api/source"):
            return {"status": 404, "json": None, "sha256": None, "redirect": None}
        if url.endswith("/.well-known/szl-source.json"):
            return {"status": 200, "json": {"revision": None}, "sha256": "1", "redirect": None}
        if url.endswith("/api/build-info"):
            return {
                "status": 200,
                "json": {"build": {"revision": sha}},
                "sha256": "2",
                "redirect": None,
            }
        raise AssertionError(url)

    monkeypatch.setattr(train, "fetch", fetch)
    observed = train.probe_source(
        "https://example.invalid",
        ("/api/build-info", "/.well-known/szl-source.json", "/api/source"),
    )
    assert observed["observed"] is True
    assert observed["revision"] == sha
    assert observed["identity_state"] == "OBSERVED"

    def disagree(url, **_kwargs):
        if url.endswith("/.well-known/szl-source.json"):
            return {
                "status": 200,
                "json": {"source_revision": OTHER},
                "sha256": "3",
                "redirect": None,
            }
        return fetch(url)

    monkeypatch.setattr(train, "fetch", disagree)
    conflict = train.probe_source(
        "https://example.invalid",
        ("/api/build-info", "/.well-known/szl-source.json", "/api/source"),
    )
    assert conflict["observed"] is False
    assert conflict["identity_state"] == "ENDPOINT_DISAGREEMENT"
