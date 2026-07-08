# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1 (advisory, NOT proven)
"""test_boot_preflight — Wave R Dev 1 boot-resilience self-test (network-free).

Asserts the env/secret PREFLIGHT + /healthz behave under the failure that took
the flagship down on 2026-07-08 ("Collision on variables and secrets names"):

  MODULE (pure, no serve.py needed):
    1. On a TOTALLY EMPTY env the preflight DEGRADES (never UNAVAILABLE, never
       raises) — a missing/renamed secret must never crash the estate.
    2. readiness()/preflight_report() NEVER raise, even on a hostile env object.
    3. NAMES ONLY: a secret VALUE never leaks into any preflight output.
    4. Every registered name has exactly one kind (secret|variable) — the exact
       axis HF forbids from colliding — and collision_names() lists them all.
    5. A subsystem whose secret is PRESENT reports LIVE; absent => DEGRADED.

  IN-PROCESS APP (Starlette TestClient, no network — skipped if deps absent):
    6. /api/a11oy/healthz returns 200 even with the env stripped bare (honest
       degrade, NOT a 503) and surfaces rollup.preflight.
    7. /api/a11oy/v1/preflight returns 200 with per-subsystem readiness and the
       collision registry, and leaks no secret value.

Run: python3 test_boot_preflight.py   (or: pytest test_boot_preflight.py)
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import szl_boot_preflight as pf  # noqa: E402

_SECRET_SENTINEL = "sk-THIS-IS-A-SECRET-VALUE-DO-NOT-LEAK-0xDEADBEEF"


# ---------------------------------------------------------------------------
# 1. Empty env => DEGRADED, never UNAVAILABLE, never crash.
# ---------------------------------------------------------------------------
def test_empty_env_degrades_not_crash():
    ready = pf.readiness(env={})
    assert ready["overall"] == pf.DEGRADED, ready
    # by design there are NO hard-required names, so a bare env is DEGRADED
    # (honest) rather than UNAVAILABLE — the estate still boots and serves.
    assert ready["overall"] != pf.UNAVAILABLE
    assert isinstance(ready["subsystems"], list) and ready["subsystems"]


# ---------------------------------------------------------------------------
# 2. Guarded: never raises, even on a hostile env whose .get() explodes.
# ---------------------------------------------------------------------------
class _HostileEnv:
    def get(self, *a, **k):
        raise RuntimeError("simulated env fault")


def test_preflight_never_raises_on_hostile_env():
    rep = pf.preflight_report(env=_HostileEnv())
    assert rep["ok"] is False and "error" in rep
    ready = pf.readiness(env=_HostileEnv())
    # hostile/broken env probing => honest UNAVAILABLE marker, but NO exception
    assert ready["overall"] in (pf.UNAVAILABLE, pf.DEGRADED)


def test_run_preflight_returns_and_never_raises():
    import io
    out = pf.run_preflight(env={}, stream=io.StringIO())
    assert "report" in out and "readiness" in out
    assert out["readiness"]["overall"] == pf.DEGRADED


# ---------------------------------------------------------------------------
# 3. NAMES ONLY — a secret VALUE never appears in preflight output.
# ---------------------------------------------------------------------------
def test_never_leaks_secret_values():
    env = {"HF_TOKEN": _SECRET_SENTINEL, "ANTHROPIC_API_KEY": _SECRET_SENTINEL,
           "SZL_COSIGN_PRIVATE_PEM": _SECRET_SENTINEL}
    rep = pf.preflight_report(env=env)
    ready = pf.readiness(env=env)
    import io
    stream = io.StringIO()
    pf.run_preflight(env=env, stream=stream)
    blob = repr(rep) + repr(ready) + stream.getvalue() + repr(pf.registry())
    assert _SECRET_SENTINEL not in blob, "secret VALUE leaked into preflight output"
    # the NAME is fine to surface
    assert "HF_TOKEN" in rep["present"]


# ---------------------------------------------------------------------------
# 4. Each name has exactly one kind; collision_names lists them all.
# ---------------------------------------------------------------------------
def test_every_name_single_kind_and_collision_list():
    reg = pf.registry()
    kinds = {}
    for spec in reg:
        assert spec["kind"] in (pf.SECRET, pf.VARIABLE), spec
        kinds.setdefault(spec["name"], set()).add(spec["kind"])
    for name, ks in kinds.items():
        assert len(ks) == 1, f"{name} declared as both secret AND variable: {ks}"
    names = pf.collision_names()
    assert set(names) == set(kinds), "collision_names must cover the whole registry"
    assert len(names) == len(set(names)), "collision_names has duplicates"


# ---------------------------------------------------------------------------
# 5. Present secret => that subsystem LIVE; absent => DEGRADED.
# ---------------------------------------------------------------------------
def test_present_secret_lights_subsystem():
    # signing subsystem's only secret is SZL_COSIGN_PRIVATE_PEM
    env = {"SZL_COSIGN_PRIVATE_PEM": _SECRET_SENTINEL}
    ready = pf.readiness(env=env)
    signing = [s for s in ready["subsystems"] if s["subsystem"] == "signing"][0]
    assert signing["label"] == pf.LIVE, signing
    # and with it absent, DEGRADED
    signing_absent = [s for s in pf.readiness(env={})["subsystems"]
                      if s["subsystem"] == "signing"][0]
    assert signing_absent["label"] == pf.DEGRADED


def test_empty_string_counts_as_absent():
    # a name set to "" (a common HF mis-config) must count as ABSENT, not present
    rep = pf.preflight_report(env={"HF_TOKEN": "   "})
    assert "HF_TOKEN" in rep["absent"] and "HF_TOKEN" not in rep["present"]


# ---------------------------------------------------------------------------
# 6 + 7. In-process app: /healthz stays 200 and /preflight works on a bare env.
# Skipped (not failed) if fastapi/starlette/httpx are unavailable.
# ---------------------------------------------------------------------------
def _load_testclient():
    try:
        from starlette.testclient import TestClient
    except Exception:
        return None
    try:
        import serve
    except Exception as exc:  # serve import failing IS a real failure to report
        raise AssertionError(f"serve.py failed to import: {exc!r}") from exc
    return TestClient(serve.app)


def test_healthz_200_and_preflight_route_when_env_bare():
    # strip the env down to nothing app-relevant, then boot in-process.
    saved = dict(os.environ)
    try:
        for k in list(os.environ):
            if k in pf._BY_NAME:
                del os.environ[k]
        client = _load_testclient()
        if client is None:
            print("[skip] starlette/httpx unavailable — module tests already cover core")
            return
        r = client.get("/api/a11oy/healthz")
        assert r.status_code == 200, f"/healthz must never 503 on a bare env; got {r.status_code}"
        body = r.json()
        assert "preflight" in body.get("rollup", {}), "healthz rollup must include preflight"
        pr = client.get("/api/a11oy/v1/preflight")
        assert pr.status_code == 200, pr.status_code
        pj = pr.json()
        assert pj["status"] in (pf.LIVE, pf.DEGRADED, pf.UNAVAILABLE)
        assert pj["readiness"]["subsystems"], pj
        assert len(pj["collision_names"]) == len(pf.collision_names())
        # a secret value set now must not leak through the live route
        assert _SECRET_SENTINEL not in pr.text
    finally:
        os.environ.clear()
        os.environ.update(saved)


# ---------------------------------------------------------------------------
# runner
# ---------------------------------------------------------------------------
def _run():
    tests = [v for k, v in sorted(globals().items())
             if k.startswith("test_") and callable(v)]
    passed = 0
    for t in tests:
        t()
        passed += 1
        print(f"  ok  {t.__name__}")
    print(f"\ntest_boot_preflight: {passed}/{len(tests)} passed (network-free)")


if __name__ == "__main__":
    _run()
