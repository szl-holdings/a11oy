#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""Sovereignty gate — EXPERIMENTAL, grounded in Allodial non-interference.

Operationalizes the half-state doctrine: a node is sovereign ONLY when a local
or owner-controlled node ACTUALLY serves requests.  The critical failure mode —
the "half-state" — is when a banner claims sovereignty while request routing is
silently delegated to an external/third-party router.  This is the ONLY
unacceptable outcome and is explicitly flagged.

Doctrine grounding:
  The allodial non-interference theorem (``ni_low_independent_of_high`` in
  ``Lutar/Allodial.lean``, PR #229, merge 783a38d0) establishes that the
  sovereign (low-security, user-visible) verdict must be INDEPENDENT of the
  external (high-security, overlord) router's state.  When routing is
  externally delegated, the low output (sovereignty verdict) becomes a function
  of the external router's state — violating non-interference and destroying the
  allodial position.

The half-state is the lattice analogue of a feudal element claiming the allodial
position: the banner says ⊤ while the actual routing position is strictly below
⊤ (under an external overlord).

CITATION: Lutar/Allodial.lean (PR #229, merge 783a38d0) — ni_low_independent_of_high
LEAN_THEOREM: Lutar/Allodial.lean::ni_low_independent_of_high / allodial_iff_top (EXPERIMENTAL — PROPOSED gate, not a locked theorem)
"""
from __future__ import annotations

from typing import TypedDict

CITATION = "Lutar/Allodial.lean (PR #229, merge 783a38d0)"
LEAN_THEOREM = (
    "Lutar/Allodial.lean::ni_low_independent_of_high / allodial_iff_top"
    " (EXPERIMENTAL — PROPOSED gate, not a locked theorem)"
)
_HONEST_NOTE = (
    "EXPERIMENTAL-tier backbone: the Lean non-interference declaration is"
    " kernel-checked, 0-sorry, no-new-axiom, but is a PROPOSED engineering gate"
    " — NOT a locked-8 theorem and NOT a formal Λ result.  The half-state check"
    " is a faithful but informal mirror of that proof, not the proof itself."
    " The sovereignty verdict is ONLY true when a local/owned node actually serves;"
    " any external routing delegation is the uniquely unacceptable half-state."
)


class SovereignVerdictOut(TypedDict):
    sovereign: bool
    half_state: bool
    served_by: str
    base_url: str
    local_node_serving: bool
    reason: str
    citation: str
    lean_theorem: str
    tier: str
    honest_note: str


def sovereign_verdict(
    served_by: str,
    base_url: str,
    local_node_serving: bool,
) -> SovereignVerdictOut:
    """Compute the sovereignty verdict for a serving node.

    Mirrors ``ni_low_independent_of_high``: the low-security (user-visible)
    sovereignty output must be invariant of the external (overlord) router state.
    When an external router intermediates, the output becomes router-state-dependent,
    destroying the allodial position.

    Parameters
    ----------
    served_by          : identifier of the serving entity (e.g. "local", "a11oy-node-0",
                         "external-router", "third-party-cdn", etc.)
    base_url           : the base URL at which this service is presented
    local_node_serving : True iff a local/owner-controlled node is ACTUALLY serving
                         requests right now (not just claimed in a banner)

    Returns
    -------
    SovereignVerdictOut with:
      sovereign   — True ONLY when local_node_serving is True
      half_state  — True when banner-sovereignty is claimed (via base_url or served_by)
                    but local_node_serving is False — the uniquely unacceptable outcome
      reason      — human-readable explanation
    """
    # Determine whether the banner/branding implies a sovereignty claim.
    # We treat any non-external served_by as an implicit sovereignty assertion.
    external_keywords = {
        "external", "router", "cdn", "proxy", "third-party", "thirdparty",
        "cloudflare", "akamai", "fastly", "aws", "gcp", "azure",
    }
    served_by_lower = (served_by or "").lower()
    banner_claims_sovereign = not any(kw in served_by_lower for kw in external_keywords)

    if local_node_serving:
        # Local node IS serving — allodial position is held.
        # Non-interference is satisfied: the sovereignty verdict is independent
        # of any external router's state because we are NOT routing through one.
        return SovereignVerdictOut(
            sovereign=True,
            half_state=False,
            served_by=served_by,
            base_url=base_url,
            local_node_serving=True,
            reason=(
                "Local/owned node is actively serving: allodial position held."
                "  The sovereignty verdict is independent of any external router"
                " state (ni_low_independent_of_high satisfied)."
            ),
            citation=CITATION,
            lean_theorem=LEAN_THEOREM,
            tier="experimental",
            honest_note=_HONEST_NOTE,
        )

    # Local node is NOT serving.
    if banner_claims_sovereign:
        # HALF-STATE: banner claims sovereignty, but routing is externally delegated.
        # This makes the sovereignty verdict (low output) a function of the external
        # router's state — violating non-interference.  UNIQUELY UNACCEPTABLE.
        return SovereignVerdictOut(
            sovereign=False,
            half_state=True,
            served_by=served_by,
            base_url=base_url,
            local_node_serving=False,
            reason=(
                "HALF-STATE DETECTED: the banner asserts sovereignty but routing is"
                " delegated externally.  The low (user-visible) sovereignty verdict"
                " now depends on the external router's state — this violates"
                " ni_low_independent_of_high and the allodial position is lost."
                "  This is the uniquely unacceptable outcome."
            ),
            citation=CITATION,
            lean_theorem=LEAN_THEOREM,
            tier="experimental",
            honest_note=_HONEST_NOTE,
        )

    # External router is explicit; no sovereignty claim made — honest non-sovereign state.
    return SovereignVerdictOut(
        sovereign=False,
        half_state=False,
        served_by=served_by,
        base_url=base_url,
        local_node_serving=False,
        reason=(
            "External routing acknowledged openly: no sovereignty claim made."
            "  Not allodial, but no half-state deception — this is honest."
        ),
        citation=CITATION,
        lean_theorem=LEAN_THEOREM,
        tier="experimental",
        honest_note=_HONEST_NOTE,
    )


__all__ = ["sovereign_verdict", "CITATION", "LEAN_THEOREM"]

# Doctrine v11 LOCKED — 749/14/163 — c7c0ba17 · Λ = Conjecture 1 (NEVER a theorem)
# SLSA L1 honest. L2 build-provenance attestation = roadmap (Wire D) — not yet claimed. L3 not claimed.


if __name__ == "__main__":
    # -----------------------------------------------------------------------
    # Self-tests for the sovereignty gate
    # -----------------------------------------------------------------------
    checks = 0

    # 1. local_node_serving=True → sovereign:true, half_state:false
    r = sovereign_verdict("a11oy-node-0", "https://a11oy.net", True)
    assert r["sovereign"] is True, "local serving must yield sovereign:true"
    assert r["half_state"] is False, "local serving must not be a half-state"
    checks += 2

    # 2. Banner sovereign (non-external served_by) + local_node_serving=False → half_state:true, sovereign:false
    r2 = sovereign_verdict("a11oy-node-0", "https://a11oy.net", False)
    assert r2["sovereign"] is False, "external routing must yield sovereign:false"
    assert r2["half_state"] is True, "banner+no-local-serving must be half_state:true"
    checks += 2

    # 3. Explicit external router + local_node_serving=False → sovereign:false, half_state:false (honest)
    r3 = sovereign_verdict("external-router", "https://a11oy.net", False)
    assert r3["sovereign"] is False, "explicit external must yield sovereign:false"
    assert r3["half_state"] is False, "explicit external with no claim must not be half-state"
    checks += 2

    # 4. CDN variant: served_by contains "cloudflare", local_node_serving=False
    r4 = sovereign_verdict("cloudflare-cdn", "https://a11oy.net", False)
    assert r4["half_state"] is False, "known external CDN must not be half-state"
    assert r4["sovereign"] is False, "CDN serving must yield sovereign:false"
    checks += 2

    # 5. Sovereignty is ONLY true when local_node_serving is True (tier/citation checks)
    assert r["tier"] == "experimental", "must carry experimental tier"
    assert "ni_low_independent_of_high" in r["lean_theorem"], "must reference non-interference theorem"
    checks += 2

    print(f"ok:true checks:{checks}")
