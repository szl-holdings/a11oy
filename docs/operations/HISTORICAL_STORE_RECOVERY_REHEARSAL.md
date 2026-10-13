# Historical store recovery rehearsal

Release state: **BLOCKED**. A successful rehearsal is evidence about one preserved
historical capture, not the current running databases or permission to restore.

## Purpose and boundary

`hf-qualify-historical-stores.yml` manually runs the existing recovery inspector
against the source-owned capture `gdw-capture-37223162231.json` and its existing
`gdw-recovery-historical-anchors.json`. Both are under `docs/operations/evidence/`.
The exact capture-byte hash and anchors remain pinned; do not rewrite either to
make a newer capture appear qualified.

The workflow checks exact protected current main before exposing the existing HF
credential. The inspector checks source ownership again before and after its work,
uses its read-only provider wrapper, verifies remote identities and local hashes,
and inspects separate disposable local copies. It never stops the running Space,
uploads a database, changes a mount, or opens the original database for writing.
Its concurrency group is shared with the canonical publisher and preservation
workflow. No automatically triggered provider writer is added.

The qualifier accepts the capture tool's two verified copy modes with exact,
capture-local paths: `SERVER_SIDE_XET_COPY` uses `originals/` and
`LOCAL_UPLOAD_FALLBACK` uses `uploaded-originals/`. The mode is also bound to the
saved private manifest. Historical captures without a mode remain valid only
with `originals/`; malformed, unknown, mixed, or mismatched modes fail closed.

## Run after the reviewed source reaches protected main

1. Read the current protected main SHA and confirm no competing maintenance or
   publisher operation. Do not pause the Space for this rehearsal.
2. Dispatch **Rehearse historical A11oy store recovery** on `main`, passing that
   exact SHA as `expected_source_sha`. A changed head requires a fresh dispatch,
   not a bypass or a rerun against stale source.
3. Read the completed run and its single public-safe status artifact. Raw capture
   and qualification reports stay in runner temporary storage; they are not
   uploaded as public artifacts. Never publish private database rows, paths, or
   arbitrary provider error text.
4. A passing rehearsal means the historical copies passed the inspector and
   pinned-anchor checks in that run. `restore_admitted`, `deployment_admitted`,
   and `later_acknowledged_writes_verified` remain false. A failed or missing run
   is **BLOCKED**, never a successful recovery.

## What is still required for a current deployment

Historical success cannot establish preservation of later acknowledged writes.
Before a current maintenance cutover, prepare and review a fresh stopped-writer
capture, an independently bound current continuity baseline, offline integrity
checks, private byte-verified copies, and the exact rollback procedure. The
running Space must remain running until that procedure is ready. Preserve the
canonical publisher, its security and parity checks, and the post-deployment
generation, receipt-chain, readiness, and source readbacks.

This rehearsal does not resurrect the durable-v1 deployment graph retired by
PR #2622 and does not qualify bucket-mounted SQLite durability. Ordinary release
authorization and long-term storage qualification remain separate decisions.
