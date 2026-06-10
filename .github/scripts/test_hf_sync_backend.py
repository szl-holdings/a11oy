#!/usr/bin/env python3
"""Network-free self-test for hf_sync_backend.py — proves the AUTO-PUSH path.

The hf-sync-backend workflow was only ever observed on the "already in sync -> no-op"
path. This exercises the actual push path end-to-end with fakes (no network, no live
Space touched): it imports the SAME module the workflow runs and asserts the OID-diff
selection only pushes files whose content differs, leaves identical files untouched,
and (delete-aware) removes backend .py orphaned on the Space while never touching
README / front-door / built-asset / vendor paths.

Run by file path (the .github/scripts dir is not an importable package):
    python3 .github/scripts/test_hf_sync_backend.py
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hf_sync_backend as hsb  # noqa: E402


def oid(data: bytes) -> str:
    return hsb.git_blob_sha1(data)


class FakeOp:
    """Stand-in for huggingface_hub.CommitOperationAdd (records its args)."""

    def __init__(self, path_in_repo, path_or_fileobj):
        self.path_in_repo = path_in_repo
        self.path_or_fileobj = path_or_fileobj


class FakeDelete:
    """Stand-in for huggingface_hub.CommitOperationDelete (records its path)."""

    def __init__(self, path_in_repo):
        self.path_in_repo = path_in_repo


class FakeCommit:
    oid = "deadbeefcafe"


class FakeApi:
    """Records create_commit calls; fails the test if the no-op path commits."""

    def __init__(self):
        self.calls = []

    def create_commit(self, **kwargs):
        self.calls.append(kwargs)
        return FakeCommit()


class SelectChangedFilesTest(unittest.TestCase):
    def setUp(self):
        # Three mirrored files with known on-disk content.
        self.blobs = {
            "serve.py": b"print('serve v2')\n",          # CHANGED vs Space
            "szl_stable.py": b"X = 1\n",                  # IDENTICAL on Space
            "Dockerfile": b"FROM python:3.12\n",          # IDENTICAL on Space
            "szl_new.py": b"def f():\n    return 42\n",   # NEW (absent on Space)
        }
        self.read_bytes = lambda p: self.blobs[p]
        self.mirror = sorted(self.blobs)
        # Space tree: serve.py holds OLD content; stable/Dockerfile match; new absent.
        self.space_oid = {
            "serve.py": oid(b"print('serve v1')\n"),
            "szl_stable.py": oid(self.blobs["szl_stable.py"]),
            "Dockerfile": oid(self.blobs["Dockerfile"]),
        }

    def test_only_changed_and_new_selected(self):
        changed = hsb.select_changed_files(self.mirror, self.space_oid, self.read_bytes)
        paths = sorted(p for p, _ in changed)
        # Changed (serve.py) and new (szl_new.py) selected; identical files skipped.
        self.assertEqual(paths, ["serve.py", "szl_new.py"])
        # The unrelated, byte-identical file is NOT re-pushed.
        self.assertNotIn("szl_stable.py", paths)
        self.assertNotIn("Dockerfile", paths)

    def test_full_sync_already_in_sync_is_a_noop(self):
        # Every file matches the Space (including the new one now present).
        space_oid = {p: oid(d) for p, d in self.blobs.items()}
        changed = hsb.select_changed_files(self.mirror, space_oid, self.read_bytes)
        self.assertEqual(changed, [])

    def test_none_blob_id_counts_as_differing(self):
        # HF can report blob_id=None; treat as "differs" so we re-push, never silently skip.
        space_oid = dict(self.space_oid)
        space_oid["szl_stable.py"] = None
        changed = hsb.select_changed_files(["szl_stable.py"], space_oid, self.read_bytes)
        self.assertEqual([p for p, _ in changed], ["szl_stable.py"])


class SelectDeletionsTest(unittest.TestCase):
    """The delete pass removes orphaned backend .py and NOTHING else."""

    def setUp(self):
        # The mirror this run keeps in sync: root modules + a packaged subdir module.
        self.mirror = ["Dockerfile", "pkg/keep.py", "serve.py", "szl_keep.py"]

    def test_orphaned_backend_py_selected(self):
        space_paths = [
            "serve.py",            # in mirror -> keep
            "szl_keep.py",         # in mirror -> keep
            "szl_orphan.py",       # root backend .py NOT in mirror -> delete
            "pkg/keep.py",         # in mirror -> keep
            "pkg/gone.py",         # subdir backend .py NOT in mirror -> delete
        ]
        self.assertEqual(
            hsb.select_deletions(self.mirror, space_paths),
            ["pkg/gone.py", "szl_orphan.py"],
        )

    def test_never_touches_non_backend_or_unmanaged_dirs(self):
        space_paths = [
            "README.md",                       # not .py
            "pages/console.html",              # front-door (hf-sync.yml)
            "console/index.js",                # front-door (hf-sync.yml)
            "console/assets/app.py",           # built-asset dir we never populate
            "static/vendor3d/three.py",        # vendor dir we never populate
            "szl_orphan.py.bak-20260601",      # timestamped backup
            "szl_orphan.py",                   # the ONLY real delete candidate
        ]
        self.assertEqual(hsb.select_deletions(self.mirror, space_paths), ["szl_orphan.py"])

    def test_in_sync_tree_yields_no_deletions(self):
        space_paths = ["Dockerfile", "serve.py", "szl_keep.py", "pkg/keep.py"]
        self.assertEqual(hsb.select_deletions(self.mirror, space_paths), [])


class SyncToSpacePushTest(unittest.TestCase):
    """End-to-end: assert create_commit gets EXACTLY the changed/deleted files."""

    def setUp(self):
        self.blobs = {
            "serve.py": b"print('serve v2')\n",
            "szl_stable.py": b"X = 1\n",
            "Dockerfile": b"FROM python:3.12\n",
        }
        self.read_bytes = lambda p: self.blobs[p]
        self.mirror = sorted(self.blobs)
        self.space_oid = {
            "serve.py": oid(b"print('serve v1')\n"),       # differs
            "szl_stable.py": oid(self.blobs["szl_stable.py"]),  # identical
            "Dockerfile": oid(self.blobs["Dockerfile"]),         # identical
        }

    def test_commit_contains_only_changed_file(self):
        api = FakeApi()
        changed, deleted = hsb.sync_to_space(
            self.mirror, self.space_oid, self.read_bytes, api, FakeOp,
            "SZLHOLDINGS/a11oy", op_delete=FakeDelete,
        )
        self.assertEqual(changed, ["serve.py"])
        self.assertEqual(deleted, [])
        self.assertEqual(len(api.calls), 1, "exactly one commit for a non-empty change set")
        ops = api.calls[0]["operations"]
        committed = [op.path_in_repo for op in ops]
        self.assertEqual(committed, ["serve.py"])
        # The identical files must NOT appear in the commit operations.
        self.assertNotIn("szl_stable.py", committed)
        self.assertNotIn("Dockerfile", committed)
        # The committed payload is the new content, not the stale Space copy.
        self.assertEqual(ops[0].path_or_fileobj, self.blobs["serve.py"])
        self.assertEqual(api.calls[0]["repo_type"], "space")
        self.assertEqual(api.calls[0]["repo_id"], "SZLHOLDINGS/a11oy")

    def test_commit_deletes_orphaned_backend_py(self):
        api = FakeApi()
        # Everything is byte-identical on the Space, but an orphaned backend .py lingers.
        in_sync = {p: oid(d) for p, d in self.blobs.items()}
        in_sync["szl_orphan.py"] = oid(b"# old module removed from the repo\n")
        changed, deleted = hsb.sync_to_space(
            self.mirror, in_sync, self.read_bytes, api, FakeOp,
            "SZLHOLDINGS/a11oy", op_delete=FakeDelete,
        )
        self.assertEqual(changed, [], "no content changes — only a deletion")
        self.assertEqual(deleted, ["szl_orphan.py"])
        self.assertEqual(len(api.calls), 1, "a deletion-only change set still commits once")
        ops = api.calls[0]["operations"]
        self.assertEqual(len(ops), 1)
        self.assertIsInstance(ops[0], FakeDelete)
        self.assertEqual(ops[0].path_in_repo, "szl_orphan.py")

    def test_no_commit_when_everything_in_sync(self):
        api = FakeApi()
        in_sync = {p: oid(d) for p, d in self.blobs.items()}
        changed, deleted = hsb.sync_to_space(
            self.mirror, in_sync, self.read_bytes, api, FakeOp,
            "SZLHOLDINGS/a11oy", op_delete=FakeDelete,
        )
        self.assertEqual(changed, [])
        self.assertEqual(deleted, [])
        self.assertEqual(api.calls, [], "an in-sync run must never create a commit")

    def test_delete_pass_skipped_without_op_delete(self):
        # Legacy add/update-only behaviour: orphan on the Space, but no op_delete given.
        api = FakeApi()
        in_sync = {p: oid(d) for p, d in self.blobs.items()}
        in_sync["szl_orphan.py"] = oid(b"# lingering\n")
        changed, deleted = hsb.sync_to_space(
            self.mirror, in_sync, self.read_bytes, api, FakeOp, "SZLHOLDINGS/a11oy",
        )
        self.assertEqual(changed, [])
        self.assertEqual(deleted, [])
        self.assertEqual(api.calls, [], "no op_delete => no delete pass, in-sync is a no-op")


class DockerfileParseTest(unittest.TestCase):
    def test_copy_parse_and_expand(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            cwd = os.getcwd()
            try:
                os.chdir(d)
                with open("Dockerfile", "w") as fh:
                    fh.write(
                        "FROM python:3.12\n"
                        "COPY --chown=u:g serve.py /app/serve.py\n"
                        "COPY szl_a.py szl_b.py /app/\n"
                        "COPY pages/ /app/pages/\n"
                        "RUN echo not-a-copy\n"
                    )
                for name in ("serve.py", "szl_a.py", "szl_b.py"):
                    with open(name, "w") as fh:
                        fh.write("x = 1\n")
                srcs = hsb.parse_dockerfile_copy_srcs("Dockerfile")
                # --chown flag dropped; dest tokens dropped; both srcs of multi-src kept.
                self.assertIn("serve.py", srcs)
                self.assertIn("szl_a.py", srcs)
                self.assertIn("szl_b.py", srcs)
                self.assertNotIn("/app/", srcs)
                py = hsb.expand_py_files(srcs)
                self.assertEqual(py, {"serve.py", "szl_a.py", "szl_b.py"})
                mirror = hsb.build_mirror_set(py)
                self.assertIn("Dockerfile", mirror)
                self.assertIn("serve.py", mirror)
            finally:
                os.chdir(cwd)


if __name__ == "__main__":
    unittest.main(verbosity=2)
