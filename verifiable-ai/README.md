# SZL Verifiable-AI — provenance-native honesty core

SZL's unfair advantage isn't a bigger model or a slicker chatbot — it's that our
AI is **architecturally forced to be honest about what it knows and doesn't.**
This package is the smallest reusable unit of that bet, extracted from a11oy's
Doctrine v11 so any agent, benchmark, or service can share it.

## The rule (Doctrine v11)

Every claim carries exactly one label:

| Label          | Meaning                                  | Must carry a value? | Must carry evidence? |
|----------------|------------------------------------------|:-------------------:|:--------------------:|
| `MEASURED`     | actually run and measured                | yes                 | yes                  |
| `MODELED`      | derived from a stated model              | yes                 | yes                  |
| `NOT-RUN`      | not executed                             | no (a number = fabrication) | — |
| `NOT-MEASURED` | executed but this quantity not measured  | no                  | — |
| `NOT-TESTED`   | out of scope for this suite              | no                  | — |

A `MEASURED` number with no provenance is an **overclaim**. A `NOT-RUN` arm that
carries a number is **fabrication**. Both are refused.

## Two primitives

- `Claim` — a single provenance-stamped assertion an agent can emit and
  self-check (`.violations()`, `.to_provenance()`).
- `honesty_gate(artifact)` — a CI-style gate that scans a whole results artifact
  and fails on any overclaim, including an `overall_label` that claims a wider
  MEASURED sweep than the arms actually support.

```python
from verifiable_ai import honesty_gate, Claim, Label

result = honesty_gate(json.load(open("benchmarks/pinn/results.json")))
assert result.ok, result.violations  # blocks the ship if it overclaims

c = Claim("burgers_rel_l2", Label.MEASURED, value=0.644, evidence={"seeds": 3})
assert c.ok
```

## Proven against our own output

The test suite runs the gate against the **real** a11oy PINN benchmark
(`results.json` / `results_gpu.json`) — the same 3-way SZL vs DeepXDE vs
NVIDIA Modulus artifact we ship — then mutates it into every overclaim shape
(measured-without-value, not-run-with-a-number, unknown label, inflated
`overall_label`) and asserts the gate catches each one.

```
python -m pytest verifiable-ai/tests -q
```

## Why this is the cornerstone

Every larger move in the "verifiable AI" plan — a provenance-native agent
platform, a public a11oy benchmark, and eventually SZL as the **auditor of AI
honesty** — reuses this core. Build the honesty primitive once; make everything
downstream inherit it.
