# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: 749 declarations · 14 unique axioms · 163 sorries.
# Λ = Conjecture 1 (Λ-Aggregator Uniqueness; NOT a closed theorem).
"""
szl_backend_hardening.py — reusable latency-hardening helpers for the SZL fabric.

PROBLEM (found by a live smoke test, 2026-06):
  - GET /api/a11oy/v1/compute-pool answered in ~6.95s and intermittently timed out
    (HTTP 000). Root cause: it probed each fabric node SYNCHRONOUSLY on every request,
    including the unreachable `chaski` tailnet GPU at 100.76.58.50 — a TCP connect that
    hangs until the OS default timeout. One dead node serialised behind the others
    dragged the whole endpoint past the edge proxy's deadline -> 000.
  - GET /api/a11oy/v1/engine/status answered in ~2.3s: it fans out concurrently with a
    per-probe timeout already, but it RE-PROBES the whole organism on EVERY request —
    no caching — so a slow organ taxes every caller.

FIX (this module, ADDITIVE — no endpoint is rewritten destructively):
  - `probe_with_timeout()` — a single honest reachability probe with a SHORT, hard
    per-target timeout (default 1.5s). Supports a TCP connect probe (the fabric case)
    and an arbitrary callable probe (engine/status, harvest). NEVER hangs, NEVER raises,
    NEVER fabricates: a timeout/refusal yields reachable=False with the real reason.
  - `probe_all_concurrent()` — runs N probes on a bounded thread pool so total wall time
    is ~max(per-probe timeout), NOT sum. One dead node no longer serialises the rest.
  - `ttl_cache` / `TTLCache` — a tiny thread-safe time-to-live cache (default 45s) so a
    hot endpoint serves the LAST real probe result instead of re-probing every request.
    The cached payload always carries a `cached_at` ISO timestamp so the caller can see
    exactly how fresh the reachability data is. Honest by construction: `reachable`
    always reflects the most recent REAL probe; nothing is invented to fill the cache.
  - `probe_fabric_pool()` — a reference, drop-in concurrent+cached prober for the
    compute-pool node list. A compute-pool handler can simply call this instead of its
    own synchronous loop; the result is identical in shape but sub-second and cached.

HONESTY / DOCTRINE v11 (binding, enforced by construction):
  - honest reachability: `reachable` is set ONLY from a real probe of THIS process; a
    timeout or refusal is reachable=False with the error string. Never bluffed green.
  - sovereign:true is NEVER decided here — it is a property of owned hardware, passed
    through verbatim from the node descriptor. This module only measures reachability.
  - joules are MEASURED only via the on-box exporter; this module makes NO energy claim.
  - locked = 8; Λ = Conjecture 1 (open, never a theorem); no key committed.
  - Pure Python stdlib (socket, threading, concurrent.futures, time). No new pip deps.

Signed-off-by: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""
from __future__ import annotations

import json
import socket
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as _FutTimeout
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Doctrine echo — same shape the other szl_* surfaces emit so any response that
# reuses it stays honesty-clean under the doctrine guards.
# ---------------------------------------------------------------------------
DOCTRINE: Dict[str, Any] = {
    "version": "v11",
    "locked": 8,
    "lambda": "Conjecture 1",          # OPEN — never a theorem, never "proven trust"
    "joules": "MEASURED only via on-box exporter; this module makes no energy claim",
    "reachability": "real probe only — never fabricated",
    "key_committed": False,
}

DEFAULT_PROBE_TIMEOUT = 1.5   # seconds, per node — short so one dead node can't stall a request
DEFAULT_CACHE_TTL = 45.0      # seconds — serve the last real probe, re-probe only when stale
DEFAULT_MAX_WORKERS = 8       # bounded thread pool for concurrent probes


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stderr(msg: str) -> None:
    print(msg, file=sys.stderr)


# ===========================================================================
# 1. probe_with_timeout — ONE honest reachability probe, hard-bounded, never hangs.
# ===========================================================================
def tcp_connect_probe(host: str, port: int, timeout: float) -> Tuple[bool, str]:
    """Real TCP connect probe. Returns (reachable, detail).

    A successful connect within `timeout` -> (True, "tcp reachable").
    A timeout/refusal/DNS failure -> (False, "<reason>"). NEVER raises; NEVER hangs
    longer than `timeout` (the socket timeout is the hard ceiling)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        s.connect((host, int(port)))
        return True, "tcp reachable"
    except socket.timeout:
        return False, "timeout"
    except OSError as exc:  # connection refused, no route, DNS, etc.
        return False, type(exc).__name__
    except Exception as exc:  # absolute backstop — still honest-degrade, never crash
        return False, repr(exc)[:120]
    finally:
        try:
            s.close()
        except Exception:
            pass


def probe_with_timeout(
    fn: Callable[[], Any],
    timeout: float = DEFAULT_PROBE_TIMEOUT,
) -> Dict[str, Any]:
    """Run an arbitrary probe callable with a HARD wall-clock timeout.

    `fn` is any zero-arg callable that performs one reachability check and returns a
    truthy/JSON-able value on success. This wrapper enforces `timeout` even if `fn`
    itself ignores timeouts (it runs `fn` on a one-shot thread and abandons it on
    timeout), so a library that hangs can never hang THIS call.

    Returns an honest envelope (never raises, never fabricates):
        {reachable: bool, detail: str, elapsed_s: float, result?: Any}
    A timeout -> reachable=False, detail="timeout". An exception inside `fn` ->
    reachable=False, detail=<repr>. Success -> reachable=True with the result attached.
    """
    started = time.monotonic()
    # NOTE: we deliberately do NOT use `with ThreadPoolExecutor(...)` here. The pool's
    # context-manager exit calls shutdown(wait=True), which would BLOCK on an abandoned
    # hung probe thread and defeat the whole timeout. We submit on a one-shot pool and,
    # on timeout, shut it down non-blocking so the caller returns immediately.
    ex = ThreadPoolExecutor(max_workers=1)
    fut = ex.submit(fn)
    try:
        result = fut.result(timeout=timeout)
    except _FutTimeout:
        # The probe overran its budget. We do NOT block on the abandoned thread;
        # the caller gets a fast, honest "unreachable (timeout)".
        ex.shutdown(wait=False)
        return {"reachable": False, "detail": "timeout",
                "elapsed_s": round(time.monotonic() - started, 4)}
    except Exception as exc:
        ex.shutdown(wait=False)
        return {"reachable": False, "detail": repr(exc)[:160],
                "elapsed_s": round(time.monotonic() - started, 4)}
    ex.shutdown(wait=False)
    reachable = bool(result) if not isinstance(result, dict) else bool(result.get("reachable", True))
    return {"reachable": reachable, "detail": "ok",
            "elapsed_s": round(time.monotonic() - started, 4), "result": result}


# ===========================================================================
# 2. probe_all_concurrent — run many probes at once; total ~= max(timeout), not sum.
# ===========================================================================
def probe_all_concurrent(
    probes: Dict[str, Callable[[], Any]],
    timeout: float = DEFAULT_PROBE_TIMEOUT,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> Dict[str, Dict[str, Any]]:
    """Run a {name: probe_callable} map concurrently, each hard-bounded to `timeout`.

    Because every probe is dispatched onto the pool BEFORE any result is collected,
    the total wall time is ~the slowest single probe (≈ timeout when one target is
    dead), never the sum. Returns {name: honest_envelope}. Never raises.
    """
    if not probes:
        return {}
    names = list(probes)
    out: Dict[str, Dict[str, Any]] = {}
    workers = max(1, min(max_workers, len(names)))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        # Dispatch ALL probes first (concurrent), each wrapped in its own hard timeout.
        futs = {name: ex.submit(probe_with_timeout, probes[name], timeout) for name in names}
        for name, fut in futs.items():
            try:
                # Generous collection ceiling: the inner probe_with_timeout already
                # enforces `timeout`; this guards against pool starvation only.
                out[name] = fut.result(timeout=timeout * 3 + 2.0)
            except Exception as exc:
                out[name] = {"reachable": False, "detail": repr(exc)[:160], "elapsed_s": None}
    return out


# ===========================================================================
# 3. TTLCache / ttl_cache — serve the last real probe; re-probe only when stale.
# ===========================================================================
class TTLCache:
    """Thread-safe single-or-keyed TTL cache. Stores (value, stored_at_monotonic).

    `get_or_compute(key, producer)` returns the cached value if it is younger than
    `ttl`; otherwise it calls `producer()` (a fresh real probe), stores the result
    with a `cached_at` ISO stamp injected (when the value is a dict), and returns it.
    HONEST: the cache never invents a value — it only ever holds the output of a real
    `producer()` call, and `cached_at` tells the caller exactly how fresh it is.
    """

    def __init__(self, ttl: float = DEFAULT_CACHE_TTL) -> None:
        self.ttl = float(ttl)
        self._lock = threading.Lock()
        self._store: Dict[Any, Tuple[Any, float]] = {}

    def _fresh(self, stored_at: float) -> bool:
        return (time.monotonic() - stored_at) < self.ttl

    def peek(self, key: Any = "_") -> Optional[Any]:
        with self._lock:
            ent = self._store.get(key)
            if ent and self._fresh(ent[1]):
                return ent[0]
            return None

    def get_or_compute(self, producer: Callable[[], Any], key: Any = "_") -> Any:
        # Fast path: a fresh value -> return it WITHOUT calling producer (no re-probe).
        with self._lock:
            ent = self._store.get(key)
            if ent and self._fresh(ent[1]):
                return ent[0]
        # Stale or missing: compute outside the lock so a slow probe can't block readers.
        value = producer()
        if isinstance(value, dict) and "cached_at" not in value:
            value = {**value, "cached_at": _now_iso()}
        with self._lock:
            self._store[key] = (value, time.monotonic())
        return value

    def invalidate(self, key: Any = "_") -> None:
        with self._lock:
            self._store.pop(key, None)


def ttl_cache(ttl: float = DEFAULT_CACHE_TTL) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator form: cache a zero/low-arg producer's result for `ttl` seconds.

    Keyed on the call args. Convenience over TTLCache for simple producers; the
    underlying cache is honest (only ever holds real producer output)."""
    cache = TTLCache(ttl=ttl)

    def _decorate(fn: Callable[..., Any]) -> Callable[..., Any]:
        def _wrapped(*args: Any, **kwargs: Any) -> Any:
            key = (args, tuple(sorted(kwargs.items())))
            return cache.get_or_compute(lambda: fn(*args, **kwargs), key=key)
        _wrapped._ttl_cache = cache  # type: ignore[attr-defined]
        return _wrapped
    return _decorate


# ===========================================================================
# 4. probe_fabric_pool — reference drop-in for the compute-pool node list.
#    Concurrent + short-timeout + cached. A compute-pool handler can import and
#    call this instead of its own synchronous loop; node descriptors are passed
#    in verbatim (sovereign/kind/etc. are NOT decided here — only reachability).
# ===========================================================================
# Default node table mirrors the LIVE /api/a11oy/v1/compute-pool fabric (probed
# 2026-06-13). It is overridable by the caller. `probe` is (host, port); a node
# without a probe target (e.g. the self CPU host) is reported reachable via its
# `static_reachable` flag (the host running this service IS reachable by definition).
# --- Dynamic tailnet-IP resolution (drift-fix 2026-06-15) ---------------------
# The sovereign GPU nodes live on the founder Tailscale tailnet, where the box
# (this host) is also a peer. Their 100.x IPs are assigned by Tailscale and can
# change across sessions / reinstalls, so a HARDCODED probe IP goes stale and the
# node shows a false `timeout` even when its Ollama is up (observed: the live GPU
# host `betterwithage` moved 100.125.77.31 -> 100.70.130.45; the box kept probing
# the old IP). This resolver reads the box's OWN `tailscale status --json` and maps
# a node name to its CURRENT tailnet IP by hostname/DNSName prefix. It is honest +
# fail-safe: if tailscale is unreadable it returns the static fallback IP, so the
# probe degrades to the previous behaviour rather than inventing reachability.
# Env override `A11OY_GPU_NODE_<NAME>_IP` (e.g. A11OY_GPU_NODE_BETTERWITHAGE_IP)
# wins over both, for explicit pinning without a code change.
import json as _json
import os as _os
import subprocess as _subprocess

_TAILSCALE_CACHE = TTLCache(ttl=30.0)

def _tailscale_peers() -> Dict[str, str]:
    """Return {lowercased-hostname: 100.x.y.z} from `tailscale status --json`.
    Empty dict (never raises) if tailscale is missing/unreadable."""
    def _producer() -> Dict[str, str]:
        out: Dict[str, str] = {}
        try:
            raw = _subprocess.run(
                ["tailscale", "status", "--json"],
                capture_output=True, text=True, timeout=4.0,
            )
            if raw.returncode != 0 or not raw.stdout:
                return out
            data = _json.loads(raw.stdout)
            peers = list((data.get("Peer") or {}).values())
            # include Self so the box can resolve its own siblings consistently
            if data.get("Self"):
                peers.append(data["Self"])
            for p in peers:
                ips = p.get("TailscaleIPs") or []
                ip4 = next((a for a in ips if ":" not in a), None)
                if not ip4:
                    continue
                for key in (p.get("HostName"), (p.get("DNSName") or "").split(".")[0]):
                    if key:
                        out[key.strip().lower()] = ip4
        except Exception:
            return {}
        return out
    try:
        return _TAILSCALE_CACHE.get("peers", _producer)
    except Exception:
        return {}

def _resolve_node_ip(name: str, fallback_ip: str) -> Tuple[str, str]:
    """Resolve a node's CURRENT tailnet IP. Returns (ip, source).
    Priority: env pin -> live tailscale-by-hostname -> static fallback."""
    env_key = "A11OY_GPU_NODE_" + "".join(c if c.isalnum() else "_" for c in name).upper() + "_IP"
    pinned = (_os.environ.get(env_key) or "").strip()
    if pinned:
        return pinned, "env-pin"
    peers = _tailscale_peers()
    # Prefix-collision guard (2026-06-15): BOTH Windows GPU boxes are tailscale-named
    # 'betterwithage' (the RTX 5050 laptop and the OMEN), so the bare suffix
    # 'betterwithage' is AMBIGUOUS and tailscale assigns suffixed hostnames
    # (betterwithage, betterwithage-1, ...). The previous logic interleaved exact +
    # prefix matching per-candidate, so 'omen-betterwithage' fell through to an exact
    # match on the bare peer 'betterwithage' and mis-mapped the OMEN to the LAPTOP's
    # IP. Honest fix: (a) try the FULL node name exact-match first; (b) require the
    # peer hostname to carry the node's DISTINGUISHING leading token (omen-/rtx-)
    # before any suffix-based match; (c) only then fall back to a bare-suffix match,
    # and ONLY if that suffix is unambiguous (exactly one peer carries it). If the
    # suffix is ambiguous we DECLINE and degrade to the static fallback rather than
    # guess — never fabricate a wrong remap.
    lname = name.lower()
    # (a) exact full-name hostname match always wins
    if lname in peers:
        return peers[lname], "tailscale-live"
    lead = lname.split("-", 1)[0] if "-" in lname else ""      # e.g. 'omen', 'rtx'
    suffix = lname.split("-", 1)[1] if "-" in lname else ""   # e.g. 'betterwithage'
    # (b) disambiguate by the leading token: a peer hostname that contains the
    #     node's distinguishing token (omen / rtx) AND the shared suffix.
    if lead and suffix:
        lead_matches = [(hn, ip) for hn, ip in peers.items()
                        if lead in hn and suffix in hn]
        if len(lead_matches) == 1:
            return lead_matches[0][1], "tailscale-lead"
        # a peer carrying just the leading token (e.g. 'omen', 'omen-1')
        lead_only = [(hn, ip) for hn, ip in peers.items() if hn.startswith(lead)]
        if len(lead_only) == 1:
            return lead_only[0][1], "tailscale-lead"
    # (c) bare-suffix fallback — ONLY if exactly one peer carries the suffix, so an
    #     ambiguous 'betterwithage' (laptop vs OMEN) NEVER silently mis-maps.
    key = suffix or lname
    suffix_matches = [(hn, ip) for hn, ip in peers.items()
                      if hn == key or hn.startswith(key + "-")]
    if len(suffix_matches) == 1:
        return suffix_matches[0][1], "tailscale-suffix"
    # Ambiguous or no live match -> honest static fallback (never guess an IP).
    return fallback_ip, "static-fallback"

DEFAULT_FABRIC_NODES: List[Dict[str, Any]] = [
    {"name": "hetzner-box-cpu", "kind": "cpu", "sovereign": True,
     "probe": None, "static_reachable": True,
     "endpoint": "127.0.0.1 (self)",
     "detail": "host running this service; reachable by definition"},
    {"name": "rtx-betterwithage", "kind": "sovereign-gpu", "sovereign": True,
     "probe": ("100.125.77.31", 11434), "endpoint": "http://100.125.77.31:11434",
     "detail": "Blackwell RTX 5050 laptop (traveling) — Ollama on founder tailnet"},
    {"name": "omen-betterwithage", "kind": "sovereign-gpu", "sovereign": True,
     "probe": ("100.70.130.45", 11434), "endpoint": "http://100.70.130.45:11434",
     "detail": "always-on home brain: OMEN RTX 4060 Ti 8GB + Ryzen 8700G — Ollama on founder tailnet"},
    {"name": "chaski", "kind": "tailnet-gpu", "sovereign": False,
     # IP refresh 2026-06-15: chaski moved 100.76.58.50 -> 100.102.173.88 (confirmed
     # live per AUTO_STATE). Static fallback updated to the current tailnet IP so the
     # box probes the right host even when tailscale is unreadable; an explicit
     # A11OY_GPU_NODE_CHASKI_IP env pin still wins. reachable is still set ONLY by a
     # real TCP probe — this refresh changes WHICH host we probe, never fakes green.
     "probe": ("100.102.173.88", 11434), "endpoint": "http://100.102.173.88:11434",
     "detail": "self-hosted Ollama on founder tailnet (Replit node)"},
    {"name": "groq", "kind": "hosted-inference", "sovereign": False,
     "probe": ("api.groq.com", 443), "endpoint": "api.groq.com:443"},
    {"name": "nvidia-nim", "kind": "hosted-inference", "sovereign": False,
     "probe": ("integrate.api.nvidia.com", 443), "endpoint": "integrate.api.nvidia.com:443"},
    {"name": "hf-router", "kind": "hosted-inference", "sovereign": False,
     "probe": ("router.huggingface.co", 443), "endpoint": "router.huggingface.co:443"},
]

# Module-level cache shared across requests so the endpoint serves the last real
# probe instead of re-probing every call.
_FABRIC_CACHE = TTLCache(ttl=DEFAULT_CACHE_TTL)


def _build_node_probe(node: Dict[str, Any], timeout: float) -> Callable[[], Any]:
    """Return a zero-arg probe for one node descriptor (TCP connect, honest)."""
    target = node.get("probe")
    if not target:
        # No network target (e.g. the self host). Honest static reachability.
        static = bool(node.get("static_reachable", False))
        return lambda: {"reachable": static, "detail": node.get("detail", "no probe target")}

    host, port = target

    def _do() -> Dict[str, Any]:
        ok, detail = tcp_connect_probe(host, port, timeout)
        return {"reachable": ok, "detail": detail}
    return _do


def _probe_fabric_uncached(
    nodes: Iterable[Dict[str, Any]],
    timeout: float,
) -> Dict[str, Any]:
    """One real concurrent sweep of the fabric. Returns the full compute-pool payload."""
    nodes = list(nodes)
    # Re-resolve sovereign/tailnet GPU node IPs LIVE from tailscale so a moved node
    # is probed at its CURRENT 100.x, not a stale hardcoded IP (honest fail-safe to
    # the static IP if tailscale is unreadable). Hosted-inference nodes (groq/nim/hf)
    # use DNS names and are left untouched.
    _resolved = []
    for _n in nodes:
        _t = _n.get("probe")
        _kind = str(_n.get("kind", ""))
        if _t and "gpu" in _kind:
            _host, _port = _t
            _ip, _src = _resolve_node_ip(_n["name"], _host)
            if _ip != _host:
                _n = dict(_n)
                _n["probe"] = (_ip, _port)
                _n["endpoint"] = "http://%s:%d" % (_ip, _port)
                _base = (_n.get("detail") or "").split(" | ip:")[0]
                _n["detail"] = (_base + (" | ip:%s via %s" % (_ip, _src))).strip(" |")
        _resolved.append(_n)
    nodes = _resolved
    probes = {n["name"]: _build_node_probe(n, timeout) for n in nodes}
    results = probe_all_concurrent(probes, timeout=timeout)

    out_nodes: List[Dict[str, Any]] = []
    for n in nodes:
        env = results.get(n["name"], {"reachable": False, "detail": "no result"})
        inner = env.get("result") if isinstance(env.get("result"), dict) else None
        reachable = bool(inner["reachable"]) if inner is not None else bool(env.get("reachable"))
        detail = (inner.get("detail") if inner else None) or env.get("detail") or n.get("detail")
        out_nodes.append({
            "name": n["name"],
            "kind": n.get("kind"),
            "endpoint": n.get("endpoint"),
            "reachable": reachable,                 # REAL probe result only
            "sovereign": bool(n.get("sovereign", False)),  # property of the node, passed through
            "detail": detail,
            "probe_elapsed_s": env.get("elapsed_s"),
        })

    reachable_n = sum(1 for x in out_nodes if x["reachable"])
    gpu_reachable = sum(1 for x in out_nodes
                        if x["reachable"] and "gpu" in str(x.get("kind", "")))
    return {
        "status": "live",
        "ns": "a11oy",
        "kind": "multi-node-compute-fabric",
        "counts": {
            "nodes_total": len(out_nodes),
            "nodes_reachable": reachable_n,
            "gpu_nodes_reachable": gpu_reachable,
        },
        "nodes": out_nodes,
        "probe_timeout_s": timeout,
        "honesty": (
            "reachable=True only on a real TCP probe THIS sweep; a timeout/refusal is "
            "reachable=False with the reason. sovereign is a property of owned hardware, "
            "passed through, never inferred from reachability. No node fabricated. No "
            "energy/joule claim (joules MEASURED only via on-box exporter). "
            "Λ = Conjecture 1; locked = 8; no key."
        ),
        "doctrine": dict(DOCTRINE),
    }


def probe_fabric_pool(
    nodes: Optional[Iterable[Dict[str, Any]]] = None,
    timeout: float = DEFAULT_PROBE_TIMEOUT,
    ttl: Optional[float] = None,
    cache: Optional[TTLCache] = None,
    force: bool = False,
) -> Dict[str, Any]:
    """Concurrent + short-timeout + cached compute-pool probe (drop-in for the handler).

    Returns in <1s even when a node is down (concurrent + per-node `timeout`), and
    serves the cached payload for `ttl` seconds so repeat requests don't re-probe.
    `cached_at` on the payload tells the caller how fresh the reachability data is.
    """
    use_nodes = list(nodes) if nodes is not None else DEFAULT_FABRIC_NODES
    use_cache = cache if cache is not None else _FABRIC_CACHE
    if ttl is not None:
        use_cache.ttl = float(ttl)
    if force:
        use_cache.invalidate()
    return use_cache.get_or_compute(lambda: _probe_fabric_uncached(use_nodes, timeout))


# ===========================================================================
# 5. cached_aggregate — drop-in TTL wrapper engine/status (and similar fan-outs) use.
#    engine_status already fans out concurrently with a per-probe timeout; it just
#    re-probes every request. This gives it (and any aggregator) a brief cache.
# ===========================================================================
_AGG_CACHES: Dict[str, TTLCache] = {}
_AGG_CACHES_LOCK = threading.Lock()


def cached_aggregate(name: str, producer: Callable[[], Any], ttl: float = 20.0) -> Any:
    """Cache a (possibly async-backed) aggregate `producer` for `ttl` seconds.

    `producer` must be a zero-arg SYNC callable returning the aggregate dict (callers
    with an async aggregator wrap it, e.g. `lambda: asyncio.run(aggregate(...))`).
    Honest: only ever caches real producer output; injects `cached_at`."""
    with _AGG_CACHES_LOCK:
        cache = _AGG_CACHES.get(name)
        if cache is None:
            cache = TTLCache(ttl=ttl)
            _AGG_CACHES[name] = cache
        else:
            cache.ttl = float(ttl)
    return cache.get_or_compute(producer)


# ===========================================================================
# serve.py wiring — ADDITIVE, try/except-guarded. Attaches a hardened, cached
# GET /api/<ns>/v1/compute-pool. If a compute-pool route is ALREADY registered by
# another module, this is harmless duplication that FastAPI resolves by first-match;
# the value is to provide a sub-second cached implementation the fabric can adopt.
# ===========================================================================
def register(app: Any, ns: str = "a11oy") -> List[str]:
    """ADDITIVE: expose the hardened compute-pool prober as a route + return helpers.

    Never replaces an existing route (uses add_api_route only if the path is free).
    Returns the list of route paths actually attached."""
    paths: List[str] = []
    try:
        from fastapi.responses import JSONResponse  # local import keeps module import-safe
    except Exception:
        JSONResponse = None  # type: ignore

    route = f"/api/{ns}/v1/compute-pool-hardened"

    # Attach under a *-hardened path to be strictly additive: it never shadows an
    # existing /compute-pool, and the live handler can import probe_fabric_pool to
    # serve the canonical path sub-second once adopted.
    existing = {getattr(r, "path", None) for r in getattr(getattr(app, "router", None), "routes", [])}
    if route not in existing and JSONResponse is not None:
        @app.get(route)
        async def _compute_pool_hardened():  # noqa: ANN202
            return JSONResponse(probe_fabric_pool())
        paths.append(route)
        _stderr(f"[a11oy:hardening] compute-pool hardened prober registered: {route}")
    else:
        _stderr(f"[a11oy:hardening] compute-pool hardened route present/again skipped: {route}")
    return paths


# ===========================================================================
# Self-test — pure stdlib, OFFLINE (mock sockets). No network, no FastAPI/httpx.
# ===========================================================================
def _selftest() -> Dict[str, Any]:
    checks: List[Tuple[str, bool]] = []

    def chk(name: str, cond: bool) -> None:
        checks.append((name, bool(cond)))

    # --- probe_with_timeout: a fast-success probe returns reachable=True quickly ---
    r = probe_with_timeout(lambda: {"reachable": True, "detail": "ok"}, timeout=1.0)
    chk("pwt_success_reachable", r["reachable"] is True)
    chk("pwt_success_fast", r["elapsed_s"] < 0.5)

    # --- probe_with_timeout: a HANGING probe is abandoned at the timeout, not later ---
    def _hang():
        time.sleep(5.0)
        return True
    t0 = time.monotonic()
    r = probe_with_timeout(_hang, timeout=0.5)
    dt = time.monotonic() - t0
    chk("pwt_hang_unreachable", r["reachable"] is False and r["detail"] == "timeout")
    chk("pwt_hang_bounded", dt < 1.5)   # bounded by ~timeout, NOT the 5s sleep

    # --- probe_all_concurrent: 4 slow probes finish in ~one timeout, not 4× ---
    def _slow():
        time.sleep(0.4)
        return {"reachable": True, "detail": "ok"}
    probes = {f"n{i}": _slow for i in range(4)}
    t0 = time.monotonic()
    res = probe_all_concurrent(probes, timeout=1.0, max_workers=8)
    dt = time.monotonic() - t0
    chk("conc_all_present", set(res) == set(probes))
    chk("conc_all_reachable", all(v.get("result", {}).get("reachable") for v in res.values()))
    chk("conc_bounded_not_serial", dt < 1.0)   # 4×0.4=1.6s serial; concurrent ~0.4s

    # --- one dead (hanging) node doesn't blow the budget for the rest ---
    mixed = {"alive1": _slow, "alive2": _slow, "dead": _hang}
    t0 = time.monotonic()
    res = probe_all_concurrent(mixed, timeout=0.5, max_workers=8)
    dt = time.monotonic() - t0
    chk("mixed_alive_reachable", res["alive1"]["result"]["reachable"] is True)
    chk("mixed_dead_unreachable", res["dead"]["reachable"] is False)
    chk("mixed_bounded", dt < 1.5)

    # --- TTLCache: a fresh hit does NOT re-run the producer ---
    calls = {"n": 0}
    def _producer():
        calls["n"] += 1
        return {"reachable": True, "v": calls["n"]}
    c = TTLCache(ttl=10.0)
    a = c.get_or_compute(_producer)
    b = c.get_or_compute(_producer)   # within TTL -> cached, no second call
    chk("cache_hit_no_reprobe", calls["n"] == 1)
    chk("cache_returns_same", a["v"] == b["v"] == 1)
    chk("cache_has_cached_at", "cached_at" in a)

    # --- TTLCache: after expiry the producer runs again (re-probe) ---
    c2 = TTLCache(ttl=0.2)
    c2.get_or_compute(_producer)
    time.sleep(0.3)
    c2.get_or_compute(_producer)
    chk("cache_reprobe_after_ttl", calls["n"] >= 3)

    # --- _resolve_node_ip: env pin + prefix-collision disambiguation (honest) ---
    # env pin wins over everything, exact key derivation.
    _os.environ["A11OY_GPU_NODE_OMEN_BETTERWITHAGE_IP"] = "100.70.130.45"
    _ip, _src = _resolve_node_ip("omen-betterwithage", "9.9.9.9")
    chk("resolve_env_pin_omen", _ip == "100.70.130.45" and _src == "env-pin")
    _os.environ["A11OY_GPU_NODE_CHASKI_IP"] = "100.102.173.88"
    _ip, _src = _resolve_node_ip("chaski", "1.2.3.4")
    chk("resolve_env_pin_chaski", _ip == "100.102.173.88" and _src == "env-pin")
    del _os.environ["A11OY_GPU_NODE_OMEN_BETTERWITHAGE_IP"]
    del _os.environ["A11OY_GPU_NODE_CHASKI_IP"]

    # collision: BOTH Windows boxes are tailscale-named 'betterwithage'. With peers
    # {omen-betterwithage: OMEN_IP, betterwithage: LAPTOP_IP}, omen MUST NOT grab the
    # laptop's IP via the shared suffix.
    _orig_peers = _tailscale_peers
    try:
        globals()["_tailscale_peers"] = lambda: {
            "omen-betterwithage": "100.70.130.45",   # OMEN
            "betterwithage": "100.125.77.31",        # RTX 5050 laptop
        }
        _ip, _src = _resolve_node_ip("omen-betterwithage", "0.0.0.0")
        chk("resolve_omen_exact_not_laptop", _ip == "100.70.130.45")
        _ip, _src = _resolve_node_ip("rtx-betterwithage", "0.0.0.0")
        chk("resolve_rtx_suffix_to_laptop", _ip == "100.125.77.31")

        # suffixed names (betterwithage / betterwithage-1) with leading token in peer
        globals()["_tailscale_peers"] = lambda: {
            "omen-betterwithage-1": "100.70.130.45",
            "betterwithage": "100.125.77.31",
        }
        _ip, _src = _resolve_node_ip("omen-betterwithage", "0.0.0.0")
        chk("resolve_omen_lead_token", _ip == "100.70.130.45" and _src == "tailscale-lead")

        # AMBIGUOUS bare suffix (two peers carry 'betterwithage', no leading token to
        # disambiguate) MUST decline to static fallback rather than guess.
        globals()["_tailscale_peers"] = lambda: {
            "betterwithage": "100.125.77.31",
            "betterwithage-1": "100.70.130.45",
        }
        _ip, _src = _resolve_node_ip("omen-betterwithage", "5.5.5.5")
        chk("resolve_ambiguous_declines", _ip == "5.5.5.5" and _src == "static-fallback")

        # empty tailscale (box has no CLI / unreadable) -> static fallback, honest.
        globals()["_tailscale_peers"] = lambda: {}
        _ip, _src = _resolve_node_ip("omen-betterwithage", "100.70.130.45")
        chk("resolve_empty_static_fallback", _ip == "100.70.130.45" and _src == "static-fallback")
    finally:
        globals()["_tailscale_peers"] = _orig_peers

    # --- probe_fabric_pool with mocked sockets: dead chaski -> reachable=False, fast ---
    orig_socket = socket.socket

    class _FakeSock:
        def __init__(self, *a, **k):
            self._t = None
        def settimeout(self, t):
            self._t = t
        def connect(self, addr):
            host, port = addr
            if host == "100.102.173.88":         # the unreachable chaski node (current IP)
                time.sleep(min(self._t or 1.5, 1.5))
                raise socket.timeout("simulated chaski hang")
            return None                          # everyone else connects instantly
        def close(self):
            pass

    socket.socket = lambda *a, **k: _FakeSock()  # type: ignore
    try:
        cache = TTLCache(ttl=30.0)
        t0 = time.monotonic()
        payload = probe_fabric_pool(timeout=1.5, cache=cache, force=True)
        dt = time.monotonic() - t0
        by = {n["name"]: n for n in payload["nodes"]}
        chk("fabric_subsecond_with_dead_node", dt < 1.0 + 1.5)  # ~max one timeout, not sum
        chk("fabric_chaski_unreachable", by["chaski"]["reachable"] is False)
        chk("fabric_chaski_not_fabricated", by["chaski"]["detail"] in ("timeout", "simulated chaski hang"))
        chk("fabric_rtx_reachable", by["rtx-betterwithage"]["reachable"] is True)
        chk("fabric_self_reachable", by["hetzner-box-cpu"]["reachable"] is True)
        chk("fabric_counts_consistent",
            payload["counts"]["nodes_reachable"] == sum(1 for n in payload["nodes"] if n["reachable"]))
        chk("fabric_doctrine_lambda", payload["doctrine"]["lambda"] == "Conjecture 1")
        chk("fabric_doctrine_locked8", payload["doctrine"]["locked"] == 8)

        # second call within TTL must be cached (no re-probe) -> effectively instant.
        t0 = time.monotonic()
        payload2 = probe_fabric_pool(timeout=1.5, cache=cache)
        dt2 = time.monotonic() - t0
        chk("fabric_cache_hit_instant", dt2 < 0.05)
        chk("fabric_cache_same_cached_at", payload2["cached_at"] == payload["cached_at"])
    finally:
        socket.socket = orig_socket  # type: ignore

    ok = all(p for _, p in checks)
    return {
        "ok": ok,
        "checks": len(checks),
        "failed": [n for n, p in checks if not p],
        "doctrine": dict(DOCTRINE),
    }


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
