<!--
SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
-->

# Rule: honest-status

How to write any README / docs / status claim. The honesty section is a feature for a defense
buyer, not a liability.

## Rules

- **Every claim needs a checkable artifact or an explicit label.** A claim is acceptable only if
  it links to (a) a live endpoint, (b) a named Lean theorem, (c) a verifiable artifact (Rekor
  index, cosign verify, UDS bundle tag), or (d) carries an explicit **ROADMAP / MODELED / SAMPLE**
  label. No claim without one of these.
- **Use the four labels precisely:**
  - **MEASURED** — backed by a real, fresh exporter delta or a live 200 endpoint.
  - **SAMPLE** — plausible but not freshly measured (e.g. joules with no reachable GPU lung).
  - **MODELED** — design-only, no hardware (e.g. orbital tier: `modeled:true` / `reachable:false`).
  - **ROADMAP** — not built yet (carbon feed, persistent kernel, `execution_guard` wrapper, SBOM;
    SLSA L3 is ROADMAP, never claimed achieved; FedRAMP/CMMC/ATO likewise ROADMAP).
- **Never inflate.** Locked formulas = 8. Λ = Conjecture 1. Khipu BFT = Conjecture 2. SLSA = L1
  honest / L2 build-attested (L3 ROADMAP).
- **Mirror status across surfaces.** README *Honest status*, `docs/architecture.md` matrix, and
  `/api/a11oy/v1/honest` must agree. If you change a claim, change it everywhere.
- When in doubt, **downgrade the label** (MEASURED → SAMPLE → ROADMAP) rather than overclaim.
</content>
