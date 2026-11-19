#!/usr/bin/env python3
"""scripts/generate_release_manifest.py — generate the ONE release manifest.

Implements the generator half of #3770. Everything measured, nothing hardcoded:

  * source commit    ← --commit or $GITHUB_SHA (full 40-hex, else honest UNKNOWN)
  * api contract     ← --openapi-json PATH when CI can export OpenAPI (preferred);
                       until then the sha256 of docs/api-contract.md
  * served frontend  ← --served-artifact PATH (sha256 of the BUILT SPA artifact)
  * model identity   ← --model-identity or $SZL_MODEL_IDENTITY
  * deployment id    ← --deployment-identity or $SZL_DEPLOYMENT_IDENTITY
  * release id       ← --release-id or $SZL_RELEASE_ID

--require-complete fails the build (exit 1) listing every missing item, so a
release can NEVER ship with UNKNOWN evidence under the strict workflow. The
default mode writes an honest manifest with UNKNOWN labels instead.

Run from the repo root or scripts/: the repo root is added to sys.path so the
canonical szl_release_manifest module is reused, never duplicated.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import szl_release_manifest as srm  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate the SZL release manifest (#3770)")
    parser.add_argument("--commit", default=None,
                        help="full 40-hex source commit (default: $GITHUB_SHA)")
    parser.add_argument("--git-ref", default=None,
                        help="git ref of the release (default: $GITHUB_REF)")
    parser.add_argument("--openapi-json", default=None,
                        help="path to the exported OpenAPI JSON (preferred API contract source)")
    parser.add_argument("--api-contract-doc", default=str(REPO_ROOT / "docs" / "api-contract.md"),
                        help="path to the API contract doc hashed until CI passes --openapi-json")
    parser.add_argument("--served-artifact", default=None,
                        help="path to the BUILT served frontend artifact (hashed at build time)")
    parser.add_argument("--model-identity", default=None,
                        help="measured model identity string (name@sha256:...)")
    parser.add_argument("--deployment-identity", default=None,
                        help="measured deployment identity (image digest / Space id@sha)")
    parser.add_argument("--release-id", default=None,
                        help="release id (default: $SZL_RELEASE_ID, else honest UNKNOWN)")
    parser.add_argument("--generated-at", default=None,
                        help="generation timestamp (ISO-8601 Z); CI supplies it")
    parser.add_argument("--output", default=str(REPO_ROOT / "release-manifest.json"),
                        help="output manifest path")
    parser.add_argument("--require-complete", action="store_true",
                        help="fail the build (exit 1) when any required evidence is missing/UNKNOWN")
    args = parser.parse_args()

    api_doc = args.api_contract_doc if (args.api_contract_doc and Path(args.api_contract_doc).exists()) else None

    manifest, missing = srm.generate_manifest(
        commit=args.commit,
        git_ref=args.git_ref,
        openapi_json_path=args.openapi_json,
        api_contract_doc_path=api_doc,
        served_artifact_path=args.served_artifact,
        model_identity=args.model_identity,
        deployment_identity=args.deployment_identity,
        release_id_value=args.release_id,
        generated_at=args.generated_at,
    )

    if args.require_complete and missing:
        sys.stderr.write("[release-manifest] --require-complete: refusing to ship, missing evidence:\n")
        for item in missing:
            sys.stderr.write("  - %s\n" % item)
        return 1

    Path(args.output).write_text(
        json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print("[release-manifest] wrote %s (status %s)" % (args.output, manifest["status"]))
    if missing:
        print("[release-manifest] honest UNKNOWN fields (not shipped evidence): %s" % ", ".join(missing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
