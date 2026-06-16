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
  4b. tcp_connect_probe retry: a COLD node that times out attempt #1 but answers
      attempt #2 reads reachable=True (honest recovery); a node down on EVERY attempt
      stays unreachable (retry NEVER fabricates green); retries=0 == single attempt.
  4c. env-configurable timeout/retries (A11OY_GPU_PROBE_TIMEOUT_S / _RETRIES): read,
      clamped to safe bounds, and honest-default on a missing/garbage value.
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
        # retries=0 keeps the timing bound deterministic: one timeout window per node,
        # concurrent, not the serial sum. The retry path is covered separately below.
        payload = bh.probe_fabric_pool(timeout=1.5, cache=cache, force=True, retries=0)
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
        first = bh.probe_fabric_pool(timeout=1.5, cache=cache, force=True, retries=0)
        t0 = time.monotonic()
        second = bh.probe_fabric_pool(timeout=1.5, cache=cache)  # within TTL -> cached
        dt = time.monotonic() - t0
        assert dt < 0.05, f"cached call should be ~instant, took {dt:.3f}s (re-probed?)"
        assert second["cached_at"] == first["cached_at"], "cached call must return the same snapshot"
    finally:
        restore()


# ===========================================================================
# 4b. tcp_connect_probe retry — honest recovery of a COLD node, never fabricated.
#     A cold Windows Ollama frequently times out the FIRST connect then answers the
#     SECOND once the path is primed; one cheap retry recovers that. The retry NEVER
#     turns a genuinely-dead node green — every attempt is a fresh REAL connect.
# ===========================================================================
def test_retry_recovers_cold_node_that_answers_second_attempt():
    state = {"n": 0}

    def cold_then_up(host, port, timeout):
        state["n"] += 1
        return (False, "timeout") if state["n"] == 1 else (True, "tcp reachable")

    orig = bh._tcp_connect_once
    bh._tcp_connect_once = cold_then_up
    try:
        ok, detail = bh.tcp_connect_probe("1.2.3.4", 11434, 0.5, retries=1)
        assert ok is True, "a node that answers the 2nd connect must read reachable=True"
        assert detail == "tcp reachable"
        assert state["n"] == 2, "the retry must actually make a second real attempt"
    finally:
        bh._tcp_connect_once = orig


def test_retry_never_fabricates_a_dead_node_up():
    def always_down(host, port, timeout):
        return (False, "timeout")

    orig = bh._tcp_connect_once
    bh._tcp_connect_once = always_down
    try:
        ok, detail = bh.tcp_connect_probe("1.2.3.4", 11434, 0.5, retries=2)
        assert ok is False, "a node down on every attempt stays honestly unreachable"
        assert detail == "timeout"
    finally:
        bh._tcp_connect_once = orig


def test_retries_zero_is_single_attempt_previous_behaviour():
    state = {"n": 0}

    def count_down(host, port, timeout):
        state["n"] += 1
        return (False, "timeout")

    orig = bh._tcp_connect_once
    bh._tcp_connect_once = count_down
    try:
        bh.tcp_connect_probe("1.2.3.4", 11434, 0.5, retries=0)
        assert state["n"] == 1, "retries=0 must make exactly one connect (previous behaviour)"
    finally:
        bh._tcp_connect_once = orig


def test_fabric_payload_reports_retries_for_transparency():
    install, restore = _mock_sockets()
    install()
    try:
        payload = bh.probe_fabric_pool(timeout=1.0, cache=bh.TTLCache(ttl=30.0),
                                       force=True, retries=2)
        assert payload["probe_retries"] == 2, payload.get("probe_retries")
    finally:
        restore()


# ===========================================================================
# 4c. env-configurable timeout/retries — clamped, honest fail-safe on garbage.
# ===========================================================================
def test_env_timeout_is_read_clamped_and_failsafe():
    assert bh._env_float("A11OY_NOPE_TIMEOUT", 3.5, 0.25, 10.0) == 3.5
    os.environ["A11OY_TMP_T"] = "4.0"
    try:
        assert bh._env_float("A11OY_TMP_T", 3.5, 0.25, 10.0) == 4.0
        os.environ["A11OY_TMP_T"] = "999"   # operator typo must not hang the endpoint
        assert bh._env_float("A11OY_TMP_T", 3.5, 0.25, 10.0) == 10.0
        os.environ["A11OY_TMP_T"] = "garbage"
        assert bh._env_float("A11OY_TMP_T", 3.5, 0.25, 10.0) == 3.5
    finally:
        os.environ.pop("A11OY_TMP_T", None)


def test_env_retries_is_read_and_clamped():
    os.environ["A11OY_TMP_R"] = "9"
    try:
        assert bh._env_int("A11OY_TMP_R", 1, 0, 3) == 3
        os.environ["A11OY_TMP_R"] = "-5"
        assert bh._env_int("A11OY_TMP_R", 1, 0, 3) == 0
    finally:
        os.environ.pop("A11OY_TMP_R", None)


# ===========================================================================
# 5. _resolve_node_ip — alias + URL-env resolution closes the stale-IP bug.
#    The hardened pool used to fall back to the STALE static chaski IP because the
#    Replit chaski host is not literally named "chaski" on the tailnet. Now the
#    resolver consults the SAME URL env vars the plain /compute-pool uses, so the
#    two endpoints agree — WITHOUT hardcoding any IP.
# ===========================================================================
def _clear_node_env():
    for k in list(os.environ):
        if (k.startswith("A11OY_GPU_NODE_") or k.startswith("A11OY_CHASKI")
                or k.startswith("A11OY_OMEN") or k.startswith("A11OY_ENERGY_")
                or k in ("SZL_GOV_LLM_URL", "A11OY_MODEL_BASE_URL",
                         "A11OY_BETTERWITHAGE_BASE_URL", "A11OY_ANCHOR_PREFERENCE")):
            os.environ.pop(k, None)


def test_resolver_uses_url_env_so_hardened_agrees_with_plain_pool():
    _clear_node_env()
    try:
        # The plain /compute-pool resolves chaski via SZL_GOV_LLM_URL; the hardened
        # resolver must read the same var instead of the stale static fallback.
        os.environ["SZL_GOV_LLM_URL"] = "http://100.102.173.88:11434/api/generate"
        ip, src = bh._resolve_node_ip("chaski", "100.76.58.50")
        assert ip == "100.102.173.88", f"expected live chaski IP, got {ip} ({src})"
        assert src.startswith("env:"), src
    finally:
        _clear_node_env()


def test_resolver_omen_from_env():
    _clear_node_env()
    try:
        os.environ["A11OY_OMEN_BASE_URL"] = "http://100.70.130.45:11434"
        ip, src = bh._resolve_node_ip("omen-betterwithage", "100.70.130.45")
        assert ip == "100.70.130.45" and src.startswith("env:"), (ip, src)
    finally:
        _clear_node_env()


def test_resolver_static_fallback_is_honest_when_nothing_set():
    _clear_node_env()
    try:
        # No env, no tailscale here -> honest static fallback (the previous behaviour),
        # never an invented/empty IP.
        ip, src = bh._resolve_node_ip("chaski", "100.76.58.50")
        assert ip == "100.76.58.50" and src == "static-fallback", (ip, src)
    finally:
        _clear_node_env()


def test_resolver_ignores_router_placeholder_url():
    _clear_node_env()
    try:
        # An HF-router URL is not a real node IP — must NOT be used as the node's host.
        os.environ["A11OY_CHASKI_BASE_URL"] = "https://router.huggingface.co/v1"
        ip, src = bh._resolve_node_ip("chaski", "100.76.58.50")
        assert src == "static-fallback", (ip, src)
    finally:
        _clear_node_env()


# ===========================================================================
# 6. select_anchor_worker — OMEN-anchor preference, honest + never starves.
# ===========================================================================
def _pool(*states):
    """states: list of (name, kind, reachable, sovereign)."""
    return {"nodes": [
        {"name": n, "kind": k, "reachable": r, "sovereign": s, "endpoint": f"http://{n}:11434"}
        for (n, k, r, s) in states
    ], "cached_at": "test-ts"}


def test_anchor_prefers_omen_when_two_sovereign_gpus_live():
    _clear_node_env()
    pool = _pool(
        ("rtx-betterwithage", "sovereign-gpu", True, True),
        ("omen-betterwithage", "sovereign-gpu", True, True),
        ("chaski", "tailnet-gpu", False, False),
    )
    sel = bh.select_anchor_worker(pool, workload="szl-fast")
    assert sel["anchor"] == "omen-betterwithage", sel
    assert sel["fallback_used"] is False
    assert sel["anchor_sovereign"] is True
    assert set(sel["reachable_sovereign_gpus"]) == {"rtx-betterwithage", "omen-betterwithage"}


def test_anchor_falls_back_to_rtx_when_omen_down_never_starves():
    _clear_node_env()
    pool = _pool(
        ("rtx-betterwithage", "sovereign-gpu", True, True),
        ("omen-betterwithage", "sovereign-gpu", False, True),
        ("chaski", "tailnet-gpu", True, False),
    )
    sel = bh.select_anchor_worker(pool)
    # rtx is next in the default preference and reachable -> chosen, not a fallback.
    assert sel["anchor"] == "rtx-betterwithage", sel
    assert sel["fallback_used"] is False


def test_anchor_clean_fallback_to_any_reachable_gpu():
    _clear_node_env()
    # Only a non-preferred GPU is up -> clean fallback so the loop is not starved.
    pool = _pool(
        ("rtx-betterwithage", "sovereign-gpu", False, True),
        ("omen-betterwithage", "sovereign-gpu", False, True),
        ("chaski", "tailnet-gpu", True, False),
    )
    sel = bh.select_anchor_worker(pool)
    assert sel["anchor"] == "chaski", sel  # chaski IS in default preference (last)
    assert sel["fallback_used"] is False


def test_anchor_none_when_no_gpu_reachable_never_fabricated():
    _clear_node_env()
    pool = _pool(
        ("rtx-betterwithage", "sovereign-gpu", False, True),
        ("omen-betterwithage", "sovereign-gpu", False, True),
        ("chaski", "tailnet-gpu", False, False),
    )
    sel = bh.select_anchor_worker(pool)
    assert sel["anchor"] is None, "no reachable GPU -> anchor None, never fabricated up"
    assert sel["candidates_considered"] == 0


def test_anchor_preference_env_override():
    _clear_node_env()
    try:
        os.environ["A11OY_ANCHOR_PREFERENCE"] = "chaski,omen-betterwithage"
        pool = _pool(
            ("omen-betterwithage", "sovereign-gpu", True, True),
            ("chaski", "tailnet-gpu", True, False),
        )
        sel = bh.select_anchor_worker(pool)
        assert sel["anchor"] == "chaski", sel  # env preference puts chaski first
    finally:
        _clear_node_env()


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
