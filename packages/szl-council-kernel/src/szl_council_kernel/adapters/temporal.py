from __future__ import annotations

import importlib.util


def temporal_capability_report() -> dict[str, object]:
    installed = importlib.util.find_spec("temporalio") is not None
    return {
        "schema": "szl.temporal-adapter-status/v1",
        "installed": installed,
        "enabled": False,
        "role": "DURABLE_ORCHESTRATION_ADAPTER_ONLY",
        "root_of_trust": False,
        "activation_required": "explicit worker configuration and workflow registration",
    }
