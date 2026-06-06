# Verify cosign + Rekor for SLSA L1

> **Verify any SZL flagship container with keyless `cosign`, then pull its public Sigstore Rekor transparency-log entry — the honest SLSA L1 proof.**
>
> **Headline number: 1 image → 1 Fulcio cert → 1 public Rekor entry, no shared secret.**

SZL signs container images with **keyless** cosign: the signing identity is a GitHub Actions
OIDC token, the certificate is issued by Fulcio, and the entry is recorded in the public Rekor
transparency log. This recipe verifies that chain for any of the five flagships.

> **Honest posture.** SZL claims **SLSA L1** (honest) — SBOM + DCO + provenance attestation — not
> L2/L3. The *image* signatures are real keyless cosign; the *runtime receipt* signatures in the
> live Spaces are still `PLACEHOLDER`. Don't conflate the two.

---

## Prerequisites

```bash
# cosign and rekor-cli (Sigstore)
brew install cosign rekor-cli            # or: go install github.com/sigstore/cosign/v2/cmd/cosign@latest
# slsa-verifier (optional, for provenance)
go install github.com/slsa-framework/slsa-verifier/v2/cli/slsa-verifier@latest
```
GHCR pull may require `read:packages`; the Rekor log lookups are fully public.

---

## Quickstart

```bash
ORG=ghcr.io/szl-holdings
IMG=$ORG/amaru:uds-v0.2.0

cosign verify $IMG \
  --certificate-identity-regexp="^https://github.com/szl-holdings/" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com" \
  | jq '.[0].optional | {Issuer, Subject: .Subject, Bundle: (.Bundle != null)}'
```

A successful verify prints the Fulcio cert subject (the GH Actions workflow identity) and confirms
a Rekor bundle is attached.

---

## Full walkthrough

### Step 1 — Verify the signature (keyless)

```bash
for o in a11oy sentra amaru killinchu rosie; do
  echo "== $o =="
  cosign verify ghcr.io/szl-holdings/$o:uds-v0.2.0 \
    --certificate-identity-regexp="^https://github.com/szl-holdings/" \
    --certificate-oidc-issuer="https://token.actions.githubusercontent.com" >/dev/null \
    && echo "OK" || echo "FAILED"
done
```

The `--certificate-identity-regexp` pins the signer to the SZL org; the `--certificate-oidc-issuer`
pins it to GitHub Actions. Both must match or verify fails — that is the trust anchor.

### Step 2 — Pull the public Rekor transparency-log entry

Each flagship README publishes its Rekor log index. These are **real and public**:

| Flagship | Image digest (prefix) | Rekor log index |
|---|---|---|
| a11oy | `sha256:7301a4…ab88` | `1710355173` |
| sentra | `sha256:360b96…b5ee` | `1710365350` |
| amaru | `sha256:317cb1…4f9f` | `1710371397` |
| killinchu | `sha256:dedfc3…718a` | `1710339915` |
| rosie | `sha256:3d634e…cbaa` | `1710144169` |

```bash
rekor-cli get --log-index 1710371397            # amaru
# Or in a browser:
#   https://search.sigstore.dev/?logIndex=1710371397
```

You can also query the public Rekor API directly (no tools needed):

```bash
curl -s "https://rekor.sigstore.dev/api/v1/log/entries?logIndex=1710371397" | jq 'keys'
# returns the entry UUID — proof the signature is in the immutable transparency log
```

### Step 3 — (Optional) Verify SLSA provenance

```bash
slsa-verifier verify-image ghcr.io/szl-holdings/amaru:uds-v0.2.0 \
  --source-uri github.com/szl-holdings/amaru \
  --builder-id "https://github.com/slsa-framework/slsa-github-generator/.github/workflows/generator_container_slsa3.yml@refs/tags/v2.0.0"
```

> **Honest note.** If provenance attestation is not yet attached to a given tag, `slsa-verifier`
> will say so. SZL's claim is L1 (SBOM + DCO + provenance pointer); treat any L3 provenance as
> aspirational until the workflow lands. The cosign + Rekor steps above are the authoritative L1
> evidence today.

### Step 4 — Cross-check the doctrine the image declares

```bash
curl -s https://szlholdings-amaru.hf.space/api/amaru/v1/honest | jq '{doctrine, slsa}'
# => { "doctrine": "v11", "slsa": "L1 (honest)" }
```

---

## See also

- **[02 — Deploy the 5-flagship UDS bundle](02-deploy-5-flagship-uds-bundle.md)** — deploy the verified images.
- **[01 — Verify a receipt end-to-end](01-verify-a-receipt-end-to-end.md)** — verify the runtime receipts.
- **[15 — Air-gapped install](15-air-gapped-install.md)** — verify before going offline.
- Sigstore: [cosign](https://docs.sigstore.dev/cosign/overview/) · [Rekor search](https://search.sigstore.dev)

## Cite this recipe

```bibtex
@misc{szl_cookbook_cosign_rekor_2026,
  title        = {Verify cosign + Rekor for SLSA L1 (SZL Cookbook recipe 06)},
  author       = {{SZL Holdings}},
  year         = {2026},
  howpublished = {\url{https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/06-cosign-rekor-slsa-l1.md}},
  note         = {Keyless cosign + public Rekor. SLSA L1 (honest). Doctrine v11 c7c0ba17.}
}
```

---
*Doctrine v11 LOCKED — 749/14/163 — kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 (honest)*
