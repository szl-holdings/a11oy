#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Adversarial and cross-process checks for advisory counterfactual replay."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import py_compile
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    spec = importlib.util.spec_from_file_location("decision_lab_test_subject", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LAB = load(ROOT / "tools" / "decision_lab.py")
STATEMENT = {
    "_type": "https://in-toto.io/Statement/v1",
    "subject": [{"name": "artifact-\u00f1", "digest": {"sha256": "a" * 64}}],
    "predicateType": "https://slsa.dev/provenance/v1",
    "predicate": {
        "buildDefinition": {"buildType": "https://example.invalid/build"},
        "runDetails": {"builder": {"id": "https://example.invalid/builder"}},
    },
}


def payload():
    return {
        "command": LAB.BIND.intent_from_command(
            principal_id="agent:operator",
            action="DeployArtifact",
            resource_id="deployment:test",
            purpose="release",
            intended_effect="deploy",
            risk_score=100,
            human_approval=True,
            mfa=True,
            evidence_digest=LAB.BIND.statement_digest(STATEMENT),
        ),
        "statement": copy.deepcopy(STATEMENT),
        "verification": {"verified": True},
    }


def scenario(identifier, changes):
    return {"id": identifier, "label": "Inspect " + identifier, "changes": changes}


def copied_lab(directory):
    target = Path(directory)
    for name in (*LAB.EXECUTED_FILES, *LAB.REFERENCE_FILES):
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / name, destination)
    return load(target / "tools" / "decision_lab.py")


class DecisionLabTests(unittest.TestCase):
    def test_default_matrix_uses_actual_evaluators(self):
        value = payload()
        result = LAB.analyze(value)
        self.assertEqual(result["schema"], LAB.SCHEMA)
        self.assertEqual(result["base"]["intentOutcome"], "ALLOW")
        self.assertEqual(result["base"]["combinedOutcome"], "REVIEW")
        self.assertFalse(result["base"]["result"]["evidence"]["verified"])
        cases = {item["id"]: item for item in result["scenarios"]}
        self.assertEqual(len(cases), 5)
        self.assertEqual(cases["humanApproval-toggle"]["intentOutcome"], "BLOCK")
        self.assertEqual(cases["mfa-toggle"]["intentOutcome"], "BLOCK")
        self.assertEqual(cases["network-toggle"]["intentOutcome"], "BLOCK")
        self.assertEqual(cases["risk-at-limit"]["intentOutcome"], "ALLOW")
        self.assertEqual(cases["risk-above-limit"]["intentOutcome"], "BLOCK")
        for item in [result["base"], *result["scenarios"]]:
            actual = LAB.BIND.bind(
                command=item["command"],
                statement=value["statement"],
                verification=value["verification"],
            )
            self.assertEqual(item["result"], LAB._stable(actual))
            self.assertIs(item["executable"], False)
            self.assertIs(item["evaluationOnly"], True)
            self.assertEqual(item["executionAuthority"], "none")

    def test_hypothetical_approval_never_establishes_authority(self):
        value = payload()
        value["command"]["context"]["humanApproval"] = False
        value["scenarios"] = [
            scenario("claimed-approval", {"context.humanApproval": True})
        ]
        result = LAB.analyze(value)
        altered = result["scenarios"][0]
        self.assertEqual(result["base"]["intentOutcome"], "BLOCK")
        self.assertEqual(altered["intentOutcome"], "ALLOW")
        self.assertEqual(altered["combinedOutcome"], "REVIEW")
        self.assertIs(altered["result"]["policyEligible"], False)
        self.assertIs(altered["result"]["executable"], False)
        self.assertIs(altered["result"]["intent"]["identityAuthenticated"], False)
        self.assertEqual(
            altered["outcomeDelta"]["intent"],
            {"before": "BLOCK", "after": "ALLOW", "changed": True},
        )

    def test_scenarios_fork_base_independently(self):
        value = payload()
        value["scenarios"] = [
            scenario("approval", {"context.humanApproval": False}),
            scenario("mfa", {"context.mfa": False}),
        ]
        result = LAB.analyze(value)
        first, second = result["scenarios"]
        self.assertTrue(second["command"]["context"]["humanApproval"])
        self.assertTrue(first["command"]["context"]["mfa"])
        self.assertEqual(first["result"]["intent"]["deny"], ["humanApproval required"])
        self.assertEqual(second["result"]["intent"]["deny"], ["mfa required"])

    def test_input_and_other_results_are_not_mutated(self):
        value = payload()
        before = copy.deepcopy(value)
        first = LAB.analyze(value)
        self.assertEqual(value, before)
        first["scenarios"][0]["command"]["context"]["purpose"] = "tampered"
        self.assertEqual(value, before)
        second = LAB.analyze(value)
        self.assertEqual(second["base"]["command"]["context"]["purpose"], "release")

    def test_compatible_alias_updates_are_explicit(self):
        value = payload()
        value["scenarios"] = [scenario("assurance", {"principal.attrs.assurance": 0})]
        result = LAB.analyze(value)["scenarios"][0]
        changes = {item["path"]: item for item in result["changes"]}
        self.assertEqual(
            set(changes), {"principal.attrs.assurance", "principal.assurance"}
        )
        self.assertEqual(changes["principal.assurance"]["kind"], "compatibility-alias")
        self.assertEqual(
            result["result"]["intent"]["deny"], ["assurance below requiredAssurance"]
        )

    def test_conflicting_alias_is_not_silently_repaired(self):
        value = payload()
        value["command"]["principal"]["assurance"] = 99
        value["scenarios"] = [scenario("assurance", {"principal.attrs.assurance": 2})]
        result = LAB.analyze(value)["scenarios"][0]
        self.assertEqual(result["command"]["principal"]["assurance"], 99)
        self.assertEqual(result["intentOutcome"], "BLOCK")
        self.assertEqual(len(result["changes"]), 1)

    def test_same_value_changes_are_reported_as_no_op(self):
        value = payload()
        value["scenarios"] = [scenario("same", {"context.riskScore": 100})]
        result = LAB.analyze(value)["scenarios"][0]
        self.assertEqual(result["changes"], [])
        self.assertFalse(
            any(delta["changed"] for delta in result["outcomeDelta"].values())
        )

    def test_digest_change_is_not_repaired(self):
        value = payload()
        value["scenarios"] = [
            scenario("wrong-digest", {"context.evidenceDigest": "b" * 64})
        ]
        result = LAB.analyze(value)["scenarios"][0]
        self.assertFalse(result["result"]["evidenceBinding"]["valid"])
        self.assertEqual(result["combinedOutcome"], "BLOCK")
        self.assertIn(
            "STATEMENT_DIGEST_MISMATCH", {item["code"] for item in result["trace"]}
        )

    def test_trace_contains_real_emitted_reason(self):
        value = payload()
        value["command"]["context"]["mfa"] = False
        result = LAB.analyze(value)
        trace = result["base"]["trace"]
        self.assertTrue(
            any(
                item["source"] == "intent.deny"
                and item["detail"] == "mfa required"
                and item["code"] == "MFA_REQUIRED"
                for item in trace
            )
        )
        for item in trace:
            if item["source"] in {"intent.deny", "evidence.deny", "evidence.review"}:
                section, field = item["source"].split(".")
                self.assertIn(item["detail"], result["base"]["result"][section][field])
        self.assertFalse(result["policy"]["nativeCedarExecuted"])
        self.assertFalse(result["policy"]["nativeOpaExecuted"])

    def test_missing_evidence_stays_review(self):
        value = payload()
        del value["statement"]
        result = LAB.analyze(value)
        self.assertEqual(result["base"]["combinedOutcome"], "REVIEW")
        self.assertFalse(result["base"]["result"]["policyEligible"])

    def test_empty_explicit_scenario_list_keeps_base_only(self):
        value = payload()
        value["scenarios"] = []
        self.assertEqual(LAB.analyze(value)["scenarios"], [])

    def test_malformed_command_reports_actual_block(self):
        result = LAB.analyze({"command": {}})
        self.assertEqual(result["base"]["intentOutcome"], "BLOCK")
        self.assertEqual(result["scenarios"], [])
        self.assertFalse(result["executable"])

    def test_limit_allows_sixteen_scenarios(self):
        value = payload()
        value["scenarios"] = [
            scenario(str(i), {"context.riskScore": i}) for i in range(16)
        ]
        self.assertEqual(len(LAB.analyze(value)["scenarios"]), 16)

    def test_rejects_seventeenth_scenario(self):
        value = payload()
        value["scenarios"] = [
            scenario(str(i), {"context.riskScore": i}) for i in range(17)
        ]
        with self.assertRaises(ValueError):
            LAB.analyze(value)

    def test_rejects_unknown_paths_and_authority_changes(self):
        for path in (
            "executable",
            "__class__.__dict__",
            "verification.verified",
            "principal.id",
            "resource.type",
            "context.humanApproval.extra",
            "context.__proto__",
        ):
            with self.subTest(path=path):
                value = payload()
                value["scenarios"] = [scenario("invalid", {path: True})]
                with self.assertRaises(ValueError):
                    LAB.analyze(value)

    def test_rejects_patch_type_coercion(self):
        for path, changed in (
            ("context.humanApproval", "false"),
            ("context.mfa", 1),
            ("context.riskScore", True),
            ("context.riskScore", 1.0),
            ("context.riskScore", 2**63),
            ("resource.attrs.allowedEffects", "deploy"),
            ("resource.attrs.allowedPurposes", [None]),
        ):
            with self.subTest(path=path, value=changed):
                value = payload()
                value["scenarios"] = [scenario("invalid", {path: changed})]
                with self.assertRaises(ValueError):
                    LAB.analyze(value)

    def test_rejects_missing_patch_path(self):
        value = payload()
        del value["command"]["context"]["mfa"]
        value["scenarios"] = [scenario("missing", {"context.mfa": True})]
        with self.assertRaises(ValueError):
            LAB.analyze(value)

    def test_rejects_duplicate_ids_and_unknown_scenario_keys(self):
        value = payload()
        value["scenarios"] = [scenario("same", {"context.mfa": False})] * 2
        with self.assertRaises(ValueError):
            LAB.analyze(value)
        value["scenarios"] = [
            dict(scenario("extra", {"context.mfa": False}), executable=True)
        ]
        with self.assertRaises(ValueError):
            LAB.analyze(value)

    def test_rejects_empty_changes_and_large_patch_sets(self):
        value = payload()
        value["scenarios"] = [scenario("empty", {})]
        with self.assertRaises(ValueError):
            LAB.analyze(value)
        value["scenarios"] = [
            scenario("many", dict.fromkeys(list(LAB.ALLOWED_CHANGES)[:13], True))
        ]
        with self.assertRaises(ValueError):
            LAB.analyze(value)

    def test_rejects_unrecognized_external_entity_store(self):
        value = payload()
        value["entities"] = {"principals": {"trusted": {}}}
        with self.assertRaises(ValueError):
            LAB.analyze(value)

    def test_rejects_nonfinite_and_nonjson_values(self):
        for invalid in (float("nan"), float("inf"), -float("inf"), {1, 2}, b"bytes"):
            value = payload()
            value["verification"]["value"] = invalid
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                LAB.analyze(value)

    def test_rejects_deep_and_cyclic_json(self):
        deep = {}
        node = deep
        for _ in range(LAB.MAX_DEPTH + 1):
            node["next"] = {}
            node = node["next"]
        for invalid in (deep,):
            value = payload()
            value["verification"] = invalid
            with self.assertRaises(ValueError):
                LAB.analyze(value)
        cyclic = payload()
        cyclic["verification"]["cycle"] = cyclic
        with self.assertRaises(ValueError):
            LAB.analyze(cyclic)

    def test_rejects_byte_node_and_string_amplification(self):
        for invalid in (
            {"data": "x" * (LAB.MAX_STRING_BYTES + 1)},
            {"items": [None] * (LAB.MAX_NODES + 1)},
            {str(i): "x" * 16384 for i in range(9)},
        ):
            value = payload()
            value["verification"] = invalid
            with self.assertRaises(ValueError):
                LAB.analyze(value)

    def test_bounds_expanded_report_size(self):
        value = payload()
        value["command"]["extra"] = {str(i): "x" * 8192 for i in range(8)}
        value["scenarios"] = [
            scenario(str(i), {"context.riskScore": i}) for i in range(16)
        ]
        with self.assertRaisesRegex(ValueError, "output limit"):
            LAB.analyze(value)

    def test_deterministic_across_python_hash_seeds(self):
        value = payload()
        value["command"]["principal"].update(
            tenantId="foreign", assurance=99, disabled=True
        )
        value["scenarios"] = []
        digests = []
        for seed in ("0", "1"):
            result = subprocess.run(
                [sys.executable, "-B", str(ROOT / "tools/decision_lab.py")],
                input=json.dumps(value),
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=dict(os.environ, PYTHONHASHSEED=seed),
                timeout=30,
                check=True,
            )
            digests.append(json.loads(result.stdout)["resultDigest"])
        self.assertEqual(digests[0], digests[1])


class ReplayTests(unittest.TestCase):
    def test_deepest_accepted_input_round_trips_with_capsule_envelope(self):
        value = payload()
        nested = None
        for _ in range(LAB.MAX_DEPTH - 1):
            nested = {"n": nested}
        value["verification"] = nested
        report = LAB.analyze(value)
        self.assertTrue(LAB.replay(report["replayCapsule"])["valid"])

    def test_maximum_input_nodes_round_trip_with_capsule_envelope(self):
        value = payload()
        value["verification"] = {"items": []}
        stack, count = [value], 0
        while stack:
            item = stack.pop()
            count += 1
            if isinstance(item, dict):
                stack.extend(item.values())
            elif isinstance(item, list):
                stack.extend(item)
        value["verification"]["items"] = [None] * (LAB.MAX_NODES - count)
        report = LAB.analyze(value)
        self.assertTrue(LAB.replay(report["replayCapsule"])["valid"])

    def test_replay_is_consistent_but_unauthenticated(self):
        report = LAB.analyze(payload())
        result = LAB.replay(report["replayCapsule"])
        self.assertTrue(result["valid"])
        self.assertEqual(result["current"]["resultDigest"], report["resultDigest"])
        self.assertEqual(result["issues"], [])
        self.assertFalse(result["authentic"])
        self.assertTrue(result["unsigned"])
        self.assertEqual(result["trust"], "unsigned-untrusted")
        self.assertFalse(result["executable"])

    def test_canonical_capsule_transport_preserves_float_and_int64_tokens(self):
        value = payload()
        value["verification"].update(floatClaim=1.0, integerClaim=9007199254740993)
        report = LAB.analyze(value)
        serialized = report["replayCapsuleJson"]
        self.assertEqual(
            serialized.encode("utf-8"), LAB._canonical(report["replayCapsule"])
        )
        self.assertIn('"floatClaim":1.0', serialized)
        self.assertIn('"integerClaim":9007199254740993', serialized)
        replayed = LAB.replay(json.loads(serialized))
        self.assertTrue(replayed["valid"])
        self.assertEqual(replayed["current"]["replayCapsuleJson"], serialized)

    def test_input_edit_is_detected_even_if_outcome_is_same(self):
        capsule = LAB.analyze(payload())["replayCapsule"]
        capsule["input"]["command"]["context"]["requestId"] = "edited"
        result = LAB.replay(capsule)
        self.assertFalse(result["valid"])
        self.assertIn(
            "INPUT_DIGEST_MISMATCH", {item["code"] for item in result["issues"]}
        )
        self.assertIn(
            "RESULT_DIGEST_MISMATCH", {item["code"] for item in result["issues"]}
        )

    def test_self_rehashed_input_requires_matching_full_result(self):
        capsule = LAB.analyze(payload())["replayCapsule"]
        capsule["input"]["command"]["context"]["riskScore"] = 102
        capsule["inputDigest"] = LAB._digest(capsule["input"])
        result = LAB.replay(capsule)
        self.assertFalse(result["valid"])
        self.assertEqual(
            [item["code"] for item in result["issues"]], ["RESULT_DIGEST_MISMATCH"]
        )

    def test_self_consistent_rewrite_is_still_unauthenticated(self):
        value = payload()
        value["command"]["principal"]["id"] = "self-issued-identity"
        rewritten = LAB.analyze(value)["replayCapsule"]
        result = LAB.replay(rewritten)
        self.assertTrue(result["valid"])
        self.assertFalse(result["authentic"])
        self.assertFalse(
            result["current"]["base"]["result"]["intent"]["identityAuthenticated"]
        )
        self.assertFalse(result["current"]["base"]["result"]["evidence"]["verified"])

    def test_rejects_authority_flags_and_boolean_coercion(self):
        capsule = LAB.analyze(payload())["replayCapsule"]
        for changed in (
            dict(capsule, unsigned=1),
            dict(capsule, unsigned=False),
            dict(capsule, verified=True),
            dict(capsule, executable=True),
            dict(capsule, schema="unknown"),
            dict(capsule, resultDigest=1),
        ):
            result = LAB.replay(changed)
            self.assertFalse(result["valid"])
            self.assertEqual(result["issues"][0]["code"], "CAPSULE_INVALID")
            self.assertFalse(result["executable"])

    def test_result_digest_edit_and_policy_digest_edit_detected(self):
        capsule = LAB.analyze(payload())["replayCapsule"]
        for field, code in (
            ("resultDigest", "RESULT_DIGEST_MISMATCH"),
            ("policyDigest", "POLICY_DRIFT"),
        ):
            altered = dict(capsule, **{field: "0" * 64})
            result = LAB.replay(altered)
            self.assertFalse(result["valid"])
            self.assertIn(code, {item["code"] for item in result["issues"]})

    def test_on_disk_drift_rejects_cached_runtime_and_restart_recomputes(self):
        with tempfile.TemporaryDirectory(prefix="anatomy-replay-drift-") as temp:
            module = copied_lab(temp)
            original = module.analyze(payload())
            changed = Path(temp) / "tools/authorize_intent.py"
            changed.write_bytes(
                changed.read_bytes() + b"\n# review-only drift fixture\n"
            )
            with self.assertRaisesRegex(ValueError, "changed since service startup"):
                module.analyze(payload())
            replayed = module.replay(original["replayCapsule"])
            self.assertFalse(replayed["valid"])
            self.assertIsNone(replayed["current"])
            self.assertIn(
                "POLICY_RUNTIME_STALE", {item["code"] for item in replayed["issues"]}
            )
            restarted = load(Path(temp) / "tools/decision_lab.py")
            replayed = restarted.replay(original["replayCapsule"])
            self.assertFalse(replayed["valid"])
            self.assertIsNotNone(replayed["current"])
            self.assertIn("POLICY_DRIFT", {item["code"] for item in replayed["issues"]})
            self.assertIn(
                "RESULT_DIGEST_MISMATCH", {item["code"] for item in replayed["issues"]}
            )

    def test_source_changed_during_evaluation_cannot_produce_report(self):
        with tempfile.TemporaryDirectory(prefix="anatomy-evaluation-drift-") as temp:
            module = copied_lab(temp)
            evaluate = module._evaluate
            changed = Path(temp) / "policy/cedar/intent-auth.cedar"

            def mutate_after_evaluation(command, submitted):
                result = evaluate(command, submitted)
                changed.write_bytes(
                    changed.read_bytes() + b"\n// concurrent drift fixture\n"
                )
                return result

            module._evaluate = mutate_after_evaluation
            value = payload()
            value["scenarios"] = []
            with self.assertRaisesRegex(ValueError, "changed during evaluation"):
                module.analyze(value)

    def test_source_changed_during_loading_cannot_initialize_runtime(self):
        with tempfile.TemporaryDirectory(prefix="anatomy-loading-drift-") as temp:
            copied_lab(temp)
            binder = Path(temp) / "tools/bind_anatomy.py"
            fixture = (
                b"\n_fixture_path = ROOT / 'policy/cedar/intent-auth.cedar'\n"
                b"_fixture_path.write_bytes(_fixture_path.read_bytes() + b'\\n// load drift fixture\\n')\n"
            )
            binder.write_bytes(binder.read_bytes() + fixture)
            with self.assertRaisesRegex(ValueError, "changed while loading"):
                load(Path(temp) / "tools/decision_lab.py")

    def test_fingerprint_and_execution_use_source_despite_stale_bytecode(self):
        with tempfile.TemporaryDirectory(prefix="anatomy-bytecode-drift-") as temp:
            copied_lab(temp)
            source = Path(temp) / "tools/authorize_intent.py"
            metadata = source.stat()
            py_compile.compile(str(source), doraise=True)
            content = source.read_bytes()
            changed = content.replace(
                b"principal is disabled", b"principal is DISABLED"
            )
            self.assertEqual(len(changed), len(content))
            source.write_bytes(changed)
            os.utime(source, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
            module = load(Path(temp) / "tools/decision_lab.py")
            value = payload()
            value["command"]["principal"]["disabled"] = True
            value["command"]["principal"]["attrs"]["disabled"] = True
            value["scenarios"] = []
            result = module.analyze(value)
            self.assertIn(
                "principal is DISABLED", result["base"]["result"]["intent"]["deny"]
            )

    def test_analysis_and_replay_do_not_write_files(self):
        with tempfile.TemporaryDirectory(prefix="anatomy-replay-read-") as temp:
            module = copied_lab(temp)
            root = Path(temp)
            before = {
                path.relative_to(root): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            report = module.analyze(payload())
            self.assertTrue(module.replay(report["replayCapsule"])["valid"])
            after = {
                path.relative_to(root): path.read_bytes()
                for path in root.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)

    def test_malformed_and_oversized_capsules_fail_closed(self):
        for invalid in (None, [], True, {}, {"x": "y" * (LAB.MAX_CAPSULE_BYTES + 1)}):
            result = LAB.replay(invalid)
            self.assertFalse(result["valid"])
            self.assertFalse(result["executable"])
            self.assertTrue(result["evaluationOnly"])
            self.assertEqual(result["executionAuthority"], "none")


if __name__ == "__main__":
    unittest.main()
