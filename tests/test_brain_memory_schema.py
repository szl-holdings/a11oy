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
