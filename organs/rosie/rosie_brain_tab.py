# rosie_brain_tab.py — Tab "🧠 Brain" (ADDITIVE, Doctrine v10)
# ---------------------------------------------------------------------------
# Founder verbatim: "Should lean and lake and all formulas and all the thesis
# should be instilled into Rosie's brain."  Rosie is the nervous system that
# INHERITS EVERYTHING — so this tab is the unified brain mirror:
#   1. Unified brain header: Lean/lake numbers (749/14/163 @ c7c0ba17), Λ-Conjecture
#      honesty, the 5 founder-locked LLM tiers + the unified router policy.
#   2. The FULL THESIS CORPUS — all formulas + all thesis across 20 versions
#      (179 rows from 171_PER_VERSION_THEOREM_TABLE.csv → thesis_corpus_171.csv),
#      searchable by version / type / keyword.
#   3. Per-Space brain slices (a11oy gates · amaru cortex · sentra immune ·
#      vessels receipts · uds deploy) — the "inherits everything" view.
#   4. Live cross-links to every Space's /brain + /mesh + /wires.
# Mirrors the _dinn.build_dinn_tab(gr, demo) sibling pattern.  ZERO BANDAID.
# [orchestrator: perplexity-agent]
import csv
import os

import szl_brain as _brain

_CSV = os.path.join(os.path.dirname(os.path.abspath(__file__)), "thesis_corpus_171.csv")


def _load_corpus():
    rows = []
    try:
        with open(_CSV, newline="", encoding="utf-8") as f:
            r = csv.DictReader(f)
            for row in r:
                rows.append([
                    row.get("version", ""), row.get("label", ""), row.get("type", ""),
                    (row.get("statement_short", "") or "")[:400],
                    row.get("lean_file", ""), row.get("reference_vector_exercised", ""),
                    row.get("status", ""),
                ])
    except Exception as e:  # honest: if the corpus is missing, say so (no fabrication)
        rows = [["(corpus load error)", str(e), "", "", "", "", ""]]
    return rows


_CORPUS = _load_corpus()
_HEADERS = ["version", "label", "type", "statement (short)", "lean_file", "ref_vector", "status"]


def _filter_corpus(query: str, type_filter: str):
    q = (query or "").strip().lower()
    tf = (type_filter or "all").strip().lower()
    out = []
    for row in _CORPUS:
        if tf != "all" and (row[2] or "").lower() != tf:
            continue
        if q and not any(q in str(c).lower() for c in row):
            continue
        out.append(row)
    return out


def _tiers_md():
    lines = ["| rank | model | use |", "|---|---|---|"]
    for t in _brain.TIERS:
        lines.append(f"| {t['rank']} | `{t['id']}` | {t['use']} |")
    return "\n".join(lines)


def _theorems_md():
    lines = ["| id | name | status | lean |", "|---|---|---|---|"]
    for k, v in _brain.THEOREMS.items():
        lines.append(f"| **{k}** | {v['name']} | {v['status']} | `{v['lean']}` |")
    return "\n".join(lines)


_BRAIN_HEADER_MD = f"""
## 🧠 Rosie — Unified Brain

Rosie is the **nervous system / cross-session** organ and **inherits everything**: the
brain slices of a11oy (gates), amaru (cortex), sentra (immune), vessels (receipts), and
uds-demo (deploy), plus the **full thesis corpus** (all formulas + all thesis) and the
**unified LLM router**.

**Lean / lake (Doctrine v10, LOCKED @ `c7c0ba17` / `lutar-v18.0.0`):**
**749** declarations · **14** unique axioms (15 raw, 1 dup `sha256`) · **163** tracked sorries
(112 baseline + 51 Putnam) · `lake build` **clean on main**.
Source: [lean_numbers.json](https://github.com/szl-holdings/.github/blob/main/.github/data/lean_numbers.json) @ `c7c0ba17`.

> **Honesty (per Doctrine v10):** Λ uniqueness is a **Conjecture, not a closed theorem**
> (open `CAUCHY_ND` sorry at `Uniqueness.lean:120` + a missing permutation-symmetry axiom).
> A2 = `IsHomogeneous`, A4 = `IsBounded`. Supply chain is honest **SLSA L1**. Receipt
> signatures are **PLACEHOLDER** — Sigstore CI signing not yet wired. Wire D cross-Space
> distributed-trace broker is **NOT wired** (in-process traceparent only — see
> [a11oy /wires](https://szlholdings-a11oy.hf.space/wires)).

### 5 founder-locked LLM tiers (unified router)
{_tiers_md()}

**Router policy:** Λ ≥ 0.90 → rank 0 (casual default) · 0.75 ≤ Λ < 0.90 → rank 2 (math/Λ-gate) ·
Λ < 0.75 → rank 3 (orchestration). `task_hint` floors: math→2, research→1, orchestration→3,
diligence→4. `max_tier` caps. Default model: **claude_sonnet_4_6**.

### Cortex theorems (the formulas Rosie reasons over)
{_theorems_md()}
"""

_SLICES_MD = f"""
### Per-Space brain slices Rosie inherits

- **a11oy — Brand Orchestration / gates:** {_brain.GATE_COMPOSITION['policy_gates']} policy gates +
  {_brain.GATE_COMPOSITION['anchor_formula_gates']} anchor formula gates; Λ-floor {_brain.GATE_COMPOSITION['lambda_floor']};
  AND-compose · severity-indexed witnesses · monotone composition (GLR-consistent).
- **amaru — cortex / reasoning:** TH1 (Λ Conjecture) · TH8 (GLR, proven) · TH10 (Conjecture 1);
  7 chakras (root→crown).
- **sentra — immune / dual-use:** 8 live operational gates; Λ-floor 0.90; immune-doctrine corpus
  (HUKLLA SBOMProvenance · drone-deny · OVERWATCH R0513 · KS-18 — references, not live gates).
- **vessels — data pipeline / receipts:** Khipu Merkle DAG (`sha256(payload ‖ parents)`) + DSSE envelope
  (signature PLACEHOLDER); TH13 PAC-Bayes receipt-DAG bound + TH8 GLR.
- **uds-demo — deploy:** UDS bundle integrity (signed tarball + manifest digest) · Zarf package contract ·
  digest-pinned deploy contract (refuse on mismatch).

### Live cross-links (each Space's brain + mesh)
- a11oy: [/brain](https://szlholdings-a11oy.hf.space/brain) · [/mesh](https://szlholdings-a11oy.hf.space/mesh) · [/wires](https://szlholdings-a11oy.hf.space/wires)
- amaru: [/brain](https://szlholdings-amaru.hf.space/brain)
- sentra: [/brain](https://szlholdings-sentra.hf.space/brain)
- vessels: [/brain](https://szlholdings-vessels.hf.space/brain) · [receipts.json](https://szlholdings-vessels.hf.space/api/vessels/receipts.json)
- uds-demo: [/brain](https://szlholdings-uds-demo.static.hf.space/brain.html)
"""


def build_brain_tab(gr, demo):
    """Attach the '🧠 Brain' TabItem as a sibling inside the open gr.Tabs() context."""
    with gr.TabItem("🧠 Brain"):
        gr.Markdown(_BRAIN_HEADER_MD)
        gr.Markdown("### Full thesis corpus — all formulas + all thesis (20 versions · "
                    f"{len(_CORPUS)} rows). Searchable.")
        with gr.Row():
            q = gr.Textbox(label="Search (version / label / statement / lean file / keyword)",
                           placeholder="e.g. Lambda, monotonicity, Putnam, Uniqueness, v18, Bekenstein", scale=3)
            tf = gr.Dropdown(label="type", choices=["all", "theorem", "lemma", "axiom",
                                                    "definition", "corollary", "conjecture", "none"],
                             value="all", scale=1)
        table = gr.Dataframe(headers=_HEADERS, value=_CORPUS, wrap=True,
                             label="thesis corpus (171_PER_VERSION_THEOREM_TABLE)", interactive=False)

        def _do(query, type_filter):
            return _filter_corpus(query, type_filter)

        q.change(_do, [q, tf], table)
        tf.change(_do, [q, tf], table)
        gr.Markdown(_SLICES_MD)
        gr.Markdown(
            "<span style='color:#a090c0'>Corpus source: <code>171_PER_VERSION_THEOREM_TABLE.csv</code> "
            "(per-version theorem/formula table). Numbers 749/14/163 @ <code>c7c0ba17</code>. "
            "Unified router source: <a href='https://github.com/szl-holdings/platform/tree/main/packages/llm-router'>"
            "platform/packages/llm-router</a>. ADDITIVE — every existing tab preserved. ZERO BANDAID.</span>"
        )
