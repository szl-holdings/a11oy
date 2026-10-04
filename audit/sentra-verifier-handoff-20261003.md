<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Sentra receipt verifier handoff

## Plan

Base source: `szl-holdings/a11oy@ac43eac84f9601d28748f31efe56ae9e93a2d8d2`.
GitHub reports the base commit signature as valid. This is source evidence,
not a deployment, independent evaluation, or authorization receipt.

The generated Sentra shell exposes the verifier manifest but offers no action
to open the existing receipt workflow. Add a fixed link to the canonical
`https://szlholdings-a11oy.hf.space/verify` page and explain the browser,
explicit online-action, key-trust and verification-scope boundaries.

Files in scope:

- `scripts/hf_publish_vertical_flagships_v4_impl.py`: Sentra HTML only.
- `tests/test_hf_publish_vertical_flagships_v4.py`: rendered handoff boundary.
- `organs/sentra/README.md`: distinguish preserved historical module commands
  from the current owner-directed generated assurance surface.
- This proof packet.

Success requires an ordinary fixed navigation link with no envelope or receipt
query, form submission, event handler, verifier prefetch, admission, approval,
new API, signing, secret, provider write or second publisher. The immutable base
renderer and sibling domain templates remain unchanged. Reachability stays
distinct from receipt verification and the Sentra iris stays closed.

## Context and baseline

- Applicable root and nested Sentra `AGENTS.md` were read before editing. At the
  base revision their Git blobs are `6aba4302ec5a104677b02248eb6f28105f4b2413`
  and `244fb1c0f99b518e1c7ccea19f411f575407241a` respectively.
- Doctrine, honest-status, code-style, security, testing and provenance rules
  were read from the isolated exact-base checkout.
- File ownership was checked against all nine observed open A11oy PRs; no
  overlap with the implementation, renderer test or nested README was found.
  PR 2429 owns publisher workflows and transaction files; these are untouched.
- Existing renderer baseline command:
  `python -B -m pytest -p no:cacheprovider tests/test_hf_publish_vertical_flagships_v4.py -q --tb=short`
  returned exit 0: **25 passed**. An initial incomplete sparse checkout lacked
  the unchanged Finance `source.json` fixture and failed; materializing that
  required fixture resolved the local harness failure before any source edit.
- Public GET observations: Sentra provider revision
  `f16c6f3ba66722f9ce3442a4da2135f5d09b043d`, RUNNING on cpu-basic;
  `/api/build-info` and `/api/source` declare older A11oy source
  `606e21927a6b043dc7ed2cd4d46d17ec1acb465c`. `/readyz` covers local landing/panels
  hashes. `/api/live` reports REACHABLE and `receipt_verified:false` for the
  canonical verifier manifest. Historical `/api/sentra/v1/honest` and `/gates`
  return 404. These GETs produced no write receipt.
- Canonical `/verify` returned HTML 200 and names the existing
  `/api/a11oy/v1/verify/receipt` contract. No receipt or key was submitted.

## Verification and release evidence

- Added the focused rendered-link authority regression before the UI change:
  `python -B -m pytest -p no:cacheprovider tests/test_hf_publish_vertical_flagships_v4.py::test_sentra_verifier_handoff_is_fixed_navigation_with_explicit_trust_scope -q --tb=short`
  returned exit 1, one failure: the rendered shell had no verifier handoff link.
- After the UI/documentation change the full renderer command above returned
  exit 0: **26 passed**. It checks the fixed host/path, no receipt query or
  automatic submission, explicit trust/scope copy, closed iris, immutable
  base/runtime pins and sibling template isolation.
- `git diff --check` returned exit 0.
- Screenshot: UNAVAILABLE in this proof packet. The coordinator deferred an
  optional browser/profile write because local free capacity was volatile.
  No screenshot, backend interaction, receipt verification or provider
  publication is claimed from the renderer tests.
- CI, protected merge and publication are UNKNOWN until their separate exact
  source readbacks. Independent validation remains UNKNOWN.

The ordinary signed commit and pull request will bind these source changes.
Source, CI, protected merge, provider publication, runtime behavior and
independent validation remain separate. This change does not qualify a model
or establish production readiness. No vault, secret, provider, restart or
operator enrollment operation was attempted.
