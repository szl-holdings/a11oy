<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Private training observations in the model view

Taxonomy: services/provenance. This change connects the canonical training
observer's report to a restricted API and a separate operator panel on
`/frontier-tooling/models`. It creates a read-only consumer of external telemetry.
It does not create a training controller, database, retention service, signer,
publication path, or promotion authority.

Implementation and local route-group acceptance do not establish production
deployment. Hosted availability additionally requires the canonical publisher,
runtime readback, operator/tenant configuration, and the canonical producer input
on that runtime. An unset or inaccessible input returns UNAVAILABLE after auth.

## Ownership and data flow

The producer remains `tools/salad/training_observer.py` in
[szl-gpu-bridge](https://github.com/szl-holdings/szl-gpu-bridge).
The reader accepts `szl.training-observation/v1`. It never edits or copies that
report and never treats file modification time as an observation time.

1. The producer atomically replaces its report after observing its configured
   candidates. Its own supervision and credentials remain outside this reader.
2. An admitted operator requests the fixed API with the existing operator and
   tenant headers.
3. The handler reads one bounded local file, validates its producer contract,
   computes expiry, and projects an allowlist of fields.
4. The browser validates the projection and displays the same revision, step,
   digest and expiry. A refresh error clears the previously displayed records.
   Local expiry does not require another successful server response.

The public model inventory and its packaged snapshot retain their existing
contract. Current private reports are not included in those assets, public CEG
observations, public event streams, examples, or committed test fixtures.

## Configuration

Use the existing owner-managed `A11OY_CODE_ADMIN_KEY` and `A11OY_CODE_TENANT`
settings. The GET/HEAD handler validates both before any source file access.
The global operator middleware's GET exemption is not used as read authorization.

`A11OY_TRAINING_OBSERVATION_FILE` names the producer's local, absolute report path.
For example, an operator-controlled deployment can mount the producer directory
read-only at `/run/a11oy-observer/` and select
`/run/a11oy-observer/training.json`. This is a configuration example, not a claim
that the mount or a cross-host transport exists. The setting is captured at route
registration; changing it requires restarting that reader instance.

The reader rejects URL/UNC inputs, relative paths, traversal, links/junctions,
directories and special files. POSIX reads retain directory handles and use
no-follow opens for every component. Windows reads check reparse attributes and
the opened file handle's final path. Reads are capped at 1 MiB and run in the
framework's synchronous-handler thread pool. No query, request body, caller clock,
or request-selected path can reconfigure the source.

The route is `GET/HEAD /api/a11oy/v1/models/training-observations`. Responses use
`Cache-Control: private, no-store` and vary on operator/tenant headers. Unsupported
methods are refused. The namespace is also in `serve.py`'s local-only proxy
defense so a failed registration cannot forward these credentials to a generic
upstream.

## Evidence interpretation

| Field or state | What it establishes |
| --- | --- |
| `reportSha256` | Identity of the exact bytes read by this request; no producer authentication |
| `hubRevision` | Immutable revision reported by the observer; no independent Hub read by this endpoint |
| `trainerStateSha256` | Digest reported by the producer for its pinned trainer-state verification |
| `PINNED_OBJECT_BYTES_VERIFIED` | Producer-reported trainer JSON integrity; not a final adapter or execution proof |
| `TERMINAL_METADATA_PRESENT` | Producer saw terminal checkpoint metadata and final filenames |
| `providerReadyCount` | Provider-reported ready instances; not trainer-process liveness |
| `OBSERVED` | Report or candidate lies within the reader's admitted observation window |
| `PARTIAL` | Report is readable but includes unavailable candidate observations |
| `STALE` | Original evidence deadline has passed |
| `CLOCK_SKEW` | Evidence timestamps are in the future relative to the reader |
| `UNAVAILABLE` | No usable input/candidate observation; never interpreted as zero work |

For candidate observation time `t_c`, report time `t_r`, producer TTL `d`, and
reader cap 660 seconds, the deadline is
`min(t_c, t_r) + min(d, 660 seconds)`. Equality at the deadline is stale. A newer
file timestamp or HTTP response cannot renew that deadline.

The parser rejects contradictory producer states, malformed revision/digest
bindings, duplicate identities/JSON keys, nonfinite values, Boolean integers,
oversized reports, and attempted verification/authority upgrades. At most 32
records can be projected; the current producer admits at most six.

Completion, final-artifact integrity, evaluation, proof verification, process
liveness and promotion remain false in this observation view. Artifact
qualification, held-out evaluation and promotion policy remain distinct existing
workstreams. No status is manufactured from `checkpointStep == targetSteps`.

## Browser behavior

Private reads are explicit. The operator enters credentials for the fixed
same-origin request; the token field is cleared immediately and neither browser
storage nor URL parameters retain it. Credentials are omitted from screenshots,
test reports, logs and source fixtures. The panel renders returned fields as text.

Cancellation and request generations prevent old requests from repopulating the
panel after a newer request, changed credential, disconnect, or navigation. The
browser rechecks expiry on visibility resume and preserves a monotonic time floor
so moving the wall clock backwards does not revive expired evidence.

## Validation and release

Run the existing model-preparation surface suites and the additional tests:

```sh
python -m unittest discover -s tests -p 'test_model_pretraining*.py' -v
python -m unittest discover -s tests -p 'test_training_observations.py' -v
node --test tests/model-pretraining.test.mjs tests/training-observations.test.mjs
python scripts/test_model_pretraining_browser.py
python scripts/test_training_observations_browser.py
```

The browser test starts an ephemeral loopback server, uses synthetic observation
data and an ephemeral test credential, and exercises the real auth and route
group. Its captures/report are local integration evidence. It does not deploy,
launch training, load weights, create a production credential or grant promotion.

The existing HF-tooling product workflow includes these suites and retains their
artifacts. `COPY routers/` and `COPY pages/` already include the added runtime
files. Publication uses the existing canonical source-to-Space workflow; there
is no second publisher or protection change.

Before claiming hosted operation, verify the merged source and exact runtime
revision, anonymous refusal, admitted real-source response, all frontend asset
bytes, local expiry, and the source producer's ongoing supervision. An available
page with an UNAVAILABLE private source is not a completed hosted integration.

## Prior art and the next architecture boundary

The following are engineering references, not claims that a vendor's product or
research validates SZL's mathematics:

- [Palantir Ontology](https://www.palantir.com/docs/foundry/ontology) joins typed
  objects, links and actions with permissions. The applicable direction is one
  identity for each run, dataset version, checkpoint, evaluation and permitted
  action, shared by the API and interface.
- [Palantir OSDK action source](https://github.com/palantir/osdk-ts/blob/main/docs/react/actions.md)
  distinguishes validation, pending work and optimistic state. This reader uses
  authoritative response states and clears failed observations; it offers no
  mutation or optimistic completion.
- [LangGraph fault tolerance](https://docs.langchain.com/oss/python/langgraph/fault-tolerance)
  treats missing acknowledgement as an unknown outcome that needs reconciliation.
  A future execution integration should persist admission and effect identity,
  then reconcile before retrying an external write.
- [NVIDIA Helix results](https://docs.nvidia.com/nemo-helix/documentation/evaluate-models/agent-eval/reading-results/)
  separates per-trial evidence, aggregate scores and missing/failed coverage.
  Future evaluation receipts should retain those denominators and exact model,
  dataset, evaluator and configuration identities.
- [NVIDIA's migration guide](https://docs.nvidia.com/nemo/agent-toolkit/1.9/resources/migration-guide.html)
  reports Agent Toolkit's October 2026 deprecation and points to Relay, Fabric and
  Helix. This change adds no dependency on that retiring toolkit.
- [Sculley et al., 2015](https://papers.neurips.cc/paper/5656-hidden-technical-debt-in-machine-learning-systems.pdf)
  identifies hidden consumers and system-boundary debt. The explicit input
  contract and separate authority boundary address that class of dependency.
- [Breck et al., 2017](https://research.google/pubs/the-ml-test-score-a-rubric-for-ml-production-readiness-and-technical-debt-reduction/)
  offers a production-readiness rubric. A successful local test or training
  checkpoint alone is insufficient evidence of production readiness.

Official video references identified for follow-up are
[Palantir Ontology Overview](https://www.youtube.com/watch?v=YDAxITCNcko) and
[NVIDIA's Agent Toolkit profiler walkthrough](https://www.youtube.com/watch?v=yrqdvBLAI3k).
Only official metadata was accessible during this review; no transcript-level
analysis is claimed. Current documentation governs dependency choices.

## MODELED research directions

These are proposed experiments, not new locked formulas or implemented products.

1. **Proof obligations attached to actions.** Connect the exact proposition,
   assumptions, toolchain, artifact digest and runtime input binding to an action.
   Study whether a decision can retain enough evidence to reproduce why it was
   admitted or refused. The canonical Lutar cross-component predicate already
   expresses halt eligibility, mode permission and receipt admission. It expressly
   remains a formal specification rather than a verified runtime refinement.
2. **Choose the next experiment from the missing evidence.** Given a refused
   promotion, propose the smallest experiment that can resolve the specific unmet
   obligation. Compare diagnostic time and measured joules against a fixed
   full-rerun baseline, including failed and inconclusive trials. Missing energy
   telemetry remains missing; no savings are inferred from token counts.
3. **Recoverable scientific runs.** Bind model, data, evaluator, policy, code and
   proof-toolchain identities to a durable run. Test restart and ambiguous-publication
   failures before allowing a controller to spend more compute or publish results.
   Maintain empirical quality, proof acceptance and operational readiness as
   separate conditions.

These directions need literature review, implementation, adversarial tests and
measured comparison before novelty or benefit claims. The eight locked formulas
and existing conjecture labels remain unchanged.
