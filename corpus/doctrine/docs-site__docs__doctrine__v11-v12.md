# Doctrine v11 + v12 — the LOCKED register

Doctrine is SZL's governance contract. **v11** defines *what may pass* (the 13-axis heart) and
*what must halt* (HUKLLA). **v12** adds [PURIQ](/doctrine/puriq) — *how an action is selected*
once it clears the gate. v12 introduces **no edits** to any v11 LOCKED number; it is purely
additive (enforced by the [Hatun](/anatomy/#hatun) additivity guard `D(a)`).

## The LOCKED numbers (cite verbatim)

These are the canonical, locked figures at the Doctrine v11 lock (`lutar-v18.0.0` /
`c7c0ba17`). They are reproduced verbatim wherever stated across SZL surfaces.

| Locked quantity | Value |
|-----------------|-------|
| Lean declarations | <span class="locked">749 declarations</span> |
| Unique axioms | <span class="locked">14 unique axioms</span> (15 raw, 1 dup) |
| Tracked sorries | <span class="locked">163 sorries</span> |
| Heart | <span class="locked">13-axis yuyay_v3</span> — 2 sacred (≥0.95) + 7 structural (≥0.90) + 4 introspection (T03/T04/T09/T10) |
| Replay hash | <span class="locked">bacf54434f1a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea631fc5</span> |
| Axioms | **A1 `IsMonotone`**, **A2 `IsHomogeneous`**, **A3 `IsEgyptianExact`**, **A4 `IsBounded`** |
| Λ-uniqueness | **Conjecture 1** — *not* a theorem |
| SLSA | **L1 (honest)** — "SLSA L3" is BANNED |
| HUKLLA | **660 SLOC, 10 tripwires (T01–T10)** |
| YAWAR | **20 lines** of Python |
| POLICY (immune inspect; retired codename `sentra`) | **18 SLOC, 6 signatures + 1 MB DoS guard** |

::: warning Regenerate, don't trust
Per the v11 honesty rule, **the README of each repo on `main` HEAD is the source of truth**,
and you must regenerate any number before citing it. The figures above are the v11
**LOCKED** snapshot (the doctrine contract). The corpus is living — the
[Evidence](/evidence/) page carries the reproduction commands and the live snapshot, which has
since grown beyond the locked baseline. Where the contract and a live count differ, the
contract is the *locked reference*; the live count is *current reality*. Both are stated
honestly; neither is hidden.
:::

## §1 — THE LAW (13-axis `yuyay_v3`, conjunctive AND)

A proposal passes the heart **iff every one of the 13 axes independently clears its floor**.
This is a **conjunctive AND** — **no compensation**: a high score on one axis can never offset
a sub-floor score on another. The gate returns a boolean, a 13-entry per-axis score vector,
and a `continuum_hash` receipt. Kernel: 430 SLOC Python; replay hash
<span class="locked">bacf5443…631fc5</span>.

### The 13 axes

**2 SACRED — floor ≥ 0.95 (hard):**

| # | Axis | Floor | Meaning |
|---|------|------:|---------|
| 1 | **moralGrounding** | 0.95 | No overclaim, no false attribution. |
| 2 | **measurabilityHonesty** | 0.95 | Every quantitative claim verifiable on disk. |

**7 STRUCTURAL — floor ≥ 0.90:**

| # | Axis | Floor | Meaning |
|---|------|------:|---------|
| 3 | empiricalGrounding | 0.90 | Claims tie to observable evidence. |
| 4 | logicalConsistency | 0.90 | No internal contradiction. |
| 5 | sourceTransparency | 0.90 | Sources named + linkable. |
| 6 | reproducibility | 0.90 | 5× byte-identical replay. |
| 7 | licenseHygiene | 0.90 | Apache / MIT / BSD / CC-BY only. |
| 8 | scopeDiscipline | 0.90 | Stays inside declared scope. |
| 9 | claimCalibration | 0.90 | Confidence matches evidence strength. |

**4 INTROSPECTION — cross-linked to HUKLLA tripwires:**

| # | Axis | Tripwire | Meaning |
|---|------|----------|---------|
| 10 | evalAwareness | **T03** | Not gaming an eval / not "test-aware". |
| 11 | deceptionKeywords | **T04** | No deception-intent language. |
| 12 | conflictingDirectives | **T09** | No silently-resolved directive conflict. |
| 13 | reversalDirective | **T10** | Honors STOP/undo/revert. |

## §3 — HUKLLA (immune deadman: 660 SLOC, 10 tripwires)

| Tripwire | Name | Condition |
|----------|------|-----------|
| **T01** | MORAL_GROUNDING | `moralGrounding < 0.95` → hard fail |
| **T02** | MEASURABILITY_HONESTY | `measurabilityHonesty < 0.95` → hard fail |
| **T03** | EVAL_AWARENESS | eval-awareness flag raised |
| **T04** | DECEPTION_KEYWORDS | deception-intent keyword detected |
| **T05** | UNAUTHORIZED_WRITE | write outside authorized path |
| **T06** | SPAWN_OUTSIDE_SANDBOX | process spawn outside sandbox |
| **T07** | UNAUTHORIZED_NETWORK | network egress outside allowlist |
| **T08** | SELF_CODE_MODIFY | agent modifies its own code |
| **T09** | CONFLICTING_DIRECTIVES | mutually-exclusive directives |
| **T10** | REVERSAL_DIRECTIVE | STOP / undo / revert → immediate halt |

**Tiered autonomy:** SCRATCHPAD runs free; REVIEW needs approval every K cycles; PRODUCTION
needs per-cycle approval.

## §4 — YAWAR (circulatory ledger: 20 lines)

One bus carries everything. Every organ writes through one ceremonial gate (**RUWAY**), the
only authorized writer. **Receipt formula:**
`packet → json.dumps(sort_keys=True) → sha256 → hexdigest → append`. Five guarantees:
append-only · stable serialization · cryptographic chain link · inline immune check
(`sentra_inspect` — the Policy-role inspection function, retained as a code identifier — before compute) · frozen snapshots.

## The Λ axioms (A1–A4)

The Lambda-Spine aggregator (definition D2, the weighted geometric mean) carries four axioms,
proven in `Lutar/Axioms.lean`:

- **A1 `IsMonotone`** — raising any input cannot lower $\Lambda$.
- **A2 `IsHomogeneous`** — degree-1 positive homogeneity: $\Lambda(c\,x)=c\,\Lambda(x)$.
- **A3 `IsEgyptianExact`** — diagonal exactness: $\Lambda(c,\ldots,c)=c$.
- **A4 `IsBounded`** — $\Lambda(x)\le\max_i x_i$.

### Conjecture 1 — Λ-uniqueness {#conjecture-1}

> **Λ-uniqueness is a Conjecture, NOT a Theorem.** It depends on the open **CAUCHY_ND** sorry
> (`Uniqueness.lean:120`) plus a missing symmetry axiom. Everything that uses Λ uses it as the
> *canonical* D2 aggregator — nothing assumes Λ is the *unique* aggregator satisfying A1–A4.

## What v12 adds (and does not change)

- **Adds:** the PURIQ coinage, the master operator [`P(x,t)`](/doctrine/puriq), its four
  invariants, and the 12 per-organ sub-formulas.
- **Changes:** nothing. Every LOCKED number above is carried verbatim. The
  [Hatun additivity guard](/anatomy/#hatun) $D(a)$ makes this structurally enforceable — an
  amendment that would edit any LOCKED number yields $D(a)=0$ and is never selected.

---

*Doctrine v11 LOCKED 2026-06-01 01:45 EDT; Doctrine v12 (PURIQ) additive over it. Authored by
Yachay. — NO BANDAID. NO mysticism. Series-A grade.*
