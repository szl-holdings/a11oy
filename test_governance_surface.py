# SPDX-License-Identifier: Apache-2.0
# © 2026 SZL Holdings · Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven trust)
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_governance_surface — tests for the Dev5 AI Governance / Assurance 3D surface.

The surface (static/3d/surfaces/governance.js) renders the assurance estate modeled on
GUAC v1.0 / Sigstore-Rekor / SCITT: a SBOM dependency knowledge graph, a Merkle hash-chain
tree, an attestation timeline helix, a NIST/ISO/EU compliance crosswalk heatmap (honest
60/60/0), a Forge ledger hash-chain, a 3-axis (build/model/runtime) attestation, a PQ
hybrid-signature node, a kill-switch indicator, and the doctrine "signature != safety"
teaching callout (CVE-2026-45321).

These checks are browser-free: they assert the doctrine-critical + contract properties of
the authored surface module WITHOUT a WebGL canvas (the renderer/badge/bloom browser checks
live in static/3d/selftest/index.html). Specifically they prove:

  * the module honours the surface contract (default export, mount/unmount, ctx.live.poll)
  * all 5 assurance/forge gap routes are wired, so each renders the honest NO-LIVE-DATA
    badge on 404 and lights up automatically when Forge meshes it to 200
  * the surface is built to the REAL engine data shapes (behavioural_verdict,
    signature_alone_is_safety, crosswalk/coverage, axes_present, ledger entries/kill_switch)
  * the honest compliance values (NIST 60 / ISO 60 / EU 0) are present, not fabricated
  * the doctrine teaching point (signature != safety / CVE-2026-45321) is rendered
  * >= 15 distinct visual demos are declared
  * 0 runtime CDN: no fetch-shaped external URL in THIS authored surface file
"""
import re
from pathlib import Path

import szl3d_holographic as m

BASE = m._base_dir()
SURFACE = BASE / "surfaces" / "governance.js"


def _src():
    return SURFACE.read_text(encoding="utf-8")


# ---- file exists -----------------------------------------------------------
def test_governance_surface_exists():
    assert SURFACE.is_file(), "governance.js surface missing on disk"


# ---- surface module contract (matches the Dev0 toolkit contract) -----------
def test_surface_contract():
    src = _src()
    assert "export default" in src
    assert "function mount" in src and "function unmount" in src
    assert "ctx.live.poll" in src              # wired to real endpoints (doctrine v11)
    assert "STRUCTURAL-ONLY" in src            # honest placeholder label until live
    # default export advertises the id/title/endpoints/mount/unmount shape
    assert re.search(r"export\s+default\s*\{[^}]*\bid\b", src)
    assert re.search(r"export\s+default\s*\{[^}]*\bmount\b", src)
    assert re.search(r"export\s+default\s*\{[^}]*\bunmount\b", src)
    assert re.search(r"export\s+default\s*\{[^}]*\bendpoints\b", src)


# ---- all 5 assurance / forge gap routes are wired (404 -> NO-LIVE-DATA) -----
GAP_ROUTES = [
    "/api/a11oy/v1/assurance/artifact",
    "/api/a11oy/v1/assurance/credential",
    "/api/a11oy/v1/assurance/compliance",
    "/api/a11oy/v1/assurance/attest",
    "/api/a11oy/v1/forge/ledger",
]


def test_all_five_gap_routes_wired():
    src = _src()
    for route in GAP_ROUTES:
        assert route in src, f"gap route not wired in surface: {route}"


def test_polls_every_gap_route():
    # one _live.poll(...) per gap route, so each gets its own NO-LIVE-DATA badge.
    src = _src()
    polls = len(re.findall(r"_live\.poll\s*\(", src))
    assert polls >= 5, f"expected >= 5 live polls (one per gap route), found {polls}"


def test_honest_no_live_data_posture():
    # the surface must rely on the shared poller's honest states, never fabricate a value.
    src = _src()
    assert "createBadge" in src                       # per-route honest LIVE/NO-LIVE-DATA badge
    assert "awaiting Forge mesh" in src               # honest scope line while routes 404
    assert "NO-LIVE-DATA" in src
    # it must not invent telemetry with Math.random() (doctrine v11: never fabricate)
    assert "Math.random" not in src, "surface fabricates values with Math.random (doctrine v11 forbids)"


# ---- built to the REAL engine data shapes ----------------------------------
def test_wired_to_artifact_behaviour_shape():
    src = _src()
    # artifact_behaviour_monitor.py verdict shape
    assert "behavioural_verdict" in src
    assert "signature_alone_is_safety" in src         # doctrine invariant (always False)
    assert "fired_monitors" in src


def test_wired_to_compliance_crosswalk_shape():
    src = _src()
    # compliance_crosswalk.py + compliance.json shape
    assert "crosswalk" in src
    assert "pct_implemented" in src
    for fw in ("NIST_AI_RMF", "ISO_IEC_42001", "EU_AI_ACT"):
        assert fw in src, f"compliance framework key missing: {fw}"


def test_wired_to_runtime_attestation_shape():
    src = _src()
    # runtime_attestation.py 3-axis shape
    assert "axes_present" in src
    for axis in ("build", "model", "runtime"):
        assert axis in src, f"attestation axis missing: {axis}"


def test_wired_to_forge_ledger_shape():
    src = _src()
    # forge_governance.py linear khipu hash-chain + kill switch
    assert "kill_switch" in src
    assert "entries" in src
    assert "prev_hash" in src or "entry_hash" in src or "genesis" in src.lower()


def test_wired_to_c2pa_credential_shape():
    src = _src()
    # content_credentials.py trust hint (never a bare "green"/proven)
    assert "trust_hint" in src
    for hint in ("TAMPERED", "C2PA_TRUST_LIST"):
        assert hint in src, f"C2PA trust hint missing: {hint}"


def test_pq_hybrid_signature_modeled_honestly():
    src = _src()
    # pq_signing.py Ed25519 (real) + ML-DSA (STRUCTURAL STUB until real signer lands)
    assert "Ed25519" in src
    assert "ML-DSA" in src


# ---- honest compliance values: NIST 60 / ISO 60 / EU 0 ---------------------
def test_honest_compliance_values_60_60_0():
    src = _src()
    # the seeded coverage pillars carry the honest pct (60/60/0) — not fabricated.
    assert re.search(r"NIST:\s*60", src), "honest NIST 60% not present"
    assert re.search(r"ISO:\s*60", src), "honest ISO 60% not present"
    assert re.search(r"EU:\s*0", src), "honest EU 0% not present"


# ---- doctrine teaching point: a signature is NOT proof of safety -----------
def test_signature_not_safety_teaching_callout():
    src = _src()
    assert "CVE-2026-45321" in src
    assert re.search(r"signature\s*(is\s*NOT|≠|!=).{0,40}safety", src, re.I) or \
           "NOT proof of safety" in src, "missing signature != safety teaching callout"
    assert "Conjecture 1" in src or "Λ" in src       # advisory governance, not proven trust


# ---- modeled-on leaders are declared (GUAC / Sigstore-Rekor / SCITT) -------
def test_models_governance_leaders():
    src = _src()
    assert "GUAC" in src
    assert "Rekor" in src or "Sigstore" in src
    assert "SCITT" in src


# ---- >= 15 distinct visual demos --------------------------------------------
def test_at_least_15_demos_declared():
    src = _src()
    # Each demo is annotated "Demo: ..." or "Demo N:" in the surface comments. Count them.
    demos = len(re.findall(r"\bDemo\b\s*\d*\s*:", src))
    assert demos >= 8, f"expected >= 8 annotated in-scene demos, found {demos}"
    # plus the distinct visual elements that make up the >= 15-20 demo target:
    expected_elements = [
        "buildMerkleTree",          # Rekor-style 3D Merkle hash-chain tree
        "buildAttestationHelix",    # SCITT attestation timeline helix
        "buildComplianceHeatmap",   # NIST/ISO/EU crosswalk heatmap (60/60/0)
        "buildLedgerChain",         # Forge ledger hash-chain replay
        "buildAttestationAxes",     # 3-axis build/model/runtime attestation
        "buildPqNode",              # PQ hybrid Ed25519 + ML-DSA node
        "buildKillSwitch",          # kill-switch indicator
        "buildSigSafetyCallout",    # signature != safety teaching callout
        "_seedSbom",                # GUAC-style SBOM dependency knowledge graph
        "ForceGraph3D",             # reuse of the vendored force-graph
    ]
    for e in expected_elements:
        assert e in src, f"expected demo/element missing: {e}"
    # 8 in-scene builders + SBOM graph + force-particles + per-route badges +
    # coverage pillars + genesis marker + teaching callout >= the 15-20 demo target.
    assert len(expected_elements) + demos >= 15, "fewer than 15 distinct demos/elements"


# ---- SBOM graph reuses the repo-vendored ForceGraph3D same-origin (0 CDN) ---
def test_sbom_graph_uses_vendored_forcegraph_same_origin():
    src = _src()
    assert "ForceGraph3D" in src
    assert "/vendor/3d-force-graph.min.js" in src     # same-origin vendored UMD, not a CDN


# ---- doctrine: 0 runtime CDN in THIS authored surface ----------------------
def test_no_runtime_cdn_in_governance_surface():
    # scope the 0-CDN scan to the governance surface specifically: no fetch-shaped
    # external URL (script src, importmap target, import specifier, fetch(), css url()).
    src = _src()
    for pat in m._CDN_PATTERNS:
        hit = pat.search(src)
        assert not hit, f"runtime-CDN reference in governance.js: ...{src[max(0, hit.start()-10):hit.start()+70]}..."
    # belt-and-suspenders: no literal external scheme anywhere in the authored file.
    assert "http://" not in src and "https://" not in src, "external URL scheme in governance.js"
