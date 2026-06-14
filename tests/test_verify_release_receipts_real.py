# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED 749/14/163 · SLSA L1 (unchanged)
"""tests/test_verify_release_receipts_real.py — integration negative-proof that
the release-asset receipt verifier (scripts/verify_release_receipts.py) catches a
TAMPERED receipt using the REAL Sigstore round-trip, with NO monkeypatching.

Why this exists (issue #408): the existing tests/test_verify_release_receipts.py
exercises the honesty/SAN-allowlist logic offline (the Sigstore verify is mocked).
That proves the policy plumbing but NOT that the actual cryptographic verify
rejects a byte-flipped receipt. This test closes that gap by running the real
verify against a committed GENUINE receipt fixture:

  - The genuine fixture VERIFIES (status PASS, exit 0) — symmetric control, so a
    broken trust root or an over-eager guard can't make the negative proof pass
    for the wrong reason.
  - A copy produced by scripts/tamper_release_receipt.py (payload- or
    signature-byteflip, signer SAN untouched so it still passes the allowlist and
    reaches the crypto) is REJECTED: the real DSSE verify raises, the run exits
    non-zero, and the failing entry is status FAIL with reason "DSSE: invalid
    signature". Nothing is weakened or disabled to get there.

HONESTY / SAFETY
  - No org private key, OIDC token, or signing is required: this VERIFIES an
    already-signed public receipt against the public Sigstore trust root.
  - Off-CI this whole module skips: it needs the `sigstore` SDK (importorskip)
    AND the public Sigstore trust root over the network, so it is gated on the
    explicit SZL_RELEASE_RECEIPT_REAL_VERIFY=1 flag that the dedicated CI job
    sets. A local/default environment never runs it (no false failures, no
    accidental network), mirroring the other real-round-trip tests.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
FIXTURE = (
    REPO_ROOT
    / "tests"
    / "fixtures"
    / "release-receipts"
    / "db137592c44c914c84d7914cbc65c5d8b5c3b6080a31dcf51f6db882f8abf712.dsse.json"
)
REPO = "szl-holdings/a11oy"

# Off-CI default has no Sigstore SDK -> skip the whole module at collection time
# (a missing optional dependency is never a test failure).
pytest.importorskip("sigstore")

# Even with the SDK present, only run where the real verify is explicitly enabled
# (the dedicated CI job sets this). This needs the public Sigstore trust root over
# the network; a developer machine that happens to have the SDK must opt in.
pytestmark = pytest.mark.skipif(
    os.environ.get("SZL_RELEASE_RECEIPT_REAL_VERIFY") != "1",
    reason=(
        "real release-receipt verify needs the public Sigstore trust root + "
        "network; set SZL_RELEASE_RECEIPT_REAL_VERIFY=1 (the dedicated CI job does)"
    ),
)


def _load(module_name: str, rel_path: str):
    """Load a repo script as a module. REPO_ROOT must be importable so the
    verifier's lazy `from szl_formulas import verify_dsse_real` resolves."""
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))
    spec = importlib.util.spec_from_file_location(
        module_name, str(REPO_ROOT / rel_path)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_fixture_is_a_real_signed_receipt():
    """Guard the fixture itself: it must be a genuine SIGSTORE-KEYLESS receipt
    with an embedded bundle, or the negative proof below would be meaningless."""
    assert FIXTURE.exists(), f"missing genuine fixture: {FIXTURE}"
    env = json.loads(FIXTURE.read_text(encoding="utf-8"))
    assert env.get("_mode") == "SIGSTORE-KEYLESS"
    assert env["_sigstore"]["bundle"]["dsseEnvelope"]["signatures"]


def test_genuine_release_receipt_verifies(tmp_path):
    """Symmetric control: the untouched genuine receipt PASSES the real verify."""
    verify = _load("verify_release_receipts", "scripts/verify_release_receipts.py")
    d = tmp_path / "genuine"
    d.mkdir()
    shutil.copy(FIXTURE, d / FIXTURE.name)

    out = tmp_path / "summary.json"
    rc = verify.main(["--dir", str(d), "--repo", REPO, "--summary-out", str(out)])
    assert rc == 0, "genuine receipt must verify (exit 0)"

    summary = json.loads(out.read_text(encoding="utf-8"))
    assert summary["checked"] == 1
    assert summary["passed"] == 1
    assert summary["failed"] == 0
    assert summary["unverifiable"] == 0
    assert summary["results"][0]["status"] == "PASS"


@pytest.mark.parametrize("strategy", ["payload-byteflip", "signature-byteflip"])
def test_tampered_release_receipt_is_rejected(tmp_path, strategy):
    """The real (un-mocked) verify REJECTS a byte-flipped receipt. The signer SAN
    is left intact by the tamper helper, so the receipt clears the allowlist and
    the failure comes from the cryptographic DSSE verify itself."""
    verify = _load("verify_release_receipts", "scripts/verify_release_receipts.py")
    tamper = _load("tamper_release_receipt", "scripts/tamper_release_receipt.py")

    d = tmp_path / "tampered"
    d.mkdir()
    tampered = d / FIXTURE.name
    rc_tamper = tamper.main([str(FIXTURE), str(tampered), "--strategy", strategy])
    assert rc_tamper == 0, "tamper helper should write a structurally-valid copy"

    out = tmp_path / "summary.json"
    rc = verify.main(["--dir", str(d), "--repo", REPO, "--summary-out", str(out)])
    assert rc == 1, "a tampered receipt MUST make the run fail loudly (exit 1)"

    summary = json.loads(out.read_text(encoding="utf-8"))
    assert summary["checked"] == 1
    assert summary["passed"] == 0
    assert summary["failed"] == 1
    entry = summary["results"][0]
    assert entry["status"] == "FAIL"
    # The real Sigstore DSSE verify raises "DSSE: invalid signature" when the
    # signed payload or the signature bytes no longer match.
    assert "invalid signature" in entry["reason"].lower(), entry["reason"]


# The genuine fixture above was minted by this real, in-allowlist producer
# workflow in this repo (its embedded Fulcio cert SAN names it). The forged-signer
# cases below keep the receipt cryptographically intact and only present an
# identity expectation it does NOT satisfy.
_FIXTURE_SIGNER_WORKFLOW = "dsse-receipts.yml"
_OTHER_ALLOWED_WORKFLOW = "release.yml"  # a real default producer, but NOT the one that signed


@pytest.mark.parametrize(
    "label,identity_args",
    [
        # A cryptographically valid receipt presented as if it should have been
        # signed by a workflow in a DIFFERENT repository: the SAN's repo no longer
        # matches the expected one, so it is not an allowed producer.
        ("wrong-repo", ["--repo", "szl-holdings/not-a11oy"]),
        # A cryptographically valid receipt whose (real) signing workflow is NOT
        # among the producers expected for this run: dsse-receipts.yml signed it,
        # but only release.yml is allowed here. This is the "wrong workflow"
        # (forged signer) substitution — a receipt minted by an unexpected, but
        # genuine, GitHub workflow identity. The repo is left correct so ONLY the
        # workflow identity is what fails.
        ("wrong-workflow", ["--repo", REPO, "--allow-workflow", _OTHER_ALLOWED_WORKFLOW]),
    ],
)
def test_forged_signer_receipt_is_rejected(tmp_path, label, identity_args):
    """A GENUINE, cryptographically-valid receipt is REJECTED when its real signer
    identity is not one the verifier expects — an identity/allowlist failure that
    is DISTINCT from the crypto "invalid signature" path.

    No monkeypatching and no weakening of the default allowlist: the receipt bytes
    are untouched (the symmetric control test above proves they verify), and the
    only thing that differs is the repo/workflow identity expectation passed to the
    verifier. This proves an attacker cannot substitute a receipt signed by an
    unexpected (but real) GitHub workflow identity.
    """
    verify = _load("verify_release_receipts", "scripts/verify_release_receipts.py")

    d = tmp_path / "forged-signer"
    d.mkdir()
    shutil.copy(FIXTURE, d / FIXTURE.name)

    out = tmp_path / "summary.json"
    rc = verify.main(["--dir", str(d), "--summary-out", str(out)] + identity_args)
    assert rc == 1, "a receipt from an unexpected signer MUST fail the run (exit 1)"

    summary = json.loads(out.read_text(encoding="utf-8"))
    assert summary["checked"] == 1
    assert summary["passed"] == 0
    assert summary["failed"] == 1
    assert summary["unverifiable"] == 0
    entry = summary["results"][0]
    assert entry["status"] == "FAIL"
    # The receipt was rejected on IDENTITY grounds (unexpected signer), BEFORE the
    # cryptographic verify — explicitly NOT the byte-flip "invalid signature" path.
    reason = entry["reason"].lower()
    assert "unexpected signer" in reason, entry["reason"]
    assert "not an allowed receipt-producing workflow" in reason, entry["reason"]
    assert "invalid signature" not in reason, entry["reason"]
    # The genuine signer SAN is still surfaced for forensics.
    assert _FIXTURE_SIGNER_WORKFLOW in entry.get("signer_identity", ""), entry
