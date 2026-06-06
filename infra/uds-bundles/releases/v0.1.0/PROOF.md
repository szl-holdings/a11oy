# SZL UDS v0.1.0 — Judge-Verifiable PROOF

**Bundle:** `zarf-package-szl-uds-amd64-0.1.0.tar.zst`
**Signing key:** ECDSA P-256, keyid `szlholdings-cosign`
**Public key fingerprint (sha256 of PEM):** `a4d73120c312d94bdd6cbdfa6f3d629cfff4b85e7addde5f9c3fd4c02341eb30`
**Doctrine:** v11 LOCKED — 749 declarations / 14 axioms / 163 tracked sorries
**Built:** 2026-06-01 by Yachay `<yachay@szlholdings.dev>`

This package is a consolidated SZL UDS governance bundle assembling the real
Istio mesh-policy and UDS Core admission manifests for all five flagships
(a11oy, amaru, sentra, killinchu, rosie). It is an **image-free proof build**:
the Kubernetes/Istio governance layer is real and inspectable; the container
images (`ghcr.io/szl-holdings/<flagship>:v0.1.0`) are layered in by the
image-bearing build on a docker-enabled host with the GHCR-write founder PAT
(see Founder UI Actions in the ledger). Honesty over speed — this is labeled a
proof build, not the full image-bearing package.

## What's inside (5 components, 25 real manifests)

| Component | Namespace | Manifests |
|---|---|---|
| a11oy-governance | a11oy | namespace, authorizationpolicy, networkpolicy, virtualservice, uds-package |
| amaru-governance | amaru | namespace, authorizationpolicy, networkpolicy, virtualservice, uds-package |
| sentra-governance | sentra | namespace, authorizationpolicy, networkpolicy, virtualservice, uds-package |
| killinchu-governance | killinchu | namespace, authorizationpolicy, networkpolicy, virtualservice, uds-package |
| rosie-governance | rosie | namespace, authorizationpolicy, networkpolicy, virtualservice, uds-package |

## 3-command judge-verifiable recipe

Download `zarf-package-szl-uds-amd64-0.1.0.tar.zst`, `szl-uds-v0.1.0.sig`,
`szl-uds-v0.1.0.sha256`, and `cosign.pub` from the release assets, then:

```bash
# 1. integrity — confirm the artifact hash
sha256sum -c szl-uds-v0.1.0.sha256
#   expect: zarf-package-szl-uds-amd64-0.1.0.tar.zst: OK

# 2. authenticity — verify the SZL org signature (offline, airgap-safe)
cosign verify-blob \
  --key cosign.pub \
  --insecure-ignore-tlog=true \
  --signature szl-uds-v0.1.0.sig \
  zarf-package-szl-uds-amd64-0.1.0.tar.zst
#   expect: Verified OK

# 3. contents — inspect the package definition and components
zarf package inspect definition zarf-package-szl-uds-amd64-0.1.0.tar.zst
```

Key pin (verify the public key is the published SZL org key):

```bash
sha256sum <(cat cosign.pub)            # or: shasum -a 256
# the PEM (whitespace-stripped) hashes to:
# a4d73120c312d94bdd6cbdfa6f3d629cfff4b85e7addde5f9c3fd4c02341eb30
```

The same public key is published at
<https://github.com/szl-holdings/.github/blob/main/cosign.pub> and is embedded
in every flagship's `szl_dsse.py` `/khipu/verify` endpoint.

## Recorded values (this build)

- **Package sha256:** `88b99afc581e8c03d13c1033306c08c1027e51189f4f6c9f87223091c1119218`
- **cosign verify-blob:** `Verified OK`
- **zarf:** v0.51.0 · **cosign:** v2.4.1
- Offline mode (`--tlog-upload=false` / `--insecure-ignore-tlog=true`) is
  intentional: the airgap blocks Rekor at deploy time. For a public
  transparency record, drop the flags on an internet-connected host.

— Yachay, SZL Holdings, 2026-06-01
