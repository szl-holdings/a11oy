# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Sign-off: Stephen P. Lutar Jr. <stephenlutar2@gmail.com>
"""test_frontier_manifest — the manifest GET must be a READ, never a mint.

GET /api/a11oy/v1/frontier/manifest used to MINT + SIGN a fresh composite Khipu
receipt on every page view (via _concept_tile_inference_provenance -> build_composite),
which both made the GET slow (~4-8s) and polluted the shared provenance chain. These
checks enforce the doctrine-v11 honesty fix:

  * building the manifest does NOT append to the shared provenance Khipu chain
    (only a REAL governed action POSTing /provenance/receipt may grow it);
  * the concept tile still DESCRIBES the capability honestly and re-verifies the chain;
  * a fresh process (empty chain) -> honest ROADMAP, no fabricated artifact;
  * after a REAL composite is POSTed, the tile READS that latest digest (still no mint);
  * the manifest is cached with a short TTL (warm reads serve the last real build).
"""
import szl_frontier_manifest as fm
import szl_khipu as kh
import szl_provenance_receipt as pr


def _prov_dag():
    return kh.get_dag(pr._KHIPU_ORGAN, ns="a11oy")


def test_manifest_get_does_not_grow_provenance_chain():
    dag = _prov_dag()
    before = dag.depth()
    for _ in range(10):
        fm._manifest_cache().invalidate()  # force a fresh compose each call
        fm.build_manifest()
    assert dag.depth() == before, (
        f"manifest GET must NOT mint a provenance receipt "
        f"(chain grew {before}->{dag.depth()})")


def test_concept_tile_reads_chain_and_reverifies():
    fm._manifest_cache().invalidate()
    m = fm.build_manifest()
    concept = next(t for t in m["capabilities"] if t["category"] == "frontier-concept")
    # The tile re-verifies chain integrity (a read) regardless of depth.
    assert concept["provenance"].get("chain_verified") is True
    assert concept["label"] in (fm.ROADMAP, fm.MEASURED)


def test_empty_chain_is_honest_roadmap_no_artifact():
    dag = _prov_dag()
    if dag.depth() != 0:
        # Another test in the session already minted a real composite; skip the
        # empty-chain branch rather than fabricating a clean process.
        return
    fm._manifest_cache().invalidate()
    m = fm.build_manifest()
    concept = next(t for t in m["capabilities"] if t["category"] == "frontier-concept")
    assert concept["label"] == fm.ROADMAP
    assert concept.get("on_artifact_minted") is False
    assert concept.get("composite_digest") is None


def test_real_post_grows_chain_then_get_reads_it():
    dag = _prov_dag()
    before = dag.depth()
    env = pr.build_composite({"action": {"cmd": "real governed action"},
                              "family": "oxides", "request_id": "test-real"})
    grew = dag.depth()
    assert grew == before + 1, "a REAL POST must grow the provenance chain"

    fm._manifest_cache().invalidate()
    m = fm.build_manifest()
    assert dag.depth() == grew, "manifest GET must NOT mint after a real action"
    concept = next(t for t in m["capabilities"] if t["category"] == "frontier-concept")
    assert concept["label"] == fm.MEASURED
    assert concept.get("on_artifact_minted") is True
    # The tile surfaces the REAL latest composite digest as a READ, never a fresh mint.
    assert concept.get("composite_digest") == env["digest"]


def test_manifest_is_cached_with_cached_at_stamp():
    fm._manifest_cache().invalidate()
    fm.build_manifest()              # cold compose -> populates cache
    warm = fm.build_manifest()       # served from cache
    assert "cached_at" in warm, "cached manifest must carry a cached_at freshness stamp"


def test_labels_stay_honest():
    fm._manifest_cache().invalidate()
    m = fm.build_manifest()
    counts = m["summary"]["label_counts"]
    # 6 MEASURED tiles + 1 MODELED orbital are invariant; the concept tile is
    # ROADMAP (empty chain) or MEASURED (after a real composite) — never upgraded past.
    assert counts.get("MEASURED", 0) >= 6
    assert counts.get("MODELED", 0) == 1
    allowed = {fm.MEASURED, fm.MODELED, fm.ROADMAP, fm.SAMPLE, fm.UNAVAILABLE}
    for t in m["capabilities"]:
        assert t["label"] in allowed


if __name__ == "__main__":
    import sys
    test_manifest_get_does_not_grow_provenance_chain()
    test_concept_tile_reads_chain_and_reverifies()
    test_empty_chain_is_honest_roadmap_no_artifact()
    test_real_post_grows_chain_then_get_reads_it()
    test_manifest_is_cached_with_cached_at_stamp()
    test_labels_stay_honest()
    print("test_frontier_manifest: ALL OK")
    sys.exit(0)
