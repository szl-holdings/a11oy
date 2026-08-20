# Council CLI qualification

Date: 2026-08-17
Branch: `feat/council-kernel-v0.6.0-20260817`

A second fresh-clone qualification was executed after adding the file-driven CLI.

```bash
python3 -m compileall -q \
  packages/council-kernel/src \
  packages/council-kernel/tests

PYTHONPATH=packages/council-kernel/src \
  python3 -m unittest discover \
  -s packages/council-kernel/tests \
  -v

PYTHONPATH=packages/council-kernel/src \
  python3 -m a11oy_council --help

git diff --check origin/main...HEAD -- \
  packages/council-kernel \
  .github/workflows/council-kernel.yml
```

Results:

- Python compilation: `PASS`
- Council and CLI tests: `22/22 PASS`
- Module entry point: `PASS`
- Whitespace validation: `PASS`
- Runtime dependencies added: `0`
- External action or provider mutation: `0`

Hosted exact-head checks and protected promotion remain required.
