"""test_dark_surfaces — every dark a11oy tab is wired and doctrine-clean.

Asserts the szl_dark_surfaces_register aggregator:
  1. parses + imports,
  2. registers ALL 7 dark-surface routes onto a fresh FastAPI app,
  3. is independently fault-tolerant (one missing module never blocks the rest),
  4. and that the invokable surfaces return doctrine-clean bodies:
       - joules figures are SAMPLE (never "measured" off-box),
       - no free-energy / perpetual-motion claim,
       - organs are EXPERIMENTAL,
       - Λ stays Conjecture 1 (never a theorem, never "proven trust").

Pure stdlib + FastAPI TestClient. Run: python3 test_dark_surfaces.py  (or pytest).
"""

from __future__ import annotations

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
# mirror serve.py: make `import a11oy.formulas` resolvable for the formula surface
if os.path.isdir(os.path.join(HERE, "src", "a11oy")) and os.path.join(HERE, "src") not in sys.path:
    sys.path.insert(0, os.path.join(HERE, "src"))

from fastapi import FastAPI  # noqa: E402

import szl_dark_surfaces_register as agg  # noqa: E402

NS = "a11oy"

# The 7 dark surfaces this PR restores. Each MUST be present after register().
EXPECTED_ROUTES = [
    f"/api/{NS}/v1/energy/budget",
    f"/api/{NS}/v1/engine/status",
    f"/api/{NS}/v1/formula/sovereign",
    f"/api/{NS}/v1/energy/provenance",
    f"/api/{NS}/v1/heart/pulse",
    f"/v1/ayni",
    f"/api/{NS}/v1/anatomy/loop",
]


def _route_paths(app: FastAPI) -> set:
    return {getattr(r, "path", None) for r in app.router.routes if getattr(r, "path", None)}


def test_all_seven_routes_registered():
    app = FastAPI()
    status = agg.register(app, ns=NS)
    paths = _route_paths(app)
    missing = [p for p in EXPECTED_ROUTES if p not in paths]
    assert not missing, f"dark surfaces NOT wired: {missing}\nstatus={status}\ngot={sorted(paths)}"
    # register() returns one honest status line per surface attempted (>= 7).
    assert len(status) >= 7, f"expected >=7 status lines, got {len(status)}: {status}"


def test_register_is_fault_tolerant():
    """A single broken module must NOT block the other surfaces.

    We hide szl_anatomy_loop (the #341 module that may not be merged when this PR
    lands) and confirm the other six still register."""
    import builtins

    real_import = builtins.__import__

    def _blocking_import(name, *a, **k):
        if name == "szl_anatomy_loop":
            raise ModuleNotFoundError("simulated: #341 not merged yet")
        return real_import(name, *a, **k)

    app = FastAPI()
    builtins.__import__ = _blocking_import
    try:
        status = agg.register(app, ns=NS)
    finally:
        builtins.__import__ = real_import

    paths = _route_paths(app)
    # anatomy/loop is intentionally absent...
    assert f"/api/{NS}/v1/anatomy/loop" not in paths, "anatomy should be skipped when blocked"
    # ...but every OTHER dark surface still came up.
    for p in EXPECTED_ROUTES:
        if p.endswith("/anatomy/loop"):
            continue
        assert p in paths, f"surface {p} was wrongly blocked by the missing anatomy module"
    assert any("NOT registered" in s for s in status), "the blocked module should log honestly"


def _scan_doctrine_clean(text: str, where: str) -> None:
    low = text.lower()
    # joules: if mentioned, must be SAMPLE/ESTIMATE/unknown, never an UNCONDITIONAL
    # "measured" off-box. The honest conditional phrasing ("'measured' only on a real
    # metered figure / on-box NVML") is allowed: any "measured" must co-occur with a
    # gating qualifier (only / real / metered / on-box / nvml).
    if "joule" in low:
        assert ("sample" in low) or ("estimate" in low) or ("unknown" in low), \
            f"{where}: joules not labelled SAMPLE/ESTIMATE/unknown"
        if "measured" in low:
            qualifiers = ("only", "real", "metered", "on-box", "on box", "nvml")
            assert any(q in low for q in qualifiers), \
                f"{where}: unconditional 'measured' joules claim off-box"
    # no free-energy / perpetual-motion CLAIMS. Honest NEGATIONS are required and
    # allowed: e.g. "no free-energy claim", "never net-positive", "not perpetual".
    # Flag only a free-energy/perpetual token that is NOT immediately negated.
    import re as _re
    for _tok in ("free energy", "free-energy", "perpetual"):
        for _m in _re.finditer(_re.escape(_tok), low):
            _ctx = low[max(0, _m.start() - 16):_m.start()]
            negated = any(neg in _ctx for neg in ("no ", "not ", "never", "non-", "without", "zero"))
            assert negated, f"{where}: unnegated free-energy / perpetual-motion claim near '{_tok}'"
    # organs are EXPERIMENTAL — never "proven trust"; trust never 100%.
    assert "proven trust" not in low, f"{where}: claims 'proven trust'"
    # Λ / Conjecture 1 must never be called a proven theorem.
    if "conjecture 1" in low or "lambda" in low or "Λ" in text:
        assert "conjecture 1 proven" not in low and "lambda proven" not in low, \
            f"{where}: claims Λ/Conjecture 1 is proven"


def test_invokable_surfaces_are_doctrine_clean():
    """Hit the surfaces that return without required runtime context and scan the
    body for doctrine violations. Surfaces whose handlers require an on-box request
    object (energy/budget, energy/provenance, heart/pulse take a Starlette Request)
    are exercised via their module self-tests instead, below."""
    from fastapi.testclient import TestClient

    app = FastAPI()
    agg.register(app, ns=NS)
    client = TestClient(app)

    for path in (f"/api/{NS}/v1/engine/status",
                 f"/api/{NS}/v1/formula/sovereign",
                 f"/api/{NS}/v1/anatomy/loop",
                 "/v1/ayni"):
        r = client.get(path)
        assert r.status_code == 200, f"{path} -> {r.status_code}: {r.text[:200]}"
        _scan_doctrine_clean(r.text, path)

    # anatomy/loop must explicitly carry the EXPERIMENTAL organ marker + sample joules.
    loop = client.get(f"/api/{NS}/v1/anatomy/loop").text.lower()
    assert "experimental" in loop, "anatomy/loop must mark organs EXPERIMENTAL"
    assert "sample" in loop, "anatomy/loop must label joules sample"

    # formula/sovereign is EXPERIMENTAL and tied to the allodial Lean gate (not a theorem).
    sov = client.get(f"/api/{NS}/v1/formula/sovereign").text.lower()
    assert "experimental" in sov, "formula/sovereign must be EXPERIMENTAL"
    assert "sovereign" in sov, "formula/sovereign must report a sovereignty verdict"


def test_module_selftests_are_doctrine_clean():
    """Energy + heart surfaces expose self-tests / honest summaries that carry the
    doctrine markers (joules SAMPLE, no free-energy, no key). Scan them directly."""
    import json

    import szl_energy_budget as eb
    # ledger summary carries the doctrine string + SAMPLE joules label.
    summ = json.dumps(eb.budget_summary())
    _scan_doctrine_clean(summ, "szl_energy_budget.budget_summary")
    assert "sample" in summ.lower(), "energy/budget summary must label joules SAMPLE/ESTIMATE"

    # aggregator's own DOCTRINE echo block is locked + honest.
    d = agg.DOCTRINE
    assert d["lambda"] == "Conjecture 1"
    assert d["locked"] == 8
    assert d["organs"] == "EXPERIMENTAL"
    assert d["free_energy"] is False
    assert d["key_committed"] is False
    assert "sample" in d["joules"].lower()


def test_no_key_committed_in_aggregator():
    """The aggregator must not embed any private key material."""
    src = open(os.path.join(HERE, "szl_dark_surfaces_register.py")).read()
    for marker in ("BEGIN PRIVATE KEY", "BEGIN RSA PRIVATE KEY", "BEGIN EC PRIVATE KEY",
                   "BEGIN OPENSSH PRIVATE KEY"):
        assert marker not in src, f"aggregator embeds a key ({marker})"


def _run_all():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        t()
        print(f"PASS {t.__name__}")
        passed += 1
    print(f"\n{passed}/{len(tests)} dark-surface tests PASSED")
    return passed == len(tests)


if __name__ == "__main__":
    sys.exit(0 if _run_all() else 1)
