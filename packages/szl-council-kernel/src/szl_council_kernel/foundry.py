from __future__ import annotations

"""Research Foundry: discover, quarantine, review, reproduce, benchmark, promote."""

import json
import os
import re
import tempfile
import threading
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .canonical import canonical_json_text, digest_object, isoformat_utc, require_digest, require_identifier, utc_now
from .enums import CouncilState, FoundryStage
from .errors import FoundryError, IntegrityError, ValidationError
from .fourfold import verify_settlement

_ALLOWED_LICENSES = {
    "Apache-2.0",
    "MIT",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "MPL-2.0",
    "CC-BY-4.0",
    "CC0-1.0",
}

_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+(all|any|the)\s+(previous|prior)\s+instructions", re.I),
    re.compile(r"reveal\s+(the\s+)?(system|developer)\s+prompt", re.I),
    re.compile(r"exfiltrat(e|ion)|steal\s+(credentials|tokens|secrets)", re.I),
    re.compile(r"curl\s+[^\n]+\|\s*(sh|bash)", re.I),
    re.compile(r"os\.environ|process\.env", re.I),
)

_STAGE_ORDER = tuple(FoundryStage)


@dataclass(frozen=True, slots=True)
class ResearchArtifact:
    artifact_id: str
    title: str
    source_url: str
    source_type: str
    stage: FoundryStage
    license_id: str | None
    revision: str | None
    content_digest: str | None
    source_claims: tuple[str, ...]
    reproduction_digest: str | None
    benchmark_digest: str | None
    design_review_digest: str | None
    promotion_council_digest: str | None
    modified_summary: str | None
    discovered_at: str
    updated_at: str
    rejection_reasons: tuple[str, ...] = ()
    schema: str = "szl.research-artifact/v1"

    def __post_init__(self) -> None:
        require_identifier(self.artifact_id, field="artifact_id")
        if not self.title or len(self.title) > 512:
            raise ValidationError("research artifact title must be bounded")
        if not self.source_url.startswith(("https://", "http://", "file://")):
            raise ValidationError("source_url must use https, http, or file")
        if self.source_type not in {"GITHUB", "GITLAB", "ARXIV", "PUBLICATION", "STANDARD", "LOCAL"}:
            raise ValidationError("unsupported research source_type")
        if self.source_type != "LOCAL" and not self.source_url.startswith("https://"):
            raise ValidationError("non-local research sources must use HTTPS")
        object.__setattr__(self, "stage", FoundryStage(self.stage))
        if self.license_id is not None and (
            not isinstance(self.license_id, str) or not self.license_id or len(self.license_id) > 128
        ):
            raise ValidationError("license_id must be a bounded SPDX-style identifier")
        if self.revision is not None and (
            not isinstance(self.revision, str) or not self.revision or len(self.revision) > 256
        ):
            raise ValidationError("revision must be bounded")
        claims = tuple(str(item) for item in self.source_claims)
        if len(claims) > 256 or any(not item or len(item) > 2048 for item in claims):
            raise ValidationError("source_claims must be bounded")
        if len(set(claims)) != len(claims):
            raise ValidationError("source_claims must be unique")
        object.__setattr__(self, "source_claims", claims)
        reasons = tuple(str(item) for item in self.rejection_reasons)
        if len(reasons) > 128 or any(not item or len(item) > 1024 for item in reasons):
            raise ValidationError("rejection_reasons must be bounded")
        object.__setattr__(self, "rejection_reasons", reasons)
        if self.modified_summary is not None and (
            not isinstance(self.modified_summary, str)
            or not self.modified_summary
            or len(self.modified_summary) > 8192
        ):
            raise ValidationError("modified_summary must be bounded")
        for name in (
            "content_digest",
            "reproduction_digest",
            "benchmark_digest",
            "design_review_digest",
            "promotion_council_digest",
        ):
            value = getattr(self, name)
            if value is not None:
                require_digest(value, field=name)
        discovered_at = isoformat_utc(self.discovered_at)
        updated_at = isoformat_utc(self.updated_at)
        if updated_at < discovered_at:
            raise ValidationError("research artifact updated_at cannot predate discovered_at")
        object.__setattr__(self, "discovered_at", discovered_at)
        object.__setattr__(self, "updated_at", updated_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "artifact_id": self.artifact_id,
            "title": self.title,
            "source_url": self.source_url,
            "source_type": self.source_type,
            "stage": self.stage.value,
            "license_id": self.license_id,
            "revision": self.revision,
            "content_digest": self.content_digest,
            "source_claims": list(self.source_claims),
            "reproduction_digest": self.reproduction_digest,
            "benchmark_digest": self.benchmark_digest,
            "design_review_digest": self.design_review_digest,
            "promotion_council_digest": self.promotion_council_digest,
            "modified_summary": self.modified_summary,
            "discovered_at": self.discovered_at,
            "updated_at": self.updated_at,
            "rejection_reasons": list(self.rejection_reasons),
        }

    @property
    def digest(self) -> str:
        return digest_object(self.to_dict())

    @property
    def promotion_evidence_manifest_digest(self) -> str:
        """Bind a promotion decision to this exact reviewed artifact prestate."""
        return digest_object(
            {
                "schema": "szl.evidence-manifest/v1",
                "evidence": [
                    {
                        "id": "foundry-artifact",
                        "tier": "VERIFIED",
                        "digest": self.digest,
                        "stage": self.stage.value,
                    }
                ],
            }
        )


class ResearchFoundry:
    def __init__(self, manifest_path: str | Path) -> None:
        self.path = Path(manifest_path)
        self._lock = threading.RLock()
        if self.path.exists() and (self.path.is_symlink() or not self.path.is_file()):
            raise ValidationError("research manifest path must be a regular file")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if self.path.parent.is_symlink():
            raise ValidationError("research manifest parent must not be a symbolic link")
        if not self.path.exists():
            self._save({})
        else:
            # Fail closed immediately on a tampered or non-canonical manifest.
            self._load()

    def _load(self) -> dict[str, ResearchArtifact]:
        with self._lock:
            if self.path.is_symlink() or not self.path.is_file():
                raise IntegrityError("research manifest is not a regular file")
            try:
                text = self.path.read_text(encoding="utf-8")
                data = json.loads(text)
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise IntegrityError("research manifest is unreadable or invalid JSON") from exc
            if not isinstance(data, Mapping) or set(data) != {
                "schema", "artifacts", "manifest_digest"
            }:
                raise IntegrityError("research manifest has an invalid top-level shape")
            if data.get("schema") != "szl.research-foundry-manifest/v1":
                raise IntegrityError("research manifest schema mismatch")
            artifacts_value = data.get("artifacts")
            if not isinstance(artifacts_value, list):
                raise IntegrityError("research manifest artifacts must be a list")
            body = {"schema": data["schema"], "artifacts": artifacts_value}
            if digest_object(body) != data.get("manifest_digest"):
                raise IntegrityError("research manifest digest mismatch")
            if canonical_json_text(data, pretty=True) != text:
                raise IntegrityError("research manifest is not canonical")
            artifacts: dict[str, ResearchArtifact] = {}
            for raw in artifacts_value:
                if not isinstance(raw, Mapping):
                    raise IntegrityError("research manifest contains a non-object artifact")
                item = dict(raw)
                item["stage"] = FoundryStage(item["stage"])
                item["source_claims"] = tuple(item.get("source_claims", ()))
                item["rejection_reasons"] = tuple(item.get("rejection_reasons", ()))
                artifact = ResearchArtifact(**item)
                if artifact.artifact_id in artifacts:
                    raise IntegrityError("research manifest contains a duplicate artifact_id")
                artifacts[artifact.artifact_id] = artifact
            expected_order = sorted(artifacts)
            observed_order = [str(item.get("artifact_id")) for item in artifacts_value]
            if observed_order != expected_order:
                raise IntegrityError("research manifest artifact order is non-canonical")
            return artifacts

    def _save(self, artifacts: Mapping[str, ResearchArtifact]) -> None:
        with self._lock:
            body = {
                "schema": "szl.research-foundry-manifest/v1",
                "artifacts": [artifacts[key].to_dict() for key in sorted(artifacts)],
            }
            encoded = canonical_json_text(
                {**body, "manifest_digest": digest_object(body)}, pretty=True
            ).encode("utf-8")
            fd, name = tempfile.mkstemp(prefix=".foundry-", suffix=".tmp", dir=self.path.parent)
            temp_path = Path(name)
            try:
                os.fchmod(fd, 0o600)
                with os.fdopen(fd, "wb", closefd=True) as handle:
                    handle.write(encoded)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp_path, self.path)
                os.chmod(self.path, 0o600)
                directory_fd = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            finally:
                if temp_path.exists():
                    temp_path.unlink()

    def register(
        self,
        *,
        artifact_id: str,
        title: str,
        source_url: str,
        source_type: str,
        discovered_at: str | datetime | None = None,
    ) -> ResearchArtifact:
        with self._lock:
            artifacts = self._load()
            if artifact_id in artifacts:
                existing = artifacts[artifact_id]
                if existing.source_url != source_url:
                    raise IntegrityError("research artifact id cannot be rebound to another source")
                return existing
            timestamp = isoformat_utc(discovered_at or utc_now())
            artifact = ResearchArtifact(
                artifact_id=artifact_id,
                title=title,
                source_url=source_url,
                source_type=source_type,
                stage=FoundryStage.DISCOVERED,
                license_id=None,
                revision=None,
                content_digest=None,
                source_claims=(),
                reproduction_digest=None,
                benchmark_digest=None,
                design_review_digest=None,
                promotion_council_digest=None,
                modified_summary=None,
                discovered_at=timestamp,
                updated_at=timestamp,
            )
            artifacts[artifact_id] = artifact
            self._save(artifacts)
            return artifact

    @staticmethod
    def scan_text(text: str) -> dict[str, Any]:
        findings = [pattern.pattern for pattern in _INJECTION_PATTERNS if pattern.search(text)]
        return {
            "schema": "szl.research-safety-scan/v1",
            "status": "PASS" if not findings else "FAIL",
            "finding_count": len(findings),
            "patterns": findings,
            "content_digest": digest_object({"text": text}),
        }

    def advance(
        self,
        artifact_id: str,
        target: FoundryStage | str,
        *,
        evidence: Mapping[str, Any],
        updated_at: str | datetime | None = None,
    ) -> ResearchArtifact:
        with self._lock:
            return self._advance_unlocked(
                artifact_id,
                target,
                evidence=evidence,
                updated_at=updated_at,
            )

    def _advance_unlocked(
        self,
        artifact_id: str,
        target: FoundryStage | str,
        *,
        evidence: Mapping[str, Any],
        updated_at: str | datetime | None = None,
    ) -> ResearchArtifact:
        target = FoundryStage(target)
        artifacts = self._load()
        if artifact_id not in artifacts:
            raise KeyError(artifact_id)
        current = artifacts[artifact_id]
        if current.stage in {FoundryStage.PROMOTED, FoundryStage.REJECTED}:
            raise FoundryError("terminal research artifact cannot advance")
        current_index = _STAGE_ORDER.index(current.stage)
        target_index = _STAGE_ORDER.index(target)
        if target == FoundryStage.REJECTED:
            reasons = tuple(str(item) for item in evidence.get("reasons", ()))
            if not reasons:
                raise FoundryError("rejection requires reasons")
            updated = replace(current, stage=target, rejection_reasons=reasons, updated_at=isoformat_utc(updated_at or utc_now()))
        else:
            if target_index != current_index + 1:
                raise FoundryError(f"foundry stages must advance one step: {current.stage.value} -> {target.value}")
            changes: dict[str, Any] = {"stage": target, "updated_at": isoformat_utc(updated_at or utc_now())}
            if target == FoundryStage.QUARANTINED:
                scan = evidence.get("safety_scan")
                if not isinstance(scan, Mapping) or scan.get("status") != "PASS":
                    raise FoundryError("quarantine requires a passing safety scan")
            elif target == FoundryStage.RIGHTS_REVIEWED:
                license_id = str(evidence.get("license_id", ""))
                if license_id not in _ALLOWED_LICENSES:
                    raise FoundryError("license is absent or not in the reviewed allowlist")
                changes["license_id"] = license_id
            elif target == FoundryStage.REVISION_PINNED:
                revision = str(evidence.get("revision", ""))
                content_digest = str(evidence.get("content_digest", ""))
                if not revision or len(revision) > 256:
                    raise FoundryError("revision pin is required")
                require_digest(content_digest, field="content_digest")
                changes.update(revision=revision, content_digest=content_digest)
            elif target == FoundryStage.SAFETY_REVIEWED:
                scan = evidence.get("safety_scan")
                if not isinstance(scan, Mapping) or scan.get("status") != "PASS":
                    raise FoundryError("safety review requires a passing scan")
            elif target == FoundryStage.CLAIMS_EXTRACTED:
                claims = tuple(str(item) for item in evidence.get("claims", ()))
                if not claims:
                    raise FoundryError("claim extraction requires bounded source claims")
                changes["source_claims"] = claims
            elif target == FoundryStage.REPRODUCED:
                changes["reproduction_digest"] = require_digest(str(evidence.get("reproduction_digest", "")), field="reproduction_digest")
            elif target == FoundryStage.BENCHMARKED:
                changes["benchmark_digest"] = require_digest(str(evidence.get("benchmark_digest", "")), field="benchmark_digest")
            elif target == FoundryStage.DESIGN_REVIEWED:
                changes["design_review_digest"] = require_digest(str(evidence.get("design_review_digest", "")), field="design_review_digest")
                summary = str(evidence.get("modified_summary", ""))
                if not summary:
                    raise FoundryError("design review requires a modification summary")
                changes["modified_summary"] = summary
            elif target == FoundryStage.PROMOTED:
                settlement = evidence.get("council_settlement")
                if not isinstance(settlement, Mapping):
                    raise FoundryError("promotion requires a complete signed Fourfold settlement")
                verification = verify_settlement(settlement)
                result = settlement.get("result")
                case = settlement.get("case")
                if (
                    verification.get("status") != "PASS"
                    or not isinstance(result, Mapping)
                    or not isinstance(case, Mapping)
                    or result.get("state") != CouncilState.QUORUM_VERIFIED.value
                    or result.get("verified") is not True
                    or case.get("evidence_manifest_digest") != current.promotion_evidence_manifest_digest
                ):
                    raise FoundryError(
                        "promotion settlement is invalid, not QUORUM_VERIFIED, or not bound to the exact artifact"
                    )
                changes["promotion_council_digest"] = require_digest(
                    str(settlement.get("settlement_digest", "")),
                    field="settlement_digest",
                )
            updated = replace(current, **changes)
        artifacts[artifact_id] = updated
        self._save(artifacts)
        return updated

    def inventory(self) -> dict[str, Any]:
        with self._lock:
            artifacts = self._load()
            body = {
                "schema": "szl.research-foundry-inventory/v1",
                "artifacts": [artifacts[key].to_dict() for key in sorted(artifacts)],
            }
            return {**body, "inventory_digest": digest_object(body)}
