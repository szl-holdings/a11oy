# Public surface relock — 2026-08-28

This receipt intentionally creates one protected-main publication event after the current pull-request reconciliation cycle.

## Required source identity

The resulting protected `main` revision is the only source revision admitted for this relock. Existing repository-native publishers must bind their outputs and readbacks to that exact immutable revision; no branch SHA, merge preview, stale deployment, mutable alias, or inferred build is accepted.

## Required public surfaces

- `https://a-11-oy.com`
- `https://a11oy.net`
- `https://huggingface.co/spaces/SZLHOLDINGS/a11oy`

## Acceptance contract

1. GitHub required checks and DCO are terminal green on the exact PR head.
2. Promotion occurs only through the protected merge path.
3. The canonical Hugging Face writer publishes the exact protected-main revision and independently reads back the Hub repository and running Space identity.
4. Domain deployment jobs publish the same protected-main revision and independently read back public health, readiness, build/source identity, and critical navigation routes.
5. `a-11-oy.com` and `a11oy.net` must not disagree about the canonical source revision or truth labels.
6. Failed, stale, redirected-to-placeholder, unavailable, or unverifiable endpoints remain red; no deployment success is inferred from a workflow start or HTTP reachability alone.
7. Existing `SIMULATED`, `REPORTED`, `MODELED`, `CONJECTURE`, `UNAVAILABLE`, and other evidence labels remain intact unless separately measured and reviewed.

This receipt changes no application behavior, credential, workflow permission, domain setting, model weight, dataset, or provider authority. It exists to force an auditable protected publication cycle through the already-governed deployment paths.

Signed-off-by: Lutar, Stephen P. <stephenlutar2@gmail.com>
