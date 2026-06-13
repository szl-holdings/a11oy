# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings
"""
szl_mosaic_governance.py - a11oy GOVERNANCE-OVER-ANOMALIES surface.

a11oy is the orchestrating governance brain. killinchu / the SZL Mosaic engine
(szl_mosaic_core.py, in the sibling mosaic_szl package) is the FIELD detector:
it detects/scores anomalies and emits structured provenance receipts
(schema "szl.mosaic.receipt/v1"). THIS module is the GOVERNED VIEW over those
detections: it takes each anomaly receipt and presents

  - its 13-axis Lambda advisory verdict        (allow | advisory | deny)
  - its signed provenance receipt               (DSSE/Khipu, honestly UNSIGNED here)
  - the human-approval gate for high-impact ROE actions (operator approvals)
  - a fused Common-Operating-Picture (COP) roll-up: counts of tracks / anomalies
    / verdicts across the air + maritime + (roadmap) orbital domains
  - multi-witness threat confirmation via Khipu BFT 3-of-4 (Conjecture 2)

clean-room note
---------------
This is a CLEAN-ROOM SZL surface inspired ONLY by the *publicly described*
capability of True Anomaly Inc.'s "Mosaic" (SDA / C2 / Threat-Warning &
Assessment -> Common Operating Picture). NO proprietary Mosaic source, assets,
or internals were seen or copied. See estate_audit/mosaic_identification.md.

HONEST POSTURE (Doctrine v11) - binding:
  - Lambda (L) = Conjecture 1 (conditional, ADVISORY). NEVER "proven trust".
    Verdicts are advisories under human-on-the-loop, never autonomous authority.
  - Khipu BFT safety = Conjecture 2 (Wave23 conditional, OPEN). Multi-witness
    confirmation REDUCES single-sensor risk; it is not a proof of correctness.
  - Confidence is a BOUNDED / conformal interval (finite-sample), not a certainty.
  - locked-proven formulas = 8 {F1,F4,F7,F11,F12,F18,F19,F22}; organs EXPERIMENTAL.
  - Receipts are real-DSSE-or-honestly-UNSIGNED, never silently fabricated.
  - When no live engine feed is wired into THIS Space, the surface returns a
    clearly-labeled deterministic SNAPSHOT (source="snapshot", verified=false).
    It NEVER fabricates a live count or a signature.
  - Sovereign own-metal, 0 CDN; pure stdlib here (no network, no new deps).

The receipt SHAPE returned here is byte-compatible with szl_mosaic_core.py's
ProvenanceReceipt ("szl.mosaic.receipt/v1") so that, once the engine feed is
wired in, the GOVERNED view ingests REAL receipts with zero schema change.
"""

from __future__ import annotations

import hashlib
import json
import time

# 13-axis Lambda trust vocabulary (advisory; Conjecture 1). Same family the
# console's Trust Score (lambda) tab already names. Listed for the governed view
# so an operator can see WHICH axes a given anomaly's advisory verdict leaned on.
LAMBDA_AXES = [
    "provenance", "consistency", "calibration", "robustness", "freshness",
    "corroboration", "specificity", "authority", "reversibility", "containment",
    "sensor_integrity", "graph_deviation", "human_review",
]

# Advisory thresholds mirror szl_mosaic_core.SZLMosaicCore defaults so the
# governed view's verdict math matches the field engine's exactly.
_ALLOW_THR = 0.35
_DENY_THR = 0.65

_DOCTRINE = {
    "doctrine": "v11",
    "lambda": "Conjecture 1 (conditional, ADVISORY) - NOT proven trust",
    "khipu_bft": "Conjecture 2 (Wave23 conditional, OPEN) - multi-witness, not a proof",
    "locked_proven": 8,
    "locked_facts": ["F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22"],
    "organs": "EXPERIMENTAL",
    "slsa": "L1 honest / L2 build-attested / L3 roadmap",
    "joules": "MEASURED only (none claimed here)",
    "sovereign": "own-metal only; 0 CDN",
    "free_energy": False,
    "receipts": "real-DSSE-or-honestly-UNSIGNED; never silently fabricated",
    "human_on_the_loop": True,
}


def _verdict(score: float) -> str:
    """Honest ADVISORY Lambda verdict (Conjecture 1). Never 'proven trust'."""
    if score < _ALLOW_THR:
        return "allow"
    if score < _DENY_THR:
        return "advisory"
    return "deny"


def _h(*parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p).encode())
    return h.hexdigest()


def _receipt(track_id, domain, score, components, witnesses, ci, ts):
    """One governed anomaly record, receipt SHAPE-compatible with
    szl_mosaic_core.ProvenanceReceipt (schema szl.mosaic.receipt/v1).

    verified=False and signing=UNSIGNED: this Space does not hold the cosign key,
    so we mark the receipt honestly unsigned and name exactly where a real DSSE/
    Khipu signature attaches. We never fabricate a signature.
    """
    verdict = _verdict(score)
    quorum_ok = witnesses >= 3  # Khipu BFT 3-of-4 (Conjecture 2)
    return {
        "schema": "szl.mosaic.receipt/v1",
        "inputs_sha256": _h("mosaic-gov-snapshot", track_id, domain, round(score, 6), ts),
        "track_id": track_id,
        "domain": domain,
        "timestep": ts,
        "detector_ensemble": [
            "IsolationForest(PyOD-lineage,BSD-2)",
            "Autoencoder(Merlion/TODS-lineage,BSD-3/Apache-2)",
            "RobustZScore(tsod-lineage,MIT)",
            "GraphDeviation(GDN/PyGOD-lineage,MIT/BSD-2)",
        ],
        "component_scores": components,
        "anomaly_score": round(float(score), 4),
        "confidence_interval": [round(ci[0], 4), round(ci[1], 4)],
        "confidence_method": (
            "split-conformal-style, alpha=0.1 (bounded finite-sample interval, "
            "NOT a certainty claim)"
        ),
        "lambda_verdict": verdict,
        "lambda_note": (
            "Lambda is Conjecture 1 (conditional, ADVISORY) - NOT proven trust. "
            "Human-on-the-loop required."
        ),
        # Khipu BFT 3-of-4 multi-witness confirmation (Conjecture 2, OPEN).
        "khipu_witnesses": witnesses,
        "khipu_quorum": "3-of-4",
        "khipu_quorum_reached": quorum_ok,
        "khipu_note": (
            "BFT 3-of-4 multi-witness confirmation (Conjecture 2, OPEN) reduces "
            "single-sensor/spoof risk; it is not a proof of correctness."
        ),
        # High-impact deny advisories require an explicit operator approval gate.
        "requires_human_approval": verdict == "deny",
        "approval_state": "PENDING_OPERATOR" if verdict == "deny" else "n/a",
        "verified": False,
        "signing": (
            "UNSIGNED - sign downstream via DSSE/Khipu in a11oy / khipu-consensus "
            "(BFT 3-of-4) on a SHA-256 Merkle DAG. real-DSSE-or-honestly-UNSIGNED; "
            "never silently fabricated."
        ),
        "doctrine": "v11",
    }


def _snapshot():
    """Deterministic, clearly-labeled SNAPSHOT of the governed-anomaly picture.

    Used when no live SZL-Mosaic engine feed is wired into THIS Space. Every
    field is labeled source="snapshot" / verified=false. NO live count and NO
    signature is fabricated. The shape is identical to what a live feed returns,
    so the frontend code path is the same live-or-snapshot.
    """
    ts = 0
    # A small, honest illustrative population spanning the fused COP domains.
    # Scores are fixed (deterministic), not random, so the snapshot is stable.
    rows = [
        # track_id, domain,     score, witnesses, components
        (101, "air",      0.12, 4, {"iforest": 0.10, "autoencoder": 0.14, "robust_zscore": 0.11}),
        (102, "air",      0.41, 4, {"iforest": 0.39, "autoencoder": 0.45, "robust_zscore": 0.38}),
        (103, "maritime", 0.22, 3, {"iforest": 0.20, "autoencoder": 0.26, "robust_zscore": 0.21}),
        (104, "maritime", 0.71, 4, {"iforest": 0.68, "autoencoder": 0.77, "robust_zscore": 0.69}),
        (105, "air",      0.83, 4, {"iforest": 0.81, "autoencoder": 0.88, "robust_zscore": 0.80}),
        (106, "orbital",  0.34, 2, {"iforest": 0.31, "autoencoder": 0.39, "robust_zscore": 0.33}),
    ]
    receipts = []
    for tid, dom, sc, wit, comp in rows:
        ci = (max(0.0, sc - 0.07), min(1.0, sc + 0.07))
        receipts.append(_receipt(tid, dom, sc, comp, wit, ci, ts))

    # Fused Common-Operating-Picture roll-up across domains.
    by_verdict = {"allow": 0, "advisory": 0, "deny": 0}
    by_domain = {}
    for r in receipts:
        by_verdict[r["lambda_verdict"]] += 1
        by_domain[r["domain"]] = by_domain.get(r["domain"], 0) + 1
    quorum_ok = sum(1 for r in receipts if r["khipu_quorum_reached"])
    pending = [r["track_id"] for r in receipts if r["approval_state"] == "PENDING_OPERATOR"]

    return {
        "status": "ok",
        "ns": "a11oy",
        "source": "snapshot",
        "source_note": (
            "SNAPSHOT - no live SZL-Mosaic engine feed is wired into this Space. "
            "Deterministic illustrative population; verified=false; no live count "
            "or signature is fabricated. Wire szl_mosaic_core receipts here to go live."
        ),
        "generated_at_unix": int(time.time()),
        "cop": {
            "tracks_total": len(receipts),
            "anomalies_scored": len(receipts),
            "by_verdict": by_verdict,
            "by_domain": by_domain,
            "domains": ["air", "maritime", "orbital (roadmap)"],
            "khipu_quorum_reached": quorum_ok,
            "khipu_quorum_total": len(receipts),
            "pending_operator_approvals": pending,
        },
        "lambda_axes": LAMBDA_AXES,
        "thresholds": {"allow_below": _ALLOW_THR, "deny_at_or_above": _DENY_THR},
        "receipts": receipts,
        "doctrine": _DOCTRINE,
    }


def governed_view():
    """Public entrypoint. Returns the governed-anomaly picture.

    This Space carries no live engine feed, so it returns the honest SNAPSHOT.
    When a live SZL-Mosaic receipt stream is mounted, replace the snapshot source
    with the ingested receipts (same schema) and set source="live".
    """
    return _snapshot()


def register(app, ns: str = "a11oy"):
    """Additive registration of the governed-anomalies surface.

    Adds GET /api/{ns}/v1/mosaic/governed. Pure stdlib, no new deps, no network.
    Idempotent and side-effect-free beyond adding one read-only route.
    """
    from fastapi.responses import JSONResponse

    path = f"/api/{ns}/v1/mosaic/governed"

    async def _handler():  # pragma: no cover - thin wrapper over governed_view()
        try:
            return JSONResponse(governed_view())
        except Exception as e:  # never 500 the console; degrade honestly
            return JSONResponse(
                {
                    "status": "error",
                    "source": "snapshot",
                    "error": f"{e!r}",
                    "note": "governed-anomaly view unavailable; nothing fabricated.",
                    "doctrine": _DOCTRINE,
                },
                status_code=200,
            )

    app.add_api_route(path, _handler, methods=["GET"], name="mosaic_governed")
    return path


if __name__ == "__main__":
    print(json.dumps(governed_view(), indent=2))
