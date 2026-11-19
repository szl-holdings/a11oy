#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate release-manifest.json at build time (see szl_release_manifest.py).

Values come from the tree (git commit, frontend bundle hash, API contract hash,
model pin in the Dockerfile) and from the environment or flags (deployment ID,
rollback target). Nothing is hardcoded; unsupplied values are written as UNKNOWN.

  python3 scripts/generate_release_manifest.py --out release-manifest.json
  python3 scripts/generate_release_manifest.py --require-complete --emit-build-args
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import szl_release_manifest as rm  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--repo-root", default=str(ROOT))
    p.add_argument("--out", default="release-manifest.json")
    p.add_argument("--git-commit")
    p.add_argument("--bundle-root", default=rm.DEFAULT_BUNDLE_ROOT)
    p.add_argument("--contract-input", action="append", dest="contract_inputs")
    p.add_argument("--openapi-json", help="OpenAPI document to hash instead of the repo contract files")
    p.add_argument("--deployment-id")
    p.add_argument("--rollback-target")
    p.add_argument("--require-complete", action="store_true", help="exit 1 if any required field is UNKNOWN")
    p.add_argument("--emit-build-args", action="store_true", help="print docker --build-arg KEY=VALUE lines")
    args = p.parse_args(argv)

    env = dict(os.environ)
    if args.deployment_id:
        env["A11OY_DEPLOYMENT_ID"] = args.deployment_id
    if args.rollback_target:
        env["A11OY_ROLLBACK_TARGET"] = args.rollback_target

    manifest = rm.build_manifest(
        Path(args.repo_root),
        env=env,
        git_commit=args.git_commit,
        bundle_root=args.bundle_root,
        contract_inputs=args.contract_inputs or rm.DEFAULT_CONTRACT_INPUTS,
        openapi_json=Path(args.openapi_json) if args.openapi_json else None,
    )
    missing = rm.unknown_fields(manifest)
    if args.require_complete and missing:
        print("ERROR: release manifest incomplete, UNKNOWN: " + ", ".join(missing), file=sys.stderr)
        return 1
    Path(args.out).write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if missing:
        print("NOTE: UNKNOWN fields: " + ", ".join(missing), file=sys.stderr)
    if args.emit_build_args:
        for key, value in rm.build_args(manifest).items():
            print(f"--build-arg {key}={value}")
    print(f"release_id={manifest['release_id']} commit={manifest['git']['commit']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
