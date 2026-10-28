# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 — 749 declarations · 163 sorries · 14 unique axioms · 13-axis canonical trust
# Sign: Yachay <yachay@szlholdings.dev>
"""szl_kernels_organ — SELF-CONTAINED, vendorable kernel scaffold for a flagship Space.

This single file bundles the szl_kernels framework (Codex + Kernel + KernelManager +
circuit breaker + telemetry + lifecycle API) plus the 7 universal kernels and the 2 vertical
kernels for each chakra. Vendored per-flagship via one Dockerfile COPY line, then wired into
serve.py with the standard SZL convention:

    import szl_kernels_organ as _kernels
    _kernels.register(app, organ="rosie")   # mounts /api/rosie/v3/kernels/* + starts loops

The routes are intended for additive registration, but this module does not detect collisions;
the caller must reserve the organ prefix before registration. Signing uses the host Space's
szl_dsse if present, otherwise an honest PLACEHOLDER DSSE envelope (never silently unsigned).
State is SQLite-backed (SZL_CODEX_DIR, default /tmp/szl_codex) for process/container-local
durability. It survives a Space rebuild only when SZL_CODEX_DIR names a persistent mounted
directory.

The lifecycle, receipt, and local Codex hash-chain machinery are implemented here. Except for
ChainKernel's local hash-chain verification, the universal and vertical kernel actions are
scaffolding: this module does not connect them to the named application substrates. Unconnected
actions report ``did_work=false`` with an explicit UNAVAILABLE result until a real adapter is
wired and tested.

Heartbeat cadences are configured at 30 seconds for the universal SIGN/MEMORY/WIRE kernels.
When the loop is registered and running, freshness establishes scheduler/loop health only; it
does not establish that an unavailable substrate adapter performed external work.
"""
from __future__ import annotations

import asyncio
import base64
import calendar
import hashlib
import hmac
import json
import os
import re
import sqlite3
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

KHIPU_PAYLOAD_TYPE = "application/vnd.szl.khipu+json"
DOCTRINE = "v11"
SUBSTRATE_UNAVAILABLE_SUMMARY = "UNAVAILABLE: substrate adapter not connected"
WAKE_RECEIPT_MAX_BODY_BYTES = 1024
WAKE_RECEIPT_MAX_CLOCK_SKEW_SECONDS = 300
CODEX_MAX_PAGE_SIZE = 100
CODEX_MAX_OFFSET = 10_000
WAKE_RECEIPT_SOURCE = "github-actions/warm-flagships"
WAKE_RECEIPT_REPOSITORY = "szl-holdings/platform"
_WAKE_RECEIPT_KEYS = frozenset(
    {"source", "repository", "run", "run_attempt", "sha", "event", "ts"}
)
_WAKE_RECEIPT_EVENTS = frozenset({"schedule", "workflow_dispatch", "push"})
_WAKE_RECEIPT_RUN_RE = re.compile(r"[1-9][0-9]{0,19}")
_WAKE_RECEIPT_ATTEMPT_RE = re.compile(r"[1-9][0-9]{0,5}")
_WAKE_RECEIPT_SHA_RE = re.compile(r"[0-9a-f]{40}")
_WAKE_RECEIPT_TS_RE = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
)


class WakeReceiptRequestError(ValueError):
    """A bounded, caller-safe wake-receipt request failure."""

    def __init__(self, status_code: int, reason: str) -> None:
        super().__init__(reason)
        self.status_code = status_code
        self.reason = reason


def _configured_bearer_token(value: Optional[str]) -> Optional[str]:
    """Accept only a non-blank ASCII token whose encoding is 32 to 512 bytes.

    The function deliberately returns no detail about the rejected value and never logs it.
    """
    if (
        not isinstance(value, str)
        or value != value.strip()
        or not value.isascii()
        or any(character.isspace() for character in value)
    ):
        return None
    encoded = value.encode("utf-8")
    if len(encoded) < 32 or len(encoded) > 512:
        return None
    return value


def _presented_bearer_token(request: Any) -> Optional[str]:
    authorization = request.headers.get("authorization") or ""
    scheme, separator, token = authorization.partition(" ")
    if (
        not separator
        or scheme.lower() != "bearer"
        or not token
        or token != token.strip()
    ):
        return None
    if (
        any(character.isspace() for character in token)
        or len(token.encode("utf-8")) > 512
    ):
        return None
    return token


def _bearer_token_matches(presented: Optional[str], expected: Optional[str]) -> bool:
    # Hash both values so compare_digest always receives fixed-length inputs.
    candidate = hashlib.sha256((presented or "").encode("utf-8")).digest()
    reference = hashlib.sha256((expected or ("\0" * 32)).encode("utf-8")).digest()
    matches = hmac.compare_digest(candidate, reference)
    return expected is not None and matches


def _unix_time() -> float:
    return time.time()


def _reject_duplicate_json_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise WakeReceiptRequestError(400, "duplicate JSON key")
        result[key] = value
    return result


def _parse_wake_receipt(raw: bytes) -> dict[str, str]:
    if not raw:
        raise WakeReceiptRequestError(400, "request body is required")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise WakeReceiptRequestError(400, "request body must be UTF-8 JSON") from error
    try:
        body = json.loads(decoded, object_pairs_hook=_reject_duplicate_json_keys)
    except WakeReceiptRequestError:
        raise
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise WakeReceiptRequestError(400, "request body must be valid JSON") from error

    if not isinstance(body, dict):
        raise WakeReceiptRequestError(400, "request body must be a JSON object")
    if frozenset(body) != _WAKE_RECEIPT_KEYS:
        raise WakeReceiptRequestError(
            400, "request body does not match the wake-receipt schema"
        )
    if any(not isinstance(body[key], str) for key in _WAKE_RECEIPT_KEYS):
        raise WakeReceiptRequestError(400, "wake-receipt fields must be strings")
    if body["source"] != WAKE_RECEIPT_SOURCE:
        raise WakeReceiptRequestError(400, "wake-receipt source is not allowed")
    if body["repository"] != WAKE_RECEIPT_REPOSITORY:
        raise WakeReceiptRequestError(400, "wake-receipt repository is not allowed")
    if not _WAKE_RECEIPT_RUN_RE.fullmatch(body["run"]):
        raise WakeReceiptRequestError(400, "wake-receipt run is invalid")
    if not _WAKE_RECEIPT_ATTEMPT_RE.fullmatch(body["run_attempt"]):
        raise WakeReceiptRequestError(400, "wake-receipt run attempt is invalid")
    if not _WAKE_RECEIPT_SHA_RE.fullmatch(body["sha"]):
        raise WakeReceiptRequestError(400, "wake-receipt revision is invalid")
    if body["event"] not in _WAKE_RECEIPT_EVENTS:
        raise WakeReceiptRequestError(400, "wake-receipt event is not allowed")
    if not _WAKE_RECEIPT_TS_RE.fullmatch(body["ts"]):
        raise WakeReceiptRequestError(400, "wake-receipt timestamp is invalid")
    try:
        parsed_timestamp = time.strptime(body["ts"], "%Y-%m-%dT%H:%M:%SZ")
    except ValueError as error:
        raise WakeReceiptRequestError(400, "wake-receipt timestamp is invalid") from error
    reported_epoch = calendar.timegm(parsed_timestamp)
    if abs(_unix_time() - reported_epoch) > WAKE_RECEIPT_MAX_CLOCK_SKEW_SECONDS:
        raise WakeReceiptRequestError(
            400, "wake-receipt timestamp is outside the allowed clock skew"
        )
    return body


async def _read_wake_receipt(request: Any) -> dict[str, str]:
    content_type = (
        (request.headers.get("content-type") or "")
        .partition(";")[0]
        .strip()
        .lower()
    )
    if content_type != "application/json":
        raise WakeReceiptRequestError(415, "content type must be application/json")

    content_length = request.headers.get("content-length")
    if content_length is not None:
        if not re.fullmatch(r"[0-9]+", content_length):
            raise WakeReceiptRequestError(400, "content length is invalid")
        try:
            declared_length = int(content_length, 10)
        except ValueError as error:
            raise WakeReceiptRequestError(400, "content length is invalid") from error
        if declared_length < 0:
            raise WakeReceiptRequestError(400, "content length is invalid")
        if declared_length > WAKE_RECEIPT_MAX_BODY_BYTES:
            raise WakeReceiptRequestError(413, "request body is too large")

    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > WAKE_RECEIPT_MAX_BODY_BYTES:
            raise WakeReceiptRequestError(413, "request body is too large")
        raw.extend(chunk)
    return _parse_wake_receipt(bytes(raw))


# ────────────────────────── signing / hashing ──────────────────────────
def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_hex(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _placeholder_signer(payload_obj: Any, payload_type: str = KHIPU_PAYLOAD_TYPE) -> dict:
    body = canonical_json(payload_obj)
    return {
        "payloadType": payload_type,
        "payload": base64.b64encode(body).decode(),
        "signatures": [
            {"sig": "PLACEHOLDER", "keyid": "szl-kernels-unsigned",
             "note": "Sigstore CI signing not yet wired per Doctrine v11"}
        ],
    }


def _resolve_host_signer() -> Callable[[Any, str], dict]:
    """Prefer the host Space's szl_dsse.sign_payload; fall back to PLACEHOLDER."""
    try:
        import szl_dsse  # type: ignore
        if hasattr(szl_dsse, "sign_payload"):
            return szl_dsse.sign_payload  # type: ignore
    except Exception:
        pass
    return _placeholder_signer


# ────────────────────────── telemetry ──────────────────────────
_OTEL = None
try:
    from opentelemetry import trace as _otel_trace  # type: ignore
    _OTEL = _otel_trace.get_tracer("szl.kernels")
except Exception:
    _OTEL = None


@contextmanager
def _span(name: str, attributes: Optional[dict] = None):
    attributes = attributes or {}
    if _OTEL is not None:
        with _OTEL.start_as_current_span(name) as sp:  # type: ignore
            for k, v in attributes.items():
                try:
                    sp.set_attribute(k, v)
                except Exception:
                    pass
            yield sp
        return
    start = time.time()
    try:
        yield None
    finally:
        line = {"otel_span": name, "duration_ms": round((time.time() - start) * 1000, 2), **attributes}
        print("[szl.kernel.span] " + json.dumps(line, sort_keys=True), file=sys.stderr)


def _span_name(organ: str, kernel: str) -> str:
    return f"szl.kernel.{organ}.{kernel}.tick"


# ────────────────────────── Codex ──────────────────────────
@dataclass
class CodexEntry:
    id: str
    ts: str
    signed_payload: dict
    tags: list = field(default_factory=list)
    embedding: Optional[list] = None
    prev_hash: Optional[str] = None

    def to_dict(self) -> dict:
        return {"id": self.id, "ts": self.ts, "signed_payload": self.signed_payload,
                "tags": self.tags, "embedding": self.embedding, "prev_hash": self.prev_hash}


class WakeReceiptConflictError(ValueError):
    """The durable idempotency key was reused for a different request."""


class Codex:
    """Versioned, signed, replayable, hash-linked knowledge base (SQLite-backed)."""

    def __init__(self, slug: str, schema: Optional[dict] = None, version: str = "1.0.0",
                 signer: Optional[Callable] = None) -> None:
        self.slug = slug
        self.schema = schema or {"type": "object"}
        self.version = version
        self.signer = signer or _resolve_host_signer()
        base = Path(os.environ.get("SZL_CODEX_DIR", "/tmp/szl_codex")) / f"{slug}.db"
        base.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(base)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._write_lock = threading.RLock()
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS entries (seq INTEGER PRIMARY KEY AUTOINCREMENT, "
            "id TEXT, ts TEXT, signed_payload TEXT, tags TEXT, embedding TEXT, "
            "prev_hash TEXT, entry_hash TEXT)"
        )
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS wake_receipt_idempotency ("
            "repository TEXT NOT NULL, run TEXT NOT NULL, run_attempt TEXT NOT NULL, "
            "request_hash TEXT NOT NULL, entry_id TEXT NOT NULL, entry_hash TEXT NOT NULL, "
            "PRIMARY KEY (repository, run, run_attempt))"
        )
        self._conn.commit()

    def head_hash(self) -> Optional[str]:
        row = self._conn.execute("SELECT entry_hash FROM entries ORDER BY seq DESC LIMIT 1").fetchone()
        return row[0] if row else None

    def count(self) -> int:
        return self._conn.execute("SELECT COUNT(*) FROM entries").fetchone()[0]

    def append(self, payload: Any, tags: Optional[list] = None,
               embedding: Optional[list] = None, payload_type: str = KHIPU_PAYLOAD_TYPE) -> CodexEntry:
        with self._write_lock:
            cursor = self._conn.cursor()
            try:
                cursor.execute("BEGIN IMMEDIATE")
                row = cursor.execute(
                    "SELECT entry_hash FROM entries ORDER BY seq DESC LIMIT 1"
                ).fetchone()
                prev = row[0] if row else None
                signed = self.signer(payload, payload_type)
                entry = CodexEntry(
                    id="ce_" + uuid.uuid4().hex[:20],
                    ts=_now_iso(),
                    signed_payload=signed,
                    tags=tags or [],
                    embedding=embedding,
                    prev_hash=prev,
                )
                entry_hash = sha256_hex(canonical_json(entry.to_dict()))
                cursor.execute(
                    "INSERT INTO entries (id, ts, signed_payload, tags, embedding, "
                    "prev_hash, entry_hash) VALUES (?,?,?,?,?,?,?)",
                    (
                        entry.id,
                        entry.ts,
                        json.dumps(entry.signed_payload),
                        json.dumps(entry.tags),
                        json.dumps(entry.embedding),
                        entry.prev_hash or "",
                        entry_hash,
                    ),
                )
                self._conn.commit()
                return entry
            except BaseException:
                self._conn.rollback()
                raise
            finally:
                cursor.close()

    def append_wake_once(self, payload: dict[str, str]) -> dict[str, Any]:
        """Atomically append one canonical wake receipt or return its first result."""
        repository = payload["repository"]
        run = payload["run"]
        run_attempt = payload["run_attempt"]
        request_hash = sha256_hex(
            canonical_json(
                {
                    key: value
                    for key, value in payload.items()
                    if key not in {"received_at", "reported_at"}
                }
            )
        )
        with self._write_lock:
            cursor = self._conn.cursor()
            try:
                cursor.execute("BEGIN IMMEDIATE")
                existing = cursor.execute(
                    "SELECT request_hash, entry_id, entry_hash "
                    "FROM wake_receipt_idempotency "
                    "WHERE repository = ? AND run = ? AND run_attempt = ?",
                    (repository, run, run_attempt),
                ).fetchone()
                if existing:
                    if not hmac.compare_digest(existing[0], request_hash):
                        raise WakeReceiptConflictError(
                            "wake-receipt idempotency key conflicts with prior request"
                        )
                    self._conn.commit()
                    current = cursor.execute(
                        "SELECT entry_hash FROM entries ORDER BY seq DESC LIMIT 1"
                    ).fetchone()
                    return {
                        "entry_id": existing[1],
                        "entry_hash": existing[2],
                        "codex_head": current[0] if current else None,
                        "replay": True,
                    }

                row = cursor.execute(
                    "SELECT entry_hash FROM entries ORDER BY seq DESC LIMIT 1"
                ).fetchone()
                previous_hash = row[0] if row else None
                entry = CodexEntry(
                    id="ce_" + uuid.uuid4().hex[:20],
                    ts=_now_iso(),
                    signed_payload=self.signer(payload, KHIPU_PAYLOAD_TYPE),
                    tags=["wake", "warmer"],
                    prev_hash=previous_hash,
                )
                entry_hash = sha256_hex(canonical_json(entry.to_dict()))
                cursor.execute(
                    "INSERT INTO entries (id, ts, signed_payload, tags, embedding, "
                    "prev_hash, entry_hash) VALUES (?,?,?,?,?,?,?)",
                    (
                        entry.id,
                        entry.ts,
                        json.dumps(entry.signed_payload),
                        json.dumps(entry.tags),
                        json.dumps(entry.embedding),
                        entry.prev_hash or "",
                        entry_hash,
                    ),
                )
                cursor.execute(
                    "INSERT INTO wake_receipt_idempotency "
                    "(repository, run, run_attempt, request_hash, entry_id, entry_hash) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        repository,
                        run,
                        run_attempt,
                        request_hash,
                        entry.id,
                        entry_hash,
                    ),
                )
                self._conn.commit()
                return {
                    "entry_id": entry.id,
                    "entry_hash": entry_hash,
                    "codex_head": entry_hash,
                    "replay": False,
                }
            except BaseException:
                self._conn.rollback()
                raise
            finally:
                cursor.close()

    def read(self, limit: int = 20, offset: int = 0) -> list:
        rows = self._conn.execute(
            "SELECT id, ts, signed_payload, tags, embedding, prev_hash, entry_hash "
            "FROM entries ORDER BY seq DESC LIMIT ? OFFSET ?", (limit, offset)).fetchall()
        return [{"id": r[0], "ts": r[1], "signed_payload": json.loads(r[2]),
                 "tags": json.loads(r[3]), "embedding": json.loads(r[4]) if r[4] else None,
                 "prev_hash": r[5] or None, "entry_hash": r[6]} for r in rows]

    def verify_chain(self) -> dict:
        rows = self._conn.execute(
            "SELECT id, ts, signed_payload, tags, embedding, prev_hash, entry_hash "
            "FROM entries ORDER BY seq ASC").fetchall()
        prev_hash = None
        for i, r in enumerate(rows):
            entry = CodexEntry(id=r[0], ts=r[1], signed_payload=json.loads(r[2]),
                               tags=json.loads(r[3]), embedding=json.loads(r[4]) if r[4] else None,
                               prev_hash=r[5] or None)
            if (entry.prev_hash or None) != prev_hash:
                return {"ok": False, "checked": i, "break_at": i, "reason": "prev_hash mismatch"}
            if sha256_hex(canonical_json(entry.to_dict())) != r[6]:
                return {"ok": False, "checked": i, "break_at": i, "reason": "entry_hash mismatch"}
            prev_hash = r[6]
        return {"ok": True, "checked": len(rows), "break_at": None}

    def to_envelope(self) -> dict:
        return {"codex_id": self.slug, "version": self.version, "schema": self.schema,
                "entry_count": self.count(), "head_hash": self.head_hash()}


# ────────────────────────── circuit breaker ──────────────────────────
@dataclass
class CircuitBreaker:
    threshold: int = 3
    fail_streak: int = 0
    open: bool = False
    last_error: Optional[str] = None
    on_open: Optional[Callable[[str], None]] = None

    def record_success(self) -> None:
        self.fail_streak = 0

    def record_failure(self, error: str) -> bool:
        self.fail_streak += 1
        self.last_error = error
        if self.fail_streak >= self.threshold and not self.open:
            self.open = True
            if self.on_open:
                try:
                    self.on_open(error)
                except Exception:
                    pass
            return True
        return False

    def reset(self) -> None:
        self.fail_streak = 0
        self.open = False
        self.last_error = None


# ────────────────────────── Kernel ──────────────────────────
class Kernel:
    name: str = "base"
    kind: str = "universal"
    cadence_sec: int = 30
    codex_slug: Optional[str] = None

    def __init__(self, organ: str = "unknown") -> None:
        self.organ = organ
        slug = self.codex_slug or self.name
        self.codex = Codex(slug=f"{organ}-{slug}")
        self.status = "stopped"
        self.ticks_total = 0
        self.last_tick_ts: Optional[str] = None
        self.last_tick_monotonic = 0.0
        self.last_heartbeat: Optional[dict] = None
        self.breaker = CircuitBreaker(threshold=3, on_open=self._on_open)

    def _on_open(self, error: str) -> None:
        self.status = "suspended"

    async def observe(self) -> Any:
        return None

    async def decide(self, observations: Any) -> Any:
        return {"work": False}

    async def act(self, decision: Any) -> dict:
        return {"did_work": False, "summary": SUBSTRATE_UNAVAILABLE_SUMMARY}

    async def sign(self, action_result: dict) -> dict:
        self.ticks_total += 1
        self.last_tick_ts = _now_iso()
        receipt = {
            "kernel": f"{self.organ}.{self.name}", "tick": self.ticks_total,
            "ts": self.last_tick_ts, "alive": True,
            "did_work": bool(action_result.get("did_work")),
            "summary": action_result.get("summary", "alive"),
            "otel_span": _span_name(self.organ, self.name), "doctrine": DOCTRINE,
        }
        entry = self.codex.append(receipt, tags=["heartbeat", self.name])
        receipt["codex_head"] = self.codex.head_hash()
        receipt["signed_payload"] = entry.signed_payload
        self.last_heartbeat = receipt
        return receipt

    async def tick(self, force: bool = False) -> dict:
        now = time.monotonic()
        if not force and self.last_tick_monotonic and (now - self.last_tick_monotonic) < self.cadence_sec:
            return self.last_heartbeat or {"kernel": f"{self.organ}.{self.name}", "rate_limited": True}
        self.last_tick_monotonic = now
        with _span(_span_name(self.organ, self.name),
                   {"tick": self.ticks_total + 1, "fail_streak": self.breaker.fail_streak}):
            try:
                obs = await self.observe()
                decision = await self.decide(obs)
                result = await self.act(decision)
                receipt = await self.sign(result)
                self.breaker.record_success()
                return receipt
            except Exception as e:  # noqa: BLE001
                tripped = self.breaker.record_failure(repr(e))
                err = {"kernel": f"{self.organ}.{self.name}", "ts": _now_iso(), "alive": False,
                       "error": repr(e), "fail_streak": self.breaker.fail_streak,
                       "circuit_open": self.breaker.open}
                if tripped:
                    err["alert"] = (f"CIRCUIT OPEN: {self.organ}.{self.name} suspended after "
                                    f"{self.breaker.threshold} consecutive failures")
                self.last_heartbeat = err
                return err

    def detail(self) -> dict:
        last_ago = round(time.monotonic() - self.last_tick_monotonic, 1) if self.last_tick_monotonic else None
        return {"name": self.name, "kind": self.kind, "codex_id": self.codex.slug,
                "cadence_sec": self.cadence_sec, "status": self.status,
                "last_tick_ts": self.last_tick_ts, "last_heartbeat_ago_sec": last_ago,
                "ticks_total": self.ticks_total, "fail_streak": self.breaker.fail_streak,
                "circuit_open": self.breaker.open}


# ────────────────────────── KernelManager ──────────────────────────
class KernelManager:
    def __init__(self, organ: str, kernels: list) -> None:
        self.organ = organ
        self.kernels: dict = {k.name: k for k in kernels}
        self._tasks: dict = {}

    async def _run(self, k: Kernel) -> None:
        k.status = "running"
        while k.status == "running":
            await k.tick(force=True)
            if k.breaker.open:
                k.status = "suspended"
                break
            await asyncio.sleep(k.cadence_sec)

    def start_all(self) -> None:
        loop = asyncio.get_event_loop()
        for name, k in self.kernels.items():
            if name not in self._tasks or self._tasks[name].done():
                self._tasks[name] = loop.create_task(self._run(k))

    def start(self, name: str) -> bool:
        k = self.kernels.get(name)
        if not k:
            return False
        k.breaker.reset()
        if name not in self._tasks or self._tasks[name].done():
            self._tasks[name] = asyncio.get_event_loop().create_task(self._run(k))
        return True

    def stop(self, name: str) -> bool:
        k = self.kernels.get(name)
        if not k:
            return False
        k.status = "stopped"
        t = self._tasks.get(name)
        if t and not t.done():
            t.cancel()
        return True

    async def tick(self, name: str) -> Optional[dict]:
        k = self.kernels.get(name)
        if not k:
            return None
        return await k.tick(force=True)

    def list(self) -> dict:
        return {"organ": self.organ, "doctrine": DOCTRINE, "kernel_count": len(self.kernels),
                "kernels": [k.detail() for k in self.kernels.values()]}

    def get(self, name: str):
        return self.kernels.get(name)


# ────────────────────────── universal kernels ──────────────────────────
class SignKernel(Kernel):
    name = "sign"; kind = "universal"; cadence_sec = 30; codex_slug = "receipt-log"


class GateKernel(Kernel):
    name = "gate"; kind = "universal"; cadence_sec = 60; codex_slug = "gate-decisions"


class ChainKernel(Kernel):
    name = "chain"; kind = "universal"; cadence_sec = 300; codex_slug = "khipu-dag"
    async def act(self, d):
        v = self.codex.verify_chain()
        return {
            "did_work": True,
            "summary": (
                f"local Codex hash-chain verification ok={v['ok']} "
                f"checked={v['checked']}"
            ),
        }


class MemoryKernel(Kernel):
    name = "memory"; kind = "universal"; cadence_sec = 30; codex_slug = "unay"


class ReplayKernel(Kernel):
    name = "replay"; kind = "universal"; cadence_sec = 300; codex_slug = "ayni-event-log"


class McpKernel(Kernel):
    name = "mcp"; kind = "universal"; cadence_sec = 60; codex_slug = "hatun-mcp-registry"


class WireKernel(Kernel):
    name = "wire"; kind = "universal"; cadence_sec = 30; codex_slug = "traceparent-log"


UNIVERSAL = [SignKernel, GateKernel, ChainKernel, MemoryKernel, ReplayKernel, McpKernel, WireKernel]


# ────────────────────────── vertical kernels per chakra ──────────────────────────
def _vertical(name_, slug_, cadence=60):
    class _V(Kernel):
        name = name_; kind = "vertical"; cadence_sec = cadence; codex_slug = slug_
    _V.__name__ = f"Vertical_{name_}"
    return _V


VERTICALS: dict[str, list] = {
    "a11oy": [
        _vertical("route", "llm-router"),
        _vertical("orchestrate", "puriq-host-plan"),
    ],
    "killinchu": [
        _vertical("geofence", "geofence-events"),
        _vertical("mission-plan", "mission-plan"),
    ],
    "rosie": [
        _vertical("aide", "aide-actions"),
        _vertical("recall-personal", "personal-recall"),
    ],
    "sentra": [
        _vertical("filter", "filter-decisions"),
        _vertical("threat-score", "threat-score"),
    ],
    "amaru": [
        _vertical("cortex-ledger", "cortex-ledger"),
        _vertical("axis-track", "yuyay-13-axes"),
    ],
}


def build_kernels(organ: str) -> list:
    """Instantiate the 7 universal + 2 vertical kernels for `organ` (9 total)."""
    verticals = VERTICALS.get(organ, [])
    classes = list(UNIVERSAL) + list(verticals)
    return [cls(organ=organ) for cls in classes]


# ────────────────────────── lifecycle API + register ──────────────────────────
_MANAGERS: dict[str, KernelManager] = {}


def register(
    app,
    organ: str,
    admin_token: Optional[str] = None,
    wake_receipt_token: Optional[str] = None,
) -> KernelManager:
    """Build the canonical kernels, mount /api/<organ>/v3/kernels/*, and start
    background loops. The caller must ensure that route prefix is unused.
    Returns the KernelManager.

    Call from serve.py:  import szl_kernels_organ as _k; _k.register(app, organ="rosie")
    """
    from fastapi.responses import JSONResponse, StreamingResponse
    from starlette.requests import Request

    mgr = KernelManager(organ=organ, kernels=build_kernels(organ))
    _MANAGERS[organ] = mgr
    admin_token = _configured_bearer_token(
        admin_token if admin_token is not None else os.environ.get("SZL_ADMIN_TOKEN")
    )
    wake_receipt_token = _configured_bearer_token(
        wake_receipt_token
        if wake_receipt_token is not None
        else os.environ.get("SZL_WAKE_RECEIPT_TOKEN")
    )
    if (
        admin_token is not None
        and wake_receipt_token is not None
        and hmac.compare_digest(
            admin_token.encode("ascii"), wake_receipt_token.encode("ascii")
        )
    ):
        # The two capabilities must not collapse to one bearer credential. Make
        # both mutation surfaces unavailable rather than silently sharing power.
        admin_token = None
        wake_receipt_token = None
    base = f"/api/{organ}/v3/kernels"

    def _admin_authentication_error(request):
        if admin_token is None:
            return JSONResponse(
                {"error": "admin authentication is unavailable"}, status_code=503
            )
        if not _bearer_token_matches(_presented_bearer_token(request), admin_token):
            return JSONResponse(
                {"error": "invalid or missing admin bearer token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        return None

    @app.get(base)
    async def _list():
        return JSONResponse(mgr.list())

    @app.get(base + "/feed")
    async def _feed():
        async def gen():
            while True:
                for k in mgr.kernels.values():
                    yield f"data: {json.dumps(k.last_heartbeat or k.detail())}\n\n"
                await asyncio.sleep(2)
        return StreamingResponse(gen(), media_type="text/event-stream")

    @app.post(base + "/wake-receipt")
    async def _wake(request: Request):
        # Used only by the authenticated warm-flagships workflow to leave a bounded wake trail.
        if wake_receipt_token is None:
            return JSONResponse(
                {"ok": False, "reason": "wake receipt authentication is unavailable"},
                status_code=503,
            )
        if not _bearer_token_matches(
            _presented_bearer_token(request), wake_receipt_token
        ):
            return JSONResponse(
                {"ok": False, "reason": "invalid or missing bearer token"},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )
        try:
            body = await _read_wake_receipt(request)
        except WakeReceiptRequestError as error:
            return JSONResponse(
                {"ok": False, "reason": error.reason}, status_code=error.status_code
            )
        k = mgr.get("sign")
        if k:
            try:
                result = k.codex.append_wake_once(
                    {
                        "schema": "szl.wake-receipt.v1",
                        "event": "wake",
                        "source": body["source"],
                        "repository": body["repository"],
                        "run": body["run"],
                        "run_attempt": body["run_attempt"],
                        "revision": body["sha"],
                        "trigger": body["event"],
                        "reported_at": body["ts"],
                        "received_at": _now_iso(),
                    }
                )
            except WakeReceiptConflictError:
                return JSONResponse(
                    {
                        "ok": False,
                        "reason": "wake-receipt idempotency key conflicts with prior request",
                    },
                    status_code=409,
                )
            return JSONResponse(
                {
                    "ok": True,
                    "codex_head": result["codex_head"],
                    "entry_id": result["entry_id"],
                    "entry_hash": result["entry_hash"],
                    "replay": result["replay"],
                }
            )
        return JSONResponse({"ok": False, "reason": "sign kernel unavailable"}, status_code=503)

    @app.get(base + "/{name}")
    async def _detail(name: str):
        k = mgr.get(name)
        if not k:
            return JSONResponse({"error": "no such kernel", "name": name}, status_code=404)
        return JSONResponse(k.detail())

    @app.get(base + "/{name}/codex")
    async def _codex(name: str, limit: int = 20, offset: int = 0):
        k = mgr.get(name)
        if not k:
            return JSONResponse({"error": "no such kernel", "name": name}, status_code=404)
        if limit < 1 or limit > CODEX_MAX_PAGE_SIZE:
            return JSONResponse(
                {
                    "error": (
                        f"limit must be between 1 and {CODEX_MAX_PAGE_SIZE}"
                    )
                },
                status_code=400,
            )
        if offset < 0 or offset > CODEX_MAX_OFFSET:
            return JSONResponse(
                {"error": f"offset must be between 0 and {CODEX_MAX_OFFSET}"},
                status_code=400,
            )
        return JSONResponse({**k.codex.to_envelope(), "entries": k.codex.read(limit=limit, offset=offset)})

    @app.get(base + "/{name}/heartbeat")
    async def _hb(name: str):
        k = mgr.get(name)
        if not k:
            return JSONResponse({"error": "no such kernel", "name": name}, status_code=404)
        return JSONResponse(k.last_heartbeat or {"kernel": f"{organ}.{name}", "alive": False, "note": "no tick yet"})

    @app.post(base + "/{name}/tick")
    async def _tick(request: Request, name: str):
        authentication_error = _admin_authentication_error(request)
        if authentication_error is not None:
            return authentication_error
        r = await mgr.tick(name)
        if r is None:
            return JSONResponse({"error": "no such kernel", "name": name}, status_code=404)
        return JSONResponse(r)

    @app.post(base + "/{name}/start")
    async def _start(request: Request, name: str):
        authentication_error = _admin_authentication_error(request)
        if authentication_error is not None:
            return authentication_error
        ok = mgr.start(name)
        return JSONResponse({"started": ok, "name": name}, status_code=200 if ok else 404)

    @app.post(base + "/{name}/stop")
    async def _stop(request: Request, name: str):
        authentication_error = _admin_authentication_error(request)
        if authentication_error is not None:
            return authentication_error
        ok = mgr.stop(name)
        return JSONResponse({"stopped": ok, "name": name}, status_code=200 if ok else 404)

    # Start all 9 loops on the running event loop. If no loop yet (import-time), defer to
    # FastAPI startup so the kernels begin emitting heartbeats as soon as the app boots.
    @app.on_event("startup")
    async def _boot_kernels():
        mgr.start_all()
        print(f"[{organ}] szl_kernels_organ: started {len(mgr.kernels)} living kernels "
              f"(7 universal + 2 vertical) — Doctrine {DOCTRINE}", file=sys.stderr)

    return mgr
