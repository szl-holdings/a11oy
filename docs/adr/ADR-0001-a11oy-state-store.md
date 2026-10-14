<!-- SPDX-License-Identifier: Apache-2.0
(c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173 -->

# ADR-0001: a11oy state store (local live stores, immutable bucket snapshots, CAS lease)

- **Status:** Accepted 2026-10-13. Decided by the owner's delegate. The code is implemented and still **inert**: it switches on only when the Space variable `A11OY_STATE_STORE=v2` is set during the rollout below.
- **Supersedes:** durable v1 (`GDW_DURABLE_STORAGE=private-dataset-v1`, `gdw_durable_*.py`). Durable v1 is **retired**. It stays inert in the tree until a cleanup PR deletes it. Do not extend it.
- **Code:** `a11oy_state_store.py`. Wiring: `gdw_runtime.py`, `gdw_workspace.py`, `routers/series_a_control_plane.py`, `szl_be_hardening.py`, `a11oy_ayllu.py`, `szl_boot_preflight.py`, `serve.py`. `szl_unay_routes.py` is shared byte-for-byte with killinchu, so activation sets its first-priority `UNAY_DATA_DIR` to the local root instead of editing it.
- **Tests:** `tests/test_state_store_handover.py`, `tests/test_state_store_restore.py`, `tests/test_state_store_wiring.py`. All offline.

## Context

**The incident (root cause #1).** The Space mounts the HF Storage Bucket `SZLHOLDINGS/szl-evidence` at `/data` as a read-write FUSE volume. That volume is created by `scripts/configure_hf_series_a_runtime.py`. Every live database sat on it:

- GDW: `a11oy/gdw/gdw.sqlite3`
- Series-A: `a11oy/series-a/control-plane-v2.sqlite3`
- Khipu: `khipu/khipu_a11oy.sqlite3` and `khipu/khipu_a11oy_council.sqlite3`
- `unay_a11oy.sqlite`
- the LMDB environments `khipu_lmdb_a11oy/` and `khipu_repl_a11oy/`

On 2026-10-04, container lifetimes overlapped during the 16:30Z deploy. That left two orphan pages (362 and 363, "never used") in the GDW file. The restore receipt in the bucket, `a11oy/gdw/recovery/2026-10-04-010879737c7f-0eda4fbcff92/applied-20261006T100941Z.json`, records this root cause.

The Space then crash-looped for about 41 hours. `gdw_runtime.main` re-raised the integrity failure, and `gdw-drain` failed every 30 minutes until a manual restore.

A FUSE object mount does not give SQLite or LMDB the locking and write ordering they need. A repair at boot does not change that. PR #2620 added a degraded boot and `gdw_sqlite_repair.py`, but the stores stayed on FUSE.

**Durable v1 was assessed as unworkable.** Each point below is checked against current main:

1. **It bricks the next deploy.** Activation requires these to match exactly:
   - `SZL_GIT_SHA` (`gdw_durable_startup.activate`)
   - `huggingface_hub == 1.31.0` (`gdw_durable_storage._hub_api`, `SDK_VERSION`)
   - the observed `sqlite3.sqlite_version` (`gdw_durable_startup.verify_runtime`)

   After cutover, any later commit or SDK bump fails activation.
2. **Every write waits on the Hub.** `GuardedConnection.commit` calls `LocalGate.acknowledge`. That backs up both databases, publishes them and makes a dataset commit under one lock, with a 60 s deadline. Any failure poisons the gate (`gdw_durable_runtime.py`). So any Hub blip takes a11oy down.
3. **Its acquisition is bound to the 2026-10-04 capture.** Production must be paused at an exact Space revision and an exact variable-hash baseline (`gdw_durable_guard.py`). Its HEAD was never created.

## Decision

a11oy storage is a **local state store with immutable bucket snapshots and a CAS lease**.

1. **Live files are on local disk.** They live under `A11OY_STATE_ROOT`, default `/tmp/a11oy-state`.
   - Boot creates the root with mode 0700. It then admits the root only if `/proc/self/mountinfo` names a local filesystem type. This reuses `gdw_durable_runtime._private_directory`.
   - The root is deliberately ephemeral. Boot always restores it from HEAD, and leftover local files are moved aside, never trusted.
   - No file under `/data` is opened for writing. The legacy copy is a read-only byte copy.
   - Paths are `gdw/gdw.sqlite3`, `series-a/control-plane-v2.sqlite3`, `khipu/khipu_a11oy{,_council}.sqlite3`, `unay/unay_a11oy.sqlite`, and `unay/khipu_{lmdb,repl}_a11oy/`.
2. **Snapshots are immutable bucket objects.** Each one is written to `a11oy/state/v2/<label>/<utc>-<epoch>-<seq>-<sha16>.{sqlite3,mdb}` and goes through these steps:
   - Copy: the SQLite backup API, or `env.copy(compact=True)` for LMDB.
   - Check: `quick_check`, with a full `integrity_check` at most hourly. Then `foreign_key_check`, the `gdw_sqlite_repair.logical_fingerprint`, and sha256.
   - Upload with `batch_bucket_files`, then read back the size and sha256.

   **When snapshots run:**
   - A store that changed is captured after 30 s without further change.
   - Under continuous writes, a capture happens at least every 300 s.
   - Container stop and handover take a final snapshot.

   **When a snapshot fails:**
   - The live database is never touched. The failure retries with backoff.
   - An object that uploaded but was not yet published stays pending until it is published.
3. **A HEAD manifest records the state.** It holds epoch, writer, boot, lease state `ACTIVE | HANDOVER_REQUESTED | RELEASED`, the latest snapshot per store, and up to five previous ones.
   - The bucket has no compare-and-swap. So HEAD lives at `state/v2/head.json` in a **dedicated private dataset**, `A11OY_STATE_DATASET` (default `SZLHOLDINGS/a11oy-state`).
   - Every change is `create_commit(parent_commit=…)`. Only HTTP 412 counts as a definite conflict. An uncertain submission is resolved by reading HEAD back, because every manifest carries a fresh `operation_id`.
   - `source_revision` is informational and never a gate. No SDK, SQLite or source version is pinned.
4. **There is a single writer across overlapping containers.**
   - **The new container asks.** It CASes `HANDOVER_REQUESTED`.
   - **The old writer hands over.** Its 15 s heartbeat sees the request. It switches to read-only (mutating requests get 503 with `Retry-After`), stops the GDW outbox drain, takes final snapshots, and CASes `RELEASED`.
   - **The new container claims.** It restores and verifies (sha256, integrity, foreign keys, logical fingerprint), then CASes epoch+1 `ACTIVE`. Only then does `gdw_runtime` import `serve.py`.
   - **Stale or silent writers.** A missing heartbeat, or one older than 120 s, means the new container proceeds from the latest snapshots. So does a writer that does not answer within 120 s. That claim is recorded as `UNCLEAN_HANDOVER`.
   - **Fencing.** A writer that sees a newer epoch becomes `FENCED` and stays read-only.
5. **Boot never crash-loops.**
   - **History walk-back.** Restore walks back through HEAD history to the newest snapshot that verifies.
   - **Orphan-page-only damage** is repaired with `gdw_sqlite_repair.repair_orphan_pages` on the private copy. The original stays put: it is the immutable object, or the frozen legacy file. The repair receipt is uploaded to `a11oy/state/v2/<label>/quarantine/`.
   - **A store that still cannot be restored is BLOCKED.** Its last good HEAD entry is kept, and nothing this process writes to that store is ever snapshotted or published. GDW maps this onto its existing degraded boot (GDW writes 503, `/api/a11oy/readyz` 503). Any other blocked store turns on the process-wide write fence.
6. **Legacy bootstrap happens once.** The first boot may find no HEAD and no v2 objects while the legacy `/data` files exist. In that case it copies each legacy file read-only and checks that the source did not change during the copy. Journal rollback and orphan repair run on the private copy. The result then goes into the store through the backup API.
   - It takes the first snapshots, creates HEAD (absent-only CAS) and writes `a11oy/state/v2/LEGACY_FROZEN.json`.
   - Once that marker or any HEAD exists, the legacy files are never read again.
7. **If the fence dataset does not exist**, the store runs in `SNAPSHOT_ONLY_UNFENCED` mode, and it says so loudly:
   - in the boot log
   - `status.mode` and `status.unfenced=true`
   - a non-authoritative `HEAD.unfenced.json`

   Restore then lists the bucket and verifies the newest objects. Once the dataset exists, the next boot adopts those objects into a fenced HEAD. The code never creates an HF repository.
8. **Status is public.** `GET /api/a11oy/v1/storage/status` shows mode, role, epoch, lease state, and per store the origin, health, snapshot age, `sha16`, integrity and failures, plus the last error class and code. It shows store labels only: no paths and no secrets. It is in an alert state when a store's snapshot or unsnapshotted change is older than 15 min, or when the process is BLOCKED or FENCED.

## Consequences

- **What is lost at a handover depends on how it ends.**
  - **Clean handover:** no acknowledged request write is lost. New mutating requests are refused before the final snapshot, and in-flight ones drain for up to 20 s. The GDW outbox drain is stopped first. The Series-A refresh scheduler is **not** quiesced. A refresh written after the final snapshot is redone by the successor; it is derived, re-fetchable data.
  - **Unclean takeover (crash):** acknowledged writes newer than the last snapshot are lost. That is up to about 30 s for a burst, or up to 300 s under continuous writes.
- **Failed final capture:** the old process stays read-only and does not publish `RELEASED`. Successfully uploaded objects remain pending. A successor can take over only under the existing unclean takeover rule; it must not label a restore from older snapshots `CLEAN`.
- **Incomplete drain:** a quiesce hook failure or a request still in flight after the drain deadline also refuses `RELEASED`. New request admission and the start of handover share one lock, so a request cannot enter after the drain begins.
- **Outbox stop timeout:** the GDW supervisor raises while its worker thread remains alive after its bounded join. The state store treats that as an incomplete drain, and the supervisor does not report the worker stopped prematurely.
- **Writes are refused during a deploy.** From the handover request until the new container serves, mutating requests answer 503 with `Retry-After`. Reads keep working.
- **Some costs remain:**
  - one dataset commit per published snapshot pass
  - a 15 s heartbeat object write
  - snapshot objects that accumulate, since this change deletes nothing (Xet chunk dedupe limits the stored bytes)
- Any running process can be checked with the status route: it reports the mode, lease, snapshot ages and integrity results.

## Alternatives rejected

- **Keep the stores on FUSE and rely on boot repair.** This keeps the root cause. Orphan repair is only safe when the orphan pages are proven empty.
- **Finish durable v1.** See the three points above. Even after a successful bootstrap, the next deploy bricks it.
- **HF persistent block storage.** Not confirmed available for this Space. It would still need single-writer handover across overlapping containers.
- **An external managed database.** It adds a new vendor and a migration of four schemas. That is out of scope for a root-cause fix to the mount.
- **A bucket-only HEAD with no CAS.** Two overlapping writers could both believe they own HEAD. It is kept only as the explicit, loudly reported `SNAPSHOT_ONLY_UNFENCED` fallback.

## Rollout

1. **Merge.** Nothing changes while `A11OY_STATE_STORE` is unset. The legacy `/data` paths apply exactly as before.
2. **Owner prerequisites. The code does not do these.**
   - Create the **private** dataset `SZLHOLDINGS/a11oy-state`.
   - Make sure the Space secret `HF_TOKEN` can write that dataset and the bucket `SZLHOLDINGS/szl-evidence` through the Hub API.
3. **One paused deploy window.**
   - Pause the Space so no legacy writer is running.
   - Set the Space variable `A11OY_STATE_STORE=v2`.
   - Deploy main. hf-sync deploys while the Space is PAUSED.

   The first boot performs the legacy bootstrap, creates HEAD epoch 1 and writes `LEGACY_FROZEN.json`.

   **Verify:**
   - `/api/a11oy/v1/storage/status` shows `mode=FENCED`, `role=WRITER`, every present store `health=OK`, and `alert=false`.
   - Series-A `receipt_count` is not lower than before the window.
   - `/api/a11oy/readyz` returns 200.

   This is the last deploy that needs a pause. Later deploys hand over between overlapping containers.
4. **Later: make the `/data` volume read-only.** That change belongs in `scripts/configure_hf_series_a_runtime.py`, a reviewed deploy helper whose SHA-256 is pinned in `tools/check_copy_sync_lockstep.py`, so it needs its own PR. Before that, the files still written under `/data` must move. They are not covered by this ADR:
   - GDW proof and receipt export directories
   - `SZL_ENERGY_LEDGER_PATH`
   - `SZL_LAKE_DIR`
   - the atelier ledger
   - `SZL_GOVERN_INFER_LOG`
5. **Cleanup PR.**
   - Delete durable v1 (`gdw_durable_startup/source/guard/image/runtime/artifacts.py`) with its incident scripts, tests and workflows.
   - Move the primitives this module imports from `gdw_durable_storage` (`StorageBlocked`, `ParentConflict`, `canonical`) and `gdw_durable_runtime` (`_private_directory`) into `a11oy_state_store.py` first.
6. **Follow-ups, each needing owner approval:**
   - snapshot retention GC, for example the last 48 plus one per day for 30 days. It deletes bucket objects.
   - a weekly restart drill under synthetic write load.

**Rollback.** Setting `A11OY_STATE_STORE=off` points the modules back at the frozen legacy files. That would silently drop every write made since cutover. A rollback must first restore the latest HEAD snapshots to the legacy paths, with the Space paused.
