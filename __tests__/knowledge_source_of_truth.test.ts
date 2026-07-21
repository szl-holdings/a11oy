import * as fs from "fs";
import * as path from "path";

import {
  KNOWLEDGE_SCHEMA_PATH,
  REPOSITORY_ROOT,
  VERTICAL_POLICIES_DIR,
} from "./support/knowledge_paths";

const ROOT_SCHEMA_ALIAS = path.join(
  REPOSITORY_ROOT,
  "a11oy-knowledge.schema.json",
);
const ROOT_POLICIES_ALIAS = path.join(REPOSITORY_ROOT, "policies", "vertical");

describe("knowledge schema source of truth", () => {
  test("the canonical schema is a real, parseable JSON file", () => {
    const schemaStat = fs.lstatSync(KNOWLEDGE_SCHEMA_PATH);
    expect(schemaStat.isFile()).toBe(true);
    expect(schemaStat.isSymbolicLink()).toBe(false);

    const schema = JSON.parse(fs.readFileSync(KNOWLEDGE_SCHEMA_PATH, "utf8"));
    expect(schema.$id).toBe(
      "https://doctrine-v6.ai/schemas/a11oy-knowledge.schema.json",
    );
    expect(schema.type).toBe("object");
  });

  test("the canonical vertical-policy directory is directly addressable", () => {
    const policiesStat = fs.lstatSync(VERTICAL_POLICIES_DIR);
    expect(policiesStat.isDirectory()).toBe(true);
    expect(policiesStat.isSymbolicLink()).toBe(false);

    const policies = fs
      .readdirSync(VERTICAL_POLICIES_DIR)
      .filter((name) => name.endsWith(".yaml"));
    expect(policies).toHaveLength(10);
  });

  test("fragile root symlink aliases stay absent on every host", () => {
    expect(fs.existsSync(ROOT_SCHEMA_ALIAS)).toBe(false);
    expect(fs.existsSync(ROOT_POLICIES_ALIAS)).toBe(false);
  });

  test("test consumers cannot drift back to root aliases", () => {
    const suites = ["compliance", "adversarial"].flatMap((directory) => {
      const absolute = path.join(REPOSITORY_ROOT, "__tests__", directory);
      return fs
        .readdirSync(absolute)
        .filter((name) => name.endsWith(".test.ts"))
        .map((name) => path.join(absolute, name));
    });

    for (const suite of suites) {
      const source = fs.readFileSync(suite, "utf8");
      expect(source).not.toContain('../../a11oy-knowledge.schema.json');
      expect(source).not.toContain('../../policies/vertical');
    }
  });
});
