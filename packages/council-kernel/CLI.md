# Council CLI

Run the source package without installation:

```bash
PYTHONPATH=packages/council-kernel/src \
  python -m a11oy_council --help
```

## Create a commitment

```bash
PYTHONPATH=packages/council-kernel/src \
  python -m a11oy_council commit assessment.json
```

The input object contains `member`, `assessment`, and `nonce`. The output contains only the member identity and SHA-256 commitment. Assessment content is revealed later.

## Compile a decision

```bash
PYTHONPATH=packages/council-kernel/src \
  python -m a11oy_council evaluate council-input.json
```

The input object contains the proposal, committed reveals, capability grants, evaluation time, optional policy, and recorded grant spend. Output is one canonical decision record with `ACT`, `ESCALATE`, or `BLOCK`, its reasons, diversity report, member results, retained minority reports, and decision digest.

## Verify a ledger

```bash
PYTHONPATH=packages/council-kernel/src \
  python -m a11oy_council verify-ledger council.jsonl
```

Invalid documents and invalid ledgers fail closed with a JSON error on standard error and a non-zero exit status. These commands do not execute the proposed action, retrieve credentials, or grant ambient authority.
