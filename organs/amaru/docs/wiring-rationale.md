# WIRING_RATIONALE.md — CHAKANA v3 Spine Canonical Wiring

## Maxwell Rigidity Result

| Parameter | Value |
|-----------|-------|
| Nodes (j) | 9     |
| Edges (b) | 21    |
| M = b − 3j + 6 | **0** |
| Verdict | **PASS — isostatic (minimally rigid)** |

---

## Directed vs. Undirected — Caveat

The Maxwell criterion (`M = b − 3j + 6 = 0`) is classically defined for **undirected** constraint graphs in structural mechanics (rigidity theory, Laman's theorem). Applying it to a **directed** graph is an architectural convention, not a formal proof of rigidity.

**Our choice: directed edges.**

AMARU is a directional cognitive pipeline; every edge carries a semantic flow direction (e.g., `KALLPA → YACHAY` means "energy primes retrieval", not the reverse). Collapsing that to undirected would erase architectural meaning.

**Mitigating convention:** The 21-edge count still satisfies `M = 0` whether treated as directed or undirected (same count). The directed interpretation adds semantic precision without breaking the numeric criterion. Any future formal rigidity proof should use the undirected projection.

---

## Bracing Edge Justifications (13 edges)

| # | Edge | Justification |
|---|------|---------------|
| 1 | KALLPA → HATUN | Sovereignty gate informs energy budget; the crown's continuum hash constrains how much energy the root may allocate in the next tick. |
| 2 | NAWI → RIMAY | Toolcall results (external reads) flow back into the proposal layer; NAWI's boundary data reshapes what RIMAY can assert. |
| 3 | NAWI → YUYAY | Toolcall results bypass proposal and pass directly to the critique gate; YUYAY can reject on boundary evidence alone. |
| 4 | YACHAY → YUYAY | Retrieved priors (codex facts) are checked at the heart gate; YUYAY validates proposals against memory, not just logic. |
| 5 | YACHAY → RUWAY | Codex updates that survive the gate are committed to the record via RUWAY; storage without serpent detour. |
| 6 | KALLPA → YUYAY | Energy budget gates critique cost; YUYAY cannot run expensive multi-pass critique if KALLPA signals low energy. |
| 7 | KALLPA → RUWAY | Commit action has an energy toll; RUWAY checks KALLPA's available budget before finalising any write. |
| 8 | HATUN → YUYAY | The HUKLLA continuum hash flows to the heart gate so YUYAY can validate proposals against the canonical sovereign state. |
| 9 | MUSQUY → YUYAY | If critique flags a simulation fault, YUYAY can request re-simulation; this edge carries the re-simulate signal. |
| 10 | MUSQUY → YACHAY | Simulation consults the codex mid-flight; intermediate simulation states pull from YACHAY to avoid stale priors. |
| 11 | MUSQUY → KALLPA | Simulation declares its energy cost upfront; KALLPA must acknowledge budget before MUSQUY proceeds. |
| 12 | HATUN → NAWI | Sovereignty governs the external boundary; HATUN authorises which reads NAWI may open, preventing unbounded toolcall escalation. |
| 13 | TUKUY → NAWI | Action-out is symmetric to action-in; an outbound action triggers the same boundary-crossing record in NAWI that an inbound toolcall would. |

---

## Edges Not Selected (and why)

| Candidate | Reason not chosen |
|-----------|------------------|
| YUYAY ↔ RUWAY (as brace) | Already Serpent-5; would be a duplicate. |
| TUKUY → HATUN (as brace) | Already Serpent-7; would be a duplicate — originally selected in error, replaced by HATUN→NAWI. |
| TUKUY ↔ SENTRA-egress | SENTRA is infrastructure, not a chakra node; excluded per task specification. |

---

## Full Edge List (21)

### Base Serpent (8)

| # | Edge | Role |
|---|------|------|
| S1 | KALLPA → YACHAY | Energy primes retrieval |
| S2 | YACHAY → MUSQUY | Codex feeds simulation |
| S3 | MUSQUY → RIMAY | Simulation drives proposal |
| S4 | RIMAY → YUYAY | Proposal enters critique gate |
| S5 | YUYAY → RUWAY | Gate approval triggers commit |
| S6 | RUWAY → TUKUY | Commit hands off to action-out |
| S7 | TUKUY → HATUN | Outbound action crowned by sovereignty |
| S8 | HATUN → KALLPA | Cycle close — sovereign hash seeds next tick |

### Bracing (13)

| # | Edge |
|---|------|
| B1 | KALLPA → HATUN |
| B2 | NAWI → RIMAY |
| B3 | NAWI → YUYAY |
| B4 | YACHAY → YUYAY |
| B5 | YACHAY → RUWAY |
| B6 | KALLPA → YUYAY |
| B7 | KALLPA → RUWAY |
| B8 | HATUN → YUYAY |
| B9 | MUSQUY → YUYAY |
| B10 | MUSQUY → YACHAY |
| B11 | MUSQUY → KALLPA |
| B12 | HATUN → NAWI |
| B13 | TUKUY → NAWI |
