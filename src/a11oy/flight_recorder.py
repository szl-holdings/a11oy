"""SegmentedFlightRecorder: the a11oy local durability log.

CANON Law 7: an ACK from this recorder means LOCAL durability only —
fcntl.flock + fsync before ACK. Remote durability is a separate, visibly
PENDING_SYNC state; a record is SYNCED only when a later sync marker covers
it. Local is not remote.

CANON Law 8: replay is non-mutating and must not double-execute; recovery
scans idempotency keys and yields only records whose key is not in the
caller-supplied executed set.

On-disk format
--------------
Header (24 bytes):
  bytes  0- 7  magic b"A11YFR01"
  bytes  8-11  format version, uint32 big-endian (1)
  bytes 12-23  reserved, zero

Then a sequence of frames:
  4 bytes   payload length N, uint32 big-endian
  4 bytes   CRC-32 of the payload bytes
  N bytes   payload: UTF-8 JSON object with sorted keys:
              seq, kind ("action" | "sync_marker"), idempotency_key,
              recorded_at (UTC RFC 3339), sync_state, prev_chain (hex
              sha256 of the previous raw frame; the first frame chains to
              the 24-byte header), record (arbitrary JSON object)
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import struct
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Optional

MAGIC = b"A11YFR01"
VERSION = 1
HEADER = MAGIC + struct.pack(">I", VERSION) + (b"\x00" * 12)
HEADER_LEN = len(HEADER)
assert HEADER_LEN == 24, "header must be exactly 24 bytes"

SYNC_PENDING = "PENDING_SYNC"
SYNC_DONE = "SYNCED"

_LEN = struct.Struct(">I")


class RecorderError(RuntimeError):
    """Raised for misuse (bad header on open, oversized record, bad seq)."""


@dataclass(frozen=True)
class AppendAck:
    """What append() returns. durability is ALWAYS the string 'LOCAL'."""

    seq: int
    idempotency_key: str
    durability: str  # always "LOCAL" — see CANON Law 7
    sync_state: str  # always PENDING_SYNC at append time
    bytes_written: int


@dataclass
class IntegrityReport:
    """Result of verify_integrity(). Corruption is reported, never hidden."""

    header_ok: bool
    segments: int
    gaps: list[int] = field(default_factory=list)
    corruptions: list[dict] = field(default_factory=list)
    first_seq: Optional[int] = None
    last_seq: Optional[int] = None
    chain_ok: bool = True
    pending_sync: list[int] = field(default_factory=list)


def _canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class SegmentedFlightRecorder:
    """Append-only, length-prefixed, hash-chained local log."""

    MAX_PAYLOAD = 16 * 1024 * 1024  # 16 MiB sanity bound per frame

    def __init__(self, path: os.PathLike | str):
        self.path = Path(path)

    # -- write path ------------------------------------------------------

    def append(self, record: dict, idempotency_key: str) -> AppendAck:
        """Append one action record. ACK implies LOCAL durability only."""
        if not idempotency_key:
            raise RecorderError("idempotency_key is required (CANON Law 8)")
        if not isinstance(record, dict):
            raise RecorderError("record must be a JSON object")
        first_open = not self.path.exists()
        with open(self.path, "a+b") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                last_seq, last_frame = self._scan_locked(fh, write_header=first_open)
                seq = last_seq + 1
                payload = _canonical(
                    {
                        "seq": seq,
                        "kind": "action",
                        "idempotency_key": idempotency_key,
                        "recorded_at": _now_utc(),
                        "sync_state": SYNC_PENDING,
                        "prev_chain": hashlib.sha256(last_frame).hexdigest(),
                        "record": record,
                    }
                )
                if len(payload) > self.MAX_PAYLOAD:
                    raise RecorderError("record exceeds MAX_PAYLOAD")
                frame = _LEN.pack(len(payload)) + _LEN.pack(zlib.crc32(payload)) + payload
                fh.seek(0, os.SEEK_END)
                fh.write(frame)
                fh.flush()
                os.fsync(fh.fileno())  # durable before ACK — Law 7
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        return AppendAck(
            seq=seq,
            idempotency_key=idempotency_key,
            durability="LOCAL",
            sync_state=SYNC_PENDING,
            bytes_written=len(frame),
        )

    def mark_synced(self, seqs: list[int]) -> AppendAck:
        """Append a sync marker covering the given action seqs (remote ACKed)."""
        if not seqs:
            raise RecorderError("mark_synced requires at least one seq")
        with open(self.path, "a+b") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                last_seq, last_frame = self._scan_locked(fh, write_header=False)
                seq = last_seq + 1
                payload = _canonical(
                    {
                        "seq": seq,
                        "kind": "sync_marker",
                        "idempotency_key": f"sync-marker-{seq}",
                        "recorded_at": _now_utc(),
                        "sync_state": SYNC_DONE,
                        "prev_chain": hashlib.sha256(last_frame).hexdigest(),
                        "record": {"synced_seqs": sorted(set(seqs))},
                    }
                )
                frame = _LEN.pack(len(payload)) + _LEN.pack(zlib.crc32(payload)) + payload
                fh.seek(0, os.SEEK_END)
                fh.write(frame)
                fh.flush()
                os.fsync(fh.fileno())
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        return AppendAck(
            seq=seq,
            idempotency_key=f"sync-marker-{seq}",
            durability="LOCAL",
            sync_state=SYNC_DONE,
            bytes_written=len(frame),
        )

    # -- read path -------------------------------------------------------

    def _scan_locked(self, fh, write_header: bool) -> tuple[int, bytes]:
        """Return (last_seq, last_raw_frame) under an held exclusive lock."""
        fh.seek(0)
        header = fh.read(HEADER_LEN)
        if header == b"" and write_header:
            fh.write(HEADER)
            fh.flush()
            os.fsync(fh.fileno())
            return 0, HEADER
        if header != HEADER:
            raise RecorderError("bad magic header: not an A11YFR01 log")
        last_seq = 0
        last_frame = HEADER
        while True:
            start = fh.tell()
            raw_len = fh.read(4)
            if raw_len == b"":
                break
            if len(raw_len) < 4:
                raise RecorderError(f"truncated length field at offset {start}")
            (length,) = _LEN.unpack(raw_len)
            if length > self.MAX_PAYLOAD:
                raise RecorderError(f"implausible frame length at offset {start}")
            raw_crc = fh.read(4)
            payload = fh.read(length)
            if len(raw_crc) < 4 or len(payload) < length:
                raise RecorderError(f"truncated frame at offset {start}")
            (crc,) = _LEN.unpack(raw_crc)
            if zlib.crc32(payload) != crc:
                raise RecorderError(f"CRC mismatch at offset {start}")
            obj = json.loads(payload.decode("utf-8"))
            last_seq = obj["seq"]
            last_frame = raw_len + raw_crc + payload
        return last_seq, last_frame

    def _walk(self) -> tuple[list[dict], IntegrityReport]:
        """Walk all frames without raising on corruption; report instead."""
        report = IntegrityReport(header_ok=False, segments=0)
        payloads: list[dict] = []
        if not self.path.exists():
            report.corruptions.append({"offset": 0, "reason": "file does not exist"})
            return payloads, report
        data = self.path.read_bytes()
        if len(data) < HEADER_LEN or data[:HEADER_LEN] != HEADER:
            report.corruptions.append({"offset": 0, "reason": "bad magic header"})
            return payloads, report
        report.header_ok = True
        prev_frame = HEADER
        offset = HEADER_LEN
        expected_seq = 1
        synced: set[int] = set()
        while offset < len(data):
            if offset + 8 > len(data):
                report.corruptions.append(
                    {"offset": offset, "reason": "truncated frame header"}
                )
                break
            (length,) = _LEN.unpack(data[offset : offset + 4])
            (crc,) = _LEN.unpack(data[offset + 4 : offset + 8])
            end = offset + 8 + length
            if end > len(data):
                report.corruptions.append(
                    {"offset": offset, "reason": "truncated frame payload"}
                )
                break
            payload_bytes = data[offset + 8 : end]
            frame_bytes = data[offset:end]
            if zlib.crc32(payload_bytes) != crc:
                report.corruptions.append(
                    {"offset": offset, "reason": "CRC mismatch (tamper or rot)"}
                )
                report.chain_ok = False
                offset = end
                continue
            try:
                obj = json.loads(payload_bytes.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                report.corruptions.append(
                    {"offset": offset, "reason": "payload is not valid JSON"}
                )
                report.chain_ok = False
                offset = end
                continue
            if hashlib.sha256(prev_frame).hexdigest() != obj.get("prev_chain"):
                report.corruptions.append(
                    {"offset": offset, "reason": "hash chain broken"}
                )
                report.chain_ok = False
            seq = obj.get("seq")
            if isinstance(seq, int):
                while expected_seq < seq:
                    report.gaps.append(expected_seq)
                    expected_seq += 1
                expected_seq = seq + 1
                if report.first_seq is None:
                    report.first_seq = seq
                report.last_seq = seq
            if obj.get("kind") == "sync_marker":
                synced.update(obj.get("record", {}).get("synced_seqs", []))
            payloads.append(obj)
            report.segments += 1
            prev_frame = frame_bytes
            offset = end
        report.pending_sync = sorted(
            p["seq"] for p in payloads if p.get("kind") == "action" and p["seq"] not in synced
        )
        return payloads, report

    def verify_integrity(self) -> IntegrityReport:
        """Return gaps, corruptions, sequence range, chain and sync state."""
        _, report = self._walk()
        return report

    def pending_sync(self) -> list[int]:
        """Seqs of action records not yet covered by a sync marker."""
        _, report = self._walk()
        return report.pending_sync

    def replay(self, executed_keys: set[str]) -> Iterator[dict]:
        """Yield action payloads whose idempotency key was NOT yet executed.

        Non-mutating (CANON Law 8): this method never writes. Recovery code
        passes the set of idempotency keys already executed downstream and
        re-executes only what this generator yields.
        """
        payloads, _ = self._walk()
        for obj in payloads:
            if obj.get("kind") != "action":
                continue
            if obj.get("idempotency_key") in executed_keys:
                continue
            yield obj
