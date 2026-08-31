# Brain evidence-admission retrieval pilot

This directory freezes a bounded, deterministic evaluation protocol for the
content-addressed canonical subset of the A11oy Brain. It is an evaluation
artifact, not a trained model and not mathematical proof.

The index builder may read only the three canonical local source families:
Formula, Lean/mathlib, and SZL-Lake. Raw graph nodes are inventory inputs only;
they cannot enter the index. Relevance judgments live in `qrels.json`, are
explicitly evaluation-only, and must never be copied into a training corpus.

Unknown source freshness is reported as unknown. It cannot raise trust. The
protocol assigns zero proof credit, performs no network access, triggers no GPU
training, and permits no model promotion.

The committed result artifacts are reproducible local pilot measurements. They
do not establish external validity or justify claims about the full Brain.
