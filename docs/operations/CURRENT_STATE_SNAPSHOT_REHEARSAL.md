# Current state snapshot rehearsal

Release state: **BLOCKED**. A successful rehearsal verifies the seven snapshot
objects named by one pinned v2 HEAD. It does not admit restore or deployment,
and it does not qualify writes that happen after the pinned HEAD.

## What it checks

`hf-rehearse-current-state-snapshots.yml` is manual. It reads the private
dataset HEAD for `SZLHOLDINGS/a11oy-state` and the seven snapshot objects that
HEAD names in `SZLHOLDINGS/szl-evidence`. Each object is copied into runner
scratch and checked for size, SHA-256, SQLite `integrity_check` and
`foreign_key_check`, or the LMDB logical digest, then the logical fingerprint
declared by HEAD. The scratch copy is deleted before the job finishes.

The Space keeps its writer lease. The rehearsal does not pause, restart, or
deploy the Space, submit a dataset commit, upload an object, or repair a
database. A snapshot that fails integrity stays failed. History entries are
not substitutes for a missing current snapshot.

Heartbeat movement alone is expected. The rehearsal passes only when the tip
HEAD still names the same seven snapshot digests after the read. A newer
snapshot during the read is `SNAPSHOTS_ADVANCED`: the pinned objects may have
verified, and the current backup did not.

## What a pass does not mean

`restore_admitted`, `deployment_admitted`, and `execution_authorized` stay
false. The public artifact omits the private HEAD revision, object paths, and
full content hashes. It is not an authority pin, a runtime identity binding,
or permission to copy snapshots back onto the live stores.

Runtime source identity remains the attested publisher binding. This rehearsal
does not read or write `A11OY_EXECUTION_AUTHORITY_PINS_JSON`,
`A11OY_EXECUTION_HF_REVISION`, `A11OY_EXECUTION_BOOT_ID`, or
`A11OY_EXECUTION_RUN_NONCE`.

The historical capture rehearsal is a different, retired-storage check. It
does not prove these current objects.

## Run

1. Confirm protected `main` and that this workflow is not already running.
   Do not pause the Space.
2. Dispatch **Rehearse current A11oy state snapshots** on that exact SHA.
3. Read the public status artifact. `SNAPSHOTS_VERIFIED` means the seven
   objects matched that pinned HEAD and were still current at the end. Any
   other result stays **BLOCKED**.
