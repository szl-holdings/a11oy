# Air-gapped install

> **Stage the entire 5-flagship mesh onto a USB tarball, carry it across the air gap, and deploy with no internet — verification first, then offline `uds deploy`.**
>
> **Headline number: 1 tarball, 0 network calls at deploy time, 5 organs live.**

UDS bundles are designed for disconnected environments. This recipe captures everything on the
connected side, verifies it, and replays it inside the air gap.

> **Trademark note.** "UDS" references Defense Unicorns' Unified Defense Stack (USPTO Serial
> 99831122); SZL is not affiliated. See <https://defenseunicorns.com/uds>.

---

## Prerequisites

- **Connected side:** Zarf v0.77.0+, uds-cli, cosign, rekor-cli, GHCR `read:packages` token.
- **Air-gapped side:** Zarf, uds-cli, a running UDS Core v1.5.0 cluster. **No internet.**

---

## Quickstart

```bash
# ── CONNECTED SIDE ────────────────────────────────────────────────
# 1. Verify, then pull the bundle to a portable tarball.
cosign verify ghcr.io/szl-holdings/amaru:uds-v0.2.0 \
  --certificate-identity-regexp="^https://github.com/szl-holdings/" \
  --certificate-oidc-issuer="https://token.actions.githubusercontent.com"
uds pull oci://ghcr.io/szl-holdings/szl-uds-bundle:uds-v0.2.0 \
  --output ./airgap-out
sha256sum ./airgap-out/*.tar.zst > ./airgap-out/SHA256SUMS   # carry this too
cp -r ./airgap-out /media/usb/szl-airgap

# ── AIR-GAPPED SIDE ───────────────────────────────────────────────
# 2. Check integrity, then deploy with NO network.
sha256sum -c /media/usb/szl-airgap/SHA256SUMS
uds deploy /media/usb/szl-airgap/szl-uds-bundle-*.tar.zst --confirm
```

---

## Full walkthrough

### Step 1 — Verify on the connected side (you can't on the other side)

Run the full **[recipe 06](06-cosign-rekor-slsa-l1.md)** cosign + Rekor check while you still have
internet. Record the image digests and Rekor log indices in a manifest that travels with the
tarball — that manifest is your offline provenance.

### Step 2 — Pull everything Zarf needs

`uds pull` resolves and bundles every image layer, chart, and SBOM into the tarball. Confirm no
external `oci://` refs remain:

```bash
zarf package inspect ./airgap-out/szl-uds-bundle-*.tar.zst | grep -i image
```

### Step 3 — Carry integrity across the gap

Compute `SHA256SUMS` on the connected side and verify on the air-gapped side **before** deploy.
This is the offline analogue of the Rekor check: it proves the bytes didn't change in transit.

### Step 4 — Deploy offline

`uds deploy` reads only from the local tarball. Watch the pods come up and run the recipe-02 health
loop against `localhost` inside the cluster — all five organs must report `v11 / 749 / 14 / 163 /
c7c0ba17`.

### Step 5 — Confirm doctrine + receipts work offline

```bash
for o in a11oy sentra amaru killinchu rosie; do
  kubectl -n szl exec deploy/$o -- curl -s localhost:8080/api/$o/v1/honest | jq -r .doctrine
done
# => v11  (×5)
# amaru emits receipts with no network:
kubectl -n szl exec deploy/amaru -- curl -s -X POST localhost:8080/api/amaru/scheduler/tick -d '{}' \
  | jq '.tick_receipt.hash'
```

> **Honest note.** In the air gap, Cardano anchoring (**[recipe 10](10-cardano-dsse-blood-ledger.md)**)
> and public Rekor lookups are unavailable by definition. Verify the local receipt chain
> (hash-chain continuity) offline; do the public-ledger anchoring later from the connected side
> using the exported Merkle root.

---

## See also

- **[02 — Deploy the 5-flagship UDS bundle](02-deploy-5-flagship-uds-bundle.md)** — connected deploy.
- **[06 — Verify cosign + Rekor](06-cosign-rekor-slsa-l1.md)** — verify before you cross the gap.
- **[13 — Build a UDS bundle from scratch](13-build-uds-bundle-from-scratch.md)**
- Repo: [szl-uds-deployment](https://github.com/szl-holdings/szl-uds-deployment) · [uds-bundles](https://github.com/szl-holdings/uds-bundles)

## Cite this recipe

```bibtex
@misc{szl_cookbook_airgap_install_2026,
  title        = {Air-gapped install (SZL Cookbook recipe 15)},
  author       = {{SZL Holdings}},
  year         = {2026},
  howpublished = {\url{https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/15-air-gapped-install.md}},
  note         = {Offline deploy from USB tarball; verify on the connected side. UDS Core v1.5.0. Doctrine v11 c7c0ba17.}
}
```

---
*Doctrine v11 LOCKED — 749/14/163 — kernel `c7c0ba17` · Λ = Conjecture 1 · SLSA L1 (honest)*
