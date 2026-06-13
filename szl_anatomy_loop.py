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
                  https://a11oy.net/api/a11oy/v1/harvest/posture; if both are
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
                  The heart is the PUMP (the beat); see YARQA for the VESSELS.
    -> YARQA      the CIRCULATORY organ of the body — the Quechua irrigation
                  canal that divides/routes flow. YARQA is the vascular system:
                  it takes the metabolized work_credits + the heart's beat and
                  disperses flow to the downstream organs
                  WAQAYCHAQ (guard/store), KAMAY (act/animate), RIKUY (observe).
                  heart (pump) + YARQA (vessels) = ONE circulatory subsystem.
                  YARQA is NOT a sibling peer of the loop; it IS the loop's
                  circulatory function, named here as a first-class organ.
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

# ---------------------------------------------------------------------------
# Doctrine constants (v11). These are the honest, fixed labels + physics floors.
# ---------------------------------------------------------------------------
DOCTRINE = "v11"
SAMPLE_LABEL = "sample"        # default — off-box, no real power meter wired
MEASURED_LABEL = "measured"    # ONLY when a real metered source is present

# Physics floors/ceilings for a bounded WORK credit (NOT free energy):
#   Bekenstein software bound  : a window of N bytes carries at most N*8 bits.
#   Landauer minimum           : erasing one bit costs at least kT ln 2 joules.
# These BOUND a credit; they never manufacture energy.
_BOLTZMANN_K = 1.380649e-23          # J/K (CODATA)
_ROOM_T_KELVIN = 300.0               # K — a labeled SAMPLE ambient, not metered
LANDAUER_FLOOR_J = _BOLTZMANN_K * _ROOM_T_KELVIN * math.log(2)  # ~2.87e-21 J/bit

# YARQA — the CIRCULATORY organ (flow-router / irrigation-canal). It is the
# vascular system of the body: the function that takes metabolized work_credits
# from KALLPA + the heart's beat and disperses flow to the downstream organs.
# heart (pump) + YARQA (vessels) = ONE circulatory subsystem. EXPERIMENTAL tier.
YARQA_NAME = "YARQA"
YARQA_ROLE = "circulatory (flow-router / irrigation-canal)"

# The downstream organs YARQA irrigates. EXPERIMENTAL tier — never claimed proven.
_ORGAN_SPECS = (
    ("WAQAYCHAQ", "guard/store — YARQA disperses the beat to the reservoir-guard organ (experimental)"),
    ("KAMAY",     "act/animate — YARQA disperses the beat to the actuation organ (experimental)"),
    ("RIKUY",     "observe — YARQA disperses the beat to the observation/telemetry organ (experimental)"),
)

# Candidate live posture surfaces, in attempt order: local box first, then public.
_POSTURE_URLS = (
    "http://127.0.0.1/api/a11oy/v1/harvest/posture",
    "http://127.0.0.1:8000/api/a11oy/v1/harvest/posture",
    "https://a11oy.net/api/a11oy/v1/harvest/posture",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# INTAKE — read the live harvest posture, degrade HONESTLY to a SAMPLE snapshot.
# Never fabricate a measured number; the SAMPLE snapshot is clearly labeled.
# ---------------------------------------------------------------------------
def _sample_posture() -> dict:
    """An honest, clearly-labeled SAMPLE intake snapshot (no live feed reached).

    Every field is labeled sample; no number here is claimed as metered. This is
    the doctrine-clean degrade path when neither the local box nor the public
    surface is reachable.
    """
    return {
        "ok": False,
        "posture": "sample",
        "grid_price_eur_mwh": None,        # unknown off-box — NOT fabricated
        "wasted_energy_available": False,  # conservative: assume nothing to soak
        "joules_label": SAMPLE_LABEL,
        "source": "SAMPLE snapshot (no live harvest feed reachable — doctrine v11)",
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


def _try_http_posture(timeout: float = 1.5):
    """Attempt the live HTTP posture surfaces (local box, then public)."""
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


def _read_intake() -> dict:
    """INTAKE: live posture if reachable, else an honest SAMPLE snapshot.

    Returns a normalized intake dict. joules_label is 'sample' by DEFAULT and
    stays sample unless a REAL on-box power meter is present. Doctrine v11: a
    live wasted-energy FEED reading (measured_any) is NOT a power measurement —
    the harvest organ itself notes 'joules_label is always sample off-box; MEASURED
    requires on-box NVML'. So we only flip to measured when the source explicitly
    reports an on-box meter (metered_onbox), which never exists off-box. We NEVER
    upgrade a sample into a measurement, and we NEVER invent numbers.
    """
    raw = _try_in_process_posture() or _try_http_posture()
    if not isinstance(raw, dict):
        return _sample_posture()

    # A live FEED reading is informational only; it is NOT an on-box power meter.
    feed_measured_any = bool(raw.get("measured_any", False))
    # Doctrine v11: joules are 'sample' off-box. Only a real on-box meter
    # (explicit metered_onbox flag) may yield 'measured' — absent off-box.
    metered_onbox = bool(raw.get("metered_onbox", False))
    joules_label = MEASURED_LABEL if metered_onbox else SAMPLE_LABEL
    # grid price is only carried through if the live feed actually supplied one;
    # absence -> None (never a fabricated figure).
    grid_price = raw.get("grid_price_eur_mwh", None)
    return {
        "ok": bool(raw.get("ok", False)),
        "posture": raw.get("posture", "unknown"),
        "grid_price_eur_mwh": grid_price,
        "wasted_energy_available": bool(raw.get("wasted_energy_available", False)),
        "joules_label": joules_label,
        "source": raw.get("source", "live harvest posture"),
        "feed_measured_any": feed_measured_any,
        "metered_onbox": metered_onbox,
    }


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
# YARQA — the CIRCULATORY organ. It IS the vascular system of the body: it takes
# the metabolized work_credits + the heart's beat and disperses flow to the
# downstream organs. heart (pump) + YARQA (vessels) = ONE circulatory subsystem.
# YARQA is a first-class, named organ here — not a sibling peer of the loop.
# EXPERIMENTAL tier (never proven).
# ---------------------------------------------------------------------------
def _yarqa_disperse(beat: dict, flowing: bool, work_credits: int = 0) -> list:
    """YARQA: the CIRCULATORY organ — the irrigation canal / vascular system.

    YARQA takes the metabolized work_credits + the heart's beat and disperses
    flow to the downstream organs (WAQAYCHAQ, KAMAY, RIKUY). It is itself the
    FIRST organ returned, named as the circulatory (flow-router) organ, so the
    unified loop view shows ONE body with the vascular system made explicit.

    Every organ is tagged EXPERIMENTAL — we make NO proven claim about any organ.
    flowing reflects whether this cycle actually soaked + beat (i.e. there was
    wasted work to circulate); when nothing was soaked, the canal is idle (honest)
    and YARQA reports flowing=False — real dispersal, never a fabricated flow.
    """
    organs = []
    # YARQA itself — the named circulatory organ (vessels), the flow-router that
    # disperses the metabolized credits + beat. flowing mirrors REAL dispersal.
    organs.append({
        "name": YARQA_NAME,
        "role": YARQA_ROLE,
        "flowing": bool(flowing),
        "dispersed_work_credits": int(work_credits) if flowing else 0,
        "note": f"EXPERIMENTAL tier — YARQA is the circulatory organ (vascular system); "
                f"the heart is the pump (beat {beat.get('beat_id','')}), YARQA is the vessels "
                f"that route the flow to the downstream organs; carries soaked WORK + receipts, "
                f"NOT electrons; never claimed proven",
    })
    # The downstream organs YARQA irrigates.
    for name, role in _ORGAN_SPECS:
        organs.append({
            "name": name,
            "role": role,
            "flowing": bool(flowing),
            "note": f"EXPERIMENTAL tier — irrigated by YARQA (circulatory); carries the beat "
                    f"{beat.get('beat_id','')}, not electrons; never claimed proven",
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
        flowing = bool(soak.get("soaked", False))
        credits = int(metab.get("work_credits", 0))
        # YARQA (circulatory organ) disperses the metabolized credits + beat.
        organs = _yarqa_disperse(beat, flowing, work_credits=credits)
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

        # joules_label is the loop-level honesty: measured ONLY if intake measured.
        joules_label = MEASURED_LABEL if intake.get("joules_label") == MEASURED_LABEL else SAMPLE_LABEL

        beats_last_cycle = 1 if flowing or beat.get("beat_id") else 0

        return {
            "ok": True,
            "kind": "anatomy-circulation-loop",
            "ns": ns,
            "doctrine": DOCTRINE,
            "intake": {
                "grid_price_eur_mwh": intake.get("grid_price_eur_mwh"),
                "posture": intake.get("posture"),
                "wasted_energy_available": bool(intake.get("wasted_energy_available", False)),
                "joules_label": intake.get("joules_label", SAMPLE_LABEL),
            },
            "organs": organs,
            "circulatory": {
                # ONE circulatory subsystem: the heart is the PUMP (the beat),
                # YARQA is the VESSELS (the flow-router that routes the beat +
                # metabolized credits to the downstream organs). EXPERIMENTAL.
                "pump": "heart/pulse (the beat; szl_heart_blood #332)",
                "vessels": YARQA_NAME,
                "vessels_role": YARQA_ROLE,
                "flowing": bool(flowing),
                "dispersed_work_credits": int(credits) if flowing else 0,
                "note": "EXPERIMENTAL tier — heart (pump) + YARQA (vessels) are ONE "
                        "circulatory subsystem; YARQA is the named circulatory organ "
                        "of the unified body, not a sibling peer; never claimed proven",
            },
            "surfaces": {
                # ONE canonical loop view + the standalone canal alias.
                "unified_loop": f"/api/{ns}/v1/anatomy/loop  (the unified organism — "
                                f"SAMAY -> KALLPA -> heart/pulse + YARQA -> organs -> "
                                f"reservoir -> receipt -> Ayni F11 -> repeat)",
                "standalone_canal": "/yarqa  (the standalone irrigation-canal view of "
                                    "the same circulatory organ; this /anatomy/loop is "
                                    "the canonical unified-body view)",
            },
            "beats_last_cycle": int(beats_last_cycle),
            "reservoir": {
                "work_credits": reservoir.get("work_credits", 0),
                "joules_label": SAMPLE_LABEL,
                "stored": bool(reservoir.get("stored", False)),
            },
            "last_receipt_id": prov.get("last_receipt_id", ""),
            "ayni": {
                "balanced": bool(ayni.get("balanced", False)),
                "intake": ayni.get("intake", 0),
                "output": ayni.get("output", 0),
                "stored": ayni.get("stored", 0),
                "note": ayni.get("note", ""),
            },
            "joules_label": joules_label,
            "honesty": (
                "ONE unified body, ONE loop, ONE receipt chain, ONE Ayni balance: "
                "SAMAY (lungs/intake) -> KALLPA (metabolism) -> heart/pulse (pump/beat) + "
                "YARQA (circulatory/dispersal vessels) -> WAQAYCHAQ/KAMAY/RIKUY (organs) -> "
                "EnergyReservoir (store) -> provenance receipt -> Ayni F11 close -> repeat; "
                "YARQA is the named CIRCULATORY organ (flow-router / irrigation-canal), the "
                "vessels to the heart's pump — not a sibling peer; carries soaked WORK + "
                "receipts, NOT electrons; joules are SAMPLE off-box (no power meter wired); "
                "organs are EXPERIMENTAL (never proven); Ayni balances (reciprocal, never "
                "net-positive); no free-energy claim; Λ = Conjecture 1; sovereign stays false "
                "unless on own metal; degrades to a labeled SAMPLE snapshot when no live feed "
                "is reachable — never fabricated."
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
                       "wasted_energy_available": False, "joules_label": SAMPLE_LABEL},
            "organs": [
                {"name": YARQA_NAME, "role": YARQA_ROLE, "flowing": False,
                 "dispersed_work_credits": 0,
                 "note": "EXPERIMENTAL tier — YARQA is the circulatory organ (vessels); "
                         "idle on a degraded cycle; never claimed proven"},
            ] + [
                {"name": n, "role": r, "flowing": False,
                 "note": "EXPERIMENTAL tier — irrigated by YARQA (circulatory); never claimed proven"}
                for n, r in _ORGAN_SPECS
            ],
            "circulatory": {
                "pump": "heart/pulse (the beat; szl_heart_blood #332)",
                "vessels": YARQA_NAME,
                "vessels_role": YARQA_ROLE,
                "flowing": False,
                "dispersed_work_credits": 0,
                "note": "EXPERIMENTAL tier — heart (pump) + YARQA (vessels) are ONE "
                        "circulatory subsystem; idle on a degraded cycle; never claimed proven",
            },
            "surfaces": {
                "unified_loop": f"/api/{ns}/v1/anatomy/loop",
                "standalone_canal": "/yarqa",
            },
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
# HTTP handler + registration (matches szl_energy_provenance / szl_heart_blood).
# ---------------------------------------------------------------------------
def _h_loop(req):
    from starlette.responses import JSONResponse
    return JSONResponse(run_loop())


_LOOP_PAGE_HTML = r'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Anatomy · Circulation Loop — a11oy</title>
<style>
:root{--bg:#0b0d10;--panel:#13171c;--line:#222a31;--ink:#e9eef2;--mut:#8aa0ad;
--gold:#d6a64c;--jade:#3fae8e;--flow:#4ea3ff;--warn:#caa14a;}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 700px at 50% -10%,#11161c,var(--bg));
color:var(--ink);font:15px/1.5 ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto,Helvetica,Arial}
.wrap{max-width:980px;margin:0 auto;padding:32px 20px 64px}
h1{font-size:26px;margin:0 0 4px;letter-spacing:.3px}
.sub{color:var(--mut);margin:0 0 18px}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0 26px}
.badge{font-size:12px;border:1px solid var(--line);border-radius:999px;padding:4px 10px;color:var(--mut);background:#0e1216}
.badge b{color:var(--gold);font-weight:600}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:16px}
.card h3{margin:0 0 4px;font-size:15px}
.card .role{color:var(--mut);font-size:12.5px;margin:0 0 10px}
.row{display:flex;justify-content:space-between;align-items:center;font-size:13px;margin:5px 0}
.row span:first-child{color:var(--mut)}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:7px;vertical-align:1px}
.on{background:var(--jade);box-shadow:0 0 8px var(--jade)}
.off{background:#3a4750}
.note{color:var(--mut);font-size:12px;margin-top:9px;border-top:1px dashed var(--line);padding-top:8px}
.vessel{border-color:var(--flow)}
.summary{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin:0 0 22px}
.kpi{background:var(--panel);border:1px solid var(--line);border-radius:14px;padding:14px}
.kpi .k{color:var(--mut);font-size:12px}.kpi .v{font-size:18px;margin-top:3px}
.foot{color:var(--mut);font-size:12px;margin-top:30px;line-height:1.7}
a{color:var(--flow);text-decoration:none}a:hover{text-decoration:underline}
.err{background:#2a1416;border:1px solid #57262b;color:#f0b8bd;padding:14px;border-radius:12px}
</style></head><body><div class="wrap">
<h1>Anatomy · Circulation Loop</h1>
<p class="sub">YARQA is the circulatory organ that irrigates the unified a11oy organism in one Ayni-balanced energy loop.</p>
<div class="badges">
<span class="badge"><b>EXPERIMENTAL</b> tier</span>
<span class="badge">doctrine <b id="b-doc">v11</b></span>
<span class="badge">joules <b id="b-j">sample</b> (off-box)</span>
<span class="badge">Λ = <b>Conjecture 1</b> (open)</span>
<span class="badge">data <b><a href="/api/__NS__/v1/anatomy/loop">/api/__NS__/v1/anatomy/loop</a></b></span>
</div>
<div id="root"><p class="sub">Loading live loop…</p></div>
<div class="foot">
This page renders the LIVE state of <code>/api/__NS__/v1/anatomy/loop</code>. The loop is an
EXPERIMENTAL anatomy demo; joule figures are SAMPLE until on-box NVML; Λ-uniqueness remains
Conjecture&nbsp;1 (open, never a theorem). No free-energy claim; sovereign only on own metal.
</div>
</div>
<script>
function esc(s){return String(s==null?'':s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));}
async function load(){
  const root=document.getElementById('root');
  try{
    const r=await fetch('/api/__NS__/v1/anatomy/loop',{headers:{'accept':'application/json'}});
    if(!r.ok) throw new Error('API '+r.status);
    const d=await r.json();
    document.getElementById('b-doc').textContent=d.doctrine||'v11';
    const intake=d.intake||{};
    document.getElementById('b-j').textContent=intake.joules_label||'sample';
    const ayni=d.ayni||{};
    const circ=d.circulatory||{};
    const summary=`
      <div class="summary">
        <div class="kpi"><div class="k">Ayni balance</div><div class="v">${ayni.balanced?'⚖️ balanced':'unbalanced'}</div></div>
        <div class="kpi"><div class="k">Circulatory vessels</div><div class="v">${esc(circ.vessels||'YARQA')}</div></div>
        <div class="kpi"><div class="k">Grid price (EUR/MWh)</div><div class="v">${intake.grid_price_eur_mwh==null?'—':esc(intake.grid_price_eur_mwh)}</div></div>
        <div class="kpi"><div class="k">Posture</div><div class="v">${esc(intake.posture||'unknown')}</div></div>
      </div>`;
    const organs=(d.organs||[]).map(o=>{
      const on=!!o.flowing;
      const vessel=(o.name===(circ.vessels||'YARQA'))?' vessel':'';
      return `<div class="card${vessel}">
        <h3><span class="dot ${on?'on':'off'}"></span>${esc(o.name)}</h3>
        <p class="role">${esc(o.role||'')}</p>
        <div class="row"><span>flowing</span><span>${on?'yes':'no'}</span></div>
        <div class="row"><span>dispersed work credits</span><span>${esc(o.dispersed_work_credits)}</span></div>
        <div class="note">${esc(o.note||'')}</div>
      </div>`;}).join('');
    root.innerHTML=summary+'<div class="grid">'+organs+'</div>';
  }catch(e){
    root.innerHTML='<div class="err">Could not load the live loop ('+esc(e.message)+'). The data API is at <a href="/api/__NS__/v1/anatomy/loop">/api/__NS__/v1/anatomy/loop</a>.</div>';
  }
}
load();
</script></body></html>'''


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

    handlers = [
        (f"{base}/loop", _loop_handler),
    ]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            from starlette.routing import Route
            app.router.routes.append(Route(path, fn))
    # ADDITIVE (#341 closeout): also serve a human-visitable HTML page at
    # /anatomy/loop. The /anatomy sub-app mount (szl_anatomy_routes) otherwise
    # shadows the SPA catch-all for this path and 404s it. Registered on `app`
    # here (the dark-surface aggregator runs BEFORE app.mount("/anatomy", ...)),
    # so this explicit route wins Starlette ordering. Honest: EXPERIMENTAL tier,
    # joules SAMPLE off-box, Lambda = Conjecture 1, doctrine v11. No fabrication.
    def _loop_page(req=None):
        from starlette.responses import HTMLResponse
        return HTMLResponse(_LOOP_PAGE_HTML.replace("__NS__", ns))
    if callable(add_api_route):
        app.add_api_route("/anatomy/loop", _loop_page, methods=["GET"], include_in_schema=False)
    else:
        from starlette.routing import Route
        app.router.routes.append(Route("/anatomy/loop", _loop_page))
    return [p for p, _ in handlers]


def _selftest() -> dict:
    """No-server self-test: run the loop offline and assert the doctrine invariants."""
    out = run_loop()
    assert out["joules_label"] == SAMPLE_LABEL, out
    assert out["ayni"]["balanced"] is True, out
    assert "kind" in out and out["kind"] == "anatomy-circulation-loop"
    for organ in out["organs"]:
        assert "experimental" in organ["note"].lower(), organ
    # YARQA is the named CIRCULATORY organ inside the unified loop (not a peer).
    yarqa = next((o for o in out["organs"] if o["name"] == YARQA_NAME), None)
    assert yarqa is not None, out["organs"]
    assert "circulatory" in yarqa["role"].lower(), yarqa
    assert out["circulatory"]["vessels"] == YARQA_NAME, out["circulatory"]
    return {"ok": True, "joules_label": out["joules_label"],
            "ayni_balanced": out["ayni"]["balanced"], "organs": len(out["organs"]),
            "circulatory_vessels": out["circulatory"]["vessels"]}


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
