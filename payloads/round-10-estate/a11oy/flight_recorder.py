"""a11oy.flight_recorder — SegmentedFlightRecorder.

Append-only, hash-chained local durability for governed actions.

Laws:
  * ACK means local durability only: fcntl.flock + fsync. Never claimed as
    remote durability.
  * An action written without upstream acknowledgement stays visibly
    PENDING_SYNC. Silent absence is a Zero-Bandaid violation.
  * Crash recovery is a test, not an assertion: verify_integrity() returns
    gaps, corruptions, and the surviving sequence range.
"""
from __future__ import annotations

import datetime
import fcntl
import hashlib
import json
import os
import struct
from pathlib import Path

MAGIC = b"A11YFR01" + b"\x00" * 16  # 24-byte segment header
_LEN = struct.Struct(">I")


def _canonical(obj) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


class SegmentedFlightRecorder:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self.path.write_bytes(MAGIC)
        elif not self.path.read_bytes().startswith(MAGIC):
            raise ValueError(f"{self.path}: bad magic — not an a11oy flight recorder segment")

    def _frames(self) -> tuple[list[dict], list[str]]:
        data = self.path.read_bytes()
        records, corruptions = [], []
        off = len(MAGIC)
        while off < len(data):
            if off + 4 > len(data):
                corruptions.append(f"truncated_length_prefix_at_offset_{off}")
                break
            (n,) = _LEN.unpack(data[off:off + 4])
            blob = data[off + 4:off + 4 + n]
            if len(blob) < n:
                corruptions.append(f"truncated_frame_at_offset_{off}_expected_{n}_got_{len(blob)}")
                break
            try:
                records.append(json.loads(blob))
            except json.JSONDecodeError:
                corruptions.append(f"undecodable_frame_at_offset_{off}")
            off += 4 + n
        return records, corruptions

    def append(self, body: dict, *, upstream_ack: bool = False, idempotency_key: str | None = None) -> dict:
        """Append one frame. ACKs local durability only.

        sync_state is ACKED_LOCAL when fsync completed; the frame carries
        PENDING_SYNC whenever the upstream ledger has not acknowledged —
        a visible, queryable state, never silently absent.
        """
        with open(self.path, "r+b") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            records, _ = self._frames()
            seq = (records[-1]["seq"] + 1) if records else 1
            prev_hash = records[-1]["record_hash"] if records else _sha(MAGIC)
            frame = {
                "seq": seq,
                "ts": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "prev_hash": prev_hash,
                "sync_state": "ACKED_LOCAL" if upstream_ack else "PENDING_SYNC",
                "idempotency_key": idempotency_key or _sha(_canonical(body))[:16],
                "body": body,
            }
            frame["record_hash"] = _sha(_canonical(frame))
            blob = _canonical(frame)
            f.seek(0, os.SEEK_END)
            f.write(_LEN.pack(len(blob)))
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
            fcntl.flock(f, fcntl.LOCK_UN)
        return frame

    def verify_integrity(self) -> dict:
        records, corruptions = self._frames()
        gaps, chain_ok = [], True
        for i, rec in enumerate(records):
            if i and rec["seq"] != records[i - 1]["seq"] + 1:
                gaps.append(f"sequence_gap_between_{records[i-1]['seq']}_and_{rec['seq']}")
            expected_prev = records[i - 1]["record_hash"] if i else _sha(MAGIC)
            if rec.get("prev_hash") != expected_prev:
                chain_ok = False
            recomputed = dict(rec)
            rh = recomputed.pop("record_hash", None)
            if rh != _sha(_canonical(recomputed)):
                corruptions.append(f"hash_mismatch_at_seq_{rec.get('seq')}")
        return {
            "ok": not corruptions and not gaps and chain_ok,
            "records": len(records),
            "gaps": gaps,
            "corruptions": corruptions,
            "chain_ok": chain_ok,
            "seq_range": [records[0]["seq"], records[-1]["seq"]] if records else None,
            "pending_sync": [r["seq"] for r in records if r.get("sync_state") == "PENDING_SYNC"],
        }

    def find_by_idempotency_key(self, key: str) -> dict | None:
        records, _ = self._frames()
        for r in records:
            if r.get("idempotency_key") == key:
                return r
        return None

    def pending_sync(self) -> list[dict]:
        records, _ = self._frames()
        return [r for r in records if r.get("sync_state") == "PENDING_SYNC"]
