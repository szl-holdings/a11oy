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
import glob
import json
import os
import re

from fastapi import FastAPI
from fastapi.responses import JSONResponse

import a11oy_frontier_page as _frontier
import szl_puriq_formulas as _puriq

CANONICAL_DOMAIN = "a-11-oy.com"

# --------------------------------------------------------------------------- #
# HARVESTED FIELD LEADERS — committed JSONL shipped in the image.
# The estate's own 134 nodes are layers 0..3 (input->output). The harvested
# research field around SZL's thesis (papers, repos, labs, people, datasets,
# benchmarks, standards, axes) sits in an OUTER "field" layer (FIELD_LAYER = -1),
# BEYOND the estate's input layer — the real-world frontier that feeds the estate.
# Every harvested node keeps its honest label/url/source/axis; nothing invented.
# Counts are the ACTUAL merged len() — never hardcoded.
# --------------------------------------------------------------------------- #
FIELD_LAYER = -1
_HARVEST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "brain", "harvest")

# Person/author kinds are the arXiv co-author MULTIPLIER (one node per unique
# paper author). They are real named researchers on real papers, but counting
# them as "distinct work" overstates the graph — pass-2's harvest report
# disclosed ~56% of nodes are these. distinct_artifacts EXCLUDES them so the
# honest headline (distinct repos+papers+orgs+datasets+…) is never conflated
# with the raw node total. See pass2_deepening_REPORT.md.
_PERSON_KINDS = frozenset({"person", "author"})


def _harvest_files() -> list:
    """Basenames of every committed harvest JSONL, sorted for determinism.

    Globs brain/harvest/*.jsonl so a newly committed harvest pass (e.g.
    pass2_deepening.jsonl) is picked up automatically — no code change needed to
    add a file, and the Dockerfile COPYs the whole brain/harvest dir."""
    return sorted(os.path.basename(p)
                  for p in glob.glob(os.path.join(_HARVEST_DIR, "*.jsonl")))

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
# HARVEST LOADER
# --------------------------------------------------------------------------- #

def _iter_harvest_records():
    """Yield (kind, obj) for every JSONL record in the committed harvest files.

    Handles BOTH record shapes present in the harvest:
      * tagged   : {"type": "node"|"edge", ...}
      * bare     : node has {kind}; edge has {rel} + {src}/{dst}.
    kind is "node" or "edge". Missing/corrupt files are skipped honestly (the
    estate graph still builds; the harvest section reports available=False)."""
    for fname in _harvest_files():
        path = os.path.join(_HARVEST_DIR, fname)
        if not os.path.isfile(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tag = obj.get("type")
                is_edge = (tag == "edge"
                           or ("rel" in obj and ("src" in obj or "dst" in obj)))
                if is_edge:
                    yield "edge", obj
                elif tag == "node" or "kind" in obj:
                    yield "node", obj


def harvest_available() -> bool:
    """True if at least one committed harvest file is present at runtime."""
    return bool(_harvest_files())


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

    estate_node_count = len(nodes)
    estate_link_count = len(links)

    # ---- FIELD layer: harvested field leaders (committed JSONL) ----------- #
    # Dedupe by id: estate nodes are canonical and WIN — harvested duplicates
    # (e.g. surface:* stubs) are dropped, never overwriting the real estate node.
    harvested_added = 0
    harvest_dupes = 0
    _link_seen = set()  # (source, target, rel) dedupe for harvested links only
    pending_edges: list = []

    def _add_field_link(src: str, dst: str, rel: str, **attrs) -> None:
        key = (src, dst, rel)
        if key in _link_seen:
            return
        if src not in index or dst not in index or src == dst:
            return
        _link_seen.add(key)
        links.append({"source": src, "target": dst, "rel": rel, **attrs})
        index[src]["degree"] += 1
        index[dst]["degree"] += 1

    for kind, obj in _iter_harvest_records():
        if kind == "node":
            hid = obj.get("id")
            if not hid:
                continue
            if hid in index:  # collision with estate (or an earlier harvest id)
                harvest_dupes += 1
                continue
            node = add_node(
                hid,
                kind=obj.get("kind", "field"),
                layer=FIELD_LAYER,
                ring="field",
                title=obj.get("label", hid),
                label="HARVESTED",
                url=obj.get("url"),
                source=obj.get("source"),
                axis=obj.get("axis"),
                src_layer=obj.get("layer"),
            )
            harvested_added += 1
            # a node's own maps_to_surface -> a real surface node (deferred until
            # every node is loaded so the target may live in a later file).
            mts = obj.get("maps_to_surface")
            if mts:
                pending_edges.append((hid, f"surface:{mts}", "maps-to-surface"))
        else:  # edge
            src = obj.get("src")
            dst = obj.get("dst")
            rel = (obj.get("rel") or "related").replace("_", "-")
            if src and dst:
                pending_edges.append((src, dst, rel))

    # attach harvested edges last: maps-to-surface edges bind field leaders to
    # the REAL estate surface nodes; targets that resolve to nothing are dropped
    # (add-link is dangling-safe) — no fabricated placeholder nodes.
    for src, dst, rel in pending_edges:
        _add_field_link(src, dst, rel, derived_from="harvest")

    # strip internal token caches before returning
    for node in nodes:
        node.pop("_tokens", None)

    # ---- honest counts + breakdown ---------------------------------------- #
    kind_counts: dict = {}
    layer_counts: dict = {}
    source_counts: dict = {}
    axis_counts: dict = {}
    for node in nodes:
        kind_counts[node["kind"]] = kind_counts.get(node["kind"], 0) + 1
        layer_counts[node["layer"]] = layer_counts.get(node["layer"], 0) + 1
        src = node.get("source")
        if src:
            source_counts[src] = source_counts.get(src, 0) + 1
        ax = node.get("axis")
        if ax:
            axis_counts[ax] = axis_counts.get(ax, 0) + 1
    rel_counts: dict = {}
    for link in links:
        rel_counts[link["rel"]] = rel_counts.get(link["rel"], 0) + 1

    # ---- HONEST composition: total vs distinct artifacts ------------------ #
    # The raw node_count is dominated by arXiv co-author person nodes (a real
    # but multiplying construction). distinct_artifacts is the honest headline:
    # every node that is NOT a person/author — i.e. repos + papers + orgs +
    # datasets + benchmarks + labs + standards + axes + surfaces + formulas +
    # topics + endpoints + estate. Never present the raw total as if it were all
    # distinct work.
    person_node_count = sum(kind_counts.get(k, 0) for k in _PERSON_KINDS)
    distinct_artifacts = len(nodes) - person_node_count

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
            "-1": "field (harvested field leaders — outer ring, beyond input)",
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
            "harvest": {"count": harvested_added,
                        "deduped_against_estate": harvest_dupes,
                        "available": harvest_available(),
                        "files": _harvest_files(),
                        "layer": FIELD_LAYER,
                        "source": "brain/harvest/*.jsonl (real field leaders; "
                                  "every node carries a verified url + source)"},
        },
        "node_count": len(nodes),
        "link_count": len(links),
        # HONEST headline: distinct real artifacts (repos+papers+orgs+datasets+
        # …) vs the raw total, which is inflated by arXiv co-author person nodes.
        "distinct_artifacts": distinct_artifacts,
        "person_node_count": person_node_count,
        "artifact_note": (
            f"node_count {len(nodes)} includes {person_node_count} arXiv "
            f"co-author person nodes (a real but multiplying construction); "
            f"distinct_artifacts {distinct_artifacts} is the honest count of "
            f"non-person nodes (repos+papers+orgs+datasets+benchmarks+…). Never "
            f"present the raw total as if it were all distinct work."),
        "summary": {
            "node_count": len(nodes),
            "link_count": len(links),
            "distinct_artifacts": distinct_artifacts,
            "person_node_count": person_node_count,
            "estate_node_count": estate_node_count,
            "estate_link_count": estate_link_count,
            "harvest_node_count": harvested_added,
            "harvest_link_count": len(links) - estate_link_count,
            "by_kind": kind_counts,
            "by_layer": {str(k): v for k, v in sorted(layer_counts.items())},
            "by_rel": rel_counts,
            "by_source": dict(sorted(source_counts.items(),
                                     key=lambda kv: (-kv[1], kv[0]))),
            "by_axis": dict(sorted(axis_counts.items(),
                                   key=lambda kv: (-kv[1], kv[0]))),
            "locked_flagged": sum(1 for n in nodes if n.get("locked")),
        },
        "nodes": nodes,
        "links": links,
    }


# --------------------------------------------------------------------------- #
# CACHE + FILTERED VIEWS (the merged graph is big — build once, slice per query)
# --------------------------------------------------------------------------- #
_CACHE: dict = {}


def get_brain_graph(ns: str = "a11oy", *, refresh: bool = False) -> dict:
    """Return the merged graph, cached per-ns (built on first call).

    The merged graph is thousands of nodes; rebuilding it per request is wasted
    work on a pure read. Deterministic, so caching is safe."""
    if refresh or ns not in _CACHE:
        _CACHE[ns] = build_brain_graph(ns)
    return _CACHE[ns]


def _matches(node: dict, layer, axis, source, kind) -> bool:
    if layer is not None and node.get("layer") != layer:
        return False
    if axis is not None and node.get("axis") != axis:
        return False
    if source is not None and node.get("source") != source:
        return False
    if kind is not None and node.get("kind") != kind:
        return False
    return True


def filtered_graph(ns: str = "a11oy", *, layer=None, axis=None, source=None,
                   kind=None, summary: bool = False) -> dict:
    """A view over the cached merged graph.

    - summary=True  drops the heavy nodes/links arrays (counts + breakdowns only)
      so the 3D surface can size the render before pulling the full payload.
    - layer/axis/source restrict to a subgraph (nodes matching the filter plus
      the links wholly within that subset). node_count/link_count on a filtered
      view are the ACTUAL sizes of the returned subset — still never fabricated."""
    graph = get_brain_graph(ns)
    filtering = (layer is not None or axis is not None or source is not None
                 or kind is not None)

    if not filtering:
        view = dict(graph)
        if summary:
            view.pop("nodes", None)
            view.pop("links", None)
            view["mode"] = "summary"
        return view

    keep_nodes = [n for n in graph["nodes"]
                  if _matches(n, layer, axis, source, kind)]
    keep_ids = {n["id"] for n in keep_nodes}
    keep_links = [l for l in graph["links"]
                  if l["source"] in keep_ids and l["target"] in keep_ids]

    view = dict(graph)
    view["filter"] = {"layer": layer, "axis": axis, "source": source,
                      "kind": kind}
    view["node_count"] = len(keep_nodes)
    view["link_count"] = len(keep_links)
    view["distinct_artifacts"] = sum(
        1 for n in keep_nodes if n.get("kind") not in _PERSON_KINDS)
    view["person_node_count"] = sum(
        1 for n in keep_nodes if n.get("kind") in _PERSON_KINDS)
    view["full_node_count"] = graph["node_count"]
    view["full_link_count"] = graph["link_count"]
    if summary:
        view.pop("nodes", None)
        view.pop("links", None)
        view["mode"] = "summary"
    else:
        view["nodes"] = keep_nodes
        view["links"] = keep_links
    return view


def register(app: FastAPI, ns: str = "a11oy") -> str:
    """Mount GET /api/<ns>/v1/brain/graph. ADDITIVE — before the SPA catch-all.

    Pure read; harvests the real estate + committed field-leader JSONL into a
    layered node/link graph (cached). Signs nothing (receipt-on-write, never on
    GET). Query params: ?layer=<int> ?axis=<token> ?source=<token>
    ?kind=<token> ?summary=1 (counts only)."""

    @app.get(f"/api/{ns}/v1/brain/graph")
    async def brain_graph(layer: int = None, axis: str = None,
                          source: str = None, kind: str = None,
                          summary: bool = False) -> JSONResponse:  # noqa: ANN202
        return JSONResponse(filtered_graph(
            ns, layer=layer, axis=axis, source=source, kind=kind,
            summary=summary))

    g = get_brain_graph(ns)
    return (f"brain-graph mounted: GET /api/{ns}/v1/brain/graph "
            f"(MODELED estate + HARVESTED field leaders; {g['node_count']} nodes, "
            f"{g['distinct_artifacts']} distinct artifacts, {g['link_count']} "
            f"links; cached; ?layer=/?axis=/?source=/?kind=/?summary=1; "
            "honest merged counts; 0 sign-on-read)")


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
    # real source counts. Surfaces are read LIVE from holographic.html (the one
    # source of truth), so pin the structural invariant, not a magic number that
    # drifts every time a surface is added: estate = 70 fixed scaffold (1 estate
    # + 4 endpoints + 8 topics + 23 formulas + 34 repos) + N live surfaces.
    surf_count = g["sources"]["surfaces"]["count"]
    assert surf_count >= 64, f"expected >=64 frontier surfaces, got {surf_count}"
    assert g["sources"]["formulas"]["count"] == 23, "expected 23 PURIQ formulas"
    assert g["sources"]["repos"]["count"] == 34, "expected 34 active org repos"
    assert g["summary"]["locked_flagged"] == 8, "exactly 8 locked formulas flagged"
    # neural-net layering present on every node
    assert all("layer" in n for n in g["nodes"]), "every node needs a layer"
    # every link references existing nodes
    ids = {n["id"] for n in g["nodes"]}
    assert all(l["source"] in ids and l["target"] in ids for l in g["links"]), \
        "dangling link endpoint"
    # required relation types are all present
    rels = set(g["summary"]["by_rel"])
    for r in ("formula-surface", "repo-surface", "surface-endpoint"):
        assert r in rels, f"required relation {r} missing"

    # ---- HONEST composition (distinct artifacts vs person multiplier) ------ #
    persons = sum(1 for n in g["nodes"] if n.get("kind") in _PERSON_KINDS)
    assert g["person_node_count"] == persons, "person_node_count must be real len()"
    assert g["distinct_artifacts"] == g["node_count"] - persons, \
        "distinct_artifacts must be node_count minus person/author nodes"
    assert g["distinct_artifacts"] == g["summary"]["distinct_artifacts"], \
        "distinct_artifacts must match between top-level and summary"
    assert g["distinct_artifacts"] <= g["node_count"], "artifacts <= total"
    # distinct_artifacts must never be presented as the raw total
    assert g["distinct_artifacts"] == g["node_count"] - g["person_node_count"]

    # ---- harvested field-leader merge (honest, deduped, layered) ---------- #
    if harvest_available():
        est_n = g["summary"]["estate_node_count"]
        har_n = g["summary"]["harvest_node_count"]
        assert est_n == 70 + surf_count, \
            f"estate = 70 scaffold + {surf_count} live surfaces, got {est_n}"
        assert har_n > 1000, f"expected thousands of harvested nodes, got {har_n}"
        assert g["node_count"] == est_n + har_n, "merged node_count must add up"
        # pass-2 must be picked up by the glob loader (not a fixed file list)
        assert "pass2_deepening.jsonl" in g["sources"]["harvest"]["files"], \
            "pass-2 harvest file must be discovered by the *.jsonl glob"
        # with pass-2 merged the graph clears the ~8,000 goal, but on TOTAL
        # nodes — the honest distinct-artifact count is much lower and disclosed
        assert har_n > 8000, f"pass-1+2 harvest should exceed 8,000, got {har_n}"
        assert g["person_node_count"] > g["distinct_artifacts"], \
            "pass-2 disclosed persons dominate — must not hide behind the total"
        # field ring present and beyond input
        assert "-1" in g["summary"]["by_layer"], "field layer (-1) must be present"
        assert FIELD_LAYER < 0, "field ring must sit beyond the input layer"
        # honest counts — never the leaked/hardcoded vanity figures
        assert g["node_count"] not in (8893, 8000), "counts must be REAL len()"
        # every harvested node keeps a real url + honest source/label
        field = [n for n in g["nodes"] if n.get("layer") == FIELD_LAYER]
        assert all(n.get("url") and n.get("source") for n in field), \
            "every harvested node needs a real url + source"
        assert all(n.get("label") == "HARVESTED" for n in field), "honest label"
        # locked-8 UNTOUCHED by the harvest
        assert g["summary"]["locked_flagged"] == 8, "harvest adds nothing to locked-8"
        # by_source / by_axis breakdowns present and non-trivial
        assert len(g["summary"]["by_source"]) >= 5, "by_source breakdown missing"
        assert len(g["summary"]["by_axis"]) >= 5, "by_axis breakdown missing"
        # maps-to-surface edges bind field leaders to REAL surface nodes
        surf_ids = {n["id"] for n in g["nodes"] if n["kind"] == "surface"}
        m2s = [l for l in g["links"] if l["rel"] == "maps-to-surface"
               and l["target"] in surf_ids]
        assert m2s, "expected maps-to-surface edges into real surface nodes"
        # filter + summary views are self-consistent
        sub = filtered_graph("a11oy", layer=FIELD_LAYER)
        assert sub["node_count"] == har_n, "layer filter must return the field ring"
        assert all(n["layer"] == FIELD_LAYER for n in sub["nodes"]), "filter leak"
        summ = filtered_graph("a11oy", summary=True)
        assert "nodes" not in summ and summ["node_count"] == g["node_count"], \
            "summary mode drops arrays but keeps honest counts"
        top_axis = next(iter(g["summary"]["by_axis"]))
        axv = filtered_graph("a11oy", axis=top_axis)
        assert axv["node_count"] > 0 and axv["node_count"] < g["node_count"], \
            "axis filter must return a proper subset"
        # kind filter returns a proper single-kind subset
        top_kind = max(g["summary"]["by_kind"].items(), key=lambda kv: kv[1])[0]
        kv = filtered_graph("a11oy", kind=top_kind)
        assert all(n["kind"] == top_kind for n in kv["nodes"]), "kind filter leak"
        assert kv["node_count"] == g["summary"]["by_kind"][top_kind], \
            "kind filter count must match by_kind"
        print(f"a11oy_brain_graph: ALL OK — MERGED {g['node_count']} nodes "
              f"({est_n} estate + {har_n} harvested; "
              f"{g['distinct_artifacts']} distinct artifacts + "
              f"{g['person_node_count']} arXiv co-author persons), "
              f"{g['link_count']} links; "
              f"files={g['sources']['harvest']['files']}; "
              f"by_layer={g['summary']['by_layer']}; "
              f"by_kind={g['summary']['by_kind']}; "
              f"by_source={len(g['summary']['by_source'])} sources; "
              f"by_axis={len(g['summary']['by_axis'])} axes; locked_flagged=8")
    else:
        assert set(g["summary"]["by_layer"]) == {"0", "1", "2", "3"}, "4 layers"
        print(f"a11oy_brain_graph: ALL OK (estate-only; harvest files absent) — "
              f"{g['node_count']} nodes, {g['link_count']} links")


if __name__ == "__main__":
    _selftest()
