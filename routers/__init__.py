"""a11oy serve.py route-group package (Wave-K Dev4 — refactor-only decomposition).

BACKGROUND
----------
serve.py is a ~11.7k-line monolith. This package is the FIRST bounded slice of a
SAFE, CI-verified decomposition: a small number of cohesive route groups are moved
out of serve.py into focused modules here, each exposing a single

    def register(app) -> dict

entry point. serve.py imports the package and calls each `register(app)` at the
SAME lexical position the routes used to occupy — i.e. BEFORE the SPA
`/{full_path:path}` catch-all — via the established guarded try/except pattern, so:

  * every path is identical,
  * every method is identical,
  * the order relative to the catch-all is identical,
  * a missing/broken group can NEVER take down the SPA (guarded), and
  * the register() functions are IMPORTED + CALLED (register-invocation-guard clean).

The additive `series_a_control_plane` module is not a refactor-only route group. It
is the single governed integration seam for current estate truth, Counterfactual
Action Passports, signed receipts, and bounded one-attempt effectors. It is exported
here so invocation and package-integrity checks can prove the production module is
intentional rather than an orphaned source file.

`frontier_now_control_plane` is an additive GET/HEAD-only projection over that
existing Series-A seam. It intentionally owns no database, signer, credentials,
scheduler, passport authority, or effectors.

`atelier_frontier` is the GET/HEAD-only clean-room reference intake and MODELED
candidate evaluator. It copies no third-party source or identity and binds no
signer, credential, persistence layer, scheduler, or effector.

The package top-level name is `routers` (not szl_*/a11oy_*), so it is intentionally
OUTSIDE the guarded-import-liveness first-party scan — and the files exist anyway.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""

__all__ = [
    "lambda_bounty",
    "research_3d",
    "frontier_reads",
    "frontier_now_control_plane",
    "atelier_frontier",
    "series_a_control_plane",
]
