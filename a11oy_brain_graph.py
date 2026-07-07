# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11 LOCKED
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""a11oy_brain_graph.py — GET /api/<ns>/v1/brain/graph.

The estate's own self-rendering knowledge brain: a node/link graph HARVESTED
from the REAL a11oy estate, shaped for a neural-network-style 3D render (input
layer -> hidden layers -> output). This is the SZL answer to the leaked
"Self-Writing Vault" diagram — but every node traces to a real file/endpoint,
the counts are the ACTUAL harvested totals, and nothing is fabricated.

WHAT IT HARVESTS (all real sources — no invented nodes):
  * 64 frontier surfaces  — reuses a11oy_frontier_page.build_surfaces_manifest()
                            (the one source of truth parsed from holographic.html;
                            each surface carries its verbatim honesty label).
  * 23 PURIQ formulas F1..F23 — reuses szl_puriq_formulas.FORMULA_META (the
                            wave formula substrate). The locked-8
                            {F1,F4,F7,F11,F12,F18,F19,F22} are flagged
                            (EXPERIMENTAL_WAVES.locked_ids); F23 (Λ) carries
                            "Conjecture 1" — NEVER a theorem.
  * 34 active org repos    — a static snapshot of the live szl-holdings GitHub
                            inventory (non-archived, non-fork) captured at build
                            time; provenance + capture date are reported.
  * topic clusters         — derived from the distinct formula organs (a real
                            grouping read from FORMULA_META, not invented).
  * live endpoints         — the real routes this view draws from.
  * estate root            — the single canonical output node (a-11-oy.com).

LINKS are REAL relations, each carrying a `rel` type and a `via`/`derived_from`
provenance field:
  * repo -> surface     (repo name token appears in the surface id/title)
  * surface -> endpoint (every surface is listed by /frontier/surfaces)
  * formula -> surface  (formula token appears in the surface id/title)
  * formula -> topic    (formula's own organ)
  * repo -> topic       (repo name token matches a topic)
  * topic -> estate     (structural backbone)
  * formula -> estate   (locked-8 + Λ proven/conjectured backbone -> thesis)
  * endpoint -> estate  (each live endpoint feeds the estate root)

LAYERS (for the neural-net render; `layer` on every node):
  0 = INPUT   : repos + surfaces
  1 = HIDDEN  : topic clusters
  2 = HIDDEN  : formulas (locked-8 highlighted)
  3 = OUTPUT  : estate root + live endpoints

Doctrine v11 honesty:
  * node_count / link_count are the ACTUAL len() of the harvested graph — never
    a made-up figure (this is explicitly NOT the leaked "8,893 nodes").
  * Top-level label is MODELED — this is a derived view over the estate.
  * PURE READ — parses files / reads module data. Signs nothing, appends to no
    provenance chain (receipts belong on writes, never on GETs).
"""

import datetime
import re

from fastapi import FastAPI
from fastapi.responses import JSONResponse

import a11oy_frontier_page as _frontier
import szl_puriq_formulas as _puriq

CANONICAL_DOMAIN = "a-11-oy.com"

# --------------------------------------------------------------------------- #
# STATIC SNAPSHOT — 34 active szl-holdings repos.
# Captured from the live GitHub inventory (gh repo list szl-holdings
# --no-archived) on 2026-07-07: non-archived, non-fork == 34 repos. Baked in as
# a static list so the endpoint is a PURE READ with no runtime network call.
# Honest label: MODELED snapshot — refresh via brain/harvest_vault.py.
# --------------------------------------------------------------------------- #
ORG_REPOS_SNAPSHOT = {
    "captured": "2026-07-07",
    "org": "szl-holdings",
    "source": "gh repo list szl-holdings --no-archived --json name (non-fork)",
    "label": "MODELED",
    "repos": [
        ".github", "a11oy", "anatomy", "david-leads", "developers", "docs-site",
        "governed-inference-meter", "hatun-mcp", "immune", "khipu-consensus",
        "khipu-sda-core", "killinchu", "lean-kernel", "lutar-lean", "ouroboros",
        "pitch-collateral", "platform", "szl-brand", "szl-build-env",
        "szl-cookbook", "szl-doctrine", "szl-energy-attest", "szl-governed-norm",
        "szl-lake", "szl-lambda-gate", "szl-mesh", "szl-papers", "szl-receipt",
        "szl-router", "szl-substrate", "szl-trust", "vsp-otel", "warhacker-demo",
        "yarqa",
    ],
}

# Tokens too generic to carry a meaningful cross-node relation.
_STOPWORDS = frozenset({
    "szl", "a11oy", "the", "and", "for", "with", "org", "demo", "core2",
    "leads", "env", "build", "collateral", "norm",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokens(*parts: str) -> set:
    """Lowercase alnum tokens (len>=3) from the given strings, minus stopwords."""
    out = set()
    for p in parts:
        for t in _TOKEN_RE.findall((p or "").lower()):
            if len(t) >= 3 and t not in _STOPWORDS:
                out.add(t)
    return out


# --------------------------------------------------------------------------- #
# GRAPH BUILDER
# --------------------------------------------------------------------------- #

def build_brain_graph(ns: str = "a11oy") -> dict:
    """Harvest the real estate into a layered node/link brain graph.

    Deterministic and pure: given the same repo state it returns the same graph.
    Counts are the real len() of what was harvested. Never fabricates a node."""
    surfaces_ep = f"/api/{ns}/v1/frontier/surfaces"
    formulas_ep = f"/api/{ns}/v1/puriq/formulas"
    manifest_ep = f"/api/{ns}/v1/frontier/manifest"
    graph_ep = f"/api/{ns}/v1/brain/graph"

    nodes: list = []
    links: list = []
    index: dict = {}  # id -> node (for degree accounting)

    def add_node(nid: str, **attrs) -> dict:
        node = {"id": nid, "degree": 0, **attrs}
        nodes.append(node)
        index[nid] = node
        return node

    def add_link(src: str, dst: str, rel: str, **attrs) -> None:
        if src not in index or dst not in index or src == dst:
            return
        links.append({"source": src, "target": dst, "rel": rel, **attrs})
        index[src]["degree"] += 1
        index[dst]["degree"] += 1

    # ---- OUTPUT layer: estate root ---------------------------------------- #
    estate_id = f"estate:{CANONICAL_DOMAIN}"
    add_node(estate_id, kind="estate", layer=3, title="SZL estate / thesis",
             domain=CANONICAL_DOMAIN, label="MODELED",
             note="derived-view root; Λ = Conjecture 1, never a theorem")

    # ---- OUTPUT layer: live endpoints ------------------------------------- #
    endpoint_defs = [
        (surfaces_ep, "frontier surfaces manifest"),
        (formulas_ep, "PURIQ formulas registry"),
        (manifest_ep, "frontier honest roll-up"),
        (graph_ep, "brain graph (this view)"),
    ]
    endpoint_ids = {}
    for path, title in endpoint_defs:
        eid = f"endpoint:{path}"
        endpoint_ids[path] = eid
        add_node(eid, kind="endpoint", layer=3, title=title, path=path,
                 label="LIVE")
        add_link(eid, estate_id, "endpoint-estate", derived_from="route-map")

    # ---- HIDDEN layer 1: topic clusters (distinct formula organs) --------- #
    topic_ids = {}

    def _organ_tokens(organ: str) -> list:
        return [t for t in organ.replace("A/agency", "A").split("/") if t]

    for meta in _puriq.FORMULA_META.values():
        for tok in _organ_tokens(meta.get("organ", "")):
            if tok not in topic_ids:
                tid = f"topic:{tok}"
                topic_ids[tok] = tid
                add_node(tid, kind="topic", layer=1, title=tok,
                         label="MODELED", derived_from="FORMULA_META.organ")
                add_link(tid, estate_id, "topic-estate", derived_from="backbone")

    # ---- INPUT layer: surfaces (real manifest) ---------------------------- #
    surf_manifest = _frontier.build_surfaces_manifest(ns)
    surface_nodes = []
    for su in surf_manifest.get("surfaces", []):
        sid = f"surface:{su['id']}"
        node = add_node(sid, kind="surface", layer=0, title=su.get("title", su["id"]),
                        label=su.get("label", "UNAVAILABLE"),
                        present=su.get("present", False), asset=su.get("asset"))
        node["_tokens"] = _tokens(su.get("id", ""), su.get("title", ""))
        surface_nodes.append((su, node, sid))
        # surface -> endpoint (every surface is listed by /frontier/surfaces)
        add_link(sid, endpoint_ids[surfaces_ep], "surface-endpoint",
                 derived_from="frontier/surfaces manifest")

    # ---- HIDDEN layer 2: formulas (locked-8 flagged) ---------------------- #
    locked = set(_puriq.EXPERIMENTAL_WAVES.get("locked_ids", []))
    for fid, meta in _puriq.FORMULA_META.items():
        nid = f"formula:{fid}"
        is_lambda = fid == "F23"
        node = add_node(
            nid, kind="formula", layer=2, title=meta.get("name", fid),
            formula_id=fid, organ=meta.get("organ", ""),
            proof_status=meta.get("proof_status", "UNATTEMPTED"),
            locked=fid in locked,
            label="MODELED" if not is_lambda else "MODELED",
            conjecture="Conjecture 1" if is_lambda else None,
            primitive=meta.get("primitive", ""))
        ftokens = _tokens(meta.get("name", ""), meta.get("primitive", ""),
                          meta.get("organ", ""))
        # formula -> topic (its own organ)
        for tok in _organ_tokens(meta.get("organ", "")):
            add_link(nid, topic_ids.get(tok, ""), "formula-topic",
                     derived_from="FORMULA_META.organ")
        # formula -> surface (shared token in surface id/title)
        for _su, snode, sid in surface_nodes:
            shared = ftokens & snode["_tokens"]
            if shared:
                add_link(nid, sid, "formula-surface", via=sorted(shared)[0])
        # locked-8 + Λ proven/conjectured backbone -> thesis output
        if fid in locked or is_lambda:
            add_link(nid, estate_id, "formula-estate",
                     derived_from="locked-8" if fid in locked else "Λ=Conjecture 1")

    # ---- INPUT layer: repos (static snapshot) ----------------------------- #
    for repo in ORG_REPOS_SNAPSHOT["repos"]:
        rid = f"repo:{repo}"
        add_node(rid, kind="repo", layer=0, title=repo, label="MODELED",
                 org=ORG_REPOS_SNAPSHOT["org"])
        rtokens = _tokens(repo)
        # repo -> surface (repo name token appears in surface id/title)
        for _su, snode, sid in surface_nodes:
            shared = rtokens & snode["_tokens"]
            if shared:
                add_link(rid, sid, "repo-surface", via=sorted(shared)[0])
        # repo -> topic (repo name token matches a topic cluster)
        for tok in rtokens:
            if tok in topic_ids:
                add_link(rid, topic_ids[tok], "repo-topic", via=tok)

    # strip internal token caches before returning
    for node in nodes:
        node.pop("_tokens", None)

    # ---- honest counts + breakdown ---------------------------------------- #
    kind_counts: dict = {}
    layer_counts: dict = {}
    for node in nodes:
        kind_counts[node["kind"]] = kind_counts.get(node["kind"], 0) + 1
        layer_counts[node["layer"]] = layer_counts.get(node["layer"], 0) + 1
    rel_counts: dict = {}
    for link in links:
        rel_counts[link["rel"]] = rel_counts.get(link["rel"], 0) + 1

    return {
        "label": "MODELED",
        "endpoint": graph_ep,
        "generated": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "doctrine": {
            "version": "v11",
            "lambda": "Conjecture 1",
            "locked_count": len(locked),
            "locked_ids": sorted(locked),
            "canonical_domain": CANONICAL_DOMAIN,
            "note": ("MODELED derived view; node/link counts are the ACTUAL "
                     "harvested totals (NOT the leaked 8,893). Pure read — no "
                     "signing on GET."),
        },
        "layers": {
            "0": "input (repos + surfaces)",
            "1": "hidden (topic clusters)",
            "2": "hidden (formulas; locked-8 highlighted)",
            "3": "output (estate root + live endpoints)",
        },
        "sources": {
            "surfaces": {"endpoint": surfaces_ep, "count": len(surface_nodes),
                         "source": "a11oy_frontier_page.build_surfaces_manifest"},
            "formulas": {"endpoint": formulas_ep, "count": len(_puriq.FORMULA_META),
                         "source": "szl_puriq_formulas.FORMULA_META"},
            "repos": {"count": len(ORG_REPOS_SNAPSHOT["repos"]),
                      "captured": ORG_REPOS_SNAPSHOT["captured"],
                      "source": ORG_REPOS_SNAPSHOT["source"]},
            "topics": {"count": len(topic_ids),
                       "source": "distinct FORMULA_META.organ"},
        },
        "node_count": len(nodes),
        "link_count": len(links),
        "summary": {
            "node_count": len(nodes),
            "link_count": len(links),
            "by_kind": kind_counts,
            "by_layer": {str(k): v for k, v in sorted(layer_counts.items())},
            "by_rel": rel_counts,
            "locked_flagged": sum(1 for n in nodes if n.get("locked")),
        },
        "nodes": nodes,
        "links": links,
    }


def register(app: FastAPI, ns: str = "a11oy") -> str:
    """Mount GET /api/<ns>/v1/brain/graph. ADDITIVE — before the SPA catch-all.

    Pure read; harvests the real estate into a layered node/link graph. Signs
    nothing (receipt-on-write, never on GET)."""

    @app.get(f"/api/{ns}/v1/brain/graph")
    async def brain_graph() -> JSONResponse:  # noqa: ANN202
        return JSONResponse(build_brain_graph(ns))

    return (f"brain-graph mounted: GET /api/{ns}/v1/brain/graph "
            "(MODELED; harvests surfaces+formulas+repos+topics into a layered "
            "neural-net graph; honest node/link counts; 0 sign-on-read)")


def _selftest() -> None:
    g = build_brain_graph("a11oy")
    assert g["label"] == "MODELED", "top label must be MODELED (derived view)"
    assert g["doctrine"]["lambda"] == "Conjecture 1", "Λ must be Conjecture 1"
    assert g["doctrine"]["locked_count"] == 8, "locked count must be EXACTLY 8"
    assert len(g["doctrine"]["locked_ids"]) == 8, "locked ids must be 8"
    assert g["doctrine"]["canonical_domain"] == "a-11-oy.com", "canonical domain"
    # counts are the ACTUAL harvested totals, never fabricated
    assert g["node_count"] == len(g["nodes"]), "node_count must equal len(nodes)"
    assert g["link_count"] == len(g["links"]), "link_count must equal len(links)"
    assert g["node_count"] != 8893, "must NOT be the leaked fabricated 8,893"
    # real source counts
    assert g["sources"]["surfaces"]["count"] == 64, "expected 64 frontier surfaces"
    assert g["sources"]["formulas"]["count"] == 23, "expected 23 PURIQ formulas"
    assert g["sources"]["repos"]["count"] == 34, "expected 34 active org repos"
    assert g["summary"]["locked_flagged"] == 8, "exactly 8 locked formulas flagged"
    # neural-net layering present on every node
    assert all("layer" in n for n in g["nodes"]), "every node needs a layer"
    assert set(g["summary"]["by_layer"]) == {"0", "1", "2", "3"}, "4 layers"
    # every link references existing nodes
    ids = {n["id"] for n in g["nodes"]}
    assert all(l["source"] in ids and l["target"] in ids for l in g["links"]), \
        "dangling link endpoint"
    # required relation types are all present
    rels = set(g["summary"]["by_rel"])
    for r in ("formula-surface", "repo-surface", "surface-endpoint"):
        assert r in rels, f"required relation {r} missing"
    print(f"a11oy_brain_graph: ALL OK — {g['node_count']} nodes, "
          f"{g['link_count']} links; by_kind={g['summary']['by_kind']}; "
          f"by_layer={g['summary']['by_layer']}; locked_flagged=8")


if __name__ == "__main__":
    _selftest()
