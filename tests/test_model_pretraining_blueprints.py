# SPDX-License-Identifier: Apache-2.0
"""Code-only HF blueprints remain inspection hints, never trained/readiness proof.

All metadata is synthetic. These tests exercise the real projection/router
module in isolation; they do not fetch a Hub model or certify a deployed app.
"""
from __future__ import annotations

import hashlib
import sys
import tempfile
import types
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from routers import model_pretraining as view


RECIPE = "RECIPE_OR_PLACEHOLDER_HINT"
SOFTWARE = "KERNEL_OR_SOFTWARE_HINT"
BLUEPRINT_TAGS = ["pytorch", "model-blueprint", "not-trained", "advisory", "tabular-classification"]
NOW = datetime(2026, 9, 13, 16, tzinfo=timezone.utc)


def fixture_manifest(tags=None, identity="SZLHOLDINGS/A11OY-Router"):
    """An explicitly synthetic observation, not an assertion that this repo exists."""
    return {
        "schemaVersion": 2, "org": "SZLHOLDINGS", "observedAt": "2026-09-10T03:20:41Z",
        "inventoryScope": {"visibility": "public-only", "authenticated": False,
                           "privateAssetsIncluded": False},
        "counts": {"models": 1},
        "inventory": {"models": [{
            "id": identity, "repoType": "model", "private": False,
            "sha": "a" * 40, "lastModified": "2026-09-09T12:00:00Z",
            "tags": list(BLUEPRINT_TAGS if tags is None else tags),
            "gated": False, "disabled": False, "license": "apache-2.0",
        }]},
    }


class BlueprintHintTests(unittest.TestCase):
    def test_exact_forge_publisher_tags_are_recipe_hint(self):
        self.assertEqual(view.category(BLUEPRINT_TAGS), RECIPE)

    def test_blueprint_tag_alone_is_recipe_hint(self):
        self.assertEqual(view.category(["model-blueprint"]), RECIPE)

    def test_not_trained_tag_alone_is_recipe_hint(self):
        self.assertEqual(view.category(["not-trained"]), RECIPE)

    def test_casefolded_tags_have_the_same_semantics(self):
        self.assertEqual(view.category(["MODEL-BLUEPRINT", "NOT-TRAINED"]), RECIPE)

    def test_not_trained_wins_over_adapter_metadata(self):
        self.assertEqual(view.category(["not-trained", "peft", "safetensors"]), RECIPE)

    def test_not_trained_wins_over_adapter_lineage_tag(self):
        self.assertEqual(view.category(["not-trained", "base_model:adapter:example/base"]), RECIPE)

    def test_not_trained_wins_over_checkpoint_metadata(self):
        self.assertEqual(view.category(["not-trained", "transformers", "text-generation"]), RECIPE)

    def test_not_trained_wins_over_quantized_metadata(self):
        self.assertEqual(view.category(["not-trained", "gguf", "llama.cpp"]), RECIPE)

    def test_not_trained_wins_over_classical_metadata(self):
        self.assertEqual(view.category(["not-trained", "logistic-regression"]), RECIPE)

    def test_kernel_and_software_precedence_is_preserved(self):
        for marker in ("kernel", "kernels", "software", "not-a-checkpoint", "not-a-model",
                       "test-fixture", "surrogate"):
            with self.subTest(marker=marker):
                self.assertEqual(view.category([marker, "model-blueprint", "not-trained"]), SOFTWARE)

    def test_unrecognized_substrings_do_not_satisfy_explicit_marker(self):
        for marker in ("not-trained-yet-ish", "example-model-blueprint", "trained", "blueprint"):
            with self.subTest(marker=marker):
                self.assertEqual(view.category([marker]), "UNCLASSIFIED")

    def test_existing_positive_hints_are_not_reclassified_without_new_marker(self):
        examples = [(["peft"], "ADAPTER_HINT"), (["gguf"], "GGUF_HINT"),
                    (["transformers", "safetensors"], "CHECKPOINT_HINT"),
                    (["logistic-regression"], "CLASSICAL_MODEL_HINT"),
                    (["roadmap"], RECIPE), ([], "UNCLASSIFIED")]
        for tags, expected in examples:
            with self.subTest(tags=tags):
                self.assertEqual(view.category(tags), expected)


class BlueprintProjectionTests(unittest.TestCase):
    def project(self, identity="SZLHOLDINGS/A11OY-Router"):
        return view.project(view.canonical(fixture_manifest(identity=identity)), [], now=NOW)

    def test_router_and_invariant_projection_use_same_existing_category(self):
        for identity in ("SZLHOLDINGS/A11OY-Router", "SZLHOLDINGS/A11OY-Invariant"):
            with self.subTest(identity=identity):
                result = self.project(identity)
                self.assertEqual(result["models"][0]["categoryHint"], RECIPE)
                self.assertEqual(result["categoryCounts"], {RECIPE: 1})

    def test_projection_does_not_invent_a_source_pointer(self):
        result = self.project()
        self.assertIsNone(result["models"][0]["sourceUrl"])
        self.assertEqual(result["models"][0]["sourceState"], "NOT_RESOLVED_BY_THIS_CATALOG")

    def test_projection_keeps_every_authority_and_verification_false(self):
        result = self.project()
        self.assertTrue(all(value is False for value in result["authority"].values()))
        for field in ("sourceAlignmentVerified", "wholeOrganizationInventoryVerified", "trainingAllowed"):
            self.assertIs(result[field], False)
        for field in ("categoryIsVerified", "sourceBytesVerified", "weightsVerified", "evaluationVerified",
                      "publicationVerified", "runtimeVerified", "trainingAllowed"):
            self.assertIs(result["models"][0][field], False)

    def test_projection_preserves_original_observation_and_content_digest(self):
        raw = view.canonical(fixture_manifest())
        result = view.project(raw, [], now=NOW)
        self.assertEqual(result["manifestSha256"], hashlib.sha256(raw).hexdigest())
        self.assertEqual(result["observedAt"], "2026-09-10T03:20:41Z")
        self.assertEqual(result["snapshotFreshness"], "STALE_SNAPSHOT")
        self.assertEqual(result["models"][0]["hubRevisionState"], "RECORDED_SNAPSHOT_NOT_LIVE")

    def test_projection_does_not_add_proposed_names_to_an_empty_inventory(self):
        data = fixture_manifest(); data["inventory"]["models"] = []; data["counts"]["models"] = 0
        result = view.project(view.canonical(data), [], now=NOW)
        self.assertEqual(result["returned"], 0)
        self.assertEqual(result["models"], [])
        self.assertEqual(result["categoryCounts"], {})


class BlueprintRouteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        snapshot = Path(temporary.name) / "projection.json"
        snapshot.write_bytes(view.build_projection(view.canonical(fixture_manifest())))
        self.snapshot = snapshot
        # Only the neighboring runtime-source service is stubbed. The actual
        # model-pretraining parser, projector and HTTP handler execute below.
        runtime = types.ModuleType("routers.hf_tooling_evidence")
        runtime.runtime_source = lambda: (None, "UNAVAILABLE")
        for context in (patch.object(view, "MANIFEST", snapshot),
                        patch.object(view, "declared_source_cards", return_value=([], "UNAVAILABLE")),
                        patch.dict(sys.modules, {"routers.hf_tooling_evidence": runtime})):
            context.start(); self.addCleanup(context.stop)
        app = FastAPI()
        view.register(app)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)

    def test_actual_get_contract_renders_hint_without_training_permission(self):
        response = self.client.get("/api/a11oy/v1/models/pretraining")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["cache-control"], "no-store")
        self.assertEqual(response.json()["models"][0]["categoryHint"], RECIPE)
        self.assertIs(response.json()["trainingAllowed"], False)
        self.assertIs(response.json()["models"][0]["weightsVerified"], False)

    def test_actual_head_contract_has_no_body(self):
        response = self.client.head("/api/a11oy/v1/models/pretraining")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"")

    def test_missing_snapshot_stays_unavailable_not_blueprint_inventory(self):
        self.snapshot.unlink()
        response = self.client.get("/api/a11oy/v1/models/pretraining")
        self.assertEqual(response.status_code, 503)
        self.assertIsNone(response.json()["returned"])
        self.assertEqual(response.json()["models"], [])
        self.assertIs(response.json()["trainingAllowed"], False)

    def test_mutating_methods_remain_rejected(self):
        for method in ("POST", "PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                response = self.client.request(method, "/api/a11oy/v1/models/pretraining")
                self.assertEqual(response.status_code, 405)


if __name__ == "__main__":
    unittest.main()
