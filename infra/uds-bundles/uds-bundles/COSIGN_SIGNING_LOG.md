# COSIGN SIGNING LOG — UDS Productionization (SZL Crew)

**Agent:** UDS Productionization subagent (signing as Yachay)
**Date:** 2026-06-01
**Signing key:** `audit_2026-05-30_cursor_offline/.secret/cosign_signing_key.key`
(ECDSA P-256, ENCRYPTED SIGSTORE PRIVATE KEY, passphrase **empty**) — provisioned by the
Wire-D + DSSE agent. Public key `.secret/cosign_signing_key.pub`.

## Public key (P-256), per prior session record
```
-----BEGIN PUBLIC KEY-----
MFkwEwYHKoZIzj0CAQYIKoZIzj0DAQcDQgAE7mrYWDnz8TvT7o4/65XGqYxo9OoV
vaB/grNuz+kVP1Xsaw0RokBKG0xT/XlV5Fz90AOwtgqC2yMBP0blK455gQ==
-----END PUBLIC KEY-----
```

## Honest signing status THIS SESSION — UPDATED (memory recovered mid-session)

After the sandbox memory pressure eased, **cosign and zarf both became runnable**. I
produced REAL, signed, verified, inspectable Zarf packages for all 5 flagships. Because
the docker daemon would not stay up, these are **image-free PROOF builds** (identical
package structure minus the `images:` layer, which needs docker/GHCR). The production
image-bearing packages are produced by `build_sign_all.sh` on a host with docker up.

| Bundle | PROOF package (real, on disk in `artifacts/`) | sha256 | Signature | verify-blob |
|---|---|---|---|---|
| a11oy | zarf-package-a11oy-runtime-proof-amd64-0.3.1.tar.zst | 800c7586… | a11oy-proof.uds.sig | **Verified OK** |
| amaru | zarf-package-amaru-attestation-proof-amd64-0.3.1.tar.zst | 041e8ac7… | amaru-proof.uds.sig | **Verified OK** |
| sentra | zarf-package-sentra-gates-proof-amd64-0.3.1.tar.zst | 4109db4c… | sentra-proof.uds.sig | **Verified OK** |
| killinchu | zarf-package-killinchu-bundle-proof-amd64-0.3.1.tar.zst | 0e581c9f… | killinchu-proof.uds.sig | **Verified OK** |
| rosie | zarf-package-rosie-replay-proof-amd64-0.3.1.tar.zst | ed04612e… | rosie-proof.uds.sig | **Verified OK** |

**5 of 5 PROOF bundles are REALLY signed and verified this session** with the SZL org key
(offline `--tlog-upload=false`). Full proof capture (zarf version, ls, sha256, verify,
inspect, deploy dry-run) is in `artifacts/PROOF_CAPTURE.txt`, `artifacts/SHA256SUMS_PROOF.txt`,
and `artifacts/DEPLOY_DRYRUN.txt`. The **production image-bearing** packages (5/5) are NOT
yet signed because docker would not stay up to build images — those are produced + signed
by `build_sign_all.sh` on a healthy host (same key, same commands).

## Exact signing command (run by `build_sign_all.sh` step 4–5)
```bash
export COSIGN_PASSWORD=""
KEY=.secret/cosign_signing_key.key
PUB=.secret/cosign_signing_key.pub
for PKG in artifacts/zarf-package-*-0.3.1.tar.zst; do
  cosign sign-blob   --key "$KEY" --tlog-upload=false --yes "$PKG" > "artifacts/$(basename ${PKG%.tar.zst}).sig"
  cosign verify-blob --key "$PUB" --signature "artifacts/$(basename ${PKG%.tar.zst}).sig" \
         --insecure-ignore-tlog=true "$PKG"   # expect: Verified OK
done
```
Offline mode (`--tlog-upload=false`) is intentional: the airgap blocks Rekor at deploy
time. For a public transparency record, drop the flag on an internet-connected host.

## Image attestation (SBOM) — staged
`syft <image> -o spdx-json` → `cosign attest --predicate <sbom> --type spdxjson --key $KEY
--tlog-upload=false --yes <image@digest>` (after image push). Commented in build script
step 7 because it requires a registry-resolvable digest.

— Yachay, 2026-06-01. Signing roadmap: migrate to GitHub Actions keyless (Fulcio/Rekor) CI signing at v0.3.0. Target is honest SLSA L1 honest · L2 build-attested (Rekor) · L3+ roadmap provenance + Sigstore-signed packages; the organ L2 SLSA provenance attestations verify via `cosign verify-attestation`. L3 is NOT claimed (doctrine: L3 is banned). Production Zarf packages will be built and signed by CI at v0.3.0 release. v0.2.0 is a source-only release — build locally with: zarf package create bundles/szl-<flagship>/
