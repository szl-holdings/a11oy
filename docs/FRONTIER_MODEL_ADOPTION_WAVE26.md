# Frontier model adoption and SZL Hugging Face consolidation

**State:** governed plan, not a local model qualification
**Evidence date:** 2026-07-16
**Machine contract:** [`frontier-adoption.json`](../model_release/frontier-qualification/frontier-adoption.json)
**Fail-closed guard:** [`frontier_admission_guard.py`](../model_release/frontier-qualification/frontier_admission_guard.py)

This wave turns frontier-model research into an executable admission boundary. It does not download weights, start training, promote a model, merge adapters, delete a Hub repository, or relabel an upstream benchmark as an SZL result.

## The product decision

SZL should present one coherent flagship family, not one overloaded tensor file and not fifteen competing model names:

| Product role | Canonical artifact | Decision |
|---|---|---|
| Flagship | [`SZL-Khipu-1.5B-BrainNavigator`](https://huggingface.co/SZLHOLDINGS/SZL-Khipu-1.5B-BrainNavigator) | Keep experimental and unpromoted; improve abstention and reconcile the signed-receipt artifact-binding conflict |
| Local distribution | [`SZL-Khipu-1.5B-GGUF`](https://huggingface.co/SZLHOLDINGS/SZL-Khipu-1.5B-GGUF) | Keep as Khipu's llama.cpp/Ollama distribution, not as a separate product |
| Candidate sibling | [`SZL-Forge-1.5B-ReceiptAgent`](https://huggingface.co/SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent) | An artifact with this label exists, but its target ReceiptAgent behavior is not established; intended role is receipt drafting only, and artifact binding/promotion remain blocked |
| Supporting substrate | SZL kernels, formulas, invariants, Ouroboros, Lambda gate, provenance control, governance signing | Group into a supporting-kernel collection; do not market these code artifacts as language-model weights |
| Next release | `SZL-Khipu-v2` | Create only after row-level Brain admission and a preregistered independent evaluation materially improve the measured abstention weakness |

The two current transformer profiles are distinct pinned repositories and revisions. No merge is authorized without a new artifact-bound receipt chain and ablation. Consolidate the product surface, router, collection, Space, evaluation contracts, receipts, and feedback loop first.

## SZL Khipu Research OS

The defensible unification is a compound, receipt-bearing research system rather than one opaque checkpoint:

1. **Khipu** proposes bounded plans, retrieval requests, citations, abstentions, and tool calls.
2. **SZL-Lake and the 9,464-node Brain** retain canonical evidence outside gradients and return immutable node revisions and source spans.
3. **The formula registry** turns the claimed formula corpus into typed obligations with explicit status; quantity alone never establishes proof.
4. **Lean and mathlib** verify proof terms that are actually represented and compiled. A model-generated proof is a proposal until the kernel accepts it.
5. **ReceiptAgent candidate** is a target role, not an established capability. If later qualified, it may draft receipt structure; the governed runtime must validate and bind it, and a separate external signer must emit DSSE. The model is never the signer.
6. **SZL-Yupaq** validates typed jobs and dispatches only named, bounded engines outside the weights.
7. **Ayllu and SZL Router** enforce budgets, tool permissions, loop caps, validation, and fail-closed abstention.

This makes the stack commercially legible without pretending that the Lake, Lean source, formula records, or all Brain nodes are model weights. The near-term release is a governed research copilot; autonomous and high-stakes operation stays blocked until the stated evaluation predicates pass.

### GitHub estate union

The supplied inventory reports 54 repositories, but the attachment is truncated during `pitch-collateral`; only 30 repository names are visible in the supplied text. An independent public GitHub readback on 2026-07-16 observed 50 public repositories, 9 archived. Those counts are not silently conflated: the contract records `SOURCE_REPORT_54_PUBLIC_READBACK_50_ATTACHMENT_TRUNCATED_REVIEW_REQUIRED` and `inventory_complete=false`. `szl-org-health`, `szl-substrate`, and `pitch-collateral` are attachment-reported but were not present in that public readback. Public repositories outside the truncated attachment—including `immune`, `anatomy`, receipt specifications, and Holo/live wrappers—remain separately visible for classification rather than silently omitted.

The canonical ownership chain is:

`a11oy -> Hatun MCP -> SZL Router -> Forge profiles -> Yupaq compute -> SZL Lake/Receipt -> Anatomy -> approved verticals`

Use the repositories by responsibility, not by forcing all of them into one checkpoint:

| Layer | Canonical repositories | Role |
|---|---|---|
| Company/governance | `.github`, `szl-brand`, `szl-doctrine`, `docs-site` | Policy, identity, documentation, and measured estate health |
| Control plane | `a11oy`, `platform` | Product/API integration; shared-substrate ownership remains a reconciliation item |
| Tools/routing | `hatun-mcp`, `szl-router`, `szl-mesh`, `khipu-consensus` | Typed tools, canonical inference routing, coordination, witnessed approval |
| Weight program / pinned artifacts (unpromoted) | `szl-forge` plus the pinned Khipu and ReceiptAgent-labeled Hugging Face artifacts | Training and qualification program; ReceiptAgent behavior is not established, and both artifacts remain unpromoted and artifact-binding-conflicted |
| Evidence/telemetry | `szl-lake`, `szl-receipt`, `vsp-otel`, `szl-telemetry`, `szl-energy-attest` | Evidence, DSSE, traces, resource receipts, public counters |
| Proof/formulas | `lutar-lean`, `lean-kernel`, `szl-formula-ledger`, `szl-lambda-gate` | Deliberately separate theorem source, kernel, status ledger, and advisory aggregation |
| Computation | `szl-quant`, `yarqa`, plus in-repo `szl_yupaq_compute.py` and `model_release/szl-compute-plane.json` | Bounded quantitative/scientific workers outside weights; Yupaq is not a separate repository |
| Loops/build | `ouroboros`, `szl-build-env`, `warhacker-demo` | Bounded recursion, reproducible build fabric, defensive dry-run verification |
| Publications | `szl-papers` | Preprints and claims tied to verifiable releases |
| Presentation | `anatomy` | Generated evidence/estate visualization; it consumes manifests and creates no proof or readiness |
| Vertical | `killinchu` | Human-governed defensive application consuming the shared stack |

This union also records current debt rather than hiding it: the two public Brain surfaces do not share one signed manifest; a11oy.net and a-11-oy.com have identity/backend parity gaps; the cited Machine Innovate hardening branch is not present in the checked repository; Forge/Mesh readiness prose is stale; and Hatun/router logic has duplicated ownership. Those are integration obligations, not reasons to invent another model name.

### Existing computation truth

The canonical implementation is [`szl_yupaq_compute.py`](../szl_yupaq_compute.py) with [`szl-compute-plane.json`](../model_release/szl-compute-plane.json), not a new model repository. It currently implements bounded schemas for Lambda aggregation, sample quant, exact QUBO baseline, external numerical run/compare, Lean inventory, formula-admission inventory, Brain inventory, and Lake inventory. Its published state remains `BOUNDED_CORE_IMPLEMENTED_LIVE_VERIFICATION_PENDING`.

The numerical registry has 1,328 preregistered cases, but MATLAB and Octave are external execution boundaries. GNU Octave needs a real isolated Linux-worker receipt. MATLAB needs an operator-provided licensed worker plus explicit offline-license review. Missing engines return `UNAVAILABLE`; they are never replaced with modeled output. A numerical receipt must bind engine and code revision, input family/dimension/condition stratum, seed, tolerance, residual, backward error, MATCH/CONFLICT result, runtime, memory/GPU, network isolation, and license state.

### Governed vertical profiles

Profiles are tool contracts behind Khipu/Yupaq, not independent weight brands. Every profile follows `DECLARED -> PINNED -> LICENSE_REVIEWED -> SANDBOX_QUALIFIED -> EVAL_QUALIFIED -> HUMAN_APPROVED`.

| Profile | Primary engines or standards | Boundary |
|---|---|---|
| Math and formal proof | [Lean 4](https://github.com/leanprover/lean4), [mathlib](https://github.com/leanprover-community/mathlib4), [SymPy](https://github.com/sympy/sympy) | Kernel acceptance is required for a proof claim; symbolic output is independently substituted/cross-checked |
| Scientific numerics | [SciPy](https://github.com/scipy/scipy), [Julia](https://github.com/JuliaLang/julia), [GNU Octave](https://github.com/gnu-octave/octave), licensed MATLAB worker | Fixed operations only; preregistered residual/backward-error and cross-engine comparison |
| BioCompute research | [ESM](https://github.com/facebookresearch/esm), [RDKit](https://github.com/rdkit/rdkit), [Chemprop](https://github.com/chemprop/chemprop), [MedCPT](https://github.com/ncbi/MedCPT), [Nextflow](https://github.com/nextflow-io/nextflow) | Research retrieval/sequence/molecule/workflow support only; no diagnosis, treatment, efficacy, toxicity, or clinical claim |
| Defensive cyber | [Zeek](https://github.com/zeek/zeek), [OpenTelemetry Collector](https://github.com/open-telemetry/opentelemetry-collector), [Sigma](https://github.com/SigmaHQ/sigma), [ATT&CK STIX](https://github.com/mitre-attack/attack-stix-data) | Triage and control coverage with analyst approval; no unauthorized offensive execution |
| Mission logistics and sensor quality | [OR-Tools](https://github.com/google/or-tools), [STAC](https://github.com/radiantearth/stac-spec), [Apache Arrow](https://github.com/apache/arrow) | Advisory, synthetic/open scenarios first; no targeting, weapons execution, navigation, or autonomous operational command |
| Quant and risk | [QuantLib](https://github.com/lballabio/QuantLib), [OSQP](https://github.com/osqp/OSQP), [PyPortfolioOpt](https://github.com/PyPortfolio/PyPortfolioOpt) | Frozen fixtures and stress analysis; no brokerage connection, performance promise, or autonomous trading |
| Policy and compliance | [OPA](https://github.com/open-policy-agent/opa), [Cedar](https://github.com/cedar-policy/cedar), [OSCAL](https://github.com/usnistgov/OSCAL) | Reproducible policy evaluation and evidence gaps; no unsupported legal conclusion |
| Energy, climate, and buildings | [PyPSA](https://github.com/PyPSA/PyPSA), [xarray](https://github.com/pydata/xarray), [EnergyPlus](https://github.com/NatLabRockies/EnergyPlus) | Scenario/QC/simulation only; no autonomous grid control or engineering certification |
| Maritime and assets | [pyais](https://github.com/M0r13n/pyais), [IOOS QC](https://github.com/ioos/ioos_qc), [IFCOpenShell](https://github.com/IfcOpenShell/IfcOpenShell), [GeoPandas](https://github.com/geopandas/geopandas) | Data-quality, geometry, and schema checks; no autopilot, unsupported valuation, or engineering conclusion |

Phase 1 should operationalize formal verification, numerical comparison, defensive triage, policy evaluation, sensor-quality analysis, and logistics scenarios. Phase 2 can qualify bio, quant risk, energy/climate, maritime, and asset profiles after licenses, datasets, hardware, and independent evaluations pass.

## The 9,464-node Brain: what is real

- The current repository reports **9,464 raw nodes** available to retrieval and evaluation.
- **Zero raw nodes are admitted to gradients** under the current signed row-level admission contract.
- Khipu is a real trained weight model, but its public card states that it was trained on **synthetic handle-navigation scenarios**, not raw Brain node content.
- Khipu's owner-run synthetic evaluation reports 11/11 schema-valid plans, 4/5 grounding-correct cases, and **2/6 abstention-correct cases**. Separately, the canonical Forge manifest reports a signed-receipt artifact-binding conflict for both Khipu and ReceiptAgent. Either blocker prevents promotion; both profiles remain experimental and unpromoted.

The correct Brain v2 architecture keeps canonical node content in a provenance-bound Lake/Brain index and trains the model to navigate, cite, abstain, and use tools. Raw node count is not training authority. Each proposed gradient row must independently pass rights, provenance, immutable revision, freshness, deduplication, contamination, and split-isolation gates.

## Frontier candidate decisions

| Candidate | Decision | Why |
|---|---|---|
| [MOSS Transcribe-Diarize 0.9B](https://huggingface.co/OpenMOSS-Team/MOSS-Transcribe-Diarize) | `LOCAL_QUALIFY` | Best immediate fit for timestamped, diarized audio evidence into the Lake and Brain; custom code must be pinned, reviewed, and executed offline |
| [Bonsai 27B Q1](https://huggingface.co/prism-ml/Bonsai-27B-gguf) | `LOCAL_QUALIFY` | Plausible 8 GB low-bit inference challenger; requires the exact Prism runtime fork and independent quality/resource receipts |
| [Ternary Bonsai 27B](https://huggingface.co/prism-ml/Ternary-Bonsai-27B-gguf) | `EVALUATION_ONLY_INFERENCE_ARTIFACT` | Reported 4K peak exceeds the laptop envelope; training from GGUF is forbidden and hybrid offload must remain separately labeled |
| [Inkling](https://huggingface.co/thinkingmachines/Inkling) | `REMOTE_ONLY` | Adopt controllable reasoning budgets, tool-schema randomization, and multimodal evaluation methods; model is not a local candidate |
| [GLM-5.2](https://huggingface.co/zai-org/GLM-5.2) | `REMOTE_ONLY` | Study shared sparse indexing, cache reuse, speculative acceptance, and long-horizon evaluation through compact SZL ablations |
| [Tencent Hy3](https://huggingface.co/tencent/Hy3) | `REMOTE_ONLY` | Adopt explicit reasoning-effort levels, tool recovery, scaffold variance, and product-feedback admission controls |
| [ThinkingCap Qwen3.6 27B](https://huggingface.co/bottlecapai/ThinkingCap-Qwen3.6-27B) | `METHODS_ONLY` | Add five-seed confidence intervals, paired comparisons, thinking-token efficiency, loop/truncation rates, and safety retention |
| [Qwythos Claude Mythos](https://huggingface.co/empero-ai/Qwythos-9B-Claude-Mythos-5-1M) | `QUARANTINE_PROVENANCE_UNRESOLVED` | Reported Claude-trace corpus lacks a public row-level rights ledger; an Apache label on weights does not establish trace rights |
| [Krea2 Identity Edit](https://huggingface.co/conradlocke/krea2-identity-edit) | `QUARANTINE_RESTRICTED_IDENTITY_MODEL` | Custom license plus identity/biometric/impersonation controls require legal and safety review; methods only |

Every record is tied to an immutable upstream revision. Local candidates are additionally tied to exact artifact and runtime digests. Unknown repositories default to denied.

## Khipu-v2 frontier methods council

These are external primary-source methods, not local SZL results. Their code licenses do not automatically license every checkpoint or dataset.

| Lane | Primary source | Independent SZL ablation |
|---|---|---|
| Hybrid retrieval | [BGE-M3 / FlagEmbedding](https://github.com/FlagOpen/FlagEmbedding), [ColBERTv2](https://github.com/stanford-futuredata/ColBERT) | Compare BM25, current retrieval, dense+sparse fusion, and late-interaction reranking on a frozen BrainQrels-v2 split |
| Temporal graph memory | [Microsoft GraphRAG](https://github.com/microsoft/graphrag), [Graphiti](https://github.com/getzep/graphiti), [HippoRAG](https://github.com/OSU-NLP-Group/HippoRAG) | Keep the Lake canonical; test rebuildable temporal/PPR sidecars whose edges retain node hash, extractor revision, validity, and supersession |
| Calibrated abstention | [Semantic entropy](https://www.nature.com/articles/s41586-024-07421-0), [UQLM](https://github.com/cvs-health/uqlm) | Calibrate retrieval support, semantic entropy, and correctness probes; report risk-coverage, AURC, ECE, Brier, abstention accuracy, latency, and energy |
| Citation verification | [ALCE](https://github.com/princeton-nlp/ALCE), [RefChecker](https://github.com/amazon-science/RefChecker), [RAGChecker](https://github.com/amazon-science/RAGChecker) | Bind every atomic claim to node ID, revision/hash, and exact span; zero invented identifiers is a release gate |
| Bounded controller | [Self-RAG](https://github.com/AkariAsai/self-rag), [Adaptive-RAG](https://github.com/starsuzi/Adaptive-RAG), [GraphRAG DRIFT](https://microsoft.github.io/graphrag/query/drift_search/) | Compare no retrieval, always retrieve, current policy, and an adaptive controller with receipt-per-step and fixed hop/token/time ceilings |

Priority is citation integrity and abstention calibration first, retrieval ablation second, temporal graph third, bounded adaptive control fourth, and admitted behavior fine-tuning last. Create BrainQrels-v2 only from rights-admitted rows, freeze its splits and seeds, and report 95% bootstrap confidence intervals.

## Live estate API

Two read-only endpoints make the contract visible to A11oy:

- `GET /api/a11oy/v1/models/frontier-adoption` returns the pinned adoption contract and explicitly reports that it has no qualification, promotion, deletion, or mutation authority.
- `GET /api/a11oy/v1/models/estate` joins the pinned classification with the public no-key Hugging Face metadata API. Download counts are returned live and labeled as adoption signals, not quality scores.

Revision drift and newly discovered organization repositories are surfaced as `REVIEW_REQUIRED` or `UNCLASSIFIED_FAIL_CLOSED`. A zero download count never authorizes deletion.

## Archive and deletion policy

Do not delete the zero-download repositories. The pinned classification identifies three weight-bearing repositories; the runtime endpoint independently recomputes file-format observations from live Hub metadata. The remaining repositories are kernel packages, governance substrates, a model-program ledger, or a deliberately blocked evidence exhibit. Their value is not represented by model-download counts.

Archive only after all of the following are true:

1. no unique weights, adapters, kernels, receipts, citations, DOI references, discussions, or inbound links remain;
2. a replacement collection or repository exists with a visible redirect notice;
3. an immutable final release and independent readback receipt are retained;
4. a deprecation window has elapsed; and
5. the archive action is separately approved and recorded.

Deletion is reserved for legal, security, or privacy necessity and requires a tombstone receipt. It is not a growth tactic.

## Guard examples

Audit the contract without network or credentials:

```bash
python model_release/frontier-qualification/frontier_admission_guard.py audit
```

Metadata review is allowed for a pinned quarantine record, but training and promotion fail closed:

```bash
python model_release/frontier-qualification/frontier_admission_guard.py check \
  --repository empero-ai/Qwythos-9B-Claude-Mythos-5-1M \
  --revision 14a29bae5143091aeaf87ad37120de4cd57d592c \
  --operation READ_METADATA
```

A local download, evaluation, or method-adoption preflight requires an ECDSA-P256 DSSE envelope verifiable by the checked-in SZL public key. Its domain-separated payload type and signed body bind the repository, immutable revision, operation, and complete evidence declaration. Unauthenticated digest-looking strings are rejected. This verifies who attested to the declared receipt hashes; it does not independently reopen and recompute every underlying receipt or consume a run-bound nonce. The guard therefore reports a valid signed declaration as `operation_preflight_admitted=true` but keeps `operation_authorized=false`, `execution_authority=false`, and `replay_protected=false`. A future executor must bind and consume a run ID, host identity, policy digest, validity window, and nonce before execution. Metadata reads remain the only unsigned operation. Train, production serve, promote, merge, trace ingestion, and real-person identity editing are hard-denied in executable code regardless of registry contents.
