#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Forward-compatible HEAD labels keep a rollback reader available."""

import copy

import pytest

import a11oy_state_store as ss


FUTURE_LABEL = "future_store_v2"


def _entry(label: str, *, digest: str, seq: int) -> dict:
    name = f"20261102T050000Z-7-{seq}-{digest[:16]}.sqlite3"
    return {
        "path": f"{ss.PREFIX}/{label}/{name}",
        "sha256": digest,
        "size": 4096,
        "kind": "sqlite",
        "integrity": "integrity_check",
        "logical_sha256": digest,
        "taken_at": "2026-11-02T05:00:00Z",
        "epoch": 7,
        "seq": seq,
    }


def _head() -> dict:
    gdw = _entry("gdw", digest="a" * 64, seq=1)
    future = _entry(FUTURE_LABEL, digest="b" * 64, seq=2)
    return {
        "schema": ss.HEAD_SCHEMA,
        "operation_id": "1" * 32,
        "sequence": 1,
        "previous_manifest_sha256": None,
        "epoch": 1,
        "writer_id": "2" * 32,
        "boot_id": "3" * 32,
        "state": ss.STATE_ACTIVE,
        "transition": "BOOTSTRAP",
        "handover": None,
        "claim": {
            "kind": ss.CLAIM_FIRST_BOOT,
            "at": "2026-11-02T05:00:00Z",
            "origins": {},
            "previous_epoch": 0,
        },
        "lease": {
            "renewed_at": "2026-11-02T05:00:00Z",
            "heartbeat_path": ss.HEARTBEAT_PATH,
            "stale_after_seconds": 120,
        },
        "source_revision": "4" * 40,
        "bucket": "TEST/bucket",
        "snapshots": {"gdw": gdw, FUTURE_LABEL: future},
        "history": {FUTURE_LABEL: [_entry(FUTURE_LABEL, digest="c" * 64, seq=1)]},
    }


def test_reader_accepts_and_preserves_a_safe_future_store_label() -> None:
    assert FUTURE_LABEL not in {spec.label for spec in ss.STORES}
    head = ss.validate_head(_head())
    assert ss.parse_head(ss.canonical(head)) == head

    replacement = _entry("gdw", digest="d" * 64, seq=3)
    snapshots, history = ss.StateStore._merged(head, {"gdw": replacement})
    assert snapshots[FUTURE_LABEL] == head["snapshots"][FUTURE_LABEL]
    assert history[FUTURE_LABEL] == head["history"][FUTURE_LABEL]
    assert snapshots["gdw"] == replacement
    assert history["gdw"] == [head["snapshots"]["gdw"]]


@pytest.mark.parametrize("label", ("../oro", "ORO", "oro-dash", "a" * 33))
def test_reader_rejects_unsafe_future_labels(label: str) -> None:
    head = _head()
    head["snapshots"][label] = head["snapshots"].pop(FUTURE_LABEL)
    with pytest.raises(ss.StorageBlocked, match="STATE_HEAD_SNAPSHOT_INVALID"):
        ss.validate_head(head)


def test_reader_rejects_a_future_label_with_a_foreign_object_path() -> None:
    head = _head()
    head["snapshots"][FUTURE_LABEL] = copy.deepcopy(head["snapshots"]["gdw"])
    with pytest.raises(ss.StorageBlocked, match="STATE_HEAD_SNAPSHOT_INVALID"):
        ss.validate_head(head)
