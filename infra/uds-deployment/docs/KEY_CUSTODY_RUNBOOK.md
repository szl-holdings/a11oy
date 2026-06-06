# Key Custody Runbook — SZL Governance Receipts

**Scope:** the signing key for SZL governance receipts (the `szl-receipts-server`
Ed25519 key introduced in PR #19, and the legacy HMAC demo key it replaces).
**Audience:** SZL platform/SecOps operators and DoD-deployment reviewers.
**Origin:** PhD Crypto/SecOps verdict, **Finding I** (`PhD_CRYPTO_VERDICT.md`
lines 110–119): *"production key custody is the largest gap to DoD-deployable.
Symmetric demo keys in plaintext Secrets must become asymmetric keys in an HSM
before any 'production crypto' claim."*
**Pricing date:** all vendor prices below are as observed **2026-05-30** with the
source URL inline. Re-verify before committing budget — cloud list prices change.

---

## 0. Where we are today (the honest baseline)

| Fact | State as of 2026-05-30 | Citation |
|---|---|---|
| Demo signer | HMAC-SHA-256, key `szl-dev-demo-key-2026-warhacker` baked into `values.yaml` (`b64enc` once into Secret `szl-receipts-hmac`). | `docs/CRYPTO_KEY_HANDLING.md`; PhD Systems verdict Scope 3 |
| Current best signer | **Ed25519 software key**, PEM mounted from a k8s Secret at `SZL_ED25519_KEY_PATH` (default `/run/secrets/szl-receipts/ed25519.pem`). | `szl-uds-deployment` PR #19 (`services/szl-receipts-server/server.py`) |
| Signing algorithm of receipts | Canonical DSSEv1 PAE, Ed25519 signature in `signatures[].sig`. | PR #19 `dsse_pae()` / `sign_dsse()`; fixes PhD Finding A1 |
| Key location | Plaintext inside a k8s Secret in the receipts namespace. | PR #19 `secret-keypair.yaml` |
| Who can forge | Anyone with `get secret` RBAC on that namespace. For HMAC, read == forge (symmetric). For Ed25519, read of the *private* key == forge. | PhD Finding I, verdict line 115 |
| HSM "in prod" | **Documentation-only.** Not implemented. | PhD Finding I, verdict line 114 |

**Ed25519 is strictly better than HMAC** (asymmetric → the *public* key can be
published for non-repudiable verification; readers of the public key cannot
forge). But a software private key in a k8s Secret is **still Tier 0**: the
private key exists in cluster etcd and in the signer pod's memory, so anyone who
can read the Secret can mint valid receipts. Moving that private key into an
HSM/KMS is the remaining gap to DoD-deployable.

---

## 1. Threat model

### 1.1 Assets
- **Signing private key** (Ed25519 today). Compromise ⇒ attacker can forge
  governance receipts that verify against the published public key.
- **Receipt hash-chain integrity.** This is a *hash* chain (`prev_hash =
  SHA256(prev record)`), not a key chain — see §4. Key compromise does NOT
  rewrite history; it lets an attacker mint *new* fraudulent receipts.

### 1.2 Who can read the signing key today (Tier 0)
1. Any principal with `get`/`list` on Secrets in the receipts namespace
   (`kubectl get secret ... -o jsonpath='{.data}'`).
2. Any principal who can `exec` into the `szl-receipts-server` pod (key is
   mounted on the filesystem + held in process memory).
3. Any principal who can read **etcd** directly (cluster-admin, node root on the
   control plane, or an etcd backup).
4. Anyone with read access to a **Secret/etcd backup** stored off-cluster.
5. CI/CD principals that provision the Secret (the key transits the pipeline).

### 1.3 Who can forge receipts
- Today: **everyone in set §1.2.** With the symmetric HMAC demo key, that set
  also includes everyone who can read the *server config*, since the key is in
  `values.yaml`/git history.

### 1.4 What happens when an attacker obtains read access to the Secret
- **HMAC (demo):** total compromise of authenticity. The attacker can mint
  receipts indistinguishable from genuine ones, AND any prior receipt's
  authenticity is now deniable (shared secret ⇒ no non-repudiation).
- **Ed25519 (PR #19):** the attacker can mint *new* forged receipts that verify
  against the published public key until the key is rotated (§3) and the new
  public key is published. Past receipts already anchored externally (Rekor / a
  published `chain_head`) remain attributable; un-anchored history within the
  compromise window is suspect. **Detection** requires either (a) an
  externally-anchored `chain_head` that the forgery cannot match, or (b)
  out-of-band logging of legitimately-issued receipt IDs.
- **Either case:** the hash chain's *integrity* (no silent edits to past
  records) is preserved because each record commits to the prior; but a
  key-holder can *append* fraudulent records or fork the chain.

### 1.5 Trust-boundary note (carried from the controller)
The DSSE receipt crosses from the Pepr controller to `szl-receipts-server` over
the in-cluster network. In the demo this hop is unauthenticated (PhD Finding G,
verdict line 98). Tier 1+ should add mTLS (UDS/Istio `PeerAuthentication: STRICT`)
so a network adversary cannot drop or substitute receipts in transit.

---

## 2. Three tiers of key custody

Each tier lists: **what / threat model / cost (with citation) / migration steps /
rotation cadence.** A cut-over never loses the chain because the chain is a hash
chain — see §4. The invariant for every migration is: **publish the new public
key, dual-sign across an overlap window (§3), then retire the old key.**

### Tier 0 — Ed25519 private key in a Kubernetes Secret (CURRENT)

- **What:** Ed25519 PEM in Secret `szl-receipts-ed25519`, mounted into the signer
  pod (PR #19). Public key published for verifiers.
- **Threat model:** anyone with `get secret` RBAC in the receipts namespace (and
  the etcd/backup readers in §1.2) can read the private key and forge. No
  hardware boundary; the key is extractable plaintext.
- **Cost:** **$0** incremental (uses existing k8s).
- **Migration steps (HMAC → Tier 0, the PR #19 cut-over):**
  1. Generate Ed25519 keypair offline:
     `openssl genpkey -algorithm ed25519 -out ed25519.pem` then
     `openssl pkey -in ed25519.pem -pubout -out ed25519.pub`.
  2. Create the Secret: `kubectl create secret generic szl-receipts-ed25519
     --from-file=ed25519.pem -n <receipts-ns>`.
  3. Publish `ed25519.pub` in a ConfigMap (and in the DU catalog listing / repo).
  4. **Dual-sign window** (§3): run the server signing with *both* HMAC and
     Ed25519 for N hours so legacy verifiers keep working, then drop HMAC.
  5. `shred -u ed25519.pem` on the ops workstation; the only copy now lives in
     the Secret.
- **Rotation cadence:** **90 days** recommended at this tier (short, because the
  key is the most exposed it will ever be). Procedure in §3.

### Tier 1 — Sealed Secrets (RECOMMENDED for the Series-A pilot)

- **What:** [bitnami-labs/sealed-secrets](https://github.com/bitnami-labs/sealed-secrets).
  The private key is encrypted into a `SealedSecret` CRD that is safe to commit
  to git; the in-cluster `sealed-secrets-controller` decrypts it into a normal
  Secret at apply time. GitOps-friendly: the encrypted blob is in version
  control, the plaintext only exists in-cluster.
- **Threat model:** **git history is now safe** — an attacker who reads the repo
  cannot recover the key (it is asymmetrically encrypted to the controller's
  cluster key). BUT an attacker *with cluster access* can still read the
  decrypted Secret (the controller materializes a normal k8s Secret), so the
  in-cluster exposure is the same as Tier 0. This closes the "key checked into
  git / leaked via repo or CI logs" hole, which is the most common real-world
  leak, without buying hardware.
- **Cost:** **$0** (Apache-2.0 OSS; runs as one lightweight controller pod).
  Source: [bitnami-labs/sealed-secrets](https://github.com/bitnami-labs/sealed-secrets).
- **Migration steps (Tier 0 → Tier 1):**
  1. Install the controller: `helm install sealed-secrets
     sealed-secrets/sealed-secrets -n kube-system` (or vendor the image for
     air-gap).
  2. Seal the existing key:
     `kubeseal --controller-namespace kube-system < ed25519-secret.yaml >
     ed25519-sealedsecret.yaml`.
  3. Commit `ed25519-sealedsecret.yaml`; delete the plaintext Secret manifest
     from git history (BFG / filter-repo) and rotate the key once (§3) so any
     previously-committed plaintext is dead.
  4. Apply the SealedSecret; the controller produces the runtime Secret the
     signer mounts — **no change to `server.py`**.
  5. **Back up the controller's sealing key** (`kubectl get secret -n
     kube-system -l sealedsecrets.bitnami.com/sealed-secrets-key`): losing it
     makes all SealedSecrets undecryptable. Store the backup at Tier 2 custody.
- **Rotation cadence:** signing key **180 days**; the controller's sealing key
  rotates on the controller's default (30-day key renewal, old keys retained for
  decrypt). Re-seal after any signing-key rotation.

### Tier 2 — External KMS / HSM (DoD-deployable)

The private key **never exists in cluster etcd or pod memory** — signing happens
inside the hardware boundary (sign-as-a-service) or the key is non-extractable.
Pick by deployment posture:

#### Option 2a — AWS CloudHSM (cloud, FIPS 140-3 Level 3)
- **What:** dedicated single-tenant HSM cluster; the Ed25519 key is generated and
  used inside the HSM via PKCS#11/JCE. The signer calls the HSM to sign; the key
  is non-extractable.
- **FIPS:** the current **hsm2m.medium** instance is **FIPS 140-3 Level 3**
  certified (Certificate #4703). (The legacy hsm1.medium was FIPS 140-2 Level 3;
  its certificate moved to the historical list on 2026-01-04 — use hsm2m.medium.)
  Source: [AWS CloudHSM FIPS validation](https://docs.aws.amazon.com/cloudhsm/latest/userguide/fips-validation.html).
- **Cost:** billed **per HSM-hour, no upfront cost** ([AWS CloudHSM pricing](https://aws.amazon.com/cloudhsm/pricing/)).
  AWS does not publish the per-hour figure on a machine-readable page; the
  widely-published us-east-1 list rate is **≈ $1.45/hr** (hsm1.medium) and
  **≈ $1.81/hr** (hsm2m.medium). At ≈ $1.81/hr a **single** hsm2m.medium ≈
  **$1,300/month**; AWS recommends **≥ 2 HSMs across AZs for HA**, so a
  production HA cluster ≈ **$2,600/month** (~$31k/yr). **Confirm the live rate in
  the pricing console before budgeting.**
- **Threat model:** key is non-extractable hardware-bound. Forgery now requires
  HSM credentials AND network reach to the HSM ENI; `kubectl get secret` no
  longer yields the key. Quorum/M-of-N can gate key admin.

#### Option 2b — HashiCorp Vault Transit secrets engine (signing-as-a-service)
- **What:** [Vault Transit](https://developer.hashicorp.com/vault/docs/secrets/transit)
  is "cryptography as a service": the signer sends the payload (or its digest) to
  Vault, Vault signs with a key that **never leaves Vault**, and returns the
  signature. Transit supports **Ed25519** sign/verify directly (and, notably,
  **ML-DSA / SLH-DSA** key types — a clean future path for the PQC dual-sign in
  the vessels `PQC_RECEIPT_UPGRADE.md`).
- **Cost:** **self-managed Vault Community Edition is free** (open source). HCP
  Vault / Vault Enterprise are paid — HashiCorp lists managed resources from
  **$0.10/resource/month (Essentials)** up to **$0.99/resource/month (Premium)**
  ([HashiCorp pricing](https://www.hashicorp.com/pricing)). For air-gap/DoD,
  self-managed Community/Enterprise on-prem is the usual choice; back Transit
  with an HSM seal for hardware key protection of the Vault master key.
- **Threat model:** the signing key never lands in the cluster; forgery requires
  a valid Vault token with `transit/sign/<key>` capability. Reduces the blast
  radius of a k8s Secret read to "can mint receipts only while holding a live
  Vault token," and the token can be short-TTL + audited. Hardware assurance
  depends on the Vault seal (use an HSM auto-unseal for FIPS-grade root key).

#### Option 2c — Google Cloud KMS, HSM protection level (cloud, FIPS 140-2 Level 3)
- **What:** asymmetric signing key with `protectionLevel: HSM`; sign via the KMS
  API. Key is non-extractable. Cloud HSM is **FIPS 140-2 Level 3 validated**
  ([Google Cloud HSM](https://cloud.google.com/kms/docs/hsm),
  [protection levels](https://cloud.google.com/kms/docs/protection-levels)).
- **Cost** ([Cloud KMS pricing](https://cloud.google.com/kms/pricing), effective
  2025-03-17): an **HSM EC-signing (Ed25519/EC) key version** is
  **$0.003424658/hour** for the first 2,000 key-versions/account (≈ **$2.50/key
  version/month**), then $0.001369863/hr; **key operations $0.03 per 10,000**.
  A single signing key version ≈ **$2.50–$3/month** + negligible per-op cost —
  the cheapest Tier 2 for a single low-volume signing key. (A dedicated
  **Single-tenant Cloud HSM** is $4.794520548/hr ≈ $3,500/month if isolation is
  required.)
- **Threat model:** equivalent to 2a (non-extractable, IAM-gated). Forgery needs
  `cloudkms.cryptoKeyVersions.useToSign` IAM on the key.

#### Option 2d — YubiHSM 2 (air-gap / on-prem, physical)
- **What:** [YubiHSM 2](https://www.yubico.com/products/hardware-security-module/)
  — a USB-A hardware security module. Works fully **offline**; ideal for an
  air-gapped signing ceremony or an on-prem appliance.
- **FIPS / price:** the standard **YubiHSM 2 v2.4 is $650 USD**; the
  **FIPS 140-2 validated YubiHSM 2 FIPS v2.2 is $950 USD**
  ([Yubico store](https://www.yubico.com/store/yubihsm-2-series/)). One-time
  hardware cost, no recurring cloud fee.
- **Threat model:** the strongest custody for air-gap — the key is on a physical
  device that need never touch a network. Compromise requires physical
  possession + the device auth key. Pair with a documented dual-control signing
  ceremony.

#### Tier 2 cost summary (as of 2026-05-30)

| Option | FIPS level | Recurring cost (single signing key) | HA / notes |
|---|---|---|---|
| AWS CloudHSM hsm2m.medium | 140-3 Level 3 | ≈ $1.81/hr ≈ **$1,300/mo per HSM** (confirm live) | ≥2 HSMs for HA ≈ **$2,600/mo** |
| Vault Transit (self-managed CE) | depends on seal | **$0** (OSS); HCP from $0.10–$0.99/resource/mo | key never leaves Vault; supports Ed25519 + ML-DSA |
| Google Cloud KMS (HSM) | 140-2 Level 3 | ≈ **$2.50–$3/mo per key version** + $0.03/10k ops | cheapest cloud Tier 2; single-tenant HSM $4.79/hr |
| YubiHSM 2 (v2.4 / FIPS v2.2) | FIPS 140-2 (FIPS SKU) | **$650 / $950 one-time** | offline / air-gap; physical custody |

**Recommendation:** Tier 1 (Sealed Secrets, $0) for the Series-A pilot to close
the git-leak hole immediately; **Google Cloud KMS HSM** or **Vault Transit** as
the lowest-friction Tier 2 for a cloud DoD pilot; **YubiHSM 2 FIPS** for the
air-gapped Warhacker/DoD demo where there is no cloud egress.

---

## 3. Rotation procedure (works at every tier)

**Goal:** rotate the signing key WITHOUT breaking the existing receipt chain.
The chain is hash-linked, so old receipts stay valid forever; the only thing that
changes is which key signs *new* receipts. The risk window is verifiers that have
not yet learned the new public key — so we **dual-sign across an overlap window**.

The **dual-sign overlap pattern is already documented** for the HMAC→ML-DSA
transition in vessels `docs/PQC_RECEIPT_UPGRADE.md` (§4 dual-sign envelope; §8
Phase 4 "Key Rotation (annual) … dual-sign with v1 and v2 during overlap window
… drop v1 after the rotation window"). Reuse that exact mechanism for Ed25519
key rotation:

1. **Provision the new key** (`szl-receipts-ed25519-v2`) at the target tier
   (Secret / SealedSecret / KMS key version / HSM object).
2. **Publish the new public key** (ConfigMap `szl-receipts-pubkeys`, DU catalog,
   repo) BEFORE any receipt is signed with it, so verifiers can fetch it.
3. **Open the overlap window:** configure the signer to attach **two**
   signatures to every new receipt — `keyid=...-v1` and `keyid=...-v2` — for
   **N hours** (default **48h**; long enough for all verifiers and any cached
   public-key copies to refresh). The DSSE envelope already supports multiple
   `signatures[]` entries, so this is additive and backward-compatible (legacy
   verifiers read v1 and ignore v2).
4. **Cut over:** after N hours, stop signing with v1; sign only with v2.
5. **Retain, don't delete, v1's public key** — it is needed to verify the
   historical receipts signed during and before the overlap. Archive the v1
   *private* key per tier (shred for Tier 0/1; disable/schedule-destroy for KMS;
   delete the HSM object after backup).
6. **Anchor a fresh `chain_head`** (§4) signed by v2 so the post-rotation chain
   has an externally verifiable root under the new key.

**Cadence by tier:** Tier 0 = 90 days · Tier 1 = 180 days · Tier 2 = 12 months
(or on personnel change / suspected compromise — rotate immediately, skip to a
0-hour overlap if a compromise is confirmed).

---

## 4. Disaster recovery

**Key principle: the chain is a HASH chain, not a KEY chain.** Each receipt
commits to the prior via `prev_hash = SHA256(prev record)` (PR #19
`_receipt_hash`; PhD Finding H, verdict lines 103–106). Therefore:

- **If the signing key is lost or corrupted:** the **integrity of the existing
  chain is preserved** — every already-issued receipt still verifies against its
  *published public key*, and the hash links still prove no record was silently
  altered. **What you lose is the ability to mint NEW receipts** until a new
  keypair is provisioned and its public key is published.
- **Recovery procedure:**
  1. Provision a fresh keypair at the current tier.
  2. Publish the new public key.
  3. Resume signing; the first new receipt's `prev_hash` still points at the last
     pre-incident record, so the chain continues unbroken across the key change
     (the chain does not care which key signed each record).
  4. Anchor a new signed `chain_head` under the new key.
- **If the key is *compromised* (not just lost):** treat all receipts in the
  exposure window as suspect, rotate immediately (§3 with a 0-hour overlap),
  publish an incident note with the last externally-anchored `chain_head` so
  third parties can distinguish genuine pre-incident receipts from any forgeries.
- **Backups:** at Tier 0/1, the *only* copy of the private key is the
  Secret/SealedSecret — **the cluster etcd backup IS the key backup**, which is
  exactly why it must be access-controlled (§1.2). At Tier 2, DR is the KMS/HSM
  provider's HA + the documented re-provision-and-republish flow above; **never
  escrow a Tier 2 private key back down to a Secret** "for safety" — that
  silently demotes you to Tier 0.
- **Chain durability caveat (open):** today the receipts server stores receipts
  on a PVC (PR #19) but the chain-truncation gap (PhD Finding H, verdict line
  106) is only fully closed by publishing an **externally-anchored signed
  `chain_head`** (e.g. to Rekor) at intervals. Until then, DR can restore the
  chain but cannot, by itself, prove the tail was not truncated before backup.

---

## 5. Audit trail — who has access, who SHOULD, and the RBAC reduction plan

### 5.1 Who has access today
- Any namespace member with `get`/`list` on Secrets in the receipts namespace.
- Anyone with pod `exec` into `szl-receipts-server`.
- cluster-admins, control-plane node root, etcd-backup readers (§1.2).
- CI principals that create the Secret + (for HMAC) anyone with repo/values.yaml
  read.

### 5.2 Who SHOULD have access
- **Tier 0/1:** a single dedicated ServiceAccount that the signer pod runs as,
  with read on *only* the one signing Secret — nobody else.
- **Tier 2:** **no human and no in-cluster SA holds the private key at all.** A
  narrowly-scoped identity holds *sign* permission (KMS IAM `useToSign` / Vault
  `transit/sign/<key>` / HSM crypto-user), gated by audit logging and, ideally,
  M-of-N for key administration.

### 5.3 RBAC reduction plan
1. **Create a dedicated ServiceAccount** `szl-receipts-signer` and run the signer
   pod as it.
2. **Scope a Role** granting `get` on the single resourceName of the signing
   Secret only — not `list`/`watch` on all Secrets:
   ```yaml
   apiVersion: rbac.authorization.k8s.io/v1
   kind: Role
   metadata: { name: szl-receipts-signer-read, namespace: <receipts-ns> }
   rules:
     - apiGroups: [""]
       resources: ["secrets"]
       resourceNames: ["szl-receipts-ed25519"]   # this Secret ONLY
       verbs: ["get"]
   ```
   Bind it to `szl-receipts-signer` only.
3. **Remove broad Secret access:** audit existing RoleBindings/ClusterRoleBindings
   for `secrets` `get/list/watch` in the namespace; remove any that are not the
   signer SA. (`kubectl auth can-i --list --as=<subject> -n <receipts-ns>`.)
4. **Gate pod exec:** deny `pods/exec` in the receipts namespace except for a
   break-glass role that is audited.
5. **Enable Kubernetes audit logging** for `get secrets` in the receipts
   namespace so every read of the key is recorded.
6. **Encrypt etcd at rest** (KMS provider for the API server) so an etcd backup
   read does not equal a key read — a prerequisite before claiming Tier 0/1 is
   acceptable for anything beyond a pilot.
7. **At Tier 2:** delete the in-cluster private-key Secret entirely; the signer
   authenticates to KMS/Vault/HSM via workload identity, and access reduces to a
   single auditable *sign* grant.

---

## 6. References

- PhD Crypto/SecOps verdict — Finding I (key management) and Finding H (hash
  chain): `PhD_CRYPTO_VERDICT.md` lines 103–119.
- `szl-uds-deployment` **PR #19** — Ed25519 signer + PVC + canonical DSSE PAE
  (the Tier 0 baseline this runbook builds on).
- vessels `docs/PQC_RECEIPT_UPGRADE.md` — the dual-sign overlap pattern reused in
  §3 (and the ML-DSA path that Vault Transit / a future HSM key can serve).
- [bitnami-labs/sealed-secrets](https://github.com/bitnami-labs/sealed-secrets) — Tier 1.
- [AWS CloudHSM](https://aws.amazon.com/cloudhsm/) · [pricing](https://aws.amazon.com/cloudhsm/pricing/) · [FIPS validation (hsm2m.medium = FIPS 140-3 Level 3, Cert #4703)](https://docs.aws.amazon.com/cloudhsm/latest/userguide/fips-validation.html)
- [HashiCorp Vault Transit secrets engine](https://developer.hashicorp.com/vault/docs/secrets/transit) · [HashiCorp pricing](https://www.hashicorp.com/pricing)
- [Google Cloud KMS HSM tier](https://cloud.google.com/kms/docs/hsm) · [pricing](https://cloud.google.com/kms/pricing) · [protection levels](https://cloud.google.com/kms/docs/protection-levels)
- [YubiHSM 2](https://www.yubico.com/products/hardware-security-module/) · [store / pricing](https://www.yubico.com/store/yubihsm-2-series/)

---

*All vendor prices observed 2026-05-30 at the cited URLs; re-verify before
budgeting. This runbook is documentation only — it does NOT provision an HSM or
migrate any key.*
