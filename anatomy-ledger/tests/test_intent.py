#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Regression tests for strict advisory intent and evidence composition."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "tools" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


AUTH = load("authorize_intent")
BIND = load("bind_anatomy")
DIGEST = "a" * 64
STATEMENT = {
    "_type": "https://in-toto.io/Statement/v1",
    "subject": [{"name": "demo", "digest": {"sha256": DIGEST}}],
    "predicateType": "https://slsa.dev/provenance/v1",
    "predicate": {
        "buildDefinition": {"buildType": "https://example.invalid/build"},
        "runDetails": {"builder": {"id": "https://example.invalid/builder"}},
    },
}


def request(action="DeployArtifact", **kwargs):
    defaults = dict(
        principal_id="agent:operator-01",
        action=action,
        resource_id="deployment:production",
        purpose="release-approved-artifact",
        intended_effect="deploy",
        risk_score=250,
        human_approval=True,
        mfa=True,
        evidence_digest=BIND.statement_digest(STATEMENT),
    )
    defaults.update(kwargs)
    return BIND.intent_from_command(**defaults)


class IntentTests(unittest.TestCase):
    def assertBlocked(self, value, entities=None):
        result = AUTH.authorize(value, entities)
        self.assertEqual(result["outcome"], "BLOCK", result)
        self.assertTrue(result["deny"])
        self.assertIs(result["executable"], False)
        self.assertIs(result["evaluationOnly"], True)

    def test_valid_request_is_advisory_only(self):
        result = AUTH.authorize(request())
        self.assertEqual(result["outcome"], "ALLOW")
        self.assertIs(result["policyEligible"], True)
        self.assertIs(result["executable"], False)
        self.assertIs(result["identityAuthenticated"], False)
        self.assertIs(result["cedarExecuted"], False)

    def test_read_without_approval_is_advisory_allow(self):
        result = AUTH.authorize(
            request("ReadResource", human_approval=False, mfa=False, evidence_digest="")
        )
        self.assertEqual(result["outcome"], "ALLOW")

    def test_unknown_action_type_and_identity(self):
        for entity in ("principal", "action", "resource"):
            for key, value in (
                ("type", "Unknown"),
                ("type", []),
                ("id", ""),
                ("id", None),
                ("id", []),
            ):
                with self.subTest(entity=entity, key=key, value=value):
                    altered = request()
                    altered[entity][key] = value
                    self.assertBlocked(altered)

    def test_unknown_action(self):
        self.assertBlocked(request("DeleteEverything"))

    def test_empty_tenants(self):
        for value in ("", " ", None, 0, False):
            with self.subTest(value=value):
                self.assertBlocked(request(tenant_id=value))

    def test_cross_tenant(self):
        altered = request()
        altered["resource"]["tenantId"] = "foreign"
        altered["resource"]["attrs"]["tenantId"] = "foreign"
        self.assertBlocked(altered)

    def test_disabled_principal(self):
        self.assertBlocked(request(disabled=True))

    def test_boolean_strings_do_not_approve(self):
        for field in ("humanApproval", "mfa"):
            for value in ("false", "true", 1, 0, [], {}, None):
                with self.subTest(field=field, value=value):
                    altered = request()
                    altered["context"][field] = value
                    self.assertBlocked(altered)

    def test_disabled_must_be_boolean(self):
        for value in ("false", 0, 1, None):
            self.assertBlocked(request(disabled=value))

    def test_boolean_and_float_are_not_integer_scores(self):
        for field in ("riskScore",):
            for value in (
                True,
                False,
                1.0,
                1.9,
                "1",
                "0",
                None,
                -1,
                2**63,
                float("nan"),
                float("inf"),
            ):
                with self.subTest(field=field, value=value):
                    altered = request()
                    altered["context"][field] = value
                    self.assertBlocked(altered)

    def test_resource_and_assurance_numeric_types(self):
        for field in ("assurance", "required_assurance", "max_risk"):
            for value in (True, 0.0, "3", -1, 2**63, None):
                with self.subTest(field=field, value=value):
                    self.assertBlocked(request(**{field: value}))

    def test_risk_and_assurance_bounds(self):
        self.assertBlocked(request(risk_score=401))
        self.assertBlocked(request(assurance=0))

    def test_malformed_collections_do_not_raise(self):
        for field in ("allowed_purposes", "allowed_effects"):
            for value in ("deploy", {}, [None], [[]], [1], [], [""]):
                with self.subTest(field=field, value=value):
                    self.assertBlocked(request(**{field: value}))

    def test_explicit_empty_allowlist_stays_empty(self):
        value = request(allowed_purposes=[], allowed_effects=[])
        self.assertEqual(value["resource"]["attrs"]["allowedPurposes"], [])
        self.assertEqual(value["resource"]["attrs"]["allowedEffects"], [])
        self.assertBlocked(value)

    def test_required_context_cannot_be_omitted(self):
        for field in AUTH.CONTEXT_FIELDS:
            with self.subTest(field=field):
                altered = request()
                del altered["context"][field]
                self.assertBlocked(altered)

    def test_required_attributes_cannot_be_omitted(self):
        for entity, fields in (
            ("principal", AUTH.PRINCIPAL_FIELDS),
            ("resource", AUTH.RESOURCE_FIELDS),
        ):
            for field in fields:
                with self.subTest(entity=entity, field=field):
                    altered = request()
                    del altered[entity]["attrs"][field]
                    self.assertBlocked(altered)

    def test_malformed_top_level_never_raises(self):
        for value in (None, [], "", 1, True, {}, {"principal": []}, {"context": []}):
            self.assertBlocked(value)

    def test_alias_conflict_denies(self):
        altered = request()
        altered["principal"]["assurance"] = 100
        self.assertBlocked(altered)

    def test_unknown_attributes_denied(self):
        altered = request()
        altered["principal"]["attrs"]["isAdministrator"] = True
        self.assertBlocked(altered)

    def test_supplied_store_is_authoritative(self):
        value = request()
        entities = {
            "principals": {
                value["principal"]["id"]: copy.deepcopy(value["principal"]["attrs"])
            },
            "resources": {
                value["resource"]["id"]: copy.deepcopy(value["resource"]["attrs"])
            },
        }
        self.assertEqual(AUTH.authorize(value, entities)["outcome"], "ALLOW")
        entities["principals"][value["principal"]["id"]]["disabled"] = True
        self.assertBlocked(value, entities)
        self.assertBlocked(value, {})

    def test_unknown_identity_cannot_inject_inline_attrs(self):
        value = request()
        entities = {"principals": {}, "resources": {}}
        self.assertBlocked(value, entities)

    def test_cedar_entities_json_supported(self):
        entities = json.loads((ROOT / "policy/cedar/entities.json").read_text())
        value = json.loads(
            (ROOT / "policy/cedar/requests/deploy-allow.json").read_text()
        )
        self.assertEqual(AUTH.authorize(value, entities)["outcome"], "ALLOW")
        value["principal"]["id"] = "agent:unknown"
        self.assertBlocked(value, entities)

    def test_cedar_read_allow_fixture(self):
        entities = json.loads((ROOT / "policy/cedar/entities.json").read_text())
        value = json.loads(
            (ROOT / "policy/cedar/requests/read-allow.json").read_text()
        )
        result = AUTH.authorize(value, entities)
        self.assertEqual(result["outcome"], "ALLOW", result)
        self.assertIs(result["executable"], False)

    def test_cedar_untrusted_and_cross_tenant_fixtures_block(self):
        entities = json.loads((ROOT / "policy/cedar/entities.json").read_text())
        for name in ("untrusted-block.json", "cross-tenant-block.json"):
            with self.subTest(name=name):
                value = json.loads(
                    (ROOT / "policy/cedar/requests" / name).read_text()
                )
                self.assertBlocked(value, entities)

    def test_malformed_entity_store_denied(self):
        for entities in (
            "invalid",
            1,
            {"principals": []},
            [None],
            [{"uid": {"type": []}}],
        ):
            self.assertBlocked(request(), entities)

    def test_invoke_tool_requires_approval(self):
        self.assertBlocked(request("InvokeTool", human_approval=False))
        self.assertBlocked(request("InvokeTool", mfa=False))

    def test_resource_approval_applies_to_read(self):
        value = request("ReadResource", human_approval=False, mfa=False)
        value["resource"]["attrs"]["requiresApproval"] = True
        self.assertBlocked(value)

    def test_unrecognized_zone_denied(self):
        for zone in ("untrusted", "internet", "", None, []):
            altered = request()
            altered["context"]["networkZone"] = zone
            self.assertBlocked(altered)

    def test_digest_must_be_sha256(self):
        for digest in ("", "abc", 123, "a" * 63, "a" * 65, "g" * 64, "a" * 64 + "\n"):
            self.assertBlocked(request(evidence_digest=digest))


class BindTests(unittest.TestCase):
    def test_missing_evidence_does_not_authorize(self):
        result = BIND.bind(command=request())
        self.assertIs(result["executable"], False)
        self.assertIs(result["policyEligible"], False)
        self.assertIs(result["evaluationOnly"], True)
        self.assertIs(result["evidenceBinding"]["valid"], False)

    def test_forged_verification_cannot_authorize(self):
        result = BIND.bind(
            command=request(), statement=STATEMENT, verification={"verified": True}
        )
        self.assertIs(result["executable"], False)
        self.assertIs(result["policyEligible"], False)
        self.assertIs(result["evidence"]["verified"], False)
        self.assertEqual(result["evidence"]["outcome"], "REVIEW")
        self.assertIs(result["evidenceBinding"]["valid"], True)

    def test_review_does_not_authorize(self):
        result = BIND.bind(
            command=request(), statement=STATEMENT, verification={"verified": False}
        )
        self.assertIs(result["executable"], False)
        self.assertIs(result["policyEligible"], False)

    def test_mutated_statement_breaks_binding(self):
        statement = copy.deepcopy(STATEMENT)
        statement["predicate"]["runDetails"]["builder"]["id"] = "changed"
        result = BIND.bind(
            command=request(), statement=statement, verification={"verified": True}
        )
        self.assertIs(result["evidenceBinding"]["valid"], False)
        self.assertIs(result["policyEligible"], False)
        self.assertIs(result["executable"], False)

    def test_artifact_subject_digest_is_not_statement_digest(self):
        result = BIND.bind(command=request(evidence_digest=DIGEST), statement=STATEMENT)
        self.assertIs(result["evidenceBinding"]["valid"], False)

    def test_digest_ignores_object_order(self):
        reversed_statement = dict(reversed(list(STATEMENT.items())))
        self.assertEqual(
            BIND.statement_digest(STATEMENT), BIND.statement_digest(reversed_statement)
        )

    def test_nonascii_digest_matches_verifier_canonicalization(self):
        statement = copy.deepcopy(STATEMENT)
        statement["subject"][0]["name"] = "evidencia-\u00f1-\u03bb"
        canonical = json.dumps(
            statement,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        self.assertEqual(
            BIND.statement_digest(statement), hashlib.sha256(canonical).hexdigest()
        )

    def test_prefixed_uppercase_digest_supported(self):
        value = request(
            evidence_digest="sha256:" + BIND.statement_digest(STATEMENT).upper()
        )
        result = BIND.bind(command=value, statement=STATEMENT)
        self.assertIs(result["evidenceBinding"]["valid"], True)
        self.assertIs(result["executable"], False)

    def test_malformed_command_does_not_raise_or_authorize(self):
        for value in (None, [], {}, {"context": []}):
            result = BIND.bind(command=value)
            self.assertIs(result["executable"], False)
            self.assertIs(result["policyEligible"], False)

    def test_projection_ignores_caller_verification(self):
        result = BIND.project_statement(
            STATEMENT, {"verified": True, "signatureValid": True}
        )
        self.assertIs(result["verification"]["verified"], False)

    def test_unserializable_statement_does_not_bind(self):
        statement = dict(STATEMENT, extra=float("nan"))
        result = BIND.bind(command=request(), statement=statement)
        self.assertIs(result["evidenceBinding"]["valid"], False)
        self.assertIs(result["executable"], False)


if __name__ == "__main__":
    unittest.main()
