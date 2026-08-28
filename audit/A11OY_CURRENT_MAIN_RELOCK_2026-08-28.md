# A11oy current-main Hugging Face relock — 2026-08-28

## Observed fail-closed state

The organization recovery verifier correctly found that protected source had advanced beyond the live canonical Space.

- protected repository: `szl-holdings/a11oy`
- protected branch: `main`
- protected source at observation: `4aec44e0d872b165654be66a8275b2484ea85f9f`
- live `/api/build-info` revision at observation: `bebbc9db959ebd2943eed51cb255d534b77ebea9`
- canonical Space: `SZLHOLDINGS/a11oy`
- canonical origin: `https://szlholdings-a11oy.hf.space`
- independent verifier: `szl-holdings/.github` run `33186739154`
- verifier artifact: `9692004610`
- verifier artifact SHA-256: `6c79da0e91d374f2c5420f31e81d11094a37a6af1624e1cd0a4ddc74d626bbcd`

The preceding repository-native publisher run `33186183254` was still completing its persistent signer, receipt storage, authenticated GDW transition, drain, and integrity proof for source `bebbc9db959ebd2943eed51cb255d534b77ebea9` when `main` advanced again.

## Required convergence

Merging this audit receipt through the protected path must create a new exact protected-main revision and trigger `.github/workflows/hf-sync.yml`, whose `push` trigger intentionally has no path filter. The resulting run must:

1. check out the exact protected merge revision;
2. publish only the Dockerfile-derived canonical file set;
3. bind `SZL_GIT_SHA` to that exact revision;
4. restart without changing the governed Space allocation;
5. prove persistent signing, receipt storage, and the isolated GDW successor configuration;
6. pass authenticated GDW transition, drain, and integrity checks;
7. publish and ingest the source-bound readiness verdict;
8. prove the live build revision, Hugging Face repository revision, served runtime revision, routes, and singleton topology all match the exact protected revision;
9. trigger strict post-deployment GitHub/Hugging Face parity.

## Truth boundary

This file records an observed deployment lag and a protected relock request. It is not deployment evidence. Completion requires the post-merge repository-native workflow and independent public readback to be terminal green for one exact revision.