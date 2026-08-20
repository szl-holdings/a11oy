"""Offline, fail-closed guard for SZL Hugging Face staging and promotion.

This module intentionally contains no Hugging Face client, HTTP client, token
lookup, subprocess upload, or repository mutation path.  It can audit the
checked-in contracts and inventory a future local payload.  Canonical publish
remains a separate, named-human action after every gate passes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DEFAULT_MANIFEST = HERE / "promotion-manifest.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ATTEMPT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$")
SAFE_TEXT_EXTENSIONS = {".json", ".jsonl", ".md", ".txt", ".yaml", ".yml"}
SAFE_MODEL_EXTENSIONS = {".safetensors"}
CANONICAL_LF_EXTENSIONS = SAFE_TEXT_EXTENSIONS | {".py", ".ps1", ".sh", ".toml"}
CANONICAL_LF_FILENAMES = {"Modelfile"}


class PromotionGuardError(RuntimeError):
    """The offline contract or prospective payload failed closed."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _artifact_identity(path: Path) -> tuple[int, str, str]:
    """Return a clone-stable identity for a manifest-bound artifact.

    Git stores the repository's text artifacts with LF endings. Windows tools
    can materialize CRLF in a working tree despite that contract, so hashing
    raw text bytes makes an otherwise identical release fail on Linux. Text is
    therefore decoded strictly as UTF-8 and normalized to LF before hashing;
    future binary payloads remain byte-exact.
    """

    raw = path.read_bytes()
    if path.suffix.lower() in CANONICAL_LF_EXTENSIONS or path.name in CANONICAL_LF_FILENAMES:
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise PromotionGuardError(f"manifest-bound text is not UTF-8: {path}") from exc
        canonical = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
        return len(canonical), hashlib.sha256(canonical).hexdigest(), "UTF8_LF"
    return len(raw), hashlib.sha256(raw).hexdigest(), "RAW_BYTES"


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PromotionGuardError(f"expected JSON object: {path}")
    return value


def _inside_root(relative_path: str, root: Path) -> Path:
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise PromotionGuardError(f"path escapes repository root: {relative_path}") from exc
    return candidate


def _candidate_by_id(manifest: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    matches = [item for item in manifest["candidates"] if item["candidate_id"] == candidate_id]
    if len(matches) != 1:
        raise PromotionGuardError(f"candidate id must resolve exactly once: {candidate_id}")
    return matches[0]


def audit_contract(
    manifest_path: Path = DEFAULT_MANIFEST,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Verify hashes, card truth, bucket prefixes, and fail-closed gates offline."""

    manifest = _load_json(manifest_path)
    errors: list[str] = []
    observations: list[dict[str, Any]] = []

    expected_top = {
        "mode": "OFFLINE_AUDIT_ONLY",
        "network_access_allowed": False,
        "credential_access_allowed": False,
        "automatic_upload_allowed": False,
        "bucket_authority": "MUTABLE_NONCANONICAL_STAGING_ONLY",
        "local_artifact_hash_basis": "TEXT_UTF8_LF_BINARY_RAW",
    }
    for field, expected in expected_top.items():
        if manifest.get(field) != expected:
            errors.append(f"{field} must be {expected!r}")

    topology_path = _inside_root(manifest.get("topology_contract", ""), root)
    if not topology_path.is_file():
        errors.append(f"bucket topology contract missing: {topology_path}")
    else:
        topology = _load_json(topology_path)
        qualified = {item["qualified_name"] for item in topology.get("topology", [])}
        required = {
            "SZLHOLDINGS/szl-forge-build-staging",
            "SZLHOLDINGS/szl-forge-eval-staging",
            "SZLHOLDINGS/szl-forge-runtime-evidence",
        }
        if not required.issubset(qualified):
            errors.append("bucket topology is missing one or more required private staging buckets")
        if topology.get("scope", {}).get("canonical_release_store") is not False:
            errors.append("bucket topology must remain noncanonical")

    candidate_ids: set[str] = set()
    candidate_slugs: set[str] = set()
    all_paths: set[str] = set()
    for candidate in manifest.get("candidates", []):
        candidate_id = candidate.get("candidate_id", "")
        slug = candidate.get("candidate_slug", "")
        if candidate_id in candidate_ids:
            errors.append(f"duplicate candidate_id: {candidate_id}")
        candidate_ids.add(candidate_id)
        if slug in candidate_slugs:
            errors.append(f"duplicate candidate_slug: {slug}")
        candidate_slugs.add(slug)

        gate_ids: set[str] = set()
        nonpassing: list[str] = []
        for gate in candidate.get("qualification_gates", []):
            if gate["gate_id"] in gate_ids:
                errors.append(f"{candidate_id}: duplicate gate {gate['gate_id']}")
            gate_ids.add(gate["gate_id"])
            if gate.get("blocking") is not True:
                errors.append(f"{candidate_id}: all declared promotion gates must block")
            if gate.get("state") != "PASS":
                nonpassing.append(gate["gate_id"])
        if nonpassing and not str(candidate.get("promotion_decision", "")).startswith("BLOCKED_"):
            errors.append(f"{candidate_id}: nonpassing gates require a BLOCKED promotion decision")

        prefixes = candidate.get("bucket_prefixes", {})
        expected_roots = {
            "build": "attempts/{attempt_id}/payload/",
            "evaluation": "attempts/{attempt_id}/payload/",
            "runtime": "batches/{attempt_id}/payload/",
        }
        for role, expected_root in expected_roots.items():
            prefix = prefixes.get(role, "")
            if not prefix.startswith(expected_root) or not prefix.endswith(f"/{slug}/"):
                errors.append(f"{candidate_id}: invalid {role} bucket prefix {prefix!r}")
            if ".." in prefix or "\\" in prefix or prefix.startswith("/"):
                errors.append(f"{candidate_id}: unsafe {role} bucket prefix {prefix!r}")
            if any(alias in prefix.lower().split("/") for alias in ("latest", "main", "current")):
                errors.append(f"{candidate_id}: mutable alias in {role} bucket prefix")

        for artifact in candidate.get("local_artifacts", []):
            relative = artifact["path"]
            if relative in all_paths:
                errors.append(f"artifact path is bound by multiple candidates: {relative}")
            all_paths.add(relative)
            path = _inside_root(relative, root)
            if not path.is_file():
                errors.append(f"{candidate_id}: missing local artifact {relative}")
                continue
            actual_bytes, actual_sha, hash_basis = _artifact_identity(path)
            if actual_bytes != artifact["bytes"]:
                errors.append(
                    f"{candidate_id}: byte mismatch for {relative}: "
                    f"expected {artifact['bytes']}, got {actual_bytes}"
                )
            if actual_sha != artifact["sha256"]:
                errors.append(
                    f"{candidate_id}: sha256 mismatch for {relative}: "
                    f"expected {artifact['sha256']}, got {actual_sha}"
                )
            observations.append(
                {
                    "candidate_id": candidate_id,
                    "path": relative,
                    "bytes": actual_bytes,
                    "sha256": actual_sha,
                    "hash_basis": hash_basis,
                }
            )

        card_contract = candidate.get("model_card_truth", {})
        card_path = _inside_root(card_contract.get("path", ""), root)
        if not card_path.is_file():
            errors.append(f"{candidate_id}: model card missing: {card_path}")
        else:
            card = card_path.read_text(encoding="utf-8")
            for literal in card_contract.get("required_literals", []):
                if literal not in card:
                    errors.append(f"{candidate_id}: model card missing truth literal {literal!r}")
            lowered = card.lower()
            for forbidden in card_contract.get("forbidden_case_insensitive_literals", []):
                if forbidden.lower() in lowered:
                    errors.append(f"{candidate_id}: model card contains forbidden claim {forbidden!r}")

    for suffix in manifest.get("forbidden_file_extensions", []):
        if not re.fullmatch(r"\.[a-z0-9]+", suffix):
            errors.append(f"invalid forbidden file extension: {suffix!r}")

    return {
        "schema_version": "szl.hf-promotion-audit.v1",
        "manifest_id": manifest.get("manifest_id"),
        "offline": True,
        "credentials_accessed": False,
        "network_accessed": False,
        "contract_integrity": "PASS" if not errors else "FAIL",
        "promotion_performed": False,
        "candidate_decisions": {
            item["candidate_id"]: item["promotion_decision"] for item in manifest.get("candidates", [])
        },
        "observed_artifacts": observations,
        "errors": errors,
    }


def inventory_payload(payload_dir: Path, forbidden_extensions: set[str]) -> list[dict[str, Any]]:
    """Hash a future local payload while rejecting unsafe model serialization."""

    payload_dir = payload_dir.resolve()
    if not payload_dir.is_dir():
        raise PromotionGuardError(f"payload directory does not exist: {payload_dir}")
    entries: list[dict[str, Any]] = []
    for path in sorted(payload_dir.rglob("*")):
        if path.is_symlink():
            raise PromotionGuardError(f"symlink payload is forbidden: {path}")
        if not path.is_file():
            continue
        relative = path.relative_to(payload_dir).as_posix()
        if ".." in Path(relative).parts:
            raise PromotionGuardError(f"unsafe payload path: {relative}")
        suffix = path.suffix.lower()
        if suffix in forbidden_extensions:
            raise PromotionGuardError(f"forbidden payload extension {suffix}: {relative}")
        if suffix not in SAFE_TEXT_EXTENSIONS | SAFE_MODEL_EXTENSIONS:
            raise PromotionGuardError(f"non-allowlisted payload extension {suffix}: {relative}")
        entries.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
        )
    if not entries:
        raise PromotionGuardError("empty payload is not stageable")
    return entries


def validate_peft_payload(
    payload_dir: Path,
    inventory: list[dict[str, Any]],
    expected_candidate_id: str,
) -> None:
    """Require safetensors and an exact external qualification binding for PEFT."""

    by_name = {item["path"]: item for item in inventory}
    required = {"adapter_model.safetensors", "adapter_config.json", "candidate-qualification.json"}
    missing = sorted(required - set(by_name))
    if missing:
        raise PromotionGuardError(f"PEFT payload missing required files: {missing}")
    if any(name == "model.safetensors" or name.startswith("model-") for name in by_name):
        raise PromotionGuardError("PEFT payload must not include full base-model weights")

    config = _load_json(payload_dir / "adapter_config.json")
    qualification = _load_json(payload_dir / "candidate-qualification.json")
    if qualification.get("candidate_id") != expected_candidate_id:
        raise PromotionGuardError("qualification candidate_id mismatch")
    if qualification.get("schema_version") != "szl.hf-candidate-qualification.v1":
        raise PromotionGuardError("qualification schema_version mismatch")
    if qualification.get("artifact_class") != "PEFT_ADAPTER":
        raise PromotionGuardError("qualification artifact_class mismatch")
    if qualification.get("decision") != "QUALIFIED_FOR_NAMED_HUMAN_PROMOTION_REVIEW":
        raise PromotionGuardError("payload qualification decision is not review-qualified")
    if qualification.get("base_repository") != "unsloth/Qwen2.5-1.5B-Instruct-bnb-4bit":
        raise PromotionGuardError("ReceiptAgent base repository mismatch")
    if qualification.get("base_revision") != "d2f2dd02b071701d5100a04a7a49d6fb0bd305b7":
        raise PromotionGuardError("ReceiptAgent base revision mismatch")
    if config.get("base_model_name_or_path") != qualification["base_repository"]:
        raise PromotionGuardError("adapter config base does not match qualification")

    expected_hash_fields = {
        "adapter_model_sha256": by_name["adapter_model.safetensors"]["sha256"],
        "adapter_config_sha256": by_name["adapter_config.json"]["sha256"],
    }
    for field, actual in expected_hash_fields.items():
        if qualification.get(field) != actual:
            raise PromotionGuardError(f"qualification {field} does not match payload")
    for field in (
        "base_file_set_sha256",
        "training_receipt_sha256",
        "reload_receipt_sha256",
        "evaluation_receipt_sha256",
        "license_review_sha256",
        "human_approval_sha256",
        "dsse_attestation_sha256",
    ):
        if not SHA256_RE.fullmatch(str(qualification.get(field, ""))):
            raise PromotionGuardError(f"missing or invalid qualification digest: {field}")
    evaluation = qualification.get("evaluation", {})
    if evaluation.get("all_required_suites_passed") is not True:
        raise PromotionGuardError("qualification does not pass every required evaluation suite")
    if evaluation.get("catastrophic_errors_observed") != 0:
        raise PromotionGuardError("qualification catastrophic-error budget is not zero")
    if not SHA256_RE.fullmatch(str(evaluation.get("held_out_split_sha256", ""))):
        raise PromotionGuardError("qualification held_out_split_sha256 is invalid")
    expected_effects = {
        "bucket_objects_uploaded": False,
        "hub_repository_mutated": False,
        "published": False,
        "promoted": False,
    }
    if qualification.get("external_mutations") != expected_effects:
        raise PromotionGuardError("qualification must precede every external mutation")


def build_stage_plan(
    candidate_id: str,
    payload_dir: Path,
    attempt_id: str,
    manifest_path: Path = DEFAULT_MANIFEST,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Build a local plan only; refuse while any promotion gate is non-PASS."""

    audit = audit_contract(manifest_path=manifest_path, root=root)
    if audit["contract_integrity"] != "PASS":
        raise PromotionGuardError("promotion contract integrity failed")
    manifest = _load_json(manifest_path)
    candidate = _candidate_by_id(manifest, candidate_id)
    nonpassing = [gate["gate_id"] for gate in candidate["qualification_gates"] if gate["state"] != "PASS"]
    if nonpassing:
        raise PromotionGuardError(
            f"candidate remains blocked by {','.join(nonpassing)}; no payload was staged or uploaded"
        )
    if not SAFE_ATTEMPT_RE.fullmatch(attempt_id):
        raise PromotionGuardError("attempt_id must be a never-reused safe identifier of 8-128 characters")

    forbidden = set(manifest["forbidden_file_extensions"])
    inventory = inventory_payload(payload_dir, forbidden)
    if candidate["artifact_class"] == "PEFT_ADAPTER":
        validate_peft_payload(payload_dir.resolve(), inventory, candidate_id)
    prefix = candidate["bucket_prefixes"]["build"].replace("{attempt_id}", attempt_id)
    return {
        "schema_version": "szl.hf-offline-stage-plan.v1",
        "candidate_id": candidate_id,
        "attempt_id": attempt_id,
        "bucket_prefix": prefix,
        "inventory": inventory,
        "network_accessed": False,
        "credentials_accessed": False,
        "objects_uploaded": False,
        "canonical_publish_performed": False,
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    audit_parser = subparsers.add_parser("audit", help="audit checked-in contracts offline")
    audit_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    plan_parser = subparsers.add_parser("stage-plan", help="build a local stage plan; never upload")
    plan_parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    plan_parser.add_argument("--candidate", required=True)
    plan_parser.add_argument("--payload-dir", type=Path, required=True)
    plan_parser.add_argument("--attempt-id", required=True)
    args = parser.parse_args(argv)

    try:
        if args.command == "audit":
            result = audit_contract(manifest_path=args.manifest)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0 if result["contract_integrity"] == "PASS" else 2
        result = build_stage_plan(
            candidate_id=args.candidate,
            payload_dir=args.payload_dir,
            attempt_id=args.attempt_id,
            manifest_path=args.manifest,
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, PromotionGuardError) as exc:
        print(json.dumps({"state": "BLOCKED", "reason": str(exc), "external_mutations": False}, indent=2))
        return 3


if __name__ == "__main__":
    raise SystemExit(_main())
