"""
Patch fragment to insert into serve.py for szl_formula_surfaces registration.

Insert this block BEFORE the SPA catch-all, using the same try/except + register() 
pattern as the other additive modules. Place it after the a11oy_governance_endpoints
block (which is already at line ~10291 in serve.py).

Copy this block verbatim into serve.py after the last "END: a11oy GOVERNANCE" comment.
"""

PATCH = """
# ============================================================================
# BEGIN: a11oy FORMULA SURFACES layer (Dev B — formula-corpus wiring)
# ADDITIVE. Namespace /api/a11oy/v1/formula-surfaces/* — no overlap with any
# existing namespace. register() inserts routes at HEAD of app.router.routes
# so they win over the /api/a11oy/{path:path} Node proxy + SPA catch-all.
#
# Wires 6 previously-dormant corpus formulas into live honest surfaces:
#   GET /api/a11oy/v1/formula-surfaces/bekenstein-plausibility
#       F19/Bekenstein plausibility ratio — APPLIED (external proven inequality,
#       Bekenstein 1981); NOT re-claimed as SZL result; SAMPLE/MODELED label.
#   GET /api/a11oy/v1/formula-surfaces/landauer
#       Landauer ratio = actual_joules / (bits_erased × k_B·T·ln2);
#       MEASURED when nvml_measured=true; SAMPLE otherwise. Honest anti-free-energy.
#   GET /api/a11oy/v1/formula-surfaces/yarqa-plug-flow  [GET + POST]
#       Yarqa Y-01/Y-02 plug-flow compartmentalization; ENGINEERING-METHOD-CFD.
#   GET /api/a11oy/v1/formula-surfaces/science/kalman
#       Kalman update step; LIVE — gain ∈ [0,1] PROVEN (FrontierKalmanGain.lean).
#   GET /api/a11oy/v1/formula-surfaces/science/hoeffding
#       Hoeffding tail bound; LIVE — PROVEN (kernel-verified).
#   GET /api/a11oy/v1/formula-surfaces/science/byzantine-quorum
#       BFT quorum threshold; faultyCount_le_n PROVEN; safety = Conjecture 2.
#   GET /api/a11oy/v1/formula-surfaces/science   — formula index
#   GET /api/a11oy/v1/formula-surfaces/healthz   — module health
#
# DOCTRINE v11: locked-8={F1,F4,F7,F11,F12,F18,F19,F22}@c7c0ba17; Λ=Conjecture 1;
# half-state forbidden; F19 APPLIED not re-claimed; labels: LIVE/MEASURED/SAMPLE/
# MODELED/UNAVAILABLE (never fabricated).
# Co-Authored-By: Perplexity Computer Agent <agent@perplexity.ai>
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
# ============================================================================
try:
    import szl_formula_surfaces as _szl_formula_surfaces
    import sys as _fs_sys
    _fs_status = _szl_formula_surfaces.register(app, ns="a11oy")
    print(f"[a11oy] Formula surfaces registered: {_fs_status}", file=_fs_sys.stderr)
    _A11OY_FORMULA_SURFACES_DIAG = {"status": "ok", "registered": _fs_status}
except Exception as _fs_e:
    import sys as _fs_sys, traceback as _fs_tb
    print(f"[a11oy] Formula surfaces FAILED (non-fatal): {_fs_e!r}", file=_fs_sys.stderr)
    _fs_tb.print_exc(file=_fs_sys.stderr)
    _A11OY_FORMULA_SURFACES_DIAG = {"status": "FAILED", "error": repr(_fs_e)}
# ============================================================================
# END: a11oy FORMULA SURFACES layer
# ============================================================================
"""

if __name__ == "__main__":
    print(PATCH)
