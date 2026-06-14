#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
#
# VENDORED 2026-06-14 from energy_ops/source_artifacts/joule_billing.py (founder seed
# artifact) into the a11oy repo, preserving the honest billing core verbatim — only this
# provenance header was prepended. Doctrine v11: refuses non-MEASURED, re-hashable
# JouleCharge.v1 receipt, DRY-RUN when no STRIPE key, idempotency by receipt digest.
# Do NOT reinvent — this is the single source of the billing math; szl_energy_ledger.py
# imports build_receipt / JouleReading / charge_stripe / d_idem from here.
"""
joule_billing.py — SZL Energy: turn a MEASURED-joule reading into a signed
governance receipt and a metered Stripe charge.

Honest by construction (per szl_joules_truth / doctrine v11):
  - Refuses to bill unless joules_label == "MEASURED" with a fresh NVML sample.
  - Never fabricates a measured number; SAMPLE/ESTIMATE readings are rejected for billing.
  - Emits a verifiable receipt (re-hashable offline) before any money moves.
  - sovereign flag is carried through untouched; this path never sets sovereign=true.

Env:
  STRIPE_API_KEY      your Stripe secret (test or live)
  STRIPE_PRICE_PER_KWH_CENTS   integer cents per kWh of sovereign compute resold
Usage:
  python joule_billing.py --node betterwithage --joules 78369.586 \
      --label MEASURED --nvml-age-s 12 --grid-price-eur-mwh 62.08 --customer cus_123
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from dataclasses import dataclass, asdict
from datetime import datetime, timezone

JOULES_PER_KWH = 3_600_000.0
MAX_NVML_AGE_S = 30           # NVML sample must be fresher than this to count as MEASURED

def sha256_canon(obj: dict) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()

@dataclass
class JouleReading:
    node: str
    joules: float
    label: str               # MEASURED | SAMPLE | ESTIMATE
    nvml_age_s: float
    grid_price_eur_mwh: float
    ts: str

    def is_billable(self) -> tuple[bool, str]:
        if self.label != "MEASURED":
            return False, f"label={self.label} (only MEASURED is billable)"
        if self.nvml_age_s > MAX_NVML_AGE_S:
            return False, f"NVML sample stale ({self.nvml_age_s}s > {MAX_NVML_AGE_S}s)"
        if self.joules <= 0:
            return False, "joules <= 0"
        return True, "ok"

def build_receipt(r: JouleReading, price_per_kwh_cents: int) -> dict:
    kwh = r.joules / JOULES_PER_KWH
    amount_cents = round(kwh * price_per_kwh_cents)
    grid_paid_us = r.grid_price_eur_mwh < 0
    decision = {
        "receipt_type": "SZL.Energy.JouleCharge.v1",
        "node": r.node,
        "joules_measured": r.joules,
        "joules_label": r.label,
        "kwh": round(kwh, 9),
        "grid_price_eur_mwh": r.grid_price_eur_mwh,
        "grid_paid_us_to_compute": grid_paid_us,
        "price_per_kwh_cents": price_per_kwh_cents,
        "amount_cents": amount_cents,
        "currency": "usd",
        "honesty": {
            "sovereign": False,            # this path NEVER sets sovereign=true
            "lambda": "Conjecture 1",
            "free_energy": False,
            "revenue": "MEASURED" if amount_cents > 0 else "ZERO",
        },
        "ts": r.ts,
    }
    return {"decision": decision, "payload_digest": sha256_canon(decision)}

def charge_stripe(receipt: dict, customer: str, api_key: str) -> dict:
    """Create a metered charge. Falls back to DRY-RUN if stripe/key absent."""
    d = receipt["decision"]
    if d["amount_cents"] <= 0:
        return {"status": "skipped", "reason": "amount=0"}
    if not api_key:
        return {"status": "dry-run", "would_charge_cents": d["amount_cents"],
                "idempotency_key": d_idem(receipt)}
    try:
        import stripe
    except ImportError:
        return {"status": "dry-run", "reason": "stripe not installed",
                "would_charge_cents": d["amount_cents"]}
    stripe.api_key = api_key
    pi = stripe.PaymentIntent.create(
        amount=d["amount_cents"], currency=d["currency"], customer=customer,
        metadata={"node": d["node"], "joules": d["joules_measured"],
                  "receipt_digest": receipt["payload_digest"]},
        idempotency_key=d_idem(receipt),
    )
    return {"status": "charged", "payment_intent": pi.id, "amount_cents": d["amount_cents"]}

def d_idem(receipt: dict) -> str:
    # idempotency: same receipt digest never double-charges
    return "joule-" + receipt["payload_digest"].split(":")[1][:32]

def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--node", required=True)
    p.add_argument("--joules", type=float, required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--nvml-age-s", type=float, required=True)
    p.add_argument("--grid-price-eur-mwh", type=float, required=True)
    p.add_argument("--customer", default="cus_demo")
    p.add_argument("--price-per-kwh-cents", type=int,
                   default=int(os.getenv("STRIPE_PRICE_PER_KWH_CENTS", "45")))
    a = p.parse_args(argv)

    reading = JouleReading(a.node, a.joules, a.label, a.nvml_age_s,
                           a.grid_price_eur_mwh,
                           datetime.now(timezone.utc).isoformat())
    ok, why = reading.is_billable()
    receipt = build_receipt(reading, a.price_per_kwh_cents)
    out = {"reading": asdict(reading), "receipt": receipt, "billable": ok, "reason": why}
    if not ok:
        out["charge"] = {"status": "blocked", "reason": why}
        print(json.dumps(out, indent=2)); return 1
    out["charge"] = charge_stripe(receipt, a.customer,
                                  os.getenv("STRIPE_API_KEY", ""))
    print(json.dumps(out, indent=2)); return 0

if __name__ == "__main__":
    sys.exit(main())
