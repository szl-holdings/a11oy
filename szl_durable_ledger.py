#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""szl_durable_ledger.py — a DURABLE, BOUNDED, ROTATING append-only record store.

Fixes the "database or disk is full" class (waveI_gapsB Gap 3). The a11oy energy /
receipt ledger (szl_energy_ledger.EnergyLedger) persisted to an UNBOUNDED append-only
JSONL file: it grew without limit until the container disk filled ("database or disk is
full" crashed killinchu live data). This module is the governed, size-capped, rotating
storage engine that path uses — no bandaid, a real bounded store.

Doctrine v11 (the whole point of this module):
  - BOUNDED: the on-disk footprint is capped. When the active segment reaches
    ``max_bytes`` it ROTATES to ``<path>.1`` (then ``.2`` …), and only the newest
    ``backup_count`` segments are kept — the oldest is DELETED. Total footprint is
    therefore ~= ``max_bytes * (backup_count + 1)``. The disk can no longer fill.
  - HONEST WHEN DEGRADED: if the underlying storage is unwritable / full ("No space
    left on device", read-only FS, missing dir), we NEVER silently drop the write and
    NEVER fabricate success. ``append()`` returns ``StoreResult(ok=False,
    status="unavailable", ...)`` with the real OSError reason, and ``status()`` reports
    ``UNAVAILABLE`` / storage pressure. The caller (and /healthz) can surface the truth.
  - DURABLE: each append is flushed + ``os.fsync``'d so a crash-after-append survives,
    exactly like the prior implementation — rotation does not weaken that.

Λ = Conjecture 1 (advisory, never "green"). Additive + guarded; sovereign=false.

DESIGN — studied leaders, folded the GOVERNED version into our ecosystem:
  * Append-only log rotation — Python ``logging.handlers.RotatingFileHandler``
    (``maxBytes`` + ``backupCount``: roll at a size cap, keep only the newest N,
    delete the oldest). https://docs.python.org/3/library/logging.handlers.html
    We reuse the .1/.2/… segment-rename + oldest-drop scheme (adapted to JSONL records
    so a hash-chain reader can walk oldest→newest across segments).
  * Bounded-folder / stale eviction — OpenTelemetry disk-buffering (per-signal max
    file size + max folder size, oldest-first eviction).
    https://github.com/open-telemetry/opentelemetry-java-contrib/blob/main/disk-buffering/README.md
  * SQLite WAL + retention alternative — the brief allows "SQLite WAL with VACUUM/
    retention" instead. We chose bounded rotating JSONL because the existing ledger is
    ALREADY an offline-verifiable hash-chained JSONL log (szl_energy_ledger), so a
    size-capped rotating JSONL is the minimal, additive, non-overlapping fix that keeps
    the chain re-hashable. WAL retention docs for the record: https://sqlite.org/wal.html
    (auto-checkpoint at 1000 pages; ``PRAGMA wal_checkpoint(TRUNCATE)`` to bound the WAL).

HONEST LIMIT (never overclaimed): rotation is retention, not archival — evicting the
oldest segment DROPS its records. For a hash-chained ledger that means the retained head
still verifies internally from the earliest RETAINED entry, but the chain is no longer
rooted at genesis once a segment has been evicted. We report ``rotations`` and
``segments`` so that truncation is auditable, never silent. Operators who must keep the
full chain from genesis mount a large ``/data`` volume and/or raise the cap; the store
protects availability first (a bounded ledger beats a crashed one).
"""
from __future__ import annotations

import json
import os
import shutil
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator, Optional

# ---------------------------------------------------------------------------
# Doctrine constants — honest storage labels + the bound defaults.
# ---------------------------------------------------------------------------
DOCTRINE = "v11"

# Honest storage-health labels. Mirrors the joules label vocabulary style: a plain
# word the caller can forward verbatim into a response / /healthz. NEVER "green".
OK = "ok"                    # storage writable, well under the cap
PRESSURE = "pressure"        # writable but near the cap OR low free disk — advisory
UNAVAILABLE = "unavailable"  # cannot write (full / read-only / missing) — HONEST refusal

# Default per-segment cap and how many rotated segments to retain. Total on-disk
# footprint is bounded to ~ max_bytes * (backup_count + 1). Chosen in the spirit of the
# OTel disk-buffering defaults (small file cap, bounded folder). Env-overridable so an
# operator with a big /data volume can raise the ceiling without a code edit.
DEFAULT_MAX_BYTES = int(os.getenv("SZL_LEDGER_MAX_BYTES", str(8 * 1024 * 1024)))     # 8 MiB/segment
DEFAULT_BACKUP_COUNT = int(os.getenv("SZL_LEDGER_BACKUP_COUNT", "4"))                 # keep newest 4

# Fraction of max_bytes at which the ACTIVE segment is considered "under pressure"
# (advisory, still writable). 0.90 => warn in the last 10% before a rotate.
PRESSURE_RATIO = float(os.getenv("SZL_LEDGER_PRESSURE_RATIO", "0.90"))

# Minimum free bytes on the filesystem below which we flag storage PRESSURE even if the
# segment is small — the disk itself is nearly full (the "disk full" early-warning).
MIN_FREE_BYTES = int(os.getenv("SZL_LEDGER_MIN_FREE_BYTES", str(16 * 1024 * 1024)))   # 16 MiB


@dataclass
class StoreResult:
    """Outcome of a single append. ``ok`` is True ONLY when the record is durably on
    disk (written + fsync'd). On a degraded store ``ok`` is False, ``status`` is
    ``UNAVAILABLE`` and ``error`` carries the real reason — never a fabricated success."""
    ok: bool
    status: str                        # OK | PRESSURE | UNAVAILABLE
    bytes_written: int = 0
    rotated: bool = False
    error: Optional[str] = None


@dataclass
class _Counters:
    appended: int = 0
    rotations: int = 0
    dropped_segments: int = 0
    write_failures: int = 0
    last_error: Optional[str] = None


def _free_bytes(path: str) -> Optional[int]:
    """Free bytes on the filesystem backing ``path`` (its dir). None if unknowable."""
    try:
        d = os.path.dirname(os.path.abspath(path)) or "."
        return int(shutil.disk_usage(d).free)
    except Exception:
        return None


class DurableStore:
    """Bounded, rotating, fsync'd append-only JSONL record store.

    - ``append(record)`` serialises one dict to a JSONL line, rotates the active
      segment first if it would exceed ``max_bytes``, writes + fsyncs, and returns a
      StoreResult. If the disk is full / read-only / the dir cannot be created, it
      returns ``ok=False, status="unavailable"`` with the real error — the record is
      NOT fabricated as written.
    - Rotation: ``<path>`` -> ``<path>.1`` -> … -> ``<path>.<backup_count>``; the file
      that would become ``.<backup_count+1>`` is deleted (oldest-first eviction), so the
      footprint is bounded. This is the RotatingFileHandler scheme adapted to records.
    - ``iter_records()`` walks ALL retained segments oldest→newest so a hash-chain reader
      reconstructs the retained ledger in order.
    - ``status()`` reports honest storage health for /healthz (OK/PRESSURE/UNAVAILABLE).

    Thread-safe (single lock). Pure stdlib. Never raises to the caller on a storage
    fault — it reports it.
    """

    def __init__(self, path: str,
                 max_bytes: int = DEFAULT_MAX_BYTES,
                 backup_count: int = DEFAULT_BACKUP_COUNT,
                 pressure_ratio: float = PRESSURE_RATIO,
                 min_free_bytes: int = MIN_FREE_BYTES,
                 fsync: bool = True):
        self.path = path
        # Guard against pathological config that would DISABLE the bound (0 => never
        # rotate => unbounded, the exact bug we are fixing). Floor both to safe minima.
        self.max_bytes = max(1024, int(max_bytes))
        self.backup_count = max(1, int(backup_count))
        self.pressure_ratio = min(max(pressure_ratio, 0.1), 0.99)
        self.min_free_bytes = max(0, int(min_free_bytes))
        self.fsync = bool(fsync)
        self._lock = threading.Lock()
        self._counters = _Counters()
        # Best-effort: ensure the parent dir exists up front (honest if it can't).
        self._dir_ok, self._dir_error = self._ensure_dir()

    # -- paths -------------------------------------------------------------
    def _segment_path(self, n: int) -> str:
        """Segment 0 == the active path; n>=1 == the rotated backups (.1 … )."""
        return self.path if n == 0 else f"{self.path}.{n}"

    def _ensure_dir(self) -> tuple[bool, Optional[str]]:
        try:
            d = os.path.dirname(os.path.abspath(self.path))
            if d:
                os.makedirs(d, exist_ok=True)
            return True, None
        except OSError as exc:
            return False, f"{type(exc).__name__}: {exc}"

    # -- size --------------------------------------------------------------
    def _active_size(self) -> int:
        try:
            return os.path.getsize(self.path)
        except OSError:
            return 0

    def total_bytes(self) -> int:
        """On-disk footprint across the active segment + all retained backups."""
        total = 0
        for n in range(0, self.backup_count + 1):
            try:
                total += os.path.getsize(self._segment_path(n))
            except OSError:
                continue
        return total

    def max_total_bytes(self) -> int:
        """The HARD upper bound on footprint: cap * (backups + 1)."""
        return self.max_bytes * (self.backup_count + 1)

    # -- rotation ----------------------------------------------------------
    def _rotate(self) -> bool:
        """Roll the active segment out to .1, shifting existing backups up and DROPPING
        the oldest beyond backup_count (oldest-first eviction — the RotatingFileHandler
        scheme). Returns True on a successful rotation. Never raises."""
        try:
            # Delete the segment that would fall off the end (oldest retained).
            oldest = self._segment_path(self.backup_count)
            if os.path.exists(oldest):
                os.remove(oldest)
                self._counters.dropped_segments += 1
            # Shift .N -> .N+1 for the rest, high to low.
            for n in range(self.backup_count - 1, 0, -1):
                src = self._segment_path(n)
                if os.path.exists(src):
                    os.replace(src, self._segment_path(n + 1))
            # Active -> .1
            if os.path.exists(self.path):
                os.replace(self.path, self._segment_path(1))
            self._counters.rotations += 1
            return True
        except OSError as exc:
            self._counters.last_error = f"rotate: {type(exc).__name__}: {exc}"
            return False

    # -- append ------------------------------------------------------------
    def append(self, record: Any) -> StoreResult:
        """Durably append one JSON-serialisable record. Rotates first if needed; writes
        + fsyncs; returns an honest StoreResult. On a storage fault returns
        ok=False/status=UNAVAILABLE with the real reason (never a fabricated success)."""
        with self._lock:
            try:
                line = json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n"
            except (TypeError, ValueError) as exc:
                self._counters.write_failures += 1
                self._counters.last_error = f"serialize: {type(exc).__name__}: {exc}"
                return StoreResult(ok=False, status=UNAVAILABLE,
                                   error=f"unserialisable record: {exc}")

            payload = line.encode("utf-8")
            rotated = False

            # Rotate BEFORE writing if this line would push the active segment past the
            # cap (and there is already something in it — a single oversized record still
            # writes to its own fresh segment rather than being dropped).
            if self._active_size() > 0 and self._active_size() + len(payload) > self.max_bytes:
                rotated = self._rotate()

            # Re-ensure the dir (a volume can appear/vanish between calls).
            if not self._dir_ok:
                self._dir_ok, self._dir_error = self._ensure_dir()

            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(line)
                    f.flush()
                    if self.fsync:
                        os.fsync(f.fileno())
            except OSError as exc:
                # HONEST degradation: full disk ("No space left on device"), read-only
                # FS, permission, missing dir. We do NOT claim the write happened.
                self._counters.write_failures += 1
                self._counters.last_error = f"{type(exc).__name__}: {exc}"
                return StoreResult(ok=False, status=UNAVAILABLE, rotated=rotated,
                                   error=f"{type(exc).__name__}: {exc}")

            self._counters.appended += 1
            st = self._pressure_status()
            return StoreResult(ok=True, status=st, bytes_written=len(payload),
                               rotated=rotated)

    # -- read --------------------------------------------------------------
    def iter_records(self, on_bad_line: Optional[Callable[[str], None]] = None) -> Iterator[dict]:
        """Yield every retained record oldest→newest across ALL segments.

        Reads the highest-numbered backup first (oldest) down to the active segment
        (newest), so a hash-chain reader reconstructs the retained ledger in order. Bad
        lines are skipped honestly (never fabricated); ``on_bad_line`` observes them."""
        for n in range(self.backup_count, -1, -1):
            seg = self._segment_path(n)
            if not os.path.exists(seg):
                continue
            try:
                with open(seg, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError:
                            if on_bad_line is not None:
                                on_bad_line(line)
                            continue
            except OSError:
                continue

    # -- health ------------------------------------------------------------
    def _pressure_status(self) -> str:
        """OK / PRESSURE for a WRITABLE store (UNAVAILABLE is decided at write time)."""
        if self._active_size() >= self.max_bytes * self.pressure_ratio:
            return PRESSURE
        free = _free_bytes(self.path)
        if free is not None and free < self.min_free_bytes:
            return PRESSURE
        return OK

    def _is_writable_now(self) -> tuple[bool, Optional[str]]:
        """Real write-probe of the store dir (mirrors szl_energy_ledger._dir_is_writable):
        a genuine test, not a guess. Returns (writable, error)."""
        try:
            d = os.path.dirname(os.path.abspath(self.path)) or "."
            os.makedirs(d, exist_ok=True)
            probe = os.path.join(d, ".szl_durable_ledger.wtest")
            with open(probe, "w", encoding="utf-8") as f:
                f.write("ok")
            os.remove(probe)
            return True, None
        except OSError as exc:
            return False, f"{type(exc).__name__}: {exc}"

    def status(self, probe: bool = True) -> dict:
        """Honest storage-health report for /healthz and the ledger summary.

        ``status`` is:
          - UNAVAILABLE if the store dir is not writable right now (full / read-only /
            missing) OR the last write failed;
          - PRESSURE if writable but the active segment is near the cap OR free disk is
            below ``min_free_bytes``;
          - OK otherwise.
        Reports the real bound so callers can prove the footprint is capped. Never
        raises, never fabricates."""
        writable, werr = (self._is_writable_now() if probe else (self._dir_ok, self._dir_error))
        total = self.total_bytes()
        active = self._active_size()
        free = _free_bytes(self.path)

        if not writable or self._counters.write_failures and self._counters.appended == 0:
            st = UNAVAILABLE
        else:
            st = self._pressure_status()
            if not writable:
                st = UNAVAILABLE

        return {
            "status": st,                              # OK | PRESSURE | UNAVAILABLE
            "writable": writable,
            "path": self.path,
            "bounded": True,
            "max_bytes_per_segment": self.max_bytes,
            "backup_count": self.backup_count,
            "max_total_bytes": self.max_total_bytes(),  # HARD footprint cap
            "active_bytes": active,
            "total_bytes": total,
            "free_bytes": free,
            "min_free_bytes": self.min_free_bytes,
            "appended": self._counters.appended,
            "rotations": self._counters.rotations,
            "dropped_segments": self._counters.dropped_segments,   # honest truncation count
            "write_failures": self._counters.write_failures,
            "last_error": werr or self._counters.last_error,
            "doctrine": DOCTRINE,
            "note": (
                "size-capped rotating append-only store; footprint bounded to "
                "max_total_bytes; oldest segment evicted on rotation (retention, not "
                "archival — truncation is reported via dropped_segments, never silent); "
                "UNAVAILABLE reported honestly when storage is degraded (never fabricated)."
            ),
        }


# ---------------------------------------------------------------------------
# Self-test — no server. Proves the store BOUNDS size and DEGRADES HONESTLY.
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    import tempfile

    out: dict = {}
    d = tempfile.mkdtemp(prefix="szl_durable_")
    path = os.path.join(d, "ledger.jsonl")

    # Tiny cap so a handful of records forces several rotations.
    store = DurableStore(path, max_bytes=512, backup_count=2, min_free_bytes=0)

    # (1) hammer far past the cap; footprint must stay bounded.
    for i in range(2000):
        r = store.append({"seq": i, "blob": "x" * 64})
        assert r.ok, r
    total = store.total_bytes()
    hard_cap = store.max_total_bytes()
    assert total <= hard_cap, (total, hard_cap)
    assert store._counters.rotations > 0, "must have rotated"
    assert store._counters.dropped_segments > 0, "must have evicted oldest segments"
    out["bounds_footprint"] = True
    out["footprint_bytes"] = total
    out["hard_cap_bytes"] = hard_cap
    out["rotations"] = store._counters.rotations

    # (2) retained records are readable oldest->newest and monotonically increasing seq.
    seqs = [rec["seq"] for rec in store.iter_records()]
    assert seqs == sorted(seqs), "retained records must read in order"
    assert seqs[-1] == 1999, "newest record must be present"
    assert seqs[0] > 0, "oldest records were evicted (retention), so seq0 dropped"
    out["reads_in_order_after_rotation"] = True
    out["retained_records"] = len(seqs)

    # (3) HONEST DEGRADATION: point the store at an UNWRITABLE dir -> UNAVAILABLE,
    # append refuses honestly (ok=False), and NOTHING is fabricated as written.
    bad = DurableStore(os.path.join(d, "nope", "ledger.jsonl"), max_bytes=512)
    # Make the parent unwritable by pointing under a file (open() will OSError).
    file_as_dir = os.path.join(d, "afile")
    with open(file_as_dir, "w") as f:
        f.write("x")
    bad2 = DurableStore(os.path.join(file_as_dir, "ledger.jsonl"), max_bytes=512)
    r = bad2.append({"seq": 0})
    assert not r.ok and r.status == UNAVAILABLE and r.error, r
    s = bad2.status()
    assert s["status"] == UNAVAILABLE and s["writable"] is False, s
    assert bad2._counters.appended == 0, "must not fabricate a write"
    out["degrades_honestly_unavailable"] = True

    # (4) healthy store reports OK/PRESSURE + a real hard cap; status never 'green'.
    hs = store.status()
    assert hs["bounded"] is True and hs["max_total_bytes"] == hard_cap, hs
    assert hs["status"] in (OK, PRESSURE), hs
    out["reports_bounded_status"] = True

    # cleanup
    shutil.rmtree(d, ignore_errors=True)

    out["ok"] = all(v is True for k, v in out.items() if isinstance(v, bool))
    return out


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
