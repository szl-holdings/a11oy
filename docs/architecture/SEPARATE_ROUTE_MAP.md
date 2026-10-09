<!-- SPDX-License-Identifier: Apache-2.0 -->
<!-- SZL Holdings | Stephen P. Lutar | ORCID 0009-0001-0110-4173 -->
# Separate route map

Evidence class: source inspection at a11oy `1b4f64342d5be7da809fd1448b00e9654ca4fbd2`. The run-loop files in this change were unchanged between `15e3bf583a4eadf95c91baa002f8e1438fa8db9c` and that main. Other repositories stay at the operator-cited pins below. These are separate routes. No integration test in this change proves they call each other. Do not read this page as one runtime.

The vertical slice added here owns only route A’s plan and run-step admission. It does not enable `SZL_SECOND_BRAIN_RAG`, does not edit the completion handler, and does not make the in-memory Khipu DAG persistent.

## A. Code run-loop

`web/code.html` posts to `/api/a11oy/v1/code/plan` and `/api/a11oy/v1/code/runstep`.

`a11oy_code_runloop.py` registers those routes. A run step calls `a11oy_code_engine.governed_turn`. The engine’s retrieve hook is `szl_agentic_loop._retrieve` (`szl_agentic_loop.py` around lines 644–685): it tries `a11oy_org_rag.query`, and on failure or abstain uses the in-image governance corpus.

This slice checks the operator principal, the `A11OY_CODE_TENANT` header `x-a11oy-tenant` compared as equal-length SHA-256 digests, the closed purpose set `chat|code|research`, and the query limits before `plan()` or `governed_turn`. The fixed frontend query is the rights-cleared string `synthetic fixture: deny-by-default gate`. An unsigned engine receipt is stored as `SIMULATED`. The append-only file exists only when `A11OY_CODE_RUNLOOP_RECEIPT_LOG` is set. The open requests mode `0o600`. That bit is not a Windows ACL proof. Unset means `persisted` false and `restart_verifiable` false. The record field for the query is `query_sha256`. The engine receipt chain is stored unchanged so `verify_run` can recompute it, and that chain still contains the step prompt. The tenant identifier and the operator token are not written. `verify_receipt_log` re-reads that file and calls `a11oy_code_engine.verify_run`. `chain_intact` true with `signature_valid` false is an unsigned chain check, not a host signature and not a deployment claim. A fsynced append sets `restart_verifiable` true; the check itself is a later process.

## B. Completion aliases

`POST /api/a11oy/v1/code/route`, `/code/auto`, and `/code/complete` are implemented in `serve.py` (`_ac_route_impl` at line 11900, `_ac_complete` at line 11847). Operator refusal runs before the body is parsed. The query limit there is 8,192 UTF-8 bytes. That handler does not check tenant or purpose.

`SZL_SECOND_BRAIN_RAG` is read at request time and is on only for `1`, `true`, or `yes` (`serve.py` around line 11713). The default is off. When enabled, `_ac_second_brain_augment` calls `packages/inference/src/retrieval/second_brain_bridge.py` `retrieve_handles`, which posts to `https://szlholdings-second-brain.hf.space/api/v1/retrieve`. `content_hash_verification` stays `UNKNOWN` (`serve.py` around line 11762). A hash-shaped pointer is not verified document content.

The completion receipt is emitted through `szl_provenance.py`. That module states the Khipu DAG is in-memory per Space and non-persistent across restart (lines 41 and 800). This slice does not change that contract and does not turn the completion path into the run-loop log.

## C. Holographic and estate surfaces

`static/3d/surfaces/brainquery.js` sets `EP_ASK` to `/api/a11oy/v1/brain/ask` (line 40).

`static/3d/surfaces/governedrag.js` sets `EP_QUERY` to `/api/a11oy/v1/rag/query` (line 36).

Estate RAG is `POST /api/a11oy/v1/rag/estate/query` (`serve.py` around line 9436), operator-gated in `szl_operator_auth.py`.

`routers/governed_graph_operations.py` sets `EXECUTION_MODE` to `PLAN_ONLY` and `EVIDENCE_LABEL` to `MODELED`. Its status truth boundary is zero effectors, zero writes, zero provider calls, and zero emitted receipts (lines 837–841). Analyse does not run the code engine and does not write the run-loop receipt log.

## D. Public Second Brain runtime

The public runtime is `szl-second-brain` at the cited pin `c96fd1f309a0a7298b89e8469f58fecaeada8fb3`. `app_operational.py` `GET /api/v1/retrieval-capabilities` returns `public_runtime_mode` `BM25_ONLY`, `dense_provider` `NOT_CONFIGURED`, and `reranker` `NOT_CONFIGURED`. The same payload lists hybrid mode names as available labels and leaves training, promotion, and execution authority at `NONE`. A library mode name is not a configured provider. This a11oy change does not call that endpoint.

## E. Hatun adapter and Anatomy projection

Hatun’s `hatun_mcp/adapters/second_brain.py` at pin `1f7cc3eb5a38340ebfc431f9ba46a11ee136b726` recognizes four literal handles: `khipu.handle.alpha`, `khipu.handle.beta`, `nav.waypoint.17`, and `receipt.bind.owner-pubkey`. Its local `call` returns only handles that appear in the query, with `hydrated` false. Its default base is `https://szlholdings-szl-second-brain.hf.space`. That is not the a11oy bridge URL in section B, and this adapter is not `retrieve_handles`.

Anatomy is a separate repository. At pin `4f7ab4b4589cb839e4e45025ffaef3085c79f448`, `pipeline_observation.py` returns the projected DAG with `state` `MODELED_PLAN_ONLY` and `execution_authorized` false. This a11oy change does not import that module.

## What this change does not join

No test here sends one query through A, B, C, D, and E. The run-loop receipt log is not the Khipu DAG, not the public Second Brain retrieve API, not the Hatun local adapter, and not the Anatomy projection.
