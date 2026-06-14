#!/usr/bin/env python3
"""Network-free self-test for hf_sync_backend.py — proves the AUTO-PUSH + REBUILD path.

The hf-sync-backend workflow was only ever observed on the "already in sync -> no-op"
path. This exercises the actual push path end-to-end with fakes (no network, no live
Space touched): it imports the SAME module the workflow runs and asserts the OID-diff
selection only pushes files whose content differs, leaves identical files untouched,
and (delete-aware) removes backend .py orphaned on the Space — including the modules
of an ENTIRE backend directory that was removed from the repo + Dockerfile COPY set —
while never touching README / front-door / built-asset / vendor paths.

It also proves the auto factory-rebuild gate: a real commit triggers exactly one
restart_space(factory_reboot=True), an in-sync run triggers none, and a failed rebuild
request re-raises (so a silent rebuild failure can't leave the Space on the old image).

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


class FakeRuntime:
    def __init__(self, stage):
        self.stage = stage


class FakeSpaceInfo:
    def __init__(self, stage):
        self.runtime = FakeRuntime(stage)


class FakeApi:
    """Records create_commit + restart_space calls; fails if the no-op path commits."""

    def __init__(self, rebuild_stage="RUNNING_BUILDING", rebuild_error=None):
        self.calls = []
        self.restart_calls = []
        self._rebuild_stage = rebuild_stage
        self._rebuild_error = rebuild_error

    def create_commit(self, **kwargs):
        self.calls.append(kwargs)
        return FakeCommit()

    def restart_space(self, **kwargs):
        self.restart_calls.append(kwargs)
        if self._rebuild_error is not None:
            raise self._rebuild_error
        return FakeSpaceInfo(self._rebuild_stage)


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

    def test_entire_packaged_dir_removed_is_swept(self):
        # The "whole directory removed" edge case: `gone_pkg/` was a packaged backend dir
        # whose modules used to be COPY'd, but the entire dir was dropped from the repo +
        # Dockerfile. No `gone_pkg/*.py` survives in the mirror, so the dir is NOT in
        # managed_backend_dirs(mirror) at all — yet its orphaned .py must still be swept.
        self.assertNotIn("gone_pkg", hsb.managed_backend_dirs(self.mirror))
        space_paths = [
            "serve.py",                  # in mirror -> keep
            "szl_keep.py",               # in mirror -> keep
            "pkg/keep.py",               # in mirror -> keep
            "gone_pkg/a.py",             # wholly-removed backend dir -> delete
            "gone_pkg/b.py",             # wholly-removed backend dir -> delete
            "gone_pkg/sub/c.py",         # nested under a wholly-removed dir -> delete
            # Protected surfaces that happen to carry a .py must NEVER be swept, even
            # though their directories are also absent from managed_backend_dirs:
            "console/assets/app.py",     # built SPA bundle
            "static/vendor3d/three.py",  # LFS/vendor blob
            "static-vendor/lib.py",      # vendored asset
            "pages/widget.py",           # front-door (hf-sync.yml)
            "web/panel.py",              # front-door html dir
            "gone_pkg/old.py.bak-20260601",  # timestamped backup -> keep
        ]
        self.assertEqual(
            hsb.select_deletions(self.mirror, space_paths),
            ["gone_pkg/a.py", "gone_pkg/b.py", "gone_pkg/sub/c.py"],
        )

    def test_protected_prefixes_never_swept_even_when_unmanaged(self):
        # Sanity: each protected prefix is exempt from the sweep on its own.
        for protected in (
            "console/assets/app.py",
            "console/static/x.py",
            "static/vendor3d/three.py",
            "static-vendor/lib.py",
            "pages/widget.py",
            "web/panel.py",
        ):
            self.assertTrue(hsb.is_protected_path(protected), protected)
            self.assertEqual(hsb.select_deletions(self.mirror, [protected]), [])


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


class FactoryRebuildTest(unittest.TestCase):
    """factory_rebuild() asks HF for a factory reboot and surfaces the outcome."""

    def test_success_requests_factory_reboot_and_returns_stage(self):
        api = FakeApi(rebuild_stage="RUNNING_BUILDING")
        stage = hsb.factory_rebuild(api, "SZLHOLDINGS/a11oy")
        self.assertEqual(stage, "RUNNING_BUILDING")
        self.assertEqual(len(api.restart_calls), 1)
        self.assertEqual(api.restart_calls[0]["repo_id"], "SZLHOLDINGS/a11oy")
        # The whole point: it must be a FACTORY reboot, not a plain restart.
        self.assertIs(api.restart_calls[0]["factory_reboot"], True)

    def test_failed_rebuild_reraises(self):
        api = FakeApi(rebuild_error=RuntimeError("HF 500"))
        # A silent rebuild failure must NOT be swallowed — it has to fail the run.
        with self.assertRaises(RuntimeError):
            hsb.factory_rebuild(api, "SZLHOLDINGS/a11oy")
        self.assertEqual(len(api.restart_calls), 1)

    def test_missing_runtime_info_does_not_crash(self):
        class NoRuntimeApi(FakeApi):
            def restart_space(self, **kwargs):
                self.restart_calls.append(kwargs)
                return object()  # no .runtime attribute
        api = NoRuntimeApi()
        self.assertIsNone(hsb.factory_rebuild(api, "SZLHOLDINGS/a11oy"))


class SyncAndMaybeRebuildTest(unittest.TestCase):
    """The rebuild is gated on a real commit: change -> rebuild, no-op -> no rebuild."""

    def setUp(self):
        self.blobs = {
            "serve.py": b"print('serve v2')\n",
            "szl_stable.py": b"X = 1\n",
            "Dockerfile": b"FROM python:3.12\n",
        }
        self.read_bytes = lambda p: self.blobs[p]
        self.mirror = sorted(self.blobs)
        self.changed_space = {
            "serve.py": oid(b"print('serve v1')\n"),       # differs
            "szl_stable.py": oid(self.blobs["szl_stable.py"]),
            "Dockerfile": oid(self.blobs["Dockerfile"]),
        }
        self.in_sync_space = {p: oid(d) for p, d in self.blobs.items()}

    def test_change_triggers_exactly_one_factory_rebuild(self):
        api = FakeApi()
        rebuilds = []
        changed, _ = hsb.sync_and_maybe_rebuild(
            self.mirror, self.changed_space, self.read_bytes, api, FakeOp,
            "SZLHOLDINGS/a11oy", op_delete=FakeDelete,
            rebuild=lambda a, s: rebuilds.append((a, s)),
        )
        self.assertEqual(changed, ["serve.py"])
        self.assertEqual(len(rebuilds), 1, "a real commit must trigger one rebuild")
        self.assertEqual(rebuilds[0][1], "SZLHOLDINGS/a11oy")

    def test_deletion_only_still_triggers_rebuild(self):
        api = FakeApi()
        rebuilds = []
        space = dict(self.in_sync_space)
        space["szl_orphan.py"] = oid(b"# removed module still on Space\n")
        changed, deleted = hsb.sync_and_maybe_rebuild(
            self.mirror, space, self.read_bytes, api, FakeOp,
            "SZLHOLDINGS/a11oy", op_delete=FakeDelete,
            rebuild=lambda a, s: rebuilds.append(s),
        )
        self.assertEqual(changed, [])
        self.assertEqual(deleted, ["szl_orphan.py"])
        self.assertEqual(len(rebuilds), 1, "a deletion-only commit must still rebuild")

    def test_in_sync_run_triggers_no_rebuild(self):
        api = FakeApi()
        rebuilds = []
        changed, deleted = hsb.sync_and_maybe_rebuild(
            self.mirror, self.in_sync_space, self.read_bytes, api, FakeOp,
            "SZLHOLDINGS/a11oy", op_delete=FakeDelete,
            rebuild=lambda a, s: rebuilds.append(s),
        )
        self.assertEqual(changed, [])
        self.assertEqual(deleted, [])
        self.assertEqual(api.calls, [], "no commit on an in-sync run")
        self.assertEqual(rebuilds, [], "no commit => NO needless factory rebuild")

    def test_default_rebuild_is_factory_rebuild(self):
        # With the real default rebuild callable, a change drives api.restart_space.
        api = FakeApi()
        hsb.sync_and_maybe_rebuild(
            self.mirror, self.changed_space, self.read_bytes, api, FakeOp,
            "SZLHOLDINGS/a11oy", op_delete=FakeDelete,
        )
        self.assertEqual(len(api.restart_calls), 1)
        self.assertIs(api.restart_calls[0]["factory_reboot"], True)


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
