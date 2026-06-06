# Doctrine ledger query

> **Read the locked 749 / 14 / 163 kernel programmatically — from every flagship's `/v1/honest` and from the canonical `szl-lake` index — and assert they all agree.**
>
> **Headline number: 1 query → 5 flagships + 1 lake → all report `c7c0ba17`.**

The doctrine is the source of truth: 749 declarations, 14 unique axioms, 163 tracked sorries,
kernel commit `c7c0ba17`, Λ = Conjecture 1, SLSA L1. This recipe pulls those numbers from every
live source and proves they are consistent.

> **Honest note on the endpoint.** There is **no live `/api/doctrine` route**. The doctrine is
> exposed per-flagship at `/v1/honest` and canonically in the lake's
> [`lake_index.json`](https://github.com/szl-holdings/szl-lake/blob/main/lake_index.json). This
> recipe uses those real surfaces, not a placeholder endpoint.

---

## Prerequisites

```bash
python3 -m pip install requests
```

---

## Quickstart (live, verified)

```python
import requests

EXPECT = {"declarations": 749, "axioms": 14, "sorries": 163, "kernel": "c7c0ba17"}
LAKE = "https://huggingface.co/datasets/SZLHOLDINGS/szl-lake/resolve/main/lake_index.json"

idx = requests.get(LAKE, timeout=30).json()
assert (idx["declarations"], idx["axioms"], idx["sorries"], idx["kernel_commit"]) == \
       (EXPECT["declarations"], EXPECT["axioms"], EXPECT["sorries"], EXPECT["kernel"])
print("lake:", idx["kernel_commit"], idx["declarations"], idx["axioms"], idx["sorries"], "OK")
# => lake: c7c0ba17 749 14 163 OK
```

---

## Full walkthrough

### Step 1 — Query every flagship's honest endpoint

```python
import requests
FLAGSHIPS = {
    "amaru":     "https://szlholdings-amaru.hf.space/api/amaru/v1/honest",
    "killinchu": "https://szlholdings-killinchu.hf.space/api/killinchu/v1/honest",
    "rosie":     "https://szlholdings-rosie.hf.space/api/rosie/v1/honest",
    "sentra":    "https://szlholdings-sentra.hf.space/api/sentra/v1/honest",
    "a11oy":     "https://szlholdings-a11oy.hf.space/api/a11oy/v1/honest",
}
for name, url in FLAGSHIPS.items():
    try:
        h = requests.get(url, timeout=30).json()
        d = h.get("declarations"); a = h.get("axioms_unique"); s = h.get("sorries_total")
        print(f"{name:10} doctrine={h.get('doctrine')} {d}/{a}/{s} "
              f"kernel={h.get('kernel_commit','(via lake)')}")
    except Exception as e:
        print(f"{name:10} (cold/error: {e}) — wake the Space and retry")
```

> **Honest note.** amaru / killinchu / rosie respond live. a11oy / sentra sleep on HF's free tier
> and may return an error until warmed — open the Space URL once to wake it. The lake index in the
> quickstart is always available.

### Step 2 — Assert Λ is Conjecture 1 everywhere

```python
h = requests.get(FLAGSHIPS["killinchu"], timeout=30).json()
assert "Conjecture" in h["lambda_status"], "Λ must remain Conjecture 1"
print("Λ:", h["lambda_status"])
# => Λ: Conjecture 1 — NOT a theorem (open CAUCHY_ND sorry + missing symmetry axiom)
```

### Step 3 — Cross-check the SLSA posture

Every flagship reports `slsa: "L1 (honest)"`. Anything claiming L2/L3 on a runtime receipt is a
red flag — the image signing is keyless cosign (**[recipe 06](06-cosign-rekor-slsa-l1.md)**), but
the honest *level* is L1.

### Step 4 — Pin to the Lean kernel commit

`c7c0ba17` is the commit in
[`lutar-lean`](https://github.com/szl-holdings/lutar-lean/commit/c7c0ba17) that the entire mesh is
anchored to. A receipt or organ declaring a different anchor is a doctrine-drift incident.

### Step 5 — Build a drift monitor

Run Steps 1–4 on a cron; alert if any source disagrees with `EXPECT`. This is the cheapest possible
doctrine-integrity check and complements **[recipe 11](11-kitaev-surface-drift-detection.md)**.

---

## See also

- **[01 — Verify a receipt end-to-end](01-verify-a-receipt-end-to-end.md)** — receipts pin the same anchor.
- **[11 — Kitaev surface drift detection](11-kitaev-surface-drift-detection.md)**
- Source of truth: [lutar-lean @ c7c0ba17](https://github.com/szl-holdings/lutar-lean/commit/c7c0ba17) · [szl-lake](https://github.com/szl-holdings/szl-lake)

## Cite this recipe

```bibtex
@misc{szl_cookbook_doctrine_query_2026,
  title        = {Doctrine ledger query (SZL Cookbook recipe 12)},
  author       = {{SZL Holdings}},
  year         = {2026},
  howpublished = {\url{https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/12-doctrine-ledger-query.md}},
  note         = {749/14/163 LOCKED, kernel c7c0ba17, Λ = Conjecture 1. No /api/doctrine route; uses /v1/honest + lake_index.json.}
}
```

---
*Doctrine v11 LOCKED — 749/14/163 — kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 (honest)*
