# SPDX-License-Identifier: Apache-2.0
# Signed-off-by: Codex <codex@openai.com>

import json

import szl_brain_memory_schema as memory


def test_portable_schema_has_governance_and_integrity_contracts():
    schema = memory.load_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    assert schema["properties"]["schema_version"]["const"] == "szl-memory/1.0"
    assert "governance" in schema["required"]
    assert "integrity" in schema["required"]


def test_example_memory_passes_executable_validator():
    record = memory.build_example_memory()
    assert memory.validate_memory_record(record) == []
    assert len(record["integrity"]["content_digest"]) == 64


def test_training_use_requires_human_review():
    record = memory.build_example_memory()
    record["governance"]["training_allowed"] = True
    assert "training_allowed requires HUMAN_REVIEWED admission" in memory.validate_memory_record(record)


def test_restricted_memory_requires_an_allowlist():
    record = memory.build_example_memory()
    record["governance"]["classification"] = "RESTRICTED"
    record["governance"]["allowed_consumers"] = []
    assert "restricted memory requires governance.allowed_consumers" in memory.validate_memory_record(record)


def test_record_is_portable_json():
    record = memory.build_example_memory()
    assert json.loads(json.dumps(record)) == record


def _schema_properties():
    schema = memory.load_schema()
    yield (), schema
    for name, definition in schema["properties"].items():
        if "properties" in definition:
            yield (name,), definition


def _object_at(record, path):
    return record if not path else record[path[0]]


def test_malformed_top_level_values_return_deterministic_errors():
    for value in (None, [], "record", True, 1, 1.0):
        assert memory.validate_memory_record(value) == ["record must be an object"]


def test_malformed_nested_objects_return_errors_without_mutation():
    for path, _ in _schema_properties():
        if not path:
            continue
        for value in (None, [], "object", True, 1, 1.0):
            record = memory.build_example_memory()
            record[path[0]] = value
            snapshot = json.dumps(record, sort_keys=True)
            errors = memory.validate_memory_record(record)
            assert errors
            assert errors == memory.validate_memory_record(record)
            assert json.dumps(record, sort_keys=True) == snapshot


def test_every_schema_required_field_is_enforced():
    for path, definition in _schema_properties():
        for field in definition["required"]:
            record = memory.build_example_memory()
            del _object_at(record, path)[field]
            name = ".".join((*path, field))
            assert f"missing required field: {name}" in memory.validate_memory_record(record)


def test_every_closed_schema_object_rejects_unknown_fields():
    for path, definition in _schema_properties():
        assert definition["additionalProperties"] is False
        record = memory.build_example_memory()
        _object_at(record, path)["unexpected"] = None
        name = ".".join((*path, "unexpected"))
        assert f"unknown field: {name}" in memory.validate_memory_record(record)


def test_unknown_field_errors_do_not_depend_on_insertion_order():
    for path, _ in _schema_properties():
        record = memory.build_example_memory()
        _object_at(record, path).update(z_extra=None, a_extra=None)
        errors = memory.validate_memory_record(record)
        record = memory.build_example_memory()
        _object_at(record, path).update(a_extra=None, z_extra=None)
        assert memory.validate_memory_record(record) == errors


def test_integrity_signature_requires_an_object():
    for value in (None, [], "signature", True, 1):
        record = memory.build_example_memory()
        record["integrity"]["signature"] = value
        assert "integrity.signature must be object" in memory.validate_memory_record(record)


def test_enum_values_reject_unhashable_and_non_string_types():
    for path, definition in _schema_properties():
        for field, rules in definition["properties"].items():
            if "enum" not in rules:
                continue
            for value in ([], {}, None, True, 1, "unsupported"):
                record = memory.build_example_memory()
                _object_at(record, path)[field] = value
                assert memory.validate_memory_record(record)


def test_declared_arrays_and_item_types_are_enforced():
    for path, definition in _schema_properties():
        for field, rules in definition["properties"].items():
            if rules.get("type") != "array":
                continue
            for value in (None, {}, "array", True, 1, ("tuple",)):
                record = memory.build_example_memory()
                _object_at(record, path)[field] = value
                assert memory.validate_memory_record(record)
            wrong_items = (None, [], 1, True)
            wrong_items += ({},) if rules["items"]["type"] == "string" else ("string",)
            for item in wrong_items:
                record = memory.build_example_memory()
                _object_at(record, path)[field] = [item]
                assert memory.validate_memory_record(record)


def test_declared_string_fields_reject_non_string_values():
    for path, definition in _schema_properties():
        for field, rules in definition["properties"].items():
            if rules.get("type") != "string":
                continue
            for value in (None, [], {}, True, 1):
                record = memory.build_example_memory()
                _object_at(record, path)[field] = value
                assert memory.validate_memory_record(record)


def test_boolean_fields_require_booleans():
    for field in ("human_review_required", "propagation_allowed", "training_allowed", "export_allowed"):
        for value in ("false", "true", 0, 1, None, [], {}):
            record = memory.build_example_memory()
            record["governance"][field] = value
            assert memory.validate_memory_record(record)


def test_numbers_reject_booleans_wrong_types_and_non_finite_values():
    fields = (
        ("epistemic_state", "confidence"), ("usage", "measured_utility"),
        ("usage", "retrieval_count"), ("usage", "successful_outcomes"),
        ("usage", "failed_outcomes"),
    )
    for path, field in fields:
        for value in (True, False, "1", None, [], {}, float("nan"), float("inf"), float("-inf")):
            record = memory.build_example_memory()
            record[path][field] = value
            assert memory.validate_memory_record(record)
    for field in ("retrieval_count", "successful_outcomes", "failed_outcomes"):
        record = memory.build_example_memory()
        record["usage"][field] = 1.0
        assert memory.validate_memory_record(record)


def test_existing_length_and_number_bounds_remain_enforced():
    invalid_fields = (
        ((), "memory_id", "short"), ((), "tenant_id", " "),
        (("content",), "summary", " "),
        (("provenance",), "extraction_method", ""),
        (("provenance",), "created_by", ""),
        (("provenance",), "sources", []),
        (("governance",), "retention_policy", ""),
        (("epistemic_state",), "confidence", -0.01),
        (("epistemic_state",), "confidence", 1.01),
        (("usage",), "measured_utility", -1.01),
        (("usage",), "measured_utility", 1.01),
        (("integrity",), "content_digest", "short"),
    )
    for path, field, value in invalid_fields:
        record = memory.build_example_memory()
        _object_at(record, path)[field] = value
        assert memory.validate_memory_record(record)
    for field in memory.REQUIRED_SCOPE:
        record = memory.build_example_memory()
        record["scope"][field] = " "
        assert memory.validate_memory_record(record)
    for field in ("retrieval_count", "successful_outcomes", "failed_outcomes"):
        record = memory.build_example_memory()
        record["usage"][field] = -1
        assert memory.validate_memory_record(record)


def test_timestamp_types_follow_existing_schema_without_new_format_rules():
    fields = (
        ("provenance", "observed_at", False), ("provenance", "ingested_at", False),
        ("governance", "expires_at", True), ("usage", "last_retrieved_at", True),
    )
    for path, field, nullable in fields:
        for value in ([], {}, True, 123):
            record = memory.build_example_memory()
            record[path][field] = value
            assert memory.validate_memory_record(record)
        record = memory.build_example_memory()
        record[path][field] = "not-a-timestamp"
        assert memory.validate_memory_record(record) == []
        record[path][field] = None
        assert bool(memory.validate_memory_record(record)) is (not nullable)
    for value in (False, 1, [], {}):
        record = memory.build_example_memory()
        record["integrity"]["previous_version_digest"] = value
        assert memory.validate_memory_record(record)


def test_unsupported_contract_versions_are_rejected_explicitly():
    for version in ("szl-memory/2.0", "prototype", "", None, [], {}, True):
        record = memory.build_example_memory()
        record["schema_version"] = version
        assert memory.validate_memory_record(record) == [
            "unsupported schema_version: only szl-memory/1.0 is supported"
        ]
    raw_candidate = {"fact_id": "synthetic", "subject": "fixture", "predicate": "state", "object": "A"}
    assert memory.validate_memory_record(raw_candidate)


def test_existing_governance_invariants_remain_enforced():
    record = memory.build_example_memory()
    record["type"] = "WORKING"
    assert "WORKING memory cannot propagate across ecosystem boundaries" in memory.validate_memory_record(record)
    record = memory.build_example_memory()
    record["governance"].update(training_allowed=True, admission_policy="HUMAN_REVIEWED")
    assert "training_allowed requires HUMAN_REVIEWED admission" in memory.validate_memory_record(record)
    record["governance"]["human_review_required"] = True
    assert memory.validate_memory_record(record) == []


def test_valid_v1_variants_and_free_form_objects_remain_valid():
    record = memory.build_example_memory()
    record["content"]["relations"] = [{"custom_relation": {"details": [None, 1]}}]
    record["integrity"]["signature"] = {"unverified": "synthetic"}
    record["integrity"]["previous_version_digest"] = "prior"
    record["provenance"].update(extraction_method=" ", created_by=" ")
    record["governance"].update(retention_policy=" ", expires_at=None)
    record["epistemic_state"]["confidence"] = 0
    record["usage"].update(retrieval_count=1, successful_outcomes=2, failed_outcomes=3, measured_utility=-1)
    snapshot = json.dumps(record, sort_keys=True)
    assert memory.validate_memory_record(record) == []
    assert json.dumps(record, sort_keys=True) == snapshot
    record["epistemic_state"]["confidence"] = 1
    record["usage"]["measured_utility"] = 1
    assert memory.validate_memory_record(record) == []


def test_structural_validity_does_not_mean_admission_or_signature_verification():
    record = memory.build_example_memory()
    record["governance"]["admission_policy"] = "REJECTED"
    record["integrity"]["content_digest"] = "z" * 64
    record["integrity"]["signature"] = {"unverified": "synthetic"}
    assert memory.validate_memory_record(record) == []
    assert "structural validity only" in memory.validate_memory_record.__doc__
