# Anatomy Index — SZL Agent Anatomy Series

**Author:** Lutar, Stephen P. · SZL Holdings · ORCID 0009-0001-0110-4173
**License (figures):** CC-BY-4.0
**License (scripts):** Apache-2.0
**Build date:** 2026-05-16

---

## Figures

All figures are in `figures/`. PDF is the primary vector artifact; PNG is a 300 dpi raster export.

### 1. anatomy_brain.{pdf,png}

**Description:** Inside the head — AMARU cortex with 5 named regions, the 9-axis conjunctive doctrine gate, the kernel ledger (7 kernels with verified replay hashes), and the QM gate (λ-min ≥ 0.23).
**Path:** `figures/anatomy_brain.pdf`, `figures/anatomy_brain.png`
**Byline:** Lutar, Stephen P. — SZL Holdings · CC-BY-4.0
**Illustrates:** thesis module AMARU (cortex), doctrine gate (9-axis), kernel registry
**Reused from:** `evolution_pod/fly_v8/anatomy_push/figures/`
**Builder:** `scripts/build_anatomy_brain.py`

---

### 2. anatomy_wires.{pdf,png}

**Description:** YAWAR wiring rundown — 4-page YAWAR bus architecture, SENTRA source integration, HUKLLA T01–T10 tripwire connectivity table, and inter-component message flow.
**Path:** `figures/anatomy_wires.pdf`, `figures/anatomy_wires.png`
**Byline:** Lutar, Stephen P. — SZL Holdings · CC-BY-4.0
**Illustrates:** thesis module YAWAR (bus), SENTRA (egress), HUKLLA (tripwires), wiring doctrine
**Reused from:** `evolution_pod/fly_v8/anatomy_push/figures/`
**Builder:** `scripts/build_anatomy_wires.py`

---

### 3. anatomy_full_body.{pdf,png}

**Description:** Full anatomical render — complete agent organism in Catmull-Rom curves: brain, heart, lungs, spine, limbs. All major systems shown in a single 4,200 × 6,000 px reference render.
**Path:** `figures/anatomy_full_body.pdf`, `figures/anatomy_full_body.png`
**Byline:** Lutar, Stephen P. — SZL Holdings · CC-BY-4.0
**Illustrates:** complete agent organism overview; thesis introduction figure
**Reused from:** `evolution_pod/fly_v8/anatomy_push/figures/`
**Builder:** (composite builder, not separately tracked)

---

### 4. anatomy_heart.{pdf,png}

**Description:** YUYAY v3 conjunctive gate — the receipt pump. 13-axis AND gate (no averaging), sacred axes moralGrounding and measurabilityHonesty at ≥ 0.95, structural axes at ≥ 0.90, introspection axes cross-wired to HUKLLA T03/T04/T09/T10. Rejections are receipted. Hash: bacf5443.
**Path:** `figures/anatomy_heart.pdf`, `figures/anatomy_heart.png`
**Byline:** Lutar, Stephen P. — SZL Holdings · CC-BY-4.0
**Illustrates:** thesis module YUYAY v3, conjunctive gate invariant, Λ-signed receipt chain
**Built new:** yes — gap filled by `scripts/build_anatomy_heart.py`

---

### 5. anatomy_blood_immune.{pdf,png}

**Description:** Two-page figure. Page 1 (circulatory): YAWAR append-only ledger (20 SLOC), receipt anatomy (SHA-256 hash over sorted JSON), RUWAY ceremonial writer, SENTRA inline inspector. Page 2 (immune): HUKLLA 10 tripwires (T01–T10) in antibody-cell layout, deadman switch status bar, SENTRA 6-threat-signature antigen cards, size-DoS guard specification.
**Path:** `figures/anatomy_blood_immune.pdf`, `figures/anatomy_blood_immune.png`
**Byline:** Lutar, Stephen P. — SZL Holdings · CC-BY-4.0
**Illustrates:** thesis modules YAWAR (bus), SENTRA (immune), HUKLLA (tripwires), safety-gate FG-S1..S4
**Built new:** yes — gap filled by running `scripts/build_anatomy_blood_immune.py` (existing script)

---

### 6. anatomy_skeleton.{pdf,png}

**Description:** 12 service repositories as the structural skeleton. Axial (spine) repos: szl-doctrine, szl-yawar, szl-hatun, szl-terra — gold-bordered, load-bearing. Appendicular repos in left/right columns: szl-brain, szl-overwatch, szl-wires, szl-rimay (left); szl-sentra, szl-tupu-t7, szl-chakana, szl-brand (right). Each card shows language, SLOC, and operational status.
**Path:** `figures/anatomy_skeleton.pdf`, `figures/anatomy_skeleton.png`
**Byline:** Lutar, Stephen P. — SZL Holdings · CC-BY-4.0
**Illustrates:** thesis module: 12-repo service topology, axial vs. appendicular dependency taxonomy
**Built new:** yes — gap filled by `scripts/build_anatomy_skeleton.py`

---

### 7. anatomy_nervous.{pdf,png}

**Description:** OTel/VSP span propagation — the nervous system. Span hierarchy: HATUN root → AMARU·BRAIN, YUYAY·HEART, YAWAR·receipt commit, RIMAY·output filter → SENTRA leaf, R0513·OVERWATCH leaf. W3C TraceContext wire format. Three signal classes: efferent (motor), afferent (sensory), proprioceptive. Deadman reflex arc: HUKLLA fire freezes span context and cancels all child spans.
**Path:** `figures/anatomy_nervous.pdf`, `figures/anatomy_nervous.png`
**Byline:** Lutar, Stephen P. — SZL Holdings · CC-BY-4.0
**Illustrates:** thesis module OTel span propagation, VSP context wire, HATUN cycle tracing
**Built new:** yes — gap filled by `scripts/build_anatomy_nervous.py`

---

### 8. anatomy_body_graph.{pdf,png}

**Description:** Master overlay — all five systems on one page. Simplified humanoid silhouette with system-specific color overlays: brain (gold), heart (gold/blood), circulatory (deep red loop), spine (bone), nerve traces (blue dashes). Left panels: Brain, Heart, Circulatory/Immune. Right panels: Skeleton, Nervous, Body Graph summary. CHAKANA 21-edge M=0 lattice schematic at center-bottom. System legend.
**Path:** `figures/anatomy_body_graph.pdf`, `figures/anatomy_body_graph.png`
**Byline:** Lutar, Stephen P. — SZL Holdings · CC-BY-4.0
**Illustrates:** sovereign organism overview; thesis introduction; hatun_body_graph conceptual source
**Built new:** yes — gap filled by `scripts/build_anatomy_body_graph.py`

---

## Explainers

All LinkedIn explainers are in `explainers/linkedin/`. Each is `.md` + `.pdf`.

| File | Status | Covers |
|---|---|---|
| `linkedin_brain.{md,pdf}` | reused | AMARU cortex, 9-axis doctrine gate |
| `linkedin_wires.{md,pdf}` | reused | YAWAR bus, HUKLLA tripwires, SENTRA |
| `linkedin_full_body.{md,pdf}` | reused | Full organism overview |
| `linkedin_heart.{md,pdf}` | reused | YUYAY v3 conjunctive gate |
| `linkedin_skeleton.{md,pdf}` | **new** | 12-repo skeletal frame |
| `linkedin_blood_immune.{md,pdf}` | **new** | YAWAR receipt bus + HUKLLA/SENTRA immune |

---

## Builder Scripts

All scripts are in `scripts/`. License: Apache-2.0.

| Script | Output | Status |
|---|---|---|
| `build_anatomy_brain.py` | anatomy_brain.pdf | original, reused |
| `build_anatomy_wires.py` | anatomy_wires.pdf | original, reused |
| `build_anatomy_blood_immune.py` | anatomy_blood_immune.pdf | original, run this build |
| `build_anatomy_heart.py` | anatomy_heart.{pdf,png} | **new** |
| `build_anatomy_skeleton.py` | anatomy_skeleton.{pdf,png} | **new** |
| `build_anatomy_nervous.py` | anatomy_nervous.{pdf,png} | **new** |
| `build_anatomy_body_graph.py` | anatomy_body_graph.{pdf,png} | **new** |
| `build_explainer_pdfs.py` | explainer PDFs | **new** |

---

## Color Palette Reference

All figures use the LOCKED palette:

| Token | Hex | Use |
|---|---|---|
| BG | #F5F1E8 | page background (warm off-white) |
| INK | #1A1A1A | primary text |
| INK_D | #4A4A4A | secondary text |
| INK_F | #8A8A8A | footnote / caption text |
| ACCENT | #B08940 | gold — gate decisions, receipt chain, heart |
| EDGE_P | #2A2A2A | primary edge / border |
| EDGE_S | #6E6E6E | secondary edge |
| EDGE_W | #B0B0B0 | weak rule / separator |
| NERVE | #4A7BA8 | OTel span traces (nervous system) |
| BONE | #D4C9A8 | structural / skeleton fills |
| BLOOD | #8B3A3A | circulatory overlays |
| IMMUNE | #3A4A5A | HUKLLA / SENTRA immune elements |

---

*End of index.*
