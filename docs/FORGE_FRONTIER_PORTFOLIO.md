# SZL Forge Frontier Portfolio

**Status:** `RESEARCH_PLAN_NOT_EXECUTED`
**Evidence cutoff:** 2026-07-15
**Machine contract:** [`forge_frontier_portfolio.json`](../model_release/forge_frontier_portfolio.json)
**Schema:** [`forge_frontier_portfolio.schema.json`](../model_release/forge_frontier_portfolio.schema.json)
**Contract tests:** [`test_forge_frontier_portfolio.py`](../model_release/test_forge_frontier_portfolio.py)

## Decision

Forge should become a small, evidence-gated **portfolio**, not one overloaded model and not a catalog of renamed upstream weights.

The portfolio has four operational lanes:

1. finish and qualify the existing ReceiptAgent program;
2. run a compact generalist bakeoff before choosing a successor base;
3. add narrow code and mathematics specialists only where they beat the generalist on preregistered tasks;
4. build the second Brain as a provenance-preserving retrieval system with separate embedding, reranking, safety, and generation components.

This document does **not** claim that any candidate has been downloaded, trained, evaluated, deployed, or measured on the laptop. Upstream model-card facts are `PRIMARY_REPORTED`; laptop suitability is an `ENGINEERING_INFERENCE`; all promotion evidence remains `NOT_MEASURED`.

## Evidence vocabulary

| Label | Meaning |
|---|---|
| `PRIMARY_REPORTED` | Stated by an official upstream repository, model card, specification, or paper. It is not an SZL measurement. |
| `ENGINEERING_INFERENCE` | A bounded technical judgment that still needs a local test. |
| `DECLARED_PLAN` | A proposed SZL artifact or activity that has not been executed by this portfolio. |
| `LOCAL_MEASURED_REQUIRED` | A promotion condition requiring a reproducible local run and retained receipt. |
| `NOT_MEASURED` | No qualifying local evidence is attached. |

Vendor benchmarks, model-card benchmark tables, parameter counts, and advertised context lengths are never converted into local performance claims. An advertised maximum context is especially not a laptop operating envelope.

## Model portfolio

| Priority | Forge identity | Upstream | Role | Portfolio disposition | Laptop position |
|---|---|---|---|---|---|
| P0 | ReceiptAgent v1 | [Unsloth Qwen2.5 1.5B Instruct bnb 4-bit](https://huggingface.co/unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit) | Receipt and schema generation | Complete the existing program | Adapter candidate only after preflight |
| P1 | Qwen3.5 2B frontier | [Qwen3.5-2B](https://huggingface.co/Qwen/Qwen3.5-2B) | Compact multimodal generalist | Frontier bakeoff | Quantized inference first; training unproven |
| P1 | Qwen3 1.7B control | [Qwen3-1.7B](https://huggingface.co/Qwen/Qwen3-1.7B) | Text-only compact generalist | Bakeoff control | Adapter candidate after preflight |
| P1 | Granite 3.3 2B control | [Granite 3.3 2B Instruct](https://huggingface.co/ibm-granite/granite-3.3-2b-instruct) | RAG, tool, and enterprise control | Bakeoff control | Quantized inference first; training unproven |
| P2 | SmolLM3 3B challenger | [SmolLM3-3B](https://huggingface.co/HuggingFaceTB/SmolLM3-3B) | Transparent-training generalist challenger | Inference challenger | Do not put in the initial laptop training queue |
| P1 | Forge Code specialist | [Qwen2.5-Coder-1.5B-Instruct](https://huggingface.co/Qwen/Qwen2.5-Coder-1.5B-Instruct) | Patch and repository tasks | Specialist candidate | Adapter candidate after preflight |
| P2 | Forge Math specialist | [Phi-4-mini-reasoning](https://huggingface.co/microsoft/Phi-4-mini-reasoning) | Proof-obligation drafting and critique | Math-only specialist | Inference challenger; no laptop training recommendation |
| P0 | Brain embedder | [Qwen3-Embedding-0.6B](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B) | Dense candidate generation | Second-Brain component | Service component after preflight |
| P0 | Brain reranker | [Qwen3-Reranker-0.6B](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B) | Candidate reranking | Second-Brain component | Service component after preflight |
| P1 | Forge safety signal | [Qwen3Guard-Gen-0.6B](https://huggingface.co/Qwen/Qwen3Guard-Gen-0.6B) | Input/output safety classification | Defense-in-depth component | Never the sole policy gate |

### Why this is better than “upgrade every model”

- It protects the one real, existing ReceiptAgent path from being displaced before qualification.
- It gives the next generalist a fair bakeoff against two compact controls instead of choosing from model-card enthusiasm.
- It prevents a code specialist, math specialist, reranker, or guard from being marketed as a universal model.
- It treats the second Brain as an information-retrieval and provenance problem, not as a request to pour 9,000-plus nodes into a fine-tune.
- It keeps the approximate 8 GB laptop target honest: inference, adapter training, and service components have different envelopes and must be measured independently.

## The bakeoff

The first bakeoff should compare the existing base, Qwen3.5 2B, Qwen3 1.7B, and Granite 3.3 2B. SmolLM3 3B is an inference challenger, not an automatic training candidate.

The preregistration must freeze:

- exact upstream revisions and hashes;
- runtime and quantization revisions;
- context sizes and prompt templates;
- held-out ReceiptBench and BrainQrels revisions;
- task metrics and minimum baselines;
- cold load, peak VRAM/RAM, first-token latency, throughput, thermals, restart, and OOM measurements;
- all fallbacks and failure cases.

The winner is not the model with the strongest upstream benchmark table. It is the smallest qualified candidate that delivers the best role-specific quality per measured latency, memory, energy where observable, and operational risk on the target host.

## Collection consolidation

Do not create a separate ungoverned dataset for every model. Build six versioned collections with stable identities and immutable releases.

| Collection | Purpose | Optional upstream seed material | Release state |
|---|---|---|---|
| `SZL-ReceiptBench` | Tool calls, receipt schemas, provenance, refusals, replay | [Salesforce xLAM function-calling 60k](https://huggingface.co/datasets/Salesforce/xlam-function-calling-60k) | Proposed, not built |
| `SZL-BrainQrels` | Human-reviewed Brain queries, relevance, hard negatives, citations, abstentions, graph routes | First-party canonical artifacts only | Proposed, not built |
| `SZL-FormulaProofObligations` | Formula-ID crosswalk, executable cases, counterexamples, checker receipts | [NVIDIA OpenMathInstruct-2](https://huggingface.co/datasets/nvidia/OpenMathInstruct-2) | Proposed, not built |
| `SZL-PolicyAdversarial` | Prompt injection, unsafe content, exfiltration, policy conflict, refusal | [NVIDIA Aegis 2.0](https://huggingface.co/datasets/nvidia/Aegis-AI-Content-Safety-Dataset-2.0), [AllenAI WildGuardMix](https://huggingface.co/datasets/allenai/wildguardmix) | Proposed, not built |
| `SZL-CodeBench` | Executable patch tasks, test preservation, secret refusal | [NVIDIA OpenCodeInstruct](https://huggingface.co/datasets/nvidia/OpenCodeInstruct) | Proposed, not built |
| `SZL-ModelReceipts` | Model/data/code/environment/training/evaluation/release receipts | First-party receipts only | Proposed, not built |

Every external dataset above is only `OPTIONAL_PENDING_ROW_LEVEL_ADMISSION`. A repository-level license label does not eliminate row-level rights, privacy, provenance, safety, or contamination review.

### Admission pipeline

Every collection uses the same fail-closed sequence:

1. acquire from an approved source and pin an immutable revision;
2. hash original bytes and record retrieval time;
3. attach license and derivation evidence;
4. scan for secrets, credentials, signed URLs, PII, private records, and prohibited content;
5. normalize with a pinned transformation and preserve transformation receipts;
6. run exact, fuzzy, and semantic deduplication;
7. run source-family and benchmark-denylist contamination checks;
8. assign deterministic splits with evaluation isolation;
9. validate schemas, labels, citations, and executable checks;
10. publish only with dataset card, Croissant metadata, W3C PROV lineage, content-addressed manifests, provenance attestation, and contamination report.

[Datasheets for Datasets](https://arxiv.org/abs/1803.09010), [Data Cards](https://arxiv.org/abs/2204.01075), and the [Hugging Face dataset-card guidance](https://huggingface.co/docs/hub/datasets-cards) motivate human-readable documentation. [MLCommons Croissant](https://docs.mlcommons.org/croissant/) provides machine-readable dataset metadata. [W3C PROV-O](https://www.w3.org/TR/prov-o/) provides a provenance vocabulary. [SLSA provenance](https://slsa.dev/spec/v1.2/provenance) and [in-toto](https://in-toto.io/) define supply-chain attestation patterns. The [Data Provenance Initiative audit](https://arxiv.org/abs/2310.16787) is a warning against treating web-scale dataset licensing and attribution as solved.

## Second Brain architecture

The second Brain should not be trained by scraping every node. It should use canonical admission, hybrid retrieval, provenance-bounded graph traversal, and receipts.

```text
immutable source bytes + hash
            |
            v
 pinned parser / Docling normalization + parser receipt
            |
            v
 rights + identity + freshness + privacy + quarantine gates
            |
            v
 versioned lexical | dense | entity | relation | community indexes
            |             |              |
            +------ hybrid candidate generation ------+
                               |
                               v
                 bounded graph expansion
                               |
                               v
                 qualified 0.6B reranker
                               |
                               v
 governed generator -> citation verification -> abstain or answer
                               |
                               v
 query + model + index + evidence + latency + outcome receipt
```

Candidate parsing is grounded in the official [Docling repository](https://github.com/docling-project/docling). Corpus-level graph routing is informed by the official [Microsoft GraphRAG repository](https://github.com/microsoft/graphrag) and the paper [From Local to Global](https://arxiv.org/abs/2404.16130). These references are design inputs, not claims that Forge currently implements or outperforms them.

Recommended routes:

- **Direct fact:** lexical + dense retrieval, bounded rerank, source citation, abstention.
- **Entity/relation:** hybrid retrieval plus local, provenance-bounded graph traversal.
- **Corpus sensemaking:** local/global community summaries, explicitly typed as derived evidence.
- **Investigation:** DRIFT-style iterative retrieval with a fixed budget, conflict tracking, and complete trace.

Non-negotiable invariants:

- original sources remain canonical and content-addressed;
- embeddings, summaries, and graph edges never replace source evidence;
- quarantined or rights-blocked material cannot enter retrieval or memory;
- every claim resolves to source, revision, chunk, and query receipt;
- memory writes require admission, confidence, conflict analysis, and a reversible correction trail;
- insufficient identity, freshness, coverage, or conflict resolution produces abstention.

## Promotion gates

All nine gates are currently blocking and `NOT_MEASURED`:

1. **Upstream identity** — revision and artifact hash verification.
2. **Rights and provenance** — model, data, code, and derivative-use evidence.
3. **Contamination** — exact, fuzzy, semantic, source-family, and benchmark-denylist tests.
4. **Task quality** — preregistered held-out role metrics and baselines.
5. **Safety** — refusal, injection, exfiltration, unsafe-content, privilege, and policy-conflict tests.
6. **Retrieval quality** — qrels recall, MRR/nDCG, citation precision, grounded answers, conflict surfacing, abstention.
7. **Resource envelope** — load, VRAM/RAM, latency, throughput, energy/power where observable, thermals, context, OOM.
8. **Restart and recovery** — clean restart, checkpoint/index recovery, identity revalidation, fail-closed dependencies.
9. **Receipt integrity** — append-only schema validation, complete identities/units/timestamps, replay and conflict rejection.

Passing model quality while failing identity, rights, safety, resource, recovery, or receipt gates is still a failed release.

## Execution sequence

### P0 — stabilize what exists

1. Freeze the current ReceiptAgent base, adapter, training data, code, and environment identities.
2. Repair or rerun its failed held-out qualification without changing the test set.
3. Create the six collection schemas and admission pipeline.
4. Build a small human-reviewed `SZL-BrainQrels` seed from canonical, rights-cleared evidence.
5. Validate the manifest with the focused contract tests.

### P1 — measure before choosing

1. Run the model preflight on one candidate at a time; stop concurrent GPU jobs.
2. Execute the compact generalist inference bakeoff.
3. Qualify Qwen3 embedding and reranking separately on BrainQrels.
4. Evaluate the code specialist on executable held-out repositories.
5. Evaluate the safety component as an independent signal, never as the only policy gate.

### P2 — train narrowly

1. Choose at most one generalist adapter program from the measured bakeoff.
2. Train the code specialist only if a measured generalist gap justifies it.
3. Keep Phi-4 mini reasoning as a math inference challenger unless a separate resource review authorizes training.
4. Add data only through an immutable collection release; never train directly from the mutable Brain or live APIs.

### P3 — release with receipts

1. Create complete model and dataset cards.
2. Attach revisions, hashes, evaluation matrices, failures, resource receipts, and limitations.
3. Produce SLSA or in-toto provenance for released artifacts.
4. Release under an experimental label first.
5. Promote only after every applicable blocking gate passes and an independent readback verifies the public artifact.

## What not to do

- Do not call a website, API mesh, Brain, anatomy, or brand a trained model unless a real weight artifact and complete model identity exist.
- Do not train directly on all Brain nodes, all API output, all formulas, or every repository file.
- Do not treat synthetic output as ground truth or silently mix it with first-party evidence.
- Do not claim mathematical proof from fluent text; use independent executable or formal checking.
- Do not claim laptop feasibility from parameter count or a successful remote demo.
- Do not upload card-only model repositories as if they contain weights.
- Do not mint release records before the immutable artifact, metadata, checksums, and readback exist.
- Do not promote an adapter because training completed; held-out quality, safety, identity, rights, resources, recovery, and receipts still gate release.

## Primary-source foundation

The full URL inventory is machine-readable in the portfolio manifest. Core methods and governance references include:

- [Model Cards for Model Reporting](https://arxiv.org/abs/1810.03993) and [Hugging Face model cards](https://huggingface.co/docs/hub/model-cards)
- [Datasheets for Datasets](https://arxiv.org/abs/1803.09010)
- [Data Cards](https://arxiv.org/abs/2204.01075) and [Hugging Face dataset cards](https://huggingface.co/docs/hub/datasets-cards)
- [Data Provenance Initiative audit](https://arxiv.org/abs/2310.16787)
- [NeMo Curator](https://github.com/NVIDIA-NeMo/Curator)
- [Language Model Evaluation Harness decontamination guidance](https://github.com/EleutherAI/lm-evaluation-harness/blob/main/docs/task_guide.md)
- [MMLU-CF](https://github.com/microsoft/MMLU-CF)
- [W3C PROV-O](https://www.w3.org/TR/prov-o/), [Croissant](https://docs.mlcommons.org/croissant/), [SLSA provenance](https://slsa.dev/spec/v1.2/provenance), and [in-toto](https://in-toto.io/)

The portfolio is intentionally conservative: it converts upstream research into a reproducible decision system without claiming that proposed models, datasets, or Brain components are already operational.
