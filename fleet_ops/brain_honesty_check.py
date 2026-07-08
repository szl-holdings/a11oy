#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED · Λ = Conjecture 1
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""brain_honesty_check.py — standing LIVENESS check for a11oy's brain-honesty estate.

The brain-honesty surfaces (szl_brain*.py — consensus, contradict, explain, gaps, ground,
health, lineage, memory, provenance, audit, uncertainty, watch) are OBSERVE-only views over
the knowledge graph, and the honesty wall (szl_honestywall.py, GET
/api/a11oy/v1/govern/honestywall/status) aggregates the estate's OWN honesty invariants into
a single verdict: INTACT / DEGRADED / VIOLATED. This script confirms — over the network,
against the LIVE HF Space — that:

  1. each brain surface's /info manifest is UP (HTTP 200, JSON, ok:true, carries a label from
     the doctrine honesty vocabulary), and
  2. the honesty wall is reachable and its verdict is NOT VIOLATED.

It NEVER fabricates a healthy result. A surface that does not answer is reported UNKNOWN
(unreachable), never PASS. A surface that answers with the wrong shape is reported DOWN. The
wall's verdict is read VERBATIM and never upgraded — a truthful VIOLATED beats a fake green.

EXIT CONTRACT (only the wall governs the exit code; brain surfaces are reported honestly but
do not gate — a single surface napping must not red-gate the estate liveness signal):
  * 0  — wall reachable AND verdict INTACT or (honestly) DEGRADED.
  * 1  — wall reachable AND verdict VIOLATED (the estate can lie right now).
  * 2  — wall UNREACHABLE after bounded retries (unreachable-when-expected → not a pass).
  * 3  — usage error / self-test failure.

Stdlib only (urllib) so it runs on a clean runner with no `pip install` and no third-party
GitHub Action (org policy: github-owned/verified actions only). Network-tolerant: each probe
is retried a bounded number of times before its honest verdict is recorded.

Cloudflare in front of the Space 403s a plain client, so every request carries a browser
User-Agent. This is READ-ONLY: GET only; mints, signs, and writes nothing.

Usage:
  brain_honesty_check.py [--base https://szlholdings-a11oy.hf.space]
                         [--attempts 4] [--sleep 10] [--timeout 20]
                         [--summary-file out.json] [--selftest]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "https://szlholdings-a11oy.hf.space"

# A plain UA gets a Cloudflare 403 in front of the Space; a browser UA is served.
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# The doctrine honesty vocabulary (re-typed here on purpose — this liveness check imports
# nothing from the surfaces it probes). An /info manifest is only UP if its label is one of
# these; an invented / green / "1.0" token is a regression, never a pass.
HONEST_VOCAB = frozenset({
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE",
})

# The brain-honesty surfaces and their /info manifest paths (relative to a namespace base).
# Each is an OBSERVE-only view; each registers GET {base}/{name}/info.
BRAIN_SURFACES = (
    "consensus", "contradict", "explain", "gaps", "ground", "health",
    "lineage", "memory", "provenance", "audit", "uncertainty", "watch",
)

# The honesty wall's compact live verdict endpoint (read VERBATIM; never upgraded).
WALL_PATH_TMPL = "/api/{ns}/v1/govern/honestywall/status"

# Per-surface liveness states (honest; never conflated).
UP = "UP"              # HTTP 200 JSON, ok:true, honest-vocabulary label present
DOWN = "DOWN"          # answered, but wrong status / not JSON / bad shape / non-honest label
UNKNOWN = "UNKNOWN"    # did not answer over the network (never counted as a pass)

# Aggregate wall verdicts (as emitted by szl_honestywall).
INTACT = "INTACT"
DEGRADED = "DEGRADED"
VIOLATED = "VIOLATED"
UNREACHABLE = "UNREACHABLE"   # this checker's honest label when the wall never answered


def _label_from(payload) -> str | None:
    """Return the honest-vocabulary label a manifest declares, or None. Reads the top-level
    ``label`` (and ``label_top`` as a fallback) VERBATIM — never upgrades or invents one."""
    if not isinstance(payload, dict):
        return None
    for key in ("label", "label_top"):
        val = payload.get(key)
        if isinstance(val, str) and val.strip().upper() in HONEST_VOCAB:
            return val.strip().upper()
    return None


def classify_info(status_code, content_type, body_bytes, err) -> tuple[str, str]:
    """Pure classifier for one /info probe. Returns (state, reason).

    UNKNOWN if the request never completed (network error) — an unreachable surface is never
    a pass. DOWN if it answered but not with a valid honest JSON manifest. UP only for a
    200 application/json body with ok:true and a doctrine honesty-vocabulary label.
    """
    if err is not None:
        return UNKNOWN, f"unreachable: {err}"
    if status_code != 200:
        return DOWN, f"HTTP {status_code} (want 200)"
    if "application/json" not in (content_type or "").lower():
        return DOWN, f"content-type '{content_type or 'none'}' not application/json (likely SPA HTML)"
    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — any decode/parse failure is a regression
        return DOWN, f"body not valid JSON: {exc}"
    if not isinstance(data, dict):
        return DOWN, "JSON payload is not an object"
    if data.get("ok") is not True:
        return DOWN, f"manifest ok flag is {data.get('ok')!r} (want true)"
    label = _label_from(data)
    if label is None:
        return DOWN, "no honest-vocabulary label present in manifest"
    return UP, f"200 JSON ok:true label={label}"


def classify_wall(status_code, content_type, body_bytes, err) -> tuple[str, str]:
    """Pure classifier for the honesty-wall status probe. Returns (verdict, reason).

    UNREACHABLE if the request never completed. Otherwise the wall's OWN verdict is read
    VERBATIM (INTACT / DEGRADED / VIOLATED) and never upgraded. A wall that answers with an
    unavailable / unparseable body is reported UNREACHABLE, not INTACT: we only trust an
    explicit honest verdict and refuse to fabricate a pass from a bad body.
    """
    if err is not None:
        return UNREACHABLE, f"unreachable: {err}"
    if status_code != 200:
        return UNREACHABLE, f"HTTP {status_code} (want 200)"
    if "application/json" not in (content_type or "").lower():
        return UNREACHABLE, f"content-type '{content_type or 'none'}' not application/json"
    try:
        data = json.loads(body_bytes.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        return UNREACHABLE, f"body not valid JSON: {exc}"
    if not isinstance(data, dict):
        return UNREACHABLE, "JSON payload is not an object"
    verdict = data.get("verdict")
    if verdict in (INTACT, DEGRADED, VIOLATED):
        reason = data.get("verdict_reason") or "(no reason field)"
        return verdict, str(reason)
    # ok:false / UNAVAILABLE / missing verdict — the wall could not attest; do NOT fabricate.
    return UNREACHABLE, f"no honest verdict emitted (verdict={verdict!r}, ok={data.get('ok')!r})"


def _probe_once(url, timeout):
    """Single GET with a browser UA. Returns (status_code, content_type, body_bytes, err)."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": BROWSER_UA, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.headers.get("Content-Type", ""), resp.read(), None
    except urllib.error.HTTPError as exc:
        body = b""
        try:
            body = exc.read()
        except Exception:  # noqa: BLE001
            pass
        ct = exc.headers.get("Content-Type", "") if exc.headers else ""
        return exc.code, ct, body, None
    except Exception as exc:  # noqa: BLE001 — URLError / timeout / DNS / TLS
        return 0, "", b"", str(exc)


def _probe(url, classifier, attempts, sleep_s, timeout):
    """Probe one URL with bounded retries. Returns (state_or_verdict, reason).

    A transient rebuild/restart is tolerated: we retry, and only settle on a non-UP / non-INTACT
    result after the attempts are exhausted. A single successful UP/INTACT/DEGRADED short-circuits.
    """
    last_state, last_reason = UNKNOWN, "no attempt made"
    for attempt in range(1, attempts + 1):
        code, ct, body, err = _probe_once(url, timeout)
        state, reason = classifier(code, ct, body, err)
        last_state, last_reason = state, f"{reason} (attempt {attempt})"
        # UP (surface) and INTACT/DEGRADED (wall) are terminal-good — stop early.
        if state in (UP, INTACT, DEGRADED):
            return state, last_reason
        if attempt < attempts:
            time.sleep(sleep_s)
    return last_state, last_reason


def run(base, attempts, sleep_s, timeout, ns="a11oy"):
    """Probe every brain surface /info and the honesty wall. Returns a result dict."""
    base = base.rstrip("/")
    surfaces = []
    for name in BRAIN_SURFACES:
        url = f"{base}/api/{ns}/v1/brain/{name}/info"
        state, reason = _probe(url, classify_info, attempts, sleep_s, timeout)
        surfaces.append({"surface": name, "url": url, "state": state, "reason": reason})

    wall_url = base + WALL_PATH_TMPL.format(ns=ns)
    wall_verdict, wall_reason = _probe(wall_url, classify_wall, attempts, sleep_s, timeout)

    up = sum(1 for s in surfaces if s["state"] == UP)
    down = sum(1 for s in surfaces if s["state"] == DOWN)
    unknown = sum(1 for s in surfaces if s["state"] == UNKNOWN)
    return {
        "base": base,
        "surfaces": surfaces,
        "surface_counts": {"total": len(surfaces), UP: up, DOWN: down, UNKNOWN: unknown},
        "wall": {"url": wall_url, "verdict": wall_verdict, "reason": wall_reason},
    }


def verdict_to_exit(wall_verdict) -> int:
    """The ONLY exit decision: governed solely by the honesty-wall verdict (read verbatim).

    0 for INTACT/DEGRADED (honest, reachable), 1 for VIOLATED (can lie now), 2 for UNREACHABLE
    (unreachable-when-expected → never fabricated into a pass)."""
    if wall_verdict in (INTACT, DEGRADED):
        return 0
    if wall_verdict == VIOLATED:
        return 1
    return 2  # UNREACHABLE or any unexpected token — refuse to pass


def _print_report(result) -> None:
    c = result["surface_counts"]
    print(f"a11oy brain-honesty liveness — base {result['base']}")
    print(f"\n== brain surfaces ({c['total']}) ==")
    for s in result["surfaces"]:
        print(f"  {s['state']:<8} brain/{s['surface']:<12} {s['reason']}")
    print(f"\n  surfaces: UP={c[UP]} DOWN={c[DOWN]} UNKNOWN={c[UNKNOWN]}")
    w = result["wall"]
    print(f"\n== honesty wall ==")
    print(f"  verdict: {w['verdict']} — {w['reason']}")


def _selftest() -> int:
    """Offline negative control: prove the pure classifiers and the exit mapping refuse to
    fabricate a pass. No network. Mirrors the org guard-with-negative-control pattern."""
    ok = True

    def check(name, got, want):
        nonlocal ok
        good = got == want
        ok = ok and good
        print(f"  {'PASS' if good else 'FAIL'} {name}: got {got!r} want {want!r}")

    # Exit mapping: only INTACT/DEGRADED pass; VIOLATED=1; anything else=2 (no fabricated pass).
    check("exit(INTACT)", verdict_to_exit(INTACT), 0)
    check("exit(DEGRADED)", verdict_to_exit(DEGRADED), 0)
    check("exit(VIOLATED)", verdict_to_exit(VIOLATED), 1)
    check("exit(UNREACHABLE)", verdict_to_exit(UNREACHABLE), 2)
    check("exit(garbage)", verdict_to_exit("GREEN"), 2)

    # Wall classifier: verbatim verdict; a bad/absent verdict is UNREACHABLE, never INTACT.
    good_wall = json.dumps({"ok": True, "verdict": VIOLATED, "verdict_reason": "1 violation"}).encode()
    check("wall verbatim VIOLATED",
          classify_wall(200, "application/json", good_wall, None)[0], VIOLATED)
    bad_wall = json.dumps({"ok": False, "label": "UNAVAILABLE"}).encode()
    check("wall no-verdict → UNREACHABLE",
          classify_wall(200, "application/json", bad_wall, None)[0], UNREACHABLE)
    check("wall network error → UNREACHABLE",
          classify_wall(0, "", b"", "timeout")[0], UNREACHABLE)

    # Info classifier: UP only for honest label; unreachable is UNKNOWN, never UP.
    up_body = json.dumps({"ok": True, "label": "MODELED"}).encode()
    check("info honest label → UP",
          classify_info(200, "application/json", up_body, None)[0], UP)
    check("info unreachable → UNKNOWN (not UP)",
          classify_info(0, "", b"", "dns")[0], UNKNOWN)
    lie_body = json.dumps({"ok": True, "label": "VERIFIED"}).encode()
    check("info non-vocab label → DOWN (never UP)",
          classify_info(200, "application/json", lie_body, None)[0], DOWN)
    spa_body = b"<html>spa</html>"
    check("info SPA-HTML → DOWN",
          classify_info(200, "text/html", spa_body, None)[0], DOWN)

    print(f"\nself-test {'PASSED' if ok else 'FAILED'}")
    return 0 if ok else 3


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="a11oy brain-honesty surface + honesty-wall liveness check (read-only)."
    )
    ap.add_argument("--base", default=DEFAULT_BASE, help=f"Base URL (default {DEFAULT_BASE}).")
    ap.add_argument("--attempts", type=int, default=4, help="Retry attempts per probe (default 4).")
    ap.add_argument("--sleep", type=float, default=10.0, help="Seconds between retries (default 10).")
    ap.add_argument("--timeout", type=float, default=20.0, help="Per-request timeout seconds (default 20).")
    ap.add_argument("--summary-file", default="", help="Optional path to write a JSON summary.")
    ap.add_argument("--selftest", action="store_true", help="Run the offline negative control and exit.")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()

    result = run(args.base, args.attempts, args.sleep, args.timeout)
    _print_report(result)

    wall_verdict = result["wall"]["verdict"]
    code = verdict_to_exit(wall_verdict)
    result["exit_code"] = code

    if args.summary_file:
        with open(args.summary_file, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2)
        print(f"\nWrote summary -> {args.summary_file}")

    print(f"\nRESULT: wall={wall_verdict} exit={code} "
          f"(0=intact/degraded, 1=violated, 2=unreachable)")
    return code


if __name__ == "__main__":
    sys.exit(main())
