"""S3 — Policy-engine and flight-recorder adversarial tests."""

from __future__ import annotations

import os

import pytest

from a11oy.flight_recorder import RecorderError, SegmentedFlightRecorder
from a11oy.policy import Effect, Rule, TypedPolicyEngine
from a11oy.schemas import SideEffectClass


# -- policy engine ---------------------------------------------------------


def test_p1_default_deny_unknown_action():
    engine = TypedPolicyEngine(
        [Rule("r1", Effect.ALLOW, ("deploy.*",))]
    )
    d = engine.evaluate(
        action_type="exfiltrate.database", side_effect_class=SideEffectClass.READ_ONLY
    )
    assert d.decision is Effect.DENY


def test_p2_glob_case_sensitivity_bypass_attempt():
    """fnmatch is case-sensitive: 'DEPLOY.ANYTHING' must NOT match 'deploy.*'."""
    engine = TypedPolicyEngine([Rule("r1", Effect.ALLOW, ("deploy.*",))])
    d = engine.evaluate(
        action_type="DEPLOY.ANYTHING", side_effect_class=SideEffectClass.READ_ONLY
    )
    assert d.decision is Effect.DENY


def test_p3_obligations_accumulate_even_when_deny_wins():
    """A DENY first-match must still accumulate obligations from later rules
    (they are recorded on the receipt for audit)."""
    engine = TypedPolicyEngine(
        [
            Rule("deny-first", Effect.DENY, ("deploy.prod",)),
            Rule("observe", Effect.ALLOW, ("deploy.*",), evidence_obligations=("test_log",)),
        ]
    )
    d = engine.evaluate(
        action_type="deploy.prod", side_effect_class=SideEffectClass.READ_ONLY
    )
    assert d.decision is Effect.DENY
    assert "test_log" in d.evidence_obligations


def test_p4_irreversible_always_needs_approval_even_with_allow_rule():
    engine = TypedPolicyEngine(
        [Rule("allow-all", Effect.ALLOW, ("*",))]
    )
    d = engine.evaluate(
        action_type="deploy.prod", side_effect_class=SideEffectClass.IRREVERSIBLE
    )
    assert d.decision is Effect.ALLOW  # rule allows...
    assert d.requires_human_approval is True  # ...but approval is mandatory
    # ...and the SCHEMA refuses an ALLOW receipt without the approval record
    # (covered by schemas._approval_present_when_required; exercised in
    # test_s26 via the receipt validator).


def test_p5_glob_shell_metachar_in_action_type():
    """Action types containing brackets/globs must not widen matches."""
    engine = TypedPolicyEngine([Rule("r1", Effect.ALLOW, ("deploy.[a-z]",))])
    d = engine.evaluate(
        action_type="deploy.5", side_effect_class=SideEffectClass.READ_ONLY
    )
    assert d.decision is Effect.DENY  # '5' not in [a-z]
    d2 = engine.evaluate(
        action_type="deploy.x", side_effect_class=SideEffectClass.READ_ONLY
    )
    assert d2.decision is Effect.ALLOW  # glob semantics are intentional here


# -- flight recorder -------------------------------------------------------


def test_r1_mid_log_frame_flip_detected(tmp_path):
    rec = SegmentedFlightRecorder(tmp_path / "log.fr")
    for i in range(5):
        rec.append({"n": i}, idempotency_key=f"k-{i}")
    data = bytearray((tmp_path / "log.fr").read_bytes())
    # Flip a byte in the MIDDLE frame (after 24-byte header + one frame-ish).
    data[60] ^= 0x01
    (tmp_path / "log.fr").write_bytes(bytes(data))
    report = rec.verify_integrity()
    assert report.corruptions, "mid-log tamper not detected"
    assert report.chain_ok is False


def test_r2_tail_truncation_detected(tmp_path):
    rec = SegmentedFlightRecorder(tmp_path / "log.fr")
    for i in range(3):
        rec.append({"n": i}, idempotency_key=f"k-{i}")
    data = (tmp_path / "log.fr").read_bytes()
    (tmp_path / "log.fr").write_bytes(data[:-6])
    report = rec.verify_integrity()
    assert report.corruptions, "tail truncation not detected"


def test_r3_frame_deletion_breaks_chain(tmp_path):
    """Splice out the middle frame entirely: length fields stay self-
    consistent, so only the hash chain can catch this."""
    rec = SegmentedFlightRecorder(tmp_path / "log.fr")
    for i in range(3):
        rec.append({"n": i}, idempotency_key=f"k-{i}")
    data = (tmp_path / "log.fr").read_bytes()
    # Parse frames to locate boundaries
    import struct

    off = 24
    frames = []
    while off < len(data):
        (ln,) = struct.unpack(">I", data[off : off + 4])
        frames.append((off, off + 8 + ln))
        off += 8 + ln
    spliced = data[: frames[1][0]] + data[frames[1][1] :]
    (tmp_path / "log.fr").write_bytes(spliced)
    report = rec.verify_integrity()
    assert report.chain_ok is False or report.gaps, "frame splice not detected"


def test_r4_seq_gap_reported(tmp_path):
    rec = SegmentedFlightRecorder(tmp_path / "log.fr")
    rec.append({"n": 0}, idempotency_key="k-0")
    rec.append({"n": 1}, idempotency_key="k-1")
    # Hand-append a frame with seq=9 (skipping 2..8) with a VALID chain link.
    import hashlib
    import json
    import struct
    import zlib
    from datetime import datetime, timezone

    data = (tmp_path / "log.fr").read_bytes()
    last_frame = data[24:]  # walk to true last frame
    off = 24
    while off < len(data):
        (ln,) = struct.unpack(">I", data[off : off + 4])
        last_frame = data[off : off + 8 + ln]
        off += 8 + ln
    payload = json.dumps(
        {
            "idempotency_key": "k-9",
            "kind": "action",
            "prev_chain": hashlib.sha256(last_frame).hexdigest(),
            "record": {"n": 9},
            "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "seq": 9,
            "sync_state": "PENDING_SYNC",
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    frame = struct.pack(">I", len(payload)) + struct.pack(">I", zlib.crc32(payload)) + payload
    with open(tmp_path / "log.fr", "ab") as fh:
        fh.write(frame)
    report = rec.verify_integrity()
    assert report.gaps == list(range(3, 9)), f"gaps not reported: {report.gaps}"
    assert report.chain_ok is True  # chain holds; the GAP is the honest signal


def test_r5_append_rejects_empty_idempotency_key(tmp_path):
    rec = SegmentedFlightRecorder(tmp_path / "log.fr")
    with pytest.raises(RecorderError):
        rec.append({"n": 0}, idempotency_key="")


def test_r6_replay_never_yields_executed(tmp_path):
    rec = SegmentedFlightRecorder(tmp_path / "log.fr")
    rec.append({"n": 0}, idempotency_key="k-0")
    rec.append({"n": 1}, idempotency_key="k-1")
    replayed = list(rec.replay({"k-0"}))
    assert len(replayed) == 1 and replayed[0]["idempotency_key"] == "k-1"


def test_r7_sync_marker_lifecycle(tmp_path):
    rec = SegmentedFlightRecorder(tmp_path / "log.fr")
    a = rec.append({"n": 0}, idempotency_key="k-0")
    assert rec.pending_sync() == [a.seq]
    rec.mark_synced([a.seq])
    assert rec.pending_sync() == []


def test_r8_not_a_log_rejected(tmp_path):
    (tmp_path / "log.fr").write_bytes(os.urandom(64))
    rec = SegmentedFlightRecorder(tmp_path / "log.fr")
    report = rec.verify_integrity()
    assert report.header_ok is False
    assert report.corruptions
