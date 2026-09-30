<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Series-A public GitHub inventory authentication

The Series-A collector has its own credential boundary:
`A11OY_GITHUB_PUBLIC_READ_TOKEN`. It no longer forwards the generic runtime
`GITHUB_TOKEN`, whose current deployment returned HTTP 401. Other runtime
consumers and all existing secrets are preserved.

With no dedicated credential, the collector explicitly uses `PUBLIC_ANONYMOUS`
and reports `authenticated: false`. This is the public repository inventory,
not private organization completeness. The public-scope privacy repair must be
published with this change: request public repositories and public PRs, filter
private rows, and retain the public scope in signed manifests and admission.

If higher API capacity is needed, bind a persistent read credential under the
dedicated name through the existing canonical Space configuration process.
Neither a workflow's short-lived `github.token` nor a personal CLI credential
should be copied into the running service. A rejected dedicated token remains
`UNAVAILABLE`; it is never retried anonymously. Rate limits, transport failures
and bounded pagination failures retain the existing fail-closed behavior.

The source repair changes the existing `services` control-plane collector, not
the publisher, signing authority, storage topology, mutation policy or DNS.
Release requires protected exact-head checks, the canonical `hf-sync.yml`
publisher, matching source/readiness, and a fresh live public inventory receipt.
