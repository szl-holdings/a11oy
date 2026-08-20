# Drone counter-UAS verdict

> **Decode a Remote-ID / MAVLink frame, fuse it with a haversine geofence and the 13-axis Λ-gate in `killinchu`, and get back a signed counter-UAS verdict with a Khipu receipt.**
>
> **Headline number: 13 trust axes → 1 ALLOW/DENY verdict, Λ floor 0.9.**

`killinchu` is the air-domain governance organ. It ingests real broadcast protocols
(Remote ID / ASTM F3411-22a, ADS-B Mode-S, MAVLink v1/v2), checks a geofence, scores 13 trust
axes, and emits a DSSE Khipu receipt. This recipe runs the full path against the **live** Space.

> **Honest scope — read this first.** Broadcast Remote-ID / ADS-B / MAVLink are **unauthenticated
> and spoofable**. Every decoded field is a *claim*, never ground truth. The verdict is
> **advisory**. killinchu's own `/v1/honest` states this, and so must any system you build on it.

---

## Prerequisites

```bash
# curl + jq only — the live killinchu Space needs no credentials.
```

---

## Quickstart (live, verified)

```bash
KIL=https://szlholdings-killinchu.hf.space/api/killinchu

# Evaluate a track against a geofence → ALLOW/DENY + Λ + signed receipt.
curl -s -X POST $KIL/v1/counter-uas/evaluate -H 'content-type: application/json' -d '{
  "track":    {"lat": 40.0, "lon": -74.0, "alt_m": 120},
  "geofence": {"center_lat": 40.0, "center_lon": -74.0, "radius_m": 500}
}' | jq '{decision, lambda, lambda_pass, breaches, khipu_root: .lambda_receipt.khipu_root}'
# => { "decision": "ALLOW", "lambda": 0.922181, "lambda_pass": true,
#      "breaches": [], "khipu_root": "8972f895b7c2…1440" }
```

A track *inside* the fence with passing Λ returns `ALLOW`; move it outside the radius and the
`breaches` array fills and the decision flips.

---

## Full walkthrough

### Step 1 — The 13-axis Λ-gate (yuyay_v3)

```bash
curl -s $KIL/v1/lambda | jq '{lambda, lambda_floor, pass, aggregate, axes: [.axes[].name]}'
# aggregate = "geometric mean (yuyay_v3 canonical, 13-axis)"; floor = 0.9
```

The 13 axes are: soundness, calibration, robustness, provenance, consent, reversibility,
transparency, fairness, containment, attestation, freshness, authority, auditability. Λ is their
geometric mean; the gate passes when Λ ≥ 0.9.

> Λ is **Conjecture 1**, not a theorem (open `CAUCHY_ND` sorry + missing symmetry axiom). The gate
> *computes* Λ; it does not *prove* Λ is the unique correct aggregator.

### Step 2 — Decode a Remote-ID frame (ASTM F3411)

```bash
# ASTM F3411 messages are 25 bytes (1 header + 24 body). A wrong length is rejected:
curl -s -X POST $KIL/v1/remote-id/decode -H 'content-type: application/json' \
  -d '{"hex":"0d00112233445566778899aabbccddee"}' | jq '{ok, error}'
# => { "ok": false, "error": "unexpected length 16 bytes — ASTM F3411 message is 25 bytes …" }
```

Provide a full 25-byte (50-hex-char) frame to get a decoded Basic-ID. The decoder is real
(`pyModeS` / `pymavlink` upstream); it does not mock.

### Step 3 — Fuse decode → geofence → Λ → verdict

```bash
curl -s -X POST $KIL/v1/counter-uas/evaluate -H 'content-type: application/json' -d '{
  "track":    {"lat": 40.0123, "lon": -74.0089, "alt_m": 90},
  "geofence": {"center_lat": 40.0, "center_lon": -74.0, "radius_m": 500}
}' | jq '{decision, breaches, reasons, lambda, signature, honesty}'
```

The haversine distance is computed against the fence center; a breach plus a sub-floor Λ yields a
`DENY` with populated `reasons`.

### Step 4 — Read (and store) the receipt

```bash
curl -s -X POST $KIL/v1/counter-uas/evaluate -H 'content-type: application/json' -d '{
  "track":{"lat":40,"lon":-74,"alt_m":120},"geofence":{"center_lat":40,"center_lon":-74,"radius_m":500}
}' | jq '.lambda_receipt'
# Note: signature.keyid = "PENDING", sig = "PLACEHOLDER — Sigstore CI signing not yet wired".
```

> **Honest note.** The live verdict's DSSE signature is a `PLACEHOLDER`; the Khipu DAG is
> in-memory and resets on Space restart. For a cryptographically valid receipt, verify a lake
> receipt (**[recipe 01](01-verify-a-receipt-end-to-end.md)**). The killinchu lake stream is
> `khipu/killinchu_receipts.ndjson`.

### Step 5 — Section 889 awareness

killinchu's honest disclosure lists five banned vendors (Huawei, ZTE, Hytera, Hikvision, Dahua)
per Section 889. If you build hardware ingest, screen telemetry source vendors accordingly.

---

## See also

- **[03 — Fine-tune a compliance regime](03-fine-tune-compliance-regime.md)** — tighten axis floors for your context.
- **[11 — Kitaev surface drift detection](11-kitaev-surface-drift-detection.md)** — detect sensor drift.
- **[01 — Verify a receipt end-to-end](01-verify-a-receipt-end-to-end.md)**
- Live: [killinchu](https://szlholdings-killinchu.hf.space) · Repo: [killinchu](https://github.com/szl-holdings/killinchu)

## Cite this recipe

```bibtex
@misc{szl_cookbook_counter_uas_2026,
  title        = {Drone counter-UAS verdict (SZL Cookbook recipe 04)},
  author       = {{SZL Holdings}},
  year         = {2026},
  howpublished = {\url{https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/04-drone-counter-uas-verdict.md}},
  note         = {Telemetry is unauthenticated claim, not ground truth. Λ = Conjecture 1.}
}
```

---
*Doctrine v11 LOCKED — 749/14/163 — kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 (honest)*
