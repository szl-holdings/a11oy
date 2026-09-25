# /verify 9-step wire — acceptance lock

Product: a-11-oy.com/verify · proof: a11oy.net · never a11oy.com.

Kept: POST /api/a11oy/v1/verify/receipt.
Aggregator: weighted GM. AM is witness only. No fifth aggregator. No fake BFT. No zkML on Khipu-1.5B.

## Math lock (equal-weight n=4, POLICY_TAU=0.80)

| vector | axes | GM | AM | min | admit | dang |
|---|---|---|---|---|---|---|
| nominal | 0.95,0.92,0.88,0.90 | 0.9121 | 0.9125 | 0.8800 | true | false |
| provenance_drop | 0.95,0.04,0.88,0.90 | 0.4165 | 0.6925 | 0.0400 | false | false |
| liar @0.80 | 0.97,0.97,0.97,0.02 | 0.3676 | 0.7325 | 0.0200 | false | false |
| hidden_weak | 0.95,0.95,0.95,0.40 | 0.7653 | 0.8125 | 0.4000 | false | true |
| false_friend | 0.95,0.92,0.90,0.55 | 0.8110 | 0.8300 | 0.5500 | true | false |

liar is dang only at FRONTIER_DEFAULT_TAU=0.70.
G = exp(Σ log x_i / n). Admit iff G ≥ 0.80 ∧ min > 0. dang ≔ (AM ≥ τ) ∧ (GM < τ).

## Honest labels

- VERIFIED — crypto check ran and passed
- ADMITTED — GM gate allowed (software, never a green VERIFIED pill)
- MEASURED — NVML/RAPL counter only
- MISMATCH — check ran and failed
- BLOCKED — Λ treated as proven/theorem
- UNSIGNED-LOCAL — no signature
- UNAVAILABLE — check could not run (missing hash, missing meter, no bundle)
- CONJECTURE — Λ uniqueness stays open

PAE with no `_pae_sha256` is UNAVAILABLE and must not flip a crypto PASS to PARTIAL.
Energy `joules=0` + UNAVAILABLE is MISMATCH. TDP/CodeCarbon cannot be MEASURED.
Rekor/SCITT/C2PA/OTS/OMS/ZK stay UNAVAILABLE unless a bundle is present and checkable.
