# SPDX-License-Identifier: Apache-2.0
"""Emit the existing finance publisher's exact build files, without publishing.

No HfApi instance, token, network call, provider write, or application code
execution occurs. Tests compare these bytes to captures from the existing
publisher main() under recording providers so this build harness cannot silently
qualify a different Dockerfile, application, configuration, or requirement set.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def load_renderer():
    path = HERE / "hf_publish_vertical_flagships_v4_impl.py"
    spec = importlib.util.spec_from_file_location("szl_finance_build_renderer", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("canonical renderer unavailable")
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    return renderer


def payloads(renderer, revision: str, run_id: int) -> dict[str, bytes]:
    if (not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision)
            or revision == "0" * 40 or type(run_id) is not int or run_id <= 0):
        raise ValueError("exact nonzero source revision and positive run identity required")
    rows = [row for row in renderer.FLAGSHIPS if row.get("slug") == "finance"]
    if len(rows) != 1:
        raise ValueError("canonical finance entry must be unique")
    item = rows[0]
    panels = renderer.html(item)
    card = renderer.readme(item)
    digest = hashlib.sha256(panels.encode()).hexdigest()
    config = {
        "slug": "finance", "title": item["title"], "vertical": item["vertical"],
        "product_source": item["source"],
        "source_repository": renderer.DEPLOYMENT_SOURCE_REPOSITORY,
        "source_revision": revision, "workflow_run_id": run_id,
        "hf_repository": renderer.ORG + "/finance",
        "artifact_set_sha256": renderer.artifact_digest(
            renderer.APP, renderer.DOCKER, renderer.REQ, panels, panels, card, "null"),
        "landing_sha256": digest, "panels_sha256": digest, "forge": None,
        "upstream": item["upstream"], "public_experience": renderer.PUBLIC_EXPERIENCE_VERSION,
    }
    return {name: value.encode("utf-8") for name, value in {
        "app.py": renderer.APP, "Dockerfile": renderer.DOCKER,
        "requirements.txt": renderer.REQ,
        "config.json": json.dumps(config, indent=2, sort_keys=True) + "\n",
        "index.html": panels, "panels.html": panels, "README.md": card,
    }.items()}


def materialize(output: Path, revision: str, run_id: int) -> dict:
    files = payloads(load_renderer(), revision, run_id)
    # Never merge generated files with a previous build or follow an output symlink.
    output.mkdir(parents=False, exist_ok=False)
    for name, raw in files.items():
        with (output / name).open("xb") as stream:
            stream.write(raw)
    evidence = {
        "schema": "szl.finance.generated-build/v1", "source_revision": revision,
        "workflow_run_id": run_id, "provider_mutations": 0,
        "deployment_verified": False,
        "files": {name: hashlib.sha256(raw).hexdigest() for name, raw in sorted(files.items())},
    }
    (output / "build-inputs.json").write_text(json.dumps(evidence, indent=2) + "\n")
    return evidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--run-id", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(materialize(args.output, args.source_revision, args.run_id), indent=2))


if __name__ == "__main__":
    main()
