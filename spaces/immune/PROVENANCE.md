# `spaces/immune` provenance

## Source recovery

The first GitHub import contained only the exact deployed artifacts under `dist/`. Its
README incorrectly said the full build source was present. That inconsistency is resolved
in v0.1.

The later inbound estate snapshot named
`immune-649e7bb87063f3a83dfa978e77c1359e4728ddd8` contained the missing TypeScript/Vite
implementation: canonicalization, admission checks, HUKLLA registry, receipt signing,
ledger logic, agent routes, and React UI. That snapshot depended on a separate workspace
monorepo and could not rebuild inside this standalone repository.

The canonical v0.1 source under `src/` is a dependency-free reconciliation of those
recovered semantics for the standalone Space. It adds the controls required by the current
doctrine:

- public state is bounded to an opaque session rather than process-global mutation;
- deterministic checks precede model classification;
- an immutable-pinned adapter contract remains unavailable without real local artifacts;
- tool authorization requires classifier qualification and a DSSE/Ed25519 receipt;
- receipt payloads contain input/action hashes, never raw inspected content;
- missing tripwire signals are `NOT_IMPLEMENTED` / `NOT_EVALUATED`;
- OpenAPI is the source for a generated route/enum contract;
- the browser flow exposes Inspector → Innate → Adaptive → Receipt evidence.

## Legacy artifacts

`dist/` is retained unchanged as historical deployment evidence. The v0.1 Dockerfile does
not execute or copy that opaque bundle. It runs `src/server/immune-server.mjs` directly.
The seed ledgers in `dist/data/immune` are also historical artifacts; v0.1 writes a separate
runtime chain at `data/immune/v1-receipts.jsonl`.

## Honest limitations

- No classifier weights, immutable model revision, tokenizer hash, runtime receipt, or
  qualification receipt are committed. Adaptive classification is therefore
  `UNAVAILABLE` by design.
- No signing key is committed. Signed receipts are `UNAVAILABLE` until an approved runtime
  secret is present.
- T09 trusted-clock-skew detection is not implemented because this standalone service has
  no independently trusted clock source.
- Passing unit/integration tests establishes implementation behavior only; it is not an
  independent security certification or model-quality measurement.

The original deployed Space was imported from
`https://huggingface.co/spaces/SZLHOLDINGS/immune` on 2026-06-30. v0.1 does not claim that
the remote Space has been updated until a separate deployment receipt exists.
