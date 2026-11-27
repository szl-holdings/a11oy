#!/usr/bin/env python3
"""Fail-closed verification of a cosign bundle, ML-BOM and lineage manifest.

Required lineage fields (PLAN.md practice #7, pending Qullqa schema):
  base model rev, dataset revs and sha256, decontam verdict, training receipt digest.
Missing files, unknown/non-PASS decontam, or malformed digests fail closed.
This script never signs, publishes or deploys.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

PASS_VERDICTS = {"PASS", "CLEAN"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SHA256_PREFIX_RE = re.compile(r"^(sha256:)?[0-9a-f]{64}$")


def fail(message: str) -> None:
    print(f"::error::{message}", file=sys.stderr)
    raise SystemExit(1)


def load_json(path: Path, label: str) -> Any:
    if not path.is_file():
        fail(f"{label} is missing: {path}")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        fail(f"{label} could not be read: {path}")
    if not raw.strip():
        fail(f"{label} is empty: {path}")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        fail(f"{label} is not valid JSON: {path}")


def require_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not SHA256_PREFIX_RE.fullmatch(value.lower()):
        fail(f"{label} is not a sha256 digest; fails closed.")
    return value.lower().removeprefix("sha256:")


def verify_bundle(path: Path) -> dict:
    data = load_json(path, "cosign bundle")
    if not isinstance(data, dict) or not data:
        fail("cosign bundle must be a non-empty JSON object; fails closed.")
    return data


def verify_mlbom(path: Path) -> dict:
    data = load_json(path, "ML-BOM")
    if not isinstance(data, dict):
        fail("ML-BOM must be a JSON object; fails closed.")
    bom_format = str(data.get("bomFormat", "")).strip()
    if bom_format.lower() != "cyclonedx":
        fail("ML-BOM bomFormat must be CycloneDX; fails closed.")
    if not data.get("specVersion"):
        fail("ML-BOM specVersion is missing; fails closed.")
    components = data.get("components")
    if not isinstance(components, list) or not components:
        fail("ML-BOM components must be a non-empty list; fails closed.")
    return data


def _base_rev(lineage: dict) -> str:
    base = lineage.get("base_model") or lineage.get("baseModel") or {}
    if isinstance(base, dict):
        rev = base.get("rev") or base.get("revision") or base.get("ref")
        if isinstance(rev, str) and rev.strip():
            return rev.strip()
    for key in ("base_model_rev", "base_rev", "baseModelRev"):
        val = lineage.get(key)
        if isinstance(val, str) and val.strip():
            return val.strip()
    fail("lineage is missing base model rev; fails closed.")
    return ""


def _datasets(lineage: dict) -> list[dict]:
    datasets = lineage.get("datasets") or lineage.get("dataset_revs") or lineage.get("train_sets")
    if not isinstance(datasets, list) or not datasets:
        fail("lineage is missing dataset revs and sha256; fails closed.")
    cleaned: list[dict] = []
    for i, item in enumerate(datasets):
        if not isinstance(item, dict):
            fail(f"lineage datasets[{i}] must be an object; fails closed.")
        rev = item.get("rev") or item.get("revision") or item.get("ref")
        digest = item.get("sha256") or item.get("digest")
        if not isinstance(rev, str) or not rev.strip():
            fail(f"lineage datasets[{i}] is missing rev; fails closed.")
        cleaned.append({"rev": rev.strip(), "sha256": require_sha256(digest, f"lineage datasets[{i}].sha256")})
    return cleaned


def _decontam(lineage: dict) -> str:
    verdict = lineage.get("decontam_verdict")
    if verdict is None and isinstance(lineage.get("decontam"), dict):
        verdict = lineage["decontam"].get("verdict")
    if not isinstance(verdict, str) or verdict.strip().upper() not in PASS_VERDICTS:
        fail(
            f"lineage decontam verdict is {verdict!r}; only PASS or CLEAN is admitted. "
            "UNKNOWN, FAIL, missing, or other values fail closed."
        )
    return verdict.strip().upper()


def verify_lineage(path: Path) -> dict:
    data = load_json(path, "lineage")
    if not isinstance(data, dict):
        fail("lineage must be a JSON object; fails closed.")
    base_rev = _base_rev(data)
    datasets = _datasets(data)
    verdict = _decontam(data)
    receipt = data.get("training_receipt_digest") or data.get("trainingReceiptDigest")
    receipt_hex = require_sha256(receipt, "training_receipt_digest")
    return {
        "base_model_rev": base_rev,
        "datasets": datasets,
        "decontam_verdict": verdict,
        "training_receipt_digest": receipt_hex,
    }


def maybe_cosign_verify(bundle: Path, image_ref: str) -> None:
    if not image_ref.strip():
        print("cosign verify skipped: no image_ref (structural bundle check only)")
        return
    cmd = [
        "cosign",
        "verify",
        "--bundle",
        str(bundle),
        "--certificate-oidc-issuer",
        "https://token.actions.githubusercontent.com",
        image_ref.strip(),
    ]
    try:
        completed = subprocess.run(cmd, check=False, capture_output=True, text=True)
    except FileNotFoundError:
        fail("cosign binary is missing; live bundle verify fails closed.")
    if completed.returncode != 0:
        err = (completed.stderr or completed.stdout or "cosign verify failed").strip().splitlines()
        fail(f"cosign verify failed; fails closed. {err[-1] if err else ''}")
    print("cosign verify PASS")


def verify(bundle: Path, mlbom: Path, lineage: Path, image_ref: str) -> None:
    verify_bundle(bundle)
    verify_mlbom(mlbom)
    summary = verify_lineage(lineage)
    maybe_cosign_verify(bundle, image_ref)
    print("model-provenance PASS")
    print(f"  base_model_rev={summary['base_model_rev']}")
    print(f"  datasets={len(summary['datasets'])}")
    print(f"  decontam_verdict={summary['decontam_verdict']}")
    print(f"  training_receipt_digest={summary['training_receipt_digest']}")


def _good_fixtures(root: Path) -> tuple[Path, Path, Path]:
    bundle = root / "cosign-bundle.json"
    mlbom = root / "model.cdx.json"
    lineage = root / "lineage.json"
    bundle.write_text(json.dumps({"mediaType": "application/vnd.dev.sigstore.bundle+json"}), encoding="utf-8")
    mlbom.write_text(
        json.dumps(
            {
                "bomFormat": "CycloneDX",
                "specVersion": "1.5",
                "components": [{"type": "machine-learning-model", "name": "example"}],
            }
        ),
        encoding="utf-8",
    )
    digest = "a" * 64
    lineage.write_text(
        json.dumps(
            {
                "base_model": {"rev": "abc123"},
                "datasets": [{"rev": "ds-1", "sha256": digest}],
                "decontam_verdict": "PASS",
                "training_receipt_digest": digest,
            }
        ),
        encoding="utf-8",
    )
    return bundle, mlbom, lineage


def self_check() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        bundle, mlbom, lineage = _good_fixtures(root)
        verify(bundle, mlbom, lineage, image_ref="")

        missing = root / "missing.json"
        try:
            verify(missing, mlbom, lineage, "")
        except SystemExit:
            pass
        else:
            raise AssertionError("missing bundle must fail closed")

        bad = json.loads(lineage.read_text())
        bad["decontam_verdict"] = "UNKNOWN"
        lineage.write_text(json.dumps(bad), encoding="utf-8")
        try:
            verify(bundle, mlbom, lineage, "")
        except SystemExit:
            pass
        else:
            raise AssertionError("UNKNOWN decontam must fail closed")

        bad["decontam_verdict"] = "PASS"
        bad.pop("datasets")
        lineage.write_text(json.dumps(bad), encoding="utf-8")
        try:
            verify(bundle, mlbom, lineage, "")
        except SystemExit:
            pass
        else:
            raise AssertionError("missing datasets must fail closed")

    print("self-check PASS")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true")
    parser.add_argument("--bundle")
    parser.add_argument("--mlbom")
    parser.add_argument("--lineage")
    parser.add_argument("--image-ref", default="")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if not (args.bundle and args.mlbom and args.lineage):
        fail("bundle, ML-BOM and lineage paths are required; fails closed.")
    verify(Path(args.bundle), Path(args.mlbom), Path(args.lineage), args.image_ref)


if __name__ == "__main__":
    main()
