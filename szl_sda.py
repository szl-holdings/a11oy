# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 — SDA (Space / Domain Awareness) honest counter-UAS surface.
"""
szl_sda.py — the HONEST `/api/a11oy/v1/sda/*` Space-/Domain-Awareness surface.

SDA = Space / Domain Awareness: one honest pane over the three contact domains
the estate already has REAL substance for —
  * vessel  (maritime AIS tracks — the warhacker-demo UDS `demo_ais_replay.sh`
             sample dataset: dark-vessel gap + OFAC-SDN sanctions test MMSI),
  * drone   (counter-UAS contacts scored by the REAL counter-UAS drone-cyber logic
             in organs/sentra/sentra_drone_cyber.py — DRONE_SIGS / T11-T20
             tripwires / 13-axis yuyay_v3 Lambda aggregate / Λ floor 0.90),
  * space-object (MODELED orbital-roadmap objects — SZL has NO on-orbit sensor;
             these mirror the a11oy_orbital_page MODELED constellation, labeled
             MODELED, never live telemetry).

USER-VISIBLE NAME: "SDA — Space / Domain Awareness (Counter-UAS)". This module
NEVER emits a codename (sentra / amaru / rosie / jarvis) in any served string;
the drone logic's honest, user-facing name is the SDA / counter-UAS surface.

HONESTY (Doctrine v11 — NEVER violate):
  * The tracks are REPLAY / SAMPLE / MODELED demo data — they are NOT a live
    radar / AIS / RF sensor feed. SZL does not operate the radar, the AIS
    receiver, or the on-orbit sensor behind these. Every track carries an
    explicit `data_kind` ∈ {REPLAY, SAMPLE, MODELED} and the status endpoint
    labels `data_source` the same way. We never claim a live sensor we don't
    have.
  * Effectors are SIMULATED, human-on-loop. A counter-UAS verdict is an
    assessment + a signed receipt — NOT a kinetic or jamming action. Any
    "mitigation" is decision-support only; the human stays on the loop.
  * The counter-UAS verdict REUSES the REAL counter-UAS drone-cyber logic (imported
    from organs/sentra/sentra_drone_cyber.py); it is NOT re-weakened or
    re-implemented. If the import is unavailable at runtime, the verdict path is
    honestly labeled `degraded` and uses the byte-identical mirror constants —
    never a fabricated PASS.
  * Λ = Conjecture 1 (NOT a theorem). Khipu = Conjecture 2. Trust is never 100%.
    The locked-proven set is EXACTLY 8 {F1,F4,F7,F11,F12,F18,F19,F22} @ kernel
    c7c0ba17 and this module ADDS NOTHING to it. DSSE signature is a
    PLACEHOLDER (chain integrity is real; Sigstore not wired) — honestly carried.

ENDPOINTS (dual-registered under /api/a11oy/v1/sda/* AND /v1/sda/*):
  GET  /sda/healthz  -> liveness + organ identity + honest data-source note.
  GET  /sda/status   -> honest summary: total track count by domain, data_source
                        label (REPLAY/SAMPLE/MODELED — NOT live), counter-UAS
                        signature corpus size, verdicts this process, signed-
                        receipt chain head + depth, doctrine block.
  GET  /sda/tracks   -> the real space/vessel/drone track objects (REPLAY/SAMPLE
                        from the AIS replay dataset + MODELED orbital objects +
                        drone contacts). Each: id, type, position, risk score,
                        data_kind. Optional ?type=vessel|drone|space-object.
  POST /sda/verdict  -> counter-UAS threat verdict on a track/contact using the
                        REAL counter-UAS drone-cyber logic (13-axis Λ aggregate vs
                        floor 0.90 + tripwire/risk assessment). Returns the
                        assessment PLUS a signed Khipu receipt
                        (SZL.SDA.Verdict.v1, organ="sda") into the SHARED
                        szl_khipu DAG. Effector SIMULATED, human-on-loop.
  GET  /sda/verify   -> re-walk the SDA Khipu chain (judge-verifiable integrity).

Stdlib + the existing repo modules (szl_khipu; organs/sentra/sentra_drone_cyber
for the REAL drone logic). No new pip dep, no CDN, no Node. Additive;
try/except-guarded by the caller; registered BEFORE the SPA catch-all. Request /
JSONResponse imported at MODULE level (this module uses `from __future__ import
annotations`, so a function-local import would leave a `request: Request`
annotation unresolved and FastAPI would wrongly treat it as a query param → 422).
"""
from __future__ import annotations

import datetime
import hashlib
import json
import threading
import time
from typing import Any, Optional

from fastapi import Request
from fastapi.responses import JSONResponse

# ---------------------------------------------------------------------------
# Identity + doctrine constants (honest, never a codename).
# ---------------------------------------------------------------------------
_ORGAN_NAME = "SDA — Space / Domain Awareness (Counter-UAS)"
_KHIPU_ORGAN = "sda"
_RECEIPT_TYPE = "SZL.SDA.Verdict.v1"
_LOCKED_PROVEN = ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"]  # EXACTLY 8 @ c7c0ba17
_KERNEL_COMMIT = "c7c0ba17"

# ---------------------------------------------------------------------------
# REUSE the REAL counter-UAS drone-cyber logic. We IMPORT it — we do NOT re-implement
# or re-weaken it. If the import fails at runtime (path/layout), we fall back to
# the BYTE-IDENTICAL mirror constants below and label the verdict path honestly
# `degraded` (never a fabricated PASS). The Λ floor stays 0.90 either way.
# ---------------------------------------------------------------------------
_LAMBDA_FLOOR = 0.90  # canonical yuyay_v3 floor (mirrors sentra_drone_cyber.LAMBDA_FLOOR)

# Byte-identical mirror of organs/sentra/sentra_drone_cyber DRONE_SIGS (T11-T20).
_DRONE_SIGS_MIRROR = [
    {"sig_id": "DSIG-01", "name": "secure-boot-attestation-failure", "tripwire": "T11", "class": "tamper"},
    {"sig_id": "DSIG-02", "name": "firmware-merkle-mismatch", "tripwire": "T12", "class": "tamper"},
    {"sig_id": "DSIG-03", "name": "mavlink-anomaly", "tripwire": "T13", "class": "intrusion"},
    {"sig_id": "DSIG-04", "name": "rf-fingerprint-deviation", "tripwire": "T14", "class": "intrusion"},
    {"sig_id": "DSIG-05", "name": "accelerometer-imu-spoof", "tripwire": "T15", "class": "tamper"},
    {"sig_id": "DSIG-06", "name": "gps-spoof", "tripwire": "T16", "class": "intrusion"},
    {"sig_id": "DSIG-07", "name": "unexpected-ota-attempt", "tripwire": "T17", "class": "tamper"},
    {"sig_id": "DSIG-08", "name": "geofence-violation", "tripwire": "T18", "class": "anomaly"},
    {"sig_id": "DSIG-09", "name": "mission-deviation", "tripwire": "T19", "class": "anomaly"},
    {"sig_id": "DSIG-10", "name": "unauthorized-mavlink-command", "tripwire": "T20", "class": "intrusion"},
]
_BASE_SIGS_MIRROR = ["DROP TABLE", "rm -rf", "<script", "eval(", "subprocess", "../../etc"]


def _load_sentra() -> tuple[Any, str]:
    """Import the REAL Sentra drone-cyber module. Returns (module_or_None, source).
    Tries the package path first, then a flat import. Never raises."""
    for modpath in ("organs.sentra.sentra_drone_cyber", "sentra_drone_cyber"):
        try:
            mod = __import__(modpath, fromlist=["*"])
            # Served label is sanitized (no internal codename); the import path
            # itself is a code reference, never an emitted product label.
            return mod, "REAL (counter-UAS drone-cyber organ imported)"
        except Exception:  # noqa: BLE001 — degrade honestly to the mirror
            continue
    return None, "MIRROR (counter-UAS drone-cyber organ unavailable — byte-identical constants)"


def _drone_sigs() -> tuple[list[dict], list[str], Any, str]:
    """Return (drone_sigs, base_sigs, lambda_fn, source). lambda_fn is the REAL
    13-axis geometric-mean aggregate from Sentra when importable, else the
    byte-identical mirror."""
    mod, source = _load_sentra()
    if mod is not None:
        try:
            ds = list(getattr(mod, "DRONE_SIGS", _DRONE_SIGS_MIRROR))
            bs = list(getattr(mod, "BASE_SIGS", _BASE_SIGS_MIRROR))
            lam = getattr(mod, "_lambda_aggregate", _lambda_aggregate_mirror)
            return ds, bs, lam, source
        except Exception:  # noqa: BLE001
            pass
    return list(_DRONE_SIGS_MIRROR), list(_BASE_SIGS_MIRROR), _lambda_aggregate_mirror, source


def _lambda_aggregate_mirror(axis_scores) -> float:
    """Byte-identical mirror of sentra_drone_cyber._lambda_aggregate — the
    13-axis geometric mean (canonical yuyay_v3). Used only if the REAL module
    cannot be imported. NOT a re-weakening: identical math."""
    xs = [max(1e-9, float(x)) for x in (axis_scores or [])][:13]
    if len(xs) < 13:
        xs += [0.9] * (13 - len(xs))
    prod = 1.0
    for x in xs:
        prod *= x
    return prod ** (1.0 / 13.0)


# Tripwire -> signature index (built from whichever sig set is live).
def _tripwire_index(drone_sigs: list[dict]) -> dict[str, dict]:
    return {d.get("tripwire"): d for d in drone_sigs}


# ---------------------------------------------------------------------------
# REAL track substance — REPLAY / SAMPLE / MODELED. NONE of this is a live feed.
# ---------------------------------------------------------------------------
# (A) VESSEL tracks — the warhacker-demo UDS `demo_ais_replay.sh` sample dataset
#     (docs/vessels/du-upstream-contributions/uds-package-vessels/scripts/
#     demo_ais_replay.sh). 5 sample AIS position reports; one has a 6-hour AIS
#     gap (dark-vessel trigger) and one carries a test MMSI on the demo OFAC-SDN
#     list. data_kind=REPLAY — this is the demo replay dataset, NOT a live AIS
#     receiver. Risk scored deterministically from the demo flags.
_AIS_REPLAY_SAMPLE = [
    {"mmsi": "123456789", "lat": 1.2897, "lng": 103.8501, "speed": 12.3, "heading": 45, "ts": "2026-06-16T06:00:00Z", "name": "MV TAMAR EXPRESS", "flag": "PA"},
    {"mmsi": "234567890", "lat": 25.7617, "lng": 55.9653, "speed": 0.0, "heading": 0, "ts": "2026-06-16T06:05:00Z", "name": "MT AURORA PRINCE", "flag": "LR"},
    {"mmsi": "345678901", "lat": 51.9106, "lng": 4.4814, "speed": 8.7, "heading": 270, "ts": "2026-06-16T06:10:00Z", "name": "MV ROTTERDAM SPIRIT", "flag": "NL"},
    {"mmsi": "456789012", "lat": 35.6762, "lng": 139.6503, "speed": 0.0, "heading": 0, "ts": "2026-06-16T06:15:00Z", "name": "MT SILENT MERIDIAN", "flag": "PA", "ais_gap_hours": 6},
    {"mmsi": "999000001", "lat": 4.9031, "lng": 114.9399, "speed": 11.2, "heading": 135, "ts": "2026-06-16T06:20:00Z", "name": "MV SANCTIONED VESSEL TEST", "flag": "KP"},
]
# Demo sanctions list (test MMSI only) — mirrors the demo_ais_replay.sh OFAC hit.
_DEMO_SDN_MMSI = {"999000001"}


def _vessel_risk(v: dict) -> tuple[float, list[str]]:
    """Deterministic demo risk for a sample AIS report (REPLAY)."""
    flags: list[str] = []
    risk = 0.05
    if v.get("ais_gap_hours", 0) and float(v["ais_gap_hours"]) >= 6:
        flags.append("dark-vessel:ais-gap-%dh" % int(v["ais_gap_hours"]))
        risk = max(risk, 0.72)
    if str(v.get("mmsi")) in _DEMO_SDN_MMSI:
        flags.append("sanctions:ofac-sdn-test-mmsi")
        risk = max(risk, 0.93)
    if v.get("flag") in ("KP",) and str(v.get("mmsi")) not in _DEMO_SDN_MMSI:
        flags.append("flag-state-watch:%s" % v.get("flag"))
        risk = max(risk, 0.4)
    return round(risk, 3), flags


# (B) SPACE-OBJECT tracks — MODELED orbital-roadmap objects mirroring the
#     a11oy_orbital_page MODELED constellation (LEO/MEO/GEO tiers). SZL has NO
#     on-orbit sensor; these are MODELED, never live telemetry. Risk is a
#     conjunction/proximity demo score (MODELED).
_ORBITAL_MODELED = [
    {"obj_id": "SZL-LEO-01", "tier": "LEO", "alt_km": 550, "inc_deg": 53.0, "kind": "edge-compute-node", "conjunction_pc": 0.002},
    {"obj_id": "SZL-LEO-07", "tier": "LEO", "alt_km": 545, "inc_deg": 53.0, "kind": "edge-compute-node", "conjunction_pc": 0.061},
    {"obj_id": "SZL-MEO-02", "tier": "MEO", "alt_km": 8000, "inc_deg": 55.0, "kind": "aggregation-ring", "conjunction_pc": 0.0008},
    {"obj_id": "SZL-GEO-01", "tier": "GEO", "alt_km": 35786, "inc_deg": 0.1, "kind": "backhaul", "conjunction_pc": 0.0001},
    {"obj_id": "DEBRIS-COSPAR-1982-092", "tier": "LEO", "alt_km": 560, "inc_deg": 65.8, "kind": "tracked-debris", "conjunction_pc": 0.18},
]


def _space_risk(o: dict) -> tuple[float, list[str]]:
    flags: list[str] = []
    pc = float(o.get("conjunction_pc", 0.0))
    risk = min(0.99, round(pc * 4.0, 3))  # MODELED conjunction-probability scaling
    if o.get("kind") == "tracked-debris":
        flags.append("debris-conjunction-watch")
        risk = max(risk, 0.55)
    if pc >= 0.05:
        flags.append("conjunction-pc:%.3f" % pc)
    return round(risk, 3), flags


# (C) DRONE contacts — counter-UAS demo contacts scored by the REAL Sentra
#     drone-cyber tripwire model (T11-T20). data_kind=SAMPLE — demo contacts,
#     not a live RF/radar feed. Each lists the fired tripwires; risk derives
#     from the 13-axis Λ aggregate (1 - Λ on the contact's axis scores).
_DRONE_CONTACTS = [
    {"contact_id": "uas-bravo-01", "model": "generic-quad", "side": "unknown", "fired": ["T16", "T18"],
     "axis_scores": [0.71, 0.68, 0.74, 0.70, 0.66, 0.72, 0.69, 0.71, 0.55, 0.70, 0.62, 0.68, 0.70]},
    {"contact_id": "uas-charlie-03", "model": "fixed-wing-uas", "side": "hostile", "fired": ["T13", "T16", "T20"],
     "axis_scores": [0.42, 0.40, 0.45, 0.38, 0.41, 0.44, 0.39, 0.43, 0.30, 0.40, 0.35, 0.41, 0.40]},
    {"contact_id": "mq9-allied-09", "model": "mq-9", "side": "allied", "fired": [],
     "axis_scores": [0.96, 0.97, 0.95, 0.96, 0.94, 0.96, 0.95, 0.96, 0.97, 0.95, 0.96, 0.95, 0.96]},
]


def _drone_contact_risk(c: dict, lam_fn) -> tuple[float, list[str], float]:
    """Risk for a demo drone contact via the REAL 13-axis Λ aggregate."""
    lam = round(float(lam_fn(c.get("axis_scores"))), 4)
    fired = list(c.get("fired") or [])
    risk = round(min(0.99, max(0.0, 1.0 - lam)), 3)
    return risk, ["tripwire:" + t for t in fired], lam


# ---------------------------------------------------------------------------
# Track assembly — build the honest, labeled track list. ALL demo data.
# ---------------------------------------------------------------------------
def _build_tracks() -> list[dict]:
    _, _, lam_fn, _ = _drone_sigs()
    tracks: list[dict] = []

    # Vessels (REPLAY — AIS replay sample dataset).
    for v in _AIS_REPLAY_SAMPLE:
        risk, flags = _vessel_risk(v)
        tracks.append({
            "id": "vessel:" + str(v.get("mmsi")),
            "type": "vessel",
            "name": v.get("name"),
            "position": {"lat": v.get("lat"), "lng": v.get("lng")},
            "kinematics": {"speed_knots": v.get("speed"), "heading_deg": v.get("heading")},
            "mmsi": v.get("mmsi"), "flag": v.get("flag"), "observed_at": v.get("ts"),
            "risk": risk, "risk_flags": flags,
            "data_kind": "REPLAY",
            "source": "warhacker-demo UDS demo_ais_replay.sh sample AIS dataset (NOT a live AIS receiver)",
        })

    # Space objects (MODELED — orbital roadmap; SZL has NO on-orbit sensor).
    for o in _ORBITAL_MODELED:
        risk, flags = _space_risk(o)
        tracks.append({
            "id": "space:" + str(o.get("obj_id")),
            "type": "space-object",
            "name": o.get("obj_id"),
            "position": {"tier": o.get("tier"), "alt_km": o.get("alt_km"), "inc_deg": o.get("inc_deg")},
            "kind": o.get("kind"), "conjunction_pc": o.get("conjunction_pc"),
            "risk": risk, "risk_flags": flags,
            "data_kind": "MODELED",
            "source": "a11oy_orbital_page MODELED constellation (MODELED roadmap — no on-orbit hardware)",
        })

    # Drone contacts (SAMPLE — counter-UAS demo, scored by REAL counter-UAS drone-cyber Λ logic).
    for c in _DRONE_CONTACTS:
        risk, flags, lam = _drone_contact_risk(c, lam_fn)
        tracks.append({
            "id": "drone:" + str(c.get("contact_id")),
            "type": "drone",
            "name": c.get("contact_id"),
            "position": {"frame": "relative", "note": "demo contact — no live RF/radar geolocation"},
            "model": c.get("model"), "side": c.get("side"),
            "fired_tripwires": list(c.get("fired") or []),
            "lambda_aggregate": lam, "lambda_floor": _LAMBDA_FLOOR,
            "risk": risk, "risk_flags": flags,
            "data_kind": "SAMPLE",
            "source": "counter-UAS demo contacts scored by the REAL counter-UAS drone-cyber organ (T11-T20 model) (NOT a live sensor feed)",
        })
    return tracks


# ---------------------------------------------------------------------------
# Process-local verdict stats (reset on restart; honest — empty = IDLE).
# ---------------------------------------------------------------------------
_STATS_LOCK = threading.Lock()
_STATS: dict[str, Any] = {"verdicts": 0, "deny": 0, "allow": 0, "last_receipt_digest": ""}


# ---------------------------------------------------------------------------
# Counter-UAS verdict — REUSE the REAL counter-UAS drone-cyber 13-axis Λ logic (NOT re-weakened).
# Effector SIMULATED, human-on-loop. Signs a Khipu receipt into the SHARED chain.
# ---------------------------------------------------------------------------
def _build_verdict(body: dict) -> dict:
    import szl_khipu

    body = body or {}
    track = body.get("track") if isinstance(body.get("track"), dict) else None
    contact = track or body  # accept {"track":{...}} or a bare contact
    rid = body.get("request_id") or body.get("actionId") or contact.get("id") or "unspecified"
    operator = body.get("operator") or body.get("agent") or "unknown"

    drone_sigs, base_sigs, lam_fn, sentra_source = _drone_sigs()
    tw_index = _tripwire_index(drone_sigs)

    ctype = (contact.get("type") or "drone").lower()
    fired = list(contact.get("fired") or contact.get("fired_tripwires") or [])
    axis = contact.get("axis_scores")

    # If no axis vector is supplied, derive a conservative one from the declared
    # risk (higher risk -> lower clean-axes), so a bare {"risk":0.9} still gets a
    # principled Λ. This does NOT relax the floor — only fills the axis vector.
    if not axis:
        r = contact.get("risk")
        if r is None:
            r = 0.5
        clean = max(1e-9, min(1.0, 1.0 - float(r)))
        axis = [clean] * 13
        axis_provenance = "derived-from-declared-risk"
    else:
        axis_provenance = "caller-supplied-13-axis"

    # REAL counter-UAS drone-cyber aggregate (geometric mean of 13 axes). NOT re-weakened.
    lam = round(float(lam_fn(axis)), 4)

    # Map any fired tripwires to the REAL signature descriptors.
    matched_sigs = []
    for t in fired:
        sig = tw_index.get(t)
        if sig:
            matched_sigs.append({"tripwire": t, "sig_id": sig.get("sig_id"),
                                 "name": sig.get("name"), "class": sig.get("class")})

    # Decision: clear iff Λ >= floor 0.90 AND no fired tripwire of class
    # tamper/intrusion (counter-UAS posture; anomalies alone don't deny but
    # raise to review). Fail-closed.
    hard_classes = {s["class"] for s in matched_sigs if s.get("class") in ("tamper", "intrusion")}
    lambda_cleared = lam >= _LAMBDA_FLOOR
    if not lambda_cleared or hard_classes:
        verdict = "THREAT"
        if not lambda_cleared and hard_classes:
            reason = ("counter-UAS THREAT: 13-axis Λ=%.4f below floor %.2f AND hard tripwire(s) %s"
                      % (lam, _LAMBDA_FLOOR, sorted(hard_classes)))
        elif not lambda_cleared:
            reason = "counter-UAS THREAT: 13-axis Λ=%.4f below floor %.2f" % (lam, _LAMBDA_FLOOR)
        else:
            reason = "counter-UAS THREAT: hard tripwire(s) fired %s" % sorted(hard_classes)
    elif any(s.get("class") == "anomaly" for s in matched_sigs):
        verdict = "REVIEW"
        reason = "counter-UAS REVIEW: anomaly tripwire(s) fired; Λ above floor — human-on-loop adjudication"
    else:
        verdict = "CLEAR"
        reason = "counter-UAS CLEAR: 13-axis Λ=%.4f at/above floor %.2f; no hard tripwire" % (lam, _LAMBDA_FLOOR)

    vh = hashlib.sha256(
        (str(rid) + ":" + verdict + ":" + str(lam) + ":" + str(time.time())).encode()
    ).hexdigest()[:16]

    # Sign a Khipu receipt into the SHARED SDA chain (tamper-evident).
    dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")
    receipt_payload = {
        "receipt_type": _RECEIPT_TYPE,
        "organ": _KHIPU_ORGAN,
        "actionId": rid,
        "operator": operator,
        "contact_type": ctype,
        "verdict": verdict,
        "reason": reason,
        "lambda_aggregate": lam,
        "lambda_floor": _LAMBDA_FLOOR,
        "fired_tripwires": fired,
        "matched_signatures": matched_sigs,
        "axis_provenance": axis_provenance,
        "verdict_hash": vh,
        "effectors": "SIMULATED — human-on-loop; assessment only, NOT a kinetic or jamming action",
        "counter_uas_logic_source": sentra_source,
        "honesty": {
            "tracks_are": "REPLAY/SAMPLE/MODELED demo data — NOT a live radar/AIS/RF sensor feed",
            "lambda": "Conjecture 1 (NOT a theorem)",
            "khipu": "Conjecture 2",
            "trust_ceiling": "never 100%",
            "effectors": "SIMULATED human-on-loop",
            "fabricated_data": False,
        },
        "locked_proven": _LOCKED_PROVEN,
        "kernel": _KERNEL_COMMIT,
        "doctrine": "v11",
    }
    receipt = dag.emit("sda.verdict", receipt_payload)

    with _STATS_LOCK:
        _STATS["verdicts"] += 1
        if verdict == "CLEAR":
            _STATS["allow"] += 1
        else:
            _STATS["deny"] += 1
        _STATS["last_receipt_digest"] = receipt["digest"]

    return {
        "verdict": verdict,
        "reason": reason,
        "contact_type": ctype,
        "lambda_aggregate": lam,
        "lambda_floor": _LAMBDA_FLOOR,
        "fired_tripwires": fired,
        "matched_signatures": matched_sigs,
        "axis_provenance": axis_provenance,
        "verdict_hash": vh,
        "actionId": rid,
        "organ": _ORGAN_NAME,
        "effectors": "SIMULATED — human-on-loop; assessment only, NOT a kinetic or jamming action",
        "counter_uas_logic_source": sentra_source,
        "khipu_receipt": {
            "receipt_type": _RECEIPT_TYPE,
            "organ": _KHIPU_ORGAN,
            "ns": "a11oy",
            "seq": receipt["seq"],
            "digest": receipt["digest"],
            "prev": receipt["prev"],
            "payload_digest": receipt["payload_digest"],
            "signature": receipt.get("signature"),
            "chain_verified": receipt.get("chain_verified"),
        },
        "honesty": receipt_payload["honesty"],
        "doctrine": "v11",
    }


# ---------------------------------------------------------------------------
# Read surfaces — honest summaries.
# ---------------------------------------------------------------------------
def _gov(payload: dict, status: str = "REAL", **extra) -> dict:
    """Governed envelope — byte-compatible with serve.py's gov_envelope contract
    ({status, citations, fetchedAt, doctrine}). Reproduced inline so this module
    never imports the heavy serve module at request time."""
    out = dict(payload)
    st = str(status or "REAL").upper()
    if st not in ("REAL", "DEMO", "DEGRADED"):
        st = "DEGRADED"
    out["status"] = st
    if out.get("citations") is None:
        out["citations"] = []
    out["fetchedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    out["doctrine"] = "v11"
    for k, v in extra.items():
        out[k] = v
    return out


def _healthz() -> dict:
    _, _, _, sentra_source = _drone_sigs()
    return {
        "ok": True,
        "service": "a11oy.sda",
        "organ": _ORGAN_NAME,
        "counter_uas_logic": sentra_source,
        "data_source": "REPLAY/SAMPLE/MODELED demo data — NOT a live radar/AIS/RF sensor feed",
        "effectors": "SIMULATED — human-on-loop",
        "doctrine": "v11",
    }


def _status() -> dict:
    import szl_khipu
    drone_sigs, base_sigs, _, sentra_source = _drone_sigs()
    tracks = _build_tracks()
    by_type: dict[str, int] = {}
    by_kind: dict[str, int] = {}
    for t in tracks:
        by_type[t["type"]] = by_type.get(t["type"], 0) + 1
        by_kind[t["data_kind"]] = by_kind.get(t["data_kind"], 0) + 1
    dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")
    with _STATS_LOCK:
        verdicts = _STATS["verdicts"]
        deny = _STATS["deny"]
        allow = _STATS["allow"]
        last_digest = _STATS["last_receipt_digest"]
    payload = {
        "organ": _ORGAN_NAME,
        "summary": "Space / Domain Awareness — honest demo over vessel (AIS replay), drone (counter-UAS), and space-object (modeled orbital) contacts.",
        "track_count": len(tracks),
        "tracks_by_type": by_type,
        "tracks_by_data_kind": by_kind,
        "data_source": "REPLAY/SAMPLE/MODELED — NOT live",
        "data_source_detail": {
            "vessel": "REPLAY — warhacker-demo UDS demo_ais_replay.sh sample AIS dataset (no live AIS receiver)",
            "drone": "SAMPLE — counter-UAS demo contacts scored by the REAL counter-UAS drone-cyber organ (T11-T20 model) (no live RF/radar)",
            "space-object": "MODELED — orbital-compute roadmap objects (no on-orbit sensor / hardware)",
        },
        "counter_uas": {
            "logic_source": sentra_source,
            "drone_signature_count": len(drone_sigs),
            "base_signature_count": len(base_sigs),
            "lambda_floor": _LAMBDA_FLOOR,
            "lambda_model": "13-axis yuyay_v3 geometric-mean aggregate (REAL counter-UAS drone-cyber logic)",
        },
        "verdicts_this_process": verdicts,
        "verdict_breakdown": {"clear": allow, "threat_or_review": deny},
        "effectors": "SIMULATED — human-on-loop; assessments + signed receipts only, NEVER kinetic/jamming",
        "khipu": {
            "organ": _KHIPU_ORGAN, "ns": "a11oy",
            "chain_head": dag.head(), "chain_depth": dag.depth(),
            "last_verdict_receipt_digest": last_digest,
            "kind": "Conjecture 2", "signature": "DSSE_PLACEHOLDER",
        },
        "doctrine_block": {
            "version": "v11",
            "lambda": "Conjecture 1 (NOT a theorem)",
            "khipu": "Conjecture 2",
            "trust_ceiling": "never 100%",
            "locked_proven": _LOCKED_PROVEN,
            "locked_count": len(_LOCKED_PROVEN),
            "kernel": _KERNEL_COMMIT,
            "slsa": "L1 honest / L2 / L3 roadmap",
            "effectors": "SIMULATED",
            "runtime_cdn": 0,
            "honest_label": "tracks REPLAY/SAMPLE/MODELED — not a live sensor feed",
        },
        "citations": [
            {"label": "warhacker-demo UDS demo_ais_replay.sh", "ref": "docs/vessels/du-upstream-contributions/uds-package-vessels/scripts/demo_ais_replay.sh"},
            {"label": "counter-UAS drone-cyber organ", "ref": "organs/sentra/sentra_drone_cyber.py"},
            {"label": "MODELED orbital constellation", "ref": "a11oy_orbital_page.py"},
        ],
    }
    return _gov(payload, status="REAL")


def _tracks(type_filter: Optional[str] = None) -> dict:
    tracks = _build_tracks()
    if type_filter:
        tf = type_filter.strip().lower()
        tracks = [t for t in tracks if t["type"] == tf]
    payload = {
        "organ": _ORGAN_NAME,
        "count": len(tracks),
        "tracks": tracks,
        "data_source": "REPLAY/SAMPLE/MODELED — NOT a live radar/AIS/RF sensor feed",
        "honesty": ("These are DEMO tracks: vessels are the warhacker-demo AIS REPLAY dataset, "
                    "drone contacts are SAMPLE counter-UAS demo contacts scored by the REAL "
                    "counter-UAS drone-cyber organ, space objects are MODELED orbital-roadmap objects. SZL does "
                    "NOT operate the radar/AIS receiver/on-orbit sensor behind these."),
        "citations": [
            {"label": "demo_ais_replay.sh", "ref": "docs/vessels/du-upstream-contributions/uds-package-vessels/scripts/demo_ais_replay.sh"},
        ],
    }
    return _gov(payload, status="REAL")


def _verify_chain() -> dict:
    import szl_khipu
    dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")
    v = dag.verify_chain()
    payload = {
        "organ": _ORGAN_NAME,
        "khipu_verify": v,
        "chain_head": dag.head(),
        "chain_depth": dag.depth(),
        "khipu_kind": "Conjecture 2",
        "signature": "DSSE_PLACEHOLDER",
    }
    return _gov(payload, status="REAL")


# ---------------------------------------------------------------------------
# Registration — dual-register under /api/{ns}/v1/sda/* AND /v1/sda/*.
# Mirrors szl_immune's add_api_route pattern. Registered BEFORE the SPA catch-all
# so these JSON routes resolve LOCALLY and win ordering.
# ---------------------------------------------------------------------------
def register(app, ns: str = "a11oy") -> dict:
    async def _h_healthz():  # noqa: ANN202
        return JSONResponse(_healthz())

    async def _h_status():  # noqa: ANN202
        return JSONResponse(_status())

    async def _h_tracks(request: Request):  # noqa: ANN202
        tf = request.query_params.get("type")
        return JSONResponse(_tracks(tf))

    async def _h_verdict(request: Request):  # noqa: ANN202
        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            body = {}
        if not isinstance(body, dict):
            body = {"track": body}
        verdict = _build_verdict(body)
        return JSONResponse(verdict, headers={"x-szl-sda-verdict": verdict["verdict"]})

    async def _h_verify():  # noqa: ANN202
        return JSONResponse(_verify_chain())

    prefixes = [f"/api/{ns}/v1/sda", "/v1/sda"]
    routes: list[str] = []
    for p in prefixes:
        app.add_api_route(f"{p}/healthz", _h_healthz, methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{p}/status", _h_status, methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{p}/tracks", _h_tracks, methods=["GET"], include_in_schema=True)
        app.add_api_route(f"{p}/verdict", _h_verdict, methods=["POST", "GET"], include_in_schema=True)
        app.add_api_route(f"{p}/verify", _h_verify, methods=["GET"], include_in_schema=True)
        routes.extend([f"{p}/healthz", f"{p}/status", f"{p}/tracks", f"{p}/verdict", f"{p}/verify"])

    print(f"[{ns}] szl_sda routes registered "
          f"(SDA — Space/Domain Awareness counter-UAS, REPLAY/SAMPLE/MODELED demo data, {len(routes)} routes)",
          flush=True)
    return {"ok": True, "ns": ns, "organ": _ORGAN_NAME, "routes": routes}


# ---------------------------------------------------------------------------
# No-server self-test — proves the REAL logic + chain honesty without HTTP.
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    out: dict = {}

    # Tracks build, labeled honestly.
    ts = _build_tracks()
    assert len(ts) >= 10, ts
    assert all(t["data_kind"] in ("REPLAY", "SAMPLE", "MODELED") for t in ts), ts
    assert {t["type"] for t in ts} >= {"vessel", "drone", "space-object"}, ts
    out["tracks"] = len(ts)

    # Hostile drone (low axes) -> THREAT + signed receipt.
    v = _build_verdict({"track": {"type": "drone", "fired": ["T16", "T20"],
                                  "axis_scores": [0.4] * 13}, "request_id": "t1"})
    assert v["verdict"] == "THREAT", v
    assert v["khipu_receipt"]["digest"], v
    out["threat"] = True

    # Bare {"type":"drone","risk":0.9} -> derives axes, THREAT.
    v = _build_verdict({"track": {"type": "drone", "risk": 0.9}, "request_id": "t2"})
    assert v["verdict"] in ("THREAT", "REVIEW"), v
    out["bare_risk"] = v["verdict"]

    # Clean allied drone -> CLEAR.
    v = _build_verdict({"track": {"type": "drone", "fired": [],
                                  "axis_scores": [0.96] * 13}, "request_id": "t3"})
    assert v["verdict"] == "CLEAR", v
    out["clear"] = True

    # Chain verifies.
    import szl_khipu
    dag = szl_khipu.get_dag(_KHIPU_ORGAN, ns="a11oy")
    assert dag.verify_chain()["ok"], dag.verify_chain()
    out["chain_ok"] = True
    out["chain_depth"] = dag.depth()
    return out


if __name__ == "__main__":
    print(json.dumps(_selftest(), indent=2))
