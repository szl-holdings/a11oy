# Retrieval benchmark

Status: PLANNED

## Existing bounded baseline

Status: COMPLETE_LOCAL_PILOT
Claim label: MEASURED_LOCAL_PILOT

The repository already contains a preregistered, deterministic BM25 pilot under
`research/brain-evidence-admission/`. `szl_brain_evidence_eval.py --verify`
rebuilds the canonical index, evaluation results, and evidence manifest and
requires byte-for-byte equality with the committed artifacts.

The pilot is deliberately narrow: five unique canonical documents, fifteen
manually judged queries, one adjudicator, no learned reranker, no independent
external corpus, and zero canonical source-timestamp coverage. All 9,464 raw
graph nodes observed by the pilot were excluded from the index. The artifact
boundary assigns zero proof credit and zero model-trust uplift, prohibits model
promotion, and triggers no training. External validity is NOT_ESTABLISHED.

The PLANNED status below applies to the full comparative benchmark, not to this
completed local baseline.

## Full comparative benchmark

Compare lexical, vector, graph, and hybrid retrieval on the same locked queries. Report
Recall@5, Recall@10, nDCG@10, citation precision, unsupported-context rate, p50/p95
latency, and authorization failures. Slice results by tenant, freshness, memory type,
classification, and contradiction presence.

The winning configuration must meet every security gate; aggregate quality cannot trade
away tenant isolation or source attribution. Publish failures and abstentions alongside
scores, with bootstrap confidence intervals where the sample permits them.
