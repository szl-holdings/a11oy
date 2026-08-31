#!/usr/bin/env python3
"""Generate a GitHub-backed Hugging Face ecosystem manifest for SZLHOLDINGS."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "docs" / "huggingface-ecosystem-manifest.json"
ORG = "SZLHOLDINGS"
PAGE_LIMIT = 100
GIT_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
RFC3339_UTC_RE = re.compile(
    r"^\d{4}-(?:0[1-9]|1[0-2])-(?:0[1-9]|[12]\d|3[01])"
    r"T(?:[01]\d|2[0-3]):[0-5]\d:[0-5]\d(?:\.\d+)?(?:Z|\+00:00)$"
)
RETRY_ATTEMPTS = 3
RETRYABLE_HTTP_CODES = frozenset({429, 500, 502, 503, 504})


def open_url_with_retry(
    url: str,
    *,
    timeout: float = 30,
    attempts: int = RETRY_ATTEMPTS,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Open a live evidence URL with bounded retries and fail closed."""

    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    for attempt in range(attempts):
        try:
            return urllib.request.urlopen(url, timeout=timeout)
        except urllib.error.HTTPError as exc:
            if exc.code not in RETRYABLE_HTTP_CODES or attempt + 1 == attempts:
                raise
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            if attempt + 1 == attempts:
                raise
        sleep(float(2**attempt))
    raise RuntimeError("unreachable retry state")


def fetch_page(url: str) -> tuple[Any, str | None]:
    with open_url_with_retry(url) as response:
        data = json.load(response)
        link = response.headers.get("Link", "")
    next_url = None
    for part in link.split(","):
        match = re.search(r'<([^>]+)>\s*;\s*rel="?next"?', part, re.IGNORECASE)
        if match:
            next_url = match.group(1)
            break
    return data, next_url


def api_items(kind: str) -> list[dict[str, Any]]:
    url: str | None = (
        f"https://huggingface.co/api/{kind}?author={ORG}"
        f"&limit={PAGE_LIMIT}&full=true"
    )
    items: dict[str, dict[str, Any]] = {}
    seen_urls: set[str] = set()
    while url:
        if url in seen_urls:
            raise RuntimeError(f"Pagination loop from Hugging Face {kind} API: {url}")
        seen_urls.add(url)
        data, url = fetch_page(url)
        if not isinstance(data, list):
            raise TypeError(f"Expected list from Hugging Face {kind} API")
        for item in data:
            if not isinstance(item, dict):
                raise TypeError(f"Expected object item from Hugging Face {kind} API")
            item_id = item.get("id") or item.get("modelId")
            if not isinstance(item_id, str) or not item_id:
                raise ValueError(f"Hugging Face {kind} API item has no repository id")
            items[item_id] = item
    return sorted(items.values(), key=lambda item: item.get("id", ""))


def observed_at_now() -> str:
    return (
        dt.datetime.now(dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def parse_rfc3339_utc(value: Any, *, field: str) -> dt.datetime:
    if not isinstance(value, str) or not RFC3339_UTC_RE.fullmatch(value):
        raise ValueError(f"{field} must be an RFC 3339 UTC timestamp")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = dt.datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"{field} must be an RFC 3339 UTC timestamp") from exc
    if parsed.utcoffset() != dt.timedelta(0):
        raise ValueError(f"{field} must be an RFC 3339 UTC timestamp")
    return parsed


def validate_observed_at(
    value: Any, *, now: dt.datetime | None = None
) -> dt.datetime:
    observed_at = parse_rfc3339_utc(value, field="observedAt")
    current = now or dt.datetime.now(dt.timezone.utc)
    if observed_at > current:
        raise ValueError("observedAt must not be in the future")
    return observed_at


def fetch_revision(
    item_id: str, repo_type: str, revision: str
) -> dict[str, Any]:
    plural = {"model": "models", "dataset": "datasets", "space": "spaces"}[
        repo_type
    ]
    encoded_id = urllib.parse.quote(item_id, safe="/")
    encoded_revision = urllib.parse.quote(revision, safe="")
    data, _ = fetch_page(
        f"https://huggingface.co/api/{plural}/{encoded_id}/revision/{encoded_revision}"
    )
    if not isinstance(data, dict):
        raise TypeError(
            f"Expected object from Hugging Face {repo_type} revision API"
        )
    return data


def fetch_card_markdown(
    item_id: str, repo_type: str, revision: str
) -> str:
    """Fetch the card at an exact repository revision.

    Repositories without a README are represented by the digest of an empty
    card so creating a card later is still detected as a semantic change.
    """

    prefix = {"model": "", "dataset": "datasets/", "space": "spaces/"}[
        repo_type
    ]
    encoded_id = urllib.parse.quote(item_id, safe="/")
    encoded_revision = urllib.parse.quote(revision, safe="")
    url = (
        f"https://huggingface.co/{prefix}{encoded_id}/raw/"
        f"{encoded_revision}/README.md"
    )
    try:
        with open_url_with_retry(url) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return ""
        raise


def normalize_card_markdown(markdown: str) -> str:
    """Normalize transport-only differences without changing card claims."""

    normalized = markdown.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in normalized.split("\n")]
    return "\n".join(lines).strip()


def card_semantic_sha256(markdown: str) -> str:
    normalized = normalize_card_markdown(markdown)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def validate_snapshot_revisions(
    existing: dict[str, Any],
    live: dict[str, Any],
    *,
    observed_at: dt.datetime,
    now: dt.datetime | None = None,
) -> None:
    """Validate retained revision fields without requiring the live head to match."""

    current = now or dt.datetime.now(dt.timezone.utc)
    for plural, repo_type in (
        ("models", "model"),
        ("datasets", "dataset"),
        ("spaces", "space"),
    ):
        live_items = {
            item.get("id"): item
            for item in live.get("inventory", {}).get(plural, [])
            if isinstance(item, dict)
        }
        for item in existing.get("inventory", {}).get(plural, []):
            if not isinstance(item, dict):
                raise ValueError(f"inventory.{plural} entries must be objects")
            item_id = item.get("id")
            if not isinstance(item_id, str) or not item_id:
                raise ValueError(f"inventory.{plural} entry has no repository id")
            stored_sha = item.get("sha")
            stored_last_modified = item.get("lastModified")
            stored_card_digest = item.get("cardSemanticSha256")
            if stored_sha is None and stored_last_modified is None:
                raise ValueError(
                    f"{item_id} sha and lastModified must both be present"
                )
            if stored_sha is None or stored_last_modified is None:
                raise ValueError(
                    f"{item_id} sha and lastModified must both be present"
                )
            if not isinstance(stored_sha, str) or not GIT_SHA_RE.fullmatch(
                stored_sha
            ):
                raise ValueError(f"{item_id} sha must be a 40-character Git SHA")
            if (
                not isinstance(stored_card_digest, str)
                or not SHA256_RE.fullmatch(stored_card_digest)
            ):
                raise ValueError(
                    f"{item_id} cardSemanticSha256 must be a SHA-256 digest"
                )
            stored_modified_at = parse_rfc3339_utc(
                stored_last_modified,
                field=f"{item_id} lastModified",
            )
            if stored_modified_at > observed_at:
                raise ValueError(
                    f"{item_id} lastModified must not be later than observedAt"
                )

            live_item = live_items.get(item_id)
            if live_item is None:
                raise ValueError(f"{item_id} is missing from the live inventory")
            live_sha = live_item.get("sha")
            live_last_modified = live_item.get("lastModified")
            live_card_digest = live_item.get("cardSemanticSha256")
            if live_sha is None or live_last_modified is None:
                raise ValueError(
                    f"live {item_id} sha and lastModified must both be present"
                )
            if not isinstance(live_sha, str) or not GIT_SHA_RE.fullmatch(live_sha):
                raise ValueError(
                    f"live {item_id} sha must be a 40-character Git SHA"
                )
            if (
                not isinstance(live_card_digest, str)
                or not SHA256_RE.fullmatch(live_card_digest)
            ):
                raise ValueError(
                    f"live {item_id} cardSemanticSha256 must be a SHA-256 digest"
                )
            live_modified_at = parse_rfc3339_utc(
                live_last_modified,
                field=f"live {item_id} lastModified",
            )
            if live_modified_at > current:
                raise ValueError(
                    f"live {item_id} lastModified must not be in the future"
                )
            if live_sha == stored_sha:
                if live_modified_at != stored_modified_at:
                    raise ValueError(
                        f"{item_id} unchanged revision has conflicting lastModified"
                    )
                continue

            try:
                historical = fetch_revision(item_id, repo_type, stored_sha)
            except Exception as exc:
                raise ValueError(
                    f"{item_id} historical revision {stored_sha} is not verifiable: {exc}"
                ) from exc
            if historical.get("sha") != stored_sha:
                raise ValueError(
                    f"{item_id} historical revision did not resolve to {stored_sha}"
                )
            if historical.get("id") != item_id:
                raise ValueError(
                    f"{item_id} historical revision resolved to another repository"
                )
            historical_modified_at = parse_rfc3339_utc(
                historical.get("lastModified"),
                field=f"{item_id} historical lastModified",
            )
            if historical_modified_at != stored_modified_at:
                raise ValueError(
                    f"{item_id} lastModified does not match its historical revision"
                )
            historical_card_digest = card_semantic_sha256(
                fetch_card_markdown(item_id, repo_type, stored_sha)
            )
            if historical_card_digest != stored_card_digest:
                raise ValueError(
                    f"{item_id} cardSemanticSha256 does not match its "
                    "historical revision"
                )

            if live_modified_at <= stored_modified_at:
                raise ValueError(
                    f"{item_id} live revision differs but is not newer than "
                    "the checked-in snapshot"
                )


def validate_generated_revision_evidence(
    manifest: dict[str, Any],
    *,
    observed_at: dt.datetime,
) -> None:
    """Require complete revision evidence that existed by the observation time."""

    for plural in ("models", "datasets", "spaces"):
        for item in manifest.get("inventory", {}).get(plural, []):
            item_id = item.get("id") if isinstance(item, dict) else None
            if not isinstance(item_id, str) or not item_id:
                raise ValueError(f"inventory.{plural} entry has no repository id")
            sha = item.get("sha")
            last_modified = item.get("lastModified")
            card_digest = item.get("cardSemanticSha256")
            if sha is None or last_modified is None:
                raise ValueError(
                    f"{item_id} sha and lastModified must both be present"
                )
            if not isinstance(sha, str) or not GIT_SHA_RE.fullmatch(sha):
                raise ValueError(f"{item_id} sha must be a 40-character Git SHA")
            if (
                not isinstance(card_digest, str)
                or not SHA256_RE.fullmatch(card_digest)
            ):
                raise ValueError(
                    f"{item_id} cardSemanticSha256 must be a SHA-256 digest"
                )
            modified_at = parse_rfc3339_utc(
                last_modified,
                field=f"{item_id} lastModified",
            )
            if modified_at > observed_at:
                raise ValueError(
                    f"{item_id} lastModified must not be later than observedAt"
                )


def evidence_url(item_id: str, repo_type: str) -> str:
    prefix = {"model": "", "dataset": "datasets/", "space": "spaces/"}[repo_type]
    return f"https://huggingface.co/{prefix}{item_id}"


def display_path(path: Path) -> Path:
    try:
        return path.relative_to(REPO_ROOT)
    except ValueError:
        return path


def semantic_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    """Return the stable public-estate contract used by ``--check``.

    ``observedAt``, ``sha``, and ``lastModified`` remain truthful snapshot
    evidence in the checked-in file. Hugging Face's content-derived dataset
    ``size_categories:*``, ``modality:*``, ``format:*``, and ``library:*`` tags
    are also excluded because Hugging Face derives them from dataset content and
    may temporarily omit them while metadata is converging. Curated tags and
    ``cardSemanticSha256`` remain in this comparison, so claim or policy drift
    still fails closed. A write refreshes every snapshot field.
    """
    stable = json.loads(json.dumps(manifest))
    for repo_type in ("models", "datasets", "spaces"):
        for item in stable.get("inventory", {}).get(repo_type, []):
            item.pop("sha", None)
            item.pop("lastModified", None)
            if repo_type == "datasets" and isinstance(item.get("tags"), list):
                item["tags"] = [
                    tag
                    for tag in item["tags"]
                    if not (
                        isinstance(tag, str)
                        and tag.startswith(
                            (
                                "size_categories:",
                                "modality:",
                                "format:",
                                "library:",
                            )
                        )
                    )
                ]
    return stable


def item_summary(item: dict[str, Any], repo_type: str) -> dict[str, Any]:
    item_id = item.get("id") or item.get("modelId")
    tags = item.get("tags") or []
    card = item.get("cardData") or {}
    revision = item.get("sha")
    if not isinstance(revision, str) or not GIT_SHA_RE.fullmatch(revision):
        raise ValueError(
            f"{item_id} sha must be a 40-character Git SHA before card fetch"
        )
    card_digest = card_semantic_sha256(
        fetch_card_markdown(str(item_id), repo_type, revision)
    )
    return {
        "id": item_id,
        "repoType": repo_type,
        "private": bool(item.get("private", False)),
        "gated": bool(item.get("gated", False)),
        "disabled": bool(item.get("disabled", False)),
        "sdk": item.get("sdk"),
        "license": card.get("license") or next((tag.removeprefix("license:") for tag in tags if isinstance(tag, str) and tag.startswith("license:")), None),
        "sha": item.get("sha"),
        "lastModified": item.get("lastModified"),
        "cardSemanticSha256": card_digest,
        "createdAt": item.get("createdAt"),
        "tags": tags,
        "claimStatus": "generated-mirror" if item_id == "SZLHOLDINGS/a11oy-v19-substrate" else "inventory",
        "evidenceUrls": [
            evidence_url(str(item_id), repo_type),
        ],
        "unsafeFlags": unsafe_flags(str(item_id), repo_type, tags, card),
    }


def unsafe_flags(item_id: str, repo_type: str, tags: list[Any], card: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    text = json.dumps({"id": item_id, "tags": tags, "card": card}, sort_keys=True).lower()
    if any(name in text for name in ["kora", "lumina", "paragon", "lyte"]):
        flags.append("stale-product-name-review")
    if item_id in {
        "SZLHOLDINGS/counsel-source",
        "SZLHOLDINGS/terra-source",
        "SZLHOLDINGS/carlota-jo-source",
    }:
        flags.append("funded-roadmap-scaffold-not-active-demo")
    if item_id == "SZLHOLDINGS/SZLHOLDINGS":
        flags.append("org-profile-duplicate-review")
    if repo_type == "space" and any(fragment in item_id for fragment in ["deep-dive", "platform"]):
        flags.append("space-card-should-link-github-commit")
    return flags


def build_manifest(*, observed_at: str | None) -> dict[str, Any]:
    models = [item_summary(item, "model") for item in api_items("models")]
    datasets = [item_summary(item, "dataset") for item in api_items("datasets")]
    spaces = [item_summary(item, "space") for item in api_items("spaces")]
    observed_at = observed_at or observed_at_now()
    counts = {
        "models": len(models),
        "datasets": len(datasets),
        "spaces": len(spaces),
    }
    return {
        "schemaVersion": 1,
        "generatedBy": "scripts/audit_huggingface_ecosystem.py",
        "observedAt": observed_at,
        "org": ORG,
        "inventoryScope": {
            "visibility": "public-only",
            "authenticated": False,
            "privateAssetsIncluded": False,
            "countMeaning": "Items returned by the author-filtered public APIs; not the authenticated organization total.",
            "revisionFields": (
                "Every item has sha and lastModified snapshot evidence plus a "
                "cardSemanticSha256 claim digest at observedAt; --check verifies "
                "retained revisions, rejects card and curated-tag drift, and "
                "ignores only complete, valid later source-only revision changes "
                "and Hugging Face-generated dataset size, modality, format, "
                "or library tags."
            ),
        },
        "canonicalGitHubRepo": "https://github.com/szl-holdings/a11oy",
        "canonicalRule": "GitHub releases, CI, manifests, checksums, and DOI records are canonical; Hugging Face is a generated discovery and diligence mirror.",
        "publicApiEndpoints": [
            f"https://huggingface.co/api/models?author={ORG}&limit={PAGE_LIMIT}&full=true",
            f"https://huggingface.co/api/datasets?author={ORG}&limit={PAGE_LIMIT}&full=true",
            f"https://huggingface.co/api/spaces?author={ORG}&limit={PAGE_LIMIT}&full=true",
        ],
        "counts": counts,
        "guardrails": [
            "Do not present Counsel, Terra, or Carlota Jo as active demo surfaces.",
            "Do not use KORA, LUMINA, PARAGON, or active Lyte framing.",
            "Do not claim zero-sorry or all-green Lean proof status without current machine-readable proof evidence.",
            "Do not claim signed UDS release assets exist unless tarball, signature, sha256, and public key assets are present and verify.",
        ],
        "inventory": {
            "models": models,
            "datasets": datasets,
            "spaces": spaces,
        },
        "recommendedActions": [
            {
                "target": "SZLHOLDINGS/a11oy-v19-substrate",
                "action": "Republish from dist/huggingface/a11oy after every GitHub canonical-source change.",
            },
            {
                "target": "SZLHOLDINGS/SZLHOLDINGS",
                "action": "Replace duplicate org-profile model/dataset copy with generated counts and GitHub source links, or deprecate.",
            },
            {
                "target": "source mirrors",
                "action": "Add generated card section: GitHub repo, exact commit, release/CI, DOI, claim status, limitations.",
            },
            {
                "target": "counsel-source/terra-source/carlota-jo-source",
                "action": "Mark funded-roadmap scaffold and remove from active-demo collections until funded.",
            },
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--check", action="store_true")
    parser.add_argument(
        "--observed-at",
        help="Explicit RFC 3339 observation time for deterministic generation.",
    )
    args = parser.parse_args()
    output = Path(args.output)
    if args.check:
        if not output.exists():
            print(f"Hugging Face ecosystem manifest is stale: {output}")
            return 1
        try:
            existing = json.loads(output.read_text(encoding="utf-8"))
            observed_at = existing["observedAt"]
            parsed_observed_at = validate_observed_at(observed_at)
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            print(f"Hugging Face ecosystem manifest is invalid: {output}: {exc}")
            return 1
        live = build_manifest(observed_at=observed_at)
        try:
            validate_snapshot_revisions(
                existing,
                live,
                observed_at=parsed_observed_at,
            )
        except (TypeError, ValueError) as exc:
            print(f"Hugging Face ecosystem manifest is invalid: {output}: {exc}")
            return 1
        canonical_existing = json.dumps(existing, indent=2, sort_keys=False) + "\n"
        if output.read_text(encoding="utf-8") != canonical_existing:
            print(f"Hugging Face ecosystem manifest is not canonically rendered: {output}")
            return 1
        if semantic_manifest(existing) != semantic_manifest(live):
            print(f"Hugging Face ecosystem manifest is stale: {output}")
            return 1
        print(f"Hugging Face ecosystem manifest is current: {display_path(output)}")
        return 0
    observed_at = args.observed_at
    if observed_at is not None:
        try:
            validate_observed_at(observed_at)
        except ValueError as exc:
            print(f"Invalid Hugging Face ecosystem observation time: {exc}")
            return 1
    manifest = build_manifest(observed_at=observed_at)
    try:
        parsed_observed_at = validate_observed_at(manifest["observedAt"])
        validate_generated_revision_evidence(
            manifest,
            observed_at=parsed_observed_at,
        )
    except (KeyError, TypeError, ValueError) as exc:
        print(f"Invalid Hugging Face ecosystem snapshot evidence: {exc}")
        return 1
    rendered = json.dumps(manifest, indent=2, sort_keys=False) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"Wrote Hugging Face ecosystem manifest: {display_path(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
