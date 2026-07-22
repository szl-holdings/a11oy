"""Demo-critical route-table regression guard (2026-06-16).

RECURRING REGRESSION: route REGISTRATIONS for several szl_* surfaces keep getting
dropped from serve.py's assembled route table during mesh/rebrand refactors, while
their handler modules stay in-image but unwired — so the live endpoints 404 even
though the code is fine. This has bitten the demo repeatedly:

  * #460 had to "restore dropped szl_energy_operator route registration",
  * an earlier fix restored the PNT routes,
  * 2026-06-16 had to restore energy/ledger, energy/projection, restraint/info
    (dropped during the fabric/TAWANTIN rebrand + status-envelope refactor).

The handlers were never the problem — the wiring was. A test that only exercises
one surface cannot catch the NEXT surface getting dropped. So this guard boots the
REAL app in-process (Starlette TestClient, no mocks, no network) and asserts that
the FULL set of demo-critical routes is present in the assembled route table. If a
future serve.py edit drops ANY of them, this test FAILS — turning a silent live
404 into a red CI gate before the demo.

Add a path here when a new surface becomes demo-critical.
"""
import warnings

import pytest

warnings.filterwarnings("ignore")

# Starlette TestClient is backed by httpx; skip cleanly if the test deps are absent.
pytest.importorskip("starlette.testclient")

import serve  # noqa: E402


# The demo-critical surfaces. Each entry is a substring that MUST appear in some
# assembled route path. (compute-pool ships as BOTH the hardened prober path
# /api/a11oy/v1/compute-pool-hardened AND the authoritative scrubbed plain path
# /api/a11oy/v1/compute-pool — see szl_backend_hardening.register(); either satisfies
# the substring match.)
DEMO_CRITICAL_ROUTES = [
    "/api/a11oy/v1/energy/operator/status",   # #460 — already restored once
    "/api/a11oy/v1/energy/ledger",            # 2026-06-16 restore
    "/api/a11oy/v1/energy/projection",        # 2026-06-16 restore
    "/api/a11oy/v1/restraint/info",           # 2026-06-16 restore
    "/api/a11oy/v1/compute-pool",             # ships as compute-pool-hardened
    "/api/a11oy/v1/verify/receipt",            # canonical public receipt verifier used by SDA
    "/api/a11oy/v1/pnt/limits",               # earlier PNT restore
    "/api/a11oy/v1/orbital/topology",         # MODELED orbital roadmap (no on-orbit hardware)
    "/api/a11oy/v1/orbital/projection",       # MODELED orbital energy from MEASURED ground coeff
    "/orbital",                               # MODELED orbital demo PAGE (renders topology+projection)
    "/api/a11oy/v1/frontier/manifest",        # honest roll-up of every live capability (composed)
    "/frontier",                              # unified ecosystem showcase PAGE (renders the manifest roll-up)
    "/api/a11oy/v1/agent/code/compose",       # GCAK — gated cell compose (hard gate before exec)
    "/api/a11oy/v1/agent/code/inspect",       # GCAK — read-only persistent-var inspect (no receipt)
    "/api/a11oy/v1/agent/code/status",        # GCAK — kernel + gate status
    "/api/a11oy/v1/agent/code/receipts",      # GCAK — signed per-cell receipt chain
    "/api/a11oy/v1/pinn/thermal",             # MODELED thermal field — console energy view probes it (no 404)
    "/ungoverned",                            # investor-WOW deep-link → /console#wowtoggle (V.wowtoggle)
    "/ungoverned-vs-a11oy",                   # investor-WOW deep-link → /console#wowtoggle
    "/vs",                                    # investor-WOW deep-link → /console#wowtoggle
    "/compare",                               # investor-WOW deep-link → /console#wowtoggle
    "/demo-cosign.pub",                        # GAP 1 — demo-signing-key public key for /verify (Option B)
    "/proof",                                  # in-browser Lean 4 proof replay PAGE (Tao-Blueprint graph + live type-check)
    "/api/a11oy/v1/attest/",                   # prove-our-whole-stack — 6-factor provenance chain for a decision receipt
    "/attest",                                 # KANCHAY prove-the-stack verifier PAGE
    "/api/a11oy/v1/genome",                    # formula-registry genome — console Genome panel reads it (4 honesty tiers)
    "/api/a11oy/v1/status",                    # Wave-R operational-dashboard back-end (honest per-subsystem/surface health rollup)
    "/api/a11oy/v1/frontier-index/catalog",    # Wave-Q honest ecosystem catalog the status aggregate is built on (drift-proof source)
    "/api/a11oy/v1/models/frontier-adoption",  # Wave-26 pinned model-admission contract
    "/api/a11oy/v1/models/estate",             # Wave-26 fail-closed live HF estate merge
]


def _assembled_paths():
    """Every path Starlette would route, from the REAL booted app (no mocks)."""
    return {
        p
        for r in serve.app.router.routes
        if (p := getattr(r, "path", None))
    }


def test_assembled_route_table_is_nonempty():
    """Sanity: the app booted and assembled a non-trivial route table."""
    paths = _assembled_paths()
    assert len(paths) > 50, f"route table suspiciously small ({len(paths)} paths) — app boot likely broke"


@pytest.mark.parametrize("expected", DEMO_CRITICAL_ROUTES)
def test_demo_critical_route_registered(expected):
    """Each demo-critical route MUST be wired into the assembled route table.

    A drop here is the recurring regression: the handler module is still in-image
    but its Route registration vanished from serve.py, so the live endpoint 404s.
    """
    paths = _assembled_paths()
    assert any(expected in p for p in paths), (
        f"DEMO-CRITICAL ROUTE DROPPED: no assembled route matches {expected!r}. "
        f"Its handler module is almost certainly still in-image but its registration "
        f"was dropped from serve.py during a refactor — re-wire it (additive, "
        f"try/except-guarded) the same way the sibling szl_* surfaces are registered."
    )


def test_no_demo_critical_route_dropped_as_a_set():
    """Belt-and-suspenders: assert the WHOLE set at once with a readable diff."""
    paths = _assembled_paths()
    missing = [
        expected
        for expected in DEMO_CRITICAL_ROUTES
        if not any(expected in p for p in paths)
    ]
    assert not missing, f"demo-critical routes missing from the assembled table: {missing}"
