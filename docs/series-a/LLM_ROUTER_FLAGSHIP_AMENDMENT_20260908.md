# Amendment — SZL LLM Router Returns to the Flagship Ring

**Effective:** 2026-09-08  
**Asset:** SZL LLM Router  
**GitHub source:** `szl-holdings/szl-router`  
**Hugging Face runtime:** `SZLHOLDINGS/llm-router-live`

This amendment supersedes the August 29, 2026 private/paused archive treatment
for **`llm-router-live` only**. The earlier consolidation ledger remains a
historical record and must not be rewritten to suggest the archive event never
occurred.

## Current authority chain

```text
GitHub: szl-holdings/szl-router@main
   ↓ exact-source publication
Hugging Face: SZLHOLDINGS/llm-router-live
   ↓ integrated product view
A11oy: https://a-11-oy.com/code
   ↓ proof and known bounds
A11oy Proof: https://a11oy.net
```

The standalone router repository owns the routing implementation and its public
Space context. A11oy owns the portfolio control plane, model registry, shared
policy context, and integrated `/code` operator experience. This is a deliberate
composition, not permission for two divergent canonical routers.

## Flagship product contract

The public router presents four logical model contracts:

- `szl-auto` — deterministic or policy-informed model selection;
- `szl-fast` — bounded low-latency route;
- `szl-large` — general high-capability route;
- `szl-coder` — code-oriented route.

Provider order remains sovereign-first when operator-owned infrastructure is
actually reachable. Unreachable or unconfigured providers are skipped or
reported honestly. They are never represented as active merely because the
router UI is available.

Each completed route carries provenance and a routing receipt. That receipt can
bind model, provider tier, attempts, request digest, cost basis, and routing
rationale. It does not prove that the answer is correct or authorize a
consequential action.

## Required current state

- `szl-router` is unarchived and classified as `FLAGSHIP`.
- `llm-router-live` is public and running.
- The Hugging Face organization card showcases the router as a flagship.
- The Space is published from one exact GitHub source revision.
- Provider credentials remain deployment secrets.
- A11oy continues to expose the integrated router experience at `/code`.
- Runtime labels are restricted to `LIVE`, `CONFIGURED_UNVERIFIED`,
  `OFFLINE_UNTIL_KEYED`, and `UNAVAILABLE` where appropriate.

## Doctrine boundary

A model proposes. Independent routing and policy logic constrain. A human binds
consequential action. A polished UI, successful HTTP response, Space runtime,
or cryptographic signature cannot create truth or authority by itself. Lambda
remains advisory; Lambda uniqueness remains Conjecture 1 — open.
