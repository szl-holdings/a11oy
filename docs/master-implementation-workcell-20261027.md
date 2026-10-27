<!-- SPDX-License-Identifier: Apache-2.0 -->
# SZL master implementation workcell — 2026-10-27

Evidence class: **DECLARED source report** with a bounded local implementation
slice. The machine-readable DAG is
[`data/master_workcell_dag_20261027.json`](../data/master_workcell_dag_20261027.json).
The branch is `feat/master-rag-dag-program-20261027`, based on
`2ce00a0430088100a0d5f076d315bfd6e0e8e712` (`origin/main`) when this workcell
was created. The artifact records that base head and uses a `CANDIDATE_COMMIT`
marker because the candidate head is produced by this workcell. It must not be
read as an exact-head CI or provider-publication witness.

The workcell covers the requested RAG/DAG, ORO, Second Brain, Living Anatomy,
Hatun MCP, a11oy Code, formula authority, and Cloudflare gateway surfaces. It
does not merge, deploy, publish, change DNS, read secrets, or authorize an
external write. The overall integration state is **BLOCKED** because provider,
hosted-runtime, and external-authorization gates are not established here.

## Current source and ownership boundary

- The local tree was clean at the start of this workcell. A sibling checkout at
  `C:/Users/steph/szl-orchestration/a11oy` owns the older
  `feat/oro-evidence-dag-integration-20261013` lane and its ORO source/tests.
  Those files were not edited or cherry-picked.
- PR **#2731** is present in the current ancestry as
  `4b5bb09922a1d2dcdd41fa60567e7138e0226e82`. The follow-up audit says its
  checks do not qualify the later candidate; this workcell treats it as
  historical source context only.
- PR **#2775** was not independently confirmed. The local current-main history
  contains `e6cf9d06c92827225054550533e1a091b59f1031`, whose commit body records
  source provenance `#2775 cd0298c9d610c2bd0a5b4eb969a5f86055ab087`; the
  `cd0298c9...` object is not present locally. `gh pr view 2775` returned
  `HTTP 401 Requires authentication`, so live PR state is **UNKNOWN** and is
  not inferred from #2776.

## Integration posture

The source inventory is intentionally separated from runtime and authorization:

| Area | Status | Boundary |
| --- | --- | --- |
| Formula authority | DECLARED | `formula_registry/formula-registry.v1.json` pins exactly F1, F4, F7, F11, F12, F18, F19, F22. Λ is Conjecture 1; Khipu BFT safety is Conjecture 2. |
| RAG engine | DECLARED | Graph + FTS5 + dense retrieval contracts exist; GET is read-only and POST requires the existing operator boundary. Hosted corpus and source identity are not proven. |
| Brain graph | MODELED | `/api/a11oy/v1/brain/graph` is a derived graph view. Rendering does not grant authority or proof. |
| ORO projection | REPORTED | The bounded projection is read-only and UNVERIFIED; it has no execution, promotion, or signing authority. Historical local evidence is retained in `audit/oro-dag-integration-20261013.md`. |
| Second Brain | DECLARED | Handles-only, bounded bridge contract; external runtime and content-byte verification remain UNKNOWN. |
| Living Anatomy | MODELED | v6 evidence is read-only and summary-only; unreadable overlays are UNAVAILABLE. No clinical validation is implied. |
| Hatun MCP | UNKNOWN | The local REST catalog is bounded; deployed JSON-RPC `/mcp/` is documented as unavailable/405 and no execution proof is claimed. |
| a11oy Code | DECLARED | Deterministic, governed proposal/receipt paths and negative tests exist; provider/model/runtime qualification is UNKNOWN. |
| Cloudflare gateway | DECLARED | Worker contracts and fail-closed preflight exist; production route, tunnel, DNS, and deployment state are UNKNOWN. |
| Backend workcell endpoint | DECLARED | `GET /api/a11oy/v1/workcell/status` validates the committed artifact and returns 503/UNAVAILABLE on missing or malformed bytes. Python tests are NOT RUN in this environment because no permitted Python interpreter is available. |
| Status UI | DECLARED | `/status` now serves the source-tree page when the absent `web/status.html` is not present and renders the workcell contract. Browser/runtime state remains UNKNOWN. |
| Provider publication | UNKNOWN | No Hugging Face publication or immutable Space commit readback was performed. |
| Hosted runtime | UNKNOWN | Local source wiring is not a runtime, storage, energy, signer, or independent-witness proof. |
| Authorization | BLOCKED | No credentials, DNS, deployment, merge, or production writes were used. |

## Bounded implementation slice

`szl_master_workcell.py` is a GET-only adapter over the committed JSON DAG. It
rejects duplicate keys, schema drift, invalid honesty labels, a changed locked
formula set, unknown edge endpoints, and malformed node metadata. A missing or
malformed artifact returns HTTP 503 with `status=UNAVAILABLE`; the handler does
not probe a provider, invoke inference, write storage, or mint/sign a receipt.

`serve.py` registers the adapter before the application catch-alls. The
Dockerfile copies both the module and the artifact because this image uses
per-file source admission. `pages/status.html` consumes the endpoint and paints
declared labels verbatim. Network errors, non-JSON responses, schema mismatch,
and non-2xx responses paint `UNAVAILABLE`; an HTTP 200 is never converted to
LIVE, MEASURED, READY, or an authorization result.

## External concept benchmark (study only)

No external implementation or weights were copied. The following are bounded
concept references for a future held-out comparison:

- **Headroom** describes type-aware, reversible compression of tool outputs,
  logs, files, and RAG results while preserving the system prompt and older
  turns; its documentation also describes a local cache/retrieve path. See
  [Headroom introduction](https://docs.headroomlabs.ai/docs) and its
  [architecture notes](https://github.com/headroomlabs-ai/headroom/blob/main/docs/content/docs/architecture.mdx).
- **Microsoft GraphRAG** describes an indexing pipeline that extracts entities,
  relationships, and claims, detects communities, writes summaries, and emits
  table/vector outputs. See the
  [official GraphRAG overview](https://microsoft.github.io/graphrag/index/overview/).
- **LightRAG** describes graph-structured indexing with dual-level retrieval and
  incremental updates in its paper. See
  [LightRAG, arXiv:2410.05779](https://arxiv.org/abs/2410.05779). Any future
  study must pin the implementation revision and license; no fork is an SZL
  authority.

The safe SZL benchmark dimensions are retrieval quality on a held-out corpus,
latency, token volume, citation/receipt overhead, and refusal behavior. External
reported savings or accuracy are not SZL measurements and are not copied into
the DAG as results.

## Validation and security

The following checks were prepared for this workcell:

```text
python -m pytest -q tests/test_workcell_status_surface.py
python -m pytest -q tests/test_status_aggregate.py tests/test_rag_route_readonly.py tests/test_hatun_evidence_contract.py
node --check <extracted inline script from pages/status.html>
python scripts/check_banned_tokens.py --root . --allowlist .doctrine-allowlist
git diff --check
```

`git diff --check` and the JavaScript syntax check were run. The Python test and
doctrine/security commands were **NOT RUN** because this managed environment has
no permitted Python interpreter on the PATH and the known Python installation is
access-denied. A changed-file secret-pattern scan and the Node JSON contract
check passed. No result is upgraded from NOT RUN to pass.

## Blockers and next milestones

1. Refresh PR #2775 with authorized read-only GitHub access and compare its exact
   head/rules/checks before deciding whether any follow-up overlaps active work.
2. Run the focused Python backend/UI/security suites on an authorized executor
   and retain their exact receipts.
3. Use the protected normal merge path, then let the canonical `hf-sync.yml`
   writer publish and independently read back the immutable Space commit and
   build identity.
4. Only after source and provider gates pass, perform target-bound runtime and
   public-route probes. A healthy HTTP response, Space `RUNNING`, or local UI is
   not a readiness or certification claim.
