# Ouroboros governed-loop ablation

This directory contains a preregistered local benchmark for the production
A11oy governed agent loop. It asks a narrow question: which loop stages add
observable governance evidence on four fixed proposal scenarios?

The benchmark measures policy-decision agreement, bounded execution,
hash-chain integrity, self-feed continuity, mutation detection, and the number
of iterations used by the advisory stop. It does not measure task accuracy,
model quality, real-world outcomes, energy, or mathematical convergence.

The no-gate, no-self-feed, and no-verifier variants are offline negative
controls. They never execute an external action and are not production routes.
The production gate is never disabled by this benchmark.

Run the protocol with:

```text
python scripts/run_ouroboros_ablation.py
```

The runner writes a content-addressed JSON receipt beside the protocol. Commit
the protocol before generating a release receipt so the receipt can name the
exact preregistration commit.
