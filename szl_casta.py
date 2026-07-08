"""
szl_casta.py — SZL CASTA: Clean-room Anomaly + Streaming Test-time Adaptation. A
Λ-advisory TRUST GATE (Λ = Conjecture 1, gray, NEVER green) over which streaming
test-time ADAPTATION updates are safe to apply, using the clean-room SDA anomaly
scorer (khipu-sda-core) as the guard against adapting to poisoned / anomalous drift —
with a signed-adaptation-receipt-per-write design.

This is an SZL cross-axis SYNTHESIS: test-time adaptation (Tent, CoTTA, EATA, MEMO)
lets a model adapt to distribution shift ONLINE, but it is well known to be fragile —
adapting to adversarial or anomalous batches can collapse the model. Streaming anomaly
detection (Robust Random Cut Forest, Isolation Forest) can flag those bad batches. No
published system COUPLES a clean-room streaming anomaly detector to a governed,
advisory-trust-gated adaptation loop that REFUSES to adapt to what the detector flags.
CASTA ties those real leaders to the SZL clean-room SDA kernel (khipu-sda-core) and the
szl-lambda-gate.

  GET  /api/<ns>/v1/frontier/casta?seed=&n_steps=&drift=&contamination=&adapt=

The endpoint returns a MODELED/CONJECTURE model of governed streaming adaptation: a
deterministic, seeded stream with a gradual distribution DRIFT and injected ANOMALIES
(contamination) is scored by the clean-room SDA detector; a streaming test-time
adaptation step is proposed per window; each proposed adaptation passes a Λ-advisory
trust gate that BLOCKS updates on anomalous windows; and the response DESCRIBES (does
not mint) the signed receipt each committed-adaptation WRITE would emit.

Returned JSON (top-level `label`, metrics nested under `payload`)
----------------------------------------------------------------------------
  label                       : "MODELED"
  payload.n_steps             : number of modeled stream windows
  payload.drift               : per-step drift magnitude (distribution shift rate)
  payload.contamination       : injected anomaly rate (fraction of windows)
  payload.adapt               : whether adaptation is enabled (gated)
  payload.windows[]           : {id, drift_offset, anomaly_score, is_anomaly,
                                adaptation_gain, applied, lambda_advisory, admitted}
  payload.stream              : {windows, admitted, gated_out, detected_anomalies,
                                true_anomalies, detection_rate, false_positive_rate,
                                mean_adaptation_gain, stability_rate}
  payload.lambda_gate         : {status, admit_threshold, mean_lambda_advisory,
                                bounds, admits, gated_out, trust, trust_cap} — Λ
                                advisory (Conjecture 1, gray)
  payload.receipt_design      : signed-adaptation-receipt-per-write DESIGN
                                (CONJECTURE), incl. an UNSIGNED content-hash preview
  payload.parts_labeled       : which parts are MODELED vs CONJECTURE
  payload.honest_note         : plain-language honesty disclaimer
  payload.citations           : dict of citable sources (verbatim, never claimed as ours)
  payload.computed_at         : ISO-8601 UTC timestamp

HONEST STATUS
  MODELED — the drifting stream, injected anomalies, clean-room anomaly scores, and
    the adaptation-gain model are a deterministic seeded simulation. detection_rate,
    false_positive_rate, mean_adaptation_gain, admits/gated_out and trust are genuinely
    COMPUTED from the modeled stream, reported not fabricated. It does NOT run a real
    test-time-adaptation loop (Tent/CoTTA/EATA/MEMO), a real anomaly forest on real
    data, or reproduce any cited system's results.
  CONJECTURE — the SZL SYNTHESIS is unproven and labeled as such: (a) Λ as a
    per-window adaptation-safe gate is the szl-lambda-gate advisory Λ = Conjecture 1
    (gray, NEVER green), not a theorem; (b) the signed-adaptation-receipt-per-write
    chain is a DESIGN — no receipt is minted here (receipt-on-WRITE, never on a GET);
    (c) the clean-room-anomaly + streaming-adaptation + signed-receipt COMBINATION as
    one surface is the SZL-original synthesis (unshipped combination).

DOCTRINE v11
  Nothing here is in the locked-8 (adds 0). Λ = Conjecture 1 (gray, never green).
  Trust is capped at 0.97 and is never 1.0. No fabricated data. Pure stdlib.
  Deterministic with seed. 0 runtime CDN. RECEIPT-ON-WRITE, NOT ON-READ.

CITATIONS (clean-room; none claimed as SZL's own; verified to resolve 2026-07-07):
  Tent: Fully Test-Time Adaptation by Entropy Minimization:
    Wang et al. 2021, arXiv:2006.10726   https://arxiv.org/abs/2006.10726
  Continual Test-Time Domain Adaptation (CoTTA):
    Wang et al. 2022, arXiv:2203.13591   https://arxiv.org/abs/2203.13591
  Efficient Test-Time Model Adaptation without Forgetting (EATA):
    Niu et al. 2022, arXiv:2204.02610   https://arxiv.org/abs/2204.02610
  MEMO: Test Time Robustness via Adaptation and Augmentation:
    Zhang et al. 2021, arXiv:2110.09506   https://arxiv.org/abs/2110.09506
  Robust Random Cut Forest Based Anomaly Detection On Streams:
    Guha et al. 2016, PMLR v48   https://proceedings.mlr.press/v48/guha16.html
  Isolation Forest:
    Liu et al. 2008, IEEE ICDM, doi:10.1109/ICDM.2008.17
    https://doi.org/10.1109/ICDM.2008.17
"""
import hashlib
from datetime import datetime, timezone

from starlette.requests import Request
from starlette.routing import Route
from starlette.responses import JSONResponse

CITATIONS = {
    "Tent: Fully Test-Time Adaptation by Entropy Minimization — Wang et al. 2021 arXiv:2006.10726": "https://arxiv.org/abs/2006.10726",
    "Continual Test-Time Domain Adaptation (CoTTA) — Wang et al. 2022 arXiv:2203.13591": "https://arxiv.org/abs/2203.13591",
    "Efficient Test-Time Model Adaptation without Forgetting (EATA) — Niu et al. 2022 arXiv:2204.02610": "https://arxiv.org/abs/2204.02610",
    "MEMO: Test Time Robustness via Adaptation and Augmentation — Zhang et al. 2021 arXiv:2110.09506": "https://arxiv.org/abs/2110.09506",
    "Robust Random Cut Forest Anomaly Detection On Streams — Guha et al. 2016 PMLR v48": "https://proceedings.mlr.press/v48/guha16.html",
    "Isolation Forest — Liu et al. 2008 IEEE ICDM doi:10.1109/ICDM.2008.17": "https://doi.org/10.1109/ICDM.2008.17",
}

# MODELED stream / detector / gate hyperparameters (reported verbatim; not trained).
_LAMBDA_MIN = 0.02          # Λ advisory lower bound (gray floor)
_LAMBDA_MAX = 0.94          # Λ advisory upper bound (NEVER 1.0 — Conjecture 1)
_LAMBDA_ADMIT = 0.55        # advisory admit threshold (a window's adaptation admitted above it)
_TRUST_CAP = 0.97           # doctrine hard cap on trust (never green / never 1.0)
_ANOMALY_THRESH = 0.62      # clean-room SDA score above which a window is flagged anomalous
_WINDOW_CAP = 96            # max window entries returned (matches surface stream cap)


def _u01(seed, i, salt=0):
    """Deterministic uniform in [0,1) from (seed, i, salt) via two LCG rounds."""
    s = ((i + 1) * 2654435761 + seed * 40503 + salt * 2246822519) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    s = (1664525 * s + 1013904223) & 0xFFFFFFFF
    return s / 4294967295.0


def _run_stream(seed=42, n_steps=48, drift=0.015, contamination=0.12, adapt=True):
    """Deterministic clean-room-anomaly + streaming-adaptation simulation.

    A stream of `n_steps` windows drifts by `drift` per step (a growing distribution
    offset). A `contamination` fraction of windows have an injected ANOMALY (a spike
    unrelated to the smooth drift). The clean-room SDA detector (khipu-sda-core)
    assigns each window an anomaly SCORE in [0,1] (high on injected anomalies, low on
    smooth drift) and flags it anomalous above _ANOMALY_THRESH. A streaming test-time
    ADAPTATION step proposes a gain that would reduce the drift offset; the Λ-gate
    ADMITS (applies) the adaptation iff the window is NOT flagged anomalous AND the
    advisory clears the threshold — i.e. it REFUSES to adapt to anomalous windows (the
    guard the field lacks). The gate is ADVISORY (gray), never green; overall trust is
    capped at _TRUST_CAP.
    """
    n_steps = max(1, min(n_steps, 4096))
    drift = min(0.2, max(0.0, float(drift)))
    contamination = min(0.9, max(0.0, float(contamination)))

    windows = []
    detected = 0
    true_anom = 0
    false_pos = 0
    applied_n = 0
    for i in range(n_steps):
        drift_offset = round(drift * i, 6)                 # accumulated distribution shift
        # injected anomaly? deterministic per window at the contamination rate.
        is_true_anom = _u01(seed, i, salt=4) < contamination
        if is_true_anom:
            true_anom += 1

        # clean-room SDA anomaly score: baseline noise for smooth drift, spiked for
        # injected anomalies (with a little modeled detector imperfection).
        base_score = 0.15 + 0.35 * _u01(seed, i, salt=8)
        if is_true_anom:
            base_score = min(0.99, base_score + 0.45)
        anomaly_score = round(base_score, 6)
        flagged = anomaly_score >= _ANOMALY_THRESH
        if flagged:
            detected += 1
            if not is_true_anom:
                false_pos += 1

        # adaptation gain: how much this window's TTA step would reduce the drift
        # offset (higher when the offset is large). Only meaningful if applied.
        adaptation_gain = round(min(0.9, 0.2 + 1.2 * drift_offset), 6)

        # Λ advisory: high when the window is clean (low anomaly score) and the
        # adaptation is useful; crushed when flagged anomalous. Bounded < 1.0
        # (Λ = Conjecture 1, gray). SZL synthesis.
        clean = max(0.0, 1.0 - anomaly_score)
        base = _LAMBDA_MIN + (_LAMBDA_MAX - _LAMBDA_MIN) * (0.6 * clean + 0.4 * adaptation_gain)
        if flagged:
            base *= 0.4
        lam = round(min(_LAMBDA_MAX, max(_LAMBDA_MIN, base)), 6)
        # admitted = adaptation is APPLIED: only if enabled, not flagged, advisory clears.
        admitted = bool(adapt and (not flagged) and lam >= _LAMBDA_ADMIT)
        if admitted:
            applied_n += 1

        windows.append({
            "id": i,
            "drift_offset": drift_offset,
            "anomaly_score": anomaly_score,
            "is_anomaly": bool(is_true_anom),
            "flagged": bool(flagged),
            "adaptation_gain": adaptation_gain,
            "applied": admitted,
            "lambda_advisory": lam,
            "admitted": admitted,
        })

    admits = applied_n
    gated_out = len(windows) - admits
    detection_rate = round(
        sum(1 for w in windows if w["flagged"] and w["is_anomaly"]) / true_anom, 6
    ) if true_anom else 0.0
    fp_rate = round(false_pos / max(1, sum(1 for w in windows if not w["is_anomaly"])), 6)
    # stability: fraction of windows where the gate made the SAFE choice (did NOT apply
    # on an anomaly, applied-or-held sensibly otherwise).
    safe = sum(1 for w in windows if not (w["applied"] and w["is_anomaly"]))
    stability_rate = round(safe / len(windows), 6) if windows else 0.0
    mean_gain = round(
        sum(w["adaptation_gain"] for w in windows if w["applied"]) / max(1, applied_n), 6
    ) if applied_n else 0.0
    mean_lambda = round(sum(w["lambda_advisory"] for w in windows) / len(windows), 6) if windows else 0.0

    # Overall trust: rises with detection quality, stability and mean Λ advisory,
    # HARD-CAPPED at _TRUST_CAP so it is never green / never 1.0 (doctrine v11).
    trust_raw = (0.35 * stability_rate + 0.25 * detection_rate
                 + 0.1 * (1.0 - fp_rate)
                 + 0.3 * (mean_lambda / _LAMBDA_MAX if _LAMBDA_MAX else 0.0))
    trust = round(min(_TRUST_CAP, max(0.0, trust_raw)), 6)

    return {
        "n_steps": n_steps,
        "drift": round(drift, 6),
        "contamination": round(contamination, 6),
        "adapt": bool(adapt),
        "anomaly_threshold": _ANOMALY_THRESH,
        "windows": windows[:_WINDOW_CAP],
        "stream": {
            "windows": len(windows),
            "admitted": admits,
            "gated_out": gated_out,
            "detected_anomalies": detected,
            "true_anomalies": true_anom,
            "detection_rate": detection_rate,
            "false_positive_rate": fp_rate,
            "mean_adaptation_gain": mean_gain,
            "stability_rate": stability_rate,
        },
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
    """Describe the signed-adaptation-receipt-PER-WRITE chain (CONJECTURE synthesis).

    RECEIPT-ON-WRITE, NOT ON-READ: this GET mints NOTHING and appends to no
    provenance chain. We compute a plain SHA3-256 content hash of the stream summary
    and return it as a clearly-UNSIGNED design PREVIEW (signed:false). A real
    deployment would emit one signed Khipu receipt per COMMITTED adaptation write,
    binding the window ids, the anomaly verdict, the adaptation gain, and the Λ-gate
    verdict into the hash-chained receipt DAG.
    """
    gate = payload["lambda_gate"]
    st = payload["stream"]
    canonical = "|".join([
        f"seed={seed}",
        f"steps={payload['n_steps']}",
        f"drift={payload['drift']}",
        f"contamination={payload['contamination']}",
        "wids=" + ",".join(str(w["id"]) for w in payload["windows"]),
        f"admits={gate['admits']}",
        f"gated_out={gate['gated_out']}",
        f"detection_rate={st['detection_rate']}",
        f"false_positive_rate={st['false_positive_rate']}",
        f"trust={gate['trust']}",
    ])
    preview_digest = hashlib.sha3_256(canonical.encode("utf-8")).hexdigest()
    return {
        "kind": "signed-adaptation-receipt-per-write (SZL synthesis — CONJECTURE, design-only)",
        "binds": [
            "window ids + anomaly verdict (clean-room SDA / khipu-sda-core)",
            "adaptation gain of the committed test-time update",
            "Λ-gate verdict (admits / gated_out; Λ = Conjecture 1, gray)",
        ],
        "chain": "one hash-linked Khipu receipt per committed-adaptation WRITE (Conjecture 2: "
                 "integrity real; BFT/consensus is the conjecture)",
        "signature": "DSSE_PLACEHOLDER (cosign founder-gated) — NOT applied here",
        "signed": False,
        "minted_on_this_get": False,
        "receipt_preview_digest": preview_digest,
        "preview_digest_alg": "SHA3-256 over a canonical stream summary (UNSIGNED preview only)",
        "doctrine": "RECEIPT-ON-WRITE, NOT ON-READ — a GET signs nothing and grows no chain.",
        "verify_when_minted": "/api/a11oy/v1/khipu/verify/{digest}",
    }


def _ii(req, key, default):
    try:
        return int(float(req.query_params.get(key, default)))
    except Exception:
        return default


def _ff(req, key, default):
    try:
        return float(req.query_params.get(key, default))
    except Exception:
        return default


def _bool(req, key, default=False):
    v = req.query_params.get(key)
    if v is None:
        return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def _h_casta(req: Request):
    seed          = _ii(req, "seed", 42)
    n_steps       = max(1, min(_ii(req, "n_steps", 48), 4096))
    drift         = min(0.2, max(0.0, _ff(req, "drift", 0.015)))
    contamination = min(0.9, max(0.0, _ff(req, "contamination", 0.12)))
    adapt         = _bool(req, "adapt", True)

    p = _run_stream(seed=seed, n_steps=n_steps, drift=drift, contamination=contamination, adapt=adapt)
    p["receipt_design"] = _receipt_design(p, seed)
    p.update({
        "label": "MODELED",
        "model": ("clean-room anomaly (khipu-sda-core) guarding streaming test-time "
                  "adaptation behind a szl-lambda-gate trust gate, with a "
                  "signed-adaptation-receipt-per-write design"),
        "seed": seed,
        "parts_labeled": {
            "MODELED": [
                "drifting stream + injected anomalies (contamination)",
                "clean-room SDA anomaly scores (khipu-sda-core)",
                "streaming test-time adaptation gain model",
                "trust (computed from detection + stability + mean Λ, hard-capped at 0.97)",
            ],
            "CONJECTURE": [
                "Λ as a per-window adaptation-safe gate (szl-lambda-gate; Λ = Conjecture 1, gray — never green)",
                "signed-adaptation-receipt-per-write chain (design-only; nothing minted on a GET)",
                "the clean-room-anomaly + streaming-adaptation + signed-receipt synthesis as one surface "
                "(unshipped combination)",
            ],
        },
        "honest_note": (
            "MODELED + CONJECTURE. The drifting stream, injected anomalies, clean-room "
            "anomaly scores, and the adaptation-gain model are a deterministic seeded "
            "simulation; detection_rate, false_positive_rate, mean_adaptation_gain, "
            "admits/gated_out and trust are genuinely computed, reported not "
            "fabricated. It does NOT run a real test-time-adaptation loop "
            "(Tent/CoTTA/EATA/MEMO), a real anomaly forest on real data, or reproduce "
            "any cited system's results. The SZL SYNTHESIS is CONJECTURE: Λ as a "
            "per-window adaptation-safe gate is the szl-lambda-gate advisory "
            "Λ = Conjecture 1 (gray, NEVER green, not a theorem), and the "
            "signed-adaptation-receipt-per-write chain is a DESIGN — no receipt is "
            "minted here (RECEIPT-ON-WRITE, never on a GET); the receipt_preview_digest "
            "is a plain UNSIGNED content hash, not a signature. Trust is capped at 0.97 "
            "and is never 1.0. Cites Tent (arXiv:2006.10726), CoTTA "
            "(arXiv:2203.13591), EATA (arXiv:2204.02610), MEMO (arXiv:2110.09506), "
            "Robust Random Cut Forest (PMLR v48 2016), Isolation Forest (IEEE ICDM "
            "2008). SZL claims NONE of these methods as its own. Nothing here is in the "
            "locked-8."
        ),
        "citations": CITATIONS,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    })
    return JSONResponse({"label": "MODELED", "payload": p})


def register(app, ns: str = "a11oy"):
    """Wire /api/<ns>/v1/frontier/casta onto app. Additive, try/except-guarded."""
    base = f"/api/{ns}/v1/frontier"
    handlers = [(f"{base}/casta", _h_casta)]
    add_api_route = getattr(app, "add_api_route", None)
    for path, fn in handlers:
        if callable(add_api_route):
            app.add_api_route(path, fn, methods=["GET"])
        else:
            app.router.routes.append(Route(path, fn))
    return [p for p, _ in handlers]


if __name__ == "__main__":
    p = _run_stream(seed=42, n_steps=48, drift=0.015, contamination=0.12, adapt=True)
    p["receipt_design"] = _receipt_design(p, 42)
    g = p["lambda_gate"]
    s = p["stream"]
    assert 0.0 <= g["trust"] <= _TRUST_CAP, "trust must be capped at 0.97"
    assert g["bounds"]["max"] < 1.0, "Λ advisory must never reach 1.0 (Conjecture 1)"
    assert p["receipt_design"]["signed"] is False, "no signing on a read path"
    assert p["receipt_design"]["minted_on_this_get"] is False
    assert g["admits"] + g["gated_out"] == s["windows"]
    # governance guard: no ANOMALOUS window may ever have its adaptation applied.
    assert not any(w["applied"] and w["is_anomaly"] for w in p["windows"]), \
        "gate must never apply adaptation on a flagged anomaly"
    # disabling adaptation must apply zero updates.
    p_off = _run_stream(seed=42, n_steps=48, drift=0.015, contamination=0.12, adapt=False)
    assert p_off["stream"]["admitted"] == 0, "adapt=False must apply no updates"
    print("windows:", s["windows"], "admitted:", s["admitted"], "gated_out:", s["gated_out"])
    print("true_anomalies:", s["true_anomalies"], "detected:", s["detected_anomalies"],
          "detection_rate:", s["detection_rate"], "false_positive_rate:", s["false_positive_rate"])
    print("mean_adaptation_gain:", s["mean_adaptation_gain"], "stability_rate:", s["stability_rate"], "mean_lambda:", g["mean_lambda_advisory"])
    print("trust:", g["trust"], "(cap", _TRUST_CAP, ")", "lambda_status:", g["status"])
    print("receipt signed:", p["receipt_design"]["signed"], "preview_digest:", p["receipt_design"]["receipt_preview_digest"][:16], "...")
    print("label: MODELED (synthesis parts CONJECTURE)")
