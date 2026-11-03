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
