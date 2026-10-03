<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Canonical frontend source alignment - 2026-10-03 UTC

- Workcell: `PLATFORM-SOURCE-ALIGNMENT-20261003`.
- Actor: Codex, with one bounded implementation agent.
- Base: signed A11oy source `80ed40fb31f93233c9e21d294c46efb62e795419`.
- Objective: retain GitHub as source authority and make the canonical frontend
  build a verifiable artifact before any Hugging Face or domain admission.
- Plan: update the platform gitlink/verifier/test pin to signed platform main
  `f2f8df6f89056e9104587674ccec0855dd5b177a`; correct generator claims for this
  new pin; add bounded Python artifact staging and negative-control tests;
  retain the admitted output in the existing canonical-web CI job; document
  the missing runtime API binding and retain the established publisher.
- Success criteria: all active pin declarations agree; artifact staging rejects
  unsafe/missing/oversized inputs, excludes source maps, binds source revisions,
  and does not imply runtime API readiness; existing CI must build/typecheck
  the exact source before retaining an artifact. Source changes are reviewed
  through the normal protected pull-request path.
- Local boundary: a small sparse checkout avoids dependency installation and
  full builds during severe C: disk pressure. The baseline source verifier
  rejects the uninitialized local submodule. Hosted checks must supply actual
  clean-checkout build and typecheck evidence.

## Fresh public observations used for planning

GitHub `szl-holdings` and Hugging Face `SZLHOLDINGS` are the verified canonical
organizations. The public catalog is already served at
`https://holdings.a-11-oy.com/frontier/`; product and proof origins are
`https://a-11-oy.com` and `https://a11oy.net` respectively. Product runtime
build-info at the final source read-back declared the A11oy base revision above.
GitHub platform main at the declared pin had a successful check rollup.

The platform frontend requires `/api/graphql`, `/api/graphql/ws`, and an
Atelier request contract absent from the current Python runtime. The platform
API server is explicitly a stub; old GraphQL documentation does not establish
an implemented resolver. Existing Python public status APIs are a separate
read-only interface. Shipping a build artifact alone cannot satisfy those API
contracts or qualify the six demo buyer lanes as live business operations.

## Publication boundary

The existing A11oy `hf-sync.yml` remains the automatic Space writer. The
current Python image ships its tracked operator console; the canonical web
build is not silently substituted for it. This work introduces no alternate
publisher, signing on reads, DNS change, model job, visibility change, or
business effect. Protected merge, exact-source CI, provider byte binding,
runtime API checks, and both domain read-backs remain distinct evidence gates.

## Verification

The source pin, its verifier and boundary test agree on the platform revision
above. Python AST parsing, Node syntax checking and whitespace validation
passed. The focused stdlib artifact suite passed 25 cases with one Windows-only
symlink-privilege skip; the Linux CI runner must execute that negative control.
Admission restricts exported file types to static web assets, with nine
sensitive or executable filename variants rejected before staging.

The local source verifier correctly rejected the intentionally uninitialized
submodule in this capacity-limited sparse checkout. No local frontend build or
typecheck is claimed. The hosted canonical-web job must perform a real clean
build, typecheck, artifact admission and upload for this pull request's exact
source. The deployment and API binding states remain BLOCKED and UNAVAILABLE.

Historical generated report packages were retained as dated observations.
Their generator now requires new source-specific build evidence and explicitly
records the unresolved runtime API binding instead of carrying the former
pin's build claim forward.
