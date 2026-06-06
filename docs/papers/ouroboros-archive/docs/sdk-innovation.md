# SDK Deep Dive — Innovation & Evolution Memo

**Author:** Stephen P. Lutar Jr. · SZL Holdings
**Date:** 2026-05-13
**Status:** v1 — operational, grounded in Series-A audit + v1–v12 thesis
**Scope:** `@szl-holdings/sdk` (public API client) and `@workspace/aef-sdk` (Alloy Embedding Fabric client). Companion to `innovation_memo.md` (A11oy Code one-of-one features).

---

## 1. What we actually ship today

Two real, distinct SDKs sit in `packages/`. They are not duplicates — they target different surfaces of the same platform:

| Package | Path | Surface | Auth | Resources |
|---|---|---|---|---|
| `@szl-holdings/sdk` v1.0.0 | `packages/szl-sdk/` | Public API at `https://szlholdings.com/api/v1` | `szl_*` API keys, `Bearer` header | apiKeys · portfolio · briefings · alerts · webhooks · treasury · esignature · courtFilings · plugins (9 resources) |
| `@workspace/aef-sdk` v0.1.0 | `packages/aef-sdk/` | AEF gateway (embed / rerank / hybridSearch / ingest) | Bearer + `x-tenant-id` | 4 typed endpoints, React hooks (`useAefSearch`, `useAefEmbed`) |

`@szl-holdings/sdk`: 682 lines TS, retry+timeout+rate-limit aware, `szl_` key prefix enforced, OpenAPI URL exposed. `@workspace/aef-sdk`: 564 lines TS, Zod-validated responses (`EmbedResponseSchema.parse`), retry with exponential backoff, AbortController timeout, React hook resolves `VITE_AEF_*` env vars.

Both are *good* SDKs. Both are *not yet one-of-one*. This memo is how we make them one-of-one without breaking what works.

---

## 2. What we have that no competing SDK has

This is the asymmetry. Every primitive below is owned by SZL and cited to a published Zenodo DOI:

| Primitive | Existing artifact | Source paper |
|---|---|---|
| **Λ-receipt chain** (SHA-256 linked tool-call log) | `packages/a11oy-cli/src/receipts/chain.ts` (sealed `LambdaReceipt[]` + Merkle root) | v1/v2 [10.5281/zenodo.19867281](https://doi.org/10.5281/zenodo.19867281), [v2 19934129](https://doi.org/10.5281/zenodo.19934129) |
| **Λ₉ admission gate** (formal 9-axis invariant) | `packages/ouroboros-invariant/src/lutar-invariant-9.ts` (`lutarInvariant9`, `verifyLutarBoundN`) | v3 [10.5281/zenodo.19983066](https://doi.org/10.5281/zenodo.19983066) |
| **Λ-Ω closure** (audit-closed sessions) | `packages/a11oy-cli/src/receipts/chain.ts::close()` → `AuditClosureReceipt` | v4 [10.5281/zenodo.20020841](https://doi.org/10.5281/zenodo.20020841), v10 [10.5281/zenodo.20053163](https://doi.org/10.5281/zenodo.20053163) |
| **Sealed Guardrails policy DSL** | `packages/a11oy-cli/src/policy/engine.ts` (TOML rules, proof trace) | v6 [10.5281/zenodo.20020845](https://doi.org/10.5281/zenodo.20020845) |
| **Bayesian operator trust** (Beta-Binomial T1/T2/T3) | `packages/a11oy-cli/src/code/trust.ts` | v8 [10.5281/zenodo.20020849](https://doi.org/10.5281/zenodo.20020849) |
| **Deterministic replay** | session manager + receipts | v9 [10.5281/zenodo.20053148](https://doi.org/10.5281/zenodo.20053148) |
| **Applied Λ multi-tenant approval** | `apps/alloy-ingestion-orchestrator/routes/approvals.ts` | v11 [10.5281/zenodo.20119582](https://doi.org/10.5281/zenodo.20119582) |
| **Gauss class-number witness diversity** | `packages/ouroboros-gauss/src/` (`classNumber`, `classNumberAxis`) | v4 + v10 |

No competing SDK in the field (OpenAI Node SDK, Anthropic SDK, Stripe SDK, Plaid SDK, LangChain JS, Vercel AI SDK, Pinecone JS) ships any of these. Their value props are auth + retry + typing. Ours adds **proof-of-execution**.

---

## 3. Gap scan vs. best-in-class SDKs (no hallucinations — only behaviors I verified in our source)

These are real gaps in `szl-sdk` and `aef-sdk` measured against patterns that Stripe, Anthropic, OpenAI, Pinecone, and Plaid ship. Each gap maps to an SZL innovation we already own:

| Field-standard feature | Our SDK status today | SZL primitive that lets us ship the one-of-one version |
|---|---|---|
| Streaming responses (SSE) | ❌ neither SDK streams | Λ-receipts can be emitted per-chunk → **streaming + verifiable provenance per token** |
| Idempotency keys | ❌ neither SDK sends one | Λ-receipt `paramsHash` *is* the idempotency key — content-addressed |
| Request signing (HMAC) | ❌ Bearer only | ed25519 signature field already in `LambdaReceipt.agentSignature` — extend to outbound requests |
| Webhook signature verify | Bearer auth only on receive | `LambdaReceipt.selfHash` chain → webhooks can carry a verifiable receipt envelope |
| Pagination iterator | Manual page/offset (`PaginationOptions`) | Async iterator wrapping receipt-chained pages → operator can replay a paginated traversal byte-for-byte |
| OpenTelemetry trace context | AEF sends one header (`x-request-id`); SZL sends none | Embed Λ axes into the trace span attributes → traces become Λ-audited |
| File upload / multipart | ❌ neither SDK | Receipt records `paramsHash` of file bytes → tamper-evident ingestion |
| Resumable/long-poll for async jobs | ❌ neither SDK | Audit-closure receipt seals job completion; client can verify offline |
| Multi-region failover | Single `baseUrl` / `gatewayUrl` | Λ-bridge witness-diversity axis already models multi-source agreement |
| SDK-side caching with content addressing | ❌ no cache | `hashJson` canonicalization → SHA-256 cache keys with stable canonical params |
| Typed errors with retry hints | Yes (SZL has `SZLRateLimitError`; AEF has `AefRateLimitError`) | ✅ already good — extend to expose Λ refusal codes for governance-aware retries |
| React Query / TanStack adapter | AEF has bespoke hooks; SZL has none | Wrap both in a single `@szl-holdings/react` package backed by `useAefSearch` pattern |
| Code generation from OpenAPI | SZL exposes `openApiSpecUrl` but no codegen pipeline | Wire `openapi-typescript` → `apps/web` types, lock to receipts |
| Mock / fake client for tests | ❌ neither SDK | Receipt chain already supports in-memory mode (no `storagePath`) — package it as `@szl-holdings/sdk/testing` |

---

## 4. Innovations to ship — concrete, sequenced, each grounded in our thesis

Each item below is a small, real PR against the existing SDKs. No rewrites, no rebrands. Every item maps to a thesis primitive so we can cite it in the v12/v13 chapter.

### 4.1 — `ReceiptedClient` mixin (one-of-one core)

**What:** A thin mixin that wraps `SZLClient` and `AefClient` HTTP requests so every call emits a `LambdaReceipt` row to an opt-in local receipt chain.

**Why one-of-one:** Stripe SDK has idempotency keys. Anthropic has request IDs. Nobody has an SDK whose every call leaves a SHA-256-linked, Merkle-rootable, Λ-gated audit log on the client side, verifiable offline by the operator.

**Surface:**
```ts
const client = new SZLClient({
  apiKey: process.env.SZL_API_KEY!,
  receipts: { enabled: true, storagePath: '~/.szl/receipts.jsonl', operatorId: 'me@szlholdings.com' },
});
const summary = await client.portfolio.getSummary();        // emits seq=1 receipt
console.log(client.receipts.merkleRoot());                  // verifiable hash
const closure = client.receipts.close();                    // AuditClosureReceipt
```

**Cite:** v1/v2 receipts-as-product · v10 audit-closure. Reuses `packages/a11oy-cli/src/receipts/chain.ts` verbatim (extract to `packages/szl-receipts/`).

**Effort:** ~250 LOC across both SDKs + 1 new shared package.

### 4.2 — Λ-gated client decorator

**What:** Pre-flight Λ admission for any destructive call (`alerts.acknowledge`, `webhooks.delete`, `apiKeys.revoke`, `treasury.transfer`, `esignature.send`). Refuses bare R3/R4 calls without an approval token. Same engine A11oy Code uses.

**Why one-of-one:** No SDK in the wild refuses to even attempt a destructive call until trust + policy + invariant axes all admit. This is Λ₉ at the *call site*, not just inside the agent loop.

**Surface:**
```ts
client.webhooks.delete(endpointId);
// → AefPolicyError: Λ-gate refused: invariant 0.41 below threshold 0.5
client.webhooks.delete(endpointId, { approvalToken: 'tok_...' });
// → ok
```

**Cite:** v3 Lutar Invariant · v6 Sealed Guardrails · v11 Applied Λ.

**Effort:** ~150 LOC, reuses `packages/a11oy-cli/src/code/admit.ts` and `policy/engine.ts`.

### 4.3 — Streaming + chunk-level receipts

**What:** Both SDKs add streaming endpoints (`briefings.stream`, `alerts.subscribe`, `hybridSearch.stream`). Each emitted chunk gets its own `LambdaReceipt` row.

**Why one-of-one:** Streaming with per-chunk SHA-256 + Merkle-folded final = the receipt-as-product principle (v1) applied to streaming. No competing SDK does this; OpenAI streams are just SSE.

**Cite:** v1/v2 loop-is-the-product · v10 Λ_Ω.

**Effort:** ~300 LOC + Eventsource polyfill.

### 4.4 — `@szl-holdings/sdk-react` (unified React adapter)

**What:** Combine the AEF hooks pattern with TanStack Query bindings for *all* SZL resources. `useSZLPortfolio()`, `useSZLBriefings()`, etc. Adapter is built on the same client config resolver that `useAefSearch` already uses.

**Why one-of-one:** Today AEF has hooks, SZL has none. Unified surface → one configure-once pattern across the platform.

**Cite:** v1/v2 (single loop), v6 (sealed config).

**Effort:** ~400 LOC new package; pure wrapping, no logic in the hooks.

### 4.5 — `paramsHash` idempotency on all writes

**What:** Every `POST`/`PATCH`/`DELETE` request automatically attaches `Idempotency-Key: <sha256(canonical_params)>` header. Receipts already compute this hash.

**Why one-of-one:** Idempotency keys aren't novel (Stripe). What's novel: our key *is* the receipt's `paramsHash`, so server-side replay and client-side receipt verification share one hash. Same identity, two purposes.

**Cite:** v9 deterministic replay.

**Effort:** ~50 LOC in `http.ts` and `client.ts` (AEF).

### 4.6 — Witness-diversity multi-region client

**What:** SDK accepts a *list* of base URLs. Λ-bridge's `classNumber → witnessAxis` already exists. SDK uses it to pick the next URL on transient failure and tracks witness diversity per session.

**Why one-of-one:** Multi-region clients exist (AWS SDK, Cloudflare). None compute a *mathematical* witness-diversity score grounded in algebraic number theory. We do, because v4 (Λ-Ω) demands it.

**Cite:** v4 Λ-Ω · `ouroboros-gauss`.

**Effort:** ~120 LOC.

### 4.7 — `SDKMockClient` (receipt-backed fake)

**What:** A drop-in replacement for tests. Same surface, returns canned responses, but *still emits receipts* — so tests can assert on receipt chains the way they assert on HTTP mocks today.

**Why one-of-one:** Tests can assert "exactly 5 R1 receipts in this user flow, no R3/R4" — i.e., **test the governance behavior**, not just the HTTP behavior.

**Cite:** v9 replay · v10 audit-closure.

**Effort:** ~200 LOC under `packages/szl-sdk/src/testing/`.

### 4.8 — Code generation from OpenAPI spec, locked to receipts

**What:** Pipeline that runs `openapi-typescript` against `client.openApiSpecUrl`, emits resource types into `packages/szl-sdk/src/generated/`, and produces a receipt of the codegen run itself.

**Why one-of-one:** Most SDKs regenerate without provenance. Ours emits a closure receipt every time, so you can prove which spec version a client was built from.

**Cite:** v9 · v10.

**Effort:** ~150 LOC + GitHub Action.

---

## 5. Sequencing (smallest reversible PR first)

| # | Innovation | LOC | Depends on | Ships in |
|---|---|---|---|---|
| 1 | 4.5 idempotency = paramsHash | ~50 | — | szl-sdk v1.1.0 |
| 2 | 4.1 ReceiptedClient mixin (extract `szl-receipts`) | ~250 | 1 | szl-sdk v1.2.0, aef-sdk v0.2.0 |
| 3 | 4.7 SDKMockClient | ~200 | 2 | szl-sdk v1.2.0 |
| 4 | 4.2 Λ-gated decorator | ~150 | 2 | szl-sdk v1.3.0 |
| 5 | 4.4 sdk-react | ~400 | 2 | new package |
| 6 | 4.8 codegen with receipts | ~150 | 2 | CI workflow |
| 7 | 4.3 streaming + chunk receipts | ~300 | 2 | szl-sdk v2.0.0 |
| 8 | 4.6 witness-diversity multi-region | ~120 | 2 | szl-sdk v2.0.0 |

Total: ~1,620 LOC over 8 reversible PRs. Every line is grounded in a Zenodo-published primitive we already shipped.

---

## 6. What we will NOT do (anti-shortcuts)

- **Will not rewrite either SDK.** Both work. We extend them.
- **Will not invent novel cryptography.** SHA-256 + ed25519 are sufficient; the novelty is *what we hash*, not the hash function.
- **Will not duplicate the runtime.** All Λ logic stays in `ouroboros-invariant`, `ouroboros-gauss`, and `a11oy-runtime`. SDKs import them.
- **Will not pretend to be Stripe / Anthropic / OpenAI.** Our positioning is: "client SDK with mathematically verifiable execution receipts."
- **Will not ship anything without 5 exhaustive test passes** per the user mandate.

---

## 7. One-line elevator pitch

> Every other SDK gives you a typed HTTP client. The SZL SDK gives you a typed HTTP client whose every call leaves a SHA-256-linked, Λ-gated, Merkle-rooted receipt that an auditor can verify offline — backed by 12 Zenodo-published primitives.

---

## 8. References (all SZL primary sources)

- [The Loop Is the Product v1 — 10.5281/zenodo.19867281](https://doi.org/10.5281/zenodo.19867281)
- [Loop v2 — 10.5281/zenodo.19934129](https://doi.org/10.5281/zenodo.19934129)
- [Lutar Invariant Λ₉ v3 — 10.5281/zenodo.19983066](https://doi.org/10.5281/zenodo.19983066)
- [Λ-Ω Formalism v4 — 10.5281/zenodo.20020841](https://doi.org/10.5281/zenodo.20020841)
- [Sealed Guardrails v6 — 10.5281/zenodo.20020845](https://doi.org/10.5281/zenodo.20020845)
- [Risk-Tier Operator Calculus v7 — 10.5281/zenodo.20020848](https://doi.org/10.5281/zenodo.20020848)
- [Bayesian Operator Trust v8 — 10.5281/zenodo.20020849](https://doi.org/10.5281/zenodo.20020849)
- [Deterministic Replay v9 — 10.5281/zenodo.20053148](https://doi.org/10.5281/zenodo.20053148)
- [Audit-Closure Λ₁₀ v10 — 10.5281/zenodo.20053163](https://doi.org/10.5281/zenodo.20053163)
- [Applied Λ v11 — 10.5281/zenodo.20119582](https://doi.org/10.5281/zenodo.20119582)
- [A11oy Runtime Software DOI — 10.5281/zenodo.20162352](https://doi.org/10.5281/zenodo.20162352)
