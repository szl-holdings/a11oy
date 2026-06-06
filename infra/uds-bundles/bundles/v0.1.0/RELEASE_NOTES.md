# UDS v0.1.0 — 5 signed proof bundles

Five image-free **PROOF** UDS/Zarf bundles (Zarf `v0.51.0`, package version `0.3.1`),
cosign-signed with an ECDSA-P256 key. Built `Mon, 01 Jun 2026 09:19:19 +0000`.

**Doctrine v11 LOCKED:** 749 declarations · 14 unique axioms · 163 sorries.
**Concept DOI:** 10.5281/zenodo.19944926.

> Naming note: Quechua component names (Amaru, Rosie, Sentra, Killinchu, a11oy)
> are brand naming, not prior-art claims. Reed–Solomon ≠ holographic.
> Event-sourcing ≠ time travel.

## Bundles

| Bundle | File | SHA-256 |
|---|---|---|
| a11oy-runtime-proof | `zarf-package-a11oy-runtime-proof-amd64-0.3.1.tar.zst` | `800c75865b588cc56d9042ac029d67e11999fd54c09e1c6b3631667ab0984d79` |
| amaru-attestation-proof | `zarf-package-amaru-attestation-proof-amd64-0.3.1.tar.zst` | `041e8ac703689ad2f8dcb123862ab3aab32bd7290d96c4e05f5cfc3aca32cfef` |
| killinchu-bundle-proof | `zarf-package-killinchu-bundle-proof-amd64-0.3.1.tar.zst` | `0e581c9f73de8187ee5d14c7cdeeeff1f55f85820e117b031cee987478d53874` |
| rosie-replay-proof | `zarf-package-rosie-replay-proof-amd64-0.3.1.tar.zst` | `ed04612ee6738e90fd0c6acc3ac70dea9240b24e51cef3ac751c08cb7b1ac5e2` |
| sentra-gates-proof | `zarf-package-sentra-gates-proof-amd64-0.3.1.tar.zst` | `4109db4c278d4a02f8f32be7fde575dda756a8b338e028d1dfef8d491c2e464b` |

## Detached signatures (cosign)

| Signature | SHA-256 |
|---|---|
| `a11oy-proof.uds.sig` | `e26848d8af53379279cc09cbebb77b0ac42b430b456f3d2b1ab907065f3c2633` |
| `amaru-proof.uds.sig` | `986a88c48bc39f377c5264e438c5bd749e7221513167efe9bd3cf69f8c5b2600` |
| `killinchu-proof.uds.sig` | `41f8db7ebcab559d4ec95757a8c552f0e15727e0e30a6d5a021d0bd118b39577` |
| `rosie-proof.uds.sig` | `61b6cee6edb4807c7520c1ce55f7a5efe2f48e7ba809216302c4c47885c5e967` |
| `sentra-proof.uds.sig` | `348336e0e3da934a7e3f341bd8f28c2657e9c91f900267cd19a8852cc4061714` |

Public key: `cosign_signing_key.pub` (attached).

## Verify (cosign)

```bash
# 1. Verify each bundle's detached signature against the attached public key.
cosign verify-blob \
  --key cosign_signing_key.pub \
  --signature a11oy-proof.uds.sig \
  zarf-package-a11oy-runtime-proof-amd64-0.3.1.tar.zst
# Expected: "Verified OK"

# Repeat for amaru / killinchu / rosie / sentra using the matching .sig file.

# 2. Confirm integrity against the published SHA-256 digests above.
sha256sum -c <<'SUMS'
800c75865b588cc56d9042ac029d67e11999fd54c09e1c6b3631667ab0984d79  zarf-package-a11oy-runtime-proof-amd64-0.3.1.tar.zst
041e8ac703689ad2f8dcb123862ab3aab32bd7290d96c4e05f5cfc3aca32cfef  zarf-package-amaru-attestation-proof-amd64-0.3.1.tar.zst
0e581c9f73de8187ee5d14c7cdeeeff1f55f85820e117b031cee987478d53874  zarf-package-killinchu-bundle-proof-amd64-0.3.1.tar.zst
ed04612ee6738e90fd0c6acc3ac70dea9240b24e51cef3ac751c08cb7b1ac5e2  zarf-package-rosie-replay-proof-amd64-0.3.1.tar.zst
4109db4c278d4a02f8f32be7fde575dda756a8b338e028d1dfef8d491c2e464b  zarf-package-sentra-gates-proof-amd64-0.3.1.tar.zst
SUMS
```

`cosign verify-blob` was captured as **Verified OK** at build time (see audit `PROOF_CAPTURE.txt`).
