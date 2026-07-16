"""Dependency-light checks for the unpublished proof-obligation dataset."""

from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import unittest
from collections import Counter


ROOT = pathlib.Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "dataset_release" / "szl-proof-obligation-queue"
DATA = PACKAGE / "data"


def load_json(path: pathlib.Path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: pathlib.Path):
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def canonical_bytes(value) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ProofObligationDatasetReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = load_json(PACKAGE / "release-manifest.json")
        cls.crosswalk = load_json(DATA / "formula-id-crosswalk.json")
        cls.tranche = read_jsonl(DATA / "admission-tranche.jsonl")
        cls.queue = read_jsonl(DATA / "proof-obligation-queue.jsonl")
        cls.brain = load_json(DATA / "brain-evidence-summary.json")

    def test_publication_and_claims_fail_closed(self):
        publication = self.manifest["publication"]
        self.assertEqual(publication["state"], "UNPUBLISHED_CANDIDATE")
        self.assertEqual(publication["doi"], "PENDING")
        self.assertEqual(publication["doi_url"], "PENDING")
        self.assertFalse(publication["peer_reviewed"])
        self.assertFalse(publication["zenodo_deposition_created"])
        self.assertFalse(publication["remote_mutation_performed"])
        self.assertFalse(publication["publish_allowed"])
        self.assertIn("DOI_NOT_MINTED", publication["blockers"])

        claims = self.manifest["claims_boundary"]
        self.assertFalse(claims["mathematical_proof_added"])
        self.assertEqual(claims["proof_credit_added"], 0)
        self.assertFalse(claims["raw_brain_text_included"])
        self.assertFalse(claims["model_training_triggered"])
        self.assertFalse(claims["training_eligibility_claimed"])
        self.assertFalse(claims["peer_review_claimed"])
        self.assertIn(
            "THE_DATASET_IS_TRAINING_ELIGIBLE",
            self.manifest["prohibited_claims"],
        )

    def test_source_copies_are_byte_identical_and_receipted(self):
        source_pairs = (
            (
                ROOT
                / "research/formula-training-admission/formula-id-crosswalk.json",
                DATA / "formula-id-crosswalk.json",
            ),
            (
                ROOT / "research/formula-training-admission/admission-tranche.jsonl",
                DATA / "admission-tranche.jsonl",
            ),
            (
                ROOT / "research/formula-training-admission/artifact-receipt.json",
                DATA / "source-artifact-receipt.json",
            ),
            (
                ROOT / "research/formula-training-admission/admission-manifest.json",
                DATA / "source-admission-manifest.json",
            ),
        )
        for source, packaged in source_pairs:
            self.assertEqual(source.read_bytes(), packaged.read_bytes())

        receipt = load_json(DATA / "source-artifact-receipt.json")
        for source_path, expected in receipt["artifacts"].items():
            self.assertEqual(sha256(ROOT / source_path), expected)
        payload = dict(receipt)
        observed = payload.pop("artifact_receipt_sha256")
        self.assertEqual(hashlib.sha256(canonical_bytes(payload)).hexdigest(), observed)

        snapshot = self.manifest["source_snapshots"]["formula_admission"]
        self.assertEqual(
            snapshot["crosswalk_and_tranche_commit"],
            "e4d269b309fe67264f1dfe64a65c3c5fb6ecf570",
        )
        self.assertEqual(
            snapshot["admission_manifest_and_receipt_commit"],
            "b7b0f2996edf674d7365d37112371fa6690e7c0e",
        )

    def test_queue_is_complete_receipt_bound_and_holdout_only(self):
        self.assertEqual(len(self.crosswalk["records"]), 146)
        self.assertEqual(len(self.tranche), 148)
        self.assertEqual(len(self.queue), 146)
        self.assertEqual(len({row["queue_id"] for row in self.queue}), 146)
        self.assertEqual(len({row["record_id"] for row in self.queue}), 146)

        status_counts = Counter(row["resolved_status"] for row in self.queue)
        self.assertEqual(
            status_counts,
            Counter(
                {
                    "OPEN": 115,
                    "CONDITIONAL": 28,
                    "KERNEL_ACCEPTED": 2,
                    "REFUTED": 1,
                }
            ),
        )
        membership = Counter(row["queue_membership"] for row in self.queue)
        self.assertEqual(membership, Counter({"ACTION_REQUIRED": 144, "AUDIT_ONLY": 2}))

        source_by_id = {
            row["record_id"]: row for row in self.crosswalk["records"]
        }
        tranche_by_id = {
            row["record_id"]: row
            for row in self.tranche
            if row["record_kind"] == "FORMULA_STATUS_METADATA"
        }
        for row in self.queue:
            source = source_by_id[row["record_id"]]
            tranche = tranche_by_id[row["record_id"]]
            self.assertEqual(row["claim_sha256"], source["claim_sha256"])
            self.assertEqual(row["resolved_status"], source["resolved_status"])
            self.assertFalse(row["proof_transfer_allowed"])
            self.assertEqual(row["split"], "HOLDOUT")
            self.assertFalse(row["training_eligible"])
            self.assertEqual(
                row["receipt_scope"]["source_record_receipt_sha256"],
                tranche["record_receipt_sha256"],
            )
            payload = dict(row)
            observed = payload.pop("queue_record_sha256")
            self.assertEqual(
                hashlib.sha256(canonical_bytes(payload)).hexdigest(), observed
            )

        self.assertTrue(all(not row["training_eligible"] for row in self.tranche))
        self.assertEqual(self.manifest["dataset"]["training_eligible_rows"], 0)
        self.assertEqual(self.manifest["dataset"]["split"], "HOLDOUT_ONLY")

    def test_namespace_collision_never_transfers_proof(self):
        collisions = [
            row
            for row in self.queue
            if row["namespace_collision"]["relation"]
            == "ID_COLLISION_DIFFERENT_STATEMENT"
        ]
        self.assertEqual(len(collisions), 46)
        self.assertEqual(len({row["formula_id"] for row in collisions}), 23)
        for row in collisions:
            self.assertFalse(row["proof_transfer_allowed"])
            self.assertIn("DISAMBIGUATE_FORMULA_NAMESPACE", row["required_actions"])

    def test_brain_summary_excludes_content_and_preserves_local_scope(self):
        self.assertEqual(self.brain["evidence_label"], "MEASURED_LOCAL_PILOT")
        admission = self.brain["admission_summary"]
        self.assertEqual(admission["raw_graph_nodes_observed"], 9464)
        self.assertEqual(admission["raw_graph_nodes_admitted"], 0)
        self.assertEqual(admission["raw_graph_nodes_excluded"], 9464)
        self.assertEqual(admission["unique_document_count"], 5)
        self.assertEqual(self.brain["metrics"]["query_count"], 15)

        boundary = self.brain["inclusion_boundary"]
        self.assertFalse(boundary["raw_brain_content_included"])
        self.assertFalse(boundary["canonical_document_text_included"])
        self.assertFalse(boundary["query_text_included"])
        self.assertFalse(boundary["per_query_results_included"])
        self.assertFalse(boundary["training_eligible"])
        self.assertFalse(self.brain["claims_boundary"]["independent_replication"])
        self.assertEqual(
            self.brain["claims_boundary"]["external_validity"], "NOT_ESTABLISHED"
        )

    def test_artifact_inventory_and_whole_package_checksums(self):
        for artifact in self.manifest["artifacts"].values():
            path = PACKAGE / artifact["path"]
            self.assertTrue(path.is_file())
            self.assertEqual(path.stat().st_size, artifact["bytes"])
            self.assertEqual(sha256(path), artifact["sha256"])

        checksum_rows = {}
        for line in (PACKAGE / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            digest, relative = line.split("  ", maxsplit=1)
            checksum_rows[relative] = digest
        self.assertNotIn("SHA256SUMS", checksum_rows)
        for relative, expected in checksum_rows.items():
            self.assertEqual(sha256(PACKAGE / relative), expected, relative)

    def test_machine_readable_schemas_encode_fail_closed_invariants(self):
        release_schema = load_json(PACKAGE / "schemas/release-manifest.schema.json")
        record_schema = load_json(
            PACKAGE / "schemas/proof-obligation-record.schema.json"
        )
        self.assertEqual(
            release_schema["properties"]["publication"]["properties"]["doi"][
                "const"
            ],
            "PENDING",
        )
        self.assertFalse(
            release_schema["properties"]["publication"]["properties"][
                "publish_allowed"
            ]["const"]
        )
        self.assertEqual(
            release_schema["properties"]["dataset"]["properties"][
                "training_eligible_rows"
            ]["const"],
            0,
        )
        self.assertFalse(record_schema["properties"]["training_eligible"]["const"])
        self.assertFalse(
            record_schema["properties"]["proof_transfer_allowed"]["const"]
        )

    def test_metadata_has_no_fabricated_doi(self):
        citation = (PACKAGE / "CITATION.cff").read_text(encoding="utf-8")
        zenodo = load_json(PACKAGE / ".zenodo.json")
        self.assertIn("DOI PENDING", citation)
        self.assertNotIn("doi:", citation.lower())
        self.assertIn("DOI PENDING", zenodo["description"])
        self.assertNotIn("doi", zenodo)
        self.assertEqual(self.manifest["license"]["spdx"], "Apache-2.0")

    def test_builder_is_idempotent(self):
        tracked = sorted(
            path
            for path in PACKAGE.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
        before = {path.relative_to(PACKAGE).as_posix(): sha256(path) for path in tracked}
        completed = subprocess.run(
            [sys.executable, str(PACKAGE / "build_package.py")],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertIn('"doi": "PENDING"', completed.stdout)
        after = {path.relative_to(PACKAGE).as_posix(): sha256(path) for path in tracked}
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
