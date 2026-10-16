# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Presentation invariants on the actual deterministic publication bundle."""

import ast
import copy
import hashlib
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class NativePresentationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = Path(cls.temp.name)
        load(HERE / "build_publication.py", "native_builder").build(
            cls.output, "a" * 40, "2026-10-13T00:00:00Z")
        cls.space = cls.output / "space"
        cls.native = load(cls.space / "native_presentation.py", "bench_native")
        cls.leaderboard = json.loads((cls.space / "leaderboard.json").read_text())
        cls.publication = json.loads((cls.space / "publication.json").read_text())
        cls.result = json.loads((cls.space / "results/reference-conformance.json").read_text())

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_installed_assets_are_exact_closed_subset(self):
        projection = json.loads((self.space / "szl/PROJECTION.json").read_text())
        self.assertEqual({Path(x["installed_path"]).name for x in projection["assets"]},
                         set(self.native.ASSETS))
        manifest = json.loads((self.space / "publication-manifest.json").read_text())
        self.assertEqual(len(manifest["files"]), 14)
        indexed = {row["path"]: row for row in manifest["files"]}
        for row in projection["assets"]:
            data = (self.space / row["installed_path"]).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), row["sha256"])
            self.assertEqual(indexed[row["installed_path"]]["sha256"], row["sha256"])
        self.assertIn("--action-press-bg", self.native.css())
        self.assertIn("data:image/svg+xml;base64,", self.native.head())
        self.assertIn('<style id="bench-native-style">' + self.native.css() + "</style>", self.native.head())

    def test_presentation_preserves_exact_original_evidence_and_inputs(self):
        before = copy.deepcopy((self.leaderboard, self.publication, self.result))
        rendered = self.native.render(*before)
        self.assertEqual(before, (self.leaderboard, self.publication, self.result))
        for value in ("SAMPLE", "COMPUTED", "STRUCTURE_ONLY", "false",
                      "REFERENCE_ONLY_NO_MODEL_SUBMISSIONS", "SAMPLE_REFERENCE_NOT_MODEL"):
            self.assertIn(value, rendered)
        self.assertIn('<p class="gb-count">0</p>', rendered)
        self.assertIn("not a model ranking", rendered)
        self.assertEqual(rendered.count('class="gb-axis-index"'), 5)
        self.assertIn(self.native._json(self.result), rendered)
        self.assertIn(self.native._json(self.leaderboard), rendered)
        self.assertIn(self.native._json(self.publication), rendered)

    def test_committed_strings_remain_inert_and_links_are_fixed(self):
        leaderboard = copy.deepcopy(self.leaderboard)
        leaderboard["reference_rows"][0]["display_name"] = '<img src=x onerror=alert(1)>'
        leaderboard["submission_rule"] = '</p><script>window.bad=true</script>'
        rendered = self.native.render(leaderboard, self.publication, self.result)
        self.assertNotIn("<script", rendered)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", rendered)
        self.assertIn("&lt;/p&gt;&lt;script&gt;", rendered)
        publication = copy.deepcopy(self.publication)
        publication["source_revision"] = '" onclick="alert(1)'
        with self.assertRaises(ValueError):
            self.native.render(leaderboard, publication, self.result)
        publication["source_revision"] = "b" * 40
        publication["dataset_revision"] = '" onclick="alert(1)'
        rendered = self.native.render(leaderboard, publication, self.result)
        self.assertNotIn('onclick="alert', rendered)
        self.assertIn('href="https://huggingface.co/datasets/SZLHOLDINGS/governed-agent-bench"', rendered)

    def test_reader_rejects_unknown_tampered_and_symlink_assets(self):
        with self.assertRaises(ValueError):
            self.native._file("../app.py", True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "szl").mkdir()
            (root / "szl/szl-tokens.css").write_text("tampered")
            with patch.object(self.native, "ROOT", root):
                with self.assertRaises(ValueError):
                    self.native._file("szl-tokens.css", True)
            (root / "szl/szl-tokens.css").unlink()
            (root / "szl/szl-tokens.css").symlink_to(self.space / "szl/szl-tokens.css")
            with patch.object(self.native, "ROOT", root):
                with self.assertRaises(OSError):
                    self.native._file("szl-tokens.css", True)
            (root / "bench.css").write_bytes(b"x" * 262145)
            with patch.object(self.native, "ROOT", root):
                with self.assertRaises(ValueError):
                    self.native._file("bench.css")

    def test_app_has_no_callbacks_timers_or_remote_component_data(self):
        source = (self.space / "app.py").read_text()
        tree = ast.parse(source)
        attrs = [x.func.attr for x in ast.walk(tree)
                 if isinstance(x, ast.Call) and isinstance(x.func, ast.Attribute)]
        self.assertFalse(set(attrs) & {"click", "load", "change", "submit", "Timer"})
        self.assertIn("js_on_load=None", source)
        self.assertIn("analytics_enabled=False", source)
        self.assertNotIn("http", source)

    def test_app_exposes_one_exact_hidden_immutable_identity(self):
        json_calls = []

        class FakeBlocks:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def launch(self, **_kwargs):
                raise AssertionError("test import must not launch the Space")

        fake_gradio = types.SimpleNamespace(
            Blocks=FakeBlocks,
            HTML=lambda *_args, **_kwargs: None,
            JSON=lambda **kwargs: json_calls.append(copy.deepcopy(kwargs)),
        )
        fake_native = types.SimpleNamespace(
            head=lambda: "<meta charset='utf-8'>",
            render=lambda *_args: "<main>read-only</main>",
        )
        with (
            patch.dict(sys.modules, {
                "gradio": fake_gradio,
                "native_presentation": fake_native,
            }),
            patch.object(sys, "path", [str(self.space), *sys.path]),
        ):
            module = load(self.space / "app.py", "bench_runtime_identity_test")

        expected = {
            "source_revision": self.publication["source_revision"],
            "dataset_repository": self.publication["dataset_repository"],
            "dataset_revision": self.publication["dataset_revision"],
            "evidence_labels": self.publication["evidence_labels"],
        }
        self.assertEqual(module.IMMUTABLE_PUBLICATION_IDENTITY, expected)
        self.assertEqual(json_calls, [{
            "value": expected,
            "label": "Immutable publication identity",
            "visible": False,
        }])


if __name__ == "__main__":
    unittest.main()
