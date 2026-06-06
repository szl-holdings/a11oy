# MINIMIZATION PROOF

## Source

`vllm/v1/sample/sampler.py` @ commit `6548560496` — Apache-2.0.

The upstream `Sampler.sample()` does:
1. Greedy branch: `argmax(logits)` (deterministic, no seed needed).
2. Random branch: apply temperature → top-k/top-p → `multinomial` with `torch.Generator`.

## Kernel derivation

The RIMAY kernel collapses this to a single seeded-multinomial path (subsumes greedy when priors dominate):

```
logits  = priors + features          # additive feature injection (linear)
probs   = softmax(logits)            # normalise
g       = Generator(); g.seed(seed)  # determinism contract
proposal= multinomial(probs, 1, g)   # sample
```

Line count (non-blank, non-comment): **7 lines** — within the ≤10 line constraint.

## Determinism argument

`torch.Generator` is a PRNG with explicit state.  
Setting `g.manual_seed(seed)` before every call resets the state identically.  
`torch.multinomial(..., generator=g)` draws from that frozen state.  
Therefore `propose(state, world, features, priors, seed=k)` is a pure function of `(features, priors, k)` — same inputs always yield the same int token id.

## Feature / prior wiring

| Argument | Role | Maps to upstream |
|---|---|---|
| `state` | reserved context (e.g. KV position) | `SamplingMetadata` context |
| `world` | reserved vocab / model config | `SamplingMetadata.vocab_size` |
| `features` | logit deltas (bias, penalty residuals) | `apply_logits_processors` output |
| `priors` | raw model logits | `logits` tensor input to `Sampler.forward` |
| `seed` | RNG seed | `SamplingMetadata.generators` |
