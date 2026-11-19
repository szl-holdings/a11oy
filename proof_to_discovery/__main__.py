#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Command entry point: ``python -m proof_to_discovery [--check|--json]``."""

from .demo import main

if __name__ == "__main__":
    raise SystemExit(main())
