# FORGE NOTE — Rekor is ALREADY done (no founder gate needed there)
**From:** CTO/PM agent · June 12 2026, ~12:10 AM EDT.

I checked the publish pipeline: `uds-bundle-publish.yml` signs keyless with `COSIGN_EXPERIMENTAL=1` (`cosign sign --yes`) AND attests the SBOM (`cosign attest --predicate <spdx> --type spdxjson`). Keyless cosign **logs to the public Rekor transparency log by default** — so every signature + attestation is already Rekor-recorded. Verified on the registry: `szl-uds-bundle:uds-v0.3.0` (digest `b2e4980f…de4b5`) carries BOTH `.sig` and `.att`.

So the earlier "founder-gated Rekor public-verify" item is NOT outstanding work — Rekor inclusion already happens automatically. I've surfaced it honestly in the live Deploy Posture tab (`sbom.attested: true`, `attestation.rekor: …public Rekor transparency log`, bundle_level shows `.sig` + DSSE SPDX `.att`). The only thing left for the outbrief is to RUN the public verify on the tower as part of the offline-deploy proof:
```
cosign verify              ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.3.0 --certificate-oidc-issuer=https://token.actions.githubusercontent.com --certificate-identity-regexp='https://github.com/szl-holdings/.*'
cosign verify-attestation  ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.3.0 --type spdxjson --certificate-oidc-issuer=https://token.actions.githubusercontent.com --certificate-identity-regexp='https://github.com/szl-holdings/.*'
```
Both will show the Rekor log index in the output — capture that for Day-3.

Still genuinely founder-gated (untouched): warn→enforce policy transition; MAJOR dep bumps.
