#!/usr/bin/env python3
"""Mirror the Dockerfile-COPY'd backend (.py + Dockerfile) to the HuggingFace Space.

This is the extracted, unit-testable form of the logic that used to live inline in
.github/workflows/hf-sync-backend.yml. The workflow now runs this module directly so
the SAME code that runs in CI is exercised by tests/test_hf_sync_backend.py.

The Space is built from THIS repo's Dockerfile, so the files it COPYs are exactly the
backend the image runs. We mirror the .py among them so the Space never builds from a
stale backend, plus the Dockerfile itself (so a newly-added module's COPY line reaches
the Space and gets baked in). We push ONLY the files whose content differs from the
Space's current copy (git-blob-OID compare), so an unchanged set is a true no-op and
never triggers a needless Space rebuild.

auto factory-rebuild (drift-fix): an HF Space commit LANDS the new files but does NOT
rebuild the running Docker container — the Space keeps serving the OLD image until a
*factory* rebuild. So mirroring the backend via create_commit alone never makes the new
code actually go live. After a real commit, main() now calls restart_space(
factory_reboot=True) so the mirrored backend serves with no manual step. It is gated on
a real commit: an in-sync run makes no commit and triggers NO rebuild (avoids a needless
multi-minute Docker rebuild). The rebuild outcome is surfaced in the run log — success
prints a ::notice:: with the resulting runtime stage; a failed request prints a loud
::error:: (mirrored-but-stale) and re-raises so a silent rebuild failure can't leave the
Space serving the old container.

delete-aware backend sync (drift-fix): the add/update-only path above left a stale
copy on the Space whenever a backend module was DELETED from the repo AND dropped from
the Dockerfile COPY set — the orphaned .py lingered in the Space tree forever. It is
harmless to the built image (no longer COPY'd) but makes the Space tree drift from
GitHub and confuses the hf-module-drift-check guard. select_deletions() now diffs the
Space's current .py tree against the computed mirror set and emits a delete for any
backend .py no longer in the mirror.

whole-directory removal (drift-fix): the first delete pass scoped deletions to the
directories the mirror still populates (managed_backend_dirs, derived from the mirror
itself). That left one edge case open: when an ENTIRE backend subdirectory is dropped
from the repo + Dockerfile COPY set, no .py from it survives in the mirror, so the dir
falls out of managed_backend_dirs and its orphaned .py were never swept — the Space tree
kept drifting from GitHub. The delete pass now also sweeps backend .py in directories
that are NOT a protected front-door / built-asset / vendor location (NON_BACKEND_PREFIXES
via is_protected_path), so a wholly-removed backend dir's modules are cleaned up too.

Deletion stays scoped to backend .py paths ONLY: a Space path is a delete candidate iff
it ends in .py, is not a *.bak* backup, is not still in the mirror, and EITHER lives in a
directory this sync actively populates (managed_backend_dirs) OR is not under a protected
prefix. This can NEVER touch README (.md), the front-door pages/*.{html,js} +
console/*.{html,js} files owned by hf-sync.yml, the built SPA bundles (console/assets,
console/static), or LFS/vendor blobs (static/, static-vendor/, static/vendor3d, etc.) —
they are either non-.py or live under a NON_BACKEND_PREFIXES path the sweep refuses to
enter. A denylist of those few stable HF-Space front-door/vendor roots is used here
(rather than a hardcoded allowlist of backend dirs) precisely so a relocated or
wholly-removed backend dir is still cleaned up without code changes.

Pure helpers (no huggingface_hub dependency): git_blob_sha1, parse_dockerfile_copy_srcs,
expand_py_files, build_mirror_set, select_changed_files, managed_backend_dirs,
is_protected_path, select_deletions, sync_to_space, factory_rebuild,
sync_and_maybe_rebuild. main() lazily imports huggingface_hub so the test suite can run
network-free with pure stdlib.
"""
import glob
import hashlib
import os


def git_blob_sha1(data: bytes) -> str:
    """git blob sha1 of raw bytes (== HF blob_id for non-LFS files)."""
    # Content-addressing, NOT a security digest: the algorithm is fixed by git's
    # own blob-id scheme (SHA-1), so it cannot be swapped for a stronger hash.
    h = hashlib.sha1(usedforsecurity=False)
    h.update(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


def parse_dockerfile_copy_srcs(dockerfile_path: str = "Dockerfile") -> list:
    """Every COPY <src...> <dest> source token from the Dockerfile (dest dropped)."""
    copy_srcs = []
    with open(dockerfile_path, "r", encoding="utf-8") as fh:
        for raw in fh:
            s = raw.strip()
            if not s.upper().startswith("COPY "):
                continue
            toks = [t for t in s.split()[1:] if not t.startswith("--")]
            if len(toks) < 2:
                continue
            copy_srcs.extend(toks[:-1])  # everything but the dest is a source
    return copy_srcs


def expand_py_files(copy_srcs) -> set:
    """Expand COPY sources to the concrete set of .py files in the checkout."""
    py_files = set()
    for src in copy_srcs:
        if any(ch in src for ch in "*?[]"):
            for m in glob.glob(src, recursive=True):
                if m.endswith(".py") and os.path.isfile(m):
                    py_files.add(os.path.normpath(m))
        elif os.path.isfile(src):
            if src.endswith(".py"):
                py_files.add(os.path.normpath(src))
        elif os.path.isdir(src):
            for root, _, files in os.walk(src):
                for f in files:
                    if f.endswith(".py"):
                        py_files.add(os.path.normpath(os.path.join(root, f)))
    return py_files


def build_mirror_set(py_files) -> list:
    """py_files + Dockerfile + serve.py, restricted to files that exist, sorted."""
    mirror = set(py_files)
    mirror.add("Dockerfile")             # so new COPY lines reach the Space
    if os.path.isfile("serve.py"):
        mirror.add("serve.py")           # primary backend entrypoint
    return sorted(p for p in mirror if os.path.isfile(p))


def select_changed_files(mirror, space_oid, read_bytes):
    """Return [(path, data), ...] for files whose content differs from the Space.

    A file is selected iff its local git-blob sha1 differs from the Space's blob_id
    for that path. A path absent from space_oid (new on the Space) always differs and
    is selected. A byte-identical file (matching OID) is skipped — this is the
    only-changed-files guarantee the auto-push relies on.

    mirror:     iterable of repo-relative paths to consider.
    space_oid:  dict {path: blob_id} of the Space's current tree (None blob_id => differs).
    read_bytes: callable(path) -> bytes; injected so tests need no real files.
    """
    changed = []
    for p in mirror:
        data = read_bytes(p)
        if space_oid.get(p) == git_blob_sha1(data):
            continue  # byte-identical on the Space already
        changed.append((p, data))
    return changed


def managed_backend_dirs(mirror) -> set:
    """Directories this sync populates, derived from the .py files in the mirror set.

    The delete pass is scoped to these directories so it can ONLY ever remove .py
    files from locations we actively mirror backend modules into. Deriving them from
    the mirror set itself (rather than a hardcoded allowlist) means a relocated
    backend tree stays correctly scoped without code changes, and front-door / built
    asset / vendor directories — which this sync never populates — are inherently
    out of scope.
    """
    return {os.path.dirname(p) for p in mirror if p.endswith(".py")}


# HF-Space directory prefixes the backend sync must NEVER delete from, even when an
# orphaned .py turns up under one. These are the front-door surfaces owned by hf-sync.yml
# (pages/, console/ — which the Dockerfile COPYs to static/ on the Space, web/) and the
# built SPA bundles + LFS/vendor blobs (static/, static-vendor/, and so static/vendor3d/).
# Backend modules never live under these, so excluding them keeps the whole-directory
# delete sweep scoped to backend .py. This is a small, stable DENYLIST (HF-Space layout
# conventions) — deliberately not an allowlist of backend dirs, so a relocated or
# wholly-removed backend dir is still swept without code changes.
NON_BACKEND_PREFIXES = ("pages/", "console/", "web/", "static/", "static-vendor/")


def is_protected_path(path) -> bool:
    """True if path lives under a front-door / built-asset / vendor prefix (never backend).

    Such a path is exempt from the delete sweep no matter what: those directories are
    populated by hf-sync.yml / the build / vendored blobs, not this backend sync, so a
    .py appearing there must not be removed by us.
    """
    norm = path.replace(os.sep, "/")
    return any(norm == pre.rstrip("/") or norm.startswith(pre) for pre in NON_BACKEND_PREFIXES)


def select_deletions(mirror, space_paths):
    """Space backend .py paths no longer in the mirror set, to delete from the Space.

    A Space path is a delete candidate iff ALL hold:
      * it ends in .py (README is .md; front-door pages/console files are .html/.js),
      * it is NOT a *.bak* timestamped backup,
      * it is NOT still in the mirror set (i.e. still COPY'd / still serve.py), and
      * its directory is one this sync still populates (managed_backend_dirs(mirror)) OR
        it is not under a protected front-door/built-asset/vendor prefix
        (is_protected_path) — the latter is what sweeps a WHOLE backend directory that was
        removed from the repo + Dockerfile COPY set, so it no longer appears in the mirror
        at all and thus falls out of managed_backend_dirs.

    Both scope clauses keep deletion to backend .py ONLY: managed_backend_dirs are by
    construction backend locations, and the protected denylist carves out the built SPA
    bundles (console/assets, console/static) and LFS/vendor blobs (static/vendor3d, etc.)
    — they live under a NON_BACKEND_PREFIXES path, so they can never be selected even if
    one happened to carry a .py extension.

    mirror:      iterable of repo-relative paths kept in sync (the local mirror set).
    space_paths: iterable of every path currently in the Space tree.
    Returns a sorted list of paths to delete.
    """
    mirror_set = set(mirror)
    dirs = managed_backend_dirs(mirror)
    deletions = []
    for p in space_paths:
        if not p.endswith(".py"):
            continue
        if ".bak" in os.path.basename(p):
            continue
        if p in mirror_set:
            continue
        if os.path.dirname(p) in dirs or not is_protected_path(p):
            deletions.append(p)
    return sorted(deletions)


def sync_to_space(mirror, space_oid, read_bytes, api, op_add, space_id, op_delete=None):
    """Build CommitOperations for changed + orphaned backend files and commit them.

    api/op_add/op_delete are injected (the real huggingface_hub HfApi +
    CommitOperationAdd + CommitOperationDelete in production, fakes in tests) so both
    the add and delete assembly paths are exercised network-free. When op_delete is
    None the delete pass is skipped entirely (add/update-only, legacy behaviour).

    Returns (changed_paths, deleted_paths). Both empty => no-op, no commit created.
    """
    changed = select_changed_files(mirror, space_oid, read_bytes)
    changed_paths = [p for p, _ in changed]
    deleted_paths = (
        select_deletions(mirror, space_oid.keys()) if op_delete is not None else []
    )
    if not changed and not deleted_paths:
        print("Backend (.py + Dockerfile) already in sync with the Space — nothing to push.")
        return changed_paths, deleted_paths

    ops = [op_add(path_in_repo=p, path_or_fileobj=data) for p, data in changed]
    ops.extend(op_delete(path_in_repo=p) for p in deleted_paths)
    commit = api.create_commit(
        repo_id=space_id,
        repo_type="space",
        operations=ops,
        commit_message="chore(sync): mirror backend .py + Dockerfile to Space (hf-sync-backend)",
        commit_description=(
            "Automated backend sync from szl-holdings/a11oy main via hf-sync-backend.\n"
            "Updated (differed from the Space): " + (", ".join(changed_paths) or "(none)") + "\n"
            "Deleted (gone from the repo + Dockerfile COPY set): "
            + (", ".join(deleted_paths) or "(none)") + "\n\n"
            "Keeps the Space-built backend (serve.py + the Dockerfile-COPY'd .py\n"
            "modules) identical to GitHub main so the Space never rebuilds from a\n"
            "stale backend, new endpoints don't 404 there, and orphaned modules\n"
            "removed from the repo don't linger in the Space tree."
        ),
    )
    print("HF commit:", getattr(commit, "oid", commit), "->", space_id,
          "changed:", len(changed_paths), "deleted:", len(deleted_paths))
    for p in changed_paths:
        print("  synced:", p)
    for p in deleted_paths:
        print("  deleted:", p)
    return changed_paths, deleted_paths


def factory_rebuild(api, space_id):
    """Trigger an HF Space factory rebuild so the just-mirrored backend actually serves.

    An HF Space commit LANDS the new files but does NOT rebuild the running Docker
    container — the Space keeps serving the OLD image until a *factory* rebuild. So
    mirroring the backend via create_commit alone never makes the new code go live.
    This calls restart_space(factory_reboot=True) (huggingface_hub, same HF_TOKEN, no
    raw HTTP / no 3rd-party action) after a real commit so the change serves with no
    human step.

    The outcome is surfaced in the run log: on success a ::notice:: prints the resulting
    runtime stage (e.g. RUNNING_BUILDING); on failure a loud ::error:: warns the backend
    was mirrored but the running container was NOT rebuilt, and the exception re-raises so
    a silent rebuild failure can't leave the Space on the old container.

    Returns the resulting runtime stage string (or None if unavailable).
    """
    try:
        info = api.restart_space(repo_id=space_id, factory_reboot=True)
    except Exception as exc:  # noqa: BLE001 - surface ANY rebuild failure loudly, then re-raise
        print(f"::error::Factory rebuild request FAILED for {space_id}: {exc}")
        print("::error::The backend was mirrored to the Space but the running container "
              "was NOT rebuilt — the Space may still serve the STALE backend until a "
              "manual factory rebuild is triggered.")
        raise
    runtime = getattr(info, "runtime", None)
    stage = getattr(runtime, "stage", None) if runtime is not None else None
    print(f"::notice::Factory rebuild triggered for {space_id} — runtime stage: {stage}")
    return stage


def sync_and_maybe_rebuild(mirror, space_oid, read_bytes, api, op_add, space_id,
                           op_delete=None, rebuild=factory_rebuild):
    """Mirror changed/orphaned backend files, then factory-rebuild ONLY on a real commit.

    This is the orchestration main() runs, extracted so the "rebuild iff a commit was
    made" gate is provable network-free: with fakes injected, the self-test asserts a
    change triggers exactly one rebuild and an in-sync run triggers none. rebuild is
    injected (defaults to factory_rebuild) so tests can record the call without touching
    a live Space.

    Returns (changed_paths, deleted_paths).
    """
    changed, deleted = sync_to_space(
        mirror, space_oid, read_bytes, api, op_add, space_id, op_delete=op_delete
    )
    if changed or deleted:
        rebuild(api, space_id)
    else:
        print("No commit made — skipping factory rebuild (Space already current).")
    return changed, deleted


def main() -> int:
    from huggingface_hub import HfApi, CommitOperationAdd, CommitOperationDelete

    token = os.environ.get("HF_TOKEN")
    if not token:
        print("::error::HF_TOKEN secret is not set on this repo — cannot push to the HuggingFace Space.")
        print("::error::Founder action required: add repo secret HF_TOKEN (HF write token with org write to SZLHOLDINGS).")
        return 1
    space_id = os.environ.get("SPACE_ID", "SZLHOLDINGS/a11oy")

    mirror = build_mirror_set(expand_py_files(parse_dockerfile_copy_srcs("Dockerfile")))
    print(f"Candidate backend files to mirror: {len(mirror)}")

    api = HfApi(token=token)
    space_oid = {}
    for it in api.list_repo_tree(repo_id=space_id, repo_type="space", recursive=True):
        path = getattr(it, "path", None)
        if path is not None:
            space_oid[path] = getattr(it, "blob_id", None)

    def read_bytes(p):
        with open(p, "rb") as fh:
            return fh.read()

    sync_and_maybe_rebuild(mirror, space_oid, read_bytes, api, CommitOperationAdd,
                           space_id, op_delete=CommitOperationDelete)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
