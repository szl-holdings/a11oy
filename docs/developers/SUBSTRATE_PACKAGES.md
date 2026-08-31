# Substrate Packages — Build Your Own Organ

The five flagships are not magic — they are thin services over a shared substrate that lives in the
**[szl-holdings/platform](https://github.com/szl-holdings/platform)** monorepo under `packages/`.
External builders can install these packages editable and compose their own governed "organ."

Doctrine v11 · Apache-2.0.

---

## The pattern

```bash
git clone https://github.com/szl-holdings/platform.git
cd platform

# install one package editable
pip install -e packages/<package-name>

# or install several
pip install -e packages/wire-d -e packages/puriq-os -e packages/formula-os
```

Each package ships a `pyproject.toml` with pinned dependencies, so you can pull just the substrate
you need without taking the whole monorepo runtime.

> **Honest status:** the canonical substrate set (12 packages) lands via **platform PR #279**
> (`feat/instill-12-substrate-packages`, 108 files). Until it merges to `main`, install from that
> branch. The `packages/` directory already contains 130+ supporting packages on `main`.

## Core substrate packages

| Package | What it gives you |
|---------|-------------------|
| **wire-d** | Wire D — W3C `traceparent` propagation across organs; the cross-mesh tracing contract. |
| **puriq-os** | PURIQ master-formula runtime — the agentic-action governance layer (master formula + 13-axis Yuyay gate). |
| **formula-os** | Formula evaluation engine — define, version, and evaluate PURIQ formulas with receipts. |
| **khipu** / **khipu-os** | Khipu Merkle DAG — build hash-linked, summation-checked, tamper-evident receipt chains. |
| **evidence-ledger** | DSSE-signed evidence ledger primitives (sign / verify / chain). |
| **doctrine-runtime** | Doctrine v11 number source-of-truth + guards (749/14/163). |
| **memory-core** / **memory-fabric** | Unay-style governed memory store + recall. |
| **decision-engine** | Deny-by-default policy decision primitives (the sentra pattern). |
| **observability-core** | OpenTelemetry export of governed spans onto the audit fiber. |
| **agents-sdk-bridge** | Bridge to compose agent loops on the substrate. |

> Browse the full list at [platform/packages](https://github.com/szl-holdings/platform/tree/main/packages).
> Package names on the feature branch may differ slightly from the table; the README in each
> package is the source of truth and includes **honesty notes** (e.g. Reed-Solomon ≠ holographic;
> event-sourcing ≠ time travel).

## Minimal "organ" recipe

```python
# my_organ.py
from evidence_ledger import sign, verify          # DSSE
from khipu import Chain                            # Merkle DAG
from decision_engine import deny_by_default        # the gate

chain = Chain()

def handle(action: dict) -> dict:
    verdict = deny_by_default(action)              # gate first
    if not verdict.allowed:
        return {"status": 403, "reasons": verdict.reasons}
    receipt = sign({"action": action, "verdict": "allow"})
    chain.append(receipt)                          # tamper-evident trail
    assert verify(receipt).ok
    return {"status": 200, "receipt": receipt}
```

That is the whole contract: **gate → sign → chain → verify.** Every flagship follows it.

> **Don't want to build an organ — just wrap your existing app?** Use the
> **[Agentic Mesh SDK](./SDK_DROP_IN.md)** instead. `npm i @szl/agentic-mesh` /
> `pip install szl-agentic-mesh` / `go get github.com/szl-holdings/sdk-go` drops the same
> **gate → sign → chain → verify** contract onto any Next.js / FastAPI / Express / Go / CLI app in
> three lines, with optional fully-offline (airgap) operation.

## Deploy airgapped

Package your organ as a **UDS Zarf bundle** (see [szl-holdings/uds-bundles](https://github.com/szl-holdings/uds-bundles))
to deploy into disconnected / IL-4 environments, cosign-verifiable offline.

*Signed Yachay `<yachay@szlholdings.dev>` · Co-Authored-By: Perplexity Computer Agent · Apache-2.0*
