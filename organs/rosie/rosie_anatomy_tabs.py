# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v10 — 749 declarations · 14 unique axioms · 163 sorries · 21 canonical formulas
"""
rosie_anatomy_tabs.py — ADDITIVE rosie tabs 20 & 21.

  Tab 20  Formula Registry      — searchable list of all 21 canonical formulas
                                  with live demo (run → result + Λ-receipt).
  Tab 21  Codex-Kernel Composer — chain builder, runs the governed loop,
                                  shows the ReceiptChain.

Self-contained: depends only on `szl_formulas` (inlined registry + composer).
Preserves all existing rosie tabs (ADDITIVE).
"""
import json
from hashlib import sha256

import szl_formulas as S

FORMULA_SRC = ("https://github.com/szl-holdings/szl-cookbook/tree/main/recipes/"
               "canonical-formulas-v1/code/python/formulas.py")


def _registry_rows():
    rows = []
    for name in S.REGISTRY:
        doc = (S.REGISTRY[name].__doc__ or "").strip().split("\n")[0]
        rows.append([name, S.PROOF_STATUS.get(name, "?"), doc])
    return rows


def _search(query):
    q = (query or "").lower().strip()
    return [r for r in _registry_rows() if q in r[0].lower() or q in r[2].lower()]


def _run_formula(name, args_json):
    fn = S.REGISTRY.get((name or "").strip())
    if fn is None:
        return f"unknown formula: {name}"
    try:
        args = json.loads(args_json or "[]")
    except Exception as e:
        return f"bad JSON args: {e}"
    # bytes coercion for dsse
    if name == "dsse_envelope" and args and isinstance(args[0], str):
        args[0] = args[0].encode()
    try:
        out = fn(*args)
    except Exception as e:
        return f"error: {e}"
    jr = out.hex() if isinstance(out, bytes) else out
    if isinstance(jr, dict):
        jr = {k: (v.hex() if isinstance(v, bytes) else v) for k, v in jr.items()}
    receipt = sha256(f"{name}|{args}|{jr}".encode()).hexdigest()
    return json.dumps({"formula": name, "result": jr,
                       "proof_status": S.PROOF_STATUS.get(name),
                       "lambda_receipt": receipt, "source": FORMULA_SRC}, indent=2, default=str)


def _run_chain(chain_json):
    try:
        calls = json.loads(chain_json or "[]")
    except Exception as e:
        return f"bad JSON: {e}"
    for c in calls:
        if c.get("formula_name") == "dsse_envelope":
            a = c.get("args", [])
            if a and isinstance(a[0], str):
                a[0] = a[0].encode()
                c["args"] = a
    chain = S.run_governed_loop(calls)

    def jf(v):
        if isinstance(v, bytes):
            return v.hex()
        if isinstance(v, dict):
            return {k: jf(x) for k, x in v.items()}
        if isinstance(v, (list, tuple)):
            return [jf(x) for x in v]
        return v

    chain["receipts"] = [jf(r) for r in chain["receipts"]]
    return json.dumps(jf(chain), indent=2, default=str)


def build_anatomy_tabs(gr, demo):
    """ADDITIVE: build rosie tabs 20 & 21 inside an existing gr.Tabs() block."""
    with gr.TabItem("20 · Formula Registry"):
        gr.Markdown(
            "### Canonical Formula Registry — 21 formulas\n"
            "Every canonical SZL formula as a pure typed function. "
            f"Source: [formulas.py]({FORMULA_SRC}). Doctrine v10 (749/14/163)."
        )
        search = gr.Textbox(label="Search formulas", placeholder="e.g. lambda, khipu, pac")
        table = gr.Dataframe(headers=["formula", "proof status", "summary"],
                             value=_registry_rows(), interactive=False, wrap=True)
        search.change(_search, inputs=search, outputs=table)
        gr.Markdown("#### Live demo")
        fn_in = gr.Textbox(label="formula name", value="lambda_bounded")
        args_in = gr.Textbox(label="args (JSON list)", value="[[0.8, 0.9, 0.7]]")
        run_btn = gr.Button("Run → Λ-receipt", variant="primary")
        out = gr.Code(label="result + Λ-receipt", language="json")
        run_btn.click(_run_formula, inputs=[fn_in, args_in], outputs=out)

    with gr.TabItem("21 · Codex-Kernel Composer"):
        gr.Markdown(
            "### Codex-Kernel Composer\n"
            "Chain formulas into a **hash-chained governed loop**. Four hard-stop "
            "validators (`state_transition`, `drift_bounds`, `human_gate`, `axis_floor`) "
            "halt the loop on failure (HUKLLA enforcement). Output is a replayable ReceiptChain."
        )
        default_chain = json.dumps([
            {"formula_name": "lambda_bounded", "args": [[0.82, 0.91, 0.77, 0.88]]},
            {"formula_name": "pac_bayes_mcallester", "args": [0.08, 1.5, 2000, 0.05]},
            {"formula_name": "lambda_homogeneous", "args": [2.0, [0.6, 0.8, 0.9]]},
            {"formula_name": "fisher_rao_distance", "args": [[0.4, 0.6], [0.45, 0.55]]},
            {"formula_name": "dsse_envelope", "args": ["chakra5-payload", "amaru-key-1"]},
        ], indent=1)
        chain_in = gr.Code(label="formula chain (JSON)", language="json", value=default_chain)
        run_c = gr.Button("Run governed loop → ReceiptChain", variant="primary")
        chain_out = gr.Code(label="ReceiptChain", language="json")
        run_c.click(_run_chain, inputs=chain_in, outputs=chain_out)
    return demo
