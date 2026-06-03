# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Author: Yachay <yachay@szlholdings.dev>
# Co-Authored-By: Perplexity Computer Agent
# Change-class: ADDITIVE — Doctrine v11 LOCKED 749/14/163 UNCHANGED.
"""
szl_bridge_schemas — schema-strict tool registry for the Cross-Harness Receipt
Bridge (Hermes + OpenClaw). Mirrors packages/policy/src/tools/schemas.ts.

Every tool call that crosses the bridge — whether it arrives as a Hermes
``<tool_call>{"name":...,"arguments":{...}}</tool_call>`` ChatML envelope or an
OpenClaw tool event — MUST validate against a registered JSON Schema 2020-12
schema here. A call whose ``name`` is unknown, or whose ``arguments`` fail
schema validation, fails-CLOSED: the bridge mints a ``kind:"schema_mismatch"``
Khipu receipt and rejects the request (Sentra deny-by-default).

Each schema:
  * is JSON Schema 2020-12 (``$schema`` declared),
  * sets ``additionalProperties: false`` (no smuggled fields),
  * declares its ``required`` arguments.

This module ships a tiny, dependency-free 2020-12 subset validator so the
Space runtime never needs ``jsonschema`` installed (honest: it implements
type / required / additionalProperties / enum / minimum / maximum / minLength /
items — the keywords the registered schemas actually use; it is NOT a full
2020-12 implementation and says so).
"""
from __future__ import annotations

from typing import Any

JSON_SCHEMA_DIALECT = "https://json-schema.org/draft/2020-12/schema"

# ─────────────────────────────────────────────────────────────────────────────
# Registered tool schemas. At least 6 (search, fetch, write_file, exec,
# sign_receipt, predict). Each is JSON Schema 2020-12, additionalProperties:false.
# ─────────────────────────────────────────────────────────────────────────────

def _schema(props: dict[str, Any], required: list[str], title: str, desc: str) -> dict[str, Any]:
    return {
        "$schema": JSON_SCHEMA_DIALECT,
        "title": title,
        "description": desc,
        "type": "object",
        "additionalProperties": False,
        "required": required,
        "properties": props,
    }


TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "search": _schema(
        {
            "q": {"type": "string", "minLength": 1, "description": "Search query."},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 100},
            "recency": {"type": "string", "enum": ["day", "week", "month", "year", "any"]},
        },
        required=["q"],
        title="search",
        desc="Full-text / web search. Returns ranked results for a query string.",
    ),
    "fetch": _schema(
        {
            "url": {"type": "string", "minLength": 1, "description": "http(s) URL to fetch."},
            "max_bytes": {"type": "integer", "minimum": 1, "maximum": 10_000_000},
            "method": {"type": "string", "enum": ["GET", "HEAD"]},
        },
        required=["url"],
        title="fetch",
        desc="Fetch the contents of a URL (read-only).",
    ),
    "write_file": _schema(
        {
            "path": {"type": "string", "minLength": 1, "description": "Destination path."},
            "content": {"type": "string", "description": "UTF-8 file contents."},
            "mode": {"type": "string", "enum": ["create", "overwrite", "append"]},
        },
        required=["path", "content"],
        title="write_file",
        desc="Write content to a file. State-changing — gated by Sentra.",
    ),
    "exec": _schema(
        {
            "cmd": {"type": "string", "minLength": 1, "description": "Command to execute."},
            "args": {"type": "array", "items": {"type": "string"}},
            "timeout_s": {"type": "integer", "minimum": 1, "maximum": 3600},
        },
        required=["cmd"],
        title="exec",
        desc="Execute a sandboxed command. High severity — Sentra deny-by-default.",
    ),
    "sign_receipt": _schema(
        {
            "actor_id": {"type": "string", "minLength": 1},
            "tool_name": {"type": "string", "minLength": 1},
            "payload": {"type": "object"},
            "kind": {"type": "string", "enum": ["action", "deliberation", "channel_ingress",
                                                "exec_audit", "schema_mismatch"]},
        },
        required=["actor_id", "tool_name", "payload"],
        title="sign_receipt",
        desc="Mint a DSSE-signed Khipu receipt over an arbitrary payload.",
    ),
    "predict": _schema(
        {
            "action": {"type": "string", "minLength": 1, "description": "Action to forecast."},
            "horizon": {"type": "integer", "minimum": 1, "maximum": 1000},
            "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
        },
        required=["action"],
        title="predict",
        desc="PAC-Bayes pre-action forward-model prediction (predicted-vs-actual).",
    ),
}


def registered_tools() -> list[str]:
    return sorted(TOOL_SCHEMAS.keys())


def get_schema(name: str) -> dict[str, Any] | None:
    return TOOL_SCHEMAS.get(name)


# ─────────────────────────────────────────────────────────────────────────────
# Minimal, dependency-free JSON Schema 2020-12 subset validator.
# Implements ONLY the keywords the registered schemas use. Honest: NOT a full
# 2020-12 implementation. Returns a list of human-readable error strings (empty
# == valid).
# ─────────────────────────────────────────────────────────────────────────────

_PY_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "integer": int,
    "number": (int, float),
    "boolean": bool,
    "null": type(None),
}


def _type_ok(value: Any, t: str) -> bool:
    if t == "integer":
        # bool is a subclass of int in Python; reject bools as integers.
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if t == "boolean":
        return isinstance(value, bool)
    py = _PY_TYPES.get(t)
    return isinstance(value, py) if py else True


def _validate(value: Any, schema: dict[str, Any], path: str, errors: list[str]) -> None:
    t = schema.get("type")
    if t is not None and not _type_ok(value, t):
        errors.append(f"{path or '<root>'}: expected type {t}, got {type(value).__name__}")
        return

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path or '<root>'}: {value!r} not in enum {schema['enum']}")

    if t == "string" and isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: string shorter than minLength {schema['minLength']}")

    if t in ("number", "integer") and isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: {value} < minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: {value} > maximum {schema['maximum']}")

    if t == "array" and isinstance(value, list):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i, item in enumerate(value):
                _validate(item, item_schema, f"{path}[{i}]", errors)

    if t == "object" and isinstance(value, dict):
        props = schema.get("properties", {})
        required = schema.get("required", [])
        for req in required:
            if req not in value:
                errors.append(f"{path or '<root>'}: missing required property '{req}'")
        if schema.get("additionalProperties") is False:
            extra = set(value.keys()) - set(props.keys())
            if extra:
                errors.append(f"{path or '<root>'}: additional properties not allowed: {sorted(extra)}")
        for k, v in value.items():
            if k in props:
                _validate(v, props[k], f"{path}.{k}" if path else k, errors)


def validate_tool_call(name: str, arguments: Any) -> dict[str, Any]:
    """Validate ``arguments`` against the registered schema for tool ``name``.

    Returns {valid: bool, errors: [str], schema_title: str|None, dialect: str}.
    Fails-CLOSED: an unknown tool name is invalid (deny-by-default).
    """
    schema = TOOL_SCHEMAS.get(name)
    if schema is None:
        return {
            "valid": False,
            "errors": [f"unknown tool '{name}'; registered tools = {registered_tools()}"],
            "schema_title": None,
            "dialect": JSON_SCHEMA_DIALECT,
        }
    if not isinstance(arguments, dict):
        return {
            "valid": False,
            "errors": [f"arguments must be an object, got {type(arguments).__name__}"],
            "schema_title": schema.get("title"),
            "dialect": JSON_SCHEMA_DIALECT,
        }
    errors: list[str] = []
    _validate(arguments, schema, "", errors)
    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "schema_title": schema.get("title"),
        "dialect": JSON_SCHEMA_DIALECT,
    }


if __name__ == "__main__":
    # Self-test.
    assert validate_tool_call("search", {"q": "test"})["valid"]
    assert not validate_tool_call("search", {"q": ""})["valid"]          # minLength
    assert not validate_tool_call("search", {})["valid"]                 # required
    assert not validate_tool_call("search", {"q": "x", "bogus": 1})["valid"]  # additionalProperties
    assert not validate_tool_call("nope", {})["valid"]                   # unknown tool
    assert validate_tool_call("exec", {"cmd": "ls", "args": ["-la"], "timeout_s": 5})["valid"]
    assert not validate_tool_call("predict", {"action": "x", "confidence": 2.0})["valid"]  # maximum
    print("OK — szl_bridge_schemas self-check passed.", registered_tools())
