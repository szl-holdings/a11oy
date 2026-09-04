# PAYLOAD-1 — a11oy Frontier handoff

Measured 2026-09-04T23:13Z. Not LIVE. Λ = Conjecture 1.

## Placement (chosen)

| Surface | Role | Decision |
|---|---|---|
| https://a-11-oy.com | Product origin | **Keep Holo / Frontier / Command here** |
| Space `SZLHOLDINGS/a11oy` | Canonical runtime | **Only Space.** No second Space. |
| https://a11oy.net | Proof origin | RECORD only. Not a product door. |
| `szl-holdings/a11oy` | Source of truth | Land operator payload under `docs/payload/` |
| `SZLHOLDINGS/holographic` | Capacity donor | Not a product door |

Do not invent a Hub Space for this thread. Tabs already live on a-11-oy.com.

## Live measure

- Runtime SHA: `6acc6c752262`
- GitHub default-branch observe: UNAVAILABLE this cut (identity field empty)
- `equivalence_state`: **UNAVAILABLE**
  - reason: `ESTATE_MANIFEST_DOES_NOT_BIND_SOURCE_TO_HF_OVERLAY_AND_RUNTIME_ARTIFACT`
- `claim_gate`: **FAILED_CLOSED** / `EXACT_SOURCE_RUNTIME_BINDING_UNAVAILABLE`
- observation: **BLOCKED** (`github_inventory_unavailable`)
- locked formulas: 8
- Routes 200: `/` `/holographic` `/frontier-now` `/console`
- `/payload` is not a product route (404/absent on purpose)

Equal git SHA is **not** MATCH. MATCH needs GitHub main + HF overlay + artifact digest.

## Doctrine

- Fail closed. Observe DRIFT. Never paint green.
- No product-door rewrite. Auto-closer kills #1475/#1481-class PRs.
- `/run` and `/eval` stay 404.
- Do not merge red / draft / BLOCKED.
- Do not write Hub from a chat plane. `hf-sync.yml` is the sole publisher.
- Do not second-dispatch hf-sync if a tip run is already queued.

## Thread that landed

- Public nav: Holo → `/holographic`, Frontier → `/frontier-now`, Command CTA → `/console`
- Command-bar chips: `a11oy#1882` MERGED
- Identity observer: `a11oy#1852` MERGED (public GitHub main vs runtime)
- Duplicate Command tab hygiene: `a11oy#1881` MERGED

## Next honest move

1. `python3 payload.py`
2. If hf-sync is already running for the tip SHA — wait.
3. Squash only CLEAN PRs.
4. Do not stamp operational until three-element bind is MATCH and claim gate opens.
