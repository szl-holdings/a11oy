"""a11oy DARK-SURFACE AGGREGATOR — wire every still-dark tab so it populates.

The a11oy.net SPA ships tabs whose HTML pages return 200 but whose backing v1
JSON API surfaces were never live (404 / "dark"), so those tabs render empty or
degraded. The backing modules ALL EXIST in this repo; they were simply not
reliably registered onto the live serve.py app (a registration could be missing,
mis-ordered, or guarded by a try/except that swallowed an unrelated import error
and skipped the rest).

This ONE additive module imports and registers EVERY dark surface behind a SINGLE
outer try/except (matching the existing szl_* additive pattern in serve.py), and —
critically — wraps EACH individual register in its OWN try/except so a single
missing or broken module can never block the other six. Every surface is restored
independently; one absent dependency degrades exactly one tab, never the SPA.

DARK SURFACES WIRED (route -> module -> register kind):
  /api/<ns>/v1/energy/budget       szl_energy_budget        register(app, ns)
  /api/<ns>/v1/engine/status       szl_engine_status        register(app, ns)
  /api/<ns>/v1/formula/sovereign   a11oy_formula_endpoints  register(app, ns)
  /api/<ns>/v1/energy/provenance   szl_energy_provenance    register(app, ns)
  /api/<ns>/v1/heart/pulse         szl_heart_blood          register(app, ns)
  /api/<ns>/v1/ayni (+ replay,    ayni_os_serve            include_router(prefix=/api/<ns>)
   tinkuy; legacy bare /v1/ayni kept)
  /api/<ns>/v1/anatomy/loop        szl_anatomy_loop         register(app, ns)  [#341]

ADDITIVE — never replaces a route, never edits another module. Registered BEFORE
the SPA catch-all so the explicit routes resolve LOCALLY and win FastAPI ordering.
Pure stdlib (the per-module registers own their optional deps); no key committed.

DOCTRINE v11 LOCKED 749/14/163. Λ = Conjecture 1 (NEVER a theorem, never "proven
trust"). Organs are EXPERIMENTAL. joules figures stay SAMPLE until on-box NVML;
NO free-energy claims. sovereign:true only on own metal. locked = 8. NO key
committed. NO HALLUCINATION.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""

from __future__ import annotations

import sys
from typing import Any, Callable, List, Tuple

# Doctrine echo block — same shape the other szl_* surfaces emit, so any response
# that reuses this constant stays honesty-clean under the doctrine guards.
DOCTRINE = {
    "version": "v11",
    "counts": "749/14/163",
    "locked": 8,
    "lambda": "Conjecture 1",          # OPEN — never a theorem, never "proven trust"
    "organs": "EXPERIMENTAL",
    "joules": "SAMPLE until on-box NVML",
    "free_energy": False,
    "sovereign": "only on own metal",
    "key_committed": False,
}


def _stderr(msg: str) -> None:
    print(msg, file=sys.stderr)


def _register_via_fn(app: Any, ns: str, module_name: str, label: str, expect: str) -> Tuple[str, bool]:
    """Import ``module_name`` and call its ``register(app, ns=ns)``.

    Each call is independently try/except-guarded by the caller; this helper does
    the import + register + honest log line. Returns (status_line, ok)."""
    mod = __import__(module_name)
    fn: Callable[..., Any] = getattr(mod, "register")
    fn(app, ns=ns)
    line = f"[a11oy:dark] {label} registered: {expect}"
    _stderr(line)
    return (line, True)


def register(app: Any, ns: str = "a11oy") -> List[str]:
    """Wire EVERY dark a11oy tab surface onto ``app`` under /api/<ns>/v1/*.

    Additive. Each individual surface is registered inside its OWN try/except so a
    single missing/broken module degrades exactly one tab and never the rest.
    Returns the list of human-readable status lines (one per surface attempted).
    """
    status: List[str] = []

    # (module_name, label, expected_primary_route) for the register(app, ns) surfaces.
    fn_surfaces: List[Tuple[str, str, str]] = [
        ("szl_energy_budget",       "Energy-budget receipt", f"/api/{ns}/v1/energy/budget"),
        ("szl_engine_status",       "Unified engine status", f"/api/{ns}/v1/engine/status"),
        ("a11oy_formula_endpoints", "Formula sovereign gate", f"/api/{ns}/v1/formula/sovereign"),
        ("szl_energy_provenance",   "Energy provenance chain", f"/api/{ns}/v1/energy/provenance"),
        ("szl_heart_blood",         "Heart+Blood heartbeat", f"/api/{ns}/v1/heart/pulse"),
        ("szl_anatomy_loop",        "Anatomy circulation loop", f"/api/{ns}/v1/anatomy/loop"),
    ]

    for module_name, label, expect in fn_surfaces:
        try:
            line, _ = _register_via_fn(app, ns, module_name, label, expect)
            status.append(line)
        except Exception as exc:  # additive: one missing module never blocks the rest
            line = f"[a11oy:dark] {label} NOT registered ({module_name}): {exc!r}"
            _stderr(line)
            status.append(line)

    # AYNI-OS is a self-contained APIRouter whose routes declare bare paths
    # (/v1/ayni, /v1/replay, /v1/tinkuy). The DOCUMENTED, dashboard-facing contract
    # is /api/<ns>/v1/ayni (the same /api/<ns>/v1/* shape every other dark surface
    # uses); mounting the router WITHOUT a prefix left it at /v1/ayni, so the
    # documented /api/<ns>/v1/ayni 404'd (it fell through to the Node proxy, which
    # answered {"error":"not found","path":"/v1/ayni"}). FIX: include the router under
    # prefix=/api/<ns> so the documented /api/<ns>/v1/ayni path resolves LOCALLY and
    # wins ordering (registered here, before the SPA catch-all / Node proxy). We ALSO
    # keep the legacy bare /v1/ayni mount for back-compat — purely additive, so any
    # existing caller of the old path is never broken. NOT register(app, ns) — own
    # try/except below so AYNI absent never blocks the other six surfaces.
    try:
        from ayni_os_serve import router as _ayni_router  # type: ignore
        included = False
        include_router = getattr(app, "include_router", None)
        if callable(include_router):
            # Documented path: /api/<ns>/v1/ayni (+ /replay, /tinkuy). Resolves LOCALLY.
            app.include_router(_ayni_router, prefix=f"/api/{ns}")
            # Legacy path: bare /v1/ayni — additive back-compat, breaks no caller.
            app.include_router(_ayni_router)
            included = True
        else:
            # Bare Starlette fallback: splice the router's routes onto app.router at
            # BOTH the documented /api/<ns> prefix and the legacy bare path.
            from starlette.routing import Route as _Route
            for _r in getattr(_ayni_router, "routes", []):
                _path = getattr(_r, "path", None)
                _ep = getattr(_r, "endpoint", None)
                _methods = list(getattr(_r, "methods", []) or ["GET"])
                if _path is not None and _ep is not None:
                    app.router.routes.append(_Route(f"/api/{ns}{_path}", _ep, methods=_methods))
                app.router.routes.append(_r)
            included = True
        if included:
            line = f"[a11oy:dark] AYNI-OS mounted: /api/{ns}/v1/ayni + /api/{ns}/v1/replay + /api/{ns}/v1/tinkuy (legacy /v1/ayni kept)"
            _stderr(line)
            status.append(line)
    except Exception as exc:  # additive: AYNI absent never blocks the other six
        line = f"[a11oy:dark] AYNI-OS NOT mounted (ayni_os_serve): {exc!r}"
        _stderr(line)
        status.append(line)

    return status
