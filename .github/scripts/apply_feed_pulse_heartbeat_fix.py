#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply the bounded feed-pulse heartbeat freshness repair.

This temporary branch helper makes two exact, fail-closed edits and then
regenerates the committed readiness matrix. It is removed by the workflow that
executes it, so the resulting PR contains only the reviewed product changes.
"""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "tools" / "readiness-harness" / "gen_tabs_matrix.py"
TEST_FILE = ROOT / "tools" / "readiness-harness" / "probe_runner.test.mjs"
TABS = ROOT / "tools" / "readiness-harness" / "tabs.json"

OLD_SCHEMA = (
    '    "feeds_pulse": {"type": "object", '
    '"anyKey": ["items", "feed_count", "live_count"]},'
)
NEW_SCHEMA = '''    "feeds_pulse": {
        "type": "object",
        "anyKey": ["items", "feed_count", "live_count"],
        # The endpoint is a current liveness/provenance heartbeat. Its child
        # rows retain original fetched_at clocks and cached/down labels, while
        # the endpoint SLA grades the explicit current probe observation.
        "requiredPathTypes": {"probed_at": "timestamp"},
    },'''

TEST_MARKER = "feed pulse freshness grades its current heartbeat clock"
TEST_BLOCK = r'''

test("feed pulse freshness grades its current heartbeat clock", () => {
  const spec = readinessMatrix.endpoints["/api/a11oy/v1/feeds/pulse"];
  const nowMs = Date.parse("2026-09-01T05:30:00Z");
  const body = {
    probed_at: "2026-09-01T05:29:50Z",
    items: [{
      feed: "celestrak",
      mode: "cached",
      fetched_at: "2026-08-31T00:00:00Z",
      source_url: "https://celestrak.org/",
    }],
  };

  const currentHeartbeat = evaluateFreshness(
    "/api/a11oy/v1/feeds/pulse",
    spec,
    body,
    nowMs,
  );
  assert.equal(currentHeartbeat.freshOk, true);
  assert.equal(currentHeartbeat.ageSec, 10);

  const missingHeartbeat = evaluateFreshness(
    "/api/a11oy/v1/feeds/pulse",
    spec,
    { items: body.items },
    nowMs,
  );
  assert.equal(missingHeartbeat.freshOk, false);
  assert.equal(missingHeartbeat.freshnessMissing, true);
  assert.match(missingHeartbeat.freshnessReason, /probed_at/);
});
'''


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"expected exactly one schema anchor in {path}, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def append_test_once(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if TEST_MARKER in text:
        raise RuntimeError(f"test marker already present in {path}")
    path.write_text(text.rstrip() + TEST_BLOCK + "\n", encoding="utf-8")


def main() -> int:
    replace_once(GENERATOR, OLD_SCHEMA, NEW_SCHEMA)
    append_test_once(TEST_FILE)
    subprocess.run([sys.executable, str(GENERATOR)], cwd=ROOT, check=True)

    matrix = json.loads(TABS.read_text(encoding="utf-8"))
    schema = matrix["schemas"]["feeds_pulse"]
    expected = {"probed_at": "timestamp"}
    if schema.get("requiredPathTypes") != expected:
        raise RuntimeError(
            "generated feeds_pulse schema did not bind the heartbeat timestamp"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
