<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Series-A manual credential prerequisites

The public inventory collector uses its dedicated credential boundary,
`A11OY_GITHUB_PUBLIC_READ_TOKEN`. Without that credential it reports
`PUBLIC_ANONYMOUS` and `authenticated: false`. Its inventory covers public
repositories and public PRs; it does not establish private organization
completeness. A rejected dedicated credential remains `UNAVAILABLE`, with no
anonymous retry. Rate limits, transport errors and incomplete pagination keep
the existing failure behavior.

An authorized owner must configure credentials for the exact canonical Space
`SZLHOLDINGS/a11oy` through the supported secure setup flow, with approval at
the time of transmission. Required destination secret names are
`A11OY_GITHUB_PUBLIC_READ_TOKEN`, `SZL_COSIGN_PRIVATE_PEM` and
`GDW_CREDENTIALS_JSON`. Do not put any of these names in public Space variables.
The publisher must not forward `DOCS_AUTOMATION_TEAM_READ_TOKEN`, workflow
`github.token`, a personal CLI credential or `GDW_OPERATOR_TOKEN` into Space
secrets. It must not derive a replacement registry or delete
`GDW_PRINCIPALS_JSON`. A legacy principal registry is an owner-resolution
blocker; existing credentials and principals must be preserved.

The configuration scripts' `--check-only` mode reads secret names and storage
metadata, never secret values. It checks the canonical bucket
`SZLHOLDINGS/szl-evidence` and the required read-write `/data` mount without
creating storage or changing volumes. Missing credentials, public-variable
collisions, a legacy principal registry, unavailable metadata and conflicting
volumes require setup. Reports contain fixed prerequisite names and bounded
status fields; they do not contain token values or registry contents.

Secret-name presence does not prove identity, authority, scope or that a
previously verified credential is the credential installed in the Space.
There is currently no supported consumer of independently verified installed
credential authority in these scripts. They therefore report
`state: SETUP_REQUIRED`, `credential_authority_state: UNKNOWN` and
`converged: false`, with a nonzero exit, even when all required names exist.
Ordinary configuration also stops before any variable or volume write.
A caller boolean, source SHA, JSON approval or receipt cannot turn this
metadata observation into credential authorization. The retained pure GitHub
reader verifier can validate an explicitly supplied credential with mocked or
separately authorized probes; it does not bind that credential to an installed
Space secret and is not called by automatic configuration.

Publication must remain blocked until the owner selects and separately
reviews a supported secure handoff and its authority validation. That decision
must preserve signing, storage, source/default-tip admission, security, parity
and actual runtime validation. The pre-deployment prerequisite gate must run
before resume, deployment, runtime configuration or restart. A quota failure
must be reported without pausing another Space or provisioning hardware.
Deployment evidence belongs in Actions artifacts and summaries; the publisher
must not edit, close, reopen or comment on issue #1043.

The canonical workflow checks exact current-main source ownership first, then
runs both configuration scripts in read-only `--check-only` mode. The bounded
prerequisite summary retains their failure state and always exits nonzero until
an independently reviewed installed-authority consumer exists. Missing,
malformed, duplicate-field or oversized reports cannot grant permission.
Resume requires successful source and prerequisite jobs. Deployment also waits
for successful resume and retains the adjacent default-branch-tip recheck.
Configuration, verdict publication, relock, Finance and explicitly requested
vertical publication remain downstream of the same prerequisite boundary.

Live restart and GDW proof entrypoints separately fail before credential reads
or provider initialization, including the standalone manual restart workflow.
Their underlying validation functions remain available for isolated mocked
review. Their HTTP destination/redirect behavior, nested provider error text,
uncertain drain retries and downstream effect scope are not admitted for live
use by this change. Future authority validation must not silently enable those
proof effects; they need their own source and effects review.

The owner decisions still required are the supported secure transmission flow,
preservation of the existing signing identity and principals, resolution of
legacy registry or storage conflicts, and independent binding of installed
credential identity/scope to that approved handoff. This source change performs
none of that configuration and does not create an approval flag or receipt-based
bypass. Releasing a source draft alone cannot satisfy these prerequisites.

These are source changes and mocked regression checks. They do not configure
live credentials, deploy a Space, prove hosted readiness or remove the release
hold. Final release also requires exact-head checks, matching shared source,
separate review of authenticated runtime proof effects and a fresh live public
inventory receipt.
