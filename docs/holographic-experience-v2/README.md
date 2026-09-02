# A11oy Holo-Constellation v2

A11oy Holo-Constellation is the shared visual and interaction system for the SZL Holdings product estate. It is designed to make every application unmistakably related while preserving a separate identity, information architecture, motion language, and operational density for each surface.

## Benchmark synthesis

The system studies six reference categories and converts them into original SZL design principles. It does not reproduce reference-company layouts, source code, visual assets, trademark treatments, illustrations, or animations.

| Reference | Principle retained | SZL-original expression |
|---|---|---|
| Anthropic | editorial clarity, calm hierarchy, readable long-form explanation | humanist display scale, measured whitespace, evidence-first prose, restrained transition timing |
| True Anomaly | mission-control framing, orbital depth, cinematic spatial storytelling | governed orbit paths, command constellations, route wakes, and domain-specific instrument fields |
| BOSS Technology | premium enterprise storytelling and modular product/service architecture | outcome-led sections, decisive product narratives, polished handoffs, and bespoke vertical compositions |
| NVIDIA | performance materiality, dimensional product reveals, high-contrast technical confidence | dependency-free holographic surfaces, specular light, GPU-inspired depth cues, and strict rendering budgets |
| New Relic | operational density, observability legibility, signal/state/action hierarchy | evidence ribbons, signal chips, anomaly pulses, confidence labels, and action-oriented command views |
| Bricklayer AI | agentic security workflows, visible role boundaries, modular automation | governed agent swarms, explicit human/machine handoffs, proof-chain states, and fail-closed action framing |

## The SZL visual thesis

**One constellation. Many instruments.**

The shared layer governs only the things that should be consistent:

- ecosystem navigation and product/proof/source handoffs;
- typography rhythm, focus behavior, touch targets, safe areas, and breakpoints;
- material rules for glass, depth, borders, shadows, and evidence labels;
- motion budgets, reduced-motion behavior, visibility throttling, and low-power modes;
- honesty boundaries distinguishing decorative motion from measured telemetry.

Everything else belongs to the product:

- Lyte behaves like a living signal observatory;
- Vessels behaves like a bathymetric fleet instrument;
- Terra behaves like a topographic parcel intelligence system;
- Aegis behaves like a threat lattice and shield console;
- PRISM Counsel behaves like a case timeline and evidence facet system;
- Carlota Jo behaves like a premium editorial advisory environment;
- Nexus behaves like a connected integration field;
- Factory behaves like an artifact assembly line;
- Ouroboros behaves like a recursive research instrument;
- KHIPU behaves like woven proof and knot topology;
- Killinchu behaves like a governed agent swarm;
- a11oy.net behaves like a restrained evidence vault, not a duplicate of the product site.

## Core assets

- `console/assets/szl-holo-v2.css` — materials, motifs, accessibility, responsive behavior, and reusable primitives.
- `console/assets/szl-holo-v2.js` — deterministic theme resolution, shared navigation, pointer light, scroll progress, panel enhancement, and low-power controls.
- `theme-registry.json` — canonical surface identities and the shared contract.
- `rollout-state.json` — source-binding state and honesty boundary.
- `scripts/rollout_holographic_experience_v2.py` — idempotent source binder.
- `tests/test_holographic_experience_v2.py` — offline contract tests.

## Progressive enhancement

The system remains usable when JavaScript is unavailable. Native content and product interactions are not replaced. CSS creates a coherent base, while JavaScript adds:

- deterministic route identity;
- a keyboard-accessible ecosystem rail;
- decorative pointer light for fine-pointer devices;
- requestAnimationFrame-throttled scroll progress;
- visibility, reduced-motion, and save-data controls;
- conservative panel enhancement for recognized card structures.

No network fetch, analytics, cookies, local storage, session storage, runtime CDN, or remote font dependency is introduced.

## Performance contract

The experience is intentionally bounded:

- core CSS: no more than 24 KiB gzip;
- core JavaScript: no more than 18 KiB gzip;
- no timer loop;
- pointer and scroll work is requestAnimationFrame-throttled;
- decorative motion stops or simplifies under reduced motion, save-data, forced colors, and constrained viewports;
- continuous animation layers are limited;
- raw assets are capped in CI to prevent accidental growth.

## Accessibility contract

Every participating surface must preserve:

- 44px minimum interactive targets;
- visible focus with sufficient contrast;
- Escape-key closure for mobile navigation;
- skip navigation where a main landmark exists;
- safe-area padding on mobile devices;
- reduced-motion, increased-contrast, forced-colors, and print modes;
- no horizontal page overflow at 320, 360, 390, 768, 1024, 1440, and 1920 pixel widths.

## Truth contract

Holographic effects are decorative. They do not establish that an agent is active, a model is trained, a workflow is healthy, a threat exists, or a metric has been measured. Runtime claims remain bound to existing honesty, readiness, evidence, and receipt endpoints.

## Rollout sequence

1. Merge the assets, registry, tests, and controllers through protected main.
2. The one-shot rollout workflow produces `feat/holographic-experience-v2-bound` with exact HTML bindings.
3. Review and merge the binding branch through normal checks.
4. Allow the canonical Hugging Face publisher to deploy source-owned Spaces.
5. Verify the two domains and each Space at the required viewports.
6. Promote product-specific compositions only after their native frontend tests pass.

## Product-specific next layer

The shared shell is the foundation, not the finished product design. Each flagship application should then receive a bespoke composition pass:

- domain-specific hero and primary workflow;
- bespoke visualization grammar;
- meaningful empty, loading, blocked, degraded, and receipt states;
- real data bindings with provenance and confidence;
- product-specific mobile navigation and keyboard flows;
- visual regression baselines and performance traces.

That second layer is how the estate becomes state of the art without becoming a collection of identical neon dashboards.
