# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 - Doctrine v11
#
# szl_hf_bucket.py - ONE shared Hugging Face "bucket" client.
#
# Both flagships (a11oy, killinchu) treat a Hugging Face *Dataset* repo as a
# durable, append-only "bucket" they write to and read from. This is the single
# production-grade foundation the rest of the series stands on (live intel
# archive, verifiable corpus, read-back, guards) - NOT one-off commit scripts.
#
# Design (no bandaids):
#   * Append-only + idempotent: each record gets a content-addressed id; writing
#     the same content twice stores exactly one entry (dedup at queue time AND at
#     commit time, so it holds across processes).
#   * Real-time but rate-aware: appends land in a local on-disk queue instantly
#     (never blocks the app request path) and a debounced background flusher
#     batches them into one Hub commit; retry + exponential backoff on 429/5xx.
#   * Offline-tolerant: if HF is unreachable (or the token is unset) appends
#     still succeed locally and the module reports an honest `queued`/`unreachable`
#     status - it NEVER fabricates a successful commit. A later flush drains the
#     queue.
#   * Auth from env only (`HF_ORG_TOKEN`, fallback `HF_WRITE_TOKEN`); the token
#     is never logged and never written to disk.
#   * Pure standard library + huggingface_hub (lazy-imported). No third-party
#     deps (org policy forbids unvetted extras). Commits go through the Hub
#     commit API (sandbox git push to HF is blocked).
#
# Repo layout (bounded reads, append-only writes):
#   <prefix>/<YYYY-MM-DD>.ndjson   - one NDJSON shard per UTC day (append-only)
#   <prefix>/head.json            - chain-state {count,last_id,last_ts,shards,...}
#
# Public interface:
#   bucket = HFBucket(repo_id=..., source="a11oy")     # construction = no network
#   bucket.append(record)                              # -> status dict
#   bucket.append_many(records)                        # -> status dict
#   bucket.read_recent(n)                              # -> list[record]
#   bucket.read_all()                                  # -> list[record]
#   bucket.head()                                      # -> chain-state dict
#   bucket.flush_queue()                               # -> status dict (drains queue)
#   bucket.status()                                    # -> honest live/queued/unreachable
#
from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

SCHEMA = "szl.hf.bucket.record/v1"
DEFAULT_PREFIX = "data"
DEFAULT_FLUSH_INTERVAL = 5.0   # seconds: debounce window for the background flusher
DEFAULT_BATCH_SIZE = 64        # records before an eager flush is signalled
DEFAULT_MAX_RETRIES = 4        # per-flush retry attempts on transient 429/5xx
DEFAULT_BACKOFF_BASE = 1.0     # seconds: exponential backoff base
DEFAULT_MAX_BACKOFF = 60.0     # seconds: backoff ceiling


# --------------------------------------------------------------------------- #
# Errors / status
# --------------------------------------------------------------------------- #
class BucketError(Exception):
    """Internal transport error. Never propagates into the app request path."""


def _is_retryable(exc: Exception) -> bool:
    """True for transient HF failures (HTTP 429 / 5xx) worth retrying."""
    status = getattr(exc, "status_code", None)
    if status is None:
        resp = getattr(exc, "response", None)
        status = getattr(resp, "status_code", None)
    if isinstance(status, int):
        return status == 429 or 500 <= status <= 599
    # Connection/DNS/timeout style failures are "unreachable" - also retryable.
    return True


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _canonical_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sanitize(repo_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", repo_id)


# --------------------------------------------------------------------------- #
# Transport abstraction (so the self-test can inject a network-free fake)
# --------------------------------------------------------------------------- #
class Transport:
    """Minimal append-only transport contract over a HF Dataset repo."""

    def read_file(self, path: str) -> Optional[bytes]:
        raise NotImplementedError

    def list_files(self, prefix: str) -> List[str]:
        raise NotImplementedError

    def commit(self, operations: List[Tuple[str, bytes]], message: str) -> str:
        raise NotImplementedError


class _HFTransport(Transport):
    """Real transport backed by huggingface_hub (lazy-imported)."""

    def __init__(self, repo_id: str, token: Optional[str], repo_type: str = "dataset", revision: str = "main"):
        self._repo_id = repo_id
        self._token = token
        self._repo_type = repo_type
        self._revision = revision
        self._api = None

    def _hf(self):
        if self._api is None:
            try:
                from huggingface_hub import HfApi  # lazy: keeps import dependency-free
            except Exception as exc:  # pragma: no cover - import guard
                raise BucketError("huggingface_hub is not installed: %r" % (exc,))
            self._api = HfApi(token=self._token)
        return self._api

    def read_file(self, path: str) -> Optional[bytes]:
        api = self._hf()
        try:
            from huggingface_hub.utils import EntryNotFoundError
        except Exception:  # pragma: no cover
            EntryNotFoundError = tuple()  # type: ignore
        try:
            local = api.hf_hub_download(
                repo_id=self._repo_id, repo_type=self._repo_type,
                filename=path, revision=self._revision, token=self._token,
            )
        except Exception as exc:
            # "Not found" is a normal first-write condition, not an error.
            name = exc.__class__.__name__
            if isinstance(EntryNotFoundError, type) and isinstance(exc, EntryNotFoundError):
                return None
            if name in ("EntryNotFoundError", "RepositoryNotFoundError"):
                return None
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 404:
                return None
            raise BucketError("read_file(%s) failed: %r" % (path, exc)) from exc
        with open(local, "rb") as fh:
            return fh.read()

    def list_files(self, prefix: str) -> List[str]:
        api = self._hf()
        try:
            files = api.list_repo_files(repo_id=self._repo_id, repo_type=self._repo_type, revision=self._revision)
        except Exception as exc:
            name = exc.__class__.__name__
            if name == "RepositoryNotFoundError":
                return []
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status == 404:
                return []
            raise BucketError("list_files failed: %r" % (exc,)) from exc
        pref = prefix.rstrip("/") + "/"
        return sorted(f for f in files if f.startswith(pref))

    def commit(self, operations: List[Tuple[str, bytes]], message: str) -> str:
        api = self._hf()
        try:
            from huggingface_hub import CommitOperationAdd
        except Exception as exc:  # pragma: no cover
            raise BucketError("huggingface_hub is not installed: %r" % (exc,))
        ops = [CommitOperationAdd(path_in_repo=p, path_or_fileobj=b) for p, b in operations]
        try:
            info = api.create_commit(
                repo_id=self._repo_id, repo_type=self._repo_type, revision=self._revision,
                operations=ops, commit_message=message,
            )
        except Exception as exc:
            raise BucketError("commit failed: %r" % (exc,)) from exc
        return getattr(info, "oid", "") or ""


# --------------------------------------------------------------------------- #
# Token resolution (env only; never logged)
# --------------------------------------------------------------------------- #
def resolve_token(explicit: Optional[str] = None) -> Optional[str]:
    if explicit:
        return explicit
    for var in ("HF_ORG_TOKEN", "HF_WRITE_TOKEN", "HF_TOKEN"):
        val = os.environ.get(var)
        if val:
            return val
    return None


# --------------------------------------------------------------------------- #
# The bucket
# --------------------------------------------------------------------------- #
class HFBucket:
    """Durable, append-only Hugging Face Dataset 'bucket' client."""

    def __init__(
        self,
        repo_id: Optional[str] = None,
        source: str = "unknown",
        *,
        prefix: str = DEFAULT_PREFIX,
        token: Optional[str] = None,
        repo_type: str = "dataset",
        revision: str = "main",
        queue_dir: Optional[str] = None,
        transport: Optional[Transport] = None,
        flush_interval: float = DEFAULT_FLUSH_INTERVAL,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_base: float = DEFAULT_BACKOFF_BASE,
        max_backoff: float = DEFAULT_MAX_BACKOFF,
        clock: Callable[[], float] = time.time,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.repo_id = repo_id or os.environ.get("SZL_HF_BUCKET_REPO") or ""
        if not self.repo_id:
            raise ValueError("repo_id is required (pass repo_id=... or set SZL_HF_BUCKET_REPO)")
        self.source = source
        self.prefix = prefix.strip("/") or DEFAULT_PREFIX
        self.repo_type = repo_type
        self.revision = revision
        self.flush_interval = max(0.0, float(flush_interval))
        self.batch_size = max(1, int(batch_size))
        self.max_retries = max(1, int(max_retries))
        self.backoff_base = max(0.0, float(backoff_base))
        self.max_backoff = max(0.0, float(max_backoff))
        self._clock = clock
        self._sleep = sleep

        self._token = resolve_token(token)
        self._transport = transport or _HFTransport(self.repo_id, self._token, repo_type, revision)

        base = queue_dir or os.environ.get("SZL_HF_BUCKET_QUEUE_DIR") or os.path.join(
            tempfile.gettempdir(), "szl_hf_bucket_queue"
        )
        self.queue_dir = os.path.join(base, _sanitize(self.repo_id), self.prefix)
        os.makedirs(self.queue_dir, exist_ok=True)

        self._lock = threading.RLock()
        # ids known to be already committed (best-effort local cache for fast dedup).
        self._committed_ids: set = set()
        self._state = "queued" if self._pending_ids() else "idle"
        self._last_error: Optional[str] = None
        self._last_commit: Optional[str] = None
        self._last_flush_at: Optional[str] = None
        self._next_retry_at = 0.0
        self._backoff = self.backoff_base

        self._flusher: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._wake = threading.Event()

    # ----- record construction / dedup id ---------------------------------- #
    def make_record(self, payload: Any, *, kind: str = "event", source: Optional[str] = None,
                    dedup_key: Optional[Any] = None, ts: Optional[str] = None) -> Dict[str, Any]:
        """Wrap a payload into the append-only record contract with a stable,
        content-addressed id. The id is derived from {source,kind,dedup-content}
        and NOT from the timestamp, so re-submitting the same logical record
        (even later) dedups to a single stored entry."""
        if isinstance(payload, dict) and payload.get("schema") == SCHEMA and "id" in payload:
            # Already a bucket record - keep its id stable (idempotent re-wrap).
            return dict(payload)
        src = source or self.source
        basis = dedup_key if dedup_key is not None else payload
        rid = _sha256_hex(_canonical_bytes({"source": src, "kind": kind, "content": basis}))
        return {
            "schema": SCHEMA,
            "id": rid,
            "ts": ts or _utcnow_iso(),
            "source": src,
            "kind": kind,
            "payload": payload,
        }

    @staticmethod
    def record_id(record: Dict[str, Any]) -> str:
        return record["id"]

    # ----- queue plumbing -------------------------------------------------- #
    def _queue_path(self, rid: str) -> str:
        return os.path.join(self.queue_dir, rid + ".json")

    def _pending_ids(self) -> List[str]:
        try:
            return sorted(f[:-5] for f in os.listdir(self.queue_dir) if f.endswith(".json"))
        except FileNotFoundError:
            return []

    def _enqueue(self, record: Dict[str, Any]) -> bool:
        """Write a record to the local queue idempotently. Returns True if newly
        queued, False if it was a duplicate (already queued or already committed)."""
        rid = record["id"]
        if rid in self._committed_ids:
            return False
        path = self._queue_path(rid)
        if os.path.exists(path):
            return False
        tmp = path + ".tmp-%d" % os.getpid()
        with open(tmp, "wb") as fh:
            fh.write(_canonical_bytes(record))
        os.replace(tmp, path)  # atomic
        return True

    # ----- public append --------------------------------------------------- #
    def append(self, record: Any, **kwargs) -> Dict[str, Any]:
        return self.append_many([record], **kwargs)

    def append_many(self, records: Iterable[Any], *, kind: str = "event",
                    source: Optional[str] = None, auto_flush: bool = True) -> Dict[str, Any]:
        """Append one-or-many records. Never blocks on the network: records land
        in the local queue and the background flusher (or flush_queue) drains
        them to HF. Returns an honest status dict."""
        queued = 0
        duplicates = 0
        ids: List[str] = []
        with self._lock:
            for raw in records:
                rec = raw if (isinstance(raw, dict) and raw.get("schema") == SCHEMA and "id" in raw) \
                    else self.make_record(raw, kind=kind, source=source)
                ids.append(rec["id"])
                if self._enqueue(rec):
                    queued += 1
                else:
                    duplicates += 1
            if queued and self._state != "unreachable":
                self._state = "queued"
        if auto_flush:
            self._maybe_eager_flush()
        return {
            "ok": True,
            "queued": queued,
            "duplicates": duplicates,
            "ids": ids,
            "pending": len(self._pending_ids()),
            "state": self.state,
        }

    def _maybe_eager_flush(self) -> None:
        pending = len(self._pending_ids())
        if pending <= 0:
            return
        if self._flusher and self._flusher.is_alive():
            self._wake.set()  # nudge the debounced background flusher
            return
        if pending >= self.batch_size:
            # No background flusher running and we have a full batch: drain now,
            # but never raise into the caller.
            try:
                self.flush_queue()
            except Exception as exc:  # pragma: no cover - defensive
                self._record_failure(repr(exc))

    # ----- flush ----------------------------------------------------------- #
    def flush_queue(self, *, force: bool = False) -> Dict[str, Any]:
        """Drain the local queue to HF in a single batched commit. Honors
        backoff unless force=True. Never raises into the caller."""
        with self._lock:
            now = self._clock()
            if not force and now < self._next_retry_at:
                return self._status_locked(extra={"skipped": "backoff"})
            pending = self._pending_ids()
            if not pending:
                if self._state == "queued":
                    self._state = "idle"
                return self._status_locked()
            try:
                committed, deduped = self._commit_pending(pending)
                self._record_success(committed, deduped)
                return self._status_locked(extra={"committed": committed, "deduped": deduped})
            except BucketError as exc:
                self._record_failure(str(exc))
                return self._status_locked(extra={"error_kind": "transport"})
            except Exception as exc:  # pragma: no cover - defensive
                self._record_failure(repr(exc))
                return self._status_locked(extra={"error_kind": "unexpected"})

    def _commit_pending(self, pending: List[str]) -> Tuple[int, int]:
        """Read affected shards, append the new (non-duplicate) records, and
        write everything + head.json in ONE Hub commit. Retries transient
        failures with exponential backoff. Raises BucketError on give-up."""
        # Load queued records.
        records: List[Dict[str, Any]] = []
        for rid in pending:
            try:
                with open(self._queue_path(rid), "rb") as fh:
                    records.append(json.loads(fh.read().decode("utf-8")))
            except FileNotFoundError:
                continue
        if not records:
            return 0, 0

        # Group by destination shard (UTC day).
        by_shard: Dict[str, List[Dict[str, Any]]] = {}
        for rec in records:
            shard = self._shard_for(rec)
            by_shard.setdefault(shard, []).append(rec)

        operations: List[Tuple[str, bytes]] = []
        committed = 0
        deduped = 0
        total_count = 0
        last_id = None
        last_ts = None

        # Read current shards (with retry), append new records, dedup at commit time.
        for shard, recs in sorted(by_shard.items()):
            existing_bytes = self._with_retry(lambda s=shard: self._transport.read_file(s)) or b""
            existing_ids = set()
            lines: List[str] = []
            for line in existing_bytes.decode("utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                lines.append(line)
                try:
                    existing_ids.add(json.loads(line)["id"])
                except Exception:
                    pass
            for rec in recs:
                if rec["id"] in existing_ids:
                    deduped += 1
                    continue
                existing_ids.add(rec["id"])
                lines.append(json.dumps(rec, sort_keys=True, separators=(",", ":"), ensure_ascii=False))
                committed += 1
            payload = ("\n".join(lines) + "\n").encode("utf-8") if lines else b""
            operations.append((shard, payload))

        # Compute head/chain-state across ALL shards (bounded: count + tip).
        all_shards = self._list_shards_with_pending(set(by_shard))
        for shard in all_shards:
            if shard in by_shard:
                blob = operations_lookup(operations, shard)
            else:
                blob = self._with_retry(lambda s=shard: self._transport.read_file(s)) or b""
            for line in blob.decode("utf-8").splitlines():
                line = line.strip()
                if not line:
                    continue
                total_count += 1
                try:
                    obj = json.loads(line)
                    last_id, last_ts = obj.get("id"), obj.get("ts")
                except Exception:
                    pass

        head = {
            "schema": "szl.hf.bucket.head/v1",
            "repo_id": self.repo_id,
            "prefix": self.prefix,
            "count": total_count,
            "last_id": last_id,
            "last_ts": last_ts,
            "shards": all_shards,
            "updated_at": _utcnow_iso(),
        }
        operations.append((self._head_path(), _canonical_bytes(head) + b"\n"))

        if committed == 0:
            # Everything queued was already in its shard: just refresh head, drop
            # the queue files, and mark them committed. Still a real (tiny) commit
            # only if head changed; otherwise skip the network entirely.
            self._drop_queue(records)
            for rec in records:
                self._committed_ids.add(rec["id"])
            return 0, deduped

        msg = "bucket: append %d record(s) from %s [%s]" % (committed, self.source, self.prefix)
        oid = self._with_retry(lambda: self._transport.commit(operations, msg))
        self._last_commit = oid
        # Success: remove queued files, remember committed ids.
        self._drop_queue(records)
        for rec in records:
            self._committed_ids.add(rec["id"])
        return committed, deduped

    def _drop_queue(self, records: List[Dict[str, Any]]) -> None:
        for rec in records:
            try:
                os.remove(self._queue_path(rec["id"]))
            except FileNotFoundError:
                pass

    def _with_retry(self, fn: Callable[[], Any]) -> Any:
        last: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                return fn()
            except BucketError as exc:
                last = exc
                cause = exc.__cause__ or exc
                if not _is_retryable(cause) or attempt == self.max_retries - 1:
                    raise
            except Exception as exc:
                last = exc
                if not _is_retryable(exc) or attempt == self.max_retries - 1:
                    raise BucketError(repr(exc)) from exc
            delay = min(self.max_backoff, self.backoff_base * (2 ** attempt))
            if delay > 0:
                self._sleep(delay)
        if last:
            raise BucketError(repr(last)) from last
        return None

    # ----- shards / head --------------------------------------------------- #
    def _shard_for(self, record: Dict[str, Any]) -> str:
        ts = record.get("ts") or _utcnow_iso()
        day = ts[:10]  # YYYY-MM-DD
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", day):
            day = _utcnow_iso()[:10]
        return "%s/%s.ndjson" % (self.prefix, day)

    def _head_path(self) -> str:
        return "%s/head.json" % self.prefix

    def _list_shards(self) -> List[str]:
        files = self._transport.list_files(self.prefix)
        return sorted(f for f in files if f.endswith(".ndjson"))

    def _list_shards_with_pending(self, pending_shards: set) -> List[str]:
        try:
            live = set(self._list_shards())
        except BucketError:
            live = set()
        return sorted(live | set(pending_shards))

    # ----- reads ----------------------------------------------------------- #
    def read_recent(self, n: int = 50) -> List[Dict[str, Any]]:
        """Return up to the n most-recent records, newest shard first within the
        result ordered oldest->newest. Reads committed records from HF; if HF is
        unreachable it honestly falls back to whatever is locally queued."""
        n = max(0, int(n))
        if n == 0:
            return []
        out: List[Dict[str, Any]] = []
        try:
            shards = self._list_shards()
        except BucketError:
            shards = []
        for shard in reversed(shards):  # newest day first
            try:
                blob = self._transport.read_file(shard) or b""
            except BucketError:
                continue
            recs = _parse_ndjson(blob)
            out = recs + out
            if len(out) >= n:
                break
        if len(out) < n:
            out = self._queued_records() + out
        return out[-n:]

    def read_all(self) -> List[Dict[str, Any]]:
        """Return all committed records (oldest->newest) plus locally-queued ones."""
        out: List[Dict[str, Any]] = []
        seen: set = set()
        try:
            shards = self._list_shards()
        except BucketError:
            shards = []
        for shard in shards:
            try:
                blob = self._transport.read_file(shard) or b""
            except BucketError:
                continue
            for rec in _parse_ndjson(blob):
                if rec.get("id") in seen:
                    continue
                seen.add(rec.get("id"))
                out.append(rec)
        for rec in self._queued_records():
            if rec.get("id") in seen:
                continue
            seen.add(rec.get("id"))
            out.append(rec)
        return out

    def _queued_records(self) -> List[Dict[str, Any]]:
        recs: List[Dict[str, Any]] = []
        for rid in self._pending_ids():
            try:
                with open(self._queue_path(rid), "rb") as fh:
                    recs.append(json.loads(fh.read().decode("utf-8")))
            except (FileNotFoundError, ValueError):
                continue
        recs.sort(key=lambda r: r.get("ts") or "")
        return recs

    def head(self) -> Dict[str, Any]:
        """Return the chain-state. Prefers the committed head.json; falls back to
        a locally-computed view (with pending count) if HF is unreachable."""
        try:
            blob = self._transport.read_file(self._head_path())
            if blob:
                h = json.loads(blob.decode("utf-8"))
                h["pending"] = len(self._pending_ids())
                h["state"] = self.state
                return h
        except (BucketError, ValueError):
            pass
        return {
            "schema": "szl.hf.bucket.head/v1",
            "repo_id": self.repo_id,
            "prefix": self.prefix,
            "count": None,
            "last_id": None,
            "last_ts": None,
            "shards": [],
            "pending": len(self._pending_ids()),
            "state": self.state,
            "note": "head unavailable (HF unreachable or not yet written)",
        }

    # ----- status / background flusher ------------------------------------ #
    @property
    def state(self) -> str:
        return self._state

    def status(self) -> Dict[str, Any]:
        with self._lock:
            return self._status_locked()

    def _status_locked(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        st = {
            "repo_id": self.repo_id,
            "prefix": self.prefix,
            "source": self.source,
            "state": self._state,
            "pending": len(self._pending_ids()),
            "token_present": bool(self._token),
            "last_error": self._last_error,
            "last_commit": self._last_commit,
            "last_flush_at": self._last_flush_at,
        }
        if extra:
            st.update(extra)
        return st

    def _record_success(self, committed: int, deduped: int) -> None:
        self._last_flush_at = _utcnow_iso()
        self._last_error = None
        self._backoff = self.backoff_base
        self._next_retry_at = 0.0
        self._state = "idle" if not self._pending_ids() else "queued"

    def _record_failure(self, message: str) -> None:
        self._last_flush_at = _utcnow_iso()
        self._last_error = message
        self._state = "unreachable"
        self._backoff = min(self.max_backoff, max(self.backoff_base, self._backoff * 2 or self.backoff_base))
        self._next_retry_at = self._clock() + self._backoff

    def start(self) -> None:
        """Start the debounced background flusher thread (idempotent)."""
        with self._lock:
            if self._flusher and self._flusher.is_alive():
                return
            self._stop.clear()
            self._flusher = threading.Thread(target=self._run, name="szl-hf-bucket-flusher", daemon=True)
            self._flusher.start()

    def stop(self, *, drain: bool = True, timeout: float = 10.0) -> None:
        """Stop the background flusher. Optionally drain the queue first."""
        self._stop.set()
        self._wake.set()
        t = self._flusher
        if t and t.is_alive():
            t.join(timeout=timeout)
        self._flusher = None
        if drain:
            self.flush_queue(force=True)

    def _run(self) -> None:
        while not self._stop.is_set():
            self._wake.wait(timeout=self.flush_interval)
            self._wake.clear()
            if self._stop.is_set():
                break
            if self._pending_ids():
                self.flush_queue()

    def __enter__(self) -> "HFBucket":
        self.start()
        return self

    def __exit__(self, *exc) -> None:
        self.stop(drain=True)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _parse_ndjson(blob: bytes) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for line in blob.decode("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def operations_lookup(operations: List[Tuple[str, bytes]], path: str) -> bytes:
    for p, b in operations:
        if p == path:
            return b
    return b""


__all__ = ["HFBucket", "Transport", "BucketError", "resolve_token", "SCHEMA"]
