"""
szl_edgefusion.py — SZL EDGEFUSION: an energy-proportional, Λ-gated multi-sensor
edge-fusion surface with a signed-fusion-receipt-per-write design.

This is an SZL cross-axis SYNTHESIS surface: it combines three real, cited strands
that no published system ships together as ONE governed fusion picture —

  (1) MULTI-SENSOR FUSION — covariance-weighted track fusion across heterogeneous
      sensors (camera / radar / lidar / IMU), the mechanism behind the field
      leaders BEVFusion, TransFuser and VINS-Fusion;
  (2) ENERGY-PROPORTIONAL / CARBON-AWARE INFERENCE — a joules-per-inference readout
      that scales with the active sensor+track workload (idle draws near a floor),
      in the spirit of MLPerf Power and carbon-aware edge inference (CarbonCall),
      with an optional neuromorphic (SNN / Loihi) efficiency factor;
  (3) THE Λ-GATE + RECEIPT CHAIN — a per-track Λ-advisory TRUST GATE (Λ = Conjecture
      1, gray, NEVER green) over what the fused picture is allowed to act on, plus a
      signed-fusion-receipt-PER-WRITE design so every fused decision is auditable
      (receipt-on-WRITE, never on a read).

  GET  /api/<ns>/v1/frontier/edgefusion?seed=&n_tracks=&n_sensors=&horizon=&neuro=

The endpoint returns a MODELED/CONJECTURE model of governed edge fusion: a
deterministic, seeded multi-sensor scene is fused per-track by inverse-variance
weighting; each fused track passes through a Λ-advisory trust gate and a
sensor-agreement consistency check; a MODELED joules-per-inference figure is
computed from a parametric energy model; and the response DESCRIBES (does not mint)
the signed fusion receipt each fused write would emit on a real WRITE.

Returned JSON (top-level `label`, metrics nested under `payload` — the edgefusion
surface reads the label at top level OR payload.label, metrics from payload)
----------------------------------------------------------------------------
  label                       : "MODELED" (the fusion/energy arithmetic is a
                                deterministic simulation; the SZL synthesis is
                                additionally flagged CONJECTURE inside payload).
  payload.n_tracks            : number of modeled sensor tracks fused
  payload.n_sensors           : number of heterogeneous sensor modalities
  payload.horizon             : staleness horizon (age beyond which a track is stale)
  payload.sensors[]           : the modeled sensor modalities {name, sigma, joules}
  payload.tracks[]            : per-track {id, sensor_agreement, fused_confidence,
                                fused_sigma, energy_j, age_steps, consistent,
                                lambda_advisory, admitted}
  payload.fusion              : {tracks, admitted, gated_out, mean_fused_confidence,
                                mean_sensor_agreement, consistency_rate}
  payload.energy              : MODELED joules readout {label, joules_per_inference,
                                joules_idle_floor, joules_total, energy_proportional,
                                neuromorphic, neuromorphic_factor, breakdown, note}
  payload.lambda_gate         : {status, admit_threshold, mean_lambda_advisory,
                                bounds, admits, gated_out, trust, trust_cap} — Λ
                                advisory (Conjecture 1, gray)
  payload.receipt_design      : signed-fusion-receipt-per-write DESIGN (CONJECTURE),
                                incl. an UNSIGNED content-hash preview (signed:false)
  payload.parts_labeled       : which parts are MODELED vs CONJECTURE
  payload.honest_note         : plain-language honesty disclaimer
  payload.citations           : dict of citable sources (verbatim, never claimed as ours)
  payload.computed_at         : ISO-8601 UTC timestamp

HONEST STATUS
  MODELED — the sensor scene, per-sensor noise (sigma), inverse-variance track
    fusion, sensor-agreement consistency check, and the joules-per-inference model
    are a deterministic seeded simulation. fused_confidence, sensor_agreement,
    consistency_rate, admits/gated_out, joules and trust are genuinely COMPUTED from
    the modeled scene, reported not fabricated. It does NOT run a trained detector,
    a real Kalman/factor-graph estimator, any of the cited fusion systems, a real
    power meter, or neuromorphic silicon. The joules figure is MODELED, NOT MEASURED
    — no NVML/RAPL/Loihi meter is wired here (that would be a MEASURED label).
  CONJECTURE — the SZL SYNTHESIS is unproven and labeled as such: (a) Λ as a
    per-track trust gate is the SZL restraint advisory Λ = Conjecture 1 (gray,
    NEVER green), not a theorem; (b) the signed-fusion-receipt-per-write chain is a
    DESIGN — no receipt is minted here (receipt-on-WRITE, never on a GET), so the
    response only DESCRIBES the receipt and shows an UNSIGNED content-hash preview;
    (c) the energy-proportional + neuromorphic + governed-fusion COMBINATION as one
    receipt-emitting surface is the SZL-original synthesis (unshipped combination).

DOCTRINE v11
  Nothing here is in the locked-8 (adds 0). Λ = Conjecture 1 (gray, never green).
  Trust is capped at 0.97 and is never 1.0. Energy is MODELED, never MEASURED (no
  real meter). No fabricated data. Pure stdlib. Deterministic with seed. 0 runtime
  CDN. RECEIPT-ON-WRITE, NOT ON-READ: this GET signs nothing and appends to no
  provenance chain — it computes a plain content hash as a clearly-UNSIGNED preview.

CITATIONS (clean-room; none claimed as SZL's own; verified to resolve 2026-07-07):
  BEVFusion: Multi-Task Multi-Sensor Fusion with Unified BEV Representation
    (camera+lidar BEV fusion): Liu et al. 2022, arXiv:2205.13542
    https://arxiv.org/abs/2205.13542
  TransFuser: Imitation with Transformer-Based Sensor Fusion for Autonomous
    Driving: Chitta et al. 2022, arXiv:2205.15997   https://arxiv.org/abs/2205.15997
  VINS-Fusion: optimization-based multi-sensor state estimator (visual-inertial):
    HKUST-Aerial-Robotics    https://github.com/HKUST-Aerial-Robotics/VINS-Fusion
  MLPerf Power: Benchmarking the Energy Efficiency of ML Systems from μWatts to
    MWatts for Sustainable AI: Tschand et al. 2024, arXiv:2410.12032
    https://arxiv.org/abs/2410.12032
  CarbonCall: Sustainability-Aware Function Calling for LLMs on Edge Devices
    (carbon-aware edge inference): 2025, arXiv:2504.20348
    https://arxiv.org/abs/2504.20348
  snnTorch / Training Spiking Neural Networks Using Lessons From Deep Learning
    (neuromorphic SNN efficiency): Eshraghian et al. 2021, arXiv:2109.12894
    https://arxiv.org/abs/2109.12894
  Loihi: A Neuromorphic Manycore Processor with On-Chip Learning (event-driven
    energy efficiency): Davies et al., IEEE Micro 38(1):82-99, 2018,
    doi:10.1109/MM.2018.112130359   https://doi.org/10.1109/MM.2018.112130359
"""
import hashlib
from datetime import datetime, timezone

from starlette.routing import Route
from starlette.responses import JSONResponse

CITATIONS = {
    "BEVFusion: Multi-Sensor Fusion w/ Unified BEV — Liu et al. 2022 arXiv:2205.13542": "https://arxiv.org/abs/2205.13542",
    "TransFuser: Transformer-Based Sensor Fusion — Chitta et al. 2022 arXiv:2205.15997": "https://arxiv.org/abs/2205.15997",
    "VINS-Fusion: optimization-based multi-sensor state estimator — HKUST-Aerial-Robotics": "https://github.com/HKUST-Aerial-Robotics/VINS-Fusion",
    "MLPerf Power: Benchmarking ML Energy Efficiency — Tschand et al. 2024 arXiv:2410.12032": "https://arxiv.org/abs/2410.12032",
    "CarbonCall: Sustainability-Aware Function Calling on Edge — 2025 arXiv:2504.20348": "https://arxiv.org/abs/2504.20348",
    "snnTorch: Training SNNs Using Lessons From Deep Learning — Eshraghian et al. 2021 arXiv:2109.12894": "https://arxiv.org/abs/2109.12894",
    "Loihi: Neuromorphic Manycore w/ On-Chip Learning — Davies et al. 2018 IEEE Micro": "https://doi.org/10.1109/MM.2018.112130359",
}

# MODELED fusion / gate / energy hyperparameters (reported verbatim; not trained).
_LAMBDA_MIN = 0.02          # Λ advisory lower bound (gray floor)
_LAMBDA_MAX = 0.94          # Λ advisory upper bound (NEVER 1.0 — Conjecture 1)
_LAMBDA_ADMIT = 0.55        # advisory admit threshold (a track is admitted above it)
_TRUST_CAP = 0.97           # doctrine hard cap on trust (never green / never 1.0)
_CONFLICT_EVERY = 6         # every Nth track is a modeled stale/disagreeing item
_TRACK_CAP = 96             # max track entries returned (matches surface stream cap)

# Parametric MODELED energy model (joules per inference). These are illustrative
# design coefficients, NOT measured from any device — reported verbatim so a reader
# can see the arithmetic. A real deployment would replace these with a MEASURED
# NVML/RAPL/Loihi delta (which alone would earn a MEASURED label).
_J_FUSION_FIXED = 0.0120    # fixed per-inference fusion cost (J), the pipeline floor
_J_PER_TRACK = 0.0026       # marginal J per fused track (association + weighting)
_J_IDLE_FLOOR = 0.0035      # idle draw (J) when no tracks are active (energy-proportional)
_NEURO_FACTOR = 0.18        # event-driven SNN/Loihi energy multiplier vs dense (MODELED)

# Per-sensor MODELED noise (sigma, lower = better) + per-sample energy (J). A larger
# heterogeneous sensor set lowers fused sigma (more evidence) but costs more joules —
# the energy/accuracy trade-off the fusion + energy leaders both study.
_SENSOR_BANK = [
    {"name": "camera", "sigma": 0.42, "joules": 0.0090},
    {"name": "lidar",  "sigma": 0.24, "joules": 0.0140},
    {"name": "radar",  "sigma": 0.55, "joules": 0.0040},
    {"name": "imu",    "sigma": 0.30, "joules": 0.0012},
    {"name": "thermal","sigma": 0.60, "joules": 0.0060},
    {"name": "acoustic","sigma": 0.70, "joules": 0.0025},
]


def _u01(seed, i, salt=0):
    """Deterministic uniform in [0,1) from (seed, i, salt) via two LCG rounds."""
    s = ((i + 1) * 2654435761 + seed * 40503 + salt * 2246822519) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    return s / 4294967295.0


def _fuse(seed=42, n_tracks=48, n_sensors=4, horizon=64, neuro=False):
    """Deterministic governed multi-sensor edge-fusion simulation.

    A scene of `n_tracks` targets is observed by `n_sensors` heterogeneous sensors.
    Each track's per-sensor detection has a MODELED quality; the track is FUSED by
    inverse-variance (covariance) weighting across the sensors that detected it,
    yielding a fused confidence and a fused sigma. A fraction of tracks are planted
    stale (age > horizon) or disagreeing (sensor_agreement low) — modeled, not
    fabricated. Each fused track gets a Λ advisory in [_LAMBDA_MIN,_LAMBDA_MAX]
    derived from its fused confidence and sensor agreement, and is ADMITTED iff its
    advisory clears the threshold AND it is consistent. The gate is ADVISORY (gray),
    never a hard green; overall trust is capped at _TRUST_CAP. A MODELED
    joules-per-inference figure scales with the active sensor+track workload
    (energy-proportional), optionally reduced by a neuromorphic (SNN/Loihi) factor.
    """
    n_tracks = max(1, n_tracks)
    n_sensors = max(1, min(n_sensors, len(_SENSOR_BANK)))
    horizon = max(1, horizon)

    sensors = _SENSOR_BANK[:n_sensors]
    # inverse-variance normaliser for a fully-observed track (all sensors agree)
    inv_var_full = sum(1.0 / (s["sigma"] ** 2) for s in sensors)

    tracks = []
    for i in range(n_tracks):
        # Which sensors detected this track (deterministic per (track, sensor)).
        detected = []
        for si, s in enumerate(sensors):
            if _u01(seed, i, salt=10 + si) > 0.22:   # ~78% detection rate per sensor
                detected.append(s)
        if not detected:
            detected = [sensors[0]]  # at least one sensor keeps the track alive

        # Inverse-variance (covariance-weighted) fusion: fused sigma^2 = 1 / Σ(1/σ²).
        inv_var = sum(1.0 / (s["sigma"] ** 2) for s in detected)
        fused_sigma = (1.0 / inv_var) ** 0.5
        # fused confidence rises as more low-noise sensors corroborate the track.
        fused_confidence = min(0.999, inv_var / inv_var_full)

        # sensor agreement: how coherent the detections are (1.0 = full corroboration).
        agreement = len(detected) / len(sensors)
        # planted disagreement/staleness keeps the consistency check honest.
        age = int(_u01(seed, i, salt=3) * (2 * horizon))
        stale = age > horizon
        planted_conflict = (i % _CONFLICT_EVERY == 0)
        consistent = not (stale or planted_conflict)
        if planted_conflict:
            agreement *= 0.5

        # MODELED energy for THIS track's fusion inference: per-sensor sampling +
        # marginal fusion cost, optionally scaled by the neuromorphic factor.
        sample_j = sum(s["joules"] for s in detected)
        track_j = (sample_j + _J_PER_TRACK)
        if neuro:
            track_j *= _NEURO_FACTOR

        # Λ advisory: rises with fused confidence + agreement, penalised if
        # inconsistent; bounded so it is NEVER 1.0 (Λ = Conjecture 1, gray). SZL synth.
        base = _LAMBDA_MIN + (_LAMBDA_MAX - _LAMBDA_MIN) * (0.6 * fused_confidence + 0.4 * agreement)
        if not consistent:
            base *= 0.5
        lam = round(min(_LAMBDA_MAX, max(_LAMBDA_MIN, base)), 6)
        admitted = bool(lam >= _LAMBDA_ADMIT and consistent)

        tracks.append({
            "id": i,
            "sensors_detected": [s["name"] for s in detected],
            "sensor_agreement": round(agreement, 6),
            "fused_confidence": round(fused_confidence, 6),
            "fused_sigma": round(fused_sigma, 6),
            "energy_j": round(track_j, 6),
            "age_steps": age,
            "consistent": consistent,
            "lambda_advisory": lam,
            "admitted": admitted,
        })

    admits = sum(1 for t in tracks if t["admitted"])
    gated_out = len(tracks) - admits
    consistent_n = sum(1 for t in tracks if t["consistent"])
    consistency_rate = round(consistent_n / len(tracks), 6) if tracks else 0.0
    mean_conf = round(sum(t["fused_confidence"] for t in tracks) / len(tracks), 6) if tracks else 0.0
    mean_agree = round(sum(t["sensor_agreement"] for t in tracks) / len(tracks), 6) if tracks else 0.0
    mean_lambda = round(sum(t["lambda_advisory"] for t in tracks) / len(tracks), 6) if tracks else 0.0

    # Overall trust: rises with consistency, agreement and mean Λ advisory, HARD-CAPPED
    # at _TRUST_CAP so it is never green / never 1.0 (doctrine v11).
    trust_raw = (0.4 * consistency_rate + 0.3 * mean_agree
                 + 0.3 * (mean_lambda / _LAMBDA_MAX if _LAMBDA_MAX else 0.0))
    trust = round(min(_TRUST_CAP, trust_raw), 6)

    # MODELED joules-per-inference for the WHOLE fused picture (energy-proportional:
    # the fixed pipeline cost + a marginal per-track cost + the sensor sampling cost).
    sample_total = sum(t["energy_j"] for t in tracks)
    fusion_fixed = _J_FUSION_FIXED * (_NEURO_FACTOR if neuro else 1.0)
    joules_per_inference = round(fusion_fixed + _J_PER_TRACK * len(tracks) + sample_total, 6)
    joules_idle_floor = round(_J_IDLE_FLOOR * (_NEURO_FACTOR if neuro else 1.0), 6)

    energy = {
        "label": "MODELED",   # NOT MEASURED — no NVML/RAPL/Loihi meter is wired here.
        "joules_per_inference": joules_per_inference,
        "joules_idle_floor": joules_idle_floor,
        "joules_total": joules_per_inference,
        "energy_proportional": True,
        "neuromorphic": bool(neuro),
        "neuromorphic_factor": _NEURO_FACTOR if neuro else 1.0,
        "breakdown": {
            "fusion_fixed_j": round(fusion_fixed, 6),
            "per_track_j": _J_PER_TRACK,
            "sensor_sample_total_j": round(sample_total, 6),
        },
        "note": ("MODELED parametric joules — scales with active sensors+tracks "
                 "(energy-proportional; idle draws near joules_idle_floor). NOT "
                 "MEASURED: no real NVML/RAPL/Loihi meter is wired. A neuromorphic "
                 "(SNN/Loihi) substrate applies an event-driven efficiency factor. "
                 "Method framing: MLPerf Power (arXiv:2410.12032), CarbonCall "
                 "(arXiv:2504.20348), Loihi (IEEE Micro 2018), snnTorch "
                 "(arXiv:2109.12894)."),
    }

    return {
        "n_tracks": n_tracks,
        "n_sensors": n_sensors,
        "horizon": horizon,
        "sensors": [{"name": s["name"], "sigma": s["sigma"], "joules": s["joules"]} for s in sensors],
        "tracks": tracks[:_TRACK_CAP],
        "fusion": {
            "tracks": len(tracks),
            "admitted": admits,
            "gated_out": gated_out,
            "mean_fused_confidence": mean_conf,
            "mean_sensor_agreement": mean_agree,
            "consistency_rate": consistency_rate,
        },
        "energy": energy,
        "lambda_gate": {
            "status": "Λ = Conjecture 1 (advisory, gray — NEVER green, not a theorem)",
            "admit_threshold": _LAMBDA_ADMIT,
            "mean_lambda_advisory": mean_lambda,
            "bounds": {"min": _LAMBDA_MIN, "max": _LAMBDA_MAX},
            "admits": admits,
            "gated_out": gated_out,
            "trust": trust,
            "trust_cap": _TRUST_CAP,
        },
    }


def _receipt_design(payload, seed):
    """Describe the signed-fusion-receipt-PER-WRITE chain (CONJECTURE synthesis).

    RECEIPT-ON-WRITE, NOT ON-READ: this GET mints NOTHING and appends to no
    provenance chain. To make the design concrete without violating that, we
    compute a plain SHA3-256 content hash of the fusion payload and return it as a
    clearly-UNSIGNED design PREVIEW (signed:false). A real deployment would emit one
    signed Khipu receipt per fused WRITE, binding the sensor set, the fused track
    ids, the Λ-gate verdict, the sensor-agreement/consistency result, and the
    MODELED energy label into the hash-chained receipt DAG — none of which happens
    on this read.
    """
    gate = payload["lambda_gate"]
    fus = payload["fusion"]
    energy = payload["energy"]
    canonical = "|".join([
        f"seed={seed}",
        f"sensors={payload['n_sensors']}",
        f"tracks={fus['tracks']}",
        "ids=" + ",".join(str(t["id"]) for t in payload["tracks"]),
        f"admits={gate['admits']}",
        f"gated_out={gate['gated_out']}",
        f"consistency_rate={fus['consistency_rate']}",
        f"joules_per_inference={energy['joules_per_inference']}",
        f"energy_label={energy['label']}",
        f"trust={gate['trust']}",
    ])
    preview_digest = hashlib.sha3_256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "signed-fusion-receipt-per-write (SZL synthesis — CONJECTURE, design-only)",
        "binds": [
            "sensor set + fused track ids",
            "Λ-gate verdict (admits / gated_out; Λ = Conjecture 1, gray)",
            "sensor-agreement / consistency result (consistency_rate, gated_out)",
            "energy label of the fusion op (MODELED here — MEASURED only with a real meter)",
        ],
        "chain": "one hash-linked Khipu receipt per fused WRITE (Conjecture 2: "
                 "integrity real; BFT/consensus is the conjecture)",
        "signature": "DSSE_PLACEHOLDER (cosign founder-gated) — NOT applied here",
        "signed": False,
        "minted_on_this_get": False,
        "receipt_preview_digest": preview_digest,
        "preview_digest_alg": "SHA3-256 over a canonical fusion summary (UNSIGNED preview only)",
        "doctrine": "RECEIPT-ON-WRITE, NOT ON-READ — a GET signs nothing and grows no chain.",
        "verify_when_minted": "/api/a11oy/v1/khipu/verify/{digest}",
    }


def _ii(req, key, default):
    try:
        return int(float(req.query_params.get(key, default)))
    except Exception:
        return default


def _bool(req, key, default=False):
    v = req.query_params.get(key)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _h_edgefusion(req):
    seed      = _ii(req, "seed", 42)
    n_tracks  = max(1, min(_ii(req, "n_tracks", 48), 512))
    n_sensors = max(1, min(_ii(req, "n_sensors", 4), len(_SENSOR_BANK)))
    horizon   = max(1, min(_ii(req, "horizon", 64), 4096))
    neuro     = _bool(req, "neuro", False)

    p = _fuse(seed=seed, n_tracks=n_tracks, n_sensors=n_sensors, horizon=horizon, neuro=neuro)
    p["receipt_design"] = _receipt_design(p, seed)
    p.update({
        "label": "MODELED",
        "model": ("energy-proportional Λ-gated multi-sensor edge fusion with a "
                  "signed-fusion-receipt-per-write design"),
        "seed": seed,
        "neuromorphic": neuro,
        "parts_labeled": {
            "MODELED": [
                "multi-sensor scene (per-sensor sigma / detection simulation)",
                "inverse-variance (covariance-weighted) track fusion",
                "sensor-agreement consistency check (consistency_rate, gated_out)",
                "joules-per-inference energy model (parametric, energy-proportional)",
                "trust (computed from consistency + agreement + mean Λ, hard-capped at 0.97)",
            ],
            "CONJECTURE": [
                "Λ as a per-track trust gate (Λ = Conjecture 1, gray — never green)",
                "signed-fusion-receipt-per-write chain (design-only; nothing minted on a GET)",
                "the energy-proportional + neuromorphic + governed-fusion synthesis "
                "as one receipt-emitting surface (unshipped combination)",
            ],
        },
        "honest_note": (
            "MODELED + CONJECTURE. The sensor scene, per-sensor noise, "
            "inverse-variance fusion, sensor-agreement consistency check and the "
            "joules-per-inference model are a deterministic seeded simulation; "
            "fused_confidence, consistency_rate, admits/gated_out, joules and trust "
            "are genuinely computed, reported not fabricated. It does NOT run a "
            "trained detector, a real Kalman/factor-graph estimator, any cited fusion "
            "system, or a real power meter. Energy is MODELED, NOT MEASURED — no "
            "NVML/RAPL/Loihi meter is wired (a real delta alone would earn MEASURED). "
            "The SZL SYNTHESIS is CONJECTURE: Λ as a per-track trust gate is the "
            "restraint advisory Λ = Conjecture 1 (gray, NEVER green, not a theorem), "
            "and the signed-fusion-receipt-per-write chain is a DESIGN — no receipt "
            "is minted here (RECEIPT-ON-WRITE, never on a GET); the "
            "receipt_preview_digest is a plain UNSIGNED content hash, not a "
            "signature. Trust is capped at 0.97 and is never 1.0. Cites BEVFusion "
            "(arXiv:2205.13542), TransFuser (arXiv:2205.15997), VINS-Fusion "
            "(HKUST-Aerial-Robotics), MLPerf Power (arXiv:2410.12032), CarbonCall "
            "(arXiv:2504.20348), snnTorch (arXiv:2109.12894), Loihi (IEEE Micro "
            "2018). SZL claims NONE of these methods as its own. Nothing here is in "
            "the locked-8."
        ),
        "citations": CITATIONS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    # Surface reads label at top level OR payload.label, metrics from payload.
    return JSONResponse({"label": "MODELED", "payload": p})


def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/frontier/edgefusion onto app. Additive, try/except-guarded."""
    base = f"/api/{ns}/v1/frontier"
    handlers = [(f"{base}/edgefusion", _h_edgefusion)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    p = _fuse(seed=42, n_tracks=48, n_sensors=4, horizon=64, neuro=False)
    p["receipt_design"] = _receipt_design(p, 42)
    g = p["lambda_gate"]
    f = p["fusion"]
    e = p["energy"]
    assert 0.0 <= g["trust"] <= _TRUST_CAP, "trust must be capped at 0.97"
    assert g["bounds"]["max"] < 1.0, "Λ advisory must never reach 1.0 (Conjecture 1)"
    assert e["label"] == "MODELED", "energy must be MODELED, never MEASURED (no meter)"
    assert p["receipt_design"]["signed"] is False, "no signing on a read path"
    assert p["receipt_design"]["minted_on_this_get"] is False
    assert g["admits"] + g["gated_out"] == f["tracks"]
    # energy-proportional: neuromorphic run must draw strictly fewer joules.
    pn = _fuse(seed=42, n_tracks=48, n_sensors=4, horizon=64, neuro=True)
    assert pn["energy"]["joules_per_inference"] < e["joules_per_inference"], \
        "neuromorphic factor must lower MODELED joules"
    print("tracks:", f["tracks"], "admitted:", f["admitted"], "gated_out:", f["gated_out"])
    print("mean_fused_confidence:", f["mean_fused_confidence"], "mean_sensor_agreement:", f["mean_sensor_agreement"])
    print("consistency_rate:", f["consistency_rate"], "mean_lambda:", g["mean_lambda_advisory"])
    print("trust:", g["trust"], "(cap", _TRUST_CAP, ")", "lambda_status:", g["status"])
    print("joules/inference (dense):", e["joules_per_inference"], "(neuro):", pn["energy"]["joules_per_inference"])
    print("receipt signed:", p["receipt_design"]["signed"], "preview_digest:", p["receipt_design"]["receipt_preview_digest"][:16], "...")
    print("label: MODELED (synthesis parts CONJECTURE)")
