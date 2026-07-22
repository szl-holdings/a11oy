> **Live service status:** the auto-generated, continuously-refreshed status board lives on the
> [`status` branch](https://github.com/szl-holdings/a11oy/blob/status/STATUS.md) and renders at
> <https://szl-holdings.github.io/a11oy/>. **This file is a hand-authored doctrine / proof-state
> snapshot**, not the live endpoint health board — the `status-page.yml` workflow no longer
> overwrites it.

# STATUS.md — a11oy (Governance Layer)

**Updated:** 2026-06-08
**Doctrine v11 — proof-carrying formula registry v1 — canonical locked count 5**

HF Space: <https://huggingface.co/spaces/SZLHOLDINGS/a11oy>

---

## Proof state (honest, never inflate)

- **LOCKED-PROVEN = EXACTLY 5** — F1, F11, F12, F18, F19. The canonical
  `formula_registry/formula-registry.v1.json` pins the evidence and source hashes.
  F4, F7, and F22 have source-present theorem work but remain **EXPERIMENTAL**;
  CI-green or source-present does not itself promote an entry into the locked set.
- **Λ (F23)** — unconditional uniqueness is machine-checked **FALSE** for A1–A5, so it stays
  **Conjecture 1**, unconditionally. We *have* proved the strongest axiom-free **conditional**
  uniqueness: slice-multiplicativity (separability) ⇒ Λ, machine-checked (Wave12), and as of
  Wave21 the conditional chain is axiom-clean end-to-end on its stated hypotheses. The
  `(C-order)` gap-shift ordering remains an **honest structural hypothesis** (documented, not faked).
- **Khipu Byzantine BFT safety** — **Conjecture 2**, open (a faulty organ can equivocate).

## Experimental · CI-green tier (separate from the canonical locked five — NEVER folded in)

- `main @ 880c803e` — Wave19 / 20 / 21 merged; Phase-1 stabilize gate cleared; CI
  (`lake build + numbers` + DCO + doctrine) green on main.
- 1323 declarations · 23 axioms (22 unique) · sorries_raw 307 · drift 307 / 254.
- All Wave19/20/21 theorems: `#print axioms ⊆ {propext, Classical.choice, Quot.sound}`;
  no `sorry`; no new axiom.

## What's Live

- **HF Space** — a11oy is deployed and operational on Hugging Face Spaces.
- **`/healthz`** — returns Doctrine v11 locked numbers (749/14/163) and service status.
- **`/sign`** — Wire D DSSE signing endpoint; Ed25519 signed receipts.
- **Λ-aggregator gate** — every request evaluated across Yuyay-13 axes before execution.
- **`/console` + `/viz/*`** — operator panel for receipt inspection and governance surfaces.
- **a11oy Code IDE** — live.
- **Wire D** — cross-cutting signing fabric live to all other flagships.
- **GitHub ↔ HF aligned** — a11oy 5/5, killinchu 9/9; UDS payload/mesh wired
  (`theorem_ref` + `lake_receipt`, honest).

## What's Experimental

- **Chain replay verification** — Khipu DAG chain anchoring is functional; full replay harness under development.
- **Multi-key rotation** — key rotation workflow documented but not yet automated.

## What's Deprecated

Nothing deprecated in this repo.

---

*Co-Authored-By: Perplexity Computer Agent*
*Doctrine v11 — locked-proven 749/14/163 — c7c0ba17 · Λ = Conjecture 1 · main @ 880c803e*
<!-- ci-retrigger 1648Z -->
