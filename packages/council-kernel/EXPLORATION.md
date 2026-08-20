# Counterfactual branch market

The branch market lets multiple bounded hypotheses compete without granting any branch merge, deployment, or promotion authority.

## Admission

Each `BranchCandidate` binds:

- the exact parent Council decision;
- an immutable patch digest;
- proposer identity and trust domain;
- estimated cost;
- expected value and residual risk;
- evidence references.

Admission applies branch-count, per-branch cost, total-cost, evidence, risk, and parent-decision gates. A passing branch enters `QUARANTINED`; a failing branch is `BLOCKED` and does not reserve budget.

## Evaluation

A `BranchEvaluation` binds the exact candidate digest, independent evaluator, evaluation source digest, verifier score, test pass rate, static and policy status, counterexamples, and typed findings.

The evaluator trust domain must differ from the proposer trust domain when independence is required. High and critical findings block by default. A branch becomes `ELIGIBLE` only after every configured gate passes.

## Recommendation

Eligible branches are ranked deterministically using verifier score, tests, expected value, risk, cost efficiency, evidence completeness, and counterexample coverage. Tie-breaking uses cost and content digest.

A recommendation always contains:

```json
{
  "promotion_authorized": false
}
```

The market can recommend one or more branches to a later governed promotion process. It contains no merge, deployment, provider mutation, secret access, or model-promotion function.
