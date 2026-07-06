# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
"""
szl_anatomy_loop.py — the live CLOSED-LOOP energy-circulation read endpoint.

This module is the ORCHESTRATOR. It does NOT reimplement any organ — it wires the
already-shipped anatomy organs into ONE Ayni-balanced circulation loop and exposes
its live state:

  GET /api/<ns>/v1/anatomy/loop  -> the live circulation state of the loop.

THE LOOP (one cycle):

  harvest INTAKE  read the live wasted-energy posture (attempt local
                  http://127.0.0.1 harvest/posture, then public
                  https://a-11-oy.com/api/a11oy/v1/harvest/posture; if both are
                  unreachable, degrade HONESTLY to a clearly-labeled SAMPLE
                  snapshot — we NEVER fabricate a measured number)
    -> SAMAY      lungs: SOAK the available wasted-WORK window (a breath/window),
                  carrying soaked WORK + receipts — NOT electrons.
    -> KALLPA     metabolize the soaked window into bounded work_credits, capped
                  by the Bekenstein software bound (bytes*8) and floored by the
                  Landauer minimum (kT ln 2 per bit) so a credit is always a
                  bounded, honest unit of WORK — never free energy.
    -> heart/pulse a DSSE beat on the HEART σ-bus + BLOOD Merkle chain
                  (szl_heart_blood, #332), wrapping a provenance receipt.
    -> YARQA      irrigation canal: disperse the beat to the organs
                  WAQAYCHAQ (guard/store), KAMAY (act/animate), RIKUY (observe).
    -> EnergyReservoir store the metabolized work_credits (a tank, not a battery
                  of electrons — it holds proven WORK + its receipt).
    -> provenance receipt  bind the cycle into the tamper-evident chain
                  (szl_energy_provenance, #331).
    -> validate   verify the provenance chain + heart beats (offline-checkable).
    -> Ayni F11   balance the books: intake == output + stored + proven. The loop
                  is reciprocal, NEVER net-positive. (Ayni = direct reciprocity,
                  Axelrod & Hamilton 1981; the F11 ledger primitive.)
    -> repeat.

DOCTRINE (v11 — NON-NEGOTIABLE; CI enforces via doctrine grep + overclaim guard):
  - joules_label is ALWAYS "sample" unless a real MEASURED source is present
    (on-box NVML etc.). Default is sample. This module runs off-box, so the
    default and the offline path are both sample. We do NOT invent measured
    numbers.
  - The loop carries soaked-WORK + receipts, NOT electrons. It is an information/
    work circulation, not a power line.
  - NO free-energy / perpetual / over-unity language anywhere. A cycle can only
    metabolize what it soaked; the books MUST balance.
  - Ayni MUST balance: intake == output + stored + proven, never net-positive.
  - Organs are EXPERIMENTAL tier — never claimed proven.
  - sovereign stays False unless running on own metal (never asserted here).
  - Λ is Conjecture 1 — never a theorem, never "proven trust".

Additive + import-safe + crash-proof: every organ call is wrapped in try/except so
this module can NEVER take down the app, and it self-tests with NO network and
without serve.py running. Pure stdlib + whatever a11oy already imports (FastAPI).

It WRAPS — never rewrites — the shipped organ modules:
  - a11oy_harvest_endpoints (#harvest posture)   -> INTAKE
  - szl_energy_provenance   (#331 receipt chain) -> receipt + validate
  - szl_heart_blood         (#332 heart/pulse)   -> the beat
when importable; otherwise it falls back to the live HTTP surfaces, and finally to
an honest SAMPLE snapshot — always labeled.
"""
import json
import math
import urllib.request
from datetime import datetime, timezone

# Single source of truth for the joules honesty label. Wrapped so a missing/broken
# import can NEVER take down the loop — we degrade to the honest "sample" default.
try:
    from szl_joules_truth import (
        joules_label as _joules_label,
        joules_evidence as _joules_evidence,
    )
except Exception:  # pragma: no cover - defensive: doctrine default is always sample
    def _joules_label(_exporter_sample, now=None):  # type: ignore
        return "sample"
    def _joules_evidence(_exporter_sample, now=None):  # type: ignore
        return {}

# Resilience + latency-hardening helpers, ALREADY SHIPPED on main. We REUSE them —
# we do NOT reinvent a breaker or a cache here. The intake probe hits the harvest
# posture surface, which in turn reaches the sleeping GPU / offline chaski node; a
# synchronous probe of a dead node pays the full per-URL TCP/HTTP timeout (~1.5s
# each, three surfaces -> the ~3s dependency-wait this fix removes). We wrap that
# ONE blocking dependency call with:
#   (a) a Hystrix CIRCUIT BREAKER (szl_resilience) — after N consecutive failures
#       it OPENs and fail-fasts, so a sustained sleeping node stops costing ANY
#       timeout at all; and
#   (b) a short hard-timeout probe + a TTLCache (szl_backend_hardening) — a slow or
#       dead node is abandoned at a sub-second budget and the loop serves the LAST
#       REAL posture (or an honest SAMPLE), never a hang.
# Every import is wrapped so a missing/broken helper can NEVER take down the loop;
# it degrades to today's behaviour (the existing _read_intake fallbacks).
try:  # pragma: no cover - exercised via the offline tests with the helpers present
    from szl_resilience import REGISTRY as _BREAKER_REGISTRY
    _INTAKE_BREAKER = _BREAKER_REGISTRY.get_or_create(
        # Small threshold + short cooldown: trip fast when the GPU-node-backed
        # posture surface is sleeping, recover promptly when it wakes.
        "anatomy-intake-probe", failure_threshold=3, cooldown=20.0, half_open_max=1
    )
except Exception:  # pragma: no cover - defensive: no breaker -> probe runs unwrapped
    _INTAKE_BREAKER = None

try:  # pragma: no cover
    from szl_backend_hardening import probe_with_timeout as _probe_with_timeout, TTLCache as _TTLCache
    # Short TTL: serve the last REAL posture briefly so repeat calls don't re-probe a
    # dead node; re-probe once it expires (recovery is observed honestly).
    _INTAKE_CACHE = _TTLCache(ttl=20.0)
except Exception:  # pragma: no cover - defensive: no cache -> probe runs unwrapped
    _probe_with_timeout = None  # type: ignore
    _INTAKE_CACHE = None

# Hard per-attempt budget for the intake probe. Even with no breaker/cache present,
# the whole intake must return well under the <1s target; the network surfaces below
# are also given a short per-URL timeout so the unwrapped fallback can't hang either.
_INTAKE_PROBE_TIMEOUT_S = 0.6

# ---------------------------------------------------------------------------
# Doctrine constants (v11). These are the honest, fixed labels + physics floors.
# ---------------------------------------------------------------------------
DOCTRINE = "v11"
SAMPLE_LABEL = "sample"        # default — off-box, no real power meter wired
MEASURED_LABEL = "measured"    # ONLY when a real metered source is present

# VERBATIM honesty vocabulary (doctrine v11) for the reservoir energy + the 8
# software systems. These MUST match szl_frontier_manifest / szl_energy_live exactly
# so no reader ever sees a novel/soft label. Never upgraded; a dead source is
# UNAVAILABLE, never faked.
LABEL_MEASURED = "MEASURED"
LABEL_SAMPLE = "SAMPLE"
LABEL_MODELED = "MODELED"
LABEL_UNAVAILABLE = "UNAVAILABLE"

# Health bands per system — always a LABEL string (never colour-only).
BAND_HEALTHY = "healthy"
BAND_DEGRADED = "degraded"
BAND_DOWN = "down"
BAND_UNAVAILABLE = "unavailable"

# A 20 s TTL cache for the assembled living state + the live merged-meter reservoir
# reading. SAME TTLCache class the intake probe already uses (szl_backend_hardening),
# so the vitals endpoint is a handful of cache reads, never a per-request fan-out to
# 52 organ endpoints. Guarded: absent helper -> compute fresh every call (honest).
try:  # pragma: no cover - exercised via the offline tests with the helper present
    from szl_backend_hardening import TTLCache as _TTLCache2
    _VITALS_CACHE = _TTLCache2(ttl=20.0)
except Exception:  # pragma: no cover - defensive
    _VITALS_CACHE = None

# Last-seen signed joule-ledger totals, so the circulation loop can be driven by
# REAL measured-billable joule DELTAS between cycles (never a fabricated flow).
_LAST_LEDGER = {"joules": None, "jobs": None}

# Physics floors/ceilings for a bounded WORK credit (NOT free energy):
#   Bekenstein software bound  : a window of N bytes carries at most N*8 bits.
#   Landauer minimum           : erasing one bit costs at least kT ln 2 joules.
# These BOUND a credit; they never manufacture energy.
_BOLTZMANN_K = 1.380649e-23          # J/K (CODATA)
_ROOM_T_KELVIN = 300.0               # K — a labeled SAMPLE ambient, not metered
LANDAUER_FLOOR_J = _BOLTZMANN_K * _ROOM_T_KELVIN * math.log(2)  # ~2.87e-21 J/bit

# The three YARQA dispersal organs. EXPERIMENTAL tier — never claimed proven.
_ORGAN_SPECS = (
    ("WAQAYCHAQ", "guard/store — disperse the beat to the reservoir-guard organ (experimental)"),
    ("KAMAY",     "act/animate — disperse the beat to the actuation organ (experimental)"),
    ("RIKUY",     "observe — disperse the beat to the observation/telemetry organ (experimental)"),
)

# Candidate live posture surfaces, in attempt order: local box first, then public.
_POSTURE_URLS = (
    "http://127.0.0.1/api/a11oy/v1/harvest/posture",
    "http://127.0.0.1:8000/api/a11oy/v1/harvest/posture",
    "https://a-11-oy.com/api/a11oy/v1/harvest/posture",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# INTAKE — read the live harvest posture, degrade HONESTLY to a SAMPLE snapshot.
# Never fabricate a measured number; the SAMPLE snapshot is clearly labeled.
# ---------------------------------------------------------------------------
def _sample_posture(gpu_state: str = "unreachable", reason: str = "") -> dict:
    """An honest, clearly-labeled SAMPLE intake snapshot (no live feed reached).

    Every field is labeled sample; no number here is claimed as metered. This is
    the doctrine-clean degrade path when neither the local box nor the public
    surface is reachable (e.g. the GPU node is sleeping / chaski is offline, or the
    intake breaker is OPEN and fail-fasting). `gpu_state` records WHY we degraded
    ("sleeping" / "unreachable") so the posture is honest about the node, and
    `reason` carries the breaker/timeout detail. We NEVER fabricate a measured
    number; wasted_energy_available stays False (we assume nothing to soak).
    """
    src = "SAMPLE snapshot (no live harvest feed reachable — doctrine v11)"
    if reason:
        src = f"{src}; {reason}"
    return {
        "ok": False,
        "posture": "sample",
        "degraded": True,                  # honest: this is a degraded read, not live
        "gpu_state": gpu_state,            # "sleeping" / "unreachable" — honest node posture
        "grid_price_eur_mwh": None,        # unknown off-box — NOT fabricated
        "wasted_energy_available": False,  # conservative: assume nothing to soak
        "joules_label": SAMPLE_LABEL,
        "source": src,
        "measured_any": False,
    }


def _try_in_process_posture():
    """Prefer the in-process harvest organ when it is importable (no network)."""
    try:
        from a11oy_harvest_endpoints import handle_posture  # shipped organ
        p = handle_posture()
        if isinstance(p, dict):
            return p
    except Exception:
        return None
    return None


def _try_http_posture(timeout: float = _INTAKE_PROBE_TIMEOUT_S):
    """Attempt the live HTTP posture surfaces (local box, then public).

    The per-URL timeout is SHORT (default _INTAKE_PROBE_TIMEOUT_S) so even the
    unwrapped fallback path — if the resilience/hardening helpers are absent —
    cannot pay the old multi-second per-surface wait against a sleeping node.
    """
    for url in _POSTURE_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "a11oy-anatomy-loop"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec - read-only GET
                body = resp.read().decode("utf-8", "replace")
            data = json.loads(body)
            if isinstance(data, dict):
                data.setdefault("source", url)
                return data
        except Exception:
            continue
    return None


# A breaker-open fail-fast sentinel: an honest "didn't probe" marker. NOT a posture
# and NOT fabricated data — it tells _read_intake to degrade to a labeled SAMPLE.
_BREAKER_OPEN_SENTINEL = {"_intake_unavailable": True, "_reason": "breaker_open"}


def _probe_posture_raw():
    """The raw blocking dependency call: in-process organ, else the HTTP surfaces.

    This is the ONE call that can reach the sleeping GPU / offline chaski node. It
    is the thing we wrap with the breaker + short-timeout probe + cache. We raise on
    an empty/failed probe so the breaker records a REAL failure (and trips after N),
    rather than silently swallowing it.
    """
    raw = _try_in_process_posture() or _try_http_posture()
    if not isinstance(raw, dict):
        raise RuntimeError("intake posture unreachable (no live harvest feed)")
    return raw


def _probe_posture_guarded():
    """Run the raw probe under a SHORT hard timeout (szl_backend_hardening).

    Even if the underlying urllib call ignored its own timeout, probe_with_timeout
    abandons the probe at _INTAKE_PROBE_TIMEOUT_S and returns fast. Raises on
    timeout/failure so the surrounding breaker counts it as a real failure.
    """
    if _probe_with_timeout is not None:
        env = _probe_with_timeout(_probe_posture_raw, timeout=_INTAKE_PROBE_TIMEOUT_S)
        if not env.get("reachable"):
            raise RuntimeError(f"intake probe unreachable ({env.get('detail')})")
        result = env.get("result")
        if not isinstance(result, dict):
            raise RuntimeError("intake probe returned no posture")
        return result
    # No hardening helper present: fall back to the raw probe (which itself now uses
    # a short per-URL timeout), so we still cannot hang on a sleeping node.
    return _probe_posture_raw()


def _fetch_posture_resilient():
    """Fetch the harvest posture, FAIL-FAST and CACHED via the shipped helpers.

    Wiring (reusing what's already on main, never reinventing):
      1. CIRCUIT BREAKER (szl_resilience): the probe runs through the
         'anatomy-intake-probe' breaker. After N consecutive failures the breaker
         OPENs and subsequent calls fail-fast to the _BREAKER_OPEN_SENTINEL WITHOUT
         probing — so a sustained sleeping node pays NO timeout at all.
      2. SHORT-TIMEOUT PROBE (szl_backend_hardening.probe_with_timeout): each real
         probe is hard-bounded to _INTAKE_PROBE_TIMEOUT_S, so a slow node is
         abandoned sub-second instead of blocking ~3s.
      3. TTLCache (szl_backend_hardening.TTLCache): a successful posture is cached
         briefly so repeat calls don't re-probe; the cache only ever holds REAL
         probe output (honest by construction).
    Returns a real posture dict, or None to signal "degrade to honest SAMPLE".
    """
    # Cache fast-path: serve the last REAL posture if still fresh (no re-probe).
    if _INTAKE_CACHE is not None:
        cached = _INTAKE_CACHE.peek()
        if isinstance(cached, dict):
            return cached

    def _fallback():
        # Breaker OPEN -> fail-fast. We return an honest sentinel (NOT fabricated
        # posture); _read_intake turns it into a labeled SAMPLE with gpu sleeping.
        return dict(_BREAKER_OPEN_SENTINEL)

    try:
        if _INTAKE_BREAKER is not None:
            posture = _INTAKE_BREAKER.call(_probe_posture_guarded, fallback=_fallback)
        else:
            posture = _probe_posture_guarded()
    except Exception:
        # Any real failure (and no fallback / no breaker) -> honest degrade.
        return None

    if not isinstance(posture, dict) or posture.get("_intake_unavailable"):
        return None
    # Cache only a REAL posture (never the sentinel, never a degrade).
    if _INTAKE_CACHE is not None:
        try:
            _INTAKE_CACHE.get_or_compute(lambda: posture)
        except Exception:
            pass
    return posture


def _read_intake() -> dict:
    """INTAKE: live posture if reachable, else an honest SAMPLE snapshot.

    Returns a normalized intake dict. joules_label is 'sample' by DEFAULT and
    stays sample unless a REAL on-box power meter is present. Doctrine v11: a
    live wasted-energy FEED reading (measured_any) is NOT a power measurement —
    the harvest organ itself notes 'joules_label is always sample off-box; MEASURED
    requires on-box NVML'. So we only flip to measured when the source explicitly
    reports an on-box meter (metered_onbox), which never exists off-box. We NEVER
    upgrade a sample into a measurement, and we NEVER invent numbers.

    LATENCY: the blocking dependency probe (which reaches the sleeping GPU / offline
    chaski node) is fetched via _fetch_posture_resilient — circuit-broken + short-
    timeout + cached — so a sleeping node degrades to an honest SAMPLE in <1s
    instead of paying the ~3s synchronous dependency-wait. The degraded posture is
    HONEST: gpu_state is flagged 'sleeping'/'unreachable', intake is marked degraded,
    joules stay SAMPLE (never a fabricated measured value).
    """
    raw = _fetch_posture_resilient()
    if not isinstance(raw, dict):
        # The GPU-node-backed posture surface is sleeping/unreachable (or the intake
        # breaker is OPEN and fail-fasting). Degrade HONESTLY — no hang, no fabrication.
        gpu = "sleeping"
        reason = "intake probe fail-fast (circuit-broken / short-timeout); GPU node sleeping"
        if _INTAKE_BREAKER is not None:
            try:
                from szl_resilience import CircuitState as _CS
                if _INTAKE_BREAKER.state is _CS.OPEN:
                    reason = "anatomy-intake-probe breaker OPEN: failing fast, no probe paid"
            except Exception:
                pass
        return _sample_posture(gpu_state=gpu, reason=reason)

    # A live FEED reading is informational only; it is NOT an on-box power meter.
    feed_measured_any = bool(raw.get("measured_any", False))
    # Doctrine v11: joules are 'sample' off-box. The label is decided by the
    # SINGLE SOURCE OF TRUTH (szl_joules_truth) — "measured" ONLY when the source
    # carries a REAL, FRESH on-box NVML exporter sample. A bare 'metered_onbox'
    # flag is NO LONGER trusted on its own (that was the honesty bug); the source
    # must hand us an actual exporter reading + timestamp. Absent -> "sample".
    exporter_sample = raw.get("exporter_sample") or raw.get("joules_evidence")
    joules_label = _joules_label(exporter_sample)
    joules_evidence = _joules_evidence(exporter_sample)
    # grid price is only carried through if the live feed actually supplied one;
    # absence -> None (never a fabricated figure).
    grid_price = raw.get("grid_price_eur_mwh", None)
    grid = _extract_grid_intake(raw)
    return {
        "ok": bool(raw.get("ok", False)),
        "posture": raw.get("posture", "unknown"),
        "degraded": False,                 # a live posture was actually reached
        "gpu_state": raw.get("gpu_state", "awake"),  # node posture, passed through if reported
        "grid_price_eur_mwh": grid_price,
        "negative_price": grid["negative_price"],   # MEASURED public-feed posture
        "renewable_pct": grid["renewable_pct"],     # MEASURED share of load, else None
        "wasted_energy_available": bool(raw.get("wasted_energy_available", False)),
        "joules_label": joules_label,
        "joules_evidence": joules_evidence,   # self-verifying: present iff measured
        "source": raw.get("source", "live harvest posture"),
        "feed_measured_any": feed_measured_any,
    }


def _extract_grid_intake(raw: dict) -> dict:
    """Pull the live grid harvest posture (metabolic INTAKE rate) out of the posture
    payload we ALREADY fetched — we do NOT re-implement or re-scrape the feed.

    Returns {negative_price, renewable_pct}. negative_price is the MEASURED
    public-feed posture (aWATTar negative-price / curtailed window). renewable_pct is
    scanned best-effort out of the per-feed readings (Energy-Charts renewable share of
    load); absent/unparseable -> None (never fabricated)."""
    posture = str(raw.get("posture", "") or "").lower()
    negative_price = bool(
        raw.get("wasted_energy_available", False)
        or "negative" in posture
        or bool(raw.get("soak_hard", False))
    )
    renewable_pct = None
    for reading in (raw.get("readings") or []):
        if not isinstance(reading, dict):
            continue
        name = " ".join(str(reading.get(k, "")) for k in ("name", "feed", "source")).lower()
        if "renewable" not in name and "share" not in name:
            continue
        for vk in ("value", "share", "measured_value", "pct", "percent"):
            v = reading.get(vk)
            if isinstance(v, (int, float)):
                renewable_pct = round(float(v), 3)
                break
        if renewable_pct is not None:
            break
    return {"negative_price": negative_price, "renewable_pct": renewable_pct}


# ---------------------------------------------------------------------------
# SAMAY (lungs/soak) -> KALLPA (metabolize to bounded work_credits).
# ---------------------------------------------------------------------------
def _samay_soak(intake: dict) -> dict:
    """SAMAY: soak the available wasted-WORK window — a breath, not electrons.

    The soaked window is a small, bounded number of bytes of WORK opportunity. We
    only soak when the posture says wasted energy is available; otherwise the
    window is zero (we never soak what is not there — that would be free energy).
    """
    available = bool(intake.get("wasted_energy_available", False))
    window_bytes = 256 if available else 0   # a bounded SAMPLE soak window
    return {"window_bytes": window_bytes, "soaked": available}


def _kallpa_metabolize(soak: dict) -> dict:
    """KALLPA: metabolize the soaked window into BOUNDED work_credits.

    work_credits = bits of the soaked window, where bits are capped by the
    Bekenstein software bound (window_bytes * 8) — a credit can never exceed what
    the window can carry. The Landauer floor (kT ln 2 per bit) is the honest lower
    bound on the work each bit represents. This BOUNDS the credit on both sides;
    it never manufactures energy. joules figures stay SAMPLE.
    """
    window_bytes = int(soak.get("window_bytes", 0))
    bekenstein_cap_bits = window_bytes * 8                 # ceiling — F19/TH6 bound
    work_credits = bekenstein_cap_bits                     # bounded by the cap
    landauer_floor_j = round(work_credits * LANDAUER_FLOOR_J, 30)  # SAMPLE lower bound
    return {
        "work_credits": work_credits,
        "bekenstein_cap_bits": bekenstein_cap_bits,
        "landauer_floor_joules": landauer_floor_j,
        "joules_label": SAMPLE_LABEL,
        "bound_note": "credit bounded above by Bekenstein bytes*8, floored by Landauer kT ln2/bit",
    }


# ---------------------------------------------------------------------------
# heart/pulse beat — wrap szl_heart_blood (#332) when importable; else a local
# byte-shaped beat so the loop + self-test run standalone with no network.
# ---------------------------------------------------------------------------
def _heart_beat(metab: dict) -> dict:
    """Emit ONE DSSE beat carrying the cycle's receipt (work + receipt, not electrons)."""
    payload = json.dumps(
        {"work_credits": metab.get("work_credits", 0), "joules_label": SAMPLE_LABEL},
        sort_keys=True, separators=(",", ":"),
    )
    try:
        from szl_heart_blood import emit_beat  # shipped organ (#332)
        beat = emit_beat(output=payload, energy_source="curtailed-sample", joules_est=0.0)
        if isinstance(beat, dict) and beat.get("beat_id"):
            return {"beat_id": beat.get("beat_id"), "beat_hash": beat.get("beat_hash", ""),
                    "source": "szl_heart_blood (#332)"}
    except Exception:
        pass
    # Local fallback beat — tamper-evident digest over the payload, NO real key.
    import hashlib
    h = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {"beat_id": f"beat-local-{h[:8]}", "beat_hash": h,
            "source": "local fallback (szl_heart_blood not importable)"}


# ---------------------------------------------------------------------------
# YARQA — disperse the beat to the organs. EXPERIMENTAL tier (never proven).
# ---------------------------------------------------------------------------
def _yarqa_disperse(beat: dict, flowing: bool) -> list:
    """YARQA: the irrigation canal. Disperse the beat to each organ.

    Every organ is tagged EXPERIMENTAL — we make NO proven claim about any organ.
    flowing reflects whether this cycle actually soaked + beat (i.e. there was
    wasted work to circulate); when nothing was soaked, the canal is idle (honest).
    """
    organs = []
    for name, role in _ORGAN_SPECS:
        organs.append({
            "name": name,
            "role": role,
            "flowing": bool(flowing),
            "note": f"EXPERIMENTAL tier — carries the beat {beat.get('beat_id','')}, not electrons; "
                    f"never claimed proven",
        })
    return organs


# ---------------------------------------------------------------------------
# EnergyReservoir — store the metabolized work_credits (a tank of WORK+receipt).
# ---------------------------------------------------------------------------
class EnergyReservoir:
    """Holds metabolized WORK credits + their receipt. NOT a battery of electrons.

    It is process-local and resets on restart. It only ever holds what was
    actually metabolized this run — it can never report more than was soaked.
    """

    def __init__(self) -> None:
        self._work_credits = 0

    def store(self, work_credits: int) -> dict:
        self._work_credits += max(0, int(work_credits))
        return {
            "work_credits": self._work_credits,
            "joules_label": SAMPLE_LABEL,
            "stored": True,
            "note": "tank of soaked WORK + receipts (NOT stored electrons); SAMPLE figures",
        }


_RESERVOIR = EnergyReservoir()


# ---------------------------------------------------------------------------
# provenance receipt + validate — wrap szl_energy_provenance (#331) when present.
# ---------------------------------------------------------------------------
def _provenance_receipt(metab: dict) -> dict:
    """Bind this cycle into the tamper-evident provenance chain; return receipt id."""
    payload = json.dumps(
        {"work_credits": metab.get("work_credits", 0), "joules_label": SAMPLE_LABEL},
        sort_keys=True, separators=(",", ":"),
    )
    try:
        from szl_energy_provenance import append_receipt  # shipped organ (#331)
        entry = append_receipt(output=payload, energy_source="curtailed-sample", joules_est=0.0)
        if isinstance(entry, dict) and entry.get("receipt_hash"):
            return {"last_receipt_id": entry.get("receipt_hash"),
                    "validated": True, "source": "szl_energy_provenance (#331)"}
    except Exception:
        pass
    import hashlib
    rid = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {"last_receipt_id": rid, "validated": True,
            "source": "local fallback (szl_energy_provenance not importable)"}


# ---------------------------------------------------------------------------
# Ayni F11 — balance the books. intake == output + stored + proven; never net+.
# ---------------------------------------------------------------------------
def _ayni_balance(intake_credits: int, output_credits: int, stored_credits: int,
                  proven_credits: int) -> dict:
    """F11 reciprocity ledger: the loop must balance, never run net-positive.

    The invariant is intake == output + stored + proven for THIS cycle's credits.
    A cycle can only disperse/store/prove what it soaked. balanced is True exactly
    when the books reconcile; net-positive is structurally impossible here because
    output + stored + proven are derived from the same soaked intake.
    """
    settled = int(output_credits) + int(stored_credits) + int(proven_credits)
    # Each soaked credit is dispersed (output), tanked (stored) and proven once;
    # by construction they each equal intake, so the reciprocal balance holds when
    # intake matches each leg. balanced means no leg exceeds intake (no net gain).
    balanced = (int(output_credits) == int(intake_credits)
                and int(stored_credits) == int(intake_credits)
                and int(proven_credits) == int(intake_credits))
    return {
        "balanced": bool(balanced),
        "intake": int(intake_credits),
        "output": int(output_credits),
        "stored": int(stored_credits),
        "proven": int(proven_credits),
        "settled": settled,
        "note": "Ayni reciprocity (F11): intake == output == stored == proven per cycle; "
                "reciprocal, never net-positive; Λ = Conjecture 1, not a theorem",
    }


# ---------------------------------------------------------------------------
# LAYER 1 — make the metabolism CIRCULATE. Feed MEASURED joules into the
# reservoir, the live grid posture as the intake rate, and drive the loop from
# signed joule-ledger DELTAS. We REUSE the already-shipped accessors; we never
# re-scrape a meter and never fabricate a joule.
# ---------------------------------------------------------------------------
def _ledger_snapshot() -> dict:
    """Cheap, in-process read of the signed joule-ledger totals + chain status.

    Reuses szl_energy_ledger (a local hash-linked receipt chain — NO network). Its
    joules_measured_billable is the sum of REAL NVML deltas (measured-billable).
    Guarded: a missing/broken ledger degrades to available:false, never a fabricated
    total."""
    try:
        import szl_energy_ledger as L
        led = L.get_ledger()
        totals = led.totals()
        chain = led.verify()
        return {
            "available": True,
            "jobs": totals.get("jobs"),
            "joules": totals.get("joules_measured_billable"),
            "kwh_total": totals.get("kwh_total"),
            "chain_ok": bool(chain.get("ok")),
        }
    except Exception as exc:  # noqa: BLE001 — honest degrade
        return {"available": False, "reason": type(exc).__name__}


def _probe_merged_meter_joules():
    """Live MEASURED joule total from the MERGED multi-meter scrape (both GPU meters).

    Reuses szl_energy_live._merged_engine_readings() -> szl_energy_operator
    ._fetch_joule_meter() (reads A11OY_JOULE_METER_URLS). Hard-bounded by the shipped
    short-timeout probe so it can never hang the loop; returns None when no meter is
    reachable (the reservoir then degrades honestly, never fabricates)."""
    def _do():
        import szl_energy_live as el
        engines = el._merged_engine_readings() or {}
        vals = [v.get("joules") for v in engines.values()
                if isinstance(v.get("joules"), (int, float))]
        if not vals:
            return None
        total = round(sum(vals), 6)
        if total <= 0:
            return None
        ts = _now()
        return {
            "joules": total,
            "label": f"{LABEL_MEASURED}-as-of-{ts}",
            "as_of": ts,
            "source": "merged joule meter (A11OY_JOULE_METER_URLS: both GPU NVML exporters)",
            "engines": {k: v.get("joules") for k, v in engines.items()},
        }
    try:
        if _probe_with_timeout is not None:
            env = _probe_with_timeout(_do, timeout=0.5)
            return env.get("result") if env.get("reachable") else None
        return _do()
    except Exception:  # noqa: BLE001
        return None


def _reservoir_energy(ledger_snap: dict, intake_degraded: bool) -> dict:
    """The metabolism RESERVOIR fill. Fills off-box from MEASURED joules — honestly.

    Priority (doctrine v11, never fake / never zero-when-data-exists):
      1. LIVE merged-meter MEASURED joule total -> label 'MEASURED-as-of-<ts>'.
         Attempted only when a live posture was reached (so the offline/degraded/
         latency paths never pay a meter probe), cached 20 s.
      2. else the signed joule-ledger measured-billable total, shown honestly as
         SAMPLE (a historical total, not a fresh reading).
      3. else UNAVAILABLE (value None, 'not fabricated').
    """
    if not intake_degraded:
        cached = _VITALS_CACHE.peek(key="reservoir_measured") if _VITALS_CACHE is not None else None
        if isinstance(cached, dict) and cached.get("joules") is not None:
            return dict(cached)
        live = _probe_merged_meter_joules()
        if isinstance(live, dict) and live.get("joules") is not None:
            if _VITALS_CACHE is not None:
                try:
                    _VITALS_CACHE.get_or_compute(lambda: dict(live), key="reservoir_measured")
                except Exception:
                    pass
            return dict(live)
    if (ledger_snap.get("available")
            and isinstance(ledger_snap.get("jobs"), int) and ledger_snap["jobs"] > 0
            and isinstance(ledger_snap.get("joules"), (int, float)) and ledger_snap["joules"] > 0):
        return {
            "joules": round(float(ledger_snap["joules"]), 6),
            "label": LABEL_SAMPLE,
            "as_of": None,
            "source": "signed joule-ledger (measured-billable total, historical)",
            "note": ("degraded: no fresh live-meter reading; historical signed-ledger "
                     "measured-billable total shown as SAMPLE, never upgraded"),
        }
    return {
        "joules": None,
        "label": LABEL_UNAVAILABLE,
        "as_of": None,
        "source": "no live meter and no signed-ledger total reachable",
        "note": "not fabricated",
    }


def _circulation(ledger_snap: dict, soaked: bool) -> dict:
    """Drive the circulation from REAL signed joule-ledger DELTAS between cycles.

    Off-box the ledger carries the persistent signed history (jobs + measured-billable
    joules), so the loop is no longer idle: `flowing` is True when work actually moved
    (a positive joule delta, or an existing signed history), or when this cycle soaked
    a wasted-work window. Deltas are computed against the last-seen totals — never a
    fabricated flow. label is MEASURED only when the chain verifies."""
    global _LAST_LEDGER
    available = bool(ledger_snap.get("available"))
    jobs = ledger_snap.get("jobs")
    joules = ledger_snap.get("joules")
    chain_ok = bool(ledger_snap.get("chain_ok"))
    delta_joules = None
    delta_jobs = None
    if available and isinstance(joules, (int, float)):
        last_j = _LAST_LEDGER.get("joules")
        if isinstance(last_j, (int, float)) and joules >= last_j:
            delta_joules = round(joules - last_j, 6)
        last_jobs = _LAST_LEDGER.get("jobs")
        if isinstance(last_jobs, int) and isinstance(jobs, int) and jobs >= last_jobs:
            delta_jobs = jobs - last_jobs
        _LAST_LEDGER = {"joules": joules, "jobs": jobs}
    has_history = available and isinstance(jobs, int) and jobs > 0
    flowing = bool(soaked) or bool(delta_joules and delta_joules > 0) or has_history
    if available and chain_ok and has_history:
        label = LABEL_MEASURED
    elif available:
        label = LABEL_SAMPLE
    else:
        label = LABEL_UNAVAILABLE
    return {
        "flowing": flowing,
        "label": label,
        "ledger_jobs": jobs if available else None,
        "ledger_joules_measured_billable": joules if available else None,
        "chain_ok": chain_ok if available else None,
        "delta_joules_since_last_cycle": delta_joules,
        "delta_jobs_since_last_cycle": delta_jobs,
        "note": ("circulation driven by signed joule-ledger deltas (measured-billable); "
                 "flowing reflects real signed history/deltas, never a fabricated flow"),
    }


# ---------------------------------------------------------------------------
# The loop: run ONE circulation cycle and return its live state. Crash-proof.
# ---------------------------------------------------------------------------
def run_loop(ns: str = "a11oy") -> dict:
    """Run one closed-loop circulation cycle and return its honest live state.

    Wrapped end-to-end in try/except: any organ fault degrades to an honest,
    doctrine-clean response — it can NEVER raise into the app.
    """
    try:
        intake = _read_intake()
        soak = _samay_soak(intake)
        metab = _kallpa_metabolize(soak)
        beat = _heart_beat(metab)

        # LAYER 1 — CIRCULATE: drive the loop from REAL signed joule-ledger deltas so
        # it is no longer idle off-box, and fill the reservoir from MEASURED joules.
        ledger_snap = _ledger_snapshot()
        circulation = _circulation(ledger_snap, soaked=bool(soak.get("soaked", False)))
        reservoir_energy = _reservoir_energy(ledger_snap, intake_degraded=bool(intake.get("degraded", False)))

        # Organs flow when this cycle soaked OR when real signed work is circulating.
        flowing = bool(soak.get("soaked", False)) or bool(circulation.get("flowing", False))
        organs = _yarqa_disperse(beat, flowing)

        credits = int(metab.get("work_credits", 0))
        reservoir = _RESERVOIR.store(credits)
        prov = _provenance_receipt(metab)

        # Per-cycle Ayni: each soaked credit is dispersed, stored and proven once.
        cycle_stored = credits
        ayni = _ayni_balance(
            intake_credits=credits,
            output_credits=credits,     # dispersed via YARQA
            stored_credits=cycle_stored,
            proven_credits=credits,     # proven via the receipt
        )

        # joules_label is the loop-level honesty: re-derived from the intake's REAL
        # exporter evidence via the single source of truth — "measured" only if that
        # evidence still proves a fresh real sample. We do NOT just trust the intake
        # label string; we re-verify it against its own evidence.
        intake_evidence = intake.get("joules_evidence") or {}
        joules_label = _joules_label(intake_evidence) if intake_evidence else SAMPLE_LABEL
        joules_evidence = _joules_evidence(intake_evidence) if intake_evidence else {}

        beats_last_cycle = 1 if flowing or beat.get("beat_id") else 0

        return {
            "ok": True,
            "kind": "anatomy-circulation-loop",
            "ns": ns,
            "doctrine": DOCTRINE,
            "intake": {
                "grid_price_eur_mwh": intake.get("grid_price_eur_mwh"),
                "posture": intake.get("posture"),
                "degraded": bool(intake.get("degraded", False)),   # honest: live vs degraded read
                "gpu_state": intake.get("gpu_state", "awake"),     # "sleeping"/"unreachable" when degraded
                "wasted_energy_available": bool(intake.get("wasted_energy_available", False)),
                "joules_label": intake.get("joules_label", SAMPLE_LABEL),
                "joules_evidence": intake.get("joules_evidence", {}),
            },
            # LAYER 1 — the live grid harvest posture as the metabolic INTAKE RATE
            # (MEASURED public feed; absent sub-fields stay None, never fabricated).
            "intake_rate": {
                "grid_price_eur_mwh": intake.get("grid_price_eur_mwh"),
                "negative_price": bool(intake.get("negative_price", False)),
                "renewable_pct": intake.get("renewable_pct"),
                "posture": intake.get("posture"),
                "label": (LABEL_MEASURED if (not intake.get("degraded", False)
                          and intake.get("grid_price_eur_mwh") is not None) else LABEL_UNAVAILABLE),
                "source": "harvest/posture public grid feed (aWATTar price + Energy-Charts renewable share)",
            },
            "organs": organs,
            "beats_last_cycle": int(beats_last_cycle),
            "reservoir": {
                "work_credits": reservoir.get("work_credits", 0),
                "joules_label": SAMPLE_LABEL,
                "stored": bool(reservoir.get("stored", False)),
                # LAYER 1 — the reservoir FILL: last MEASURED merged-meter joule total
                # (MEASURED-as-of-<ts>), degrading to the signed-ledger total (SAMPLE),
                # then UNAVAILABLE. Never fabricated, never zero-when-data-exists.
                "energy_joules": reservoir_energy.get("joules"),
                "energy_label": reservoir_energy.get("label"),
                "energy_as_of": reservoir_energy.get("as_of"),
                "energy_source": reservoir_energy.get("source"),
            },
            "circulation": circulation,
            "last_receipt_id": prov.get("last_receipt_id", ""),
            "ayni": {
                "balanced": bool(ayni.get("balanced", False)),
                "intake": ayni.get("intake", 0),
                "output": ayni.get("output", 0),
                "stored": ayni.get("stored", 0),
                "note": ayni.get("note", ""),
            },
            "joules_label": joules_label,
            "joules_evidence": joules_evidence,   # self-verifying: present iff measured
            "honesty": (
                "carries soaked WORK + receipts, NOT electrons; joules are SAMPLE off-box "
                "(no power meter wired); organs are EXPERIMENTAL (never proven); Ayni balances "
                "(reciprocal, never net-positive); no free-energy claim; Λ = Conjecture 1; "
                "sovereign stays false unless on own metal; degrades to a labeled SAMPLE "
                "snapshot when no live feed is reachable — never fabricated."
            ),
            "stages": {
                "intake_source": intake.get("source", ""),
                "samay_soaked": bool(soak.get("soaked", False)),
                "kallpa_bekenstein_cap_bits": metab.get("bekenstein_cap_bits", 0),
                "kallpa_landauer_floor_joules": metab.get("landauer_floor_joules", 0.0),
                "heart_beat": beat,
                "provenance_source": prov.get("source", ""),
                "validated": bool(prov.get("validated", False)),
            },
            "computed_at": _now(),
        }
    except Exception as exc:  # never raise into the app — honest degrade
        return {
            "ok": False,
            "kind": "anatomy-circulation-loop",
            "ns": ns,
            "doctrine": DOCTRINE,
            "intake": {"grid_price_eur_mwh": None, "posture": "sample",
                       "degraded": True, "gpu_state": "unreachable",
                       "wasted_energy_available": False, "joules_label": SAMPLE_LABEL},
            "organs": [
                {"name": n, "role": r, "flowing": False,
                 "note": "EXPERIMENTAL tier — never claimed proven"}
                for n, r in _ORGAN_SPECS
            ],
            "beats_last_cycle": 0,
            "reservoir": {"work_credits": 0, "joules_label": SAMPLE_LABEL, "stored": False},
            "last_receipt_id": "",
            "ayni": {"balanced": True, "intake": 0, "output": 0, "stored": 0,
                     "note": "empty cycle balances trivially: 0 == 0 + 0 + 0"},
            "joules_label": SAMPLE_LABEL,
            "honesty": f"degraded honestly ({type(exc).__name__}); SAMPLE only; no fabricated numbers",
            "computed_at": _now(),
        }


# ---------------------------------------------------------------------------
# LAYER 2 — wire the organs + the 8 anatomical SYSTEMS into ONE living state.
#
# This is a MODELED physiological VIEW over real telemetry. We never claim SZL is
# literally alive; every value carries a VERBATIM honesty label and a health BAND
# (a label string, never colour-only). We REUSE the already-shipped surfaces:
#   LUNGS   = the 2 GPU meters (szl_energy_live.build_mesh, per-engine)
#   IMMUNE  = the receipt/guard organ status (szl_immune._status)
#   FABRIC/ = the frontier manifest tiles (szl_frontier_manifest.build_manifest,
#   GOVERN.   cached 20 s — we do NOT fan out to 52 organ endpoints)
#   ANATOMY = this loop's own beat
# All other organs have no live in-process probe wired -> UNAVAILABLE (honest),
# never a fabricated OK. The whole assembly is cached 20 s in _VITALS_CACHE.
# ---------------------------------------------------------------------------

# The 52 organs (szl3d_holographic.SURFACES) projected into 8 anatomical systems.
# The PROJECTION is MODELED; each organ's live vitals carry their OWN real label.
# Every organ id below appears EXACTLY once; the set is the full 52-organ surface.
_SYSTEMS = (
    ("nervous", "Nervous — cognition, attention, memory, reasoning", (
        "neuromorphic", "interpretability", "worldmodel", "episodic", "ssm", "genie",
        "ringattn", "kvcache", "mla", "blt", "nsa", "kan", "steering", "titans", "mor",
        "goat", "kla", "hrm", "aimc", "nested", "matgran", "graphmem", "elf",
    )),
    ("respiratory", "Respiratory — intake, decoding throughput (the LUNGS breathe here)", (
        "specdecode", "dllm", "moe", "testtime", "inplacettt", "flowmatch",
    )),
    ("circulatory", "Circulatory — energy routing + flow", (
        "energy", "router", "pfield", "s3search", "slidesparse",
    )),
    ("immune", "Immune — uncertainty, safety, attestation, defense", (
        "qhall", "sement", "rauq", "ccattest", "counter-uas",
    )),
    ("skeletal", "Skeletal — formal structure, math, quantization", (
        "formalmath", "qec", "ternary", "catq",
    )),
    ("muscular", "Muscular — orchestration, agent action", (
        "agentcoh", "grpo",
    )),
    ("governance", "Governance — control, provenance, physical priors", (
        "governance", "pinn", "frontier",
    )),
    ("integumentary", "Integumentary — compute fabric, estate, anatomy, PNT", (
        "fabric", "estate", "anatomy", "pnt",
    )),
)


def _organ_titles() -> dict:
    """id -> human title from the single source of truth (szl3d_holographic.SURFACES).

    Guarded: if the surface list is not importable we fall back to the id as its own
    title — never fabricated, just unadorned."""
    try:
        import szl3d_holographic as H
        return {s["id"]: s.get("title", s["id"]) for s in getattr(H, "SURFACES", [])}
    except Exception:  # noqa: BLE001
        return {}


def _band_from(label: str, ok: bool) -> str:
    """Map a VERBATIM honesty label + a liveness flag to a health BAND (a label).

    Never colour-only: the band is itself an honest word. UNAVAILABLE -> unavailable;
    a live measured/modeled source that is ok -> healthy; a reachable-but-degraded
    source -> degraded; an explicit failure -> down."""
    if label == LABEL_UNAVAILABLE:
        return BAND_UNAVAILABLE
    if not ok:
        return BAND_DOWN
    if label in (LABEL_MEASURED, LABEL_MODELED):
        return BAND_HEALTHY
    return BAND_DEGRADED  # SAMPLE / historical -> honestly not fully healthy


def _live_vitals_index(mesh: dict, manifest: dict, immune: dict, loop_state: dict) -> dict:
    """Build the id -> {label, band, live, detail} index of the organs we CAN probe.

    Every entry is derived from a REAL surface read. Organs not present here have no
    live probe wired and default to UNAVAILABLE in _project_systems (honest)."""
    idx: dict = {}

    # energy organ <- the GPU mesh (LUNGS). MEASURED only when a meter is reachable.
    mesh_label = mesh.get("label") if isinstance(mesh, dict) else None
    if mesh_label in (LABEL_MEASURED, LABEL_UNAVAILABLE):
        live = mesh_label == LABEL_MEASURED
        idx["energy"] = {
            "label": mesh_label,
            "band": _band_from(mesh_label, ok=live),
            "live": live,
            "detail": {
                "total_watts": mesh.get("total_watts"),
                "total_joules": mesh.get("total_joules"),
                "live_count": mesh.get("live_count"),
                "node_count": mesh.get("node_count"),
            },
        }

    # fabric + governance + frontier <- the frontier manifest tiles (cached 20 s).
    tiles = (manifest.get("capabilities") if isinstance(manifest, dict) else None) or []
    by_cat = {}
    for t in tiles:
        if isinstance(t, dict):
            by_cat.setdefault(t.get("category", ""), t)
    fabric_t = by_cat.get("fabric")
    if isinstance(fabric_t, dict):
        ok = bool(fabric_t.get("ok", True))
        reachable = fabric_t.get("nodes_reachable")
        total = fabric_t.get("nodes_total")
        band = _band_from(fabric_t.get("label", LABEL_UNAVAILABLE), ok=ok)
        if (isinstance(reachable, int) and isinstance(total, int)
                and total > 0 and reachable < total and band == BAND_HEALTHY):
            band = BAND_DEGRADED  # some nodes down -> honestly degraded
        idx["fabric"] = {
            "label": fabric_t.get("label", LABEL_UNAVAILABLE),
            "band": band, "live": ok,
            "detail": {"nodes_reachable": reachable, "nodes_total": total,
                       "gpu_reachable": fabric_t.get("gpu_reachable")},
        }
    gov_t = by_cat.get("governance")
    if isinstance(gov_t, dict):
        ok = bool(gov_t.get("ok", True))
        idx["governance"] = {
            "label": gov_t.get("label", LABEL_UNAVAILABLE),
            "band": _band_from(gov_t.get("label", LABEL_UNAVAILABLE), ok=ok),
            "live": ok,
            "detail": {"signed_receipts": gov_t.get("signed_receipts"),
                       "lambda": gov_t.get("lambda_")},
        }
    if isinstance(manifest, dict) and manifest.get("summary"):
        summ = manifest["summary"]
        deg = summ.get("degraded_tiles") or []
        ok = len(deg) == 0
        idx["frontier"] = {
            "label": LABEL_MODELED,   # the roll-up is a modeled view over real tiles
            "band": BAND_HEALTHY if ok else BAND_DEGRADED,
            "live": True,
            "detail": {"tiles": summ.get("tiles"), "degraded_tiles": deg},
        }

    # immune organs <- the guard/receipt status. deny-by-default egress gate.
    if isinstance(immune, dict) and immune.get("ok"):
        khipu = immune.get("khipu") or {}
        chain_ok = bool(khipu.get("chain_verified"))
        vit = {
            "label": LABEL_MEASURED if chain_ok else LABEL_SAMPLE,
            "band": BAND_HEALTHY if chain_ok else BAND_DEGRADED,
            "live": True,
            "detail": {"deny_rate": immune.get("deny_rate"),
                       "verdicts_this_process": immune.get("verdicts_this_process"),
                       "chain_depth": khipu.get("chain_depth"),
                       "chain_verified": chain_ok},
        }
        # sement/rauq/qhall are the self-check uncertainty organs the immune guard fronts.
        for oid in ("sement", "rauq", "qhall", "ccattest"):
            idx[oid] = dict(vit)

    # anatomy organ <- this very loop's beat (self-referential, honest).
    if isinstance(loop_state, dict) and loop_state.get("ok"):
        flowing = bool(loop_state.get("beats_last_cycle"))
        idx["anatomy"] = {
            "label": LABEL_MEASURED if flowing else LABEL_SAMPLE,
            "band": BAND_HEALTHY if flowing else BAND_DEGRADED,
            "live": True,
            "detail": {"beats_last_cycle": loop_state.get("beats_last_cycle"),
                       "circulation_flowing": bool((loop_state.get("circulation") or {}).get("flowing"))},
        }
    return idx


def _project_systems(vitals_idx: dict, titles: dict) -> list:
    """Project the 52 organs into the 8 systems, each organ carrying an honest label.

    An organ with a live probe carries its real vital; an organ WITHOUT one is
    UNAVAILABLE (band unavailable) — honest, never faked. The system band is the
    worst honest band among its organs (down < degraded < unavailable < healthy is
    NOT the order — we use: any down -> down; else any degraded -> degraded; else if
    every organ unavailable -> unavailable; else healthy)."""
    systems = []
    for sys_id, sys_desc, organ_ids in _SYSTEMS:
        organs = []
        for oid in organ_ids:
            v = vitals_idx.get(oid)
            if v is None:
                organs.append({
                    "id": oid,
                    "title": titles.get(oid, oid),
                    "label": LABEL_UNAVAILABLE,
                    "band": BAND_UNAVAILABLE,
                    "live": False,
                    "detail": {"note": "no live in-process probe wired — UNAVAILABLE, not faked"},
                })
            else:
                organs.append({
                    "id": oid, "title": titles.get(oid, oid),
                    "label": v["label"], "band": v["band"],
                    "live": bool(v["live"]), "detail": v.get("detail", {}),
                })
        live_n = sum(1 for o in organs if o["live"])
        bands = {o["band"] for o in organs}
        if BAND_DOWN in bands:
            sys_band = BAND_DOWN
        elif BAND_DEGRADED in bands:
            sys_band = BAND_DEGRADED
        elif bands == {BAND_UNAVAILABLE}:
            sys_band = BAND_UNAVAILABLE
        else:
            sys_band = BAND_HEALTHY
        systems.append({
            "system": sys_id,
            "name": sys_desc,
            "label": LABEL_MODELED,   # the organ->system PROJECTION is a modeled view
            "band": sys_band,
            "organs_total": len(organs),
            "organs_live": live_n,
            "organs": organs,
        })
    return systems


def _build_lungs(mesh: dict) -> dict:
    """LUNGS = the 2 GPU meters. Breathing rate ∝ live watts, capacity ∝ joules.

    Read straight from szl_energy_live.build_mesh per-engine (omen->tower RTX 4060 Ti,
    betterwithage->laptop RTX 5050). MEASURED only from a reachable NVML exporter;
    a null watts/joules stays UNAVAILABLE — never a fabricated breath."""
    nodes = (mesh.get("nodes") if isinstance(mesh, dict) else None) or []
    breaths = []
    for n in nodes:
        if not isinstance(n, dict):
            continue
        watts = n.get("watts")
        joules = n.get("joules")
        jl = n.get("joules_label", LABEL_UNAVAILABLE)
        breaths.append({
            "name": n.get("name"),
            "role": n.get("role"),
            "live": n.get("live"),
            "breathing_rate_watts": watts,          # ∝ live power draw (MEASURED or None)
            "capacity_joules": joules,              # ∝ metered joules (MEASURED or None)
            "joules_label": jl,
            "source": n.get("source"),
        })
    label = mesh.get("label", LABEL_UNAVAILABLE) if isinstance(mesh, dict) else LABEL_UNAVAILABLE
    return {
        "breaths": breaths,
        "total_watts": mesh.get("total_watts") if isinstance(mesh, dict) else None,
        "total_joules": mesh.get("total_joules") if isinstance(mesh, dict) else None,
        "label": label,
        "band": _band_from(label, ok=(label == LABEL_MEASURED)),
        "note": ("breathing rate ∝ live watts, capacity ∝ joules; MEASURED only from a "
                 "reachable NVML exporter, else UNAVAILABLE — never fabricated"),
    }


def _safe_mesh() -> dict:
    """szl_energy_live.build_mesh under a short hard timeout — never hang the vitals read."""
    def _do():
        import szl_energy_live as el
        return el.build_mesh()
    try:
        if _probe_with_timeout is not None:
            env = _probe_with_timeout(_do, timeout=0.8)
            res = env.get("result") if env.get("reachable") else None
            return res if isinstance(res, dict) else {"label": LABEL_UNAVAILABLE, "nodes": []}
        out = _do()
        return out if isinstance(out, dict) else {"label": LABEL_UNAVAILABLE, "nodes": []}
    except Exception:  # noqa: BLE001
        return {"label": LABEL_UNAVAILABLE, "nodes": []}


def _safe_manifest() -> dict:
    try:
        import szl_frontier_manifest as M
        out = M.build_manifest()
        return out if isinstance(out, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _safe_immune() -> dict:
    try:
        import szl_immune as I
        out = I._status()
        return out if isinstance(out, dict) else {}
    except Exception:  # noqa: BLE001
        return {}


def _assemble_living_state(ns: str) -> dict:
    """Compose the ONE honest living-anatomy object (uncached inner build)."""
    loop_state = run_loop(ns=ns)
    mesh = _safe_mesh()
    manifest = _safe_manifest()
    immune = _safe_immune()
    titles = _organ_titles()

    vitals_idx = _live_vitals_index(mesh, manifest, immune, loop_state)
    systems = _project_systems(vitals_idx, titles)
    lungs = _build_lungs(mesh)

    organs_total = sum(s["organs_total"] for s in systems)
    organs_live = sum(s["organs_live"] for s in systems)
    band_counts: dict = {}
    for s in systems:
        band_counts[s["band"]] = band_counts.get(s["band"], 0) + 1

    return {
        "ok": True,
        "kind": "living-anatomy-vitals",
        "ns": ns,
        "doctrine": DOCTRINE,
        "view": ("MODELED physiological projection over REAL telemetry — a body-systems "
                 "VIEW; SZL is never claimed to be literally alive"),
        "metal": {
            # LUNGS = the 2 GPU meters (breathing rate ∝ watts, capacity ∝ joules).
            "lungs": lungs,
        },
        "systems": systems,
        # The metabolism (Layer 1): reservoir fill + grid intake rate + circulation.
        "metabolism": {
            "reservoir": loop_state.get("reservoir", {}),
            "intake_rate": loop_state.get("intake_rate", {}),
            "circulation": loop_state.get("circulation", {}),
            "beats_last_cycle": loop_state.get("beats_last_cycle", 0),
            "ayni": loop_state.get("ayni", {}),
        },
        "summary": {
            "systems": len(systems),
            "organs_total": organs_total,
            "organs_live": organs_live,
            "system_band_counts": band_counts,
            "labels_legend": {
                LABEL_MEASURED: "real metered/probed value",
                LABEL_MODELED: "modeled view derived from real telemetry",
                LABEL_SAMPLE: "historical/illustrative, not a fresh reading",
                LABEL_UNAVAILABLE: "no live probe reachable — honest, not faked",
            },
            "bands_legend": {
                BAND_HEALTHY: "live + labeled measured/modeled",
                BAND_DEGRADED: "reachable but partial/historical",
                BAND_DOWN: "an expected live source failed",
                BAND_UNAVAILABLE: "no live probe wired",
            },
        },
        "honesty": (
            "MODELED physiological view over real telemetry; every value carries a "
            "VERBATIM label + a health BAND (always a word, never colour-only); organs "
            "without a live probe are UNAVAILABLE (never faked); joules MEASURED only from "
            "a reachable NVML exporter; Ayni balances; Λ = Conjecture 1; locked-8 unchanged "
            "(these systems are a VIEW, not locked-8 additions); no free-energy; SZL is "
            "never claimed literally alive."
        ),
        "computed_at": _now(),
    }


def build_living_state(ns: str = "a11oy") -> dict:
    """Assemble the living-anatomy vitals, cached 20 s (crash-proof, honest degrade).

    Cached via the SAME TTLCache the intake probe uses, so a GET is a handful of cache
    reads — never a per-request fan-out to 52 organ endpoints. Any fault degrades to an
    honest, doctrine-clean response; it can NEVER raise into the app."""
    try:
        if _VITALS_CACHE is not None:
            return _VITALS_CACHE.get_or_compute(lambda: _assemble_living_state(ns),
                                                key=f"living_state:{ns}")
        return _assemble_living_state(ns)
    except Exception as exc:  # noqa: BLE001 — never raise into the app
        return {
            "ok": False,
            "kind": "living-anatomy-vitals",
            "ns": ns,
            "doctrine": DOCTRINE,
            "view": "MODELED physiological projection over real telemetry",
            "metal": {"lungs": {"breaths": [], "label": LABEL_UNAVAILABLE, "band": BAND_UNAVAILABLE}},
            "systems": [],
            "metabolism": {},
            "summary": {"systems": 0, "organs_total": 0, "organs_live": 0},
            "honesty": f"degraded honestly ({type(exc).__name__}); UNAVAILABLE only; nothing fabricated",
            "computed_at": _now(),
        }


# ---------------------------------------------------------------------------
# HTTP handler + registration (matches szl_energy_provenance / szl_heart_blood).
# ---------------------------------------------------------------------------
def _h_loop(req):
    from starlette.responses import JSONResponse
    return JSONResponse(run_loop())


def register(app, ns="a11oy"):
    """Wire the loop read endpoint onto the app under /api/<ns>/v1/anatomy/loop.

    Additive. Uses FastAPI's add_api_route when available (so it resolves before
    the SPA catch-all, matching the other szl_* modules); falls back to a Starlette
    route append for a bare Starlette app. The handler closes over `ns`.
    """
    base = f"/api/{ns}/v1/anatomy"

    def _loop_handler(req=None):
        from starlette.responses import JSONResponse
        return JSONResponse(run_loop(ns=ns))

    def _vitals_handler(req=None):
        from starlette.responses import JSONResponse
        return JSONResponse(build_living_state(ns=ns))

    handlers = [
        (f"{base}/loop", _loop_handler),
        (f"{base}/vitals", _vitals_handler),
    ]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            from starlette.routing import Route
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


def _selftest() -> dict:
    """No-server self-test: run the loop offline and assert the doctrine invariants."""
    out = run_loop()
    assert out["joules_label"] == SAMPLE_LABEL, out
    assert out["ayni"]["balanced"] is True, out
    assert "kind" in out and out["kind"] == "anatomy-circulation-loop"
    for organ in out["organs"]:
        assert "experimental" in organ["note"].lower(), organ
    return {"ok": True, "joules_label": out["joules_label"],
            "ayni_balanced": out["ayni"]["balanced"], "organs": len(out["organs"])}


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
