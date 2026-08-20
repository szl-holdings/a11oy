# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 · SLSA L1 (unchanged)
"""tests/test_recheck_rekor_baseline.py — proves the emptied-ledger guard
(issue #320) in scripts/recheck_rekor_receipts.py.

The scheduled Rekor re-check used to treat "zero receipts found" as an honest
soft pass. That is correct only before any receipt is published; once the
append-only governance-receipts ledger is populated, an empty result means the
ledger branch was wiped or the fetch step silently failed — which would let the
monitor go green with nothing to re-check and mask a real regression.

Contract that matters for trust:
  - With NO baseline (and none recorded yet), an empty ledger is still a soft
    pass (exit 0) — no false alarm on first use.
  - With a recorded baseline > 0, an empty ledger fails LOUDLY (exit 1).
  - A ledger that drops *below* (but not to zero) its baseline also fails — the
    ledger is append-only, so any decrease is a regression.
  - A ledger at or above its baseline passes (when nothing fails verification).
  - A present-but-malformed baseline file is a loud environment error (exit 2),
    never a silent min=0 that disables the guard.

These tests are offline: no receipt bodies are verified (placeholder/real
verification is monkeypatched away where needed), so no Sigstore SDK, network,
or org key is ever required.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "recheck_rekor_receipts.py"


def _load_script():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location("recheck_rekor_receipts", str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(tmp_path: Path, name: str, obj: dict) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def _write_baseline(tmp_path: Path, value) -> Path:
    p = tmp_path / "rekor-recheck-baseline.json"
    p.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
    return p


def test_empty_ledger_no_baseline_is_soft_pass(tmp_path):
    """First-use empty state, no baseline recorded -> honest soft pass."""
    script = _load_script()
    rc = script.main(["--dir", str(tmp_path)])
    assert rc == 0


def test_empty_ledger_with_baseline_fails_loudly(tmp_path):
    """Once a baseline > 0 is recorded, an empty ledger is a LOUD failure."""
    script = _load_script()
    receipts = tmp_path / "receipts"
    receipts.mkdir()
    baseline = _write_baseline(tmp_path, {"min_receipts": 3})
    rc = script.main(["--dir", str(receipts), "--baseline", str(baseline)])
    assert rc == 1


def test_min_receipts_flag_empty_ledger_fails(tmp_path):
    """--min-receipts is an equivalent floor without a baseline file."""
    script = _load_script()
    rc = script.main(["--dir", str(tmp_path), "--min-receipts", "3"])
    assert rc == 1


def test_ledger_below_baseline_fails(tmp_path):
    """An append-only ledger dropping below its baseline is a regression."""
    script = _load_script()
    _write(tmp_path, "a.dsse.json", {"_mode": "PLACEHOLDER", "_note": "PLACEHOLDER"})
    rc = script.main(["--dir", str(tmp_path), "--min-receipts", "3"])
    assert rc == 1


def test_baseline_satisfied_passes(tmp_path, monkeypatch):
    """At/above the baseline with everything verifying -> exit 0."""
    script = _load_script()
    monkeypatch.setattr(
        script,
        "_verify_one",
        lambda envelope, identity, issuer: {
            "payloadType": "p",
            "certificate_fpr_sha256": "abc",
        },
    )
    for i in range(3):
        _write(
            tmp_path,
            f"r{i}.dsse.json",
            {"_mode": "SIGSTORE-KEYLESS", "_sigstore": {"bundle": {"x": 1}}},
        )
    rc = script.main(["--dir", str(tmp_path), "--min-receipts", "3"])
    assert rc == 0


def test_baseline_summary_fields_present(tmp_path):
    """The JSON summary surfaces min_expected + baseline_ok for the workflow."""
    script = _load_script()
    summary_out = tmp_path / "summary.json"
    rc = script.main(
        [
            "--dir",
            str(tmp_path),
            "--min-receipts",
            "3",
            "--summary-out",
            str(summary_out),
        ]
    )
    assert rc == 1
    data = json.loads(summary_out.read_text(encoding="utf-8"))
    assert data["min_expected"] == 3
    assert data["baseline_ok"] is False
    assert data["checked"] == 0


def test_failed_verification_still_fails_even_above_baseline(tmp_path, monkeypatch):
    """The baseline floor is additive — a real verification failure still fails."""
    script = _load_script()

    def _boom(envelope, identity, issuer):
        raise RuntimeError("Rekor inclusion proof invalid")

    monkeypatch.setattr(script, "_verify_one", _boom)
    for i in range(3):
        _write(
            tmp_path,
            f"r{i}.dsse.json",
            {"_mode": "SIGSTORE-KEYLESS", "_sigstore": {"bundle": {"x": 1}}},
        )
    rc = script.main(["--dir", str(tmp_path), "--min-receipts", "3"])
    assert rc == 1


def test_malformed_baseline_is_loud_env_error(tmp_path):
    """A corrupt checked-in baseline must NOT silently disable the guard."""
    script = _load_script()
    baseline = _write_baseline(tmp_path, "{ this is not json")
    try:
        rc = script.main(["--dir", str(tmp_path), "--baseline", str(baseline)])
    except SystemExit as exc:
        assert exc.code == 2
    else:
        assert False, f"expected SystemExit(2) for malformed baseline, got rc={rc}"


def test_missing_baseline_file_is_no_floor(tmp_path):
    """A baseline path that does not exist yet = no floor (first-use tolerated)."""
    script = _load_script()
    missing = tmp_path / "does-not-exist.json"
    rc = script.main(["--dir", str(tmp_path), "--baseline", str(missing)])
    assert rc == 0
