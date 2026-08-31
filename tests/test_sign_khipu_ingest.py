# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 · SLSA L1 (unchanged)
"""tests/test_sign_khipu_ingest.py — proves the vessels Khipu-ingest consumer
(scripts/sign_khipu_ingest_receipt.py + szl_wire.ingest_receipt) is HONEST.

Contract that matters for trust (issue #194):
  - Off-CI (no ambient OIDC) ingest_receipt() records the honest dsse_envelope()
    PLACEHOLDER — never a fabricated signature.
  - The CI helper script REFUSES (exit 2) by default when only a placeholder is
    available, so a deploy/release pipeline cannot silently ship an unsigned
    consumer receipt; --allow-placeholder downgrades that to the honest placeholder.
  - The real keyless round-trip (ingest -> SIGSTORE-KEYLESS) is `skipif`-guarded:
    it runs ONLY where a real ambient OIDC token exists (CI with id-token: write).

No org private key is ever required, embedded, or baked into CI.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "sign_khipu_ingest_receipt.py"


def _load_szl_wire():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location(
        "szl_wire", str(REPO_ROOT / "szl_wire.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_script():
    spec = importlib.util.spec_from_file_location("sign_khipu_ingest_receipt", str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _clear_oidc(monkeypatch):
    monkeypatch.delenv("SIGSTORE_IDENTITY_TOKEN", raising=False)
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_URL", raising=False)
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", raising=False)


def _has_ambient_oidc() -> bool:
    if os.environ.get("SIGSTORE_IDENTITY_TOKEN"):
        return True
    return bool(
        os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL")
        and os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    )


def test_ingest_records_honest_placeholder_off_ci(monkeypatch):
    """Off-CI, the consumer records the honest placeholder, not a fake signature."""
    _clear_oidc(monkeypatch)
    wire = _load_szl_wire()
    receipt = wire.emit_gate_decision_receipt(
        action_id="test-run", gate="unit-test", lambda_score=0.0, fired=[], passed=True,
    )
    node = wire.ingest_receipt(receipt)
    assert node["dsse"]["_mode"] == "PLACEHOLDER"
    # The placeholder must be clearly disclosed, never dressed up as real.
    assert "PLACEHOLDER" in node["dsse"].get("_note", "PLACEHOLDER")


def test_script_refuses_placeholder_by_default(monkeypatch, tmp_path):
    """The CI helper exits non-zero rather than ship an unsigned consumer receipt."""
    _clear_oidc(monkeypatch)
    script = _load_script()
    rc = script.main(["--out-dir", str(tmp_path), "--action-id", "test-refuse"])
    assert rc == 2
    # Nothing should be written when it refuses.
    assert not list(tmp_path.glob("*.dsse.json"))


def test_script_allow_placeholder_writes_honest_envelope(monkeypatch, tmp_path):
    """--allow-placeholder degrades to the honest placeholder and records it."""
    _clear_oidc(monkeypatch)
    script = _load_script()
    rc = script.main(
        ["--out-dir", str(tmp_path), "--action-id", "test-allow", "--allow-placeholder"]
    )
    assert rc == 0
    envelopes = list(tmp_path.glob("*.dsse.json"))
    assert len(envelopes) == 1
    env = json.loads(envelopes[0].read_text(encoding="utf-8"))
    assert env["_mode"] == "PLACEHOLDER"


@pytest.mark.skipif(
    not _has_ambient_oidc(),
    reason="real Sigstore keyless ingest requires an ambient OIDC token (CI id-token: write)",
)
def test_ingest_records_real_signature_in_ci(tmp_path):
    """Live: ingest mints a REAL Sigstore keyless DSSE envelope inside CI."""
    script = _load_script()
    rc = script.main(["--out-dir", str(tmp_path), "--action-id", "ci-live"])
    assert rc == 0
    env = json.loads(next(tmp_path.glob("*.dsse.json")).read_text(encoding="utf-8"))
    assert env["_mode"] == "SIGSTORE-KEYLESS"
    assert env["_sigstore"]["bundle"]
