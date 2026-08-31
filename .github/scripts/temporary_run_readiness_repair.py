#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

TARGET = Path(".github/scripts/temporary_apply_readiness_contract_repair.py")


def load_target():
    spec = importlib.util.spec_from_file_location("temporary_readiness_repair", TARGET)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load the reviewed readiness constructor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AstEntryPattern:
    def subn(self, text: str, replacement: str, count: int = 1):
        if count != 1:
            raise SystemExit("router schema replacement must remain single-shot")
        tree = ast.parse(text)
        dictionaries = []
        for node in tree.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            target = node.targets[0]
            if isinstance(target, ast.Name) and target.id == "SCHEMAS":
                if not isinstance(node.value, ast.Dict):
                    raise SystemExit("SCHEMAS is no longer a literal dictionary")
                dictionaries.append(node.value)
        if len(dictionaries) != 1:
            raise SystemExit(f"expected one SCHEMAS dictionary, observed {len(dictionaries)}")

        matches = []
        for key, value in zip(dictionaries[0].keys, dictionaries[0].values, strict=True):
            if isinstance(key, ast.Constant) and key.value == "router_stats":
                matches.append((key, value))
        if len(matches) != 1:
            raise SystemExit(f"expected one router_stats schema, observed {len(matches)}")
        key, value = matches[0]
        predecessor = ast.literal_eval(value)
        properties = predecessor.get("properties") if isinstance(predecessor, dict) else None
        if (
            not isinstance(properties, dict)
            or properties.get("state") != {"const": "MODELED"}
            or properties.get("throughput_state") != {"const": "MODELED"}
        ):
            raise SystemExit("router_stats is not the reviewed obsolete modeled schema")
        if key.lineno is None or value.end_lineno is None:
            raise SystemExit("AST source coordinates are unavailable")

        lines = text.splitlines(keepends=True)
        start = key.lineno - 1
        stop = value.end_lineno
        if lines[stop - 1].strip() != "},":
            raise SystemExit("router_stats no longer owns an exact trailing-comma line")
        updated = "".join(lines[:start]) + replacement + "".join(lines[stop:])
        return updated, 1


def main() -> None:
    module = load_target()
    original_compile = module.re.compile

    def compile_with_ast(pattern, flags=0):
        if isinstance(pattern, str) and "router_stats" in pattern and "feeds_pulse" in pattern:
            return AstEntryPattern()
        return original_compile(pattern, flags)

    module.re.compile = compile_with_ast
    try:
        module.main()
    finally:
        module.re.compile = original_compile


if __name__ == "__main__":
    main()
