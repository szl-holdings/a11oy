#!/usr/bin/env python3
"""Build deterministic Hugging Face dataset and Space payloads.

The builder performs no network or credential access. It scores the committed
reference submission with the canonical evaluator, copies only allowlisted
benchmark artifacts, and emits exact SHA-256 inventories for both payloads.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
DATASET_REPO = "SZLHOLDINGS/governed-agent-bench"
SPACE_REPO = "SZLHOLDINGS/governed-agent-bench"
MANAGED_BY = "szl-holdings/a11oy:benchmarks/governed-agent-bench"


class PublicationBuildError(RuntimeError):
    """The publication payload could not be built truthfully."""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def _inventory(folder: Path) -> list[dict[str, object]]:
    return [
        {
            "path": path.relative_to(folder).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": _sha256(path),
        }
        for path in sorted(folder.rglob("*"))
        if path.is_file() and path.name != "publication-manifest.json"
    ]


def _dataset_readme(source_revision: str) -> str:
    return f"""---
license: apache-2.0
pretty_name: governed-agent-bench
task_categories:
- other
tags:
- governance
- agents
- evaluation
- receipts
- rollback
---

# governed-agent-bench v0

This dataset is the immutable public mirror of
[`szl-holdings/a11oy@{source_revision}`](https://github.com/szl-holdings/a11oy/tree/{source_revision}/benchmarks/governed-agent-bench).

It measures five governability axes:

1. fail-closed behavior;
2. non-increasing authority across delegation;
3. false-success rejection;
4. receipt completeness; and
5. rollback discipline.

## Evidence labels

- Corpus: **SAMPLE**
- Scores: **COMPUTED**
- Receipt verification: **STRUCTURE_ONLY**
- Cryptographic verification: **false**

The reference result proves that the evaluator and known-good fixture close
their deterministic contract. It is not a model-quality or production claim.
The public leaderboard contains zero eligible model submissions until an exact
submission is evaluated and published with its receipt.

## Reproduce

```bash
python score.py submissions/reference-conformance.jsonl --strict
```

The canonical source, schema, evaluator, reference submission, result, and
publication manifest are all included in this dataset revision. The companion
Space is <https://huggingface.co/spaces/{SPACE_REPO}>.
"""


def _space_readme(source_revision: str) -> str:
    return f"""---
title: Governed Agent Bench
emoji: "\U0001F9ED"
colorFrom: gray
colorTo: blue
sdk: gradio
sdk_version: 6.20.0
app_file: app.py
pinned: false
license: apache-2.0
---

# Governed Agent Bench

Evidence-labeled leaderboard payload for the governability benchmark generated
from `szl-holdings/a11oy@{source_revision}`.

The Space renders only committed benchmark output. It does not call a model,
mint a score, or upgrade a `SAMPLE`/`COMPUTED` result into a verified production
claim.
"""


def build(output: Path, source_revision: str, observed_at: str) -> dict[str, object]:
    if not SHA_RE.fullmatch(source_revision):
        raise PublicationBuildError("source revision must be 40 lowercase hexadecimal characters")
    if not observed_at or "T" not in observed_at:
        raise PublicationBuildError("observed-at must be a non-empty ISO-8601 timestamp")

    dataset = output / "dataset"
    space = output / "space"
    dataset.mkdir(parents=True, exist_ok=True)
    space.mkdir(parents=True, exist_ok=True)

    canonical_files = {
        "cases.jsonl": HERE / "cases.jsonl",
        "schema.json": HERE / "schema.json",
        "manifest.json": HERE / "manifest.json",
        "score.py": HERE / "score.py",
        "submissions/reference-conformance.jsonl": HERE / "fixtures/passing.jsonl",
        "LICENSE": ROOT / "LICENSE",
    }
    for relative, source in canonical_files.items():
        if not source.is_file():
            raise PublicationBuildError(f"missing canonical source: {source}")
        _copy(source, dataset / relative)

    result_path = dataset / "results/reference-conformance.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        str(HERE / "score.py"),
        str(HERE / "fixtures/passing.jsonl"),
        "--strict",
        "--output",
        str(result_path),
    ]
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise PublicationBuildError(
            "reference scoring failed: " + (completed.stderr or completed.stdout).strip()
        )

    result = json.loads(result_path.read_text(encoding="utf-8"))
    required_result = {
        "score": 100.0,
        "perfect": True,
        "dataset_label": "SAMPLE",
        "score_label": "COMPUTED",
        "receipt_verification": "STRUCTURE_ONLY",
        "cryptographic_verification": False,
    }
    for field, expected in required_result.items():
        if result.get(field) != expected:
            raise PublicationBuildError(
                f"reference result {field} must be {expected!r}, got {result.get(field)!r}"
            )

    leaderboard = {
        "schema_version": "szl.governed-agent-bench-leaderboard.v1",
        "benchmark": "governed-agent-bench",
        "benchmark_version": result["version"],
        "status": "REFERENCE_ONLY_NO_MODEL_SUBMISSIONS",
        "source_repository": "szl-holdings/a11oy",
        "source_revision": source_revision,
        "observed_at": observed_at,
        "eligible_model_submissions": 0,
        "reference_rows": [
            {
                "entry_id": "reference-conformance-v0",
                "display_name": "Reference conformance fixture",
                "entry_class": "SAMPLE_REFERENCE_NOT_MODEL",
                "score": result["score"],
                "passed": result["passed"],
                "total": result["total"],
                "dataset_label": result["dataset_label"],
                "score_label": result["score_label"],
                "receipt_verification": result["receipt_verification"],
                "cryptographic_verification": result["cryptographic_verification"],
                "eligible_for_model_ranking": False,
                "result_path": "results/reference-conformance.json",
            }
        ],
        "model_submissions": [],
        "submission_rule": (
            "A model row is listed only after the exact JSONL submission, evaluator "
            "revision, result, license/model identity, and publication receipt are committed."
        ),
    }
    _write_json(dataset / "leaderboard.json", leaderboard)
    (dataset / "README.md").write_text(
        _dataset_readme(source_revision), encoding="utf-8", newline="\n"
    )

    _copy(HERE / "huggingface" / "app.py", space / "app.py")
    _copy(HERE / "huggingface" / "requirements.txt", space / "requirements.txt")
    _copy(ROOT / "LICENSE", space / "LICENSE")
    _copy(result_path, space / "results" / "reference-conformance.json")
    _write_json(space / "leaderboard.json", leaderboard)
    _write_json(
        space / "publication.json",
        {
            "schema_version": "szl.governed-agent-bench-space-publication.v1",
            "managed_by": MANAGED_BY,
            "source_revision": source_revision,
            "dataset_repository": DATASET_REPO,
            "dataset_revision": "RESOLVED_BY_PROTECTED_PUBLICATION",
            "evidence_labels": {
                "corpus": "SAMPLE",
                "score": "COMPUTED",
                "receipt_verification": "STRUCTURE_ONLY",
                "cryptographic_verification": False,
            },
        },
    )
    (space / "README.md").write_text(
        _space_readme(source_revision), encoding="utf-8", newline="\n"
    )

    dataset_manifest = {
        "schema_version": "szl.governed-agent-bench-publication-manifest.v1",
        "managed_by": MANAGED_BY,
        "repo_type": "dataset",
        "repo_id": DATASET_REPO,
        "source_revision": source_revision,
        "observed_at": observed_at,
        "files": _inventory(dataset),
    }
    space_manifest = {
        "schema_version": "szl.governed-agent-bench-publication-manifest.v1",
        "managed_by": MANAGED_BY,
        "repo_type": "space",
        "repo_id": SPACE_REPO,
        "source_revision": source_revision,
        "observed_at": observed_at,
        "files": _inventory(space),
    }
    _write_json(dataset / "publication-manifest.json", dataset_manifest)
    _write_json(space / "publication-manifest.json", space_manifest)
    return {
        "schema_version": "szl.governed-agent-bench-publication-build.v1",
        "source_revision": source_revision,
        "observed_at": observed_at,
        "dataset": dataset_manifest,
        "space": space_manifest,
        "network_accessed": False,
        "credentials_accessed": False,
        "publication_performed": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--observed-at", required=True)
    args = parser.parse_args()
    try:
        report = build(args.output, args.source_revision, args.observed_at)
    except PublicationBuildError as exc:
        print(f"publication build failed: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
