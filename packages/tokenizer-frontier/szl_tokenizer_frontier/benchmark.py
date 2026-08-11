from __future__ import annotations

import time
from dataclasses import asdict, dataclass
from typing import Callable, Iterable

from .equivalence import SemanticGateResult, semantic_equivalence
from .profile import TokenizerProfile
from .tokenizer import EncodedDocument, Tokenizer


@dataclass(frozen=True)
class BenchmarkResult:
    schema: str
    engine: str
    workload: str
    documents: int
    bytes_processed: int
    tokens_processed: int
    elapsed_seconds: float
    bytes_per_second: float
    tokens_per_second: float
    semantic_gate: dict
    promotable: bool
    measured: bool

    def record(self) -> dict:
        return asdict(self)


def benchmark_candidate(
    *,
    engine: str,
    workload: str,
    texts: Iterable[str],
    candidate: Tokenizer,
    candidate_profile: TokenizerProfile,
    oracle: Tokenizer,
    oracle_profile: TokenizerProfile,
    timer: Callable[[], float] = time.perf_counter,
) -> BenchmarkResult:
    corpus = tuple(texts)
    if not corpus:
        raise ValueError("at least one benchmark document is required")

    start = timer()
    candidate_documents = tuple(candidate.encode_with_offsets(text) for text in corpus)
    elapsed = max(0.0, timer() - start)
    oracle_documents = tuple(oracle.encode_with_offsets(text) for text in corpus)
    gate = semantic_equivalence(
        oracle_profile=oracle_profile,
        candidate_profile=candidate_profile,
        oracle_documents=oracle_documents,
        candidate_documents=candidate_documents,
    )
    bytes_processed = sum(len(text.encode("utf-8")) for text in corpus)
    tokens_processed = sum(len(item.token_ids) for item in candidate_documents)
    measured = elapsed > 0
    return BenchmarkResult(
        schema="szl.tokenizer-benchmark/v1",
        engine=engine,
        workload=workload,
        documents=len(corpus),
        bytes_processed=bytes_processed,
        tokens_processed=tokens_processed,
        elapsed_seconds=elapsed,
        bytes_per_second=(bytes_processed / elapsed if measured else 0.0),
        tokens_per_second=(tokens_processed / elapsed if measured else 0.0),
        semantic_gate=gate.record(),
        promotable=gate.promotable and measured,
        measured=measured,
    )
