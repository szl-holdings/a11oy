# Yupaq: the governed computation plane

Yupaq is the computation organ beneath the SZL-Forge model family. It does not
ask a language model to impersonate a calculator, theorem prover, numerical
engine, policy authority, or signer. The model proposes a typed job; the current
bounded core validates its schema, invokes a named engine, preserves the engine's
honesty label, and binds a receipt. Independent invariant and policy approval are
target stages and are not yet wired into `run_job()`.

The runtime is `szl_yupaq_compute.py`. Its canonical manifest is
`model_release/szl-compute-plane.json`.

## Implemented bounded core; live verification pending

The bounded core exposes five API surfaces:

- `GET /api/a11oy/v1/compute/capabilities`
- `POST /api/a11oy/v1/compute/jobs`
- `GET /api/a11oy/v1/compute/jobs/{job_id}`
- `GET /api/a11oy/v1/compute/receipts/{job_id}`
- `POST /api/a11oy/v1/compute/receipts/verify`

Capabilities and offline receipt verification are public/read-only. Job submission,
job readback, and stored-receipt readback fail closed unless the caller presents the
bearer whose SHA-256 is held in `A11OY_COMPUTE_TOKEN_SHA256`. In-memory job identity
is owner-scoped. Durable replay protection remains a public-promotion gate.

The contract has nine allowlisted operations. It rejects unknown fields and
does not accept source code, expressions, paths, URLs, package names, shell
arguments, provider keys, or arbitrary function names. Each run records real
wall-clock duration, request/result hashes, an optional verified DSSE envelope,
a Lake append result, and zero proof/trust uplift by default. The general runtime
budget is measured after execution; only adapters with their own timeout enforce a
hard engine deadline. The API runs synchronous engines off the event loop, but this
is not a killable worker sandbox.

## Target Ouroboros computation loop

`ADMIT -> PLAN -> RETRIEVE -> COMPUTE -> CROSSCHECK -> PROVE OR LABEL OPEN ->
LAMBDA ADVISORY GATE -> POLICY APPROVAL -> SIGN -> APPEND -> OBSERVE -> LEARN`

This is the target release path, not a claim that every stage runs today. The
implemented bounded core covers authentication, schema validation, named-engine
execution, evidence labeling, receipt binding, and a best-effort Lake append.
An unavailable engine remains unavailable; a sample Quant result remains a sample;
a Python recomputation is not called a fresh Lean kernel proof.

## How the organs fit

| Organ | Role | Weight boundary |
|---|---|---|
| SZL-Forge | Proposes typed jobs and explains bounded results | Adapter behavior only |
| A11oy Operator | Selects tools and requests authorization | Proposal only |
| Khipu Brain | Retrieves evidence paths and contradictions | All 9,464 nodes usable for RAG/eval; zero raw nodes in gradients |
| Quant Engine | Fixed PCA/TDA/Kelly reference computation | CPU sample path today; no live/backtest claim |
| Numerical Lab | MATLAB/Octave fixed matrix operations | External isolated engines; no arbitrary code |
| Lean/mathlib | Kernel inventory and future queued proof jobs | Proof checking remains outside weights |
| Formula registry | Typed namespaces and status crosswalk | No same-ID proof transfer |
| Lambda | Advisory weighted geometric-mean gate | Uniqueness remains Conjecture 1 |
| Invariant/policy | Target fail-closed authorization stage; not yet in `run_job()` | Never delegated to the model |
| Immune/Sentinel | Adversarial evaluation and runtime defense | Never self-certifies model safety |
| SZL Lake | Durable receipt and evidence sink | Integrity after admission, not semantic truth by itself |
| OTel/VSP | Trace and measured latency correlation | Evidence only |
| Anatomy/Holographic | Dependency and receipt visualization | Interface, not a proof engine |

## Formula accounting

The current versioned evidence does not establish “200 proven formulas.” The
verified accounting is:

- 100 formulas extracted from the thesis source;
- 146 namespace-scoped crosswalk records;
- 148 holdout rows;
- 2 `KERNEL_ACCEPTED`, 28 `CONDITIONAL`, 115 `OPEN`, and 1 `REFUTED` record in
  the current admission reconciliation;
- 269 declarations in the pinned Lean inventory;
- zero formula rows admitted to model gradients.

These sets overlap. They must not be added together or treated as 494 distinct
proofs. Lambda is executable as an advisory calculation, while unconditional
Lambda uniqueness stays `CONJECTURE_1_OPEN`.

## Next vertical packs

The same plane can support six packs without creating six unrelated LLMs:

1. Proof Forge: Lean 4, mathlib, and Lake builds.
2. Numerical Lab: Octave, licensed MATLAB, JAX/PyTorch reference parity.
3. SciML/Digital Twin: ODE/PDE/control, PINN, CALPHAD, infrastructure and
   Anatomy simulation.
4. Quant & Risk: optimization, scenario analysis, portfolio/risk, and later
   QuantLib/CVXPY/OSQP adapters.
5. Uncertainty Lab: conformal prediction, calibration, Bayesian diagnostics,
   and counterfactual utility.
6. Verifiable Compute: OTel, DSSE, in-toto, Lake, and bounded RISC Zero/EZKL
   research only after useful CPU reference workloads exist.

The commercial differentiator is not “the model knows 200 formulas.” It is that
one governed system can tell a buyer exactly which engine computed a result,
which formula namespace it used, which proof status applies, which data and
code hashes were bound, what failed, and how to independently verify the
receipt.
