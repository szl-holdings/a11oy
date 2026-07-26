<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Governed release threat model

Status: **IMPLEMENTED NOT DEPLOYED** for the local policy boundary; **PREPARED IN A PR** for supply-chain and admission changes; **BLOCKED** for production enforcement.

## Protected assets

- Production identities, deployment authority, signing authority, and human approvals.
- Source commits, immutable image and model digests, SBOMs, provenance, receipts, and audit events.
- Agent prompts, tool arguments, retrieved documents, customer data, and secrets.
- The distinction between PROVED, MEASURED, MODELED, PLANNED, and RETIRED claims.

## Trust boundaries

An untrusted user or agent may propose an action. Schema validation, policy evaluation, human approval, receipt issuance, worker verification, build, independent provenance verification, admission, deployment, and telemetry are separate boundaries. The authorization service receives an injected private key; execution workers receive only its public key. Observability records evidence and grants no authority.

## Primary threats and controls

| Threat | Control | Current status |
| --- | --- | --- |
| Unknown or mutable action | Strict schema, immutable digest target, finite action set, default denial | IMPLEMENTED NOT DEPLOYED |
| Forged, replayed, expired, cross-principal, cross-environment, or cross-artifact receipt | ECDSA signature plus exact request, principal, environment, artifact, policy, expiry, and revocation checks | MEASURED in contract tests |
| Worker mints its own authorization | Public-key-only worker verifier | IMPLEMENTED NOT DEPLOYED |
| Rejected action reaches execution | Append-only lifecycle rejects `REJECTED -> EXECUTING`; issuer refuses DENY | MEASURED in negative tests |
| Build signs a mutable tag | Reusable build signs and attests the immutable digest only | PREPARED IN A PR |
| Wrong source or altered artifact | GitHub attestation and independent expected-repository verification | MEASURED for existing GHCR digest |
| Unsigned image admission | Sigstore warning-mode policy manifest and negative fixture | PREPARED IN A PR; cluster test BLOCKED |
| Fork pull request obtains publish authority | Verification workflow has no publish credentials; reusable build is release-only | PREPARED IN A PR |
| Prompt or tool content leaks through telemetry | Content capture off; recursive redaction before export | MEASURED in adversarial tests |
| Mandatory denial trace sampled away | Mandatory security and governance events force 100% sampling | MEASURED in unit tests |
| Stale Hugging Face runtime reports RUNNING | Compare source revision with runtime build identity | MEASURED: Killinchu mismatch detected |
| Redirect or shim conceals a missing surface | Formal route retirement or a real implementation, never an unlabeled redirect | BLOCKED in Killinchu pending repository decision |
| Workspace stubs create a false green build | Missing real package release boundary remains explicit | BLOCKED pending architecture authorization |

## Failure posture

Unknown fields, unsupported actions, mutable targets, expired inputs, missing approval, missing provenance, missing rollback, signature errors, identity drift, and unavailable mandatory evidence all fail closed. Production enforcement, traffic changes, public claim upgrades, destructive infrastructure, and live Hugging Face mutation require explicit authorization.

## Residual risks

The local ECDSA implementation has not been deployed with a managed key or workload identity. The Lean scope currently covers T1 and T2 only and has no independent English-statement review, so the public theorem count remains **0/12 PROVED**. The proposed reusable workflow is not protected until it is reviewed and merged. No staging cluster, GPU node, cloud inventory, backup restoration, or admission-controller evidence was available in this execution.
