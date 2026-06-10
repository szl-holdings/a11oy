# Fine-tune a customer compliance regime

<!-- RETIRED-ORGANS-NOTICE -->
> **⚠️ Retired organs notice.** `amaru`, `sentra`, and `rosie` have been retired and consolidated into the **[a11oy](https://github.com/szl-holdings/a11oy)** flagship (Memory, Sentinel, and Operator verticals). Their standalone `szl-holdings/{amaru,sentra,rosie}` GitHub repositories and `szlholdings-{amaru,sentra,rosie}.hf.space` Hugging Face Spaces **no longer exist**; only the signed GHCR images persist, for supply-chain verification. Any amaru/sentra/rosie Space URLs, repo links, or endpoints referenced below are **historical and not live** — use a11oy instead.

> **Take the doctrine pretrain set, project new receipts through `sentra`'s σ-algebra of governance signals, and emit a customer-specific Λ-extension that runs as an overlay — without touching the locked kernel.**
>
> **Headline number: 1 customer regime, 0 changes to 749/14/163.**

A "compliance regime" in SZL is **not** a model fine-tune that mutates the kernel. The kernel
(`c7c0ba17`, 749/14/163) is LOCKED. Instead you define an **overlay**: a measurable function on
the receipt-bus σ-algebra that *tightens* gates for your context (e.g., EU AI Act high-risk,
NIST AI RMF, CMMC). This recipe builds and tests one.

> **Honest framing.** Λ is **Conjecture 1**, not a theorem. The overlay you build is an
> engineering policy on top of the gate; it inherits Λ's *measured* axis scores, not a proof of
> optimality. We say "extension," never "improvement to the proof."

---

## Prerequisites

```bash
python3 -m pip install requests
```
No kernel write access required (and none is possible — that is the design).

---

## Quickstart

```python
import requests

SENTRA = "https://szlholdings-sentra.hf.space/api/sentra"

# A customer regime = a set of axis floors + required gates, applied as an overlay.
regime = {
    "name": "acme-eu-ai-act-high-risk",
    "axis_floors": {"transparency": 0.95, "fairness": 0.95, "auditability": 0.95},
    "required_gates": ["dual-use", "STIX/TAXII", "receipt-hash"],
    "inherit": "doctrine-v11",         # never rewrites the kernel
}

# Project a candidate action through sentra; overlay decides PASS/FAIL on top of the base verdict.
action = {"kind": "model_output", "text": "…", "context": {"sector": "credit_scoring"}}
base = requests.post(f"{SENTRA}/v1/inspect", json={"action": action}, timeout=60).json()
print("base verdict:", base.get("verdict"))
```

The overlay never asks sentra to change a gate; it reads sentra's per-axis signals and applies
*stricter* floors locally.

---

## Full walkthrough

### Step 1 — The σ-algebra of governance signals

Every governed action produces a vector of 13 trust-axis scores (the `yuyay_v3` axes:
soundness, calibration, robustness, provenance, consent, reversibility, transparency, fairness,
containment, attestation, freshness, authority, auditability). These axes generate a σ-algebra
\(\Sigma\) over the receipt bus: events are measurable sets like "fairness < 0.9 ∧ sector =
credit." A *regime* is a measurable predicate on \(\Sigma\).

```python
AXES = ["soundness","calibration","robustness","provenance","consent","reversibility",
        "transparency","fairness","containment","attestation","freshness","authority","auditability"]
```

### Step 2 — Pull the doctrine pretrain set (axis priors)

The doctrine axis priors come from the locked kernel and the lake. Use the live Λ axis snapshot
as the canonical prior (this is exactly what the gate uses):

```python
import requests
axes = requests.get("https://szlholdings-killinchu.hf.space/api/killinchu/v1/lambda", timeout=60).json()
prior = {a["name"]: a["score"] for a in axes["axes"]}
print("Λ prior:", round(axes["lambda"], 6), "floor:", axes["lambda_floor"], "pass:", axes["pass"])
# => Λ prior: 0.922181 floor: 0.9 pass: True
```

### Step 3 — Define the Λ-extension (overlay)

```python
def lambda_extension(axis_scores: dict, regime: dict) -> dict:
    floors = {**{a: regime["inherit_floor"] for a in AXES}, **regime["axis_floors"]}
    failures = [a for a in AXES if axis_scores.get(a, 0.0) < floors[a]]
    # geometric mean (yuyay_v3 canonical aggregate) — same operator as the base gate
    import math
    geo = math.exp(sum(math.log(max(axis_scores.get(a, 1e-9), 1e-9)) for a in AXES) / len(AXES))
    return {"regime": regime["name"], "lambda_overlay": round(geo, 6),
            "pass": not failures, "failed_axes": failures, "inherits": "c7c0ba17"}

regime = {"name": "acme-eu-ai-act-high-risk", "inherit_floor": 0.90,
          "axis_floors": {"transparency": 0.95, "fairness": 0.95, "auditability": 0.95}}
print(lambda_extension(prior, regime))
# Fairness/transparency 0.90 < 0.95 → fails the tightened regime, as intended.
```

### Step 4 — Bind the regime to a receipt

Wrap the overlay decision as a Khipu receipt so it is itself auditable (verify it with
**[recipe 01](01-verify-a-receipt-end-to-end.md)**). Submit candidate receipts back through
sentra's `/v1/verdict` for the chained, signed base verdict; store the overlay decision alongside.

### Step 5 — Validate against your corpus

Replay your historical receipts through the overlay and report the confusion matrix vs. your
manual compliance labels. Pair this with **[recipe 09 — PAC-Bayes confidence margin](09-pac-bayes-confidence-margin.md)**
to put a tail bound on the regime's empirical risk.

---

## See also

- **[09 — PAC-Bayes confidence margin](09-pac-bayes-confidence-margin.md)** — bound the regime's risk.
- **[12 — Doctrine ledger query](12-doctrine-ledger-query.md)** — read the locked priors.
- **[01 — Verify a receipt end-to-end](01-verify-a-receipt-end-to-end.md)**
- Live: [sentra](https://szlholdings-sentra.hf.space) · [killinchu Λ axes](https://szlholdings-killinchu.hf.space/api/killinchu/v1/lambda)

## Cite this recipe

```bibtex
@misc{szl_cookbook_compliance_regime_2026,
  title        = {Fine-tune a customer compliance regime (SZL Cookbook recipe 03)},
  author       = {{SZL Holdings}},
  year         = {2026},
  howpublished = {\url{https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/03-fine-tune-compliance-regime.md}},
  note         = {Λ = Conjecture 1; overlay never mutates the locked kernel c7c0ba17.}
}
```

---
*Doctrine v11 LOCKED — 749/14/163 — kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 (honest)*
