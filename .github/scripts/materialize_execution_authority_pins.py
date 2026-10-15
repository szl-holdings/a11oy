#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Validate independently configured public pins and write one exclusive local file."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
import szl_execution_readiness as gate


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-sha", required=True)
    parser.add_argument("--runtime-sha", required=True)
    parser.add_argument("--boot-id", required=True)
    parser.add_argument("--run-nonce", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        raw = os.environ.get("A11OY_EXECUTION_AUTHORITY_PINS_JSON", "").encode()
        gate.require(0 < len(raw) <= 16384, "INDEPENDENT_AUTHORITY_PINS_REQUIRED")
        pins = gate.acceptance.strict_json(raw)
        gate.acceptance.fields(pins, "schema approval_public_pem approval_key_id runtime_public_pem runtime_key_id",
                               "INVALID_AUTHORITY_CONFIGURATION")
        gate.require(pins["schema"] == "szl.execution-authority-pins/v1", "AUTHORITY_SCHEMA_MISMATCH")
        context = gate.acceptance.AdmissionContext(args.source_sha, args.runtime_sha, args.boot_id, args.run_nonce,
            pins["approval_public_pem"].encode(), pins["approval_key_id"],
            pins["runtime_public_pem"].encode(), pins["runtime_key_id"])
        gate._context(context, args.source_sha)
        with Path(args.output).open("xb") as stream:
            stream.write(gate.acceptance.canonical(pins))
        print(json.dumps({"public_pins_written": True, "execution_authorized": False}))
        return 0
    except Exception:
        print(json.dumps({"public_pins_written": False, "error": "INDEPENDENT_PUBLIC_PINS_UNAVAILABLE",
                          "execution_authorized": False}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
