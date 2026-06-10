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

Pure helpers (no huggingface_hub dependency): git_blob_sha1, parse_dockerfile_copy_srcs,
expand_py_files, build_mirror_set, select_changed_files, sync_to_space. main() lazily
imports huggingface_hub so the test suite can run network-free with pure stdlib.
"""
import glob
import hashlib
import os


def git_blob_sha1(data: bytes) -> str:
    """git blob sha1 of raw bytes (== HF blob_id for non-LFS files)."""
    h = hashlib.sha1()
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


def sync_to_space(mirror, space_oid, read_bytes, api, op_add, space_id):
    """Build CommitOperationAdds for changed files and commit them via `api`.

    api/op_add are injected (the real huggingface_hub HfApi + CommitOperationAdd in
    production, fakes in tests) so the commit-assembly path is exercised network-free.
    Returns the list of changed paths actually committed (empty => no-op, no commit).
    """
    changed = select_changed_files(mirror, space_oid, read_bytes)
    changed_paths = [p for p, _ in changed]
    if not changed:
        print("Backend (.py + Dockerfile) already in sync with the Space — nothing to push.")
        return changed_paths

    ops = [op_add(path_in_repo=p, path_or_fileobj=data) for p, data in changed]
    commit = api.create_commit(
        repo_id=space_id,
        repo_type="space",
        operations=ops,
        commit_message="chore(sync): mirror backend .py + Dockerfile to Space (hf-sync-backend)",
        commit_description=(
            "Automated backend sync from szl-holdings/a11oy main via hf-sync-backend.\n"
            "Updated (differed from the Space): " + ", ".join(changed_paths) + "\n\n"
            "Keeps the Space-built backend (serve.py + the Dockerfile-COPY'd .py\n"
            "modules) identical to GitHub main so the Space never rebuilds from a\n"
            "stale backend and new endpoints don't 404 there."
        ),
    )
    print("HF commit:", getattr(commit, "oid", commit), "->", space_id, "changed:", len(changed_paths))
    for p in changed_paths:
        print("  synced:", p)
    return changed_paths


def main() -> int:
    from huggingface_hub import HfApi, CommitOperationAdd

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

    sync_to_space(mirror, space_oid, read_bytes, api, CommitOperationAdd, space_id)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
