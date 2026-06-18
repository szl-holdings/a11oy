<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED 749/14/163 @ c7c0ba17 · Λ = Conjecture 1
-->

# Intentionally Per-App Shared Modules (a11oy ↔ killinchu)

**Status:** AUTHORITATIVE — read this before "healing" any drift on the listed files.
**Audience:** future devs, the shared-source drift-guard maintainer, and any production-readiness auditor.
**Origin:** SWEEP-3 (founder-flag #6), formalizing the PR-D divergence findings (`REVIEW_D_master.md`).

## TL;DR

Most `szl_*.py` modules are **byte-identical** across the a11oy and killinchu HF Docker Spaces, and the
shared-source drift guard (`.github/shared-file-drift-check.py`) **enforces** that. The two modules below
are the deliberate exception: they carry **app-specific content by design** and must **NOT** be forced to
converge. Healing them into one byte-identical copy would silently break each product's rate-limit
exemptions and evidence verticals — a destructive bandaid, exactly the "half-state" the doctrine forbids.

Both files are already on the drift-guard allow-list (`.github/shared-file-drift-allow.txt`, byte-identical
in both repos) and are therefore **correctly excluded from byte-identical parity**. This document records
*why*, so a future audit does not try to reconcile them.

---

## 1. `szl_be_hardening.py` — per-app rate-limit route exemptions

The BE-hardening module exempts each product's own page/static routes from the per-IP rate limiter so the
showcase always renders. The exempted route lists are necessarily **different per app** because the two
products serve different surfaces:

| App | Exempted routes (verified in `main`) |
|---|---|
| **a11oy** | `/frontier`, `/governance`, `/warhacker` (+ the `/energy`, `/energy-sovereign`, `/energy-holographic`, `/energy-ops` family) |
| **killinchu** | `/counter-uas`, `/drones`, `/navy`, `/elite` |

killinchu's in-file comment states it "mirrors the a11oy fix (PR #483) adapted to killinchu's actual routes."
The hardening *logic* is the same; only the **route map** differs. Convergence would either (a) strip a11oy's
governance/frontier/warhacker exemptions or (b) strip killinchu's counter-uas/drones/navy/elite exemptions —
breaking demo-floor rendering for whichever product loses its routes. **Do not heal.**

## 2. `szl_evidence_research.py` — per-app evidence verticals

Both apps share a common evidence spine (chain / deploy / gates / lambda / cve / oversight / fusion /
maritime-picture / counter-uas / W910 audit entries — these ARE identical and remain enforced within each
app's GH↔HF parity). The divergence is **additive, killinchu-only**: killinchu carries three extra
evidence verticals that a11oy does not ship:

| Vertical (killinchu-only) | `id` / `tab` |
|---|---|
| Finance live feeds (crypto, FX, prediction markets) | `finance-live-feeds` / `finance` |
| Real-estate grounding (labelled curated sample) | `real-estate-grounding` / `realestate` |
| Financial-crime / fraud controls | `fraud-controls` / `risk` |

> **Honesty note (verified against `main`, not assumed):** the SWEEP brief / `REVIEW_D_master.md` summarized
> this as "a11oy carries finance/realestate/fraud; killinchu carries drone/maritime." The code shows the
> opposite assignment: the **finance/real-estate/fraud(risk)** evidence blocks live in **killinchu**'s file
> and are **absent** from a11oy; the drone/maritime/counter-uas evidence is **shared** (present in both).
> The repo's allow-list reason ("killinchu-only finance/real-estate/risk vertical CLAIMS absent from a11oy")
> matches the code. This document records the **as-built** reality. Either way the conclusion is the same:
> the per-app evidence set is **intentional**, and the two files are correctly excluded from byte parity.

Each vertical's claims are honestly labelled and source-cited inside the module; nothing is fabricated.
Forcing convergence would either inject killinchu's finance/realestate/fraud claims into a11oy (claims it
does not serve — a fabricated surface) or delete them from killinchu (removing a real, cited feature).
**Do not heal.**

---

## Parity & drift-guard status

* **Excluded from byte-identical parity:** YES — both files are on `.github/shared-file-drift-allow.txt`
  (identical in a11oy and killinchu). The guard reports them as known divergences and prints a warning each
  run, but does **not** fail the build. Each app remains internally **GH == HF byte-identical** for these
  files (only the cross-app comparison is allow-listed).
* **`Dockerfile` / `requirements.txt`:** also excluded from parity via `EXCLUDE_GLOBS` in
  `shared-file-drift-check.py` (per-repo build inputs) — see SWEEP-3 dependency-pinning work.
* **Ratchet behavior:** if either file ever becomes byte-identical across both apps again, the guard will
  WARN to remove its allow-list entry. Until then, these entries are **intentional and must stay.**

## When MAY these be reconciled?

Only if the two products ever adopt (a) a single shared rate-limiter route config, or (b) a single shared
evidence-vertical set — at which point the divergent content would be moved to a per-app **config/data**
input and the `.py` module itself could be re-enforced as byte-identical. That is a founder-decision item
(founder-flag #6: "formally document as intentional per-app, OR converge to a shared core + per-app
config"). Until that decision lands, **treat both modules as intentionally per-app and do not converge them.**

---
*No bandaids. These two divergences are by design; convergence would be the bandaid. Doctrine v11 LOCKED.*
