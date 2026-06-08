# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 · SLSA L1 (unchanged)
"""tests/test_verify_release_receipts.py — proves the release-asset receipt
verifier (scripts/verify_release_receipts.py, issue #241) is HONEST and pins the
signer identity per producing workflow.

Contract that matters for trust:
  - A PLACEHOLDER (or any non-real) asset is reported as UNVERIFIABLE and FAILS
    the run — a published release receipt must carry a genuine signature, so a
    placeholder is never a silent pass.
  - The signer SAN read from the embedded Fulcio cert must name one of the allowed
    receipt-producing workflows in this repo; an unexpected signer FAILS even if
    the bundle would otherwise verify.
  - An empty release (no receipt assets yet) is an honest soft pass (exit 0).

These tests are offline: the real Sigstore round-trip is monkeypatched, and the
SAN-allowlist logic is exercised directly. No org key is ever required.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "verify_release_receipts.py"


def _load_script():
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location("verify_release_receipts", str(SCRIPT))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write(tmp_path: Path, name: str, obj: dict) -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return p


def test_empty_release_is_soft_pass(tmp_path):
    """No published receipt assets -> nothing to verify -> exit 0."""
    script = _load_script()
    rc = script.main(["--dir", str(tmp_path)])
    assert rc == 0


def test_placeholder_asset_is_unverifiable_not_silent_pass(tmp_path):
    """A placeholder among the published assets fails as UNVERIFIABLE."""
    script = _load_script()
    _write(tmp_path, "a.dsse.json", {"_mode": "PLACEHOLDER", "_note": "PLACEHOLDER"})
    summary = script.verify_dir(
        tmp_path,
        repo="szl-holdings/a11oy",
        allowed_workflows=script._DEFAULT_PRODUCER_WORKFLOWS,
        issuer=script._SIGSTORE_OIDC_ISSUER,
    )
    assert summary["unverifiable"] == 1
    assert summary["passed"] == 0
    assert summary["results"][0]["status"] == "UNVERIFIABLE"
    # The run as a whole must fail loudly (exit 1), never silently pass.
    rc = script.main(["--dir", str(tmp_path)])
    assert rc == 1


def test_unknown_mode_is_unverifiable(tmp_path):
    script = _load_script()
    _write(tmp_path, "b.dsse.json", {"_mode": "WHO-KNOWS"})
    rc = script.main(["--dir", str(tmp_path)])
    assert rc == 1


def test_san_allowlist_accepts_known_producers():
    script = _load_script()
    repo = "szl-holdings/a11oy"
    for wf in script._DEFAULT_PRODUCER_WORKFLOWS:
        san = f"https://github.com/{repo}/.github/workflows/{wf}@refs/tags/v1.2.3"
        assert script.san_is_allowed_producer(
            san, repo=repo, allowed_workflows=script._DEFAULT_PRODUCER_WORKFLOWS
        ), wf
    # main-ref signers (dispatch-driven producers) are also accepted.
    san_main = f"https://github.com/{repo}/.github/workflows/release.yml@refs/heads/main"
    assert script.san_is_allowed_producer(
        san_main, repo=repo, allowed_workflows=script._DEFAULT_PRODUCER_WORKFLOWS
    )


def test_san_allowlist_rejects_unexpected_signers():
    script = _load_script()
    repo = "szl-holdings/a11oy"
    bad = [
        f"https://github.com/{repo}/.github/workflows/evil.yml@refs/tags/v1",
        "https://github.com/attacker/a11oy/.github/workflows/release.yml@refs/tags/v1",
        "https://example.com/not-a-github-identity",
        f"https://github.com/{repo}/.github/workflows/release.yml",  # no @ref
    ]
    for san in bad:
        assert not script.san_is_allowed_producer(
            san, repo=repo, allowed_workflows=script._DEFAULT_PRODUCER_WORKFLOWS
        ), san


def test_real_envelope_with_unexpected_signer_fails(tmp_path, monkeypatch):
    """Even a bundle that *would* verify fails when its signer is not allowed."""
    script = _load_script()

    # Stub SAN extraction + the underlying Sigstore verify so the test is offline.
    monkeypatch.setattr(
        script,
        "_signer_san",
        lambda bundle: "https://github.com/attacker/a11oy/.github/workflows/release.yml@refs/tags/v1",
    )
    monkeypatch.setattr(
        script, "_verify_real", lambda env, identity, issuer: {"payloadType": "x"}
    )
    _write(
        tmp_path,
        "c.dsse.json",
        {"_mode": "SIGSTORE-KEYLESS", "_sigstore": {"bundle": {"x": 1}}},
    )
    rc = script.main(["--dir", str(tmp_path)])
    assert rc == 1


def test_real_envelope_with_allowed_signer_passes(tmp_path, monkeypatch):
    """An allowed signer whose bundle verifies is a PASS (exit 0)."""
    script = _load_script()
    monkeypatch.setattr(
        script,
        "_signer_san",
        lambda bundle: "https://github.com/szl-holdings/a11oy/.github/workflows/release.yml@refs/tags/v1.0.0",
    )
    monkeypatch.setattr(
        script,
        "_verify_real",
        lambda env, identity, issuer: {"payloadType": "p", "certificate_fpr_sha256": "abc"},
    )
    _write(
        tmp_path,
        "d.dsse.json",
        {"_mode": "SIGSTORE-KEYLESS", "_sigstore": {"bundle": {"x": 1}, "rekor_log_index": 42}},
    )
    rc = script.main(["--dir", str(tmp_path), "--repo", "szl-holdings/a11oy"])
    assert rc == 0


def test_real_envelope_failing_verification_fails_loudly(tmp_path, monkeypatch):
    script = _load_script()
    monkeypatch.setattr(
        script,
        "_signer_san",
        lambda bundle: "https://github.com/szl-holdings/a11oy/.github/workflows/slsa.yml@refs/tags/v1",
    )

    def _boom(env, identity, issuer):
        raise RuntimeError("Rekor inclusion proof invalid")

    monkeypatch.setattr(script, "_verify_real", _boom)
    _write(
        tmp_path,
        "e.dsse.json",
        {"_mode": "SIGSTORE-KEYLESS", "_sigstore": {"bundle": {"x": 1}}},
    )
    rc = script.main(["--dir", str(tmp_path)])
    assert rc == 1
