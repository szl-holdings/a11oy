# Security policy

## Core invariants

1. Models never create or expand their own authority.
2. Child grants must be a strict subset of parent grants.
3. Every mutation is bound to an exact target, idempotency key, budget, and postcondition set.
4. Sentinel and Verifier vetoes cannot be overridden by majority support.
5. Signed dissent and counterevidence remain discoverable.
6. The presentation layer cannot write a verified state.
7. Private chain-of-thought, credentials, raw prompts, and unrestricted tool payloads are not protocol state.
8. Ambiguous external side effects are never automatically retried.
9. Local test keys and single-runtime workers never establish production independence.

## Supported local executor

The reference executor supports only atomic file operations inside an explicitly configured sandbox root. It rejects path traversal, symbolic links, targets outside the sandbox, unsupported tools, capability expansion, and idempotency conflicts.

## Reporting

Report security defects privately to the repository owner. Do not include live credentials, customer data, or exploit payloads in public issues.
