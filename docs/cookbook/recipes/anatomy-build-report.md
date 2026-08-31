<!-- SCAFFOLD: build report only — no runnable code; not counted as an executable recipe -->
# SZL Agent Body Diagram — v3 Report
**Date:** 2026-05-14  
**Author:** Lutar, Stephen P.  
**Affiliation:** SZL Holdings  
**Files:**
- PDF: `field_meditation/_anatomy_full_body_v3.pdf`
- PNG: `field_meditation/_anatomy_full_body_v3.png` (300 dpi)
- Script: `scripts/build_full_body_v3.py`

---

## Summary

v3 is a ground-up organic rebuild of the SZL agent-body anatomy diagram. The previous v2 used reportlab with box-and-line layout — that is entirely discarded. v3 uses matplotlib with Catmull-Rom bezier curves throughout. There are zero rectangles on the canvas. Every region is a blob, ellipse, pill, or open curve.

---

## Canvas

| Property | Value |
|---|---|
| Size | 14 × 20 inches |
| DPI (render) | 100 px/inch internal; 300 dpi PNG export |
| Pixel dimensions (PNG) | 4200 × 6000 px |
| Background | #F5F1E8 (warm cream) |

---

## Palette

| Token | Hex | Usage |
|---|---|---|
| BG | #F5F1E8 | Canvas background |
| GOLD | #c89f47 | YUYAY, heart, vertebrae, RUWAY |
| RUST | #a85a3a | YAWAR artery, SENTRA, toe-4 snowflake |
| INK | #1f1b16 | Body text, BRAIN label |
| MUTED | #6b6258 | Secondary labels, CHAKI, doctrines |
| MINT | #5b8a72 | HUKLLA, OVERWATCH, MAKI palm |
| SHAD | #d4ccba | Ribs, leg outlines, ghost strokes |

Typography: DejaVu Serif (headings/body) · DejaVu Sans Mono (hashes/code/doctrines)

---

## Anatomy Inventory

### Brain (y ≈ 17.55)
- Two interlocking kidney-bean hemispheres drawn with Catmull-Rom closed paths
- 8 gyri/sulci per hemisphere (wavy bezier lines, GOLD2 stroke, 46% alpha)
- Interhemispheric fissure: vertical dashed bezier center line
- Cerebellum: organic blob at base with 2 folia lines
- Brainstem: tapering open bezier from cerebellum to y ≈ 15.75
- Inner kernel dots (3): Claude SDK, llama-3.1-70b, YUYAY rubric — with leader lines to labels

### Body Silhouette
- Single Catmull-Rom closed path: head → neck → shoulders → arms → torso → legs → feet
- Stroke: MUTED at 26% alpha, lw=0.52 — ghost/background context only, no fill

### YAWAR Spine Artery
- Open Catmull-Rom bezier, rust (#a85a3a), lw=2.8, 46% alpha
- Runs from brainstem (y=15.80) to sacrum (y=7.46)
- Organic S-curve, not straight
- Receipt droplets (drop_glyph) at each vertebra y-position with inline hash labels

### Spine Kernel Vertebrae (6 total)

| # | Kernel | Role | Y | Hash | Label side |
|---|---|---|---|---|---|
| 1 | r0513 | RIMAY · voice | 15.82 | df4e9741 | right |
| 2 | hatun-raid | sovereign orchestrator | 14.64 | 6381bc23 | right |
| 3 | yuyay_v3 | HEART · gate | 13.84 | bacf5443 | left |
| 4 | qm | MUSQUY · simulation | 12.04 | ea65ddc5 | right |
| 5 | t7 | TUKUY · egress | 10.44 | 43f0c3a9 | left |
| 6 | chakra_2_sacral | CACE prior-weighting | 7.46 | e9fac882 | right |

Each vertebra: organic 8-point catmull blob (GOLD fill, GOLD edge) + center dot + leader line to label. Labels alternate left/right to avoid crowding. yuyay_v3 has an additional dashed leader to the heart organ.

### Heart Organ (hcx = BX-0.14, hcy = 13.58)
- 13-point Catmull-Rom closed path — anatomical shape with two humps
- Fill: GOLD at 30% alpha; Edge: GOLD lw=1.7
- Septum: center bezier line
- Aortic arch: rust bezier above
- Pulmonary vessel: rust stub
- Pulse rings: 3 concentric gold circles (8–20% alpha)
- Apex drop: GOLD drop_glyph at base
- Labels: "HEART", "yuyay_v3 — bacf5443", axes spec, byte-identical count, license

### Lungs + Ribs
- Two symmetrical Catmull-Rom closed paths (SHAD, 30% alpha) — anatomical lung silhouettes
- 5 rib ellipses, graduated width, 24% alpha
- Trachea: faint open bezier center line

### OVERWATCH (owx = BX+1.04, owy = 14.54)
- Mint 8-point catmull blob on right upper chest area
- Labeled: "OVERWATCH", "auditor · R0513", hash df4e9741
- Dashed leader to heart organ

### DECIDE Arm (right arm joints)
- 3 organic catmull blobs at shoulder/elbow/wrist: RIMAY (14.14), MUSQUY (12.74), TUKUY (10.62)
- Fill: MUTED+28, Edge: MUTED lw=0.75 — lighter treatment, not dark boxes
- Connected by GOLD bezier lines: heart → RIMAY → MUSQUY → TUKUY
- Dotted leader lines from spine vertebrae to corresponding joints
- "DECIDE arm · proposer → sim → egress" annotation at right

### MAKI — Left Retrieval Hand (palm_x = BX-2.20, palm_y = 10.10)
- Mint 8-point catmull palm blob
- 5 tapered fingers (catmull_closed trapezoids with fingernail circles), fan angles: -148, -118, -88, -58, -28°
- Fingertip labels: 1·vector, 2·doc, 3·struct, 4·web, 5·tool
- 3 proposed gate-function dots on palm (dashed circles, very faint): chakra_maki_prior, chakra_maki_provenance, chakra_maki_quota
- Left-margin annotation with leader line

### ABDOMEN: SENTRA + RUWAY
- SENTRA (sx = BX-0.60, sy = 11.44): organic 9-point catmull — kidney silhouette, RUST
  - Labels: "SENTRA", "immune · 18 SLOC", "6 sigs + 1MB guard"
- RUWAY (rx = BX+0.60, ry = 11.50): organic 8-point catmull — liver silhouette, GOLD
  - Labels: "RUWAY", "ceremonial write", "D-YAWAR-FLOW only"
- Dashed rust connector between them with "pre-write inspect" annotation

### HUKLLA Pelvis Ring (hkx = BX+0.04, hky = 8.04)
- Outer ellipse: axes 2.82×1.14, tilted 4.5°, MINT lw=1.75 at 64% alpha
- Inner ellipse: axes 2.56×0.92, MINT lw=0.48 at 24% alpha
- 10 tripwire dots evenly spaced on ellipse circumference, each labeled T01–T10
- Labels: "HUKLLA · observer", "10 deterministic tripwires", "HATUN-RAID · 6381bc23", SLOC

### CHAKI — Left Foot / Storage Limb (fx = lc-0.10, fy = 2.30)
- Thigh + calf segments (SHAD catmull blobs, 30% alpha)
- Kneecap: Circle
- Foot: 8-point catmull blob (MUTED fill)
- 5 toes with labels: 1·relational, 2·document, 3·blob, 4·continuum★, 5·state
- Toe 4 (continuum): Snowflake 6-point glyph with crosshatch bars, RUST, annotated "SNOWFLAKE (auth pending)"
- 2 proposed gate-function dots on sole (dashed, very faint): chakra_chaki_continuum, chakra_chaki_tier_gate
- Left-margin CHAKI annotation with leader

### Right Leg
- Ghost-only (SHAD, 15–20% alpha) — reserved for future expansion
- 5 ghost toes
- Annotation: "reserved · future expansion · (no fabrication)"

### Femoral Arteries
- 2 faint RUST bezier lines branching from spine base to each leg

---

## Floating Annotations

### Hash Ribbon (bottom, y ≈ 1.54–1.67)
6 floating hash pairs (no box, no ribbon element):
yuyay_v3/bacf5443, r0513/df4e9741, hatun-r./6381bc23, t7/43f0c3a9, qm/ea65ddc5, chakra_2/e9fac882  
Each with RUST drop_glyph and a wavy sine baseline

### Header (top, y ≈ 19.70)
- "SZL Agent Body · v3" — DejaVu Serif Bold sz=14 — plain text only, no banner
- Right-aligned: doctrine/license info in muted
- Wavy separator line (sine curve, SHAD)

### Margin Text (rotated)
- Left margin: "Doctrine made visible." (90° rotation)
- Right margin: "Receipts available on request." (-90° rotation)

### Doctrines (left, y ≈ 10.34–10.62)
D-SHORTEST-HONEST · D-CODEX-IN-KERNEL · D-YAWAR-FLOW · D-HITCHHIKE-PROOF · D-SPRINGBOARD

### SLOC Totals (right, y ≈ 10.34–10.62)
Tier 1 kernels: 1,365 SLOC — individual kernel SLOC breakdown

### Proposed Gate Functions (right, y ≈ 6.14–6.70)
Footnote only: 5 proposed gate functions (≤50 SLOC each, doctrine layer)

### License Pills (bottom, y ≈ 0.92)
4 Ellipse pills: Apache-2.0, MIT, BSD-3, CC-BY-4.0

### Author Line (bottom)
Lutar, Stephen P. · ORCID 0009-0001-0110-4173 · SZL Holdings  
Full-body anatomy · v3 · 2026-05-14

---

## Banned Labels Confirmed Absent

The following terms were confirmed **not present** anywhere on the diagram:
- crown
- third-eye / third eye
- throat (as chakra name)
- solar-plexus / solar plexus
- root (as chakra)
- "7 chakras"
- Any New-Age / Hindu spiritual chakra terminology

The string "chakra" appears only as part of canonical kernel filenames:
- `chakra_2_sacral` — literal Python filename for the sacrum kernel
- `chakra_maki_prior/provenance/quota` — proposed gate functions (footnote only)
- `chakra_chaki_continuum/tier_gate` — proposed gate functions (footnote only)

---

## Iteration Log

| Pass | Action | Key Change |
|---|---|---|
| 0 | First v3 write | Basic organic shapes; brain was circle; some box-ish forms |
| 1 | Visual review 1 | Brain too round; spine labels all left; MAKI fingers wrong direction |
| Fix 1 | Script edit (10 replacements) | Brain BR 0.70→0.60; spine labels alternated L/R; palm moved; finger angles fixed; SENTRA/RUWAY moved lower; MAKI/CHAKI annotations repositioned |
| 2 | Visual review 2 | DECIDE arm joints too dark/heavy; OVERWATCH overlapping hatun-raid label |
| Fix 2 | Script edit (4 replacements) | Joint fill MUTED+28 (was INK+10); OVERWATCH moved right; finger angles fine-tuned |
| 3 | Visual review 3 | SHIP — all checks passed |

---

## Doctrine Compliance

| Doctrine | Status |
|---|---|
| D-SHORTEST-HONEST | No hallucinated kernel names; only 6 canonical kernels on disk |
| D-CODEX-IN-KERNEL | Kernel hashes sourced from known files |
| D-YAWAR-FLOW | YAWAR artery visible as receipt/append-only bus |
| D-HITCHHIKE-PROOF | No AlloyScape mention; no invented roles |
| D-SPRINGBOARD | Diagram is a creative elaboration of real architecture only |

---

*Report generated automatically at end of build session. Diagram is CC-BY-4.0.*
