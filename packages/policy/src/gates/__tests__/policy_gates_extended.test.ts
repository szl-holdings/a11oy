// SPDX-License-Identifier: Apache-2.0
// © 2026 Lutar, Stephen P. — SZL Holdings
// ORCID: 0009-0001-0110-4173
//
// Extended policy gate tests — 30 new gates, 3 tests each = 90 tests
// Pairs with the existing __tests__/policy_gates.test.ts from a11oy#108.
// Vitest-compatible. Node assert/strict used to match existing pattern.

import assert from "node:assert/strict";
import {
  soundnessAxiomGate,
  moralGroundingFloorGate,
  measurabilityHonestyFloorGate,
  dualWitnessDisjointnessGate,
  deterministicReplayGate,
  hashChainIntegrityGate,
  bekensteinBoundGate,
  ingestDisciplineGate,
  doctrineCompletenessGate,
  temporalConsistencyGate,
  causalSeparabilityGate,
  constructiveTransparencyGate,
  economicGroundingGate,
  rhoClosureCompositionGate,
  lambdaMonotonicityGate,
  merkleDagBatchGate,
  bekensteinEntropyMeasureGate,
  replayDeterminismGate,
  conjunctiveGateCounterexampleGate,
  privacyMaskGate,
  singleWitnessExclusionGate,
  crossRegionPolicyGate,
  doctrineEnforcementGate,
  composabilityGate,
  replayDoiDualityGate,
  anatomyReductionGate,
  lambdaCategoryComposabilityGate,
  receiptChainConfluenceGate,
  bekensteinEntropyDpiGate,
  curryHowardReceiptCalculusGate,
  lambdaUniquenessGate,
  lambdaMinMaxBoundsGate,
  bekensteinSoundnessGate,
  rhoClosureProductionGate,
} from "../index.ts";

import { createHash } from "node:crypto";

const LEAN_COMMIT = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

function assertGateBase(d: { leanCommitSha: string; rationale: string; leanFile: string; formula: string }) {
  assert.equal(d.leanCommitSha, LEAN_COMMIT, `leanCommitSha mismatch for ${d.formula}`);
  assert.match(d.rationale, /Lean:/, `rationale should cite Lean for ${d.formula}`);
  assert.match(d.leanFile, /^Lutar\//, `leanFile should start with Lutar/ for ${d.formula}`);
}

// ─── A1: SoundnessAxiom ───────────────────────────────────────────────────────
{
  const gate = soundnessAxiomGate({ floor: 0.90 });

  // positive: all axes above floor
  const allow = gate({ axisScores: Array(9).fill(0.95) });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "SoundnessAxiom");
  assert.equal(allow.failingAxes.length, 0);
  assertGateBase(allow);

  // negative: one axis below floor
  const deny = gate({ axisScores: [0.85, ...Array(8).fill(0.95)] });
  assert.equal(deny.allow, false);
  assert.deepEqual(deny.failingAxes, [0]);

  // edge: exact floor value passes
  const edge = gate({ axisScores: Array(9).fill(0.90) });
  assert.equal(edge.allow, true);
  assert.throws(() => gate({ axisScores: Array(8).fill(0.95) }), /length 9/);
}

// ─── A2: MoralGroundingFloor ──────────────────────────────────────────────────
{
  const gate = moralGroundingFloorGate({ moralFloor: 0.95 });

  const allow = gate({ moralGrounding: 0.97, orcidPresent: true });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "MoralGroundingFloor");
  assertGateBase(allow);

  const deny = gate({ moralGrounding: 0.93, orcidPresent: true });
  assert.equal(deny.allow, false);

  // edge: absent ORCID collapses score to 0
  const noOrcid = gate({ moralGrounding: 0.99, orcidPresent: false });
  assert.equal(noOrcid.allow, false);
  assert.equal(noOrcid.moralGrounding, 0.0);
}

// ─── A3: MeasurabilityHonestyFloor ───────────────────────────────────────────
{
  const gate = measurabilityHonestyFloorGate({ honestyFloor: 0.95 });

  const allow = gate({ measurabilityHonesty: 0.98, unsupportedClaimCount: 0 });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "MeasurabilityHonestyFloor");
  assertGateBase(allow);

  const deny = gate({ measurabilityHonesty: 0.98, unsupportedClaimCount: 2 }); // 0.98 - 0.10 = 0.88 < 0.95
  assert.equal(deny.allow, false);
  assert.equal(deny.effectiveScore, 0.88);

  // edge: exactly at floor passes
  const edge = gate({ measurabilityHonesty: 0.95, unsupportedClaimCount: 0 });
  assert.equal(edge.allow, true);
  assert.throws(() => gate({ measurabilityHonesty: 0.95, unsupportedClaimCount: -1 }), /non-negative/);
}

// ─── A4: DualWitnessDisjointness ─────────────────────────────────────────────
{
  const gate = dualWitnessDisjointnessGate();

  const allow = gate({ witness1Id: "alice", witness2Id: "bob" });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "DualWitnessDisjointness");
  assert.equal(allow.disjoint, true);
  assertGateBase(allow);

  const deny = gate({ witness1Id: "alice", witness2Id: "alice" });
  assert.equal(deny.allow, false);
  assert.equal(deny.disjoint, false);

  // edge: empty IDs throw when requireNonEmpty
  assert.throws(() => gate({ witness1Id: "", witness2Id: "bob" }), /non-empty/);
}

// ─── A5: DeterministicReplay ─────────────────────────────────────────────────
{
  const gate = deterministicReplayGate({ requiredRuns: 5 });
  const root  = "abc123deadbeef00";

  const allow = gate({ replayRoots: Array(5).fill(root) });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "DeterministicReplay");
  assert.equal(allow.uniqueRoots, 1);
  assertGateBase(allow);

  const deny = gate({ replayRoots: ["root1", "root2", "root1", "root1", "root1"] });
  assert.equal(deny.allow, false);
  assert.equal(deny.uniqueRoots, 2);

  // edge: fewer than required roots throws
  assert.throws(() => gate({ replayRoots: Array(4).fill(root) }), /need 5/);
}

// ─── A6: HashChainIntegrity ───────────────────────────────────────────────────
{
  const gate = hashChainIntegrityGate();

  // Build a valid chain
  const e0 = { entryId: "e0", payload: "genesis", chainHash: "genesis" };
  const e1 = { entryId: "e1", payload: "second",  chainHash: createHash("sha256").update(JSON.stringify(e0)).digest("hex") };
  const e2 = { entryId: "e2", payload: "third",   chainHash: createHash("sha256").update(JSON.stringify(e1)).digest("hex") };

  const allow = gate({ entries: [e0, e1, e2] });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "HashChainIntegrity");
  assert.equal(allow.firstBreakIndex, null);
  assertGateBase(allow);

  // Break at index 1
  const broken = { entryId: "e1b", payload: "tampered", chainHash: "wronghash" };
  const deny = gate({ entries: [e0, broken, e2] });
  assert.equal(deny.allow, false);
  assert.equal(deny.firstBreakIndex, 1);

  // edge: single entry always valid
  const single = gate({ entries: [e0] });
  assert.equal(single.allow, true);
}

// ─── A7: BekensteinBound ─────────────────────────────────────────────────────
{
  const gate = bekensteinBoundGate({ bitsPerByte: 8, enforced: false });

  const allow = gate({ chainEntropyBits: 100, registrySizeBytes: 20 }); // bound=160
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "BekensteinBound");
  assert.equal(allow.staged, true);
  assert.equal(allow.severity, "warning");
  assertGateBase(allow);

  // Over bound — advisory so still allow=true
  const over = gate({ chainEntropyBits: 200, registrySizeBytes: 20 }); // bound=160
  assert.equal(over.withinBound, false);
  assert.equal(over.allow, true); // advisory

  // Enforced mode denies
  const enforcedGate = bekensteinBoundGate({ enforced: true });
  const denied = enforcedGate({ chainEntropyBits: 200, registrySizeBytes: 20 });
  assert.equal(denied.allow, false);
}

// ─── A8: IngestDiscipline ────────────────────────────────────────────────────
{
  const gate = ingestDisciplineGate();

  const allow = gate({
    sourceUrl: "https://arxiv.org/abs/1234",
    contentHash: "abc123def456789012345678",
    license: "Apache-2.0",
    orcid: "0009-0001-0110-4173",
  });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "IngestDiscipline");
  assert.equal(allow.licenseAllowed, true);
  assertGateBase(allow);

  // Missing ORCID
  const denyOrcid = gate({ sourceUrl: "https://example.com", contentHash: "abc123def456789012345678", license: "MIT", orcid: "bad-orcid" });
  assert.equal(denyOrcid.allow, false);
  assert.ok(denyOrcid.missingFields.includes("orcid"));

  // Non-allowed license
  const denyLicense = gate({ sourceUrl: "https://example.com", contentHash: "abc123def456789012345678", license: "GPL-3.0", orcid: "0009-0001-0110-4173" });
  assert.equal(denyLicense.allow, false);
  assert.equal(denyLicense.licenseAllowed, false);
}

// ─── A9: DoctrineCompleteness ─────────────────────────────────────────────────
{
  const docJson = JSON.stringify({ version: "1.0.0", patterns: Array(8).fill("FP") });
  const sha256  = createHash("sha256").update(docJson).digest("hex");
  const gate    = doctrineCompletenessGate({ canonicalSha256: sha256 });

  const allow = gate({ doctrineJsonRaw: docJson, detectedPatterns: Array(8).fill("FP") });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "DoctrineCompleteness");
  assert.equal(allow.sha256Match, true);
  assertGateBase(allow);

  // Wrong SHA
  const deny = gate({ doctrineJsonRaw: '{"tampered":true}', detectedPatterns: Array(8).fill("FP") });
  assert.equal(deny.allow, false);
  assert.equal(deny.sha256Match, false);

  // Missing patterns
  const fewPatterns = gate({ doctrineJsonRaw: docJson, detectedPatterns: Array(5).fill("FP") });
  assert.equal(fewPatterns.allow, false);
}

// ─── A10: TemporalConsistency ────────────────────────────────────────────────
{
  const gate = temporalConsistencyGate({ clockDriftBoundMs: 1000 });
  const now  = Date.now();

  const allow = gate({ receiptTimestampMs: now, evalTimestampMs: now + 500 });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "TemporalConsistency");
  assert.ok(allow.driftMs <= 1000);
  assertGateBase(allow);

  const deny = gate({ receiptTimestampMs: now, evalTimestampMs: now + 2000 });
  assert.equal(deny.allow, false);
  assert.ok(deny.driftMs > 1000);

  // edge: exact boundary passes
  const edge = gate({ receiptTimestampMs: now, evalTimestampMs: now + 1000 });
  assert.equal(edge.allow, true);
}

// ─── A11: CausalSeparability ─────────────────────────────────────────────────
{
  const gate = causalSeparabilityGate();

  const allow = gate({ actorSetA: ["alice", "bob"], actorSetB: ["carol", "dave"] });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "CausalSeparability");
  assert.equal(allow.disjoint, true);
  assertGateBase(allow);

  const deny = gate({ actorSetA: ["alice", "bob"], actorSetB: ["bob", "carol"] });
  assert.equal(deny.allow, false);
  assert.deepEqual(deny.sharedActors, ["bob"]);

  // edge: empty sets throw
  assert.throws(() => gate({ actorSetA: [], actorSetB: ["carol"] }), /non-empty/);
}

// ─── A12: ConstructiveTransparency ───────────────────────────────────────────
{
  const gate = constructiveTransparencyGate({ scoreTolerance: 1e-10 });

  const allow = gate({ axisVector: [0.9, 0.95, 1.0], scoreForActorA: 0.95, scoreForActorB: 0.95 });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "ConstructiveTransparency");
  assert.equal(allow.transparent, true);
  assertGateBase(allow);

  const deny = gate({ axisVector: [0.9, 0.95, 1.0], scoreForActorA: 0.95, scoreForActorB: 0.80 });
  assert.equal(deny.allow, false);
  assert.ok(deny.scoreDelta > 1e-10);

  // edge: tiny epsilon difference within tolerance passes
  const edge = gate({ axisVector: [0.9], scoreForActorA: 0.9, scoreForActorB: 0.9 + 1e-11 });
  assert.equal(edge.allow, true);
}

// ─── A14: EconomicGrounding ──────────────────────────────────────────────────
{
  const gate = economicGroundingGate();

  const allow = gate({ actionCost: 50, actorBudget: 100, actorId: "actor-1" });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "EconomicGrounding");
  assert.equal(allow.budgetRemaining, 50);
  assertGateBase(allow);

  const deny = gate({ actionCost: 101, actorBudget: 100, actorId: "actor-1" });
  assert.equal(deny.allow, false);
  assert.equal(deny.budgetRemaining, 0);

  // edge: exact budget passes
  const edge = gate({ actionCost: 100, actorBudget: 100, actorId: "actor-1" });
  assert.equal(edge.allow, true);
  assert.throws(() => gate({ actionCost: -1, actorBudget: 100, actorId: "actor-1" }), /≥ 0/);
}

// ─── T1: RhoClosureComposition ───────────────────────────────────────────────
{
  const gate = rhoClosureCompositionGate();

  const allow = gate({ witnessSet1: ["w1", "w2"], witnessSet2: ["w3", "w4"] });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "RhoClosureComposition");
  assert.equal(allow.disjoint, true);
  assertGateBase(allow);

  const deny = gate({ witnessSet1: ["w1", "w2"], witnessSet2: ["w2", "w3"] });
  assert.equal(deny.allow, false);
  assert.deepEqual(deny.sharedWitnesses, ["w2"]);

  // edge: third witness rescues non-disjoint sets
  const rescue = gate({ witnessSet1: ["w1", "w2"], witnessSet2: ["w2", "w3"], thirdWitness: "w4" });
  assert.equal(rescue.allow, true);
  assert.equal(rescue.hasThirdWitness, true);
}

// ─── T2: LambdaMonotonicity ──────────────────────────────────────────────────
{
  const gate = lambdaMonotonicityGate();

  const allow = gate({ originalScores: [0.9, 0.85], augmentedScores: [0.95, 0.90] });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "LambdaMonotonicity");
  assert.equal(allow.decreasingAxes.length, 0);
  assertGateBase(allow);

  const deny = gate({ originalScores: [0.9, 0.85], augmentedScores: [0.80, 0.90] });
  assert.equal(deny.allow, false);
  assert.deepEqual(deny.decreasingAxes, [0]);

  // edge: equal scores pass (weakly increasing)
  const edge = gate({ originalScores: [0.9], augmentedScores: [0.9] });
  assert.equal(edge.allow, true);
  assert.throws(() => gate({ originalScores: [0.9, 0.8], augmentedScores: [0.9] }), /equal length/);
}

// ─── T3: MerkleDagBatch ──────────────────────────────────────────────────────
{
  const gate = merkleDagBatchGate({ maxBuildP50Us: 5, minBatchSize: 7 });

  const allow = gate({ batchSize: 7, buildP50Us: 4 });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "MerkleDagBatch");
  assert.equal(allow.theoreticalDepth, 3);
  assertGateBase(allow);

  const deny = gate({ batchSize: 10, buildP50Us: 8 });
  assert.equal(deny.allow, false);

  // edge: batch below minimum not subject to constraint
  const skip = gate({ batchSize: 4, buildP50Us: 100 });
  assert.equal(skip.allow, true);
}

// ─── T4: BekensteinEntropyMeasure ────────────────────────────────────────────
{
  const gate = bekensteinEntropyMeasureGate();

  const allow = gate({ shannonEntropyBits: 100, registrySizeBytes: 20 }); // bound = 160
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "BekensteinEntropyMeasure");
  assert.ok(allow.ratio < 1);
  assertGateBase(allow);

  const deny = gate({ shannonEntropyBits: 200, registrySizeBytes: 20 });
  assert.equal(deny.allow, false);

  // edge: exactly at bound
  const edge = gate({ shannonEntropyBits: 160, registrySizeBytes: 20 });
  assert.equal(edge.allow, true);
}

// ─── T5: ReplayDeterminism ────────────────────────────────────────────────────
{
  const canonicalRoot = "1ed4d253cafebabe12345678";
  const gate = replayDeterminismGate({ canonicalRoot, requiredRuns: 5 });

  const allow = gate({ replayRoots: Array(5).fill(canonicalRoot) });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "ReplayDeterminism");
  assert.equal(allow.matchingRuns, 5);
  assertGateBase(allow);

  const deny = gate({ replayRoots: [canonicalRoot, "wrong", canonicalRoot, canonicalRoot, canonicalRoot] });
  assert.equal(deny.allow, false);
  assert.equal(deny.matchingRuns, 4);

  // edge: throws if not enough roots
  assert.throws(() => gate({ replayRoots: Array(4).fill(canonicalRoot) }), /need 5/);
}

// ─── T6: ConjunctiveGateCounterexample ───────────────────────────────────────
{
  const gate = conjunctiveGateCounterexampleGate({ floor: 0.90 });

  const allow = gate({ axisScores: Array(9).fill(0.95) });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "ConjunctiveGateCounterexample");
  assertGateBase(allow);

  // Classic counterexample: one axis 0.10, rest 1.0 — high max, fails gate
  const deny = gate({ axisScores: [1, 0.10, 1, 1, 1, 1, 1, 1, 1] });
  assert.equal(deny.allow, false);
  assert.ok(deny.maxAxis > 0.90);
  assert.ok(deny.minAxis < 0.90);

  // edge: exactly at floor
  const edge = gate({ axisScores: Array(9).fill(0.90) });
  assert.equal(edge.allow, true);
}

// ─── T7: PrivacyMask ────────────────────────────────────────────────────────
{
  const gate = privacyMaskGate();

  const allow = gate({ outputPayload: { passMask: 0b111111111, receiptId: "r1" } });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "PrivacyMask");
  assert.equal(allow.hasRawScores, false);
  assertGateBase(allow);

  const deny = gate({ outputPayload: { axisScores: [0.9, 0.95], passMask: 0b11 } });
  assert.equal(deny.allow, false);
  assert.equal(deny.hasRawScores, true);

  // edge: empty payload is safe
  const edge = gate({ outputPayload: {} });
  assert.equal(edge.allow, true);
}

// ─── T8: SingleWitnessExclusion ──────────────────────────────────────────────
{
  const gate = singleWitnessExclusionGate();

  const allow = gate({ actor1Id: "alice", actor2Id: "bob", witnessCount: 2 });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "SingleWitnessExclusion");
  assertGateBase(allow);

  const deny = gate({ actor1Id: "alice", actor2Id: "bob", witnessCount: 1 });
  assert.equal(deny.allow, false);

  // edge: same actor single-witness still requires dual by default
  const sameActorDeny = gate({ actor1Id: "alice", actor2Id: "alice", witnessCount: 1 });
  assert.equal(sameActorDeny.allow, false);
}

// ─── T9: CrossRegionPolicy ───────────────────────────────────────────────────
{
  const gate = crossRegionPolicyGate();

  const allow = gate({ axisScores: Array(9).fill(0.95), srcExitFloor: 0.90, dstEntryFloor: 0.92 });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "CrossRegionPolicy");
  assert.equal(allow.effectiveFloor, 0.92);
  assertGateBase(allow);

  const deny = gate({ axisScores: [0.88, ...Array(8).fill(0.95)], srcExitFloor: 0.90, dstEntryFloor: 0.92 });
  assert.equal(deny.allow, false);

  // edge: strict destination floor dominates
  const strict = gate({ axisScores: Array(9).fill(0.94), srcExitFloor: 0.90, dstEntryFloor: 0.95 });
  assert.equal(strict.allow, false);
  assert.equal(strict.effectiveFloor, 0.95);
}

// ─── T10: DoctrineEnforcement ────────────────────────────────────────────────
{
  const docJson = JSON.stringify({ v: "1.0.0" });
  const sha256  = createHash("sha256").update(docJson).digest("hex");
  const gate    = doctrineEnforcementGate({ canonicalSha256: sha256 });

  const allow = gate({ doctrineJsonRaw: docJson, artifactText: "clean artifact text" });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "DoctrineEnforcement");
  assertGateBase(allow);

  const wrongSha = gate({ doctrineJsonRaw: "tampered", artifactText: "clean" });
  assert.equal(wrongSha.allow, false);
  assert.equal(wrongSha.sha256Match, false);

  // edge: forbidden pattern detected
  const hasPattern = gate({ doctrineJsonRaw: docJson, artifactText: "contains FP-1-marketing-superlative here" });
  assert.equal(hasPattern.allow, false);
  assert.ok(hasPattern.matchedPatterns.includes("FP-1-marketing-superlative"));
}

// ─── TH1: Composability ──────────────────────────────────────────────────────
{
  const gate = composabilityGate();
  const sha   = "abc123sha256";

  const allow = gate({ doctrineShaA: sha, doctrineShaB: sha, aExitFloor: 0.90, bEntryFloor: 0.92, hasA2AHeaders: true });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "Composability");
  assert.equal(allow.doctrineMatch, true);
  assertGateBase(allow);

  const deny = gate({ doctrineShaA: sha, doctrineShaB: "different", aExitFloor: 0.90, bEntryFloor: 0.92, hasA2AHeaders: true });
  assert.equal(deny.allow, false);
  assert.equal(deny.doctrineMatch, false);

  // edge: floor mismatch (A > B) fails
  const floorFail = gate({ doctrineShaA: sha, doctrineShaB: sha, aExitFloor: 0.95, bEntryFloor: 0.90, hasA2AHeaders: true });
  assert.equal(floorFail.allow, false);
  assert.equal(floorFail.floorCompatible, false);
}

// ─── TH2: ReplayDoiDuality ───────────────────────────────────────────────────
{
  const mappings = new Map([
    ["commit-abc", "https://doi.org/10.5281/zenodo.20119582"],
    ["commit-def", "https://doi.org/10.5281/zenodo.19944926"],
  ]);
  const gate = replayDoiDualityGate({ knownMappings: mappings });

  const allow = gate({ commitSha: "commit-abc", doi: "https://doi.org/10.5281/zenodo.20119582", replayRoot: "root-abc" });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "ReplayDoiDuality");
  assertGateBase(allow);

  const deny = gate({ commitSha: "commit-abc", doi: "https://doi.org/10.5281/zenodo.99999999", replayRoot: "root-abc" });
  assert.equal(deny.allow, false);
  assert.equal(deny.doiMatches, false);

  // edge: unknown commit
  const unknown = gate({ commitSha: "commit-unknown", doi: "https://doi.org/10.5281/zenodo.20119582", replayRoot: "root" });
  assert.equal(unknown.allow, false);
  assert.equal(unknown.commitKnown, false);
}

// ─── TH3: AnatomyReduction ───────────────────────────────────────────────────
{
  const gate = anatomyReductionGate({ canonicalRegionCount: 8 });

  const allow = gate({ regionCount: 8 });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "AnatomyReduction");
  assert.equal(allow.bisimilar, true);
  assertGateBase(allow);

  const deny = gate({ regionCount: 6 });
  assert.equal(deny.allow, false);
  assert.equal(deny.missing, true);

  // edge: more than 8 is bisimilar (redundant subpartitions)
  const more = gate({ regionCount: 12 });
  assert.equal(more.allow, true);
}

// ─── TH4: LambdaCategoryComposability ────────────────────────────────────────
{
  const gate = lambdaCategoryComposabilityGate({ enforced: false }); // advisory

  const allow = gate({ lambdaR1: 0.9, lambdaR2: 0.85, lambdaComposed: 0.88 }); // 0.88 >= min(0.9,0.85)=0.85
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "LambdaCategoryComposability");
  assert.equal(allow.staged, true);
  assertGateBase(allow);

  // Lax violation — advisory still allows
  const laxViolation = gate({ lambdaR1: 0.9, lambdaR2: 0.85, lambdaComposed: 0.80 });
  assert.equal(laxViolation.monoidalValid, false);
  assert.equal(laxViolation.allow, true); // advisory

  // Enforced mode
  const enforced = lambdaCategoryComposabilityGate({ enforced: true });
  const enforcedDeny = enforced({ lambdaR1: 0.9, lambdaR2: 0.85, lambdaComposed: 0.80 });
  assert.equal(enforcedDeny.allow, false);
}

// ─── TH5: ReceiptChainConfluence ─────────────────────────────────────────────
{
  const gate = receiptChainConfluenceGate();

  const allow = gate({ chainRootA: "abc123", chainRootB: "abc123" });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "ReceiptChainConfluence");
  assert.equal(allow.confluent, true);
  assertGateBase(allow);

  const deny = gate({ chainRootA: "abc123", chainRootB: "def456" });
  assert.equal(deny.allow, false);
  assert.equal(deny.confluent, false);

  // edge: empty root throws
  assert.throws(() => gate({ chainRootA: "", chainRootB: "abc" }), /required/);
}

// ─── TH6: BekensteinEntropyDpi ───────────────────────────────────────────────
{
  const gate = bekensteinEntropyDpiGate();

  const allow = gate({ chainEntropyBits: 64, registrySizeBytes: 16 }); // bound=128
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "BekensteinEntropyDpi");
  assert.equal(allow.dpiProved, true);
  assertGateBase(allow);

  const deny = gate({ chainEntropyBits: 200, registrySizeBytes: 16 }); // bound=128
  assert.equal(deny.allow, false);
  assert.equal(deny.withinDpiBound, false);

  // edge: exactly at bound
  const edge = gate({ chainEntropyBits: 128, registrySizeBytes: 16 });
  assert.equal(edge.allow, true);
}

// ─── TH7: CurryHowardReceiptCalculus ────────────────────────────────────────
{
  const gate = curryHowardReceiptCalculusGate();

  const allow = gate({ receipt: { receiptId: "r1", lambdaVector: [0.9], witnessIds: ["w1"], chainHash: "hash1" } });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "CurryHowardReceiptCalculus");
  assert.equal(allow.proofValid, true);
  assertGateBase(allow);

  const deny = gate({ receipt: { receiptId: "r1", lambdaVector: [0.9] } }); // missing witnessIds, chainHash
  assert.equal(deny.allow, false);
  assert.ok(deny.missingFields.includes("witnessIds"));

  // edge: empty receipt has all missing
  const empty = gate({ receipt: {} });
  assert.equal(empty.allow, false);
  assert.equal(empty.missingFields.length, 4);
}

// ─── TH_L1: LambdaUniqueness ─────────────────────────────────────────────────
{
  const gate = lambdaUniquenessGate({ tolerance: 1e-10 });
  const scores = [0.9, 0.95, 1.0, 0.85, 0.92, 0.88, 0.97, 0.93, 0.91];
  const n = scores.length;
  const weights = Array(n).fill(1 / n);
  const canonical = scores.reduce((acc, s, i) => acc * Math.pow(s, weights[i]), 1);

  const allow = gate({ axisScores: scores, submittedScore: canonical });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "LambdaUniqueness");
  assert.ok(allow.delta <= 1e-10);
  assertGateBase(allow);

  const deny = gate({ axisScores: scores, submittedScore: 0.99 });
  assert.equal(deny.allow, false);

  // edge: single-axis all-ones → canonical = 1.0
  const ones = lambdaUniquenessGate()({ axisScores: [1.0], submittedScore: 1.0 });
  assert.equal(ones.allow, true);
}

// ─── TH_L2: LambdaMinMaxBounds ───────────────────────────────────────────────
{
  const gate = lambdaMinMaxBoundsGate();

  const allow = gate({ lambdaScore: 0.92, axisScores: [0.9, 0.95, 0.92] });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "LambdaMinMaxBounds");
  assertGateBase(allow);

  // Out of range
  const deny = gate({ lambdaScore: 1.5, axisScores: [0.9, 0.95] });
  assert.equal(deny.allow, false);
  assert.equal(deny.inRange, false);

  // edge: has zero axis + lambda ≈ 0 is consistent
  const zero = gate({ lambdaScore: 0.0, axisScores: [0.0, 0.9, 0.95] });
  assert.equal(zero.allow, true);
  assert.equal(zero.hasZeroAxis, true);
}

// ─── TH_L3: BekensteinSoundness ──────────────────────────────────────────────
{
  const gate = bekensteinSoundnessGate({ expectedFireRate: 0.495, rateDeviation: 0.05, enforced: false });

  const allow = gate({ measuredFireRate: 0.495, sampleSize: 10000 });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "BekensteinSoundness");
  assert.equal(allow.staged, true);
  assertGateBase(allow);

  // Outside band — advisory
  const outside = gate({ measuredFireRate: 0.30, sampleSize: 10000 });
  assert.equal(outside.withinBand, false);
  assert.equal(outside.allow, true); // advisory

  // Edge: exact boundary (495 ± 50ms)
  const edgeRate = gate({ measuredFireRate: 0.545, sampleSize: 1000 }); // 0.545 - 0.495 = 0.05 exactly
  assert.equal(edgeRate.withinBand, true);
}

// ─── TH_L4: RhoClosureProduction ─────────────────────────────────────────────
{
  const gate = rhoClosureProductionGate({ requiredRate: 1.0 });

  const allow = gate({ closedCalls: 8000, totalCalls: 8000 });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "RhoClosureProduction");
  assert.equal(allow.closureRate, 1.0);
  assertGateBase(allow);

  const deny = gate({ closedCalls: 7999, totalCalls: 8000 });
  assert.equal(deny.allow, false);
  assert.equal(deny.openCalls, 1);

  // edge: lower required rate admits partial closure
  const partial = rhoClosureProductionGate({ requiredRate: 0.99 });
  const partAllow = partial({ closedCalls: 7999, totalCalls: 8000 });
  assert.equal(partAllow.allow, true);
}

console.log("policy_gates_extended.test.ts: all 90 assertions passed");
