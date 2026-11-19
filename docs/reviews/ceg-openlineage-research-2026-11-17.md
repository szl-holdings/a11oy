<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# CEG lineage interoperability and serving research, 17 November 2026

## Decision and boundaries

This change projects A11oy's existing Canonical Evidence Graph (CEG) into
OpenLineage 2.0.2 static job metadata and exposes parent references that do not
resolve within the returned bounded graph. It does not create a second graph,
new storage, a remote publisher, a model serving path, an execution receipt,
or an authorization path.

Source of truth: szl_evidence_graph.py and the reviewed receipt bundle.
Operator surface: /command-v2 (Evidence room).
Read-only APIs: /api/a11oy/v1/evidence/graph,
and /api/a11oy/v1/evidence/openlineage.

The OpenLineage projection is a JobEvent, never a RunEvent. An observed edge
is a data dependency for the snapshot export, not proof that an inference,
training run, deployment or user action succeeded. The output snapshot name
is the existing CEG digest; neither that hash nor the linkage score authenticates
the upstream observer.

## Leaders, public code, publications, and specific takeaways

| Leader / primary source | Concrete mechanism | SZL adaptation | Avoided claim |
| --- | --- | --- | --- |
| Palantir Foundry Workflow Lineage | Maps actions, models, functions, objects and their downstream dependencies; displays model lifecycle state and supports refactor tracing. https://www.palantir.com/docs/foundry/workflow-lineage/overview | Show unresolved in-view evidence parents next to the current A11oy evidence graph. Keep model inventory, declared interfaces and runtime assertions distinct. | Palantir implementation, source code or proprietary performance is not reproduced. |
| Palantir public Ontology SDK | Published client SDK maps typed Ontology entities, actions and queries; https://github.com/palantir/osdk-ts | Reuse only the documented client-boundary principles, with A11oy's own permission and evidence model. | Public SDK is not Palantir's proprietary Ontology or AIP backend. |
| Palantir Ontology actions | Action type specifies the permitted object changes and side effects. https://www.palantir.com/docs/foundry/action-types/overview | CEG remains observational. No graph field can override the pre-existing deterministic admission gate. | A lineage edge does not ALLOW execution. |
| OpenLineage specification 2.0.2 | JobEvent is static job metadata with inputs/outputs; RunEvent represents execution. https://openlineage.io/docs/spec/ and https://openlineage.io/spec/2-0-2/OpenLineage.json | Export a schema-validated JobEvent that names only the included edge IDs as inputs and the graph digest as output. Do not invent runId or COMPLETE. | No OpenLineage backend publishing or job execution claim. |
| OpenLineage source | Standardized job, dataset and run identities; facets require versioned schema references. https://github.com/OpenLineage/OpenLineage | No unversioned custom facet schema. Reuse existing CEG payload instead of wrapping confidential inputs in facets. | Static metadata does not prove a real production pipeline ran. |
| NVIDIA Dynamo | A distributed inference control plane: KV-aware routing, prefill/decode separation, SLO-aware benchmarking and health. https://github.com/ai-dynamo/dynamo and https://docs.dynamo.nvidia.com/dynamo/user-guides/disaggregated-serving | For SZL's 2x RTX A6000 service, measure workload, VRAM occupancy and TTFT/ITL before considering disaggregation. Keep Maya/Bonsai active services untouched. | Hardware-specific vendor throughput numbers are not A6000 measurements. |
| vLLM / PagedAttention | KV cache paging and sharing to reduce fragmentation; SOSP 2023 publication. https://github.com/vllm-project/vllm and https://doi.org/10.1145/3600006.3613165 | Benchmark cache residency and replay on the actual serving models before engine selection. | Downloaded model bytes are not loadability or inference quality. |
| DistServe / OSDI 2024 | Separates prefill and decode to optimize SLO goodput, including placement and communication cost. https://www.usenix.org/conference/osdi24/presentation/zhong-yinmin | Compare aggregated vs disaggregated only if the measured traffic and free hardware justify a split. | Paper speedups are not transferred to SZL. |
| NVIDIA AIPerf | Defines client-observed TTFT, ITL, goodput and energy-delay product. https://docs.nvidia.com/aiperf/reference/ai-perf-metrics-reference | Adopt transparent metric definitions and report sample count, measurement window, workload and precision. | Unmeasured joules remain UNAVAILABLE, never zero. |
| LangGraph fault tolerance | Persist task boundaries; a started but uncompleted task may rerun after recovery. https://github.com/langchain-ai/docs/blob/main/src/oss/langgraph/functional-api.mdx | Preserve decision/outcome separately; remote mutation retry requires operation ID and reconciliation. | Receipt-on-write is not exactly-once remote execution. |

## Mathematical contract

Let E be receipt IDs included in the bounded snapshot, and let P be the set
of DISTINCT referenced parent IDs of those included edges:

    P = union(edge.parents for edge in included_edges)
    R_view = |P intersect E| / |P|, when |P| > 0
    R_view = null (UNAVAILABLE), when |P| = 0
    unresolved_in_view = sorted(P minus E)

R_view is topology resolution within the returned view, NOT fraction of correct
claims, not signature verification, not execution permission, and not full-ledger
coverage. A truncated view may mark a parent unresolved even if it exists in
an omitted part of the source. Returned unresolved IDs are bounded to a
16-identifier preview; the full unresolved count remains explicit.

The graph digest is unchanged:

    H_graph = SHA256(canonical_json({schema: graph_schema, edges: included_edges}))

The deterministic CEG serializer is not asserted to be RFC 8785 and the graph
digest is not an ECDSA signature. EvidenceEdge's receipt IDs are checked when
projecting to OpenLineage, and a caller-supplied mismatch is rejected.

NVIDIA AIPerf's directly sourced streaming definitions are:

    TTFT = t_first_content - t_request_start
    ITL = (t_final - t_first_content) / (output_tokens - 1), if tokens > 1
    goodput = count(requests meeting ALL declared latency SLOs) / window_seconds
    energy-delay-product = energy_per_request * mean_request_latency_seconds

For token counts of one or zero, ITL has no valid denominator. Goodput without
an SLO and measured window is unavailable. For an inference router, apply hard
policy eligibility BEFORE quality/latency/cost/energy optimization. Optimization
cannot turn a deterministic DENY into ALLOW. Treat Lambda as advisory
Conjecture 1, Khipu BFT as Conjecture 2, and the locked-proven formula count as 8.

## API/frontend integration

The existing read-only graph API now additionally returns parent_resolution:
state, unique denominator, resolved/unresolved counts, nullable ratio, bounded
preview, and signature-verified false. This is additive; the CEG digest and
historical graph schema remain unchanged.

The new endpoint returns an OpenLineage JobEvent, not a wrapper masquerading as
one. It names the included CEG edges as input datasets and the existing bounded
graph digest as one output dataset. It checks edge IDs, graph digest, order,
coverage counts, bounded flag and UTC observation time before projection. A
missing receipt bundle causes HTTP 503 rather than an empty-success export.
No network calls or new writes occur in the route.

The Evidence room in /command-v2 now shows the parent-reference state and
links to the static lineage JSON. That link does not trigger an automatic fetch
during page load. Parent-reference ratio null renders as unavailable instead
of fabricated 100% coverage.

## Verification and remaining admission gates

Local focused evidence/backend suite and Command v2 frontend suite are required.
The emitted example was also validated directly against the published
OpenLineage 2.0.2 JSON Schema using Draft 2020-12 with URI/date-time checking.

This change is source-only until the protected-branch CI gate, merge, canonical
HF sync and exact deployed build identity are all observed. There is no claim
that a PR or a local test alone makes A11oy production-ready.

Still required for comprehensive production:
1. Complete per-model weight SHA-256, license, adapter/base compatibility,
   actual loaded-engine identity and successful inference evidence.
2. Source/runtime SHA equality and independent HF Space readback after deploy.
3. Distinct state-store health: fencing, snapshots, CAS lease and last unresolved
   errors, not merely a 200 liveness response.
4. Policy-signed mutation receipts with explicit remote operation IDs and
   timeout reconciliation, rather than automatic replay of uncertain POSTs.
5. Measured latency/goodput/energy on held-out A6000 workloads and a comparison
   against simple aggregated serving before introducing Dynamo or vLLM.
6. Cross-repository mapping of Github, HF, Cloudflare and PyPI identities
   without treating marketing or metadata as authorization.

The proposed next capability is an operator-visible minimum missing-evidence
explanation for each requested action. Derive it from the existing graph and
deterministic admission policy, with no model-selected approvals; first test on
public scientific-data provenance and reproducible analysis workflows.
