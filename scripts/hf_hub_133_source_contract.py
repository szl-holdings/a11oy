#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) 2026 Lutar, Stephen P. - SZL Holdings - ORCID 0009-0001-0110-4173
"""Exact Hub 1.33 source successor; never grants runtime/provider authority.

Run as ``python -m scripts.hf_hub_133_source_contract``. The historical 1.31
release contract and its immutable Forge observations remain unchanged.
"""
from __future__ import annotations

from pathlib import Path
import re
from scripts import hf_hub_131_source_contract as historical

HF_HUB_VERSION = "1.33.0"
HF_XET_VERSION = "1.7.0"
HF_HUB_RELEASE_COMMIT = "9eeace5e467939b8f6af6ff280a134bc7c22802f"
HF_HUB_TAG_OBJECT = "a93d85c0e6e0f35c29c33e60cb1e1ca9d60a1692"
HF_HUB_TAG_SIGNATURE_VERIFIED = False
HF_HUB_TAG_SIGNATURE_REASON = "unsigned"
HF_HUB_WHEEL_SHA256 = "04e434b06e100eddbce9a6e817d72693a7884b10a79bd67ab48080d5c07eb899"


def _transport_pin(text: str) -> str | None:
    """Require one exact native transport pin; ranges and duplicates stay unknown."""
    entries = [line.split("#", 1)[0].strip() for line in text.splitlines()]
    entries = [line for line in entries
               if re.match(r"hf[-_]xet(?=[\s<>=!~;\[]|$)", line, re.IGNORECASE)]
    if len(entries) != 1:
        return None
    match = re.fullmatch(r"hf[-_]xet\s*==\s*(\d+(?:\.\d+){2})", entries[0], re.IGNORECASE)
    return match.group(1) if match else None


def evaluate_runtime_alignment(*, audit_text: str, docker_text: str) -> dict[str, object]:
    audit = historical._pin(audit_text)
    runtime = historical._pin(docker_text)
    audit_transport = _transport_pin(audit_text)
    runtime_transport = _transport_pin(docker_text)
    native_aligned = audit_transport == runtime_transport == HF_XET_VERSION
    aligned = audit == runtime == HF_HUB_VERSION and native_aligned
    return {
        "auditPin": audit,
        "runtimePin": runtime,
        "requiredVersion": HF_HUB_VERSION,
        "auditTransportPin": audit_transport,
        "runtimeTransportPin": runtime_transport,
        "requiredTransportVersion": HF_XET_VERSION,
        "nativeTransportAligned": native_aligned,
        "exactReleaseCommit": HF_HUB_RELEASE_COMMIT,
        "annotatedTagObject": HF_HUB_TAG_OBJECT,
        "tagSignatureVerified": HF_HUB_TAG_SIGNATURE_VERIFIED,
        "tagSignatureReason": HF_HUB_TAG_SIGNATURE_REASON,
        "wheelSha256": HF_HUB_WHEEL_SHA256,
        "historicalForge131EvaluationMerge": historical.FORGE_EVALUATION_MERGE,
        "aligned": aligned,
        "disposition": "EVALUATION" if aligned else "HOLD",
        "productionAuthorized": False,
        "automaticPromotionAuthorized": False,
        "hubPublicationAuthorized": False,
        "sandboxJobCreationAuthorized": False,
    }


def evaluate_repository(root: Path) -> dict[str, object]:
    return evaluate_runtime_alignment(
        audit_text=historical._expand_includes(root, "requirements-audit.txt"),
        docker_text=historical.runtime_install_text(root),
    )


if __name__ == "__main__":
    for key, value in sorted(evaluate_repository(Path(__file__).resolve().parents[1]).items()):
        print(f"{key}={value}")
