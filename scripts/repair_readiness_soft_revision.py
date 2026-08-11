#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

OLD_AFTER_FETCH = '''async function fetchBuildRevision() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${BASE}/api/build-info`, {
      method: "GET",
      headers: { accept: "application/json" },
      cache: "no-store",
      signal: controller.signal,
    });
    if (!response.ok) {
      throw new Error(`/api/build-info returned HTTP ${response.status}`);
    }
    const payload = await response.json();
    const revision = payload?.build?.revision || payload?.revision;
    if (typeof revision !== "string" || !SHA40.test(revision)) {
      throw new Error("/api/build-info lacks an exact source revision");
    }
    return revision;
  } finally {
    clearTimeout(timeout);
  }
}
'''

NEW_AFTER_FETCH = OLD_AFTER_FETCH + '''
async function observeBuildRevision(fetcher = fetchBuildRevision, soft = SOFT) {
  try {
    return { status: "OBSERVED", revision: await fetcher(), error: null };
  } catch (error) {
    if (!soft) throw error;
    const message = error instanceof Error ? error.message : String(error);
    return { status: "UNAVAILABLE", revision: null, error: message };
  }
}
'''

OLD_MAIN = '''  const sourceRevisionBefore = await fetchBuildRevision();
  const results = await pool(paths, CONCURRENCY, (p) => probeEndpoint(p, ENDPOINTS[p]));
  const sourceRevisionAfter = await fetchBuildRevision();
  if (sourceRevisionAfter !== sourceRevisionBefore) {
    throw new Error(
      `deployment revision changed during probe: ${sourceRevisionBefore} -> ${sourceRevisionAfter}`,
    );
  }

  const lies = results.filter((r) => r.lie);
'''

NEW_MAIN = '''  const sourceBefore = await observeBuildRevision();
  const results = await pool(paths, CONCURRENCY, (p) => probeEndpoint(p, ENDPOINTS[p]));
  const sourceAfter = await observeBuildRevision();
  let sourceRevisionStatus =
    sourceBefore.status === "OBSERVED" && sourceAfter.status === "OBSERVED"
      ? "OBSERVED"
      : "UNAVAILABLE";
  let sourceRevisionError = sourceBefore.error || sourceAfter.error || null;
  if (
    sourceRevisionStatus === "OBSERVED" &&
    sourceBefore.revision !== sourceAfter.revision
  ) {
    const message = `deployment revision changed during probe: ${sourceBefore.revision} -> ${sourceAfter.revision}`;
    if (!SOFT) throw new Error(message);
    sourceRevisionStatus = "DIVERGENT";
    sourceRevisionError = message;
  }
  const sourceRevision =
    sourceRevisionStatus === "OBSERVED" ? sourceAfter.revision : null;

  const lies = results.filter((r) => r.lie);
'''

OLD_VERDICT = '''    sourceRevision: sourceRevisionAfter,
    summary: {
'''
NEW_VERDICT = '''    sourceRevision,
    sourceRevisionStatus,
    sourceRevisionError,
    summary: {
'''

OLD_EXPORT = '''export { findTimestamp, validateSchema };'''
NEW_EXPORT = '''export { findTimestamp, observeBuildRevision, validateSchema };'''


def replace_once(text: str, old: str, new: str, name: str) -> str:
    if new in text:
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{name}: expected one source anchor, found {count}")
    return text.replace(old, new, 1)


def patch(text: str) -> str:
    text = replace_once(text, OLD_AFTER_FETCH, NEW_AFTER_FETCH, "revision observer")
    text = replace_once(text, OLD_MAIN, NEW_MAIN, "main revision handling")
    text = replace_once(text, OLD_VERDICT, NEW_VERDICT, "verdict evidence")
    text = replace_once(text, OLD_EXPORT, NEW_EXPORT, "observer export")
    return text


def validate(text: str) -> None:
    for token in (
        "async function observeBuildRevision",
        'status: "UNAVAILABLE"',
        'sourceRevisionStatus = "DIVERGENT"',
        "sourceRevisionError,",
        "observeBuildRevision, validateSchema",
    ):
        if token not in text:
            raise RuntimeError(f"required readiness token missing: {token}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    original = args.path.read_text(encoding="utf-8")
    patched = patch(original)
    validate(patched)
    if args.check and patched != original:
        print(f"readiness soft revision contract FAIL_UNAPPLIED: {args.path}")
        return 1
    if not args.check:
        args.path.write_text(patched, encoding="utf-8")
    print(f"readiness soft revision contract PASS: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
