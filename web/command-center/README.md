# a11oy Command Center — web surface

Product origin: **https://a-11-oy.com**  
Proof registry: **https://a11oy.net** (do not host this package there)  
Runtime Space: **https://szlholdings-a11oy.hf.space** (Python flagship — do not replace)

This folder is the inspectable Command Center / public estate UI:

- Homepage with honesty doctrine v11
- `/console` — one pane of glass (health, Λ, receipts, locked-8, P1–P6)
- `/frontiers` — shipped vs replica vs conjecture vs roadmap
- Superpowers, Formulas, Evidence, Observability, Wires, Mesh, IMMUNE, Verify

It is **not** a second flagship. It is **not** the Python runtime. It must
**not** overwrite `web/` root, `console/`, `a11oy_landing.html`, or the
HF Dockerfile at repo root.

Λ is Conjecture 1 — advisory, never a theorem, never 1.0, never rendered as
proven-green. Signer state is UNSIGNED-honest unless an independent verify
passes. Energy is UNAVAILABLE without a live exporter delta.

## Run

```bash
cd web/command-center
npm install
npm test
npm run dev
```

Build:

```bash
npm run build
```

GitHub Pages / a-11-oy.com DNS is **not** flipped by this folder.

## Honesty

- MEASURED — read this session
- REPORTED — named source, not re-derived here
- UNKNOWN / UNAVAILABLE — not invented
- CONJECTURE — gray, never a theorem
