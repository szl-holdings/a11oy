"""Exercise the sync CLI against real immutable Git objects, without network calls.

The Bash wrapper delegates to this exact embedded Python program. Running that
program directly makes these stdlib-only contract tests portable to Windows.
"""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
WRAPPER = (ROOT / "scripts/sync_from_monorepo.sh").read_text(encoding="utf-8")
PROGRAM = WRAPPER.split("<<'PY'\n", 1)[1].rsplit("\nPY", 1)[0]


class VendorSyncContract(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="szl-vendor-contract-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.platform = self.root / "platform"
        self.platform.mkdir()
        self.consumer = self.root / "consumer"
        self.consumer.mkdir()
        self.git("init", "--quiet")
        self.git("config", "core.autocrlf", "false")
        self.git("config", "user.name", "Vendor fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        (self.platform / "core.py").write_bytes(b"print('old')\n")
        (self.platform / "other.py").write_bytes(b"print('unrelated')\n")
        self.first = self.commit()
        (self.platform / "core.py").write_bytes(b"#!/usr/bin/env python3\nprint('new')\n")
        (self.platform / "other.py").write_bytes(b"print('unwanted rollforward')\n")
        self.second = self.commit()
        # Neither current HEAD nor dirty working-tree bytes are the source contract.
        (self.platform / "core.py").write_bytes(b"uncommitted bytes must never be vendored\n")
        self.manifest = {
            "monorepo": "szl-holdings/platform", "pin": self.first,
            "files": {
                "core.py": {"source": "core.py", "header": True, "revision": self.second},
                "other.py": {"source": "other.py", "header": True},
            },
        }
        self.save()

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.platform), *args], check=True,
            capture_output=True, timeout=30).stdout.decode().strip()

    def commit(self):
        self.git("add", ".")
        self.git("-c", "commit.gpgsign=false", "commit", "--quiet", "-m", "fixture")
        return self.git("rev-parse", "HEAD")

    def save(self):
        (self.consumer / "vendor.manifest.json").write_text(
            json.dumps(self.manifest), encoding="utf-8")

    def cli(self, *args, expected=0):
        env = dict(os.environ, PLATFORM_DIR=str(self.platform), PYTHONIOENCODING="utf-8")
        result = subprocess.run(
            [sys.executable, "-c", PROGRAM, *args], cwd=self.consumer, env=env,
            capture_output=True, text=True, encoding="utf-8", timeout=60)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_per_entry_and_default_pins_use_commit_bytes_and_canonical_headers(self):
        self.cli("sync")
        core = (self.consumer / "core.py").read_text(encoding="utf-8")
        other = (self.consumer / "other.py").read_text(encoding="utf-8")
        self.assertTrue(core.startswith("#!/usr/bin/env python3\n# VENDORED FROM "))
        self.assertIn("@" + self.second + " — core.py", core)
        self.assertTrue(core.endswith("print('new')\n"))
        self.assertIn("@" + self.first + " — other.py", other)
        self.assertTrue(other.endswith("print('unrelated')\n"))
        self.cli("check", "--strict-headers")

    def test_target_sync_preserves_unrelated_bytes_and_manifest(self):
        other = self.consumer / "other.py"
        other.write_bytes(b"preserve this entry exactly\n")
        before = (self.consumer / "vendor.manifest.json").read_bytes()
        self.cli("sync", "--only", "core.py")
        self.assertEqual(other.read_bytes(), b"preserve this entry exactly\n")
        self.assertEqual((self.consumer / "vendor.manifest.json").read_bytes(), before)
        self.cli("check", "--strict-headers", expected=1)

    def test_repeated_selectors_sync_all_selected_entries(self):
        self.cli("sync", "--only", "core.py", "--only", "other.py", "--only", "core.py")
        self.cli("check", "--strict-headers")

    def test_check_cannot_be_narrowed_and_unknown_arguments_fail(self):
        self.cli("check", "--only", "core.py", expected=2)
        self.cli("sync", "--only", "missing.py", expected=2)
        self.cli("sync", "--skip-validation", expected=2)
        self.cli("check", "main", expected=2)
        self.assertFalse((self.consumer / "core.py").exists())

    def test_invalid_unselected_revision_is_rejected_before_any_write(self):
        for revision in ("main", "a" * 39, "A" * 40, None, 123):
            with self.subTest(revision=revision):
                self.manifest["files"]["other.py"]["revision"] = revision
                self.save()
                self.cli("sync", "--only", "core.py", expected=2)
                self.assertFalse((self.consumer / "core.py").exists())

    def test_default_pin_must_remain_immutable_with_overrides(self):
        self.manifest["pin"] = "main"
        self.save()
        self.cli("sync", "--only", "core.py", expected=2)
        self.assertFalse((self.consumer / "core.py").exists())

    def test_missing_commit_never_falls_back_to_worktree_or_network(self):
        self.manifest["files"]["core.py"]["revision"] = "0" * 40
        self.save()
        self.cli("sync", "--only", "core.py", expected=1)
        self.assertFalse((self.consumer / "core.py").exists())

    def test_missing_blob_never_falls_back_to_worktree(self):
        (self.platform / "untracked.py").write_bytes(b"working tree only\n")
        self.manifest["files"]["core.py"]["source"] = "untracked.py"
        self.save()
        self.cli("sync", "--only", "core.py", expected=1)
        self.assertFalse((self.consumer / "core.py").exists())

    def test_replacement_refs_cannot_substitute_declared_commit_bytes(self):
        self.git("replace", self.second, self.first)
        self.assertEqual(self.git("show", self.second + ":core.py"), "print('old')")
        self.cli("sync", "--only", "core.py")
        core = (self.consumer / "core.py").read_text(encoding="utf-8")
        self.assertIn("@" + self.second + " — core.py", core)
        self.assertTrue(core.endswith("print('new')\n"))
        self.assertNotIn("print('old')", core)

    def test_partial_clone_missing_blob_never_triggers_lazy_fetch(self):
        self.git("config", "uploadpack.allowFilter", "true")
        filtered = self.root / "filtered-platform"
        clone = subprocess.run(
            ["git", "clone", "--quiet", "--filter=blob:none", "--no-checkout", "--no-local",
             str(self.platform), str(filtered)], capture_output=True, text=True, timeout=30)
        self.assertEqual(clone.returncode, 0, clone.stderr)
        self.assertNotIn("filtering not recognized", clone.stderr)
        self.platform = filtered

        def blob_is_local():
            return subprocess.run(
                ["git", "--no-replace-objects", "-C", str(filtered), "cat-file", "-e",
                 self.second + ":core.py"], capture_output=True, timeout=30,
                env=dict(os.environ, GIT_NO_LAZY_FETCH="1")).returncode == 0

        self.assertFalse(blob_is_local())
        # The remote fixture is available and could supply the blob. The local
        # immutable lookup must refuse instead of silently contacting that remote.
        self.cli("sync", "--only", "core.py", expected=1)
        self.assertFalse(blob_is_local())
        self.assertFalse((self.consumer / "core.py").exists())

    def test_invalid_paths_and_header_type_fail_before_writes(self):
        for field, value in (("source", "../core.py"), ("source", "/core.py"),
                             ("source", "C:\\core.py"), ("header", "true")):
            with self.subTest(field=field, value=value):
                original = dict(self.manifest["files"]["other.py"])
                self.manifest["files"]["other.py"][field] = value
                self.save()
                self.cli("sync", "--only", "core.py", expected=2)
                self.assertFalse((self.consumer / "core.py").exists())
                self.manifest["files"]["other.py"] = original

    def test_strict_headers_still_reject_missing_and_malformed_headers(self):
        self.cli("sync")
        core = self.consumer / "core.py"
        core.write_bytes(b"#!/usr/bin/env python3\nprint('new')\n")
        self.cli("check")
        self.cli("check", "--strict-headers", expected=1)
        self.cli("sync", "--only", "core.py")
        core.write_bytes(core.read_bytes().replace(b"DO NOT EDIT HERE.", b"DO EDIT HERE."))
        self.cli("check", expected=1)


if __name__ == "__main__":
    unittest.main()
