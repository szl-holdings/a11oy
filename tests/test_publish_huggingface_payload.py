"""Offline regression controls for the existing fixed-target payload publisher."""
from __future__ import annotations

import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import prepare_huggingface_payload as prepare
import publish_huggingface_payload as publish

PARENT = "a" * 40
SOURCE = "b" * 40
COMMIT = "c" * 40


class Add:
    def __init__(self, *, path_in_repo, path_or_fileobj):
        self.path_in_repo = path_in_repo
        self.content = path_or_fileobj


class MemoryHub:
    def __init__(self):
        self.head = PARENT
        self.files = {
            "README.md": b"old card\n",
            "bom/model-bom.cdx.json": b'{"bomFormat":"CycloneDX"}\n',
            ".gitattributes": b"*.bin filter=lfs\n",
        }
        self.parent_files = dict(self.files)
        self.calls = []
        self.reads = []
        self.commits = []
        self.private = False
        self.gated = False
        self.id = publish.TARGET
        self.race_at_commit = False
        self.corrupt_after_commit = None

    def repo_info(self, **kwargs):
        self.calls.append(kwargs)
        assert kwargs["repo_id"] == publish.TARGET
        assert kwargs["repo_type"] == "model"
        assert kwargs["files_metadata"] is True
        revision = kwargs["revision"]
        if revision == "main":
            revision = self.head
        files = self.parent_files if revision == PARENT else self.files
        return SimpleNamespace(
            id=self.id, private=self.private, gated=self.gated, sha=revision,
            siblings=[SimpleNamespace(rfilename=p, size=len(b)) for p, b in files.items()],
        )

    def read(self, path, revision, size):
        self.reads.append((path, revision, size))
        files = self.parent_files if revision == PARENT else self.files
        return files[path]

    def create_commit(self, **kwargs):
        assert kwargs["revision"] == "main"
        if self.race_at_commit:
            self.head = "d" * 40
        if kwargs["parent_commit"] != self.head:
            raise publish.PublishError("Parent conflict.")
        self.commits.append(kwargs)
        for operation in kwargs["operations"]:
            assert isinstance(operation, Add)
            self.files[operation.path_in_repo] = operation.content
        self.head = COMMIT
        if self.corrupt_after_commit:
            self.corrupt_after_commit(self.files)
        return SimpleNamespace(oid=COMMIT)


class PublisherControls(unittest.TestCase):
    def setUp(self):
        self.api = MemoryHub()
        self.payload = {"README.md": b"new source card\n", "LICENSE": b"source license\n"}

    def run_plan(self, **overrides):
        options = dict(read_file=self.api.read, operation_factory=Add,
                       check_source=lambda: SOURCE)
        options.update(overrides)
        return publish.reconcile(self.api, PARENT, self.payload, SOURCE, **options)

    def test_default_plan_reads_preserved_parent_bytes_without_mutation(self):
        result = self.run_plan()
        self.assertEqual(result["mode"], "PLAN")
        self.assertFalse(result["verified"])
        self.assertEqual(result["deleted_paths"], [])
        self.assertEqual({x["path"] for x in result["preserved"]}, publish.PRESERVE)
        self.assertEqual(self.api.commits, [])
        self.assertTrue(all(revision == PARENT for _, revision, _ in self.api.reads))

    def test_apply_is_one_additive_parent_bound_commit_with_full_immutable_readback(self):
        original_bom = self.api.files["bom/model-bom.cdx.json"]
        result = self.run_plan(apply=True)
        self.assertTrue(result["verified"])
        self.assertEqual(result["commit"], COMMIT)
        self.assertEqual(len(self.api.commits), 1)
        operation = self.api.commits[0]
        self.assertEqual(operation["parent_commit"], PARENT)
        self.assertEqual(operation["repo_id"], publish.TARGET)
        self.assertEqual({x.path_in_repo for x in operation["operations"]}, set(self.payload))
        self.assertEqual(self.api.files["bom/model-bom.cdx.json"], original_bom)
        self.assertEqual({path for path, revision, _ in self.api.reads if revision == COMMIT},
                         set(self.payload) | publish.PRESERVE)

    def test_old_prune_footprint_is_now_preserved_instead_of_deleted(self):
        stale = set(self.api.parent_files) - self.payload.keys()
        self.assertIn("bom/model-bom.cdx.json", stale)
        self.run_plan(apply=True)
        self.assertEqual(self.api.files.keys(), self.payload.keys() | stale)

    def test_unknown_remote_file_requires_review_before_any_commit(self):
        self.api.parent_files["unowned/private-notes.txt"] = b"unknown"
        with self.assertRaisesRegex(publish.PublishError, "Unmanaged remote"):
            self.run_plan(apply=True)
        self.assertEqual(self.api.commits, [])
        self.assertEqual(self.api.reads, [])

    def test_payload_cannot_overwrite_bom_or_provider_attributes(self):
        for path in publish.PRESERVE:
            with self.subTest(path=path):
                self.payload[path] = b"overwrite"
                with self.assertRaisesRegex(publish.PublishError, "collides"):
                    self.run_plan(apply=True)
                del self.payload[path]
        self.assertEqual(self.api.commits, [])

    def test_stale_operator_parent_refuses_before_mutation(self):
        self.api.head = "d" * 40
        with self.assertRaisesRegex(publish.PublishError, "advanced"):
            self.run_plan(apply=True)
        self.assertEqual(self.api.commits, [])

    def test_source_recheck_failure_refuses_before_mutation(self):
        with self.assertRaisesRegex(publish.PublishError, "source changed"):
            self.run_plan(apply=True, check_source=lambda: "d" * 40)
        self.assertEqual(self.api.commits, [])

    def test_parent_advance_during_source_recheck_refuses_before_mutation(self):
        def advance():
            self.api.head = "d" * 40
            return SOURCE
        with self.assertRaisesRegex(publish.PublishError, "advanced"):
            self.run_plan(apply=True, check_source=advance)
        self.assertEqual(self.api.commits, [])

    def test_server_side_parent_conflict_never_retries_or_rebases(self):
        self.api.race_at_commit = True
        with self.assertRaisesRegex(publish.PublishError, "Parent conflict"):
            self.run_plan(apply=True)
        self.assertEqual(self.api.commits, [])

    def test_postcommit_corruption_never_yields_success(self):
        def changed_bytes(files):
            files["README.md"] = b"x" * len(files["README.md"])
        def removed_bom(files):
            del files["bom/model-bom.cdx.json"]
        def unknown_extra(files):
            files["surprise.txt"] = b"new"
        def changed_bom(files):
            files["bom/model-bom.cdx.json"] = b"corrupt"
        for corrupt in (changed_bytes, removed_bom, unknown_extra, changed_bom):
            with self.subTest(corrupt=corrupt.__name__):
                self.api = MemoryHub()
                self.api.corrupt_after_commit = corrupt
                with self.assertRaisesRegex(publish.PublishError, COMMIT + " exists.*unverified"):
                    self.run_plan(apply=True)
                self.assertEqual(len(self.api.commits), 1)

    def test_failed_postcommit_transport_never_yields_success(self):
        def read(path, revision, size):
            if revision == COMMIT:
                raise OSError("offline readback failure")
            return self.api.read(path, revision, size)
        with self.assertRaisesRegex(publish.PublishError, "exists.*unverified"):
            self.run_plan(apply=True, read_file=read)
        self.assertEqual(len(self.api.commits), 1)

    def test_visibility_gate_and_target_mismatch_do_not_mutate(self):
        for key, value in (("private", True), ("gated", "auto"), ("gated", None),
                           ("id", "another/target")):
            with self.subTest(key=key, value=value):
                self.api = MemoryHub()
                setattr(self.api, key, value)
                with self.assertRaisesRegex(publish.PublishError, "fixed existing target"):
                    self.run_plan(apply=True)
                self.assertEqual(self.api.commits, [])

    def test_invalid_revision_is_rejected_before_api_access(self):
        for value in ("main", "../x", "A" * 40, "a" * 39, ""):
            with self.subTest(value=value):
                with self.assertRaises(publish.PublishError):
                    publish.reconcile(self.api, value, self.payload, SOURCE,
                                      read_file=self.api.read, operation_factory=Add,
                                      check_source=lambda: SOURCE, apply=True)
        self.assertEqual(self.api.calls, [])


class SourceAndPayloadControls(unittest.TestCase):
    def test_canonical_source_requires_current_signed_clean_main(self):
        def git_result(command, **kwargs):
            arguments = tuple(command[1:])
            if arguments == ("rev-parse", "--show-toplevel"):
                return str(publish.ROOT)
            if arguments == ("rev-parse", "HEAD"):
                return SOURCE
            return ""
        valid = {"sha": SOURCE, "verification": {"verified": True, "reason": "valid"}}
        with patch.object(publish.subprocess, "check_output", side_effect=git_result):
            with patch.object(publish, "github_json",
                              side_effect=[{"object": {"sha": SOURCE}}, valid]):
                self.assertEqual(publish.canonical_source(), SOURCE)
            for commit in ({**valid, "sha": "d" * 40},
                           {"sha": SOURCE, "verification": {"verified": False, "reason": "unsigned"}},
                           {"sha": SOURCE, "verification": {"verified": True, "reason": "unknown"}}):
                with self.subTest(commit=commit):
                    with patch.object(publish, "github_json",
                                      side_effect=[{"object": {"sha": SOURCE}}, commit]):
                        with self.assertRaisesRegex(publish.PublishError, "signature evidence"):
                            publish.canonical_source()
            with patch.object(publish, "github_json", return_value={"object": {"sha": "d" * 40}}):
                with self.assertRaisesRegex(publish.PublishError, "currently observed"):
                    publish.canonical_source()

    def test_dirty_ignored_or_symlink_source_refuses_without_network(self):
        for failing_arg, value in (("status", " M README.md"),
                                   ("-v", "h huggingface/README.md"),
                                   ("-v", "S huggingface/README.md"),
                                   ("--others", "huggingface/test-results/ignored.json"),
                                   ("--stage", "120000 abc 0\tdocs/input.md")):
            def git_result(command, **kwargs):
                if command[1:] == ["rev-parse", "--show-toplevel"]:
                    return str(publish.ROOT)
                if command[1:] == ["rev-parse", "HEAD"]:
                    return SOURCE
                return value if failing_arg in command else ""
            with self.subTest(failing_arg=failing_arg):
                with patch.object(publish.subprocess, "check_output", side_effect=git_result):
                    with patch.object(publish, "github_json") as network:
                        with self.assertRaises(publish.PublishError):
                            publish.canonical_source()
                        network.assert_not_called()

    def test_source_redirect_is_refused(self):
        with self.assertRaisesRegex(publish.PublishError, "redirected"):
            publish.NoRedirect().redirect_request(None, None, 302, None, None,
                                                   "https://another.example/source")

    def test_remote_paths_sizes_and_duplicates_are_closed(self):
        for siblings in (
            [SimpleNamespace(rfilename="../outside", size=1)],
            [SimpleNamespace(rfilename="x", size=None)],
            [SimpleNamespace(rfilename="x", size=publish.MAX_FILE_BYTES + 1)],
            [SimpleNamespace(rfilename="x", size=1), SimpleNamespace(rfilename="x", size=1)],
        ):
            info = SimpleNamespace(id=publish.TARGET, private=False, gated=False,
                                   sha=PARENT, siblings=siblings)
            api = SimpleNamespace(repo_info=lambda **kwargs: info)
            with self.subTest(siblings=siblings):
                with self.assertRaises(publish.PublishError):
                    publish.remote_state(api, PARENT)

    def test_snapshot_rejects_symlinks_and_protected_path(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / "README.md").write_bytes(b"card")
            (folder / "link").symlink_to(folder / "README.md")
            with self.assertRaisesRegex(publish.PublishError, "symlink"):
                publish.snapshot(folder)
            (folder / "link").unlink()
            (folder / ".gitattributes").write_bytes(b"override")
            with self.assertRaisesRegex(publish.PublishError, "preserved"):
                publish.snapshot(folder)

    def test_exact_existing_stager_projection_is_required(self):
        root = publish.ROOT
        (root / "dist").mkdir(exist_ok=True)
        source = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
        with tempfile.TemporaryDirectory(prefix="publisher-test-", dir=root / "dist") as temporary:
            folder = Path(temporary) / "payload"
            with patch.object(prepare, "OUT_DIR", folder):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(prepare.main(), 0)
            original = (folder / "README.md").read_bytes()
            expected = publish.canonical_payload(folder, source)
            self.assertEqual(expected["README.md"], original)
            hygiene = json.loads(expected["a11oy-metadata.json"])["publishHygiene"]
            self.assertIs(hygiene["deleteStaleRemoteFiles"], False)
            self.assertEqual(set(hygiene["preserveRemoteFiles"]), publish.PRESERVE)
            (folder / "README.md").write_bytes(original + b"\nnot canonical\n")
            with self.assertRaisesRegex(publish.PublishError, "canonical stager"):
                publish.canonical_payload(folder, source)
            (folder / "README.md").write_bytes(original)
            (folder / "extra.txt").write_bytes(b"unowned payload")
            with self.assertRaisesRegex(publish.PublishError, "canonical stager"):
                publish.canonical_payload(folder, source)

    def test_cli_rejects_other_target_type_and_missing_parent(self):
        for args in (["--repo-id", "another/model"], ["--repo-type", "space"], []):
            with self.subTest(args=args):
                with patch.object(sys, "argv", ["publisher", *args]):
                    with contextlib.redirect_stderr(io.StringIO()):
                        with self.assertRaises(SystemExit) as error:
                            publish.main()
                        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
