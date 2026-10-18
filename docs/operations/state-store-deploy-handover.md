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
