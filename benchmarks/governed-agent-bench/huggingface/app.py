# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Read-only native view of the exact committed benchmark package."""

import json
from pathlib import Path

import gradio as gr
from native_presentation import head, render

ROOT = Path(__file__).resolve().parent
LEADERBOARD = json.loads((ROOT / "leaderboard.json").read_text(encoding="utf-8"))
PUBLICATION = json.loads((ROOT / "publication.json").read_text(encoding="utf-8"))
RESULT = json.loads((ROOT / "results/reference-conformance.json").read_text(encoding="utf-8"))

with gr.Blocks(title="Governed Agent Bench", analytics_enabled=False, fill_width=True) as demo:
    gr.HTML(render(LEADERBOARD, PUBLICATION, RESULT), elem_id="bench-native",
            apply_default_css=False, js_on_load=None)

if __name__ == "__main__":
    demo.launch(head=head(), footer_links=[],
                theme=gr.themes.Base(font=["system-ui"], font_mono=["ui-monospace"]))
