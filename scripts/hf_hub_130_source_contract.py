#!/usr/bin/env python3
"""Fail-closed Hugging Face Hub 1.30 provenance/runtime contract.

This module does not publish, deploy, download weights, or authorize a model.
It makes the canonical Hub-client version drift and revision-identity boundary
machine-readable so a dependency bump cannot silently become production proof.
"""
from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import Iterable

HF_HUB_130_VERSION = "1.30.0"
HF_HUB_130_RELEASE_COMMIT = "48ef2781c2c4c2247431c97efcd5487e89d42732"
HF_HUB_130_TAG_OBJECT = "103720584dcc9865259dc5165f1a42e0bdea15d5"
SHA40 = re.compile(r"^[0-9a-f]{40}$")
PIN = re.compile(r"huggingface[_-]hub==([0-9]+(?:\.[0-9]+){2})", re.IGNORECASE)


class ContractError(ValueError):
    """Malformed evidence cannot become authority."""


def _pin(text: str) -> str:
    values = sorted(set(PIN.findall(text)))
    if len(values) != 1:
        raise ContractError(f"expected one Hugging Face Hub pin, observed {values!r}")
    return values[0]


@dataclasses.dataclass(frozen=True, slots=True)
class RevisionBinding:
    repo_id: str
    repo_type: str
    requested_revision: str
    resolved_revision: str

    def __post_init__(self) -> None:
        if not self.repo_id or "/" not in self.repo_id:
            raise ContractError("repo_id must be explicit")
        if self.repo_type not in {"model", "dataset", "space", "kernel"}:
            raise ContractError("repo_type must be explicit and supported")
        if not self.requested_revision:
            raise ContractError("requested_revision must be explicit")
        if not SHA40.fullmatch(self.resolved_revision):
            raise ContractError("resolved_revision must be an exact lowercase SHA-40")

    def same_authority(self, other: "RevisionBinding") -> bool:
        """A commit oid alone never proves two bindings have the same authority."""
        return (
            self.repo_id == other.repo_id
            and self.repo_type == other.repo_type
            and self.requested_revision == other.requested_revision
            and self.resolved_revision == other.resolved_revision
        )


def serving_authorized(*, upstream_chat_eligible: bool, szl_allowlisted: bool,
                       evaluation_passed: bool, policy_passed: bool) -> bool:
    """Provider eligibility is availability only; SZL gates remain authoritative."""
    del upstream_chat_eligible
    return bool(szl_allowlisted and evaluation_passed and policy_passed)


def evaluate_runtime_alignment(*, audit_text: str, docker_text: str) -> dict[str, object]:
    audit = _pin(audit_text)
    runtime = _pin(docker_text)
    aligned = audit == runtime == HF_HUB_130_VERSION
    return {
        "auditPin": audit,
        "runtimePin": runtime,
        "requiredVersion": HF_HUB_130_VERSION,
        "exactReleaseCommit": HF_HUB_130_RELEASE_COMMIT,
        "annotatedTagObject": HF_HUB_130_TAG_OBJECT,
        "aligned": aligned,
        "disposition": "EVALUATION" if aligned else "HOLD",
        "productionAuthorized": False,
        "automaticPromotionAuthorized": False,
    }


def evaluate_repository(root: Path) -> dict[str, object]:
    return evaluate_runtime_alignment(
        audit_text=(root / "requirements-audit.txt").read_text(encoding="utf-8"),
        docker_text=(root / "Dockerfile").read_text(encoding="utf-8"),
    )


def main(argv: Iterable[str] | None = None) -> int:
    del argv
    result = evaluate_repository(Path(__file__).resolve().parents[1])
    for key in sorted(result):
        print(f"{key}={result[key]}")
    # Drift is evidence, not an exception: the caller receives a deterministic HOLD.
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
