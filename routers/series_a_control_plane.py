# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings
"""Series-A Live Control Plane for A11oy.

One additive controller combines three previously separate payload families:

* a signed, current estate truth plane;
* a bounded Counterfactual Action Passport; and
* a zero-bandaid, one-attempt local action executor.

It uses real GitHub, Hugging Face, HTTP, SQLite, and ECDSA-P256 boundaries.
GET/HEAD requests never sign or mutate state. Refresh/evaluate/execute operations
are explicit POSTs, append hash-linked receipts, and fail closed.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, AsyncIterator, Callable, Mapping
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse

SCHEMA_MANIFEST = "szl.estate-manifest/v2"
SCHEMA_PASSPORT = "szl.counterfactual-action-passport/v3"
SCHEMA_RECEIPT = "szl.series-a-receipt/v1"
SCHEMA_STATUS = "szl.series-a-status/v1"
SCHEMA_TRUST = "szl.agent-trust-factor/v1"
PAYLOAD_TYPE = "application/vnd.szl.series-a-receipt.v1+json"
ORG = "szl-holdings"
HF_ORG = "SZLHOLDINGS"
CANONICAL_SPACE = f"{HF_ORG}/a11oy"
FORBIDDEN_CLONES = tuple(f"{HF_ORG}/a11oy-clone-{index}" for index in range(1, 5))
TTL_SECONDS = 300
MAX_BODY = 64 * 1024
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_PAGES = 20
ALLOWED_ACTIONS = {"estate.refresh", "probe.public_surface"}
ALLOWED_PROBE_HOSTS = {
    "a-11-oy.com",
    "a11oy.net",
    "szlholdings-a11oy.hf.space",
    "szlholdings-killinchu.hf.space",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _future(seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=seconds)).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def _canonical(value: Any) -> bytes:
    """Narrow deterministic JSON for signed control-plane records."""

    def walk(item: Any, path: str = "$") -> None:
        if isinstance(item, float):
            raise ValueError(f"{path}: floats are forbidden in signed records")
        if isinstance(item, dict):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise ValueError(f"{path}: keys must be strings")
                lowered = key.lower()
                if any(token in lowered for token in ("password", "secret_value", "private_key", "authorization")):
                    raise ValueError(f"{path}.{key}: secret-shaped field is forbidden")
                walk(child, f"{path}.{key}")
            return
        if isinstance(item, list):
            for index, child in enumerate(item):
                walk(child, f"{path}[{index}]")
            return
        if item is None or isinstance(item, (str, int, bool)):
            return
        raise ValueError(f"{path}: unsupported type {type(item).__name__}")

    walk(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _sha(value: Any) -> str:
    payload = value if isinstance(value, (bytes, bytearray)) else _canonical(value)
    return hashlib.sha256(payload).hexdigest()


def _pae(payload_type: str, payload: bytes) -> bytes:
    ptype = payload_type.encode("utf-8")
    return b"DSSEv1 " + str(len(ptype)).encode() + b" " + ptype + b" " + str(len(payload)).encode() + b" " + payload


def _safe_error(exc: Exception) -> dict[str, str]:
    return {"error_class": type(exc).__name__, "error": str(exc)[:240]}


def _git_revision() -> str:
    for key in ("SZL_GIT_SHA", "A11OY_GIT_SHA", "GITHUB_SHA"):
        value = (os.environ.get(key) or "").strip().lower()
        if len(value) == 40 and all(ch in "0123456789abcdef" for ch in value):
            return value
    return "UNKNOWN"


class ReceiptSigner:
    def __init__(self) -> None:
        self.private_key = None
        self.public_pem = ""
        self.source = "unavailable"
        self.error = ""
        try:
            from a11oy_signing_key import load_signing_key

            private_key, public_pem, source, error = load_signing_key()
            self.private_key = private_key
            self.public_pem = public_pem or ""
            self.source = source or "unavailable"
            self.error = error or ""
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {str(exc)[:180]}"

    @property
    def keyid(self) -> str | None:
        return _sha(self.public_pem.encode("utf-8")) if self.public_pem else None

    def sign(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        body = _canonical(dict(payload))
        envelope: dict[str, Any] = {
            "payloadType": PAYLOAD_TYPE,
            "payload": base64.b64encode(body).decode("ascii"),
            "signatures": [],
            "pae_sha256": hashlib.sha256(_pae(PAYLOAD_TYPE, body)).hexdigest(),
            "key_source": self.source,
        }
        if self.private_key is None:
            envelope["signature_status"] = "UNSIGNED_UNAVAILABLE"
            envelope["signature_error"] = self.error or "signing key unavailable"
            return envelope
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import ec

            signature = self.private_key.sign(
                _pae(PAYLOAD_TYPE, body), ec.ECDSA(hashes.SHA256())
            )
            envelope["signatures"] = [
                {
                    "keyid": self.keyid,
                    "sig": base64.b64encode(signature).decode("ascii"),
                }
            ]
            envelope["signature_status"] = "SIGNED"
            return envelope
        except Exception as exc:
            envelope["signature_status"] = "UNSIGNED_ERROR"
            envelope["signature_error"] = f"{type(exc).__name__}: {str(exc)[:180]}"
            return envelope


class Store:
    def __init__(self, requested_path: str | None = None) -> None:
        self.path = self._resolve_path(requested_path)
        self.lock = threading.RLock()
        self._init()

    @staticmethod
    def _resolve_path(requested: str | None) -> str:
        candidates = [
            requested or os.environ.get("A11OY_SERIES_A_DB") or "/data/series-a/control-plane.sqlite3",
            "/tmp/a11oy_series_a_control_plane.sqlite3",
        ]
        for candidate in candidates:
            try:
                path = Path(candidate)
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.parent.joinpath(".write-probe").open("w", encoding="utf-8") as probe:
                    probe.write("ok")
                path.parent.joinpath(".write-probe").unlink(missing_ok=True)
                return str(path)
            except Exception:
                continue
        raise RuntimeError("no writable SQLite location")

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=FULL")
        return connection

    def _init(self) -> None:
        with self.lock, self.connect() as db:
            db.executescript(
                """
                CREATE TABLE IF NOT EXISTS snapshots(
                  digest TEXT PRIMARY KEY,
                  payload TEXT NOT NULL,
                  envelope TEXT NOT NULL,
                  observed_at TEXT NOT NULL,
                  valid_until TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS passports(
                  digest TEXT PRIMARY KEY,
                  payload TEXT NOT NULL,
                  decision TEXT NOT NULL,
                  attempts INTEGER NOT NULL DEFAULT 0 CHECK(attempts BETWEEN 0 AND 1),
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS receipts(
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                  receipt_id TEXT NOT NULL UNIQUE,
                  kind TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  envelope TEXT NOT NULL,
                  previous_hash TEXT NOT NULL,
                  receipt_hash TEXT NOT NULL UNIQUE,
                  created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events(
                  sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                  event_id TEXT NOT NULL UNIQUE,
                  kind TEXT NOT NULL,
                  payload TEXT NOT NULL,
                  created_at TEXT NOT NULL
                );
                """
            )

    def append_event(self, kind: str, payload: Mapping[str, Any]) -> None:
        with self.lock, self.connect() as db:
            db.execute(
                "INSERT INTO events(event_id,kind,payload,created_at) VALUES(?,?,?,?)",
                (f"evt_{uuid.uuid4().hex}", kind, json.dumps(dict(payload), sort_keys=True), _now()),
            )

    def events_since(self, sequence: int, limit: int = 100) -> list[dict[str, Any]]:
        with self.lock, self.connect() as db:
            rows = db.execute(
                "SELECT sequence,event_id,kind,payload,created_at FROM events WHERE sequence>? ORDER BY sequence LIMIT ?",
                (max(0, sequence), max(1, min(limit, 500))),
            ).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "event_id": row["event_id"],
                "kind": row["kind"],
                "payload": json.loads(row["payload"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def append_receipt(
        self, kind: str, payload: Mapping[str, Any], signer: ReceiptSigner
    ) -> dict[str, Any]:
        with self.lock, self.connect() as db:
            row = db.execute(
                "SELECT receipt_hash FROM receipts ORDER BY sequence DESC LIMIT 1"
            ).fetchone()
            previous = row["receipt_hash"] if row else "0" * 64
            receipt = {
                "schema": SCHEMA_RECEIPT,
                "receipt_id": f"rcpt_{uuid.uuid4().hex}",
                "kind": kind,
                "created_at": _now(),
                "source_revision": _git_revision(),
                "previous_receipt_hash": previous,
                "payload": dict(payload),
            }
            envelope = signer.sign(receipt)
            receipt_hash = _sha(envelope)
            db.execute(
                """INSERT INTO receipts(receipt_id,kind,payload,envelope,previous_hash,receipt_hash,created_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (
                    receipt["receipt_id"],
                    kind,
                    json.dumps(receipt, sort_keys=True),
                    json.dumps(envelope, sort_keys=True),
                    previous,
                    receipt_hash,
                    receipt["created_at"],
                ),
            )
        self.append_event(kind, {"receipt_hash": receipt_hash, "receipt_id": receipt["receipt_id"]})
        return {"receipt": receipt, "envelope": envelope, "receipt_hash": receipt_hash}

    def list_receipts(self, limit: int = 50) -> list[dict[str, Any]]:
        with self.lock, self.connect() as db:
            rows = db.execute(
                "SELECT sequence,kind,payload,envelope,receipt_hash,created_at FROM receipts ORDER BY sequence DESC LIMIT ?",
                (max(1, min(limit, 200)),),
            ).fetchall()
        return [
            {
                "sequence": row["sequence"],
                "kind": row["kind"],
                "receipt": json.loads(row["payload"]),
                "envelope": json.loads(row["envelope"]),
                "receipt_hash": row["receipt_hash"],
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    def save_snapshot(self, manifest: Mapping[str, Any], envelope: Mapping[str, Any]) -> str:
        digest = _sha(manifest)
        with self.lock, self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO snapshots(digest,payload,envelope,observed_at,valid_until) VALUES(?,?,?,?,?)",
                (
                    digest,
                    json.dumps(dict(manifest), sort_keys=True),
                    json.dumps(dict(envelope), sort_keys=True),
                    manifest["observed_at"],
                    manifest["valid_until"],
                ),
            )
        return digest

    def latest_snapshot(self) -> dict[str, Any] | None:
        with self.lock, self.connect() as db:
            row = db.execute(
                "SELECT digest,payload,envelope,observed_at,valid_until FROM snapshots ORDER BY observed_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return {
            "digest": row["digest"],
            "manifest": json.loads(row["payload"]),
            "envelope": json.loads(row["envelope"]),
            "observed_at": row["observed_at"],
            "valid_until": row["valid_until"],
        }

    def save_passport(self, passport: Mapping[str, Any]) -> str:
        digest = _sha(passport)
        with self.lock, self.connect() as db:
            db.execute(
                "INSERT INTO passports(digest,payload,decision,attempts,created_at) VALUES(?,?,?,?,?)",
                (digest, json.dumps(dict(passport), sort_keys=True), passport["decision"], 0, passport["created_at"]),
            )
        return digest

    def load_passport(self, digest: str) -> dict[str, Any] | None:
        with self.lock, self.connect() as db:
            row = db.execute(
                "SELECT payload,decision,attempts FROM passports WHERE digest=?", (digest,)
            ).fetchone()
        if row is None:
            return None
        value = json.loads(row["payload"])
        value["attempts"] = row["attempts"]
        return value

    def consume_attempt(self, digest: str) -> None:
        with self.lock, self.connect() as db:
            result = db.execute(
                "UPDATE passports SET attempts=1 WHERE digest=? AND attempts=0", (digest,)
            )
            if result.rowcount != 1:
                raise RuntimeError("passport attempt is absent or already consumed")


@dataclass
class Observation:
    state: str
    value: Any = None
    detail: Mapping[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        value = {"state": self.state}
        if self.value is not None:
            value["value"] = self.value
        if self.detail:
            value["detail"] = dict(self.detail)
        return value


class Collector:
    def __init__(self) -> None:
        self.github_token = (os.environ.get("GITHUB_TOKEN") or "").strip()
        self.hf_token = (os.environ.get("HF_TOKEN") or "").strip()

    async def _json(
        self,
        client: httpx.AsyncClient,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        allowed_host: str,
    ) -> tuple[Any, httpx.Response]:
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != allowed_host or parsed.username or parsed.password:
            raise RuntimeError("outbound URL left the fixed HTTPS origin")
        response = await client.get(url, params=params)
        if response.status_code != 200:
            raise RuntimeError(f"HTTP {response.status_code}")
        if len(response.content) > MAX_RESPONSE_BYTES:
            raise RuntimeError("response exceeded byte limit")
        final = urlsplit(str(response.url))
        if final.scheme != "https" or final.hostname != allowed_host:
            raise RuntimeError("redirect left the fixed HTTPS origin")
        return response.json(), response

    async def github(self) -> Observation:
        headers = {"accept": "application/vnd.github+json", "user-agent": "szl-series-a/1"}
        if self.github_token:
            headers["authorization"] = f"Bearer {self.github_token}"
        try:
            repos: list[dict[str, Any]] = []
            async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=False) as client:
                complete = False
                for page in range(1, MAX_PAGES + 1):
                    values, _ = await self._json(
                        client,
                        f"https://api.github.com/orgs/{ORG}/repos",
                        params={"type": "all", "per_page": 100, "page": page},
                        allowed_host="api.github.com",
                    )
                    if not isinstance(values, list):
                        raise RuntimeError("repository listing was not an array")
                    repos.extend(item for item in values if isinstance(item, dict))
                    if len(values) < 100:
                        complete = True
                        break
                if not complete:
                    raise RuntimeError("repository pagination exceeded bounded window")
                pr_data, _ = await self._json(
                    client,
                    "https://api.github.com/search/issues",
                    params={"q": f"org:{ORG} is:pr is:open", "per_page": 1},
                    allowed_host="api.github.com",
                )
            rows = [
                {
                    "name": str(item.get("name") or ""),
                    "archived": bool(item.get("archived")),
                    "visibility": str(item.get("visibility") or "unknown"),
                    "default_branch": str(item.get("default_branch") or ""),
                    "updated_at": str(item.get("updated_at") or ""),
                }
                for item in repos
            ]
            return Observation(
                "OBSERVED",
                {
                    "repository_count": len(rows),
                    "open_pull_request_count": int((pr_data or {}).get("total_count", 0)),
                    "pagination_complete": True,
                    "repositories": rows,
                },
                {"authenticated": bool(self.github_token)},
            )
        except Exception as exc:
            return Observation("UNAVAILABLE", detail=_safe_error(exc))

    def _hf_list(self, method_name: str, kwargs: Mapping[str, Any]) -> list[Any]:
        from huggingface_hub import HfApi

        api = HfApi(token=self.hf_token or None)
        method = getattr(api, method_name, None)
        if method is None:
            raise AttributeError(f"HfApi.{method_name} unavailable")
        return list(method(**dict(kwargs)))

    async def _hf_kernels(self) -> list[dict[str, Any]]:
        headers = {"accept": "application/json", "user-agent": "szl-series-a/1"}
        if self.hf_token:
            headers["authorization"] = f"Bearer {self.hf_token}"
        output: list[dict[str, Any]] = []
        url: str | None = "https://huggingface.co/api/kernels"
        params: Mapping[str, Any] | None = {"author": HF_ORG, "limit": 1000, "full": "true"}
        async with httpx.AsyncClient(headers=headers, timeout=30, follow_redirects=False) as client:
            for _ in range(MAX_PAGES):
                if not url:
                    return output
                values, response = await self._json(
                    client, url, params=params, allowed_host="huggingface.co"
                )
                if not isinstance(values, list):
                    raise RuntimeError("kernel listing was not an array")
                output.extend(item for item in values if isinstance(item, dict))
                link = response.links.get("next") or {}
                url = link.get("url") if isinstance(link, dict) else None
                params = None
                if not url:
                    return output
        raise RuntimeError("kernel pagination exceeded bounded window")

    async def huggingface(self) -> Observation:
        categories: dict[str, Any] = {}
        errors: dict[str, Any] = {}
        methods = {
            "models": ("list_models", {"author": HF_ORG}),
            "datasets": ("list_datasets", {"author": HF_ORG}),
            "spaces": ("list_spaces", {"author": HF_ORG}),
            "collections": ("list_collections", {"owner": HF_ORG}),
            "buckets": ("list_buckets", {"namespace": HF_ORG}),
        }
        for name, (method, kwargs) in methods.items():
            try:
                items = await asyncio.to_thread(self._hf_list, method, kwargs)
                rows = []
                for item in items:
                    item_id = None
                    for field in ("id", "repo_id", "name", "slug"):
                        candidate = item.get(field) if isinstance(item, dict) else getattr(item, field, None)
                        if isinstance(candidate, str) and candidate:
                            item_id = candidate
                            break
                    rows.append({"id": item_id})
                categories[name] = {"state": "OBSERVED", "count": len(rows), "items": rows}
            except Exception as exc:
                categories[name] = {"state": "UNAVAILABLE"}
                errors[name] = _safe_error(exc)
        try:
            kernels = await self._hf_kernels()
            categories["kernels"] = {
                "state": "OBSERVED",
                "count": len(kernels),
                "items": [{"id": str(item.get("id") or item.get("repo_id") or "")} for item in kernels],
            }
        except Exception as exc:
            categories["kernels"] = {"state": "UNAVAILABLE"}
            errors["kernels"] = _safe_error(exc)

        space_ids = {
            row.get("id")
            for row in categories.get("spaces", {}).get("items", [])
            if isinstance(row, dict)
        }
        clones_present = sorted(value for value in FORBIDDEN_CLONES if value in space_ids)
        canonical_present = CANONICAL_SPACE in space_ids
        state = "OBSERVED" if categories.get("spaces", {}).get("state") == "OBSERVED" else "PARTIAL"
        return Observation(
            state,
            {
                "categories": categories,
                "canonical_space": CANONICAL_SPACE,
                "canonical_present": canonical_present,
                "forbidden_clones_present": clones_present,
                "singleton_ok": canonical_present and not clones_present,
            },
            {"authenticated": bool(self.hf_token), "errors": errors},
        )

    async def collect(self) -> dict[str, Any]:
        github, hf = await asyncio.gather(self.github(), self.huggingface())
        critical_failures: list[str] = []
        if github.state != "OBSERVED":
            critical_failures.append("github_inventory_unavailable")
        if hf.state not in {"OBSERVED", "PARTIAL"}:
            critical_failures.append("huggingface_inventory_unavailable")
        hf_value = hf.value if isinstance(hf.value, dict) else {}
        if hf_value and not hf_value.get("singleton_ok"):
            critical_failures.append("canonical_a11oy_singleton_failed")
        categories = hf_value.get("categories", {}) if isinstance(hf_value, dict) else {}
        counts = {
            name: value.get("count") if isinstance(value, dict) and value.get("state") == "OBSERVED" else None
            for name, value in categories.items()
        }
        manifest = {
            "schema": SCHEMA_MANIFEST,
            "observed_at": _now(),
            "valid_until": _future(TTL_SECONDS),
            "source_revision": _git_revision(),
            "organization": ORG,
            "huggingface_organization": HF_ORG,
            "status": "BLOCKED" if critical_failures else "OBSERVED",
            "critical_failures": critical_failures,
            "github": github.as_dict(),
            "huggingface": hf.as_dict(),
            "counts": {
                "github_repositories": (
                    github.value.get("repository_count")
                    if isinstance(github.value, dict) and github.state == "OBSERVED"
                    else None
                ),
                "github_open_pull_requests": (
                    github.value.get("open_pull_request_count")
                    if isinstance(github.value, dict) and github.state == "OBSERVED"
                    else None
                ),
                **counts,
            },
            "claim": "CURRENT_OBSERVATION_NOT_ETERNAL_TRUTH",
            "counterfactual_label": "MODELED",
            "private_reasoning_collected": False,
        }
        manifest["manifest_digest"] = _sha(manifest)
        return manifest


class Service:
    def __init__(self, db_path: str | None = None) -> None:
        self.store = Store(db_path)
        self.signer = ReceiptSigner()
        self.collector = Collector()
        self.refresh_lock = asyncio.Lock()
        self.started = False
        self.background_task: asyncio.Task[Any] | None = None

    async def start(self) -> None:
        if self.started:
            return
        self.started = True
        if (os.environ.get("A11OY_SERIES_A_STARTUP_REFRESH") or "1").strip() == "0":
            self.store.append_event("estate.refresh.skipped", {"reason": "explicit test/runtime configuration"})
            return

        async def run() -> None:
            try:
                await self.refresh("startup")
            except Exception as exc:
                self.store.append_event("estate.refresh.failed", _safe_error(exc))

        self.background_task = asyncio.create_task(run(), name="a11oy-series-a-startup-refresh")

    async def refresh(self, actor: str) -> dict[str, Any]:
        if self.refresh_lock.locked():
            raise HTTPException(status_code=409, detail="estate refresh already running")
        async with self.refresh_lock:
            manifest = await self.collector.collect()
            envelope = self.signer.sign(manifest)
            digest = self.store.save_snapshot(manifest, envelope)
            receipt = self.store.append_receipt(
                "estate.refresh",
                {
                    "actor": actor,
                    "manifest_digest": digest,
                    "status": manifest["status"],
                    "counts": manifest["counts"],
                },
                self.signer,
            )
            return {"manifest": manifest, "envelope": envelope, "refresh_receipt": receipt}

    def latest_status(self) -> dict[str, Any]:
        latest = self.store.latest_snapshot()
        if latest is None:
            return {
                "schema": SCHEMA_STATUS,
                "state": "PENDING",
                "terminal": True,
                "source_revision": _git_revision(),
                "signing_key_source": self.signer.source,
                "database": self.store.path,
                "detail": "no completed refresh is persisted yet",
            }
        valid_until = datetime.fromisoformat(latest["valid_until"].replace("Z", "+00:00"))
        stale = datetime.now(timezone.utc) >= valid_until
        manifest = latest["manifest"]
        return {
            "schema": SCHEMA_STATUS,
            "state": "STALE" if stale else manifest["status"],
            "terminal": True,
            "source_revision": _git_revision(),
            "manifest_digest": latest["digest"],
            "observed_at": latest["observed_at"],
            "valid_until": latest["valid_until"],
            "counts": manifest.get("counts", {}),
            "critical_failures": manifest.get("critical_failures", []),
            "signature_status": latest["envelope"].get("signature_status"),
            "signing_key_source": self.signer.source,
            "database": self.store.path,
        }

    def evaluate_passport(self, body: Mapping[str, Any]) -> dict[str, Any]:
        action = body.get("action")
        if not isinstance(action, dict):
            raise HTTPException(status_code=422, detail="action must be an object")
        action_type = str(action.get("type") or "")
        target = str(action.get("target") or "")
        impact = str(action.get("impact") or "MODERATE").upper()
        irreversible = bool(action.get("irreversible", False))
        if action_type not in ALLOWED_ACTIONS:
            decision = "BLOCK"
            reasons = ["ACTION_TYPE_NOT_ALLOWLISTED"]
        elif not target:
            decision = "BLOCK"
            reasons = ["TARGET_REQUIRED"]
        elif action_type == "estate.refresh" and target != "szl://estate/current":
            decision = "BLOCK"
            reasons = ["TARGET_NOT_ALLOWLISTED"]
        elif action_type == "probe.public_surface":
            parsed_target = urlsplit(target)
            if (
                parsed_target.scheme != "https"
                or parsed_target.hostname not in ALLOWED_PROBE_HOSTS
                or parsed_target.username
                or parsed_target.password
            ):
                decision = "BLOCK"
                reasons = ["TARGET_NOT_ALLOWLISTED"]
            elif impact in {"HIGH", "CRITICAL"} or irreversible:
                decision = "REQUIRE_APPROVAL"
                reasons = ["INDEPENDENT_APPROVAL_REQUIRED"]
            else:
                decision = "ALLOW"
                reasons = ["BOUNDED_REVERSIBLE_ACTION"]
        elif impact in {"HIGH", "CRITICAL"} or irreversible:
            decision = "REQUIRE_APPROVAL"
            reasons = ["INDEPENDENT_APPROVAL_REQUIRED"]
        else:
            decision = "ALLOW"
            reasons = ["BOUNDED_REVERSIBLE_ACTION"]

        evidence = body.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            decision = "BLOCK"
            reasons = sorted(set(reasons + ["EVIDENCE_REQUIRED"]))
        else:
            for item in evidence:
                if not isinstance(item, dict) or item.get("label") in {"UNKNOWN", "UNAVAILABLE"}:
                    decision = "BLOCK"
                    reasons = sorted(set(reasons + ["NON_ACTIONABLE_EVIDENCE"]))
                    break

        no_action = {
            "scenario_id": "no-action",
            "kind": "NO_ACTION",
            "label": "MODELED",
            "outcome": str(body.get("expected_if_withheld") or "current state persists"),
        }
        proposed = {
            "scenario_id": "proposed-action",
            "kind": "PROPOSED_ACTION",
            "label": "MODELED",
            "outcome": str(body.get("expected_if_acted") or "bounded action completes or fails closed"),
        }
        passport = {
            "schema": SCHEMA_PASSPORT,
            "passport_id": f"cap_{uuid.uuid4().hex}",
            "created_at": _now(),
            "source_revision": _git_revision(),
            "subject": {
                "principal_id": str(body.get("principal_id") or "anonymous-proposer"),
                "workload_id": str(body.get("workload_id") or "a11oy-series-a"),
            },
            "action": action,
            "action_digest": _sha(action),
            "evidence": evidence if isinstance(evidence, list) else [],
            "counterfactuals": [no_action, proposed],
            "decision": decision,
            "reason_codes": reasons,
            "max_attempts": 1,
            "private_reasoning_collected": False,
        }
        digest = self.store.save_passport(passport)
        receipt = self.store.append_receipt(
            "passport.evaluate",
            {"passport_digest": digest, "decision": decision, "reason_codes": reasons},
            self.signer,
        )
        return {"passport": passport, "passport_digest": digest, "decision_receipt": receipt}

    async def execute(self, body: Mapping[str, Any]) -> dict[str, Any]:
        digest = str(body.get("passport_digest") or "")
        passport = self.store.load_passport(digest)
        if passport is None:
            raise HTTPException(status_code=404, detail="passport not found")
        if passport["attempts"] != 0:
            raise HTTPException(status_code=409, detail="passport attempt already consumed")
        if passport["decision"] != "ALLOW":
            raise HTTPException(status_code=403, detail=f"passport decision is {passport['decision']}")
        self.store.consume_attempt(digest)
        action = passport["action"]
        started = _now()
        try:
            if action["type"] == "estate.refresh":
                result = await self.refresh(passport["passport_id"])
                outcome = {
                    "status": "SUCCEEDED",
                    "manifest_digest": result["manifest"]["manifest_digest"],
                    "estate_status": result["manifest"]["status"],
                }
            elif action["type"] == "probe.public_surface":
                outcome = await self._probe(str(action["target"]))
            else:
                raise RuntimeError("action left allowlist after authorization")
        except Exception as exc:
            outcome = {"status": "FAILED", **_safe_error(exc)}
        outcome.update(
            {
                "started_at": started,
                "completed_at": _now(),
                "attempt": 1,
                "max_attempts": 1,
                "passport_digest": digest,
            }
        )
        receipt = self.store.append_receipt("passport.outcome", outcome, self.signer)
        return {"outcome": outcome, "outcome_receipt": receipt}

    async def _probe(self, target: str) -> dict[str, Any]:
        parsed = urlsplit(target)
        if parsed.scheme != "https" or parsed.hostname not in ALLOWED_PROBE_HOSTS or parsed.username or parsed.password:
            raise RuntimeError("probe target is not in the fixed HTTPS allowlist")
        start = time.monotonic()
        async with httpx.AsyncClient(timeout=15, follow_redirects=False) as client:
            response = await client.get(target, headers={"accept": "application/json,text/html;q=0.9"})
        final = urlsplit(str(response.url))
        if final.hostname not in ALLOWED_PROBE_HOSTS:
            raise RuntimeError("probe redirect left the allowlist")
        return {
            "status": "SUCCEEDED" if 200 <= response.status_code < 400 else "FAILED",
            "target": target,
            "http_status": response.status_code,
            "latency_ms": int((time.monotonic() - start) * 1000),
            "bytes": len(response.content),
            "content_type": response.headers.get("content-type", ""),
        }

    def trust_factor(self) -> dict[str, Any]:
        receipts = self.store.list_receipts(200)
        decisions = [
            item["receipt"]["payload"].get("decision")
            for item in receipts
            if item["kind"] == "passport.evaluate"
        ]
        counts = {name: decisions.count(name) for name in ("ALLOW", "BLOCK", "REQUIRE_APPROVAL")}
        total = sum(counts.values())
        penalty = counts["BLOCK"] * 10 + counts["REQUIRE_APPROVAL"] * 3
        score = 100 if total == 0 else max(0, 100 - (penalty * 100 // max(1, total * 10)))
        return {
            "schema": SCHEMA_TRUST,
            "state": "OBSERVED",
            "total_evaluations": total,
            "counts": counts,
            "score_0_to_100": score,
            "basis": "local signed passport decision receipts",
            "not_a_security_certification": True,
        }


async def _bounded_json(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "").split(";", 1)[0].lower()
    if content_type != "application/json":
        raise HTTPException(status_code=415, detail="content-type must be application/json")
    declared = request.headers.get("content-length")
    if declared:
        try:
            if int(declared) > MAX_BODY:
                raise HTTPException(status_code=413, detail="request exceeds 64 KiB")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="invalid content-length") from exc
    body = await request.body()
    if len(body) > MAX_BODY:
        raise HTTPException(status_code=413, detail="request exceeds 64 KiB")
    try:
        value = json.loads(body.decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail="request must be UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise HTTPException(status_code=422, detail="request must be one JSON object")
    return value


def _asset(name: str) -> str:
    path = Path(__file__).resolve().parent / "series_a_web" / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"asset missing: {name}")
    return path.read_text(encoding="utf-8")


def register(app: FastAPI, ns: str = "a11oy", *, db_path: str | None = None) -> dict[str, Any]:
    if any(getattr(route, "path", None) == f"/api/{ns}/v1/series-a/status" for route in app.router.routes):
        return {"ok": True, "state": "ALREADY_REGISTERED", "routes": []}

    service = Service(db_path)
    prefix = f"/api/{ns}/v1/series-a"

    async def page(request: Request) -> Response:
        if request.method == "HEAD":
            return Response(status_code=200, media_type="text/html")
        return HTMLResponse(_asset("index.html"), headers={"cache-control": "no-store"})

    async def js(request: Request) -> Response:
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/javascript")
        return Response(_asset("app.js"), media_type="application/javascript", headers={"cache-control": "public,max-age=300"})

    async def css(request: Request) -> Response:
        if request.method == "HEAD":
            return Response(status_code=200, media_type="text/css")
        return Response(_asset("styles.css"), media_type="text/css", headers={"cache-control": "public,max-age=300"})

    async def status(request: Request) -> Response:
        payload = service.latest_status()
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        return JSONResponse(payload, headers={"cache-control": "no-store"})

    async def manifest(request: Request) -> Response:
        latest = service.store.latest_snapshot()
        if latest is None:
            payload = {"schema": SCHEMA_MANIFEST, "status": "PENDING", "terminal": True}
        else:
            payload = latest
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        return JSONResponse(payload, headers={"cache-control": "no-store"})

    async def refresh(request: Request) -> Response:
        body = await _bounded_json(request)
        actor = str(body.get("actor") or "operator")[:120]
        return JSONResponse(await service.refresh(actor))

    async def evaluate(request: Request) -> Response:
        return JSONResponse(service.evaluate_passport(await _bounded_json(request)))

    async def execute(request: Request) -> Response:
        return JSONResponse(await service.execute(await _bounded_json(request)))

    async def receipts(request: Request) -> Response:
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        return JSONResponse({"schema": "szl.series-a-receipts/v1", "items": service.store.list_receipts(50)})

    async def trust(request: Request) -> Response:
        if request.method == "HEAD":
            return Response(status_code=200, media_type="application/json")
        return JSONResponse(service.trust_factor())

    async def public_key(request: Request) -> Response:
        if request.method == "HEAD":
            return Response(status_code=200, media_type="text/plain")
        if not service.signer.public_pem:
            return JSONResponse({"state": "UNAVAILABLE", "reason": service.signer.error}, status_code=503)
        return Response(service.signer.public_pem, media_type="text/plain", headers={"cache-control": "public,max-age=300"})

    async def events(request: Request) -> StreamingResponse:
        last = int(request.query_params.get("after", "0") or 0)

        async def generate() -> AsyncIterator[bytes]:
            cursor = max(0, last)
            for _ in range(120):
                values = service.store.events_since(cursor)
                for event in values:
                    cursor = event["sequence"]
                    yield f"id: {cursor}\nevent: {event['kind']}\ndata: {json.dumps(event, separators=(',', ':'))}\n\n".encode()
                if await request.is_disconnected():
                    break
                yield b": heartbeat\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(generate(), media_type="text/event-stream", headers={"cache-control": "no-store"})

    routes: list[tuple[str, Callable[..., Any], list[str]]] = [
        ("/series-a", page, ["GET", "HEAD"]),
        ("/series-a/app.js", js, ["GET", "HEAD"]),
        ("/series-a/styles.css", css, ["GET", "HEAD"]),
        (f"{prefix}/status", status, ["GET", "HEAD"]),
        (f"{prefix}/manifest", manifest, ["GET", "HEAD"]),
        (f"{prefix}/refresh", refresh, ["POST"]),
        (f"{prefix}/passports/evaluate", evaluate, ["POST"]),
        (f"{prefix}/passports/execute", execute, ["POST"]),
        (f"{prefix}/receipts", receipts, ["GET", "HEAD"]),
        (f"{prefix}/trust", trust, ["GET", "HEAD"]),
        (f"{prefix}/public-key", public_key, ["GET", "HEAD"]),
        (f"{prefix}/events", events, ["GET"]),
    ]
    added: list[str] = []
    for path, endpoint, methods in routes:
        app.add_api_route(path, endpoint, methods=methods, include_in_schema=False)
        added.append(path)

    route_set = set(added)
    selected = [route for route in app.router.routes if getattr(route, "path", None) in route_set]
    selected_ids = {id(route) for route in selected}
    app.router.routes[:] = selected + [route for route in app.router.routes if id(route) not in selected_ids]

    app.state.szl_series_a_service = service
    add_handler = getattr(app, "add_event_handler", None)
    if callable(add_handler):
        add_handler("startup", service.start)

    return {
        "ok": True,
        "state": "REGISTERED",
        "namespace": ns,
        "routes": sorted(added),
        "database": service.store.path,
        "signing_key_source": service.signer.source,
        "sign_on_read": False,
        "effectors": sorted(ALLOWED_ACTIONS),
        "max_attempts": 1,
        "private_reasoning_collected": False,
    }
