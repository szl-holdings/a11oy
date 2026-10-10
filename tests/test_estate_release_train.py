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

    def test_semantic_html_retains_exact_cloudflare_webmcp_as_provider_evidence(self) -> None:
        baseline = release.SemanticHTML()
        baseline.feed('<title>A11oy</title><script src="/app.js"></script>')
        bridge = "https://a-11-oy.com/.webmcp/bridge.js"
        apex = release.SemanticHTML()
        apex.feed(
            '<title>A11oy</title><script src="/app.js"></script>'
            f'<script type="module" src="{bridge}" '
            'data-packs="c2pa,mcp-server-client"></script>'
        )
        self.assertEqual(
            baseline.result()["semantic_sha256"], apex.result()["semantic_sha256"]
        )
        self.assertEqual(apex.result()["provider_scripts"], [bridge])
        self.assertEqual(apex.result()["scripts"], ["/app.js"])

    def test_semantic_html_webmcp_variants_remain_product_drift(self) -> None:
        baseline = release.SemanticHTML()
        baseline.feed('<title>A11oy</title><script src="/app.js"></script>')
        bridge = "https://a-11-oy.com/.webmcp/bridge.js"
        urls = (
            "http://a-11-oy.com/.webmcp/bridge.js",
            "https://example.com/.webmcp/bridge.js",
            "https://a-11-oy.com.evil.example/.webmcp/bridge.js",
            "https://a11oy.net/.webmcp/bridge.js",
            "https://www.a-11-oy.com/.webmcp/bridge.js",
            "https://a-11-oy.com:443/.webmcp/bridge.js",
            "https://user@a-11-oy.com/.webmcp/bridge.js",
            "https://a-11-oy.com/.webmcp/other.js",
            "https://a-11-oy.com/.webmcp/bridge.js/extra",
            "https://a-11-oy.com/.webmcp/bridge.js/",
            "/changed-product.js",
            "https://a-11-oy.com/.webmcp/bridge.js?pack=other",
            "https://a-11-oy.com/.webmcp/bridge.js#other",
            "https://a-11-oy.com/.webmcp/bridge.js?",
            "https://a-11-oy.com/.webmcp/bridge.js#",
            " https://a-11-oy.com/.webmcp/bridge.js",
            "/.webmcp/bridge.js",
        )
        tags = [
            f'<script type="module" src="{url}" '
            'data-packs="mcp-server-client"></script>'
            for url in urls
        ]
        tags.extend(
            (
                f'<script src="{bridge}" data-packs="mcp-server-client"></script>',
                f'<script type="text/javascript" src="{bridge}" '
                'data-packs="mcp-server-client"></script>',
                f'<script type="module" src="{bridge}"></script>',
                f'<script type="module" src="{bridge}" data-packs="dom"></script>',
                f'<script type="module" src="{bridge}" '
                'data-packs="mcp-server-client"></script>',
                f'<script type="module" src="{bridge}" data-packs="c2pa"></script>',
                f'<script type="module" src="{bridge}" '
                'data-packs="mcp-server-client,dom"></script>',
                f'<script type="module" src="{bridge}" '
                'data-packs="c2pa,mcp-server-client,dom"></script>',
                f'<script type="module" src="{bridge}" '
                'data-packs="mcp-server-client" onload="changed()"></script>',
                f'<script type="module" src="{bridge}" '
                'data-packs="mcp-server-client" async></script>',
                f'<script type="module" src="{bridge}" '
                'data-packs="mcp-server-client" data-packs="dom"></script>',
                f'<script type="module" src="{bridge}" src="{bridge}" '
                'data-packs="mcp-server-client"></script>',
            )
        )
        for tag in tags:
            with self.subTest(tag=tag):
                changed = release.SemanticHTML()
                changed.feed(
                    '<title>A11oy</title><script src="/app.js"></script>' + tag
                )
                self.assertNotEqual(
                    baseline.result()["semantic_sha256"],
                    changed.result()["semantic_sha256"],
                )
                self.assertEqual(changed.result()["provider_scripts"], [])

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
        config, record, manifest, blob = self._profile_fixture()
        counts = record["counts"]
        result, files = self._profile_observation(config, record, manifest, blob, counts)
        self.assertTrue(result["aligned"])
        self.assertEqual(result["declared_counts"], counts)
        self.assertEqual(
            files.call_args_list[0],
            mock.call("szl-holdings/.github", "profile/public-inventory.json", "f" * 40),
        )
        self.assertNotIn("profile/README.md", str(files.call_args_list))
        result, _ = self._profile_observation(
            config, record, manifest, blob, {**counts, "spaces": counts["spaces"] + 1}
        )
        self.assertFalse(result["aligned"])

    def _profile_fixture(self):
        config = json.loads((ROOT / "config/estate-release-train.v1.json").read_text())
        scope = config["public_inventory_scope"]
        counts = {"spaces": 23, "models": 49, "datasets": 34, "kernels": 14}
        record = {
            "schema": "szl.public-profile-inventory/v1", "counts": counts,
            "scope": scope, "scope_sha256": release.canonical_sha256(scope),
            "observed_at": "2026-09-29T21:16:06Z",
            "source_repository": "szl-holdings/a11oy",
            "source_path": "docs/huggingface-ecosystem-manifest.json",
            "source_revision": "a" * 40, "source_git_blob": "b" * 40,
            "source_sha256": "c" * 64, "production_authorization": False,
            "runtime_readiness_inferred": False, "model_quality_inferred": False,
        }
        manifest = {"status": 200, "sha256": "c" * 64, "json": {
            "schemaVersion": 2, "org": "SZLHOLDINGS", "counts": counts,
            "inventoryScope": {"visibility": "public-only", "authenticated": False,
                               "privateAssetsIncluded": False},
        }}
        blob = {"status": 200, "json": {
            "type": "file", "path": record["source_path"], "sha": "b" * 40,
        }}
        return config, record, manifest, blob

    def _profile_observation(self, config, record, manifest, blob, counts, *, text=None, pinned=None,
                             inventory=None):
        response = {"status": 200, "json": record,
                    "text": json.dumps(record) if text is None else text,
                    "sha256": "d" * 64}
        with (
            mock.patch.object(
                release, "github_main", return_value={"observed": True, "sha": "f" * 40},
            ),
            mock.patch.object(
                release, "github_file", side_effect=[response, manifest, pinned or manifest],
            ) as files,
            mock.patch.object(release, "fetch", return_value=blob),
        ):
            result = release.profile_inventory_contract(
                config, {"counts": counts, "observed": True,
                         "enumeration_state": {kind: "COMPLETE" for kind in counts}}
                        if inventory is None else inventory,
                "e" * 40,
            )
        return result, files

    def test_profile_counts_require_observed_complete_enumeration(self) -> None:
        config, record, manifest, blob = self._profile_fixture()
        counts = record["counts"]
        complete = {kind: "COMPLETE" for kind in counts}
        for inventory in (
            {"counts": counts, "observed": True},
            {"counts": counts, "observed": True, "enumeration_state":
             {**complete, "spaces": "PARTIAL"}},
            {"counts": counts, "observed": False, "enumeration_state": complete},
        ):
            with self.subTest(inventory=inventory):
                result, _ = self._profile_observation(
                    config, record, manifest, blob, counts, inventory=inventory,
                )
                self.assertFalse(result["aligned"])

    def test_profile_historical_prose_cannot_override_current_scoped_record(self) -> None:
        config, record, manifest, blob = self._profile_fixture()
        result, files = self._profile_observation(config, record, manifest, blob, record["counts"])
        self.assertTrue(result["aligned"])
        self.assertEqual(result["declared_counts"], {"spaces": 23, "models": 49, "datasets": 34, "kernels": 14})
        # README is deliberately not fetched: its historical 21/46/35 paragraph
        # cannot supply a current declaration or override the selected record.
        self.assertEqual(files.call_count, 3)

    def test_profile_missing_malformed_ambiguous_or_wrong_scope_is_blocking(self) -> None:
        config, valid, manifest, blob = self._profile_fixture()
        variants = [None, [], {**valid, "schema": "wrong"},
                    {**valid, "counts": {**valid["counts"], "spaces": True}},
                    {**valid, "scope": {**valid["scope"], "authentication": "token"}},
                    {**valid, "scope_sha256": "0" * 64},
                    {**valid, "source_revision": "short"},
                    {**valid, "production_authorization": True},
                    {**valid, "observed_at": "2026-09-29"}]
        for record in variants:
            with self.subTest(record=record):
                result, _ = self._profile_observation(config, record, manifest, blob, valid["counts"])
                self.assertFalse(result["aligned"])
                self.assertIn("HF_PROFILE_INVENTORY_RECORD_UNAVAILABLE_OR_INVALID", result["blockers"])
        for text in ("{broken", json.dumps(valid)[:-1] + ',"counts":{"spaces":0,"models":0,"datasets":0}}'):
            with self.subTest(text=text):
                result, _ = self._profile_observation(config, valid, manifest, blob, valid["counts"], text=text)
                self.assertFalse(result["aligned"])
                self.assertIsNone(result["declared_counts"])

    def test_profile_source_hash_blob_and_current_manifest_must_match(self) -> None:
        config, record, manifest, blob = self._profile_fixture()
        variants = (
            ({**manifest, "sha256": "0" * 64}, manifest, blob),
            (manifest, {**manifest, "sha256": "0" * 64}, blob),
            (manifest, manifest, {"status": 404}),
            (manifest, manifest, {**blob, "json": {**blob["json"], "sha": "0" * 40}}),
            (manifest, {**manifest, "json": {**manifest["json"],
                "inventoryScope": {"visibility": "all", "authenticated": True,
                                   "privateAssetsIncluded": True}}}, blob),
        )
        for current, pinned, metadata in variants:
            with self.subTest(current=current, pinned=pinned, metadata=metadata):
                result, _ = self._profile_observation(config, record, current, metadata, record["counts"], pinned=pinned)
                self.assertFalse(result["aligned"])
                self.assertIn("HF_PROFILE_INVENTORY_SOURCE_BINDING_MISMATCH_OR_UNAVAILABLE", result["blockers"])

    def _profile_contract_for_text(self, text, observed=None, manifest=None):
        counts = {"spaces": 23, "models": 49, "datasets": 34, "kernels": 14}
        sha = "f" * 40
        config = {"profile": {"repository": "szl-holdings/.github", "path": "profile/README.md"}}
        with (
            mock.patch.object(release, "github_main", return_value={"observed": True, "sha": sha}),
            mock.patch.object(release, "github_file", side_effect=[
                {"text": text}, {"json": {"counts": counts if manifest is None else manifest}},
            ]),
        ):
            return release.profile_inventory_contract(
                config, {"counts": counts if observed is None else observed,
                         "observed": True,
                         "enumeration_state": {kind: "COMPLETE" for kind in counts}}, sha,
            )

    def test_profile_current_prose_cannot_substitute_for_scoped_source_record(self):
        current = (
            "**Current inventory** (observed **2026-09-29T02:04:17Z**, authenticated Hub API): "
            "public **23 Spaces, 49 models, 34 datasets**; including private: "
            "29 Spaces, 49 models, 43 datasets. Repository counts only."
        )
        historical = (
            "**Historical public snapshot:** 21 public Spaces, 46 models, 35 datasets, "
            "observed **2026-09-10T03:20:41Z** under the anonymous "
            "`hf-public-author-membership/v1` predicate."
        )
        for text in (current + "\n\n" + historical, historical + "\n\n" + current):
            with self.subTest(historical_first=text.startswith(historical)):
                result = self._profile_contract_for_text(text)
                self.assertEqual(release.declared_profile_counts(text),
                                 {"spaces": 23, "models": 49, "datasets": 34})
                self.assertIsNone(result["declared_counts"])
                self.assertFalse(result["aligned"])
                self.assertIn("HF_PROFILE_INVENTORY_RECORD_UNAVAILABLE_OR_INVALID", result["blockers"])

    def test_profile_historical_snapshot_cannot_satisfy_current_count_gate(self):
        result = self._profile_contract_for_text(
            "**Historical public snapshot:** 23 public Spaces, 49 models, 34 datasets"
        )
        self.assertIsNone(result["declared_counts"])
        self.assertFalse(result["aligned"])
        self.assertIn("HF_INVENTORY_COUNT_MISMATCH_OR_UNAVAILABLE", result["blockers"])

    def test_profile_malformed_current_declaration_cannot_fall_back_to_history(self):
        result = self._profile_contract_for_text(
            "**Current inventory**: including private: 29 Spaces, 49 models, 43 datasets.\n\n"
            "**Historical public snapshot:** 23 public Spaces, 49 models, 34 datasets"
        )
        self.assertIsNone(result["declared_counts"])
        self.assertFalse(result["aligned"])

    def test_profile_conflicting_current_declarations_fail_closed(self):
        result = self._profile_contract_for_text(
            "**Current inventory**: public **23 Spaces, 49 models, 34 datasets**.\n\n"
            "**Current inventory**: public **24 Spaces, 49 models, 34 datasets**."
        )
        self.assertIsNone(result["declared_counts"])
        self.assertFalse(result["aligned"])

    def test_profile_current_declaration_still_requires_manifest_and_observed_equality(self):
        config, record, manifest, blob = self._profile_fixture()
        different = {"spaces": 24, "models": 49, "datasets": 34, "kernels": 14}
        for kwargs in ({"observed": different}, {"manifest": different}):
            with self.subTest(kwargs=kwargs):
                current = {**manifest, "json": {**manifest["json"],
                            "counts": kwargs.get("manifest", record["counts"])}}
                result, _ = self._profile_observation(
                    config, record, current, blob,
                    kwargs.get("observed", record["counts"]), pinned=manifest,
                )
                self.assertEqual(result["declared_counts"], {"spaces": 23, "models": 49, "datasets": 34, "kernels": 14})
                self.assertFalse(result["aligned"])
                self.assertIn("HF_INVENTORY_COUNT_MISMATCH_OR_UNAVAILABLE", result["blockers"])

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


def inventory_fixture(org, get):
    def absent_reserved(url, **kw):
        return {'status': 404} if url.endswith('/README') else get(url, **kw)
    return release.hf_inventory(org, absent_reserved)


class InventoryAndIdentityContractTests(unittest.TestCase):
    def test_object_200_is_unavailable_not_zero(self) -> None:
        result = inventory_fixture(
            "SZLHOLDINGS",
            lambda url, **kw: {"status": 200, "json": {"items": []}, "link": None},
        )
        self.assertFalse(result["observed"])
        self.assertIsNone(result["counts"]["models"])
        self.assertEqual(result["enumeration_state"]["models"], "UNAVAILABLE")
        self.assertEqual(result["errors"]["models"], "INVALID_LIST_RESPONSE")

    def test_empty_list_is_observed_zero(self) -> None:
        result = inventory_fixture(
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

        result = inventory_fixture("SZLHOLDINGS", getter)
        self.assertTrue(result["observed"])
        self.assertEqual(result["counts"]["models"], 2)
        self.assertEqual(len(result["page_evidence"]["models"]), 2)

    def test_duplicate_id_and_wrong_namespace_unavailable(self) -> None:
        dup = inventory_fixture(
            "SZLHOLDINGS",
            lambda url, **kw: {
                "status": 200,
                "json": [_row(), _row()],
                "link": None,
            },
        )
        self.assertFalse(dup["observed"])
        self.assertEqual(dup["errors"]["models"], "DUPLICATE_ID")
        foreign = inventory_fixture(
            "SZLHOLDINGS",
            lambda url, **kw: {
                "status": 200,
                "json": [_row(id="other/model")],
                "link": None,
            },
        )
        self.assertEqual(foreign["errors"]["models"], "FOREIGN_OR_MALFORMED_ID")

    def test_authorization_failure_is_not_zero(self) -> None:
        result = inventory_fixture(
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
            result = inventory_fixture("SZLHOLDINGS", getter)
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
            if url.endswith('/pages'):
                return {"status": 200, "json": {"build_type": "legacy"}}
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
            if url.endswith('/pages'):
                return {"status": 200, "json": {"build_type": "legacy"}}
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

    def test_actions_pages_uses_the_current_deployment_instead_of_a_stale_branch_build(self) -> None:
        current, old = 'c' * 40, 'd' * 40
        responses = {
            'https://a11oy.net/': {'status': 200},
            'https://a11oy.net/health.json': {'status': 200, 'json': {'probe_contract': 'STATIC_DOCUMENT'}},
            'https://api.github.com/repos/szl-holdings/a11oy-net/pages': {
                'status': 200, 'json': {'build_type': 'workflow', 'html_url': 'http://a11oy.net/'}},
            'https://api.github.com/repos/szl-holdings/a11oy-net/pages/builds/latest': {
                'status': 200, 'json': {'commit': old, 'status': 'built'}},
            'https://api.github.com/repos/szl-holdings/a11oy-net/deployments?environment=github-pages&per_page=1': {
                'status': 200, 'json': [{'id': 42, 'sha': current, 'ref': 'main', 'environment': 'github-pages'}]},
            'https://api.github.com/repos/szl-holdings/a11oy-net/deployments/42/statuses?per_page=1': {
                'status': 200, 'json': [{'state': 'success', 'environment_url': 'http://a11oy.net/',
                                      'log_url': 'https://github.com/szl-holdings/a11oy-net/actions/runs/123'}]},
        }
        config = {'proof': {'repository': 'szl-holdings/a11oy-net', 'origin': 'https://a11oy.net'}}
        with mock.patch.object(release, 'github_main', return_value={'observed': True, 'sha': current}), \
                mock.patch.object(release, 'fetch', side_effect=lambda url, **kw: responses[url]) as probe:
            result = release.proof_contract(config)
        self.assertTrue(result['aligned'])
        self.assertEqual(result['pages_revision'], current)
        self.assertEqual(result['pages_revision_source'], 'github-pages-deployment')
        self.assertEqual(result['pages_deployment_id'], 42)
        self.assertFalse(any('pages/builds/latest' in row.args[0] for row in probe.call_args_list))

    def test_actions_pages_never_falls_back_to_an_old_successful_build(self) -> None:
        current = 'c' * 40
        config = {'proof': {'repository': 'szl-holdings/a11oy-net', 'origin': 'https://a11oy.net'}}
        deployments_url = 'https://api.github.com/repos/szl-holdings/a11oy-net/deployments?environment=github-pages&per_page=1'
        status_url = 'https://api.github.com/repos/szl-holdings/a11oy-net/deployments/42/statuses?per_page=1'
        valid_deployment = {'id': 42, 'sha': current, 'ref': 'main', 'environment': 'github-pages'}
        valid_status = {'state': 'success', 'environment_url': 'https://a11oy.net/'}
        cases = [
            ({'status': 403, 'json': []}, {'status': 200, 'json': [valid_status]}),
            ({'status': 200, 'json': []}, {'status': 200, 'json': [valid_status]}),
            ({'status': 200, 'json': {'sha': current}}, {'status': 200, 'json': [valid_status]}),
            ({'status': 200, 'json': [dict(valid_deployment, sha='d' * 40)]}, {'status': 200, 'json': [valid_status]}),
            ({'status': 200, 'json': [dict(valid_deployment, ref='feature')]}, {'status': 200, 'json': [valid_status]}),
            ({'status': 200, 'json': [dict(valid_deployment, environment='preview')]}, {'status': 200, 'json': [valid_status]}),
            ({'status': 200, 'json': [dict(valid_deployment, id=True)]}, {'status': 200, 'json': [valid_status]}),
            ({'status': 200, 'json': [dict(valid_deployment, id='42')]}, {'status': 200, 'json': [valid_status]}),
            ({'status': 200, 'json': [dict(valid_deployment, sha='short')]}, {'status': 200, 'json': [valid_status]}),
            ({'status': 200, 'json': [dict(valid_deployment, ref=[])]}, {'status': 200, 'json': [valid_status]}),
            ({'status': 200, 'json': [valid_deployment]}, {'status': 403, 'json': [valid_status]}),
            ({'status': 200, 'json': [valid_deployment]}, {'status': 200, 'json': []}),
            ({'status': 200, 'json': [valid_deployment]}, {'status': 200, 'json': valid_status}),
            ({'status': 200, 'json': [valid_deployment]}, {'status': 200, 'json': [dict(valid_status, state=[])]}),
            ({'status': 200, 'json': [valid_deployment]}, {'status': 200, 'json': [{'state': 'failure', 'environment_url': 'https://a11oy.net/'}]}),
            ({'status': 200, 'json': [valid_deployment]}, {'status': 200, 'json': [{'state': 'in_progress', 'environment_url': 'https://a11oy.net/'}]}),
            ({'status': 200, 'json': [valid_deployment]}, {'status': 200, 'json': [{'state': 'inactive', 'environment_url': 'https://a11oy.net/'}]}),
            ({'status': 200, 'json': [valid_deployment]}, {'status': 200, 'json': [dict(valid_status, environment_url='https://other.example/')]}),
            ({'status': 200, 'json': [valid_deployment]}, {'status': 200, 'json': [dict(valid_status, environment_url='https://a11oy.net/preview')]}),
        ]
        for deployments, statuses in cases:
            with self.subTest(deployments=deployments, statuses=statuses):
                def fake_fetch(url: str, **kw: object) -> dict[str, object]:
                    if url.endswith('/pages'):
                        return {'status': 200, 'json': {'build_type': 'workflow', 'html_url': 'https://a11oy.net/'}}
                    if url == deployments_url:
                        return deployments
                    if url == status_url:
                        return statuses
                    if 'pages/builds/latest' in url:
                        raise AssertionError('workflow mode must not fall back to a branch build')
                    return {'status': 200, 'json': {}}
                with mock.patch.object(release, 'github_main', return_value={'observed': True, 'sha': current}), \
                        mock.patch.object(release, 'fetch', side_effect=fake_fetch):
                    result = release.proof_contract(config)
                self.assertFalse(result['aligned'])
                self.assertTrue(result['blockers'])

    def test_actions_pages_configuration_must_name_the_observed_public_site(self) -> None:
        sha = 'c' * 40
        config = {'proof': {'repository': 'szl-holdings/a11oy-net', 'origin': 'https://a11oy.net'}}
        for site in (None, 'https://other.example/', 'https://a11oy.net/preview', 'https://a11oy.net:8443/'):
            with self.subTest(site=site):
                def fake_fetch(url: str, **kw: object) -> dict[str, object]:
                    if url.endswith('/pages'):
                        return {'status': 200, 'json': {'build_type': 'workflow', 'html_url': site}}
                    if '/deployments?' in url:
                        return {'status': 200, 'json': [{'id': 42, 'sha': sha, 'ref': 'main', 'environment': 'github-pages'}]}
                    if '/statuses?' in url:
                        return {'status': 200, 'json': [{'state': 'success', 'environment_url': 'https://a11oy.net/'}]}
                    return {'status': 200, 'json': {}}
                with mock.patch.object(release, 'github_main', return_value={'observed': True, 'sha': sha}), \
                        mock.patch.object(release, 'fetch', side_effect=fake_fetch):
                    result = release.proof_contract(config)
                self.assertFalse(result['aligned'])

    def test_unknown_pages_mode_cannot_become_success_from_a_build_record(self) -> None:
        sha = 'c' * 40
        config = {'proof': {'repository': 'szl-holdings/a11oy-net', 'origin': 'https://a11oy.net'}}
        for metadata in ({'status': 403, 'json': {}}, {'status': 200, 'json': {}},
                         {'status': 200, 'json': {'build_type': 'other'}}):
            with self.subTest(metadata=metadata):
                def fake_fetch(url: str, **kw: object) -> dict[str, object]:
                    if url.endswith('/pages'):
                        return metadata
                    if 'pages/builds/latest' in url:
                        return {'status': 200, 'json': {'commit': sha, 'status': 'built'}}
                    return {'status': 200, 'json': {}}
                with mock.patch.object(release, 'github_main', return_value={'observed': True, 'sha': sha}), \
                        mock.patch.object(release, 'fetch', side_effect=fake_fetch):
                    result = release.proof_contract(config)
                self.assertFalse(result['aligned'])


if __name__ == "__main__":
    unittest.main()
