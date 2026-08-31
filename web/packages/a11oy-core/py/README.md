# Lambda-AttnRes and Governed Delta Workspace

Status: **MODELED**

This Python package is a research organ inside `@a11oy/core`. It adds:

- a NumPy delta-memory update and trust/risk-aware depth retrieval;
- a PyTorch depth aggregator with an exact lambda endpoint, an
  epsilon-pinned geometric path, and exact rational weight certificates;
- immutable proposal and workspace contracts;
- a fail-closed reference kernel with deterministic hash receipts;
- append-only JSONL replay for research evaluation; and
- a standalone FastAPI surface that is not mounted into the production
  `serve.py` application.

The package complements the canonical root `gdw_workspace.py` durability
surface. Its JSONL store is not a production replacement for the canonical
tenant-safe SQLite state, outbox, signing, or generation-fencing contracts.
The compatibility function is named `egyptian_project` after the Wave 26
payload, but its machine-checked output is precisely an exact rational simplex
projection. The implementation does not claim that each stored coefficient is
a minimal Egyptian decomposition.

Install and test:

```console
python -m pip install -r web/packages/a11oy-core/py/requirements.txt
python -m pytest web/packages/a11oy-core/py/szl_gdw/tests -q
```

## Honest limitations

> Governed Delta Workspace and Λ-AttnRes are **MODELED** orchestration and
> tensor-layer architectures inspired by Kimi K3, Kimi Linear, Attention
> Residuals, DeltaNet, and related work. They operate over explicit agent
> outputs, receipts, and stored representations. They do **not** reproduce
> Kimi K3’s weights, do **not** read proprietary model activations or J-space,
> and do **not** currently have loss or scaling-efficiency evidence beyond
> small-scale experiments. All numerical behavior and claims are subject to
> revision as empirical data accumulates.
