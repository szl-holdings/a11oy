# Hugging Face Space Frontend Census v1

## Objective

Audit every public `SZLHOLDINGS` Space as an application, not merely as a Hub card. The census converts current public runtime and browser evidence into a deterministic remediation list without assuming that reachability proves readiness.

## Public discovery

The census enumerates the public organization through the Hugging Face Spaces API and retains only canonical `SZLHOLDINGS/*` identities. Each observation records:

- Space identity and public URL
- SDK and app file when exposed
- short-description state and platform length boundary
- immutable repository revision
- immutable runtime revision
- runtime stage

Unresolved or unavailable values remain unavailable; the audit never reconstructs identities from aggregate counts.

## Browser matrix

Every `RUNNING` Space is rendered at:

- 360 × 800
- 390 × 844
- 768 × 1024
- 1024 × 900
- 1440 × 1000

The browser contract checks:

- HTTP reachability
- device-width viewport metadata
- at least one visible primary interaction target
- document-level horizontal overflow
- primary controls below 44 × 44 CSS pixels
- uncaught page errors
- title and release-marker observations

Console errors are retained as evidence but are not automatically hard failures because optional fonts, blocked analytics, and external browser policy can create non-contract noise. Uncaught page errors remain fail-closed.

## Metadata and runtime gates

A Space is blocked when applicable evidence shows:

- no immutable Hub repository SHA
- runtime SHA divergence
- runtime stage other than `RUNNING`
- missing SDK
- missing or overlong `short_description`
- missing `app_file` for Static, Gradio, or Streamlit surfaces
- a non-Static `SZLHOLDINGS/README` organization-card implementation

The audit does not change runtime allocation, secrets, storage, visibility, source branches, or any Hub repository.

## Evidence outputs

- `report.json` — complete machine-readable observation and failures
- `summary.csv` — one row per Space
- failure screenshots at 390 and 1440 pixels

The permanent workflow synchronizes one deterministic drift issue. The initial baseline is evidence-producing rather than an automatic deployment writer. Each remediation must land in the Space's canonical source repository and close only after immutable live readback.
