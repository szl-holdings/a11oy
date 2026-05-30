import { strict as assert } from "node:assert";
import { ALL_THEOREMS, getNewTheorem, getTheorem, MATH_POD_THEOREMS, NEW_THEOREMS } from "./theorems.ts";

assert.equal(NEW_THEOREMS.length, 3);
assert.ok(MATH_POD_THEOREMS.length >= 4);
assert.equal(ALL_THEOREMS.length, NEW_THEOREMS.length + MATH_POD_THEOREMS.length);

assert.equal(getNewTheorem("TH1")?.name, "composability");
assert.equal(getNewTheorem("TH4"), undefined);
assert.equal(getTheorem("TH4")?.name, "lambda_category_composability");
assert.equal(getTheorem("TH6")?.maturity, "proven");
assert.equal(getTheorem("TH7")?.name, "curry_howard_receipt_calculus");
assert.equal(getTheorem("TH-DOES-NOT-EXIST"), undefined);

console.log("[a11oy-knowledge] OK theorem lookup covers TH1-TH7");
