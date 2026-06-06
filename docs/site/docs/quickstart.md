# Quickstart — five minutes to your first call

This page gets you from zero to a verifiable result against each of the five flagships.
Everything here is **real** — the endpoints, repos, and commands all exist today. Where a
piece is not yet end-to-end wired, it is labelled **in development** with an honest note.

::: tip Prerequisites
- **Node 18+** and **pnpm** for the TypeScript fabric repos (a11oy, amaru, rosie, sentra).
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
at tag `lutar-v18.0.0`. The corpus is living; see [Evidence](/evidence/) for the
single source of truth and the live snapshot.

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

## 2 · amaru — mint a provenance receipt

`amaru` anchors governance receipts. Convergence of its append-only sync is guaranteed by a
Banach contraction; provenance hashes are Shor-9-qubit encoded before anchoring.

```sh
git clone https://github.com/szl-holdings/amaru.git && cd amaru
pnpm install && pnpm test
```

```ts
import { mintReceipt } from '@szl/amaru'

const receipt = mintReceipt({
  payload: { decisionId: 'd-001', value: 1 },
  // anchor: 'cardano' is in development for mainnet; local Merkle anchoring is live
})
console.log(receipt.sha256, receipt.lamport)
```

::: warning In development
Cardano **mainnet** anchoring is in development (target: Series-A milestone). The local
append-only delta log, Shor encoding, and Lamport ordering are live today.
:::

## 3 · sentra — score posture drift

`sentra` models cyber posture as a Kitaev surface and scores topological drift from the
ground state.

```bash
git clone https://github.com/szl-holdings/sentra.git && cd sentra
pnpm install && pnpm test
```

```ts
import { driftScore } from '@szl/sentra'

const report = driftScore({ baseline: surfaceA, observed: surfaceB })
console.log(report.stability, report.events)
// drift events ranked by CVSS-weighted severity; remediation passes the Covenant gate
```

## 4 · killinchu — decode a Remote-ID frame

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
**unauthenticated and spoofable**. Malformed input returns an honest error, never a silent pass.
:::

## 5 · rosie — verify a receipt-DAG invariant

`rosie` ships the Khipu-indexed receipt DAG. Its summation invariant
`rootValue = Σ pendantValues = Σ Σ decisionValues` is formally verified in `lutar-lean`.

```bash
git clone https://github.com/szl-holdings/rosie.git && cd rosie
pnpm install && pnpm test   # 10 runtime tests incl. TH11 failure modes
```

```ts
import { KhipuRoot, verifySumInvariant } from './src/khipu-receipt'

const root = KhipuRoot.from(organReceipts)
console.log(verifySumInvariant(root)) // true ⇔ sum-of-sums holds end to end
```

## Next steps

- **[The 12 organs](/anatomy/)** — formula-by-formula breakdown.
- **[SDKs](/sdks/)** — `szl-python` and `szl-ts` unified clients (in development).
- **[Cookbook](/cookbook/)** — runnable, Lean-backed recipes.
- **[API Reference](/api/)** — endpoint tables, OpenAPI when published.
