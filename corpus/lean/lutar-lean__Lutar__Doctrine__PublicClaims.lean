/-
Copyright © 2026 Lutar, Stephen P. (SZL Holdings).
Released under the Apache-2.0 License.
ORCID: 0009-0001-0110-4173
Date:  2026-05-28

# Public Claims Inventory — Doctrine V6

DOI (thesis): 10.5281/zenodo.14502417

## Purpose

This file is the authoritative source of truth for publicly-claimed Lean
theorems in the SZL Holdings / Lutar ecosystem. It records:

  (a) The Lean theorem with a matching name.
  (b) The runtime counterpart in platform code.
  (c) The doctrine doc citation.

**Doctrine V6 maintenance rule:**
Every PR that adds or removes a publicly-claimed theorem MUST update this
file. Every public post (LinkedIn, Zenodo, etc.) that claims a theorem
"builds offline" MUST have a corresponding entry here before the post is
made. LinkedIn/external claims that fail this check receive a follow-up
correction post within 48 hours (T01 integrity obligation).

## Integrity background

LinkedIn post 2026-05-27 claimed "HUKLLA halt-eligibility, OVERWATCH
read-only, Bekenstein admission build offline today." PhD-Math audit
confirmed these had no Lean files at that date. This file was created
as part of the integrity remediation PR (2026-05-28) that adds the
missing Lean files.

Zero `sorry`. Doctrine V6.

**Doctrine V6 declaration.**
No banned words appear in this file. All `#check` targets are genuine.
-/

import Lutar.HUKLLA.HaltEligibility
import Lutar.OVERWATCH.ReadOnly
import Lutar.DPI.DPIBound

namespace Lutar.Doctrine.PublicClaims

/-! ## Entry 1 — HUKLLA Halt-Eligibility -/

/-!
**Public claim:** LinkedIn post 2026-05-27 — "HUKLLA halt-eligibility."

**Lean theorem:** `Lutar.HUKLLA.halt_eligibility_monotone` and
`Lutar.HUKLLA.halt_eligibility_decidable`.
File: `Lutar/HUKLLA/HaltEligibility.lean`.

**Runtime counterpart:**
- Doctrine doc: `szl-holdings/ouroboros-thesis/docs/HUKLLA.md` (T01–T11).
- CI gate: `doi-title-gate.yml` in ouroboros-thesis and szl-trust (T11).
- Kernel tripwires (T01–T10): `szl-holdings/amaru/src/chakras/chakra_7_crown/HUKLLA_10_TRIPWIRES.md`.
- Runtime constant: `A11OY_DOCTRINE_LAMBDA_FLOOR=0.90` in
  `szl-holdings/a11oy/deploy/manifests/a11oy-deployment.yaml` (line 34–35).
- TS governance: `ouroboros-guardrails` lambda gate (≥ 0.90 proceeds).

**Status:** Lean file created 2026-05-28. Closes the gap identified by
PhD-Math audit. Theorem is genuine and zero-sorry.
-/

-- Confirm the key theorems typecheck.
#check @Lutar.HUKLLA.halt_eligibility_monotone
#check @Lutar.HUKLLA.halt_eligibility_decidable
#check @Lutar.HUKLLA.not_eligible_of_low_score

/-! ## Entry 2 — OVERWATCH Read-Only -/

/-!
**Public claim:** LinkedIn post 2026-05-27 — "OVERWATCH read-only."

**Lean theorems:** Five invariants in `Lutar/OVERWATCH/ReadOnly.lean`:
1. `overwatch_no_writes` — allowed ops are non-write.
2. `overwatch_read_admitted` — read ops are admitted.
3. `overwatch_rejects_write` — write ops are refused.
4. `overwatch_rejects_exec` — exec ops are refused.
5. `overwatch_halt_separation_of_powers` — OVERWATCH cannot halt.

**Runtime counterpart:**
- Python kernel: `r0513_overwatch_evolution/06_kernel.py` (commit `df4e9741`, 146 SLOC).
- Anatomy doc: `szl-holdings/ouroboros-thesis/docs/anatomy/hatun-sources.md`.
- LinkedIn anatomy: `linkedin_brain.md` — "OVERWATCH — r0513, df4e9741. 146 SLOC.
  Read-only. Five invariants. Watches every cycle. Halt authority belongs to HUKLLA."

**Status:** Lean file created 2026-05-28. Five invariants match the public claim.
Separation-of-powers theorem added as formal codification of the public statement.
-/

#check @Lutar.OVERWATCH.overwatch_no_writes
#check @Lutar.OVERWATCH.overwatch_read_admitted
#check @Lutar.OVERWATCH.overwatch_rejects_write
#check @Lutar.OVERWATCH.overwatch_rejects_exec
#check @Lutar.OVERWATCH.overwatch_halt_separation_of_powers

/-! ## Entry 3 — DPI Receipt-Chain Entropy Bound (formerly "Bekenstein") -/

/-!
**Public claim:** LinkedIn post 2026-05-27 — "Bekenstein admission."

**Retraction (F1-4 errata):** The name "Bekenstein" was retracted. See
`szl-holdings/ouroboros-thesis/CHANGELOG.md`: "TH6 relabel — Bekenstein →
DPI. The receipt-chain entropy bound is the elementary Cover-Thomas DPI
(Theorem 2.8.1, Elements of Information Theory, 2006), not the Bekenstein
physical bound."

**Lean theorems:** `Lutar/DPI/DPIBound.lean`:
- `dpi_bound_positive` — bound is strictly positive.
- `dpi_bound_monotone` — bound is monotone in receipt size.
- `dpi_admit_monotone` — admission gate is monotone.

**Runtime counterpart:**
- `szl-holdings/platform/packages/ouroboros-loop/src/loop.ts`
  `bekensteinCheck` → being renamed `dpiCheck` in the platform PR.
- `szl-holdings/platform/packages/ouroboros-integrations/src/lutar-formulas.ts`
  `bekensteinBound`, `bekensteinCheck` → deprecated aliases, renamed to
  `dpiBound`, `dpiCheck` in the platform PR.
- `szl-holdings/platform/packages/ouroboros-integrations/bench/the-four.bench.ts`
  `benchBekenstein` → renamed `benchDpiBound`.

**Update suggestion for any new public post:**
"The runtime 'Bekenstein gate' is being renamed DPIGate. The bound is the
Cover-Thomas DPI receipt-chain bound (sizeBytes × 8 bits), not the physical
Bekenstein bound. See CHANGELOG.md F1-4 errata."

**Status:** Lean file created 2026-05-28 under `Lutar/DPI/DPIBound.lean`.
Runtime rename in companion platform PR.
-/

#check @Lutar.DPI.dpi_bound_positive
#check @Lutar.DPI.dpi_bound_monotone
#check @Lutar.DPI.dpi_admit_monotone

end Lutar.Doctrine.PublicClaims
