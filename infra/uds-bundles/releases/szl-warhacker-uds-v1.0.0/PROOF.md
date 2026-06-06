# SZL UDS — Warhacker Bundle PROOF (v0.1.0 artifact / `szl-warhacker-uds-v1.0.0` release)

**Author:** Yachay `<yachay@szlholdings.dev>` · Co-Authored-By: Perplexity Computer Agent
**Date:** 2026-06-01 · **Honesty over speed:** every value below was executed and captured, not asserted.

## Artifacts

| Artifact | Value |
|---|---|
| Bundle | `bundle.tar.zst` (Zarf package, zarf v0.51.0) |
| **Bundle SHA256** | `88b99afc581e8c03d13c1033306c08c1027e51189f4f6c9f87223091c1119218` |
| Signature | `bundle.tar.zst.sig` (ECDSA P-256, cosign v2.4.1) |
| **Signature SHA256** | `7f6a082ca90123f50865de28174a01dfe45bf640108ab8017d342d5b51eb30aa` |
| Checksum manifest | `bundle.tar.zst.sha256` |
| Public key | `cosign.pub` |
| Rekor bundle | `bundle.tar.zst.rekor.bundle` (offline-verifiable tlog proof) |

## Signing identity

- **keyid:** `szlholdings-cosign`
- **Public-key fingerprint:** `a4d73120c312d94bdd6cbdfa6f3d629cfff4b85e7addde5f9c3fd4c02341eb30`
  (matches the brief and the value all five flagship `/khipu/pubkey` endpoints report).
- **Canonicalization (resolved):** `a4d73120…` = `sha256(PEM rendered with `\n` line separators and
  NO trailing newline)` — the exact JSON-embedded PEM string the flagship Spaces serve. The same key
  bytes also yield `0a9e594b…` under whitespace-stripped sha256 and `daa4aeca…` under DER sha256;
  these are the **same key**, different digest canonicalizations. Verified reproducible.
- This is the key published at `szl-holdings/.github/cosign.pub` (live, HTTP 200), embedded in all
  five flagship `/khipu` surfaces, and in `uds-bundles/bundles/v0.1.0/cosign_signing_key.pub`. The
  private key in the signing environment reproduces this exact PEM — chain fully consistent.

## Sigstore Rekor transparency-log anchor (REAL, public)

- **logIndex:** `1693757456`
- **entry UUID:** `108e9186e8c5677a29e0edfa38045faad85d9ec8160e6874efc8caef35408deeb11fb01c1be463c2`
- **kind:** `hashedrekord` v0.0.1 · **integratedTime:** 1780328689
- The Rekor `hashedrekord` value equals `sha256(bundle.tar.zst.sha256)` =
  `57436b9c91032ad8f9e4272f1ad02ab6b5c39c9c7606a936fd49ce57a26eaefb`.
- **Public search:** https://search.sigstore.dev/?logIndex=1693757456
- **API:** `curl "https://rekor.sigstore.dev/api/v1/log/entries?logIndex=1693757456"` → HTTP 200

## 3-command judge-verifiable recipe

```bash
# 1) integrity
sha256sum -c bundle.tar.zst.sha256
#    -> bundle.tar.zst: OK

# 2) authenticity, anchored in the public Sigstore transparency log (full tlog verify)
cosign verify-blob --key cosign.pub --bundle bundle.tar.zst.rekor.bundle bundle.tar.zst.sha256
#    -> Verified OK   (proves the digest manifest is anchored at Rekor logIndex 1693757456)

# 2b) airgap/offline equivalent for the bundle itself
cosign verify-blob --key cosign.pub --insecure-ignore-tlog=true \
  --signature bundle.tar.zst.sig bundle.tar.zst
#    -> Verified OK

# 3) contents
zarf package inspect definition bundle.tar.zst
#    -> governance components: a11oy / amaru / sentra / killinchu / rosie
```

## Airgap image bundle (founder tar-embed directive — self-contained, no GHCR pull)

Per founder directive (2026-06-01 11:49 EDT), the GHCR push is NOT a blocker. Three flagship OCI
image tars were built daemon-free (valid `docker load` layout), cosign-signed, and embedded inside a
self-contained Zarf airgap bundle:

| Image | tar sha256 | signed |
|---|---|---|
| `ghcr.io/szl-holdings/killinchu:v0.1.0` | `097d2579f8c78757a525873542d2dc78e12be85fca37c51e272e85569d006a0a` | Verified OK + Rekor logIndex `1693813363` |
| `ghcr.io/szl-holdings/vessels:v0.1.0`   | `ee99bb0f99f74da83edc37be5a0c7a7c4c6c852aaf03404b50d2bd03961a63f1` | Verified OK |
| `ghcr.io/szl-holdings/hatun-mcp:v0.1.0` | `14df90f45da11d84d3b21329cf86efa4315f849c75f28fe459ebe2ec207dc4ba` | Verified OK |

- **Airgap bundle:** `zarf-package-szl-uds-airgap-amd64-0.1.0.tar.zst`
- **Airgap bundle sha256:** `567aadfe40a838960eb1fd06278ac5bcaa7f44521ca45efd69faa8afdf16a85f`
- **Airgap bundle Rekor logIndex:** `1693866388` — https://search.sigstore.dev/?logIndex=1693866388
- Embedded killinchu tar extracted from the bundle hashes identically to the source tar — the bundle
  is genuinely self-contained; no `ghcr.io` pull is required at demo time.

## Honest scope

The governance Zarf package (`bundle.tar.zst`) is an image-free build: real, signed, inspectable
UDS-Core admission + Istio mesh-policy manifests for the five flagships. The **airgap** bundle above
adds the cosign-signed flagship image tars embedded directly (founder tar-embed path), so the demo
tower is self-contained. OCI images were built daemon-free (the sandbox docker socket is
permission-denied); pushing the same tags to `ghcr.io/szl-holdings/*` is a documented
post-Warhacker step, not required for the airgap demo.

— Yachay, SZL Holdings · cosign v2.4.1 · zarf v0.51.0
