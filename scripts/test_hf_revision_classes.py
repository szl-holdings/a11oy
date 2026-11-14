#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Offline fail-closed tests for Hugging Face revision classes; no network."""
from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SPEC = importlib.util.spec_from_file_location("hf_revision_classes_under_test", HERE / "hf_revision_classes.py")
assert SPEC and SPEC.loader
C = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(C)
MANIFEST = ROOT / "docs" / "huggingface-ecosystem-manifest.json"
NEMO = ("model", "SZLHOLDINGS/szl-nemo")


def real_document() -> dict:
    return json.loads((ROOT / C.POLICY_RELATIVE).read_text(encoding="utf-8"))


def entry(document: dict, repo_type: str, repo_id: str) -> dict:
    return next(row for row in document["entries"] if (row["repoType"], row["id"]) == (repo_type, repo_id))


NEMO_SOURCE = ("model_release/szl-nemo/release-manifest.json", "/hub/repository")
PROMOTION_SOURCE = ("model_release/hf-promotion/promotion-manifest.json", "/candidates/*/canonical_target")
FAMILY_SOURCE = ("model_release/szl-forge-family.json", "/profiles/*/hf_target")
RECEIPT_AGENT_SOURCE = ("model_release/receipt-agent/release-manifest.json", "/hf_artifact_family/*/target_id")


def source(document: dict, path: str, pointer: str) -> dict:
    return next(row for row in document["bindingSources"] if (row["path"], row["pointer"]) == (path, pointer))


class RealPolicyTests(unittest.TestCase):
    def test_tracked_policy_and_manifest_validate_offline(self) -> None:
        classes = C.load_revision_classes()
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        C.validate_manifest_coverage(classes, manifest, label="tracked manifest")
        self.assertEqual(C.governed_changes(classes, manifest, manifest), [])
        self.assertRegex(classes.sha256, r"^[0-9a-f]{64}$")

    def test_szl_nemo_and_every_gated_row_are_governed_exact(self) -> None:
        classes = C.load_revision_classes()
        self.assertEqual(classes.class_of(*NEMO), C.GOVERNED_EXACT)
        sources = classes.policy_source(*NEMO)
        self.assertIn("model_release/szl-nemo/release-manifest.json#/hub/repository", sources)
        self.assertIn("model_release/hf-promotion/promotion-manifest.json#/candidates/0/canonical_target", sources)
        for key in (("model", "SZLHOLDINGS/SZL-Forge-1.5B-ReceiptAgent"), ("model", "SZLHOLDINGS/szl-lambda-gate")):
            self.assertEqual(classes.class_of(*key), C.GOVERNED_EXACT, key)
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        gated = [(C.PLURALS[plural], row["id"]) for plural in C.PLURALS
                 for row in manifest["inventory"][plural] if row.get("gated")]
        self.assertTrue(gated)
        for key in gated:
            self.assertEqual(classes.class_of(*key), C.GOVERNED_EXACT, key)

    def test_every_discovered_binding_is_governed_and_cited(self) -> None:
        classes = C.load_revision_classes()
        self.assertTrue(classes.bindings)
        refs = {binding.ref.split("#")[0] for binding in classes.bindings}
        for path, _ in C.REQUIRED_BINDING_SOURCES:
            self.assertIn(path, refs)
        for binding in classes.bindings:
            self.assertEqual(classes.class_of(binding.repo_type, binding.repo_id), C.GOVERNED_EXACT, binding)
            self.assertIn(binding.ref, classes.policy_source(binding.repo_type, binding.repo_id))
        self.assertNotIn(("kernel", "SZLHOLDINGS/szl-nemo"), {(b.repo_type, b.repo_id) for b in classes.bindings})

    def test_twins_are_keyed_by_repo_type(self) -> None:
        classes = C.load_revision_classes()
        self.assertEqual(classes.class_of("model", "SZLHOLDINGS/szl-lambda-gate"), C.GOVERNED_EXACT)
        self.assertEqual(classes.class_of("kernel", "SZLHOLDINGS/szl-lambda-gate"), C.SOURCE_TRACKED)
        self.assertEqual(classes.class_of("kernel", "SZLHOLDINGS/szl-nemo"), C.SOURCE_TRACKED)
        self.assertEqual(classes.policy_source("dataset", "SZLHOLDINGS/unlisted"), [C.DEFAULT_POLICY_SOURCE])

    def test_append_only_class_is_reserved_and_unused(self) -> None:
        document = real_document()
        self.assertEqual(document["classes"][C.APPEND_ONLY_EVIDENCE]["status"], "RESERVED_UNUSED")
        self.assertFalse([row for row in document["entries"] if row["class"] == C.APPEND_ONLY_EVIDENCE])


class LoaderFailClosedTests(unittest.TestCase):
    def load_bytes(self, raw: bytes | None, *, symlink: bool = False) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(ROOT / C.SCAN_ROOT, root / C.SCAN_ROOT)
            (root / "docs").mkdir()
            target = root / C.POLICY_RELATIVE
            if symlink:
                real = root / "real.json"
                real.write_bytes(raw or b"")
                target.symlink_to(real)
            elif raw is not None:
                target.write_bytes(raw)
            C.load_revision_classes(root=root)

    def test_real_bytes_load_from_a_copied_root(self) -> None:
        self.load_bytes((ROOT / C.POLICY_RELATIVE).read_bytes())

    def test_missing_unreadable_or_invalid_policy_is_an_error_not_a_default(self) -> None:
        text = (ROOT / C.POLICY_RELATIVE).read_text(encoding="utf-8")
        duplicate = text.replace('"schema":', '"schema": "x",\n  "schema":', 1)
        cases = {
            "missing": None,
            "empty": b"",
            "empty-object": b"{}",
            "not-json": b"{",
            "array": b"[]",
            "duplicate-key": duplicate.encode(),
            "nonfinite": text.replace('"entries": [', '"entries": [NaN,', 1).encode(),
            "not-utf8": b"\xff\xfe",
        }
        for name, raw in cases.items():
            with self.subTest(case=name), self.assertRaises(C.RevisionClassError):
                self.load_bytes(raw)
        with self.subTest(case="symlink"), self.assertRaises(C.RevisionClassError):
            self.load_bytes((ROOT / C.POLICY_RELATIVE).read_bytes(), symlink=True)


class ValidatorRuleTests(unittest.TestCase):
    def assertRejected(self, document: dict, pattern: str, root: Path = ROOT) -> None:
        with self.assertRaisesRegex(C.RevisionClassError, pattern):
            C.validate_document(document, root=root)

    def test_real_document_passes(self) -> None:
        C.validate_document(real_document(), root=ROOT)

    def test_bound_repo_unclassified_or_not_governed_exact_fails(self) -> None:
        document = real_document()
        document["entries"] = [row for row in document["entries"] if (row["repoType"], row["id"]) != NEMO]
        self.assertRejected(document, "bound model SZLHOLDINGS/szl-nemo .* must be classed GOVERNED_EXACT")
        document = real_document()
        entry(document, *NEMO)["class"] = C.SOURCE_TRACKED
        self.assertRejected(document, "must be classed GOVERNED_EXACT")

    def test_binding_must_be_cited_and_citations_must_be_real(self) -> None:
        document = real_document()
        entry(document, *NEMO)["policySource"].remove("model_release/szl-nemo/release-manifest.json#/hub/repository")
        self.assertRejected(document, "policySource must cite")
        document = real_document()
        entry(document, *NEMO)["policySource"].append("model_release/szl-forge-family.json#/profiles/9/hf_target")
        self.assertRejected(document, "not a discovered binding")

    def test_gated_row_must_be_governed_exact(self) -> None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
        for change in ("remove", "source-tracked"):
            document = real_document()
            if change == "remove":
                document["entries"].remove(entry(document, "model", "SZLHOLDINGS/szl-lambda-gate"))
            else:
                entry(document, "model", "SZLHOLDINGS/szl-lambda-gate")["class"] = C.SOURCE_TRACKED
            classes = C.validate_document(document, root=ROOT)
            with self.subTest(change=change), self.assertRaisesRegex(C.RevisionClassError, "gated model SZLHOLDINGS/szl-lambda-gate"):
                C.validate_manifest_coverage(classes, manifest, label="tracked manifest")

    def test_entry_shape_rules(self) -> None:
        def mutate(change):
            document = real_document()
            change(document, entry(document, *NEMO))
            return document

        cases = {
            "duplicate key": (lambda d, e: d["entries"].append(copy.deepcopy(e)), "duplicates"),
            "missing policySource": (lambda d, e: e.pop("policySource"), "must have exactly"),
            "empty policySource": (lambda d, e: e.update(policySource=[]), "non-empty policySource"),
            "blank policySource": (lambda d, e: e.update(policySource=[" "]), "non-empty policySource"),
            "string policySource": (lambda d, e: e.update(policySource="x"), "non-empty policySource"),
            "missing rationale": (lambda d, e: e.update(rationale=""), "requires a rationale"),
            "unknown class": (lambda d, e: e.update({"class": "GOVERNED_LOOSE"}), "unknown class"),
            "reserved class": (lambda d, e: e.update({"class": C.APPEND_ONLY_EVIDENCE}), "reserved class"),
            "unknown repoType": (lambda d, e: e.update(repoType="collection"), "repoType is unknown"),
            "foreign id": (lambda d, e: e.update(id="other/szl-nemo"), "SZLHOLDINGS repository id"),
            "extra key": (lambda d, e: e.update(mutablePaths=["*"]), "must have exactly"),
        }
        for name, (change, pattern) in cases.items():
            with self.subTest(case=name):
                self.assertRejected(mutate(change), pattern)

    def test_document_level_rules(self) -> None:
        def changed(change):
            document = real_document()
            change(document)
            return document

        cases = {
            "default class": (lambda d: d.update(defaultClass=C.GOVERNED_EXACT), "defaultClass"),
            "schema": (lambda d: d.update(schema="szl.hf-revision-classes/v0"), "schema must be"),
            "spdx": (lambda d: d.update({"$comment": "x"}), "SPDX"),
            "unknown key": (lambda d: d.update(extra=True), "top-level keys"),
            "missing key": (lambda d: d.pop("referenceOnlySources"), "top-level keys"),
            "append-only claimed enforced": (
                lambda d: d["classes"][C.APPEND_ONLY_EVIDENCE].update(status="ENFORCED"), "RESERVED_UNUSED"),
            "class removed": (lambda d: d["classes"].pop(C.SOURCE_TRACKED), "exactly the known"),
            "required source dropped": (
                lambda d: d.update(bindingSources=[s for s in d["bindingSources"] if s["pointer"] != "/hub/repository"]),
                "required binding sources are not declared"),
            "binding without namespace": (
                lambda d: d["bindingSources"][0].pop("repoType"), "fixed repoType or a repoTypeField"),
            "binding with two namespaces": (
                lambda d: d["bindingSources"][0].update(repoTypeField="x", repoTypeMap={"X": "model"}),
                "fixed repoType or a repoTypeField"),
            "stale source": (
                lambda d: d["referenceOnlySources"].append(
                    {"path": "model_release/szl-forge-family.json", "pointer": "/base/none", "rationale": "x"}),
                "match no SZLHOLDINGS reference"),
            "ambiguous source": (
                lambda d: d["referenceOnlySources"].append(
                    {"path": "model_release/szl-nemo/release-manifest.json", "pointer": "/hub/repository",
                     "rationale": "shadow"}),
                "more than one source"),
            "outside scan root": (
                lambda d: d["referenceOnlySources"].append(
                    {"path": "docs/huggingface-ecosystem-manifest.json", "pointer": "/org", "rationale": "x"}),
                "model_release/ JSON file"),
            "duplicate source": (
                lambda d: d["bindingSources"].append(copy.deepcopy(d["bindingSources"][0])), "duplicates another source"),
        }
        for name, (change, pattern) in cases.items():
            with self.subTest(case=name):
                self.assertRejected(changed(change), pattern)


    def test_required_sources_pin_their_namespace_in_code(self) -> None:
        self.assertEqual(set(C.REQUIRED_BINDING_SOURCES), {NEMO_SOURCE, PROMOTION_SOURCE, FAMILY_SOURCE,
                                                           RECEIPT_AGENT_SOURCE})
        document = real_document()
        for key, namespace in C.REQUIRED_BINDING_SOURCES.items():
            row = source(document, *key)
            self.assertEqual({name: row[name] for name in C.NAMESPACE_KEYS if name in row}, namespace, key)

    def test_policy_only_edits_cannot_de_govern_a_required_binding(self) -> None:
        # Policy-only attacks: no model_release file changes, and every entry
        # is rewritten to stay consistent, so only the namespace pin stops them.
        def reroute(document: dict, path: str, repo_type: str | None) -> None:
            moved: dict[tuple[str, str], list[str]] = {}
            for row in document["entries"]:
                cited = [item for item in row["policySource"] if item.startswith(f"{path}#")]
                row["policySource"] = [item for item in row["policySource"] if item not in cited]
                if cited and repo_type is not None:
                    moved.setdefault((repo_type, row["id"]), []).extend(cited)
            document["entries"] = [row for row in document["entries"] if row["policySource"]]
            for (kind, repo_id), cited in moved.items():
                existing = [row for row in document["entries"] if (row["repoType"], row["id"]) == (kind, repo_id)]
                if existing:
                    existing[0]["policySource"].extend(cited)
                else:
                    document["entries"].append({"repoType": kind, "id": repo_id, "class": C.GOVERNED_EXACT,
                                                "policySource": cited, "rationale": "re-namespaced"})

        def nemo_and_promotion(document: dict) -> None:
            source(document, *NEMO_SOURCE)["repoType"] = "kernel"
            reroute(document, NEMO_SOURCE[0], "kernel")
            source(document, *PROMOTION_SOURCE)["repoTypeMap"] = {"MODEL": None}
            reroute(document, PROMOTION_SOURCE[0], None)

        def promotion_null(document: dict) -> None:
            source(document, *PROMOTION_SOURCE)["repoTypeMap"] = {"MODEL": None}
            reroute(document, PROMOTION_SOURCE[0], None)

        def family_to_space(document: dict) -> None:
            source(document, *FAMILY_SOURCE)["repoType"] = "space"
            reroute(document, FAMILY_SOURCE[0], "space")

        def receipt_agent_null(document: dict) -> None:
            source(document, *RECEIPT_AGENT_SOURCE)["repoTypeMap"].update(
                EVALUATION_DATASET=None, SCHEMA_DATASET=None, SPACE=None)
            ra = f"{RECEIPT_AGENT_SOURCE[0]}#/hf_artifact_family/"
            for row in document["entries"]:
                row["policySource"] = [item for item in row["policySource"]
                                       if not item.startswith(ra) or item == f"{ra}0/target_id"]
            document["entries"] = [row for row in document["entries"] if row["policySource"]]

        cases = {
            "szl-nemo to kernel and promotion MODEL to null": (nemo_and_promotion, "required namespace"),
            "promotion MODEL to null": (promotion_null, "MODEL'\\] to no repository namespace"),
            "forge family to space": (family_to_space, "required namespace"),
            "receipt-agent datasets and space to null": (receipt_agent_null, "to no repository namespace"),
        }
        for name, (attack, pattern) in cases.items():
            with self.subTest(case=name):
                document = real_document()
                attack(document)
                self.assertRejected(document, pattern)

    def test_each_required_source_rejects_re_namespacing(self) -> None:
        def changed(key, change):
            document = real_document()
            change(source(document, *key))
            return document

        required = "must declare the required namespace"
        unnamespaced = "to no repository namespace; only \\['COLLECTION'\\] may map to null"
        cases = {
            "szl-nemo to kernel": (NEMO_SOURCE, lambda s: s.update(repoType="kernel"), required),
            "szl-nemo to a field map": (
                NEMO_SOURCE, lambda s: (s.pop("repoType"), s.update(repoTypeField="repository_role",
                                                                    repoTypeMap={"X": "model"})), required),
            "promotion MODEL to null": (
                PROMOTION_SOURCE, lambda s: s.update(repoTypeMap={"MODEL": None}), unnamespaced),
            "promotion MODEL to kernel": (
                PROMOTION_SOURCE, lambda s: s.update(repoTypeMap={"MODEL": "kernel"}), required),
            "promotion extra kind": (
                PROMOTION_SOURCE, lambda s: s["repoTypeMap"].update(DATASET="kernel"), required),
            "promotion other field": (
                PROMOTION_SOURCE, lambda s: s.update(repoTypeField="track"), required),
            "forge family to space": (FAMILY_SOURCE, lambda s: s.update(repoType="space"), required),
            "forge family to kernel": (FAMILY_SOURCE, lambda s: s.update(repoType="kernel"), required),
            "receipt-agent eval to null": (
                RECEIPT_AGENT_SOURCE, lambda s: s["repoTypeMap"].update(EVALUATION_DATASET=None), unnamespaced),
            "receipt-agent schemas to null": (
                RECEIPT_AGENT_SOURCE, lambda s: s["repoTypeMap"].update(SCHEMA_DATASET=None), unnamespaced),
            "receipt-agent space to null": (
                RECEIPT_AGENT_SOURCE, lambda s: s["repoTypeMap"].update(SPACE=None), unnamespaced),
            "receipt-agent adapter to null": (
                RECEIPT_AGENT_SOURCE, lambda s: s["repoTypeMap"].update(MODEL_ADAPTER=None), unnamespaced),
            "receipt-agent space to kernel": (
                RECEIPT_AGENT_SOURCE, lambda s: s["repoTypeMap"].update(SPACE="kernel"), required),
            "receipt-agent collection dropped": (
                RECEIPT_AGENT_SOURCE, lambda s: s["repoTypeMap"].pop("COLLECTION"), required),
        }
        for name, (key, change, pattern) in cases.items():
            with self.subTest(case=name):
                self.assertRejected(changed(key, change), pattern)

    def test_only_collection_may_map_to_no_namespace_in_any_binding_source(self) -> None:
        document = real_document()
        row = next(row for row in document["bindingSources"] if row["pointer"] == "/components/*/hf_target")
        row["repoTypeMap"]["MODEL_PROFILE_PEFT_ADAPTER"] = None
        self.assertRejected(document, "MODEL_PROFILE_PEFT_ADAPTER.*no repository namespace")

    def test_required_source_cannot_move_to_reference_only(self) -> None:
        document = real_document()
        row = source(document, *NEMO_SOURCE)
        document["bindingSources"].remove(row)
        document["referenceOnlySources"].append({"path": row["path"], "pointer": row["pointer"],
                                                 "rationale": "relaxed"})
        self.assertRejected(document, "required binding sources are not declared")


class BindingDiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        shutil.copytree(ROOT / C.SCAN_ROOT, self.root / C.SCAN_ROOT)

    def write(self, relative: str, value) -> None:
        (self.root / relative).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def test_copied_tree_matches_real_tree(self) -> None:
        C.validate_document(real_document(), root=self.root)

    def test_new_unreviewed_binding_file_fails_closed(self) -> None:
        self.write("model_release/new-release.json", {"hub": {"repository": "SZLHOLDINGS/new-weights"}})
        with self.assertRaisesRegex(C.RevisionClassError, "unreviewed SZLHOLDINGS repository reference .*new-release.json#/hub/repository"):
            C.validate_document(real_document(), root=self.root)

    def test_new_target_in_a_declared_binding_must_be_classified(self) -> None:
        path = self.root / "model_release/szl-forge-family.json"
        family = json.loads(path.read_text(encoding="utf-8"))
        family["profiles"].append({**family["profiles"][-1], "hf_target": "SZLHOLDINGS/SZL-New-1.5B"})
        path.write_text(json.dumps(family), encoding="utf-8")
        with self.assertRaisesRegex(C.RevisionClassError, "bound model SZLHOLDINGS/SZL-New-1.5B"):
            C.validate_document(real_document(), root=self.root)

    def test_unmapped_namespace_field_fails_closed(self) -> None:
        path = self.root / "model_release/hf-promotion/promotion-manifest.json"
        promotion = json.loads(path.read_text(encoding="utf-8"))
        promotion["candidates"][0]["target_kind"] = "DATASET"
        path.write_text(json.dumps(promotion), encoding="utf-8")
        with self.assertRaisesRegex(C.RevisionClassError, "has no mapped target_kind"):
            C.validate_document(real_document(), root=self.root)

    def test_repository_id_as_json_key_fails_closed(self) -> None:
        self.write("model_release/keyed.json", {"SZLHOLDINGS/szl-nemo": {"revision": "a" * 40}})
        with self.assertRaisesRegex(C.RevisionClassError, "used as a JSON key"):
            C.validate_document(real_document(), root=self.root)

    def test_unparseable_or_symlinked_scan_file_fails_closed(self) -> None:
        (self.root / "model_release/broken.json").write_text("{", encoding="utf-8")
        with self.assertRaisesRegex(C.RevisionClassError, "broken.json is not valid JSON"):
            C.validate_document(real_document(), root=self.root)
        (self.root / "model_release/broken.json").unlink()
        (self.root / "model_release/link.json").symlink_to(self.root / "model_release/szl-forge-family.json")
        with self.assertRaisesRegex(C.RevisionClassError, "regular file"):
            C.validate_document(real_document(), root=self.root)

    def test_removed_binding_location_fails_instead_of_relaxing(self) -> None:
        path = self.root / "model_release/szl-nemo/release-manifest.json"
        release = json.loads(path.read_text(encoding="utf-8"))
        release["hub"]["repo"] = release["hub"].pop("repository")
        path.write_text(json.dumps(release), encoding="utf-8")
        with self.assertRaisesRegex(C.RevisionClassError, "unreviewed SZLHOLDINGS repository reference"):
            C.validate_document(real_document(), root=self.root)


class GovernedChangeTests(unittest.TestCase):
    def test_governed_and_gated_changes_are_listed_and_source_tracked_are_not(self) -> None:
        classes = C.load_revision_classes()
        old = json.loads(MANIFEST.read_text(encoding="utf-8"))
        new = copy.deepcopy(old)
        rows = {(C.PLURALS[p], r["id"]): r for p in C.PLURALS for r in new["inventory"][p]}
        rows[NEMO]["sha"] = "f" * 40
        rows[("model", "SZLHOLDINGS/szl-lambda-gate")]["lastModified"] = "2026-11-03T00:00:00.000Z"
        rows[("kernel", "SZLHOLDINGS/szl-lambda-gate")]["sha"] = "f" * 40
        changes = C.governed_changes(classes, old, new)
        self.assertEqual(
            [(c["repoType"], c["id"], c["change"], c["fields"]) for c in changes],
            [("model", "SZLHOLDINGS/szl-lambda-gate", "REVISION_CHANGED", ["lastModified"]),
             ("model", "SZLHOLDINGS/szl-nemo", "REVISION_CHANGED", ["sha"])],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
