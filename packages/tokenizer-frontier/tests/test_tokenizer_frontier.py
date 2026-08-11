from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from szl_tokenizer_frontier import (
    EncodedDocument,
    IngressNode,
    IngressRequest,
    MappingTokenizer,
    PrefixFoundry,
    PrefixStore,
    TokenizerProfile,
    Utf8ByteTokenizer,
    benchmark_candidate,
    decide_promotion,
    rank_ingress,
    semantic_equivalence,
)


class Timer:
    def __init__(self, values):
        self.values = iter(values)

    def __call__(self):
        return next(self.values)


def profile(**updates):
    values = {
        "tokenizer_id": "openai-community/gpt2",
        "tokenizer_revision": "a" * 40,
        "family": "BPE",
        "normalization": "none",
        "special_tokens": {"eos_token": 50256},
        "added_tokens": (),
        "pre_tokenizer": "ByteLevel",
        "post_processor": "ByteLevel",
    }
    values.update(updates)
    return TokenizerProfile(**values)


class TokenizerFrontierTests(unittest.TestCase):
    def test_profile_digest_is_deterministic(self):
        self.assertEqual(profile().digest_sha3_256, profile().digest_sha3_256)
        self.assertEqual(len(profile().digest_sha3_256), 64)

    def test_utf8_byte_tokenizer_has_one_offset_per_token(self):
        encoded = Utf8ByteTokenizer().encode_with_offsets("Aé")
        self.assertEqual(encoded.token_ids, (65, 195, 169))
        self.assertEqual(encoded.offsets, ((0, 1), (1, 2), (2, 3)))

    def test_semantic_gate_requires_ids_offsets_and_profile(self):
        encoded = Utf8ByteTokenizer().encode_with_offsets("hello")
        result = semantic_equivalence(
            oracle_profile=profile(),
            candidate_profile=profile(),
            oracle_documents=[encoded],
            candidate_documents=[encoded],
        )
        self.assertTrue(result.promotable)
        self.assertEqual(result.state, "VERIFIED")

    def test_revision_mismatch_blocks_promotion(self):
        encoded = Utf8ByteTokenizer().encode_with_offsets("hello")
        result = semantic_equivalence(
            oracle_profile=profile(),
            candidate_profile=profile(tokenizer_revision="b" * 40),
            oracle_documents=[encoded],
            candidate_documents=[encoded],
        )
        self.assertFalse(result.promotable)
        self.assertFalse(result.checks["profile_revision"])

    def test_token_id_mismatch_is_reported(self):
        oracle = EncodedDocument((1, 2), ((0, 1), (1, 2)))
        candidate = EncodedDocument((1, 3), ((0, 1), (1, 2)))
        result = semantic_equivalence(
            oracle_profile=profile(),
            candidate_profile=profile(),
            oracle_documents=[oracle],
            candidate_documents=[candidate],
        )
        self.assertFalse(result.promotable)
        self.assertEqual(result.mismatches[0]["field"], "token_ids")

    def test_offset_mismatch_is_reported(self):
        oracle = EncodedDocument((1, 2), ((0, 1), (1, 2)))
        candidate = EncodedDocument((1, 2), ((0, 1), (2, 3)))
        result = semantic_equivalence(
            oracle_profile=profile(),
            candidate_profile=profile(),
            oracle_documents=[oracle],
            candidate_documents=[candidate],
        )
        self.assertFalse(result.promotable)
        self.assertEqual(result.mismatches[0]["field"], "offsets")

    def test_prefix_foundry_is_content_addressed_and_omits_raw_text(self):
        with tempfile.TemporaryDirectory() as directory:
            store = PrefixStore(directory)
            foundry = PrefixFoundry(store)
            first = foundry.build(
                tenant="acme",
                kind="system_prompt",
                text="You are governed.",
                profile=profile(),
                tokenizer=Utf8ByteTokenizer(),
                metadata={"policy": "covenant-v1"},
            )
            second = foundry.build(
                tenant="acme",
                kind="system_prompt",
                text="You are governed.",
                profile=profile(),
                tokenizer=Utf8ByteTokenizer(),
                metadata={"policy": "covenant-v1"},
            )
            self.assertEqual(first.object_id, second.object_id)
            record = store.read("acme", first.object_id)
            self.assertNotIn("text", record)
            self.assertFalse(record["raw_text_persisted"])
            self.assertEqual(record["tokenizer_profile_digest_sha3_256"], profile().digest_sha3_256)

    def test_prefix_store_rejects_tenant_path_traversal(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                PrefixFoundry(PrefixStore(directory)).build(
                    tenant="../escape",
                    kind="system_prompt",
                    text="x",
                    profile=profile(),
                    tokenizer=Utf8ByteTokenizer(),
                )

    def test_benchmark_requires_exact_semantics(self):
        texts = ["hello", "world"]
        result = benchmark_candidate(
            engine="candidate",
            workload="corpus_prep",
            texts=texts,
            candidate=Utf8ByteTokenizer(),
            candidate_profile=profile(),
            oracle=Utf8ByteTokenizer(),
            oracle_profile=profile(),
            timer=Timer([10.0, 10.5]),
        )
        self.assertTrue(result.promotable)
        self.assertTrue(result.measured)
        self.assertGreater(result.bytes_per_second, 0)

    def test_zero_elapsed_benchmark_is_not_promotable(self):
        result = benchmark_candidate(
            engine="candidate",
            workload="corpus_prep",
            texts=["hello"],
            candidate=Utf8ByteTokenizer(),
            candidate_profile=profile(),
            oracle=Utf8ByteTokenizer(),
            oracle_profile=profile(),
            timer=Timer([10.0, 10.0]),
        )
        self.assertFalse(result.promotable)
        self.assertFalse(result.measured)

    def test_interactive_promotion_requires_prior_stage_receipts(self):
        candidate = benchmark_candidate(
            engine="candidate",
            workload="interactive",
            texts=["hello"],
            candidate=Utf8ByteTokenizer(),
            candidate_profile=profile(),
            oracle=Utf8ByteTokenizer(),
            oracle_profile=profile(),
            timer=Timer([0.0, 0.5]),
        )
        oracle = benchmark_candidate(
            engine="oracle",
            workload="interactive",
            texts=["hello"],
            candidate=Utf8ByteTokenizer(),
            candidate_profile=profile(),
            oracle=Utf8ByteTokenizer(),
            oracle_profile=profile(),
            timer=Timer([0.0, 1.0]),
        )
        blocked = decide_promotion(stage="interactive", candidate=candidate, oracle=oracle)
        self.assertEqual(blocked.state, "BLOCKED")
        self.assertIn("PRIOR_STAGE_NOT_VERIFIED:corpus_prep", blocked.reasons)
        allowed = decide_promotion(
            stage="interactive",
            candidate=candidate,
            oracle=oracle,
            prior_stage_receipts={
                "corpus_prep": "VERIFIED",
                "retrieval_indexing": "VERIFIED",
                "batch_prefill": "VERIFIED",
            },
        )
        self.assertEqual(allowed.state, "VERIFIED")

    def test_minimum_speedup_cannot_weaken_oracle(self):
        candidate = benchmark_candidate(
            engine="candidate",
            workload="corpus_prep",
            texts=["hello"],
            candidate=Utf8ByteTokenizer(),
            candidate_profile=profile(),
            oracle=Utf8ByteTokenizer(),
            oracle_profile=profile(),
            timer=Timer([0.0, 1.0]),
        )
        with self.assertRaises(ValueError):
            decide_promotion(
                stage="corpus_prep",
                candidate=candidate,
                oracle=candidate,
                minimum_speedup=0.99,
            )

    def test_routing_uses_tokenizer_and_cache_signals(self):
        result = rank_ingress(
            [
                IngressNode("warm", 2.0, 1.0, 1.0, 0.8),
                IngressNode("cold", 4.0, 0.0, 0.4, 0.4),
            ],
            IngressRequest(prefix_heavy=True),
        )
        self.assertEqual(result["node_id"], "warm")
        self.assertIn("not the owner-authored RVO", result["limitation"])

    def test_routing_fails_closed_without_healthy_node(self):
        result = rank_ingress(
            [IngressNode("down", 10.0, 1.0, 1.0, 1.0, health="FAILED")],
            IngressRequest(corpus_heavy=True),
        )
        self.assertEqual(result["state"], "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
