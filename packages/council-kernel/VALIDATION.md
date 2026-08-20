# Council kernel validation

Date: 2026-08-17
Branch: `feat/council-kernel-v0.6.0-20260817`

## Commands executed from a fresh public clone

```bash
python3 -m compileall -q \
  packages/council-kernel/src \
  packages/council-kernel/tests

PYTHONPATH=packages/council-kernel/src \
  python3 -m unittest discover \
  -s packages/council-kernel/tests \
  -v

git diff --check origin/main...HEAD -- \
  packages/council-kernel \
  .github/workflows/council-kernel.yml
```

## Result

- Python compilation: `PASS`
- Council contract tests: `18/18 PASS`
- Whitespace validation: `PASS`
- Runtime dependencies added: `0`
- Key or token material added: `0`
- Runtime route or effect path added: `0`

The tests cover capability denial, exact targets, budgets, risk classes, required roles, blinded commitment/reveal, Sentinel and Verifier vetoes, Authority denial, correlation discounting, minority retention, append-only ledger verification, tamper detection, and honest signature state.

## Remaining promotion authority

Hosted exact-head checks, independent review, protected squash merge, and any later runtime integration remain separate gates. No deployment or production-autonomy claim follows from this local qualification.
