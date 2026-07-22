#!/usr/bin/env python3
"""Verify the revision currently serving a Hugging Face Space.

The Space repository SHA and the running container SHA are separate facts.
Metadata-only commits can advance the repository without rebuilding the
container. Source parity is checked by a separate workflow; this verifier
therefore fails closed on the runtime revision and stage only, while reporting
the repository revision for auditability.
"""

import argparse
import json
import sys
import urllib.request


def evaluate_metadata(metadata: dict, expected_runtime_sha: str) -> dict:
    runtime = metadata.get("runtime") or {}
    repository_sha = metadata.get("sha")
    runtime_sha = runtime.get("sha")
    stage = runtime.get("stage")

    failures = []
    if not repository_sha:
        failures.append("repository revision is missing")
    if not runtime_sha:
        failures.append("runtime revision is missing")
    elif runtime_sha != expected_runtime_sha:
        failures.append(
            f"runtime revision mismatch: expected={expected_runtime_sha} "
            f"observed={runtime_sha}"
        )
    if stage != "RUNNING":
        failures.append(f"runtime stage is not RUNNING: observed={stage!r}")

    return {
        "status": "PASS" if not failures else "FAIL",
        "expected_runtime_sha": expected_runtime_sha,
        "repository_sha": repository_sha,
        "runtime_sha": runtime_sha,
        "runtime_stage": stage,
        "repository_runtime_relation": (
            "SAME_REVISION"
            if repository_sha and repository_sha == runtime_sha
            else "DISTINCT_REVISIONS"
        ),
        "source_parity_evaluated_here": False,
        "failures": failures,
    }


def fetch_metadata(space: str, timeout: float = 30.0) -> dict:
    request = urllib.request.Request(
        f"https://huggingface.co/api/spaces/{space}",
        headers={"User-Agent": "a11oy-hf-runtime-evidence/1.0"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--space", default="SZLHOLDINGS/a11oy")
    parser.add_argument("--expected-runtime-sha", required=True)
    parser.add_argument("--timeout", type=float, default=30.0)
    args = parser.parse_args()

    result = evaluate_metadata(
        fetch_metadata(args.space, timeout=args.timeout),
        args.expected_runtime_sha,
    )
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
