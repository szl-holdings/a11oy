# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 · SLSA L1 (unchanged)
"""tests/test_dsse_envelope_real.py — proves szl_formulas Tier B (issue #203)
real Sigstore keyless signing is HONEST.

It asserts the contract that matters for trust:
  - Without an ambient OIDC token, dsse_envelope_real() REFUSES (raises
    DsseSigningUnavailable) — it NEVER fabricates a signature.
  - sign_dsse_or_placeholder() falls back to the honest dsse_envelope()
    PLACEHOLDER (clearly marked `_mode="PLACEHOLDER"`), keeping the original
    placeholder keyid unchanged.
  - The full keyless round-trip (sign + Rekor + verify) is `skipif`-guarded: it
    runs ONLY where a real ambient OIDC token exists (i.e. in CI with
    `id-token: write`). It is never satisfied by a local/default environment.

No org private key is ever required, embedded, or baked into CI.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_szl_formulas():
    spec = importlib.util.spec_from_file_location(
        "szl_formulas", str(REPO_ROOT / "szl_formulas.py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


szl = _load_szl_formulas()


def _has_ambient_oidc() -> bool:
    if os.environ.get("SIGSTORE_IDENTITY_TOKEN"):
        return True
    # GitHub Actions exposes these only when the job has `id-token: write`.
    return bool(
        os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL")
        and os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    )


def test_real_signing_refuses_without_oidc(monkeypatch):
    """No ambient identity -> honest refusal, never a fabricated signature."""
    monkeypatch.delenv("SIGSTORE_IDENTITY_TOKEN", raising=False)
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_URL", raising=False)
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", raising=False)
    assert szl.real_signing_available() is False
    with pytest.raises(szl.DsseSigningUnavailable):
        szl.dsse_envelope_real(b'{"governance":"log"}')


def test_placeholder_fallback_is_honest(monkeypatch):
    """sign_dsse_or_placeholder degrades to the honest placeholder off-CI."""
    monkeypatch.delenv("SIGSTORE_IDENTITY_TOKEN", raising=False)
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_URL", raising=False)
    monkeypatch.delenv("ACTIONS_ID_TOKEN_REQUEST_TOKEN", raising=False)
    env = szl.sign_dsse_or_placeholder(b'{"governance":"log"}')
    assert env["_mode"] == "PLACEHOLDER"
    # The placeholder keyid is unchanged by the Tier B work.
    baseline = szl.dsse_envelope(b'{"governance":"log"}', signer="s")
    assert env["signatures"][0]["keyid"] == baseline["signatures"][0]["keyid"]


def test_registry_and_proof_status_register_real_signer():
    assert szl.REGISTRY.get("dsse_envelope_real") is szl.dsse_envelope_real
    assert "REAL" in szl.PROOF_STATUS.get("dsse_envelope_real", "")
    # Honesty guard: the placeholder entry must still disclose PLACEHOLDER.
    assert "PLACEHOLDER" in szl.PROOF_STATUS.get("dsse_envelope", "")


@pytest.mark.skipif(
    not _has_ambient_oidc(),
    reason="real Sigstore keyless round-trip requires an ambient OIDC token (CI id-token: write)",
)
def test_keyless_sign_and_verify_roundtrip():
    """Live: mint a real Fulcio cert + Rekor entry, then verify it back."""
    payload = b'{"governance":"decision-log","doctrine":"v11"}'
    envelope = szl.dsse_envelope_real(payload, subject_name="szl-governance-test")
    assert envelope["_mode"] == "SIGSTORE-KEYLESS"
    assert envelope["_sigstore"]["bundle"]
    repo = os.environ.get("GITHUB_REPOSITORY", "szl-holdings/a11oy")
    ref = os.environ.get("GITHUB_REF", "refs/heads/main")
    identity = f"https://github.com/{repo}/.github/workflows/dsse-receipts.yml@{ref}"
    result = szl.verify_dsse_real(envelope, identity=identity)
    assert result["verified"] is True
