#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Fail-closed probe: live Hugging Face Lyte Space vs the publisher pin.

Does not publish. Does not write tokens. Does not merge GitHub.
Exit 0 if the Space runtime revision matches SOURCE_REVISION in
hf_publish_lyte_enterprise.py. Exit 2 on MEASURED drift. Exit 1 if the
Space is UNAVAILABLE.
"""
from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

PUBLISHER = Path(__file__).resolve().with_name("hf_publish_lyte_enterprise.py")
ORIGIN = "https://szlholdings-lyte.hf.space/healthz"
USER_AGENT = "SZLHOLDINGS-Lyte-Space-Revision-Probe/4.0"


def publisher_pin() -> str:
    text = PUBLISHER.read_text(encoding="utf-8")
    match = re.search(r'^SOURCE_REVISION = "([0-9a-f]{40})"', text, re.M)
    if not match:
        raise SystemExit("publisher SOURCE_REVISION is UNAVAILABLE")
    return match.group(1)


def main() -> int:
    pin = publisher_pin()
    req = urllib.request.Request(ORIGIN, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as res:
            body = json.loads(res.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"truth_label": "UNAVAILABLE", "error": str(exc), "publisher_pin": pin}))
        return 1
    observed = str(body.get("runtime_source_revision") or body.get("source_revision") or "")
    aligned = observed == pin
    payload = {
        "truth_label": "MEASURED",
        "origin": ORIGIN,
        "publisher_pin": pin,
        "space_revision": observed,
        "aligned": aligned,
        "verdict": "ALIGNED" if aligned else "DRIFT",
        "effectors_enabled": body.get("effectors_enabled"),
        "version": body.get("version"),
        "note": "A forecast-hash match is not a source-revision match. This probe does not publish.",
    }
    print(json.dumps(payload, sort_keys=True))
    return 0 if aligned else 2


if __name__ == "__main__":
    raise SystemExit(main())
