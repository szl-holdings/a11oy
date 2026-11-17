<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# Preserve the existing writer before an A11oy deploy

This procedure applies after state-store v2 is active. It uses the existing
private dataset lease and the canonical `hf-sync.yml` publisher. It does not
activate storage, start a second writer, change credentials, pause the Space,
or establish that a deployment is qualified.

The storage ADR permits later deploys through an overlapping-container handover.
For a deliberate maintenance window, the operator helper can request the same
drain while the old process is still serving. This matters when the old runtime
has its finalizer only outside Uvicorn: [Uvicorn 0.54.0](https://github.com/Kludex/uvicorn/blob/0.54.0/uvicorn/server.py)
re-raises SIGTERM after ASGI
shutdown and can terminate before that outer `finally` runs. The repaired
ASGI shutdown hook awaits the existing state-store close operation before this
signal boundary, including when an earlier application cleanup raises.

## Canonical snapshot cadence

The existing `scripts/configure_hf_series_a_runtime.py` convergence owner manages
`A11OY_STATE_PERIODIC_SECONDS=300` for the canonical Space, matching ADR-0001's
continuous-write snapshot interval. The 900-second alert default remains in
`a11oy_state_store`; this setting does not activate v2 or change its lease rules.
A 1,800-second override allows ordinary waiting to exceed that alert threshold.
Restarting only resets the observation ages and does not reconcile the interval.

The normal `hf-sync.yml` configuration step corrects a drifted cadence only after
its existing maintenance-window, protected-main and installed-authority gates.
It requires provider readback of the complete managed variable contract. Its
`--check-only` path performs one bounded readback after authority verification;
missing or drifted values remain `SETUP_REQUIRED` without any provider write.
An already converged deployment receives no cadence write. A configuration
change can restart the Space through the provider, so keep it inside the sole
publisher's coordinated handover and verify the resulting source, boot and
storage state. Independent execution admission remains separate.

## Admission and read-only preflight

Coordinate the sole publisher and check that neither `hf-sync.yml` nor
`restart-drill.yml` is running. Observe the current protected main, Space commit,
`/api/build-info`, `/api/a11oy/v1/storage/status`, and Series-A storage receipt
count. Keep these observations separate from the later deployment result.

Require fenced v2 storage, the expected active writer, a fresh heartbeat, all
seven required stores healthy, no pending publication and no unresolved errors.
Obtain the immutable private dataset HEAD commit, exact HEAD SHA256, writer ID,
boot ID and epoch through an authenticated read of `state/v2/head.json`. Never
copy a token into an argument or receipt. These identities are one-operation CAS
preconditions, not permanent source-version or storage-version gates.

```sh
python scripts/request_state_store_handover.py \
  --dataset SZLHOLDINGS/a11oy-state --bucket SZLHOLDINGS/szl-evidence \
  --expected-head-commit <observed-dataset-commit> \
  --expected-head-sha256 <observed-head-sha256> \
  --expected-writer-id <observed-writer> --expected-boot-id <observed-boot> \
  --expected-epoch <observed-epoch>
```

The default is read-only. `PREFLIGHT_VERIFIED` binds the observed HEAD and
heartbeat; it does not verify the snapshot objects. Any changed precondition
requires a fresh read and review before another attempt.

## Explicit handover and its limit

Append `--execute --receipt <new-private-local-receipt.jsonl> --timeout 180`
to the same command only for the intended maintenance window. The helper writes
and fsyncs an unsigned, hash-chained local intent before submitting the existing
`HANDOVER_REQUEST` CAS transition. It preserves the writer, boot, epoch, lease,
snapshots, history and other non-transition fields. It never claims a lease.

The old writer refuses new writes, stops the GDW outbox, drains admitted
requests and captures the final snapshots. Success requires an exactly causal
`RELEASED` HEAD: same writer, boot and epoch, the next sequence, and the request
body's hash as its predecessor. The helper rechecks the immutable release
commit. A different release or changed owner is a failure.

There is no cancellation or resume operation. After release the old process
stays read-only until replaced. On timeout, missing evidence, failed drain or
uncertain outcome, keep the existing process and local files intact and hold
deployment. Never manufacture `RELEASED`, claim a successor epoch, or use an
unclean takeover to turn this procedure green.

If the local operator process was interrupted, use `--observe-receipt
<existing-receipt.jsonl>` with the same expected identity arguments. This
validates the recorded intent and observes its exact release without submitting
another request. It does not resume the old writer.

## Preservation and deployment readback

`RELEASE_OBSERVED` deliberately leaves `object_preservation=NOT_VERIFIED`,
`runtime_health=NOT_VERIFIED` and `publication_authorized=false`. Before deploy:

1. Read back each required released snapshot object and verify its declared
   size and SHA256, then its SQLite integrity/foreign-key/logical fingerprint or
   LMDB logical digest. Retain the immutable HEAD/request/release identities and
   verification results. The helper requires all seven snapshot labels and
   usable metadata; that is intentionally conservative, not object verification.
2. Check the serving runtime reports `RELEASED`, `writable=false`, healthy
   required stores, no pending publication and no release/quiesce error.
3. Recheck publisher ownership and protected main. Then the normal publisher
   dispatch is:

   ```sh
   gh workflow run hf-sync.yml --repo szl-holdings/a11oy --ref main \
     -f open_deploy_window=true -f publish_vertical_flagships=false
   ```

4. Verify the matching run's publication artifact and immutable HF commit,
   then `/api/build-info` at the canonical Space and product origin. The new
   storage status must show a later epoch, `claim=CLEAN`, `mode=FENCED`,
   `role=WRITER`, all seven stores restored and healthy, no pending errors, and
   a fresh heartbeat. Series-A receipt count must not decrease. Compare the
   restored lineage with the released snapshots; normal later writes can change
   current snapshot hashes.

An HTTP 200 or a completed workflow that skipped a closed deployment window is
not publication. An `UNCLEAN_HANDOVER` is not clean preservation. This procedure
does not qualify outbound replication crash recovery or model execution.

## Local lifecycle regression receipt

Evidence class: MEASURED for these local tests; provider mutation: NOT RUN.
The regression loads the actual `serve.py` shutdown hook into a minimal FastAPI
application and sends a real SIGTERM to a child Uvicorn process. On protected
source `315b0f4b910d4e55ba200dba50b099f9f9304e72`, the process terminates without
the storage-finalizer marker. With this change, the marker completes before
signal termination; the outer runtime `finally` still does not run. Separate
tests check awaited off-loop finalization and an earlier cleanup failure.

WSL Ubuntu, Python 3.12, FastAPI 0.143.0, actual Uvicorn 0.54.0 wheel SHA256
`505bdb0f318731d45f1f712071fc781a8981f6847a31c902c9f5e652d4f67faf`:

```text
python -B -m pytest -q -p no:cacheprovider --basetemp=<fresh directory> tests/test_state_store_asgi_shutdown.py tests/test_state_store_handover_operator.py tests/test_state_store_wiring.py tests/test_state_store_handover.py
143 passed, 1 warning, 11 subtests passed
```

Plugin autoload and bytecode writes were disabled. The existing primary-runtime
CI matrix runs the new tests with the Docker dependency closure. The real signal
test is POSIX-specific; it is not a Windows process-semantics claim. No live
handover, runtime snapshot object validation or deployment was performed by this
local regression. The warning is the existing Starlette TestClient deprecation
for its HTTPX adapter. The 31 operator cases cover read-only preflight, exact
identity and heartbeat admission, failed audit writes, uncertain CAS outcomes,
causal release/readback, timeout and read-only receipt recovery.

## Configuration-to-publication barrier

`.github/scripts/await_hf_config_writer.py` is a read-only observation in the
existing `hf-sync.yml` lane. Before each writable Series-A or GDW configuration
batch, it records a baseline. After the batch, an explicit, well-formed
no-change report skips waiting. A changed batch requires the recorded baseline
and a later process boot, storage boot, writer ID and lease epoch. Missing
baseline evidence holds that changed batch; baseline collection alone grants
no provider authority. This also covers deferred post-deploy configuration.
Only validated, allowlisted baseline fields are retained; arbitrary input fields
and malformed identities never enter the uploaded observation report.

The successful observation requires unchanged provider repository/running
commit identity, an attested source-copy report, matching immutable private
HEAD and heartbeat identities, ACTIVE fenced writer status, all seven stores
healthy, no pending publication or active errors, and a CLEAN restored claim.
The process identity from Series-A and the storage owner are separately observed.
The two public GETs do not prove that they came from the same process; reports
explicitly record same_process_binding=NOT_ESTABLISHED. No load-balancer
stickiness or new authority is assumed.
At least three consecutive observations must span 30 seconds and show at least
15 seconds of heartbeat progression. Boot/epoch churn resets the observation;
a new unclean claim, publication drift, or a storage writer change within one
epoch holds it. The highest observed epoch and per-owner HEAD sequence/heartbeat
watermarks survive streak resets and unavailable reads; older state cannot
settle after newer coherent state was observed. An old UNCLEAN or RELEASED baseline remains in the report and is
never relabeled as historical clean preservation.

Polling uses a 900-second monotonic deadline, rechecked after reads and validation
and before success. Each SDK child has a timeout of at most 30 seconds. Python
cannot guarantee interruptible operating-system process creation; these are
bounded polling and SDK child-timeout controls, with workflow cancellation as
an outer limit. Preflight has 50 minutes and runtime-config has 55 minutes:
each retains its previous 15-/20-minute allowance plus both 900-second waits and
both 30-second captures, with four additional minutes of margin. The runtime
allowance still includes the existing 900-second exact-source wait.
Partial progress is retained as unsigned WAITING evidence; only
WRITER_STABLE_AFTER_CONFIG satisfies the changed-batch barrier. The child receives
only HF_TOKEN and allowlisted operating-system, certificate and proxy settings;
it does not inherit the GitHub credential. Child arguments and reports contain
no credential values.
Private dataset and bucket access must already be available to the canonical
publisher credential. This helper reads fixed metadata and the heartbeat object;
it does not construct a runtime, request handover, renew a lease, verify snapshot
object contents, or establish independent execution authority.

### Restart boundaries and remaining scope

| Existing owner | Restart-causing operation | Coverage |
|---|---|---|
| A11oy Series-A configuration helper | Variable and, when required, volume reconciliation | Baseline and changed-batch writer barrier before the next batch/publication. Multiple writes within one helper batch can still cause intermediate boots. |
| A11oy GDW configuration helper | Variable reconciliation | Its own baseline and changed-batch barrier. |
| Shared reusable publisher | Derived COPY-set Space commit | Existing publication/current-main guards and final exact-runtime verification remain. |
| Shared `hf_space_source_binding.py` | `SZL_GIT_SHA` variable binding after publication | Separate unresolved sequencing boundary: the pinned helper unconditionally writes the value, including an already matching value. This PR does not modify that owner. |
| Shared reusable publisher | Explicit restart for a PAUSED Space | Existing manifest-bound conditional restart; unchanged. |
| Deferred A11oy runtime configuration | The same configuration batches after publication | The same per-batch barrier, followed by the existing exact-source wait. |

The shared code is pinned at
[`5f140bab`](https://github.com/szl-holdings/.github/blob/5f140bab8adb64fe25252d8832b67b1f43a56c36/.github/workflows/reusable-hf-deploy.yml);
[source binding](https://github.com/szl-holdings/.github/blob/5f140bab8adb64fe25252d8832b67b1f43a56c36/.github/scripts/hf_space_source_binding.py)
and [publication](https://github.com/szl-holdings/.github/blob/5f140bab8adb64fe25252d8832b67b1f43a56c36/.github/scripts/hf_deploy_from_dockerfile.py)
remain that repository's responsibility. Hugging Face documents configuration
changes as [restart-triggering](https://huggingface.co/docs/huggingface_hub/guides/manage-spaces#configure-secrets-and-variables).
The barrier closes the observation gap between completed configuration batches
and the next step; it does not claim every restart boundary is coordinated.

A deliberate verified-release maintenance operation still uses the existing
helper and object verifier described above. If configuration subsequently
starts a new writer, the earlier release is not a release of that writer.
Any later explicit preservation operation needs its own fresh CAS identity,
causal release and complete snapshot verification. The observer does not take
over another operator's prepared RELEASED state.

### Retained incident and cadence evidence

[Publisher run 43991653922](https://github.com/szl-holdings/a11oy/actions/runs/43991653922)
changed the periodic configuration at 2026-11-17 00:57:14Z, published source files
at 00:58:15–21Z, and bound the source variable at 00:58:23Z. The immutable HEAD
chain records epoch 277 RELEASED at 00:58:21Z and epoch 278 CLEAN at 00:58:25Z.
The epoch-278 CLAIM commit
`8c960c6098d40ca4f4fdc9762efd16afffc3c316` identifies its actual source as
`654c515bb02c7241499364b767416e2d7babc028`.

Epoch 278 has no snapshot or release transition before HANDOVER_REQUEST at
00:59:45Z and epoch 279 UNCLEAN_HANDOVER at 01:01:52Z, commit
`1d39c3cef4f11c75020f9713bbb49632a181f33b`. The request changed the informational
HEAD source field to requester `4d724ba783500d6fbe06638853bafa8f3f2a38e2`;
that field in the request is not evidence that epoch 278 ran that source.
The 17 retained consecutive HEADs (sequences 22032–22048) match their predecessor
hashes without a missing transition.

Recovery after a nonresponsive writer is supported by ADR-0001. The closely
spaced configuration/publication operations expose an avoidable sequencing
risk, but the retained successor logs do not identify the earlier container's
exit reason. Termination before ASGI startup, a stall, and a failed finalizer
must not be conflated with a demonstrated root cause. No zero-loss claim is
established for the unclean transition.

Later epoch-279 GDW captures at 01:06:58, 01:12:09 and 01:17:16Z are separated
by 311 and 307 seconds after the canonical 300-second configuration was installed.
Its later RELEASE at 01:21:24Z and epoch-280 CLEAN claim at 01:26:54Z establish a
different transition; they do not erase epoch 278's missing release.
