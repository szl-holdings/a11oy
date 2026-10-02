<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->
# Proof HTML response integrity

The observed `a11oy.net/experiments/confirmation/` and `source-index.html`
responses each contain one additional 367-byte Cloudflare Web Analytics script.
Removing that exact insertion reconstructs every immutable source byte, but the
served responses still fail exact source parity. This controller belongs to the
supply-chain maintenance layer and changes no application route or model.

`scripts/proof_cloudflare_rum.py` audits by default. It resolves one active
`a11oy.net` zone and its account, enumerates bounded account RUM metadata, and
requires exactly one existing property matching that zone, domain, and the
SHA-256 of the public beacon identifier. The identifier itself is not committed
or logged. Provider identifiers and the public snippet are hashed in the saved
settings projection; undocumented fields are hashed, and the complete original provider object has a separate exact
canonical hash. Authentication uses only the existing `CLOUDFLARE_API_TOKEN`.

The manual `Proof HTML Cloudflare RUM admission` workflow runs the network-free
contracts first. Only dispatch on canonical protected `main` accesses the
`production` environment. Audit performs GETs only. Apply requires the settings
hash from a prior successful audit, admits the zone again and reads the property
immediately before writing. It preserves exclusive before-settings and admission
files with flush/fsync, then makes at most one PUT with the sole field `auto_install: false`.
No property is created, deleted, or renamed. No DNS, rule, token, other site, or
other zone is changed. There are no request retries or automatic rollback.

The mutation response and independent subsequent GET must equal the original
property with only `auto_install` changed. Any changed setting, denied request,
ambiguous target, incomplete pagination, oversized response or redirect fails
the run. A failed PUT transport can leave the mutation outcome unknown; preserve
the receipt and read back before taking another action. The mutation-outcome field
also distinguishes a rejected write from an observed success response whose final
state could not be verified. Compare-before-write is
not an atomic provider compare-and-swap: an external writer could act after the
last GET. Workflow concurrency and the separately coordinated sole writer reduce
that race, and exact readback detects a differing final object.

Audit artifacts are unsigned observations. A write attempt additionally produces
an unsigned DSSE-formatted mutation payload with a verifiable provider-event hash
chain, with no signature or independent
identity claim. Credentials, provider error text and raw API bodies are never
logged. The receipt preserves numeric provider status/error codes and body hashes.
To restore injection later, separately admit the then-current property and use
the preserved `rollback_single_field` value; this tool deliberately has no restore
or arbitrary-write option.

After settings readback, verify the served HTML against immutable Git source
without normalization, then verify the complete 27-file proof composition. The
settings receipt alone does not qualify delivery, the broader product, or any
scientific claim. The registered Foundation Confirmation gate remains FAILED.

The Cloudflare API requires Zone Zone Read for the zone, Account Settings Read
for account/RUM observation and Account Settings Write for the update. A token
existing in GitHub is not proof of those scopes. Preserve provider denials and
do not grant or rotate credentials from this controller.

Primary API and behavior references:

- [RUM automatic edge injection](https://developers.cloudflare.com/speed/observatory/rum-beacon/)
- [List Web Analytics sites](https://developers.cloudflare.com/api/resources/rum/subresources/site_info/methods/list/)
- [Get a Web Analytics site](https://developers.cloudflare.com/api/resources/rum/subresources/site_info/methods/get/)
- [Update a Web Analytics site](https://developers.cloudflare.com/api/resources/rum/subresources/site_info/methods/update/)
- [List zones](https://developers.cloudflare.com/api/resources/zones/methods/list/)
