# Sovereign AI for .gov

Air-gapped, auditable, kernel-checked governed AI for government environments. The full SZL
[anatomy](/anatomy/) deployed where external egress is prohibited and every decision must be
replayable by an auditor.

## The requirement

Government and defense environments need AI that is:

- **Sovereign** — runs on-prem / air-gapped, no external API egress.
- **Auditable** — every decision carries a replayable receipt chain.
- **Verifiable** — claims backed by machine-checked proofs, not vendor assurances.
- **Honest about limits** — no overclaiming of certification or capability.

## How the anatomy meets it

| Requirement | Organ / mechanism |
|-------------|-------------------|
| No external egress | HUKLLA **T07 UNAUTHORIZED_NETWORK** tripwire halts on egress outside the allowlist |
| Replayable decisions | [Khipu](/anatomy/#khipu) receipt DAG + [Yawar](/anatomy/#yawar) append-only ledger |
| Machine-checked claims | [`lutar-lean`](https://github.com/szl-holdings/lutar-lean) kernel proofs |
| Bounded autonomy | Tiered autonomy: SCRATCHPAD free · REVIEW per-K-cycle · PRODUCTION per-cycle approval |
| No self-modification | HUKLLA **T08 SELF_CODE_MODIFY** tripwire |
| Honest posture | [Kanchay `K(a)`](/anatomy/#kanchay) banned-claims register; SLSA L1 honest |

## Delivery surface

The [Warhacker mission packs](/use-cases/warhacker) demonstrate the delivery path: the UDS
air-gap stack (Zarf / `uds-cli` / UDS Core) carries the SZL bundle into the enclave, and the
SZL overlay adds the kernel-checked receipt chain. The result is governed AI that an air-gapped
operator can deploy, run, and **fully audit offline**.

## Certification path (honest)

SZL is **not** currently FedRAMP / SOC 2 / IL5 / CMMC certified. The architecture is *designed
toward* those frameworks — see the honest [Compliance & Security](/compliance) roadmap. Claiming
a certification not yet held is a [Doctrine v11](/doctrine/v11-v12) sacred-axis violation
(measurabilityHonesty, T02), so this site states the path, not a badge.

::: warning Honest status
SLSA **L1** today (provenance generated, not L3-verified). cosign signing **PENDING**.
FedRAMP / SOC 2 / IL5 / CMMC are **target frameworks on the roadmap**, not held certifications.
:::
