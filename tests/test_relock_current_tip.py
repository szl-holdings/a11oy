# SPDX-License-Identifier: Apache-2.0
"""UNSIGNED-honest current-tip relock must not reuse the 95-probe receipt."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "relock_current_tip.py"
RECEIPT = ROOT / "docs" / "receipts" / "current-tip-relock-1d1d8ace.json"

SPEC = importlib.util.spec_from_file_location("relock_current_tip", SCRIPT)
assert SPEC and SPEC.loader
relock = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(relock)

CURRENT_TIP = "1d1d8ace2be629fea9171f05774312c13137400a"
FORBIDDEN = ("LIVE", "RUNNING", "PASS")


def test_relock_binds_current_tip_and_rejects_95_probe() -> None:
    receipt = relock.build_relock_receipt(CURRENT_TIP, observed_at="2026-09-11T00:00:00Z")
    assert receipt["git_sha"] == CURRENT_TIP
    assert receipt["signer"] == "ABSENT"
    assert receipt["signed_relock"] is False
    assert receipt["dsse"] is None
    assert receipt["certified"] is False
    assert receipt["proven_trust"] is False
    assert receipt["publication_eligible"] is False
    assert receipt["first_paint"] == "OBSERVED"
    assert receipt["status"] == "UNSIGNED-honest"
    assert receipt["historical_95_probe"]["covers_current_tip"] is False
    assert receipt["historical_95_probe"]["git_sha"] == relock.HISTORICAL_95_PROBE_SHA
    assert receipt["historical_95_probe"]["git_sha"] != CURRENT_TIP
    assert receipt["lyte_three_plane"]["signed_relock"] is False
    assert receipt["doctrine_lock"]["commit"] == "c7c0ba17"
    for forbidden in FORBIDDEN:
        assert receipt["first_paint"] != forbidden
        assert receipt["status"] != forbidden


def test_relock_refuses_to_reuse_95_probe_sha() -> None:
    with pytest.raises(ValueError, match="95-probe"):
        relock.build_relock_receipt(relock.HISTORICAL_95_PROBE_SHA)


def test_committed_receipt_covers_current_tip_only() -> None:
    body = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert body["git_sha"] == CURRENT_TIP
    assert body["historical_95_probe"]["covers_current_tip"] is False
    assert body["historical_95_probe"]["git_sha"] != body["git_sha"]
    assert body["signer"] == "ABSENT"
    assert body["signed_relock"] is False
    assert body["certified"] is False
    assert body["proven_trust"] is False
    assert body["publication_eligible"] is False
    for forbidden in FORBIDDEN:
        assert body["first_paint"] != forbidden
        assert body["status"] != forbidden
        assert body.get("relock_status") != forbidden
