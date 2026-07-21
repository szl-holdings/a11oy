import * as path from "path";

/**
 * Cross-platform locations for the canonical vertical-policy contract.
 *
 * Do not reintroduce root-level symlinks. Git checks them out as ordinary
 * pointer-text files when core.symlinks=false (the default on many Windows
 * hosts), which makes JSON and directory consumers fail in a misleading way.
 */
export const REPOSITORY_ROOT = path.resolve(__dirname, "../..");

export const KNOWLEDGE_SCHEMA_PATH = path.join(
  REPOSITORY_ROOT,
  "packages",
  "knowledge",
  "a11oy-knowledge.schema.json",
);

export const VERTICAL_POLICIES_DIR = path.join(
  REPOSITORY_ROOT,
  "packages",
  "knowledge",
  "vertical",
);
