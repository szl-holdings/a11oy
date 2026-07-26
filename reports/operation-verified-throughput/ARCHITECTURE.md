<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Architecture

Primary status: **IMPLEMENTED NOT DEPLOYED**

Generated: `2026-07-26T08:09:12.347408Z`

Status vocabulary: **DEPLOYED**, **IMPLEMENTED NOT DEPLOYED**, **PREPARED IN A PR**, **PROVED**, **MEASURED**, **MODELED**, **FAILED**, **BLOCKED**, **AWAITING AUTHORIZATION**, **DOWNGRADED**, and **RETIRED** are distinct and are not interchangeable.

```text
untrusted proposal
  -> strict schema
  -> finite policy evaluation
  -> human approval when high risk
  -> ECDSA receipt issuer (private key)
  -> append-only lifecycle
  -> execution worker (public key only)
  -> reusable build -> SBOM/scan/sign/attest
  -> independent verification
  -> admission -> staging -> observation
```

The authorization plane, execution plane, build plane, admission plane, and observability plane are separate. Telemetry can record a decision but cannot authorize it. Production identity is an exact tuple of source commit, artifact digest, model/tokenizer revisions when applicable, runtime, environment, and observation time.

The repository's operational Hugging Face surface is `pnpm payload:huggingface`; the diligence demo is `pnpm test:doctrine` in `web/packages/a11oy-core`. The canonical web application is the immutable `vendor/platform` gitlink at `6e0dc7b423fbcfb2c165348e60b41cd55a9b9ace`, using its declared `pnpm@10.26.1` toolchain and `@workspace/a11oy` artifact. A clean production build and typecheck are **MEASURED**. The partial root `web/` mirror is **RETIRED** as an application build target and remains only for doctrine, historical, and static sources.
