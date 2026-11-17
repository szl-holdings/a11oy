#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Run Linux contract tests with the existing process-wide network boundary.

Install the Frontier honesty checker's audited socket/DNS denial before pytest
can import plugins, conftests, or the application. Real unavailable paths remain
observable; no backend responses or assertions are replaced. All pytest arguments
and its exit status pass through unchanged.

The target is Linux CI, where asyncio/TestClient use AF_UNIX socketpairs. This
runner does not relax the boundary for Windows INET-based socketpair IPC. As with
the existing checker, this is a test I/O boundary, not an untrusted-code sandbox.
"""
import importlib.util
from pathlib import Path
import sys


def main(argv=None) -> int:
    spec = importlib.util.spec_from_file_location(
        "offline_frontier_guard", Path(__file__).with_name("frontier_index_honesty_check.py"))
    guard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(guard)
    guard._install_no_network_guard()
    import pytest

    return int(pytest.main(sys.argv[1:] if argv is None else argv))


if __name__ == "__main__":
    raise SystemExit(main())
