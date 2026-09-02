#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compatibility entrypoint for the current Hugging Face Space restart API.

The base recovery operator remains the complete fail-closed implementation. This
entrypoint binds its restart transport to the Hub API's documented `factory`
JSON field before executing the same inventory, fold-preservation, restart,
factory-reboot, polling, receipt, and exit-code logic.
"""
from __future__ import annotations

import urllib.parse
from typing import Any

import hf_estate_recover as base


def _restart(
    self: base.HfEstate,
    repo_id: str,
    *,
    factory_reboot: bool,
) -> tuple[bool, int, str]:
    encoded = urllib.parse.quote(repo_id, safe="/")
    status, payload = self.http.request(
        "POST",
        f"{base.HF_ENDPOINT}/api/spaces/{encoded}/restart",
        payload={"factory": bool(factory_reboot)},
        timeout=60,
    )
    detail = ""
    if isinstance(payload, dict):
        detail = str(
            payload.get("error")
            or payload.get("message")
            or payload.get("stage")
            or ""
        )
    return 200 <= status < 300, status, detail[:500]


base.HfEstate.restart = _restart

if __name__ == "__main__":
    raise SystemExit(base.main())
