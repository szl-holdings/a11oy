"""
szl_lake_store.py — Unified Receipt Ledger durable store
Doctrine v11 LOCKED 749/14/163 | kernel c7c0ba17 | Λ = Conjecture 1 (OPEN)

The one durable store every SZL component appends governance receipts to.

Root cause this fixes: each organ (ouroboros, hatun-mcp, szl-router, szl-mesh,
vsp-otel, szl-trust, a11oy …) previously held receipts in an in-process silo
that never converged. This module is a real, restart-durable, append-only
ledger — NOT an in-memory map that resets.

Storage format (stdlib-only, no parquet/pyarrow dependency):
  NDJSON, one signed-receipt envelope per line, partitioned on disk by
      <root>/<organ>/<YYYY-MM-DD>.ndjson
  append-only — exactly the shape the szl-lake README documents as canonical
  for khipu/ receipt streams.

Khipu hash-chain (F4 / F22 — Khipu = Conjecture 2, ADVISORY BFT, NOT a proven
theorem): per organ, each stored envelope links prev_hash -> chain_hash where

    chain_hash = SHA3-256( canonical_json({
        "prev_hash":   <prev chain_hash or null>,
        "receipt_id":  <this receipt's identity>,
        "organ":       <organ>,
        "ts":          <receipt timestamp>,
        "chain_index": <1-based position in this organ's chain>,
    }) )

so the per-organ chain head is a single value any other component can fetch and
compare for cross-component verification. SHA3-256 is the locked Khipu hash.

Honest labels only: if a receipt carries no measured energy (e.g. NVML/joules
absent) the envelope stores energy as {"label": "UNAVAILABLE"} — joules are
NEVER fabricated.

stdlib-only. Apache-2.0 — SZL Holdings 2026.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import threading
from datetime import datetime, timezone
from typing import Any, Iterable

# Khipu locked hash: SHA3-256 (advisory BFT chain — Conjecture 2, not proven).
CHAIN_HASH = "sha3_256"
SCHEMA = "szl.lake.receipt/v1"
# Filesystem-safe organ name: lowercase alnum, dash, underscore, dot. Anything
# else is rejected (prevents path traversal — organ becomes a directory name).
_ORGAN_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")

DEFAULT_ROOT = os.environ.get("SZL_LAKE_DIR", "khipu")


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonical_json(obj: Any) -> bytes:
    """Compact, sorted-key JSON bytes — the canonical form for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def _sha3_256(b: bytes) -> str:
    return hashlib.sha3_256(b).hexdigest()


def canonical_hash(obj: Any) -> str:
    """SHA3-256 over canonical JSON of obj."""
    return _sha3_256(canonical_json(obj))


def normalize_organ(organ: Any) -> str:
    """Lowercase + validate an organ label for safe use as a directory name."""
    if not isinstance(organ, str):
        raise ValueError(f"organ must be a string, got {type(organ).__name__}")
    name = organ.strip().lower()
    if not _ORGAN_RE.match(name):
        raise ValueError(
            f"invalid organ name {organ!r}: must match {_ORGAN_RE.pattern}")
    return name


def receipt_identity(receipt: dict) -> str:
    """Stable dedupe identity for a receipt.

    Prefers the receipt's own id/hash (the DSSE receipt shape uses 'id' or
    'hash'); falls back to a content hash so an id-less receipt is still
    deduplicated by content rather than silently duplicated.
    """
    for key in ("id", "hash", "receipt_id"):
        val = receipt.get(key)
        if isinstance(val, str) and val:
            return val
    return canonical_hash(receipt)


def normalize_energy(receipt: dict) -> Any:
    """Honest energy label. Never fabricate joules.

    Returns the receipt's energy as-is when it carries a real measurement;
    otherwise {"label": "UNAVAILABLE"} (NVML/joules absent).
    """
    energy = receipt.get("energy", None)
    if energy is None:
        return {"label": "UNAVAILABLE"}
    if isinstance(energy, (int, float)):
        return {"label": "MEASURED", "joules": energy}
    if isinstance(energy, dict):
        # Already labelled? trust an explicit honest label; otherwise, if it
        # carries a numeric joules reading, mark MEASURED, else UNAVAILABLE.
        if energy.get("label"):
            return energy
        joules = energy.get("joules")
        if isinstance(joules, (int, float)):
            return {"label": "MEASURED", "joules": joules}
        return {"label": "UNAVAILABLE"}
    return {"label": "UNAVAILABLE"}


def _receipt_ts(receipt: dict) -> str:
    """Best-effort receipt timestamp (ISO string). Falls back to ingest time."""
    for key in ("ts", "timestamp", "time", "created_at"):
        val = receipt.get(key)
        if isinstance(val, str) and val:
            return val
        if isinstance(val, (int, float)):
            # epoch seconds
            return datetime.fromtimestamp(val, timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.%fZ")
    return _now_iso()


def _partition_date(ts: str) -> str:
    """YYYY-MM-DD partition key derived from an ISO timestamp (UTC)."""
    try:
        cleaned = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(cleaned)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d")
    except (ValueError, TypeError):
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")


class _OrganState:
    """In-memory mirror of one organ's on-disk chain (rebuilt from disk)."""

    __slots__ = ("seen", "chain_index", "chain_head", "count")

    def __init__(self) -> None:
        self.seen: set[str] = set()
        self.chain_index: int = 0
        self.chain_head: str | None = None
        self.count: int = 0


class ReceiptLedger:
    """Durable, append-only, hash-chained receipt ledger.

    Thread-safe. Survives process restarts because all state is reconstructed
    from the on-disk NDJSON partitions — there is no authoritative in-memory
    map that could reset.
    """

    def __init__(self, root: str | None = None) -> None:
        self.root = os.path.abspath(root or DEFAULT_ROOT)
        self._lock = threading.RLock()
        self._states: dict[str, _OrganState] = {}

    # ---- paths ----------------------------------------------------------
    def _organ_dir(self, organ: str) -> str:
        return os.path.join(self.root, organ)

    def _partition_path(self, organ: str, date: str) -> str:
        return os.path.join(self._organ_dir(organ), f"{date}.ndjson")

    def _iter_partition_files(self, organ: str) -> list[str]:
        d = self._organ_dir(organ)
        if not os.path.isdir(d):
            return []
        files = [os.path.join(d, f) for f in os.listdir(d)
                 if f.endswith(".ndjson")]
        # date-named files sort chronologically as strings
        return sorted(files)

    def _list_organs(self) -> list[str]:
        if not os.path.isdir(self.root):
            return []
        return sorted(
            name for name in os.listdir(self.root)
            if os.path.isdir(os.path.join(self.root, name))
            and _ORGAN_RE.match(name)
        )

    # ---- state rebuild --------------------------------------------------
    def _rebuild_state(self, organ: str) -> _OrganState:
        """Reconstruct an organ's chain state by replaying its partitions."""
        st = _OrganState()
        for path in self._iter_partition_files(organ):
            with open(path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        env = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rid = env.get("receipt_id")
                    if rid:
                        st.seen.add(rid)
                    ci = env.get("chain_index")
                    if isinstance(ci, int) and ci > st.chain_index:
                        st.chain_index = ci
                    ch = env.get("chain_hash")
                    if ch:
                        st.chain_head = ch
                    st.count += 1
        return st

    def _state(self, organ: str) -> _OrganState:
        st = self._states.get(organ)
        if st is None:
            st = self._rebuild_state(organ)
            self._states[organ] = st
        return st

    # ---- write ----------------------------------------------------------
    def append(self, receipt: dict) -> dict:
        """Append a single receipt. Idempotent on its id/hash.

        Returns {accepted, duplicate, receipt_id, ledger_offset, chain_index,
        chain_head, organ}.
        """
        if not isinstance(receipt, dict):
            raise ValueError("receipt must be a JSON object")
        organ = normalize_organ(receipt.get("organ", "unknown"))
        rid = receipt_identity(receipt)
        ts = _receipt_ts(receipt)

        with self._lock:
            st = self._state(organ)

            if rid in st.seen:
                return {
                    "accepted": False,
                    "duplicate": True,
                    "receipt_id": rid,
                    "organ": organ,
                    "ledger_offset": st.count,
                    "chain_index": st.chain_index,
                    "chain_head": st.chain_head,
                }

            chain_index = st.chain_index + 1
            prev_hash = st.chain_head
            chain_hash = canonical_hash({
                "prev_hash": prev_hash,
                "receipt_id": rid,
                "organ": organ,
                "ts": ts,
                "chain_index": chain_index,
            })

            envelope = {
                "schema": SCHEMA,
                "chain_alg": CHAIN_HASH,
                "organ": organ,
                "receipt_id": rid,
                "prev_hash": prev_hash,
                "chain_hash": chain_hash,
                "chain_index": chain_index,
                "ts": ts,
                "ingested_at": _now_iso(),
                "energy": normalize_energy(receipt),
                "receipt": receipt,
            }

            date = _partition_date(ts)
            path = self._partition_path(organ, date)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(envelope, sort_keys=True,
                                    separators=(",", ":")) + "\n")
                fh.flush()
                os.fsync(fh.fileno())

            st.seen.add(rid)
            st.chain_index = chain_index
            st.chain_head = chain_hash
            st.count += 1

            return {
                "accepted": True,
                "duplicate": False,
                "receipt_id": rid,
                "organ": organ,
                "ledger_offset": st.count,
                "chain_index": chain_index,
                "chain_head": chain_hash,
            }

    def append_batch(self, receipts: Iterable[dict]) -> dict:
        """Append many receipts (e.g. NDJSON batch). Per-receipt idempotent."""
        results = []
        accepted = duplicates = 0
        with self._lock:
            for rec in receipts:
                r = self.append(rec)
                results.append(r)
                if r["accepted"]:
                    accepted += 1
                elif r["duplicate"]:
                    duplicates += 1
        return {
            "accepted": accepted,
            "duplicates": duplicates,
            "total": len(results),
            "results": results,
        }

    # ---- read -----------------------------------------------------------
    def query(self, organ: str | None = None, since: str | None = None,
              limit: int = 100) -> list[dict]:
        """Return stored envelopes, newest-first, filtered by organ/since.

        since: ISO timestamp; only receipts with ts >= since are returned.
        """
        limit = max(0, int(limit))
        organs = [normalize_organ(organ)] if organ else self._list_organs()

        since_dt = _parse_dt(since) if since else None
        out: list[dict] = []
        with self._lock:
            for org in organs:
                for path in self._iter_partition_files(org):
                    with open(path, "r", encoding="utf-8") as fh:
                        for line in fh:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                env = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if since_dt is not None:
                                env_dt = _parse_dt(env.get("ts"))
                                if env_dt is not None and env_dt < since_dt:
                                    continue
                            out.append(env)
        # newest-first by ingest order: sort by (ts, chain_index)
        out.sort(key=lambda e: (str(e.get("ts")), e.get("chain_index") or 0),
                 reverse=True)
        if limit:
            return out[:limit]
        return out

    def chain_head(self, organ: str) -> dict:
        """Current hash-chain head + count for one organ."""
        org = normalize_organ(organ)
        with self._lock:
            st = self._state(org)
            return {
                "organ": org,
                "chain_alg": CHAIN_HASH,
                "chain_head": st.chain_head,
                "chain_index": st.chain_index,
                "count": st.count,
            }

    def health(self) -> dict:
        """Store reachability, total receipts, and per-organ counts."""
        with self._lock:
            per_organ = {}
            total = 0
            for org in self._list_organs():
                st = self._state(org)
                per_organ[org] = {
                    "count": st.count,
                    "chain_index": st.chain_index,
                    "chain_head": st.chain_head,
                }
                total += st.count
            return {
                "ok": os.path.isdir(self.root) or not per_organ,
                "store": self.root,
                "chain_alg": CHAIN_HASH,
                "schema": SCHEMA,
                "total_receipts": total,
                "organs": per_organ,
            }

    def reload(self) -> None:
        """Drop cached state so the next read replays from disk."""
        with self._lock:
            self._states.clear()


def _parse_dt(ts: Any) -> datetime | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except ValueError:
        return None


_DEFAULT_LEDGER: ReceiptLedger | None = None
_DEFAULT_LOCK = threading.Lock()


def get_default_ledger() -> ReceiptLedger:
    """Process-wide default ledger rooted at $SZL_LAKE_DIR (or ./khipu)."""
    global _DEFAULT_LEDGER
    with _DEFAULT_LOCK:
        if _DEFAULT_LEDGER is None:
            _DEFAULT_LEDGER = ReceiptLedger()
        return _DEFAULT_LEDGER


if __name__ == "__main__":
    import sys
    led = get_default_ledger()
    print(json.dumps(led.health(), indent=2))
    sys.exit(0)
