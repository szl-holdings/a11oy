# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""a11oy_code — the single import entrypoint for the governed flagship agent.

This is a MANIFEST, not logic. SZL AI is consolidated into ONE flagship — "a11oy
Code" — and this package re-exports the consolidated governed surface from the
existing top-level modules so callers have one place to import from:

    from a11oy_code import AgentLoop, run_agent, govern_infer, register_wallpa
    from a11oy_code import willay_gated_turn, register_willay

Willay is the DISCLOSURE / SIGNING seam of the flagship: the governed INVERSE
gate. Where the closed frontier removes the governor and hides the reasoning,
Willay makes the governance verdict inspectable and returns it as a SIGNED DSSE
provenance receipt — "they hide the governor; we sign and show it." Its gate+sign
entrypoint (``willay_gated_turn``) and FastAPI registrar (``register_willay``)
are re-exported here so the flagship's disclosure seam lives at the same import.

Doctrine v11 (LOCKED): EXACTLY 8 locked-proven Lean formulas
{F1,F4,F7,F11,F12,F18,F19,F22}. Λ = Conjecture 1 — advisory ONLY, never a
theorem, never 1.0. Honesty doctrine: the half-state (claiming more than is
real) is the only unacceptable outcome.

Every re-export is import-guarded: if a backing module is unavailable in this
image, its name is honestly dropped from ``__all__`` and listed in
``UNAVAILABLE`` rather than shadowed by a fabricated stub. ADDITIVE ONLY — no
existing logic is moved or modified here.
"""
from __future__ import annotations

__doctrine__ = {
    "version": "v11",
    "locked_proven": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "lambda": "Conjecture 1 (advisory; never a theorem, never 1.0)",
    "honesty": "the half-state — claiming more than is real — is the only unacceptable outcome",
}

__all__: list[str] = []
UNAVAILABLE: dict[str, str] = {}


def _export(name: str, loader):
    """Bind ``name`` to ``loader()`` and add to __all__; honest-skip on failure."""
    try:
        globals()[name] = loader()
        __all__.append(name)
    except Exception as exc:  # honest: name dropped, reason recorded, no stub
        UNAVAILABLE[name] = repr(exc)


# --- Agent loop (governed FSM brain) ---------------------------------------
def _load_agent_loop():
    from a11oy_agent_loop import AgentLoop
    return AgentLoop


def _load_run_agent():
    from a11oy_agent_loop import run_agent
    return run_agent


_export("AgentLoop", _load_agent_loop)
_export("run_agent", _load_run_agent)


# --- v4 agent surface (FastAPI registrar) ----------------------------------
def _load_register_v4():
    from a11oy_v4_agent import register as register_v4
    return register_v4


_export("register_v4", _load_register_v4)


# --- Governed inference (govern decides) -----------------------------------
def _load_govern_infer():
    from szl_governed_api import govern_infer
    return govern_infer


_export("govern_infer", _load_govern_infer)


# --- Wallpa (VOICE/expression organ) registrar -----------------------------
def _load_register_wallpa():
    from szl_wallpa import register as register_wallpa
    return register_wallpa


_export("register_wallpa", _load_register_wallpa)


# --- MCP client ------------------------------------------------------------
def _load_mcp_client():
    from a11oy_mcp_client import HatunMcpClient as McpClient
    return McpClient


_export("McpClient", _load_mcp_client)


# --- Governed kernel -------------------------------------------------------
def _load_governed_kernel():
    from a11oy_governed_kernel import GovernedKernel
    return GovernedKernel


_export("GovernedKernel", _load_governed_kernel)


# --- Experimental tier registrar -------------------------------------------
def _load_register_exp():
    from a11oy_experimental_tier import register as register_exp
    return register_exp


_export("register_exp", _load_register_exp)


# --- Willay (governed-inverse disclosure/signing gate) ---------------------
# "they hide the governor; we sign and show it" — the gate+sign entrypoint,
# its FastAPI registrar, and the receipt verifier of the flagship's seam.
def _load_willay_gated_turn():
    from szl_willay_gateway import gated_turn
    return gated_turn


def _load_register_willay():
    from szl_willay_gateway import register as register_willay
    return register_willay


def _load_willay_verify_receipt():
    from szl_willay_gateway import verify_receipt
    return verify_receipt


_export("willay_gated_turn", _load_willay_gated_turn)
_export("register_willay", _load_register_willay)
_export("willay_verify_receipt", _load_willay_verify_receipt)


# --- Cognitive drift guard (governed-reasoning step, default OFF) -----------
# Additive reimplementation of the platform cognitive-runtime drift-detector
# pattern: scores current-step-intent vs stated-objective divergence. Gated by
# env A11OY_DRIFT_GUARD=1; honest no-op otherwise. See szl_agentic_loop.
def _load_drift_check():
    from szl_agentic_loop import drift_check
    return drift_check


_export("drift_check", _load_drift_check)


def manifest() -> dict:
    """Honest snapshot of what the flagship surface actually exposes here."""
    return {
        "flagship": "a11oy Code",
        "doctrine": __doctrine__,
        "available": sorted(__all__),
        "unavailable": dict(UNAVAILABLE),
    }
