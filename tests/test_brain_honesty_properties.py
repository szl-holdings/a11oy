# SPDX-License-Identifier: Apache-2.0
# © 2026 Lutar, Stephen P. — SZL Holdings · ORCID 0009-0001-0110-4173 · Doctrine v11
# Signed-off-by: Stephen Lutar <stephenlutar2@gmail.com>
"""Cross-cutting honesty PROPERTY / adversarial tests for the brain surfaces.

Every brain surface (ground, uncertainty, consensus, contradict, provenance, lineage,
memory, gaps, explain, queryaudit, health, watch) is an honest DERIVED VIEW over the same
knowledge graph. Each surface guards its own invariants in its own suite; this file pins the
invariants they SHARE, so a regression in any one surface that quietly breaks the shared
honesty contract is caught here regardless of which surface introduced it.

Each surface import is GUARDED — a surface absent from this checkout SKIPS, never fails, so
this file is safe to run against any subset of main.

The shared invariants asserted for EACH available surface:

  1. HONEST LABEL, NEVER FABRICATED. A surface's own emitted top label is a derived-view
     label (MODELED / STRUCTURAL-ONLY), NEVER upgraded to MEASURED / PROVEN / VERIFIED — the
     four MODELED reasoning views carry no live exporter delta, so a MEASURED self-label would
     be a fabrication. Any published honest-label palette contains only recognised honest
     tokens, never an invented one.
  2. RECEIPT-ON-WRITE-NOT-ON-READ. A GET / describe / compute read mints NO receipt: no
     minted content digest (`content_sha256`) appears anywhere in a read body. Where a receipt
     IS minted (POST path) it is an UNSIGNED SHA-256 (64 hex, signed=False) — never a
     fabricated signature.
  3. UNIT-INTERVAL SCORES. Any confidence / score / trust value a surface reports is in [0,1],
     and the trust ceiling is < 1.0 (never a fabricated 100%).
  4. MONOTONIC HONESTY — no silent upgrade. When a surface's own components indicate
     abstain / insufficient / conflict, the surface must NOT return its 'good' verdict. An
     empty / thin / smeared input reads as the honest negative verdict, never softened.
  5. DETERMINISTIC RECEIPT. A surface's content receipt is reproducible for identical input.

Adversarial / negative label tokens in this file (MEASURED, PROVEN, VERIFIED, GUARANTEED,
CERTIFIED) are NEGATIVE examples only — they exist to prove a surface never emits them. The
doctrine stays intact: Λ is Conjecture 1, never a theorem, never green; Khipu BFT is
Conjecture 2, never proven; the locked count is exactly 8 and nothing here adds to it.
"""
import importlib
import re

import pytest

NS = "a11oy"

# The 12 brain honesty surfaces. Absent modules SKIP (guarded import), never fail.
SURFACE_MODULES = [
    "szl_brainground",
    "szl_brainuncertainty",
    "szl_brainconsensus",
    "szl_braincontradict",
    "szl_brainprovenance",
    "szl_brainlineage",
    "szl_brainmemory",
    "szl_braingaps",
    "szl_brainexplain",
    "szl_brainqueryaudit",
    "szl_brainhealth",
    "szl_brainwatch",
]

# The recognised honest-label palette (doctrine vocabulary). A surface may REFERENCE any of
# these; the property below only checks nothing OUTSIDE this palette sneaks into a published
# vocabulary — i.e. no invented / marketing label.
HONEST_VOCAB = {
    "LIVE", "MEASURED", "MODELED", "SAMPLE", "SIMULATED", "CACHED", "PROVEN",
    "CONJECTURE", "ROADMAP", "DEGRADED", "REPLAY", "STRUCTURAL-ONLY", "HONEST-STUB",
    "UNSIGNED-LOCAL", "UNAVAILABLE", "HARVESTED", "UNLABELLED", "INDETERMINATE",
}

# A surface's OWN emitted top label must be a derived-view label — never an upgrade that
# would fabricate a live measurement or a proof for a MODELED reasoning view.
DERIVED_VIEW_LABELS = {"MODELED", "STRUCTURAL-ONLY"}
FORBIDDEN_SELF_UPGRADES = {
    "MEASURED", "PROVEN", "PROVED", "VERIFIED", "GUARANTEED", "CERTIFIED",
    "THEOREM", "ABSOLUTE", "100%",
}

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

# key substrings whose numeric value must live in the unit interval [0,1].
_UNIT_KEY_HINTS = ("confidence", "uncertainty", "probability", "trust_ceiling",
                   "_share", "corroboration", "single_source_risk")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _load(modname):
    """Import a surface module or SKIP (never fail) when it is absent from this checkout."""
    return pytest.importorskip(modname)


def _info(mod):
    """The universal pure-read entry point every surface exposes."""
    if not hasattr(mod, "handle_info"):
        pytest.skip(f"{mod.__name__} exposes no handle_info")
    return mod.handle_info(NS)


def _walk(obj):
    """Yield every (key, value) pair and every scalar reached in a nested dict/list."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k, v
            yield from _walk(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            yield None, v
            yield from _walk(v)


def _receipt_fn(mod):
    """Resolve the surface's content-receipt minter (public or private), or None."""
    for name in ("content_receipt", "_content_receipt"):
        fn = getattr(mod, name, None)
        if callable(fn):
            return fn
    return None


# --------------------------------------------------------------------------- #
# 1. honest label — never fabricated, never upgraded
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("modname", SURFACE_MODULES)
def test_top_label_is_derived_view_never_upgraded(modname):
    """The surface's OWN emitted top label is a MODELED / STRUCTURAL-ONLY derived view — it is
    NEVER upgraded to MEASURED / PROVEN / VERIFIED (Λ is Conjecture 1, never a theorem, so a
    reasoning view never fabricates a measurement or a proof for itself)."""
    mod = _load(modname)
    info = _info(mod)
    label = info.get("label")
    assert isinstance(label, str) and label, f"{modname}: missing honest top label"
    assert label not in FORBIDDEN_SELF_UPGRADES, (
        f"{modname}: top label {label!r} is a fabricated upgrade")
    assert label in DERIVED_VIEW_LABELS, (
        f"{modname}: top label {label!r} not an honest derived-view label")


@pytest.mark.parametrize("modname", SURFACE_MODULES)
def test_published_vocabulary_holds_only_recognised_honest_tokens(modname):
    """If the surface publishes an honest-label palette, every entry is a RECOGNISED honest
    token — an invented / marketing label can never be smuggled into the vocabulary."""
    mod = _load(modname)
    info = _info(mod)
    published = set()
    palette = info.get("honest_labels_vocabulary")
    if isinstance(palette, (list, tuple)):
        published.update(str(x) for x in palette)
    hl = info.get("honest_labels")
    if isinstance(hl, dict) and isinstance(hl.get("labels"), (list, tuple)):
        published.update(str(x) for x in hl["labels"])
    if not published:
        pytest.skip(f"{modname} publishes no explicit label palette in info")
    unknown = published - HONEST_VOCAB
    assert not unknown, f"{modname}: unrecognised label token(s) in published palette: {unknown}"


# --------------------------------------------------------------------------- #
# 2. receipt-on-write-not-on-read
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("modname", SURFACE_MODULES)
def test_read_path_mints_no_content_digest(modname):
    """handle_info is a PURE READ — it must mint NO receipt: no content digest anywhere in the
    body. (A static receipt-POLICY description block is fine; it carries no `content_sha256`.)"""
    mod = _load(modname)
    info = _info(mod)
    for k, _v in _walk(info):
        assert k != "content_sha256", (
            f"{modname}: a GET read minted a content digest — receipt-on-write violated")


@pytest.mark.parametrize("modname", SURFACE_MODULES)
def test_any_signed_flag_is_false_and_algorithm_is_sha256(modname):
    """Anywhere a read body describes a receipt it declares signed=False (never a fabricated
    signature) and, if named, the sha256 algorithm."""
    mod = _load(modname)
    info = _info(mod)
    for k, v in _walk(info):
        if k == "signed":
            assert v is False, f"{modname}: read body claims a signed receipt"
        if k == "algorithm" and isinstance(v, str):
            assert v.lower() == "sha256", f"{modname}: unexpected receipt algorithm {v!r}"


# --------------------------------------------------------------------------- #
# 3. unit-interval scores + honest trust ceiling
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("modname", SURFACE_MODULES)
def test_reported_scores_are_in_unit_interval(modname):
    """Any confidence / score / trust / share value reported in a read body is in [0,1]."""
    mod = _load(modname)
    info = _info(mod)
    seen_any = False
    for k, v in _walk(info):
        if not isinstance(k, str) or isinstance(v, bool) or not isinstance(v, (int, float)):
            continue
        if any(h in k for h in _UNIT_KEY_HINTS):
            seen_any = True
            assert 0.0 <= float(v) <= 1.0, f"{modname}: {k}={v} outside [0,1]"
    # every surface at least publishes a doctrine trust ceiling; make the property non-vacuous.
    assert seen_any, f"{modname}: no unit-interval score found to check"


@pytest.mark.parametrize("modname", SURFACE_MODULES)
def test_trust_ceiling_is_honest_never_hundred_percent(modname):
    """The doctrine trust ceiling is < 1.0 — trust is never fabricated as a perfect 100%."""
    mod = _load(modname)
    info = _info(mod)
    doctrine = info.get("doctrine")
    if not isinstance(doctrine, dict) or "trust_ceiling" not in doctrine:
        pytest.skip(f"{modname} exposes no doctrine trust ceiling in info")
    ceiling = float(doctrine["trust_ceiling"])
    assert 0.0 < ceiling < 1.0, f"{modname}: trust ceiling {ceiling} not an honest fraction < 1"
    if "trust_100_percent" in doctrine:
        assert doctrine["trust_100_percent"] is False


@pytest.mark.parametrize("modname", SURFACE_MODULES)
def test_doctrine_locked_count_is_exactly_eight(modname):
    """Locked-proven count is exactly 8 and nothing is added; Λ = Conjecture 1, Khipu BFT =
    Conjecture 2 — never inflated, never called a theorem."""
    mod = _load(modname)
    info = _info(mod)
    doctrine = info.get("doctrine")
    if not isinstance(doctrine, dict) or "locked_proven" not in doctrine:
        pytest.skip(f"{modname} exposes no doctrine block in info")
    assert doctrine["locked_proven"] == 8, f"{modname}: locked count inflated"
    if "adds_to_locked_8" in doctrine:
        assert doctrine["adds_to_locked_8"] == 0
    if isinstance(doctrine.get("locked_set"), (list, tuple)):
        assert len(doctrine["locked_set"]) == 8
    if "lambda" in doctrine:
        assert str(doctrine["lambda"]).startswith("Conjecture 1")
    if "khipu_bft" in doctrine:
        assert str(doctrine["khipu_bft"]).startswith("Conjecture 2")


# --------------------------------------------------------------------------- #
# 5. deterministic, unsigned receipt (POST-path minter)
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("modname", SURFACE_MODULES)
def test_content_receipt_is_unsigned_sha256_and_deterministic(modname):
    """Where a surface mints a content receipt, it is a deterministic UNSIGNED SHA-256 (64 hex,
    signed=False) — identical input yields an identical digest, and no signature is fabricated."""
    mod = _load(modname)
    fn = _receipt_fn(mod)
    if fn is None:
        pytest.skip(f"{modname} exposes no content-receipt minter (chained / n/a)")
    # A representative synthetic payload; every surface's canonical serializer reads via
    # dict.get(...) with defaults, so this is honest cross-surface input, not a mock of logic.
    payload = {
        "query": "brain graph knowledge (Λ is Conjecture 1, never a theorem)",
        "verdict": "INSUFFICIENT",
        "label": "MODELED",
        "should_abstain": True,
        "grounding_confidence": 0.0,
    }
    r1 = fn(dict(payload))
    r2 = fn(dict(payload))
    assert isinstance(r1, dict), f"{modname}: receipt is not a dict"
    assert r1.get("algorithm") == "sha256", f"{modname}: receipt algorithm not sha256"
    assert r1.get("signed") is False, f"{modname}: receipt claims a fabricated signature"
    digest = r1.get("content_sha256")
    assert isinstance(digest, str) and _HEX64.match(digest), (
        f"{modname}: content_sha256 is not 64 lowercase hex")
    assert digest == r2.get("content_sha256"), f"{modname}: receipt digest is non-deterministic"
    if "mode" in r1:
        assert r1["mode"] == "UNSIGNED-CONTENT-DIGEST"


# --------------------------------------------------------------------------- #
# 4. monotonic honesty — a negative signal is NEVER upgraded to the 'good' verdict.
#    Realised as adversarial cases on the surfaces whose scoring is a pure, index-free
#    function of a supplied graph / retrieval. Each is guarded independently.
# --------------------------------------------------------------------------- #
class _EmptyIndex:
    """A retriever that honestly returns nothing — smeared / empty evidence."""
    def search(self, q, k):
        return []


def test_brainground_empty_grounding_abstains_never_grounded():
    bg = _load("szl_brainground")
    for attr in ("compute_confidence", "VERDICT_GROUNDED", "VERDICT_INSUFFICIENT"):
        if not hasattr(bg, attr):
            pytest.skip(f"szl_brainground missing {attr}")
    r = bg.compute_confidence({
        "query": "zxqw nonsense termz",
        "seeds": [],
        "grounding_subgraph": {"node_count": 0, "link_count": 0, "nodes": []},
    })
    assert 0.0 <= float(r.get("grounding_confidence", 0.0)) <= 1.0
    # empty grounding is INSUFFICIENT and abstains — never silently upgraded to GROUNDED.
    assert r["verdict"] != bg.VERDICT_GROUNDED
    assert r["verdict"] == bg.VERDICT_INSUFFICIENT
    assert r.get("should_abstain") is True


def test_brainuncertainty_no_results_is_highly_uncertain_never_confident():
    bu = _load("szl_brainuncertainty")
    for attr in ("assess", "CONFIDENT", "HIGHLY_UNCERTAIN"):
        if not hasattr(bu, attr):
            pytest.skip(f"szl_brainuncertainty missing {attr}")
    a = bu.assess(_EmptyIndex(), "sharp query", 5)
    assert a.get("results_retrieved") == 0
    assert 0.0 <= float(a.get("uncertainty", 1.0)) <= 1.0
    # no evidence is HIGHLY-UNCERTAIN + abstain — never upgraded to CONFIDENT.
    assert a["verdict"] != bu.CONFIDENT
    assert a["verdict"] == bu.HIGHLY_UNCERTAIN
    assert a.get("abstain_recommended") is True


def test_braingaps_thin_graph_is_sparse_never_well_covered():
    bg = _load("szl_braingaps")
    for attr in ("analyze", "WELL_COVERED", "SPARSE"):
        if not hasattr(bg, attr):
            pytest.skip(f"szl_braingaps missing {attr}")
    # A thin graph: three tiny communities, an island, an orphan. Node titles carry their
    # honest qualifier — Λ is Conjecture 1, never a theorem; Khipu BFT is Conjecture 2, never
    # proven — so the doctrine honesty grep never false-flags this fixture.
    nodes = [
        {"id": "lambda-core", "title": "Lambda kernel core", "label": "MODELED", "degree": 2},
        {"id": "lambda-note", "title": "Lambda is Conjecture 1, never a theorem",
         "label": "CONJECTURE", "degree": 1},
        {"id": "khipu-node", "title": "Khipu BFT is Conjecture 2, never proven",
         "label": "MODELED", "degree": 1},
        {"id": "islet", "title": "orphan islet", "label": "UNAVAILABLE", "degree": 0},
    ]
    community_of = {"lambda-core": "c0", "lambda-note": "c0", "khipu-node": "c1", "islet": "c2"}
    gmap = bg.analyze(nodes=nodes, link_count=2, community_of=community_of,
                      community_algo="fixture-cc", content_hash="deadbeef", ns=NS)
    # a thin, island-heavy graph reads SPARSE — never softened to WELL-COVERED.
    assert gmap["estate_verdict"] != bg.WELL_COVERED
    assert gmap["estate_verdict"] == bg.SPARSE
