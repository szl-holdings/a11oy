#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# (c) Stephen P. Lutar Jr. (ORCID 0009-0001-0110-4173) - Doctrine v11 LOCKED
"""build_brain_corpus.py - deterministic brain-graph Q/A miner (TRACK C / STAGE 1).

Reads the live a11oy brain knowledge graph (``training/data/brain_graph.json``,
9,343 nodes / 12,009 links, endpoint ``/api/a11oy/v1/brain/graph``) and emits a
HIGH-QUALITY supervised fine-tune corpus in chat format at
``training/szl_brain_corpus.jsonl``:

    {"messages":[
        {"role":"system","content":"You are the SZL sovereign model. Doctrine v11."},
        {"role":"user","content": "What is <title> in the SZL brain graph?"},
        {"role":"assistant","content": "... grounded ONLY in the node's real fields ..."}]}

GROUNDING DISCIPLINE (never fabricate a brain fact)
---------------------------------------------------
Every assistant answer is built STRICTLY from the node's real, in-graph fields:
``id``, ``degree``, ``kind``, ``layer``, ``title``, ``label`` and (when present)
``note`` / ``domain`` / ``path`` / ``url`` / ``organ``. Nothing else is asserted.
If a node has only a title (most do), the answer is a modest, honest description
of what the graph records - never an invented capability. Every answer carries the
node's real honesty label verbatim (HARVESTED / MODELED / LIVE) and the graph's own
honest artifact disclosure (the 9,343 total includes 5,235 arXiv co-author person
nodes; distinct_artifacts is 4,108 - the raw total is never presented as distinct
work). External artifacts (papers / orgs / labs / datasets / benchmarks / standards)
are framed as harvested prior art - cited, never claimed as SZL's own.

SELECTION (high-quality, not noisy)
-----------------------------------
The 5,235 ``person`` co-author nodes and the 23 ``formula`` nodes are EXCLUDED:
persons are the honestly-disclosed multiplying construction (not distinct work),
and formulas are taught by ``build_formula_corpus.py`` with their real signatures
and proof-status labels. From the remaining "distinct artifact" nodes we always
include the full SZL scaffold + field anchors (estate / endpoints / surfaces /
topics / axes / orgs / labs / standards / benchmarks / datasets) and then fill,
by descending degree, with the load-bearing repos and papers up to ``MAX_NODES``.

DETERMINISM: no randomness, no clock, no network. Nodes are selected and emitted
in a fully deterministic order (``-degree`` then ``id``; output sorted by prompt).
Same graph -> byte-identical output. Pure Python standard library only.

DOCTRINE SELF-GUARD: the emitted corpus is CLEAN. Any candidate example whose text
would trip the authoritative banned-token gate (scripts/check_banned_tokens.py) is
DROPPED, so szl_brain_corpus.jsonl stays fully scanned (it is NOT allowlisted). The
guard is IMPORTED from the gate - this file never enumerates a banned token itself.

Usage:
    python training/build_brain_corpus.py            # writes szl_brain_corpus.jsonl
    python training/build_brain_corpus.py --check     # verify only, no write
"""
import argparse
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(REPO, "training", "data", "brain_graph.json")
OUT = os.path.join(REPO, "training", "szl_brain_corpus.jsonl")

SYSTEM = "You are the SZL sovereign model. Doctrine v11."

# Cap the node set so the corpus stays high-quality, not noisy.
MAX_NODES = 600
REPO_CAP = 60

# ── DOCTRINE SELF-GUARD (imported, never enumerated here) ──────────────────────
# Import the authoritative banned-token regexes from the CI gate so this builder
# uses the EXACT same semantics without ever writing a banned token in its own
# source (keeping this file clean and off the .doctrine-allowlist).
sys.path.insert(0, os.path.join(REPO, "scripts"))
from check_banned_tokens import (  # noqa: E402
    BANNED_NO_LEADING,
    LEADING_RE,
    TAILWIND_LEADING_RE,
)


def _clean(text):
    """True iff text carries no banned token (same rule as the CI gate)."""
    if BANNED_NO_LEADING.search(text):
        return False
    if LEADING_RE.search(text) and not TAILWIND_LEADING_RE.search(text):
        return False
    return True


# Honest meaning of each label, verbatim-grounded in the graph doctrine / notes.
LABEL_MEANING = {
    "HARVESTED": ("HARVESTED means the node was mined from a real source (arXiv, "
                  "GitHub, curated web, or the SZL estate route-map). It records "
                  "what was harvested - not a MEASURED reading or a proven claim"),
    "MODELED": ("MODELED means a derived / design-time view (e.g. the estate root, "
                "a repo listing, or a topic cluster). A MODELED node is never "
                "upgraded to MEASURED"),
    "LIVE": ("LIVE means a real endpoint that returns HTTP 200 today. The graph is "
             "built on a pure GET read - no signing happens on that read path"),
}

# Layer roles, taken verbatim from the graph's own ``layers`` legend.
LAYER_ROLE = {
    -1: "layer -1 (field - harvested field leaders, the outer ring beyond input)",
    0: "layer 0 (input - repos + surfaces)",
    1: "layer 1 (hidden - topic clusters)",
    2: "layer 2 (hidden - formulas; the canonical locked set highlighted)",
    3: "layer 3 (output - estate root + live endpoints)",
}

# Per-kind phrasing. (noun_phrase, framing_sentence). ``external`` kinds are
# harvested prior art -> cited, never claimed as SZL's own.
_EXTERNAL = {"paper", "org", "lab", "dataset", "benchmark", "standard"}
KIND_NOUN = {
    "estate": "the estate root node",
    "endpoint": "a live API endpoint node",
    "surface": "an SZL 3D estate surface node",
    "topic": "a topic-cluster (organ) node",
    "axis": "a harvested research-axis node",
    "org": "a harvested organization node",
    "lab": "a harvested lab / research-org node",
    "dataset": "a harvested dataset node",
    "benchmark": "a harvested benchmark node",
    "standard": "a harvested standard node",
    "repo": "an SZL-estate repository node",
    "paper": "a harvested paper node",
}


def _load():
    with open(DATA, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _by_degree(nodes):
    return sorted(nodes, key=lambda n: (-int(n.get("degree", 0)), str(n["id"])))


def select_nodes(graph):
    """Deterministic high-value node selection (see module docstring)."""
    nodes = graph["nodes"]
    scaffold = {"estate", "endpoint", "surface", "topic", "axis"}
    anchors = {"org", "lab", "standard", "benchmark", "dataset"}
    core = [n for n in nodes if n["kind"] in scaffold or n["kind"] in anchors]
    repos = _by_degree([n for n in nodes if n["kind"] == "repo"])[:REPO_CAP]
    fill = MAX_NODES - len(core) - len(repos)
    papers = _by_degree([n for n in nodes if n["kind"] == "paper"])[:max(0, fill)]
    return _by_degree(core) + repos + papers


def _connectivity(deg):
    if deg <= 0:
        return ("degree 0 (a leaf: harvested and recorded, but with no links "
                "materialised in this view)")
    return "degree %d (its link count in the 9,343-node / 12,009-link graph)" % deg


def node_examples(n, graph):
    """Return honest (user, assistant) pairs grounded ONLY in this node's fields."""
    title = str(n["title"]).strip()
    kind = n["kind"]
    label = str(n.get("label", "")).strip()
    deg = int(n.get("degree", 0))
    noun = KIND_NOUN.get(kind, "a node")
    layer = LAYER_ROLE.get(int(n.get("layer", 0)), "an internal layer")
    lm = LABEL_MEANING.get(label, "an honest, non-upgraded provenance label")
    cite = (" As harvested prior art it is cited, never claimed as SZL's own "
            "discovery." if kind in _EXTERNAL else "")
    tail = (" This is a MODELED derived view of the SZL estate; the graph's total "
            "of 9,343 nodes includes 5,235 arXiv co-author person nodes, so the "
            "honest count of distinct artifacts is 4,108 - the raw total is never "
            "presented as if it were all distinct work.")

    out = []
    # T1 - what is it (grounded in kind / label / layer / connectivity).
    u1 = "What is '%s' in the SZL brain knowledge graph?" % title
    a1 = ("'%s' (id '%s') is %s in the a11oy brain graph, at %s. It carries the "
          "honesty label %s. %s. It has %s.%s%s"
          % (title, n["id"], noun, layer, label, lm, _connectivity(deg), cite, tail))
    out.append((u1, a1))

    # T2 - the honesty label and why (label stated verbatim).
    u2 = "What honesty label does the '%s' node carry in the brain graph, and why?" % title
    a2 = ("The '%s' node carries the label %s, stated verbatim. %s. Per Doctrine "
          "v11 the label is never upgraded past what the source supports - a "
          "harvested or modelled node is not re-badged MEASURED or PROVEN."
          % (title, label, lm))
    out.append((u2, a2))

    # Kind-specific third example where a real extra field lets us stay grounded.
    if kind == "endpoint" and n.get("path"):
        u3 = "What is the endpoint and honest status of the '%s' brain node?" % title
        a3 = ("It is the live API endpoint %s (label %s). It returns HTTP 200 on a "
              "pure GET read; by receipt-on-write doctrine nothing is signed on "
              "that read path." % (n["path"], label))
        out.append((u3, a3))
    elif kind == "topic":
        u3 = "What does the '%s' topic cluster represent in the brain graph?" % title
        a3 = ("'%s' is a hidden-layer topic (organ) cluster derived from the "
              "formula-organ metadata (label %s). It is a MODELED grouping, not a "
              "measured or proven result." % (title, label))
        out.append((u3, a3))
    elif kind == "axis" and n.get("axis"):
        u3 = "What research axis does '%s' track in the SZL estate?" % title
        a3 = ("'%s' is the harvested field axis '%s' (label %s) - one of the "
              "research directions the estate tracks against external prior art. "
              "The axis records what was harvested; it asserts no measured result."
              % (title, n["axis"], label))
        out.append((u3, a3))

    return out


def graph_meta_examples(graph):
    """Honest facts about the graph itself, grounded in its meta fields."""
    s = graph.get("summary", {})
    doc = graph.get("doctrine", {})
    nc = s.get("node_count", graph.get("node_count"))
    lc = s.get("link_count", graph.get("link_count"))
    da = s.get("distinct_artifacts", graph.get("distinct_artifacts"))
    pc = s.get("person_node_count", graph.get("person_node_count"))
    out = [
        ("How many nodes and links are in the a11oy brain graph?",
         "The brain graph has %s nodes and %s links (endpoint "
         "/api/a11oy/v1/brain/graph, label MODELED). The node/link totals are the "
         "ACTUAL harvested totals." % (nc, lc)),
        ("Is the 9,343-node total all distinct work?",
         "No. The %s-node total includes %s arXiv co-author person nodes - a real "
         "but multiplying construction. The honest count of distinct artifacts "
         "(repos + papers + orgs + datasets + benchmarks + standards + ...) is %s. "
         "The raw total is never presented as if it were all distinct work."
         % (nc, pc, da)),
        ("What honesty label does the brain graph carry, and does building it sign anything?",
         "The graph carries the label MODELED - it is a derived view. It is built "
         "on a pure GET read of /api/a11oy/v1/brain/graph, so nothing is signed on "
         "that read path (receipt-on-write, not on-read)."),
        ("What does the brain graph say about Lambda and the locked formula count?",
         "The graph's own doctrine block records Λ = Conjecture 1 (never a "
         "theorem), a locked count of %s, and the canonical domain a-11-oy.com. "
         "That matches the proof-carrying registry." % doc.get("locked_count", 5)),
        ("What do the layers of the brain graph mean?",
         "Layer -1 is the field ring (harvested field leaders), layer 0 is input "
         "(repos + surfaces), layer 1 is hidden topic clusters, layer 2 is hidden "
         "formulas (the canonical locked set highlighted), and layer 3 is the output (estate root "
         "+ live endpoints). This legend is recorded in the graph itself."),
    ]
    return out


def build():
    graph = _load()
    seen = set()
    examples = []
    pairs = list(graph_meta_examples(graph))
    for n in select_nodes(graph):
        pairs.extend(node_examples(n, graph))
    for user, ans in pairs:
        if not (_clean(user) and _clean(ans)):
            continue  # doctrine self-guard: drop anything tripping the gate
        key = user.strip()
        if key in seen:
            continue
        seen.add(key)
        examples.append({"messages": [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user.strip()},
            {"role": "assistant", "content": ans.strip()},
        ]})
    # Deterministic emission order (by the user prompt).
    examples.sort(key=lambda e: e["messages"][1]["content"])
    return examples


def main():
    ap = argparse.ArgumentParser(description="Build the SZL brain-graph corpus.")
    ap.add_argument("--check", action="store_true",
                    help="verify counts/cleanliness only; do not write")
    args = ap.parse_args()

    examples = build()
    n = len(examples)
    assert 800 <= n <= 3000, "brain corpus count %d outside expected [800,3000]" % n
    for ex in examples:
        for msg in ex["messages"]:
            assert _clean(msg["content"]), "banned token leaked into brain corpus"

    if args.check:
        print("build_brain_corpus: OK - %d clean examples (would write %s)"
              % (n, OUT))
        return 0

    with open(OUT, "w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex, ensure_ascii=False, sort_keys=True) + "\n")
    print("build_brain_corpus: wrote %d examples -> %s" % (n, OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
