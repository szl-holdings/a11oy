"""Static contract guards for the Holographic Integrity Control Plane.

These tests deliberately stay front-end-only: backend behavior has its own module and
route tests. Here we pin the exact same-origin reads, the single bounded atomize POST,
the proposal/zero-effector/unsigned truth boundaries, and the additive shell registration
without booting a browser.
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


def test_integrity_control_preserves_the_two_contract_polls():
    js = _text(SURFACE)
    assert 'const SECURITY_EP = "/api/a11oy/v1/waqay/security-loop/manifest"' in js
    assert 'const CLAIM_EP = "/api/a11oy/v1/claim-integrity/info"' in js
    assert "ctx.live.poll(SECURITY_EP" in js
    assert "ctx.live.poll(CLAIM_EP" in js
    assert "ctx.live.poll(ATOMIZE_EP" not in js


def test_claim_compiler_calls_only_the_exact_atomize_post():
    js = _text(SURFACE)
    assert 'const ATOMIZE_EP = "/api/a11oy/v1/claim-integrity/atomize"' in js
    assert "fetch(ATOMIZE_EP" in js
    assert 'method: "POST"' in js
    assert 'body: JSON.stringify({ text: prose })' in js
    assert "endpoints: [SECURITY_EP, CLAIM_EP, ATOMIZE_EP]" in js
    assert "/api/a11oy/v1/claim-integrity/evaluate" not in js
    assert "localStorage" not in js and "sessionStorage" not in js


def test_claim_compiler_is_cancellable_and_surfaces_refusals():
    js = _text(SURFACE)
    assert '"AbortController" in window' in js
    assert "_compileController.abort()" in js
    for required in (
        "413 · INPUT TOO LARGE",
        "422 · INVALID INPUT",
        "503 · UNAVAILABLE",
        'role", "status"',
        'aria-live", "polite"',
    ):
        assert required in js


def test_claim_compiler_renders_only_structural_review_candidates():
    js = _text(SURFACE)
    for required in (
        'payload.semantic_atomization_computed === false',
        'String(payload.decision_state || "").toUpperCase() === "PROPOSAL_ONLY"',
        "payload.effectors_enabled === 0",
        'payload.method === "VISIBLE-PUNCTUATION-AND-NEWLINE-SPLIT"',
        "payload.candidate_count <= 32",
        "payload.candidate_count === atoms.length",
        "atom.human_review_required === true",
        "atom.atomic === false",
        '=== "STRUCTURAL-SPLIT-ONLY"',
        'row.dataset.reviewRequired = "true"',
        "REVIEW REQUIRED",
        "No semantic evaluation, persistence, signing, approval, or effectors.",
    ):
        assert required in js


def test_claim_compiler_controls_are_mobile_bounded_and_accessible():
    js = _text(SURFACE)
    assert 'compiler.dataset.claimCompiler = "structural-only"' in js
    assert '_proseInput = document.createElement("textarea")' in js
    assert '_compileButton = document.createElement("button")' in js
    assert '_compileButton.type = "button"' in js
    assert 'width: "100%"' in js
    assert 'resize: "vertical"' in js
    assert '_show.el.style.width = "min(94vw, 460px)"' in js
    assert "startExpanded: true" in js


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
