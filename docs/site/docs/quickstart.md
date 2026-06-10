# Quickstart — five minutes to your first call

This page gets you from zero to a verifiable result against the **two shipping flagships**,
a11oy and killinchu. Everything in those sections is **real** — the endpoints, repos, and
commands all exist today. The Provenance Anchor, Operator, and Policy roles (internal
codenames *amaru*, *rosie*, *sentra* — retired) are **roadmap/frontier** and are documented
honestly below; they are not yet released as cloneable repos or published packages.

::: tip Prerequisites
- **Node 18+** and **pnpm** for the a11oy TypeScript fabric.
- **Python 3.11+** for killinchu and the math/receipt tooling.
- A clone of the relevant repo from [`github.com/szl-holdings`](https://github.com/szl-holdings).
:::

## 0 · Verify the corpus (30 seconds)

Before trusting any number on this site, reproduce the canonical Lean figures yourself.
This is the Doctrine v11 honesty rule — **regenerate, don't trust**:

```bash
gh repo clone szl-holdings/lutar-lean /tmp/lutar -- --depth 1
cd /tmp/lutar
DECL=$(grep -rE '^(theorem|lemma|def|abbrev|axiom) ' --include='*.lean' Lutar/ | wc -l)
AXIOM_UNIQ=$(grep -rhE '^axiom ' --include='*.lean' Lutar/ | awk '{print $2}' | sort -u | wc -l)
SORRY=$(grep -rE '\bsorry\b' --include='*.lean' Lutar/ | wc -l)
echo "Lean: $DECL declarations / $AXIOM_UNIQ unique axioms / $SORRY sorries"
```

The Doctrine v11 LOCKED snapshot is <span class="locked">749 declarations</span> /
<span class="locked">14 unique axioms</span> / <span class="locked">163 sorries</span>
at tag `lutar-v18.0.0`, kernel `c7c0ba17`. The corpus is living; see [Evidence](/evidence/)
for the single source of truth and the live snapshot. Note: exactly **8** formulas are
locked-proven {F1, F4, F7, F11, F12, F18, F19, F22}; Λ unconditional is **Conjecture 1** (machine-checked
false, never a theorem); the conditional Λ result is axiom-free PROVEN (Wave 22); Khipu BFT
is **Conjecture 2** (Wave 23 `khipu_quorum_safety_conditional` is conditional-only).

## 1 · a11oy — evaluate a policy gate

`a11oy` is the governed execution fabric. The fastest first call is the Covenant Policy
engine deciding whether an action may proceed.

```bash
git clone https://github.com/szl-holdings/a11oy.git && cd a11oy
pnpm install && pnpm build
```

```ts
import { CovenantPolicy } from '@szl/a11oy-policy'

const policy = new CovenantPolicy()
const decision = policy.evaluate({
  action: 'deploy',
  axes: { moralGrounding: 0.97, measurabilityHonesty: 0.96 /* ...13 axes */ },
})

console.log(decision.passed, decision.continuumHash)
// → false unless all 13 axes clear their floors (conjunctive AND, no compensation)
```

You can also hit the live Space directly:

```bash
curl -s https://szlholdings-a11oy.hf.space/healthz | jq .   # → doctrine v11 · 749/14/163
```

## 2 · killinchu — decode a Remote-ID frame

`killinchu` is the drone-intelligence flagship. The honest counter-UAS path: decode a real
broadcast self-ID, run the haversine geofence + 13-axis Λ-gate, emit a Khipu receipt.

```bash
# Against the live Space API (no install needed)
curl -s https://szlholdings-killinchu.hf.space/api/killinchu/v1/honest | jq .

curl -s -X POST https://szlholdings-killinchu.hf.space/api/killinchu/v1/remote-id/decode \
  -H 'content-type: application/json' \
  -d '{"hex":"0d01..."}' | jq .
```

::: tip Honest by construction
`GET /api/killinchu/v1/honest` returns the Doctrine v11 disclosure as JSON: Λ is a
**Conjecture**, DSSE signatures are **PLACEHOLDER**, broadcast Remote-ID/ADS-B/MAVLink are
**unauthenticated and spoofable**, and the effector path is a **command demonstration,
simulated**. Malformed input returns an honest error, never a silent pass.
:::

## Roadmap roles (not yet released)

The following roles are on the roadmap. They are **not** cloneable repos or published
packages today — the commands and imports below describe the intended shape, not a current
release. See [Flagships](/flagships/) for honest status.

- **Provenance Anchor** *(internal codename amaru, retired)* — append-only governance-receipt
  sync with a Banach-contraction convergence bound; Cardano mainnet anchoring is **in
  development**. Local Merkle anchoring is the live primitive inside a11oy today.
- **Operator** *(internal codename rosie, retired)* — Khipu-indexed receipt-DAG console. Its
  summation invariant `rootValue = Σ pendantValues = Σ Σ decisionValues` is formally verified
  in `lutar-lean`; the standalone console is roadmap.
- **Policy** *(internal codename sentra, retired)* — Kitaev-surface posture-drift detector.
  Roadmap cyber-resilience pack; the live policy gate ships inside a11oy.

## Next steps

- **[The 12 organs](/anatomy/)** — formula-by-formula breakdown.
- **[SDKs](/sdks/)** — `szl-python` and `szl-ts` unified clients (in development).
- **[Cookbook](/cookbook/)** — runnable, Lean-backed recipes.
- **[API Reference](/api/)** — endpoint tables, OpenAPI when published.
