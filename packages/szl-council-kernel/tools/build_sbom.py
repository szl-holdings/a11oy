#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import uuid
from importlib import metadata
from pathlib import Path

PACKAGE = "szl-council-kernel"
VERSION = "0.5.0rc1"
RUNTIME_DEPENDENCIES = ("cryptography", "jsonschema")


def component(name: str) -> dict[str, object]:
    try:
        version = metadata.version(name)
        dist = metadata.distribution(name)
        license_value = dist.metadata.get("License") or "UNKNOWN"
    except metadata.PackageNotFoundError:
        version = "UNAVAILABLE"
        license_value = "UNKNOWN"
    return {
        "type": "library",
        "name": name,
        "version": version,
        "bom-ref": f"pkg:pypi/{name}@{version}",
        "purl": f"pkg:pypi/{name}@{version}",
        "licenses": [{"license": {"name": license_value}}],
        "properties": [
            {"name": "szl.inventory.status", "value": "INSTALLED_VERSION_OBSERVED" if version != "UNAVAILABLE" else "UNAVAILABLE"}
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--source-revision", default="UNCOMMITTED")
    ap.add_argument("--source-tree", default="UNAVAILABLE")
    args = ap.parse_args()
    components = [component(name) for name in RUNTIME_DEPENDENCIES]
    serial_seed = f"{PACKAGE}:{VERSION}:{args.source_revision}:{args.source_tree}"
    serial = uuid.UUID(hashlib.md5(serial_seed.encode("utf-8"), usedforsecurity=False).hexdigest())
    root_ref = f"pkg:pypi/{PACKAGE}@{VERSION}"
    bom = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.6",
        "serialNumber": f"urn:uuid:{serial}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "group": "com.szlholdings",
                "name": PACKAGE,
                "version": VERSION,
                "bom-ref": root_ref,
                "purl": root_ref,
                "licenses": [{"license": {"id": "Apache-2.0"}}],
                "properties": [
                    {"name": "szl.source.revision", "value": args.source_revision},
                    {"name": "szl.source.tree", "value": args.source_tree},
                    {"name": "szl.assurance.scope", "value": "SOURCE_AND_LOCAL_RUNTIME_INVENTORY_ONLY"},
                    {"name": "szl.vulnerability.audit", "value": "NOT_PERFORMED_OFFLINE_NO_ADVISORY_DATABASE"},
                ],
            }
        },
        "components": components,
        "dependencies": [
            {"ref": root_ref, "dependsOn": [item["bom-ref"] for item in components]},
            *[{"ref": item["bom-ref"], "dependsOn": []} for item in components],
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(bom, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"schema": "szl.sbom-build/v1", "status": "PASS", "component_count": len(components) + 1, "output": str(args.output)}, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
