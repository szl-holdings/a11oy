# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""Dependency-free state-native token-ingress primitives.

The production container copies ``routers/`` as one governed runtime unit.  This
module contains bounded computation only: no provider call, network access,
model training, signing, credential access, or repository mutation.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence

MAX_PREFIX_ENTRIES = 256
MAX_PREFIX_BYTES = 16 * 1024 * 1024
MAX_INGEST_FILES = 4096
MAX_INGEST_FILE_BYTES = 8 * 1024 * 1024
MAX_INGEST_TOTAL_BYTES = 128 * 1024 * 1024

_SEMANTIC_DIGEST_FIELDS = (
    "vocabulary_sha256",
    "normalization_sha256",
    "special_tokens_sha256",
    "added_tokens_sha256",
    "chat_template_sha256",
    "document_separator_sha256",
)


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _canonical_sha256(value: object) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class TokenizerNodeSignal:
    """Observed ingress capability for one runtime node."""

    node_id: str
    tokenizer_tokens_per_sec: float
    tokenizer_cache_warmth: float
    prefix_cache_hit_rate: float
    kv_cache_hit_rate: float
    available: bool = True
    measured: bool = False

    def validate(self) -> None:
        if not self.node_id.strip():
            raise ValueError("node_id is required")
        if not math.isfinite(self.tokenizer_tokens_per_sec) or self.tokenizer_tokens_per_sec < 0:
            raise ValueError("tokenizer_tokens_per_sec must be finite and non-negative")
        for name, value in (
            ("tokenizer_cache_warmth", self.tokenizer_cache_warmth),
            ("prefix_cache_hit_rate", self.prefix_cache_hit_rate),
            ("kv_cache_hit_rate", self.kv_cache_hit_rate),
        ):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and between 0 and 1")


@dataclass(frozen=True)
class IngressWorkload:
    """Routing hints for work before model execution."""

    prefix_heavy: bool = False
    corpus_heavy: bool = False
    prefill_heavy: bool = False

    @property
    def ingress_weight(self) -> float:
        flags = sum((self.prefix_heavy, self.corpus_heavy, self.prefill_heavy))
        return min(1.0, 0.25 + 0.25 * flags)


def choose_ingress_node(
    nodes: Sequence[TokenizerNodeSignal], workload: IngressWorkload
) -> dict[str, object]:
    """Select one available node from explicit throughput and locality evidence."""

    eligible = [node for node in nodes if node.available]
    if not eligible:
        return {"status": "BLOCKED", "reason": "no available ingress nodes", "node": None}
    for node in eligible:
        node.validate()

    max_tps = max(node.tokenizer_tokens_per_sec for node in eligible) or 1.0
    ingress_weight = workload.ingress_weight

    def score(node: TokenizerNodeSignal) -> float:
        throughput = node.tokenizer_tokens_per_sec / max_tps
        cache = (
            0.45 * node.tokenizer_cache_warmth
            + 0.35 * node.prefix_cache_hit_rate
            + 0.20 * node.kv_cache_hit_rate
        )
        return round((1.0 - ingress_weight) * throughput + ingress_weight * cache, 6)

    ranked = sorted(eligible, key=lambda node: (-score(node), node.node_id))
    winner = ranked[0]
    return {
        "status": "PASS",
        "node": winner.node_id,
        "score": score(winner),
        "evidence": "MEASURED" if winner.measured else "SAMPLE",
        "policy": "tokenizer-throughput + cache-warmth + prefix/KV reuse",
        "ranking": [{"node": node.node_id, "score": score(node)} for node in ranked],
    }


@dataclass(frozen=True)
class SemanticTokenContract:
    """Digest-bound tokenizer semantics independent of implementation branding.

    Empty or inapplicable components are represented by the SHA-256 digest of the
    canonical empty value selected by the caller; missing evidence is not accepted.
    """

    source: str
    tokenizer_family: str
    vocabulary_sha256: str
    normalization_sha256: str
    special_tokens_sha256: str
    added_tokens_sha256: str
    chat_template_sha256: str
    document_separator_sha256: str

    def validate(self) -> None:
        if not self.source.strip():
            raise ValueError("semantic token contract source is required")
        if not self.tokenizer_family.strip():
            raise ValueError("tokenizer_family is required")
        for field_name in _SEMANTIC_DIGEST_FIELDS:
            value = getattr(self, field_name)
            if not _is_sha256(value):
                raise ValueError(f"{field_name} must be one lowercase SHA-256 digest")

    def semantic_fields(self) -> dict[str, str]:
        self.validate()
        return {
            "tokenizer_family": self.tokenizer_family,
            **{name: getattr(self, name) for name in _SEMANTIC_DIGEST_FIELDS},
        }

    def digest(self) -> str:
        return _canonical_sha256(self.semantic_fields())

    def mismatches(self, other: "SemanticTokenContract") -> list[str]:
        left = self.semantic_fields()
        right = other.semantic_fields()
        return sorted(name for name in left if left[name] != right[name])


@dataclass(frozen=True)
class TokenizerParityCase:
    name: str
    oracle_ids: tuple[int, ...]
    candidate_ids: tuple[int, ...]
    oracle_decoded_text: str
    candidate_decoded_text: str

    def exact_match(self) -> bool:
        return (
            self.oracle_ids == self.candidate_ids
            and self.oracle_decoded_text == self.candidate_decoded_text
        )


def qualify_tokenizer_candidate(
    oracle: SemanticTokenContract,
    candidate: SemanticTokenContract,
    cases: Sequence[TokenizerParityCase],
) -> dict[str, object]:
    """Fail closed unless semantic digests and every representative case match."""

    oracle.validate()
    candidate.validate()
    if not cases:
        return {
            "status": "BLOCKED",
            "eligible": False,
            "reason": "no representative semantic-parity cases supplied",
            "oracle_source": oracle.source,
            "candidate_source": candidate.source,
        }

    contract_mismatches = oracle.mismatches(candidate)
    case_mismatches = [case.name for case in cases if not case.exact_match()]
    eligible = not contract_mismatches and not case_mismatches
    return {
        "status": "PASS" if eligible else "FAIL",
        "eligible": eligible,
        "oracle_source": oracle.source,
        "candidate_source": candidate.source,
        "oracle_contract_sha256": oracle.digest(),
        "candidate_contract_sha256": candidate.digest(),
        "contract_mismatches": contract_mismatches,
        "case_mismatches": case_mismatches,
        "cases": len(cases),
        "policy": (
            "exact vocabulary/normalization/special-token/added-token/chat-template/"
            "document-separator digests + token IDs + decoded text"
        ),
    }


@dataclass
class PrefixFoundry:
    """Bounded content-addressed token-prefix store bound to one semantic contract."""

    max_entries: int = MAX_PREFIX_ENTRIES
    max_bytes: int = MAX_PREFIX_BYTES
    _entries: dict[str, bytes] = field(default_factory=dict)
    _bytes: int = 0

    @staticmethod
    def digest(namespace: str, semantic_contract_sha256: str, content: bytes) -> str:
        if not namespace.strip():
            raise ValueError("namespace is required")
        if not _is_sha256(semantic_contract_sha256):
            raise ValueError("semantic_contract_sha256 must be one lowercase SHA-256 digest")
        hasher = hashlib.sha256()
        hasher.update(namespace.encode("utf-8"))
        hasher.update(b"\0")
        hasher.update(semantic_contract_sha256.encode("ascii"))
        hasher.update(b"\0")
        hasher.update(content)
        return hasher.hexdigest()

    def put(self, namespace: str, semantic_contract_sha256: str, content: bytes) -> str:
        if self.max_entries < 1 or self.max_bytes < 1:
            raise ValueError("foundry budgets must be positive")
        if not content:
            raise ValueError("prefix content must not be empty")
        if len(content) > self.max_bytes:
            raise ValueError("prefix exceeds foundry byte budget")
        key = self.digest(namespace, semantic_contract_sha256, content)
        if key in self._entries:
            return key

        while self._entries and (
            len(self._entries) >= self.max_entries or self._bytes + len(content) > self.max_bytes
        ):
            oldest_key = next(iter(self._entries))
            old = self._entries.pop(oldest_key)
            self._bytes -= len(old)

        self._entries[key] = bytes(content)
        self._bytes += len(content)
        return key

    def get(self, key: str) -> bytes | None:
        return self._entries.get(key)

    def snapshot(self) -> dict[str, int]:
        return {"entries": len(self._entries), "bytes": self._bytes}


@dataclass(frozen=True)
class IngestedFile:
    path: str
    sha256: str
    size_bytes: int
    text: bool


def _is_probably_binary(data: bytes) -> bool:
    return bool(data) and b"\0" in data[:4096]


def _path_contains_symlink(root: Path, relative_path: Path) -> bool:
    cursor = root
    for part in relative_path.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return True
    return False


def ingest_repository_files(
    root: Path,
    relative_paths: Iterable[str],
    *,
    max_files: int = MAX_INGEST_FILES,
    max_file_bytes: int = MAX_INGEST_FILE_BYTES,
    max_total_bytes: int = MAX_INGEST_TOTAL_BYTES,
) -> dict[str, object]:
    """Read one deterministic repository batch with containment and byte budgets."""

    root = root.resolve()
    if not root.is_dir():
        raise ValueError("root must be an existing directory")
    if max_files < 1 or max_file_bytes < 1 or max_total_bytes < 1:
        raise ValueError("ingest budgets must be positive")

    normalized = sorted(set(relative_paths))
    if len(normalized) > max_files:
        return {
            "status": "BLOCKED",
            "reason": "file-count-budget",
            "files": [],
            "text_payloads": {},
            "skipped": [],
            "total_bytes": 0,
        }

    total = 0
    manifest: list[IngestedFile] = []
    text_payloads: dict[str, str] = {}
    skipped: list[dict[str, str]] = []

    for raw_path in normalized:
        rel = Path(raw_path)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"path escapes repository root: {raw_path}")
        if _path_contains_symlink(root, rel):
            skipped.append({"path": rel.as_posix(), "reason": "symlink"})
            continue

        target = (root / rel).resolve()
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"path escapes repository root: {raw_path}") from exc
        if not target.is_file():
            skipped.append({"path": rel.as_posix(), "reason": "not-a-file"})
            continue

        size = target.stat().st_size
        if size > max_file_bytes:
            skipped.append({"path": rel.as_posix(), "reason": "file-budget"})
            continue
        if total + size > max_total_bytes:
            return {
                "status": "BLOCKED",
                "reason": "total-ingest-byte-budget",
                "files": [item.__dict__ for item in manifest],
                "text_payloads": text_payloads,
                "skipped": skipped,
                "total_bytes": total,
            }

        data = target.read_bytes()
        if len(data) > max_file_bytes or total + len(data) > max_total_bytes:
            return {
                "status": "BLOCKED",
                "reason": "post-read-byte-budget",
                "files": [item.__dict__ for item in manifest],
                "text_payloads": text_payloads,
                "skipped": skipped,
                "total_bytes": total,
            }

        total += len(data)
        is_text = not _is_probably_binary(data)
        manifest.append(
            IngestedFile(
                path=rel.as_posix(),
                sha256=hashlib.sha256(data).hexdigest(),
                size_bytes=len(data),
                text=is_text,
            )
        )
        if is_text:
            text_payloads[rel.as_posix()] = data.decode("utf-8", errors="replace")
        else:
            skipped.append({"path": rel.as_posix(), "reason": "binary"})

    manifest_rows = [item.__dict__ for item in manifest]
    return {
        "status": "PASS",
        "files": manifest_rows,
        "text_payloads": text_payloads,
        "skipped": skipped,
        "total_bytes": total,
        "batch_sha256": _canonical_sha256(manifest_rows),
    }


def verifier_reinvestment(
    saved_milliseconds: float,
    *,
    measured: bool = False,
    weights: Mapping[str, float] | None = None,
) -> dict[str, object]:
    """Allocate recovered ingress time to verification before traffic expansion."""

    if not math.isfinite(saved_milliseconds) or saved_milliseconds < 0:
        raise ValueError("saved_milliseconds must be finite and non-negative")
    allocation = dict(
        weights
        or {
            "branch_scoring": 0.30,
            "static_analysis": 0.25,
            "policy_checks": 0.20,
            "replay": 0.15,
            "counterexamples": 0.10,
        }
    )
    if not allocation or any(
        not math.isfinite(value) or value < 0 for value in allocation.values()
    ):
        raise ValueError("verification weights must be finite and non-negative")
    total = sum(allocation.values())
    if total <= 0:
        raise ValueError("verification weights must have positive total")

    budget = {
        name: round(saved_milliseconds * value / total, 3)
        for name, value in allocation.items()
    }
    return {
        "evidence": "MEASURED" if measured else "MODELED",
        "saved_milliseconds": saved_milliseconds,
        "verification_budget_ms": budget,
        "policy": "reinvest ingress savings into verification before expanding interactive traffic",
    }
