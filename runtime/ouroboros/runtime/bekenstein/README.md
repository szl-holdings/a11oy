# ouroboros/bekenstein

**Operationalizes:** TH6 — Bekenstein Entropy Budget  
**Repo:** szl-holdings/ouroboros  
**Path:** packages/bekenstein

## What it does

Tracks Shannon entropy of input and output payloads at every gate transit, then asserts the total output information content does not exceed the **Bekenstein bound** (a physical upper limit on the information content of a bounded region of space).

The software analogy used here: a payload of `N` bytes has a Bekenstein bound of `N × 8` bits — the maximum entropy any byte-bounded payload can encode. The Shannon entropy of the actual output is always ≤ this bound, making the assertion a meaningful sanity check that guards against entropy inflation attacks.

### Ledger

Every call to `trackTransit` appends an `EntropyRecord` to an in-memory ledger. Use `getLedger()` or `budgetSummary()` to inspect cumulative budget usage.

## Exports

| Symbol | Purpose |
|--------|---------|
| `shannonEntropy(buf)` | Shannon entropy in bits per symbol |
| `stringEntropy(s)` | Entropy of a UTF-8 string |
| `bekensteinBound(n)` | Upper bound (bits) for n bytes |
| `trackTransit(hash, in, out)` | Record and assert entropy transit |
| `getLedger()` | All entropy records |
| `budgetSummary()` | Aggregate summary |

## Env vars

None.

## HTTP endpoints

None — library only. Integrate into `lambda-gate` middleware for automatic per-transit tracking.

## Install & test

```bash
pnpm install
pnpm test
```
