# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
"""State-native token ingress controls for a11oy.

Taxonomy home: services/ (flat-rooted repository map).

This module implements bounded, dependency-free primitives that let the existing
agent/runtime layers exploit tokenizer throughput and cache warmth without
promoting an alternate tokenizer as semantically equivalent.  It deliberately
separates *routing evidence* from *semantic authority*:

* routing signals may be observed and scored;
* a tokenizer candidate is eligible only after exact token-id and special-token
  parity against the declared oracle;
* prefix persistence is content-addressed and bounded;
* repository ingestion is file-native and path-contained;
* saved ingress budget can be assigned to verifier work, but is never labelled
  MEASURED unless the caller supplies measured evidence.

No network calls, provider writes, model training, or signing occur here.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Sequence


MAX_PREFIX_ENTRIES = 256
MAX_PREFIX_BYTES = 16 * 1024 * 1024
MAX_INGEST_FILE_BYTES = 8 * 1024 * 1024
MAX_INGEST_TOTAL_BYTES = 128 * 1024 * 1024


@dataclass(frozen=True)
class TokenizerNodeSignal:
    """Observed ingress capability for one candidate runtime node."""

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
        if self.tokenizer_tokens_per_sec < 0:
            raise ValueError("tokenizer_tokens_per_sec must be non-negative")
        for name, value in (
            ("tokenizer_cache_warmth", self.tokenizer_cache_warmth),
            ("prefix_cache_hit_rate", self.prefix_cache_hit_rate),
            ("kv_cache_hit_rate", self.kv_cache_hit_rate),
        ):
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between 0 and 1")


@dataclass(frozen=True)
class IngressWorkload:
    """Routing hints for a request before model execution."""

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
    """Choose the strongest available ingress node from explicit observations.

    Throughput is normalized against the best available node.  Cache signals gain
    weight as the workload becomes more prefix/corpus/prefill heavy.  The function
    is deterministic and returns the evidence label separately from the score.
    """

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
class TokenizerParityCase:
    name: str
    oracle_ids: tuple[int, ...]
    candidate_ids: tuple[int, ...]
    oracle_special_tokens: tuple[str, ...] = ()
    candidate_special_tokens: tuple[str, ...] = ()
    oracle_normalized_text: str | None = None
    candidate_normalized_text: str | None = None

    def exact_match(self) -> bool:
        return (
            self.oracle_ids == self.candidate_ids
            and self.oracle_special_tokens == self.candidate_special_tokens
            and self.oracle_normalized_text == self.candidate_normalized_text
        )


def qualify_tokenizer_candidate(
    oracle: str, candidate: str, cases: Sequence[TokenizerParityCase]
) -> dict[str, object]:
    """Fail closed unless every representative case matches the oracle exactly."""

    if not oracle.strip() or not candidate.strip():
        raise ValueError("oracle and candidate names are required")
    if not cases:
        return {
            "status": "BLOCKED",
            "oracle": oracle,
            "candidate": candidate,
            "reason": "no representative semantic-parity cases supplied",
            "eligible": False,
        }

    mismatches = [case.name for case in cases if not case.exact_match()]
    return {
        "status": "PASS" if not mismatches else "FAIL",
        "oracle": oracle,
        "candidate": candidate,
        "eligible": not mismatches,
        "cases": len(cases),
        "mismatches": mismatches,
        "policy": "exact token IDs + special tokens + normalization parity",
    }


@dataclass
class PrefixFoundry:
    """Bounded content-addressed prefix store for reusable prompt scaffolds."""

    max_entries: int = MAX_PREFIX_ENTRIES
    max_bytes: int = MAX_PREFIX_BYTES
    _entries: dict[str, bytes] = field(default_factory=dict)
    _bytes: int = 0

    @staticmethod
    def digest(namespace: str, content: bytes) -> str:
        if not namespace.strip():
            raise ValueError("namespace is required")
        h = hashlib.sha256()
        h.update(namespace.encode("utf-8"))
        h.update(b"\0")
        h.update(content)
        return h.hexdigest()

    def put(self, namespace: str, content: bytes) -> str:
        if not content:
            raise ValueError("prefix content must not be empty")
        if len(content) > self.max_bytes:
            raise ValueError("prefix exceeds foundry byte budget")
        key = self.digest(namespace, content)
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


def _is_probably_binary(data: bytes) -> bool:
    if not data:
        return False
    sample = data[:4096]
    return b"\0" in sample


def ingest_repository_files(
    root: Path,
    relative_paths: Iterable[str],
    *,
    max_file_bytes: int = MAX_INGEST_FILE_BYTES,
    max_total_bytes: int = MAX_INGEST_TOTAL_BYTES,
) -> dict[str, object]:
    """Read a caller-selected repository batch with containment and byte budgets.

    The operation is file-native: each selected path is opened once, hashed from its
    raw bytes, and returned as a stable manifest.  Binary files are classified and
    omitted from the text payload rather than decoded through a Python per-line loop.
    """

    root = root.resolve()
    if not root.is_dir():
        raise ValueError("root must be an existing directory")

    total = 0
    manifest: list[IngestedFile] = []
    text_payloads: dict[str, str] = {}
    skipped: list[dict[str, str]] = []

    for raw_path in relative_paths:
        rel = Path(raw_path)
        if rel.is_absolute() or ".." in rel.parts:
            raise ValueError(f"path escapes repository root: {raw_path}")
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
                "skipped": skipped,
                "total_bytes": total,
            }

        data = target.read_bytes()
        total += len(data)
        digest = hashlib.sha256(data).hexdigest()
        manifest.append(IngestedFile(rel.as_posix(), digest, len(data)))
        if _is_probably_binary(data):
            skipped.append({"path": rel.as_posix(), "reason": "binary"})
        else:
            text_payloads[rel.as_posix()] = data.decode("utf-8", errors="replace")

    return {
        "status": "PASS",
        "files": [item.__dict__ for item in manifest],
        "text_payloads": text_payloads,
        "skipped": skipped,
        "total_bytes": total,
    }


def verifier_reinvestment(
    saved_milliseconds: float,
    *,
    measured: bool = False,
    weights: Mapping[str, float] | None = None,
) -> dict[str, object]:
    """Allocate saved ingress latency to verification rather than overclaim speed."""

    if saved_milliseconds < 0:
        raise ValueError("saved_milliseconds must be non-negative")
    allocation = dict(weights or {
        "branch_scoring": 0.30,
        "static_analysis": 0.25,
        "policy_checks": 0.20,
        "replay": 0.15,
        "counterexamples": 0.10,
    })
    if not allocation or any(value < 0 for value in allocation.values()):
        raise ValueError("verification weights must be non-negative")
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
