# Wave 26 — Lambda-AttnRes and Governed Delta Workspace

Status: **MODELED**

Claim boundary: auditability and executable contracts only

## Delivered surface

Wave 26 adds a Python research organ under
`web/packages/a11oy-core/py/szl_gdw` and zero-sorry structural Lean hooks
under the repository's canonical `proofs/lutar-lean/Lutar` package.

The implementation corrects the draft payload's executable gaps:

- summary matrices are validated as `(number_of_summaries, query_width)`;
- retention and learning-rate validation is complete;
- lambda values of zero and one are exact fixed endpoints;
- rational rows close exactly in `ℚ`;
- certificate scoring uses one declared float16-quantized surface for
  float32/float16 input identity;
- callers' workspace states are immutable;
- proposal and receipt identities are content hashes rather than process IDs;
- a stale parent is rejected before policy execution;
- accepted transitions must advance exactly one step; and
- replay detects both record tampering and state-continuity drift.

The package-local API is intentionally standalone. A GET reports capability
metadata without minting a receipt. A POST evaluates a proposed state change
through the supplied kernel and produces a deterministic hash receipt. This
wave does not mount a new production route, change the existing GDW durability
contract, or create a signed Khipu receipt.

## Prior art boundary

The organ is independently implemented and cites, rather than claims,
the following prior art:

- [Kimi K3](https://arxiv.org/abs/2607.24653)
- [Attention Residuals](https://arxiv.org/abs/2603.15031)
- [official Attention Residuals repository](https://github.com/MoonshotAI/Attention-Residuals)
- [Kimi Linear / Kimi Delta Attention](https://arxiv.org/abs/2510.26692)
- [Gated Delta Networks](https://arxiv.org/abs/2412.06464)
- [Hyper-Connections](https://arxiv.org/abs/2409.19606)
- [TorchLean](https://arxiv.org/abs/2602.22631)

Attention Residuals motivates learned selection over model depth. KDA and
Gated DeltaNet motivate sequence-memory update rules. TorchLean motivates
closing the semantic gap between executable operators and formal statements.
Wave 26 combines none of their weights, training results, or implementation
claims.

## Claim-upgrade gate

The capability remains MODELED until a separate evaluation supplies all of:

1. three or more compute budgets;
2. matched model dimensions, tokens, data, optimizer, and hardware;
3. standard residual, Block AttnRes, and Lambda-AttnRes arms;
4. validation loss versus tokens and FLOPs;
5. seeds, configuration hashes, source commits, and raw artifacts; and
6. an independent review of any proposed wording change.

The empty evidence ledger at
`docs/evidence/wave26/lambda_attnres_loss_curves.json` is deliberately marked
`UNAVAILABLE`; it is not sample performance data.

## Honest limitations

> Governed Delta Workspace and Λ-AttnRes are **MODELED** orchestration and
> tensor-layer architectures inspired by Kimi K3, Kimi Linear, Attention
> Residuals, DeltaNet, and related work. They operate over explicit agent
> outputs, receipts, and stored representations. They do **not** reproduce
> Kimi K3’s weights, do **not** read proprietary model activations or J-space,
> and do **not** currently have loss or scaling-efficiency evidence beyond
> small-scale experiments. All numerical behavior and claims are subject to
> revision as empirical data accumulates.
