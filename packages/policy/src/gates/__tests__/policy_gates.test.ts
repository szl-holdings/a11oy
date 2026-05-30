import assert from "node:assert/strict";
import {
  adversarialRobustnessGate,
  emitFormulaGateReceipt,
  falsePositionGate,
  liuHuiPiGate,
  madhavaBoundGate,
  summationInvariantGate,
} from "../index.ts";
import { verifyReceipt } from "../../../../receipt-substrate/src/index.ts";

const leanCommit = "1dca00032dfc9aa8559cc6c2e4b63192fcf52371";

function assertLeanAnchor(decision: { leanCommitSha: string; rationale: string; leanFile: string }) {
  assert.equal(decision.leanCommitSha, leanCommit);
  assert.match(decision.rationale, /Lean:/);
  assert.match(decision.leanFile, /^Lutar\//);
}

{
  const gate = madhavaBoundGate({ threshold: 0.01 });
  const allow = gate({ x: 0.5, N: 5 });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "MadhavaBound");
  assert.ok(allow.remainderBound <= allow.threshold);
  assertLeanAnchor(allow);

  const deny = gate({ x: 1, N: 1 });
  assert.equal(deny.allow, false);
  assert.ok(deny.remainderBound > deny.threshold);
  assert.throws(() => gate({ x: 1.2, N: 2 }), /must be ≤ 1/);
  assert.throws(() => gate({ x: 0.5, N: 0 }), /N must be ≥ 1/);

  const receipt = emitFormulaGateReceipt(allow, {
    actorId: "did:szl:policy-test",
    invocationId: "policy-gate-madhava-demo",
    vertical: "a11oy",
    regime: "doctrine-v6",
    timestamp: new Date("2026-05-29T00:00:00.000Z"),
  });
  assert.equal(receipt.event_type, "A11OY_OPERATION");
  assert.equal(receipt.envelope.tool_name, "policy_gate.MadhavaBound");
  assert.equal(receipt.envelope.payload && typeof receipt.envelope.payload === "object", true);
  assert.equal(verifyReceipt(receipt).valid, true);
}

{
  const gate = falsePositionGate({ tolerance: 1e-10 });
  const allow = gate({ x1: 0, y1: 0, x2: 10, y2: 20, T: 6 });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "FalsePosition");
  assert.equal(allow.xStar, 3);
  assert.ok(allow.residual <= allow.tolerance);
  assertLeanAnchor(allow);

  assert.throws(() => gate({ x1: 1, y1: 0, x2: 1, y2: 2, T: 1 }), /x₁ = x₂/);
  assert.throws(() => gate({ x1: 0, y1: 2, x2: 1, y2: 2, T: 2 }), /y₁ = y₂/);
  assert.throws(() => gate({ x1: 0, y1: 0, x2: 1, y2: Number.NaN, T: 1 }), /must be finite/);
}

{
  const gate = liuHuiPiGate({ threshold: 0.01 });
  const allow = gate({ k: 5 });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "LiuHuiPi");
  assert.ok(allow.absError <= allow.threshold);
  assertLeanAnchor(allow);

  const deny = liuHuiPiGate({ threshold: 1e-12 })({ k: 5 });
  assert.equal(deny.allow, false);
  assert.throws(() => gate({ k: -1 }), /k must be in/);
}

{
  const gate = adversarialRobustnessGate({ maxEpsilon: 0.5 });
  const allow = gate({ lipschitz1: 1, lipschitz2: 2, delta: 0.1 });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "AdversarialRobustness");
  assert.equal(allow.composedLipschitz, 2);
  assert.ok(allow.epsilon2 <= allow.maxEpsilon);
  assertLeanAnchor(allow);

  const deny = gate({ lipschitz1: 2, lipschitz2: 2, delta: 0.2 });
  assert.equal(deny.allow, false);
  assert.throws(() => gate({ lipschitz1: 0, lipschitz2: 1, delta: 0.1 }), /lipschitz1/);
}

{
  const gate = summationInvariantGate();
  const allow = gate({
    khipuId: "khipu-demo",
    primaryCord: 15,
    organs: [
      { organId: "heart", decisions: [{ decisionId: "d1", value: 4 }, { decisionId: "d2", value: 6 }] },
      { organId: "brain", decisions: [{ decisionId: "d3", value: 5 }] },
    ],
  });
  assert.equal(allow.allow, true);
  assert.equal(allow.formula, "SummationInvariant");
  assert.equal(allow.computedTotal, 15);
  assert.equal(allow.delta, 0);
  assertLeanAnchor(allow);

  const deny = gate({
    khipuId: "khipu-tampered",
    primaryCord: 14,
    organs: [{ organId: "heart", decisions: [{ decisionId: "d1", value: 15 }] }],
  });
  assert.equal(deny.allow, false);
  assert.equal(deny.delta, 1);
  assert.throws(() => gate({ khipuId: "bad", primaryCord: 0, organs: null as never }), /organs must be an array/);
}

console.log("[policy-gates] OK 5 gates / 22 assertions + receipt emission");
