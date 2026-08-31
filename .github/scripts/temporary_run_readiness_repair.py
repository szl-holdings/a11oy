#!/usr/bin/env python3
from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

TARGET = Path(".github/scripts/temporary_apply_readiness_contract_repair.py")
NODE_TEST = Path("tools/readiness-harness/probe_runner.test.mjs")


def load_target():
    spec = importlib.util.spec_from_file_location("temporary_readiness_repair", TARGET)
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load the reviewed readiness constructor")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class AstEntryPattern:
    def subn(self, replacement: str, text: str, count: int = 1):
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


def patch_node_test() -> None:
    source = NODE_TEST.read_text(encoding="utf-8")
    old = '''test("router-stats schema requires truthful modeled tier-display signals", () => {
  const modeled = {
    state: "MODELED",
    mode: "modeled",
    catalog_state: "LIVE",
    throughput_state: "MODELED",
    routes: [{ tier: "T0", model: "alpha", modeled_load: 0 }],
    servedThisWindow: 0,
    tiers: ["T0"],
    source: "szl_brain.TIERS",
    doctrine: "v11",
    honesty: "Deterministic tier-display signals; not QPS or observed traffic.",
  };
  assert.equal(validateSchema("router_stats", modeled).ok, true);
  assert.equal(validateSchema("router_stats", { ...modeled, state: "LIVE" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...modeled, throughput_state: "OBSERVED" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...modeled, source: "szl_llm_registry.router_stats_snapshot" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...modeled, routes: [] }).ok, false);
  assert.equal(validateSchema("router_stats", { ...modeled, servedThisWindow: -1 }).ok, false);
  assert.equal(validateSchema("router_stats", { ...modeled, servedThisWindow: 0.5 }).ok, false);
});'''
    new = '''test("router-stats schema requires observed process-lifetime counters", () => {
  const observed = {
    state: "LIVE",
    mode: "live",
    data_kind: "live",
    catalog_state: "LIVE",
    throughput_state: "OBSERVED",
    routes: [{ tier: "T0", model: "alpha", decisions_since_start: 0 }],
    servedThisWindow: 0,
    routingDecisionsSinceStart: 0,
    tiers: ["T0"],
    counter_scope: "process-lifetime",
    counter_started_at: "2026-08-31T00:00:00Z",
    observed_at: "2026-08-31T00:01:00Z",
    source: "szl_llm_registry.router_stats_snapshot",
    doctrine: "v11",
    honesty: "Observed routing-decision counters; not QPS, tokens, or inference completions.",
  };
  assert.equal(validateSchema("router_stats", observed).ok, true);
  assert.equal(validateSchema("router_stats", { ...observed, state: "MODELED" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, throughput_state: "MODELED" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, source: "szl_brain.TIERS" }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, routes: [] }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, servedThisWindow: -1 }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, servedThisWindow: 0.5 }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, routingDecisionsSinceStart: -1 }).ok, false);
  assert.equal(validateSchema("router_stats", { ...observed, counter_started_at: "not-a-time" }).ok, false);

  const unavailable = {
    state: "UNAVAILABLE",
    mode: "unavailable",
    data_kind: "unavailable",
    catalog_state: "UNAVAILABLE",
    throughput_state: "UNAVAILABLE",
    routes: [],
    servedThisWindow: null,
    routingDecisionsSinceStart: null,
    tiers: [],
    counter_scope: "process-lifetime",
    counter_started_at: null,
    observed_at: "2026-08-31T00:01:00Z",
    source: "unavailable",
    doctrine: "v11",
    honesty: "Registry unavailable; no replacement counter is fabricated.",
  };
  assert.equal(validateSchema("router_stats", unavailable).ok, true);
});'''
    if source.count(old) != 1:
        raise SystemExit(
            f"obsolete Node router fixture count must be 1, observed {source.count(old)}"
        )
    NODE_TEST.write_text(source.replace(old, new, 1), encoding="utf-8", newline="\n")


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
        patch_node_test()
    finally:
        module.re.compile = original_compile


if __name__ == "__main__":
    main()
