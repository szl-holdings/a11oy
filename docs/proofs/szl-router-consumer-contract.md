<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Governed router consumer proof packet — 2026-09-12

Base source: A11oy `a0f4f15fb4a324c8d24eb40f5d02d6bb02e8705c`.
Peer contract: szl-router `091346fd29b8fec4e0f1ce056a97b66933a6a8f2`.

Scope: add an explicit `effort: szl-router` transport to the existing governed
inference endpoint, after the existing real governance gates. Keep default
serving unchanged; do not set deployment variables or call public providers.
Add a services-layer adapter, Dockerfile copy, operator runbook, and CI for both
the fixture and immutable peer source.

Local validation used Python 3.11 and a fresh `.venv` containing only the same
four direct dependencies specified by the workflow: FastAPI 0.140.13, HTTPX
0.28.1, Pydantic 2.13.4, pytest 9.1.1. Both runs exited zero:

```text
python -m pytest -q tests/test_szl_router_client.py
32 passed

SZL_ROUTER_CONTRACT_CHECKOUT=<peer checkout>
python -m pytest -q tests/test_szl_router_client.py
32 passed
```

Cases include the actual A11oy governance allow/deny paths, request propagation,
classification restrictions, unchanged default provider selection, root gateway
authentication/routing/receipt implementation, digest/source tampering, missing
configuration, recursion, refusals with and without text, failed-provider status
propagation, secret-echo diagnostics, response cache policy, and duplicate JSON
keys. The HTTP consumer also executes gateway transport off the serving event
loop, and source admission rejects missing controlled files or changed source
guarantees. The consumer and governance-surface suites together passed 49 cases.
Provider HTTP responses are synthetic and isolated. The tests prove the
software contract; they do not prove live inference or an independent witness.

The dependency stack emits Starlette/HTTPX and AnyIO
deprecation warnings; these do not change the contract result. CI uses Python
3.12 and must pass on the submitted head before merge.

No UI changed, so screenshot evidence is not applicable. No secrets, deployment
configuration, source publication, paid inference, or provider runtime were
mutated. Gateway receipt claims remain `HASH_INTEGRITY_ONLY` and `UNSIGNED`.
Protected merge, canonical publication, exact deployment readback, model-weight
binding, and live end-to-end inference are separate outstanding proof layers.
