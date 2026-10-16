<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Python product production roadmap

Status: **ROADMAP**, with the bounded implementation below. A reachable site,
passed unit tests, loaded model or provider-reported `RUNNING` state does not
establish whole-product production readiness. This document does not authorize
a provider change, activate an action, or replace a release gate.

## Current implementation boundary

The [command centre](ATELIER_COMMAND_CENTRE.md) has a Python-authored,
server-rendered core at `/command-centre` and `/a11oy/atelier`.
[Python components](../routers/command_centre_view.py) render navigation and the
ownership projection; the existing guarded JavaScript action client and CSS
remain. Other product frontends have not all been migrated. The ownership view
is discovery, not an Ayllu backend integration or admitted council action.

The [governed loop](../szl_agent_loop_governed.py) distinguishes incomplete,
blocked and upstream-reported complete work. Its completion evidence remains
`UPSTREAM_REPORTED_UNVERIFIED`, with `receipt_verification_asserted=false` and
`model_qualified=false`. An `OBSERVED_COMPLETE` result therefore is not trusted
server acceptance, independently verified inference or permission to execute.
See [completion regressions](../tests/test_agentloop_completion_evidence.py).

## One product, explicit source owners

| Component | Retained authority | Planned integration boundary |
| --- | --- | --- |
| A11oy | [`szl-holdings/a11oy`](https://github.com/szl-holdings/a11oy); product `a-11-oy.com`; Space `SZLHOLDINGS/a11oy` | Python product shell and governed backend; migrate interactions incrementally with route, authorization, accessibility and receipt parity. |
| Ayllu | [`szl-holdings/ayllu`](https://github.com/szl-holdings/ayllu); Space `SZLHOLDINGS/ayllu` | Bounded advisory council/legal module under the A11oy experience. Logical fold is planned, not implemented. Preserve its independent source and publisher until a separately qualified migration. |
| Platform | [`szl-holdings/platform`](https://github.com/szl-holdings/platform) | Reuse reviewed contracts and behavior specifications. Its proprietary license boundary remains; no wholesale copying or implicit relicensing into Apache-2.0 packages. |
| Python engineering packages | [`szl-holdings/szl-platform`](https://github.com/szl-holdings/szl-platform), [`szl-substrate`](https://github.com/szl-holdings/szl-substrate) | Distinct source owners, not aliases of Platform. Admit versioned dependencies after compatibility and provenance checks. |
| Model inference | [`szl-holdings/szl-forge`](https://github.com/szl-holdings/szl-forge/tree/f4688d2233ed4123995fab7861b9a074f60cc3d5/spaces/szl-model-inference-lab), existing `SZLHOLDINGS/szl-model-inference-lab` | Reuse a bounded, explicitly selected model lane; model publication and qualification remain separate from the product shell. |
| Proof origin | [`szl-holdings/a11oy-net`](https://github.com/szl-holdings/a11oy-net); `a11oy.net` | Read-only proof and inventory projections, not execution authority. |

The existing [public-estate contract](../static/shared/public-estate-contract.v1.json)
owns topology; [measured membership](huggingface-ecosystem-manifest.json) and the
[keep policy](series-a/hf-space-keep-list.yaml) remain separate. Extend their
[deterministic renderer](../scripts/render_public_estate_alignment.py), not a
parallel registry. Ayllu's current `INVENTORY_ONLY`, `governedKeep=false`, `FOLD`
classification is a policy disposition, not a completed migration. Current PRISM
Counsel and Ayllu are separate implementations; route parity must be demonstrated
before a shared legal capability is admitted.

Canonical GitHub organization is `szl-holdings`; HF namespace is `SZLHOLDINGS`.
Public API observations on 2026-10-15 UTC returned 128 public GitHub repositories,
48 model records, 37 datasets, 38 Spaces including the reserved README Space,
and 14 native kernel records. These are dated inventory counts, not trained-model
quality or production capability counts. Private inventory is not projected.
Use the [public Hub API](https://huggingface.co/api/organizations/SZLHOLDINGS/overview)
and the existing timestamped [proof inventory](https://a11oy.net/public-inventory.json)
for subsequent observations; preserve differing observation times and scopes.

`hf-sync.yml` remains the sole automatic publisher to `SZLHOLDINGS/a11oy`.
Ayllu retains its own source-owned `hf-space.yml`. Publication requires protected
GitHub source, exact deployment-file binding, immutable Hub readback, runtime
source verification and product/proof checks. A repository link or shared screen
does not grant publisher authority. This work deletes, archives, renames or
consolidates no repositories or Spaces and creates no second publisher.

## Free-first operating budget

New hosting and model spend must remain **at or below $100/month in aggregate**.
Reuse existing resources and open-source/open-weight candidates first, subject
to their exact software, weight and dataset licenses. No paid resource, hardware
upgrade or model purchase is created by this work.

The [HF hardware documentation](https://huggingface.co/docs/hub/spaces-gpus),
observed 2026-10-15 UTC, lists CPU Basic at no hourly charge, CPU Upgrade at
`$0.03/hour` (about `$21.90` for 730 hours), and T4 small at `$0.40/hour`
(about `$292` for 730 hours). CPU Basic can sleep after 48 hours of inactivity;
it is not an availability commitment. Existing plan, storage, transfer, taxes
and any other recurring charges require separate accounting. Prices and quotas
must be checked again before provisioning. Continuous T4 hosting does not fit
this ceiling.

ROADMAP: bind per-request and monthly token/cost ceilings to server policy,
reserve budget before dispatch, reconcile actual usage, cap concurrency and
reject exhausted or unknown-cost work. Keep the selected model/backend explicit;
do not silently fall back to a paid provider, different model or automatic retry
after an ambiguous timeout. Separate usage telemetry from enforced admission.

## Production admission work, in dependency order

1. **Identity and custody.** Bind stable operator/tenant identity, least-privilege
   scopes, revocation, browser session/CSRF protection and audit attribution to
   each admitted action. Preserve policy denial before inference or writes.
   Sandbox/code execution requires genuinely separate second-approver custody;
   a second token held by the same actor or a client-supplied attestation flag
   is not that custody. Ayllu's demo HumanLock is not production authentication.

2. **Model and budget qualification.** Choose one license-compatible model,
   immutable artifact identity, backend, task suite and budget. Run held-out
   task, abstention, adversarial and grounding evaluations with explicit pass
   thresholds; measure latency, throughput and cost on the intended hardware.
   The existing CPU lab is a candidate for bounded advisory work, not general
   qualification: its documented Khipu lane limits concurrency to one and output
   to 32 tokens; the owner reports research-only abstention evidence. Loaded-file
   hashes, health responses, asset counts and model-card rankings do not replace
   evaluation. Enforce no-fallback budget policy before admitting live use.

3. **Trusted server acceptance for five exact POST contracts.** Preserve the
   [readiness matrix](../tools/readiness-harness/tabs.json) and GET/HEAD-only
   observer. A separately governed, bounded producer must establish positive
   semantic outcomes for `/api/a11oy/v1/policy/decide`,
   `/api/a11oy/v1/operator/ask`, `/api/a11oy/v1/policy/compliance`,
   `/api/a11oy/v1/eval/run` and `/api/a11oy/v1/agentloop/run`. Bind canonical
   origin, deployed source, fixture/task, selected model, execution identity,
   freshness, effect scope and response digest; verify the trusted producer
   identity and applicable receipt signatures/chains. Test tampering, replay,
   duplication, stale/foreign evidence and unknown outcomes. HTTP 200, generic
   objects, input-validation errors and upstream self-reports are insufficient.
   Keep denied, unavailable, modeled and completed outcomes distinct. Acceptance
   of a compliance route does not certify regulatory compliance; chat-loop
   acceptance does not qualify sandbox execution.

4. **Durability and recovery.** New stores must use
   [`a11oy_state_store`](../a11oy_state_store.py) under
   [ADR-0001](adr/ADR-0001-a11oy-state-store.md), not a new storage stack or a
   writable SQLite/LMDB database on the `/data` object mount. Define acceptable
   recovery point and recovery time objectives; verify backup, restore, lease fencing,
   overlapping-container handover, interrupted snapshots and tenant isolation.
   ADR-0001 explicitly allows loss of acknowledged writes newer than the last
   snapshot after an unclean takeover (about 30 seconds for a burst or 300 under
   continuous writes); snapshot failures can extend exposure. Do not claim
   zero-loss durability. Tighten the design if the required recovery point is
   smaller. Check `/api/a11oy/v1/storage/status`; a mount alone proves neither
   recovery nor backup freshness.

5. **Capacity and release qualification.** Declare availability, latency,
   concurrency, error-rate and recovery SLOs for the selected workload. Exercise
   authenticated load, cold starts, provider timeout, exhausted budget, signer
   outage, storage failure, deployment rollback and alert delivery. Capture
   source-bound browser/accessibility proof and backend acceptance from the
   same deployment. Publish through the existing writer only after its gates
   pass; retain rollback and recovery evidence. Re-observe operational capability
   status independently: closing five route contracts does not establish energy
   measurement, sovereign compute, signed bundles or every governance capability.

Exit condition: a documented, bounded workload passes all applicable admission,
recovery, model and SLO gates on an exact deployed revision. Until then, expose
the measured capability and its limits; retain HOLD/UNAVAILABLE for missing
evidence. A Python rewrite or logical repository fold is not itself that exit
condition.
