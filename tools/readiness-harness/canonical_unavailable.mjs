// SPDX-License-Identifier: Apache-2.0
// Sidecar for tools/readiness-harness/probe_runner.mjs.
// Nested freshness.status=UNAVAILABLE is honest only on the exact
// canonical unavailable envelope. Do not expand allowLabels.

export function sourceOwningFreshnessStatus(body, path, valueAtPath) {
  const text = String(path || "");
  const suffix = "freshness.status";
  const lower = text.toLowerCase();
  if (lower === suffix) return body;
  if (!lower.endsWith("." + suffix)) return null;
  const prefix = text.slice(0, text.length - (suffix.length + 1));
  if (!prefix || prefix.includes("[")) return null;
  const candidate = valueAtPath(body, prefix);
  return candidate.found ? candidate.value : null;
}

export function canonicalUnavailableStatus(entry, body, helpers) {
  const { valueAtPath, isCanonicalUnavailableSource } = helpers;
  return (
    entry.normalized === "unavailable"
    && /(^|\.)freshness\.status$/i.test(entry.path)
    && isCanonicalUnavailableSource(
      sourceOwningFreshnessStatus(body, entry.path, valueAtPath),
    )
  );
}
