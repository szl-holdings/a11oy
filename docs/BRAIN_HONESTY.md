<!--
SPDX-License-Identifier: Apache-2.0
© 2026 Lutar, Stephen P. Jr. — SZL Holdings · ORCID 0009-0001-0110-4173
Doctrine v11 LOCKED · Λ = Conjecture 1
-->

# The Brain's Honesty & Governance Surfaces

*A guide for technical-diligence and investor readers. Every claim here is drawn
verbatim from the modules' own docstrings and `/info` endpoints on `main`; nothing is
invented. Where a surface is MODELED rather than MEASURED, this document says so.*

## Thesis

The a11oy brain turns the estate's knowledge graph into a queryable retriever
(`szl_brain_api.py`: hippoRAG personalized-PageRank local retrieval ⊕ graphRAG-community
global retrieval). The honesty surfaces documented here exist so that the brain **answers
when it is grounded, abstains honestly when it is not, traces its sources, and flags its
own contradictions** — rather than answering anyway and hoping the reader cannot tell the
difference.

Each surface is deterministic and explainable: it reuses the *same* honest retrieval the
brain already runs, invents no nodes, harvests nothing, and reports every component of its
score separately so a number can never hide a weak part. None of these surfaces advances
any detection, fusion, effector, targeting, or cueing capability — they are honesty and
observability over the estate's own graph, and nothing more.

### Doctrine constraints that bound every surface (v11 LOCKED)

These are enforced by CI (the doctrine-grep gate) and the honest-status review, not
aspirational. This guide holds itself to the same rules it describes:

- **Λ is Conjecture 1, never a theorem.** Λ-uniqueness is advisory and gray; Khipu BFT
  safety is Conjecture 2. Neither is ever called proven.
- **The locked-proof count is 8** — `{F1, F4, F7, F11, F12, F18, F19, F22}` (the no-axiom
  theorem `locked_count_eight`). None of these surfaces adds to that set, touches a locked
  formula, or touches the kernel. The count is never inflated.
- **Trust ceiling 0.97**, never 100%. No surface reports a green 1.0 or a proof.
- **Honest labels, never upgraded.** MEASURED needs a real, fresh delta; unverified is
  SAMPLE; design-only is MODELED; future work is ROADMAP. A component that is not reachable
  is reported UNAVAILABLE, never fabricated.
- **Receipt-on-write, not on-read.** Every `GET` mints nothing. Only a `POST` receipt
  endpoint emits an **unsigned** SHA-256 content digest over the computed result — a plain
  content hash, never a fabricated signature.
- **A truthful BLOCKED/DEGRADED beats a fake green.** Every verdict below has an honest
  negative state that is never softened.

## Surface map

All routes are additive and registered before the SPA catch-all. `{ns}` is the API
namespace (e.g. `a11oy`), so a path shown as `/api/{ns}/v1/brain/ground` resolves to
`/api/a11oy/v1/brain/ground`. Every surface exposes the same three-verb shape:
`GET .../info` (static describe), `GET ...` (run the read), and a `POST` write endpoint
that mints the unsigned content-digest receipt.

| Surface | Honesty question it answers | Honest verdicts | Data label |
|---|---|---|---|
| **brainground** | Do I have enough grounding to answer, or should I abstain? | GROUNDED · WEAK-GROUNDING · INSUFFICIENT-GROUNDING | MODELED |
| **brainuncertainty** | How uncertain is the retrieval itself? | CONFIDENT · UNCERTAIN · HIGHLY-UNCERTAIN | MODELED |
| **brainconsensus** | How many independent nodes support this, and how broadly do they agree? | CORROBORATED · WEAK-CORROBORATION · SINGLE-SOURCE | MODELED |
| **braincontradict** | Do two grounded claims disagree? | NO-CONFLICT · POSSIBLE-CONFLICT · CONFLICT-FLAGGED | MODELED |
| **brainprovenance** | What graph nodes did this answer stand on? | TRACEABLE · PARTIAL-PROVENANCE · UNTRACEABLE | MODELED |
| **brainlineage** | How did this node enter the graph? | TRACED · PARTIAL-LINEAGE · UNKNOWN-ORIGIN | MODELED / STRUCTURAL-ONLY |
| **brainmemory** | Is this knowledge fresh, or should it be re-harvested? | FRESH · AGING · STALE | STRUCTURAL-ONLY (today) |
| **braingaps** | Where does the graph *not* have grounding? | per-topic COVERED · THIN · GAP; estate WELL-COVERED · PATCHY · SPARSE | MEASURED counts + MODELED verdict |
| **brainexplain** | Why did the brain retrieve what it did? | EXPLAINABLE · PARTIALLY-EXPLAINABLE · OPAQUE | MODELED |
| **brainqueryaudit** | Which queries were asked, and what verdict did each get? | CHAIN-INTACT · CHAIN-BROKEN | MODELED (hash-linked digests) |
| **brainhealth** | Can the brain be trusted for this query right now? | TRUSTWORTHY · DEGRADED · UNTRUSTWORTHY · INSUFFICIENT-SIGNAL | MODELED (rollup) |
| **brainwatch** | Is the honesty posture drifting over time? | STABLE · DRIFTING · DEGRADED · BASELINE-ONLY | MEASURED posture + MODELED drift |

## The surfaces in detail

### brainground — grounding confidence & honest abstention

**Question:** *Do I have enough grounding to answer this query, or should I abstain?*
It scores the real grounding subgraph the brain returns for a query and, when grounding is
weak, returns `INSUFFICIENT-GROUNDING` — the point being that the brain can truthfully say
"I don't have enough grounding" rather than answer anyway.

`grounding_confidence` (0..1) is combined from four components, each reported verbatim so
the number cannot hide a weak part: seed coverage, subgraph cohesion, salience mass, and
community consistency. Below a weak threshold, or below a minimum node count, the verdict
is `INSUFFICIENT-GROUNDING` and the surface states the brain *should abstain*; a middle band
is `WEAK-GROUNDING`; only a strong grounding is `GROUNDED`. High confidence is never claimed
when the components are weak.

- **Endpoints:** `GET /api/{ns}/v1/brain/ground/info` · `GET /api/{ns}/v1/brain/ground?q=&k=`
  · `POST /api/{ns}/v1/brain/ground/receipt`
- **Label:** MODELED — a deterministic graph statistic over the real grounding subgraph,
  never a MEASURED semantic truth.

### brainuncertainty — calibrated uncertainty on a retrieval

**Question:** *How uncertain is the retrieval itself?* (distinct from "how grounded"). It
reads the same honest ranked retrieval and derives three explainable components in [0,1]:
score dispersion (the gap between the top results), retrieval entropy over communities
(Shannon entropy of the score mass across communities), and rank stability (sensitivity of
the top-k ordering to a small change in k). These combine into one uncertainty in [0,1],
each component reported alongside. The verdict is never `CONFIDENT` when dispersion or
entropy is high — a flat or smeared retrieval can never be reported as confident.

- **Endpoints:** `GET /api/{ns}/v1/brain/uncertainty/info` ·
  `GET /api/{ns}/v1/brain/uncertainty?q=&k=` · `POST /api/{ns}/v1/brain/uncertainty/receipt`
- **Label:** MODELED — this is calibration honesty, not a probability guarantee. The number
  is a deterministic measure of the retrieval's own shape, *not* a claim that the answer is
  right with probability (1 − uncertainty).

### brainconsensus — corroboration of a grounding

**Question:** *How many independent nodes support this claim, and how broadly do they
agree?* A claim backed by many nodes spanning several distinct graph communities is
well-corroborated; a claim that collapses onto a single node or a single clique is
`SINGLE-SOURCE` and is flagged as such. It counts distinct supporting nodes, distinct
communities spanned, and support concentration (a Herfindahl / inverse-Simpson effective
community count). A `SINGLE-SOURCE-RISK` flag fires when support collapses to one node or
one community, and the verdict is never `CORROBORATED` while that flag is set.

- **Endpoints:** `GET /api/{ns}/v1/brain/consensus/info` ·
  `GET /api/{ns}/v1/brain/consensus?q=&k=` · `POST /api/{ns}/v1/brain/consensus/receipt`
- **Label:** MODELED — corroboration honesty, not a truth guarantee. Broad distribution is
  *not* a claim that a well-corroborated statement is therefore true; many nodes can share
  one upstream error.

### braincontradict — contradiction detector (present, never resolve)

**Question:** *Do two topically-related grounded claims disagree?* It retrieves the subgraph
for a query and looks for disagreeing pairs using only transparent, deterministic heuristics:
negation polarity, antonym opposition (a small published antonym table), and numeric
conflict. There is no black-box model in the detection path — every flag is explainable by
the exact tokens that triggered it, and confidence is an honest heuristic strength, never a
proof and never 1.0.

Critically, this surface **presents** conflicts and refuses to **resolve** them: every
reported conflict carries both sides verbatim, the reason it was flagged, and an explicit
`adjudication: human-required` with `resolution: null`. It never picks a winner and never
hides a side.

- **Endpoints:** `GET /api/{ns}/v1/brain/contradict/info` ·
  `GET /api/{ns}/v1/brain/contradict?q=&k=` · `POST /api/{ns}/v1/brain/contradict/receipt`
- **Label:** MODELED — a deterministic lexical/structural heuristic, never MEASURED.

### brainprovenance — per-answer source lineage

**Question:** *What did this answer stand on, and how well is each source labelled?* For a
retrieval it builds a deterministic provenance chain: the ordered supporting nodes (sorted
by ppr, then salience, then id), each carried with its verbatim node label, community, and a
contribution weight derived from the node's own ppr — never a fabricated importance. It then
computes an honest coverage statement (how much of the grounding is HARVESTED vs MODELED vs
UNAVAILABLE vs unlabelled, read verbatim). The verdict is never `TRACEABLE` while any node is
UNAVAILABLE or unlabelled.

This is source-lineage provenance only. It is explicitly *not* cryptographic attestation of
a model or artifact, and *not* SLSA / in-toto / Rekor build provenance.

- **Endpoints:** `GET /api/{ns}/v1/brain/provenance/info` ·
  `GET /api/{ns}/v1/brain/provenance?q=&k=` · `POST /api/{ns}/v1/brain/provenance/receipt`
- **Label:** MODELED (the surface's own derived view; underlying node labels are read
  verbatim and never upgraded).

### brainlineage — node-origin lineage

**Question:** *How did this node enter the graph — what is its origin metadata chain?*
Distinct from brainprovenance (which nodes supported an *answer*), this reads only the real
origin fields the graph builder attached to a node: strong (an explicit cited `source` /
`url`), structural (`derived_from`, `axis`, `org`, `organ`, `formula_id`, …), or weak
(label / community / kind only). An origin is `TRACED` only from a strong field;
`PARTIAL-LINEAGE` from a structural one; and `UNKNOWN-ORIGIN` when no origin field exists —
a source is never fabricated.

- **Endpoints:** `GET /api/{ns}/v1/brain/lineage/info` ·
  `GET /api/{ns}/v1/brain/lineage?q=&k=` (and per-node id lookup) ·
  `POST /api/{ns}/v1/brain/lineage/receipt`
- **Label:** MODELED when an explicit source exists; **STRUCTURAL-ONLY** when only a
  structural or unknown origin is inferable.

### brainmemory — memory freshness / decay honesty

**Question:** *Is this knowledge fresh, or should it be re-harvested?* A freshness score
wants a real recency signal (when was a node last harvested?). The module detects at request
time whether any real recency field is present. If one is, freshness is MODELED (recency ⊕
structural proxy). **In the estate today, harvested nodes carry no per-node timestamp**, so
the surface reports **STRUCTURAL-ONLY** freshness: a connectivity/salience proxy that flags
weakly-embedded nodes (low degree, low salience) as the ones most likely to be stale. It
does *not* claim to measure decay, and never invents a timestamp or a half-life. Each node
gets `FRESH` / `AGING` / `STALE`; stale nodes carry the honest note that they should be
re-harvested.

- **Endpoints:** `GET /api/{ns}/v1/brain/memory/info` ·
  `GET /api/{ns}/v1/brain/memory?k=` · `POST /api/{ns}/v1/brain/memory/receipt`
- **Label:** STRUCTURAL-ONLY today (MODELED only if a real recency field appears); never
  printed as MEASURED.

### braingaps — an honest map of what the brain does *not* know

**Question:** *Do we actually have grounding for this topic, or is it a gap?* Most surfaces
describe what the graph has; this one is the mirror image — it reports where the graph is
thin or empty: thin communities, island nodes (degree ≤ a small bound), and the share of
nodes carrying no real honesty label. The structural counts of the current read are MEASURED;
the per-topic and estate verdicts are a MODELED judgement over those counts. A topic with no
matched node is reported as `GAP`, never dressed up as `COVERED`; an estate posture at/above
the material sparsity threshold is `SPARSE`, never softened to `WELL-COVERED`.

- **Endpoints:** `GET /api/{ns}/v1/brain/gaps/info` ·
  `GET /api/{ns}/v1/brain/gaps?q=&k=` · `POST /api/{ns}/v1/brain/gaps/receipt`
- **Label:** MEASURED structural counts of this read + MODELED coverage verdict.

### brainexplain — why the brain retrieved what it did

**Question:** *Why did the brain retrieve these nodes for this query?* An explainability
trace over the real retrieval subgraph, turned into a deterministic plain-language account —
never an invented rationale. It reports which query terms matched which seed nodes, a
per-node rationale (rank, personalized PageRank, the `ppr_gain` lift above baseline salience,
and the honest basis for inclusion: direct-term-match / substring / vector-similarity /
graph-traversal / unattributed), the communities traversed, and each node's verbatim label.
Where a node has no attributable signal it is reported `unattributed` honestly. A result is
never softened from `OPAQUE`/`PARTIALLY-EXPLAINABLE` up to `EXPLAINABLE`.

- **Endpoints:** `GET /api/{ns}/v1/brain/explain/info` ·
  `GET /api/{ns}/v1/brain/explain?q=&k=` · `POST /api/{ns}/v1/brain/explain/receipt`
- **Label:** MODELED — a derived account over a real subgraph, never a MEASURED fact.

### brainqueryaudit — an append-only, hash-linked query ledger

**Question:** *Which queries were asked, and what honest verdict did each return?* A `POST`
appends one `{query, timestamp_utc, returned_verdict, grounding_label}` entry and mints an
unsigned SHA-256 receipt that chains to the prior entry's receipt (hash-linked and
tamper-evident — a mini transparency log). A `GET` recomputes the chain and reports honestly
whether it is `CHAIN-INTACT` or `CHAIN-BROKEN` (with the first broken index). Each receipt is
an unsigned content digest, not a signature or a cryptographic proof beyond the digest and
its hash-link. The ledger is **ephemeral (in-memory)**; it does not persist across process
restart and is labelled accordingly.

- **Endpoints:** `GET /api/{ns}/v1/brain/audit/info` · `GET /api/{ns}/v1/brain/audit` ·
  `POST /api/{ns}/v1/brain/audit/record`
- **Label:** MODELED (a derived audit view); receipts are UNSIGNED-CONTENT-DIGEST, hash-linked.

### brainhealth — a rollup of the brain's honesty signals

**Question:** *Can the brain be trusted for this query right now?* The brain's equivalent of
the estate honesty wall, scoped strictly to knowledge-graph honesty. It rolls up the
available sibling surfaces — grounding, freshness (brainmemory), provenance, contradiction,
uncertainty — each read verbatim with its own label. Every component is gathered through a
guarded import: one that is not present degrades to `UNAVAILABLE`, never fabricated. The
verdict is never `TRUSTWORTHY` if any available component abstains, is insufficient, is
conflict-flagged, or is stale-dominant; too few available components yields
`INSUFFICIENT-SIGNAL`.

- **Endpoints:** `GET /api/{ns}/v1/brain/health/info` ·
  `GET /api/{ns}/v1/brain/health?q=&k=` · `POST /api/{ns}/v1/brain/health/receipt`
- **Label:** MODELED (a rollup view; component labels are never upgraded).

### brainwatch — honesty-posture drift monitor

**Question:** *Is the graph's honesty posture drifting over time?* It computes a deterministic
posture snapshot of the live graph — label distribution, community posture, orphan share
(degree ≤ 1), and a Gini concentration of salience — all MEASURED from the current read. It
then compares the current snapshot against a *prior* snapshot supplied by the caller and
reports drift; that delta is MODELED (a derived comparison), and is only computed when a real
prior is supplied. With no prior it reports `BASELINE-ONLY` and fabricates no trend. A
material rise in the UNAVAILABLE or orphan share yields `DEGRADED`, which is never softened to
`STABLE`.

- **Endpoints:** `GET /api/{ns}/v1/brain/watch/info` · `GET /api/{ns}/v1/brain/watch` ·
  `POST /api/{ns}/v1/brain/watch/compare`
- **Label:** MEASURED posture numbers of this read + MODELED drift delta.

## How the surfaces compose

Read together, these twelve surfaces let a diligence reader ask a full honesty question and
get honest answers at each step: *Is there grounding?* (brainground) *How uncertain and how
corroborated is it?* (brainuncertainty, brainconsensus) *Does anything contradict it?*
(braincontradict) *What sources does it rest on, and where did they come from?*
(brainprovenance, brainlineage) *Is that knowledge fresh?* (brainmemory) *What does the graph
not cover?* (braingaps) *Why were these nodes chosen?* (brainexplain) *What was asked, and
can the record be trusted?* (brainqueryaudit) *Can the brain be trusted for this query?*
(brainhealth) *And is the whole posture drifting?* (brainwatch).

Each answer carries its honest label and an explicit negative verdict that is never softened.
That is the design intent: the brain answers when grounded, abstains honestly when not,
traces its sources, and flags its own contradictions — under Doctrine v11, with Λ as
Conjecture 1 (never a theorem), the locked-proof count held at 8, and a trust ceiling of
0.97.
