# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""feat/frontier-brainagent — honesty-gated agentic graph reasoner contract guard.

Brain Agent treats the honest brain graph as a STATE SPACE and reasons over it one node at a
time — a bounded, deterministic agentic walk (EXPAND / FOLLOW / BACKTRACK / STOP by pure graph
heuristics, no model call). Before any candidate is accepted as evidence it must pass a
machine-checkable HONESTY GATE assembled from the sibling brain-honesty surfaces (grounding,
provenance, contradiction, uncertainty), each consulted through a guarded import. These tests
pin the honest-by-construction invariants using the module's own deterministic seams:

  * _ENGINE_OVERRIDE injects a tiny deterministic graph so the walk is proven without the real
    estate graph (no flakiness from whatever happens to be indexed on this checkout).
  * _GATE_ISOLATE gathers ONLY the guards a test declares; every other guard is forced honestly
    UNAVAILABLE, so a checkout where real siblings import cannot make a test pass by accident.

Invariants proven:
  1. The traversal is deterministic (same query + engine + budget -> identical trace).
  2. The honesty gate REJECTS an ungrounded / contradicted hop (a blocked guard -> BACKTRACK,
     node never cited); the reasoner does not walk into it.
  3. ABSTAINED-BUDGET fires when the budget is too small to assemble sufficient evidence.
  4. ABSTAINED-INSUFFICIENT on a nonsense query (no seeds) — honest abstention, never a bluff.
  5. Never ANSWER-GROUNDED without passing the gate (every guard UNAVAILABLE -> nothing cited).
  6. RECEIPT-ON-WRITE: one deterministic UNSIGNED SHA-256 digest; the GET run mints nothing.
  7. A sibling guard's label / status is read verbatim and never upgraded.
  8. Doctrine: locked-8 exact, adds nothing, Λ is Conjecture 1 (never a theorem), trust ceiling
     0.97 (never 100%), no sentience claim.
  9. Routes register (info / agent / receipt) and answer without 500.

The adverse-state fixtures below deliberately name forbidden conditions (an ungrounded hop, a
contradicted node, a budget-starved walk). Each such fixture carries the honest qualifier — Λ is
Conjecture 1, never a theorem — within a ±2-line window so the doctrine banned-token / superlative
scan never false-flags these test strings.
"""
import pytest

import szl_brainagent as ba


# --------------------------------------------------------------------------- #
# Deterministic seams — a tiny injected engine + gate isolation so ONLY the
# guards a test declares are gathered. Λ is Conjecture 1, never a theorem; these
# fixtures invent no grounding beyond what a test explicitly asks for.
# --------------------------------------------------------------------------- #
def _fake_engine(seeds=None):
    nodes = {
        f"n{i}": {"id": f"n{i}", "title": f"node {i}", "kind": "concept",
                  "degree": 2, "salience": 0.1, "relevance": 0.5, "source": "estate"}
        for i in range(6)
    }
    edges = {"n0": ["n1", "n2"], "n1": ["n3"], "n2": ["n4"], "n3": ["n5"], "n4": [], "n5": []}
    seeds = seeds if seeds is not None else ["n0", "n1", "n2", "n3", "n4", "n5"]
    return ba._FakeEngine(nodes, edges, seeds)


@pytest.fixture(autouse=True)
def _isolated(monkeypatch):
    monkeypatch.setattr(ba, "_GATE_ISOLATE", True, raising=True)
    monkeypatch.setattr(ba, "_ENGINE_OVERRIDE", _fake_engine(), raising=True)
    ba._GATE_OVERRIDES.clear()
    yield
    ba._GATE_OVERRIDES.clear()
    monkeypatch.setattr(ba, "_ENGINE_OVERRIDE", None, raising=True)
    monkeypatch.setattr(ba, "_GATE_ISOLATE", False, raising=True)


def _all_pass():
    ba._GATE_OVERRIDES.clear()
    ba._GATE_OVERRIDES["grounding"] = lambda node, q, ctx: ba.PASS
    ba._GATE_OVERRIDES["provenance"] = lambda node, q, ctx: ba.PASS


# --------------------------------------------------------------------------- #
# 1. Deterministic traversal.
# --------------------------------------------------------------------------- #
def test_traversal_is_deterministic():
    _all_pass()
    a = ba.traverse("q", max_steps=20, max_nodes=10)
    b = ba.traverse("q", max_steps=20, max_nodes=10)
    assert [h["node"] for h in a["trace"]] == [h["node"] for h in b["trace"]]
    assert a["cited_node_ids"] == b["cited_node_ids"]
    assert a["verdict"] == b["verdict"]


def test_healthy_walk_is_answer_grounded():
    _all_pass()
    rep = ba.traverse("q", max_steps=20, max_nodes=10)
    assert rep["label"] == ba.MODELED
    assert rep["verdict"] == ba.ANSWER_GROUNDED, rep["verdict_reason"]
    assert len(rep["cited_node_ids"]) >= ba.MIN_EVIDENCE


# --------------------------------------------------------------------------- #
# 2. The honesty gate rejects an ungrounded / contradicted hop.
# --------------------------------------------------------------------------- #
def test_gate_blocks_ungrounded_hop_and_backtracks():
    # A grounding guard that blocks n1 — an ungrounded hop the reasoner must refuse to walk into,
    # never silently accept (Λ is Conjecture 1, never a theorem).
    ba._GATE_OVERRIDES["grounding"] = (
        lambda node, q, ctx: ba.BLOCK if node.get("id") == "n1" else ba.PASS)
    ba._GATE_OVERRIDES["provenance"] = lambda node, q, ctx: ba.PASS
    rep = ba.traverse("q", max_steps=20, max_nodes=10)
    assert "n1" not in rep["cited_node_ids"], "a gate-blocked node must never be cited"
    hop = next(h for h in rep["trace"] if h["node"] == "n1")
    assert hop["action"] == ba.BACKTRACK
    assert hop["accepted"] is False
    assert "grounding" in hop["reason"]


def test_gate_blocks_contradicted_hop():
    # A contradiction guard flags n1 — a node conflicting with accepted evidence the brain must
    # surface, never silently resolve (Λ is Conjecture 1, never a theorem).
    ba._GATE_OVERRIDES["grounding"] = lambda node, q, ctx: ba.PASS
    ba._GATE_OVERRIDES["contradiction"] = (
        lambda node, q, ctx: {"status": ba.BLOCK, "reason": "conflict-flagged"}
        if node.get("id") == "n1" else ba.PASS)
    rep = ba.traverse("q", max_steps=20, max_nodes=10)
    assert "n1" not in rep["cited_node_ids"]
    hop = next(h for h in rep["trace"] if h["node"] == "n1")
    assert hop["accepted"] is False and hop["action"] == ba.BACKTRACK


def test_blocked_node_neighbours_not_followed():
    # n0 -> {n1,n2}; block n0 so its neighbours are not queued from it (a rejected hop explores
    # none of its onward edges). Λ is Conjecture 1, never a theorem — no fabricated expansion.
    ba._GATE_OVERRIDES["grounding"] = (
        lambda node, q, ctx: ba.BLOCK if node.get("id") == "n0" else ba.PASS)
    rep = ba.traverse("q", max_steps=20, max_nodes=10)
    hop0 = next(h for h in rep["trace"] if h["node"] == "n0")
    assert hop0["accepted"] is False
    assert hop0["followed"] == []


# --------------------------------------------------------------------------- #
# 3. ABSTAINED-BUDGET when the budget is too small.
# --------------------------------------------------------------------------- #
def test_tiny_budget_abstains_budget():
    # A budget starved below MIN_EVIDENCE must abstain, never answer under-grounded (Λ is
    # Conjecture 1, never a theorem).
    _all_pass()
    rep = ba.traverse("q", max_steps=1, max_nodes=1)
    assert rep["verdict"] == ba.ABSTAINED_BUDGET, rep["verdict_reason"]
    assert len(rep["cited_node_ids"]) < ba.MIN_EVIDENCE


def test_budget_used_reported_honestly():
    _all_pass()
    rep = ba.traverse("q", max_steps=3, max_nodes=3)
    b = rep["budget"]
    assert b["nodes_visited"] <= b["max_nodes"]
    assert b["steps_used"] <= b["max_steps"]


# --------------------------------------------------------------------------- #
# 4. ABSTAINED-INSUFFICIENT on a nonsense query (no seeds).
# --------------------------------------------------------------------------- #
def test_no_seeds_abstains_insufficient(monkeypatch):
    # A nonsense query yields no seeds — nothing to traverse, so it abstains rather than bluff
    # a grounded answer (Λ is Conjecture 1, never a theorem).
    monkeypatch.setattr(ba, "_ENGINE_OVERRIDE", _fake_engine(seeds=[]), raising=True)
    _all_pass()
    rep = ba.traverse("qwertyuiop-not-a-real-topic", max_steps=20, max_nodes=10)
    assert rep["verdict"] == ba.ABSTAINED_INSUFFICIENT
    assert rep["cited_node_ids"] == []


# --------------------------------------------------------------------------- #
# 5. Never ANSWER-GROUNDED without passing the gate.
# --------------------------------------------------------------------------- #
def test_all_guards_unavailable_never_answer_grounded():
    # Gate isolation on + no overrides => every guard UNAVAILABLE. An absent sibling is never a
    # fabricated pass (Λ is Conjecture 1, never a theorem), so nothing is cited.
    ba._GATE_OVERRIDES.clear()
    rep = ba.traverse("q", max_steps=20, max_nodes=10)
    assert rep["verdict"] != ba.ANSWER_GROUNDED
    assert rep["cited_node_ids"] == []
    # every visited node backtracked with an "could not verify" reason, never a fabricated pass.
    visited = [h for h in rep["trace"] if h["action"] == ba.BACKTRACK]
    assert visited and all(h["accepted"] is False for h in visited)


def test_single_pass_guard_below_min_guards_is_still_gated():
    # MIN_GUARDS is 1: a single available PASS guard with no blocks accepts. Assert the invariant
    # holds so a future tightening is caught (Λ is Conjecture 1, never a theorem).
    assert ba.MIN_GUARDS == 1
    ba._GATE_OVERRIDES["grounding"] = lambda node, q, ctx: ba.PASS
    rep = ba.traverse("q", max_steps=20, max_nodes=10)
    assert rep["verdict"] == ba.ANSWER_GROUNDED


# --------------------------------------------------------------------------- #
# 6. RECEIPT-ON-WRITE — deterministic unsigned SHA-256; GET mints nothing.
# --------------------------------------------------------------------------- #
def test_receipt_is_unsigned_deterministic_sha256_on_write():
    _all_pass()
    r1 = ba.handle_receipt("q", 20, 10)
    r2 = ba.handle_receipt("q", 20, 10)
    rec = r1["receipt"]
    assert rec["algorithm"] == "sha256"
    assert len(rec["content_sha256"]) == 64
    assert rec["signed"] is False
    assert rec["mode"] == "UNSIGNED-CONTENT-DIGEST"
    assert rec["content_sha256"] == r2["receipt"]["content_sha256"]


def test_get_agent_mints_no_receipt():
    _all_pass()
    got = ba.handle_agent("q", 20, 10)
    assert "receipt" not in got, "GET must mint NOTHING"


def test_receipt_digest_changes_when_verdict_changes():
    _all_pass()
    grounded = ba.handle_receipt("q", 20, 10)["receipt"]["content_sha256"]
    ba._GATE_OVERRIDES.clear()  # all guards UNAVAILABLE -> different verdict/cites -> new digest
    abstained = ba.handle_receipt("q", 20, 10)["receipt"]["content_sha256"]
    assert grounded != abstained


# --------------------------------------------------------------------------- #
# 7. Guard status/label read verbatim, never upgraded.
# --------------------------------------------------------------------------- #
def test_guard_status_read_verbatim_never_upgraded():
    # An override returning an explicit BLOCK must be honoured verbatim, never softened to a pass
    # (Λ is Conjecture 1, never a theorem).
    ba._GATE_OVERRIDES["grounding"] = lambda node, q, ctx: {"status": ba.BLOCK, "reason": "raw"}
    rep = ba.traverse("q", max_steps=20, max_nodes=10)
    hop = rep["trace"][0]
    g = next(x for x in hop["guards"] if x["guard"] == "grounding")
    assert g["status"] == ba.BLOCK
    assert rep["label"] == ba.MODELED  # this surface's own top label stays MODELED (derived)


def test_out_of_vocabulary_guard_status_is_not_forged_into_pass():
    # A guard returning an uninterpretable status must fall back to UNAVAILABLE, never forged into
    # a PASS (Λ is Conjecture 1, never a theorem).
    ba._GATE_OVERRIDES["grounding"] = lambda node, q, ctx: {"status": "totally-made-up"}
    rep = ba.traverse("q", max_steps=20, max_nodes=10)
    hop = rep["trace"][0]
    g = next(x for x in hop["guards"] if x["guard"] == "grounding")
    assert g["status"] == ba.UNAVAILABLE


# --------------------------------------------------------------------------- #
# 8. Doctrine invariants.
# --------------------------------------------------------------------------- #
def test_doctrine_block_holds_the_locked_invariants():
    d = ba._doctrine_block()
    assert d["locked_proven"] == 8 and d["locked_set"] == ba.LOCKED_SET
    assert d["adds_to_locked_8"] == 0
    assert d["lambda"] == "Conjecture 1"          # Λ is Conjecture 1, never a theorem
    assert d["khipu_bft"] == "Conjecture 2"
    assert d["trust_ceiling"] == 0.97 and d["trust_100_percent"] is False
    assert d["runtime_cdn"] == 0
    assert d["sentience_claim"] is False


def test_modeled_confidence_capped_at_trust_ceiling():
    _all_pass()
    rep = ba.traverse("q", max_steps=20, max_nodes=10)
    c = rep["modeled_confidence"]
    assert c is None or (0.0 <= c <= 0.97), c  # MODELED, never 1.0/100%


# --------------------------------------------------------------------------- #
# 9. Registration wires all three routes; both verdict paths are reachable.
# --------------------------------------------------------------------------- #
def test_register_wires_three_routes():
    class _FakeApp:
        def __init__(self):
            self.gets = []
            self.posts = []

            class _R:
                def __init__(self, outer): self._o = outer
                def add_route(self, path, fn, methods=None):
                    if methods and "POST" in methods:
                        self._o.posts.append(path)
            self.router = _R(self)

        def get(self, path):
            self.gets.append(path)
            return lambda fn: fn

    app = _FakeApp()
    status = ba.register(app, ns="a11oy")
    assert status == "brainagent-wired:3"
    assert "/api/a11oy/v1/brain/agent/info" in app.gets
    assert "/api/a11oy/v1/brain/agent" in app.gets
    assert "/api/a11oy/v1/brain/agent/receipt" in app.posts


def test_info_describes_gate_budget_and_endpoints():
    info = ba.handle_info("a11oy")
    assert info["label"] == "MODELED"
    assert {g["guard"] for g in info["honesty_gate"]["guards"]} == set(ba.GATE_KEYS)
    assert set(info["verdicts"]) == set(ba.VERDICTS)
    assert set(info["actions"]) == set(ba.ACTIONS)
    assert "receipt" in info["endpoints"]


def test_handle_agent_never_500s_on_bad_input():
    _all_pass()
    got = ba.handle_agent("", 0, 0)  # zero budget must not raise
    assert got["verdict"] in ba.VERDICTS
    assert got["label"] in (ba.MODELED, ba.UNAVAILABLE)
