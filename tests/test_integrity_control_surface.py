"""Static contract guards for the Holographic Integrity Control Plane.

These tests deliberately stay front-end-only: backend behavior has its own module and
route tests. Here we pin the exact same-origin reads, the proposal/zero-effector/unsigned
truth boundaries, and the additive shell registration without booting a browser.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SHELL = ROOT / "static" / "3d" / "holographic.html"
SURFACE = ROOT / "static" / "3d" / "surfaces" / "integritycontrol.js"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_integrity_control_is_additive_and_registered_once():
    html = _text(SHELL)
    assert html.count('id: "integritycontrol"') == 1
    assert 'cat: "governance"' in html
    assert 'short: "Integrity Control Plane"' in html
    assert 'mod: "/static/3d/surfaces/integritycontrol.js"' in html


def test_integrity_control_reads_only_the_two_contract_routes():
    js = _text(SURFACE)
    assert 'const SECURITY_EP = "/api/a11oy/v1/waqay/security-loop/manifest"' in js
    assert 'const CLAIM_EP = "/api/a11oy/v1/claim-integrity/info"' in js
    assert "endpoints: [SECURITY_EP, CLAIM_EP]" in js
    assert "ctx.live.poll(SECURITY_EP" in js
    assert "ctx.live.poll(CLAIM_EP" in js
    assert "fetch(" not in js, "surface must use the shared honest poller, not an ad-hoc fetch"


def test_integrity_boundaries_are_visible_and_fail_closed():
    js = _text(SURFACE)
    for required in (
        'securityMode === "PROPOSAL_ONLY"',
        'claimMode === "PROPOSAL_ONLY"',
        "securityEffectors === 0",
        "claimEffectors === 0",
        'externalMutations === "DISABLED"',
        '"UNSIGNED"',
        '"BOUNDARY-VIOLATION"',
        '"NO-LIVE-DATA"',
        '"proposal only · no action"',
        "LIVE</b> here can only mean a manifest fetch succeeded",
    ):
        assert required in js
    assert 'if (m.state !== "live" && m.state !== "degraded") S.security = null' in js
    assert 'if (m.state !== "live" && m.state !== "degraded") S.claim = null' in js


def test_integrity_surface_never_presents_live_effectors_or_third_party_branding():
    js = _text(SURFACE)
    upper = js.upper()
    assert "LIVE EFFECTORS" not in upper
    assert "EFFECTORS LIVE" not in upper
    assert "PALANTIR" not in upper
    assert "SECURITY FORGE" not in upper
    assert "NO COPIED THIRD-PARTY INTERFACE" in upper
