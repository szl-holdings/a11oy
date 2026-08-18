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

The additive token-ingress modules implement bounded routing, semantic-oracle
qualification, Prefix Foundry state, file-native ingestion, and verifier-budget
allocation. The Memory Covenant controller adds a fail-closed read-only PostgreSQL
boundary that refuses provider-owner/BYPASSRLS identities and exposes no secret or
write path.

The package top-level name is `routers` (not szl_*/a11oy_*), so it is intentionally
OUTSIDE the guarded-import-liveness first-party scan — and the files exist anyway.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""

__all__ = [
    "lambda_bounty",
    "research_3d",
    "frontier_reads",
    "series_a_control_plane",
    "token_ingress",
    "token_ingress_core",
    "memory_covenant",
]
