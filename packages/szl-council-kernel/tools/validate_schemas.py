#!/usr/bin/env python3
from __future__ import annotations

import json
import tempfile
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from szl_council_kernel.canary import run_canary
from szl_council_kernel.fourfold import COMMITMENT_CONTENT_TYPE
from szl_council_kernel.proof import PublicVerifier, verify_signed_object
from szl_council_kernel.schema_registry import load_schema, schema_names, validate_schema_instance


def main() -> int:
    errors: list[dict[str, str]] = []
    validated_instances: list[str] = []
    for name in schema_names():
        try:
            schema = load_schema(name)
            Draft202012Validator.check_schema(schema)
            Draft202012Validator(schema, format_checker=FormatChecker())
        except Exception as exc:
            errors.append({"schema": name, "error": f"{type(exc).__name__}:{exc}"})

    if not errors:
        try:
            with tempfile.TemporaryDirectory(prefix="szl-schema-canary-") as temporary:
                report = run_canary(Path(temporary) / "run")
                settlement = report["run"]["council"]
                instances = {
                    "council-settlement": settlement,
                    "council-case": settlement["case"],
                    "council-policy": settlement["policy"],
                    "council-registry": settlement["registry"],
                    "council-result": settlement["result"],
                    "epistemic-diversity-report": settlement["result"]["diversity"],
                    "dsse-envelope": settlement["signed_result"],
                    "act-escalate-gate-result": report["run"]["gate"],
                }
                for name, value in instances.items():
                    validate_schema_instance(name, value)
                    validated_instances.append(name)
                for index, identity in enumerate(settlement["registry"]["identities"]):
                    validate_schema_instance("council-identity", identity)
                    validated_instances.append(f"council-identity:{index}")
                authority = settlement["registry"]["identities"][0]
                commitment = verify_signed_object(
                    settlement["commitments"]["AUTHORITY"],
                    PublicVerifier(key_id=authority["key_id"], public_key=authority["public_key"]),
                    expected_payload_type=COMMITMENT_CONTENT_TYPE,
                )
                validate_schema_instance("council-commitment", commitment)
                validated_instances.append("council-commitment")
                validate_schema_instance(
                    "council-assessment", settlement["reveals"]["AUTHORITY"]["assessment"]
                )
                validated_instances.append("council-assessment")
        except Exception as exc:
            errors.append({"schema": "instance-conformance", "error": f"{type(exc).__name__}:{exc}"})

    report = {
        "schema": "szl.schema-validation/v2",
        "status": "PASS" if not errors else "FAIL",
        "schema_count": len(schema_names()),
        "validated_instance_count": len(validated_instances),
        "validated_instances": validated_instances,
        "errors": errors,
    }
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
