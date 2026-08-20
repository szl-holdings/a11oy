#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs" / "huggingface-ecosystem-manifest.json"
DEFAULT_OUTPUT = ROOT / "docs" / "huggingface-frontend-remediation-queue-v1.json"

BUCKET_KINDS = {
    "organization": "organization",
    "organizations": "organization",
    "org_card": "organization",
    "org_cards": "organization",
    "spaces": "space",
    "space": "space",
    "models": "model",
    "model": "model",
    "datasets": "dataset",
    "dataset": "dataset",
    "kernels": "kernel",
    "kernel": "kernel",
    "verifiers": "kernel",
    "collections": "collection",
    "collection": "collection",
    "buckets": "bucket",
    "bucket": "bucket",
}

IDENTITY_KEYS = (
    "repo_id",
    "asset_id",
    "id",
    "name",
    "slug",
    "path",
    "repository",
    "repo",
    "url",
)
KIND_KEYS = ("asset_type", "repo_type", "kind", "type", "category")
SOURCE_KEYS = (
    "source_revision",
    "source_sha",
    "github_sha",
    "commit_sha",
    "revision",
    "sha",
)
SHORT_DESCRIPTION_KEYS = (
    "short_description",
    "shortdescription",
    "description_short",
)
DESCRIPTION_KEYS = ("description", "summary", "card_summary", "purpose")
LICENSE_KEYS = ("license", "license_name", "license_id")
SDK_KEYS = ("sdk", "space_sdk")
RUNTIME_KEYS = ("runtime_stage", "runtime_state", "space_stage")

UNRESOLVED_MARKERS = (
    "unknown",
    "unresolved",
    "unavailable",
    "unnamed",
    "tbd",
    "missing",
)
BAD_RUNTIME_STATES = {
    "PAUSED",
    "STOPPED",
    "FAILED",
    "ERROR",
    "BUILD_ERROR",
    "CONFIG_ERROR",
    "RUNTIME_ERROR",
    "NO_APP_FILE",
    "UNAVAILABLE",
}
RESPONSIVE_TOKENS = (
    "responsive",
    "mobile",
    "viewport",
    "accessibility",
    "a11y",
    "touch_target",
    "reduced_motion",
    "horizontal_overflow",
)
CARD_EVIDENCE_TOKENS = (
    "card_data",
    "carddata",
    "readme",
    "metadata",
    "front_matter",
    "frontmatter",
)


def _canonical_key(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def _scalar_text(value: Any) -> str | None:
    if isinstance(value, str):
        text = value.strip()
        return text or None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return None


def _flatten(record: dict[str, Any], *, depth: int = 2) -> dict[str, list[Any]]:
    flattened: dict[str, list[Any]] = {}

    def visit(node: Any, prefix: tuple[str, ...], remaining: int) -> None:
        if isinstance(node, dict) and remaining >= 0:
            for key, value in node.items():
                canonical = _canonical_key(str(key))
                flattened.setdefault(canonical, []).append(value)
                flattened.setdefault(".".join((*prefix, canonical)), []).append(value)
                if remaining:
                    visit(value, (*prefix, canonical), remaining - 1)
        elif isinstance(node, list) and remaining:
            for value in node:
                visit(value, prefix, remaining - 1)

    visit(record, (), depth)
    return flattened


def _first_text(flattened: dict[str, list[Any]], keys: Iterable[str]) -> str | None:
    for key in keys:
        for candidate_key, values in flattened.items():
            if candidate_key == key or candidate_key.endswith("." + key):
                for value in values:
                    text = _scalar_text(value)
                    if text:
                        return text
    return None


def _list_strings(flattened: dict[str, list[Any]], key: str) -> list[str]:
    values: list[str] = []
    for candidate_key, candidates in flattened.items():
        if candidate_key == key or candidate_key.endswith("." + key):
            for candidate in candidates:
                if isinstance(candidate, list):
                    values.extend(str(item).strip() for item in candidate if str(item).strip())
                else:
                    text = _scalar_text(candidate)
                    if text:
                        values.append(text)
    return values


def _infer_kind(record: dict[str, Any], bucket_kind: str) -> str:
    flattened = _flatten(record, depth=1)
    explicit = _first_text(flattened, KIND_KEYS)
    candidate = _canonical_key(explicit or bucket_kind or "asset")
    aliases = {
        "spaces": "space",
        "models": "model",
        "datasets": "dataset",
        "kernels": "kernel",
        "verifier": "kernel",
        "verifiers": "kernel",
        "collections": "collection",
        "buckets": "bucket",
        "org": "organization",
        "org_card": "organization",
        "organization_card": "organization",
    }
    return aliases.get(candidate, candidate)


def _identity(record: dict[str, Any]) -> str | None:
    flattened = _flatten(record, depth=1)
    return _first_text(flattened, IDENTITY_KEYS)


def _iter_asset_records(
    node: Any,
    path: tuple[str, ...] = (),
) -> Iterable[tuple[str, dict[str, Any], tuple[str, ...]]]:
    if isinstance(node, dict):
        for key, value in node.items():
            canonical = _canonical_key(str(key))
            bucket_kind = BUCKET_KINDS.get(canonical)
            if bucket_kind and isinstance(value, list):
                for index, item in enumerate(value):
                    if isinstance(item, dict):
                        yield bucket_kind, item, (*path, canonical, str(index))
            elif bucket_kind and isinstance(value, dict):
                yield bucket_kind, value, (*path, canonical)
            yield from _iter_asset_records(value, (*path, canonical))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _iter_asset_records(item, (*path, str(index)))


def _source_observation(manifest: dict[str, Any]) -> str:
    for key in ("generated_at", "observed_at", "captured_at", "snapshot_at", "updated_at"):
        text = _scalar_text(manifest.get(key))
        if text:
            return text
    return "UNAVAILABLE"


def _has_key_token(flattened: dict[str, list[Any]], tokens: Iterable[str]) -> bool:
    return any(any(token in key for token in tokens) for key in flattened)


def _license(flattened: dict[str, list[Any]]) -> str | None:
    direct = _first_text(flattened, LICENSE_KEYS)
    if direct:
        return direct
    for tag in _list_strings(flattened, "tags"):
        if tag.lower().startswith("license:"):
            return tag.split(":", 1)[1].strip() or None
    return None


def _action(
    code: str,
    priority: str,
    title: str,
    evidence_state: str,
    detail: str,
) -> dict[str, str]:
    return {
        "code": code,
        "priority": priority,
        "title": title,
        "evidence_state": evidence_state,
        "detail": detail,
    }


def _classify_asset(kind: str, identity: str | None, record: dict[str, Any]) -> list[dict[str, str]]:
    flattened = _flatten(record)
    actions: list[dict[str, str]] = []
    identity_lower = (identity or "").lower()

    if not identity or any(marker in identity_lower for marker in UNRESOLVED_MARKERS):
        actions.append(
            _action(
                "IDENTITY_UNRESOLVED",
                "P0",
                "Resolve canonical asset identity",
                "UNAVAILABLE",
                "The public observation does not expose a stable canonical identity; do not guess or publish against an aggregate count.",
            )
        )

    source_revision = _first_text(flattened, SOURCE_KEYS)
    if not source_revision:
        actions.append(
            _action(
                "SOURCE_BINDING_REVIEW_REQUIRED",
                "P1",
                "Bind card or runtime to immutable source",
                "UNAVAILABLE",
                "No immutable source revision is represented in the observed asset evidence.",
            )
        )

    short_description = _first_text(flattened, SHORT_DESCRIPTION_KEYS)
    description = _first_text(flattened, DESCRIPTION_KEYS)
    if short_description and len(short_description) > 60:
        actions.append(
            _action(
                "SHORT_DESCRIPTION_TOO_LONG",
                "P1",
                "Reduce short description to 60 characters",
                "OBSERVED",
                f"Observed short description length is {len(short_description)} characters.",
            )
        )
    if kind in {"organization", "space", "model", "dataset", "kernel", "collection"} and not (
        short_description or description
    ):
        actions.append(
            _action(
                "CARD_NARRATIVE_REQUIRED",
                "P1",
                "Add a bounded public card narrative",
                "UNAVAILABLE",
                "No concise purpose or description is represented in the observed asset evidence.",
            )
        )

    if kind == "space":
        sdk = _first_text(flattened, SDK_KEYS)
        if not sdk:
            actions.append(
                _action(
                    "SPACE_SDK_REVIEW_REQUIRED",
                    "P1",
                    "Declare and verify the Space SDK",
                    "UNAVAILABLE",
                    "The observed Space record does not expose a framework/runtime SDK.",
                )
            )
        runtime_state = _first_text(flattened, RUNTIME_KEYS)
        if runtime_state and runtime_state.upper() in BAD_RUNTIME_STATES:
            actions.append(
                _action(
                    "SPACE_RUNTIME_NOT_RUNNING",
                    "P1",
                    "Restore or explicitly archive the Space runtime",
                    "OBSERVED",
                    f"Observed runtime state is {runtime_state}.",
                )
            )

    if kind in {"model", "dataset"} and not _license(flattened):
        actions.append(
            _action(
                "LICENSE_EVIDENCE_REQUIRED",
                "P1",
                "Publish explicit license evidence",
                "UNAVAILABLE",
                "No license field or license tag is represented in the observed card evidence.",
            )
        )

    if kind in {"organization", "space"}:
        responsive_priority = "P1"
    else:
        responsive_priority = "P2"
    if kind in {"organization", "space", "model", "dataset", "kernel", "collection"} and not _has_key_token(
        flattened, RESPONSIVE_TOKENS
    ):
        actions.append(
            _action(
                "RESPONSIVE_EVIDENCE_REQUIRED",
                responsive_priority,
                "Prove the universal viewport contract",
                "UNAVAILABLE",
                "No mobile, viewport, accessibility, touch-target, overflow, or reduced-motion evidence is represented for this surface.",
            )
        )

    if kind in {"model", "dataset", "kernel", "collection"} and not _has_key_token(
        flattened, CARD_EVIDENCE_TOKENS
    ):
        actions.append(
            _action(
                "CARD_METADATA_REVIEW_REQUIRED",
                "P2",
                "Review framework-native card metadata",
                "UNAVAILABLE",
                "The public observation does not include explicit card/front-matter evidence for this asset.",
            )
        )

    actions.sort(key=lambda item: (item["priority"], item["code"]))
    return actions


def build_queue(manifest: dict[str, Any], source_bytes: bytes) -> dict[str, Any]:
    aggregates: dict[tuple[str, str], dict[str, Any]] = {}
    unresolved_counter = 0

    for bucket_kind, record, path in _iter_asset_records(manifest):
        kind = _infer_kind(record, bucket_kind)
        identity = _identity(record)
        if identity:
            key_identity = identity
        else:
            unresolved_counter += 1
            key_identity = f"UNRESOLVED::{kind}::{unresolved_counter}"
        key = (kind, key_identity)
        score = len(_flatten(record))
        current = aggregates.get(key)
        if current is None or score > current["score"]:
            aggregates[key] = {
                "kind": kind,
                "identity": identity,
                "record": record,
                "score": score,
                "source_paths": {"/".join(path)},
            }
        else:
            current["source_paths"].add("/".join(path))

    assets: list[dict[str, Any]] = []
    priority_counts: Counter[str] = Counter()
    code_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()

    for key in sorted(aggregates):
        aggregate = aggregates[key]
        actions = _classify_asset(
            aggregate["kind"],
            aggregate["identity"],
            aggregate["record"],
        )
        if not actions:
            continue
        for action in actions:
            priority_counts[action["priority"]] += 1
            code_counts[action["code"]] += 1
        type_counts[aggregate["kind"]] += 1
        assets.append(
            {
                "asset_id": aggregate["identity"] or key[1],
                "asset_type": aggregate["kind"],
                "source_paths": sorted(aggregate["source_paths"]),
                "actions": actions,
            }
        )

    assets.sort(
        key=lambda asset: (
            min(action["priority"] for action in asset["actions"]),
            asset["asset_type"],
            asset["asset_id"],
        )
    )

    return {
        "schema": "szl.huggingface-frontend-remediation-queue/v1",
        "contract": "docs/HUGGINGFACE_UNIVERSAL_FRONTEND_CONTRACT_V1.md",
        "source_manifest": str(DEFAULT_MANIFEST.relative_to(ROOT)),
        "source_manifest_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_observed_at": _source_observation(manifest),
        "remote_mutation": False,
        "status": "OPEN" if assets else "CURRENT",
        "summary": {
            "assets_discovered": len(aggregates),
            "assets_queued": len(assets),
            "actions_total": sum(priority_counts.values()),
            "actions_by_priority": dict(sorted(priority_counts.items())),
            "actions_by_code": dict(sorted(code_counts.items())),
            "queued_assets_by_type": dict(sorted(type_counts.items())),
        },
        "assets": assets,
    }


def _render(queue: dict[str, Any]) -> str:
    return json.dumps(queue, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()

    source_bytes = args.manifest.read_bytes()
    manifest = json.loads(source_bytes)
    if not isinstance(manifest, dict):
        raise SystemExit("manifest root must be a JSON object")
    queue = build_queue(manifest, source_bytes)
    rendered = _render(queue)

    if args.check:
        if not args.output.exists() or args.output.read_text(encoding="utf-8") != rendered:
            print(
                json.dumps(
                    {
                        "status": "DRIFT",
                        "output": str(args.output),
                        "source_manifest_sha256": queue["source_manifest_sha256"],
                        "summary": queue["summary"],
                    },
                    indent=2,
                    sort_keys=True,
                )
            )
            return 1
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "PASS",
                "output": str(args.output),
                "source_manifest_sha256": queue["source_manifest_sha256"],
                "summary": queue["summary"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
