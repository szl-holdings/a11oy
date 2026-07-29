"""Run one bounded GDW outbox drain pass from the command line."""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gdw_runtime import drain_once  # noqa: E402


def main(limit, lease_seconds):
    report = drain_once(limit=limit, lease_seconds=lease_seconds)
    print(report)
    if report["failed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument("--lease-seconds", type=int, default=300)
    args = parser.parse_args()
    main(args.limit, args.lease_seconds)
