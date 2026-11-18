<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Bounded restraint receipt canary

Implementation status: available for review. This change records no live run.
The governance tile requires an actual restraint decision signed and verified
in the current application process. A general signer self-test does not satisfy
that predicate. This manual operation exercises the existing protected route;
it changes no runtime implementation, deployment, credential or readiness gate.

An administrator may dispatch `restraint-receipt-canary.yml` on protected `main`,
providing that exact deployed source SHA and explicitly authorizing one receipt.
The workflow refuses rerun attempts and shares the canonical deployment queue.
It uses the existing `A11OY_CODE_ADMIN_KEY` repository secret, and independently
configured `A11OY_EXECUTION_HF_REVISION`, `A11OY_EXECUTION_BOOT_ID`, and
`A11OY_EXECUTION_AUTHORITY_PINS_JSON` variables. Stale or missing expected context
blocks before the POST. Never update a pin from this operation's responses.

The request is fixed: full restraint advice, in Python, for adding an API cache
while preserving validation and error handling. No arbitrary body, URL, model,
GPU, energy-start or key-selection option exists. The existing route authenticates
the operator and signs and verifies the deterministic decision.

The client reserves at most nine requests: eight GET reads and exactly one POST.
It follows no redirects, performs no retries, limits each response to 128 KiB,
and applies a 60-second aggregate deadline with a maximum five-second blocking
I/O interval. A deadline crossing is rejected even if a response later arrives.
The normal HTTPX client retains configured proxies and CA trust; the canary does
not install a transport that bypasses managed egress routing.
After an ambiguous POST failure the result says `UNKNOWN_NO_RETRY`; this does
not prove that the server canceled or did not finish the receipt. Inspect the
retained result and current readback before considering a new manual run.

Before and after the POST, the client checks the independently expected GitHub
source, HF repository/runtime revision, and process boot. It verifies the native
DSSE signature with the configured public runtime key, checks the fixed task
digest, and requires a new matching receipt digest and signer fingerprint from
`restraint/info`. It imports only the public-key-only acceptance verifier, never
the runtime private-key resolver. Successful artifacts retain
the verified DSSE fields and native wrapper digest, excluding arbitrary unsigned
server metadata. Failures retain fixed reason codes and request/effect accounting;
if a signature was already verified, that receipt is preserved explicitly as
unqualified even when later identity or observation checks fail.

The native receipt does not sign its source or boot identity. Those are separate
bracketing observations, explicitly labeled that way in the report. This canary
is not the independently approved five-case execution producer, a model benchmark,
a release qualification, an ownership proof, or evidence that every frontier
capability is ready. No caller acquires additional execution authority.

Offline verification: `python -m pytest -q tests/test_restraint_receipt_canary.py`.
The separate `restraint-receipt-canary-ci.yml` runs these offline adverse cases
on matching pull requests and main pushes. It receives no operator credentials
and never invokes the live canary entrypoint. The mutation workflow remains
manual-only and shares the canonical deployment concurrency group.
