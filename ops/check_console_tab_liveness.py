#!/usr/bin/env python3
"""
a11oy console honesty + tab-liveness guard.

Fails (exit 1) if the a11oy /console (pages/console.html) regresses on any of:
  1. NO-DEAD-TAB  - every nav tab (data-view= / go('...')) resolves to a real
                    dispatch entry (V.<k>=, V['<k>']=, base VIEWS {<k>:{...}},
                    reg('<k>'), or a defs [['<k>',...]] row).
  2. HONESTY      - doctrine v11 invariants intact: exactly the 8 LOCKED formula
                    IDs, the locked baseline commit, and Lambda = "Conjecture 1"
                    (Lambda stays a conjecture).
  3. AUTO-REFRESH - Constellation (3D) + Decision-Graphs (2D) keep their 30s
                    refresh timers, each guarded by `typeof setInterval` and
                    gated on document.visibilityState (no background polling).
  4. NO-FAKE-LIVE - any V.<k>/V['<k>'] tab whose render advertises a "LIVE" badge
                    must actually call a live loader; a tab with neither a loader
                    nor an honest label is a static placeholder and is rejected.

This guard is intentionally conservative: it only flags clear violations, so a
green run is a real signal. NEVER weaken a check to make a real violation pass.
"""
import re
import sys
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
CANDIDATES = [
    HERE.parent / "pages" / "console.html",   # ops/ -> repo root
    HERE / "console.html",
    pathlib.Path("pages/console.html"),
]

# data-view anchors that are NOT real views (querySelector targets in fallbacks)
NON_VIEW_KEYS = {"bounties"}

LOCKED_IDS = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]
LOCKED_BASELINE = "c7c0ba17"

LOADER_TOKENS = [
    "gj(", "gjFast(", "pj(", "getJSON", "a11oyPoll", "fetch(", "postJSON",
    "_load(", "_init(", "_render(", "_poll(", "whPlayByPlay",
    "cn_render", "cn_soft", "cn_setup",
]


def find_src():
    for p in CANDIDATES:
        if p.exists():
            return p
    print("FATAL: pages/console.html not found in any of:",
          [str(p) for p in CANDIDATES])
    sys.exit(2)


def nav_keys(src):
    keys = set(re.findall(r'data-view="([a-z0-9_]+)"', src))
    keys |= set(re.findall(r"go\('([a-z0-9_]+)'\)", src))
    return {k for k in keys if k not in NON_VIEW_KEYS}


def resolves(src, k):
    """True if nav key k has any real dispatch entry."""
    pats = [
        r"\bV\." + re.escape(k) + r"\s*=",
        r"\bV\[['\"]" + re.escape(k) + r"['\"]\]\s*=",
        # base VIEWS object literal key, possibly preceded by a comment close */
        r"(?<![A-Za-z0-9_])" + re.escape(k) + r"\s*:\s*\{\s*title:",
        r"\breg\(['\"]" + re.escape(k) + r"['\"]",
        r"\[\s*['\"]" + re.escape(k) + r"['\"]\s*,\s*['\"]",
    ]
    return any(re.search(p, src) for p in pats)


def v_assignment_bodies(src):
    """Yield (key, body) for each V.<k>= / V['<k>']= assignment, body sliced up
    to the next V-assignment (bounds the full render body for token scanning)."""
    marks = []
    for m in re.finditer(r"\bV\.([a-zA-Z0-9_]+)\s*=", src):
        marks.append((m.start(), m.group(1)))
    for m in re.finditer(r"\bV\[['\"]([a-zA-Z0-9_]+)['\"]\]\s*=", src):
        marks.append((m.start(), m.group(1)))
    marks.sort()
    for i, (pos, key) in enumerate(marks):
        end = marks[i + 1][0] if i + 1 < len(marks) else len(src)
        yield key, src[pos:end]


def main():
    p = find_src()
    src = p.read_text(encoding="utf-8")
    fails = []

    # 1. NO-DEAD-TAB
    dead = sorted(k for k in nav_keys(src) if not resolves(src, k))
    if dead:
        fails.append("DEAD-TAB: nav tab(s) with no dispatch entry: " + ", ".join(dead))

    # 2. HONESTY
    for fid in LOCKED_IDS:
        if not re.search(r"\b" + fid + r"\b", src):
            fails.append(f"HONESTY: locked formula id {fid} missing")
    if LOCKED_BASELINE not in src:
        fails.append(f"HONESTY: locked baseline commit {LOCKED_BASELINE} missing")
    if "Conjecture 1" not in src:
        fails.append("HONESTY: Lambda must read 'Conjecture 1' (advisory, not a theorem)")

    # 3. AUTO-REFRESH + VISIBILITY
    if "CN_REFRESH_MS" not in src:
        fails.append("AUTO-REFRESH: CN_REFRESH_MS missing")
    for t in ("__cn_con_timer", "__cn_gr_timer"):
        if t not in src:
            fails.append(f"AUTO-REFRESH: timer {t} missing")
    if src.count("typeof setInterval==='function'") < 2:
        fails.append("AUTO-REFRESH: setInterval guard missing on a refresh timer")
    if "visibilityState" not in src:
        fails.append("AUTO-REFRESH: visibilityState gating missing (background polling)")

    # 4. NO-FAKE-LIVE: a tab whose top badge literally advertises "LIVE" must
    #    actually call a live loader. (Conservative: only the badge word "LIVE"
    #    triggers it, so honestly-labeled tabs are never falsely flagged.)
    for key, body in v_assignment_bodies(src):
        has_loader = any(t in body for t in LOADER_TOKENS)
        advertises_live = bool(re.search(r"badge\s*:\s*'[^']*\bLIVE\b", body))
        if advertises_live and not has_loader:
            fails.append(f"FAKE-LIVE: tab '{key}' badge says LIVE but its render calls no loader")

    if fails:
        print("a11oy console liveness/honesty guard: FAIL")
        for f in fails:
            print("  - " + f)
        sys.exit(1)
    print("a11oy console liveness/honesty guard: PASS "
          f"({len(nav_keys(src))} nav tabs all resolved; honesty + auto-refresh intact)")


if __name__ == "__main__":
    main()
