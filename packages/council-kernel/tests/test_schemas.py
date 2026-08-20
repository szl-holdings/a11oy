from __future__ import annotations

import json
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = (
    ROOT / "schemas" / "evaluation-input.schema.json",
    ROOT / "schemas" / "decision-record.schema.json",
)


def walk(value: object):
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


class SchemaTests(unittest.TestCase):
    def test_schemas_are_draft_2020_12_json(self) -> None:
        for path in SCHEMAS:
            with self.subTest(path=path.name):
                schema = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(
                    schema["$schema"],
                    "https://json-schema.org/draft/2020-12/schema",
                )
                self.assertTrue(schema["$id"].startswith("urn:a11oy:council:"))

    def test_all_schema_references_are_internal(self) -> None:
        for path in SCHEMAS:
            schema = json.loads(path.read_text(encoding="utf-8"))
            references = [
                node["$ref"]
                for node in walk(schema)
                if isinstance(node, dict) and "$ref" in node
            ]
            with self.subTest(path=path.name):
                self.assertTrue(references)
                self.assertTrue(all(reference.startswith("#/") for reference in references))

    def test_object_boundaries_are_explicit(self) -> None:
        for path in SCHEMAS:
            schema = json.loads(path.read_text(encoding="utf-8"))
            object_nodes = [
                node
                for node in walk(schema)
                if isinstance(node, dict) and node.get("type") == "object"
            ]
            with self.subTest(path=path.name):
                self.assertTrue(object_nodes)
                self.assertTrue(
                    all("additionalProperties" in node for node in object_nodes),
                    "every object boundary must declare its additional-property policy",
                )


if __name__ == "__main__":
    unittest.main()
