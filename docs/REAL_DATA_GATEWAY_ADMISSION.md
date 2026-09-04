# Governed Real Data Gateway — admission contract

This branch is admissible only when the permanent source—not a bootstrap workflow—satisfies every condition below.

## Backend

- One Python adapter serves Sentra/Aegis, PURIQ Finance, Vessels, PRISM Counsel, Terra, and Lyte.
- Provider hosts and path prefixes are fixed in source.
- Requests are credential-free HTTPS `GET` operations with redirects denied.
- CVE, NOAA station, and Census state selectors are allowlisted and bounded.
- Response time, byte count, status, and SHA-256 digest are measured.
- Provider fields remain reported and source-attributed.
- A failed provider returns `UNAVAILABLE` with `data=null`; it never becomes an empty market, zero risk, or sample record.
- Cache hits preserve the original observation time and are labeled `CACHED`.

## Product experience

- `/static/3d/real-data-gateway.html` is usable at phone, tablet, desktop, wide, and high-zoom geometries.
- Controls are at least 44 pixels and 48 pixels for coarse pointers.
- Technical values wrap or scroll within their own bounded region.
- Reduced-motion, increased-contrast, forced-colors, safe-area, and keyboard-focus contracts are present.
- User, developer, and investor evidence is progressively disclosed rather than compressed into a desktop dashboard.

## Authority

- `external_writes=DISABLED`
- `effectors=[]`
- `production_authorization=false`
- `automatic_remediation=false`
- no arbitrary URL, credential, request body, provider mutation, or customer-system action

## Release proof

The exact protected head must pass focused parser, cache, egress, GET/HEAD, Python, JavaScript, repository, security, container, and doctrine gates. After protected merge, the canonical Hugging Face publisher must bind `/api/build-info` to the exact source revision. A separate read-only workflow must then verify the page, registry, and all six vertical evidence envelopes.
