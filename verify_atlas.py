# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Doctrine v11 LOCKED: locked-proven=8 · Λ=Conjecture 1
# Co-Authored-By: Perplexity Computer Agent
"""
verify_atlas.py — independent stdlib verifier for szl_kc_atlas.py (Wave 27).

Asserts, against the organ's own three endpoints:
  * exactly 8 clusters (flower taxonomy)
  * locked_core == 8 (immutable pistil {F1,F4,F7,F11,F12,F18,F19,F22})
  * coverage == 1.0 : all 67 surfaces classified exactly once (no orphan, no double-count)
  * atlas itself = 68th surface (home cluster 6)
  * conjecture cluster GRAY, never green
  * deterministic (same seed => identical) + seed-sensitive organism layout
  * register(...) returns the 3 exact paths
  * MODELED label + honesty_invariants present + classification basis cited per cluster

Prints per-check PASS/FAIL. On success: "RESULT: ALL PASS" (exit 0). On any failure it
prints the failing check and exits non-zero.
"""
import sys

import szl_kc_atlas as atlas

FAILS = []


def check(name, cond):
    ok = bool(cond)
    print(("PASS" if ok else "FAIL"), "-", name)
    if not ok:
        FAILS.append(name)
    return ok


def main() -> int:
    LOCKED8 = ("F1", "F4", "F7", "F11", "F12", "F18", "F19", "F22")

    m = atlas.atlas_map(seed=42)
    org = atlas.atlas_organism(seed=42)
    mf = atlas.atlas_manifest(seed=42)

    # --- label MODELED on every endpoint ---
    check("label MODELED on map/organism/manifest",
          m["label"] == org["label"] == mf["label"] == "MODELED")

    # --- exactly 8 clusters ---
    check("map has exactly 8 clusters", m["clusters_total"] == 8 and len(m["clusters"]) == 8)
    check("organism has exactly 8 petals", org["petals_total"] == 8 and len(org["petals"]) == 8)
    check("manifest reports 8 clusters", mf["clusters_total"] == 8 and len(mf["clusters"]) == 8)

    # --- locked_core == 8, immutable pistil, exact set ---
    check("map locked_core count == 8", m["locked_core_count"] == 8)
    check("manifest locked_core count == 8", mf["locked_core_count"] == 8)
    check("organism locked_core count == 8", org["locked_core_count"] == 8)
    check("locked_core is the fixed locked-8 set",
          sorted(m["locked_core"]) == sorted(LOCKED8))
    check("organism center is the immutable locked-8 pistil",
          org["center"]["is_pistil"] is True and org["center"]["immutable"] is True
          and [o["id"] for o in org["center"]["locked8"]] == list(LOCKED8))
    c1 = next(c for c in m["clusters"] if c["cluster"] == 1)
    check("cluster 1 kernel objects are exactly the locked-8",
          sorted(c1["kernel_object_ids"]) == sorted(LOCKED8))

    # --- coverage 1.0: all 67 classified exactly once (no orphan / no double-count) ---
    check("surface_count == 67", m["surface_count"] == 67)
    check("total_classified == 67", m["total_classified"] == 67)
    check("coverage == 1.0", m["coverage"] == 1.0)
    check("zero orphans", m["orphans"] == [])
    check("zero unknown assignments", m["unknown_assignments"] == [])
    check("zero double-counts", m["double_counts"] == [])
    check("every_surface_classified_once flag True", m["every_surface_classified_once"] is True)

    # independent recount across cluster members (no double-count, no missing)
    seen = {}
    for c in m["clusters"]:
        for s in c["surfaces"]:
            seen[s["id"]] = seen.get(s["id"], 0) + 1
    live_ids = set(s["id"] for s in atlas.LIVE_SURFACES)
    check("cluster members == the 67 live surfaces", set(seen.keys()) == live_ids)
    check("no surface appears more than once", all(v == 1 for v in seen.values()))
    check("member total sums to 67", sum(seen.values()) == 67)

    # cluster surface counts sum to 67
    check("sum of per-cluster surface counts == 67",
          sum(c["surface_count"] for c in m["clusters"]) == 67)

    # --- atlas itself = 68th surface (home cluster 6) ---
    check("atlas is the 68th surface (home cluster 6)",
          m["atlas_is_68th"]["home_cluster"] == 6 and mf["surface_index"] == 68)

    # --- conjecture cluster GRAY, never green ---
    c8 = next(c for c in m["clusters"] if c["cluster"] == 8)
    check("cluster 8 is gray", c8["gray"] is True and m["conjecture_cluster_gray"] is True)
    check("organism conjecture cluster gray", org["conjecture_cluster_gray"] is True)
    check("manifest conjecture_rendered_green == 0", mf["conjecture_rendered_green"] == 0)
    check("Lambda Conjecture 1 lives in gray cluster 8",
          "Lambda_C1" in c8["kernel_object_ids"])
    check("manifest honesty: conjecture gray never green",
          mf["honesty_invariants"]["conjecture_cluster_gray_never_green"] is True)

    # --- classification basis cited per cluster (to the Flower Brain) ---
    check("every cluster cites a classification basis to szl_kc_flower.py",
          all(isinstance(c["classification_basis"], str)
              and "szl_kc_flower.py" in c["classification_basis"] for c in m["clusters"]))

    # --- kernel clusters carry kernel objects ---
    check("kernel clusters (1,2,3,4,5,8) carry kernel objects",
          all(len(next(c for c in m["clusters"] if c["cluster"] == cn)["kernel_object_ids"]) >= 1
              for cn in (1, 2, 3, 4, 5, 8)))

    # --- bridges: cross-cluster + flower->all + loopforge->5,8 ---
    check("cross-cluster bridges exist (>=8)", m["cross_cluster_bridges"] >= 8)
    flower_dst = {b["dst_cluster"] for b in m["bridges"] if b["surface"] == "flower"}
    check("flower bridges to clusters 1,2,3,4,5,7,8", {1, 2, 3, 4, 5, 7, 8}.issubset(flower_dst))
    lf_dst = {b["dst_cluster"] for b in m["bridges"] if b["surface"] == "loopforge"}
    check("loopforge bridges to OUROBOROS(5) + CONJECTURE(8)", 5 in lf_dst and 8 in lf_dst)
    check("every bridge cites a reason",
          all(isinstance(b["why"], str) and b["why"].strip() for b in m["bridges"]))

    # --- organism: loop-forge flow overlay proposer->kernel->archive ---
    lf = org["loop_forge_flow"]
    check("loop-forge flow overlay stages proposer->kernel_gate->archive",
          lf["stages"] == ["proposer", "kernel_gate", "archive"])
    check("loop-forge writer!=judge & conjecture stays gray",
          lf["writer_ne_judge"] is True and lf["conjecture_stays_gray"] is True)
    check("organism cross-links present (>=8)", org["cross_links_total"] >= 8)

    # --- honesty_invariants all true ---
    hi = mf["honesty_invariants"]
    check("manifest honesty_invariants all True",
          all(hi[k] for k in (
              "label_is_MODELED", "clusters_is_exactly_8", "locked_core_is_exactly_8",
              "conjecture_cluster_gray_never_green", "coverage_full",
              "every_surface_classified_once", "zero_orphans", "zero_double_counts",
              "classification_basis_cited_per_cluster", "no_consciousness_claim")))
    check("no_consciousness_claim True", hi["no_consciousness_claim"] is True)

    # --- deterministic (same seed => identical) ---
    check("map deterministic", atlas.atlas_map(42) == atlas.atlas_map(42))
    check("organism deterministic", atlas.atlas_organism(42) == atlas.atlas_organism(42))
    check("manifest deterministic", atlas.atlas_manifest(42) == atlas.atlas_manifest(42))
    check("organism layout seed-sensitive", atlas.atlas_organism(7) != atlas.atlas_organism(42))
    check("classification seed-independent",
          atlas.atlas_map(7)["clusters"] == atlas.atlas_map(42)["clusters"])

    # --- register returns exactly the 3 paths ---
    class _NoApp:
        pass
    paths = atlas.register(_NoApp(), ns="killinchu")
    check("register returns the 3 exact atlas paths",
          paths == [
              "/api/killinchu/v1/atlas/manifest",
              "/api/killinchu/v1/atlas/map",
              "/api/killinchu/v1/atlas/organism",
          ])
    # namespace is honored
    paths_a = atlas.register(_NoApp(), ns="a11oy")
    check("register honors ns",
          paths_a == [
              "/api/a11oy/v1/atlas/manifest",
              "/api/a11oy/v1/atlas/map",
              "/api/a11oy/v1/atlas/organism",
          ])

    print()
    if FAILS:
        print("RESULT: FAIL (%d checks failed): %s" % (len(FAILS), ", ".join(FAILS)))
        return 1
    print("RESULT: ALL PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
