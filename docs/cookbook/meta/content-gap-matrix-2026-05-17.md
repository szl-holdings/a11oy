# Content Gap Matrix — workspace assets → GitHub repos

Generated 2026-05-17 17:00 EDT. State of the world after deep-zoom audit.

## Critical finding

The 5 specialized-agent repos (**amaru, terra, vessels, counsel, carlota-jo**) have **zero product content** — only hygiene scaffolding (LICENSE, README, CI). All the deep work (chakra wiring, anatomy, doctrine, master rollups) lives only in workspace.

The thesis IS on `ouroboros-thesis` (papers/v1-v13, docs/anatomy/, arxiv_pkg/, figures/, v2/) — that part you can see.
The anatomy bundle IS on `ouroboros` (docs/anatomy/) and `ouroboros-thesis` (docs/anatomy/) — also present.

What's missing is mostly the **specialized-agent spec content** for the 5 thin repos, plus a few index/rollup documents.

## Asset → Repo mapping (gaps only)

### amaru (currently 14 files, ALL hygiene)
- `field_meditation/amaru_sentra_chakras/00_PROPOSAL.md` → `docs/proposal.md`
- `field_meditation/amaru_sentra_chakras/02_PROPOSAL_CODEX_AND_FLOW.md` → `docs/codex-and-flow.md`
- `field_meditation/amaru_sentra_chakras/05_RECONCILIATION_v3_SPINE.md` → `docs/spine-reconciliation.md`
- `field_meditation/amaru_sentra_chakras/amaru_scheduler.py` → `src/amaru_scheduler.py`
- `field_meditation/amaru_sentra_chakras/yawar_bus.py` → `src/yawar_bus.py`
- `field_meditation/amaru_sentra_chakras/chakra_1_root/` → `src/chakras/chakra_1_root/` (full tree)
- `field_meditation/amaru_sentra_chakras/chakra_2_sacral/` → same
- `field_meditation/amaru_sentra_chakras/chakra_3_solar/` → same
- `field_meditation/maki_chaki_limbs_proposal.md` → `docs/maki-chaki-limbs.md`

### sentra (currently 26 files, has some content)
- `field_meditation/amaru_sentra_chakras/sentra_immune.py` → `src/sentra_immune.py`
- `field_meditation/amaru_sentra_chakras/03_TUPU_VERDICT.md` → `docs/tupu-verdict.md`
- `field_meditation/amaru_sentra_chakras/tupu_verify.py` → `src/tupu_verify.py`
- `field_meditation/amaru_sentra_chakras/tupu_replay_5x.py` → `src/tupu_replay_5x.py`

### terra, vessels, counsel, carlota-jo (each 14 files, hygiene-only)
These are placeholder repos. Add `docs/charter.md` describing each agent's specialized role. Pulled from session memory of agent specs.

### a11oy (currently 35 files, has src/)
- `a11oy/AGI_HORIZON.md` → on-repo (verify)
- `a11oy/BRAIN_V0_REPORT.md`, `BRAIN_V0_5_REPORT.md`, `BRAIN_V1_REPORT.md` → `docs/brain-reports/`
- `agentic_rag_research/99_synthesis_a11oy_rag.md` → `docs/rag-synthesis.md`

### ouroboros-thesis (currently 265 files — biggest repo, but missing master rollups)
- `innovations_master_thesis.md` → `docs/innovation-master.md`
- `moonshot_one_of_one.md` → `docs/moonshot.md`
- `sdk_innovation_memo.md` → `docs/sdk-innovation.md`
- `thesis/szl_thesis_exhaustive.md` → `papers/v13-exhaustive/exhaustive.md`
- `thesis/szl_thesis_exhaustive.pdf` → same dir, .pdf
- Per-chakra docs (1-7) → `docs/chakras/chakra_N_*.md`
- `field_meditation/hatun_body_graph_SOURCES.md` → `docs/anatomy/hatun-sources.md` (anatomy folder)

### szl-cookbook (currently 75 files, operational cookbook)
- `field_meditation/qillqa_runtime_evolution/06_unification_with_existing_chakras.md` → `recipes/chakra-unification.md`
- `field_meditation/_anatomy_full_body_v3_report.md` → `recipes/anatomy-build-report.md`

### szl-brand (currently 92 files, brand assets)
- Various JPG mockups in workspace root (01-a11oy.jpg, 02-sentra.jpg, etc.) → `mockups/` — VERIFY first if already present
- `posts/linkedin_brain.md`, `linkedin_wires.md`, `linkedin_full_body.md` (+PDFs) → `posts/`

### .github (org profile)
- Need `profile/README.md` for org landing page (verify whether present)

## What's NOT missing (your visible work IS on GitHub)
- Full thesis v1-v13 ✅ `ouroboros-thesis/papers/v*/`
- arXiv v2 package ✅ `ouroboros-thesis/arxiv_pkg/`
- Anatomy bundle (8 PDFs + builders + LinkedIn explainers) ✅ `ouroboros-thesis/docs/anatomy/` AND `ouroboros/docs/anatomy/`
- LinkedIn posts (brain/wires/full_body) ✅ `ouroboros-thesis/docs/anatomy/explainers/linkedin/`
- LinkedIn PDFs ✅ same dir
- Runtime packages (lambda-gate, bekenstein, category, closure, glr, types) ✅ `ouroboros/runtime/`
- a11oy core, bot-reviewer, formulas, MCP server ✅ `ouroboros/agentic/`
- Lutar Lean formalization ✅ `lutar-lean/Lutar*.lean`
- TH8 Lean v2 skeleton ✅ `lutar-lean/TH8/lean_v2/` AND `ouroboros-thesis/arxiv_pkg/ancillary/`
- Trust deposit (E4 codex run) ✅ `szl-trust/runs/`
- Innovation heatmap figures ✅ `ouroboros-thesis/figures/09_innovation_heatmap.*`

## Execution plan

Spawn 5 parallel general_purpose subagents:
1. **amaru filler** — land chakra wiring + scheduler + yawar bus + 3 chakra subtrees via PRs
2. **sentra filler** — land sentra_immune.py + tupu_verify.py + tupu_replay_5x.py + tupu-verdict doc
3. **specialized-charters** — author concise charter docs for terra/vessels/counsel/carlota-jo
4. **ouroboros-thesis rollups** — land innovation-master, moonshot, sdk-innovation, exhaustive (md+pdf), chakra docs
5. **a11oy reports + cookbook + brand** — propagate brain reports, RAG synthesis, cookbook recipes, brand mockups

All via PRs (respect required_signatures).
