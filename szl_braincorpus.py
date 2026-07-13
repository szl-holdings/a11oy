# SPDX-License-Identifier: Apache-2.0
"""Bounded, content-addressed local corpus admission for the A11oy Brain.

This module is intentionally an *admission/status* boundary, not a harvester and not a
trainer.  It reads only three operator-selected JSON manifests, verifies local bytes, and
classifies every item without changing any Brain trust threshold.  Missing sources remain
``SOURCE_UNAVAILABLE``; malformed, conflicting, or weakly evidenced claims are quarantined.

No request parameter can choose a filesystem path.  Defaults are repo-confined.  An operator
may opt into one explicit manifest path per source through a named environment variable; an
explicit manifest may reference only relative artifacts below its own directory.
"""

from __future__ import annotations

import datetime as _datetime
import hashlib
import json
import os
import pathlib
import re
from collections import defaultdict
from typing import Any, Mapping, Sequence

SCHEMA_VERSION = "szl.brain.corpus-evidence.v1"
PROOF_RECEIPT_SCHEMA = "szl.lean-kernel-proof-receipt.v1"
ARTIFACT_RECEIPT_SCHEMA = "szl.brain.artifact-receipt.v1"
SOURCE_TYPES = ("szl_lake", "lean_mathlib", "formula")
EVIDENCE_CLASSES = ("PROVED", "OPEN", "REFUTED", "EXPERIMENTAL", "UNKNOWN")

MAX_MANIFEST_BYTES = 8 * 1024 * 1024
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_ENTRIES = 5_000

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
_FORMULA_ID_RE = re.compile(r"^F[1-9][0-9]*$", re.IGNORECASE)

DEFAULT_MANIFESTS = {
    "szl_lake": pathlib.Path("data/szl-lake/evidence-manifest.json"),
    "lean_mathlib": pathlib.Path("docs/thesis/v18/lean-corpus-evidence.json"),
    "formula": pathlib.Path("corpus/formulas/formula-corpus-evidence.json"),
}
MANIFEST_ENV = {
    "szl_lake": "A11OY_BRAIN_CORPUS_SZL_LAKE_MANIFEST",
    "lean_mathlib": "A11OY_BRAIN_CORPUS_LEAN_MANIFEST",
    "formula": "A11OY_BRAIN_CORPUS_FORMULA_MANIFEST",
}

MANIFEST_CONTRACT = {
    "schema_version": SCHEMA_VERSION,
    "source_types": list(SOURCE_TYPES),
    "evidence_classes": list(EVIDENCE_CLASSES),
    "required_top_level": ["schema_version", "source_type", "version", "entries"],
    "entry_required": ["id", "evidence_class", "source_path", "artifact_sha256"],
    "artifact_receipt_optional": {
        "schema_version": ARTIFACT_RECEIPT_SCHEMA,
        "purpose": (
            "bind the admitted artifact to exact local source bytes and licenses; this "
            "receipt never grants mathematical proof credit"
        ),
    },
    "proof_receipt_required_for_proved": [
        "schema_version", "verified", "artifact_sha256", "sorry_count",
        "kernel_commit", "lean_commit", "mathlib_commit", "receipt_sha256",
    ],
    "proof_rule": (
        "PROVED requires verified local artifact bytes, zero sorry/admit obligations, an exact "
        "40-hex kernel/Lean/mathlib commit triple matching the manifest toolchain, and a valid "
        "content-addressed kernel receipt"
    ),
    "non_uplift_rule": (
        "OPEN, REFUTED, EXPERIMENTAL, UNKNOWN, invalid PROVED claims, and F-ID conflicts "
        "receive zero proof credit and cannot raise query trust"
    ),
    "path_rule": (
        "default manifests and artifacts are repo-confined; explicitly configured manifests "
        "may read only relative artifacts confined below that manifest's directory"
    ),
}


def _utc_now() -> str:
    return _datetime.datetime.now(_datetime.timezone.utc).isoformat()


def _canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_json(value: Any) -> str:
    """Return the canonical JSON SHA-256 used by proof receipts and fixture builders."""
    return hashlib.sha256(_canonical_json_bytes(value)).hexdigest()


def _sha256_file(path: pathlib.Path, maximum: int) -> tuple[str | None, int, str | None]:
    try:
        size = path.stat().st_size
        if size > maximum:
            return None, size, f"FILE_TOO_LARGE:{size}>{maximum}"
        digest = hashlib.sha256()
        read = 0
        with path.open("rb") as stream:
            while True:
                chunk = stream.read(1024 * 1024)
                if not chunk:
                    break
                read += len(chunk)
                if read > maximum:
                    return None, read, f"FILE_TOO_LARGE:{read}>{maximum}"
                digest.update(chunk)
        return digest.hexdigest(), read, None
    except OSError as exc:
        return None, 0, f"READ_FAILED:{type(exc).__name__}"


def _read_file_bounded(path: pathlib.Path, maximum: int) -> tuple[bytes | None, str | None]:
    """Read once so the bytes parsed are exactly the bytes that receive the content hash."""
    try:
        with path.open("rb") as stream:
            raw = stream.read(maximum + 1)
        if len(raw) > maximum:
            return None, f"FILE_TOO_LARGE:{len(raw)}>{maximum}"
        return raw, None
    except OSError as exc:
        return None, f"READ_FAILED:{type(exc).__name__}"


def _inside(path: pathlib.Path, boundary: pathlib.Path) -> bool:
    try:
        path.relative_to(boundary)
        return True
    except ValueError:
        return False


def _safe_manifest_path(
    source_type: str,
    repo_root: pathlib.Path,
    environ: Mapping[str, str],
) -> tuple[pathlib.Path, pathlib.Path, str, str | None]:
    """Resolve one fixed source path; no API/user value participates in this decision."""
    env_name = MANIFEST_ENV[source_type]
    configured = str(environ.get(env_name, "")).strip()
    root = repo_root.resolve()
    if configured:
        raw = pathlib.Path(configured).expanduser()
        path = (root / raw if not raw.is_absolute() else raw).resolve()
        boundary = path.parent
        origin = f"EXPLICIT_CONFIG:{env_name}"
    else:
        path = (root / DEFAULT_MANIFESTS[source_type]).resolve()
        boundary = root
        origin = "REPO_DEFAULT"
        if not _inside(path, root):
            return path, boundary, origin, "MANIFEST_PATH_ESCAPES_REPO"
    if path.suffix.lower() != ".json":
        return path, boundary, origin, "MANIFEST_MUST_BE_JSON"
    return path, boundary, origin, None


def _entry_shell(entry: Any, source_type: str, ordinal: int) -> dict[str, Any]:
    entry_id = entry.get("id") if isinstance(entry, dict) else None
    return {
        "id": str(entry_id or f"entry-{ordinal}"),
        "source_type": source_type,
        "declared_class": "UNKNOWN",
        "effective_class": "UNKNOWN",
        "artifact_sha256": None,
        "artifact_verified": False,
        "artifact_receipt_valid": False,
        "proof_receipt_valid": False,
        "proof_credit": 0,
        "trust_uplift_eligible": False,
        "disposition": "QUARANTINED",
        "quarantine_reasons": [],
    }


def _validate_artifact_receipt(
    receipt: Any,
    artifact_sha256: str,
    artifact_boundary: pathlib.Path,
) -> tuple[bool, list[str], dict[str, Any] | None]:
    """Verify an optional local-byte receipt without upgrading proof status."""
    if receipt is None:
        return False, [], None
    if not isinstance(receipt, dict):
        return False, ["ARTIFACT_RECEIPT_NOT_OBJECT"], None
    reasons: list[str] = []
    if receipt.get("schema_version") != ARTIFACT_RECEIPT_SCHEMA:
        reasons.append("ARTIFACT_RECEIPT_SCHEMA_MISMATCH")
    if receipt.get("verified") is not True:
        reasons.append("ARTIFACT_RECEIPT_NOT_VERIFIED")
    if str(receipt.get("artifact_sha256") or "").lower() != artifact_sha256:
        reasons.append("ARTIFACT_RECEIPT_ARTIFACT_MISMATCH")
    if receipt.get("proof_credit") not in {0, 0.0}:
        reasons.append("ARTIFACT_RECEIPT_PROOF_CREDIT_FORBIDDEN")

    assets = receipt.get("source_assets")
    if not isinstance(assets, list) or not assets:
        reasons.append("ARTIFACT_RECEIPT_SOURCE_ASSETS_REQUIRED")
        assets = []
    elif len(assets) > 128:
        reasons.append("ARTIFACT_RECEIPT_TOO_MANY_SOURCE_ASSETS")
        assets = assets[:128]
    public_assets: list[dict[str, Any]] = []
    for ordinal, asset in enumerate(assets):
        if not isinstance(asset, dict):
            reasons.append(f"ARTIFACT_RECEIPT_ASSET_NOT_OBJECT:{ordinal}")
            continue
        path_value = str(asset.get("path") or "").strip()
        expected = str(asset.get("sha256") or "").lower()
        license_id = str(asset.get("license") or "").strip()
        if not path_value:
            reasons.append(f"ARTIFACT_RECEIPT_ASSET_PATH_REQUIRED:{ordinal}")
            continue
        relative = pathlib.Path(path_value)
        path = (artifact_boundary / relative).resolve() if not relative.is_absolute() else None
        if path is None or not _inside(path, artifact_boundary):
            reasons.append(f"ARTIFACT_RECEIPT_ASSET_PATH_FORBIDDEN:{ordinal}")
            continue
        if not _SHA256_RE.fullmatch(expected):
            reasons.append(f"ARTIFACT_RECEIPT_ASSET_SHA_INVALID:{ordinal}")
        if not license_id or license_id.upper() == "UNKNOWN":
            reasons.append(f"ARTIFACT_RECEIPT_ASSET_LICENSE_UNKNOWN:{ordinal}")
        actual, size, read_error = _sha256_file(path, MAX_ARTIFACT_BYTES)
        if read_error:
            reasons.append(f"ARTIFACT_RECEIPT_ASSET_{read_error}:{ordinal}")
        elif actual != expected:
            reasons.append(f"ARTIFACT_RECEIPT_ASSET_SHA_MISMATCH:{ordinal}")
        public_assets.append({
            "path": path_value.replace("\\", "/"),
            "sha256": expected or None,
            "license": license_id or None,
            "bytes": size,
        })

    stored = str(receipt.get("receipt_sha256") or "").lower()
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    if not _SHA256_RE.fullmatch(stored) or stored != sha256_json(body):
        reasons.append("ARTIFACT_RECEIPT_DIGEST_MISMATCH")
    public = {
        "schema_version": receipt.get("schema_version"),
        "verified": receipt.get("verified") is True,
        "artifact_sha256": str(receipt.get("artifact_sha256") or "").lower() or None,
        "proof_credit": receipt.get("proof_credit"),
        "source_asset_count": len(public_assets),
        "source_assets": public_assets,
        "receipt_sha256": stored or None,
    }
    return not reasons, reasons, public


def _validate_toolchain(manifest: Mapping[str, Any]) -> tuple[dict[str, str], list[str]]:
    raw = manifest.get("toolchain")
    if not isinstance(raw, dict):
        return {}, ["TOOLCHAIN_REQUIRED_FOR_PROVED"]
    toolchain: dict[str, str] = {}
    reasons: list[str] = []
    for name in ("kernel_commit", "lean_commit", "mathlib_commit"):
        value = str(raw.get(name) or "").lower()
        if not _COMMIT_RE.fullmatch(value):
            reasons.append(f"INVALID_EXACT_{name.upper()}")
        else:
            toolchain[name] = value
    return toolchain, reasons


def _validate_receipt(
    receipt: Any,
    artifact_sha256: str,
    toolchain: Mapping[str, str],
) -> tuple[bool, list[str], dict[str, Any] | None]:
    if not isinstance(receipt, dict):
        return False, ["KERNEL_RECEIPT_REQUIRED"], None
    reasons: list[str] = []
    if receipt.get("schema_version") != PROOF_RECEIPT_SCHEMA:
        reasons.append("KERNEL_RECEIPT_SCHEMA_MISMATCH")
    if receipt.get("verified") is not True:
        reasons.append("KERNEL_RECEIPT_NOT_VERIFIED")
    if receipt.get("artifact_sha256") != artifact_sha256:
        reasons.append("KERNEL_RECEIPT_ARTIFACT_MISMATCH")
    try:
        receipt_sorries = int(receipt.get("sorry_count"))
    except (TypeError, ValueError):
        receipt_sorries = -1
    if receipt_sorries != 0:
        reasons.append("KERNEL_RECEIPT_NOT_ZERO_SORRY")
    for name in ("kernel_commit", "lean_commit", "mathlib_commit"):
        value = str(receipt.get(name) or "").lower()
        if not _COMMIT_RE.fullmatch(value):
            reasons.append(f"KERNEL_RECEIPT_INVALID_{name.upper()}")
        elif value != toolchain.get(name):
            reasons.append(f"KERNEL_RECEIPT_{name.upper()}_MISMATCH")
    stored = str(receipt.get("receipt_sha256") or "").lower()
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    computed = sha256_json(body)
    if not _SHA256_RE.fullmatch(stored) or stored != computed:
        reasons.append("KERNEL_RECEIPT_DIGEST_MISMATCH")
    public = {
        "schema_version": receipt.get("schema_version"),
        "verified": receipt.get("verified") is True,
        "sorry_count": receipt_sorries,
        "kernel_commit": receipt.get("kernel_commit"),
        "lean_commit": receipt.get("lean_commit"),
        "mathlib_commit": receipt.get("mathlib_commit"),
        "receipt_sha256": stored or None,
    }
    return not reasons, reasons, public


def _validate_entry(
    entry: Any,
    source_type: str,
    ordinal: int,
    artifact_boundary: pathlib.Path,
    toolchain: Mapping[str, str],
) -> dict[str, Any]:
    out = _entry_shell(entry, source_type, ordinal)
    reasons: list[str] = out["quarantine_reasons"]
    if not isinstance(entry, dict):
        reasons.append("ENTRY_NOT_OBJECT")
        return out

    entry_id = str(entry.get("id") or "").strip()
    if not entry_id:
        reasons.append("ENTRY_ID_REQUIRED")
    else:
        out["id"] = entry_id.upper() if _FORMULA_ID_RE.fullmatch(entry_id) else entry_id

    declared = str(entry.get("evidence_class") or "UNKNOWN").upper()
    if declared not in EVIDENCE_CLASSES:
        reasons.append("INVALID_EVIDENCE_CLASS")
        declared = "UNKNOWN"
    out["declared_class"] = declared
    out["effective_class"] = declared

    expected = str(entry.get("artifact_sha256") or "").lower()
    out["artifact_sha256"] = expected or None
    if not _SHA256_RE.fullmatch(expected):
        reasons.append("INVALID_ARTIFACT_SHA256")

    source_path = entry.get("source_path")
    if not isinstance(source_path, str) or not source_path.strip():
        reasons.append("SOURCE_PATH_REQUIRED")
        artifact_path = None
    else:
        relative = pathlib.Path(source_path.strip())
        if relative.is_absolute():
            reasons.append("ABSOLUTE_ARTIFACT_PATH_FORBIDDEN")
            artifact_path = None
        else:
            artifact_path = (artifact_boundary / relative).resolve()
            if not _inside(artifact_path, artifact_boundary):
                reasons.append("ARTIFACT_PATH_ESCAPES_BOUNDARY")
                artifact_path = None

    if artifact_path is not None:
        out["source_path"] = source_path.replace("\\", "/")
        if not artifact_path.is_file():
            reasons.append("ARTIFACT_SOURCE_UNAVAILABLE")
        else:
            actual, size, read_error = _sha256_file(artifact_path, MAX_ARTIFACT_BYTES)
            out["artifact_bytes"] = size
            out["computed_artifact_sha256"] = actual
            if read_error:
                reasons.append(read_error)
            elif actual != expected:
                reasons.append("ARTIFACT_SHA256_MISMATCH")
            else:
                out["artifact_verified"] = True

    try:
        sorry_count = int(entry.get("sorry_count", 0))
    except (TypeError, ValueError):
        sorry_count = -1
    if sorry_count < 0:
        reasons.append("INVALID_SORRY_COUNT")
        sorry_count = 0
    out["sorry_count"] = sorry_count

    artifact_receipt_valid, artifact_receipt_reasons, artifact_receipt_public = (
        _validate_artifact_receipt(entry.get("artifact_receipt"), expected, artifact_boundary)
    )
    reasons.extend(artifact_receipt_reasons)
    out["artifact_receipt_valid"] = artifact_receipt_valid
    out["artifact_receipt"] = artifact_receipt_public

    if declared == "PROVED":
        if sorry_count != 0:
            reasons.append("PROVED_REQUIRES_ZERO_SORRY")
        valid_receipt, receipt_reasons, receipt_public = _validate_receipt(
            entry.get("proof_receipt"), expected, toolchain,
        )
        reasons.extend(receipt_reasons)
        out["proof_receipt"] = receipt_public
        out["proof_receipt_valid"] = valid_receipt
        if reasons or not out["artifact_verified"] or not valid_receipt:
            out["effective_class"] = "UNKNOWN"
    else:
        out["proof_receipt"] = None
        out["proof_receipt_valid"] = False

    proof_eligible = bool(
        declared == "PROVED"
        and out["effective_class"] == "PROVED"
        and out["artifact_verified"]
        and out["proof_receipt_valid"]
        and not reasons
    )
    out["proof_credit"] = 1 if proof_eligible else 0
    out["trust_uplift_eligible"] = proof_eligible
    if proof_eligible:
        out["disposition"] = "ADMITTED_PROOF_EVIDENCE"
    elif not reasons and declared in {"OPEN", "REFUTED", "EXPERIMENTAL", "UNKNOWN"}:
        out["disposition"] = "QUARANTINED_NON_PROOF"
        reasons.append(f"{declared}_HAS_ZERO_PROOF_CREDIT")
    elif reasons:
        out["effective_class"] = "UNKNOWN"
    return out


def _load_manifest(
    source_type: str,
    manifest_path: pathlib.Path,
    artifact_boundary: pathlib.Path,
    origin: str,
) -> dict[str, Any]:
    public_path = (
        manifest_path.relative_to(artifact_boundary).as_posix()
        if origin == "REPO_DEFAULT"
        else f"<explicit-config>/{manifest_path.name}"
    )
    base: dict[str, Any] = {
        "source_type": source_type,
        "status": "SOURCE_UNAVAILABLE",
        "manifest_origin": origin,
        "manifest_path": public_path,
        "entries": [],
        "counts": {name: 0 for name in EVIDENCE_CLASSES},
        "proof_credit": 0,
        "errors": [],
    }
    if not manifest_path.is_file():
        base["errors"] = ["MANIFEST_NOT_FOUND"]
        return base
    raw, read_error = _read_file_bounded(manifest_path, MAX_MANIFEST_BYTES)
    base["manifest_sha256"] = hashlib.sha256(raw).hexdigest() if raw is not None else None
    base["manifest_bytes"] = len(raw) if raw is not None else 0
    if read_error:
        base["status"] = "MANIFEST_QUARANTINED"
        base["errors"] = [read_error]
        return base
    try:
        manifest = json.loads(raw.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        base["status"] = "MANIFEST_QUARANTINED"
        base["errors"] = [f"INVALID_JSON:{type(exc).__name__}"]
        return base
    if not isinstance(manifest, dict):
        base["status"] = "MANIFEST_QUARANTINED"
        base["errors"] = ["MANIFEST_NOT_OBJECT"]
        return base
    if manifest.get("schema_version") != SCHEMA_VERSION:
        base["status"] = "MANIFEST_QUARANTINED"
        base["errors"] = ["SCHEMA_VERSION_MISMATCH"]
        return base
    if manifest.get("source_type") != source_type:
        base["status"] = "MANIFEST_QUARANTINED"
        base["errors"] = ["SOURCE_TYPE_MISMATCH"]
        return base
    if not isinstance(manifest.get("version"), str) or not manifest["version"].strip():
        base["status"] = "MANIFEST_QUARANTINED"
        base["errors"] = ["VERSION_REQUIRED"]
        return base
    entries = manifest.get("entries")
    if not isinstance(entries, list):
        base["status"] = "MANIFEST_QUARANTINED"
        base["errors"] = ["ENTRIES_MUST_BE_ARRAY"]
        return base
    if len(entries) > MAX_ENTRIES:
        base["status"] = "MANIFEST_QUARANTINED"
        base["errors"] = [f"TOO_MANY_ENTRIES:{len(entries)}>{MAX_ENTRIES}"]
        return base

    expected_manifest_digest = manifest.get("content_sha256")
    if expected_manifest_digest is not None:
        body = {key: value for key, value in manifest.items() if key != "content_sha256"}
        actual_manifest_digest = sha256_json(body)
        base["manifest_content_sha256"] = actual_manifest_digest
        if (not isinstance(expected_manifest_digest, str)
                or expected_manifest_digest.lower() != actual_manifest_digest):
            base["status"] = "MANIFEST_QUARANTINED"
            base["errors"] = ["MANIFEST_CONTENT_DIGEST_MISMATCH"]
            return base

    toolchain, toolchain_errors = _validate_toolchain(manifest)
    if any(str(e.get("evidence_class") or "").upper() == "PROVED"
           for e in entries if isinstance(e, dict)) and toolchain_errors:
        base["errors"].extend(toolchain_errors)
    base["version"] = manifest["version"]
    base["toolchain"] = toolchain or None
    base["entries"] = [
        _validate_entry(e, source_type, i, artifact_boundary, toolchain)
        for i, e in enumerate(entries)
    ]
    for entry in base["entries"]:
        base["counts"][entry["effective_class"]] += 1
        base["proof_credit"] += entry["proof_credit"]
    quarantined = sum(e["disposition"].startswith("QUARANTINED") for e in base["entries"])
    if base["errors"] or quarantined:
        base["status"] = "PARTIAL_QUARANTINE" if base["entries"] else "MANIFEST_QUARANTINED"
    else:
        base["status"] = "INGESTED_LOCAL"
    return base


def _apply_formula_id_conflicts(sources: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in sources:
        for entry in source.get("entries", []):
            entry_id = str(entry.get("id") or "").upper()
            if _FORMULA_ID_RE.fullmatch(entry_id):
                by_id[entry_id].append(entry)
    conflicts: list[dict[str, Any]] = []
    for formula_id, rows in sorted(by_id.items()):
        signatures = {
            (
                row.get("artifact_sha256"), row.get("effective_class"),
                (row.get("proof_receipt") or {}).get("receipt_sha256"),
            )
            for row in rows
        }
        if len(signatures) <= 1:
            continue
        conflicts.append({
            "formula_id": formula_id,
            "reason": "F_ID_CONFLICT",
            "variants": len(signatures),
            "sources": sorted({str(row.get("source_type")) for row in rows}),
        })
        for row in rows:
            row["disposition"] = "QUARANTINED"
            row["effective_class"] = "UNKNOWN"
            row["proof_credit"] = 0
            row["trust_uplift_eligible"] = False
            row.setdefault("quarantine_reasons", []).append("F_ID_CONFLICT")
    return conflicts


def build_corpus_status(
    repo_root: pathlib.Path | str | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    """Build a bounded, read-only admission status from local canonical manifests."""
    root = pathlib.Path(repo_root or pathlib.Path(__file__).resolve().parent).resolve()
    env = os.environ if environ is None else environ
    sources: list[dict[str, Any]] = []
    for source_type in SOURCE_TYPES:
        manifest_path, boundary, origin, path_error = _safe_manifest_path(source_type, root, env)
        if path_error:
            sources.append({
                "source_type": source_type,
                "status": "SOURCE_UNAVAILABLE",
                "manifest_origin": origin,
                "manifest_path": (
                    manifest_path.relative_to(root).as_posix()
                    if origin == "REPO_DEFAULT" and _inside(manifest_path, root)
                    else f"<explicit-config>/{manifest_path.name}"
                ),
                "entries": [],
                "counts": {name: 0 for name in EVIDENCE_CLASSES},
                "proof_credit": 0,
                "errors": [path_error],
            })
            continue
        # Default artifacts are repo-confined. Explicit external artifacts are confined below
        # the explicit manifest directory; the environment is the sole operator trust boundary.
        artifact_boundary = root if origin == "REPO_DEFAULT" else boundary
        sources.append(_load_manifest(source_type, manifest_path, artifact_boundary, origin))

    conflicts = _apply_formula_id_conflicts(sources)
    counts = {name: 0 for name in EVIDENCE_CLASSES}
    proof_credit = 0
    quarantined_entries = 0
    for source in sources:
        source["counts"] = {name: 0 for name in EVIDENCE_CLASSES}
        source["proof_credit"] = 0
        for entry in source.get("entries", []):
            source["counts"][entry["effective_class"]] += 1
            source["proof_credit"] += entry["proof_credit"]
            counts[entry["effective_class"]] += 1
            proof_credit += entry["proof_credit"]
            quarantined_entries += int(entry["disposition"].startswith("QUARANTINED"))
        if any("F_ID_CONFLICT" in e.get("quarantine_reasons", []) for e in source.get("entries", [])):
            source["status"] = "PARTIAL_QUARANTINE"

    corpus_operational = any(
        source["status"] in {"INGESTED_LOCAL", "PARTIAL_QUARANTINE"}
        and bool(source.get("entries"))
        for source in sources
    )

    return {
        "ok": True,
        "endpoint": "brain/health/corpus-sources",
        "label": "MEASURED",
        "schema_version": SCHEMA_VERSION,
        "manifest_contract": MANIFEST_CONTRACT,
        "sources": sources,
        "formula_id_conflicts": conflicts,
        "summary": {
            "counts": counts,
            "proof_credit": proof_credit,
            "quarantined_entries": quarantined_entries,
            "trust_uplift_from_non_proved": 0,
            "missing_sources": sum(s["status"] == "SOURCE_UNAVAILABLE" for s in sources),
            "corpus_operational": corpus_operational,
            "proof_admission_available": proof_credit > 0,
            "network_access": False,
            "gpu_training_started": False,
            "writes_performed": 0,
            "trust_thresholds_changed": False,
        },
        "note": (
            "This is admission evidence, not a proof-count claim. Legacy/Hugging Face snapshots "
            "are not translated into the canonical contract; missing sources remain unavailable."
        ),
        "timestamp_utc": _utc_now(),
    }


def info() -> dict[str, Any]:
    """Static, side-effect-free contract description for documentation and tests."""
    return {
        "service": "a11oy.brain.corpus-admission",
        "schema_version": SCHEMA_VERSION,
        "contract": MANIFEST_CONTRACT,
        "effectors": 0,
        "network_access": False,
        "gpu_training": False,
        "request_selected_paths": False,
    }
