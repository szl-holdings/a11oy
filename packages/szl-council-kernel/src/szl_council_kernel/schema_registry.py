from __future__ import annotations

import json
from importlib.resources import files
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

_SCHEMA_FILES = {
    "autonomy-envelope": "autonomy-envelope-v1.schema.json",
    "capability-grant": "capability-grant-v1.schema.json",
    "council-case": "council-case-v1.schema.json",
    "council-policy": "council-policy-v1.schema.json",
    "council-identity": "council-identity-v1.schema.json",
    "council-assessment": "council-assessment-v1.schema.json",
    "council-commitment": "council-commitment-v1.schema.json",
    "council-registry": "council-registry-v1.schema.json",
    "council-result": "council-result-v1.schema.json",
    "council-settlement": "council-settlement-v2.schema.json",
    "dsse-envelope": "dsse-envelope-v1.schema.json",
    "epistemic-diversity-report": "epistemic-diversity-report-v1.schema.json",
    "act-escalate-gate-result": "act-escalate-gate-result-v1.schema.json",
    "action-request": "action-request-v1.schema.json",
    "action-receipt": "action-receipt-v1.schema.json",
    "state-event": "state-event-v1.schema.json",
    "research-artifact": "research-artifact-v1.schema.json",
    "deliberation-graph": "deliberation-graph-v1.schema.json",
}


def schema_names() -> tuple[str, ...]:
    return tuple(sorted(_SCHEMA_FILES))


def load_schema(name: str) -> dict[str, Any]:
    if name not in _SCHEMA_FILES:
        raise KeyError(name)
    resource = files("szl_council_kernel.schemas").joinpath(_SCHEMA_FILES[name])
    schema = json.loads(resource.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def validate_schema_instance(name: str, value: Any) -> None:
    Draft202012Validator(load_schema(name), format_checker=FormatChecker()).validate(value)
