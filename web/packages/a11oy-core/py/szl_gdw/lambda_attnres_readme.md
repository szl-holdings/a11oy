<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Λ-AttnRes runtime note

`LambdaAttnRes` accepts a finite tensor shaped `(batch, tokens, sources,
dimension)`.

- `λ = 0` is the exact arithmetic attention-residual path.
- `λ = 1` is the exact sign-preserving geometric path with an epsilon floor.
- interior λ values blend both paths.
- optional Egyptian projection records exact rational rows that sum to one.
- the returned certificate is labeled `MODELED`; it is a reproducibility
  record, not a training or performance claim.

The module imports PyTorch only on the tensor path. The workspace, status,
persistence, and receipt routes remain importable without PyTorch and expose a
structured `UNAVAILABLE` tensor response if that dependency is absent.

See `docs/WAVE26_GDW_PAYLOAD.md` and `docs/WAVE26_GDW_EVIDENCE.md` for the API,
durability, and claim-upgrade contracts.
