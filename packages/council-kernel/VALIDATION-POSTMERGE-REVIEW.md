# Council post-merge review qualification

Date: 2026-08-20

- Protected successor base: `e484563ab3bce2e655f27876042821e991e8651f`
- Reviewed pull request: `#1339`
- Reviewed source head: `766d1c0091719c1a9c8e1a3c5789a7caa85cf2b8`
- Scope: `packages/council-kernel/**`

## Review contracts

The local current-main successor addresses the four post-merge review threads:

1. Action receipts reject a proposal digest that differs from the bound decision and reject `APPLIED` unless the decision is `ACT`.
2. Revocation registries replay structurally valid `capability.revoked` records from a reopened hash-chain ledger and fail closed on malformed or conflicting durable entries.
3. Outcome observations timestamped after the evaluation time remain `PENDING`, including at the learning-promotion boundary.
4. Duplicate reveal identities compile to an auditable `BLOCK` decision with zero usable diversity instead of raising during diversity measurement.
5. Rebound revoked grant identifiers, time-travel promotion dispositions, and contradictory signed `APPLIED` receipt payloads fail closed.

## Commands

```bash
python3 -m compileall -q \
  packages/council-kernel/src \
  packages/council-kernel/tests

PYTHONPATH=packages/council-kernel/src \
  python3 -m unittest discover \
  -s packages/council-kernel/tests \
  -v
```

## Local result

- Python compilation: `PASS`
- Complete Council package tests: `109/109 PASS`
- Added runtime dependencies: `0`
- Added runtime routes or provider effect paths: `0`

This is local source qualification only. It does not establish a pushed branch, hosted checks, independent review, protected promotion, deployment, managed signing authority, or production autonomy.
