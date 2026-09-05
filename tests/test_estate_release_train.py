from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "verify_estate_release_train.py"
SPEC = importlib.util.spec_from_file_location("estate_release_train", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class EstateReleaseTrainTests(unittest.TestCase):
    def test_extracts_only_recognized_exact_source_revisions(self) -> None:
        sha = "a" * 40
        cases = [
            ({"source_revision": sha}, (sha, "source_revision")),
            ({"build": {"revision": sha}}, (sha, "build.revision")),
            ({"source": {"source_sha": sha}}, (sha, "source.source_sha")),
            ({"git": {"git_sha": sha}}, (sha, "git.git_sha")),
            ({"revision": "short"}, (None, None)),
            ({"sha256": "b" * 64}, (None, None)),
            ({"nested": {"revision": sha}}, (None, None)),
        ]
        for payload, expected in cases:
            with self.subTest(payload=payload):
                self.assertEqual(release.extract_source_revision(payload), expected)

    def test_semantic_html_ignores_body_copy_but_tracks_product_contract(self) -> None:
        first = release.SemanticHTML()
        first.feed(
            '<html data-szl-public-experience-v3="true"><head>'
            '<title>A11oy</title><link rel="stylesheet" href="/a.css">'
            '<script src="/a.js"></script></head><body>'
            '<a href="/products/?x=1">Products</a><p>old copy</p></body></html>'
        )
        second = release.SemanticHTML()
        second.feed(
            '<html data-szl-public-experience-v3="true"><head>'
            '<title>A11oy</title><link rel="stylesheet" href="/a.css">'
            '<script src="/a.js"></script></head><body>'
            '<a href="/products/?x=2">Products</a><p>new copy</p></body></html>'
        )
        self.assertEqual(
            first.result()["semantic_sha256"],
            second.result()["semantic_sha256"],
        )

        changed = release.SemanticHTML()
        changed.feed(
            '<html data-szl-public-experience-v4="true"><head>'
            '<title>A11oy</title><link rel="stylesheet" href="/b.css">'
            '</head><body><a href="/products/">Products</a></body></html>'
        )
        self.assertNotEqual(
            first.result()["semantic_sha256"],
            changed.result()["semantic_sha256"],
        )

    def test_inspect_component_requires_source_running_root_and_exact_witness(self) -> None:
        sha = "c" * 40
        component = {
            "key": "example",
            "source_repository": "szl-holdings/example",
            "hf_repo_id": "SZLHOLDINGS/example",
            "origin": "https://szlholdings-example.hf.space",
            "required": True,
        }
        with (
            mock.patch.object(
                release,
                "github_main",
                return_value={"observed": True, "sha": sha},
            ),
            mock.patch.object(
                release,
                "hf_space",
                return_value={"observed": True, "stage": "RUNNING"},
            ),
            mock.patch.object(
                release,
                "probe_source",
                return_value={"observed": True, "revision": sha},
            ),
            mock.patch.object(
                release,
                "fetch",
                return_value={"status": 200, "sha256": "d" * 64, "bytes": 100},
            ),
        ):
            result = release.inspect_component(component, ("/api/build-info",))
        self.assertTrue(result["aligned"])
        self.assertEqual(result["blockers"], [])

        with (
            mock.patch.object(
                release,
                "github_main",
                return_value={"observed": True, "sha": sha},
            ),
            mock.patch.object(
                release,
                "hf_space",
                return_value={"observed": True, "stage": "RUNNING"},
            ),
            mock.patch.object(
                release,
                "probe_source",
                return_value={"observed": True, "revision": "e" * 40},
            ),
            mock.patch.object(
                release,
                "fetch",
                return_value={"status": 200, "sha256": "d" * 64, "bytes": 100},
            ),
        ):
            result = release.inspect_component(component, ("/api/build-info",))
        self.assertFalse(result["aligned"])
        self.assertIn("SOURCE_REVISION_MISMATCH", result["blockers"])

    def test_profile_contract_requires_three_way_count_equality(self) -> None:
        sha = "f" * 40
        config = {
            "profile": {
                "repository": "szl-holdings/.github",
                "path": "profile/README.md",
            }
        }
        profile = {
            "text": "Artifacts: 15 public Spaces, 44 models, 33 datasets"
        }
        manifest = {"json": {"counts": {"spaces": 15, "models": 44, "datasets": 33}}}
        with (
            mock.patch.object(
                release,
                "github_main",
                return_value={"observed": True, "sha": sha},
            ),
            mock.patch.object(
                release,
                "github_file",
                side_effect=[profile, manifest],
            ),
        ):
            result = release.profile_inventory_contract(
                config,
                {"counts": {"spaces": 15, "models": 44, "datasets": 33}},
                sha,
            )
        self.assertTrue(result["aligned"])

    def test_release_id_is_deterministic_and_authority_is_fail_closed(self) -> None:
        config = json.loads(
            (ROOT / "config" / "estate-release-train.v1.json").read_text(
                encoding="utf-8"
            )
        )
        authority = config["authority"]
        self.assertEqual(authority["provider_writes"], "CANONICAL_WORKFLOWS_ONLY")
        self.assertEqual(authority["external_effectors"], [])
        self.assertIs(authority["production_authorization"], False)
        self.assertIs(authority["human_approval_required"], True)
        vector = {"a": "1" * 40, "b": "2" * 40}
        self.assertEqual(
            release.canonical_sha256(vector), release.canonical_sha256(vector)
        )

    def test_config_rejects_wrong_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps({"schema": "wrong"}), encoding="utf-8")
            with self.assertRaisesRegex(release.AlignmentError, "schema"):
                release.load_config(path)


if __name__ == "__main__":
    unittest.main()
