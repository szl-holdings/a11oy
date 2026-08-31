"""szl_demo_freeze.py — Demo-freeze startup guard + SZL_DEMO_MODE toggle.

Author: Yachay <yachay@szlholdings.dev>
ADDITIVE · Doctrine v11 LOCKED (749/14/163) · cosign keyid: szlholdings-cosign
Signed-off-by: Yachay <yachay@szlholdings.dev>

This single vendored module is copied into each flagship Space (the "one file per
Space" doctrine). It provides TWO independent, opt-in, env-var-gated features.
Neither activates unless the founder sets the corresponding env var on the Space.
Nothing here blocks startup or requests — the freeze check is ADVISORY and records
into the receipt chain; demo mode only narrows behaviour, it never crashes.

────────────────────────────────────────────────────────────────────────────
FEATURE 1 — STARTUP_CHECK_FROZEN_BASELINE  (advisory drift detector)
────────────────────────────────────────────────────────────────────────────
Founder sets env var STARTUP_CHECK_FROZEN_BASELINE=1 on T-7 (HF Space → Settings →
Variables and secrets). On startup we hash a small set of CRITICAL files and compare
to the frozen-baseline manifest committed alongside this module
(demo_freeze_baseline.manifest.json). On MISMATCH we DO NOT block — we log a WARNING
and append a `demo_freeze.drift` event to the receipt chain so the divergence is
provable after the fact.

────────────────────────────────────────────────────────────────────────────
FEATURE 2 — SZL_DEMO_MODE  (deterministic, network-quiet demo posture)
────────────────────────────────────────────────────────────────────────────
Founder sets env var SZL_DEMO_MODE=1 on T-1. When active:
  • agent auto-write loops pause            (sentra/amaru auto-loops -> no-op)
  • external API calls are blocked          EXCEPT cosign verify (kills network flake)
  • all RNG is pinned to DEMO_SEED          (deterministic responses)
  • a "DEMO MODE" chip is injected in the UI footer
Use the helpers below from serve.py / organ loops / HTTP egress / template render.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable, Optional

log = logging.getLogger("szl.demo_freeze")

# ── env reads (single source of truth) ─────────────────────────────────────
def _truthy(v: Optional[str]) -> bool:
    return str(v or "").strip().lower() in {"1", "true", "yes", "on"}

DEMO_MODE: bool = _truthy(os.getenv("SZL_DEMO_MODE"))
STARTUP_CHECK: bool = _truthy(os.getenv("STARTUP_CHECK_FROZEN_BASELINE"))
DEMO_SEED: int = int(os.getenv("SZL_DEMO_SEED", "749"))  # 749 = locked declarations count

FREEZE_TAG = "demo-freeze-baseline-2026-06-09"
DOCTRINE = "v11 LOCKED (749/14/163)"
COSIGN_KEYID = "szlholdings-cosign"

# Endpoints that remain ALLOWED for external egress while in demo mode.
# Only cosign verify (and its read-only pubkey) — everything else is network-quiet.
_DEMO_ALLOWED_EGRESS = ("/khipu/verify", "/khipu/pubkey")


# ════════════════════════════════════════════════════════════════════════════
# FEATURE 1 — frozen-baseline startup check (advisory; receipt-chain warning)
# ════════════════════════════════════════════════════════════════════════════
def _sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def compute_critical_hashes(root: str, critical_files: Iterable[str]) -> dict:
    """Hash each critical file (path relative to root). Missing files -> 'MISSING'."""
    root_p = Path(root)
    out = {}
    for rel in critical_files:
        fp = root_p / rel
        out[rel] = _sha256_file(fp) if fp.is_file() else "MISSING"
    return out


def run_startup_baseline_check(
    root: str = ".",
    manifest_path: str = "demo_freeze_baseline.manifest.json",
    receipt_appender: Optional[Callable[[dict], None]] = None,
) -> dict:
    """ADVISORY: compare current critical-file hashes to the frozen manifest.

    Returns a result dict. NEVER raises on drift; NEVER blocks startup.
    If `receipt_appender` is provided, a `demo_freeze.drift`/`demo_freeze.ok`
    receipt is appended to the chain so divergence is provable.
    """
    result = {
        "feature": "STARTUP_CHECK_FROZEN_BASELINE",
        "enabled": STARTUP_CHECK,
        "freeze_tag": FREEZE_TAG,
        "doctrine": DOCTRINE,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "status": "skipped",
        "drift": [],
    }
    if not STARTUP_CHECK:
        return result

    mpath = Path(root) / manifest_path
    if not mpath.is_file():
        result["status"] = "no-manifest"
        log.warning("[demo-freeze] STARTUP_CHECK_FROZEN_BASELINE set but manifest %s missing — cannot verify baseline.", mpath)
        return result

    manifest = json.loads(mpath.read_text())
    expected = manifest.get("critical_file_hashes", {})
    actual = compute_critical_hashes(root, expected.keys())

    drift = [
        {"file": f, "expected": expected[f], "actual": actual.get(f, "MISSING")}
        for f in expected
        if expected[f] != actual.get(f)
    ]
    result["actual_hashes"] = actual
    result["baseline_hf_sha"] = manifest.get("hf_sha")

    if drift:
        result["status"] = "drift"
        result["drift"] = drift
        log.warning(
            "[demo-freeze] ⚠️ BASELINE DRIFT vs %s — %d critical file(s) changed: %s "
            "(ADVISORY: not blocking; recorded to receipt chain).",
            FREEZE_TAG, len(drift), ", ".join(d["file"] for d in drift),
        )
    else:
        result["status"] = "ok"
        log.info("[demo-freeze] ✅ critical files match frozen baseline %s.", FREEZE_TAG)

    if receipt_appender is not None:
        try:
            receipt_appender({
                "type": "demo_freeze.drift" if drift else "demo_freeze.ok",
                "freeze_tag": FREEZE_TAG,
                "doctrine": DOCTRINE,
                "cosign_keyid": COSIGN_KEYID,
                "drift_count": len(drift),
                "drift": drift,
                "baseline_hf_sha": manifest.get("hf_sha"),
                "recorded_at": result["checked_at"],
                "signer": "Yachay <yachay@szlholdings.dev>",
            })
        except Exception as e:  # receipt failure must never break startup
            log.warning("[demo-freeze] receipt append failed (non-fatal): %s", e)

    return result


# ════════════════════════════════════════════════════════════════════════════
# FEATURE 2 — SZL_DEMO_MODE helpers
# ════════════════════════════════════════════════════════════════════════════
def pin_determinism() -> None:
    """Seed all RNGs so demo responses are reproducible. Call once at startup."""
    if not DEMO_MODE:
        return
    random.seed(DEMO_SEED)
    os.environ.setdefault("PYTHONHASHSEED", str(DEMO_SEED))
    try:
        import numpy as np  # optional
        np.random.seed(DEMO_SEED)
    except Exception:
        pass
    log.info("[demo-mode] determinism pinned to seed=%d", DEMO_SEED)


def agent_writes_paused() -> bool:
    """True when agent auto-write loops (sentra/amaru) must NO-OP.

    Wrap auto-loop write bodies:  if agent_writes_paused(): return
    """
    return DEMO_MODE


def external_egress_allowed(url_or_path: str) -> bool:
    """Gate outbound calls in demo mode. Only cosign verify/pubkey allowed.

    Wrap your HTTP client:  if not external_egress_allowed(url): raise/skip
    """
    if not DEMO_MODE:
        return True
    s = str(url_or_path)
    return any(allow in s for allow in _DEMO_ALLOWED_EGRESS)


def demo_mode_footer_html() -> str:
    """HTML snippet for the UI footer chip. Empty string when demo mode is off."""
    if not DEMO_MODE:
        return ""
    return (
        '<div id="szl-demo-chip" role="status" aria-label="Demo mode active" '
        'style="position:fixed;left:50%;bottom:env(safe-area-inset-bottom,8px);'
        'transform:translateX(-50%);z-index:2147483647;'
        'font:600 12px/1 ui-monospace,SFMono-Regular,Menlo,monospace;'
        'letter-spacing:.08em;color:#0b0e14;background:#e9c46a;'
        'padding:6px 12px;border-radius:999px;'
        'box-shadow:0 2px 10px rgba(0,0,0,.35);pointer-events:none;">'
        '● DEMO MODE</div>'
    )


def status() -> dict:
    """Machine-readable status for /healthz and the receipt chain."""
    return {
        "demo_mode": DEMO_MODE,
        "startup_baseline_check": STARTUP_CHECK,
        "demo_seed": DEMO_SEED if DEMO_MODE else None,
        "agent_writes_paused": agent_writes_paused(),
        "freeze_tag": FREEZE_TAG,
        "doctrine": DOCTRINE,
        "cosign_keyid": COSIGN_KEYID,
    }


# ── INTEGRATION (paste into serve.py top-level, after app + receipts exist) ──
# from szl_demo_freeze import (
#     run_startup_baseline_check, pin_determinism, agent_writes_paused,
#     external_egress_allowed, demo_mode_footer_html, status as demo_status,
# )
# pin_determinism()
# run_startup_baseline_check(root=".", receipt_appender=khipu_append)  # khipu_append = your receipt fn
# # in /healthz JSON:  payload["demo_freeze"] = demo_status()
# # in each agent auto-loop body:  if agent_writes_paused(): return
# # in your HTTP egress wrapper:   if not external_egress_allowed(url): raise RuntimeError("demo-mode: egress blocked")
# # in your base template footer:  {{ demo_mode_footer_html()|safe }}
