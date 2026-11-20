# Khipu frontier: proof-gated handle navigation

Date: 2026-11-19 UTC. Owner: szl-holdings/a11oy. State: SOURCE CANDIDATE / NOT RELEASED.
Separate incident: https://github.com/szl-holdings/a11oy/issues/3776

## Measured motivation

Local BETTERWITHAGE Khipu had 0/3 strict plan-schema passes on three novel synthetic cases. With JSON Schema-constrained output, 2/2 results were structurally valid but the cited target selection and evidence-free abstention were still incorrect. This is not an independent trained model evaluation.

Existing ayllu/backend.py checks that citedNodeIds belong to offered handles, but did not conjunctively validate the Khipu NAVIGATE/ABSTAIN decision, CITE step set, and independent evidence (node ID, chunk ID, SHA-256) identity. The first-party pure Khipu plan guard adds those structural checks. It never supplies private document text to models or claims a signed/executed action.

## Mathematical invariant candidate, not a formal proof

Let O = controller-offered IDs; P = model-selected distinct candidate IDs; C = cited IDs; T = step sequence; E = controller-derived (node, chunk, SHA-256) tuples.

StructuralAdmit = Shape AND Identity AND (C subset P subset O)
  AND CiteSteps(T) = C AND DecisionConsistent AND EvidenceBound.

NAVIGATE requires nonempty C, null abstainReason, uniquely cited CITE steps, step IDs within P, and each cited ID's source tuple present in E.
ABSTAIN requires empty C, empty T, and a nonblank abstainReason.
Both require the original exact query, HANDLES_ONLY, MODEL_PROPOSED, groundedOnly true, and NOT_RESOLVED Brain status. No claim of model-accessed content or execution is permitted.

Even when structural admission passes: semantic_relevance_verified=false, execution_authorized=false, signer_verified=false. This is a structural gate, not an assertion that any cited handle actually answers the question.

ProductionAdmission = StructuralAdmit AND IndependentSemanticEval AND
  VerifiedWeightBytes AND AuthenticatedIngress AND IndependentlyVerifiedReceipt
  AND ProtectedSourceAndOwnerApproval.

None of the additional factors follows from a passing unit test or local completion.

## Source integration and compatibility

ayllu/backend.py retains existing legacy PLAN / citedNodeIds membership semantics; its previous receipt-verifier state CITATIONS_WITHIN_OFFERED_HANDLES still means only set membership. For explicit NAVIGATE or ABSTAIN outputs, a second independent validation occurs before returning model text. Invalid proposals return no model answer and retain only fixed reason labels and output SHA-256. The plan_invariants diagnostic explicitly keeps execution, semantic relevance, and signing flags false.

No new database, package dependency, model weights, provider, network service, training set, secret, or API was added.

## Leaders and source-backed, falsifiable concept transfers

| External source | Research / code | SZL experiment — not an adopted implementation |
|---|---|---|
| Microsoft GraphRAG | https://www.microsoft.com/en-us/research/publication/from-local-to-global-a-graph-rag-approach-to-query-focused-summarization/ ; https://github.com/microsoft/graphrag | Separate local source retrieval from global graph synthesis and measure recall on rights-cleared fixtures. No private graph export. |
| Stanford DSPy / GEPA | https://arxiv.org/abs/2507.19457 ; https://github.com/stanfordnlp/dspy | Future prompt optimization with independent synthetic train/held-out split and explicit abstention metric; not part of this change. |
| OpenAI Structured Outputs | https://openai.com/index/introducing-structured-outputs-in-the-api/ | Syntax constraints do not prove target relevance: add a second independent acceptance gate. |
| Scale / Reflection SWE-bench Pro V2 | https://labs.scale.com/leaderboard/swe_bench_pro_public_v2 | Red/green adversarial fail-to-pass tests plus pass-to-pass regression on clean exact source. |
| SLSA v1.2 | https://slsa.dev/spec/v1.2/build-provenance | Verify source/builder/artifact subject/signature separately from model-generated hashes. |
| Lean 4 and mathlib4 | https://github.com/leanprover/lean4 ; https://github.com/leanprover-community/mathlib4 | Possible later proof of finite set inclusion, no duplicate citation, ABSTAIN with no actions. Python tests are NOT Lean proofs. |
| DeepSeek, China | https://arxiv.org/abs/2412.19437 ; https://github.com/deepseek-ai/DeepSeek-V3 | Study efficient routing under hardware limits; do not claim a 671B model can run on local laptop. |
| LG AI Research, Korea | https://arxiv.org/abs/2608.04505 ; https://github.com/LG-AI-EXAONE/K-EXAONE-2.0 | Rights-cleared long-context/multilingual relevance and abstention tests, not weights or output copying. |
| TerminusDB, Ireland-founded | https://terminusdb.com/docs/knowledge-graph-database-version-control/ ; https://github.com/terminusdb/terminusdb | Versioned graph evidence IDs for existing Lake; no replacement database without consistency/performance proof. |

External papers, code and hosted models are untrusted research inputs; any code reuse would need independent license review. This source change imports no external code.

## Kimi peer review — challenged and narrowed

Two bounded calls used kimi-k3.1-pro:cloud via Ollama with public research summaries only, no private graph content or credentials. One broad response hit the output-token cap; a second concise adversarial critique completed. Kimi suggested testing repeated CITE action IDs, wrong node-to-evidence tuple pairings, and abstention with hidden steps. New tests initially exposed the repeated CITE weakness; the guard was revised to reject it. We rejected an earlier suggestion to inspect raw node text within the model: that violates SZL's HANDLES_ONLY boundary.

Kimi was a non-authoritative hypothesis generator. Actual cloud billing was not independently audited; no continuous process or external tool privileges were created.

## Next independent acceptance gates

1. Run all focused unit and backend integration tests on exact PR head and require clean, passing GitHub CI. Test malformed/unhashable input, invented candidates, evidence digest mismatch, duplicate CITE, NAVIGATE without support, ABSTAIN with actions, and legacy compatibility.
2. Human review confirms legacy receipt contract and independent source ownership. No automatic merge or deployment.
3. Complete frozen, licensed held-out semantic routing and abstention evaluation with offered/cited denominators; model text never self-certifies relevance.
4. Reconcile actual local Khipu weight bytes with immutable Hugging Face GGUF and signed training/quantization receipts.
5. Authenticate governed HTTPS cloud inference ingress, enforce immutable model pin and signed turn verification, and preserve A11oy source/HF deployment parity. Until then the production P0 remains HOLD.

No model files or user evidence should be automatically deleted; cleanup is limited to created temporary scripts and cache files after all receipts are retained.
