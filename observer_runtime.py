#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Provenance service: fixed-plan execution with durable attempt consumption.

The Series-A owner registers this module through register_from_service(). Source
registration does not establish live execution admission: independent public pins
and immutable process HF identity are mandatory; their absence disables execution.
No public method accepts a signer, target URL, runtime identity or SQL predicate.
"""

import asyncio
import base64
import hashlib
import json
import os
import re
import secrets
import sqlite3
import tempfile
import threading
from contextlib import asynccontextmanager, closing, nullcontext
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

import a11oy_state_store as state_store
from a11oy_code_runloop import _tenant_refusal
from routers.series_a_control_plane import Service, Store, _git_revision
from szl_dsse import pae
from szl_operator_auth import principal_from_headers
from szl_source_attestation import measure_hf_revision
from tools import execution_acceptance as acceptance


PREFIX = "/api/a11oy/v1/series-a/execution-observations"
CHALLENGE_TYPE = "application/vnd.szl.execution-observation-challenge.v1+json"
MAX_CHALLENGES = 64
MAX_EXPORTS = 8
MAX_ARCHIVE_SNAPSHOT = 64 * 1024 * 1024


class ObserverBlocked(ValueError):
    pass


def require(condition, code):
    if not condition:
        raise ObserverBlocked(code)


def utcnow():
    return datetime.now(timezone.utc)


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def error_code(exc):
    code = str(exc)
    return code if re.fullmatch(r"[A-Z][A-Z0-9_]{0,95}", code) else "OBSERVATION_UNAVAILABLE"


@dataclass(frozen=True)
class AuthorityPins:
    """Public-only configuration installed independently of request evidence."""

    approval_public_key: bytes
    approval_key_id: str
    runtime_public_key: bytes
    runtime_key_id: str

    @classmethod
    def from_file(cls, path):
        """Read only a deployment-selected public pin file; never mint authority."""
        if path is None:
            return None
        raw = Path(path).read_bytes()
        require(len(raw) <= 16384, "AUTHORITY_CONFIGURATION_TOO_LARGE")
        value = acceptance.strict_json(raw)
        acceptance.fields(value, "schema approval_public_pem approval_key_id runtime_public_pem runtime_key_id",
                          "INVALID_AUTHORITY_CONFIGURATION")
        require(value["schema"] == "szl.execution-authority-pins/v1", "INVALID_AUTHORITY_CONFIGURATION")
        pins = cls(value["approval_public_pem"].encode(), value["approval_key_id"],
                   value["runtime_public_pem"].encode(), value["runtime_key_id"])
        pins.validate()
        return pins

    def validate(self):
        require(self.approval_key_id != self.runtime_key_id, "SEPARATE_APPROVAL_AUTHORITY_REQUIRED")
        acceptance.public_key(self.approval_public_key, self.approval_key_id)
        acceptance.public_key(self.runtime_public_key, self.runtime_key_id)


@dataclass
class Challenge:
    nonce: str
    context: acceptance.AdmissionContext
    operator_reference: str
    issued_at: datetime
    expires_at: datetime
    state: str = "ISSUED"


class Observer:
    """Owns admission, existing Series-A storage, runtime signing and bounded export."""

    def __init__(self, service, app, *, authority_file=None):
        require(isinstance(service, Service), "SERIES_A_SERVICE_REQUIRED")
        self.service = service
        self.configuration_error = None
        try:
            self.pins = AuthorityPins.from_file(authority_file)
        except Exception:
            self.pins = None
            self.configuration_error = "INVALID_AUTHORITY_CONFIGURATION"
        self._app = app
        self._challenges = {}
        self._exports = {}
        self._archives = {}
        self.archive_status = "NOT_RESTORED"
        self._guard = threading.RLock()
        self._run_lock = asyncio.Lock()
        self._cancelled = set()
        self._active_nonce = None
        self._active_task = None
        self._installed_manager = None
        self.adapters = None

    def _fixed_adapters(self):
        if self.adapters is None:
            from observer_adapters import FixedAdapters
            require(self.pins is not None, "APPROVAL_AUTHORITY_UNAVAILABLE")
            require(self._native_owner() is not None, "NATIVE_READBACK_OWNER_UNAVAILABLE")
            return FixedAdapters(self._app, self.pins.runtime_public_key, self.pins.runtime_key_id)
        return self.adapters  # Explicit in-process test fixture only; no HTTP setter.

    def _native_owner(self):
        from native_readbacks import NativeReadbacks
        owner = getattr(self._app.state, "execution_native_readbacks", None)
        require(owner is None or (isinstance(owner, NativeReadbacks) and owner.service is self.service),
                "NATIVE_READBACK_OWNER_MISMATCH")
        return owner

    def _caller(self, headers):
        lowered = {str(key).lower(): str(value) for key, value in headers.items()}
        credentials = {key: lowered[key] for key in ("authorization", "x-a11oy-tenant") if key in lowered}
        require(principal_from_headers(credentials).get("operator") is True, "OPERATOR_REQUIRED")
        request = Request({"type": "http", "headers": [
            (key.encode("latin-1"), value.encode("latin-1")) for key, value in credentials.items()]})
        require(_tenant_refusal(request) is None, "TENANT_REQUIRED")
        operator_reference = "shared-operator:tenant-sha256:" + hashlib.sha256(
            credentials["x-a11oy-tenant"].encode()).hexdigest()
        return credentials, operator_reference

    def _identity(self, nonce):
        require(self.pins is not None, "APPROVAL_AUTHORITY_UNAVAILABLE")
        self.pins.validate()
        source = _git_revision()
        revision = measure_hf_revision("SZLHOLDINGS/a11oy")
        require(acceptance.SHA40.fullmatch(source or "") is not None, "PROTECTED_SOURCE_IDENTITY_UNAVAILABLE")
        require(revision.get("measurement_method") == "SPACE_REPOSITORY_COMMIT"
                and revision.get("revision_state") == "MEASURED"
                and acceptance.SHA40.fullmatch(revision.get("hf_revision") or "") is not None,
                "IMMUTABLE_PROCESS_HF_REVISION_UNAVAILABLE")
        signer = self.service.signer
        require(str(signer.source).startswith("persistent:")
                and isinstance(signer.private_key, ec.EllipticCurvePrivateKey)
                and isinstance(signer.private_key.curve, ec.SECP256R1), "PERSISTENT_RUNTIME_SIGNER_REQUIRED")
        actual_public = signer.private_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        acceptance.public_key(actual_public, self.pins.runtime_key_id)
        require(signer.keyid == self.pins.runtime_key_id, "RUNTIME_PUBLIC_PIN_MISMATCH")
        manager = state_store.active()
        require(isinstance(manager, state_store.StateStore), "ACTIVE_STATE_MANAGER_REQUIRED")
        require(self._installed_manager is None or manager is self._installed_manager,
                "STATE_MANAGER_REPLACED")
        require(manager.source_revision == source, "STATE_SOURCE_IDENTITY_MISMATCH")
        require(Path(self.service.store.path).resolve() == manager.local_path("series_a").resolve(),
                "REGISTERED_SERIES_A_PATH_REQUIRED")
        require(bool(self.service.runtime_boot_id), "PROCESS_BOOT_ID_REQUIRED")
        manager.confirmed_writer()
        return acceptance.AdmissionContext(source, revision["hf_revision"], self.service.runtime_boot_id,
            nonce, self.pins.approval_public_key, self.pins.approval_key_id,
            self.pins.runtime_public_key, self.pins.runtime_key_id), manager

    def _sign(self, payload, kind):
        require(kind in (CHALLENGE_TYPE, acceptance.RECEIPT_TYPE), "OBSERVATION_SIGNING_SCOPE_INVALID")
        raw = acceptance.canonical(payload)
        signature = self.service.signer.private_key.sign(pae(kind, raw), ec.ECDSA(hashes.SHA256()))
        result = {"payloadType": kind, "payload": base64.b64encode(raw).decode(),
                  "signatures": [{"keyid": self.pins.runtime_key_id,
                                  "sig": base64.b64encode(signature).decode()}]}
        public = acceptance.public_key(self.pins.runtime_public_key, self.pins.runtime_key_id)
        require(acceptance.verify(result, kind, public, self.pins.runtime_key_id) == payload,
                "OBSERVATION_SIGNATURE_VERIFICATION_FAILED")
        return result

    def challenge(self, headers):
        _, operator_reference = self._caller(headers)
        nonce = secrets.token_hex(32)
        context, manager = self._identity(nonce)
        now = utcnow()
        challenge = Challenge(nonce, context, operator_reference, now, now + acceptance.MAX_AGE)
        payload = {"schema": "szl.execution-observation-challenge/v1", "origin": acceptance.ORIGIN,
                   "source_revision": context.source_revision, "runtime_revision": context.runtime_revision,
                   "runtime_boot_id": context.runtime_boot_id, "run_nonce": nonce,
                   "operator_reference": operator_reference, "issued_at": stamp(now),
                   "expires_at": stamp(challenge.expires_at), "approval_key_id": self.pins.approval_key_id,
                   "runtime_key_id": self.pins.runtime_key_id, "execution_authorized": False}
        with self._guard:
            self._challenges = {key: value for key, value in self._challenges.items() if value.expires_at >= now}
            self._prune_exports(now)
            self._cancelled.intersection_update(set(self._challenges) | {self._active_nonce})
            require(len(self._challenges) < MAX_CHALLENGES, "OBSERVATION_CHALLENGE_CAPACITY_REACHED")
            receipt = self._sign(payload, CHALLENGE_TYPE)
            self._challenges[nonce] = challenge
            if self._installed_manager is None:
                manager.add_quiesce_hook(self._quiesce)
                self._installed_manager = manager
        return {"challenge": payload, "receipt": receipt, "execution_authorized": False}

    def _quiesce(self):
        with self._guard:
            nonce = self._active_nonce
        if nonce is not None:
            self._cancel(nonce)

    def _cancel(self, nonce):
        with self._guard:
            self._cancelled.add(nonce)
            self._exports.pop(nonce, None)
            challenge = self._challenges.get(nonce)
            if challenge is not None:
                challenge.state = "BURNED"
            active = self._active_task if nonce == self._active_nonce else None
        if active is not None:
            loop, task = active
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass  # Closed event loop cannot dispatch another case.

    def cancel(self, nonce, headers):
        _, operator_reference = self._caller(headers)
        require(type(nonce) is str and acceptance.HEX64.fullmatch(nonce), "OBSERVATION_NONCE_REQUIRED")
        with self._guard:
            challenge = self._challenges.get(nonce)
            require(challenge is not None, "OBSERVATION_CHALLENGE_CONSUMED_OR_UNKNOWN")
            require(challenge.operator_reference == operator_reference, "OPERATOR_BINDING_CHANGED")
        self._cancel(nonce)
        return {"state": "CANCEL_REQUESTED", "run_nonce": nonce, "retry_allowed": False,
                "remote_cancellation_confirmed": False, "publication_eligible": False}

    def _prune_exports(self, now):
        # Called only by authenticated POST paths while holding the guard.
        for key in [key for key, value in self._exports.items() if value[0].expires_at < now]:
            self._exports.pop(key)

    def _recheck(self, challenge, credentials, manager):
        _, operator_reference = self._caller(credentials)
        require(operator_reference == challenge.operator_reference, "OPERATOR_BINDING_CHANGED")
        require(utcnow() <= challenge.expires_at, "OBSERVATION_CHALLENGE_EXPIRED")
        with self._guard:
            require(challenge.nonce not in self._cancelled, "OBSERVATION_CANCELLED")
        observed, current = self._identity(challenge.nonce)
        require(current is manager and observed == challenge.context, "RUNTIME_IDENTITY_CHANGED")
        require(utcnow() <= challenge.expires_at, "OBSERVATION_CHALLENGE_EXPIRED")
        with self._guard:
            require(challenge.nonce not in self._cancelled, "OBSERVATION_CANCELLED")

    def _acknowledge(self, manager, rows):
        owner = self._native_owner()
        native_matches = owner.snapshot_predicate(rows) if owner is not None else lambda path: True
        nonce = rows[0]["run_nonce"]
        journal = self._journal_at(self.service.store.path, nonce)
        require(journal is not None, "SIGNED_PLAN_JOURNAL_REQUIRED")
        return manager.snapshot_confirmed("series_a", lambda path:
            self._journal_at(path, nonce) == journal and native_matches(path) and all(
            Store.execution_observation_matches(path, expected) for expected in rows))

    @staticmethod
    def _journal_at(path, nonce):
        with closing(sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)) as db:
            db.row_factory = sqlite3.Row
            if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                          "AND name='execution_observation_evidence'").fetchone() is None:
                return None
            row = db.execute("SELECT * FROM execution_observation_evidence WHERE run_nonce=?", (nonce,)).fetchone()
            return dict(row) if row is not None else None

    def _journal_plan(self, challenge, envelope):
        raw = acceptance.canonical(envelope).decode()
        context = challenge.context
        with self.service.store.lock, closing(self.service.store.connect()) as db, db:
            db.execute("""CREATE TABLE IF NOT EXISTS execution_observation_evidence(
                run_nonce TEXT PRIMARY KEY REFERENCES execution_observation_plans(run_nonce),
                source_revision TEXT NOT NULL, runtime_revision TEXT NOT NULL,
                runtime_boot_id TEXT NOT NULL, operator_reference TEXT NOT NULL,
                approval_key_id TEXT NOT NULL, runtime_key_id TEXT NOT NULL,
                plan_envelope_json TEXT NOT NULL, plan_envelope_sha256 TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('PLANNED','COMPLETE')),
                bundle_json TEXT, bundle_sha256 TEXT)""")
            db.execute("""INSERT INTO execution_observation_evidence
                (run_nonce,source_revision,runtime_revision,runtime_boot_id,operator_reference,
                 approval_key_id,runtime_key_id,plan_envelope_json,plan_envelope_sha256,state)
                VALUES(?,?,?,?,?,?,?,?,?,'PLANNED')""",
                (challenge.nonce, context.source_revision, context.runtime_revision, context.runtime_boot_id,
                 challenge.operator_reference, context.authority_key_id, context.runtime_key_id,
                 raw, acceptance.digest(raw.encode())))

    def _journal_complete(self, nonce, bundle):
        raw = acceptance.canonical(bundle).decode()
        with self.service.store.lock, closing(self.service.store.connect()) as db, db:
            row = db.execute("SELECT plan_envelope_json FROM execution_observation_evidence "
                             "WHERE run_nonce=? AND state='PLANNED'", (nonce,)).fetchone()
            require(row is not None and row[0] == acceptance.canonical(bundle["plan"]).decode(),
                    "SIGNED_PLAN_JOURNAL_MISMATCH")
            result = db.execute("UPDATE execution_observation_evidence SET state='COMPLETE',"
                                "bundle_json=?,bundle_sha256=? WHERE run_nonce=? AND state='PLANNED'",
                                (raw, acceptance.digest(raw.encode()), nonce))
            require(result.rowcount == 1, "BUNDLE_ALREADY_COMPLETED")

    def _durable_call(self, manager, nonce, function, *args, **kwargs):
        """A cancelled awaiting task cannot release an in-flight storage fence.

        Python cannot stop an already running filesystem/provider operation.
        The worker owns this additional inflight count until that operation
        finishes; a concurrent quiesce therefore cannot mistake it for drained.
        No subsequent effect or export is resumed after task cancellation.
        """
        require(manager.begin_write(), "OBSERVATION_WRITER_UNAVAILABLE")
        try:
            with self._guard:
                require(nonce not in self._cancelled, "OBSERVATION_CANCELLED")
            return function(*args, **kwargs)
        finally:
            manager.end_write()

    async def run(self, envelope, nonce, headers):
        credentials, operator_reference = self._caller(headers)
        require(type(nonce) is str and acceptance.HEX64.fullmatch(nonce), "OBSERVATION_NONCE_REQUIRED")
        envelope_bytes = acceptance.canonical(envelope)
        require(len(envelope_bytes) <= acceptance.MAX_BYTES, "PLAN_TOO_LARGE")
        envelope = acceptance.strict_json(envelope_bytes)
        async with self._run_lock:
            with self._guard:
                challenge = self._challenges.get(nonce)
                require(challenge is not None and challenge.state == "ISSUED", "OBSERVATION_CHALLENGE_CONSUMED_OR_UNKNOWN")
                require(operator_reference == challenge.operator_reference, "OPERATOR_BINDING_CHANGED")
                self._prune_exports(utcnow())
                require(len(self._exports) < MAX_EXPORTS, "OBSERVATION_EXPORT_CAPACITY_REACHED")
            context, manager = await asyncio.to_thread(self._identity, nonce)
            require(context == challenge.context, "RUNTIME_IDENTITY_CHANGED")
            plan = acceptance.validate_plan(envelope, context)
            require(plan["operator_reference"] == challenge.operator_reference, "OPERATOR_PLAN_BINDING_MISMATCH")
            require(acceptance.moment(plan["issued_at"]) >= challenge.issued_at
                    and acceptance.moment(plan["expires_at"]) <= challenge.expires_at,
                    "PLAN_CHALLENGE_VALIDITY_MISMATCH")
            challenge.expires_at = acceptance.moment(plan["expires_at"])
            adapters = self._fixed_adapters()
            await asyncio.to_thread(adapters.preflight, plan)
            require(manager.begin_write(), "OBSERVATION_WRITER_UNAVAILABLE")
            with self._guard:
                challenge.state = "BURNED"
                self._active_nonce = nonce
                self._active_task = (asyncio.get_running_loop(), asyncio.current_task())
            rows, observations = [], []
            plan_digest = acceptance.digest(acceptance.canonical(plan))
            try:
                await asyncio.to_thread(self._recheck, challenge, credentials, manager)
                planned = {case["id"]: case for case in plan["cases"]}
                for case_id in acceptance.CONTRACTS:
                    case = planned[case_id]
                    request = {key: case[key] for key in ("method", "path", "body")}
                    receipt_id = "observation-" + secrets.token_hex(24)
                    row = await asyncio.to_thread(self._durable_call, manager, nonce,
                        self.service.store.reserve_execution_observation,
                        source_revision=context.source_revision, runtime_boot_id=context.runtime_boot_id,
                        run_nonce=nonce, plan_sha256=plan_digest, case_id=case_id,
                        request_sha256=acceptance.digest(acceptance.canonical(request)),
                        receipt_id=receipt_id, started_at=stamp(utcnow()))
                    rows.append(row)
                await asyncio.to_thread(self._durable_call, manager, nonce, self._journal_plan, challenge, envelope)
                await asyncio.to_thread(self._durable_call, manager, nonce, self._acknowledge, manager, rows)
                for index, row in enumerate(rows):
                    await asyncio.to_thread(self._recheck, challenge, credentials, manager)
                    case = planned[row["case_id"]]
                    begun = utcnow()
                    owner = self._native_owner()
                    with owner.case_scope(nonce, row["case_id"]) if owner is not None else nullcontext():
                        remaining = (challenge.expires_at - utcnow()).total_seconds()
                        require(remaining > 0, "OBSERVATION_CHALLENGE_EXPIRED")
                        try:
                            # Cancels the internal ASGI await; strict native
                            # handlers close their shared execution budget and
                            # forbid subsequent provider dispatches. An already
                            # sent remote request cannot be recalled by this.
                            captured = await asyncio.wait_for(adapters.capture(case, credentials),
                                                              timeout=remaining)
                        except TimeoutError:
                            raise ObserverBlocked("OBSERVATION_AUTHORITY_EXPIRED") from None
                    await asyncio.to_thread(self._recheck, challenge, credentials, manager)
                    require(captured.response_status == case["expected_status"], "NATIVE_RESPONSE_STATUS_MISMATCH")
                    for name in ("response", "readback"):
                        raw = getattr(captured, name + "_bytes")
                        require(type(raw) is bytes and len(raw) <= acceptance.MAX_BODY, "OBSERVATION_BODY_TOO_LARGE")
                        value = acceptance.strict_json(raw)
                        for pointer, expected in case[name + "_assertions"].items():
                            observed = value
                            for part in pointer[1:].split("/"):
                                key = part.replace("~1", "/").replace("~0", "~")
                                require(type(observed) is dict and key in observed, "OBSERVATION_ASSERTION_MISSING")
                                observed = observed[key]
                            require(acceptance.canonical(observed) == acceptance.canonical(expected),
                                    "OBSERVATION_ASSERTION_FAILED")
                    payload = {"schema": "szl.execution-observation/v1", "receipt_id": row["receipt_id"],
                        "case_id": row["case_id"], "plan_sha256": plan_digest, "origin": acceptance.ORIGIN,
                        "source_revision": context.source_revision, "runtime_revision": context.runtime_revision,
                        "runtime_boot_id": context.runtime_boot_id, "run_nonce": nonce,
                        "operator_reference": operator_reference, "request_sha256": row["request_sha256"],
                        "response_sha256": acceptance.digest(captured.response_bytes),
                        "readback_sha256": acceptance.digest(captured.readback_bytes),
                        "response_status": captured.response_status, "started_at": stamp(begun),
                        "completed_at": stamp(utcnow())}
                    observation = {"receipt": self._sign(payload, acceptance.RECEIPT_TYPE),
                                   "response_b64": base64.b64encode(captured.response_bytes).decode(),
                                   "readback_b64": base64.b64encode(captured.readback_bytes).decode()}
                    await asyncio.to_thread(self._recheck, challenge, credentials, manager)
                    rows[index] = await asyncio.to_thread(self._durable_call, manager, nonce,
                                                         self.service.store.complete_execution_observation,
                                                         row["receipt_id"], observation)
                    await asyncio.to_thread(self._durable_call, manager, nonce, self._acknowledge, manager, rows)
                    observations.append(observation)
                bundle = {"schema": "szl.execution-acceptance-bundle/v1", "plan": envelope,
                          "observations": observations}
                acceptance.validate(bundle, context)
                await asyncio.to_thread(self._durable_call, manager, nonce, self._journal_complete, nonce, bundle)
                ack = await asyncio.to_thread(self._durable_call, manager, nonce, self._acknowledge, manager, rows)
                await asyncio.to_thread(self._recheck, challenge, credentials, manager)
                result = {"schema": "szl.execution-observation-export/v1", "bundle": bundle,
                          "storage_acknowledgment": ack, "publication_eligible": False,
                          "execution_authorized": False, "passive_probe_modified": False,
                          "archive_only": False}
                raw = acceptance.canonical(result)
                require(len(raw) <= acceptance.MAX_BYTES, "OBSERVATION_EXPORT_TOO_LARGE")
                with self._guard:
                    require(nonce not in self._cancelled, "OBSERVATION_CANCELLED")
                    require(len(self._exports) < MAX_EXPORTS, "OBSERVATION_EXPORT_CAPACITY_REACHED")
                    self._exports[nonce] = (challenge, raw, manager,
                        acceptance.digest(acceptance.canonical(bundle)))
                    challenge.state = "COMPLETED"
                return raw
            except BaseException:
                with self._guard:
                    self._cancelled.add(nonce)
                    self._exports.pop(nonce, None)
                raise
            finally:
                with self._guard:
                    self._active_nonce = None
                    self._active_task = None
                manager.end_write()

    async def export(self, nonce, headers):
        credentials, operator_reference = self._caller(headers)
        with self._guard:
            value = self._exports.get(nonce)
            archived = self._archives.get(nonce)
        if value is None and archived is not None:
            expected_operator, raw, manager = archived
            require(operator_reference == expected_operator, "OPERATOR_BINDING_CHANGED")
            require(state_store.active() is manager, "STATE_MANAGER_REPLACED")
            await asyncio.to_thread(manager.confirmed_writer)
            return raw
        require(value is not None, "OBSERVATION_EXPORT_UNAVAILABLE")
        challenge, raw, manager, _ = value
        require(operator_reference == challenge.operator_reference, "OPERATOR_BINDING_CHANGED")
        await asyncio.to_thread(self._recheck, challenge, credentials, manager)
        return raw

    def context_for_bundle_digest(self, digest):
        """Internal, read-only readiness admission from a previously accepted run.

        Only a digest indexes service-owned completed state. Submitted evidence
        never supplies source, boot, nonce, authority or key material. This is
        not an HTTP endpoint and does not grant execution or publish an artifact.
        """
        require(type(digest) is str and acceptance.HEX64.fullmatch(digest),
                "OBSERVATION_BUNDLE_DIGEST_REQUIRED")
        with self._guard:
            matches = [value for value in self._exports.values() if value[3] == digest]
            require(len(matches) == 1, "OBSERVATION_BUNDLE_NOT_ADMITTED")
            challenge, _, manager, _ = matches[0]
            require(challenge.state == "COMPLETED" and challenge.nonce not in self._cancelled,
                    "OBSERVATION_BUNDLE_NOT_ADMITTED")
        require(utcnow() <= challenge.expires_at, "OBSERVATION_CHALLENGE_EXPIRED")
        current, current_manager = self._identity(challenge.nonce)
        require(current == challenge.context and current_manager is manager, "RUNTIME_IDENTITY_CHANGED")
        require(utcnow() <= challenge.expires_at, "OBSERVATION_CHALLENGE_EXPIRED")
        with self._guard:
            require(challenge.state == "COMPLETED" and challenge.nonce not in self._cancelled
                    and challenge.nonce in self._exports, "OBSERVATION_BUNDLE_NOT_ADMITTED")
        return current

    def restore_completed_archives(self):
        """Startup-only restore from already acknowledged immutable SQLite bytes.

        Historical context is used only to verify archived signatures at their
        original validity interval. It never enters the current-boot admission
        cache, never permits replay, and never grants readiness or execution.
        GET handlers read these frozen bytes without SQLite/schema/signing work.
        """
        require(self.pins is not None, "APPROVAL_AUTHORITY_UNAVAILABLE")
        owner = self._native_owner()
        require(owner is not None, "NATIVE_READBACK_OWNER_UNAVAILABLE")
        with self._guard:
            require(self._active_nonce is None and not self._exports and not self._challenges,
                    "ARCHIVE_RESTORE_STARTUP_ONLY")
        manager = state_store.active()
        require(isinstance(manager, state_store.StateStore)
                and Path(self.service.store.path).resolve() == manager.local_path("series_a").resolve(),
                "REGISTERED_SERIES_A_PATH_REQUIRED")
        head = manager.confirmed_writer()
        entry = head["snapshots"].get("series_a")
        if entry is None:
            self.archive_status = "NO_ACKNOWLEDGED_ARCHIVE"
            return {"restored": 0, "read_only": True}
        require(type(entry.get("size")) is int and 0 < entry["size"] <= MAX_ARCHIVE_SNAPSHOT,
                "ARCHIVE_SNAPSHOT_TOO_LARGE")
        raw = manager.objects.get_bytes(entry["path"], limit=entry["size"])
        require(type(raw) is bytes and len(raw) == entry["size"]
                and acceptance.digest(raw) == entry["sha256"], "ARCHIVE_SNAPSHOT_MISMATCH")
        restored = {}
        with tempfile.TemporaryDirectory(prefix="szl-observation-archive-") as temporary:
            path = Path(temporary) / "acknowledged.sqlite3"
            path.write_bytes(raw)
            report = state_store.verify_sqlite(path, full=True)
            require(report["ok"] and report["logical_sha256"] == entry["logical_sha256"],
                    "ARCHIVE_SNAPSHOT_INVALID")
            with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as db:
                if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                              "AND name='execution_observation_evidence'").fetchone() is None:
                    self.archive_status = "NO_ACKNOWLEDGED_ARCHIVE"
                    return {"restored": 0, "read_only": True}
                nonces = [row[0] for row in db.execute("SELECT run_nonce FROM execution_observation_evidence "
                    "WHERE state='COMPLETE' ORDER BY rowid DESC LIMIT ?", (MAX_EXPORTS,))]
            for nonce in nonces:
                journal = self._journal_at(path, nonce)
                require(journal["approval_key_id"] == self.pins.approval_key_id
                        and journal["runtime_key_id"] == self.pins.runtime_key_id, "ARCHIVE_PUBLIC_PINS_CHANGED")
                body = journal["bundle_json"].encode()
                require(acceptance.digest(body) == journal["bundle_sha256"], "ARCHIVE_BUNDLE_HASH_MISMATCH")
                bundle = acceptance.strict_json(body)
                require(acceptance.canonical(bundle["plan"]).decode() == journal["plan_envelope_json"]
                        and acceptance.digest(journal["plan_envelope_json"].encode()) ==
                        journal["plan_envelope_sha256"], "ARCHIVE_PLAN_MISMATCH")
                historical = acceptance.AdmissionContext(journal["source_revision"], journal["runtime_revision"],
                    journal["runtime_boot_id"], nonce, self.pins.approval_public_key, self.pins.approval_key_id,
                    self.pins.runtime_public_key, self.pins.runtime_key_id)
                plan = acceptance.verify(bundle["plan"], acceptance.PLAN_TYPE,
                    acceptance.public_key(self.pins.approval_public_key, self.pins.approval_key_id),
                    self.pins.approval_key_id)
                acceptance.validate(bundle, historical, now=acceptance.moment(plan["expires_at"]))
                require(plan["operator_reference"] == journal["operator_reference"], "ARCHIVE_OPERATOR_MISMATCH")
                public = acceptance.public_key(self.pins.runtime_public_key, self.pins.runtime_key_id)
                stored_rows = []
                for observation in bundle["observations"]:
                    receipt = acceptance.verify(observation["receipt"], acceptance.RECEIPT_TYPE,
                                                public, self.pins.runtime_key_id)
                    stored = Store.read_execution_observation_at(path, receipt["receipt_id"])
                    require(stored is not None and stored["state"] == "COMPLETED"
                            and stored["run_nonce"] == nonce
                            and stored["source_revision"] == journal["source_revision"]
                            and stored["runtime_boot_id"] == journal["runtime_boot_id"]
                            and stored["plan_sha256"] == receipt["plan_sha256"]
                            and stored["case_id"] == receipt["case_id"]
                            and stored["request_sha256"] == receipt["request_sha256"]
                            and stored["observation_json"] == acceptance.canonical(observation).decode()
                            and stored["observation_sha256"] == acceptance.digest(acceptance.canonical(observation)),
                            "ARCHIVE_NATIVE_ROW_MISMATCH")
                    require(acceptance.moment(plan["issued_at"]) <= acceptance.moment(stored["started_at"])
                            <= acceptance.moment(receipt["started_at"]), "ARCHIVE_RESERVATION_TIME_MISMATCH")
                    stored_rows.append(stored)
                require(owner.snapshot_predicate(stored_rows)(path), "ARCHIVE_OWNING_NATIVE_READBACK_MISMATCH")
                ack = {"schema": "szl.state-restored-snapshot/v1", "label": "series_a", "entry": dict(entry),
                       "epoch": head["epoch"], "writer_id": head["writer_id"], "boot_id": head["boot_id"],
                       "verification": "ACKNOWLEDGED_IMMUTABLE_BYTES", "current_runtime_admitted": False}
                exported = acceptance.canonical({"schema": "szl.execution-observation-export/v1",
                    "bundle": bundle, "storage_acknowledgment": ack, "archive_only": True,
                    "publication_eligible": False, "execution_authorized": False, "passive_probe_modified": False})
                require(len(exported) <= acceptance.MAX_BYTES, "OBSERVATION_EXPORT_TOO_LARGE")
                restored[nonce] = (journal["operator_reference"], exported, manager)
        current = manager.confirmed_writer()
        require(current["snapshots"].get("series_a") == entry, "ARCHIVE_SNAPSHOT_CHANGED")
        with self._guard:
            self._archives = restored
            self.archive_status = "RESTORED_HISTORICAL_ONLY"
        return {"restored": len(restored), "read_only": True, "current_runtime_admitted": False}


def register(app, observer):
    """Mount the existing Series-A observer; registration grants no execution authority."""
    async def challenge(request):
        try:
            observer._caller(request.headers)
            async for chunk in request.stream():
                require(not chunk, "CHALLENGE_BODY_FORBIDDEN")
            result = await asyncio.to_thread(observer.challenge, request.headers)
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        except Exception as exc:
            return JSONResponse({"status": "BLOCKED", "error": error_code(exc)}, status_code=403,
                                headers={"Cache-Control": "no-store"})

    async def execute(request):
        try:
            observer._caller(request.headers)
            body = bytearray()
            async for chunk in request.stream():
                require(len(body) + len(chunk) <= acceptance.MAX_BYTES, "PLAN_TOO_LARGE")
                body.extend(chunk)
            value = acceptance.strict_json(bytes(body))
            acceptance.fields(value, "plan run_nonce", "INVALID_OBSERVATION_REQUEST")
            result = await observer.run(value["plan"], value["run_nonce"], request.headers)
            return Response(result, media_type="application/json", headers={"Cache-Control": "no-store"})
        except Exception as exc:
            return JSONResponse({"status": "BLOCKED", "error": error_code(exc)}, status_code=409,
                                headers={"Cache-Control": "no-store"})

    async def export(request):
        try:
            result = await observer.export(request.path_params["nonce"], request.headers)
            return Response(result, media_type="application/json", headers={"Cache-Control": "no-store"})
        except Exception as exc:
            return JSONResponse({"status": "BLOCKED", "error": error_code(exc)}, status_code=409,
                                headers={"Cache-Control": "no-store"})

    async def cancel(request):
        try:
            observer._caller(request.headers)
            async for chunk in request.stream():
                require(not chunk, "CANCEL_BODY_FORBIDDEN")
            result = observer.cancel(request.path_params["nonce"], request.headers)
            return JSONResponse(result, headers={"Cache-Control": "no-store"})
        except Exception as exc:
            return JSONResponse({"status": "BLOCKED", "error": error_code(exc)}, status_code=409,
                                headers={"Cache-Control": "no-store"})

    routes = [Route(PREFIX + "/challenge", challenge, methods=["POST"]),
              Route(PREFIX + "/run", execute, methods=["POST"]),
              Route(PREFIX + "/cancel/{nonce}", cancel, methods=["POST"]),
              Route(PREFIX + "/exports/{nonce}", export, methods=["GET"])]
    app.router.routes[0:0] = routes
    return {"registered": [route.path for route in routes], "publication_eligible": False}


def register_from_service(app):
    """Concrete Series-A startup integration; no new service or signer is made.

    The public pin path is deployment configuration, never an HTTP parameter.
    An absent/invalid file leaves every execution route disabled. The existing
    registered Service and active StateStore retain ownership and lifecycle.
    """
    require(getattr(app.state, "szl_execution_observer", None) is None,
            "OBSERVATION_SERVICE_ALREADY_REGISTERED")
    service = getattr(app.state, "szl_series_a_service", None)
    subject = Observer(service, app, authority_file=os.environ.get("A11OY_EXECUTION_AUTHORITY_FILE") or None)
    require(getattr(app.state, "execution_native_readbacks", None) is None,
            "NATIVE_READBACK_OWNER_ALREADY_REGISTERED")
    if subject.pins is not None:
        from native_readbacks import NativeReadbacks
        app.state.execution_native_readbacks = NativeReadbacks(
            service, subject.pins.runtime_public_key, subject.pins.runtime_key_id)
    result = register(app, subject)
    app.state.szl_execution_observer = subject
    async def restore_archives():
        if subject.pins is None:
            subject.archive_status = "DISABLED_NO_AUTHORITY"
            return
        try:
            await asyncio.to_thread(subject.restore_completed_archives)
        except Exception as exc:
            subject.archive_status = error_code(exc)
    prior_lifespan = app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(application):
        async with prior_lifespan(application) as state:
            await restore_archives()
            yield state
    app.router.lifespan_context = lifespan
    return {**result, "authority_configured": subject.pins is not None,
            "configuration_error": subject.configuration_error, "sign_on_read": False}
