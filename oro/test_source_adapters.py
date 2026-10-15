"""Negative controls for the bounded ORO inspection adapters."""
import hashlib
import unittest
from unittest.mock import patch

from oro.source_adapters import project_source_snapshots


def digest(value):
    return hashlib.sha256(str(value).encode()).hexdigest()


def khipu_node(index, parent=None):
    return {
        "index": index, "space": "a11oy", "wire": "F",
        "digest": digest(index), "parents": [parent] if parent else [],
        "receipt": {"secret": "must-never-leave-owner"},
        "dsse": {"signatures": [{"sig": "must-never-leave-owner"}]},
        "signed": False,
    }


class ExistingDag:
    def __init__(self, nodes):
        self.nodes = nodes
        self.calls = []

    def recent(self, count):
        self.calls.append(("recent", count))
        return self.nodes[-count:]

    def checkpoint(self):
        raise AssertionError("projection must not checkpoint")

    def verify(self):
        raise AssertionError("projection must not invoke mutating verification")

    def append_signed(self, _receipt):
        raise AssertionError("projection must not append")


def brain_snapshot(**changes):
    value = {
        "status": "LIVE", "schema": "szl.second-brain.retrieve/v1",
        "ready": True, "content_access": "HANDLES_ONLY",
        "index_is_model_weights": False,
        "raw_graph_nodes_admitted_to_gradients": 0,
        "k": 1,
        "handles": [{"nodeId": "private-looking-id", "sha256": digest("pointer"),
                     "label": "must-never-leave-owner", "note": "must-never-leave-owner",
                     "source": "must-never-leave-owner", "nodeKind": "citation"}],
    }
    value.update(changes)
    return value


def anatomy_snapshot(**changes):
    value = {
        "ready": True, "state": "STALE",
        "snapshot_sha256": digest("anatomy-snapshot"),
        "source": {
            "repository": "szl-holdings/a11oy",
            "revision": "a" * 40,
            "path": "console/assets/brain-frontier-v7.json",
            "sha256": digest("anatomy-source"),
        },
        "dag": {"state": "MODELED_PLAN_ONLY", "decision": "REVISE",
                "contract_digest": digest("anatomy-contract"),
                "execution_authorized": False,
                "nodes": [{"id": "modeled-only", "label": "must-never-leave-owner",
                           "role": "observation", "depends_on": [], "control_after": []}],
                "layers": [["modeled-only"]], "node_count": 1},
    }
    value.update(changes)
    return value


class SourceAdapterTests(unittest.TestCase):
    def test_existing_owners_join_without_cross_source_edges_or_content(self):
        first = khipu_node(0)
        second = khipu_node(1, first["digest"])
        owner = ExistingDag([first, second])
        result = project_source_snapshots(
            canonical_khipu_dag=owner,
            second_brain=brain_snapshot(), second_brain_revision="b" * 40,
            anatomy=anatomy_snapshot(),
            hatun={"action": "NAVIGATE", "handles": ["khipu.handle.alpha"],
                   "hydrated": False, "secret": "must-never-leave-owner"},
        )
        self.assertEqual(owner.calls, [("recent", 33)])
        self.assertEqual(len(result["nodes"]), 4)
        self.assertEqual(result["sources"]["canonical_khipu"]["window_complete"], True)
        self.assertEqual(result["sources"]["hatun"]["count"], 0)
        self.assertEqual(result["sources"]["anatomy"]["observation_state"], "STALE")
        self.assertEqual(result["sources"]["second_brain"]["content_hash_verification"], "UNKNOWN")
        self.assertFalse(result["execution_authority"])
        self.assertFalse(result["promotion_authority"])
        self.assertFalse(result["signing_authority"])
        self.assertTrue(all(node["evidence"]["proof_status"] == "UNVERIFIED"
                            for node in result["nodes"]))
        by_id = {node["node_id"]: node for node in result["nodes"]}
        self.assertEqual(by_id["khipu:" + second["digest"]]["parents"],
                         ["khipu:" + first["digest"]])
        self.assertNotIn("must-never-leave-owner", str(result))
        self.assertNotIn("private-looking-id", str(result))
        self.assertNotIn("khipu.handle.alpha", str(result))

    def test_real_wire_f_reader_does_not_append_or_sign_on_projection(self):
        import szl_provenance

        owner = szl_provenance._KhipuDAG("a11oy")
        with patch.object(szl_provenance.szl_dsse, "sign_payload",
                          return_value={"signed": False, "signatures": []}):
            owner.append_signed({"schema": "test", "secret": "owner-only"})
            before = len(owner.nodes)
            result = project_source_snapshots(canonical_khipu_dag=owner)
        self.assertEqual(len(owner.nodes), before)
        self.assertEqual(result["sources"]["canonical_khipu"]["signature_verification"], "UNKNOWN")
        self.assertNotIn("owner-only", str(result))

    def test_bounded_window_marks_omitted_parent_instead_of_inventing_anchor(self):
        rows = [khipu_node(0)]
        for index in range(1, 34):
            rows.append(khipu_node(index, rows[-1]["digest"]))
        result = project_source_snapshots(canonical_khipu_dag=ExistingDag(rows))
        state = result["sources"]["canonical_khipu"]
        self.assertEqual(state["count"], 32)
        self.assertFalse(state["window_complete"])
        self.assertEqual(state["omitted_parent_digests"], [rows[1]["digest"]])
        self.assertEqual(result["nodes"][0]["parents"], [])

    def test_khipu_missing_internal_parent_and_noncontiguous_index_refused(self):
        first = khipu_node(0)
        second = khipu_node(1, digest("missing"))
        with self.assertRaisesRegex(ValueError, "immediate predecessor"):
            project_source_snapshots(canonical_khipu_dag=ExistingDag([first, second]))
        with self.assertRaisesRegex(ValueError, "noncontiguous"):
            project_source_snapshots(canonical_khipu_dag=ExistingDag([first, khipu_node(3, first["digest"])]))

    def test_khipu_cannot_skip_an_interior_parent(self):
        first = khipu_node(0)
        second = khipu_node(1, first["digest"])
        third = khipu_node(2, first["digest"])
        with self.assertRaisesRegex(ValueError, "immediate predecessor"):
            project_source_snapshots(canonical_khipu_dag=ExistingDag([first, second, third]))

    def test_second_brain_requires_exact_revision_and_handles_only_contract(self):
        with self.assertRaisesRegex(ValueError, "source revision"):
            project_source_snapshots(second_brain=brain_snapshot())
        with self.assertRaisesRegex(ValueError, "source revision"):
            project_source_snapshots(second_brain=brain_snapshot(), second_brain_revision="main")
        with self.assertRaisesRegex(ValueError, "handle-only"):
            project_source_snapshots(second_brain=brain_snapshot(content_access="FULL_TEXT"),
                                     second_brain_revision="b" * 40)
        bad = brain_snapshot()
        bad["handles"][0]["sha256"] = "bad"
        with self.assertRaisesRegex(ValueError, "pointer"):
            project_source_snapshots(second_brain=bad, second_brain_revision="b" * 40)

    def test_second_brain_bounds_keys_and_identifier_before_encoding(self):
        oversized = brain_snapshot()
        oversized["handles"][0]["nodeId"] = "x" * 100000
        with self.assertRaisesRegex(ValueError, "node identifier"):
            project_source_snapshots(second_brain=oversized, second_brain_revision="b" * 40)
        too_many_fields = brain_snapshot()
        too_many_fields["handles"][0].update({str(index): index for index in range(100)})
        with self.assertRaisesRegex(ValueError, "handle"):
            project_source_snapshots(second_brain=too_many_fields, second_brain_revision="b" * 40)
        non_utf8 = brain_snapshot()
        non_utf8["handles"][0]["nodeId"] = "\ud800"
        with self.assertRaisesRegex(ValueError, "node identifier"):
            project_source_snapshots(second_brain=non_utf8, second_brain_revision="b" * 40)

    def test_second_brain_normalizes_owner_accepted_uppercase_pointer(self):
        snapshot = brain_snapshot()
        snapshot["handles"][0]["sha256"] = "ABCDEF" * 10 + "ABCD"
        result = project_source_snapshots(second_brain=snapshot,
                                          second_brain_revision="b" * 40)
        self.assertEqual(result["nodes"][0]["evidence"]["sha256"],
                         snapshot["handles"][0]["sha256"].lower())

    def test_second_brain_cannot_smuggle_proof_status_or_unavailable_handles(self):
        bad = brain_snapshot()
        bad["handles"][0]["proof_status"] = "PROVEN"
        with self.assertRaisesRegex(ValueError, "handle"):
            project_source_snapshots(second_brain=bad, second_brain_revision="b" * 40)
        with self.assertRaisesRegex(ValueError, "unavailable"):
            project_source_snapshots(second_brain=brain_snapshot(status="UNAVAILABLE"))

    def test_anatomy_source_binding_and_effect_boundary(self):
        bad_source = anatomy_snapshot()
        bad_source["source"]["revision"] = "main"
        with self.assertRaisesRegex(ValueError, "source revision"):
            project_source_snapshots(anatomy=bad_source)
        bad_dag = anatomy_snapshot()
        bad_dag["dag"]["execution_authorized"] = True
        with self.assertRaisesRegex(ValueError, "source contract"):
            project_source_snapshots(anatomy=bad_dag)
        bad_contract = anatomy_snapshot()
        bad_contract["dag"]["contract_digest"] = "not-a-digest"
        with self.assertRaisesRegex(ValueError, "contract digest"):
            project_source_snapshots(anatomy=bad_contract)
        too_large = anatomy_snapshot()
        too_large["dag"]["nodes"] = [
            {"id": str(index), "depends_on": []} for index in range(65)]
        too_large["dag"]["node_count"] = 65
        with self.assertRaisesRegex(ValueError, "outside bound"):
            project_source_snapshots(anatomy=too_large)
        missing_parent = anatomy_snapshot()
        missing_parent["dag"]["nodes"][0]["depends_on"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "dependency missing"):
            project_source_snapshots(anatomy=missing_parent)
        cycle = anatomy_snapshot()
        cycle["dag"]["nodes"][0]["depends_on"] = ["modeled-only"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            project_source_snapshots(anatomy=cycle)
        missing_control = anatomy_snapshot()
        missing_control["dag"]["nodes"][0]["control_after"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "dependency missing"):
            project_source_snapshots(anatomy=missing_control)
        cyclic_control = anatomy_snapshot()
        cyclic_control["dag"]["nodes"][0]["control_after"] = ["modeled-only"]
        with self.assertRaisesRegex(ValueError, "cycle"):
            project_source_snapshots(anatomy=cyclic_control)
        missing_field = anatomy_snapshot()
        missing_field["dag"]["nodes"][0].pop("control_after")
        with self.assertRaisesRegex(ValueError, "topology node"):
            project_source_snapshots(anatomy=missing_field)

    def test_anatomy_failed_observations_emit_no_evidence(self):
        for observation_state, expected in (
                ("PENDING", "UNKNOWN"), ("FAILED", "BLOCKED"),
                ("UNAVAILABLE", "UNAVAILABLE"), ("REJECTED", "BLOCKED")):
            with self.subTest(observation_state=observation_state):
                result = project_source_snapshots(
                    anatomy=anatomy_snapshot(state=observation_state))
                self.assertEqual(result["nodes"], [])
                self.assertEqual(result["sources"]["anatomy"]["state"], expected)
                self.assertEqual(result["sources"]["anatomy"]["observation_state"],
                                 observation_state)

    def test_anatomy_layers_are_bounded_and_respect_dependencies(self):
        excessive = anatomy_snapshot()
        excessive["dag"]["layers"] = [["modeled-only"] * 100000]
        with self.assertRaisesRegex(ValueError, "layers mismatch"):
            project_source_snapshots(anatomy=excessive)
        reversed_layers = anatomy_snapshot()
        reversed_layers["dag"]["nodes"] = [
            {"id": "first", "label": "First", "role": "observation",
             "depends_on": [], "control_after": []},
            {"id": "second", "label": "Second", "role": "observation",
             "depends_on": ["first"], "control_after": []},
        ]
        reversed_layers["dag"]["node_count"] = 2
        reversed_layers["dag"]["layers"] = [["second"], ["first"]]
        with self.assertRaisesRegex(ValueError, "violate dependency order"):
            project_source_snapshots(anatomy=reversed_layers)

    def test_hatun_identifiers_never_become_evidence_nodes(self):
        result = project_source_snapshots(
            hatun={"action": "ABSTAIN", "handles": [], "hydrated": False})
        self.assertEqual(result["nodes"], [])
        self.assertEqual(result["sources"]["hatun"]["evidence_handles"], "UNAVAILABLE")
        with self.assertRaisesRegex(ValueError, "unhydrated"):
            project_source_snapshots(hatun={"action": "NAVIGATE", "handles": [], "hydrated": True})
        for handles in (["unknown"], ["khipu.handle.alpha", "khipu.handle.alpha"]):
            with self.subTest(handles=handles):
                with self.assertRaisesRegex(ValueError, "unhydrated"):
                    project_source_snapshots(hatun={"action": "NAVIGATE", "handles": handles,
                                                   "hydrated": False})
        refusal = project_source_snapshots(hatun={"action": "REFUSE", "handles": [],
                                                  "reason": "INVENTED_IDENTIFIER"})
        self.assertEqual(refusal["nodes"], [])
        self.assertEqual(refusal["sources"]["hatun"]["state"], "DECLARED")


if __name__ == "__main__":
    unittest.main()
