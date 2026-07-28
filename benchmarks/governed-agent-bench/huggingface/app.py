"""Read-only governed-agent-bench leaderboard Space."""

from __future__ import annotations

import json
from pathlib import Path

import gradio as gr


ROOT = Path(__file__).resolve().parent
LEADERBOARD = json.loads((ROOT / "leaderboard.json").read_text(encoding="utf-8"))
PUBLICATION = json.loads((ROOT / "publication.json").read_text(encoding="utf-8"))


def _axis_rows() -> list[list[object]]:
    result_path = ROOT / "results" / "reference-conformance.json"
    if not result_path.exists():
        return []
    result = json.loads(result_path.read_text(encoding="utf-8"))
    return [
        [axis.replace("_", " ").title(), values["passed"], values["total"], values["pass_rate"]]
        for axis, values in sorted(result["axes"].items())
    ]


def _reference_rows() -> list[list[object]]:
    return [
        [
            row["display_name"],
            row["entry_class"],
            row["score"],
            f'{row["passed"]}/{row["total"]}',
            row["dataset_label"],
            row["score_label"],
            row["receipt_verification"],
            row["eligible_for_model_ranking"],
        ]
        for row in LEADERBOARD["reference_rows"]
    ]


with gr.Blocks(title="Governed Agent Bench") as demo:
    gr.Markdown(
        """
        # Governed Agent Bench

        A public benchmark for fail-closed behavior, delegation authority,
        false-success rejection, mutation receipts, and rollback discipline.

        **Current evidence boundary:** the corpus is `SAMPLE`, scores are
        `COMPUTED`, and receipt checks are `STRUCTURE_ONLY`. A reference fixture
        validates the evaluator; it is not a model ranking.
        """
    )
    with gr.Row():
        gr.Number(
            value=LEADERBOARD["eligible_model_submissions"],
            label="Eligible model submissions",
            interactive=False,
        )
        gr.Textbox(
            value=LEADERBOARD["status"],
            label="Leaderboard state",
            interactive=False,
        )
    gr.Dataframe(
        value=_reference_rows(),
        headers=[
            "Entry",
            "Class",
            "Score",
            "Cases",
            "Corpus",
            "Score label",
            "Receipt verification",
            "Model-ranked",
        ],
        datatype=["str", "str", "number", "str", "str", "str", "str", "bool"],
        interactive=False,
        label="Reproducible reference",
    )
    gr.Dataframe(
        value=_axis_rows(),
        headers=["Axis", "Passed", "Total", "Pass rate"],
        datatype=["str", "number", "number", "number"],
        interactive=False,
        label="Reference axis closure",
    )
    gr.JSON(
        value={
            "source_revision": PUBLICATION["source_revision"],
            "dataset_repository": PUBLICATION["dataset_repository"],
            "dataset_revision": PUBLICATION["dataset_revision"],
            "evidence_labels": PUBLICATION["evidence_labels"],
        },
        label="Immutable publication identity",
    )
    gr.Markdown(
        f"""
        [Dataset](https://huggingface.co/datasets/SZLHOLDINGS/governed-agent-bench)
        · [Canonical source](https://github.com/szl-holdings/a11oy/tree/{PUBLICATION["source_revision"]}/benchmarks/governed-agent-bench)

        Model submissions remain empty until an exact JSONL trace, model and
        license identity, evaluator revision, result, and publication receipt
        are reviewed and committed together.
        """
    )


if __name__ == "__main__":
    demo.launch()
