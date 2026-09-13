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
            ({"revision": "short"}, (None, "INVALID")),
            ({"sha256": "b" * 64}, (None, None)),
            ({"nested": {"revision": sha}}, (None, None)),
            (
                {"source_revision": sha, "build": {"revision": sha}},
                (sha, "source_revision"),
            ),
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

    def test_semantic_html_excludes_only_known_cloudflare_beacon(self) -> None:
        baseline = release.SemanticHTML()
        baseline.feed(
            '<html data-szl-public-experience-v3="true"><head>'
            '<title>A11oy</title><script src="/app.js"></script>'
            '</head><body><a href="/trust">Trust</a></body></html>'
        )
        beacon = (
            "https://static.cloudflareinsights.com/"
            "beacon.min.js/v31edd6df95cf4e85bb4c19e7a9bdbcba1788362987495"
        )
        apex = release.SemanticHTML()
        apex.feed(
            '<html data-szl-public-experience-v3="true"><head>'
            '<title>A11oy</title><script src="/app.js"></script>'
            f'<script src="{beacon}"></script>'
            '</head><body><a href="/trust">Trust</a></body></html>'
        )
        self.assertEqual(
            baseline.result()["semantic_sha256"],
            apex.result()["semantic_sha256"],
        )
        self.assertEqual(apex.result()["provider_scripts"], [beacon])
        self.assertEqual(baseline.result()["provider_scripts"], [])

        unknown_external = release.SemanticHTML()
        unknown_external.feed(
            '<html data-szl-public-experience-v3="true"><head>'
            '<title>A11oy</title><script src="/app.js"></script>'
            '<script src="https://example.com/beacon.min.js/v1"></script>'
            '</head><body><a href="/trust">Trust</a></body></html>'
        )
        self.assertNotEqual(
            baseline.result()["semantic_sha256"],
            unknown_external.result()["semantic_sha256"],
        )

        cloudflare_other_path = release.SemanticHTML()
        cloudflare_other_path.feed(
            '<html data-szl-public-experience-v3="true"><head>'
            '<title>A11oy</title><script src="/app.js"></script>'
            '<script src="https://static.cloudflareinsights.com/other.js"></script>'
            '</head><body><a href="/trust">Trust</a></body></html>'
        )
        self.assertNotEqual(
            baseline.result()["semantic_sha256"],
            cloudflare_other_path.result()["semantic_sha256"],
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


def _row(name: str = "a11oy", **kwargs: object) -> dict[str, object]:
    return {"id": f"SZLHOLDINGS/{name}", "sha": "1" * 40, "private": False, **kwargs}


class InventoryAndIdentityContractTests(unittest.TestCase):
    def test_object_200_is_unavailable_not_zero(self) -> None:
        result = release.hf_inventory(
            "SZLHOLDINGS",
            lambda url, **kw: {"status": 200, "json": {"items": []}, "link": None},
        )
        self.assertFalse(result["observed"])
        self.assertIsNone(result["counts"]["models"])
        self.assertEqual(result["enumeration_state"]["models"], "UNAVAILABLE")
        self.assertEqual(result["errors"]["models"], "INVALID_LIST_RESPONSE")

    def test_empty_list_is_observed_zero(self) -> None:
        result = release.hf_inventory(
            "SZLHOLDINGS",
            lambda url, **kw: {"status": 200, "json": [], "link": None},
        )
        self.assertTrue(result["observed"])
        self.assertEqual(result["counts"]["models"], 0)
        self.assertEqual(result["enumeration_state"]["spaces"], "COMPLETE")

    def test_pagination_completes_two_pages(self) -> None:
        def getter(url: str, **kw: object) -> dict[str, object]:
            if "cursor=" in url:
                return {"status": 200, "json": [_row("last")], "link": None}
            next_url = url + "&cursor=page2"
            return {
                "status": 200,
                "json": [_row("first")],
                "link": f'<{next_url}>; rel="next"',
            }

        result = release.hf_inventory("SZLHOLDINGS", getter)
        self.assertTrue(result["observed"])
        self.assertEqual(result["counts"]["models"], 2)
        self.assertEqual(len(result["page_evidence"]["models"]), 2)

    def test_duplicate_id_and_wrong_namespace_unavailable(self) -> None:
        dup = release.hf_inventory(
            "SZLHOLDINGS",
            lambda url, **kw: {
                "status": 200,
                "json": [_row(), _row()],
                "link": None,
            },
        )
        self.assertFalse(dup["observed"])
        self.assertEqual(dup["errors"]["models"], "DUPLICATE_ID")
        foreign = release.hf_inventory(
            "SZLHOLDINGS",
            lambda url, **kw: {
                "status": 200,
                "json": [_row(id="other/model")],
                "link": None,
            },
        )
        self.assertEqual(foreign["errors"]["models"], "FOREIGN_OR_MALFORMED_ID")

    def test_authorization_failure_is_not_zero(self) -> None:
        result = release.hf_inventory(
            "SZLHOLDINGS",
            lambda url, **kw: {"status": 401, "json": [], "link": None},
        )
        self.assertIsNone(result["counts"]["spaces"])
        self.assertEqual(result["errors"]["spaces"], "HTTP_UNAVAILABLE")

    def test_page_budget_is_partial_not_complete(self) -> None:
        def getter(url: str, **kw: object) -> dict[str, object]:
            counters["n"] += 1
            kind = "models"
            if "/datasets" in url:
                kind = "datasets"
            elif "/spaces" in url:
                kind = "spaces"
            next_url = (
                f"https://huggingface.co/api/{kind}"
                f"?author=SZLHOLDINGS&limit=100&full=true&cursor=p{counters['n']}"
            )
            return {
                "status": 200,
                "json": [_row(f"{kind}-{counters['n']}")],
                "link": f'<{next_url}>; rel="next"',
            }

        counters = {"n": 0}

        original = release.MAX_INVENTORY_PAGES
        release.MAX_INVENTORY_PAGES = 2
        try:
            result = release.hf_inventory("SZLHOLDINGS", getter)
        finally:
            release.MAX_INVENTORY_PAGES = original
        self.assertFalse(result["observed"])
        self.assertEqual(result["enumeration_state"]["models"], "PARTIAL")
        self.assertIsNone(result["counts"]["models"])

    def test_conflicting_aliases_fail_closed(self) -> None:
        value, state = release.extract_source_revision(
            {
                "source_revision": "a" * 40,
                "build": {"revision": "b" * 40},
            }
        )
        self.assertIsNone(value)
        self.assertEqual(state, "CONFLICT")

    def test_invalid_alias_cannot_be_masked_by_valid_alias(self) -> None:
        value, state = release.extract_source_revision(
            {"source_revision": "main", "build": {"revision": "a" * 40}}
        )
        self.assertIsNone(value)
        self.assertEqual(state, "INVALID")

    def test_probe_source_rejects_endpoint_disagreement(self) -> None:
        sha_a = "a" * 40
        sha_b = "b" * 40
        responses = {
            "https://example.invalid/api/build-info": {
                "status": 200,
                "json": {"source_revision": sha_a},
                "sha256": "1",
                "redirect": None,
            },
            "https://example.invalid/.well-known/szl-source.json": {
                "status": 200,
                "json": {"source_revision": sha_b},
                "sha256": "2",
                "redirect": None,
            },
        }

        def fake_fetch(url: str, **kw: object) -> dict[str, object]:
            return responses[url]

        with mock.patch.object(release, "fetch", side_effect=fake_fetch):
            result = release.probe_source(
                "https://example.invalid",
                ("/api/build-info", "/.well-known/szl-source.json"),
            )
        self.assertFalse(result["observed"])
        self.assertEqual(result["identity_state"], "ENDPOINT_DISAGREEMENT")
        self.assertEqual(len(result["observations"]), 2)

    def test_proof_does_not_treat_health_sha_as_pages_deployment(self) -> None:
        sha = "c" * 40
        config = {
            "proof": {
                "repository": "szl-holdings/a11oy-net",
                "origin": "https://a11oy.net",
            }
        }

        def fake_fetch(url: str, **kw: object) -> dict[str, object]:
            if url.endswith("/health.json"):
                return {
                    "status": 200,
                    "json": {"probe_contract": "STATIC_DOCUMENT", "sha": "f" * 40},
                }
            if "pages/builds/latest" in url:
                return {"status": 200, "json": {"commit": sha, "status": "built"}}
            return {"status": 200, "json": {}, "text": "<html></html>"}

        with (
            unittest.mock.patch.object(
                release,
                "github_main",
                return_value={"observed": True, "sha": sha},
            ),
            unittest.mock.patch.object(release, "fetch", side_effect=fake_fetch),
        ):
            result = release.proof_contract(config)
        self.assertTrue(result["aligned"])
        self.assertTrue(result["health_is_not_pages_deployment"])
        self.assertIsNone(result["health_revision"])
        self.assertEqual(result["pages_revision"], sha)

    def test_proof_health_conflict_is_not_pages_success_mask(self) -> None:
        sha = "c" * 40
        config = {
            "proof": {
                "repository": "szl-holdings/a11oy-net",
                "origin": "https://a11oy.net",
            }
        }

        def fake_fetch(url: str, **kw: object) -> dict[str, object]:
            if url.endswith("/health.json"):
                return {
                    "status": 200,
                    "json": {
                        "source_revision": "d" * 40,
                        "git_sha": "e" * 40,
                    },
                }
            if "pages/builds/latest" in url:
                return {"status": 200, "json": {"commit": sha, "status": "built"}}
            return {"status": 200, "json": {}}

        with (
            unittest.mock.patch.object(
                release,
                "github_main",
                return_value={"observed": True, "sha": sha},
            ),
            unittest.mock.patch.object(release, "fetch", side_effect=fake_fetch),
        ):
            result = release.proof_contract(config)
        self.assertIn("PROOF_HEALTH_DOCUMENT_CONFLICT", result["blockers"])
        self.assertTrue(result["aligned"])
        self.assertEqual(result["pages_revision"], sha)


if __name__ == "__main__":
    unittest.main()
