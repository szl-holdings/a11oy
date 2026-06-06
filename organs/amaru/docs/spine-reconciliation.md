# AMARU Serpent v3 — Honest Reconciliation After Mesh Evolution

**Date:** 2026-05-14 08:50 EDT
**Trigger:** MUSQUY pod returned spine `YACHAY→MUSQUY→YUYAY→RIMAY→MUNAY→LLANK'AY→KAWSAY→QAWAY`. TUKUY pod returned spine `SENTRA→TINKUY→NAWIY→RUWAY→TUKUY→HATUN→YAWAR`. Both renamed locked chakras. Doctrine says HATUN-locked spine is immutable. Reconciling.

## Locked v1 spine (immutable identifiers)
1. **KALLPA** — Root — L1 energy/compute dispatch
2. **YACHAY** — Sacral — L2 retrieval (codex + PIRWA)
3. **RIMAY** — Solar plexus — L3 propose
4. **YUYAY** — Heart — L4 critique (9-axis gate)
5. **RUWAY** — Throat — L5 commit + receipt
6. **NAWI** — Third eye — Boundary-in (TINKUY toolcall)
7. **HATUN** — Crown — Boundary-self (continuum_hash + HUKLLA gate)

**Infrastructure (NOT chakras):** AMARU (scheduler) · YAWAR (bus) · SENTRA (immune).

## What the pods proposed (wandered names)
- MUSQUY pod: invented MUNAY / LLANK'AY / KAWSAY / QAWAY. These are real Quechua words (love / work / life / seeing) but they were not in our locked spine. Pod was being creative; I gave it that latitude. Roll back.
- TUKUY pod: put SENTRA and YAWAR in the chakra sequence. Category error — they're infrastructure, not chakras.

## v3 spine — additions only, no renames

### Ascending (propose phase, AMARU rises)
1. **KALLPA** — root — energy budget for this tick (NINA dispatch)
2. **YACHAY** — sacral — retrieve relevant codexes + features
3. **MUSQUY** — between sacral and solar (NEW, position 2.5) — cheap simulate of K candidate proposals; NINA-gated; READ-ONLY against YAWAR; ≥3× cheaper than RIMAY else aborts
4. **RIMAY** — solar — propose chosen action from MUSQUY-surviving candidates
5. **YUYAY** — heart — 9-axis critique gate

### Boundary (NAWI fires when external input/tool needed at any ascending point)
6. **NAWI** — third eye — TINKUY toolcall when proposal/critique needs external read

### Descending (commit phase, AMARU descends)
7. **RUWAY** — throat — commit + receipt to YAWAR
8. **TUKUY** — between throat and crown (NEW, position 7.5) — actions-OUT to external systems (HTTP/DB/Slack/ERP/edge); SENTRA inspects egress; never writes YAWAR directly (receipts flow back via SENTRA→RUWAY next tick)
9. **HATUN** — crown — final continuum_hash + HUKLLA allegiance gate

**Total: 7 original chakras + 2 new (MUSQUY, TUKUY) = 9-position spine.** AMARU still serpentines: ascend 1→5 with optional NAWI sidestep, then 5→9 descend (or 9→1 full cycle if cycling continuously).

## Maxwell rigidity check on v3 spine
- j = 9 chakras (nodes)
- For rigid M=0: b = 3(9) − 6 = 21 edges required
- Sequential serpent only: 8 edges → M = 8 − 27 + 6 = −13 (very floppy)
- **Need 13 additional bracing edges.** Candidates inherit from chakra design rules doc + new MUSQUY/TUKUY:
  - MUSQUY ↔ YUYAY (critique can request re-simulate)
  - MUSQUY ↔ YACHAY (simulate consults codex)
  - MUSQUY ↔ KALLPA (simulate pays energy)
  - TUKUY ↔ RUWAY (only committed state can be acted on)
  - TUKUY ↔ HATUN (HUKLLA sovereignty over outbound)
  - TUKUY ↔ NAWI (action-out symmetric to action-in)
  - Plus 7 bracing edges from chakra_design rules doc (root↔crown, heart↔throat, etc.)
- Total: 21 edges → M = 0. Rigid. Locked when wiring file written.

## What the pods built that we KEEP (honest credits)

### MUSQUY (simulate chakra)
- Springboard: **open_spiel Apache-2.0** (DeepMind) + DSPy MIT + papers from Yao/Hafner/Fan/Gu-Su/Tang-Ellis
- Position: 2.5 in v3 spine
- File: `musquy_simulate_evolution/05_kernel.py` — 407 SLOC (this is more than D-SHORTEST-HONEST should allow; flag for compression review)
- Replay: `a56975eecc802375...` 5× identical PASS
- NINA gate: simulate η < commit η, else abort
- KAWSAY feedback: real outcomes flow back via YAWAR → MUSQUY cache

### TUKUY (action-out chakra)
- Springboard: **Temporal MIT** + Airflow Apache-2.0 + OpenTelemetry Apache-2.0 + Activepieces core MIT
- Rejected: n8n Sustainable Use License (verified raw LICENSE.md)
- Position: 7.5 in v3 spine (between RUWAY and HATUN on descent)
- File: `tukuy_action_evolution/05_kernel.py` — 162 SLOC (also above D-SHORTEST-HONEST line; review)
- Mocked replay: 3/3 PASS, continuum_hash byte-identical
- SENTRA egress: every outbound payload inspected before delivery
- Failures re-enter via SENTRA → RUWAY next tick (no direct YAWAR writes)

### QILLQA runtime (ontology layer, not a chakra — supports YACHAY)
- Springboard: **RDFLib BSD-3** primary + pyoxigraph Apache + pySHACL Apache + LinkML Apache
- 8 named devs with GitHubs (Mendel-Gleason / Feeney / Pellissier-Tanon / Lindström / Grimnes / Seaborne / Sirin)
- Build step: live mutable schema → LinkML YAML → `gen-python` → frozen `codex.py` per chakra (preserves D-CODEX-IN-KERNEL)
- Maxwell on definitional schema: M ≥ 6, over-constrained, correct for ontology

### Docling (PDF ingestion, replaces Marker)
- License: **MIT** (IBM Research)
- Used inside QILLQA build pipeline + YACHAY codex ingestion
- Marker GPL-3.0 isolated as dev-only subprocess, never imported

## What I'm NOT doing without confirm

- NOT writing the 13 new bracing edges into a `chakana_wiring.py` until you confirm v3 spine
- NOT compressing MUSQUY (407 SLOC) or TUKUY (162 SLOC) toward D-SHORTEST-HONEST until you confirm spine
- NOT pushing anything to GitHub
- NOT minting any DOI

## Three decisions awaiting confirm
1. **v3 spine accepted?** 7 originals + MUSQUY + TUKUY = 9 positions
2. **D-SHORTEST-HONEST compression pass on MUSQUY/TUKUY?** They're large because pods didn't compress; not a doctrine failure, just incomplete work. ~30 min of compression each.
3. **Wire the 13 bracing edges?** Required to hit Maxwell M=0 on v3 spine.
