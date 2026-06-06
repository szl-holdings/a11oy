# szl-python

The Python client for the SZL anatomy.

::: warning In development
`szl-python` is **in development** (target: Series-A milestone). The interface below is the
**planned** surface; it is documented now so integrators can design against it. The shapes are
real — they mirror the live per-flagship packages and the [Doctrine v11](/doctrine/v11-v12)
types — but the unified PyPI package is not yet published. Use the per-flagship paths in the
[Quickstart](/quickstart) today.
:::

## Install (planned)

```bash
pip install szl   # in development — not yet on PyPI
```

## Init (planned)

```python
from szl import Client

szl = Client(org="szl-holdings")  # honest local mode by default; no signing yet
```

## Examples (planned surface)

```python
# 1 · Evaluate the 13-axis Λ-gate (a11oy)
decision = szl.policy.evaluate(
    action="deploy-model",
    axes={"moralGrounding": 0.97, "measurabilityHonesty": 0.96},  # ...13 axes
)
print(decision.passed, decision.continuum_hash)

# 2 · Mint + verify a Khipu receipt (amaru / rosie)
receipt = szl.receipts.mint(payload={"decisionId": "d-001", "value": 1})
assert receipt.chain_verified            # hash chain verified
assert receipt.signature == "DSSE-PLACEHOLDER"  # honest: signing not yet wired

# 3 · Decode a Remote-ID broadcast (killinchu)
track = szl.killinchu.remote_id.decode(hex="0d01...")
print(track.operator_id, track.position)
```

## Interim path (live today)

- **Lean numbers / proofs:** clone [`lutar-lean`](https://github.com/szl-holdings/lutar-lean).
- **killinchu:** call the live Space API directly (see [killinchu API](/api/killinchu)).
- **Receipts / formulas:** the math tooling in the SZL cookbook recipes ships runnable Python.
