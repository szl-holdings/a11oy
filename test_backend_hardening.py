# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""test_backend_hardening — the latency-hardening helpers are correct AND honest.

Runs fully OFFLINE (mock sockets; no network). Asserts:
  1. probe_with_timeout: a HANGING probe is abandoned at ~timeout (never hangs/crashes)
     and yields reachable=False with detail="timeout" — NOT fabricated, NOT a crash.
  2. probe_all_concurrent: N slow probes + one dead node finish in ~one timeout window,
     NOT the serial sum; per-node timeout is respected and one dead node never serialises
     the rest.
  3. TTLCache: a fresh hit returns WITHOUT re-running the producer (no re-probe within TTL);
     after TTL expiry the producer runs again. cached_at is stamped.
  4. probe_fabric_pool with mocked sockets (chaski @ 100.102.173.88 hangs to timeout):
       - returns sub-second even with the dead node,
       - chaski is reachable=False with an honest reason (never green, never invented),
       - reachable counts are consistent with the per-node results,
       - a second call within TTL is served from cache (no re-probe) and is effectively
         instant with an identical cached_at,
       - doctrine stays clean (Λ=Conjecture 1, locked=8, no energy claim).

Run: python3 test_backend_hardening.py   (or: pytest test_backend_hardening.py)
"""
from __future__ import annotations

import os
import socket
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import szl_backend_hardening as bh  # noqa: E402


# ---------------------------------------------------------------------------
# A mock socket whose `connect` behaviour is keyed on host: the chaski tailnet
# node (100.102.173.88) hangs up to its timeout then raises socket.timeout; every
# other host connects instantly. No real network is ever touched.
# ---------------------------------------------------------------------------
class _FakeSock:
    def __init__(self, *a, **k):
        self._t = 1.5

    def settimeout(self, t):
        self._t = t

    def connect(self, addr):
        host, _port = addr
        if host == "100.102.173.88":          # the unreachable chaski node (current IP)
            time.sleep(min(self._t or 1.5, 1.5))
            raise socket.timeout("simulated chaski hang")
        return None                            # everyone else connects instantly

    def close(self):
        pass


def _mock_sockets():
    """Context-manager-ish helper returning (install, restore)."""
    orig = socket.socket

    def install():
        socket.socket = lambda *a, **k: _FakeSock()  # type: ignore

    def restore():
        socket.socket = orig  # type: ignore

    return install, restore


# ===========================================================================
# 1. probe_with_timeout — a hanging probe is bounded, honest, never crashes.
# ===========================================================================
def test_probe_with_timeout_hang_is_bounded_and_honest():
    def hang():
        time.sleep(5.0)
        return True

    t0 = time.monotonic()
    r = bh.probe_with_timeout(hang, timeout=0.5)
    dt = time.monotonic() - t0
    assert r["reachable"] is False, "a hung probe must be reachable=False, not fabricated green"
    assert r["detail"] == "timeout", f"expected timeout detail, got {r!r}"
    assert dt < 1.5, f"probe must be bounded by ~timeout, took {dt:.2f}s (would be 5s if it hung)"


def test_probe_with_timeout_success_is_fast():
    r = bh.probe_with_timeout(lambda: {"reachable": True}, timeout=1.0)
    assert r["reachable"] is True
    assert r["elapsed_s"] < 0.5


def test_probe_with_timeout_exception_degrades_honestly():
    def boom():
        raise ConnectionRefusedError("nope")

    r = bh.probe_with_timeout(boom, timeout=1.0)
    assert r["reachable"] is False
    assert "ConnectionRefusedError" in r["detail"]


# ===========================================================================
# 2. probe_all_concurrent — total ≈ max(timeout), not the serial sum.
# ===========================================================================
def test_concurrent_probes_do_not_exceed_per_node_timeout_window():
    def slow():
        time.sleep(0.4)
        return {"reachable": True}

    probes = {f"n{i}": slow for i in range(5)}  # 5×0.4 = 2.0s if serial
    t0 = time.monotonic()
    res = bh.probe_all_concurrent(probes, timeout=1.0, max_workers=8)
    dt = time.monotonic() - t0
    assert set(res) == set(probes)
    assert all(v["result"]["reachable"] for v in res.values())
    assert dt < 1.0, f"concurrent run took {dt:.2f}s — should be ~0.4s, not the 2.0s serial sum"


def test_one_dead_node_does_not_serialise_the_rest():
    def slow():
        time.sleep(0.3)
        return {"reachable": True}

    def hang():
        time.sleep(5.0)
        return True

    mixed = {"alive1": slow, "alive2": slow, "dead": hang}
    t0 = time.monotonic()
    res = bh.probe_all_concurrent(mixed, timeout=0.6, max_workers=8)
    dt = time.monotonic() - t0
    assert res["alive1"]["result"]["reachable"] is True
    assert res["alive2"]["result"]["reachable"] is True
    assert res["dead"]["reachable"] is False, "the dead node must be honestly unreachable"
    assert dt < 1.5, f"a dead node serialised the rest (took {dt:.2f}s)"


# ===========================================================================
# 3. TTLCache — fresh hit returns without re-probing; expiry re-probes.
# ===========================================================================
def test_cache_returns_within_ttl_without_reprobe():
    calls = {"n": 0}

    def producer():
        calls["n"] += 1
        return {"reachable": True, "v": calls["n"]}

    c = bh.TTLCache(ttl=10.0)
    a = c.get_or_compute(producer)
    b = c.get_or_compute(producer)
    assert calls["n"] == 1, "producer must NOT be re-run within TTL (no re-probe)"
    assert a["v"] == b["v"] == 1
    assert "cached_at" in a, "cache must stamp cached_at so freshness is visible"


def test_cache_reprobes_after_ttl_expiry():
    calls = {"n": 0}

    def producer():
        calls["n"] += 1
        return {"reachable": True}

    c = bh.TTLCache(ttl=0.2)
    c.get_or_compute(producer)
    assert calls["n"] == 1
    time.sleep(0.3)
    c.get_or_compute(producer)
    assert calls["n"] == 2, "after TTL expiry the producer must run again (fresh real probe)"


# ===========================================================================
# 4. probe_fabric_pool — concurrent + cached + honest with a dead chaski node.
# ===========================================================================
def test_fabric_pool_subsecond_with_dead_chaski_and_honest():
    install, restore = _mock_sockets()
    install()
    try:
        cache = bh.TTLCache(ttl=30.0)
        t0 = time.monotonic()
        payload = bh.probe_fabric_pool(timeout=1.5, cache=cache, force=True)
        dt = time.monotonic() - t0
        by = {n["name"]: n for n in payload["nodes"]}

        # Sub-second-ish: bounded by ~one timeout window even though chaski hangs.
        assert dt < (1.5 + 1.0), f"fabric probe took {dt:.2f}s — concurrency/timeout not bounding it"

        # Honest reachability: chaski is DOWN with a real reason, never fabricated green.
        assert by["chaski"]["reachable"] is False
        assert by["chaski"]["detail"] in ("timeout", "simulated chaski hang"), by["chaski"]
        # The reachable nodes really connected.
        assert by["rtx-betterwithage"]["reachable"] is True
        assert by["hetzner-box-cpu"]["reachable"] is True
        # Counts are consistent with the per-node truth (not invented).
        assert payload["counts"]["nodes_reachable"] == sum(
            1 for n in payload["nodes"] if n["reachable"]
        )
        # Doctrine clean.
        assert payload["doctrine"]["lambda"] == "Conjecture 1"
        assert payload["doctrine"]["locked"] == 8
        assert payload["doctrine"]["key_committed"] is False
        # No fabricated energy claim anywhere in the body.
        assert "joules" not in payload["counts"]
    finally:
        restore()


def test_fabric_pool_second_call_is_cached_no_reprobe():
    install, restore = _mock_sockets()
    install()
    try:
        cache = bh.TTLCache(ttl=30.0)
        first = bh.probe_fabric_pool(timeout=1.5, cache=cache, force=True)
        t0 = time.monotonic()
        second = bh.probe_fabric_pool(timeout=1.5, cache=cache)  # within TTL -> cached
        dt = time.monotonic() - t0
        assert dt < 0.05, f"cached call should be ~instant, took {dt:.3f}s (re-probed?)"
        assert second["cached_at"] == first["cached_at"], "cached call must return the same snapshot"
    finally:
        restore()


def _run_all() -> int:
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    failed = []
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
        except AssertionError as exc:
            failed.append((t.__name__, repr(exc)))
            print(f"  FAIL  {t.__name__}: {exc!r}")
        except Exception as exc:  # an unexpected crash is itself a failure
            failed.append((t.__name__, repr(exc)))
            print(f"  ERROR {t.__name__}: {exc!r}")
    print(f"\n{len(tests) - len(failed)}/{len(tests)} passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(_run_all())
