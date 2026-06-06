# rosie_upgrades_tab.py — Tab 14 "All Upgrades Index" (ADDITIVE)
# Renders the org-wide upgrade inventory (Cursor PRs, Replit verbatim, cookbook
# recipes, szl-trust E4 receipts, Wires, Lean theorems @ Doctrine v11 749/14/163)
# as a gr.HTML block. Cross-links to a11oy /codex-kernel, /wires, /research/dinn.
# Mirrors the _dinn.build_dinn_tab(gr, demo) sibling pattern. ZERO BANDAID.
# [orchestrator: perplexity-agent]

_UPGRADES_INNER_HTML = r"""<div class='szl-upgrades'><style>
:root{--bg:#0b0e14;--card:#121826;--ink:#e8eef7;--mut:#8aa0bf;--acc:#5ad1c0;--line:#243149}
*{box-sizing:border-box}
body{margin:0;font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;background:var(--bg);color:var(--ink)}
.wrap{max-width:1060px;margin:0 auto;padding:32px 20px 80px}
h1{font-size:26px;margin:0 0 4px}
h2{font-size:18px;margin:34px 0 10px;border-bottom:1px solid var(--line);padding-bottom:6px}
.sub{color:var(--mut);margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px 18px;margin:14px 0}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--mut);font-weight:600}
code{background:#0a1626;padding:1px 5px;border-radius:5px;color:var(--acc);font-size:12px}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
.b{display:inline-block;padding:1px 8px;border-radius:999px;font-size:11px;font-weight:700}
.green{background:#0f3a2e;color:#5ad1c0}.amber{background:#3a2f0f;color:#e0c060}.gray{background:#222b3a;color:#8aa0bf}
.note{color:var(--mut);font-size:13px}
.kpis{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px 14px;min-width:120px}
.kpi b{font-size:20px;display:block;color:var(--acc)}
.foot{margin-top:40px;color:var(--mut);font-size:12px;border-top:1px solid var(--line);padding-top:14px}
</style><div class="wrap">
<h1>rosie — operator console + Khipu DAG ingest</h1>
<p class="sub">All Upgrades Index · Doctrine v11 · generated 2026-06-01</p>
<p class="note">This index is scoped to <b>rosie</b> upgrades. The org-wide master index lives on the <a href='https://huggingface.co/SZLHOLDINGS' target='_blank' rel='noopener'>org card</a> and the a11oy <a href='https://szlholdings-a11oy.hf.space/upgrades' target='_blank' rel='noopener'>/upgrades</a> route.</p>

<div class="kpis">
  <div class="kpi"><b>2</b>Cursor PRs (this Space)</div>
  <div class="kpi"><b>749</b>Lean declarations</div>
  <div class="kpi"><b>14</b>unique axioms</div>
  <div class="kpi"><b>163</b>tracked sorries</div>
  <div class="kpi"><b>12</b>E4 receipts</div>
</div>

<h2>1 · Cursor PRs merged & instilled</h2>
<div class="card"><table>
<tr><th>PR</th><th>Title</th><th>Merged</th><th>SHA</th><th>Type</th><th>Diff</th><th>Live</th></tr>
<tr><td><a href='https://github.com/szl-holdings/rosie/pull/32' target='_blank' rel='noopener'>rosie#32</a></td><td>Add AGENTS.md with Cursor Cloud development instructions</td><td>2026-05-29</td><td><code>22116b9287</code></td><td>feature</td><td>1f · +48/-0</td><td><span class="b green">LIVE</span></td></tr>
<tr><td><a href='https://github.com/szl-holdings/rosie/pull/39' target='_blank' rel='noopener'>rosie#39</a></td><td>chore(license): add SPDX-License-Identifier headers (rosie)</td><td>2026-05-29</td><td><code>c5fdc90f45</code></td><td>feature</td><td>2f · +8/-0</td><td><span class="b green">LIVE</span></td></tr>
</table>
<p class="note">Liveness verified per <a href="https://github.com/szl-holdings/.github/tree/main/cursor-directives" target="_blank" rel="noopener">cursor-directives</a> + re-instill ship log (64). IP-HOLD PRs (a11oy#57 / amaru#46 / sentra#45) intentionally untouched.</p>
</div>

<h2>2 · Replit verbatim surface</h2>
<div class="card"></div>

<h2>3 · Cookbook recipes instilled</h2>
<div class="card"><ul><li><a href='https://github.com/szl-holdings/szl-cookbook/tree/main/recipes/knot-calculus-v1' target='_blank' rel='noopener'>knot-calculus-v1</a></li><li><a href='https://github.com/szl-holdings/szl-cookbook/tree/main/recipes/anatomy-evolved-v1' target='_blank' rel='noopener'>anatomy-evolved-v1</a></li><li><a href='https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/chakra-unification.md' target='_blank' rel='noopener'>chakra-unification</a></li><li><a href='https://github.com/szl-holdings/szl-cookbook/blob/main/recipes/anatomy-build-report.md' target='_blank' rel='noopener'>anatomy-build-report</a></li></ul></div>

<h2>4 · szl-trust E4 governed-loop receipts</h2>
<div class="card"><p>szl-trust <b>E4 codex-kernel governed loop</b>: <b>12</b> receipts emitted · 0 hard-stop failures · stop reason <code>convergence</code> · ledger digest <code>4d0a943cef5b8fa605919db38df5e8e7</code>.</p><p class='note'>Run <code>run_386723681730b1fd</code> · kernel codex-kernel-runner-1.0.0 · <a href='https://github.com/szl-holdings/szl-trust/tree/main/runs/E4-codex-kernel-2026-04-29' target='_blank' rel='noopener'>12 receipts + run manifest</a>. Replay status: not_run (offline deterministic emulator — honest disclosure).</p></div>

<h2>5 · Wires</h2>
<div class="card"><table>
<tr><th>Wire</th><th>Route</th><th>Endpoints</th><th>Status</th></tr>
<tr><td><b>Wire B</b></td><td>a11oy -&gt; sentra</td><td><code>/v1/verdict + /v1/inspect</code></td><td><span class='b green'>LIVE</span></td></tr><tr><td><b>Wire C</b></td><td>a11oy -&gt; rosie</td><td><code>/v1/events + Khipu DAG ingest</code></td><td><span class='b green'>LIVE</span></td></tr><tr><td><b>Wire D</b></td><td>honest-disclosure</td><td><code>pending</code></td><td><span class='b amber'>PENDING</span></td></tr>
</table></div>

<h2>6 · Lean theorems (Doctrine v11 honest numbers)</h2>
<div class="card"><p><b>749</b> declarations · <b>14</b> unique axioms · <b>163</b> tracked sorries <span class='note'>(Doctrine v11 honest numbers — <a href='https://github.com/szl-holdings/.github/blob/main/.github/data/lean_numbers.json' target='_blank' rel='noopener'>lean_numbers.json</a> @ <code>c7c0ba17</code>)</span></p><p class='note'>749 declarations / 14 unique axioms / 163 tracked sorries per Doctrine v11. Sorries carry discharge routes (PACBayes, MadhavaBound, TwoWitness, Uniqueness, Putnam set).</p><p class='note'>14 unique axioms (honest gap): MomentSubGaussian, audit_reidemeister_invariance, canonicalReceipt, chromotopology_code_bijection, gleason_length_mod_8, klDivergence_nonneg, lambda_schur_concave_n_axis, lambda_stationary_unique, liu_hui_pi_converges, pinsker, r1_invariance, r2_invariance, sha256, sha256_collision_resistant</p></div>

<h2>7 · Cross-Space surfaces (linked, not duplicated)</h2>
<div class="card"><p>This page <b>links</b> to sibling surfaces rather than duplicating them:</p><ul><li><a href='https://szlholdings-a11oy.hf.space/research/dinn' target='_blank' rel='noopener'>DINN demos</a> — knot-DINN, doctrine-DINN, bekenstein-DINN (DINN agent surface)</li><li><a href='https://szlholdings-a11oy.hf.space/codex-kernel' target='_blank' rel='noopener'>codex-kernel</a> — replay-grade governed loop + Dresden-Venus emulator</li><li><a href='https://szlholdings-a11oy.hf.space/wires' target='_blank' rel='noopener'>Wires</a> — Wire B/C live, Wire D honest-disclosure pending</li></ul><p>Other Space upgrade indexes:</p><ul><li><a href='https://szlholdings-a11oy.hf.space/upgrades' target='_blank' rel='noopener'>a11oy upgrades</a></li><li><a href='https://szlholdings-amaru.hf.space/upgrades' target='_blank' rel='noopener'>amaru upgrades</a></li><li><a href='https://szlholdings-sentra.hf.space/upgrades' target='_blank' rel='noopener'>sentra upgrades</a></li><li><a href='https://szlholdings-vessels.hf.space/upgrades' target='_blank' rel='noopener'>vessels upgrades</a></li></ul></div>

<div class="foot">
Source of truth: <a href="https://github.com/szl-holdings/.github/blob/main/.github/data/lean_numbers.json" target="_blank" rel="noopener">org .github/data/lean_numbers.json</a> @ <code>c7c0ba17</code>.
Cursor directives: <a href="https://github.com/szl-holdings/.github/tree/main/cursor-directives" target="_blank" rel="noopener">.github/cursor-directives</a>.
Doctrine: <a href="https://github.com/szl-holdings/.github/tree/main/doctrine" target="_blank" rel="noopener">.github/doctrine</a>.
Additive surface — existing routes preserved. ZERO BANDAID. Doctrine v11 honest numbers (749/14/163).
</div>
</div></div>"""


def build_upgrades_tab(gr, demo):
    """Insert Tab 14 — All Upgrades Index — as a sibling TabItem inside gr.Tabs()."""
    with gr.TabItem("🚀 All Upgrades Index"):
        gr.HTML(_UPGRADES_INNER_HTML)
