# a11oy Restraint — benchmark (Ponytail methodology, our measurements)

Two arms — **no-skill baseline** vs **a11oy-restraint** — over the same five
everyday tasks Ponytail uses (email validator, JS debounce, CSV sum, React
countdown, FastAPI rate-limit). Code LOC is counted from fenced code blocks;
tokens and latency come from the API. Median reported.

## Honesty labels (Doctrine v11)

- **MEASURED** — printed ONLY for a run we actually executed on our stack.
- **SAMPLE** — an illustrative fixture derived from our ladder model (the
  `/api/a11oy/v1/restraint/bench` endpoint returns this when no model run is
  wired on the Space).
- **ROADMAP** — the overall bench label until a real run is wired.

We **never** reprint Ponytail's published numbers as ours.

## Reproduce

```bash
cp ../../.env.example ../../.env     # add your model key
npx promptfoo@latest eval -c benchmarks/restraint/promptfooconfig.yaml --repeat 10
npx promptfoo@latest view
```

Once a run completes, paste the measured medians into a `results/` file and the
UI/endpoint can surface them as **MEASURED** for that run only.

## Citation (Ponytail, MIT)

a11oy Restraint **adopts** the 6-rung ladder and the lite/full/ultra intensity
levels from the open-source **Ponytail** coding-agent skill
(<https://github.com/DietrichGebert/ponytail>, MIT, © 2026 DietrichGebert) —
**adopted + governed, not invented here**. Ponytail's published results
(80–94% less code, 47–77% cheaper, 3–6× faster; median of 10 runs across
Haiku/Sonnet/Opus) are **cited as Ponytail's**, never claimed as ours. Our
contribution is the governance (signed DSSE receipts + advisory Λ), the
measured-on-our-stack benchmark, and the J/token energy tie-in.
