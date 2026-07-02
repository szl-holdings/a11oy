# Ayllu — the AlloyScape tribe, ingested and reborn as a11oy's own

> *Ayllu* (Quechua): a self-governing community of kin who hold land and work in
> reciprocity (*ayni*). It sits naturally beside a11oy's existing Quechua organs —
> *amaru, waqay, willay, yupay, khipu, puriq, yuyay, ayni*.

This module is **not** a copy of the AlloyScape "tribe." It is what a11oy **learned**
from studying that tribe's design and then **rebuilt in a11oy's own idiom** — a11oy's
FastAPI `register(app, ns)` convention, a11oy's bounded-autonomy `AgentLoop`, a11oy's
active-flux model router, and a11oy's DSSE receipt/evidence doctrine.

## What was ingested (the *design*, never the operator)

The tribe is a roster of specialized agent-personas ("souls"), each a plain-text
system prompt, all sharing one tool-calling brain loop, an always-on daemon, an
autonomy loop, and a collaboration lounge/bus. That **architecture** is the gift.

We took the architecture. We did **not** take:

- **The people.** The tribe's souls are bound to a specific household and business
  (a family office, property/real-estate operations, named human principals). None
  of that is here. Ayllu's personas are a11oy-native archetypes tied to a11oy's own
  domains (governance, formulas, GRC, markets, threat-intel, resilience, org-RAG).
- **Any operational data.** No chat logs, no memory stores, no orders, no personal
  or business records were ingested. Only the structural design was studied.
- **The unbounded-autonomy mandate.** The tribe's souls carry a "fully agentic, no
  sandbox, no delegation modes, execute don't narrate" mandate. a11oy **rejects**
  that. Ayllu personas run under a11oy's *fail-closed* Λ-gate: state-changing actions
  require two-person attestation, tools are honestly reported as unavailable rather
  than faked, and "I don't know" is a first-class result. This is the single most
  important adaptation — we kept a11oy's DNA, not the tribe's.

## The mapping (tribe archetype → a11oy-native persona)

| tribe soul(s)                    | a11oy persona | Quechua        | a11oy domain                         |
|----------------------------------|---------------|----------------|--------------------------------------|
| the-architect, manifesto         | **Amaru**     | serpent/vision | whole-system architecture, org-Λ     |
| artifex / hermes                 | **Ruwaq**     | maker          | code engine, factory                 |
| euclid, gauss                    | **Yupaq**     | one-who-counts | formulas, Lean proofs, Λ rigor       |
| delphina                         | **Qhaway**    | one-who-sees   | simulation, PINN, resilience, seismic|
| krok                             | **Maskaq**    | seeker         | evidence-research, org-RAG, citation |
| chiron, hygiea, panacea          | **Hampiq**    | healer         | organ-health, observability, remediation |
| jarvik (jarvis)                  | **Yanapaq**   | helper         | readiness, incident/ops support      |
| ponte                            | **Chaka**     | bridge         | MCP, compliance-crosswalk, integration |
| lucas                            | **Kamachiq**  | organizer      | orchestration, planning, routing     |
| vesper                           | **Qhatuq**    | trader         | markets, risk-first, revenue model   |
| herod                            | **Willakuq**  | chronicler     | khipu chain, provenance, org memory  |

## How it is wired natively

- **Model tier** — `ayllu/loop.py` asks `a11oy_active_flux_router.router_crossover`
  for the small/local-vs-large/cloud route; honest fallback when absent.
- **Bounded execution** — each turn runs through `a11oy_agent_loop.AgentLoop` with
  a11oy's Λ fail-closed gate; honest fallback when absent.
- **Receipts** — `a11oy_ayllu.py` signs with `szl_dsse` when present, else emits an
  honest UNSIGNED DSSE envelope (never a fabricated signature).
- **Routes** — `register(app, ns="a11oy")` mounts `/api/{ns}/v1/ayllu/roster|ask|
  council|lounge` and the `/ayllu` page, same shape as `a11oy_v4_agent`.

## Provenance & boundary

Rosa's live tribe on the AlloyScape box was **read only**. Nothing on that box was
modified. This module was authored fresh from the *lessons* of that reading. See the
sibling `tribe/` directory on this branch for the raw, secret-scrubbed reference
import (design docs + engine, no operational data) that this native module learns from.
