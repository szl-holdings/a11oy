#!/usr/bin/env python3
"""Validate the public-pattern synthesis manifest.

The manifest is a clean-room guardrail: public sources can inspire original
SZL/A11oy work, but private/unlicensed copying is not allowed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlparse


REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = REPO_ROOT / "docs" / "public-pattern-source-manifest.json"

ALLOWED_STATUSES = {
    "verified-runtime",
    "release-payload",
    "lean-backed-current-green",
    "lean-backed-needs-upstream-ci",
    "thesis-anchor",
    "historical",
    "roadmap",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def is_public_url(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme in {"https", "http"} and bool(parsed.netloc)


def main() -> int:
    errors: list[str] = []
    manifest = load_json(MANIFEST_PATH)

    if manifest.get("privateIngestionAllowed") is not False:
        errors.append("privateIngestionAllowed must be false")

    copying_rule = manifest.get("copyingRule", "").lower()
    for required in ["pattern-only", "no upstream code", "private material"]:
        if required not in copying_rule:
            errors.append(f"copyingRule must include {required!r}")

    if "endorsement" not in manifest.get("endorsementBoundary", "").lower():
        errors.append("endorsementBoundary must explicitly reject implied endorsement")

    queues = manifest.get("sourceQueues", [])
    if not isinstance(queues, list) or not queues:
        errors.append("sourceQueues must be a non-empty list")
        queues = []

    queue_ids: set[str] = set()
    for queue in queues:
        queue_id = queue.get("id", "<missing>")
        if queue_id in queue_ids:
            errors.append(f"duplicate source queue id: {queue_id}")
        queue_ids.add(queue_id)

        public_url = queue.get("publicUrl")
        if not isinstance(public_url, str) or not is_public_url(public_url):
            errors.append(f"{queue_id}: publicUrl must be an http(s) URL")

        audit_mode = queue.get("auditMode", "")
        if "public" not in audit_mode and "authorized" not in audit_mode:
            errors.append(f"{queue_id}: auditMode must be public/authorized scoped")

    patterns = manifest.get("patterns", [])
    if not isinstance(patterns, list) or not patterns:
        errors.append("patterns must be a non-empty list")
        patterns = []

    pattern_ids: set[str] = set()
    required_pattern_fields = {
        "id",
        "name",
        "sourceQueueIds",
        "publicSourceCategories",
        "licenseCaveat",
        "a11oyTransform",
        "localEvidence",
        "validationCommands",
        "claimStatus",
    }
    for pattern in patterns:
        pattern_id = pattern.get("id", "<missing>")
        if pattern_id in pattern_ids:
            errors.append(f"duplicate pattern id: {pattern_id}")
        pattern_ids.add(pattern_id)

        missing = sorted(required_pattern_fields - pattern.keys())
        if missing:
            errors.append(f"{pattern_id}: missing fields: {', '.join(missing)}")

        if pattern.get("claimStatus") not in ALLOWED_STATUSES:
            errors.append(f"{pattern_id}: unsupported claimStatus {pattern.get('claimStatus')!r}")

        for queue_id in pattern.get("sourceQueueIds", []):
            if queue_id not in queue_ids:
                errors.append(f"{pattern_id}: unknown sourceQueueId {queue_id}")

        license_caveat = pattern.get("licenseCaveat", "").lower()
        if not any(token in license_caveat for token in ["copy", "license", "redistribute"]):
            errors.append(f"{pattern_id}: licenseCaveat must state copying/license boundary")

        transform = pattern.get("a11oyTransform", "").lower()
        if "a11oy" not in transform and "szl" not in transform:
            errors.append(f"{pattern_id}: a11oyTransform must describe original SZL/A11oy work")

        local_evidence = pattern.get("localEvidence", [])
        if not isinstance(local_evidence, list) or not local_evidence:
            errors.append(f"{pattern_id}: localEvidence must be a non-empty list")
        for evidence in local_evidence:
            # URLs are allowed as evidence, but local paths should exist when
            # they are part of this checkout.
            if isinstance(evidence, str) and not is_public_url(evidence):
                if not (REPO_ROOT / evidence).exists():
                    errors.append(f"{pattern_id}: local evidence path does not exist: {evidence}")

        commands = pattern.get("validationCommands", [])
        if not isinstance(commands, list) or not commands:
            errors.append(f"{pattern_id}: validationCommands must be a non-empty list")

    if errors:
        print("Public pattern manifest validation failed:")
        for error in errors:
            print(f"  - {error}")
        return 1

    print(f"Validated {MANIFEST_PATH.relative_to(REPO_ROOT)} ({len(patterns)} patterns)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
