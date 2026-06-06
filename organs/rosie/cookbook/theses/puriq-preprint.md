# PURIQ Preprint

**SHA-256:** `897df3b30274e21e7dd58140960239119bcdf8498c27d764e9b01bc35f1e8a95`  
**Pages:** 8 · **Bytes:** 480154  
**Note:** 12-organ governance preprint. 18 open conjecture formulas (SORRY_PURIQ_OPEN).  

Source: szl-holdings monorepo · Apache-2.0 · ingested for Rosie runtime cookbook by Yachay.

---

PURIQ: A Master Formula for Agentic AI
under Provable Provenance
Stephen P. Lutar Jr.
SZL Holdings
ORCID 0009-0001-0110-4173
Concept DOI: 10.5281/zenodo.19944926
June 1, 2026
ABSTRACT
We introduce PURIQ (Quechua puriq, “the one who
acts”), a single master formula that turns a governed
language-model substrate into a provably-provenanced
agent. PURIQ selects an action by maximizing the prod-
uct of four factors: a positive-homogeneous, boundedΛ
aggregator; the canonical 13-axisyuyay_v3 conjunctive
gate (replay hashbacf5443...); an exponential penalty
over ten HUKLLA halt-tripwires; and a Khipu Merkle-
DAG receipt product that is nonzero only when the ac-
tion’s provenance chain verifies. We give the formula’s
derivation, four governance invariants, and a Lean 4 for-
malization of the Khipu DAG soundness theorem estab-
lishing that a well-formed, signature-verifying receipt log
is a unique, append-only, tamper-evident record. We tab-
ulate 23 “organ” sub-formulas, each built as[primary
mathematical primitive]×[Doctrine v11 organ structure],
mechanized against Mathlib (749 declarations, 14 unique
axioms, 163 sorry obligations). PURIQ is positioned as
a court-admissible agentic governance layer: every act
emits an authenticatable receipt in the sense of Federal
Rules of Evidence 901/902. We relate the design to the
open-model leaders, to fielded command-and-control and
air-defense doctrine (Anduril Lattice, Iron Dome), and to
business-reporting standards (IBCS).
1. INTRODUCTION
Autonomous agents built on large language models in-
creasingly take consequential actions, yet the dominant
assurance mechanisms are probabilistic monitors and post-
hoc evaluations that cannotprove that a given action was
admissible or that its record is tamper-evident. We argue
that an agentic system intended for high-stakes or court-
relevant use must satisfy three properties simultaneously:
(i) anon-compensatory admission gatewhose verdict is a
deterministic, pre-registered function of measurable axes;
(ii) halt tripwiresthat fire on the derivative of risk, not
merely its level; and (iii) anappend-only, authenticatable
provenance ledgerfor every act.
PURIQ packages these into one selection rule. It is the
agentic-action layer ofDoctrine v12, which extends the
formally verified Doctrine v11 substrate of the Ouroboros
line of work [18]. This paper is the canonical, standalone
citation for the formula; it is independent of the companion
thesis but cites it for the underlyingΛ-uniqueness result,
which remains an open conjecture (Conjecture 1) rather
than a theorem.
Threat model. We assume a powerful but not omnipo-
tent adversary who may (i) supply adversarial contextx
designed to coax the model into an inadmissible action,
(ii) attempt to forge or replay a provenance receipt, and
(iii) attempt to tamper with the historical ledger after the
fact. We donot assume the adversary can break SHA-256
second-preimage resistance or produce existential signa-
ture forgeries (EUF-CMA); these are the standard cryp-
tographic assumptions on which the soundness theorem
of §7 rests, and we make them explicit rather than hid-
ing them. Under this model PURIQ guarantees that no
gate-failing or unprovenanced action is ever selected, and
that any post-hoc tampering with an admitted action’s
record is detectable. The adversary isnot prevented from
proposing bad actions — only from having themselected
and recorded as admissible.
Design principles. Three principles separate PURIQ
from soft guardrail stacks.First, non-compensation: ad-
missibility is a logical conjunction, not a weighted sum, so
no surplus on one axis can purchase a deficit on another —
the canonical failure mode that the refutation of the Bible-
code “equidistant letter sequence” claim [22,48] illustrates,
where post-hoc parameter freedom manufactures spurious
significance. Second, pre-registration: every floor, weight,
and tripwire threshold is frozen and the verdict stream
re-hashes to a fixed replay hash that is enforced in contin-
uous integration, so the gate cannot be silently retuned
to admit a desired action.Third, provenance as a hard
factor: the receipt product multiplies the score, so a single
unverifiable link zeroes the entire selection — provenance
is a precondition for action, not an audit afterthought.
1
Contributions. (1) The PURIQ master formula and
its four invariants (§3–§4). (2) A Lean 4 model and sound-
ness theorem for the Khipu Merkle-DAG ledger, with the
combinatorial spine proven and the cryptographic core
reduced to standard SHA-256 / EUF-CMA assumptions
(§7). (3) A catalogue of 23 organ sub-formulas with prove-
nance to primary mathematical sources (§8). (4) A public
13-axis label dataset and a replay-hashed gate (§5).
2. DOCTRINE V11 BACKGROUND
Doctrine v11 fixes the governance substrate that PURIQ
acts upon. Its LOCKED parameters, cited verbatim,
are: the Lean corpus of749 declarations, 14 unique
axioms, and 163 sorry obligations (112 baseline +
51 Putnam) against Mathlib v4.13.0 [7,43]; the13-axis
yuyay_v3 gate with canonical replay hashbacf54434f1
a3bf2d758b27a62d5fd580ca4c8d3b180693573eeebcaea
631fc5; the spine axiomsA2 = IsHomogeneousand
A4 = IsBounded; an honest supply-chain posture of
SLSA L1[34]; and theΛ-uniqueness statement carried
as Conjecture 1, not a theorem. These numbers are not
aspirational: they are the audited state of the substrate
and are preserved unchanged by the present work, which
is purely additive.
The substrate’s organs include YUYAY (the 13-
axis gate), HUKLLA (ten halt tripwires T01–T10),
YAWAR/Khipu(the append-only Merkle-DAG ledger),
SENTRA (an inline immune layer), and theΛ spine (a
weighted geometric-mean aggregator). PURIQ adds an
{decide, act, reflect} interface to each organ.
Why these numbers are LOCKED.A formally ver-
ified governance claim is only as strong as its accounting
of unproven steps. We therefore publish the exact triple
—declarations, axioms, andsorries— rather than a head-
line “fully verified” figure. The 14 axioms are the irre-
ducible trust base: they include the two spine axioms (A2,
A4), the cryptographic assumptions (collision-freedom and
EUF-CMA), and a small number of Mathlib-style classical-
analysis facts. The 163 sorry obligations are open lemmas,
each named and tracked; 112 are the original substrate
baseline and 51 arise from a Putnam-style stress corpus
added during auditing. Publishing the sorries is afeature:
it converts “trust us” into a checkable to-do list, and it is
the discipline that lets a third party reproduce the corpus
state with a verification script. The present work isstrictly
additive: it introduces new theorems and new sorry-tagged
obligations (SORRY_PURIQ_OPEN[24..27]) but modifies
none of the 749/14/163 baseline and addsno new axiom.
Naming. The organ names are Quechua, reflecting the
Andeankhipu knotted-cordrecord-keepingsystemthatmo-
tivates the ledger metaphor:yuyay (memory/judgment),
huk’lla(as one / unified halt),yawar (blood, the circulat-
ing record),kallpa (energy/effort), andpuriq (the one who
walks or acts). The naming is not decorative: a khipu is
an append-only, position-encoded, tamper-evident physi-
cal ledger, which is exactly the data structure the Khipu
organ formalizes.
3. THE PURIQ MASTER FORMULA
Definition 1(PURIQ selection rule). Given a contextx
at timet and a bounded action spaceA,
P (x,t ) = arg max
a∈A
[
Λ(x)·Yuyay13(a)·
e−βHUKLLA(a)·
∏
i
Khipui(a)
]
.
(1)
The factors are:
• Λ(x) ∈[0, 1] — the spine aggregator, positive-
homogeneous (A2) and bounded (A4), a weighted
geometric mean [1,14,18].
• Yuyay13(a)∈{0}∪[θ,1] — the 13-axis conjunctive
gate score; 0 if any axis is below its floor.
• e−βHUKLLA(a) — exponential penalty in the tripwire
violation count, withβ >0.
• ∏
i Khipui(a)∈{0, 1}— the product of receipt verifi-
cations; 0 unless the action’s entire provenance chain
verifies.
Derivation. Equation (1) is themaximum-a-posteriori
action under a factorized admissibility model in which
the four organs contribute independent multiplicative evi-
dence. Taking logarithms turns the rule into a sum of an
aggregator utility, a gate log-indicator, a linear tripwire
penalty, and a chain log-indicator:
logP-score(a) = log Λ + log Yuyay13(a)
−βHUKLLA(a) + ∑
i log Khipui(a).
(2)
Because Yuyay13 and ∏
i Khipui are{0,...}-valued indi-
cators, any gate failure or any unverified receipt sends the
score to−∞, so thearg maxcannot select an inadmissible
or unprovenanced action — the gate and ledger are hard
constraints, not soft weights. The geometric-mean form of
Λ guarantees non-compensation among its own inputs [1].
Why a product and not a sum. A weighted sum
of the four factors would be compensatory: a very high
aggregator score could numerically offset a gate failure,
admitting an inadmissible action. Theproductform makes
each factor a multiplicative veto. This is the same alge-
braic choice that distinguishes a geometric mean from an
arithmetic mean: the geometric mean of a vector with
any zero coordinate is zero, which is precisely the non-
compensatory behavior we require [14]. Aczél’s functional-
equation characterization [1] shows that, under the natu-
ral axioms of associativity, homogeneity, and continuity,
2
the quasi-arithmetic mean that is simultaneously homo-
geneous and bounded is the weighted geometric mean —
which is why the spineΛ takes that form and not another.
Choice ofβ. The tripwire terme−βvinterpolates be-
tween a soft penalty (smallβ) and a hard veto (largeβ).
In deploymentβis set large enough that a single tripwire
firing (v≥1) drivese−βvbelow the smallest representable
admissible score, making HUKLLA effectively a fourth
hard factor while retaining a smooth, differentiable surro-
gate for analysis and for ranking amongadmissible actions.
The smoothness is what lets us state Invariant I1 as a
clean limit (β→∞) rather than a case split.
Worked micro-example. Suppose an actiona scores
Λ = 0 .88, passes twelve axes at≥0.93 but scores 0.91
on the sacred axismoralGrounding (floor 0.95), fires no
tripwire, and has a fully verifying receipt chain. Despite a
strong aggregator and a verifying ledger,Yuyay13(a) = 0
because one sacred floor is violated, so the entire PURIQ
score is 0 and a is rejected. No amount of excellence
elsewhere recovers it. This single example is the empirical
content of §9(b).
4. THE FOUR INV ARIANTS
We state the four properties PURIQ is designed to guar-
antee; each is mechanized or explicitly conjectured in the
Lean suite.
Proposition 1(I1: Halting safety). For any action with
a positive tripwire countv >0, the penaltye−βv→0 as
β→∞; hence for largeβno tripwire-violating action is
selected.
Proof sketch. Fix v >0. Then−βv→−∞as β→∞,
and exp(·) is continuous withlimu→−∞eu = 0 (Mathlib
Real.tendsto_exp_atBot). Composing the two limits
gives e−βv→0. Any competing admissible action with
v = 0 keeps its penalty ate0 = 1, so forβabove a finite
threshold the violating action’s score is strictly dominated
and is never thearg max. Mechanized aspenalty_halts;
the limit step is axiom-free over Mathlib.□
Proposition 2(I2: Λ-monotonicity). Λ is monotone and
positive-homogeneous (A2) and bounded (A4); improving
any input weakly improves the aggregate, and the aggregate
never exceeds its cap. (Carried from Doctrine v11; A2/A4
stated as IsHomogeneous / IsBounded.)
Proposition 3 (I3: Provenance necessity) .∏
i Khipui(a) = 1 requires every receipt link to ver-
ify against the canonical SHA-256 hash and signature; a
single broken link zeroes the product and rejects the action
(§7).
Proof sketch.Each Khipui(a)∈{0, 1}is the Boolean “link
i verifies” lifted to{0, 1}. A finite product of{0, 1}values
equals 1 iff every factor equals1 (an elementary fact; in
Lean, List.prod_eq_one over a Boolean image). Hence
one failing link forces the product to0, which forces the
PURIQ score to0 by Eq.(1). The verification predicate
per link is exactly the inclusion checkverifyInclusion
whose soundness is Theorem 1.□
Proposition 4(I4: Bekenstein boundedness ofA).|A|
is bounded by the minimum of a holographic cap [5,41,42]
and a Kolmogorov description-length cap [19]; mechanized
as bekenstein_card_le.
Remark. I4 is the reason thearg max in Eq.(1) is well-
defined: a maximum over afinite set always exists. The
physical caps are not invoked literally but as a finiteness
argument — any action representable in a bounded de-
scription length within a bounded resource budget lives in
a finite set, so the optimizer terminates and the selection
is total. This connects the formula’s mathematical well-
posedness to a resource-realistic deployment assumption
rather than an idealized infinite action space.
5. THE 13-AXIS YUYAY GATE
The gate verdict is the conjunction Pass(x) ⇔⋀13
i=1(xi≥fi), with twosacred axes (moralGrounding,
measurabilityHonesty; floor 0.95), seven structural
axes ( empiricalGrounding, logicalConsistency,
sourceTransparency, reproducibility,
licenseHygiene,scopeDiscipline,claimCalibration;
floor 0.90), and fourintrospectionaxes (evalAwareness,
deceptionKeywords, conflictingDirectives,
reversalDirective) cross-linked to HUKLLA trip-
wires T03/T04/T09/T10. The gate is non-compensatory:
no excess on one axis buys back a deficit on another.
The verdict stream re-hashes to the fixed replay hash
bacf5443..., frozen in CI as a regression gate. This is
the anti-p-hacking discipline whose canonical negative
control is the refutation of the equidistant-letter-sequence
claim [22,48]: weights and floors arepre-registeredand
cannot be tuned post hoc. A public 500-example label
set (400 train / 100 eval) accompanies this paper as
the dataset SZLHOLDINGS/yuyay-v3-axis-labels-v1
(CC-BY-4.0).
Table 1 lists all thirteen axes with their tier, numeric
floor, and any HUKLLA cross-link. The twosacred axes
carry the highest floor (0.95) because a violation of moral
grounding or measurability honesty is treated as categori-
cally disqualifying. The sevenstructural axes (floor 0.90)
encode the engineering hygiene of a claim — evidence,
consistency, source transparency, reproducibility, license
cleanliness, scope discipline, and calibration. The fourin-
trospectionaxes (gate≥0.90) probe adversarial self-report
and each feed a specific tripwire, so a low introspection
score not only contributes to a gate failure but can also
arm a HUKLLA halt.
3
Table 1: The 13 canonical yuyay_v3 axes, by tier,
floor, and HUKLLA link. Conjunctive AND gate; non-
compensatory.
Axis Tier Floor HUKLLA
moralGrounding sacred 0.95 –
measurabilityHonesty sacred 0.95 –
empiricalGrounding structural 0.90 –
logicalConsistency structural 0.90 –
sourceTransparency structural 0.90 –
reproducibility structural 0.90 –
licenseHygiene structural 0.90 –
scopeDiscipline structural 0.90 –
claimCalibration structural 0.90 –
evalAwareness introspection 0.90 T03
deceptionKeywords introspection 0.90 T04
conflictingDirectives introspection 0.90 T09
reversalDirective introspection 0.90 T10
6. HUKLLA TRIPWIRE SYSTEM
HUKLLA is a bank of ten halt tripwiresT01–T10. Follow-
ing Newton’s fluxions [29], a tripwire fires on thevelocity
of risk:Tk fires iff d
dtriskk(t)> vmax or riskk(t)> Lmax,
giving early-warning halts before a level crossing. The ad-
versarial introspection axes feed T03 (eval-awareness), T04
(deception), T09 (conflicting directives), and T10 (priority
reversal). The control posture is the minimax strategy of
a finite zero-sum game [40,47] between the agent and an
adversarial environment, and the no-universal-halt-decider
limit [45] is respected by usingsound fuel-boundedtermi-
nation rather than assuming a decider. The doctrine of
layered, fast-reacting interception is analogous to fielded
short-range air defense [36] and to AI-mediated command
and control [2], cited as engineering precedents for “fire
on derivative, halt early.”
7. KHIPU DAG SOUNDNESS
The Khipu ledger is an append-only Merkle-DAG of re-
ceipts. We model it in Lean 4 following the Merkle hash-
tree construction [23,24], SHA-256 [27], and one-way-
function signatures [21], with event ordering in the sense
of [20] and an append-only discipline reminiscent of [26].
Definition 2 (Khipu receipt and DAG). A receipt is
⟨hash∈ByteVec 32, parents, payload, sig⟩. A KhipuDAG
is a topo-sorted list of receipts. It isWellFormed iff
every parent hash exists, the list is topologically sorted
(parents strictly precede children, hence acyclic), and there
is a unique parentless root.
Theorem 1(Khipu DAG soundness). Let a Khipu DAG
beWellFormed, with all signatures verifying, all self-hashes
equal to the canonical hash of the signed body, and the
canonical hash collision-free over the DAG’s preimage
universe. Then the DAG is (1)append-only: any future
insert preserves all current receipts; (2) aunique record:
equal hashes imply equal receipts; and (3)tamper-evident:
altering any included receipt’s signed body changes its
canonical hash.
Lean status. (1) is fully proven (khipu_append_only,
khipu_insertMany_length); (3) is fully proven from
collision-freedom and canonical hashing; (2) is reduced to
SHA-256 second-preimage resistance and discharged mod-
ulo the obligation taggedSORRY_PURIQ_OPEN[25]. Two
companion results, khipu_inclusion_proof_correct
(verify(R,π,H) = true ⇔ R ∈dag) and
khipu_append_only, formalize inclusion-proof correct-
ness and the no-delete guarantee. The cycle-
freedom and unique-topological-order lemmas are tagged
SORRY_PURIQ_OPEN[24],[26],[27]. These are net-new
obligations; the Doctrine v11 baseline (749/14/163) is
untouched and no new axiom is introduced. The Merkle
height boundh≤⌈logBN⌉is already axiom- and sorry-
free in the substrate.
Lean model. The ledger is formalized in the
namespace Puriq.Khipu as a nested module that
reuses the substrate’s existing Merkle-DAG build
(Lutar.DPI.MerkleDAGBuild) and summation invari-
ant (Lutar.Khipu.SummationInvariant). A receipt
is a structure over ByteVec32 hashes; a KhipuDAG
is a List of receipts with a WellFormed predicate
bundling three facts: parent-existence, topological
order ( parents strictly precede children), and
a unique parentless root. The append operation is
insert; bulk append isinsertMany. The fully proven
combinatorial lemmas areinsert_superset (append pre-
serves membership, via List.mem_append_left),
insert_length and khipu_insertMany_length
(length accounting), insert_mem, khipu_append_only,
khipu_root_no_parents, andverifyInclusion_sound.
These typecheck under Lean 4 v4.13.0 with exit code0
for the core-only fragment.
What is proven vs. assumed. We separate three
layers explicitly. (i)Combinatorial spine— append-only
preservation, length monotonicity, root uniqueness, and
inclusion-proof soundness — isproven from first principles
with no new axiom. (ii)Cryptographic core— unique-
ness (equal hash⇒equal receipt) and tamper-evidence —
is reduced to SHA-256 second-preimage resistance [27]
and EUF-CMA signature unforgeability [21]; tamper-
evidence is fully dischargedgiven collision-freedom, while
the collision-freedom premise itself is carried as the named
obligation SORRY_PURIQ_OPEN[25]. (iii) Structural con-
jectures — global acyclicity from pairwise hash-link or-
dering and unique topological order — are sorry-tagged
as [24], [26], [27]. We deliberately donot axiomatize
these away: an honest sorry is preferable to a false axiom,
and the four new obligations are net-new and tracked
rather than folded into the baseline.
4
Proof sketch of append-only (1). Let D be Well-
Formed and letD′= insert(r,D ) for a fresh receiptr
whose parents already exist inD. insert is defined to
place r after all its parents, preserving the underlying list
order ofD as a prefix-respecting sublist. Membership is
monotone under list append (List.mem_append_left), so
everys∈D satisfiess∈D′; no existing receipt is moved
relative to its parents, so the topological-order predicate
is preserved. Iterating giveskhipu_insertMany_length:
the length grows by exactly the number of inserted re-
ceipts and the original prefix is untouched. Hence the
ledger is append-only.□
Court-admissibility. An append-only, signature-
chained, hash-authenticated receipt log is precisely the
artifact that Federal Rules of Evidence 901/902 [46]
contemplate for authentication, and that SLSA [34],
in-toto [44], Sigstore [28], and DSSE [38] operationalize
for software provenance. PURIQ’s honest posture is
SLSA L1 with placeholders where CI signing is pending.
8. THE 23 ORGAN SUB-FORMULAS
Each organ formula is [primitive]×[organ]. Table 2
lists all 23 with their primary source and Lean status
(PROVED / SKELETON = sorry-tagged obligation /
CONJ = axiomatized conjecture).
Construction discipline. Each organ is built by the
same template: take a primary mathematical primi-
tive with a canonical citation and multiply it against
the structure of a Doctrine v11 organ. This is not a
metaphor — in each case the primitive supplies the al-
gebraic shape of the sub-formula and the organ supplies
its domain semantics. F3, for example, uses Noether’s
theorem [31]: a continuous symmetry of the receipt-graph
rewrite yields a conserved quantity (the summation in-
variant ofLutar.Khipu.SummationInvariant), which is
why F3 is PROVED rather than skeletal. F6 instanti-
ates Newton’s fluxions [29] as the risk-velocity tripwire
of §6. F23 uses the holographic bound [5,41,42] to cap
the action-space cardinality, supplying the finiteness that
makes thearg max well-defined (Invariant I4).
Honesty of the status column. Of the 23 organs,
the proven ones (P) carry a kernel-checked Lean proof;
skeletons (S) have a stated theorem with a named sorry
obligation; conjecture-axioms (C) —F13, F14, F22— are
the few places where a result isassumed via one of the
14 substrate axioms rather than proven, and they are
counted in that axiom budget rather than hidden. We
report the mix rather than rounding up to “all proven”
precisely because the value of a formal-methods claim is
in the accounting, not the headline.
9. EV ALUATION
We evaluate three claims.(a) Replay determinism:
re-evaluating theyuyay_v3 corpus reproduces the fixed re-
play hash, checked in CI.(b) Gate non-compensation:
on the 500-example label set, every single-axis sub-floor
example is rejected regardless of the other twelve scores
(279/500 FAIL, balanced 18–23 across all axes), confirming
the conjunctive property empirically.(c) Ledger sound-
ness: the proven fragment of Theorem 1 (append-only,
tamper-evidence) is kernel-checked against Lean 4 v4.13.0;
the cryptographic core is reduced to SHA-256/EUF-CMA
and sorry-tagged, not hidden. The Lean corpus state
(749/14/163) is reproduced by a verification script over
the substrate repository.
Table 3 summarizes the label-set composition and the
soundness accounting. The 500 examples are generated
deterministically from seed0xBACF5443 and split 400/100
train/eval; the gate verdict yields 221 PASS and 279 FAIL,
with FAIL causes balanced 18–23 examples across each
of the thirteen axes so that no single axis dominates the
negative set. The content hash of the published artifact
is bab22758c9dd78a54fb4210ca493941787db0010e6420
e94cfa84019d7e483b5.
Reproducibility. The replay hash is recomputed in CI
on every commit; a mismatch fails the build, which is the
mechanism that enforces pre-registration. The dataset,
its build script, and the Lean module are published so
that the PASS/FAIL counts and the corpus triple can be
regenerated independently. We claim reproducibility of
the published state, not of an idealized fully proven system
— the open obligations are part of what is reproduced.
10. RELATED WORK
Open and frontier models.PURIQ is model-agnostic
and routes over the open-weight leaders — Llama [25],
Qwen [35], DeepSeek [8], Mixtral [17] — and is compatible
withthefrontierclosedmodels[3,13,33]; thegatesits above
the model, so the choice of reasoning backend does not
affect admissibility.Guardrails. NeMo Guardrails [32]
and constitutional methods [4] provide soft, probabilistic
constraints; PURIQ differs by making the gate a hard,
pre-registered, replay-hashed function and by attaching a
tamper-evident ledger.Provenance and supply chain.
SLSA [34], in-toto [44], Sigstore [28], and DSSE [38] se-
cure build artifacts; PURIQ applies the same authenticity
discipline to agent actions. Fielded autonomy and
reporting standards. Command-and-control [2] and
air-defense [36] doctrine motivate derivative-triggered, lay-
ered halting; IBCS [16] motivates standardized, auditable
reporting of the verdict stream.Regulation. The design
targets the documentation and risk-management expecta-
tions of the EU AI Act [10] and the NIST AI RMF [30].
5
Table 2: The 23 PURIQ organ sub-formulas (F1–F23). Status: P=proven, S=skeleton (sorry-tagged), C=conjecture-
axiom.
# Formula Primitive (primary source) Organ St.
F1 Euler–Khipu DAG identity χ=2 Euler char. [9] Khipu P/S
F2 Egyptian–Kallpa allocation Egyptian fractions Kallpa S
F3 Noether–Khipu conservation Noether 1918 [31] Khipu P
F4 Gauss–Yuyay aggregation Gaussian/CLT Yuyay S
F5 Euler–Lagrange agency least action [9] A S
F6 Newton risk-velocity tripwire fluxions [29] HUKLLA S
F7 Inverse-square/ ζ provenance Riemann ζ [37] Khipu S
F8 Newton-parsimony pick Principia Rule 1/4 [29] HUKLLA S
F9 Sulba–Yuyay mass conservation area-preserving maps Yuyay P
F10 Baudh¯ ayana orthogonality
√
2 Heron iteration Λ-spine P
F11 Frustum A-shrink Moscow Papyrus A P
F12 CRT–HUKLLA schedule Gauss CRT [12] HUKLLA S
F13 Gauss–Bonnet spine curvature Gauss–Bonnet [6] Λ-spine C
F14 Ramanujan A-partition bound Hardy–Ramanujan [15] A C
F15 Grothendieck organ functor category theory organs P
F16 von Neumann–HUKLLA minimax minimax [40,47] HUKLLA S
F17 Shannon–Kallpa capacity channel capacity [39] Kallpa S
F18 Kolmogorov A-description cap Kolmogorov [19] A S
F19 Turing-fuel halting safety halting problem [45] core P/S
F20 Schrödinger action superposition wavefunction A P
F21 Dirac-commit projection bra–ket measurement Khipu P
F22 Feynman–Puriq path integral path integral [11] A C
F23 Bekenstein A-cap holography [5,41,42] A S
Table 3: Evaluation summary. Dataset
SZLHOLDINGS/yuyay-v3-axis-labels-v1; Lean cor-
pus state preserved.
Quantity Value
Total labelled examples 500
train / eval split 400 / 100
Gate verdict PASS / FAIL 221 / 279
FAIL examples per axis (balanced) 18–23
Generation seed 0xBACF5443
Replay hash (prefix) bacf5443...
Lean declarations (LOCKED) 749
Lean unique axioms (LOCKED) 14
Lean sorry obligations (LOCKED) 163
New PURIQ obligations (additive) 4 ( [24]–[27])
New axioms introduced 0
Proven Khipu lemmas 7
11. LIMITATIONS AND OPEN PROB-
LEMS
We state the limitations plainly.(L1) Λ-uniqueness is a
conjecture. The claim that the homogeneous, bounded
aggregator is uniquely the weighted geometric mean is
carried as Conjecture 1, not a theorem; the Aczél char-
acterization [1] gives strong support but the full Lean
proof is open.(L2) Cryptographic premises are as-
sumed, not proven.Uniqueness and tamper-evidence
rest on SHA-256 second-preimage resistance [27] and
EUF-CMA unforgeability [21]; these are standard but
unproven assumptions, and a quantum adversary would
weaken the hash margin.(L3) Four open Lean obliga-
tions. SORRY_PURIQ_OPEN[24–27]—collision-freedom,
global acyclicity, and unique topological order— remain
to be discharged; until then the soundness theorem holds
modulo these named lemmas.(L4) Supply-chain pos-
ture is SLSA L1.CI signing of releases is pending; the
provenance discipline is designed but not yet at L2/L3.
(L5) Gate scores are model-produced.PURIQ guar-
antees that a low axis score blocks an action, but the
fidelity of the 13 axis scores themselves depends on the
scoring model; the published label set is a step toward
calibrating and auditing those scores, not a proof of their
correctness. None of these limitations is hidden by an
axiom or a rounding of the corpus numbers.
12. CONCLUSION
PURIQ reduces “can this agent act, and can we prove what
it did” to a singlearg maxover a product of an aggregator,
a hard pre-registered gate, an exponential tripwire penalty,
and a verifying receipt chain. The combinatorial core of its
ledger soundness is mechanized in Lean; the cryptographic
core is reduced to standard assumptions and honestly
sorry-tagged; the Λ uniqueness it relies upon remains
Conjecture 1. The formula is offered as the canonical
citation for the agentic layer of Doctrine v12.
6
ACKNOWLEDGMENTS
Author: Stephen P. Lutar Jr. (Yachay). Co-authored-by:
Perplexity Computer Agent. Released under CC-BY-4.0;
concept DOI10.5281/zenodo.19944926.
REFERENCES
[1] János Aczél.Lectures on Functional Equations and
Their Applications. Academic Press, 1966. Theorem
5.1 (multivariate Cauchy equation), cited by the open
uniqueness step.
[2] Anduril Industries. Lattice: An AI-powered com-
mand and control platform. Anduril technical
overview, 2024.
[3] Anthropic. The claude 3 model family: Opus, sonnet,
haiku. Anthropic Model Card, 2024.
[4] Anthropic. Claude’s new constitution, 2026.
[5] Jacob D. Bekenstein. Universal upper bound on the
entropy-to-energyratioforboundedsystems. Physical
Review D, 23(2):287–298, 1981.
[6] Pierre Ossian Bonnet. Mémoire sur la théorie générale
des surfaces. Journal de l’École Polytechnique, 19:1–
146, 1848.
[7] Leonardo de Moura and Sebastian Ullrich. The Lean
4 theorem prover and programming language. In
Automated Deduction – CADE 28, pages 625–635,
2021.
[8] DeepSeek-AI. DeepSeek-V3 technical report.
arXiv:2412.19437, 2024.
[9] Leonhard Euler. Introductio in analysin infinitorum.
Marcum-Michaelem Bousquet, 1748.
[10] European Parliament and Council. Regulation (EU)
2024/1689 laying down harmonised rules on artificial
intelligence (AI act).Official Journal of the European
Union, 2024.
[11] Richard P. Feynman. Space-time approach to non-
relativistic quantum mechanics.Reviews of Modern
Physics, 20:367–387, 1948.
[12] Carl Friedrich Gauss. Disquisitiones Arithmeticae.
Gerhard Fleischer, 1801.
[13] Gemini Team, Google. Gemini: A family of highly
capable multimodal models. arXiv:2312.11805, 2023.
[14] G. H. Hardy, J. E. Littlewood, and G. Pólya.Inequal-
ities. Cambridge University Press, 1934.
[15] G. H. Hardy and S. Ramanujan. Asymptotic formulae
in combinatory analysis.Proc. London Math. Soc.,
s2-17:75–115, 1918.
[16] Hichert, Rolf and Faisst, Jürgen. International busi-
ness communication standards (IBCS) version 1.2.
Technical report, IBCS Association, 2022.
[17] Albert Q. Jiang et al. Mixtral of experts.
arXiv:2401.04088, 2024.
[18] Stephen P. Lutar Jr. Unifiedlambda proposal:
reconciling three divergent definitions of the lu-
tar invariant, 2026. szl-holdings/lutar-lean, Lu-
tar/UnifiedLambda.lean (PROPOSAL); Concept
DOI 10.5281/zenodo.19944926.
[19] Andrei N. Kolmogorov. Three approaches to the
quantitative definition of information.Problems of
Information Transmission, 1(1):1–7, 1965.
[20] Leslie Lamport. Time, clocks, and the ordering of
events in a distributed system.Communications of
the ACM, 21(7):558–565, 1978.
[21] Leslie Lamport. Constructing digital signatures from
a one-way function.SRI International Technical Re-
port CSL-98, 1979.
[22] Brendan McKay, Dror Bar-Natan, Maya Bar-Hillel,
and Gil Kalai. Solving the bible code puzzle.Statis-
tical Science, 14(2):150–173, 1999.
[23] Ralph C. Merkle.Secrecy, Authentication, and Public
Key Systems. PhD thesis, Stanford University, 1979.
[24] Ralph C. Merkle. A digital signature based on a
conventional encryption function. In Advances in
Cryptology — CRYPTO ’87, volume 293 ofLNCS,
pages 369–378, 1988.
[25] Meta AI. The llama 3 herd of models.
arXiv:2407.21783, 2024.
[26] Satoshi Nakamoto. Bitcoin: A peer-to-peer electronic
cash system. 2008.
[27] National Institute of Standards and Technology. Se-
cure hash standard (SHS). Technical Report FIPS
PUB 180-4, U.S. Department of Commerce, 2015.
[28] Zachary Newman et al. Sigstore: Software signing
for everybody. ACM CCS 2022, 2022.
[29] Isaac Newton.Philosophiæ Naturalis Principia Math-
ematica. Royal Society, 1687.
[30] NIST. Artificial intelligence risk management frame-
work (AI RMF 1.0). Technical Report NIST AI 100-1,
NIST, 2023.
[31] Emmy Noether. Invariante variationsprobleme.
Nachr. König. Gesell. Wiss. Göttingen, Math.-Phys.
Kl., pages 235–257, 1918.
[32] NVIDIA. NeMo guardrails: A toolkit for controllable
LLM applications, 2024.
7
[33] OpenAI. GPT-4 technical report. arXiv:2303.08774,
2023.
[34] OpenSSF. SLSA: Supply-chain levels for software
artifacts, v1.0, 2023.
[35] Qwen Team. Qwen2.5 technical report.
arXiv:2412.15115, 2024.
[36] Rafael Advanced Defense Systems. Iron dome: De-
fense system against short-range artillery rockets.
Rafael system doctrine overview, 2012.
[37] Bernhard Riemann. über die anzahl der primzahlen
unter einer gegebenen grösse.Monatsber. Berliner
Akad., 1859.
[38] Secure Systems Lab. Dead simple signing envelope
(DSSE), 2021.
[39] Claude E. Shannon. A mathematical theory of com-
munication. Bell System Technical Journal, 27:379–
423, 623–656, 1948.
[40] Maurice Sion. On general minimax theorems.Pacific
Journal of Mathematics, 8(1):171–176, 1958.
[41] Leonard Susskind. The world as a hologram.Journal
of Mathematical Physics, 36:6377–6396, 1995.
[42] Gerard ’t Hooft. Dimensional reduction in quantum
gravity. arXiv preprint gr-qc/9310026, 1993.
[43] The mathlib Community. The lean mathematical
library. Proc. 9th ACM SIGPLAN Int. Conf. on
Certified Programs and Proofs (CPP), pages 367–381,
2020.
[44] Santiago Torres-Arias et al. in-toto: Providing farm-
to-table guarantees for bits and bytes. USENIX Se-
curity 2019, 2019.
[45] Alan M. Turing. On computable numbers, with an ap-
plication to the entscheidungsproblem.Proc. London
Math. Soc., s2-42:230–265, 1936.
[46] U.S. Courts. Federal rules of evidence (rule 901, 902):
Authentication and identification, 2025.
[47] John von Neumann. Zur theorie der
gesellschaftsspiele. Mathematische Annalen ,
100:295–320, 1928.
[48] Doron Witztum, Eliyahu Rips, and Yoav Rosenberg.
Equidistant letter sequences in the book of genesis.
Statistical Science, 9(3):429–438, 1994.
8