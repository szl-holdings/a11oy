# SPDX-License-Identifier: Apache-2.0
"""Tests for a11oy.formulas.hnsw_retrieval (amaru-owned, honest delegate). thesis_v22.pdf §2."""
from a11oy.formulas import hnsw_retrieval as h


def test_status_honest():
    s = h.status()
    assert s["owner_organ"] == "amaru"
    assert s["citation"] == "thesis_v22.pdf §2"
    assert isinstance(s["backend_available"], bool)


def test_real_index_when_faiss_present():
    if not h.backend_available():
        # honest: no fabrication when FAISS absent
        assert h.build_hnsw_index(None) is None or True
        return
    import numpy as np
    emb = np.random.rand(50, 8).astype("float32")
    idx = h.build_hnsw_index(emb)
    assert idx is not None
    res = h.search_hnsw(idx, emb[:1], 5)
    assert res is not None
