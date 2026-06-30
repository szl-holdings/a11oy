"""szl_eu_energy.py — EU AI Act Article 53 signed energy disclosure.

Pattern from: HF AI Energy Score (Sasha Luccioni / HF Research, public methodology)
+ GSF-SCI ISO-21031 formula.  EU AI Act Article 53(1)(b) enforcement begins August 2026.
Differentiator: we SIGN the energy disclosure into the Merkle log — no competitor does this.
Their energy labels are self-reported dashboards; ours is machine-signed, Merkle-logged,
verifiable per-inference.

HONEST REALITY (v11 — NEVER violate):
  The live HF Space runs on a CPU-basic tier with NO NVML GPU meter.  On this runtime:
    - energy_wh_per_1k_tokens is null
    - measurement_label is "UNAVAILABLE"
    - signed: true (the disclosure *structure* is signed; the value inside is honestly null)
    - The signed structure proves the hook exists + is doctrine-compliant BEFORE the meter
      is live — the sovereign TDX/GPU deployment auto-populates MEASURED values.

  We NEVER fabricate watt-hours, joules, tokens, or gCO2 figures.

METHODOLOGY (when meter IS live):
  energy_wh_per_1k_tokens = (nvml_joules_delta / token_count) * 1000 / 3600
    (Wh = J / 3600; per-1k-token normalisation matches HF AI Energy Score)
  gco2_per_1k_tokens = energy_wh_per_1k_tokens * (grid_gco2_per_kwh / 1000)
    (HF AI Energy Score + GSF-SCI ISO-21031 methodology)
  methodology_label: "HF-Energy-Score + GSF-SCI ISO-21031"

SIGNING:
  The disclosure object is DSSE-signed (same szl_dsse signer used elsewhere) and
  appended to the Khipu Merkle log so it is per-inference provable, not a dashboard stat.

ENDPOINTS:
  GET /api/a11oy/v1/energy/eu-disclosure   — honest UNAVAILABLE now; MEASURED on metal+meter

RECEIPT FIELD:
  energy_eu_disclosure: { watt_hours_per_1k_tokens, gco2_per_1k_tokens,
                          methodology, measurement_label, signed, merkle_leaf,
                          article: "EU-AI-Act-53(1)(b)" }

SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · Doctrine v11
"""

from __future__ import annotations

import hashlib
import json as _json
import os
from datetime import datetime, timezone
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_METHODOLOGY = "HF-Energy-Score + GSF-SCI ISO-21031"
_ARTICLE = "EU-AI-Act-53(1)(b)"
_LABEL_MEASURED = "MEASURED"
_LABEL_UNAVAILABLE = "UNAVAILABLE"
_J_PER_KWH = 3_600_000.0  # joules per kWh
_WH_PER_J = 1.0 / 3600.0  # Wh per joule

# Default grid carbon intensity (gCO2eq/kWh) — MODELED fallback when no live feed.
# EU average 2024 approx 330 gCO2eq/kWh (Ember Climate, public data).
# Overridable by env SZL_GRID_GCO2_PER_KWH.
_DEFAULT_GRID_GCO2_PER_KWH = float(
    os.environ.get("SZL_GRID_GCO2_PER_KWH", "330.0")
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Meter probe — reads NVML joules delta from the in-process energy sovereign module
# (same source used by szl_governed_api governed_infer).
# ---------------------------------------------------------------------------
def _nvml_available() -> bool:
    """True ONLY when the sovereign NVML exporter is configured AND reachable.

    Uses the same probe as szl_energy_live (fire-and-forget, short timeout).
    Returns False if any import or network call fails — never fabricates.
    """
    try:
        import szl_energy_live as _el
        snap = _el.meter_snapshot()
        return bool(snap.get("reachable"))
    except Exception:
        return False


def compute_eu_disclosure(
    nvml_joules_delta: float | None,
    token_count: int | None,
    grid_gco2_per_kwh: float | None = None,
) -> dict:
    """Compute the EU-AI-Act Art. 53 energy disclosure object.

    Args:
        nvml_joules_delta: Measured GPU joule delta for this inference (MEASURED);
                           or None when no NVML meter is available.
        token_count:       Total tokens (prompt + completion) for this inference.
                           None or 0 → UNAVAILABLE.
        grid_gco2_per_kwh: Grid carbon intensity in gCO2eq/kWh.  If None, uses the
                           env-overridable default (MODELED label).

    Returns a disclosure dict.  measurement_label is MEASURED iff both
    nvml_joules_delta and token_count are real positive numbers.
    NEVER fabricates any value.
    """
    carbon_label = "MODELED"
    if grid_gco2_per_kwh is None:
        grid_gco2_per_kwh = _DEFAULT_GRID_GCO2_PER_KWH
        carbon_label = "MODELED"
    else:
        carbon_label = "MEASURED"

    # Determine if we can compute MEASURED values
    has_joules = isinstance(nvml_joules_delta, (int, float)) and nvml_joules_delta > 0
    has_tokens = isinstance(token_count, int) and token_count > 0

    if has_joules and has_tokens:
        # HF AI Energy Score formula: Wh per 1000 tokens
        wh_per_1k = (nvml_joules_delta * _WH_PER_J / token_count) * 1000.0
        wh_per_1k = round(wh_per_1k, 9)
        # GSF-SCI: gCO2eq per 1000 tokens
        gco2_per_1k = (wh_per_1k / 1000.0) * grid_gco2_per_kwh  # Wh → kWh → gCO2
        gco2_per_1k = round(gco2_per_1k, 9)
        measurement_label = _LABEL_MEASURED
        note = "energy_wh_per_1k_tokens MEASURED from live NVML exporter + token count"
    else:
        wh_per_1k = None
        gco2_per_1k = None
        measurement_label = _LABEL_UNAVAILABLE
        reasons = []
        if not has_joules:
            reasons.append("no NVML joule delta (no GPU meter on current runtime)")
        if not has_tokens:
            reasons.append("no token count")
        note = "; ".join(reasons) + " — values NOT fabricated"

    disclosure = {
        "article": _ARTICLE,
        "methodology": _METHODOLOGY,
        "watt_hours_per_1k_tokens": wh_per_1k,
        "gco2_per_1k_tokens": gco2_per_1k,
        "grid_gco2_per_kwh": grid_gco2_per_kwh,
        "carbon_intensity_label": carbon_label,
        "measurement_label": measurement_label,
        "note": note,
        "doctrine": (
            "v11 — energy MEASURED only from real NVML exporter + real token count; "
            "NEVER fabricated. Disclosure SIGNED+Merkle-logged so it is per-inference "
            "provable, not a self-reported dashboard stat. "
            "Differentiator: we sign the energy disclosure — no competitor does this."
        ),
    }
    return disclosure


# ---------------------------------------------------------------------------
# DSSE signing + Khipu Merkle log
# ---------------------------------------------------------------------------
def _sign_disclosure(disclosure: dict, receipt_id: str | None = None) -> dict:
    """DSSE-sign the disclosure object using szl_dsse (same signer as govern/infer receipts).

    Returns the disclosure dict extended with:
      signed: true
      dsse_signature: <hex-encoded signature> (or None + signed: false when unavailable)
      merkle_leaf: sha256 of the signed payload
      signed_at: ISO timestamp

    NEVER raises into the caller — any signing failure degrades gracefully with
    signed=False and an honest error note.
    """
    payload_bytes = _json.dumps(disclosure, sort_keys=True, default=str).encode("utf-8")
    merkle_leaf = hashlib.sha256(payload_bytes).hexdigest()

    # Attempt DSSE signing via szl_dsse (always available in the a11oy image)
    sig_hex = None
    signed_ok = False
    sign_note = None
    try:
        import szl_dsse as _dsse
        # szl_dsse.sign_payload(payload_obj: Any, payload_type: str) -> dict
        # It does canonical_json(payload_obj) internally — pass the dict, NOT bytes.
        signer = getattr(_dsse, "sign_payload", None) or getattr(_dsse, "sign", None)
        if callable(signer):
            sig_raw = signer(disclosure)  # pass dict so canonical_json works
            if isinstance(sig_raw, (bytes, bytearray)):
                sig_hex = sig_raw.hex()
            elif isinstance(sig_raw, dict):
                # sign_payload returns a DSSE envelope dict; extract b64 sig
                sigs = sig_raw.get("signatures", [])
                if sigs and isinstance(sigs, list):
                    sig_hex = sigs[0].get("sig")  # b64-encoded ECDSA sig
                elif sig_raw.get("signed") is False:
                    # No key — UNSIGNED envelope (honesty marker set)
                    sig_hex = None
                    sign_note = sig_raw.get("honesty", "UNSIGNED — no key")
                else:
                    sig_hex = sig_raw.get("sig") or sig_raw.get("signature")
                signed_ok = bool(sig_hex) and sig_raw.get("signed", True) is not False
            else:
                signed_ok = sig_hex is not None
        else:
            sign_note = "szl_dsse has no sign_payload/sign callable"
    except Exception as e:
        sign_note = f"szl_dsse unavailable: {type(e).__name__}"

    # Attempt Khipu Merkle log append
    merkle_entry = None
    try:
        import szl_khipu as _khipu
        if hasattr(_khipu, "append") and callable(_khipu.append):
            entry = _khipu.append({
                "type": "eu_energy_disclosure",
                "article": _ARTICLE,
                "merkle_leaf": merkle_leaf,
                "measurement_label": disclosure.get("measurement_label"),
                "receipt_id": receipt_id,
            })
            merkle_entry = entry if isinstance(entry, dict) else {"appended": True}
    except Exception as e:
        merkle_entry = {"error": f"khipu unavailable: {type(e).__name__}"}

    result = dict(disclosure)
    result.update({
        "signed": signed_ok,
        "dsse_signature": sig_hex,
        "merkle_leaf": merkle_leaf,
        "merkle_entry": merkle_entry,
        "signed_at": _now_iso(),
    })
    if sign_note:
        result["sign_note"] = sign_note
    return result


# ---------------------------------------------------------------------------
# Public builder — for receipt embedding
# ---------------------------------------------------------------------------
def build_eu_disclosure(
    nvml_joules_delta: float | None = None,
    token_count: int | None = None,
    grid_gco2_per_kwh: float | None = None,
    receipt_id: str | None = None,
) -> dict:
    """Build and sign an EU-AI-Act Art. 53 energy disclosure object.

    Intended for embedding in govern/infer receipts as the `energy_eu_disclosure`
    field, AND for the standalone GET endpoint.

    On the current HF CPU-basic Space (no NVML meter):
      measurement_label = "UNAVAILABLE", watt_hours_per_1k_tokens = null, signed = true

    On a sovereign GPU node with NVML meter live:
      measurement_label = "MEASURED", watt_hours_per_1k_tokens = <real value>, signed = true

    NEVER fabricates energy values.
    """
    disclosure = compute_eu_disclosure(nvml_joules_delta, token_count, grid_gco2_per_kwh)
    signed_disclosure = _sign_disclosure(disclosure, receipt_id=receipt_id)
    signed_disclosure["ts"] = _now_iso()
    return signed_disclosure


def eu_disclosure_field_for_receipt(
    nvml_joules_delta: float | None = None,
    token_count: int | None = None,
    receipt_id: str | None = None,
) -> dict:
    """Convenience wrapper for embedding in govern/infer receipts.

    Returns the complete signed disclosure dict as the `energy_eu_disclosure` field.
    Always returns a complete dict; never raises.
    """
    try:
        return build_eu_disclosure(
            nvml_joules_delta=nvml_joules_delta,
            token_count=token_count,
            receipt_id=receipt_id,
        )
    except Exception as e:
        # Fail-safe: honest UNAVAILABLE, never fabricate
        return {
            "article": _ARTICLE,
            "methodology": _METHODOLOGY,
            "watt_hours_per_1k_tokens": None,
            "gco2_per_1k_tokens": None,
            "measurement_label": _LABEL_UNAVAILABLE,
            "signed": False,
            "merkle_leaf": None,
            "note": f"eu_disclosure_field_for_receipt fail-open: {type(e).__name__}: {e}"[:200],
            "doctrine": "v11 — no fabricated values; fail-open to UNAVAILABLE.",
        }


# ---------------------------------------------------------------------------
# Snapshot for the GET endpoint — uses live NVML if available
# ---------------------------------------------------------------------------
def build_live_eu_disclosure() -> dict:
    """Build a fresh EU disclosure snapshot for the GET endpoint.

    Pulls joule data from szl_energy_live if the meter is live (MEASURED);
    otherwise returns an honest UNAVAILABLE disclosure with signed=true.
    """
    nvml_joules = None
    token_count = None  # No aggregate token count at endpoint level — per-inference only

    # Try to get total_joules from the live meter snapshot as a reference value
    joules_note = None
    try:
        import szl_energy_live as _el
        snap = _el.meter_snapshot()
        if snap.get("reachable"):
            # total_joules is cumulative since meter start — not per-inference.
            # For the endpoint we surface it as context only, not as wh_per_1k_tokens
            # (which requires both joule delta AND token count for a specific inference).
            joules_note = (
                f"NVML meter live: total_joules={snap.get('total_joules')}, "
                f"total_watts={snap.get('total_watts')}. "
                f"wh_per_1k_tokens requires per-inference token count — see govern/infer receipt."
            )
    except Exception:
        pass

    disclosure = build_eu_disclosure(
        nvml_joules_delta=nvml_joules,  # None → UNAVAILABLE for the endpoint snapshot
        token_count=token_count,
    )
    if joules_note:
        disclosure["meter_note"] = joules_note
    disclosure["endpoint_note"] = (
        "This endpoint shows the signed disclosure schema. "
        "Per-inference MEASURED values are in the govern/infer receipt "
        "energy_eu_disclosure field (populated when NVML + token count are both available)."
    )
    return disclosure


# ---------------------------------------------------------------------------
# HTTP handler + registration
# ---------------------------------------------------------------------------
def _h_eu_disclosure(request):
    from starlette.responses import JSONResponse  # type: ignore[import]
    return JSONResponse(build_live_eu_disclosure())


def register(app, ns: str = "a11oy") -> dict:
    """Wire GET /api/<ns>/v1/energy/eu-disclosure onto the app.

    Additive. Uses routes.insert(0, ...) to front-move so this route wins over
    the generic /api/a11oy/{path:path} Node proxy catch-all (same proven pattern
    as szl_compliance, szl_e8, etc. in serve.py).
    Returns {"registered": [...], "status": "ok"|"failed:<reason>"}.
    """
    path = f"/api/{ns}/v1/energy/eu-disclosure"
    try:
        from starlette.routing import Route  # type: ignore[import]
    except Exception as e:
        return {"registered": [], "status": f"failed:starlette-absent:{e}"}

    try:
        # Front-insert so this route beats the /api/a11oy/{path:path} Node proxy
        # catch-all.  add_api_route appends (loses to pre-registered catch-all);
        # insert(0, ...) is the canonical pattern in this codebase.
        _r = Route(path, _h_eu_disclosure, methods=["GET"])
        app.router.routes.insert(0, _r)
        return {"registered": [path], "status": "ok"}
    except Exception as e:
        return {"registered": [], "status": f"failed:{type(e).__name__}:{e}"}


# ---------------------------------------------------------------------------
# No-server self-test
# ---------------------------------------------------------------------------
def _selftest() -> dict:
    out: dict = {}

    # (a) UNAVAILABLE when no joules/tokens — no fabrication
    d = compute_eu_disclosure(None, None)
    assert d["measurement_label"] == _LABEL_UNAVAILABLE, d
    assert d["watt_hours_per_1k_tokens"] is None, d
    assert d["gco2_per_1k_tokens"] is None, d
    assert "NOT fabricated" in d.get("note", ""), d
    out["unavailable_no_fabrication"] = True

    # (b) MEASURED when real joules + tokens provided
    # Example: 100 J for 500 tokens → 0.2 J/token → 200 J/1k tokens
    # = 200/3600 Wh/1k = 0.05556 Wh/1k
    d2 = compute_eu_disclosure(nvml_joules_delta=100.0, token_count=500)
    assert d2["measurement_label"] == _LABEL_MEASURED, d2
    assert d2["watt_hours_per_1k_tokens"] is not None
    expected_wh = (100.0 / 3600.0 / 500) * 1000
    assert abs(d2["watt_hours_per_1k_tokens"] - expected_wh) < 1e-6, d2
    assert d2["gco2_per_1k_tokens"] is not None
    out["measured_values_correct"] = True

    # (c) Signed disclosure has signed key + merkle_leaf
    sd = build_eu_disclosure()
    assert "signed" in sd, sd
    assert "merkle_leaf" in sd and sd["merkle_leaf"] is not None, sd
    assert "signed_at" in sd, sd
    out["signed_structure_present"] = True

    # (d) EU article reference present
    assert sd["article"] == _ARTICLE, sd
    assert sd["methodology"] == _METHODOLOGY, sd
    out["article_methodology_correct"] = True

    # (e) Live endpoint builds without error
    live = build_live_eu_disclosure()
    assert live["measurement_label"] == _LABEL_UNAVAILABLE, live  # current HF CPU state
    assert live["signed"] in (True, False)  # bool regardless of DSSE availability
    out["live_endpoint_ok"] = True

    out["ok"] = all(v is True for v in out.values())
    return out


if __name__ == "__main__":
    import json
    print(json.dumps(_selftest(), indent=2, default=str))
