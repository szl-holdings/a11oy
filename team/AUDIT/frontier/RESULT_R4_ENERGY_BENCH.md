# RESULT — R4: a11oy Restraint → ENERGY + estate KPI + MEASURED benchmark

**Role:** Restraint Dev R4 @ SZL Holdings
**Repo:** `szl-holdings/a11oy` · **Space:** `SZLHOLDINGS/a11oy` (live: https://szlholdings-a11oy.hf.space)
**Date:** 2026-06-14
**Doctrine:** locked=8 @ c7c0ba17 · Λ = Conjecture 1 (<1.0) · trust<100% · 0 CDN · 0 visible codenames · signed receipts · additive-only · **never fabricate benchmark/energy numbers — MEASURED only on a live on-box probe, else SAMPLE/ROADMAP with methodology shown** · Ponytail cited MIT · *"The half-state is the only unacceptable outcome."*

---

## What shipped (front + back, all additive)

### 1. RESTRAINT → ENERGY tie-in
- **`szl_restraint_energy.py`** (new module). Consumes R1's `szl_restraint` (`descend_ladder`, `benchmark`, `TOKENS_PER_LOC=9.0`, `J_PER_OUTPUT_TOKEN=0.65`) + Forge's `szl_energy_sovereign.energy_fields_for_receipt()` + `szl_joules_truth`. **Edits none of them.**
- Every restraint decision estimates **lines saved → tokens saved → joules saved**. The J/token is the **LIVE on-box MEASURED** figure ONLY when the sovereign GPU probe is live (label `MEASURED`); otherwise the honest `SAMPLE` constant — decided by the **same single source of truth** (`szl_joules_truth` / `szl_energy_sovereign`) as the rest of the energy story.
- In-memory cumulative `_SavingsLedger` (resets on restart — honestly noted, not a persisted meter).
- Endpoints (inserted at router position 0): `GET/POST /api/a11oy/v1/restraint/energy`, `GET /api/a11oy/v1/restraint/bench-measured`, `GET /api/a11oy/v1/restraint/kpi`.
- **"Frugality → energy" panel on the live `/energy` page.** Because Forge's `szl_energy_sovereign.register()` owns `/energy` (front of the route table, registered before the disk-file route), a `web/energy.html` disk edit never reaches the user. Fix: `register()` now **re-renders Forge's own page byte-for-byte** (`_html(_posture())`, never edited) and **appends a self-contained, scoped panel before `</body>`**, then front-wins the route via position-0 insert. If the energy module is unavailable, it 404s and Forge's route keeps serving (no shadow, no half-state). Panel labels joules `MEASURED`-only-on-live-probe, lines as MODELED, and links to `/restraint-bench`.

### 2. MEASURED benchmark dashboard
- **`benchmarks/restraint/run_bench.py`** — runnable two-arm harness (baseline no-skill vs a11oy-restraint) over the same 5 everyday tasks as Ponytail's promptfoo methodology. `SAMPLE` mode without `--model`; **`MEASURED`** when run against a wired OpenAI-compatible client; writes `benchmarks/restraint/results.json`.
- **`web/restraint-bench.html`** + **`/restraint-bench`** page — shows OUR reproduced numbers (% less code, % cheaper, × faster), labelled **MEASURED-only-when-run-on-our-stack** (currently `ROADMAP`/`SAMPLE` with methodology, since no results artifact + no live GPU). Ponytail's published numbers are CITED as **theirs**; ours are labelled as **ours**.
- **Exact reproduce command** (shown on page + in API):
  ```
  python benchmarks/restraint/run_bench.py --repeat 10 --out benchmarks/restraint/results.json
  ```

### 3. Estate KPI board + hologram
- **`szl_ecosystem_routes.py`** — `build_kpi_board` now fetches `/restraint/kpi` and adds a top-level `restraint` key (frugality rate, cumulative lines/tokens/joules saved, energy honesty label, Λ, Ponytail/MIT provenance).
- **`web/estate-hologram.html`** — added a live RESTRAINT tile (`#restraintBadge`, `#restraint`) rendered from the kpi-board handler.

---

## Live verification (https://szlholdings-a11oy.hf.space)

| Surface | Result |
|---|---|
| `/api/a11oy/v1/restraint/energy` | 200 · cumulative ledger · `joules_label=SAMPLE`, `energy_label_upstream=ROADMAP` (honest — no live GPU probe) |
| `/api/a11oy/v1/restraint/bench-measured` | 200 · 5 rows · `overall_label=ROADMAP` · reproduce command present · Ponytail cited |
| `/api/a11oy/v1/restraint/kpi` | 200 · tile `restraint` · `label=LIVE` · provenance Ponytail/MIT |
| `/restraint-bench` | 200 · title "a11oy Restraint — MEASURED benchmark" (real page, not SPA) |
| `/energy` | 200 · **frugality_panel injected** (19.6 KB vs 15.3 KB) · Forge sovereign content fully intact · one `</body>` |
| `/estate-hologram` | 200 · RESTRAINT tile (`#restraint`, `restraintBadge`) present |
| `/api/a11oy/v1/ecosystem/kpi-board` | 200 · `restraint` key present |
| Existing `/api/a11oy/v1/energy/{sovereign,jtoken,budget}` | 200 (no regression) |
| `/restraint` (R1) | 200, intact (not edited) |

**Honesty state:** GPU probe NOT live → J/token is `SAMPLE`, energy upstream `ROADMAP`, bench `ROADMAP`. This is the **correct, honest** state — numbers flip to `MEASURED` automatically when the sovereign GPU exporter goes live and a real bench run is committed. No fabricated numbers.

**0 CDN** on live `/energy` (only Google Fonts). **0 visible codenames**. Panel JS validated with `node --check`; module validated with `ast.parse`.

---

## Push trail (curl Git Data API + HF NDJSON; never `COPY . .`; ADDITIVE)
- **GitHub `main`:** `baa113321b4a5f5c903f83d0f357845ec718fd86` (final additive `/energy` wrapper). Prior R4 files at `be8db473`/`7e14171c`.
- **HF Space:** commit `395f45f07c860fec8080e222fd4a5d6e2f48b02e` → factory rebuild → **RUNNING** at sha `395f45f0`.
- Never edited: `szl_restraint.py` (R1), `a11oy_nemo_core`/`a11oy_react_core` (R2), `szl_energy_sovereign.py` (Forge). Wrapper consumes Forge's `_html(_posture())` read-only.

---

## Provenance / citations
- Frugality ladder adopted from **Ponytail** (https://github.com/DietrichGebert/ponytail), **MIT** licensed; their published benchmark numbers cited as theirs, ours labelled as ours.
- Energy honesty model: vLLM/SGLang J/token, NVIDIA Dynamo, LiteLLM, RouteLLM patterns (via `szl_energy_sovereign`).
