#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Small offline fixtures exercise artifact admission failures, never a build."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/create_canonical_web_artifact.py"
SPEC = importlib.util.spec_from_file_location("canonical_web_artifact", SCRIPT)
admission = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(admission)
SOURCE = "a" * 40
PLATFORM = "b" * 40
INDEX = ('<script type="module" src="/a11oy/assets/main.js"></script>'
         '<link rel="stylesheet" href="/a11oy/assets/main.css">')


class ArtifactAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = tempfile.TemporaryDirectory(prefix="szl-canonical-web-fixture-")
        self.addCleanup(self.fixture.cleanup)
        self.root = Path(self.fixture.name)
        self.source = self.root / "vendor/platform/artifacts/a11oy/dist/public"
        self.source.mkdir(parents=True)
        (self.source / "assets").mkdir()
        (self.source / "index.html").write_text(INDEX, encoding="utf-8")
        (self.source / "assets/main.js").write_bytes(b"console.log('fixture');")
        (self.source / "assets/main.css").write_bytes(b"body{color:black}")
        (self.source / "assets/main.js.map").write_bytes(b'{"sources":["private-source"]}')
        self.output = self.root / "review-bundle"
        self.identity = {"revision": SOURCE, "platform_revision": PLATFORM,
                         "platform_gitlink": PLATFORM, "package": "@workspace/a11oy"}

    def stage(self, reader=None):
        return admission.stage_artifact(self.root, self.output, SOURCE,
                                        reader or (lambda root, sha: self.identity.copy()))

    def rejected(self, code):
        with self.assertRaisesRegex(admission.AdmissionError, code):
            self.stage()
        self.assertFalse((self.output / "manifest.json").exists())

    def test_exact_bytes_hashes_and_hidden_maps_excluded(self):
        manifest = self.stage()
        self.assertEqual(manifest["deployment"], "BLOCKED")
        self.assertEqual(manifest["runtime_api_binding"], "UNAVAILABLE")
        self.assertFalse(manifest["provider_writes"])
        self.assertEqual(manifest["excluded_source_maps"], ["assets/main.js.map"])
        self.assertFalse((self.output / "public/assets/main.js.map").exists())
        self.assertEqual(len(manifest["files"]), 3)
        for record in manifest["files"]:
            content = (self.output / "public" / record["path"]).read_bytes()
            self.assertEqual(content, (self.source / record["path"]).read_bytes())
            self.assertEqual(record["size"], len(content))
            self.assertEqual(record["sha256"], hashlib.sha256(content).hexdigest())
        self.assertEqual(json.loads((self.output / "manifest.json").read_text()), manifest)

    def test_existing_output_is_preserved(self):
        self.output.mkdir()
        sentinel = self.output / "sentinel"
        sentinel.write_bytes(b"keep")
        self.rejected("OUTPUT_ALREADY_EXISTS")
        self.assertEqual(sentinel.read_bytes(), b"keep")

    def test_output_cannot_overlap_source(self):
        self.output = self.source / "new"
        self.rejected("OUTPUT_SOURCE_OVERLAP")

    def test_unsafe_portable_names(self):
        for value in ("../x", "/x", "a\\x", "a//x", "a/../x", "a/CON.txt", "a/file.", "a/%2e"):
            with self.subTest(value=value), self.assertRaises(admission.AdmissionError):
                admission.safe_name(value)

    def test_external_wrong_base_traversal_and_missing_index_references(self):
        for reference in ("https://other.test/main.js", "//other.test/main.js",
                          "/assets/main.js", "/a11oy/assets/%2e%2e/main.js",
                          "/a11oy/assets/missing.js", "/a11oy/assets/main.js.map"):
            with self.subTest(reference=reference):
                (self.source / "index.html").write_text(
                    f'<script src="{reference}"></script>', encoding="utf-8")
                self.rejected("INDEX_|UNSAFE_PATH")
                self.assertFalse(self.output.exists())

    def test_missing_index(self):
        (self.source / "index.html").unlink()
        self.rejected("INDEX_MISSING")

    def test_sensitive_and_executable_exports_are_rejected_before_copy(self):
        for name in ("private.pem", "credentials.key", "server.P12", "native.bin",
                     "program.exe", "library.dll", "helper.py", "run.ps1", "archive.zip"):
            with self.subTest(name=name):
                candidate = self.source / name
                candidate.write_bytes(b"private fixture")
                try:
                    self.rejected("NON_STATIC_EXPORT_REJECTED")
                    self.assertFalse(self.output.exists())
                finally:
                    candidate.unlink()

    def test_static_images_fonts_wasm_and_manifest_remain_admissible(self):
        for name in ("photo.webp", "icon.svg", "font.woff2", "module.wasm", "site.webmanifest"):
            (self.source / name).write_bytes(b"static fixture")
        manifest = self.stage()
        self.assertEqual(len(manifest["files"]), 8)
        self.assertEqual(manifest["embedded_content_security"], "NOT_EVALUATED")

    def test_duplicate_browser_attributes_fail_closed(self):
        (self.source / "index.html").write_text(
            '<script src="https://other.test/x.js" src="/a11oy/assets/main.js"></script>',
            encoding="utf-8")
        self.rejected("INDEX_REFERENCE_INVALID")

    def test_special_file_mode_is_rejected_before_read(self):
        original = Path.lstat
        target = self.source / "assets/main.js"
        def special(path, *args, **kwargs):
            if path == target:
                return SimpleNamespace(st_mode=stat.S_IFIFO, st_nlink=1)
            return original(path, *args, **kwargs)
        with patch.object(Path, "lstat", special):
            self.rejected("FILE_NOT_SINGLE_REGULAR_FILE")

    def test_hardlinked_file_is_rejected_even_if_a_source_map(self):
        os.link(self.source / "assets/main.js.map", self.root / "map-link")
        self.rejected("FILE_NOT_SINGLE_REGULAR_FILE")

    def test_symbolic_link_is_rejected(self):
        try:
            (self.source / "assets/link.js").symlink_to(self.source / "assets/main.js")
        except OSError as error:
            self.skipTest(f"host cannot create symlinks: {error.__class__.__name__}")
        self.rejected("FILE_NOT_SINGLE_REGULAR_FILE")

    def test_file_count_size_and_total_bounds(self):
        for setting, limit in (("MAX_FILES", 2), ("MAX_FILE_BYTES", 1), ("MAX_TOTAL_BYTES", 1)):
            with self.subTest(setting=setting), patch.object(admission, setting, limit):
                self.rejected("OUTPUT_LIMIT_EXCEEDED")

    def test_identity_mismatch_is_rejected_before_staging(self):
        with self.assertRaisesRegex(admission.AdmissionError, "SOURCE_REVISION_MISMATCH"):
            self.stage(lambda root, sha: {"revision": "c" * 40})
        self.assertFalse(self.output.exists())

    def test_identity_change_during_staging_has_no_manifest(self):
        identities = iter((self.identity, {**self.identity, "revision": "c" * 40}))
        with self.assertRaisesRegex(admission.AdmissionError, "SOURCE_CHANGED"):
            self.stage(lambda root, sha: next(identities))
        self.assertFalse((self.output / "manifest.json").exists())

    def test_source_change_during_copy_has_no_manifest(self):
        original = admission.checked_bytes
        calls = 0

        def changed(path, expected):
            nonlocal calls
            calls += 1
            if calls == 2:
                path.write_bytes(b"changed")
            return original(path, expected)

        with patch.object(admission, "checked_bytes", changed):
            self.rejected("SOURCE_CHANGED")

    def test_new_source_file_during_copy_has_no_manifest(self):
        original = admission.checked_bytes
        def introduced(path, expected):
            payload = original(path, expected)
            if "public" in path.parts and self.output in path.parents:
                (self.source / "new.txt").write_bytes(b"new")
            return payload
        with patch.object(admission, "checked_bytes", introduced):
            self.rejected("SOURCE_CHANGED")

    def test_staged_copy_readback_corruption_has_no_manifest(self):
        original = admission.checked_bytes
        def corrupted(path, expected):
            payload = original(path, expected)
            return b"corrupt" if self.output in path.parents else payload
        with patch.object(admission, "checked_bytes", corrupted):
            self.rejected("STAGED_BYTES_MISMATCH")


class IdentityAdmissionTests(unittest.TestCase):
    def fake_git(self, root, *arguments):
        responses = {
            ("rev-parse", "HEAD"): PLATFORM if root.as_posix().endswith("vendor/platform") else SOURCE,
            ("diff", "--quiet", "HEAD", "--"): "",
            ("ls-tree", "HEAD", "--", "vendor/platform"): f"160000 commit {PLATFORM}\tvendor/platform",
            ("config", "-f", ".gitmodules", "--get", "submodule.vendor/platform.url"):
                "https://github.com/szl-holdings/platform.git",
            ("show", f"{PLATFORM}:package.json"): '{"packageManager":"pnpm@10.26.1"}',
            ("show", f"{PLATFORM}:artifacts/a11oy/package.json"): '{"name":"@workspace/a11oy"}',
        }
        return responses[arguments]

    def test_exact_gitlink_package_and_toolchain_identity(self):
        with patch.object(admission, "git", self.fake_git), patch.object(
                admission, "command", side_effect=("v24.1.0", "10.26.1")):
            identity = admission.collect_identity(Path("fixture"), SOURCE)
        self.assertEqual(identity["platform_revision"], PLATFORM)
        self.assertEqual(identity["platform_gitlink"], PLATFORM)

    def test_wrong_expected_source(self):
        with patch.object(admission, "git", self.fake_git):
            with self.assertRaisesRegex(admission.AdmissionError, "SOURCE_REVISION_MISMATCH"):
                admission.collect_identity(Path("fixture"), "c" * 40)

    def test_missing_expected_source(self):
        with self.assertRaisesRegex(admission.AdmissionError, "EXPECTED_SOURCE_REQUIRED"):
            admission.collect_identity(Path("fixture"), None)

    def test_unmatched_gitlink(self):
        def wrong(root, *args):
            return "160000 commit " + "c" * 40 + "\tvendor/platform" if args[0] == "ls-tree" else self.fake_git(root, *args)
        with patch.object(admission, "git", wrong):
            with self.assertRaisesRegex(admission.AdmissionError, "PLATFORM_GITLINK_MISMATCH"):
                admission.collect_identity(Path("fixture"), SOURCE)

    def test_wrong_source_url(self):
        def wrong(root, *args):
            return "https://other.test/platform.git" if args[0] == "config" else self.fake_git(root, *args)
        with patch.object(admission, "git", wrong):
            with self.assertRaisesRegex(admission.AdmissionError, "PLATFORM_SOURCE_MISMATCH"):
                admission.collect_identity(Path("fixture"), SOURCE)

    def test_wrong_package_metadata(self):
        for field in ("package.json", "artifacts/a11oy/package.json"):
            def wrong(root, *args):
                return '{}' if args == ("show", f"{PLATFORM}:{field}") else self.fake_git(root, *args)
            with self.subTest(field=field), patch.object(admission, "git", wrong), patch.object(
                    admission, "command", side_effect=("v24.1.0", "10.26.1")):
                with self.assertRaisesRegex(admission.AdmissionError, "TOOLCHAIN_OR_PACKAGE_MISMATCH"):
                    admission.collect_identity(Path("fixture"), SOURCE)

    def test_wrong_node_or_pnpm(self):
        for values in (("v22.0.0", "10.26.1"), ("v24.1.0", "10.33.3")):
            with self.subTest(values=values), patch.object(admission, "git", self.fake_git), patch.object(
                    admission, "command", side_effect=values):
                with self.assertRaisesRegex(admission.AdmissionError, "TOOLCHAIN_OR_PACKAGE_MISMATCH"):
                    admission.collect_identity(Path("fixture"), SOURCE)

    def test_dirty_tracked_source_fails(self):
        def dirty(root, *args):
            if args[0] == "diff":
                raise subprocess.CalledProcessError(1, ["git", "diff"])
            return self.fake_git(root, *args)
        with patch.object(admission, "git", dirty):
            with self.assertRaises(subprocess.CalledProcessError):
                admission.collect_identity(Path("fixture"), SOURCE)


if __name__ == "__main__":
    unittest.main()
