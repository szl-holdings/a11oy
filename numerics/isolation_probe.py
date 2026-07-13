# SPDX-License-Identifier: Apache-2.0
"""Fixed child used only to attest a fresh Linux network namespace.

The parent launches this file through ``unshare --net``.  It performs no
network operation and accepts no command, expression, or package input.
"""

import json
import os
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        return 64
    target = Path(sys.argv[1])
    interfaces = sorted(path.name for path in Path("/sys/class/net").iterdir())
    loopback_state = None
    state_path = Path("/sys/class/net/lo/operstate")
    if state_path.is_file():
        loopback_state = state_path.read_text(encoding="utf-8").strip()
    payload = {
        "schema": "szl.numerics.network-namespace-evidence/v1",
        "network_operations_performed": 0,
        "network_namespace": os.readlink("/proc/self/ns/net"),
        "interfaces": interfaces,
        "loopback_operstate": loopback_state,
    }
    target.write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
